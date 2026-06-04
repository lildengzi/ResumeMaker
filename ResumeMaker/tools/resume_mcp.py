from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple

from core.data import ensure_resume_shape, merge_resume
from core.logging_config import get_logger


logger = get_logger(__name__)


class ResumeMCPTool:
    """Local MCP-like boundary for controlled resume reads and writes.

    The agent receives only a deep-copied resume JSON snapshot. Submitted JSON is
    schema-checked and constrained before it can become the committed resume.
    """

    def __init__(self, resume_data: Dict[str, Any]) -> None:
        self._original = ensure_resume_shape(deepcopy(resume_data))
        self._committed = ensure_resume_shape(deepcopy(resume_data))

    def get_resume_json(self) -> Dict[str, Any]:
        logger.info("resume_mcp.snapshot module_count=%s", len(self._committed.get("modules", []) or []))
        return deepcopy(self._committed)

    def submit_resume_json(self, candidate_resume: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        guarded, logs = self.validate_resume_patch(self._committed, candidate_resume)
        self._committed = merge_resume(self._committed, guarded)
        logger.info("resume_mcp.submit accepted module_count=%s", len(self._committed.get("modules", []) or []))
        return deepcopy(self._committed), logs

    def rollback(self) -> Dict[str, Any]:
        self._committed = deepcopy(self._original)
        logger.warning("resume_mcp.rollback")
        return deepcopy(self._committed)

    @staticmethod
    def validate_resume_patch(
        current_resume: Dict[str, Any],
        candidate_resume: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[str]]:
        if not isinstance(candidate_resume, dict):
            raise ValueError("MCP submit_resume_json expects a JSON object.")

        unsupported_keys = sorted(
            set(candidate_resume.keys()) - {"basics", "modules", "style", "conditional_suggestions"}
        )
        if unsupported_keys:
            raise ValueError(f"MCP submit rejected unsupported top-level keys: {unsupported_keys}")
        if "modules" not in candidate_resume or not isinstance(candidate_resume.get("modules"), list):
            raise ValueError("MCP submit requires a modules list.")

        current = ensure_resume_shape(current_resume)
        incoming = ensure_resume_shape(candidate_resume)
        guarded_modules: List[Dict[str, Any]] = []
        logs: List[str] = ["mcp.snapshot.deep_copied", "mcp.schema.validated", "mcp.basics_style.preserved"]

        current_by_id = {str(module.get("id", "")): module for module in current.get("modules", [])}
        current_by_type = {str(module.get("type", "")): module for module in current.get("modules", [])}

        for incoming_module in incoming.get("modules", []):
            if not isinstance(incoming_module, dict):
                raise ValueError("MCP submit rejected non-object module.")

            module_id = str(incoming_module.get("id", "") or "")
            module_type = str(incoming_module.get("type", "") or "")
            current_module = current_by_id.get(module_id) or current_by_type.get(module_type)
            if not current_module:
                raise ValueError(f"MCP submit rejected unknown module: {module_id or module_type}")
            if module_type != str(current_module.get("type", "")):
                raise ValueError(f"MCP submit rejected module type change: {module_id}")

            guarded = deepcopy(current_module)
            guarded["title"] = str(incoming_module.get("title", guarded.get("title", "")) or guarded.get("title", ""))
            guarded["visible"] = bool(incoming_module.get("visible", guarded.get("visible", True)))
            guarded["order"] = current_module.get("order", guarded.get("order", 0))
            guarded["content"] = ResumeMCPTool._constrain_module_content(current_module, incoming_module)
            guarded_modules.append(guarded)

        if not guarded_modules:
            raise ValueError("MCP submit did not include any recognized modules.")

        logs.append(f"mcp.modules.accepted={len(guarded_modules)}")
        return {
            "basics": deepcopy(current.get("basics", {})),
            "modules": guarded_modules,
            "style": deepcopy(current.get("style", {})),
        }, logs

    @staticmethod
    def _constrain_module_content(
        current_module: Dict[str, Any],
        incoming_module: Dict[str, Any],
    ) -> Dict[str, Any]:
        module_type = str(current_module.get("type", "") or "")
        current_content = current_module.get("content", {}) if isinstance(current_module.get("content"), dict) else {}
        incoming_content = incoming_module.get("content", {}) if isinstance(incoming_module.get("content"), dict) else {}

        if module_type in {"skills", "selfEvaluation"}:
            incoming_items = incoming_content.get("items", [])
            if not isinstance(incoming_items, list) or not all(isinstance(item, str) for item in incoming_items):
                raise ValueError(f"MCP submit rejected {module_type}: content.items must be a string list.")
            return {"items": incoming_items}

        if module_type == "custom":
            fields = current_content.get("fields", [])
            incoming_highlights = incoming_content.get("highlights", current_content.get("highlights", []))
            if not isinstance(incoming_highlights, list) or not all(isinstance(item, str) for item in incoming_highlights):
                raise ValueError("MCP submit rejected custom: content.highlights must be a string list.")
            return {
                "fields": deepcopy(fields if isinstance(fields, list) else []),
                "description": str(incoming_content.get("description", current_content.get("description", "")) or ""),
                "highlights": incoming_highlights,
            }

        current_items = current_content.get("items", [])
        incoming_items = incoming_content.get("items", [])
        if not isinstance(current_items, list) or not isinstance(incoming_items, list):
            raise ValueError(f"MCP submit rejected {module_type}: content.items must be a list.")
        if len(incoming_items) != len(current_items):
            raise ValueError(f"MCP submit rejected {module_type}: cannot add or remove experience items.")

        factual_keys_by_type = {
            "education": {"school", "degree", "major", "startDate", "endDate"},
            "projects": {"name", "role", "startDate", "endDate"},
            "companyExperience": {"company", "role", "startDate", "endDate"},
            "campusExperience": {"organization", "role", "startDate", "endDate"},
        }
        factual_keys = factual_keys_by_type.get(module_type, set())
        guarded_items: List[Dict[str, Any]] = []

        for current_item, incoming_item in zip(current_items, incoming_items):
            if not isinstance(current_item, dict) or not isinstance(incoming_item, dict):
                raise ValueError(f"MCP submit rejected {module_type}: items must be JSON objects.")
            guarded_item = deepcopy(current_item)
            for key, value in incoming_item.items():
                if key in factual_keys:
                    continue
                if key == "highlights":
                    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                        raise ValueError(f"MCP submit rejected {module_type}: highlights must be a string list.")
                    guarded_item[key] = value
                elif key in guarded_item:
                    guarded_item[key] = value
            guarded_items.append(guarded_item)

        return {"items": guarded_items}
