from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.common.forms import optional_str, parse_datetime
from app.common.ids import new_uuid_str
from app.config import Settings
from app.plants.models import Plant
from app.plants.services import create_plant, get_plant
from app.propagation.models import PROPAGATION_METHODS, PropagationEvent


class PropagationError(ValueError):
    pass


PROPAGATION_STATUSES = ("in_progress", "rooted", "separated", "failed", "completed")


def _validate_choice(value: str | None, choices: tuple[str, ...], field_name: str) -> str:
    normalized = optional_str(value)
    if normalized is None:
        raise PropagationError(f"{field_name} is required.")
    if normalized not in choices:
        raise PropagationError(f"Invalid {field_name}: {normalized}.")
    return normalized


def _is_ancestor(candidate: Plant | None, target_id: str) -> bool:
    current = candidate
    seen: set[str] = set()
    while current is not None and current.id not in seen:
        if current.id == target_id:
            return True
        seen.add(current.id)
        current = current.parent_plant
    return False


def start_propagation(
    session: Session, source_plant: Plant, payload: Mapping[str, Any]
) -> PropagationEvent:
    method = _validate_choice(payload.get("method"), PROPAGATION_METHODS, "method")
    event = PropagationEvent(
        id=new_uuid_str(),
        source_plant=source_plant,
        method=method,
        started_at=parse_datetime(payload.get("started_at")) or datetime.now(UTC),
        status=optional_str(payload.get("status")) or "in_progress",
        material_type=optional_str(payload.get("material_type")),
        cutting_length=None,
        cutting_diameter=None,
        node_count=None,
        medium=optional_str(payload.get("medium")),
        hormone=optional_str(payload.get("hormone")),
        environment=optional_str(payload.get("environment")),
        success_notes=optional_str(payload.get("success_notes")),
        failure_notes=optional_str(payload.get("failure_notes")),
    )
    session.add(event)
    session.flush()
    return event


def complete_propagation(
    session: Session,
    settings: Settings,
    source_plant: Plant,
    event: PropagationEvent,
    payload: Mapping[str, Any],
) -> Plant:
    if event.source_plant_id != source_plant.id:
        raise PropagationError("Propagation event does not belong to the source plant.")

    if event.new_plant_id is not None:
        new_plant = get_plant(session, event.new_plant_id)
    else:
        scientific_name = source_plant.taxon.scientific_name if source_plant.taxon else None
        if scientific_name is None:
            raise PropagationError("Source plant needs a taxon to create a propagated plant.")
        plant_payload: dict[str, Any] = {
            "scientific_name": scientific_name,
            "family": source_plant.taxon.family if source_plant.taxon else None,
            "genus": source_plant.taxon.genus if source_plant.taxon else None,
            "species": source_plant.taxon.species if source_plant.taxon else None,
            "subspecies": source_plant.taxon.subspecies if source_plant.taxon else None,
            "variety": source_plant.taxon.variety if source_plant.taxon else None,
            "taxon_cultivar": source_plant.taxon.cultivar if source_plant.taxon else None,
            "cultivar_name": source_plant.cultivar_name,
            "common_name": source_plant.common_name,
            "status": optional_str(payload.get("status")) or "quarantine",
            "acquisition_type": "cutting"
            if event.method.endswith("cutting")
            else "division"
            if event.method == "division"
            else "graft"
            if event.method in {"graft", "approach_graft"}
            else "seed",
            "notes": optional_str(payload.get("notes"))
            or f"Propagation from {source_plant.display_id}.",
            "current_location_id": optional_str(payload.get("current_location_id"))
            or source_plant.current_location_id,
            "container_id": optional_str(payload.get("container_id")),
            "parent_plant_id": source_plant.id,
            "rootstock_plant_id": source_plant.rootstock_plant_id
            if source_plant.is_grafted
            else None,
            "is_grafted": source_plant.is_grafted,
            "graft_notes": source_plant.graft_notes,
            "is_edible": source_plant.is_edible,
            "is_toxic": source_plant.is_toxic,
            "pollinator_value": source_plant.pollinator_value,
            "wildlife_value": source_plant.wildlife_value,
        }
        new_plant = create_plant(session, settings, plant_payload)
        event.new_plant = new_plant

    event.status = optional_str(payload.get("status")) or "completed"
    event.separated_at = parse_datetime(payload.get("separated_at")) or datetime.now(UTC)
    event.rooted_at = (
        parse_datetime(payload.get("rooted_at")) or event.rooted_at or event.separated_at
    )
    event.success_notes = optional_str(payload.get("success_notes")) or event.success_notes
    event.failure_notes = optional_str(payload.get("failure_notes"))
    session.add_all([event, new_plant])
    session.flush()
    return new_plant


def fail_propagation(
    session: Session, event: PropagationEvent, *, notes: str | None = None
) -> PropagationEvent:
    event.status = "failed"
    event.failed_at = datetime.now(UTC)
    event.failure_notes = notes or event.failure_notes
    session.add(event)
    session.flush()
    return event


def lineage_summary(session: Session, plant: Plant) -> dict[str, list[dict[str, Any]]]:
    ancestors: list[dict[str, Any]] = []
    current = plant.parent_plant
    seen: set[str] = set()
    while current is not None and current.id not in seen:
        ancestors.append(
            {
                "id": current.id,
                "display_id": current.display_id,
                "status": current.status,
                "scientific_name": current.taxon.scientific_name if current.taxon else None,
            },
        )
        seen.add(current.id)
        current = current.parent_plant
    descendants = [
        {
            "id": event.new_plant.id if event.new_plant else None,
            "display_id": event.new_plant.display_id if event.new_plant else None,
            "method": event.method,
            "status": event.status,
        }
        for event in session.scalars(
            select(PropagationEvent)
            .where(PropagationEvent.source_plant_id == plant.id)
            .options(selectinload(PropagationEvent.new_plant))
            .order_by(PropagationEvent.started_at.asc()),
        ).all()
    ]
    return {"ancestors": ancestors, "descendants": descendants}
