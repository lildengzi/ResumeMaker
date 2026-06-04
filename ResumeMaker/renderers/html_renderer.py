from __future__ import annotations

from copy import deepcopy
from html import escape
from typing import Any, Dict, List

from config import APP_CONFIG
from core.assets import get_photo_data_uri
from core.data import ensure_resume_shape, has_module_content, normalize_experience_items, normalize_list_of_strings


PREVIEW_DEFAULTS = APP_CONFIG.get("preview", {})
RESUME_DEFAULTS = APP_CONFIG.get("resume", {})
RESUME_STYLE_CONFIG = APP_CONFIG.get("resume_style", {})
TEMPLATE_PRESETS: Dict[str, Dict[str, Any]] = deepcopy(RESUME_STYLE_CONFIG.get("templates", {}))
DEFAULT_STYLE_PARAMS: Dict[str, Any] = deepcopy(RESUME_STYLE_CONFIG.get("defaults", {}))


def get_template_options() -> List[str]:
    return list(TEMPLATE_PRESETS.keys())


def get_template_label(template_key: str) -> str:
    fallback_key = DEFAULT_STYLE_PARAMS.get("template", "modern_blue")
    preset = TEMPLATE_PRESETS.get(template_key, TEMPLATE_PRESETS.get(fallback_key, {}))
    return str(preset.get("template_label", template_key))


