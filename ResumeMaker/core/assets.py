import base64
import mimetypes
from pathlib import Path
from typing import Optional

from tools.permission import ensure_workspace_path


def get_photo_bytes(photo_path: str) -> Optional[bytes]:
    if not photo_path:
        return None
    try:
        path = ensure_workspace_path(photo_path)
        if path.exists() and path.is_file():
            return path.read_bytes()
    except (OSError, ValueError):
        return None
    return None


def get_photo_data_uri(photo_path: str) -> str:
    photo_bytes = get_photo_bytes(photo_path)
    if not photo_bytes:
        return ""

    mime_type, _ = mimetypes.guess_type(photo_path)
    if not mime_type:
        mime_type = "image/png"

    encoded = base64.b64encode(photo_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"
