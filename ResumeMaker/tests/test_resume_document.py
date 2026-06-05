from core.resume_document import create_resume_document, get_resume_document, notify_document_changed, sync_session_aliases
from core.document_commands import save_document_snapshot


def test_document_observer_updates_preview_and_exports():
    session_state = {
        "resume_data": {
            "basics": {"name": "Alice", "headline": "Engineer"},
            "modules": [],
            "style": {},
        },
        "style_params": {"template": "modern_blue", "show_photo": False},
        "jd_input": "Python backend",
        "uploaded_files_meta": [{"name": "a.md", "type": "readme"}],
    }

    session_state["resume_document"] = create_resume_document(
        session_state["resume_data"],
        session_state["style_params"],
        session_state["jd_input"],
        session_state["uploaded_files_meta"],
    )

    notify_document_changed(session_state, "change")
    document = get_resume_document(session_state)

    assert document["resume"]["basics"]["name"] == "Alice"
    assert document["inputs"]["jd_text"] == "Python backend"
    assert document["runtime"]["preview_version"] == 1
    assert "Alice" in document["runtime"]["preview_html"]
    assert document["runtime"]["conditional_suggestions"] == []
    assert "# Alice" in document["exports"]["markdown"]


def test_document_observer_skips_duplicate_updates():
    session_state = {
        "resume_data": {
            "basics": {"name": "Alice", "headline": "Engineer"},
            "modules": [],
            "style": {},
        },
        "style_params": {"template": "modern_blue", "show_photo": False},
        "jd_input": "",
        "uploaded_files_meta": [],
    }

    session_state["resume_document"] = create_resume_document(
        session_state["resume_data"],
        session_state["style_params"],
    )

    notify_document_changed(session_state, "change")
    first_version = get_resume_document(session_state)["runtime"]["preview_version"]
    notify_document_changed(session_state, "change")
    second_version = get_resume_document(session_state)["runtime"]["preview_version"]

    assert first_version == 1
    assert second_version == 1


def test_document_observer_reuses_preview_html_for_duplicate_updates():
    session_state = {
        "resume_data": {
            "basics": {"name": "Alice", "headline": "Engineer"},
            "modules": [],
            "style": {},
        },
        "style_params": {"template": "modern_blue", "show_photo": False},
        "jd_input": "",
        "uploaded_files_meta": [],
    }

    session_state["resume_document"] = create_resume_document(
        session_state["resume_data"],
        session_state["style_params"],
    )

    notify_document_changed(session_state, "change")
    first_html = get_resume_document(session_state)["runtime"]["preview_html"]
    notify_document_changed(session_state, "change")
    second_html = get_resume_document(session_state)["runtime"]["preview_html"]

    assert first_html
    assert first_html == second_html


def test_sync_session_aliases_does_not_clear_existing_jd_widget_value():
    session_state = {
        "resume_data": {
            "basics": {"name": "Alice", "headline": "Engineer"},
            "modules": [],
            "style": {},
        },
        "style_params": {},
        "jd_input": "fresh user typed JD",
        "uploaded_files_meta": [],
    }
    session_state["resume_document"] = create_resume_document(
        session_state["resume_data"],
        session_state["style_params"],
        jd_text="",
    )

    sync_session_aliases(session_state, include_widget_keys=True)

    assert session_state["jd_input"] == "fresh user typed JD"


def test_document_snapshot_preserves_input_context():
    document = create_resume_document(
        {
            "basics": {"name": "Alice", "headline": "Math tutor"},
            "modules": [],
            "style": {},
        },
        {},
        jd_text="家长需要看教学能力和考试成绩",
        uploaded_files=[{"name": "grades.md", "type": "readme", "raw_text": "数学成绩优秀"}],
    )

    snapshot = save_document_snapshot(document)

    assert snapshot["inputs"]["jd_text"] == "家长需要看教学能力和考试成绩"
    assert snapshot["inputs"]["uploaded_files"][0]["raw_text"] == "数学成绩优秀"
