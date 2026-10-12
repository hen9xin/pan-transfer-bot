"""
网盘链接转存工具 - FastAPI 后端服务
特点：
1. 零外部 AI API 依赖，纯本地智能算法二创改写
2. 兼容夸克网盘与百度网盘两种主流网盘链接
3. 自动识别平台、自动提取提取码、自动转存并生成专属新分享链接
"""

import os
import re
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

import config
from services.link_parser import parse_content, parse_content_async, detect_platform, extract_passcode
from services.text_generator import generate_copy, rewrite_text_locally
from services.quark import QuarkPanService
from services.baidu import BaiduPanService
from services.cookie_extractor import (
    load_saved_settings,
    save_settings,
    auto_detect_and_save
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pan_transfer_tool")

app = FastAPI(
    title="网盘链接转存工具 API",
    description="支持夸克与百度网盘链接解析、自动转存与本地智能文案二创",
    version="2.0.0"
)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================= 数据模型 (Pydantic Models) =================

class ParseRequest(BaseModel):
    text: str = Field(..., description="输入的文案或网盘分享链接")


class ParseResponse(BaseModel):
    platform: str = Field(..., description="网盘类型: quark / baidu / unknown")
    links: List[str] = Field(default_factory=list, description="提取到的网盘链接列表")
    share_ids: List[str] = Field(default_factory=list, description="提取出的分享码 ID")
    passcode: str = Field(default="", description="自动识别出的提取码")
    clean_text: str = Field(default="", description="剥离链接后的纯文案")


class GenerateRequest(BaseModel):
    text: Optional[str] = Field("", description="原帖内容（文案或链接）")
    link: Optional[str] = Field("", description="直接传入的网盘链接（可选）")
    passcode: Optional[str] = Field("", description="提取码（可选，不填则自动识别）")
    custom_title: Optional[str] = Field(None, description="自定义新分享标题")
    quark_cookie: Optional[str] = Field(None, description="前端传入的夸克 Cookie")
    baidu_cookie: Optional[str] = Field(None, description="前端传入的百度网盘 Cookie")


class GenerateResponse(BaseModel):
    success: bool = Field(..., description="处理状态")
    platform: str = Field(..., description="使用的网盘平台: quark / baidu")
    original_link: str = Field(..., description="原始网盘分享链接")
    new_link: Optional[str] = Field(None, description="转存后生成的新分享链接")
    passcode: Optional[str] = Field(None, description="新分享提取码")
    title: str = Field(default="", description="文件或分享标题")
    file_count: int = Field(default=0, description="文件数量")
    files: List[Dict[str, Any]] = Field(default_factory=list, description="包含的文件列表")
    rewritten_text: str = Field(default="", description="本地生成的二创推特文案")
    final_tweet: str = Field(default="", description="拼接好的可直接复制发布的完整推特文案")
    transfer_msg: Optional[str] = Field(None, description="转存状态提示或说明")


class SettingsPayload(BaseModel):
    quark_cookie: Optional[str] = Field("", description="夸克网盘 Cookie")
    baidu_cookie: Optional[str] = Field("", description="百度网盘 Cookie")
    api_base_url: Optional[str] = Field("", description="API 基础服务地址")


# ================= 全局异常处理 =================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error": str(exc.detail)}
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"服务器内部异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"服务器内部处理异常: {str(exc)}", "error": str(exc)}
    )


# ================= 业务接口 (API Endpoints) =================

@app.post("/api/parse", response_model=ParseResponse, summary="解析网盘链接与文案")
async def api_parse(payload: ParseRequest):
    """
    智能识别文本中的夸克或百度网盘链接，提取提取码与纯净正文
    """
    try:
        result = await parse_content_async(payload.text)
        return ParseResponse(
            platform=result["platform"],
            links=result["links"],
            share_ids=result["share_ids"],
            passcode=result["passcode"],
            clean_text=result["clean_text"]
        )
    except Exception as exc:
        logger.error(f"解析文本链接异常: {exc}")
        raise HTTPException(status_code=400, detail=f"解析失败: {str(exc)}")


