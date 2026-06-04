from typing import Any, Dict

from core.markdown import render_markdown


def render_resume_markdown(resume_data: Dict[str, Any]) -> str:
    return render_markdown(resume_data)