def build_style_params(style_params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    merged = deepcopy(DEFAULT_STYLE_PARAMS)
    incoming = style_params or {}
    for key, value in incoming.items():
        if value is not None:
            merged[key] = value

    fallback_key = str(DEFAULT_STYLE_PARAMS.get("template", "modern_blue"))
    template_key = str(merged.get("template", fallback_key))
    preset = deepcopy(TEMPLATE_PRESETS.get(template_key, TEMPLATE_PRESETS.get(fallback_key, {})))
    preview_config = deepcopy(PREVIEW_DEFAULTS)
    preview_config.update(preset)

    font_size = int(merged.get("font_size", DEFAULT_STYLE_PARAMS.get("font_size", 14)))
    line_height = float(merged.get("line_height", DEFAULT_STYLE_PARAMS.get("line_height", 1.65)))
    page_margin = int(merged.get("page_margin", DEFAULT_STYLE_PARAMS.get("page_margin", 32)))
    preview_scale = int(merged.get("preview_scale", DEFAULT_STYLE_PARAMS.get("preview_scale", 100)))

    preview_config["font_family"] = merged.get("font_family", preview_config.get("font_family"))
    preview_config["font_size"] = font_size
    preview_config["body_font_size"] = int(merged.get("body_font_size", font_size))
    preview_config["line_height"] = line_height
    if bool(merged.get("dense_mode", False)):
        preview_config["content_gap"] = 14
        preview_config["section_gap"] = 16
        preview_config["item_gap"] = 8
    else:
        preview_config["content_gap"] = 18
        preview_config["section_gap"] = 22
        preview_config["item_gap"] = 12
    preview_config["page_margin"] = page_margin
    preview_config["page_padding"] = f"{page_margin + 12}px {page_margin}px"
    preview_config["name_font_size"] = int(merged.get("name_font_size", max(font_size + 14, 26)))
    preview_config["headline_font_size"] = int(merged.get("headline_font_size", max(font_size + 2, 16)))
    preview_config["section_title_font_size"] = int(
        merged.get("section_title_font_size", max(font_size + 1, 15))
    )
    preview_config["meta_font_size"] = max(font_size - 1, 12)
    preview_config["small_font_size"] = max(font_size - 2, 11)
    preview_config["bullet_gap"] = 8
    preview_config["show_photo"] = bool(merged.get("show_photo", True))
    preview_config["preview_scale"] = preview_scale
    preview_config["template"] = template_key
    preview_config["template_label"] = get_template_label(template_key)
    return preview_config


def _render_plain_list(items: List[str], empty_text: str) -> str:
    valid_items = [item.strip() for item in items if item and item.strip()]
    if not valid_items:
        return f'<li class="muted">{escape(empty_text)}</li>'
    return "".join(f'<li><span>{escape(item)}</span></li>' for item in valid_items)


def _render_prose_paragraphs(items: List[str], empty_text: str) -> str:
    valid_items = [item.strip() for item in items if item and item.strip()]
    if not valid_items:
        return f'<div class="muted">{escape(empty_text)}</div>'
    return "".join(f'<div class="detail-line">{escape(item)}</div>' for item in valid_items)


def _render_skill_tags(items: List[str], empty_text: str) -> str:
    valid_items = [item.strip() for item in items if item and item.strip()]
    if not valid_items:
        return f'<div class="muted">{escape(empty_text)}</div>'
    return "".join(f'<span class="skill-tag">{escape(item)}</span>' for item in valid_items)


def _render_experience_section(items: List[Dict[str, Any]], primary_key: str, empty_text: str) -> str:
    blocks: List[str] = []
    for item in items:
        primary = escape(str(item.get(primary_key, "") or "").strip())
        role = escape(str(item.get("role", "") or "").strip())
        title = " ｜ ".join([part for part in [primary, role] if part]) or escape(empty_text)
        period = " ~ ".join(
            [
                part
                for part in [
                    str(item.get("startDate", "") or "").strip(),
                    str(item.get("endDate", "") or "").strip(),
                ]
                if part
            ]
        )
        description = escape(str(item.get("description", "") or "").strip())
        highlights = normalize_list_of_strings(item.get("highlights", []))

        block_parts = ['<article class="resume-item timeline-item">']
        block_parts.append('<div class="timeline-content">')
        block_parts.append(f'<div class="item-title">{title}</div>')
        if period:
            block_parts.append(f'<div class="item-period">{escape(period)}</div>')
        if description:
            block_parts.append(f'<div class="item-desc">{description}</div>')
        if highlights:
            block_parts.append(f'<div class="detail-lines">{_render_prose_paragraphs(highlights, empty_text)}</div>')
        block_parts.append("</div></article>")
        blocks.append("".join(block_parts))

    if not blocks:
        return f'<div class="resume-item muted">{escape(empty_text)}</div>'
    return "".join(blocks)


def _render_education(items: List[Dict[str, Any]], empty_text: str) -> str:
    blocks: List[str] = []
    for item in items:
        school = escape(str(item.get("school", "") or "").strip())
        degree = escape(str(item.get("degree", "") or "").strip())
        major = escape(str(item.get("major", "") or "").strip())
        title = " ｜ ".join([part for part in [school, degree, major] if part]) or escape(empty_text)
        period = " ~ ".join(
            [
                part
                for part in [
                    str(item.get("startDate", "") or "").strip(),
                    str(item.get("endDate", "") or "").strip(),
                ]
                if part
            ]
        )
        details = escape(str(item.get("details", "") or "").strip())

        block_parts = ['<article class="resume-item education-item">']
        block_parts.append(f'<div class="item-title">{title}</div>')
        if period:
            block_parts.append(f'<div class="item-period">{escape(period)}</div>')
        if details:
            block_parts.append(f'<div class="item-desc">{details}</div>')
        block_parts.append("</article>")
        blocks.append("".join(block_parts))

    if not blocks:
        return f'<div class="resume-item muted">{escape(empty_text)}</div>'
    return "".join(blocks)


def _render_custom_section(content: Dict[str, Any], empty_text: str) -> str:
    fields = content.get("fields", []) if isinstance(content.get("fields"), list) else []
    description = escape(str(content.get("description", "") or "").strip())
    highlights = normalize_list_of_strings(content.get("highlights", []))

    field_parts: List[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        value = escape(str(field.get("value", "") or "").strip())
        if not value:
            continue
        field_parts.append(f'<span class="custom-field">{value}</span>')

    block_parts = ['<article class="resume-item custom-item">']
    if field_parts:
        block_parts.append(f'<div class="custom-field-grid">{"".join(field_parts)}</div>')
    if description:
        block_parts.append(f'<div class="item-desc">{description}</div>')
    if highlights:
        block_parts.append(f'<div class="detail-lines">{_render_prose_paragraphs(highlights, empty_text)}</div>')
    block_parts.append("</article>")

    if not field_parts and not description and not highlights:
        return f'<div class="resume-item muted">{escape(empty_text)}</div>'
    return "".join(block_parts)


def _render_module_section(module: Dict[str, Any], empty_text: str) -> str:
    module_type = str(module.get("type", "custom"))
    title = escape(str(module.get("title", "未命名模块") or "未命名模块"))
    content = module.get("content", {}) if isinstance(module.get("content"), dict) else {}
    items = content.get("items", [])

    if module_type == "education":
        body = _render_education(normalize_experience_items(items, "education"), "暂无教育经历")
    elif module_type == "skills":
        body = f'<div class="skills-grid">{_render_skill_tags(normalize_list_of_strings(items), empty_text)}</div>'
    elif module_type == "projects":
        body = _render_experience_section(normalize_experience_items(items, "projects"), "name", "暂无项目经历")
    elif module_type == "companyExperience":
        body = _render_experience_section(
            normalize_experience_items(items, "companyExperience"), "company", "暂无工作经历"
        )
    elif module_type == "campusExperience":
        body = _render_experience_section(
            normalize_experience_items(items, "campusExperience"), "organization", "暂无校园经历"
        )
    elif module_type == "selfEvaluation":
        body = f'<div class="prose-block">{_render_prose_paragraphs(normalize_list_of_strings(items), empty_text)}</div>'
    else:
        body = _render_custom_section(content, empty_text)

    return f"""
    <section class="resume-section">
      <div class="section-title-row">
        <h3>{title}</h3>
      </div>
      {body}
    </section>
    """


def render_resume_preview_html(resume_data: Dict[str, Any], style_params: Dict[str, Any] | None = None) -> str:
    data = ensure_resume_shape(resume_data)
    basics = data.get("basics", {})
    modules = sorted(
        [
            module
            for module in data.get("modules", [])
            if bool(module.get("visible", True)) and has_module_content(module)
        ],
        key=lambda module: int(module.get("order", 0)),
    )
    style_config = build_style_params(style_params)
    empty_text = str(RESUME_DEFAULTS.get("empty_text", "暂无"))

    contact_parts = [
        str(basics.get("city", "") or "").strip(),
        str(basics.get("phone", "") or "").strip(),
        str(basics.get("email", "") or "").strip(),
        str(basics.get("website", "") or "").strip(),
        str(basics.get("portfolio", "") or "").strip(),
    ]
    contact_line = " · ".join([escape(part) for part in contact_parts if part])

    extra_parts = []
    if str(basics.get("age", "") or "").strip():
        extra_parts.append(f"年龄：{escape(str(basics.get('age', '')).strip())}")
    if str(basics.get("gender", "") or "").strip():
        extra_parts.append(f"性别：{escape(str(basics.get('gender', '')).strip())}")
    extra_line = " · ".join(extra_parts)

    photo_html = ""
    photo_path = str(basics.get("photo_path", "") or "").strip()
    photo_data_uri = get_photo_data_uri(photo_path)
    if photo_data_uri and style_config.get("show_photo"):
        photo_html = (
            '<div class="resume-avatar-wrap">'
            f'<img class="resume-avatar" src="{photo_data_uri}" alt="profile photo" />'
            "</div>"
        )

    sections_html = "".join(_render_module_section(module, empty_text) for module in modules)

    return f"""
    <div class="resume-stage">
      <div class="resume-scale-shell">
        <div class="resume-scale-frame">
          <div class="resume-a4 template-{escape(style_config.get("template", "modern_blue"))}">
            <header class="resume-header">
              <div class="resume-header-main">
                <div class="resume-name">{escape(str(basics.get("name", "") or "").strip() or RESUME_DEFAULTS.get("default_name", "未命名候选人"))}</div>
                <div class="resume-headline">{escape(str(basics.get("headline", "") or "").strip() or RESUME_DEFAULTS.get("default_headline", "未填写应聘岗位"))}</div>
                {"<div class='resume-contact'>" + contact_line + "</div>" if contact_line else ""}
                {"<div class='resume-contact secondary'>" + extra_line + "</div>" if extra_line else ""}
              </div>
              {photo_html}
            </header>

            {sections_html}
          </div>
        </div>
      </div>
    </div>
    """


def build_full_preview_document(resume_data: Dict[str, Any], style_params: Dict[str, Any] | None = None) -> str:
    style_config = build_style_params(style_params)
    preview_html = render_resume_preview_html(resume_data, style_params=style_params)
    preview_scale = int(style_config.get("preview_scale", 100))
    a4_width = int(style_config.get("a4_width_px", 794))
    a4_height = int(style_config.get("a4_min_height_px", 1123))
    scaled_width = round(a4_width * preview_scale / 100)
    scaled_height = round(a4_height * preview_scale / 100)

    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            padding: 0;
            background: transparent;
            font-family: {style_config.get("font_family")};
            color: {style_config.get("text_primary", "#111827")};
        }}

        .resume-stage {{
            width: 100%;
            padding: 24px 0 44px;
            background:
                radial-gradient(circle at top left, {style_config.get("accent_soft", "#eff6ff")} 0%, transparent 32%),
                {style_config.get("stage_background", "#eef2f7")};
            border-radius: 20px;
            overflow: auto;
        }}

        .resume-scale-shell {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            padding: 0 24px;
        }}

        .resume-scale-frame {{
            width: {scaled_width}px;
            min-height: {scaled_height}px;
            display: flex;
            justify-content: center;
            align-items: flex-start;
        }}

        .resume-a4 {{
            width: {a4_width}px;
            min-height: {a4_height}px;
            margin: 0 auto;
            background: {style_config.get("page_background", "#ffffff")};
            color: {style_config.get("text_primary", "#111827")};
            box-shadow: {style_config.get("page_shadow", "0 10px 30px rgba(15, 23, 42, 0.14)")};
            border: 1px solid {style_config.get("page_border", "#dbe2ea")};
            border-radius: 22px;
            padding: {style_config.get("page_padding", "56px 52px")};
            line-height: {style_config.get("line_height", 1.65)};
            position: relative;
            transform: scale({preview_scale / 100});
            transform-origin: top center;
        }}

        .resume-a4::before {{
            content: "";
            position: absolute;
            inset: 0;
            border-radius: 22px;
            pointer-events: none;
            background: linear-gradient(
                180deg,
                rgba(255,255,255,0.00) 0%,
                rgba(255,255,255,0.00) 76%,
                rgba(148, 163, 184, 0.05) 100%
            );
        }}

        .resume-header {{
            display: flex;
            justify-content: space-between;
            gap: 20px;
            align-items: flex-start;
            border-bottom: 1px solid {style_config.get("section_border", "#dbe7f5")};
            padding-bottom: 18px;
            margin-bottom: {style_config.get("content_gap", 18)}px;
        }}

        .resume-header-main {{
            flex: 1;
            min-width: 0;
        }}

        .resume-name {{
            font-size: {style_config.get("name_font_size", 30)}px;
            font-weight: 800;
            letter-spacing: 0.4px;
            line-height: 1.15;
            margin-bottom: 8px;
            color: {style_config.get("text_primary", "#111827")};
        }}

        .resume-headline {{
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: 999px;
            background: {style_config.get("accent_soft", "#eff6ff")};
            color: {style_config.get("accent_color", "#2563eb")};
            font-size: {style_config.get("headline_font_size", 16)}px;
            font-weight: 700;
            margin-bottom: 12px;
        }}

        .resume-contact {{
            font-size: {style_config.get("meta_font_size", 13)}px;
            color: {style_config.get("text_secondary", "#374151")};
            margin-top: 4px;
            word-break: break-word;
        }}

        .resume-contact.secondary {{
            color: {style_config.get("text_muted", "#64748b")};
        }}

        .resume-avatar-wrap {{
            width: 108px;
            min-width: 108px;
            height: 132px;
            padding: 6px;
            border-radius: 18px;
            background: linear-gradient(180deg, {style_config.get("accent_soft", "#eff6ff")}, #ffffff);
            border: 1px solid {style_config.get("page_border", "#dbe2ea")};
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
        }}

        .resume-avatar {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 12px;
            display: block;
        }}

        .resume-section {{
            margin-bottom: {style_config.get("section_gap", 22)}px;
        }}

        .section-title-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }}

        .resume-section h3 {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            margin: 0;
            font-size: {style_config.get("section_title_font_size", 16)}px;
            font-weight: 800;
            letter-spacing: 0.2px;
            color: {style_config.get("text_primary", "#111827")};
        }}

        .resume-section h3::before {{
            content: "";
            width: 6px;
            height: 18px;
            border-radius: 999px;
            background: linear-gradient(180deg, {style_config.get("accent_color", "#2563eb")}, {style_config.get("timeline_color", "#93c5fd")});
            display: inline-block;
        }}

        .resume-item {{
            margin-bottom: {style_config.get("item_gap", 12)}px;
        }}

        .education-item,
        .timeline-content,
        .custom-item {{
            background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(248,250,252,0.92));
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 14px;
            padding: 12px 14px;
        }}

        .custom-field-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px 12px;
            margin-bottom: 8px;
        }}

        .custom-field {{
            display: inline-flex;
            align-items: center;
            min-height: 28px;
            padding: 4px 10px;
            border: 1px solid {style_config.get("section_border", "#dbe7f5")};
            border-radius: 6px;
            color: {style_config.get("text_secondary", "#374151")};
            background: {style_config.get("accent_soft", "#eff6ff")};
            font-size: {style_config.get("small_font_size", 11)}px;
        }}

        .timeline-item {{
            position: relative;
            display: block;
            margin-bottom: {style_config.get("item_gap", 12)}px;
        }}

        .timeline-dot {{
            display: none;
        }}

        .timeline-content {{
            flex: 1;
        }}

        .item-title {{
            font-size: {max(int(style_config.get("body_font_size", 13)) + 1, 14)}px;
            font-weight: 700;
            color: {style_config.get("text_primary", "#111827")};
            line-height: {style_config.get("line_height", 1.65)};
        }}

        .item-period {{
            font-size: {style_config.get("small_font_size", 11)}px;
            color: {style_config.get("text_muted", "#64748b")};
            margin-top: 3px;
        }}

        .item-desc {{
            font-size: {style_config.get("body_font_size", 13)}px;
            color: {style_config.get("text_secondary", "#374151")};
            margin-top: 6px;
            line-height: {style_config.get("line_height", 1.65)};
            font-family: {style_config.get("font_family", '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif')};
            white-space: normal;
        }}

        .item-list {{
            margin: 8px 0 0 0;
            padding-left: 20px;
        }}

        .item-list li {{
            margin-bottom: {style_config.get("bullet_gap", 8)}px;
            color: {style_config.get("text_secondary", "#374151")};
            font-size: {style_config.get("body_font_size", 13)}px;
        }}

        .item-list li span {{
            display: inline-block;
        }}

        .prose-list {{
            margin-top: 2px;
        }}

        .prose-block {{
            margin-top: 2px;
        }}

        .prose-block .detail-line {{
            margin: 0 0 6px 0;
            padding: 0;
            color: {style_config.get("text_secondary", "#374151")};
            font-size: {style_config.get("body_font_size", 13)}px;
            line-height: {style_config.get("line_height", 1.65)};
            font-family: {style_config.get("font_family", '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif')};
            white-space: normal;
        }}

        .prose-block .detail-line::marker {{
            content: "";
        }}

        .detail-lines {{
            margin-top: 6px;
        }}

        .detail-line {{
            margin: 0 0 6px 0;
            padding: 0;
            color: {style_config.get("text_secondary", "#374151")};
            font-size: {style_config.get("body_font_size", 13)}px;
            line-height: {style_config.get("line_height", 1.65)};
            font-family: {style_config.get("font_family", '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif')};
            white-space: normal;
        }}

        .skills-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}

        .skill-tag {{
            display: inline-flex;
            align-items: center;
            min-height: 34px;
            padding: 6px 12px;
            border-radius: 999px;
            background: {style_config.get("tag_background", "#eff6ff")};
            color: {style_config.get("tag_text", "#1d4ed8")};
            border: 1px solid {style_config.get("section_border", "#bfdbfe")};
            font-size: {style_config.get("body_font_size", 13)}px;
            font-weight: 600;
        }}

        .muted {{
            color: {style_config.get("text_muted", "#64748b")};
            font-size: {style_config.get("body_font_size", 13)}px;
        }}

        @media (max-width: 900px) {{
            .resume-stage {{
                padding: 0;
                background: transparent;
                border-radius: 0;
            }}

            .resume-scale-shell,
            .resume-scale-frame {{
                width: 100%;
                min-height: auto;
                padding: 0;
            }}

            .resume-a4 {{
                width: 100%;
                min-height: auto;
                padding: 24px 18px;
                border-radius: 0;
                box-shadow: none;
                border-left: none;
                border-right: none;
                transform: none;
            }}

            .resume-header {{
                flex-direction: column;
            }}

            .resume-avatar-wrap {{
                width: 96px;
                height: 118px;
            }}
        }}
      </style>
    </head>
    <body>
      {preview_html}
    </body>
    </html>
    """
