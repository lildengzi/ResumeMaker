from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from agents.factory import AgentFactory
from config import APP_CONFIG
from core.data import ensure_resume_shape
from core.logging_config import get_logger
from core.llm import create_llm


WorkflowState = Dict[str, Any]
logger = get_logger(__name__)


# 这里保留独立的 Workflow 类，是为了让学习者看到：
# - 页面层只负责触发，不直接拼接所有后端细节；
# - Agent 的调用顺序由工作流统一编排；
# - 未来如果要升级到 LangGraph / 重试 / 分支逻辑，可以在这里继续扩展。
#
# 当前版本仍然是“顺序执行”的轻量实现，并不是真正的图式工作流。
class ResumeWorkflow:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or APP_CONFIG
        self.workflow_config = self.config.get("workflow", {})

    def build_initial_state(
        self,
        jd_text: str,
        current_resume: Dict[str, Any],
        uploaded_files: Optional[List[Dict[str, Any]]] = None,
        style_params: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        return {
            "jd_text": (jd_text or "").strip(),
            "current_resume": ensure_resume_shape(current_resume),
            "uploaded_files": uploaded_files or [],
            "style_params": style_params or {},
            "collected_facts": {},
            "optimized_resume": None,
            "final_resume": None,
            "workflow_logs": [],
            "error": None,
        }

    def run(self, initial_state: WorkflowState) -> WorkflowState:
        state = deepcopy(initial_state)
        logger.info(
            "workflow.start has_jd=%s upload_count=%s module_count=%s",
            bool(state.get("jd_text")),
            len(state.get("uploaded_files", []) or []),
            len(state.get("current_resume", {}).get("modules", []) or []),
        )
        llm = self._try_create_llm()
        if llm is None:
            state["llm_error"] = getattr(self, "_last_llm_error", "LLM is not configured.")

        entry_agent_name = self.workflow_config.get("entry_agent", "info_collector")
        parser_agent_name = self.workflow_config.get("parser_agent", "existing_resume_parser")
        writer_agent_name = self.workflow_config.get("writer_agent", "resume_writer")

        entry_agent = AgentFactory.create(entry_agent_name, llm=llm, config=self.config)
        parser_agent = AgentFactory.create(parser_agent_name, llm=llm, config=self.config)
        writer_agent = AgentFactory.create(writer_agent_name, llm=llm, config=self.config)

        state = entry_agent.run(state)
        state = parser_agent.run(state)
        state = writer_agent.run(state)
        logger.info(
            "workflow.finish error=%s parsed_changes=%s suggestions=%s",
            bool(state.get("error")),
            len(state.get("parsed_resume_changes", []) or []),
            len(state.get("conditional_suggestions", []) or []),
        )
        return state

    @staticmethod
    def get_final_resume(state: WorkflowState) -> Dict[str, Any]:
        final_resume = state.get("final_resume")
        if isinstance(final_resume, dict):
            return ensure_resume_shape(final_resume)
        return ensure_resume_shape(state.get("current_resume", {}))

    @staticmethod
    def get_workflow_logs(state: WorkflowState) -> List[Dict[str, Any]]:
        logs = state.get("workflow_logs", [])
        if isinstance(logs, list):
            return logs
        return []

    def _try_create_llm(self):
        try:
            return create_llm()
        except Exception as exc:
            self._last_llm_error = str(exc)
            logger.warning("workflow.llm_unavailable error=%s", exc)
            return None
