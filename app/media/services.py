from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, BinaryIO, cast

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.common.forms import optional_str
from app.common.ids import new_uuid_str
from app.config import Settings
from app.media.models import MediaAsset
from app.plants.models import Plant

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/svg+xml",
    "application/pdf",
}


class MediaError(ValueError):
    pass


def _media_root(settings: Settings) -> Path:
    return Path(settings.media_root).expanduser().resolve()


def plant_media_directory(settings: Settings, plant_id: str) -> Path:
    return _media_root(settings) / "plants" / plant_id / "originals"


def _safe_filename(filename: str | None, fallback: str = "upload") -> str:
    if not filename:
        return fallback
    name = Path(filename).name.strip()
    return name or fallback


def _file_object(upload: UploadFile | BinaryIO | Any) -> BinaryIO:
    file_obj = getattr(upload, "file", upload)
    if not hasattr(file_obj, "read"):
        raise MediaError("Upload must be a file-like object.")
    return cast(BinaryIO, file_obj)


def _content_type(upload: UploadFile | Any) -> str | None:
    return optional_str(getattr(upload, "content_type", None))


def store_upload(
    session: Session,
    settings: Settings,
    plant: Plant,
    upload: UploadFile | BinaryIO | Any,
    *,
    observation_id: str | None = None,
    view_type: str = "other",
    caption: str | None = None,
    captured_at: datetime | None = None,
    asset_metadata: Mapping[str, object] | None = None,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> MediaAsset:
    content_type = _content_type(upload)
    if content_type is not None and content_type not in ALLOWED_MEDIA_TYPES:
        raise MediaError(f"Unsupported media type: {content_type}")

    file_obj = _file_object(upload)
    original_name = _safe_filename(getattr(upload, "filename", None))
    suffix = Path(original_name).suffix.lower()
    suffix = suffix if suffix and len(suffix) <= 8 else ".bin"

    directory = plant_media_directory(settings, plant.id)
    directory.mkdir(parents=True, exist_ok=True)

    asset_id = new_uuid_str()
    target = directory / f"{asset_id}{suffix}"
    digest = sha256()
    total = 0
    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0)
        except Exception:  # pragma: no cover - defensive
            pass

    with target.open("wb") as destination:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                destination.close()
                target.unlink(missing_ok=True)
                raise MediaError("Upload exceeds maximum allowed size.")
            digest.update(chunk)
            destination.write(chunk)

    media_root = _media_root(settings)
    relative_path = target.relative_to(media_root).as_posix()
    asset = MediaAsset(
        id=asset_id,
        plant_id=plant.id,
        observation_id=observation_id,
        file_path=relative_path,
        original_filename=original_name,
        media_type=content_type or "application/octet-stream",
        captured_at=captured_at or datetime.now(UTC),
        view_type=view_type,
        caption=caption,
        checksum=digest.hexdigest(),
        width=None,
        height=None,
        asset_metadata=dict(asset_metadata or {}),
    )
    session.add(asset)
    session.flush()
    return asset


def media_path(settings: Settings, asset: MediaAsset) -> Path:
    return _media_root(settings) / asset.file_path
