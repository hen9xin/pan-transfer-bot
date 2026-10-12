"""
网盘链接解析服务
支持：
1. 夸克网盘 (Quark Pan) 与百度网盘 (Baidu Pan) 原生链接提取
2. 各类防封短链/中转聚合链接（如 pan.nameishare.com、t.cn 等）智能重定向穿透与追踪
3. 提取码自动提取与文本净化
"""

import re
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# 通用 URL 匹配正则
GENERIC_URL_PATTERN = re.compile(
    r'(https?://[^\s\u4e00-\u9fa5\r\n]+)',
    re.IGNORECASE
)

# 夸克网盘链接正则匹配表达式
QUARK_LINK_PATTERN = re.compile(
    r'(https?://(?:pan|b)\.quark\.cn/s/[a-zA-Z0-9]+(?:[^\s\u4e00-\u9fa5\r\n]*)?)',
    re.IGNORECASE
)

LOOSE_QUARK_LINK_PATTERN = re.compile(
    r'((?:https?://)?(?:pan|b)\.quark\.cn/s/[a-zA-Z0-9]+(?:[^\s\u4e00-\u9fa5\r\n]*)?)',
    re.IGNORECASE
)

# 百度网盘链接正则匹配表达式
BAIDU_LINK_PATTERN = re.compile(
    r'(https?://(?:pan|yun)\.baidu\.com/(?:s/[a-zA-Z0-9_-]+|share/link\?[^\s\u4e00-\u9fa5\r\n]+))',
    re.IGNORECASE
)

LOOSE_BAIDU_LINK_PATTERN = re.compile(
    r'((?:https?://)?(?:pan|yun)\.baidu\.com/(?:s/[a-zA-Z0-9_-]+|share/link\?[^\s\u4e00-\u9fa5\r\n]+))',
    re.IGNORECASE
)

