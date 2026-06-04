from copy import deepcopy
import json
from uuid import uuid4
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from config import APP_CONFIG, get_path_from_storage, update_resume_style_config
from core import (
    create_generic_module,
    get_photo_data_uri,
    import_existing_resume,
    load_resume_data,
    normalize_list_of_strings,
    run_resume_workflow,
    save_resume_data,
)
from core.document_commands import (
    add_module,
    delete_module,
    move_module,
    replace_resume_from_agent,
    save_document_snapshot,
    update_basics,
    update_module,
)
from core.resume_document import (
    create_resume_document,
    get_document_exports,
    get_document_runtime,
    get_resume_document,
    notify_document_changed,
    sync_session_aliases,
)
from renderers import render_resume_document_pdf, render_resume_markdown
from ui.i18n import ensure_language_state, render_language_selector, t
from ui.preview import render_resume_preview
from ui.sidebar import ensure_style_state, get_current_style_params, render_jd_and_file_controls, render_style_controls


UPLOAD_DIR = get_path_from_storage("upload_dir")
UPLOAD_DIR.mkdir(exist_ok=True)

PREVIEW_CONFIG = APP_CONFIG["preview"]
RESUME_CONFIG = APP_CONFIG["resume"]


def init_state() -> None:
    ensure_language_state()
    if "resume_data" not in st.session_state:
        st.session_state.resume_data = load_resume_data()
        _renumber_modules()
    if "jd_input" not in st.session_state:
        st.session_state.jd_input = ""
    ensure_style_state()
    if "resume_document" not in st.session_state:
        st.session_state.resume_document = create_resume_document(
            st.session_state.resume_data,
            st.session_state.get("style_params", {}),
            st.session_state.get("jd_input", ""),
            st.session_state.get("uploaded_files_meta", []),
        )
    sync_session_aliases(st.session_state, include_widget_keys=True)
    if "resume_history" not in st.session_state:
        st.session_state.resume_history = [deepcopy(st.session_state.resume_data)]
    if "last_resume_snapshot" not in st.session_state:
        st.session_state.last_resume_snapshot = deepcopy(st.session_state.resume_data)
    if "photo_uploader_key" not in st.session_state:
        st.session_state.photo_uploader_key = 0
    if "preview_resume_data" not in st.session_state:
        st.session_state.preview_resume_data = deepcopy(st.session_state.resume_data)
    if "preview_version" not in st.session_state:
        st.session_state.preview_version = 0
    if "preview_signature" not in st.session_state:
        st.session_state.preview_signature = ""
    if "pdf_bytes" not in st.session_state:
        st.session_state.pdf_bytes = None
    if "pdf_ready_for_version" not in st.session_state:
        st.session_state.pdf_ready_for_version = -1
    if "workflow_logs" not in st.session_state:
        st.session_state.workflow_logs = []
    if "markdown_export" not in st.session_state:
        st.session_state.markdown_export = ""
    if "ai_success_message" not in st.session_state:
        st.session_state.ai_success_message = ""
    if "ai_is_running" not in st.session_state:
        st.session_state.ai_is_running = False
    if "last_optimization_signature" not in st.session_state:
        st.session_state.last_optimization_signature = ""
    if "last_optimization_notice" not in st.session_state:
        st.session_state.last_optimization_notice = ""
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0
    sync_session_aliases(st.session_state, include_widget_keys=True)


def persist_resume() -> None:
    document = get_resume_document(st.session_state)
    snapshot = save_document_snapshot(document)
    save_resume_data(snapshot)
    sync_session_aliases(st.session_state)


def persist_style_config() -> None:
    style_to_save = dict(st.session_state.get("style_params", {}))
    style_to_save.pop("preview_scale", None)
    update_resume_style_config(style_to_save)


