from __future__ import annotations

import io

from PIL import Image

from core.data import get_default_resume_data
from renderers.html_renderer import build_full_preview_document, render_resume_preview_html
from renderers.markdown_renderer import render_resume_markdown
from renderers.pdf_renderer import (
    PLAYWRIGHT_SCREENSHOT_SCRIPT,
    _convert_png_to_pdf,
    build_pdf_html_document,
    build_pdf_html_document_from_resume_document,
    render_resume_document_pdf,
    render_resume_pdf,
)


def _sample_resume():
    resume = get_default_resume_data()
    resume["basics"].update(
        {
            "name": "Alice",
            "headline": "Backend Engineer",
            "city": "Shanghai",
            "email": "alice@example.com",
            "website": "https://alice.example.com",
            "portfolio": "https://portfolio.example.com/alice",
        }
    )
    resume["modules"] = [
        {
            "id": "skills_1",
            "title": "Skills",
            "type": "skills",
            "visible": True,
            "order": 1,
            "content": {"items": ["Python", "FastAPI"]},
        },
        {
            "id": "projects_1",
            "title": "Projects",
            "type": "projects",
            "visible": True,
            "order": 2,
            "content": {
                "items": [
                    {
                        "name": "Resume Maker",
                        "role": "Developer",
                        "startDate": "2026.01",
                        "endDate": "2026.03",
                        "description": "Built export pipeline.",
                        "highlights": ["HTML preview", "Markdown export"],
                    }
                ]
            },
        },
    ]
    return resume


def test_three_templates_render_distinct_html():
    resume = _sample_resume()
    rendered = {
        template: render_resume_preview_html(
            resume,
            style_params={"template": template, "show_photo": False},
        )
        for template in ["modern_blue", "elegant_gray", "emerald_pro"]
    }

    for template, html in rendered.items():
        assert f"template-{template}" in html
        assert "Alice" in html
        assert "Python" in html
        assert "https://alice.example.com" in html
        assert "https://portfolio.example.com/alice" in html

    assert len(set(rendered.values())) == 3


def test_full_preview_document_contains_expected_template_styles():
    html = build_full_preview_document(
        _sample_resume(),
        style_params={"template": "emerald_pro", "preview_scale": 90, "show_photo": False},
    )

    assert "<!DOCTYPE html>" in html
    assert "template-emerald_pro" in html
    assert "#059669" in html
    assert "transform: scale(0.9)" in html


def test_markdown_export_uses_visible_modules_in_order():
    resume = _sample_resume()
    resume["modules"].append(
        {
            "id": "hidden_1",
            "title": "Hidden",
            "type": "custom",
            "visible": False,
            "order": 0,
            "content": {"items": ["should not render"]},
        }
    )

    markdown = render_resume_markdown(resume)

    assert markdown.startswith("# Alice")
    assert "**Backend Engineer**" in markdown
    assert "https://alice.example.com" in markdown
    assert "https://portfolio.example.com/alice" in markdown
    assert "## Skills" in markdown
    assert "## Projects" in markdown
    assert markdown.index("## Skills") < markdown.index("## Projects")
    assert "should not render" not in markdown


def test_custom_module_renders_dynamic_field_boxes_above_description():
    resume = _sample_resume()
    resume["modules"].append(
        {
            "id": "custom_1",
            "title": "Additional",
            "type": "custom",
            "visible": True,
            "order": 3,
            "content": {
                "fields": [
                    {"label": "name", "value": "Competition"},
                    {"label": "role", "value": "Team lead"},
                    {"label": "time", "value": "2025.01 ~ 2025.03"},
                ],
                "description": "Built prototype.",
                "highlights": ["First prize"],
            },
        }
    )

    html = render_resume_preview_html(resume, style_params={"show_photo": False})
    markdown = render_resume_markdown(resume)

    assert "Competition" in html
    assert "Team lead" in html
    assert "2025.01 ~ 2025.03" in html
    assert "Built prototype." in html
    assert "First prize" in html
    assert "- Competition" in markdown
    assert "- Team lead" in markdown
    assert "- 2025.01 ~ 2025.03" in markdown
    assert "- Description: Built prototype." in markdown
    assert "- First prize" in markdown
    assert "General subfield" not in html
    assert "General subfield" not in markdown


