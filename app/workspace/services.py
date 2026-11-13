from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.access.services import PrincipalContext, serialize_principal
from app.care.access import task_snapshot
from app.care.serialization import serialize_task_occurrence
from app.locations.models import Location
from app.observations.models import Observation
from app.plants.models import Plant
from app.platform.events import list_platform_events
from app.platform.location_access import exact_location_scope_ids
from app.platform.scope_access import resolve_visible_scope_ids
from app.platform.services import list_telemetry_events, serialize_platform_catalog

WORKSPACE_SIDEBAR_ITEMS: tuple[dict[str, Any], ...] = (
    {"page": "map", "label": "Map", "icon": "map"},
    {"page": "tasks", "label": "Tasks", "icon": "tasks"},
    {"page": "plants", "label": "Plants", "icon": "plants"},
    {"page": "monitoring", "label": "Monitoring", "icon": "health"},
    {"page": "schedule", "label": "Schedule", "icon": "calendar"},
    {"page": "automations", "label": "Automations", "icon": "spark"},
    {"page": "people", "label": "People", "icon": "people"},
    {"page": "inventory", "label": "Inventory", "icon": "inventory"},
    {"page": "reports", "label": "Reports", "icon": "reports"},
    {"page": "settings", "label": "Settings", "icon": "settings"},
)


def _serialize_task(task: Any, session: Session) -> dict[str, Any]:
    return serialize_task_occurrence(task, session)


def _plant_counts_by_location(session: Session, location_ids: set[str] | None) -> dict[str, int]:
    statement = (
        select(Plant.current_location_id, func.count(Plant.id))
        .where(Plant.current_location_id.is_not(None))
        .group_by(Plant.current_location_id)
    )
    if location_ids is not None:
        statement = statement.where(Plant.current_location_id.in_(location_ids))
    rows = session.execute(statement).all()
    return {str(location_id): int(count) for location_id, count in rows}


