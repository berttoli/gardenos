from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.care.services import initial_tasks_for_plant
from app.common.forms import optional_str, parse_date
from app.common.ids import new_uuid_str
from app.config import Settings
from app.media.models import MediaAsset
from app.media.services import ALLOWED_MEDIA_TYPES, MAX_UPLOAD_BYTES, MediaError, store_upload
from app.observations.services import create_observation, record_measurement
from app.onboarding.models import OnboardingDraft
from app.plants.models import Plant
from app.plants.services import create_plant


class OnboardingError(ValueError):
    pass


def _as_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_dict_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def create_draft(session: Session, *, state: Mapping[str, Any] | None = None) -> OnboardingDraft:
    draft = OnboardingDraft(
        draft_token=token_urlsafe(24),
        current_step=1,
        state=dict(state or {}),
    )
    session.add(draft)
    session.flush()
    return draft


def get_draft(session: Session, draft_token: str) -> OnboardingDraft | None:
    return session.scalar(select(OnboardingDraft).where(OnboardingDraft.draft_token == draft_token))


def save_step(
    session: Session, draft: OnboardingDraft, step: int, payload: Mapping[str, Any]
) -> OnboardingDraft:
    state = dict(draft.state)
    steps = _as_dict(state.get("steps"))
    steps[str(step)] = dict(payload)
    state["steps"] = steps
    if step == 1:
        state["plant"] = dict(payload)
    elif step == 2:
        state["arrival_observation"] = dict(payload)
    elif step == 3:
        state["photos"] = dict(payload)
    elif step == 4:
        state["measurements"] = dict(payload)
    elif step == 5:
        state["placement"] = dict(payload)
    elif step == 6:
        state["initial_tasks"] = dict(payload)
    draft.state = state
    draft.current_step = step
    session.add(draft)
    session.flush()
    return draft


def store_draft_media(
    session: Session,
    settings: Settings,
    draft: OnboardingDraft,
    upload: Any,
    *,
    view_type: str = "other",
    caption: str | None = None,
) -> dict[str, Any]:
    draft_dir = Path(settings.media_root).expanduser().resolve() / "drafts" / draft.draft_token
    draft_dir.mkdir(parents=True, exist_ok=True)
    original_name = Path(getattr(upload, "filename", "upload")).name or "upload"
    suffix = Path(original_name).suffix.lower() or ".bin"
    temp_name = f"{new_uuid_str()}{suffix}"
    temp_path = draft_dir / temp_name
    file_obj = getattr(upload, "file", upload)

    content_type = getattr(upload, "content_type", None)
    if content_type is not None and content_type not in ALLOWED_MEDIA_TYPES:
        raise MediaError(f"Unsupported media type: {content_type}")

    digest = sha256()
    total = 0
    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0)
        except Exception:  # pragma: no cover - defensive
            pass

    with temp_path.open("wb") as destination:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                destination.close()
                temp_path.unlink(missing_ok=True)
                raise MediaError("Upload exceeds maximum allowed size.")
            digest.update(chunk)
            destination.write(chunk)
    metadata = {
        "id": new_uuid_str(),
        "temporary_path": temp_path.relative_to(
            Path(settings.media_root).expanduser().resolve()
        ).as_posix(),
        "original_filename": original_name,
        "checksum": digest.hexdigest(),
        "view_type": view_type,
        "caption": caption,
    }
    state = dict(draft.state)
    media_records = _as_dict_list(state.get("media_records", []))
    media_records.append(metadata)
    state["media_records"] = media_records
    draft.state = state
    session.add(draft)
    session.flush()
    return metadata


def _promote_draft_media(
    session: Session, settings: Settings, plant: Plant, draft: OnboardingDraft
) -> list[MediaAsset]:
    media_records = _as_dict_list(draft.state.get("media_records", []))
    promoted: list[MediaAsset] = []
    for record in media_records:
        temporary_path = record.get("temporary_path")
        if not temporary_path:
            continue
        upload_path = Path(settings.media_root).expanduser().resolve() / str(temporary_path)
        if not upload_path.exists():
            continue
        with upload_path.open("rb") as file_obj:
            promoted.append(
                store_upload(
                    session,
                    settings,
                    plant,
                    file_obj,
                    observation_id=None,
                    view_type=str(record.get("view_type") or "other"),
                    caption=optional_str(record.get("caption")),
                ),
            )
        upload_path.unlink(missing_ok=True)
    return promoted


def complete_onboarding(session: Session, settings: Settings, draft: OnboardingDraft) -> Plant:
    state = dict(draft.state)
    plant_payload = _as_dict(state.get("plant"))
    if not plant_payload:
        raise OnboardingError("Onboarding draft is missing plant details.")

    plant = create_plant(session, settings, plant_payload)

    arrival_observation = state.get("arrival_observation")
    if isinstance(arrival_observation, Mapping):
        create_observation(session, plant, arrival_observation)

    measurements = state.get("measurements")
    if isinstance(measurements, Mapping):
        record_measurement(session, plant, measurements)

    placement = _as_dict(state.get("placement"))
    if placement:
        if placement.get("current_location_id"):
            plant.current_location_id = optional_str(placement.get("current_location_id"))
        if placement.get("container_id"):
            plant.container_id = optional_str(placement.get("container_id"))
        if placement.get("status"):
            plant.status = optional_str(placement.get("status")) or plant.status
        session.add(plant)

    _promote_draft_media(session, settings, plant, draft)
    initial_tasks_for_plant(
        session,
        plant,
        quarantine_end=parse_date(placement.get("expected_quarantine_end_date")),
    )

    draft.plant_id = plant.id
    draft.completed_at = datetime.now(UTC)
    session.add(draft)
    session.flush()
    return plant


def abandon_draft(session: Session, draft: OnboardingDraft) -> OnboardingDraft:
    draft.abandoned_at = datetime.now(UTC)
    session.add(draft)
    session.flush()
    return draft
