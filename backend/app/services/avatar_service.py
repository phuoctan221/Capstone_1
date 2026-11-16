"""Safe local avatar storage for the self-hosted deployment."""
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import BASE_DIR, settings

AVATAR_DIR = BASE_DIR / "uploads" / "avatars"
_ALLOWED = {
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/webp": (b"RIFF", ".webp"),
}


def _matches_image(content: bytes, content_type: str) -> bool:
    signature, extension = _ALLOWED[content_type]
    if not content.startswith(signature):
        return False
    return content_type != "image/webp" or content[8:12] == b"WEBP"


async def save_avatar(upload: UploadFile) -> str:
    content_type = (upload.content_type or "").split(";", 1)[0].lower()
    if content_type not in _ALLOWED:
        raise HTTPException(415, "Chỉ hỗ trợ ảnh PNG, JPG hoặc WebP.")

    content = await upload.read(settings.AVATAR_MAX_BYTES + 1)
    if len(content) > settings.AVATAR_MAX_BYTES:
        raise HTTPException(413, "Ảnh đại diện không được lớn hơn 2 MB.")
    if not content or not _matches_image(content, content_type):
        raise HTTPException(422, "Tệp tải lên không phải ảnh hợp lệ.")

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    _, extension = _ALLOWED[content_type]
    filename = f"{uuid4().hex}{extension}"
    target = AVATAR_DIR / filename
    target.write_bytes(content)
    await upload.close()
    return f"/api/uploads/avatars/{filename}"


def delete_avatar(avatar_url: str | None) -> None:
    if not avatar_url or not avatar_url.startswith("/api/uploads/avatars/"):
        return
    filename = Path(avatar_url).name
    target = AVATAR_DIR / filename
    if target.parent == AVATAR_DIR and target.exists():
        target.unlink()