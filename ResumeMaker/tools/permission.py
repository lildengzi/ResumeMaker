from __future__ import annotations

from pathlib import Path


WORKSPACE_DIR = Path(__file__).resolve().parent.parent


def ensure_workspace_path(path: str | Path) -> Path:
    """确保传入路径位于当前项目工作区内，避免工具越权访问。"""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (WORKSPACE_DIR / candidate).resolve()
    else:
        candidate = candidate.resolve()

    workspace = WORKSPACE_DIR.resolve()
    if workspace == candidate or workspace in candidate.parents:
        return candidate

    raise ValueError(f"禁止访问工作区之外的路径：{candidate}")
