from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.care.models import TaskDefinition
from app.common.forms import optional_str
from app.locations.models import Location
from app.plants.models import Plant
from app.platform.location_access import exact_location_scope_ids
from app.platform.models import ScopeNode


def _resolve_scope_node_from_location(
    session: Session,
    location: Location,
    location_scope_ids: dict[str, str] | None = None,
) -> ScopeNode | None:
    if location_scope_ids is None:
        location_scope_ids = exact_location_scope_ids(session)
    scope_id = location_scope_ids.get(location.id)
    return session.get(ScopeNode, scope_id) if scope_id is not None else None


@dataclass(frozen=True, slots=True)
class TaskScopeProjection:
    scope_node: ScopeNode | None
    source_kind: str | None
    source_id: str | None

    @property
    def scope_node_id(self) -> str | None:
        return self.scope_node.id if self.scope_node is not None else None

    @property
    def scope_node_type(self) -> str | None:
        return self.scope_node.scope_type if self.scope_node is not None else None

    @property
    def scope_node_name(self) -> str | None:
        return self.scope_node.name if self.scope_node is not None else None

    @property
    def scope_node_slug(self) -> str | None:
        return self.scope_node.slug if self.scope_node is not None else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope_node_id": self.scope_node_id,
            "scope_node_type": self.scope_node_type,
            "scope_node_name": self.scope_node_name,
            "scope_node_slug": self.scope_node_slug,
            "scope_source_kind": self.source_kind,
            "scope_source_id": self.source_id,
        }


def resolve_task_scope_projection(
    session: Session,
    task_definition: TaskDefinition | None,
    *,
    plant: Plant | None = None,
    location_scope_ids: dict[str, str] | None = None,
) -> TaskScopeProjection:
    if task_definition is None:
        if plant is not None and plant.current_location is not None:
            scope_node = _resolve_scope_node_from_location(
                session, plant.current_location, location_scope_ids
            )
            return TaskScopeProjection(
                scope_node=scope_node,
                source_kind="plant_location" if scope_node is not None else None,
                source_id=plant.current_location.id if scope_node is not None else None,
            )
        return TaskScopeProjection(scope_node=None, source_kind=None, source_id=None)

    scope_id = optional_str(task_definition.scope_id)
    if scope_id is not None:
        scope_node = session.get(ScopeNode, scope_id)
        if scope_node is not None:
            return TaskScopeProjection(
                scope_node=scope_node,
                source_kind="scope_node",
                source_id=scope_node.id,
            )

        location = session.get(Location, scope_id)
        if location is not None:
            scope_node = _resolve_scope_node_from_location(session, location, location_scope_ids)
            return TaskScopeProjection(
                scope_node=scope_node,
                source_kind="location",
                source_id=location.id,
            )

        plant_source = session.get(Plant, scope_id)
        if plant_source is not None and plant_source.current_location is not None:
            scope_node = _resolve_scope_node_from_location(
                session, plant_source.current_location, location_scope_ids
            )
            return TaskScopeProjection(
                scope_node=scope_node,
                source_kind="plant_location" if scope_node is not None else "plant",
                source_id=(
                    plant_source.current_location.id if scope_node is not None else plant_source.id
                ),
            )
        # A declared but unresolved identifier must not inherit the occurrence's
        # plant scope: that can silently authorize a different nursery.
        return TaskScopeProjection(scope_node=None, source_kind=None, source_id=None)

    if plant is not None and plant.current_location is not None:
        scope_node = _resolve_scope_node_from_location(
            session, plant.current_location, location_scope_ids
        )
        return TaskScopeProjection(
            scope_node=scope_node,
            source_kind="plant_location" if scope_node is not None else None,
            source_id=plant.current_location.id if scope_node is not None else None,
        )

    return TaskScopeProjection(scope_node=None, source_kind=None, source_id=None)


def resolve_task_scope_node(
    session: Session,
    task_definition: TaskDefinition | None,
    *,
    plant: Plant | None = None,
) -> ScopeNode | None:
    return resolve_task_scope_projection(session, task_definition, plant=plant).scope_node


def task_scope_summary(
    session: Session,
    task_definition: TaskDefinition | None,
    *,
    plant: Plant | None = None,
) -> dict[str, Any]:
    return resolve_task_scope_projection(session, task_definition, plant=plant).as_dict()


def backfill_task_definition_scope(
    session: Session,
    task_definition: TaskDefinition,
) -> bool:
    projection = resolve_task_scope_projection(session, task_definition)
    scope_node = projection.scope_node
    if scope_node is None:
        return False

    changed = False
    if task_definition.scope_type != scope_node.scope_type:
        task_definition.scope_type = scope_node.scope_type
        changed = True
    if task_definition.scope_id != scope_node.id:
        task_definition.scope_id = scope_node.id
        changed = True
    if changed:
        session.add(task_definition)
        session.flush()
    return changed


def backfill_task_definitions(
    session: Session,
    task_definitions: Mapping[str, TaskDefinition] | None = None,
) -> int:
    if task_definitions is None:
        items = list(session.scalars(select(TaskDefinition)).all())
    else:
        items = list(task_definitions.values())

    updated = 0
    for task_definition in items:
        if backfill_task_definition_scope(session, task_definition):
            updated += 1
    return updated
