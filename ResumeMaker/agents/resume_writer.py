from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, List

from agents.base_agent import BaseResumeAgent, WorkflowState
from config import APP_CONFIG
from core.data import ensure_resume_shape
from core.llm import extract_json_block
from core.service import build_local_resume_draft
from tools.resume_mcp import ResumeMCPTool


class ResumeWriterAgent(BaseResumeAgent):
    def __init__(self, llm=None, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name="resume_writer", llm=llm, config=config or APP_CONFIG)

    def run(self, state: WorkflowState) -> WorkflowState:
        next_state = deepcopy(state)
        current_resume = ensure_resume_shape(next_state.get("current_resume", {}))
        resume_tool = ResumeMCPTool(current_resume)
        resume_snapshot = resume_tool.get_resume_json()
        jd_text = str(next_state.get("jd_text", "") or "").strip()
        collected_facts = next_state.get("collected_facts", {})
        if not isinstance(collected_facts, dict):
            collected_facts = {}

        try:
            llm = self.require_llm()
            prompt = self._build_prompt(jd_text, resume_snapshot, collected_facts)
            response = llm.invoke(prompt)
            raw_content = response.content if hasattr(response, "content") else response
            content = raw_content if isinstance(raw_content, str) else str(raw_content)
            optimized = extract_json_block(content)
            suggestions = self._extract_conditional_suggestions(optimized)
            merged, guardrail_logs = resume_tool.submit_resume_json(optimized)
        except Exception as exc:
            next_state["error"] = str(exc)
            guardrail_logs = [f"LLM output rejected: {exc}"]
            llm_error = str(next_state.get("llm_error", "") or "").strip()
            if llm_error and llm_error != str(exc):
                guardrail_logs.append(f"LLM initialization failed: {llm_error}")
            merged = resume_tool.rollback()
            suggestions = []

        if self.config.get("workflow", {}).get("fallback_to_local_draft", True):
            merged = build_local_resume_draft(merged)

        next_state["optimized_resume"] = merged
        next_state["final_resume"] = merged
        next_state["conditional_suggestions"] = suggestions
        next_state["workflow_logs"] = [
            *(next_state.get("workflow_logs", []) or []),
            {
                "agent": self.name,
                "message_key": "workflow.log.resume_writer",
                "message": "Resume content optimization completed.",
                "details": guardrail_logs,
            },
        ]
        return next_state

    def _build_prompt(
        self,
        jd_text: str,
        current_resume: Dict[str, Any],
        collected_facts: Dict[str, Any] | None = None,
    ) -> str:
        prompt_config = self.config.get("prompts", {})
        rules = prompt_config.get("resume_writer_rules", [])
        rules_text = "\n".join(f"{idx + 1}. {rule}" for idx, rule in enumerate(rules))
        facts = collected_facts or {}
        uploaded_context = facts.get("uploaded_resume_context", {})
        if not isinstance(uploaded_context, dict):
            uploaded_context = {}
        uploaded_resume_text = str(uploaded_context.get("text", "") or "").strip()
        supplemental_context = facts.get("supplemental_context", {})
        if not isinstance(supplemental_context, dict):
            supplemental_context = {}
        supplemental_text = str(supplemental_context.get("text", "") or "").strip()
        optimization_goal = str(facts.get("optimization_goal", "") or "").strip()

        if jd_text:
            jd_instruction = prompt_config.get("resume_writer_with_jd", "").format(jd_text=jd_text)
        else:
            jd_instruction = prompt_config.get("resume_writer_without_jd", "")

        uploaded_resume_section = ""
        if uploaded_resume_text:
            uploaded_resume_section = (
                "Uploaded existing resume text. Use it only as factual context and writing reference; "
                "do not invent information that is not present:\n"
                f"{uploaded_resume_text}\n\n"
            )
        supplemental_section = ""
        if supplemental_text:
            supplemental_section = (
                "Supplemental candidate materials. These may include project notes, teaching cases, grades, "
                "certificates, portfolio notes, or parent/student-facing evidence. Use them only as factual context:\n"
                f"{supplemental_text}\n\n"
            )

        return (
            f"{prompt_config.get('resume_writer_system', 'You are a senior Chinese resume optimization expert.')}\n\n"
            f"General rules:\n{rules_text}\n\n"
            "Hard JSON boundary: return one valid JSON object only. The object may contain only top-level keys "
            "basics, modules, style, and conditional_suggestions. Editable resume content is limited to modules. "
            "Do not change factual anchors: name, contact details, photo, style, school, company, project name, "
            "organization, course/subject names, role, or dates when they are real evidence in the resume. Education "
            "facts are hard anchors. For skills, projects, companyExperience, campusExperience, selfEvaluation, and "
            "custom modules, you may rewrite, hide, clear, reorder, or replace items when the current content is "
            "irrelevant to the target scenario. Do not add nonexistent facts or modules.\n\n"
            f"Optimization mode: {optimization_goal or ('jd_targeted' if jd_text else 'general_resume_polish')}\n"
            "If uploaded resume text is provided, first use real experiences, skills, and outcomes from that text. "
            "If no JD is provided, polish the existing resume generally. If a JD is provided, strengthen only real "
            "experience that matches the JD or target communication scenario. This resume may target technical roles, "
            "tutoring, internships, campus work, competitions, admissions, or other candidate-introduction scenarios.\n\n"
            "Audience fit contract:\n"
            "1. Choose what the reader cares about. For parents hiring a tutor, prioritize subject competence, exam or "
            "course performance if provided, teaching method, ability to keep a child focused, patience, responsibility, "
            "communication with parents, availability fit, and trial-class readiness.\n"
            "2. Remove or hide irrelevant technical implementation details when the reader is not evaluating technical ability.\n"
            "3. For tutoring/parent-facing scenarios, set technical projects to visible=false or clear their items unless "
            "they are real tutoring/teaching cases. Do not keep long technical project sections just to prove explanation ability.\n"
            "4. Translate real technical/campus/project experience into broadly understandable strengths only when relevant: "
            "clear explanation, planning, responsibility, communication, persistence, and structured problem solving.\n\n"
            "STAR rewrite contract:\n"
            "1. For projects, companyExperience, campusExperience, tutoring/teaching cases, and custom evidence modules, "
            "rewrite editable description/highlights with STAR or evidence-first structure: context, action owned by "
            "the candidate, and result/impact.\n"
            "2. Do not invent metrics, exam scores, rankings, revenue, awards, teaching outcomes, deployment facts, "
            "or business outcomes.\n"
            "3. If a stronger STAR rewrite needs missing facts, put short questions in top-level "
            "conditional_suggestions instead of fabricating them.\n"
            "4. conditional_suggestions must be a string array. These suggestions are shown below the preview only "
            "and must not be inserted into the resume body.\n\n"
            "Skills tag contract:\n"
            "1. For the skills module, content.items must be short tag phrases, not full sentences.\n"
            "2. Each skills item must describe exactly one skill, specialty, tool, method, subject, or competency.\n"
            "3. Prefer tags like Python, FastAPI, Math tutoring, Error analysis, Parent communication, Trial-class preparation.\n"
            "4. Do not write sentence-style skills such as 'I am good at explaining math problems to students patiently'. "
            "Move sentence-level claims to selfEvaluation, experience description, or highlights when they are evidence-based.\n\n"
            "Tool contract:\n"
            "- The JSON below is the result of resume_mcp.get_resume_json(), a deep-copied snapshot of the current resume.\n"
            "- Your returned JSON will be passed to resume_mcp.submit_resume_json(). That tool validates schema, "
            "preserves factual anchors, and commits only accepted changes.\n"
            "- If the submit tool rejects your JSON, the workflow rolls back to the original snapshot.\n\n"
            f"{jd_instruction}\n\n"
            f"{uploaded_resume_section}"
            f"{supplemental_section}"
            f"Current resume JSON:\n{json.dumps(current_resume, ensure_ascii=False, indent=2)}\n\n"
            "Return JSON only."
        ).strip()

    @staticmethod
    def _extract_conditional_suggestions(payload: Dict[str, Any]) -> List[str]:
        raw_items = payload.get("conditional_suggestions", [])
        if not isinstance(raw_items, list):
            return []

        suggestions: List[str] = []
        for item in raw_items:
            text = str(item or "").strip()
            if text:
                suggestions.append(text[:240])
        return suggestions[:8]
