from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.care.models import TASK_SCOPES, TASK_TYPES, TaskDefinition, TaskOccurrence
from app.care.updaters import backfill_task_definition_scope, task_scope_summary
from app.common.forms import optional_str, parse_bool, parse_date, parse_int
from app.observations.models import Observation
from app.plants.models import Plant
from app.plants.services import plants_in_quarantine, recent_plants
from app.platform.events import record_platform_event
from app.propagation.models import PropagationEvent


class TaskError(ValueError):
    pass


def _validate_choice(value: str | None, choices: tuple[str, ...], field_name: str) -> str:
    normalized = optional_str(value)
    if normalized is None:
        raise TaskError(f"{field_name} is required.")
    if normalized not in choices:
        raise TaskError(f"Invalid {field_name}: {normalized}.")
    return normalized


def create_task_definition(session: Session, payload: Mapping[str, Any]) -> TaskDefinition:
    priority = parse_int(payload.get("priority"))
    task = TaskDefinition(
        title=optional_str(payload.get("title")) or "Untitled task",
        description=optional_str(payload.get("description")),
        task_type=_validate_choice(payload.get("task_type"), TASK_TYPES, "task_type")
        if optional_str(payload.get("task_type"))
        else "custom",
        priority=priority if priority is not None else 3,
        scope_type=_validate_choice(payload.get("scope_type"), TASK_SCOPES, "scope_type")
        if optional_str(payload.get("scope_type"))
        else "garden",
        scope_id=optional_str(payload.get("scope_id")),
        recurrence_rule=optional_str(payload.get("recurrence_rule")),
        seasonal_start=parse_date(payload.get("seasonal_start")),
        seasonal_end=parse_date(payload.get("seasonal_end")),
        due_date=parse_date(payload.get("due_date")),
        estimated_minutes=parse_int(payload.get("estimated_minutes")),
        completion_behavior=optional_str(payload.get("completion_behavior")),
        is_active=parse_bool(payload.get("is_active"), True),
    )
    session.add(task)
    session.flush()
    backfill_task_definition_scope(session, task)
    return task


def ensure_task_occurrence(
    session: Session,
    task_definition: TaskDefinition,
    *,
    plant_id: str | None = None,
    scheduled_for: datetime | None = None,
    completion_notes: str | None = None,
    performed_by: str | None = None,
) -> TaskOccurrence:
    scheduled = scheduled_for or datetime.now(UTC)
    existing = session.scalar(
        select(TaskOccurrence).where(
            TaskOccurrence.task_definition_id == task_definition.id,
            TaskOccurrence.plant_id == plant_id,
            TaskOccurrence.scheduled_for == scheduled,
        ),
    )
    if existing is not None:
        return existing

    occurrence = TaskOccurrence(
        task_definition=task_definition,
        plant_id=plant_id,
        scheduled_for=scheduled,
        completion_notes=completion_notes,
        performed_by=performed_by,
    )
    session.add(occurrence)
    session.flush()
    scope_payload = task_scope_summary(session, task_definition, plant=occurrence.plant)
    record_platform_event(
        session,
        event_type="task.occurrence.scheduled",
        source_kind="task",
        source_id=occurrence.id,
        scope_node=scope_payload["scope_node_id"],
        payload={
            "task_definition_id": task_definition.id,
            "plant_id": plant_id,
            "scheduled_for": occurrence.scheduled_for.isoformat(),
            "performed_by": performed_by,
            **scope_payload,
        },
    )
    return occurrence


def complete_task_occurrence(
    session: Session,
    occurrence: TaskOccurrence,
    *,
    completion_notes: str | None = None,
    performed_by: str | None = None,
) -> TaskOccurrence:
    # Retried requests must preserve the original completion and emit one event.
    if occurrence.completed_at is not None:
        return occurrence
    occurrence.completed_at = datetime.now(UTC)
    if completion_notes is not None:
        occurrence.completion_notes = completion_notes
    if performed_by is not None:
        occurrence.performed_by = performed_by
    session.add(occurrence)
    session.flush()
    scope_payload = task_scope_summary(
        session,
        occurrence.task_definition,
        plant=occurrence.plant,
    )
    record_platform_event(
        session,
        event_type="task.occurrence.completed",
        source_kind="task",
        source_id=occurrence.id,
        scope_node=scope_payload["scope_node_id"],
        payload={
            "task_definition_id": occurrence.task_definition_id,
            "plant_id": occurrence.plant_id,
            "completed_at": occurrence.completed_at.isoformat(),
            "completion_notes": occurrence.completion_notes,
            "performed_by": occurrence.performed_by,
            **scope_payload,
        },
    )
    return occurrence


