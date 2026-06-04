from core import get_default_resume_data
from renderers.html_renderer import build_style_params, render_resume_preview_html


def test_build_style_params_merges_template_and_custom_values():
    params = build_style_params(
        {
            "template": "emerald_pro",
            "body_font_size": 15,
            "font_size": 15,
            "page_margin": 40,
            "line_height": 1.8,
            "dense_mode": True,
            "show_photo": False,
        }
    )

    assert params["template"] == "emerald_pro"
    assert params["template_label"] == "翡翠专业"
    assert params["body_font_size"] == 15
    assert params["page_margin"] == 40
    assert params["line_height"] == 1.8
    assert params["show_photo"] is False
    assert params["content_gap"] == 14
    assert params["section_gap"] == 16
    assert params["item_gap"] == 8


def test_build_style_params_falls_back_to_default_template():
    params = build_style_params({"template": "unknown_template"})

    assert params["template"] == "unknown_template"
    assert params["template_label"] == "现代蓝"
    assert "font_family" in params
    assert "accent_color" in params


def test_render_resume_preview_html_renders_basic_content():
    resume = get_default_resume_data()
    resume["basics"]["name"] = "张三"
    resume["basics"]["headline"] = "Python 后端开发"
    skills_module = next(module for module in resume["modules"] if module["type"] == "skills")
    skills_module["content"]["items"] = ["Python", "FastAPI"]

    html = render_resume_preview_html(resume, style_params={"show_photo": False})

    assert "张三" in html
    assert "Python 后端开发" in html
    assert "Python" in html
    assert "FastAPI" in html
    assert "resume-avatar" not in html


def test_experience_preview_does_not_render_timeline_dot():
    resume = get_default_resume_data()
    project_module = next(module for module in resume["modules"] if module["type"] == "projects")
    project_module["content"]["items"] = [
        {
            "name": "ResumeMaker",
            "role": "Developer",
            "startDate": "2025.01",
            "endDate": "2025.03",
            "description": "Built preview.",
            "highlights": ["No marker detail."],
        }
    ]

    html = render_resume_preview_html(resume, style_params={"show_photo": False})

    assert "timeline-dot" not in html
    assert '<ul class="item-list">' not in html
    assert '<div class="detail-lines">' in html
    assert "ResumeMaker · Developer" not in html
    assert "ResumeMaker ｜ Developer" in html


def test_self_evaluation_renders_as_paragraphs_without_list_markers():
    resume = get_default_resume_data()
    self_eval_module = next(module for module in resume["modules"] if module["type"] == "selfEvaluation")
    self_eval_module["content"]["items"] = ["Harness Engineering方法。", "抗压能力强。"]

    html = render_resume_preview_html(resume, style_params={"show_photo": False})

    assert '<div class="prose-block">' in html
    assert '<div class="detail-line">Harness Engineering方法。</div>' in html
    assert "prose-list" not in html