def parse_multiline_text(value: str) -> List[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def editor_key(name: str) -> str:
    return f"v{int(st.session_state.get('editor_version', 0))}_{name}"


def bump_editor_version() -> None:
    st.session_state["editor_version"] = int(st.session_state.get("editor_version", 0)) + 1


def get_ui_style_css() -> str:
    return """
        section[data-testid="stSidebar"] [data-testid="stExpander"] {
            border: 1px solid var(--border-color);
            border-radius: 8px;
        }

        section[data-testid="stSidebar"] [data-testid="stExpander"] details {
            border-radius: 8px;
        }

        section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--border-color);
        }

        section[data-testid="stSidebar"] button {
            border-radius: 6px;
        }
    """


def render_ui_style() -> None:
    st.markdown(
        f"""
        <style>
        {get_ui_style_css()}
        </style>
        """,
        unsafe_allow_html=True,
    )


def has_minimum_resume_info() -> bool:
    basics = st.session_state.resume_data.get("basics", {})
    required_fields = RESUME_CONFIG.get("minimum_required_fields", ["name", "headline"])
    return all(str(basics.get(field, "") or "").strip() for field in required_fields)


def has_uploaded_existing_resume() -> bool:
    for file_meta in st.session_state.get("uploaded_files_meta", []) or []:
        if isinstance(file_meta, dict) and str(file_meta.get("type", "") or "") == "existing_resume":
            return True
    return False


def build_optimization_signature(
    resume_data: Dict[str, Any],
    jd_text: str,
    uploaded_files: List[Dict[str, Any]],
    style_params: Dict[str, Any],
) -> str:
    signature_files = []
    for file_meta in uploaded_files or []:
        if not isinstance(file_meta, dict):
            continue
        signature_files.append(
            {
                "name": file_meta.get("name", ""),
                "type": file_meta.get("type", ""),
                "path": file_meta.get("path", ""),
                "size_bytes": file_meta.get("size_bytes", 0),
                "raw_text": file_meta.get("raw_text", ""),
                "parse_status": file_meta.get("parse_status", ""),
            }
        )

    signature_payload = {
        "resume_data": resume_data,
        "jd_text": jd_text,
        "uploaded_files": signature_files,
        "style_params": style_params,
    }
    return json.dumps(signature_payload, ensure_ascii=False, sort_keys=True, default=str)


def is_duplicate_optimization_request(
    last_signature: str,
    current_signature: str,
    ai_is_running: bool = False,
) -> bool:
    return bool(not ai_is_running and last_signature and last_signature == current_signature)


def _build_preview_signature() -> str:
    return repr(
        {
            "resume_document": get_resume_document(st.session_state),
            "style_params": get_current_style_params(),
        }
    )


def refresh_preview(force: bool = False) -> None:
    notify_document_changed(st.session_state, "force" if force else "change")


def push_resume_history() -> None:
    max_history = int(APP_CONFIG.get("workflow", {}).get("max_history", 3))
    history = st.session_state.get("resume_history", [])
    history.append(deepcopy(st.session_state.resume_data))
    st.session_state.resume_history = history[-max_history:]


def _sorted_modules() -> List[Dict[str, Any]]:
    return sorted(
        st.session_state.resume_data.get("modules", []),
        key=lambda item: int(item.get("order", 0)),
    )


def _ensure_unique_module_ids(modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    normalized: List[Dict[str, Any]] = []
    for idx, module in enumerate(modules, start=1):
        module_copy = deepcopy(module)
        raw_id = str(module_copy.get("id") or "").strip()
        if not raw_id or raw_id in seen:
            module_type = str(module_copy.get("type") or "custom")
            raw_id = f"{module_type}_{idx}_{uuid4().hex[:8]}"
        module_copy["id"] = raw_id
        seen.add(raw_id)
        normalized.append(module_copy)
    return normalized


def _renumber_modules() -> None:
    modules = _ensure_unique_module_ids(_sorted_modules())
    for idx, module in enumerate(modules, start=1):
        module["order"] = idx
    st.session_state.resume_data["modules"] = modules


def get_expander_default_state(key: str, default: bool = False) -> bool:
    return bool(st.session_state.get(f"expander_state_{key}", default))


def _replace_module_in_state(updated_module: Dict[str, Any]) -> None:
    """将正在编辑的模块写回 session_state，避免子条目操作后模块顺序和预览数据脱节。"""
    update_module(get_resume_document(st.session_state), str(updated_module.get("id")), updated_module)
    _renumber_modules()


def _delete_module(module_id: str) -> None:
    delete_module(get_resume_document(st.session_state), module_id)
    sync_session_aliases(st.session_state)
    persist_resume()
    st.rerun()


def _move_module(module_id: str, direction: int) -> None:
    modules = _sorted_modules()
    index = next((idx for idx, module in enumerate(modules) if module.get("id") == module_id), None)
    if index is None:
        return

    target_index = index + direction
    if target_index < 0 or target_index >= len(modules):
        return

    move_module(get_resume_document(st.session_state), module_id, direction)
    sync_session_aliases(st.session_state)
    persist_resume()
    st.rerun()


def _add_module() -> None:
    modules = _ensure_unique_module_ids(_sorted_modules())
    new_module_id = f"custom_{len(modules) + 1}_{uuid4().hex[:8]}"
    add_module(get_resume_document(st.session_state), new_module_id)
    sync_session_aliases(st.session_state)
    persist_resume()
    st.rerun()


def render_basics_editor() -> None:
    with st.expander(t("basics.section"), expanded=get_expander_default_state("basics", False)):
        basics = st.session_state.resume_data["basics"]

        update_basics(
            get_resume_document(st.session_state),
            "name",
            st.text_input(t("basics.name"), basics.get("name", ""), key=editor_key("basics_name")),
        )
        update_basics(
            get_resume_document(st.session_state),
            "headline",
            st.text_input(t("basics.headline"), basics.get("headline", ""), key=editor_key("basics_headline")),
        )
        col1, col2 = st.columns(2)
        with col1:
            update_basics(get_resume_document(st.session_state), "age", st.text_input(t("basics.age"), basics.get("age", ""), key=editor_key("basics_age")))
            update_basics(get_resume_document(st.session_state), "city", st.text_input(t("basics.city"), basics.get("city", ""), key=editor_key("basics_city")))
            update_basics(get_resume_document(st.session_state), "phone", st.text_input(t("basics.phone"), basics.get("phone", ""), key=editor_key("basics_phone")))
        with col2:
            update_basics(get_resume_document(st.session_state), "gender", st.text_input(t("basics.gender"), basics.get("gender", ""), key=editor_key("basics_gender")))
            update_basics(get_resume_document(st.session_state), "email", st.text_input(t("basics.email"), basics.get("email", ""), key=editor_key("basics_email")))
            update_basics(get_resume_document(st.session_state), "website", st.text_input(t("basics.website"), basics.get("website", ""), key=editor_key("basics_website")))
            update_basics(get_resume_document(st.session_state), "portfolio", st.text_input(t("basics.portfolio"), basics.get("portfolio", ""), key=editor_key("basics_portfolio")))

        uploaded_photo = st.file_uploader(
            t("basics.photo.upload"),
            type=["png", "jpg", "jpeg"],
            key=f"photo_uploader_{st.session_state.photo_uploader_key}",
        )
        if uploaded_photo is not None:
            ext = Path(uploaded_photo.name).suffix or ".png"
            target_path = UPLOAD_DIR / f"profile_photo{ext}"
            target_path.write_bytes(uploaded_photo.getbuffer())
            update_basics(get_resume_document(st.session_state), "photo_path", str(target_path))
            sync_session_aliases(st.session_state)
            persist_resume()

        current_photo = basics.get("photo_path", "").strip()
        current_photo_data_uri = get_photo_data_uri(current_photo)
        if current_photo_data_uri:
            st.image(current_photo_data_uri, caption=t("basics.photo.caption"), width=180)
            if st.button(t("basics.photo.remove"), key="remove_photo_btn", use_container_width=True):
                update_basics(get_resume_document(st.session_state), "photo_path", "")
                st.session_state.photo_uploader_key += 1
                persist_resume()
                st.rerun()


def render_simple_list_module_editor(module: Dict[str, Any]) -> None:
    items = normalize_list_of_strings(module.get("content", {}).get("items", []))
    updated = st.text_area(
        t("module.simple_list"),
        "\n".join(items),
        height=140,
        key=editor_key(f"module_textarea_{module['id']}"),
    )
    module["content"]["items"] = parse_multiline_text(updated)


def render_education_module_editor(module: Dict[str, Any]) -> None:
    items = module.get("content", {}).setdefault("items", [])

    for idx, item in enumerate(items):
        st.markdown(f"**{t('education.item_heading', index=idx + 1)}**")
        item["school"] = st.text_input(t("field.school"), item.get("school", ""), key=editor_key(f"{module['id']}_school_{idx}"))
        col1, col2 = st.columns(2)
        with col1:
            item["degree"] = st.text_input(t("field.degree"), item.get("degree", ""), key=editor_key(f"{module['id']}_degree_{idx}"))
            item["startDate"] = st.text_input(t("field.start_date"), item.get("startDate", ""), key=editor_key(f"{module['id']}_start_{idx}"))
        with col2:
            item["major"] = st.text_input(t("field.major"), item.get("major", ""), key=editor_key(f"{module['id']}_major_{idx}"))
            item["endDate"] = st.text_input(t("field.end_date"), item.get("endDate", ""), key=editor_key(f"{module['id']}_end_{idx}"))
        item["details"] = st.text_area(t("field.details"), item.get("details", ""), key=editor_key(f"{module['id']}_details_{idx}"))

        if st.button(t("education.delete"), key=f"{module['id']}_delete_item_{idx}", use_container_width=True):
            items.pop(idx)
            module["content"]["items"] = items
            _replace_module_in_state(module)
            persist_resume()
            st.rerun()

        st.divider()

    if st.button(t("education.add"), key=f"{module['id']}_add_item_btn", use_container_width=True):
        items.append(
            {
                "school": "",
                "degree": "",
                "major": "",
                "startDate": "",
                "endDate": "",
                "details": "",
            }
        )
        module["content"]["items"] = items
        _replace_module_in_state(module)
        persist_resume()
        st.rerun()


def render_experience_module_editor(module: Dict[str, Any], primary_key: str, primary_label: str) -> None:
    items = module.get("content", {}).setdefault("items", [])

    for idx, item in enumerate(items):
        title = str(module.get("title", t("experience.fallback_title")) or t("experience.fallback_title"))
        st.markdown(f"**{t('experience.heading', title=title, index=idx + 1)}**")
        item[primary_key] = st.text_input(
            primary_label,
            item.get(primary_key, ""),
            key=editor_key(f"{module['id']}_{primary_key}_{idx}"),
        )
        item["role"] = st.text_input(t("experience.role"), item.get("role", ""), key=editor_key(f"{module['id']}_role_{idx}"))
        col1, col2 = st.columns(2)
        with col1:
            item["startDate"] = st.text_input(t("field.start_date"), item.get("startDate", ""), key=editor_key(f"{module['id']}_start_{idx}"))
        with col2:
            item["endDate"] = st.text_input(t("field.end_date"), item.get("endDate", ""), key=editor_key(f"{module['id']}_end_{idx}"))

        item["description"] = st.text_area(
            t("experience.description"),
            item.get("description", ""),
            height=80,
            key=editor_key(f"{module['id']}_description_{idx}"),
        )
        highlights_text = "\n".join(item.get("highlights", []))
        item["highlights"] = parse_multiline_text(
            st.text_area(
                t("experience.highlights"),
                highlights_text,
                height=100,
                key=editor_key(f"{module['id']}_highlights_{idx}"),
            )
        )

        if st.button(t("experience.delete"), key=f"{module['id']}_delete_item_{idx}", use_container_width=True):
            items.pop(idx)
            persist_resume()
            st.rerun()

        st.divider()

    if st.button(
        t("experience.add", title=str(module.get("title", t("experience.fallback_title")) or t("experience.fallback_title"))),
        key=f"{module['id']}_add_item_btn",
        use_container_width=True,
    ):
        items.append(
            {
                primary_key: "",
                "role": "",
                "startDate": "",
                "endDate": "",
                "description": "",
                "highlights": [],
            }
        )
        persist_resume()
        st.rerun()


def _normalize_custom_fields(raw_fields: Any) -> List[Dict[str, str]]:
    fields: List[Dict[str, str]] = []
    if not isinstance(raw_fields, list):
        return fields

    for field in raw_fields:
        if isinstance(field, dict):
            fields.append(
                {
                    "label": "General subfield",
                    "value": str(field.get("value", "") or ""),
                }
            )
        elif isinstance(field, str) and field.strip():
            fields.append({"label": "General subfield", "value": field.strip()})
    return fields


def _compact_custom_fields(fields: List[Dict[str, str]]) -> List[Dict[str, str]]:
    compacted: List[Dict[str, str]] = []
    for field in fields:
        value = str(field.get("value", "") or "").strip()
        if value:
            compacted.append({"label": "General subfield", "value": value})
    return compacted


def render_custom_module_editor(module: Dict[str, Any]) -> None:
    content = module.setdefault("content", {})
    fields = _normalize_custom_fields(content.get("fields", []))

    count_key = f"{module['id']}_custom_field_count"
    if count_key not in st.session_state:
        st.session_state[count_key] = max(1, len(fields))

    while len(fields) < int(st.session_state[count_key]):
        fields.append({"label": "General subfield", "value": ""})

    st.caption(t("custom.caption"))
    for idx, field in enumerate(fields):
        col1, col2 = st.columns([3, 1])
        with col1:
            field["value"] = st.text_input(
                t("custom.general_subfield"),
                field.get("value", ""),
                key=editor_key(f"{module['id']}_custom_field_value_{idx}"),
                placeholder=t("custom.value_placeholder"),
            )
        with col2:
            st.write("")
            if st.button(t("custom.delete"), key=f"{module['id']}_delete_custom_field_{idx}", use_container_width=True):
                fields.pop(idx)
                st.session_state[count_key] = max(1, len(fields))
                content["fields"] = _compact_custom_fields(fields)
                _replace_module_in_state(module)
                persist_resume()
                st.rerun()

    if st.button(t("custom.add_field"), key=f"{module['id']}_add_custom_field_btn", use_container_width=True):
        st.session_state[count_key] = int(st.session_state[count_key]) + 1
        content["fields"] = _compact_custom_fields(fields)
        _replace_module_in_state(module)
        persist_resume()
        st.rerun()

    content["fields"] = _compact_custom_fields(fields)
    content["description"] = st.text_area(
        t("custom.description"),
        str(content.get("description", "") or ""),
        height=100,
        key=editor_key(f"{module['id']}_custom_description"),
    ).strip()
    content["highlights"] = parse_multiline_text(
        st.text_area(
            t("custom.highlights"),
            "\n".join(normalize_list_of_strings(content.get("highlights", []))),
            height=100,
            key=editor_key(f"{module['id']}_custom_highlights"),
        )
    )
    content.pop("items", None)
    _replace_module_in_state(module)


def render_module_editor(module: Dict[str, Any], index: int, total: int) -> None:
    title = str(module.get("title", t("module.fallback_title")) or t("module.fallback_title"))
    module_type = str(module.get("type", "custom"))

    with st.container(border=True):
        header_col, visible_col = st.columns([3, 1])
        with header_col:
            updated_title = st.text_input(
                t("module.title"),
                title,
                key=editor_key(f"module_title_{module['id']}"),
                label_visibility="collapsed",
                placeholder=t("module.title"),
            )
            module["title"] = updated_title.strip() or title
        with visible_col:
            module["visible"] = st.toggle(
                t("module.show"),
                value=bool(module.get("visible", True)),
                key=editor_key(f"module_visible_{module['id']}"),
            )

        details_key = f"module_details_{module['id']}"
        with st.expander(t("module.details"), expanded=get_expander_default_state(details_key, False)):
            op_col1, op_col2, op_col3 = st.columns(3)
            with op_col1:
                if st.button(t("module.up"), key=f"module_up_{module['id']}", use_container_width=True, disabled=index == 0):
                    _move_module(module["id"], -1)
            with op_col2:
                if st.button(
                    t("module.down"),
                    key=f"module_down_{module['id']}",
                    use_container_width=True,
                    disabled=index == total - 1,
                ):
                    _move_module(module["id"], 1)
            with op_col3:
                if st.button(t("module.delete"), key=f"module_delete_{module['id']}", use_container_width=True):
                    _delete_module(module["id"])
    
            st.caption(t("module.type", module_type=module_type))
    
            if module_type == "education":
                render_education_module_editor(module)
            elif module_type == "skills":
                render_simple_list_module_editor(module)
            elif module_type == "projects":
                render_experience_module_editor(module, "name", t("module.project_name"))
            elif module_type == "companyExperience":
                render_experience_module_editor(module, "company", t("module.company_name"))
            elif module_type == "campusExperience":
                render_experience_module_editor(module, "organization", t("module.organization"))
            elif module_type == "selfEvaluation":
                render_simple_list_module_editor(module)
            else:
                render_custom_module_editor(module)
    
    
def render_modules_editor() -> None:
    with st.expander(t("module.section"), expanded=get_expander_default_state("modules", False)):
        st.caption(t("module.caption"))
        if st.button(t("module.add"), key="add_module_btn", use_container_width=True):
            _add_module()

        _renumber_modules()
        modules = _sorted_modules()
        if not modules:
            st.info(t("module.empty"))
            return

        for idx, module in enumerate(modules):
            render_module_editor(module, idx, len(modules))


def run_ai_optimization() -> None:
    if st.session_state.get("ai_is_running", False):
        st.info(t("ai.duplicate_running"))
        return

    notify_document_changed(st.session_state)
    jd_text = st.session_state.jd_input.strip()
    uploaded_files = st.session_state.get("uploaded_files_meta", [])
    style_params = st.session_state.get("style_params", {})
    document = get_resume_document(st.session_state)
    document.setdefault("inputs", {})["jd_text"] = jd_text
    document["inputs"]["uploaded_files"] = deepcopy(uploaded_files)

    if not has_minimum_resume_info() and not has_uploaded_existing_resume():
        st.warning(t("ai.minimum_info_warning"))
        return

    current_signature = build_optimization_signature(
        st.session_state.resume_data,
        jd_text,
        uploaded_files,
        style_params,
    )
    if is_duplicate_optimization_request(
        st.session_state.get("last_optimization_signature", ""),
        current_signature,
        st.session_state.get("ai_is_running", False),
    ):
        st.session_state.last_optimization_notice = t("ai.duplicate_input")
        st.info(st.session_state.last_optimization_notice)
        return

    st.session_state.last_resume_snapshot = deepcopy(st.session_state.resume_data)
    st.session_state.ai_is_running = True

    progress_placeholder = st.empty()
    try:
        if jd_text:
            progress_placeholder.info(t("ai.info.analyzing_jd"))
        else:
            progress_placeholder.info(t("ai.info.generic_optimization"))

        with st.spinner(t("ai.spinner")):
            progress_placeholder.info(t("ai.info.workflow"))
            workflow_result = run_resume_workflow(
                jd_text=jd_text,
                current_resume=st.session_state.resume_data,
                uploaded_files=uploaded_files,
                style_params=style_params,
            )
            optimized = workflow_result["final_resume"]

        push_resume_history()
        st.session_state.resume_data = optimized
        workflow_logs = workflow_result.get("workflow_logs") or [
            {
                "agent": "workflow",
                "message_key": "workflow.log.completed",
                "message": "Workflow completed.",
            },
        ]
        if workflow_result.get("error"):
            workflow_logs.append(
                {
                    "agent": "workflow",
                    "message_key": "workflow.log.fallback",
                    "message": "LLM failed; local fallback was written back.",
                    "details": [
                        detail
                        for detail in [
                            str(workflow_result.get("error") or ""),
                            str(workflow_result.get("llm_error") or ""),
                        ]
                        if detail
                    ],
                }
            )
        replace_resume_from_agent(document, optimized)
        bump_editor_version()
        document.setdefault("inputs", {})["jd_text"] = jd_text
        document["inputs"]["uploaded_files"] = deepcopy(uploaded_files)
        st.session_state.uploaded_files_meta = deepcopy(uploaded_files)
        runtime = document.setdefault("runtime", {})
        runtime["workflow_logs"] = workflow_logs
        runtime["conditional_suggestions"] = workflow_result.get("conditional_suggestions", [])
        persist_resume()
        refresh_preview(force=True)
        st.session_state.last_optimization_signature = current_signature
        progress_placeholder.empty()
        st.session_state.ai_success_message = t("ai.success")
        st.rerun()
    except Exception as exc:
        progress_placeholder.empty()
        error_message = str(exc)

        if "API Key" in error_message or "未配置" in error_message:
            st.error(t("ai.error.missing_api_key"))
        elif "提取 JSON" in error_message:
            st.error(t("ai.error.invalid_json"))
        else:
            st.error(t("ai.error.prefix", error_message=error_message))
    finally:
        st.session_state.ai_is_running = False


def import_existing_resume_to_document() -> None:
    uploaded_files = st.session_state.get("uploaded_files_meta", [])
    if not has_uploaded_existing_resume():
        st.warning(t("import.no_existing_resume"))
        return

    document = get_resume_document(st.session_state)
    st.session_state.last_resume_snapshot = deepcopy(st.session_state.resume_data)

    with st.spinner(t("import.spinner")):
        import_result = import_existing_resume(
            current_resume=st.session_state.resume_data,
            uploaded_files=uploaded_files,
        )

    imported_resume = import_result["final_resume"]
    st.session_state.resume_data = imported_resume
    replace_resume_from_agent(document, imported_resume)
    bump_editor_version()
    document.setdefault("inputs", {})["uploaded_files"] = deepcopy(uploaded_files)
    st.session_state.uploaded_files_meta = deepcopy(uploaded_files)
    runtime = document.setdefault("runtime", {})
    runtime["workflow_logs"] = import_result.get("workflow_logs", [])
    runtime["conditional_suggestions"] = []
    persist_resume()
    refresh_preview(force=True)
    st.session_state.last_optimization_signature = ""
    changes = import_result.get("parsed_resume_changes", [])
    if changes:
        st.success(t("import.success", count=len(changes)))
    else:
        st.warning(t("import.no_changes"))
    st.rerun()


def undo_last_optimization() -> None:
    snapshot = st.session_state.get("last_resume_snapshot")
    if snapshot:
        st.session_state.resume_data = deepcopy(snapshot)
        get_resume_document(st.session_state)["resume"] = deepcopy(snapshot)
        get_document_runtime(st.session_state)["conditional_suggestions"] = []
        bump_editor_version()
        st.session_state.last_optimization_signature = ""
        persist_resume()
        refresh_preview(force=True)
        st.success(t("undo.success"))


def prepare_pdf(show_success: bool = True) -> None:
    document = get_resume_document(st.session_state)
    exports = get_document_exports(st.session_state)
    runtime = get_document_runtime(st.session_state)
    with st.spinner(t("export.pdf_spinner")):
        exports["pdf_bytes"] = render_resume_document_pdf(document)
        exports["pdf_ready_for_version"] = runtime.get("preview_version", 0)
        sync_session_aliases(st.session_state)
    if show_success:
        st.success(t("export.pdf_ready"))


def ensure_pdf_ready() -> bytes:
    exports = get_document_exports(st.session_state)
    runtime = get_document_runtime(st.session_state)
    pdf_bytes = exports.get("pdf_bytes")
    ready_version = exports.get("pdf_ready_for_version", -1)
    current_version = runtime.get("preview_version", 0)

    if (not pdf_bytes) or ready_version != current_version:
        prepare_pdf(show_success=False)

    return get_document_exports(st.session_state)["pdf_bytes"]


def render_sidebar() -> None:
    with st.sidebar:
        st.title(t("sidebar.title"))
        st.caption(t("sidebar.caption"))
        render_language_selector()
        if st.session_state.get("ai_success_message"):
            st.success(st.session_state.ai_success_message)
            st.session_state.ai_success_message = ""
        if st.session_state.get("last_optimization_notice"):
            st.info(st.session_state.last_optimization_notice)
            st.session_state.last_optimization_notice = ""

        render_style_controls()
        render_basics_editor()
        render_modules_editor()
        render_jd_and_file_controls(UPLOAD_DIR)
        notify_document_changed(st.session_state)

        if st.button(
            t("import.existing_resume"),
            use_container_width=True,
            disabled=not has_uploaded_existing_resume(),
        ):
            import_existing_resume_to_document()

        st.caption(t("sidebar.min_info_tip"))

        is_ai_running = bool(st.session_state.get("ai_is_running", False))
        if st.button(
            t("sidebar.generate"),
            type="primary",
            use_container_width=True,
            disabled=is_ai_running,
        ):
            run_ai_optimization()

        if st.button(t("sidebar.undo"), use_container_width=True):
            undo_last_optimization()

        st.divider()
        if st.button(t("sidebar.save"), use_container_width=True):
            persist_resume()
            persist_style_config()
            st.success(t("save.success"))

        st.divider()
        st.subheader(t("export.section"))
        st.caption(t("export.caption"))

        st.download_button(
            t("export.download_markdown"),
            data=get_document_exports(st.session_state).get("markdown", "")
            or render_resume_markdown(get_resume_document(st.session_state)["resume"]),
            file_name="resume.md",
            mime="text/markdown",
            use_container_width=True,
        )

    notify_document_changed(st.session_state)


def render_main_panel() -> None:
    current_scale = int(st.session_state.get("preview_scale", 100))
    action_col1, action_col2 = st.columns([2, 2])
    with action_col1:
        if st.button(t("export.generate_pdf"), use_container_width=True):
            prepare_pdf()

        exports = get_document_exports(st.session_state)
        runtime = get_document_runtime(st.session_state)
        pdf_bytes = exports.get("pdf_bytes")
        pdf_ready_for_version = exports.get("pdf_ready_for_version", -1)
        current_version = runtime.get("preview_version", 0)
        if pdf_bytes and pdf_ready_for_version == current_version:
            st.download_button(
                t("export.download_pdf"),
                data=pdf_bytes,
                file_name="resume.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.caption(t("export.pdf_lazy_caption"))
    with action_col2:
        preview_scale = st.slider(
            t("export.preview_scale"),
            min_value=70,
            max_value=160,
            value=current_scale,
            step=10,
            format="%d%%",
            key="preview_scale_slider",
        )
        st.session_state.preview_scale = preview_scale
        get_document_runtime(st.session_state)["preview_scale"] = preview_scale

    render_resume_preview(
        resume_data=get_resume_document(st.session_state)["resume"],
        style_params=get_current_style_params(),
        preview_version=get_document_runtime(st.session_state).get("preview_version", 0),
        workflow_logs=get_document_runtime(st.session_state).get("workflow_logs", []),
        preview_html=get_document_runtime(st.session_state).get("preview_html", ""),
        conditional_suggestions=get_document_runtime(st.session_state).get("conditional_suggestions", []),
    )


def main() -> None:
    st.set_page_config(
        page_title=PREVIEW_CONFIG.get("page_title", "智能简历生成器 MVP"),
        page_icon=PREVIEW_CONFIG.get("page_icon", "📄"),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    render_ui_style()
    render_sidebar()
    refresh_preview()
    render_main_panel()


if __name__ == "__main__":
    main()
