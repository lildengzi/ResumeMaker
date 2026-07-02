import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = Path(os.getenv("RESUMEMAKER_CONFIG_PATH", BASE_DIR / "config.json"))
DEFAULT_ENV_PATH = BASE_DIR / ".env"

if "PYTEST_VERSION" not in os.environ:
    load_dotenv(DEFAULT_ENV_PATH, override=True)


DEFAULT_CONFIG: Dict[str, Any] = {
    "storage": {
        "resume_data_file": "resume_data.json",
        "database_file": "app.db",
        "asset_dir": "assets",
        "upload_dir": "uploads",
    },
    "llm": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "temperature_env": "LLM_TEMPERATURE",
        "timeout_env": "LLM_TIMEOUT",
        "max_retries_env": "LLM_MAX_RETRIES",
        "temperature": 0.2,
        "timeout": 12,
        "max_retries": 0,
    },
    "workflow": {
        "max_history": 3,
        "entry_agent": "info_collector",
        "parser_agent": "existing_resume_parser",
        "writer_agent": "resume_writer",
        "fallback_to_local_draft": True,
    },
    "preview": {
        "page_title": "智能简历生成器 MVP",
        "page_icon": "📄",
        "stage_background": "#eef2f7",
        "page_background": "#ffffff",
        "page_shadow": "0 10px 30px rgba(15, 23, 42, 0.14)",
        "page_border": "#dbe2ea",
        "accent_color": "#2563eb",
        "text_primary": "#111827",
        "text_secondary": "#374151",
        "text_muted": "#64748b",
        "section_border": "#dbe7f5",
        "a4_width_px": 794,
        "a4_min_height_px": 1123,
        "page_padding": "56px 52px",
        "line_height": 1.65,
        "name_font_size": 30,
        "headline_font_size": 16,
        "section_title_font_size": 16,
        "body_font_size": 13,
    },
    "resume_style": {
        "defaults": {
            "template": "modern_blue",
            "font_size": 14,
            "page_margin": 32,
            "line_height": 1.65,
            "name_font_size": 30,
            "headline_font_size": 16,
            "section_title_font_size": 16,
            "body_font_size": 13,
            "sidebar_preview_height": 1320,
            "preview_scale": 100,
            "show_photo": True,
            "dense_mode": False,
        },
        "templates": {
            "modern_blue": {
                "template_label": "现代蓝",
                "stage_background": "#eef4ff",
                "page_background": "#ffffff",
                "page_shadow": "0 20px 45px rgba(37, 99, 235, 0.12)",
                "page_border": "#dbe7ff",
                "accent_color": "#2563eb",
                "accent_soft": "#eff6ff",
                "text_primary": "#0f172a",
                "text_secondary": "#334155",
                "text_muted": "#64748b",
                "section_border": "#bfdbfe",
                "tag_background": "#eff6ff",
                "tag_text": "#1d4ed8",
                "timeline_color": "#93c5fd",
                "font_family": '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
            },
            "elegant_gray": {
                "template_label": "雅致灰",
                "stage_background": "#f3f4f6",
                "page_background": "#ffffff",
                "page_shadow": "0 18px 38px rgba(17, 24, 39, 0.10)",
                "page_border": "#e5e7eb",
                "accent_color": "#4b5563",
                "accent_soft": "#f3f4f6",
                "text_primary": "#111827",
                "text_secondary": "#374151",
                "text_muted": "#6b7280",
                "section_border": "#d1d5db",
                "tag_background": "#f3f4f6",
                "tag_text": "#374151",
                "timeline_color": "#d1d5db",
                "font_family": '"Georgia", "PingFang SC", "Microsoft YaHei", serif',
            },
            "emerald_pro": {
                "template_label": "翡翠专业",
                "stage_background": "#ecfdf5",
                "page_background": "#ffffff",
                "page_shadow": "0 20px 42px rgba(16, 185, 129, 0.10)",
                "page_border": "#d1fae5",
                "accent_color": "#059669",
                "accent_soft": "#ecfdf5",
                "text_primary": "#064e3b",
                "text_secondary": "#065f46",
                "text_muted": "#6b7280",
                "section_border": "#a7f3d0",
                "tag_background": "#d1fae5",
                "tag_text": "#047857",
                "timeline_color": "#6ee7b7",
                "font_family": '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
            },
        },
    },
    "resume": {
        "default_name": "未命名候选人",
        "default_headline": "未填写应聘岗位",
        "empty_text": "暂无",
        "minimum_required_fields": ["name", "headline"],
        "role_skills_map": {
            "python": ["Python 开发", "FastAPI / Flask", "MySQL / PostgreSQL", "接口设计", "Git 协作"],
            "java": ["Java 开发", "Spring Boot", "MySQL", "RESTful API", "Git 协作"],
            "后端": ["后端开发", "接口设计", "数据库基础", "日志排查", "Git 协作"],
            "前端": ["HTML / CSS / JavaScript", "页面开发", "组件化思维", "接口联调", "Git 协作"],
            "测试": ["测试用例设计", "缺陷跟踪", "接口测试", "基础自动化", "沟通协作"],
            "产品": ["需求分析", "原型设计", "跨团队沟通", "文档撰写", "数据分析基础"],
            "运营": ["活动执行", "内容运营", "数据整理", "用户分析", "跨部门协同"],
            "算法": ["Python", "数据结构与算法", "模型调试基础", "数据处理", "实验分析"],
        },
        "default_skills": ["办公软件应用", "文档整理", "沟通协作", "学习能力", "执行力"],
        "default_self_evaluation_templates": [
            "具备明确的 {role_name} 求职方向，能够持续学习并快速适应新的工作要求。",
            "做事认真负责，具备良好的沟通协作意识与执行能力。",
            "能够根据任务目标主动推进工作，注重结果输出与问题复盘。",
        ],
    },
    "prompts": {
        "resume_writer_system": "你是一名资深中文简历优化专家。",
        "resume_writer_rules": [
            "输出必须是合法 JSON，对象结构必须与输入简历一致。",
            "不要虚构不存在的教育、公司、项目、获奖、证书。",
            "可以优化 skills、projects、companyExperience、campusExperience、selfEvaluation 的表达。",
            "保留 basics 和 education 的事实信息，不要修改姓名、联系方式、学校等事实字段。",
            "如果提供了 JD，就强化与 JD 相关的技术关键词、业务价值、量化表达，但必须基于已有经历合理润色。",
            "如果没有提供 JD，就进行通用优化，提升表达清晰度、专业性、可读性和简历呈现效果。",
            "highlights 必须是字符串数组。",
            "如果用户当前信息非常少，也不要报错。",
            "绝不要编造具体公司、项目名称、时间、业绩数字。",
            "只返回 JSON，不要输出解释、标题、代码块说明。",
        ],
        "resume_writer_with_jd": "岗位描述 JD：\n{jd_text}\n\n请结合 JD 做针对性优化。",
        "resume_writer_without_jd": "当前未提供 JD。请基于现有简历信息做通用优化，重点提升表达清晰度、专业性、可读性和简历呈现效果。",
        "info_collector_system": "你是一名信息整理助手，负责汇总输入的岗位描述、已有简历数据和上传文件元信息，不进行编造。",
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_app_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    if "PYTEST_VERSION" not in os.environ:
        load_dotenv(DEFAULT_ENV_PATH, override=True)
    config = deepcopy(DEFAULT_CONFIG)
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as file:
            user_config = json.load(file)
        config = _deep_merge(config, user_config)

    llm_config = config["llm"]
    api_key_env = llm_config.get("api_key_env", "OPENAI_API_KEY")
    base_url_env = llm_config.get("base_url_env", "OPENAI_BASE_URL")
    model_env = llm_config.get("model_env", "LLM_MODEL")
    temperature_env = llm_config.get("temperature_env", "LLM_TEMPERATURE")
    timeout_env = llm_config.get("timeout_env", "LLM_TIMEOUT")
    max_retries_env = llm_config.get("max_retries_env", "LLM_MAX_RETRIES")

    configured_api_key = str(llm_config.get("api_key", "") or "").strip()
    env_api_key = str(os.getenv(api_key_env, "") or "").strip()
    llm_config["api_key"] = configured_api_key or env_api_key

    configured_base_url = str(llm_config.get("base_url", "") or "").strip()
    env_base_url = str(os.getenv(base_url_env, "") or "").strip()
    llm_config["base_url"] = configured_base_url or (env_base_url or None)

    configured_model = str(llm_config.get("model", "") or "").strip()
    env_model = str(os.getenv(model_env, "") or "").strip()
    if configured_model or env_model:
        llm_config["model"] = configured_model or env_model

    temperature = os.getenv(temperature_env)
    if temperature:
        try:
            llm_config["temperature"] = float(temperature)
        except ValueError:
            llm_config["temperature"] = llm_config.get("temperature", 0.2)

    timeout = os.getenv(timeout_env)
    if timeout:
        try:
            llm_config["timeout"] = float(timeout)
        except ValueError:
            llm_config["timeout"] = llm_config.get("timeout", 12)

    max_retries = os.getenv(max_retries_env)
    if max_retries:
        try:
            llm_config["max_retries"] = int(max_retries)
        except ValueError:
            llm_config["max_retries"] = llm_config.get("max_retries", 0)

    return config


APP_CONFIG = load_app_config()


def save_app_config(config: Dict[str, Any], config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)


def update_resume_style_config(
    style_defaults: Dict[str, Any],
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    template_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    config = load_app_config(config_path)
    config.setdefault("resume_style", {})
    config["resume_style"]["defaults"] = deepcopy(style_defaults)

    if template_overrides is not None:
        config["resume_style"]["templates"] = deepcopy(template_overrides)

    save_app_config(config, config_path)

    global APP_CONFIG
    APP_CONFIG = config
    return config


def update_llm_config(
    llm_updates: Dict[str, Any],
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> Dict[str, Any]:
    config = load_app_config(config_path)
    config.setdefault("llm", {})
    llm_config = config["llm"]

    for key in ("api_key", "base_url", "model"):
        if key not in llm_updates:
            continue
        value = str(llm_updates.get(key, "") or "").strip()
        llm_config[key] = value or (None if key == "base_url" else "")

    save_app_config(config, config_path)

    global APP_CONFIG
    APP_CONFIG = config
    return config


def get_path_from_storage(key: str) -> Path:
    storage_config = APP_CONFIG["storage"]
    return BASE_DIR / storage_config[key]
