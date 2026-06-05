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


def test_resume_mcp_submit_preserves_basics_style_and_allows_project_rewrite():
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
    assert committed_project["name"] == "Invented"
    assert committed_project["role"] == "Tech Lead"
    assert committed_project["startDate"] == "2026.01"
    assert committed_project["description"] == "Used Streamlit to improve resume preview reliability."
    assert "mcp.schema.validated" in logs


def test_resume_mcp_allows_parent_facing_replacement_of_editable_modules():
    resume = _resume_with_project()
    education_module = next(module for module in resume["modules"] if module["type"] == "education")
    education_module["content"]["items"] = [
        {
            "school": "Example University",
            "degree": "本科",
            "major": "数学",
            "startDate": "2023.09",
            "endDate": "2027.06",
            "details": "高等数学、教育心理学",
        }
    ]
    campus_module = next(module for module in resume["modules"] if module["type"] == "campusExperience")
    campus_module["content"]["items"] = [
        {
            "organization": "Student Union",
            "role": "Member",
            "startDate": "2024.01",
            "endDate": "2024.06",
            "description": "Organized events.",
            "highlights": ["Coordinated classmates."],
        }
    ]
    tool = ResumeMCPTool(resume)
    candidate = deepcopy(tool.get_resume_json())

    next(module for module in candidate["modules"] if module["type"] == "skills")["content"]["items"] = [
        "小学数学知识讲解",
        "错题分析与复盘",
        "耐心沟通",
    ]
    next(module for module in candidate["modules"] if module["type"] == "projects")["content"]["items"] = []
    next(module for module in candidate["modules"] if module["type"] == "campusExperience")["content"]["items"] = [
        {
            "organization": "同伴学习辅导",
            "role": "数学讲解与作业辅导",
            "startDate": "",
            "endDate": "",
            "description": "用家长能理解的方式说明知识点和学习计划。",
            "highlights": ["课前准备例题，课后整理错题。"],
        }
    ]
    next(module for module in candidate["modules"] if module["type"] == "selfEvaluation")["content"]["items"] = [
        "讲解有耐心，能根据孩子反应调整节奏。",
        "重视课前准备和课后反馈，适合需要长期陪伴的学生。",
    ]
    candidate["basics"]["name"] = "Other"
    candidate["style"]["theme_color"] = "#000000"
    candidate_education = next(module for module in candidate["modules"] if module["type"] == "education")
    candidate_education["content"]["items"][0]["school"] = "Invented School"

    committed, _ = tool.submit_resume_json(candidate)

    assert committed["basics"]["name"] == "Candidate"
    assert committed["style"]["theme_color"] == "#123456"
    committed_education = next(module for module in committed["modules"] if module["type"] == "education")
    assert committed_education["content"]["items"][0]["school"] == "Example University"
    assert next(module for module in committed["modules"] if module["type"] == "projects")["content"]["items"] == []
    assert "小学数学知识讲解" in next(module for module in committed["modules"] if module["type"] == "skills")[
        "content"
    ]["items"]
    assert "同伴学习辅导" in str(
        next(module for module in committed["modules"] if module["type"] == "campusExperience")["content"]["items"]
    )


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
