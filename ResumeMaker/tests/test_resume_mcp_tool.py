from copy import deepcopy

import pytest

from core.data import get_default_resume_data
from tools.resume_mcp import ResumeMCPTool


def _resume_with_project():
    resume = get_default_resume_data()
    resume["basics"]["name"] = "Candidate"
    resume["style"]["theme_color"] = "#123456"
    project_module = next(module for module in resume["modules"] if module["type"] == "projects")
    project_module["content"]["items"] = [
        {
            "name": "ResumeMaker",
            "role": "Backend Developer",
            "startDate": "2025.01",
            "endDate": "2025.03",
            "description": "Built preview.",
            "highlights": ["Built export flow"],
        }
    ]
    return resume


def test_resume_mcp_returns_deep_copied_snapshot():
    resume = _resume_with_project()
    tool = ResumeMCPTool(resume)

    snapshot = tool.get_resume_json()
    snapshot["basics"]["name"] = "Mutated"

    assert tool.get_resume_json()["basics"]["name"] == "Candidate"
    assert resume["basics"]["name"] == "Candidate"


def test_resume_mcp_submit_preserves_fact_anchors_and_style():
    resume = _resume_with_project()
    tool = ResumeMCPTool(resume)
    candidate = deepcopy(tool.get_resume_json())
    project_module = next(module for module in candidate["modules"] if module["type"] == "projects")
    project = project_module["content"]["items"][0]
    project["name"] = "Invented"
    project["role"] = "Tech Lead"
    project["startDate"] = "2026.01"
    project["description"] = "Used Streamlit to improve resume preview reliability."
    project["highlights"] = ["Reduced export failures after adding validation."]
    candidate["basics"]["name"] = "Other"
    candidate["style"]["theme_color"] = "#000000"

    committed, logs = tool.submit_resume_json(candidate)

    committed_project = next(module for module in committed["modules"] if module["type"] == "projects")["content"][
        "items"
    ][0]
    assert committed["basics"]["name"] == "Candidate"
    assert committed["style"]["theme_color"] == "#123456"
    assert committed_project["name"] == "ResumeMaker"
    assert committed_project["role"] == "Backend Developer"
    assert committed_project["startDate"] == "2025.01"
    assert committed_project["description"] == "Used Streamlit to improve resume preview reliability."
    assert "mcp.schema.validated" in logs


def test_resume_mcp_rejects_unknown_modules_and_can_rollback():
    resume = _resume_with_project()
    tool = ResumeMCPTool(resume)
    candidate = deepcopy(tool.get_resume_json())
    candidate["modules"].append(
        {
            "id": "invented_99",
            "title": "Awards",
            "type": "custom",
            "visible": True,
            "order": 99,
            "content": {"fields": [], "description": "Invented", "highlights": []},
        }
    )

    with pytest.raises(ValueError, match="unknown module"):
        tool.submit_resume_json(candidate)

    assert tool.rollback()["basics"]["name"] == "Candidate"
