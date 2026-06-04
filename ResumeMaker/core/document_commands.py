from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from core.data import create_generic_module, ensure_resume_shape


def mark_dirty(document: Dict[str, Any], dirty: bool = True) -> None:
    document.setdefault("runtime", {})["dirty"] = dirty


def update_basics(document: Dict[str, Any], field: str, value: Any) -> None:
    basics = document.setdefault("resume", {}).setdefault("basics", {})
    if basics.get(field) == value:
        return
    basics[field] = value
    mark_dirty(document)


def update_module(document: Dict[str, Any], module_id: str, patch: Dict[str, Any]) -> None:
    modules = document.setdefault("resume", {}).setdefault("modules", [])
    for index, module in enumerate(modules):
        if module.get("id") == module_id:
            updated = deepcopy(module)
            updated.update(patch)
            if updated == module:
                return
            modules[index] = updated
            mark_dirty(document)
            return


def add_module(document: Dict[str, Any], module_id: str | None = None) -> Dict[str, Any]:
    modules = document.setdefault("resume", {}).setdefault("modules", [])
    order = len(modules) + 1
    module = create_generic_module(order)
    if module_id:
        module["id"] = module_id
    modules.append(module)
    _renumber_modules(modules)
    mark_dirty(document)
    return module


def delete_module(document: Dict[str, Any], module_id: str) -> None:
    modules = document.setdefault("resume", {}).setdefault("modules", [])
    document["resume"]["modules"] = [module for module in modules if module.get("id") != module_id]
    _renumber_modules(document["resume"]["modules"])
    mark_dirty(document)


def move_module(document: Dict[str, Any], module_id: str, direction: int) -> None:
    modules = sorted(
        document.setdefault("resume", {}).setdefault("modules", []),
        key=lambda item: int(item.get("order", 0)),
    )
    index = next((idx for idx, module in enumerate(modules) if module.get("id") == module_id), None)
    if index is None:
        return

    target_index = index + direction
    if target_index < 0 or target_index >= len(modules):
        return

    modules[index], modules[target_index] = modules[target_index], modules[index]
    _renumber_modules(modules)
    document["resume"]["modules"] = modules
    mark_dirty(document)


def replace_resume_from_agent(document: Dict[str, Any], optimized_resume: Dict[str, Any]) -> None:
    document["resume"] = ensure_resume_shape(optimized_resume)
    mark_dirty(document)


def save_document_snapshot(document: Dict[str, Any]) -> Dict[str, Any]:
    mark_dirty(document, False)
    return ensure_resume_shape(document.get("resume", {}))


def _renumber_modules(modules: List[Dict[str, Any]]) -> None:
    for index, module in enumerate(modules, start=1):
        module["order"] = index
