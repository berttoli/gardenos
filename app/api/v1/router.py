from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.access.dependencies import require_permission
from app.access.services import PrincipalContext
from app.api.v1.access import router as access_router
from app.api.v1.auth import router as auth_router
from app.api.v1.common import json_value, request_payload
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.platform import router as platform_router
from app.api.v1.workspace import router as workspace_router
from app.auth.models import User
from app.care.access import task_is_visible, task_snapshot
from app.care.models import TaskOccurrence
from app.care.serialization import serialize_task_occurrence
from app.care.services import complete_task_occurrence
from app.common.forms import optional_str, parse_bool, parse_int
from app.communication.models import Conversation, Message
from app.communication.services import (
    append_message,
    create_conversation,
    get_conversation_bundle,
    list_conversations,
)
from app.dependencies import get_current_user, get_db
from app.labels.services import default_label_template, label_pdf_data, label_preview_data
from app.media.models import MediaAsset
from app.media.services import MediaError, store_upload
from app.observations.models import Measurement, Observation, Treatment
from app.observations.services import (
    create_observation,
    health_trends,
    record_measurement,
    record_treatment,
)
from app.plants.models import Plant
from app.plants.services import (
    build_plant_timeline,
    create_plant,
    get_plant,
    latest_health_score,
    list_plants,
    move_plant,
    plant_summary,
    update_plant,
)
from app.platform.scope_access import resolve_visible_scope_ids
from app.propagation.models import PropagationEvent
from app.propagation.services import (
    complete_propagation,
    fail_propagation,
    lineage_summary,
    start_propagation,
)

router = APIRouter(prefix="/api/v1", tags=["v1"])
router.include_router(access_router)
router.include_router(auth_router)
router.include_router(onboarding_router)
router.include_router(platform_router)
router.include_router(workspace_router)

_json_value = json_value
_request_payload = request_payload


def _serialize_plant(plant: Plant, db: Session) -> dict[str, Any]:
    return {
        **plant_summary(plant),
        "accession_date": plant.accession_date.isoformat() if plant.accession_date else None,
        "purchase_price": float(plant.purchase_price) if plant.purchase_price is not None else None,
        "taxon": {
            "id": plant.taxon.id,
            "scientific_name": plant.taxon.scientific_name,
            "common_names": plant.taxon.common_names,
            "display_code": plant.taxon.display_code,
        }
        if plant.taxon
        else None,
        "care_profile": {
            "id": plant.care_profile.id,
            "name": plant.care_profile.name,
        }
        if plant.care_profile
        else None,
        "timeline": _json_value(build_plant_timeline(db, plant)),
        "trends": _json_value(health_trends(db, plant.id)),
        "lineage": _json_value(lineage_summary(db, plant)),
        "latest_health_score": latest_health_score(plant),
    }


def _serialize_observation(observation: Observation) -> dict[str, Any]:
    return {
        "id": observation.id,
        "plant_id": observation.plant_id,
        "observed_at": observation.observed_at.isoformat(),
        "observation_type": observation.observation_type,
        "summary": observation.summary,
        "notes": observation.notes,
        "overall_health_score": float(observation.overall_health_score)
        if observation.overall_health_score is not None
        else None,
    }


def _serialize_measurement(measurement: Measurement) -> dict[str, Any]:
    return {
        "id": measurement.id,
        "plant_id": measurement.plant_id,
        "measured_at": measurement.measured_at.isoformat(),
        "height": float(measurement.height) if measurement.height is not None else None,
        "canopy_width": float(measurement.canopy_width)
        if measurement.canopy_width is not None
        else None,
        "trunk_diameter": float(measurement.trunk_diameter)
        if measurement.trunk_diameter is not None
        else None,
        "soil_moisture": float(measurement.soil_moisture)
        if measurement.soil_moisture is not None
        else None,
        "notes": measurement.notes,
    }


def _serialize_treatment(treatment: Treatment) -> dict[str, Any]:
    return {
        "id": treatment.id,
        "plant_id": treatment.plant_id,
        "observation_id": treatment.observation_id,
        "treatment_type": treatment.treatment_type,
        "product_name": treatment.product_name,
        "applied_at": treatment.applied_at.isoformat(),
        "result": treatment.result,
    }


def _serialize_media(asset: MediaAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "plant_id": asset.plant_id,
        "observation_id": asset.observation_id,
        "file_path": asset.file_path,
        "original_filename": asset.original_filename,
        "media_type": asset.media_type,
        "captured_at": asset.captured_at.isoformat() if asset.captured_at else None,
        "view_type": asset.view_type,
        "caption": asset.caption,
        "checksum": asset.checksum,
        "download_url": f"/media/assets/{asset.id}",
    }


def _serialize_task(occurrence: TaskOccurrence, db: Session) -> dict[str, Any]:
    return serialize_task_occurrence(occurrence, db)


