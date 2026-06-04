from __future__ import annotations

import os
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest

from ui.i18n import TEXT


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_E2E") != "1",
    reason="Set RUN_E2E=1 to run Streamlit browser interaction tests.",
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "resume_data.json"
CONFIG_FILE = PROJECT_ROOT / "config.json"
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

SAMPLE_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
    b"\x02\xfeA\xe2&\xb5\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, timeout_seconds: int = 30) -> None:
    from urllib.request import urlopen

    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Streamlit server did not become ready: {last_error}")


@pytest.fixture(autouse=True)
def restore_project_files() -> Iterator[None]:
    original_data = DATA_FILE.read_bytes() if DATA_FILE.exists() else None
    original_config = CONFIG_FILE.read_bytes() if CONFIG_FILE.exists() else None
    original_uploads = (
        {path.name: path.read_bytes() for path in UPLOAD_DIR.glob("*") if path.is_file()}
        if UPLOAD_DIR.exists()
        else {}
    )

    yield

    if original_data is None:
        DATA_FILE.unlink(missing_ok=True)
    else:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_bytes(original_data)

    if original_config is None:
        CONFIG_FILE.unlink(missing_ok=True)
    else:
        CONFIG_FILE.write_bytes(original_config)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for path in UPLOAD_DIR.glob("*"):
        if path.is_file() and path.name not in original_uploads:
            path.unlink()
    for name, content in original_uploads.items():
        (UPLOAD_DIR / name).write_bytes(content)


@pytest.fixture()
def streamlit_app_url():
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless=true",
            f"--server.port={port}",
            "--browser.gatherUsageStats=false",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        _wait_for_server(url)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture()
def browser_page(streamlit_app_url):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        pytest.skip(f"Playwright is not installed: {exc}")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.goto(streamlit_app_url, wait_until="load")
            yield page
            browser.close()
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Playwright browser is not installed. Run: python -m playwright install chromium")
        raise


def _fill_minimum_resume_info(page) -> None:
    page.get_by_label("姓名").fill("自动化测试候选人")
    page.get_by_label("姓名").press("Tab")
    page.get_by_label("应聘岗位 / 职位标题").fill("后端开发实习生")
    page.get_by_label("应聘岗位 / 职位标题").press("Tab")


def _expand_latest_generic_module(page) -> None:
    page.get_by_text(TEXT["zh"]["module.details"]).last.click()


def _module_count_from_json() -> int:
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return len(json.load(file).get("modules", []))


def _wait_for_module_count(expected_count: int, timeout_ms: int = 10_000) -> None:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if DATA_FILE.exists() and _module_count_from_json() == expected_count:
            return
        time.sleep(0.25)
    raise AssertionError(f"Expected {expected_count} modules in {DATA_FILE}")


def _text_exists_in_any_frame(page, text: str) -> bool:
    for frame in page.frames:
        try:
            if frame.get_by_text(text).count() > 0:
                return True
            if text in frame.content():
                return True
        except Exception:
            continue
    return False


def _wait_for_text_in_any_frame(page, text: str, timeout_ms: int = 10_000) -> None:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if _text_exists_in_any_frame(page, text):
            return
        page.wait_for_timeout(250)
    raise AssertionError(f"Text was not found in any page frame: {text}")


def test_manual_resume_edit_updates_preview(browser_page):
    candidate_name = "自动化测试候选人"
    headline = "后端开发实习生"

    browser_page.get_by_label("姓名").fill(candidate_name)
    browser_page.get_by_label("姓名").press("Tab")
    browser_page.get_by_label("应聘岗位 / 职位标题").fill(headline)
    browser_page.get_by_label("应聘岗位 / 职位标题").press("Tab")
    browser_page.get_by_role("button", name="保存当前内容").click()

    assert browser_page.get_by_label("姓名").input_value() == candidate_name
    assert browser_page.get_by_label("应聘岗位 / 职位标题").input_value() == headline
    _wait_for_text_in_any_frame(browser_page, candidate_name)
    _wait_for_text_in_any_frame(browser_page, headline)


def test_add_and_delete_custom_module(browser_page):
    module_title = "E2E Custom Module"
    module_content = "E2E custom module content"

    before_count = _module_count_from_json()
    browser_page.get_by_role("button", name=TEXT["zh"]["module.add"]).click()
    _wait_for_module_count(before_count + 1)

    browser_page.get_by_label(TEXT["zh"]["module.title"]).last.fill(module_title)
    browser_page.get_by_label(TEXT["zh"]["module.title"]).last.press("Tab")
    _expand_latest_generic_module(browser_page)
    visible_custom_field = browser_page.locator(
        f"input[aria-label='{TEXT['zh']['custom.general_subfield']}']:visible"
    ).last
    visible_custom_field.fill(module_content)
    visible_custom_field.press("Tab")
    browser_page.get_by_role("button", name=TEXT["zh"]["sidebar.save"]).click()

    assert _module_count_from_json() == before_count + 1
    _wait_for_text_in_any_frame(browser_page, module_title)
    _wait_for_text_in_any_frame(browser_page, module_content)

    browser_page.get_by_text(TEXT["zh"]["module.details"]).last.click()
    browser_page.get_by_role("button", name=TEXT["zh"]["module.delete"]).last.click()
    _wait_for_module_count(before_count)


def test_style_controls_can_be_changed(browser_page):
    browser_page.get_by_label("模板主题").click()
    browser_page.get_by_text("雅致灰").click()

    assert browser_page.get_by_text("雅致灰").count() > 0


def test_jd_input_and_agent_generation_button(browser_page):
    _fill_minimum_resume_info(browser_page)
    browser_page.get_by_label("粘贴岗位描述文本").fill(
        "招聘 Python 后端开发实习生，熟悉接口设计、数据库和日志排查。"
    )
    browser_page.get_by_role("button", name="✨ 智能生成简历").click()
    assert browser_page.get_by_text("智能生成完成").wait_for(timeout=30_000) is None


def test_markdown_download_button_exists(browser_page):
    download_button = browser_page.get_by_role("button", name="下载 Markdown")
    download_button.wait_for(timeout=10_000)
    assert download_button.is_enabled()


def test_pdf_generation_is_explicit_and_page_stays_responsive(browser_page):
    browser_page.get_by_text("PDF 只会在点击“生成 PDF”后创建").wait_for(timeout=10_000)
    generate_button = browser_page.get_by_role("button", name="生成 PDF")
    generate_button.wait_for(timeout=10_000)
    assert generate_button.is_enabled()

    browser_page.get_by_label("姓名").fill("PDF 不阻塞测试")
    generate_button.click()
    browser_page.get_by_role("button", name="📥 下载 PDF 简历").wait_for(timeout=30_000)


def test_upload_photo_shows_preview(browser_page, tmp_path):
    image_path = tmp_path / "avatar.png"
    image_path.write_bytes(SAMPLE_PNG_BYTES)

    browser_page.locator("section[data-testid='stFileUploaderDropzone'] input[type='file']").first.set_input_files(
        str(image_path)
    )
    browser_page.get_by_text("当前照片预览").wait_for(timeout=10_000)
    assert browser_page.get_by_role("img").count() > 0
