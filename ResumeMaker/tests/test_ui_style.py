from app import get_ui_style_css


def test_app_ui_style_keeps_streamlit_theme_control_for_inputs():
    css = get_ui_style_css()
    declarations = [part.strip() for part in css.split(";")]

    assert "stTextInput" not in css
    assert "stTextArea" not in css
    assert "input" not in css.lower()
    assert "textarea" not in css.lower()
    assert "background:" not in css
    assert "color:" not in declarations
    assert "var(--border-color)" in css


def test_app_ui_style_does_not_hide_or_disable_user_inputs():
    css = get_ui_style_css().lower()

    forbidden_snippets = [
        "display: none",
        "visibility: hidden",
        "opacity: 0",
        "pointer-events: none",
        "height: 0",
        "width: 0",
        "overflow: hidden",
    ]

    for snippet in forbidden_snippets:
        assert snippet not in css