def clean_and_extract_cookie(raw: str) -> str:
    """智能从纯文本、多行请求标头、或 cURL 命令中提纯出真正的 Cookie"""
    if not raw:
        return ""
    text = raw.strip()

    # 1. cURL 常用 cookie 选项: -b '...' 或 --cookie '...'
    m_b = re.search(r'(?:-b|--cookie)\s+\$?[\'\"]([^\'\"]+)[\'\"]', text)
    if m_b:
        return m_b.group(1).strip()

    # 2. cURL 请求头选项: -H 'cookie: ...' 或 -H $'cookie: ...' 或 --header
    m_h = re.search(r'(?:-H|--header)\s+\$?[\'\"](?:cookie|Cookie):\s*([^\'\"]+)[\'\"]', text, re.IGNORECASE)
    if m_h:
        return m_h.group(1).strip()

    # 3. 逐行匹配: -H 'Cookie: xxx' 或普通标头 'Cookie: xxx'
    for line in text.splitlines():
        line_clean = line.strip().rstrip('\\^').strip()
        m_line_h = re.search(r'(?:-H|--header|-b|--cookie)\s+\$?[\'\"]?(?:cookie|Cookie)?\s*[:：=]?\s*([^\'\"]+)', line_clean, re.IGNORECASE)
        if m_line_h and ('=' in m_line_h.group(1)):
            val = m_line_h.group(1).strip().strip("'\"`")
            if 'b-user-id' in val or '__pus' in val or 'BDUSS' in val or ';' in val:
                return val

        m = re.match(r'^(?:cookie|Cookie)\s*[:：]\s*(.+)$', line_clean, re.IGNORECASE)
        if m:
            val = m.group(1).strip().strip("'\"`")
            if val:
                return val

    # 4. JSON / JS 对象中格式: "cookie": "..."
    m_json = re.search(r'[\'\"`]cookie[\'\"`]\s*[:：=]\s*[\'\"`]([^\'\"`]+)[\'\"`]', text, re.IGNORECASE)
    if m_json:
        return m_json.group(1).strip()

    # 5. 扫描包含关键认证字段整行提取（保留完整 cookie 键值对）
    for line in text.splitlines():
        line_clean = line.strip().rstrip('\\^').strip().strip("'\"`")
        if ('__pus=' in line_clean or 'b-user-id=' in line_clean or 'BDUSS=' in line_clean):
            if ':' in line_clean:
                line_clean = line_clean.split(':', 1)[1].strip()
            return line_clean.strip("'\"` ")

    # 6. 单行直接以 cookie: 开头
    if text.lower().startswith("cookie:"):
        text = text[7:].strip()

    # 7. 降级：将所有换行替换为分号，并清理多余符号
    return text.replace("\r\n", "; ").replace("\n", "; ").replace("\r", "; ").strip()


@app.get("/api/settings", summary="获取网盘配置")
async def api_get_settings():
    saved = load_saved_settings()
    return {
        "success": True,
        "quark_cookie": saved.get("quark_cookie", ""),
        "baidu_cookie": saved.get("baidu_cookie", ""),
        "has_quark": bool(saved.get("quark_cookie")),
        "has_baidu": bool(saved.get("baidu_cookie"))
    }


@app.post("/api/settings", summary="保存网盘配置")
async def api_save_settings(payload: SettingsPayload):
    q_c = clean_and_extract_cookie(payload.quark_cookie or "")
    b_c = clean_and_extract_cookie(payload.baidu_cookie or "")
    save_settings(quark_cookie=q_c, baidu_cookie=b_c)
    saved = load_saved_settings()
    return {
        "success": True,
        "quark_cookie": saved.get("quark_cookie", ""),
        "baidu_cookie": saved.get("baidu_cookie", ""),
        "has_quark": bool(saved.get("quark_cookie")),
        "has_baidu": bool(saved.get("baidu_cookie")),
        "message": "配置已成功保存！"
    }


@app.post("/api/settings/auto-detect", summary="自动从本机浏览器提取并保存 Cookie")
async def api_auto_detect_settings():
    return auto_detect_and_save()


