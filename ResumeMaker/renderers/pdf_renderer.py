from __future__ import annotations

import io
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

from PIL import Image

from core.data import ensure_resume_shape
from renderers.html_renderer import build_full_preview_document, build_style_params


PLAYWRIGHT_SCREENSHOT_SCRIPT = r"""
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

html_path = Path(sys.argv[1])
png_path = Path(sys.argv[2])

html_document = html_path.read_text(encoding="utf-8")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 2200}, device_scale_factor=2)
    page.set_content(html_document, wait_until="load")
    page.emulate_media(media="screen")
    page.locator(".resume-a4").screenshot(path=str(png_path))
    browser.close()
"""


def build_pdf_html_document(
    resume_data: Dict[str, Any], style_params: Dict[str, Any] | None = None
) -> str:
    normalized_data = ensure_resume_shape(resume_data)
    normalized_style = dict(style_params or {})
    normalized_style["preview_scale"] = 100

    style_config = build_style_params(normalized_style)
    return build_full_preview_document(normalized_data, style_params=style_config)


def build_pdf_html_document_from_resume_document(resume_document: Dict[str, Any]) -> str:
    resume_data = resume_document.get("resume", {})
    style_params = dict(resume_document.get("style", {}))
    return build_pdf_html_document(resume_data, style_params=style_params)


def _render_preview_png_via_subprocess(html_document: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="resume_pdf_") as temp_dir:
        temp_path = Path(temp_dir)
        html_path = temp_path / "resume_preview.html"
        png_path = temp_path / "resume_preview.png"

        html_path.write_text(html_document, encoding="utf-8")

        completed = subprocess.run(
            [sys.executable, "-c", PLAYWRIGHT_SCREENSHOT_SCRIPT, str(html_path), str(png_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            stderr_text = completed.stderr.strip()
            stdout_text = completed.stdout.strip()
            details = "\n".join(part for part in [stderr_text, stdout_text] if part)
            raise RuntimeError(f"Playwright preview screenshot failed.\n{details}")

        if not png_path.exists():
            raise RuntimeError("Playwright preview screenshot failed: output PNG was not created.")

        return png_path.read_bytes()


def _convert_png_to_pdf(png_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(png_bytes)) as image:
        rgb_image = image.convert("RGB")
        pdf_buffer = io.BytesIO()
        rgb_image.save(pdf_buffer, format="PDF", resolution=144.0)
        return pdf_buffer.getvalue()


def render_resume_pdf(resume_data: Dict[str, Any], style_params: Dict[str, Any] | None = None) -> bytes:
    html_document = build_pdf_html_document(resume_data, style_params=style_params)
    png_bytes = _render_preview_png_via_subprocess(html_document)
    return _convert_png_to_pdf(png_bytes)


def render_resume_document_pdf(resume_document: Dict[str, Any]) -> bytes:
    html_document = build_pdf_html_document_from_resume_document(resume_document)
    png_bytes = _render_preview_png_via_subprocess(html_document)
    return _convert_png_to_pdf(png_bytes)
