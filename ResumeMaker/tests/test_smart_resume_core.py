from core.data import (
    ensure_modular_resume_shape,
    ensure_resume_shape,
    get_default_modular_resume_data,
    get_default_resume_data,
    merge_resume,
    migrate_legacy_resume,
    normalize_list_of_strings,
    save_resume_data,
)
import json
import pytest
from config import DEFAULT_CONFIG
from core.llm import extract_json_block
from core.service import build_local_resume_draft


def test_extract_json_block_from_fenced_json():
    text = """```json
    {"skills": ["Python", "FastAPI"]}
    ```"""

    result = extract_json_block(text)

    assert result == {"skills": ["Python", "FastAPI"]}


def test_extract_json_block_from_plain_text_with_json():
    text = '以下是结果：{"selfEvaluation":["认真负责"]}，请查收。'

    result = extract_json_block(text)

    assert result == {"selfEvaluation": ["认真负责"]}


def test_extract_json_block_raises_for_invalid_text():
    text = "这不是一个 JSON 输出"

    try:
        extract_json_block(text)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "提取 JSON" in str(exc)


def test_normalize_list_of_strings_filters_empty_and_non_string_values():
    items = [" Python ", "", "  ", None, 123, "FastAPI"]

    result = normalize_list_of_strings(items)

    assert result == ["Python", "FastAPI"]


def test_default_llm_config_has_fast_failure_bounds():
    llm_config = DEFAULT_CONFIG["llm"]

    assert llm_config["timeout"] == 12
    assert llm_config["max_retries"] == 0


def test_merge_resume_uses_modules_as_the_merge_surface():
    original = get_default_resume_data()
    original["basics"]["name"] = "张三"
    original["basics"]["headline"] = "Python 后端开发"
    original["modules"][0]["content"]["items"][0]["school"] = "示例大学"

    optimized = get_default_resume_data()
    optimized["basics"]["name"] = "李四"
    optimized["modules"][0]["content"]["items"][0]["school"] = "另一所大学"
    optimized["modules"][1]["content"]["items"] = [" Python ", "", "FastAPI"]
    optimized["modules"][5]["content"]["items"] = ["认真负责"]
    optimized["modules"][2]["content"]["items"] = [
        {
            "name": "简历生成器",
            "role": "开发者",
            "startDate": "2024.01",
            "endDate": "2024.03",
            "description": "负责核心开发",
            "highlights": ["独立完成", "", "支持导出"],
        }
    ]

    merged = merge_resume(original, optimized)

    assert merged["basics"]["name"] == "张三"
    assert merged["modules"][0]["content"]["items"][0]["school"] == "另一所大学"
    assert merged["modules"][1]["content"]["items"] == ["Python", "FastAPI"]
    assert merged["modules"][5]["content"]["items"] == ["认真负责"]
    assert merged["modules"][2]["content"]["items"][0]["highlights"] == ["独立完成", "支持导出"]


def test_build_local_resume_draft_fills_missing_skills_and_self_evaluation():
    resume = get_default_resume_data()
    resume["basics"]["headline"] = "Python 后端开发"

    drafted = build_local_resume_draft(resume)

    skills_module = next(module for module in drafted["modules"] if module["type"] == "skills")
    self_evaluation_module = next(module for module in drafted["modules"] if module["type"] == "selfEvaluation")

    assert skills_module["content"]["items"]
    assert len(skills_module["content"]["items"]) <= 5
    assert any(
        "Python" in skill or "接口" in skill or "Git" in skill for skill in skills_module["content"]["items"]
    )
    assert self_evaluation_module["content"]["items"]
    assert any("Python 后端开发" in item for item in self_evaluation_module["content"]["items"])


def test_build_local_resume_draft_keeps_existing_content():
    resume = get_default_resume_data()
    resume["basics"]["headline"] = "测试工程师"
    resume["modules"][1]["content"]["items"] = ["接口测试"]
    resume["modules"][5]["content"]["items"] = ["已有自我评价"]

    drafted = build_local_resume_draft(resume)

    assert drafted["modules"][1]["content"]["items"] == ["接口测试"]
    assert drafted["modules"][5]["content"]["items"] == ["已有自我评价"]


