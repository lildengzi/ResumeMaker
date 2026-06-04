from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import BinaryIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class WebFetchResult:
    text: str
    ok: bool
    message: str = ""
    final_url: str = ""


class _SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._ignored_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = tag.lower()
        if normalized in {"script", "style", "noscript", "svg"}:
            self._ignored_stack.append(normalized)
        elif normalized in {"p", "br", "li", "div", "section", "article", "tr", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if self._ignored_stack and self._ignored_stack[-1] == normalized:
            self._ignored_stack.pop()
        elif normalized in {"p", "li", "div", "section", "article", "tr", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_stack:
            return
        text = unescape(data).strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        lines = []
        current = []
        for chunk in self._chunks:
            if chunk == "\n":
                if current:
                    lines.append(" ".join(current))
                    current = []
            else:
                current.append(" ".join(chunk.split()))
        if current:
            lines.append(" ".join(current))
        return "\n".join(line for line in lines if line).strip()


def _validate_url(url: str) -> str | None:
    if not url or not url.strip():
        return "Enter a URL before fetching."

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return "Only http and https URLs are supported."
    if not parsed.netloc:
        return "Enter a complete URL with a hostname."
    return None


def _read_limited(response: BinaryIO, max_bytes: int) -> tuple[bytes, bool]:
    data = response.read(max_bytes + 1)
    return data[:max_bytes], len(data) > max_bytes


def _decode_response(data: bytes, content_type: str) -> str:
    charset = "utf-8"
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            charset = part.split("=", 1)[1].strip() or charset
            break
    return data.decode(charset, errors="replace")


def _html_to_text(html: str) -> str:
    extractor = _SimpleHTMLTextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.get_text()


def fetch_jd_from_url(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> WebFetchResult:
    """Fetch a JD webpage and return plain text without raising UI-breaking errors."""
    validation_error = _validate_url(url)
    if validation_error:
        return WebFetchResult("", False, validation_error)

    normalized_url = url.strip()
    request = Request(
        normalized_url,
        headers={
            "User-Agent": "ResumeMaker/1.0 (+https://local-resume-maker)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            if content_type and "text/" not in content_type and "html" not in content_type:
                return WebFetchResult("", False, f"Unsupported content type: {content_type}")

            body, truncated = _read_limited(response, max_bytes)
            html = _decode_response(body, content_type)
            text = _html_to_text(html) if "html" in content_type.lower() or "<" in html else html.strip()
            if not text:
                return WebFetchResult("", False, "The page was fetched, but no readable text was found.")

            message = "Fetched JD text."
            if truncated:
                message = f"{message} Result was limited to {max_bytes} bytes."
            return WebFetchResult(text, True, message, response.geturl())
    except HTTPError as exc:
        return WebFetchResult("", False, f"HTTP error {exc.code}: {exc.reason}")
    except URLError as exc:
        return WebFetchResult("", False, f"Could not fetch URL: {exc.reason}")
    except TimeoutError:
        return WebFetchResult("", False, "The request timed out.")
    except Exception as exc:
        return WebFetchResult("", False, f"Could not fetch URL: {exc}")


def fetch_webpage_text(url: str) -> str:
    """Backward-compatible text-only webpage fetch API."""
    return fetch_jd_from_url(url).text

