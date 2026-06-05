import json
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


def _summarize_uploaded_materials(uploaded_files: Optional[List[Dict[str, Any]]] = None) -> str:
    summaries: List[str] = []
    for file_meta in uploaded_files or []:
        if not isinstance(file_meta, dict):
            continue
        name = str(file_meta.get("name", "") or "").strip()
        file_type = str(file_meta.get("type", "") or "").strip()
        raw_text = str(file_meta.get("raw_text", "") or "").strip()
        if raw_text:
            summaries.append(f"[{file_type or 'material'}] {name}\n{raw_text[:4000]}")
        elif name:
            summaries.append(f"[{file_type or 'material'}] {name}")
    return "\n\n".join(summaries)


def build_resume_discussion_prompt(
    question: str,
    current_resume: Dict[str, Any],
    target_context: str = "",
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    shaped_resume = ensure_resume_shape(current_resume)
    history_lines = []
    for item in chat_history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip()
        content = str(item.get("content", "") or "").strip()
        if role and content:
            history_lines.append(f"{role}: {content[:1200]}")

    return (
        "你是一个求职简历策略顾问，不是代替用户编造经历的文案机器。\n"
        "你的目标是帮助求职者用真实材料快速做出针对不同岗位/场景的高通过率简历。\n\n"
        "工作原则：\n"
        "1. 先理解候选人的真实材料，再给建议。\n"
        "2. 可以指出哪些内容该保留、删除、隐藏、改写、补充。\n"
        "3. 不要编造不存在的成绩、证书、教学结果、公司、项目、时间和奖项。\n"
        "4. 如果信息不足，要给出具体补充问题或材料清单。\n"
        "5. 面对不同读者要转换表达。例如家长看家教简历时，不要细讲技术实现，要突出学科能力、耐心、责任感、讲解方法、专注力引导和家长沟通。\n"
        "6. 回答要具体、可执行，可以直接给出可粘贴到简历里的改写片段，但必须标注哪些依赖用户确认。\n\n"
        f"目标场景 / JD：\n{target_context or '未提供，按通用求职/候选人展示场景分析。'}\n\n"
        f"当前简历 JSON：\n{json.dumps(shaped_resume, ensure_ascii=False, indent=2)}\n\n"
        f"上传材料摘要：\n{_summarize_uploaded_materials(uploaded_files) or '无'}\n\n"
        f"对话历史：\n{chr(10).join(history_lines[-8:]) or '无'}\n\n"
        f"用户问题：\n{question}\n\n"
        "请用中文回答，优先给出结论，然后给出具体修改建议、材料缺口和真实性风险。"
    )


def discuss_resume_with_ai(
    question: str,
    current_resume: Dict[str, Any],
    target_context: str = "",
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
    llm: Any = None,
) -> Dict[str, Any]:
    question = str(question or "").strip()
    if not question:
        return {"answer": "请先输入你想讨论的问题。", "error": None}

    prompt = build_resume_discussion_prompt(
        question=question,
        current_resume=current_resume,
        target_context=target_context,
        uploaded_files=uploaded_files,
        chat_history=chat_history,
    )

    try:
        advisor_llm = llm or create_llm()
        response = advisor_llm.invoke(prompt)
        raw_content = response.content if hasattr(response, "content") else response
        answer = raw_content if isinstance(raw_content, str) else str(raw_content)
        return {"answer": answer.strip(), "error": None, "prompt": prompt}
    except Exception as exc:
        logger.warning("service.discuss_resume_with_ai failed error=%s", exc)
        fallback = (
            "当前无法调用模型，但可以先按这个方向处理：\n"
            "- 明确目标读者最关心什么，例如技术面试官看项目，家长看学科能力、耐心、责任感和沟通方式。\n"
            "- 删除或隐藏目标读者不关心的内容，不要硬把无关技术项目包装成优势。\n"
            "- 只保留可被当前材料证明的能力；缺少成绩、教学经历、证书或成果时，应先补材料再写进简历。\n"
            "- 每段经历最好回答：我做了什么、体现什么能力、对目标岗位有什么价值。"
        )
        return {"answer": fallback, "error": str(exc), "prompt": prompt}


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
