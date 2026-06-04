import json
import re
from typing import Any, Dict

from langchain_openai import ChatOpenAI

from config import load_app_config
from core.logging_config import get_logger


logger = get_logger(__name__)


def create_llm() -> ChatOpenAI:
    llm_config = load_app_config()["llm"]
    api_key = str(llm_config.get("api_key", "") or "").strip()
    if not api_key:
        raise ValueError("未检测到 LLM API Key，请先在环境变量或配置中完成设置。")

    kwargs: Dict[str, Any] = {
        "model": llm_config.get("model", "gpt-4o-mini"),
        "api_key": api_key,
        "temperature": float(llm_config.get("temperature", 0.2)),
        "timeout": float(llm_config.get("timeout", 12)),
        "max_retries": int(llm_config.get("max_retries", 0)),
    }

    base_url = llm_config.get("base_url")
    if base_url:
        kwargs["base_url"] = base_url

    logger.info(
        "llm.create model=%s base_url_configured=%s timeout=%s max_retries=%s",
        kwargs["model"],
        bool(base_url),
        kwargs["timeout"],
        kwargs["max_retries"],
    )
    return ChatOpenAI(**kwargs)


def extract_json_block(text: str) -> Dict[str, Any]:
    if not text or not isinstance(text, str):
        raise ValueError("LLM 未返回有效文本。")

    cleaned = text.strip()

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced_match:
        return json.loads(fenced_match.group(1))

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])

    raise ValueError(f"未能从模型输出中提取 JSON：\n{cleaned}")