# 常见提取码正则模式 (提取码/密码/访问码/code/pwd)
PASSCODE_PATTERN = re.compile(
    r'(?:提取码|提取|密码|访问码|code|pwd|key)\s*[:：=\s]\s*([a-zA-Z0-9]{4,6})',
    re.IGNORECASE
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def extract_share_id(url: str) -> str:
    """从夸克网盘链接中提取 share_id (pwd_id)"""
    match = re.search(r'/s/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    return ""


def extract_baidu_surl(url: str) -> str:
    """从百度网盘链接中提取 surl"""
    match = re.search(r'/s/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    shareid_match = re.search(r'[?&]shareid=([0-9]+)', url)
    if shareid_match:
        return shareid_match.group(1)
    return ""


def extract_passcode(text: str) -> str:
    """从文本中自动提取可能存在的网盘提取码 (4~6位数字/字母)"""
    match_url = re.search(r'[?&]pwd=([a-zA-Z0-9]{4,6})', text)
    if match_url:
        return match_url.group(1)
    match = PASSCODE_PATTERN.search(text)
    if match:
        return match.group(1)
    return ""


def detect_platform(url: str) -> str:
    """检测链接所属网盘平台"""
    if not url:
        return "unknown"
    if "quark.cn" in url:
        return "quark"
    if "baidu.com" in url:
        return "baidu"
    return "unknown"


async def resolve_real_url(url: str) -> str:
    """
    智能穿透短链/中转链接：
    若传入的不是直接的 quark/baidu 链接（如 pan.nameishare.com），自动跟随 301/302 重定向并提取真实网盘链接
    """
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    # 若已经是原生网盘链接，直接返回
    if "quark.cn" in url or "baidu.com" in url:
        return url

    logger.info(f"检测到非直连网盘链接，正在尝试跟踪穿透短链: {url}")
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(url)
            final_url = str(resp.url)
            logger.info(f"短链重定向最终地址: {final_url}")

            if "quark.cn" in final_url or "baidu.com" in final_url:
                return final_url

            # 若页面内通过 JS 跳转或包含网盘链接，在 HTML 源码中正则搜寻
            html_text = resp.text
            quark_in_html = QUARK_LINK_PATTERN.search(html_text)
            if quark_in_html:
                logger.info(f"在页面内容中找到夸克分享链接: {quark_in_html.group(1)}")
                return quark_in_html.group(1)

            baidu_in_html = BAIDU_LINK_PATTERN.search(html_text)
            if baidu_in_html:
                logger.info(f"在页面内容中找到百度网盘链接: {baidu_in_html.group(1)}")
                return baidu_in_html.group(1)

            return final_url
    except Exception as exc:
        logger.warning(f"短链穿透失败: {url}, 错误: {exc}")
        return url


async def parse_content_async(text: str) -> Dict[str, Any]:
    """
    异步解析文本内容：
    1. 提取所有网盘直链及第三方中转链接；
    2. 针对短链/中转链自动异步穿透追踪真实网盘地址；
    3. 返回识别到的平台、真实链接、提取码以及净化后的纯文本。
    """
    if not text:
        return {
            "platform": "unknown",
            "links": [],
            "share_ids": [],
            "passcode": "",
            "clean_text": ""
        }

    # 1. 提取所有网络链接
    all_raw_urls = GENERIC_URL_PATTERN.findall(text)

    links: List[str] = []
    share_ids: List[str] = []
    platform = "unknown"

    for raw_url in all_raw_urls:
        candidate = raw_url.strip()
        # 清理可能附带的中文符号或标点
        candidate = candidate.rstrip("，。！？；、“”‘’)\"]}")
        
        # 穿透获取真实网盘 URL
        real_url = await resolve_real_url(candidate)
        plat = detect_platform(real_url)

        if plat != "unknown":
            if platform == "unknown":
                platform = plat
            if real_url not in links:
                links.append(real_url)
                if plat == "quark":
                    sid = extract_share_id(real_url)
                    if sid:
                        share_ids.append(sid)
                elif plat == "baidu":
                    bsid = extract_baidu_surl(real_url)
                    if bsid:
                        share_ids.append(bsid)

    # 2. 自动识别提取码
    passcode = extract_passcode(text)

    # 3. 剔除所有链接以生成纯净文案
    clean_text = text
    for raw in all_raw_urls:
        clean_text = clean_text.replace(raw, "")

    # 去掉多余空行与两端空格
    lines = [line.strip() for line in clean_text.splitlines()]
    clean_text = "\n".join([line for line in lines if line])

    return {
        "platform": platform,
        "links": links,
        "share_ids": share_ids,
        "passcode": passcode,
        "clean_text": clean_text
    }


def parse_content(text: str) -> Dict[str, Any]:
    """同步兼容入口（若包含原生直链）"""
    quark_matches = LOOSE_QUARK_LINK_PATTERN.findall(text)
    baidu_matches = LOOSE_BAIDU_LINK_PATTERN.findall(text)

    links: List[str] = []
    share_ids: List[str] = []
    platform = "unknown"

    if quark_matches:
        platform = "quark"
        for item in quark_matches:
            link = item.strip()
            if not link.startswith("http"):
                link = "https://" + link
            if link not in links:
                links.append(link)
                sid = extract_share_id(link)
                if sid:
                    share_ids.append(sid)
    elif baidu_matches:
        platform = "baidu"
        for item in baidu_matches:
            link = item.strip()
            if not link.startswith("http"):
                link = "https://" + link
            if link not in links:
                links.append(link)
                bsid = extract_baidu_surl(link)
                if bsid:
                    share_ids.append(bsid)

    passcode = extract_passcode(text)
    clean_text = text
    for raw in quark_matches + baidu_matches:
        clean_text = clean_text.replace(raw, "")

    lines = [line.strip() for line in clean_text.splitlines()]
    clean_text = "\n".join([line for line in lines if line])

    return {
        "platform": platform,
        "links": links,
        "share_ids": share_ids,
        "passcode": passcode,
        "clean_text": clean_text
    }
