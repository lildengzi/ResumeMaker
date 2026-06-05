import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import get_path_from_storage
from tools.permission import ensure_workspace_path


RESUME_DATA_FILE = get_path_from_storage("resume_data_file")

DEFAULT_STYLE_CONFIG: Dict[str, Any] = {
    "theme_color": "#2563eb",
    "font_size": 14,
    "line_height": 1.6,
    "page_margin": 40,
    "module_gap": 24,
    "show_photo": True,
}

DEFAULT_INPUTS: Dict[str, Any] = {
    "jd_text": "",
    "jd_source": "manual",
    "jd_url_input": "",
    "jd_ocr_text": "",
    "uploaded_readme_text": "",
    "existing_resume_name": "",
    "uploaded_files": [],
}

INPUT_TEXT_FIELDS = (
    "jd_text",
    "jd_source",
    "jd_url_input",
    "jd_ocr_text",
    "uploaded_readme_text",
    "existing_resume_name",
)

PERSISTENT_UPLOAD_TYPES = {"readme", "existing_resume"}


CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def sanitize_text_value(value: Any, max_length: int = 2000) -> str:
    text = CONTROL_CHARS_RE.sub("", str(value or ""))
    return text.strip()[:max_length]


def sanitize_photo_path(value: Any) -> str:
    raw_path = sanitize_text_value(value, max_length=500)
    if not raw_path:
        return ""
    try:
        safe_path = ensure_workspace_path(raw_path)
    except ValueError:
        return ""
    if "uploads" not in [part.lower() for part in safe_path.parts]:
        return ""
    return str(safe_path)

MODULE_TYPE_LABELS: Dict[str, str] = {
    "education": "教育经历",
    "skills": "专业技能",
    "projects": "项目经历",
    "companyExperience": "实习 / 工作经历",
    "campusExperience": "校园经历",
    "selfEvaluation": "自我评价",
    "custom": "通用模块",
}

GENERIC_MODULE_TYPE = "custom"
GENERIC_MODULE_TITLE = "通用模块"

MODULE_ITEM_TEMPLATES: Dict[str, Any] = {
    "education": {
        "school": "",
        "degree": "",
        "major": "",
        "startDate": "",
        "endDate": "",
        "details": "",
    },
    "projects": {
        "name": "",
        "role": "",
        "startDate": "",
        "endDate": "",
        "description": "",
        "highlights": [],
    },
    "companyExperience": {
        "company": "",
        "role": "",
        "startDate": "",
        "endDate": "",
        "description": "",
        "highlights": [],
    },
    "campusExperience": {
        "organization": "",
        "role": "",
        "startDate": "",
        "endDate": "",
        "description": "",
        "highlights": [],
    },
}


def _build_module(
    module_id: str,
    title: str,
    module_type: str,
    order: int,
    content: Dict[str, Any],
    visible: bool = True,
) -> Dict[str, Any]:
    return {
        "id": module_id,
        "title": title,
        "type": module_type,
        "visible": visible,
        "order": order,
        "content": content,
    }


def create_module(module_type: str, order: int, title: Optional[str] = None) -> Dict[str, Any]:
    module_id = f"{module_type}_{order}"
    resolved_title = title or MODULE_TYPE_LABELS.get(module_type, GENERIC_MODULE_TITLE)

    if module_type in ["education", "projects", "companyExperience", "campusExperience"]:
        content = {"items": [deepcopy(MODULE_ITEM_TEMPLATES[module_type])]}
    elif module_type in ["skills", "selfEvaluation", "custom"]:
        content = {"items": []}
    else:
        content = {"items": []}

    return _build_module(module_id, resolved_title, module_type, order, content)


class ModuleFactory:
    """集中创建简历模块，避免页面层直接拼装模块结构。"""

    @staticmethod
    def create(module_type: str, order: int, title: Optional[str] = None) -> Dict[str, Any]:
        return create_module(module_type, order, title)

    @staticmethod
    def create_generic(order: int, title: Optional[str] = None) -> Dict[str, Any]:
        return create_module(GENERIC_MODULE_TYPE, order, title or GENERIC_MODULE_TITLE)


