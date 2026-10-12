import os
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")


def get_current_cookies():
    """读取网盘 Cookie 配置，优先读取 settings.json，兜底读取环境变量"""
    quark = os.getenv("QUARK_COOKIE", "")
    baidu = os.getenv("BAIDU_COOKIE", "")
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                quark = d.get("quark_cookie") or quark
                baidu = d.get("baidu_cookie") or baidu
        except Exception:
            pass
    return quark.strip(), baidu.strip()


QUARK_COOKIE, BAIDU_COOKIE = get_current_cookies()

# 百度网盘默认分享提取码（可选：若未设置或长度不为4，则自动随机生成）
BAIDU_DEFAULT_PWD = os.getenv("BAIDU_DEFAULT_PWD", "").strip()

# 可选：DeepSeek 大模型文案改写配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

# 服务器配置
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
