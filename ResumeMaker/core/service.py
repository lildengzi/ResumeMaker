from typing import Any, Dict, List, Optional

from config import APP_CONFIG
from core.data import ensure_resume_shape, get_default_resume_data, normalize_list_of_strings
from core.logging_config import get_logger
from core.llm import create_llm


logger = get_logger(__name__)


def _find_module(data: Dict[str, Any], module_type: str) -> Dict[str, Any] | None:
    for module in data.get("modules", []):
        if module.get("type") == module_type:
            return module
    return None


def build_local_resume_draft(current_resume: Dict[str, Any]) -> Dict[str, Any]:
    data = ensure_resume_shape(current_resume)
    basics = data.get("basics", {})
    headline = basics.get("headline", "").strip().lower()

    resume_config = APP_CONFIG["resume"]
    role_skills_map = resume_config.get("role_skills_map", {})
    generated_skills: List[str] = []

    for keyword, items in role_skills_map.items():
        if keyword in headline and isinstance(items, list):
            generated_skills.extend([str(item).strip() for item in items if str(item).strip()])

    if not generated_skills:
        generated_skills = normalize_list_of_strings(resume_config.get("default_skills", []))

    skills_module = _find_module(data, "skills")
    existing_skills = normalize_list_of_strings((skills_module or {}).get("content", {}).get("items", []))
    if not existing_skills:
        if skills_module is not None:
            skills_module["content"] = {"items": generated_skills[:5]}
    else:
        if skills_module is not None:
            skills_module["content"] = {"items": existing_skills}

    self_evaluation_module = _find_module(data, "selfEvaluation")
    existing_self_evaluation = normalize_list_of_strings(
        (self_evaluation_module or {}).get("content", {}).get("items", [])
    )
    if not existing_self_evaluation:
        role_name = basics.get("headline", "").strip() or "目标岗位"
        templates = resume_config.get("default_self_evaluation_templates", [])
        if self_evaluation_module is not None:
            self_evaluation_module["content"] = {
                "items": [
                    str(template).format(role_name=role_name).strip()
                    for template in templates
                    if str(template).strip()
                ]
            }

    return data


def optimize_resume_by_jd(
    jd_text: str,
    current_resume: Dict[str, Any],
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
    style_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return run_resume_workflow(jd_text, current_resume, uploaded_files, style_params)["final_resume"]


def run_resume_workflow(
    jd_text: str,
    current_resume: Dict[str, Any],
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
    style_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from workflow.graph import ResumeWorkflow

    logger.info(
        "service.run_resume_workflow start has_jd=%s upload_count=%s",
        bool(str(jd_text or "").strip()),
        len(uploaded_files or []),
    )
    workflow = ResumeWorkflow(config=APP_CONFIG)
    initial_state = workflow.build_initial_state(
        jd_text=jd_text,
        current_resume=current_resume,
        uploaded_files=uploaded_files,
        style_params=style_params,
    )
    result_state = workflow.run(initial_state)
    logger.info(
        "service.run_resume_workflow finish error=%s parsed_changes=%s suggestions=%s",
        bool(result_state.get("error")),
        len(result_state.get("parsed_resume_changes", []) or []),
        len(result_state.get("conditional_suggestions", []) or []),
    )
    return {
        "final_resume": workflow.get_final_resume(result_state),
        "workflow_logs": workflow.get_workflow_logs(result_state),
        "error": result_state.get("error"),
        "llm_error": result_state.get("llm_error"),
        "parsed_resume_changes": result_state.get("parsed_resume_changes", []),
        "conditional_suggestions": result_state.get("conditional_suggestions", []),
    }


def import_existing_resume(
    current_resume: Dict[str, Any],
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    from agents.existing_resume_parser import ExistingResumeParserAgent
    from agents.info_collector import InfoCollectorAgent
    try:
        llm = create_llm()
    except Exception:
        logger.warning("service.import_existing_resume llm_unavailable", exc_info=True)
        llm = None

    logger.info("service.import_existing_resume start upload_count=%s", len(uploaded_files or []))
    current = ensure_resume_shape(current_resume)
    import_base = get_default_resume_data()
    import_base["style"] = current.get("style", import_base.get("style", {}))
    if current.get("basics", {}).get("photo_path"):
        import_base["basics"]["photo_path"] = current["basics"]["photo_path"]

    state: Dict[str, Any] = {
        "jd_text": "",
        "current_resume": import_base,
        "uploaded_files": uploaded_files or [],
        "workflow_logs": [],
    }
    state = InfoCollectorAgent(config=APP_CONFIG).run(state)
    state = ExistingResumeParserAgent(llm=llm, config=APP_CONFIG).run(state)
    logger.info(
        "service.import_existing_resume finish error=%s parsed_changes=%s",
        bool(state.get("existing_resume_parser_error")),
        len(state.get("parsed_resume_changes", []) or []),
    )
    return {
        "final_resume": ensure_resume_shape(state.get("current_resume", {})),
        "workflow_logs": state.get("workflow_logs", []),
        "parsed_resume_changes": state.get("parsed_resume_changes", []),
        "error": state.get("existing_resume_parser_error"),
    }
