from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.care.models import TaskOccurrence
from app.care.updaters import task_scope_summary


def _utc_isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def serialize_task_occurrence(occurrence: TaskOccurrence, session: Session) -> dict[str, Any]:
    task_definition = occurrence.task_definition
    plant = occurrence.plant
    scope = task_scope_summary(session, task_definition, plant=plant)
    return {
        "id": occurrence.id,
        "status": (
            "completed"
            if occurrence.completed_at
            else "skipped"
            if occurrence.skipped_at
            else "pending"
        ),
        "task_definition_id": occurrence.task_definition_id,
        "plant_id": occurrence.plant_id,
        "title": task_definition.title if task_definition else None,
        "task_type": task_definition.task_type if task_definition else None,
        "priority": task_definition.priority if task_definition else None,
        "scheduled_for": _utc_isoformat(occurrence.scheduled_for),
        "completed_at": _utc_isoformat(occurrence.completed_at),
        "skipped_at": _utc_isoformat(occurrence.skipped_at),
        "completion_notes": occurrence.completion_notes,
        "performed_by": occurrence.performed_by,
        "location_id": plant.current_location_id if plant else None,
        "zone": plant.current_location.name if plant and plant.current_location else None,
        **scope,
    }
