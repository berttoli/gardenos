from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.v1.common import commit_session, json_value, request_payload
from app.auth.models import User
from app.common.forms import optional_str
from app.config import Settings
from app.dependencies import get_current_user, get_db, get_settings
from app.onboarding.models import OnboardingDraft
from app.onboarding.services import (
    OnboardingError,
    abandon_draft,
    complete_onboarding,
    create_draft,
    get_draft,
    save_step,
    store_draft_media,
)
from app.plants.services import plant_summary

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_json_value = json_value


def _serialize_draft(draft: OnboardingDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "draft_token": draft.draft_token,
        "plant_id": draft.plant_id,
        "current_step": draft.current_step,
        "state": _json_value(draft.state),
        "completed_at": draft.completed_at.isoformat() if draft.completed_at else None,
        "abandoned_at": draft.abandoned_at.isoformat() if draft.abandoned_at else None,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
    }


def _serialize_planted_summary(plant: Any) -> dict[str, Any]:
    summary = plant_summary(plant)
    return {
        "id": summary["id"],
        "display_id": summary["display_id"],
        "status": summary["status"],
        "scientific_name": summary["scientific_name"],
        "common_name": summary["common_name"],
        "current_location": summary["current_location"],
        "container": summary["container"],
    }


@router.post("/drafts", status_code=status.HTTP_201_CREATED)
def onboarding_create_draft(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    draft = create_draft(db)
    commit_session(db)
    return JSONResponse(_serialize_draft(draft), status_code=status.HTTP_201_CREATED)


@router.get("/drafts/{draft_token}")
def onboarding_get_draft(
    draft_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    draft = get_draft(db, draft_token)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding draft not found."
        )
    return JSONResponse(_serialize_draft(draft))


@router.patch("/drafts/{draft_token}/steps/{step}")
async def onboarding_save_step(
    draft_token: str,
    step: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    draft = get_draft(db, draft_token)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding draft not found."
        )
    payload = await request_payload(request)
    save_step(db, draft, step, payload)
    commit_session(db)
    return JSONResponse(_serialize_draft(draft))


@router.post("/drafts/{draft_token}/media", status_code=status.HTTP_201_CREATED)
async def onboarding_upload_media(
    draft_token: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    draft = get_draft(db, draft_token)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding draft not found."
        )
    form = await request.form()
    upload = form.get("file")
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A media file is required."
        )
    try:
        metadata = store_draft_media(
            db,
            settings,
            draft,
            upload,
            view_type=optional_str(form.get("view_type")) or "whole_plant",
            caption=optional_str(form.get("caption")),
        )
    except OnboardingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    commit_session(db)
    return JSONResponse(json_value(metadata), status_code=status.HTTP_201_CREATED)


@router.post("/drafts/{draft_token}/complete", status_code=status.HTTP_201_CREATED)
def onboarding_complete(
    draft_token: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    draft = get_draft(db, draft_token)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding draft not found."
        )
    plant = complete_onboarding(db, settings, draft)
    commit_session(db)
    return JSONResponse(
        {
            "draft": _serialize_draft(draft),
            "plant": _serialize_planted_summary(plant),
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/drafts/{draft_token}/abandon")
def onboarding_abandon(
    draft_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    draft = get_draft(db, draft_token)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding draft not found."
        )
    abandon_draft(db, draft)
    commit_session(db)
    return JSONResponse(_serialize_draft(draft))