def _plant_summary(session: Session, location_ids: set[str] | None) -> dict[str, int]:
    statement = select(func.count(Plant.id))
    if location_ids is not None:
        statement = statement.where(Plant.current_location_id.in_(location_ids))
    latest_health_score = (
        select(Observation.overall_health_score)
        .where(Observation.plant_id == Plant.id)
        .order_by(Observation.observed_at.desc(), Observation.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    return {
        "plant_count": session.scalar(statement) or 0,
        "quarantine_plant_count": session.scalar(statement.where(Plant.status == "quarantine"))
        or 0,
        "follow_up_plant_count": session.scalar(
            statement.where(
                or_(Plant.status.in_(("declining", "quarantine")), latest_health_score < 6.5)
            )
        )
        or 0,
    }


def _build_location_tree(
    locations: list[Location],
    *,
    plant_counts: dict[str, int],
    selected_location_id: str | None = None,
) -> list[dict[str, Any]]:
    children_by_parent: dict[str | None, list[Location]] = defaultdict(list)
    location_ids = {location.id for location in locations}
    for location in locations:
        parent_id = location.parent_id if location.parent_id in location_ids else None
        children_by_parent[parent_id].append(location)

    def build(location: Location, ancestors: list[dict[str, str]]) -> dict[str, Any]:
        current_path = [
            *ancestors,
            {"id": location.id, "name": location.name, "type": location.location_type},
        ]
        children = sorted(
            children_by_parent.get(location.id, []),
            key=lambda item: item.name.casefold(),
        )
        serialized_children = [build(child, current_path) for child in children]
        direct_plant_count = plant_counts.get(location.id, 0)
        aggregate_plant_count = direct_plant_count + sum(
            child["plant_count"] for child in serialized_children
        )
        return {
            "id": location.id,
            "parent_id": location.parent_id if location.parent_id in location_ids else None,
            "name": location.name,
            "location_type": location.location_type,
            "description": location.description,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "elevation": location.elevation,
            "sun_exposure": location.sun_exposure,
            "wind_exposure": location.wind_exposure,
            "irrigation_zone": location.irrigation_zone,
            "microclimate_notes": location.microclimate_notes,
            "depth": len(ancestors),
            "path": current_path,
            "direct_plant_count": direct_plant_count,
            "plant_count": aggregate_plant_count,
            "child_count": len(serialized_children),
            "is_selected": location.id == selected_location_id,
            "children": serialized_children,
        }

    roots = sorted(children_by_parent.get(None, []), key=lambda item: item.name.casefold())
    return [build(location, []) for location in roots]


def build_system_services_payload(
    session: Session,
    principal: PrincipalContext,
) -> list[dict[str, Any]]:
    scope_ids = resolve_visible_scope_ids(session, principal)
    platform_catalog = serialize_platform_catalog(session, scope_node_ids=scope_ids)
    telemetry_events = list_telemetry_events(session, scope_node_ids=scope_ids)
    event_ready = bool(list_platform_events(session, scope_node_ids=scope_ids, limit=1))
    database_ready = session.execute(select(1)).scalar_one_or_none() == 1

    return [
        {
            "key": "postgres",
            "name": "Postgres",
            "kind": "database",
            "status": "ready" if database_ready else "degraded",
            "surface": "storage",
            "details": {"healthy": database_ready},
        },
        {
            "key": "api",
            "name": "Garden API",
            "kind": "service",
            "status": "ready",
            "surface": "api",
            "details": {"health_endpoint": "/health/ready"},
        },
        {
            "key": "platform-catalog",
            "name": "Platform Catalog",
            "kind": "service",
            "status": "ready" if platform_catalog["summary"]["scope_count"] > 0 else "degraded",
            "surface": "catalog",
            "details": {
                "scope_count": platform_catalog["summary"]["scope_count"],
                "skill_count": platform_catalog["summary"]["skill_count"],
                "connector_count": platform_catalog["summary"]["connector_count"],
            },
        },
        {
            "key": "telemetry",
            "name": "Telemetry",
            "kind": "service",
            "status": "ready" if telemetry_events else "idle",
            "surface": "monitoring",
            "details": {
                "event_count": len(telemetry_events),
                "last_event_at": telemetry_events[0].occurred_at.isoformat()
                if telemetry_events
                else None,
            },
        },
        {
            "key": "event-stream",
            "name": "Event Stream",
            "kind": "service",
            "status": "ready" if event_ready else "idle",
            "surface": "events",
            "details": {"stream_path": "/api/v1/platform/events/stream"},
        },
    ]


def build_workspace_payload(
    session: Session,
    principal: PrincipalContext,
    *,
    selected_location_id: str | None = None,
) -> dict[str, Any]:
    scope_ids = resolve_visible_scope_ids(session, principal)
    locations = list(session.scalars(select(Location).order_by(Location.name)).all())
    if scope_ids is not None:
        location_scope_ids = exact_location_scope_ids(session)
        locations = [
            location for location in locations if location_scope_ids.get(location.id) in scope_ids
        ]
    visible_location_ids = {location.id for location in locations}
    if selected_location_id not in visible_location_ids:
        selected_location_id = None
    plant_location_ids = visible_location_ids if scope_ids is not None else None
    if "plants.read" not in principal.permissions:
        plant_location_ids = set()
    plant_counts = _plant_counts_by_location(session, plant_location_ids)
    plant_summary = _plant_summary(session, plant_location_ids)

    location_tree = _build_location_tree(
        locations,
        plant_counts=plant_counts,
        selected_location_id=selected_location_id,
    )
    tasks = task_snapshot(session, principal)
    due_tasks = [_serialize_task(task, session) for task in tasks["due"]]
    overdue_tasks = [_serialize_task(task, session) for task in tasks["overdue"]]
    completed_tasks = [_serialize_task(task, session) for task in tasks["completed"]]
    system_services = build_system_services_payload(session, principal)

    sidebar = []
    for item in WORKSPACE_SIDEBAR_ITEMS:
        pending_count = len(due_tasks) + len(overdue_tasks)
        badge = str(pending_count) if item["page"] == "tasks" and pending_count else None
        sidebar.append({**item, "badge": badge})

    return {
        "authenticated": True,
        "principal": serialize_principal(principal),
        "selected_location_id": selected_location_id,
        "summary": {
            **plant_summary,
            "location_count": len(locations),
            "root_location_count": len(location_tree),
            "due_task_count": len(due_tasks),
            "overdue_task_count": len(overdue_tasks),
        },
        "sidebar": sidebar,
        "system_services": system_services,
        "navigation": {
            "locations": location_tree,
        },
        "tasks": {
            "due": due_tasks,
            "overdue": overdue_tasks,
            "completed": completed_tasks,
        },
    }
