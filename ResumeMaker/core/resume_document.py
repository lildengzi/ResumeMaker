from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable, Dict, List, MutableMapping

from core.data import ensure_resume_shape
from renderers import build_full_preview_document, build_style_params, render_resume_markdown


DocumentObserver = Callable[[MutableMapping[str, Any], str], None]


DOCUMENT_KEY = "resume_document"


def create_resume_document(
    resume_data: Dict[str, Any] | None = None,
    style_params: Dict[str, Any] | None = None,
    jd_text: str = "",
    uploaded_files: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    resume = ensure_resume_shape(resume_data)
    style = build_style_params(style_params or resume.get("style", {}))
    style.pop("preview_scale", None)
    resume["style"] = deepcopy(style)
    saved_inputs = resume.get("inputs", {}) if isinstance(resume.get("inputs"), dict) else {}
    resolved_jd_text = jd_text if jd_text else str(saved_inputs.get("jd_text", "") or "")
    resolved_uploaded_files = uploaded_files if uploaded_files is not None else saved_inputs.get("uploaded_files", [])

    return {
        "resume": resume,
        "style": deepcopy(style),
        "inputs": {
            **deepcopy(saved_inputs),
            "jd_text": resolved_jd_text,
            "uploaded_files": deepcopy(resolved_uploaded_files or []),
        },
        "runtime": {
            "preview_version": 0,
            "preview_html": "",
            "preview_signature": "",
            "preview_scale": 100,
            "dirty": False,
            "workflow_logs": [],
            "conditional_suggestions": [],
        },
        "exports": {
            "markdown": "",
            "pdf_bytes": None,
            "pdf_ready_for_version": -1,
        },
    }


def ensure_resume_document(session_state: MutableMapping[str, Any]) -> Dict[str, Any]:
    if DOCUMENT_KEY not in session_state:
        session_state[DOCUMENT_KEY] = create_resume_document(
            session_state.get("resume_data"),
            session_state.get("style_params"),
            str(session_state.get("jd_input", "") or ""),
            session_state.get("uploaded_files_meta", []),
        )
    return session_state[DOCUMENT_KEY]


def get_resume_document(session_state: MutableMapping[str, Any]) -> Dict[str, Any]:
    return ensure_resume_document(session_state)


def get_document_resume(session_state: MutableMapping[str, Any]) -> Dict[str, Any]:
    return get_resume_document(session_state)["resume"]


def get_document_style(session_state: MutableMapping[str, Any]) -> Dict[str, Any]:
    return get_resume_document(session_state)["style"]


def get_document_exports(session_state: MutableMapping[str, Any]) -> Dict[str, Any]:
    return get_resume_document(session_state)["exports"]


def get_document_runtime(session_state: MutableMapping[str, Any]) -> Dict[str, Any]:
    return get_resume_document(session_state)["runtime"]


def sync_session_aliases(session_state: MutableMapping[str, Any], include_widget_keys: bool = False) -> None:
    """Expose legacy session keys as references into the unified document JSON."""
    document = ensure_resume_document(session_state)
    session_state["resume_data"] = document["resume"]
    session_state["style_params"] = document["style"]
    session_state["uploaded_files_meta"] = document["inputs"].get("uploaded_files", [])
    session_state["preview_resume_data"] = document["resume"]
    session_state["preview_version"] = document["runtime"].get("preview_version", 0)
    session_state["preview_html"] = document["runtime"].get("preview_html", "")
    session_state["preview_signature"] = document["runtime"].get("preview_signature", "")
    session_state["workflow_logs"] = document["runtime"].get("workflow_logs", [])
    session_state["markdown_export"] = document["exports"].get("markdown", "")
    session_state["pdf_bytes"] = document["exports"].get("pdf_bytes")
    session_state["pdf_ready_for_version"] = document["exports"].get("pdf_ready_for_version", -1)
    if include_widget_keys:
        if "jd_input" not in session_state:
            session_state["jd_input"] = document["inputs"].get("jd_text", "")
        if "preview_scale" not in session_state:
            session_state["preview_scale"] = document["runtime"].get(
                "preview_scale",
                session_state.get("preview_scale", 100),
            )


def _document_signature(document: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "resume": document.get("resume", {}),
            "style": document.get("style", {}),
            "preview_scale": document.get("runtime", {}).get("preview_scale", 100),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _normalize_document_observer(session_state: MutableMapping[str, Any], event: str) -> None:
    document = ensure_resume_document(session_state)
    document["resume"] = ensure_resume_shape(session_state.get("resume_data", document.get("resume", {})))
    document["style"] = build_style_params(session_state.get("style_params", document.get("style", {})))
    document["style"].pop("preview_scale", None)
    document["resume"]["style"] = deepcopy(document["style"])

    document.setdefault("inputs", {})
    document["inputs"]["jd_text"] = str(session_state.get("jd_input", document["inputs"].get("jd_text", "")) or "")
    document["inputs"]["uploaded_files"] = deepcopy(
        session_state.get("uploaded_files_meta", document["inputs"].get("uploaded_files", [])) or []
    )
    for key in ["jd_source", "jd_url_input", "jd_ocr_text", "uploaded_readme_text", "existing_resume_name"]:
        if key in session_state:
            document["inputs"][key] = deepcopy(session_state.get(key, ""))
    document.setdefault("runtime", {})["preview_scale"] = int(
        session_state.get("preview_scale", document.get("runtime", {}).get("preview_scale", 100)) or 100
    )


def _preview_observer(session_state: MutableMapping[str, Any], event: str) -> None:
    document = ensure_resume_document(session_state)
    runtime = document.setdefault("runtime", {})
    signature = _document_signature(document)
    if event != "force" and signature == runtime.get("preview_signature", ""):
        runtime["_document_changed"] = False
        return

    style_params = dict(document.get("style", {}))
    style_params["preview_scale"] = int(runtime.get("preview_scale", 100))
    runtime["preview_html"] = build_full_preview_document(document["resume"], style_params=style_params)
    runtime["preview_version"] = int(runtime.get("preview_version", 0)) + 1
    runtime["preview_signature"] = signature
    runtime["_document_changed"] = True


def _markdown_observer(session_state: MutableMapping[str, Any], event: str) -> None:
    document = ensure_resume_document(session_state)
    if not document.setdefault("runtime", {}).get("_document_changed", False):
        return
    document.setdefault("exports", {})["markdown"] = render_resume_markdown(document["resume"])


def _pdf_invalidation_observer(session_state: MutableMapping[str, Any], event: str) -> None:
    document = ensure_resume_document(session_state)
    if not document.setdefault("runtime", {}).get("_document_changed", False):
        return
    exports = document.setdefault("exports", {})
    exports["pdf_bytes"] = None
    exports["pdf_ready_for_version"] = -1


def _legacy_alias_observer(session_state: MutableMapping[str, Any], event: str) -> None:
    sync_session_aliases(session_state)


DOCUMENT_OBSERVERS: List[DocumentObserver] = [
    _normalize_document_observer,
    _preview_observer,
    _markdown_observer,
    _pdf_invalidation_observer,
    _legacy_alias_observer,
]


def notify_document_changed(session_state: MutableMapping[str, Any], event: str = "change") -> None:
    for observer in DOCUMENT_OBSERVERS:
        observer(session_state, event)