def test_pdf_html_document_uses_preview_document():
    html = build_pdf_html_document(_sample_resume(), style_params={"template": "elegant_gray"})

    assert "<!DOCTYPE html>" in html
    assert "template-elegant_gray" in html
    assert "Alice" in html


def test_pdf_html_document_can_use_unified_resume_document():
    html = build_pdf_html_document_from_resume_document(
        {
            "resume": _sample_resume(),
            "style": {"template": "emerald_pro", "show_photo": False},
        }
    )

    assert "<!DOCTYPE html>" in html
    assert "template-emerald_pro" in html
    assert "Alice" in html


def test_pdf_html_document_ignores_preview_only_scale():
    html = build_pdf_html_document(
        _sample_resume(),
        style_params={"template": "modern_blue", "preview_scale": 70, "show_photo": False},
    )

    assert "template-modern_blue" in html
    assert "transform: scale(1.0)" in html
    assert "transform: scale(0.7)" not in html


def test_pdf_screenshot_targets_resume_page_only():
    assert 'locator(".resume-a4").screenshot' in PLAYWRIGHT_SCREENSHOT_SCRIPT
    assert "full_page=True" not in PLAYWRIGHT_SCREENSHOT_SCRIPT


def test_png_to_pdf_conversion_returns_pdf_bytes():
    image = Image.new("RGB", (20, 20), color=(255, 255, 255))
    png_buffer = io.BytesIO()
    image.save(png_buffer, format="PNG")

    pdf_bytes = _convert_png_to_pdf(png_buffer.getvalue())

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 100


def test_render_resume_pdf_can_use_generated_preview_png(monkeypatch):
    image = Image.new("RGB", (20, 20), color=(255, 255, 255))
    png_buffer = io.BytesIO()
    image.save(png_buffer, format="PNG")

    monkeypatch.setattr(
        "renderers.pdf_renderer._render_preview_png_via_subprocess",
        lambda html_document: png_buffer.getvalue(),
    )

    pdf_bytes = render_resume_pdf(_sample_resume(), style_params={"template": "modern_blue"})

    assert pdf_bytes.startswith(b"%PDF")


def test_render_resume_document_pdf_can_use_generated_preview_png(monkeypatch):
    image = Image.new("RGB", (20, 20), color=(255, 255, 255))
    png_buffer = io.BytesIO()
    image.save(png_buffer, format="PNG")

    monkeypatch.setattr(
        "renderers.pdf_renderer._render_preview_png_via_subprocess",
        lambda html_document: png_buffer.getvalue(),
    )

    pdf_bytes = render_resume_document_pdf(
        {
            "resume": _sample_resume(),
            "style": {"template": "modern_blue", "show_photo": False},
        }
    )

    assert pdf_bytes.startswith(b"%PDF")


def test_empty_minimal_resume_renders_preview_and_markdown_without_sections():
    resume = {"basics": {"name": "First User", "headline": "Intern"}, "modules": []}

    html = render_resume_preview_html(resume, style_params={"show_photo": False})
    markdown = render_resume_markdown(resume)

    assert "First User" in html
    assert "Intern" in html
    assert "resume-a4" in html
    assert markdown.startswith("# First User")
    assert "**Intern**" in markdown


def test_custom_general_fields_render_without_placeholder_labels_or_dropped_text():
    resume = {
        "basics": {"name": "Casey", "headline": "Product Analyst"},
        "modules": [
            {
                "id": "custom_1",
                "title": "Volunteer Work",
                "type": "custom",
                "visible": True,
                "order": 1,
                "content": {
                    "fields": [
                        {"label": "General field", "value": "Community dashboard"},
                        {"label": "", "value": "Data cleanup lead"},
                    ],
                    "description": "Kept weekly metrics readable for non-technical users.",
                    "highlights": ["Reduced manual reporting time"],
                },
            }
        ],
    }

    html = render_resume_preview_html(resume, style_params={"show_photo": False})
    markdown = render_resume_markdown(resume)

    for expected in [
        "Community dashboard",
        "Data cleanup lead",
        "Kept weekly metrics readable",
        "Reduced manual reporting time",
    ]:
        assert expected in html
        assert expected in markdown

    assert "General field" not in html
    assert "General field" not in markdown