def _serialize_conversation_summary(
    conversation: Conversation,
    *,
    message_count: int,
    last_message_at: datetime | None,
) -> dict[str, Any]:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "description": conversation.description,
        "created_by_user_id": conversation.created_by_user_id,
        "message_count": message_count,
        "last_message_at": last_message_at.isoformat() if last_message_at is not None else None,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


def _serialize_message(message: Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "author_user_id": message.author_user_id,
        "role": message.role,
        "content": message.content,
        "metadata": _json_value(message.metadata_json),
        "created_at": message.created_at.isoformat(),
        "updated_at": message.updated_at.isoformat(),
    }


def _serialize_conversation_detail(
    conversation: Conversation,
    messages: list[Message],
) -> dict[str, Any]:
    last_message_at = messages[-1].created_at if messages else None
    return {
        "conversation": _serialize_conversation_summary(
            conversation,
            message_count=len(messages),
            last_message_at=last_message_at,
        ),
        "messages": [_serialize_message(message) for message in messages],
    }


@router.get("/plants")
def plants_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    params = request.query_params
    plants = list_plants(
        db,
        query=optional_str(params.get("query")),
        status=optional_str(params.get("status")),
        location_id=optional_str(params.get("location_id")),
        acquisition_year=parse_int(params.get("acquisition_year")),
        grafted=parse_bool(params.get("grafted")) if params.get("grafted") is not None else None,
        edible=parse_bool(params.get("edible")) if params.get("edible") is not None else None,
        toxic=parse_bool(params.get("toxic")) if params.get("toxic") is not None else None,
        pollinator_value=parse_bool(params.get("pollinator_value"))
        if params.get("pollinator_value") is not None
        else None,
        taxonomy_id=optional_str(params.get("taxonomy_id")),
    )
    return JSONResponse([_serialize_plant(plant, db) for plant in plants])


