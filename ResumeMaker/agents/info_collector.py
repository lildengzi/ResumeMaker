from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from agents.base_agent import BaseResumeAgent, WorkflowState
from core.data import ensure_resume_shape
from tools.file_tools import parse_uploaded_resume


MAX_CONTEXT_TEXT_CHARS = 12000


# 这个 Agent 当前主要承担“输入整理”职责，而不是复杂推理。
# 之所以仍保留为独立 Agent，是为了让学习者看到：
# - 工作流中的每一步可以是不同职责的节点；
# - 以后如果要接入 OCR、URL 抓取、文件解析，可以继续扩展在这里。
class InfoCollectorAgent(BaseResumeAgent):
    def __init__(self, llm=None, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name="info_collector", llm=llm, config=config)

    def run(self, state: WorkflowState) -> WorkflowState:
        next_state = deepcopy(state)
        current_resume = ensure_resume_shape(next_state.get("current_resume", {}))
        jd_text = str(next_state.get("jd_text", "") or "").strip()
        uploaded_files = next_state.get("uploaded_files", []) or []
        normalized_files = self._normalize_uploaded_files(uploaded_files)
        uploaded_resume_context = self._collect_uploaded_resume_context(normalized_files)
        supplemental_context = self._collect_supplemental_context(normalized_files)

        basics = current_resume.get("basics", {})
        collected_facts = {
            "candidate_name": basics.get("name", "").strip(),
            "headline": basics.get("headline", "").strip(),
            "jd_text": jd_text,
            "has_jd": bool(jd_text),
            "optimization_goal": "jd_targeted" if jd_text else "general_resume_polish",
            "uploaded_files": normalized_files,
            "uploaded_resume_context": uploaded_resume_context,
            "supplemental_context": supplemental_context,
            "sections_summary": self._summarize_sections(current_resume),
        }

        next_state["collected_facts"] = collected_facts
        next_state["workflow_logs"] = [
            *(next_state.get("workflow_logs", []) or []),
            {
                "agent": self.name,
                "message_key": (
                    "workflow.log.info_collector"
                    if normalized_files
                    else "workflow.log.info_collector.no_uploads"
                ),
                "message_args": {"file_count": len(normalized_files)},
                "message": "已完成输入信息汇总。",
            },
        ]
        return next_state

    @staticmethod
    def _normalize_uploaded_files(uploaded_files: List[Any]) -> List[Dict[str, str]]:
        normalized: List[Dict[str, str]] = []
        for item in uploaded_files:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "name": str(item.get("name", "") or "").strip(),
                        "type": str(item.get("type", "") or "").strip(),
                        "path": str(item.get("path", "") or "").strip(),
                        "raw_text": str(item.get("raw_text", "") or "").strip(),
                    }
                )
        return normalized

    @staticmethod
    def _summarize_sections(current_resume: Dict[str, Any]) -> Dict[str, int]:
        counts = {
            "education_count": 0,
            "skills_count": 0,
            "projects_count": 0,
            "company_experience_count": 0,
            "campus_experience_count": 0,
            "self_evaluation_count": 0,
        }
        key_by_type = {
            "education": "education_count",
            "skills": "skills_count",
            "projects": "projects_count",
            "companyExperience": "company_experience_count",
            "campusExperience": "campus_experience_count",
            "selfEvaluation": "self_evaluation_count",
        }

        for module in current_resume.get("modules", []) or []:
            if not isinstance(module, dict):
                continue
            count_key = key_by_type.get(str(module.get("type", "") or ""))
            if not count_key:
                continue
            items = module.get("content", {}).get("items", [])
            counts[count_key] += len(items) if isinstance(items, list) else 0

        return counts

    @staticmethod
    def _collect_uploaded_resume_context(uploaded_files: List[Dict[str, str]]) -> Dict[str, Any]:
        parsed_files: List[Dict[str, str]] = []
        text_parts: List[str] = []

        for file_meta in uploaded_files:
            if file_meta.get("type") != "existing_resume":
                continue

            parsed: Dict[str, Any] = {}
            raw_text = str(file_meta.get("raw_text", "") or "").strip()
            if not raw_text and file_meta.get("path"):
                try:
                    parsed = parse_uploaded_resume(file_meta["path"])
                    raw_text = str(parsed.get("raw_text", "") or "").strip()
                except Exception as exc:
                    parsed = {"note": f"解析失败：{exc}"}

            entry = {
                "name": file_meta.get("name", ""),
                "file_type": str(parsed.get("file_type", "") or ""),
                "note": str(parsed.get("note", "") or ""),
                "has_text": bool(raw_text),
            }
            parsed_files.append(entry)

            if raw_text:
                remaining = MAX_CONTEXT_TEXT_CHARS - sum(len(part) for part in text_parts)
                if remaining <= 0:
                    continue
                clipped = raw_text[:remaining]
                text_parts.append(f"文件：{file_meta.get('name', '')}\n{clipped}")

        return {
            "files": parsed_files,
            "text": "\n\n".join(text_parts).strip(),
        }

    @staticmethod
    def _collect_supplemental_context(uploaded_files: List[Dict[str, str]]) -> Dict[str, Any]:
        parsed_files: List[Dict[str, str]] = []
        text_parts: List[str] = []

        for file_meta in uploaded_files:
            if file_meta.get("type") == "existing_resume":
                continue

            raw_text = str(file_meta.get("raw_text", "") or "").strip()
            if not raw_text:
                continue

            entry = {
                "name": file_meta.get("name", ""),
                "type": file_meta.get("type", ""),
                "has_text": True,
            }
            parsed_files.append(entry)

            remaining = MAX_CONTEXT_TEXT_CHARS - sum(len(part) for part in text_parts)
            if remaining <= 0:
                continue
            text_parts.append(f"文件：{file_meta.get('name', '')}\n{raw_text[:remaining]}")

        return {
            "files": parsed_files,
            "text": "\n\n".join(text_parts).strip(),
        }
