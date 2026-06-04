from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import streamlit as st

from renderers import DEFAULT_STYLE_PARAMS, build_style_params, get_template_label, get_template_options
from tools.file_tools import parse_uploaded_file
from tools.ocr_tool import extract_jd_text_from_image
from tools.web_tool import fetch_jd_from_url
from ui.i18n import t


STYLE_WIDGET_KEYS = {
    "template": "style_template_selector",
    "font_size": "style_font_size_slider",
    "page_margin": "style_margin_slider",
    "line_height": "style_line_height_slider",
    "show_photo": "style_show_photo_toggle",
}


def ensure_style_state() -> None:
    if "style_params" not in st.session_state:
        st.session_state.style_params = dict(DEFAULT_STYLE_PARAMS)
    if "preview_scale" not in st.session_state:
        st.session_state.preview_scale = int(DEFAULT_STYLE_PARAMS.get("preview_scale", 100))


def ensure_upload_state() -> None:
    if "uploaded_files_meta" not in st.session_state:
        st.session_state.uploaded_files_meta = []
    if "jd_source" not in st.session_state:
        st.session_state.jd_source = "manual"
    legacy_jd_sources = {"手动输入": "manual", "图片OCR": "image_ocr", "网页链接": "web_url"}
    if st.session_state.jd_source in legacy_jd_sources:
        st.session_state.jd_source = legacy_jd_sources[st.session_state.jd_source]
    if st.session_state.jd_source not in {"manual", "image_ocr", "web_url"}:
        st.session_state.jd_source = "manual"
    if "jd_url_input" not in st.session_state:
        st.session_state.jd_url_input = ""
    if "jd_ocr_text" not in st.session_state:
        st.session_state.jd_ocr_text = ""
    if "uploaded_readme_text" not in st.session_state:
        st.session_state.uploaded_readme_text = ""
    if "existing_resume_name" not in st.session_state:
        st.session_state.existing_resume_name = ""


def get_current_style_params() -> Dict[str, Any]:
    ensure_style_state()
    style_params = dict(st.session_state.style_params)
    style_params["preview_scale"] = int(st.session_state.get("preview_scale", 100))
    return build_style_params(style_params)


def _sync_style_widgets_from_state(force: bool = False) -> None:
    style_params = st.session_state.style_params

    widget_defaults = {
        STYLE_WIDGET_KEYS["template"]: style_params.get(
            "template",
            DEFAULT_STYLE_PARAMS["template"],
        ),
        STYLE_WIDGET_KEYS["font_size"]: int(
            style_params.get("body_font_size", DEFAULT_STYLE_PARAMS["body_font_size"])
        ),
        STYLE_WIDGET_KEYS["page_margin"]: int(
            style_params.get("page_margin", DEFAULT_STYLE_PARAMS["page_margin"])
        ),
        STYLE_WIDGET_KEYS["line_height"]: float(
            style_params.get("line_height", DEFAULT_STYLE_PARAMS["line_height"])
        ),
        STYLE_WIDGET_KEYS["show_photo"]: bool(
            style_params.get("show_photo", DEFAULT_STYLE_PARAMS.get("show_photo", True))
        ),
    }

    for key, value in widget_defaults.items():
        if force or key not in st.session_state:
            st.session_state[key] = value


def render_style_controls() -> Dict[str, Any]:
    ensure_style_state()

    if st.session_state.get("pending_style_reset", False):
        st.session_state.style_params = dict(DEFAULT_STYLE_PARAMS)
        st.session_state["pending_style_reset"] = False
        _sync_style_widgets_from_state(force=True)
    else:
        _sync_style_widgets_from_state(force=False)

    with st.expander(t("style.section"), expanded=False):
        template_options = get_template_options()
        current_template = st.session_state.get(STYLE_WIDGET_KEYS["template"], DEFAULT_STYLE_PARAMS["template"])
        if current_template not in template_options:
            st.session_state[STYLE_WIDGET_KEYS["template"]] = template_options[0]

        selected_template = st.selectbox(
            t("style.template"),
            options=template_options,
            format_func=get_template_label,
            key=STYLE_WIDGET_KEYS["template"],
        )

        font_size = st.slider(
            t("style.font_size"),
            min_value=12,
            max_value=18,
            step=1,
            key=STYLE_WIDGET_KEYS["font_size"],
        )
        page_margin = st.slider(
            t("style.page_margin"),
            min_value=18,
            max_value=48,
            step=2,
            key=STYLE_WIDGET_KEYS["page_margin"],
        )
        line_height = st.slider(
            t("style.line_height"),
            min_value=1.2,
            max_value=2.0,
            step=0.05,
            key=STYLE_WIDGET_KEYS["line_height"],
        )

        show_photo = st.toggle(
            t("style.show_photo"),
            key=STYLE_WIDGET_KEYS["show_photo"],
        )

        st.session_state.style_params.update(
            {
                "template": selected_template,
                "font_size": font_size,
                "body_font_size": font_size,
                "page_margin": page_margin,
                "line_height": line_height,
                "show_photo": show_photo,
                "headline_font_size": max(font_size + 2, 16),
                "section_title_font_size": max(font_size + 1, 15),
                "name_font_size": max(font_size + 14, 26),
            }
        )

        if st.button(t("style.reset"), key="reset_style_params_btn", use_container_width=True):
            preserved_scale = int(st.session_state.get("preview_scale", DEFAULT_STYLE_PARAMS.get("preview_scale", 100)))
            st.session_state.preview_scale = preserved_scale
            st.session_state["pending_style_reset"] = True
            st.rerun()

    return get_current_style_params()


