from typing import Any, Dict, List

from config import APP_CONFIG
from core.data import ensure_resume_shape, has_module_content, normalize_experience_items, normalize_list_of_strings


def format_contact_line(basics: Dict[str, Any]) -> str:
    parts = [
        str(basics.get("city", "") or "").strip(),
        str(basics.get("phone", "") or "").strip(),
        str(basics.get("email", "") or "").strip(),
        str(basics.get("website", "") or "").strip(),
        str(basics.get("portfolio", "") or "").strip(),
    ]
    return " | ".join([part for part in parts if part])


def _render_education_markdown(items: List[Dict[str, Any]], empty_text: str) -> List[str]:
    lines: List[str] = []
    education_items = normalize_experience_items(items, "education")
    if education_items:
        for edu in education_items:
            title_parts = [edu.get("school", "").strip(), edu.get("degree", "").strip(), edu.get("major", "").strip()]
            title = " - ".join([p for p in title_parts if p])
            period = " ~ ".join([p for p in [edu.get("startDate", "").strip(), edu.get("endDate", "").strip()] if p])
            lines.append(f"- **{title or '未填写教育经历'}**")
            if period:
                lines.append(f"  - 时间：{period}")
            if edu.get("details", "").strip():
                lines.append(f"  - 说明：{edu['details'].strip()}")
    else:
        lines.append(f"- {empty_text}")
    return lines


def _render_skills_markdown(items: List[str], empty_text: str) -> List[str]:
    lines: List[str] = []
    skills = normalize_list_of_strings(items)
    if skills:
        for skill in skills:
            lines.append(f"- {skill}")
    else:
        lines.append(f"- {empty_text}")
    return lines


def _render_experience_markdown(
    items: List[Dict[str, Any]],
    item_type: str,
    primary_key: str,
    fallback_title: str,
    empty_text: str,
) -> List[str]:
    lines: List[str] = []
    experience_items = normalize_experience_items(items, item_type)
    if experience_items:
        for item in experience_items:
            title_parts = [item.get(primary_key, "").strip(), item.get("role", "").strip()]
            title = " | ".join([p for p in title_parts if p]) or fallback_title
            period = " ~ ".join([p for p in [item.get("startDate", "").strip(), item.get("endDate", "").strip()] if p])
            lines.append(f"- **{title}**")
            if period:
                lines.append(f"  - 时间：{period}")
            if item.get("description", "").strip():
                lines.append(f"  - 描述：{item['description'].strip()}")
            for hl in normalize_list_of_strings(item.get("highlights", [])):
                lines.append(f"  - {hl}")
    else:
        lines.append(f"- {empty_text}")
    return lines


def _render_self_evaluation_markdown(items: List[str], empty_text: str) -> List[str]:
    lines: List[str] = []
    self_evaluation = normalize_list_of_strings(items)
    if self_evaluation:
        for item in self_evaluation:
            lines.append(f"- {item}")
    else:
        lines.append(f"- {empty_text}")
    return lines


def _render_custom_markdown(content: Dict[str, Any], empty_text: str) -> List[str]:
    fields = content.get("fields", []) if isinstance(content.get("fields"), list) else []
    description = str(content.get("description", "") or "").strip()
    highlights = normalize_list_of_strings(content.get("highlights", []))

    lines: List[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        value = str(field.get("value", "") or "").strip()
        if value:
            lines.append(f"- {value}")

    if description:
        lines.append(f"- Description: {description}")
    for highlight in highlights:
        lines.append(f"- {highlight}")

    if not lines:
        lines.append(f"- {empty_text}")
    return lines


def render_markdown(resume_data: Dict[str, Any]) -> str:
    data = ensure_resume_shape(resume_data)
    basics = data["basics"]
    resume_config = APP_CONFIG["resume"]
    empty_text = str(resume_config.get("empty_text", "暂无"))

    lines: List[str] = []
    name = basics.get("name", "").strip() or resume_config.get("default_name", "未命名候选人")
    headline = basics.get("headline", "").strip()

    lines.append(f"# {name}")
    if headline:
        lines.append(f"**{headline}**")

    contact_line = format_contact_line(basics)
    if contact_line:
        lines.append(contact_line)

    extra_basic_fields = []
    if basics.get("age", "").strip():
        extra_basic_fields.append(f"年龄：{basics['age']}")
    if basics.get("gender", "").strip():
        extra_basic_fields.append(f"性别：{basics['gender']}")
    if extra_basic_fields:
        lines.append(" | ".join(extra_basic_fields))

    lines.append("")

    modules = sorted(
        [
            module
            for module in data.get("modules", [])
            if bool(module.get("visible", True)) and has_module_content(module)
        ],
        key=lambda item: int(item.get("order", 0)),
    )

    for module in modules:
        title = str(module.get("title", "未命名模块") or "未命名模块").strip()
        module_type = str(module.get("type", "custom"))
        content = module.get("content", {}) if isinstance(module.get("content"), dict) else {}
        items = content.get("items", [])

        lines.append(f"## {title}")

        if module_type == "education":
            lines.extend(_render_education_markdown(items, empty_text))
        elif module_type == "skills":
            lines.extend(_render_skills_markdown(items, empty_text))
        elif module_type == "projects":
            lines.extend(_render_experience_markdown(items, "projects", "name", "未填写项目", empty_text))
        elif module_type == "companyExperience":
            lines.extend(
                _render_experience_markdown(items, "companyExperience", "company", "未填写工作经历", empty_text)
            )
        elif module_type == "campusExperience":
            lines.extend(
                _render_experience_markdown(items, "campusExperience", "organization", "未填写校园经历", empty_text)
            )
        elif module_type == "selfEvaluation":
            lines.extend(_render_self_evaluation_markdown(items, empty_text))
        else:
            lines.extend(_render_custom_markdown(content, empty_text))

        lines.append("")

    if lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)