def test_get_default_modular_resume_data_contains_modules_and_style():
    data = get_default_modular_resume_data()

    assert "basics" in data
    assert "modules" in data
    assert "style" in data
    assert isinstance(data["modules"], list)
    assert len(data["modules"]) >= 6
    assert data["modules"][0]["title"] == "教育经历"
    assert "theme_color" in data["style"]


def test_migrate_legacy_resume_converts_fixed_sections_to_modules():
    legacy = {
        "basics": {"name": "张三"},
        "skills": [" Python ", "FastAPI", ""],
        "projects": [
            {
                "name": "智能简历生成器",
                "role": "开发者",
                "startDate": "2024.01",
                "endDate": "2024.03",
                "description": "负责核心开发",
                "highlights": ["独立完成"],
            }
        ],
    }

    migrated = migrate_legacy_resume(legacy)

    assert migrated["basics"]["name"] == "张三"
    assert "modules" in migrated
    assert len(migrated["modules"]) >= 6

    skills_module = next(module for module in migrated["modules"] if module["type"] == "skills")
    projects_module = next(module for module in migrated["modules"] if module["type"] == "projects")

    assert skills_module["content"]["items"] == ["Python", "FastAPI"]
    assert projects_module["content"]["items"][0]["name"] == "智能简历生成器"


def test_ensure_modular_resume_shape_keeps_existing_modules_and_fills_defaults():
    modular = {
        "basics": {"name": "李四"},
        "modules": [
            {
                "id": "custom_1",
                "title": "获奖经历",
                "type": "custom",
                "visible": True,
                "order": 9,
                "content": {"items": [{"title": "一等奖", "description": "全国竞赛"}]},
            }
        ],
        "style": {"theme_color": "#000000"},
    }

    normalized = ensure_modular_resume_shape(modular)

    assert normalized["basics"]["name"] == "李四"
    assert normalized["style"]["theme_color"] == "#000000"
    assert normalized["style"]["font_size"] == 14
    assert len(normalized["modules"]) == 1
    assert normalized["modules"][0]["title"] == "获奖经历"
    assert normalized["modules"][0]["type"] == "custom"


def test_save_resume_data_does_not_persist_legacy_top_level_sections(tmp_path):
    resume = get_default_resume_data()
    resume["modules"][1]["content"]["items"] = ["Python"]
    target = "data/parser_test_saved_resume_data.json"

    save_resume_data(resume, target)
    from pathlib import Path

    target_path = Path(target)
    try:
        saved = json.loads(target_path.read_text(encoding="utf-8"))
    finally:
        target_path.unlink(missing_ok=True)

    assert set(saved.keys()) == {"basics", "modules", "style"}
    assert "skills" not in saved
    skills_module = next(module for module in saved["modules"] if module["type"] == "skills")
    assert skills_module["content"]["items"] == ["Python"]


def test_resume_shape_sanitizes_photo_path_and_control_characters():
    shaped = ensure_resume_shape(
        {
            "basics": {
                "name": "Alice\x00<script>",
                "headline": "Backend",
                "photo_path": "../outside/secret.png",
            },
            "modules": [
                {
                    "id": "skills",
                    "title": "Skills",
                    "type": "skills",
                    "visible": True,
                    "order": 1,
                    "content": {"items": ["Python\x00", "'quoted skill\""]},
                }
            ],
        }
    )

    assert shaped["basics"]["name"] == "Alice<script>"
    assert shaped["basics"]["photo_path"] == ""
    assert shaped["modules"][0]["content"]["items"] == ["Python", "'quoted skill\""]


def test_save_resume_data_rejects_path_outside_workspace(tmp_path):
    with pytest.raises(ValueError):
        save_resume_data(get_default_resume_data(), tmp_path / "resume_data.json")
