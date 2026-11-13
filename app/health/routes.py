from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.database import check_database_ready
from app.dependencies import get_session_factory

router = APIRouter()


@router.get("/health/live")
def health_live() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.get("/health/ready")
def health_ready(request: Request) -> JSONResponse:
    session_factory = get_session_factory(request)
    if not check_database_ready(session_factory):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not ready.",
        )
    return JSONResponse({"status": "ready"})
