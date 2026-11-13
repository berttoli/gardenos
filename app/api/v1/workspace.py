from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.access.dependencies import require_permission
from app.access.services import PrincipalContext
from app.dependencies import get_db
from app.workspace.services import build_workspace_payload

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("")
def workspace_bootstrap(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("access.read")),
    location_id: str | None = Query(default=None, min_length=1),
) -> JSONResponse:
    payload = build_workspace_payload(
        db,
        current_principal,
        selected_location_id=location_id,
    )
    return JSONResponse(payload)