def create_generic_module(order: int, title: Optional[str] = None) -> Dict[str, Any]:
    return ModuleFactory.create_generic(order, title)


def normalize_basics(basics: Any, template_basics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    normalized = deepcopy(template_basics or {})
    if isinstance(basics, dict):
        normalized.update(basics)

    for key, value in list(normalized.items()):
        normalized[key] = sanitize_text_value(value, max_length=500)

    normalized["photo_path"] = sanitize_photo_path(normalized.get("photo_path", ""))

    legacy_github = str(normalized.get("github", "") or "").strip()
    if legacy_github and not str(normalized.get("website", "") or "").strip():
        normalized["website"] = legacy_github

    normalized.setdefault("website", "")
    normalized.setdefault("portfolio", "")
    normalized.pop("github", None)
    return normalized


def _build_default_resume_template() -> Dict[str, Any]:
    return {
        "basics": {
            "name": "",
            "headline": "",
            "age": "",
            "gender": "",
            "city": "",
            "phone": "",
            "email": "",
            "website": "",
            "portfolio": "",
            "photo_path": "",
        },
        "modules": [
            create_module("education", 1, "教育经历"),
            create_module("skills", 2, "专业技能"),
            create_module("projects", 3, "项目经历"),
            create_module("companyExperience", 4, "实习 / 工作经历"),
            create_module("campusExperience", 5, "校园经历"),
            create_module("selfEvaluation", 6, "自我评价"),
        ],
        "style": deepcopy(DEFAULT_STYLE_CONFIG),
    }


def get_default_resume_data() -> Dict[str, Any]:
    return _build_default_resume_template()


def normalize_list_of_strings(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    result: List[str] = []
    for item in items:
        if isinstance(item, str):
            stripped = sanitize_text_value(item)
            if stripped:
                result.append(stripped)
    return result


def normalize_experience_items(items: Any, item_type: str) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []

    template = deepcopy(MODULE_ITEM_TEMPLATES.get(item_type, {}))
    normalized_items: List[Dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        merged = deepcopy(template)
        merged.update(item)
        for key, value in list(merged.items()):
            if key == "highlights":
                continue
            if isinstance(value, str):
                merged[key] = sanitize_text_value(value, max_length=1000)
        if "highlights" in merged:
            merged["highlights"] = normalize_list_of_strings(merged.get("highlights", []))
        normalized_items.append(merged)

    return normalized_items


def _normalize_custom_field(field: Any) -> Dict[str, str]:
    if isinstance(field, dict):
        label = sanitize_text_value(field.get("label", field.get("name", "")), max_length=120)
        value = sanitize_text_value(field.get("value", ""), max_length=1000)
        if not value and label in field:
            value = sanitize_text_value(field.get(label, ""), max_length=1000)
        return {"label": "General subfield", "value": value}
    if isinstance(field, str):
        return {"label": "General subfield", "value": sanitize_text_value(field, max_length=1000)}
    return {"label": "General subfield", "value": ""}


def _normalize_custom_content(content: Any) -> Dict[str, Any]:
    if not isinstance(content, dict):
        content = {}

    fields = [_normalize_custom_field(field) for field in content.get("fields", []) if isinstance(field, (dict, str))]
    fields = [field for field in fields if field["value"]]
    description = sanitize_text_value(content.get("description", ""), max_length=4000)
    highlights = normalize_list_of_strings(content.get("highlights", []))

    legacy_items = content.get("items", [])
    if isinstance(legacy_items, list):
        legacy_descriptions: List[str] = []
        for item in legacy_items:
            if isinstance(item, dict):
                for key in ["name", "title", "role", "startDate", "endDate"]:
                    value = sanitize_text_value(item.get(key, ""), max_length=1000)
                    if value:
                        fields.append({"label": "General subfield", "value": value})
                item_description = sanitize_text_value(item.get("description", ""), max_length=4000)
                if item_description:
                    legacy_descriptions.append(item_description)
                highlights.extend(normalize_list_of_strings(item.get("highlights", [])))
            elif isinstance(item, str) and sanitize_text_value(item):
                legacy_descriptions.append(sanitize_text_value(item, max_length=4000))

        if not description and legacy_descriptions:
            description = "\n".join(legacy_descriptions)

    return {
        "fields": fields,
        "description": description,
        "highlights": highlights,
    }


def _normalize_custom_items(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            title = str(item.get("title", "") or "").strip()
            role = str(item.get("role", "") or "").strip()
            start_date = str(item.get("startDate", "") or "").strip()
            end_date = str(item.get("endDate", "") or "").strip()
            description = str(item.get("description", "") or "").strip()
            highlights = normalize_list_of_strings(item.get("highlights", []))
            if title or role or start_date or end_date or description or highlights:
                result.append(
                    {
                        "title": title,
                        "role": role,
                        "startDate": start_date,
                        "endDate": end_date,
                        "description": description,
                        "highlights": highlights,
                    }
                )
            continue
        elif isinstance(item, str):
            stripped = item.strip()
            if stripped:
                result.append(
                    {
                        "title": "",
                        "role": "",
                        "startDate": "",
                        "endDate": "",
                        "description": stripped,
                        "highlights": [],
                    }
                )
    return result


def normalize_module_content(module_type: str, content: Any) -> Dict[str, Any]:
    if not isinstance(content, dict):
        content = {}

    items = content.get("items", [])

    if module_type == "education":
        return {"items": normalize_experience_items(items, "education")}
    if module_type == "projects":
        return {"items": normalize_experience_items(items, "projects")}
    if module_type == "companyExperience":
        return {"items": normalize_experience_items(items, "companyExperience")}
    if module_type == "campusExperience":
        return {"items": normalize_experience_items(items, "campusExperience")}
    if module_type in ["skills", "selfEvaluation"]:
        return {"items": normalize_list_of_strings(items)}
    return _normalize_custom_content(content)


def normalize_uploaded_file_meta(file_meta: Any) -> Dict[str, Any] | None:
    if not isinstance(file_meta, dict):
        return None

    normalized: Dict[str, Any] = {
        "name": sanitize_text_value(file_meta.get("name", ""), max_length=300),
        "original_name": sanitize_text_value(file_meta.get("original_name", ""), max_length=300),
        "type": sanitize_text_value(file_meta.get("type", ""), max_length=80),
        "file_type": sanitize_text_value(file_meta.get("file_type", ""), max_length=80),
        "classification": sanitize_text_value(file_meta.get("classification", ""), max_length=80),
        "suffix": sanitize_text_value(file_meta.get("suffix", ""), max_length=20),
        "parse_status": sanitize_text_value(file_meta.get("parse_status", ""), max_length=80),
        "material_category": sanitize_text_value(file_meta.get("material_category", ""), max_length=80),
        "material_title": sanitize_text_value(file_meta.get("material_title", ""), max_length=300),
        "raw_text": sanitize_text_value(file_meta.get("raw_text", ""), max_length=20000),
    }

    raw_path = sanitize_text_value(file_meta.get("path", ""), max_length=500)
    if raw_path:
        try:
            normalized["path"] = str(ensure_workspace_path(raw_path))
        except ValueError:
            normalized["path"] = ""
    else:
        normalized["path"] = ""

    try:
        normalized["size_bytes"] = int(file_meta.get("size_bytes", 0) or 0)
    except (TypeError, ValueError):
        normalized["size_bytes"] = 0

    notes = file_meta.get("notes", [])
    normalized["notes"] = normalize_list_of_strings(notes)[:8] if isinstance(notes, list) else []
    metadata = file_meta.get("metadata", {})
    normalized["metadata"] = deepcopy(metadata) if isinstance(metadata, dict) else {}

    if not normalized["name"] and normalized["original_name"]:
        normalized["name"] = normalized["original_name"]
    if not normalized["original_name"] and normalized["name"]:
        normalized["original_name"] = normalized["name"]
    return normalized if normalized["name"] or normalized["path"] or normalized["raw_text"] else None


def normalize_inputs(inputs: Any) -> Dict[str, Any]:
    normalized = deepcopy(DEFAULT_INPUTS)
    if not isinstance(inputs, dict):
        return normalized

    for key in INPUT_TEXT_FIELDS:
        normalized[key] = sanitize_text_value(inputs.get(key, normalized.get(key, "")), max_length=20000)

    files = []
    raw_files = inputs.get("uploaded_files", [])
    if isinstance(raw_files, list):
        for file_meta in raw_files:
            normalized_file = normalize_uploaded_file_meta(file_meta)
            if normalized_file is not None:
                files.append(normalized_file)
    normalized["uploaded_files"] = files
    return normalized


def normalize_persistent_inputs(inputs: Any) -> Dict[str, Any]:
    normalized = normalize_inputs(inputs)
    persisted_files = [
        file_meta
        for file_meta in normalized.get("uploaded_files", [])
        if file_meta.get("type") in PERSISTENT_UPLOAD_TYPES
    ]
    return {
        "uploaded_readme_text": normalized.get("uploaded_readme_text", ""),
        "existing_resume_name": normalized.get("existing_resume_name", ""),
        "uploaded_files": persisted_files,
    }


def _has_section_content(items: Any) -> bool:
    if not isinstance(items, list):
        return False
    for item in items:
        if isinstance(item, str) and item.strip():
            return True
        if isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str) and value.strip():
                    return True
                if isinstance(value, list) and _has_section_content(value):
                    return True
    return False


def has_module_content(module: Dict[str, Any]) -> bool:
    content = module.get("content", {}) if isinstance(module.get("content"), dict) else {}
    if str(module.get("type", "") or "") == "custom":
        return bool(
            _has_section_content(content.get("fields", []))
            or str(content.get("description", "") or "").strip()
            or _has_section_content(content.get("highlights", []))
            or _has_section_content(content.get("items", []))
        )
    return _has_section_content(content.get("items", []))


def _sync_legacy_sections_to_modules(data: Dict[str, Any], modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """兼容旧代码直接修改顶层 education/skills/projects 等字段的场景。"""
    section_types = {
        "education": lambda value: normalize_experience_items(value, "education"),
        "skills": normalize_list_of_strings,
        "projects": lambda value: normalize_experience_items(value, "projects"),
        "companyExperience": lambda value: normalize_experience_items(value, "companyExperience"),
        "campusExperience": lambda value: normalize_experience_items(value, "campusExperience"),
        "selfEvaluation": normalize_list_of_strings,
    }

    synced = deepcopy(modules)
    for section, normalizer in section_types.items():
        if section not in data or not _has_section_content(data.get(section)):
            continue
        normalized_items = normalizer(data.get(section, []))
        for module in synced:
            if module.get("type") == section:
                module["content"] = {"items": deepcopy(normalized_items)}
                break

    return synced


def _ensure_unique_module_ids(modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """确保模块 ID 全局唯一，避免 Streamlit widget key 冲突。

    历史数据、AI 返回结果或旧版迁移数据中可能出现多个模块共享同一个 id。
    Streamlit 的 key 通常会基于模块 id 生成，因此这里在数据归一化阶段做兜底修复。
    """
    used_ids: set[str] = set()
    normalized: List[Dict[str, Any]] = []

    for idx, module in enumerate(modules, start=1):
        module_copy = deepcopy(module)
        module_type = str(module_copy.get("type") or "custom")
        base_id = str(module_copy.get("id") or "").strip() or f"{module_type}_{idx}"
        unique_id = base_id

        if unique_id in used_ids:
            suffix = 2
            unique_id = f"{base_id}_{idx}_{suffix}"
            while unique_id in used_ids:
                suffix += 1
                unique_id = f"{base_id}_{idx}_{suffix}"

        module_copy["id"] = unique_id
        used_ids.add(unique_id)
        normalized.append(module_copy)

    return normalized


def _legacy_from_modules(modules: List[Dict[str, Any]]) -> Dict[str, Any]:
    legacy = {
        "education": [],
        "skills": [],
        "projects": [],
        "companyExperience": [],
        "campusExperience": [],
        "selfEvaluation": [],
    }

    for module in sorted(modules, key=lambda item: int(item.get("order", 0))):
        if not bool(module.get("visible", True)):
            continue

        module_type = str(module.get("type", "custom"))
        items = module.get("content", {}).get("items", [])

        if module_type in legacy:
            legacy[module_type] = deepcopy(items)

    return legacy


def get_default_modular_resume_data() -> Dict[str, Any]:
    return deepcopy(get_default_resume_data())


def migrate_legacy_resume(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    template = get_default_modular_resume_data()
    if not isinstance(data, dict):
        return deepcopy(template)

    basics = normalize_basics(data.get("basics", {}), template["basics"])

    style = deepcopy(DEFAULT_STYLE_CONFIG)
    incoming_style = data.get("style", {})
    if isinstance(incoming_style, dict):
        style.update(incoming_style)

    if isinstance(data.get("modules"), list):
        modules: List[Dict[str, Any]] = []
        for idx, item in enumerate(data.get("modules", []), start=1):
            if not isinstance(item, dict):
                continue

            module_type = str(item.get("type") or "custom")
            modules.append(
                {
                    "id": str(item.get("id") or f"module_{idx}"),
                    "title": str(item.get("title") or MODULE_TYPE_LABELS.get(module_type, f"模块 {idx}")),
                    "type": module_type,
                    "visible": bool(item.get("visible", True)),
                    "order": int(item.get("order", idx)),
                    "content": normalize_module_content(module_type, item.get("content", {})),
                }
            )

        result = {
            "basics": basics,
            "modules": modules,
            "style": style,
        }
        if "inputs" in data:
            result["inputs"] = normalize_inputs(data.get("inputs", {}))
        return result

    modules = [
        _build_module(
            "education",
            "教育经历",
            "education",
            1,
            {"items": normalize_experience_items(data.get("education", []), "education")},
        ),
        _build_module(
            "skills",
            "专业技能",
            "skills",
            2,
            {"items": normalize_list_of_strings(data.get("skills", []))},
        ),
        _build_module(
            "projects",
            "项目经历",
            "projects",
            3,
            {"items": normalize_experience_items(data.get("projects", []), "projects")},
        ),
        _build_module(
            "company_experience",
            "实习 / 工作经历",
            "companyExperience",
            4,
            {"items": normalize_experience_items(data.get("companyExperience", []), "companyExperience")},
        ),
        _build_module(
            "campus_experience",
            "校园经历",
            "campusExperience",
            5,
            {"items": normalize_experience_items(data.get("campusExperience", []), "campusExperience")},
        ),
        _build_module(
            "self_evaluation",
            "自我评价",
            "selfEvaluation",
            6,
            {"items": normalize_list_of_strings(data.get("selfEvaluation", []))},
        ),
    ]

    result = {
        "basics": basics,
        "modules": modules,
        "style": style,
    }
    if "inputs" in data:
        result["inputs"] = normalize_inputs(data.get("inputs", {}))
    return result


def ensure_modular_resume_shape(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    migrated = migrate_legacy_resume(data)
    template = get_default_modular_resume_data()

    basics = normalize_basics(migrated.get("basics", {}), template["basics"])

    style = deepcopy(DEFAULT_STYLE_CONFIG)
    incoming_style = migrated.get("style", {})
    if isinstance(incoming_style, dict):
        style.update(incoming_style)

    migrated_modules = migrated.get("modules", [])

    modules: List[Dict[str, Any]] = []
    for idx, item in enumerate(migrated_modules, start=1):
        if not isinstance(item, dict):
            continue

        module_type = str(item.get("type") or "custom")
        modules.append(
            {
                "id": str(item.get("id") or f"module_{idx}"),
                "title": str(item.get("title") or MODULE_TYPE_LABELS.get(module_type, f"模块 {idx}")),
                "type": module_type,
                "visible": bool(item.get("visible", True)),
                "order": int(item.get("order", idx)),
                "content": normalize_module_content(module_type, item.get("content", {})),
            }
        )

    normalized_modules = _ensure_unique_module_ids(modules or deepcopy(template["modules"]))

    normalized = {
        "basics": basics,
        "modules": normalized_modules,
        "style": style,
    }
    if "inputs" in migrated:
        normalized["inputs"] = normalize_inputs(migrated.get("inputs", {}))
    return normalized


def ensure_resume_shape(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return ensure_modular_resume_shape(data)


def _is_default_resume_path(file_path: Path | str) -> bool:
    try:
        return ensure_workspace_path(file_path) == ensure_workspace_path(RESUME_DATA_FILE)
    except ValueError:
        return False


def _load_resume_data_json(file_path: Path | str = RESUME_DATA_FILE) -> Dict[str, Any]:
    safe_path = ensure_workspace_path(file_path)
    if not safe_path.exists():
        data = get_default_resume_data()
        _save_resume_data_json(data, safe_path)
        return data

    try:
        with safe_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return ensure_resume_shape(data)
    except (json.JSONDecodeError, OSError):
        data = get_default_resume_data()
        _save_resume_data_json(data, safe_path)
        return data


def _save_resume_data_json(data: Dict[str, Any], file_path: Path | str = RESUME_DATA_FILE) -> None:
    safe_path = ensure_workspace_path(file_path)
    shaped = ensure_resume_shape(data)
    normalized = {
        "basics": deepcopy(shaped.get("basics", {})),
        "modules": deepcopy(shaped.get("modules", [])),
        "style": deepcopy(shaped.get("style", {})),
    }
    input_source = data.get("inputs", shaped.get("inputs", {})) if isinstance(data, dict) else {}
    if input_source:
        normalized["inputs"] = normalize_persistent_inputs(input_source)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    with safe_path.open("w", encoding="utf-8") as file:
        json.dump(normalized, file, ensure_ascii=False, indent=2)


def load_resume_data(file_path: Path = RESUME_DATA_FILE) -> Dict[str, Any]:
    if _is_default_resume_path(file_path):
        try:
            from core.storage import load_workspace

            return load_workspace(legacy_resume_path=RESUME_DATA_FILE)
        except Exception:
            return _load_resume_data_json(file_path)
    return _load_resume_data_json(file_path)


def save_resume_data(data: Dict[str, Any], file_path: Path = RESUME_DATA_FILE) -> None:
    if _is_default_resume_path(file_path):
        try:
            from core.storage import save_workspace

            stored = save_workspace(data)
            _save_resume_data_json(stored, file_path)
            return
        except Exception:
            _save_resume_data_json(data, file_path)
            return
    _save_resume_data_json(data, file_path)


def merge_resume(original: Dict[str, Any], optimized: Dict[str, Any]) -> Dict[str, Any]:
    result = ensure_resume_shape(deepcopy(original))
    optimized = ensure_resume_shape(optimized)

    optimized_by_id = {module.get("id"): module for module in optimized.get("modules", [])}
    optimized_by_type = {module.get("type"): module for module in optimized.get("modules", [])}
    merged_modules: List[Dict[str, Any]] = []
    used_ids: set[str] = set()

    for module in result.get("modules", []):
        module_id = module.get("id")
        module_type = module.get("type")
        incoming = optimized_by_id.get(module_id) or optimized_by_type.get(module_type)
        if incoming:
            merged = deepcopy(module)
            merged["title"] = incoming.get("title", merged.get("title"))
            merged["visible"] = incoming.get("visible", merged.get("visible", True))
            merged["order"] = incoming.get("order", merged.get("order", 0))
            merged["content"] = incoming.get("content", merged.get("content", {}))
            merged_modules.append(merged)
            if incoming.get("id"):
                used_ids.add(str(incoming.get("id")))
        else:
            merged_modules.append(deepcopy(module))

    existing_ids = {str(module.get("id")) for module in merged_modules if module.get("id")}
    for module in optimized.get("modules", []):
        module_id = str(module.get("id") or "")
        if module_id and module_id not in existing_ids and module_id not in used_ids:
            merged_modules.append(deepcopy(module))

    result["basics"] = deepcopy(result.get("basics", {}))
    result["modules"] = _ensure_unique_module_ids(merged_modules)
    return ensure_resume_shape(result)