@app.post("/api/generate", response_model=GenerateResponse, summary="一键全流程转存与本地二创生成")
async def api_generate(
    payload: GenerateRequest,
    x_quark_cookie: Optional[str] = Header(None, alias="x-quark-cookie"),
    x_baidu_cookie: Optional[str] = Header(None, alias="x-baidu-cookie")
):
    """
    核心接口：
    1. 接收输入内容（支持纯链接，或推文正文+链接）
    2. 自动判定平台（夸克 Quark / 百度网盘 Baidu）
    3. 自动识别提取码
    4. 执行对应网盘的转存并生成新的分享链接
    5. 本地智能算法对文案或文件信息进行二创重塑（零第三方 AI API）
    6. 输出可直接发布的推特推文
    """
    input_text = (payload.text or payload.link or "").strip()
    if not input_text:
        raise HTTPException(status_code=400, detail="请输入网盘分享链接或推特原帖内容")

    # 1. 提取并判定链接（支持短链重定向自动穿透）
    parsed = await parse_content_async(input_text)
    links = parsed["links"]
    passcode = payload.passcode.strip() if payload.passcode else parsed.get("passcode", "")
    clean_text = parsed.get("clean_text", "")

    if not links:
        detected_plat = detect_platform(input_text)
        if detected_plat != "unknown":
            links = [input_text]
            parsed["platform"] = detected_plat
        else:
            raise HTTPException(
                status_code=400,
                detail="未检测到有效的网盘分享链接！请粘贴包含夸克（pan.quark.cn）或百度网盘（pan.baidu.com）的分享链接。"
            )

    target_link = links[0]
    # 若链接自身明确携带 ?pwd= 提取码参数，以该参数为最高权威准则（彻底杜绝残留旧提取码导致的验证失败）
    link_pwd_match = re.search(r'[?&]pwd=([a-zA-Z0-9]{4,6})', target_link)
    if link_pwd_match:
        passcode = link_pwd_match.group(1)

    platform = parsed["platform"]
    if platform == "unknown":
        platform = detect_platform(target_link)

    # Cookie 凭证获取与智能清洗提取（支持前端传递、本地 settings.json 缓存、以及从浏览器自动提取）
    saved_cfg = load_saved_settings()
    raw_quark_cookie = (
        payload.quark_cookie
        or x_quark_cookie
        or saved_cfg.get("quark_cookie")
        or config.QUARK_COOKIE
    )
    raw_baidu_cookie = (
        payload.baidu_cookie
        or x_baidu_cookie
        or saved_cfg.get("baidu_cookie")
        or config.BAIDU_COOKIE
    )

    quark_cookie = clean_and_extract_cookie(raw_quark_cookie)
    baidu_cookie = clean_and_extract_cookie(raw_baidu_cookie)

    # 若对应平台 Cookie 为空，自动尝试从本机已登录的浏览器中提取
    if platform == "quark" and not quark_cookie:
        logger.info("夸克 Cookie 为空，正在从本机浏览器自动扫描提取...")
        auto_res = auto_detect_and_save()
        quark_cookie = clean_and_extract_cookie(auto_res.get("quark_cookie", ""))

    if platform == "baidu" and not baidu_cookie:
        logger.info("百度 Cookie 为空，正在从本机浏览器自动扫描提取...")
        auto_res = auto_detect_and_save()
        baidu_cookie = clean_and_extract_cookie(auto_res.get("baidu_cookie", ""))

    new_share_url = None
    new_passcode = ""
    share_title = payload.custom_title or ""
    files_list = []
    file_count = 0
    total_size = 0
    transfer_msg = None

    # 2. 执行网盘转存与再分享（必须生成用户自己的专属链接）
    if platform == "quark":
        if not quark_cookie:
            raise HTTPException(
                status_code=400,
                detail="未配置夸克网盘 Cookie，无法自动转存到你的网盘并生成专属分享链接。请先在右上角【设置】中粘贴并保存夸克 Cookie！"
            )
        try:
            service = QuarkPanService(cookie=quark_cookie)
            res = await service.transfer_and_reshare(
                share_url=target_link,
                passcode=passcode,
                custom_title=payload.custom_title
            )
            new_share_url = res.get("new_share_url")
            new_passcode = res.get("passcode", "")
            share_title = res.get("title", share_title)
            files_list = res.get("files", [])
            file_count = res.get("file_count", len(files_list))
            total_size = sum(f.get("file_size", 0) or 0 for f in files_list)
            transfer_msg = "夸克网盘转存并生成专属新链接成功！"
        except Exception as exc:
            logger.error(f"夸克转存失败: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"夸克网盘转存与生成专属链接失败: {str(exc)}")

    elif platform == "baidu":
        if not baidu_cookie:
            raise HTTPException(
                status_code=400,
                detail="未配置百度网盘 Cookie，无法自动转存到你的网盘并生成专属分享链接。请先在右上角【设置】中粘贴并保存百度 Cookie！"
            )
        try:
            service = BaiduPanService(cookie=baidu_cookie)
            res = await service.transfer_and_reshare(
                share_url=target_link,
                passcode=passcode,
                custom_title=payload.custom_title
            )
            new_share_url = res.get("new_share_url")
            new_passcode = res.get("passcode", "")
            share_title = res.get("title", share_title)
            files_list = res.get("files", [])
            file_count = res.get("file_count", len(files_list))
            total_size = sum(int(f.get("size", 0) or 0) for f in files_list)
            transfer_msg = "百度网盘转存并生成专属新链接成功！"
        except Exception as exc:
            logger.error(f"百度网盘转存失败: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"百度网盘转存与生成专属链接失败: {str(exc)}")
    else:
        raise HTTPException(status_code=400, detail="暂不支持该网盘类型，仅支持夸克网盘与百度网盘")

    # 3. 严格校验：专属新链接必须存在，绝不能放原作者的原始链接
    if not new_share_url:
        raise HTTPException(status_code=500, detail="未能生成你的个人网盘专属分享链接，请重试或检查网盘容量与 Cookie！")

    effective_link = new_share_url
    effective_passcode = new_passcode

    # 4. 纯本地智能算法二创生成推广文案，并将用户的专属新链接直接集成进文案中！
    rewritten_text = generate_copy(
        title=share_title,
        files=files_list,
        file_count=file_count,
        total_size=total_size,
        platform=platform,
        original_text=clean_text,
        share_link=effective_link,
        passcode=effective_passcode
    )

    final_tweet = rewritten_text

    return GenerateResponse(
        success=True,
        platform=platform,
        original_link=target_link,
        new_link=new_share_url,
        passcode=effective_passcode,
        title=share_title,
        file_count=file_count,
        files=files_list,
        rewritten_text=rewritten_text,
        final_tweet=final_tweet,
        transfer_msg=transfer_msg
    )


# ================= 静态资源托管与首页路由 =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", summary="首页入口")
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse(
        content={"message": "网盘链接转存工具 API 运行正常，未找到静态前端页面"}
    )


if __name__ == "__main__":
    logger.info(f"正在启动网盘链接转存服务: http://{config.HOST}:{config.PORT}")
    uvicorn.run(
        "app:app",
        host=config.HOST,
        port=config.PORT,
        reload=True
    )