def initial_tasks_for_plant(
    session: Session, plant: Plant, *, quarantine_end: date | None = None
) -> list[TaskOccurrence]:
    now = datetime.now(UTC)
    plans = (
        {
            "title": "Inspect moisture",
            "description": "Check soil moisture before watering.",
            "task_type": "inspect",
            "priority": 1,
            "completion_behavior": "record_only",
        },
        {
            "title": "Inspect pests",
            "description": "Look for pests, webbing, eggs, and spotting.",
            "task_type": "inspect",
            "priority": 1,
            "completion_behavior": "record_only",
        },
        {
            "title": "Photograph after acclimation",
            "description": "Capture a baseline photo once the plant settles in.",
            "task_type": "photograph",
            "priority": 2,
            "completion_behavior": "record_only",
        },
        {
            "title": "Review quarantine status",
            "description": "Confirm the plant is still in the right placement.",
            "task_type": "inspect",
            "priority": 2,
            "completion_behavior": "record_only",
        },
    )
    occurrences: list[TaskOccurrence] = []
    for offset, plan in enumerate(plans):
        task = create_task_definition(
            session,
            {
                **plan,
                "scope_type": "plant",
                "scope_id": plant.id,
                "due_date": quarantine_end or None,
                "is_active": True,
            },
        )
        occurrence = ensure_task_occurrence(
            session,
            task,
            plant_id=plant.id,
            scheduled_for=now + timedelta(days=offset),
        )
        occurrences.append(occurrence)
    return occurrences


def due_tasks(session: Session, *, limit: int = 10) -> list[TaskOccurrence]:
    stmt = (
        select(TaskOccurrence)
        .join(TaskDefinition)
        .options(
            selectinload(TaskOccurrence.task_definition),
            selectinload(TaskOccurrence.plant).selectinload(Plant.current_location),
        )
        .where(TaskOccurrence.completed_at.is_(None), TaskOccurrence.skipped_at.is_(None))
        .order_by(TaskOccurrence.scheduled_for.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def overdue_tasks(session: Session, *, limit: int = 10) -> list[TaskOccurrence]:
    now = datetime.now(UTC)
    stmt = (
        select(TaskOccurrence)
        .join(TaskDefinition)
        .options(
            selectinload(TaskOccurrence.task_definition),
            selectinload(TaskOccurrence.plant).selectinload(Plant.current_location),
        )
        .where(
            TaskOccurrence.completed_at.is_(None),
            TaskOccurrence.skipped_at.is_(None),
            TaskOccurrence.scheduled_for < now,
        )
        .order_by(TaskOccurrence.scheduled_for.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def recent_propagation_events(session: Session, *, limit: int = 8) -> list[PropagationEvent]:
    stmt = (
        select(PropagationEvent)
        .options(
            selectinload(PropagationEvent.source_plant), selectinload(PropagationEvent.new_plant)
        )
        .order_by(desc(PropagationEvent.started_at))
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def plants_needing_follow_up(session: Session, *, limit: int = 8) -> list[Plant]:
    plants = recent_plants(session, limit=25)
    flagged: list[Plant] = []
    for plant in plants:
        status_flag = plant.status in {"declining", "quarantine"}
        recent_flag = False
        latest_observation = (
            max(plant.observations, key=lambda item: item.observed_at)
            if plant.observations
            else None
        )
        if latest_observation is not None:
            score = latest_observation.overall_health_score
            if score is not None and float(score) < 6.5:
                recent_flag = True
        if status_flag or recent_flag:
            flagged.append(plant)
    return flagged[:limit]


def dashboard_snapshot(session: Session) -> dict[str, Any]:
    return {
        "due_tasks": due_tasks(session),
        "overdue_tasks": overdue_tasks(session),
        "quarantine_plants": plants_in_quarantine(session),
        "plants_needing_follow_up": plants_needing_follow_up(session),
        "recent_observations": list(
            session.scalars(
                select(Observation)
                .options(selectinload(Observation.plant), selectinload(Observation.assessment))
                .order_by(desc(Observation.observed_at))
                .limit(8),
            ).all(),
        ),
        "recent_plants": recent_plants(session),
        "propagation_events": recent_propagation_events(session),
    }
