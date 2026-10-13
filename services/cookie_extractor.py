"""
浏览器 Cookie 自动提取服务
自动扫描本机已安装浏览器（Chrome / Edge 等）的本地缓存与存储，
智能提取夸克网盘与百度网盘的有效认证 Cookie，无需用户手动打开开发者工具。
"""

import os
import glob
import re
import json
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")
ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def extract_cookies_from_browser_storage() -> Dict[str, str]:
    """
    自动扫描本机 Chrome 和 Edge 的 LevelDB 本地存储，提取夸克与百度 Cookie
    """
    quark_cookie = ""
    baidu_cookie = ""

    # 常见浏览器用户数据目录列表
    search_paths = [
        # Chrome
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Profile 1\Local Storage\leveldb"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Local Storage\leveldb"),
        # Edge
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Local Storage\leveldb"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Profile 1\Local Storage\leveldb"),
    ]

    # 也补充遍历所有 Profile * 目录
    for base_parent in [
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
    ]:
        if os.path.exists(base_parent):
            try:
                for sub in os.listdir(base_parent):
                    if sub.startswith("Profile "):
                        p = os.path.join(base_parent, sub, "Local Storage", "leveldb")
                        if p not in search_paths and os.path.exists(p):
                            search_paths.append(p)
            except Exception:
                pass

    for base in search_paths:
        if not os.path.exists(base):
            continue
        files = glob.glob(os.path.join(base, "*.ldb")) + glob.glob(os.path.join(base, "*.log"))
        for f in files:
            try:
                with open(f, "rb") as fp:
                    data = fp.read()

                # 提取夸克 Cookie (以 b-user-id= 或 _UP_A4A 开头)
                q_matches = re.findall(b"(?:b-user-id|_UP_A4A|_c_WBKFRo)=[^\x00\x01\x02\r\n\t]+", data)
                for m in q_matches:
                    s = m.decode("latin1", errors="ignore").strip()
                    if ("b-user-id=" in s or "_UP_A4A" in s) and len(s) > len(quark_cookie):
                        quark_cookie = s

                # 提取百度 Cookie (必须包含 BDUSS)
                b_matches = re.findall(b"(?:BAIDUID|BDUSS)=[^\x00\x01\x02\r\n\t]+", data)
                for m in b_matches:
                    s = m.decode("latin1", errors="ignore").strip()
                    if "BDUSS=" in s and len(s) > len(baidu_cookie):
                        baidu_cookie = s
            except Exception as e:
                logger.debug(f"读取文件 {f} 异常: {e}")

    return {
        "quark_cookie": clean_cookie_string(quark_cookie),
        "baidu_cookie": clean_cookie_string(baidu_cookie)
    }


def clean_cookie_string(raw: str) -> str:
    """清洗 Cookie 字符串，去除多余前缀与非法不可见字符"""
    if not raw:
        return ""
    text = raw.strip()
    # 截取到合理的终止边界
    if text.startswith("cookie:"):
        text = text[7:].strip()
    return text


def load_saved_settings() -> Dict[str, str]:
    """从本地配置文件读取已保存的 Cookie 设置"""
    settings = {"quark_cookie": "", "baidu_cookie": ""}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                settings["quark_cookie"] = d.get("quark_cookie", "")
                settings["baidu_cookie"] = d.get("baidu_cookie", "")
        except Exception as e:
            logger.warning(f"读取 settings.json 异常: {e}")

    # 如果 settings.json 为空，尝试从 .env 读取
    if not settings["quark_cookie"] and not settings["baidu_cookie"] and os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("QUARK_COOKIE="):
                        settings["quark_cookie"] = line.split("=", 1)[1].strip()
                    elif line.startswith("BAIDU_COOKIE="):
                        settings["baidu_cookie"] = line.split("=", 1)[1].strip()
        except Exception:
            pass

    return settings


def save_settings(quark_cookie: str = "", baidu_cookie: str = "") -> bool:
    """将 Cookie 配置持久化到 settings.json 和 .env 中"""
    current = load_saved_settings()
    if quark_cookie:
        current["quark_cookie"] = clean_cookie_string(quark_cookie)
    if baidu_cookie:
        current["baidu_cookie"] = clean_cookie_string(baidu_cookie)

    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)

        # 同步更新或写入 .env，保留其他配置项（如 BAIDU_DEFAULT_PWD 等）
        env_lines_dict = {}
        if os.path.exists(ENV_FILE):
            try:
                with open(ENV_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str and not line_str.startswith("#") and "=" in line_str:
                            k, v = line_str.split("=", 1)
                            env_lines_dict[k.strip()] = v.strip()
            except Exception:
                pass

        env_lines_dict["QUARK_COOKIE"] = current.get("quark_cookie", "")
        env_lines_dict["BAIDU_COOKIE"] = current.get("baidu_cookie", "")
        if "HOST" not in env_lines_dict:
            env_lines_dict["HOST"] = "0.0.0.0"
        if "PORT" not in env_lines_dict:
            env_lines_dict["PORT"] = "8000"

        with open(ENV_FILE, "w", encoding="utf-8") as f:
            for k, v in env_lines_dict.items():
                f.write(f"{k}={v}\n")

        logger.info("已成功持久化保存网盘 Cookie 配置至 settings.json 与 .env")
        return True
    except Exception as e:
        logger.error(f"保存设置失败: {e}")
        return False


def auto_detect_and_save() -> Dict[str, Any]:
    """执行一键自动提取并保存"""
    extracted = extract_cookies_from_browser_storage()
    quark_c = extracted.get("quark_cookie", "")
    baidu_c = extracted.get("baidu_cookie", "")

    # 如果提取成功，自动持久化保存
    if quark_c or baidu_c:
        save_settings(quark_cookie=quark_c, baidu_cookie=baidu_c)

    # 读取合并后的最新设置
    saved = load_saved_settings()
    return {
        "success": bool(saved.get("quark_cookie") or saved.get("baidu_cookie")),
        "quark_cookie": saved.get("quark_cookie", ""),
        "baidu_cookie": saved.get("baidu_cookie", ""),
        "has_quark": bool(saved.get("quark_cookie")),
        "has_baidu": bool(saved.get("baidu_cookie")),
        "message": "已成功自动获取网盘 Cookie！" if (saved.get("quark_cookie") or saved.get("baidu_cookie")) else "未在本地浏览器中检测到网盘登录 Cookie"
    }
