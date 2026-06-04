from __future__ import annotations

from io import BytesIO

from PIL import Image

from tools.ocr_tool import extract_jd_text_from_image
from tools.web_tool import _html_to_text, _read_limited, fetch_jd_from_url
from ui import sidebar


def test_fetch_jd_from_url_rejects_invalid_url_without_crashing():
    result = fetch_jd_from_url("ftp://example.com/job")

    assert not result.ok
    assert result.text == ""
    assert "http" in result.message


def test_html_to_text_strips_scripts_and_keeps_readable_content():
    html = """
    <html><head><style>.x{}</style><script>alert(1)</script></head>
    <body><h1>Senior Python Engineer</h1><p>Build APIs</p><li>Redis</li></body></html>
    """

    text = _html_to_text(html)

    assert "Senior Python Engineer" in text
    assert "Build APIs" in text
    assert "Redis" in text
    assert "alert" not in text
    assert ".x" not in text


def test_read_limited_reports_truncation():
    data, truncated = _read_limited(BytesIO(b"abcdef"), 3)

    assert data == b"abc"
    assert truncated is True


def test_ocr_empty_image_bytes_returns_clear_failure():
    result = extract_jd_text_from_image(b"")

    assert not result.ok
    assert result.text == ""
    assert result.message


def test_ocr_unavailable_or_empty_result_does_not_raise():
    image = Image.new("RGB", (20, 20), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    result = extract_jd_text_from_image(buffer.getvalue())

    assert isinstance(result.text, str)
    assert isinstance(result.message, str)


def test_sidebar_url_helper_preserves_existing_text_on_fetch_failure():
    text, message, ok = sidebar._apply_jd_url_fetch("not-a-url", "manual JD")

    assert text == "manual JD"
    assert not ok
    assert message


def test_sidebar_ocr_helper_preserves_existing_text_on_ocr_failure():
    text, message, ok = sidebar._apply_jd_ocr_result(b"", "manual OCR text")

    assert text == "manual OCR text"
    assert not ok
    assert message