def _save_uploaded_file(upload_dir: Path, uploaded_file, target_prefix: str) -> str:
    ext = Path(uploaded_file.name).suffix
    target_path = upload_dir / f"{target_prefix}{ext}"
    target_path.write_bytes(uploaded_file.getbuffer())
    return str(target_path)


def _apply_jd_ocr_result(image_bytes: bytes, existing_text: str = "") -> Tuple[str, str, bool]:
    result = extract_jd_text_from_image(image_bytes)
    if result.ok:
        return result.text, result.message, True
    return existing_text, result.message, False


def _apply_jd_url_fetch(url: str, existing_text: str = "") -> Tuple[str, str, bool]:
    result = fetch_jd_from_url(url)
    if result.ok:
        return result.text, result.message, True
    return existing_text, result.message, False


def _parse_saved_upload(file_path: str, original_name: str, file_role: str) -> Dict[str, Any]:
    try:
        parsed = parse_uploaded_file(file_path, declared_type=file_role)
    except Exception as exc:
        parsed = {
            "name": original_name,
            "file_name": original_name,
            "path": file_path,
            "type": file_role,
            "file_type": "unknown",
            "classification": file_role,
            "suffix": Path(original_name).suffix.lower(),
            "size_bytes": 0,
            "raw_text": "",
            "parse_status": "error",
            "notes": [f"Upload parsing failed: {exc}"],
            "metadata": {},
        }
    parsed["name"] = original_name
    parsed["original_name"] = original_name
    parsed["type"] = file_role
    return parsed


def render_jd_and_file_controls(upload_dir: Path) -> Tuple[str, List[Dict[str, Any]]]:
    ensure_upload_state()

    collected_files: List[Dict[str, Any]] = []

    with st.expander(t("jd.section"), expanded=False):
        jd_source = st.radio(
            t("jd.source"),
            options=["manual", "image_ocr", "web_url"],
            format_func=lambda option: t(f"jd.{option}"),
            key="jd_source",
            horizontal=True,
        )

        if jd_source == "manual":
            st.text_area(
                t("jd.paste_text"),
                height=180,
                key="jd_input",
                placeholder=t("jd.input_placeholder"),
            )
        elif jd_source == "image_ocr":
            uploaded_jd_image = st.file_uploader(
                t("jd.upload_image"),
                type=["png", "jpg", "jpeg"],
                key="jd_image_uploader",
            )
            if uploaded_jd_image is not None:
                file_path = _save_uploaded_file(upload_dir, uploaded_jd_image, "jd_image")
                image_bytes = uploaded_jd_image.getvalue()
                if st.button(t("jd.run_ocr"), key="jd_run_ocr_btn", use_container_width=True):
                    text, message, ok = _apply_jd_ocr_result(
                        image_bytes,
                        st.session_state.get("jd_ocr_text", ""),
                    )
                    st.session_state.jd_ocr_text = text
                    if ok:
                        st.session_state.jd_input = text
                        st.success(message)
                    else:
                        st.warning(message or t("jd.ocr_pending"))
                collected_files.append(
                    {
                        "name": uploaded_jd_image.name,
                        "type": "jd_image",
                        "path": file_path,
                    }
                )
            st.text_area(
                t("jd.ocr_result"),
                height=180,
                key="jd_ocr_text",
                placeholder=t("jd.ocr_placeholder"),
            )
            st.session_state.jd_input = st.session_state.jd_ocr_text
        else:
            st.text_input(
                t("jd.url"),
                key="jd_url_input",
                placeholder=t("jd.url_placeholder"),
            )
            if st.button(t("jd.fetch_url"), key="jd_fetch_url_btn", use_container_width=True):
                text, message, ok = _apply_jd_url_fetch(
                    st.session_state.get("jd_url_input", ""),
                    st.session_state.get("jd_input", ""),
                )
                st.session_state.jd_input = text
                if ok:
                    st.success(message)
                else:
                    st.warning(message or t("jd.url_tip"))
            st.text_area(
                t("jd.paste_after_fetch"),
                height=180,
                key="jd_input",
                placeholder=t("jd.ocr_placeholder"),
            )

    with st.expander(t("file.section"), expanded=False):
        uploaded_readme = st.file_uploader(
            t("file.readme"),
            type=["md", "txt"],
            key="readme_uploader",
        )
        if uploaded_readme is not None:
            file_path = _save_uploaded_file(upload_dir, uploaded_readme, "project_readme")
            parsed_readme = _parse_saved_upload(file_path, uploaded_readme.name, "readme")
            st.session_state.uploaded_readme_text = parsed_readme.get("raw_text", "")
            collected_files.append(parsed_readme)
            st.success(t("file.readme_uploaded"))

        existing_resume = st.file_uploader(
            t("file.existing_resume"),
            type=["pdf", "md", "txt"],
            key="existing_resume_uploader",
        )
        if existing_resume is not None:
            file_path = _save_uploaded_file(upload_dir, existing_resume, "existing_resume")
            st.session_state.existing_resume_name = existing_resume.name
            collected_files.append(_parse_saved_upload(file_path, existing_resume.name, "existing_resume"))
            st.success(t("file.existing_resume_saved"))

        if collected_files:
            st.session_state.uploaded_files_meta = collected_files

        cached_files = st.session_state.get("uploaded_files_meta", [])
        if cached_files:
            st.caption(t("file.cached"))
            for file_meta in cached_files:
                st.write(f"- {file_meta.get('type', 'file')}: {file_meta.get('name', '')}")

    return st.session_state.get("jd_input", ""), st.session_state.get("uploaded_files_meta", [])
