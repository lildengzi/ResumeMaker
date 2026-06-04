from __future__ import annotations

from copy import deepcopy

from core.data import create_generic_module, create_module, ensure_resume_shape, get_default_resume_data


def test_create_module_assigns_order_type_and_initial_items():
    module = create_module("projects", 7)

    assert module["id"] == "projects_7"
    assert module["type"] == "projects"
    assert module["order"] == 7
    assert module["visible"] is True
    assert module["content"]["items"] == [
        {
            "name": "",
            "role": "",
            "startDate": "",
            "endDate": "",
            "description": "",
            "highlights": [],
        }
    ]


def test_create_generic_module_is_the_only_new_module_shape():
    module = create_generic_module(3)

    assert module["id"] == "custom_3"
    assert module["title"] == "通用模块"
    assert module["type"] == "custom"
    assert module["order"] == 3
    assert module["visible"] is True
    assert module["content"]["items"] == []


def test_legacy_github_is_migrated_to_website_and_removed_from_basics():
    resume = get_default_resume_data()
    resume["basics"]["github"] = "https://example.com/legacy"

    normalized = ensure_resume_shape(resume)

    assert normalized["basics"]["website"] == "https://example.com/legacy"
    assert "portfolio" in normalized["basics"]
    assert "github" not in normalized["basics"]


def test_ensure_resume_shape_deduplicates_module_ids_after_additions():
    resume = get_default_resume_data()
    duplicate = deepcopy(resume["modules"][0])
    duplicate["order"] = 99
    resume["modules"].append(duplicate)

    normalized = ensure_resume_shape(resume)
    module_ids = [module["id"] for module in normalized["modules"]]

    assert len(module_ids) == len(set(module_ids))
    assert len(normalized["modules"]) == len(resume["modules"])


def test_ensure_resume_shape_keeps_deleted_module_list_without_readding_defaults():
    resume = get_default_resume_data()
    resume["modules"] = [module for module in resume["modules"] if module["type"] != "campusExperience"]

    normalized = ensure_resume_shape(resume)
    module_types = [module["type"] for module in normalized["modules"]]

    assert "campusExperience" not in module_types
    assert len(normalized["modules"]) == len(resume["modules"])


def test_runtime_shape_does_not_generate_legacy_top_level_sections():
    resume = get_default_resume_data()
    resume["modules"] = [
        {
            "id": "projects_1",
            "title": "Projects",
            "type": "projects",
            "visible": True,
            "order": 2,
            "content": {"items": [{"name": "Visible Project", "highlights": ["A"]}]},
        },
        {
            "id": "skills_1",
            "title": "Skills",
            "type": "skills",
            "visible": False,
            "order": 1,
            "content": {"items": ["Hidden Skill"]},
        },
    ]

    normalized = ensure_resume_shape(resume)

    assert "projects" not in normalized
    assert "skills" not in normalized
    projects_module = next(module for module in normalized["modules"] if module["type"] == "projects")
    assert projects_module["content"]["items"][0]["name"] == "Visible Project"


def test_custom_module_keeps_dynamic_field_boxes_above_description():
    resume = get_default_resume_data()
    resume["modules"] = [
        {
            "id": "custom_1",
            "title": "Extra",
            "type": "custom",
            "visible": True,
            "order": 1,
            "content": {
                "fields": [
                    {"label": "name", "value": "Competition"},
                    {"label": "role", "value": "Team lead"},
                    {"label": "", "value": ""},
                ],
                "description": "Built prototype.",
                "highlights": ["First prize", ""],
            },
        }
    ]

    normalized = ensure_resume_shape(resume)

    assert normalized["modules"][0]["content"] == {
        "fields": [
            {"label": "General subfield", "value": "Competition"},
            {"label": "General subfield", "value": "Team lead"},
        ],
        "description": "Built prototype.",
        "highlights": ["First prize"],
    }


def test_custom_module_migrates_legacy_items_to_field_boxes_and_description():
    resume = get_default_resume_data()
    resume["modules"] = [
        {
            "id": "custom_1",
            "title": "Extra",
            "type": "custom",
            "visible": True,
            "order": 1,
            "content": {
                "items": [
                    {
                        "title": "Competition",
                        "role": "Team lead",
                        "startDate": "2025.01",
                        "endDate": "2025.03",
                        "description": "Built prototype.",
                        "highlights": ["First prize"],
                    }
                ]
            },
        }
    ]

    normalized = ensure_resume_shape(resume)

    assert normalized["modules"][0]["content"]["fields"] == [
        {"label": "General subfield", "value": "Competition"},
        {"label": "General subfield", "value": "Team lead"},
        {"label": "General subfield", "value": "2025.01"},
        {"label": "General subfield", "value": "2025.03"},
    ]
    assert normalized["modules"][0]["content"]["description"] == "Built prototype."
    assert normalized["modules"][0]["content"]["highlights"] == ["First prize"]


def test_reordered_modules_are_preserved_by_normalization():
    resume = get_default_resume_data()
    resume["modules"] = [
        {
            "id": "skills_1",
            "title": "Skills",
            "type": "skills",
            "visible": True,
            "order": 20,
            "content": {"items": ["Python"]},
        },
        {
            "id": "education_1",
            "title": "Education",
            "type": "education",
            "visible": True,
            "order": 10,
            "content": {"items": [{"school": "Example University"}]},
        },
    ]

    normalized = ensure_resume_shape(resume)

    assert [module["order"] for module in normalized["modules"]] == [20, 10]
    assert sorted(module["order"] for module in normalized["modules"]) == [10, 20]
