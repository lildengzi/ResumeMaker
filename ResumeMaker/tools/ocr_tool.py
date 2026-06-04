from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Optional


@dataclass(frozen=True)
class OCRResult:
    text: str
    ok: bool
    message: str = ""


def extract_jd_text_from_image(image_bytes: bytes) -> OCRResult:
    """Extract JD text from an image if optional OCR packages are installed."""
    if not image_bytes:
        return OCRResult("", False, "No image data was provided.")

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        return OCRResult(
            "",
            False,
            "Pillow is required to read images before OCR. Install project requirements and try again.",
        )

    try:
        import pytesseract
    except ImportError:
        return OCRResult(
            "",
            False,
            "OCR engine is not installed. Install pytesseract and Tesseract, or paste the JD text manually.",
        )

    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return OCRResult("", False, "The uploaded file is not a readable image.")

    try:
        text = pytesseract.image_to_string(image).strip()
    except Exception as exc:
        return OCRResult("", False, f"OCR failed: {exc}")

    if not text:
        return OCRResult("", False, "OCR completed but did not find readable text.")

    return OCRResult(text, True, "OCR text extracted.")


def ocr_extract_text(image_bytes: bytes) -> str:
    """Backward-compatible text-only OCR API."""
    return extract_jd_text_from_image(image_bytes).text

