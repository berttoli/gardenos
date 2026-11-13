from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access.services import PrincipalContext
from app.care.models import TaskOccurrence
from app.care.updaters import resolve_task_scope_projection
from app.plants.models import Plant
from app.platform.location_access import exact_location_scope_ids
from app.platform.scope_access import resolve_visible_scope_ids


def exact_task_scope_id(
    session: Session,
    occurrence: TaskOccurrence,
    *,
    location_scope_ids: dict[str, str] | None = None,
) -> str | None:
    return resolve_task_scope_projection(
        session,
        occurrence.task_definition,
        plant=occurrence.plant,
        location_scope_ids=location_scope_ids,
    ).scope_node_id


def task_is_visible(
    session: Session,
    occurrence: TaskOccurrence,
    scope_ids: set[str] | None,
    *,
    location_scope_ids: dict[str, str] | None = None,
) -> bool:
    if scope_ids is None:
        return True
    if not scope_ids:
        return False
    if location_scope_ids is None:
        location_scope_ids = exact_location_scope_ids(session)
    # A task may also carry a plant reference. Do not expose a foreign or
    # unmapped plant through an otherwise accessible task definition.
    if occurrence.plant is not None:
        location_id = occurrence.plant.current_location_id
        if location_id is None or location_scope_ids.get(location_id) not in scope_ids:
            return False
    return (
        exact_task_scope_id(session, occurrence, location_scope_ids=location_scope_ids) in scope_ids
    )


def task_snapshot(
    session: Session,
    principal: PrincipalContext,
    *,
    limit: int = 50,
) -> dict[str, list[TaskOccurrence]]:
    """Return disjoint, scoped task lists; completed work survives a new read."""
    result: dict[str, list[TaskOccurrence]] = {"due": [], "overdue": [], "completed": []}
    if "tasks.read" not in principal.permissions:
        return result
    scope_ids = resolve_visible_scope_ids(session, principal)
    if scope_ids == set():
        return result
    location_scope_ids = exact_location_scope_ids(session) if scope_ids is not None else {}
    statement = (
        select(TaskOccurrence)
        .options(
            selectinload(TaskOccurrence.task_definition),
            selectinload(TaskOccurrence.plant).selectinload(Plant.current_location),
        )
        .where(TaskOccurrence.skipped_at.is_(None))
        .order_by(TaskOccurrence.scheduled_for, TaskOccurrence.id)
    )
    now = datetime.now(UTC)
    for occurrence in session.scalars(statement):
        if not task_is_visible(
            session, occurrence, scope_ids, location_scope_ids=location_scope_ids
        ):
            continue
        if occurrence.completed_at is not None:
            result["completed"].append(occurrence)
            continue
        scheduled = occurrence.scheduled_for
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=UTC)
        bucket = "overdue" if scheduled < now else "due"
        if len(result[bucket]) < limit:
            result[bucket].append(occurrence)
    result["completed"].sort(
        key=lambda occurrence: (
            occurrence.completed_at.isoformat() if occurrence.completed_at else "",
            occurrence.id,
        ),
        reverse=True,
    )
    result["completed"] = result["completed"][:limit]
    return result
