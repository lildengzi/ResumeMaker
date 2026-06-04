import app
from app import build_optimization_signature, is_duplicate_optimization_request


def test_optimization_signature_is_stable_for_equivalent_inputs():
    resume = {"basics": {"name": "Alice", "headline": "Backend"}, "modules": []}
    files = [
        {
            "type": "existing_resume",
            "name": "resume.pdf",
            "path": "data/uploads/resume.pdf",
            "size_bytes": 128,
            "raw_text": "Python backend",
            "parse_status": "parsed",
            "notes": ["ignored for signature"],
        }
    ]

    first = build_optimization_signature(resume, "Need Python", files, {"template": "modern_blue"})
    second = build_optimization_signature(resume, "Need Python", files, {"template": "modern_blue"})

    assert first == second


def test_optimization_signature_changes_when_user_inputs_change():
    resume = {"basics": {"name": "Alice", "headline": "Backend"}, "modules": []}
    original = build_optimization_signature(resume, "Need Python", [], {"template": "modern_blue"})
    changed_jd = build_optimization_signature(resume, "Need FastAPI", [], {"template": "modern_blue"})
    changed_resume = build_optimization_signature(
        {"basics": {"name": "Alice", "headline": "Frontend"}, "modules": []},
        "Need Python",
        [],
        {"template": "modern_blue"},
    )
    changed_upload = build_optimization_signature(
        resume,
        "Need Python",
        [{"type": "existing_resume", "name": "resume.pdf", "raw_text": "new text"}],
        {"template": "modern_blue"},
    )

    assert changed_jd != original
    assert changed_resume != original
    assert changed_upload != original


def test_duplicate_optimization_request_requires_completed_matching_signature():
    signature = build_optimization_signature({"basics": {}}, "", [], {})

    assert is_duplicate_optimization_request(signature, signature) is True
    assert is_duplicate_optimization_request("", signature) is False
    assert is_duplicate_optimization_request(signature, signature, ai_is_running=True) is False
    assert is_duplicate_optimization_request(signature, signature + "x") is False


def test_editor_key_changes_when_editor_version_changes(monkeypatch):
    state = {"editor_version": 0}
    monkeypatch.setattr(app.st, "session_state", state)

    first_key = app.editor_key("basics_name")
    app.bump_editor_version()
    second_key = app.editor_key("basics_name")

    assert first_key == "v0_basics_name"
    assert second_key == "v1_basics_name"
