"""
夸克网盘 API 服务
实现夸克网盘链接的转存（保存到自己网盘）和二次分享生成新链接功能。
"""

import asyncio
from datetime import datetime
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

from config import QUARK_COOKIE
from services.link_parser import extract_share_id

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Content-Type": "application/json",
    "Referer": "https://pan.quark.cn/",
    "Origin": "https://pan.quark.cn",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class QuarkPanService:
    """夸克网盘操作服务类"""

    def __init__(self, cookie: Optional[str] = None):
        self.cookie = cookie or QUARK_COOKIE

    def _get_headers(self) -> Dict[str, str]:
        headers = BASE_HEADERS.copy()
        if self.cookie:
            c = self.cookie.strip()
            # 移除用户从 DevTools 复制时可能带上的 'Cookie:' 标签
            if c.lower().startswith("cookie:"):
                c = c[7:].strip()
            # 替换所有的换行符为分号或空格
            c = c.replace("\r\n", "; ").replace("\n", "; ").replace("\r", "; ")
            headers["Cookie"] = c
        return headers

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000)

    async def get_share_token(self, share_url: str, passcode: str = "") -> Tuple[str, str]:
        """
        获取分享链接的访问令牌 (stoken) 及分享 ID (pwd_id)

        :param share_url: 夸克分享链接或分享码
        :param passcode: 提取码（如有）
        :return: (pwd_id, stoken)
        """
        pwd_id = extract_share_id(share_url) or share_url.strip()
        if not pwd_id:
            raise ValueError(f"无法从链接中解析出有效的夸克分享 ID: {share_url}")

        ts = self._get_timestamp()
        url = f"https://drive-h.quark.cn/1/clouddrive/share/sharepage/token?pr=ucpro&fr=pc&uc_param_str=&__dt=200&__t={ts}"
        payload = {
            "pwd_id": pwd_id,
            "passcode": passcode
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._get_headers())
            try:
                result = response.json()
            except Exception:
                result = {}

            if response.status_code != 200 or result.get("code") != 0:
                code = result.get("code")
                msg = result.get("message") or response.text
                if code == 41004 or "不存在" in str(msg) or "失效" in str(msg):
                    raise RuntimeError(f"夸克网盘分享链接已失效或文件已被原作者删除 (错误码: {code})")
                elif code == 41002 or "提取码" in str(msg):
                    raise RuntimeError(f"夸克网盘提取码不正确，请核对后重试")
                raise RuntimeError(f"获取夸克分享 Token 失败: {msg} (HTTP {response.status_code}, 错误码: {code})")

            stoken = result.get("data", {}).get("stoken")
            if not stoken:
                raise RuntimeError(f"返回数据中缺失 stoken: {result}")

            return pwd_id, stoken

    async def get_file_list(
        self,
        pwd_id: str,
        stoken: str,
        pdir_fid: str = "0",
        page: int = 1,
        size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取分享目录下的文件列表

        :param pwd_id: 分享 ID
        :param stoken: 访问令牌
        :param pdir_fid: 父目录 ID，默认根目录 "0"
        :param page: 页码
        :param size: 单页大小
        :return: 文件信息列表
        """
        ts = self._get_timestamp()
        url = f"https://drive-h.quark.cn/1/clouddrive/share/sharepage/detail?pr=ucpro&fr=pc&uc_param_str=&__dt=200&__t={ts}"
        payload = {
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": pdir_fid,
            "force": 0,
            "_page": page,
            "_size": size,
            "_sort": "file_type:asc,updated_at:desc"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 夸克目前 detail 接口必须使用 GET 请求
            response = await client.get(url, params=payload, headers=self._get_headers())
            if response.status_code != 200:
                # 容错尝试 POST
                response = await client.post(url, json=payload, headers=self._get_headers())

            if response.status_code != 200:
                raise RuntimeError(f"获取分享文件列表失败 (HTTP {response.status_code}): {response.text}")

            result = response.json()
            if result.get("code") != 0:
                msg = result.get("message", "未知错误")
                raise RuntimeError(f"获取分享文件列表失败: {msg} (错误码: {result.get('code')})")

            file_list = result.get("data", {}).get("list", [])
            return file_list

    async def _wait_for_task(self, task_id: str, max_retries: int = 10, interval: float = 1.0) -> Dict[str, Any]:
        """
        轮询异步转存任务状态
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(max_retries):
                ts = self._get_timestamp()
                url = f"https://drive-h.quark.cn/1/clouddrive/task?pr=ucpro&fr=pc&task_id={task_id}&__dt=200&__t={ts}"
                res = await client.get(url, headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    task_data = data.get("data", {})
                    status = task_data.get("status")
                    # 2 表示成功完成
                    if status == 2:
                        return task_data
                    elif status in (3, 4):  # 失败状态
                        raise RuntimeError(f"夸克转存任务执行失败: {task_data.get('message', '未知错误')}")
                await asyncio.sleep(interval)
        return {}

    async def save_files(
        self,
        pwd_id: str,
        stoken: str,
        fid_list: List[str],
        fid_token_list: List[str],
        to_pdir_fid: str = "0"
    ) -> List[str]:
        """
        转存文件到自己的网盘

        :param pwd_id: 分享 ID
        :param stoken: 访问令牌
        :param fid_list: 待保存的文件 fid 列表
        :param fid_token_list: 文件对应的 share_fid_token 列表
        :param to_pdir_fid: 保存目标文件夹 ID，默认根目录 "0"
        :return: 保存成功后在自己网盘中的 fid 列表
        """
        if not self.cookie:
            raise ValueError("未配置夸克网盘 Cookie，无法转存。请在 .env 中设置 QUARK_COOKIE")

        ts = self._get_timestamp()
        url = f"https://drive-h.quark.cn/1/clouddrive/share/sharepage/save?pr=ucpro&fr=pc&uc_param_str=&__dt=200&__t={ts}"
        payload = {
            "pwd_id": pwd_id,
            "stoken": stoken,
            "fid_list": fid_list,
            "fid_token_list": fid_token_list,
            "to_pdir_fid": to_pdir_fid
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._get_headers())
            if response.status_code == 401 or '"code":31001' in response.text:
                raise RuntimeError("夸克网盘 Cookie 无效或不完整（缺少登录身份凭据）。注意：核心登录凭据（如 __pus、b-user-id）受浏览器 HttpOnly 保护，无法通过控制台 document.cookie 获取；必须从 F12 Network 列表里点击一个请求，在右侧 Request Headers 复制完整的 Cookie。")
            if response.status_code != 200:
                raise RuntimeError(f"文件转存请求失败 (HTTP {response.status_code}): {response.text}")

            result = response.json()
            if result.get("code") != 0:
                msg = result.get("message", "未知错误")
                raise RuntimeError(f"文件转存失败: {msg} (错误码: {result.get('code')})")

            data = result.get("data", {})
            task_id = data.get("task_id")
            logger.info(f"夸克 save 请求返回: task_id={task_id}, data={data}")

            save_as = data.get("save_as") or {}
            new_fids = (
                save_as.get("save_as_top_fids")
                or data.get("save_as_top_fids")
                or save_as.get("fids")
                or data.get("fids")
                or []
            )

            # 如果有异步任务ID，等待任务完成
            if task_id:
                task_res = await self._wait_for_task(task_id)
                logger.info(f"夸克 task 任务完成返回: task_res={task_res}")
                task_save_as = task_res.get("save_as") or {}
                top_fids = (
                    task_save_as.get("save_as_top_fids")
                    or task_res.get("save_as_top_fids")
                    or task_save_as.get("fids")
                    or task_res.get("fids")
                    or task_save_as.get("top_fids")
                    or task_save_as.get("save_as_fids")
                    or []
                )
                if top_fids:
                    new_fids = top_fids

            return new_fids

    async def get_personal_file_list(
        self,
        pdir_fid: str = "0",
        page: int = 1,
        size: int = 20
    ) -> List[Dict[str, Any]]:
        """获取个人网盘指定目录下的文件列表（默认根目录按最新更新时间排序）"""
        if not self.cookie:
            return []
        ts = self._get_timestamp()
        url = f"https://drive-h.quark.cn/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid={pdir_fid}&_page={page}&_size={size}&_sort=file_type:asc,updated_at:desc&__dt=200&__t={ts}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url, headers=self._get_headers())
            if res.status_code != 200:
                url_pc = f"https://drive-pc.quark.cn/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid={pdir_fid}&_page={page}&_size={size}&_sort=file_type:asc,updated_at:desc&__dt=200&__t={ts}"
                res = await client.get(url_pc, headers=self._get_headers())
            if res.status_code == 200:
                d = res.json()
                return d.get("data", {}).get("list", [])
        return []

    async def get_or_create_folder(self, pdir_fid: str, folder_name: str) -> str:
        """
        在指定父目录(pdir_fid)下查找或创建文件夹，并返回该文件夹的 fid
        """
        if not self.cookie:
            return "0"

        folder_name = folder_name.strip()
        # 1. 先检查父目录下是否已经存在同名文件夹
        existing_files = await self.get_personal_file_list(pdir_fid=pdir_fid, size=50)
        for f in existing_files:
            if f.get("file_name") == folder_name and (f.get("dir") is True or f.get("file_type") == 0):
                logger.info(f"父目录 {pdir_fid} 下已存在文件夹: {folder_name} (fid={f['fid']})")
                return f["fid"]

        # 2. 如果不存在，调用接口创建文件夹
        ts = self._get_timestamp()
        url = f"https://drive-h.quark.cn/1/clouddrive/file?pr=ucpro&fr=pc&uc_param_str=&__dt=200&__t={ts}"
        payload = {
            "pdir_fid": pdir_fid,
            "file_name": folder_name,
            "dir_path": "",
            "dir_init_lock": False
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=self._get_headers())
            if resp.status_code != 200:
                # 尝试 drive-pc 域名
                url_pc = f"https://drive-pc.quark.cn/1/clouddrive/file?pr=ucpro&fr=pc&uc_param_str=&__dt=200&__t={ts}"
                resp = await client.post(url_pc, json=payload, headers=self._get_headers())

            if resp.status_code == 200:
                res_json = resp.json()
                if res_json.get("code") == 0:
                    new_fid = res_json.get("data", {}).get("fid")
                    if new_fid:
                        logger.info(f"成功创建文件夹: {folder_name} (fid={new_fid})")
                        return new_fid

        # 3. 兜底重新刷新父目录列表匹配
        refreshed_files = await self.get_personal_file_list(pdir_fid=pdir_fid, size=50)
        for f in refreshed_files:
            if f.get("file_name") == folder_name:
                return f["fid"]

        return pdir_fid

    async def get_or_create_date_path(self) -> str:
        """
        按照 年 -> 月 -> 日 规则层级创建文件夹并返回今日最终存放目录的 fid
        规则示例：2026 -> 10月 -> 10月12日
        """
        now = datetime.now()
        year_str = f"{now.year}"
        month_str = f"{now.month}月"
        day_str = f"{now.month}月{now.day}日"

        logger.info(f"准备按日期层级归档目录: {year_str} / {month_str} / {day_str}")

        # 1. 根目录下创建/获取 年份 文件夹 (如 2026)
        year_fid = await self.get_or_create_folder("0", year_str)
        # 2. 年份目录下创建/获取 月份 文件夹 (如 10月)
        month_fid = await self.get_or_create_folder(year_fid, month_str)
        # 3. 月份目录下创建/获取 日期 文件夹 (如 10月12日)
        day_fid = await self.get_or_create_folder(month_fid, day_str)

        logger.info(f"日期归档目标目录就绪: {year_str}/{month_str}/{day_str} (target_fid={day_fid})")
        return day_fid

    async def create_share(
        self,
        fid_list: List[str],
        title: str = "夸克分享文件",
        url_type: int = 1,
        expired_type: int = 1,
        expire_time: int = 0
    ) -> Dict[str, Any]:
        """
        对已转存到自己网盘的文件创建新的分享链接

        :param fid_list: 要分享的文件 fid 列表（必须是个人网盘中的 fid）
        :param title: 分享标题
        :param url_type: 链接类型 (1: 默认公开链接)
        :param expired_type: 过期时间类型 (1: 永久有效)
        :param expire_time: 有效期（秒），0 表示永久
        :return: 包含 share_url, pwd_id, passcode 等字段的字典
        """
        if not self.cookie:
            raise ValueError("未配置夸克网盘 Cookie，无法创建分享。请在设置中配置夸克 Cookie")

        ts = self._get_timestamp()
        url = f"https://drive-pc.quark.cn/1/clouddrive/share?pr=ucpro&fr=pc&uc_param_str=&__dt=200&__t={ts}"
        payload = {
            "title": title,
            "fid_list": fid_list,
            "url_type": url_type,
            "expired_type": expired_type,
            "expire_time": expire_time
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._get_headers())
            if response.status_code != 200:
                url_h = f"https://drive-h.quark.cn/1/clouddrive/share?pr=ucpro&fr=pc&uc_param_str=&__dt=200&__t={ts}"
                response = await client.post(url_h, json=payload, headers=self._get_headers())

            if response.status_code != 200:
                raise RuntimeError(f"创建分享链接请求失败 (HTTP {response.status_code}): {response.text}")

            result = response.json()
            logger.info(f"夸克 create_share API 响应: {result}")
            if result.get("code") != 0:
                msg = result.get("message", "未知错误")
                raise RuntimeError(f"创建分享链接失败: {msg} (错误码: {result.get('code')})")

            data = result.get("data", {})
            share_id = None

            # 1. 检查是否为同步任务响应
            task_sync = data.get("task_sync")
            if task_sync:
                task_resp = data.get("task_resp", {})
                if task_resp.get("code") == 0:
                    resp_data = task_resp.get("data", {})
                    share_id = resp_data.get("share_id") or resp_data.get("pwd_id")
                else:
                    logger.warning(f"同步创建分享 task_resp 返回异常: {task_resp}")

            # 2. 如果未获取到 share_id，检查是否有异步 task_id
            if not share_id:
                task_id = data.get("task_id")
                if task_id:
                    logger.info(f"分享创建为异步任务，task_id={task_id}，等待任务完成...")
                    task_res = await self._wait_for_task(task_id)
                    share_id = (
                        task_res.get("share_id")
                        or task_res.get("pwd_id")
                        or task_res.get("data", {}).get("share_id")
                        or task_res.get("data", {}).get("pwd_id")
                    )

            # 3. 兜底检查 data 顶级字段
            if not share_id:
                share_id = data.get("share_id") or data.get("pwd_id") or data.get("shareid")

            if not share_id:
                raise RuntimeError(f"夸克创建分享成功，但未能解析到分享 share_id，返回数据: {result}")

            logger.info(f"成功获取到夸克新分享 share_id: {share_id}")

            # 4. 调用 clouddrive/share/password 获取完整分享链接和提取码（如有）
            share_url = None
            passcode = ""
            pwd_url = f"https://drive-pc.quark.cn/1/clouddrive/share/password?pr=ucpro&fr=pc&uc_param_str=&__dt=200&__t={ts}"
            pwd_payload = {"share_id": share_id}

            try:
                pwd_res = await client.post(pwd_url, json=pwd_payload, headers=self._get_headers())
                if pwd_res.status_code == 200:
                    pwd_data = pwd_res.json()
                    logger.info(f"夸克 share/password API 响应: {pwd_data}")
                    if pwd_data.get("code") == 0:
                        pwd_detail = pwd_data.get("data", {})
                        share_url = pwd_detail.get("share_url") or pwd_detail.get("url")
                        passcode = pwd_detail.get("share_pwd", "") or pwd_detail.get("passcode", "")
            except Exception as e:
                logger.warning(f"获取分享密码详情接口失败: {e}")

            # 5. 如果 share_url 未取到，直接通过 share_id 构造标准的夸克分享链接
            if not share_url:
                share_url = f"https://pan.quark.cn/s/{share_id}"

            return {
                "share_url": share_url,
                "pwd_id": share_id,
                "passcode": passcode,
                "title": title,
                "raw_data": data
            }

    async def transfer_and_reshare(
        self,
        share_url: str,
        passcode: str = "",
        custom_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        完整流程：解析链接 → 获取详情 → 按 年/月/日 规则归档目录 → 转存至对应日期目录 → 创建新分享链接

        :param share_url: 原始夸克分享链接
        :param passcode: 原始提取码（如有）
        :param custom_title: 新分享标题（可选）
        :return: 包含新链接与文件信息的完整响应
        """
        logger.info(f"开始处理夸克网盘转存分享流程: {share_url}")

        # 1. 获取分享访问凭证
        pwd_id, stoken = await self.get_share_token(share_url, passcode)
        logger.info(f"成功获取分享 Token: pwd_id={pwd_id}")

        # 2. 获取分享文件列表
        files = await self.get_file_list(pwd_id, stoken)
        if not files:
            raise RuntimeError("分享链接中未找到任何文件或分享已失效")

        fid_list = [f["fid"] for f in files if "fid" in f]
        fid_token_list = [f.get("share_fid_token", "") for f in files if "fid" in f]

        if not fid_list:
            raise RuntimeError("未解析到有效的文件 ID 列表")

        # 确定新分享标题（默认使用第一个文件名）
        first_file_name = files[0].get("file_name", "分享文件")
        share_title = custom_title or f"{first_file_name}"

        # 3. 按日期规则创建分类文件夹：年 -> 月 -> 日 (如 2026 / 10月 / 10月12日)
        target_dir_fid = await self.get_or_create_date_path()

        # 4. 转存文件到个人网盘的日期归档目录中
        logger.info(f"正在转存文件到日期归档目录 (to_pdir_fid={target_dir_fid})，文件数量: {len(fid_list)}")
        saved_fids = await self.save_files(pwd_id, stoken, fid_list, fid_token_list, to_pdir_fid=target_dir_fid)

        # 5. 确保拿到用户个人网盘中的真实 fid（多层兜底保障）
        if not saved_fids or saved_fids == fid_list:
            logger.info("saved_fids 与原始分享 fid 相同或为空，启动日期归档目录扫描匹配真实 fid...")
            matched_fids = []
            target_names = {f.get("file_name", "").strip() for f in files if f.get("file_name")}

            for retry in range(3):
                personal_files = await self.get_personal_file_list(pdir_fid=target_dir_fid, size=50)
                if personal_files:
                    for pf in personal_files:
                        pf_name = pf.get("file_name", "").strip()
                        if pf_name in target_names or any(tn in pf_name or pf_name in tn for tn in target_names):
                            matched_fids.append(pf["fid"])
                    if not matched_fids:
                        # 兜底取最新转存的文件
                        matched_fids = [personal_files[0]["fid"]]
                    break
                await asyncio.sleep(1.0)

            if matched_fids:
                saved_fids = matched_fids
            else:
                raise RuntimeError("文件已转存到个人网盘日期归档目录，但未能定位到新生成的文件 ID，无法创建专属分享链接。")

        # 6. 创建属于用户自己的新分享链接（永久有效: expired_type=1, expire_time=0）
        logger.info(f"转存完成，正在创建用户个人专属分享链接（永久有效）: fids={saved_fids}")
        share_result = await self.create_share(
            saved_fids,
            title=share_title,
            url_type=1,
            expired_type=1,
            expire_time=0
        )
        new_share_url = share_result.get("share_url")
        if not new_share_url:
            raise RuntimeError("转存已完成，但未能生成你的个人网盘专属分享链接，请重试")

        logger.info(f"成功生成个人专属分享链接: {new_share_url} (永久有效)")

        return {
            "success": True,
            "original_url": share_url,
            "new_share_url": new_share_url,
            "share_id": share_result.get("pwd_id"),
            "passcode": share_result.get("passcode"),
            "title": share_title,
            "file_count": len(files),
            "files": [
                {
                    "fid": f.get("fid"),
                    "file_name": f.get("file_name"),
                    "file_size": f.get("size")
                }
                for f in files
            ]
        }


# 模块级单例与便捷调用函数
_default_quark_service = QuarkPanService()

async def get_share_token(share_url: str, passcode: str = "") -> Tuple[str, str]:
    return await _default_quark_service.get_share_token(share_url, passcode)

async def get_file_list(pwd_id: str, stoken: str) -> List[Dict[str, Any]]:
    return await _default_quark_service.get_file_list(pwd_id, stoken)

async def save_files(pwd_id: str, stoken: str, fid_list: List[str], fid_token_list: List[str]) -> List[str]:
    return await _default_quark_service.save_files(pwd_id, stoken, fid_list, fid_token_list)

async def create_share(fid_list: List[str], title: str = "夸克分享文件") -> Dict[str, Any]:
    return await _default_quark_service.create_share(fid_list, title)

async def transfer_and_reshare(share_url: str, passcode: str = "", custom_title: Optional[str] = None) -> Dict[str, Any]:
    return await _default_quark_service.transfer_and_reshare(share_url, passcode, custom_title)
