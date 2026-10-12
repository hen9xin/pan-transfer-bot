"""
DeepSeek AI 文案改写服务
使用 DeepSeek OpenAI 兼容接口对推特/X 内容进行二次创作改写。
"""

import logging
from typing import Optional
import httpx

from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "你是一个资深的社交媒体爆款文案专家，精通推特/X平台的高互动传播风格。\n"
    "请对用户提供的推文内容进行二创重写（Secondary Creation）：\n"
    "1. 核心保留：完整保留原内容的核心干货与关键事实信息；\n"
    "2. 语言重构：大幅改变句式结构与用词，彻底摆脱原文句序，形成全新表达；\n"
    "3. 吸睛排版：语言精练短小，节奏明快，合理分段并适当添加 2~4 个相关的 Emoji 表情提升可读性；\n"
    "4. 平台适配：符合 Twitter/X 短文本风格，富有感染力和互动感；\n"
    "5. 纯净输出：仅返回改写后的最终推文文本，切勿添加任何客套话、解释、前缀或引号。"
)


async def rewrite_tweet_text(
    text: str,
    system_prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> str:
    """
    使用 DeepSeek API 异步改写文本

    :param text: 待改写的原始文本
    :param system_prompt: 自定义系统提示词（可选）
    :param api_key: 自定义 API Key（可选，默认读取配置）
    :param model: 自定义模型名称（可选，默认读取配置）
    :return: 改写后的文本
    :raises RuntimeError: 当 API 请求失败或配置缺失时
    """
    if not text or not text.strip():
        return ""

    key = api_key or DEEPSEEK_API_KEY
    if not key or key == "your_deepseek_api_key_here":
        raise ValueError("DeepSeek API Key 未配置，请在 .env 文件中设置 DEEPSEEK_API_KEY")

    endpoint = DEEPSEEK_API_URL or "https://api.deepseek.com/v1/chat/completions"
    target_model = model or DEEPSEEK_MODEL or "deepseek-chat"
    sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": text.strip()}
        ],
        "temperature": 0.7,
        "max_tokens": 1024,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"DeepSeek API 请求失败: 状态码 {response.status_code}, 内容: {error_detail}")
                raise RuntimeError(f"DeepSeek API 响应异常 (HTTP {response.status_code}): {error_detail}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("DeepSeek API 返回结果为空，未包含 choices 字段")

            rewritten_text = choices[0].get("message", {}).get("content", "").strip()
            if not rewritten_text:
                raise RuntimeError("DeepSeek API 生成的内容为空")

            return rewritten_text

    except httpx.TimeoutException as exc:
        logger.error(f"DeepSeek API 请求超时: {exc}")
        raise RuntimeError("DeepSeek API 请求超时，请检查网络连接或稍后重试") from exc
    except httpx.RequestError as exc:
        logger.error(f"DeepSeek API 网络请求异常: {exc}")
        raise RuntimeError(f"DeepSeek API 请求发生网络错误: {str(exc)}") from exc
    except Exception as exc:
        logger.error(f"DeepSeek 文案改写异常: {exc}", exc_info=True)
        raise