@router.post("/plants")
async def plant_create(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = create_plant(db, request.app.state.settings, await _request_payload(request))
    db.commit()
    return JSONResponse(_serialize_plant(plant, db), status_code=status.HTTP_201_CREATED)


@router.get("/plants/{plant_id}")
def plant_detail(
    plant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = get_plant(db, plant_id)
    return JSONResponse(_serialize_plant(plant, db))


@router.patch("/plants/{plant_id}")
async def plant_update(
    plant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = get_plant(db, plant_id)
    update_plant(db, plant, await _request_payload(request), request.app.state.settings)
    db.commit()
    return JSONResponse(_serialize_plant(plant, db))


@router.post("/plants/{plant_id}/observations")
async def plant_observation_create(
    plant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = get_plant(db, plant_id)
    observation = create_observation(db, plant, await _request_payload(request))
    db.commit()
    return JSONResponse(_serialize_observation(observation), status_code=status.HTTP_201_CREATED)


@router.post("/plants/{plant_id}/measurements")
async def plant_measurement_create(
    plant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = get_plant(db, plant_id)
    measurement = record_measurement(db, plant, await _request_payload(request))
    db.commit()
    return JSONResponse(_serialize_measurement(measurement), status_code=status.HTTP_201_CREATED)


@router.post("/plants/{plant_id}/media")
async def plant_media_upload(
    plant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = get_plant(db, plant_id)
    form = await request.form()
    upload = form.get("file") or form.get("upload") or form.get("media")
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A media file is required."
        )
    try:
        asset = store_upload(
            db,
            request.app.state.settings,
            plant,
            upload,
            observation_id=optional_str(form.get("observation_id")),
            view_type=optional_str(form.get("view_type")) or "other",
            caption=optional_str(form.get("caption")),
        )
    except MediaError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return JSONResponse(_serialize_media(asset), status_code=status.HTTP_201_CREATED)


@router.post("/plants/{plant_id}/move")
async def plant_move(
    plant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = get_plant(db, plant_id)
    payload = await _request_payload(request)
    move_plant(
        db,
        plant,
        location_id=optional_str(payload.get("current_location_id")),
        container_id=optional_str(payload.get("container_id")),
        notes=optional_str(payload.get("notes")),
        performed_by=optional_str(payload.get("performed_by")),
    )
    db.commit()
    return JSONResponse(_serialize_plant(plant, db))


@router.post("/plants/{plant_id}/treatments")
async def plant_treatment_create(
    plant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = get_plant(db, plant_id)
    treatment = record_treatment(db, plant, await _request_payload(request))
    db.commit()
    return JSONResponse(_serialize_treatment(treatment), status_code=status.HTTP_201_CREATED)


@router.post("/plants/{plant_id}/propagations")
async def plant_propagation_create(
    plant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = get_plant(db, plant_id)
    event = start_propagation(db, plant, await _request_payload(request))
    db.commit()
    return JSONResponse(
        {
            "id": event.id,
            "source_plant_id": event.source_plant_id,
            "new_plant_id": event.new_plant_id,
            "method": event.method,
            "status": event.status,
            "started_at": event.started_at.isoformat(),
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/plants/{plant_id}/timeline")
def plant_timeline(
    plant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    plant = get_plant(db, plant_id)
    return JSONResponse(_json_value(build_plant_timeline(db, plant)))


@router.get("/tasks")
def tasks_index(
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(require_permission("tasks.read")),
) -> JSONResponse:
    snapshot = task_snapshot(db, principal)
    return JSONResponse(
        {
            "due_tasks": [_serialize_task(task, db) for task in snapshot["due"]],
            "overdue_tasks": [_serialize_task(task, db) for task in snapshot["overdue"]],
            "completed_tasks": [_serialize_task(task, db) for task in snapshot["completed"]],
        },
    )


@router.post("/tasks/{task_id}/complete")
async def task_complete(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: PrincipalContext = Depends(require_permission("tasks.write")),
) -> JSONResponse:
    payload = await _request_payload(request)

    def persist_completion() -> dict[str, Any]:
        # Serialize competing completions in PostgreSQL as well as sequential retries.
        occurrence = db.scalar(
            select(TaskOccurrence).where(TaskOccurrence.id == task_id).with_for_update()
        )
        if occurrence is None or not task_is_visible(
            db, occurrence, resolve_visible_scope_ids(db, principal)
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task occurrence not found."
            )
        if occurrence.skipped_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="A skipped task cannot be completed."
            )
        complete_task_occurrence(
            db,
            occurrence,
            completion_notes=optional_str(payload.get("completion_notes")),
            performed_by=optional_str(payload.get("performed_by")),
        )
        db.commit()
        return _serialize_task(occurrence, db)

    return JSONResponse(await run_in_threadpool(persist_completion))


@router.get("/labels/{plant_id}")
def label_preview(
    plant_id: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    plant = get_plant(db, plant_id)
    template = default_label_template(db)
    data = label_preview_data(plant, template)
    return JSONResponse(
        {
            "plant_id": plant.id,
            "display_id": plant.display_id,
            "template": {
                "id": template.id,
                "name": template.name,
                "width_mm": template.width_mm,
                "height_mm": template.height_mm,
                "template_type": template.template_type,
            },
            "public_url": data["public_url"],
            "preview_svg": data["qr_svg"],
            "pdf_url": f"/labels/{plant.id}/pdf",
        },
    )


@router.get("/labels/{plant_id}/pdf")
def label_pdf(
    plant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    del current_user
    plant = get_plant(db, plant_id)
    template = default_label_template(db)
    pdf = label_pdf_data(plant, template)
    db.commit()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{plant.display_id}.pdf"'},
    )


@router.post("/propagations/{event_id}/complete")
async def propagation_complete(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    event = db.get(PropagationEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Propagation event not found."
        )
    source_plant = get_plant(db, event.source_plant_id)
    new_plant = complete_propagation(
        db, request.app.state.settings, source_plant, event, await _request_payload(request)
    )
    db.commit()
    return JSONResponse(
        {"event_id": event.id, "new_plant_id": new_plant.id, "display_id": new_plant.display_id}
    )


@router.post("/propagations/{event_id}/fail")
async def propagation_fail(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    event = db.get(PropagationEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Propagation event not found."
        )
    fail_propagation(
        db, event, notes=optional_str((await _request_payload(request)).get("failure_notes"))
    )
    db.commit()
    return JSONResponse({"event_id": event.id, "status": event.status})


@router.get("/conversations")
def conversations_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    params = request.query_params
    limit = parse_int(params.get("limit")) or 50
    conversations = list_conversations(db, limit=max(limit, 1))
    return JSONResponse(
        {
            "conversations": [
                _serialize_conversation_summary(
                    conversation,
                    message_count=message_count,
                    last_message_at=last_message_at,
                )
                for conversation, message_count, last_message_at in conversations
            ],
            "count": len(conversations),
        },
    )


@router.post("/conversations")
async def conversation_create(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    payload = await _request_payload(request)
    conversation = create_conversation(
        db,
        payload,
        created_by_user_id=current_user.id,
    )
    db.commit()
    return JSONResponse(
        _serialize_conversation_summary(
            conversation,
            message_count=0,
            last_message_at=None,
        ),
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/conversations/{conversation_id}")
def conversation_detail(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    del current_user
    try:
        conversation, messages = get_conversation_bundle(db, conversation_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return JSONResponse(_serialize_conversation_detail(conversation, messages))


@router.post("/conversations/{conversation_id}/messages")
async def conversation_message_create(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    payload = await _request_payload(request)
    try:
        conversation, _messages = get_conversation_bundle(db, conversation_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    try:
        message = append_message(
            db,
            conversation,
            payload,
            author_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return JSONResponse(_serialize_message(message), status_code=status.HTTP_201_CREATED)
