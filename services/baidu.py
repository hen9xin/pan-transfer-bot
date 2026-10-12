"""
百度网盘 API 服务
实现百度网盘链接的验证、文件列表获取、按日期层级自动归档转存与专属重新分享功能。
"""

import asyncio
from datetime import datetime
import logging
import re
import time
import json
import random
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import httpx

from config import BAIDU_COOKIE, BAIDU_DEFAULT_PWD

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class BaiduPanService:
    """百度网盘操作服务类"""

    def __init__(self, cookie: Optional[str] = None):
        self.cookie = cookie or BAIDU_COOKIE
        self._bdstoken = None

    def _get_headers(self) -> Dict[str, str]:
        c = (self.cookie or "").strip()
        if c.lower().startswith("cookie:"):
            c = c[7:].strip()
        c = c.replace("\r\n", "; ").replace("\n", "; ").replace("\r", "; ").strip()
        return {
            "User-Agent": USER_AGENT,
            "Referer": "https://pan.baidu.com/",
            "Origin": "https://pan.baidu.com",
            "Cookie": c,
            "Accept": "application/json, text/plain, */*",
        }

    @staticmethod
    def extract_surl(share_url: str) -> str:
        """从分享链接提取 surl (短链接 ID)"""
        match = re.search(r'/s/([a-zA-Z0-9_-]+)', share_url)
        if match:
            return match.group(1)
        match_param = re.search(r'[?&]surl=([a-zA-Z0-9_-]+)', share_url)
        if match_param:
            surl = match_param.group(1)
            return ("1" + surl) if not surl.startswith("1") else surl
        return ""

    async def _get_bdstoken(self) -> str:
        """获取 bdstoken (CSRF token)"""
        if self._bdstoken:
            return self._bdstoken

        if not self.cookie:
            return ""

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(
                    "https://pan.baidu.com/api/gettemplatevariable?clienttype=0&app_id=250528&fields=[%22bdstoken%22]",
                    headers=self._get_headers()
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("errno") == 0:
                        self._bdstoken = data.get("result", {}).get("bdstoken", "")
                        return self._bdstoken
        except Exception as e:
            logger.warning(f"获取百度 bdstoken 异常: {e}")
        return ""

    async def verify_share(self, surl: str, pwd: str = "") -> Dict[str, Any]:
        """验证分享链接并获取 shareid, uk, sekey 等信息"""
        clean_surl = surl.lstrip('1') if surl.startswith('1') else surl
        share_page_url = f"https://pan.baidu.com/s/{surl}"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = self._get_headers()
            headers["Referer"] = "https://pan.baidu.com/"
            page_resp = await client.get(share_page_url, headers=headers)
            page_text = page_resp.text

            # 提取 share_uk 和 shareid（优先匹配真正的 share_uk）
            uk = ""
            uk_match = re.search(r'share_uk["\']?\s*:\s*["\']?(\d+)', page_text)
            if uk_match:
                uk = uk_match.group(1)
            else:
                m_uk = re.search(r'[\'"]uk[\'"]\s*:\s*[\'"]?([1-9]\d*)[\'"]?', page_text)
                if m_uk:
                    uk = m_uk.group(1)

            shareid = ""
            shareid_match = re.search(r'shareid["\']?\s*:\s*["\']?(\d+)', page_text)
            if shareid_match:
                shareid = shareid_match.group(1)

            sekey = ""
            if pwd:
                verify_url = "https://pan.baidu.com/share/verify"
                params = {
                    "surl": clean_surl,
                    "t": int(time.time() * 1000),
                    "channel": "chunlei",
                    "web": "1",
                    "clienttype": "0"
                }
                verify_resp = await client.post(
                    verify_url,
                    params=params,
                    data={"pwd": pwd, "vcode": "", "vcode_str": ""},
                    headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}
                )
                verify_data = verify_resp.json()
                if verify_data.get("errno") != 0:
                    err_msg = verify_data.get("err_msg") or "提取码错误或失效"
                    raise RuntimeError(f"百度网盘提取码验证失败: {err_msg} (errno: {verify_data.get('errno')})")

                # 获取 randsk / BDCLND
                randsk = verify_data.get("randsk", "")
                if randsk:
                    sekey = randsk
                for cookie in verify_resp.cookies.jar:
                    if cookie.name == "BDCLND":
                        sekey = cookie.value

                # 若之前未提取到 uk 或 shareid，带上 BDCLND cookie 重新刷新页面提取
                if not shareid or not uk or uk == "0":
                    cookie_header = headers.get("Cookie", "")
                    if sekey:
                        cookie_header = f"{cookie_header}; BDCLND={sekey}".strip("; ")
                    page_resp2 = await client.get(share_page_url, headers={**headers, "Cookie": cookie_header})
                    page_text2 = page_resp2.text

                    uk_match2 = re.search(r'share_uk["\']?\s*:\s*["\']?(\d+)', page_text2)
                    if uk_match2:
                        uk = uk_match2.group(1)
                    shareid_match2 = re.search(r'shareid["\']?\s*:\s*["\']?(\d+)', page_text2)
                    if shareid_match2:
                        shareid = shareid_match2.group(1)

            logger.info(f"百度网盘解析分享凭据: shareid={shareid}, uk={uk}, clean_surl={clean_surl}, has_sekey={bool(sekey)}")

            return {
                "shareid": shareid,
                "uk": uk,
                "surl": surl,
                "clean_surl": clean_surl,
                "sekey": sekey
            }

    async def get_file_list(
        self,
        shareid: str,
        uk: str,
        sekey: str = "",
        clean_surl: str = "",
        dir: str = "/",
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """获取分享中的文件列表（双重机制保障：优先通过 shorturl 与 root=1 获取，备选通过 shareid 与 uk 获取）"""
        headers = self._get_headers()
        curr_c = headers.get("Cookie", "")
        clean_cookie = re.sub(r'(?:^|;\s*)BDCLND=[^;]*', '', curr_c).strip('; ')
        if sekey:
            encoded_sekey = sekey if '%' in sekey else urllib.parse.quote(sekey)
            headers["Cookie"] = f"{clean_cookie}; BDCLND={encoded_sekey}".strip("; ")
        else:
            headers["Cookie"] = clean_cookie

        referer_url = f"https://pan.baidu.com/s/1{clean_surl}" if clean_surl else "https://pan.baidu.com/"
        headers["Referer"] = referer_url
        unquoted_sekey = urllib.parse.unquote(sekey) if sekey else ""

        # 机制 1: 优先使用 shorturl + root=1 接口模式（官方最新标准通道）
        if clean_surl:
            params = {
                "shorturl": clean_surl,
                "root": "1" if dir == "/" else "0",
                "dir": dir,
                "page": page,
                "num": 100,
                "order": "name",
                "clienttype": "0",
                "web": "1",
                "channel": "chunlei",
                "app_id": "250528",
            }
            if unquoted_sekey:
                params["sekey"] = unquoted_sekey

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get("https://pan.baidu.com/share/list", params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(f"百度 shorturl 获取文件列表结果: errno={data.get('errno')}")
                    if data.get("errno") == 0:
                        flist = data.get("list", [])
                        if flist:
                            return flist

        # 机制 2: 备选使用 shareid + uk 模式
        if shareid and uk and uk != "0":
            params = {
                "shareid": shareid,
                "uk": uk,
                "dir": dir,
                "page": page,
                "num": 100,
                "order": "name",
                "clienttype": "0",
                "web": "1",
                "channel": "chunlei",
                "app_id": "250528",
            }
            if unquoted_sekey:
                params["sekey"] = unquoted_sekey

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get("https://pan.baidu.com/share/list", params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(f"百度 shareid 获取文件列表结果: errno={data.get('errno')}")
                    if data.get("errno") == 0:
                        return data.get("list", [])
                    else:
                        msg = data.get("err_msg") or data.get("show_msg") or data.get("errmsg") or "未知错误"
                        raise RuntimeError(f"获取百度网盘文件列表失败: {msg} (errno: {data.get('errno')})")

        raise RuntimeError("无法获取百度网盘文件列表，请检查分享链接或提取码是否正确")

    async def _wait_for_task(self, task_id: str, max_retries: int = 15, interval: float = 1.0) -> Dict[str, Any]:
        """轮询异步转存任务状态"""
        bdstoken = await self._get_bdstoken()
        params = {
            "taskid": str(task_id),
            "channel": "chunlei",
            "web": "1",
            "clienttype": "0",
            "app_id": "250528",
        }
        if bdstoken:
            params["bdstoken"] = bdstoken
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(max_retries):
                try:
                    res = await client.get(
                        "https://pan.baidu.com/share/taskquery",
                        params=params,
                        headers=self._get_headers()
                    )
                    if res.status_code == 200:
                        data = res.json()
                        logger.info(f"百度 taskquery 返回: {data}")
                        errno = data.get("errno", -1)
                        status = data.get("status", "")
                        task_errno = data.get("task_errno", 0)
                        if status == "success" or (errno == 0 and task_errno == 0 and data.get("task_status") == "success"):
                            return data
                        elif status == "failed" or (task_errno != 0 and task_errno is not None):
                            msg = data.get("show_msg") or data.get("err_msg") or "未知错误"
                            raise RuntimeError(f"百度转存异步任务执行失败: {msg} (task_errno: {task_errno})")
                except Exception as e:
                    logger.warning(f"轮询百度任务异常: {e}")
                await asyncio.sleep(interval)
        return {}

    async def check_folder_exists(self, parent_dir: str, folder_name: str) -> bool:
        """检查网盘中 parent_dir 下是否存在名为 folder_name 的目录"""
        if not self.cookie:
            return False

        bdstoken = await self._get_bdstoken()
        headers = self._get_headers()
        full_path = f"{parent_dir.rstrip('/')}/{folder_name}"

        # 方式 1：直接通过 api/list 查询完整目标目录
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                direct_resp = await client.get(
                    "https://pan.baidu.com/api/list",
                    params={
                        "dir": full_path,
                        "bdstoken": bdstoken,
                        "order": "time",
                        "desc": "1",
                        "page": "1",
                        "num": "1",
                        "clienttype": "0",
                        "web": "1",
                        "app_id": "250528"
                    },
                    headers=headers
                )
                if direct_resp.status_code == 200:
                    d_data = direct_resp.json()
                    if d_data.get("errno") == 0:
                        logger.info(f"探测到目标目录已存在: {full_path}")
                        return True
        except Exception as e:
            logger.debug(f"直接探测目录 {full_path} 异常: {e}")

        # 方式 2：列举父目录下的子项，严格匹配文件夹名和 isdir 标识
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                parent_resp = await client.get(
                    "https://pan.baidu.com/api/list",
                    params={
                        "dir": parent_dir,
                        "bdstoken": bdstoken,
                        "order": "time",
                        "desc": "1",
                        "page": "1",
                        "num": "100",
                        "clienttype": "0",
                        "web": "1",
                        "app_id": "250528"
                    },
                    headers=headers
                )
                if parent_resp.status_code == 200:
                    p_data = parent_resp.json()
                    if p_data.get("errno") == 0:
                        for item in p_data.get("list", []):
                            if item.get("server_filename") == folder_name and str(item.get("isdir", "0")) == "1":
                                logger.info(f"父目录 {parent_dir} 下发现已存在文件夹: {folder_name}")
                                return True
        except Exception as e:
            logger.warning(f"列举父目录 {parent_dir} 异常: {e}")

        return False

    async def create_folder(self, path: str) -> bool:
        """在个人网盘创建文件夹，强制指定 rtype=0 防止冲突时自动生成时间戳重命名副本"""
        if not self.cookie:
            return False
        bdstoken = await self._get_bdstoken()
        params = {
            "a": "commit",
            "channel": "chunlei",
            "web": "1",
            "clienttype": "0",
            "app_id": "250528",
        }
        if bdstoken:
            params["bdstoken"] = bdstoken
        form_data = {
            "path": path,
            "isdir": "1",
            "size": "0",
            "block_list": "[]",
            "uploadid": "",
            "rtype": "0"  # 严格禁止百度自动命名生成形如 _20261012_020150 的时间戳副本
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://pan.baidu.com/api/create",
                params=params,
                data=form_data,
                headers={**self._get_headers(), "Content-Type": "application/x-www-form-urlencoded"}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("errno") in (0, -8):  # 0: 成功, -8: 目录已存在
                    logger.info(f"百度网盘目录就绪: {path} (errno={data.get('errno')})")
                    return True
                logger.warning(f"百度网盘创建目录响应: {data}")
        return False

    async def get_or_create_date_path(self) -> str:
        """
        按照 年 -> 月 -> 日 规则层级创建文件夹并返回今日最终存放目录路径
        规则示例：/2026/10月/10月12日
        严格先检查父级与子级目录是否存在，若已存在则直接复用，绝不重复创建多余同名副本文件夹
        """
        now = datetime.now()
        year_name = f"{now.year}"
        month_name = f"{now.month}月"
        day_name = f"{now.month}月{now.day}日"

        # 1. 确保年份目录 /2026 存在（先检查，不存在才创建）
        year_path = f"/{year_name}"
        if not await self.check_folder_exists("/", year_name):
            logger.info(f"年份目录不存在，正在创建: {year_path}")
            await self.create_folder(year_path)
        else:
            logger.info(f"年份目录已存在，跳过创建: {year_path}")

        # 2. 确保月份目录 /2026/10月 存在（先检查，不存在才创建）
        month_path = f"{year_path}/{month_name}"
        if not await self.check_folder_exists(year_path, month_name):
            logger.info(f"月份目录不存在，正在创建: {month_path}")
            await self.create_folder(month_path)
        else:
            logger.info(f"月份目录已存在，跳过创建: {month_path}")

        # 3. 确保日期目录 /2026/10月/10月12日 存在（先检查，不存在才创建）
        day_path = f"{month_path}/{day_name}"
        if not await self.check_folder_exists(month_path, day_name):
            logger.info(f"日期目录不存在，正在创建: {day_path}")
            await self.create_folder(day_path)
        else:
            logger.info(f"日期目录已存在，跳过创建: {day_path}")

        logger.info(f"百度网盘日期归档目标目录就绪: {day_path}")
        return day_path

    async def transfer_files(
        self,
        shareid: str,
        uk: str,
        fs_ids: List[int],
        sekey: str = "",
        path: str = "/",
        share_url: str = "",
        clean_surl: str = ""
    ) -> Dict[str, Any]:
        """转存文件到自己的网盘指定目录"""
        if not self.cookie:
            raise ValueError("未配置百度网盘 Cookie，无法自动转存")

        bdstoken = await self._get_bdstoken()
        unquoted_sekey = urllib.parse.unquote(sekey) if sekey else ""

        params = {
            "shareid": shareid,
            "from": uk,
            "channel": "chunlei",
            "web": "1",
            "app_id": "250528",
            "clienttype": "0",
            "ondup": "newcopy",
            "async": "1",
        }
        if clean_surl:
            params["surl"] = clean_surl
        if bdstoken:
            params["bdstoken"] = bdstoken
        if unquoted_sekey:
            params["sekey"] = unquoted_sekey

        form_data = {
            "fsidlist": json.dumps(fs_ids),
            "path": path,
        }
        if unquoted_sekey:
            form_data["sekey"] = unquoted_sekey

        headers = self._get_headers()
        curr_c = headers.get("Cookie", "")
        # 清理 Cookie 中可能存在的旧 BDCLND 字段，确保只有一个全新的有效 BDCLND
        clean_cookie = re.sub(r'(?:^|;\s*)BDCLND=[^;]*', '', curr_c).strip('; ')
        if sekey:
            encoded_sekey = sekey if '%' in sekey else urllib.parse.quote(sekey)
            headers["Cookie"] = f"{clean_cookie}; BDCLND={encoded_sekey}".strip("; ")
        else:
            headers["Cookie"] = clean_cookie

        referer_url = share_url or (f"https://pan.baidu.com/s/1{clean_surl}" if clean_surl else "https://pan.baidu.com/")
        headers["Referer"] = referer_url
        headers["Origin"] = "https://pan.baidu.com"
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://pan.baidu.com/share/transfer",
                params=params,
                data=form_data,
                headers=headers
            )
            data = resp.json()
            logger.info(f"百度网盘 transfer 响应: {data}")

            # 针对 200025 异常尝试备用重试策略（不带 params 中的 sekey，纯靠 Cookie BDCLND 与 form_data sekey）
            if data.get("errno") == 200025:
                logger.warning("转存返回 errno 200025，尝试使用备用凭证通道重试...")
                retry_params = params.copy()
                retry_params.pop("sekey", None)
                retry_resp = await client.post(
                    "https://pan.baidu.com/share/transfer",
                    params=retry_params,
                    data=form_data,
                    headers=headers
                )
                retry_data = retry_resp.json()
                logger.info(f"百度网盘 transfer 备用重试响应: {retry_data}")
                if retry_data.get("errno") == 0:
                    data = retry_data

            if data.get("errno") != 0:
                msg = data.get("err_msg") or data.get("errmsg") or data.get("show_msg") or "转存失败"
                raise RuntimeError(f"百度网盘转存失败: {msg} (errno: {data.get('errno')})")

            to_fs_ids = []
            # 1. 尝试直接从 extra.list 中提取 to_fs_id
            extra_list = data.get("extra", {}).get("list", [])
            for item in extra_list:
                fid = item.get("to_fs_id") or item.get("fs_id")
                if fid:
                    to_fs_ids.append(int(fid))

            # 2. 如果是异步任务，等待任务完成
            task_id = data.get("taskid")
            if task_id:
                task_res = await self._wait_for_task(task_id)
                task_extra_list = task_res.get("extra", {}).get("list", [])
                for item in task_extra_list:
                    fid = item.get("to_fs_id") or item.get("fs_id")
                    if fid and int(fid) not in to_fs_ids:
                        to_fs_ids.append(int(fid))

            return {
                "raw_data": data,
                "to_fs_ids": to_fs_ids
            }

    DEFAULT_BAIDU_PWD = BAIDU_DEFAULT_PWD or os.getenv("BAIDU_DEFAULT_PWD", "").strip()

    @staticmethod
    def generate_random_pwd() -> str:
        """生成符合百度网盘规范的4位提取码（小写字母与数字组合，排除混淆字符）"""
        chars = "23456789abcdefghjkmnpqrstuvwxyz"
        return "".join(random.choices(chars, k=4))

    async def create_share(
        self,
        fs_ids: List[int],
        period: int = 0,
        pwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建属于用户自己的新分享链接
        period: 0=永久有效, 1=1天, 7=7天, 30=30天（默认0永久有效）
        pwd: 4位提取码（留空则优先使用配置的 BAIDU_DEFAULT_PWD，否则随机生成）
        """
        if not self.cookie:
            raise ValueError("未配置百度网盘 Cookie，无法创建新分享链接")

        bdstoken = await self._get_bdstoken()

        params = {
            "channel": "chunlei",
            "web": "1",
            "clienttype": "0",
            "app_id": "250528",
        }
        if bdstoken:
            params["bdstoken"] = bdstoken

        # 百度网盘 schannel=4 要求提取码严格为 4 位字符串
        clean_pwd = (pwd or "").strip()
        if len(clean_pwd) == 4:
            final_pwd = clean_pwd
        elif self.DEFAULT_BAIDU_PWD and len(self.DEFAULT_BAIDU_PWD) == 4:
            final_pwd = self.DEFAULT_BAIDU_PWD
        else:
            final_pwd = self.generate_random_pwd()

        form_data = {
            "fid_list": json.dumps(fs_ids),
            "schannel": "4",
            "channel_list": "[]",
            "period": str(period),
            "pwd": final_pwd,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://pan.baidu.com/share/set",
                params=params,
                data=form_data,
                headers={**self._get_headers(), "Content-Type": "application/x-www-form-urlencoded"}
            )
            data = resp.json()
            logger.info(f"百度网盘 share/set 响应: {data}")
            if data.get("errno") != 0:
                msg = data.get("err_msg") or data.get("show_msg") or "未知错误"
                raise RuntimeError(f"创建百度网盘分享失败: {msg} (errno: {data.get('errno')})")

            share_url = data.get("link") or (f"https://pan.baidu.com/s/{data.get('shorturl')}" if data.get("shorturl") else "")
            returned_pwd = data.get("pwd") or final_pwd
            return {
                "share_url": share_url,
                "shareid": str(data.get("shareid", "")),
                "passcode": returned_pwd,
            }

    async def transfer_and_reshare(
        self,
        share_url: str,
        passcode: str = "",
        custom_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """完整流程：提取验证 → 获取文件列表 → 按年/月/日建立归档目录 → 转存至对应日期目录 → 创建专属分享链接"""
        logger.info(f"开始处理百度网盘转存流程: {share_url}")

        surl = self.extract_surl(share_url)
        if not surl:
            raise ValueError(f"无法从链接中提取百度网盘分享ID: {share_url}")

        # 优先从链接自身提取提取码，避免传入历史残留或不匹配的提取码
        pwd_match = re.search(r'[?&]pwd=([a-zA-Z0-9]{4,6})', share_url)
        if pwd_match:
            passcode = pwd_match.group(1)
            logger.info(f"从链接参数中自动识别并锁定提取码: {passcode}")

        # 1. 验证分享链接并获取凭证
        share_info = await self.verify_share(surl, passcode)
        shareid = share_info["shareid"]
        uk = share_info["uk"]
        clean_surl = share_info.get("clean_surl", "")
        sekey = share_info.get("sekey", "")

        # 2. 获取分享文件列表
        files = await self.get_file_list(
            shareid=shareid,
            uk=uk,
            sekey=sekey,
            clean_surl=clean_surl
        )
        if not files:
            raise RuntimeError("分享链接中未找到文件或分享已失效")

        fs_ids = [int(f["fs_id"]) for f in files if "fs_id" in f]
        if not fs_ids:
            raise RuntimeError("未解析到有效的文件ID")

        first_file_name = files[0].get("server_filename", files[0].get("file_name", "分享文件"))
        share_title = custom_title or first_file_name

        # 3. 按 年 -> 月 -> 日 规则层级创建归档文件夹（与夸克网盘规则严格一致）
        date_dir = await self.get_or_create_date_path()

        # 4. 转存文件到对应的日期归档目录
        logger.info(f"正在转存 {len(fs_ids)} 个文件到百度网盘日期归档目录: {date_dir}")
        transfer_result = await self.transfer_files(
            shareid=shareid,
            uk=uk,
            fs_ids=fs_ids,
            sekey=sekey,
            path=date_dir,
            share_url=share_url,
            clean_surl=clean_surl
        )
        to_fs_ids = transfer_result.get("to_fs_ids", [])

        # 5. 确保拿到用户个人网盘中的真实 fs_id
        new_fs_ids = to_fs_ids[:]
        if not new_fs_ids:
            logger.info("未直接从 transfer 响应中获取到 to_fs_ids，启动日期归档目录扫描匹配真实 fs_id...")
            bdstoken = await self._get_bdstoken()
            target_names = {f.get("server_filename", f.get("file_name", "")).strip() for f in files}
            headers = self._get_headers()

            for retry in range(5):
                await asyncio.sleep(1.0)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    search_resp = await client.get(
                        "https://pan.baidu.com/api/list",
                        params={
                            "dir": date_dir,
                            "bdstoken": bdstoken,
                            "order": "time",
                            "desc": "1",
                            "page": "1",
                            "num": "50",
                            "clienttype": "0",
                            "web": "1",
                            "app_id": "250528"
                        },
                        headers=headers
                    )
                    if search_resp.status_code == 200:
                        search_data = search_resp.json()
                        file_items = search_data.get("list", [])
                        for item in file_items:
                            sf_name = item.get("server_filename", "").strip()
                            if sf_name in target_names or any(tn in sf_name or sf_name in tn for tn in target_names):
                                fid_val = int(item["fs_id"])
                                if fid_val not in new_fs_ids:
                                    new_fs_ids.append(fid_val)
                        if new_fs_ids:
                            break
                        if not new_fs_ids and file_items:
                            new_fs_ids = [int(file_items[0]["fs_id"])]
                            break

        if not new_fs_ids:
            raise RuntimeError(f"文件已转存到个人网盘日期归档目录（{date_dir}），但未能定位到新生成的文件 ID，无法创建专属分享链接。请检查网盘目录。")

        # 6. 为用户创建专属的新分享链接（支持环境变量指定提取码或随机生成4位，默认永久有效 period=0）
        configured_pwd = self.DEFAULT_BAIDU_PWD.strip() if self.DEFAULT_BAIDU_PWD else ""
        new_share_pwd = configured_pwd if len(configured_pwd) == 4 else self.generate_random_pwd()
        logger.info(f"转存完成，正在创建用户个人专属百度分享链接: fs_ids={new_fs_ids}, pwd={new_share_pwd}, period=0(永久有效)")
        share_result = await self.create_share(new_fs_ids, period=0, pwd=new_share_pwd)
        new_share_url = share_result.get("share_url")
        if not new_share_url:
            raise RuntimeError("转存已成功，但未能生成你的百度网盘专属分享链接，请重试")

        final_passcode = share_result.get("passcode") or new_share_pwd
        logger.info(f"成功生成百度网盘专属分享链接: {new_share_url} (提取码: {final_passcode}, 永久有效)")

        return {
            "success": True,
            "original_url": share_url,
            "new_share_url": new_share_url,
            "share_id": str(share_result.get("shareid", "")),
            "passcode": final_passcode,
            "title": share_title,
            "file_count": len(files),
            "files": [
                {
                    "file_name": f.get("server_filename", f.get("file_name", "")),
                    "size": int(f.get("size") or 0),
                    "fid": str(f.get("fs_id", "")),
                }
                for f in files
            ]
        }
