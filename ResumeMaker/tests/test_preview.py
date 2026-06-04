from ui.preview import _format_workflow_log_details, _format_workflow_log_message, render_conditional_suggestions_html


class FakeSessionState(dict):
    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value


def test_render_conditional_suggestions_html_uses_plain_numbered_rows_and_escapes_text():
    html = render_conditional_suggestions_html(["补充 QPS 指标", "<script>alert(1)</script>"])

    assert "条件补充建议" in html
    assert "suggestion-index" not in html
    assert "<ul" not in html
    assert "<li" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_render_conditional_suggestions_html_omits_empty_content():
    assert render_conditional_suggestions_html(["", "   "]) == ""


def test_workflow_log_message_uses_current_language(monkeypatch):
    state = FakeSessionState({"ui_language": "zh"})
    monkeypatch.setattr("ui.i18n.st.session_state", state)

    log = {
        "agent": "resume_writer",
        "message_key": "workflow.log.resume_writer",
        "message": "fallback",
    }

    assert "STAR 法则" in _format_workflow_log_message(log)
    state["ui_language"] = "en"
    assert "STAR method" in _format_workflow_log_message(log)


def test_workflow_log_message_falls_back_to_legacy_message():
    assert _format_workflow_log_message({"message": "legacy log"}) == "legacy log"


def test_workflow_log_details_normalizes_strings_and_lists():
    assert _format_workflow_log_details({"details": "missing api key"}) == ["missing api key"]
    timeout_details = _format_workflow_log_details({"details": ["", "network timeout"]})
    assert timeout_details[0] == "network timeout"
    assert "LLM_TIMEOUT" in timeout_details[1]
