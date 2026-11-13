from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_settings
from app.media.models import MediaAsset
from app.media.services import media_path

router = APIRouter()


@router.get("/media/assets/{asset_id}")
def media_asset_download(
    asset_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found.")
    path = media_path(settings, asset)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file missing.")
    return FileResponse(path, media_type=asset.media_type, filename=asset.original_filename)
