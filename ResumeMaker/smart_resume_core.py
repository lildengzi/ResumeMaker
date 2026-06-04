from dotenv import load_dotenv

from core import (
    DEFAULT_STYLE_CONFIG,
    build_local_resume_draft,
    create_llm,
    ensure_modular_resume_shape,
    ensure_resume_shape,
    extract_json_block,
    format_contact_line,
    get_default_modular_resume_data,
    get_default_resume_data,
    get_photo_bytes,
    get_photo_data_uri,
    load_resume_data,
    merge_resume,
    migrate_legacy_resume,
    normalize_experience_items,
    normalize_list_of_strings,
    optimize_resume_by_jd,
    render_markdown,
    save_resume_data,
)


# smart_resume_core.py 现在作为“兼容入口层”保留：
# - 旧代码仍可继续 from smart_resume_core import ...
# - 具体实现已下沉到 core/ 子模块
# - 后续可以逐步把调用方直接改为从 core.xxx 导入
load_dotenv()

__all__ = [
    "DEFAULT_STYLE_CONFIG",
    "build_local_resume_draft",
    "create_llm",
    "ensure_modular_resume_shape",
    "ensure_resume_shape",
    "extract_json_block",
    "format_contact_line",
    "get_default_modular_resume_data",
    "get_default_resume_data",
    "get_photo_bytes",
    "get_photo_data_uri",
    "load_resume_data",
    "merge_resume",
    "migrate_legacy_resume",
    "normalize_experience_items",
    "normalize_list_of_strings",
    "optimize_resume_by_jd",
    "render_markdown",
    "save_resume_data",
]
