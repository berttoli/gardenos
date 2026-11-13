from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import exists, extract, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.common.forms import optional_str, parse_bool, parse_date, parse_decimal
from app.common.identifiers import compact_code
from app.config import Settings
from app.containers.models import Container
from app.locations.models import Location
from app.observations.models import Observation
from app.plants.models import (
    ACQUISITION_TYPES,
    PLANT_STATUSES,
    Plant,
    PlantContainerHistory,
    PlantIdentifierAlias,
    PlantLocationHistory,
    PlantStatusHistory,
)
from app.taxonomy.models import Taxon


class PlantError(ValueError):
    pass


class PlantNotFound(PlantError):
    pass


def _validate_choice(value: str | None, choices: Sequence[str], field_name: str) -> str:
    normalized = optional_str(value)
    if normalized is None:
        raise PlantError(f"{field_name} is required.")
    if normalized not in choices:
        raise PlantError(f"Invalid {field_name}: {normalized}.")
    return normalized


def _normalize_identifier(identifier: str | None) -> str:
    normalized = optional_str(identifier)
    if normalized is None:
        raise PlantError("display_id is required.")
    return normalized.upper()


def _parse_scientific_name(scientific_name: str) -> tuple[str, str | None]:
    cleaned = scientific_name.strip()
    parts = [part for part in cleaned.split() if part]
    if not parts:
        raise PlantError("scientific_name is required.")
    genus = parts[0]
    species = parts[1] if len(parts) > 1 else None
    return genus, species


def _is_ancestor(candidate: Plant | None, target_id: str) -> bool:
    current = candidate
    seen: set[str] = set()
    while current is not None and current.id not in seen:
        if current.id == target_id:
            return True
        seen.add(current.id)
        current = current.parent_plant
    return False


def _load_related_plant(
    session: Session, related_id: str | None, field_name: str
) -> Plant | None:
    normalized = optional_str(related_id)
    if normalized is None:
        return None
    related = session.get(Plant, normalized)
    if related is None:
        raise PlantError(f"{field_name} {normalized} not found.")
    return related


def _validate_lineage_link(
    session: Session,
    plant: Plant | None,
    related_id: str | None,
    field_name: str,
) -> Plant | None:
    related = _load_related_plant(session, related_id, field_name)
    if plant is None or related is None:
        return related
    if related.id == plant.id:
        raise PlantError(f"{field_name} cannot reference the plant itself.")
    if _is_ancestor(related, plant.id):
        raise PlantError(f"{field_name} cannot create a lineage cycle.")
    return related


def get_or_create_taxon(
    session: Session,
    *,
    scientific_name: str,
    family: str | None = None,
    genus: str | None = None,
    species: str | None = None,
    subspecies: str | None = None,
    variety: str | None = None,
    cultivar: str | None = None,
    common_names: Sequence[str] | None = None,
    native_range: str | None = None,
    hardiness_min: str | None = None,
    hardiness_max: str | None = None,
    notes: str | None = None,
    display_code: str | None = None,
) -> Taxon:
    existing = session.scalar(select(Taxon).where(Taxon.scientific_name == scientific_name.strip()))
    if existing is not None:
        return existing

    inferred_genus, inferred_species = _parse_scientific_name(scientific_name)
    taxon = Taxon(
        family=optional_str(family),
        genus=optional_str(genus) or inferred_genus,
        species=optional_str(species) or inferred_species,
        subspecies=optional_str(subspecies),
        variety=optional_str(variety),
        cultivar=optional_str(cultivar),
        scientific_name=scientific_name.strip(),
        common_names=list(common_names or []),
        native_range=optional_str(native_range),
        hardiness_min=optional_str(hardiness_min),
        hardiness_max=optional_str(hardiness_max),
        notes=optional_str(notes),
        display_code=optional_str(display_code),
    )
    session.add(taxon)
    session.flush()
    return taxon


def _taxon_code(taxon: Taxon | None, scientific_name: str | None) -> str:
    if taxon is not None and taxon.display_code:
        return taxon.display_code.strip().upper()
    source = scientific_name or (taxon.scientific_name if taxon is not None else None)
    if source is None:
        return "UNK"
    return compact_code(source, fallback="UNK", max_length=3 if " " not in source.strip() else 2)


def _cultivar_code(cultivar_name: str | None, taxon: Taxon | None = None) -> str:
    source = cultivar_name or (taxon.cultivar if taxon is not None else None)
    return compact_code(source, fallback="UNK", max_length=2)


def build_display_prefix(
    taxon: Taxon | None,
    *,
    scientific_name: str | None = None,
    cultivar_name: str | None = None,
) -> str:
    return f"{_taxon_code(taxon, scientific_name)}-{_cultivar_code(cultivar_name, taxon)}"


def _display_sequence_from_identifier(prefix: str, identifier: str) -> int | None:
    if not identifier.startswith(f"{prefix}-"):
        return None
    suffix = identifier[len(prefix) + 1 :]
    if not suffix.isdigit():
        return None
    return int(suffix)


def next_display_sequence(session: Session, prefix: str) -> int:
    candidates: list[str] = []
    plant_ids = session.scalars(
        select(Plant.display_id).where(Plant.display_id.like(f"{prefix}-%"))
    ).all()
    alias_ids = session.scalars(
        select(PlantIdentifierAlias.identifier).where(
            PlantIdentifierAlias.identifier.like(f"{prefix}-%")
        ),
    ).all()
    candidates.extend(plant_ids)
    candidates.extend(alias_ids)
    highest = 0
    for identifier in candidates:
        sequence = _display_sequence_from_identifier(prefix, identifier)
        if sequence is not None and sequence > highest:
            highest = sequence
    return highest + 1


def suggest_display_id(
    session: Session,
    *,
    taxon: Taxon | None,
    scientific_name: str | None = None,
    cultivar_name: str | None = None,
    sequence_width: int = 3,
) -> str:
    prefix = build_display_prefix(
        taxon, scientific_name=scientific_name, cultivar_name=cultivar_name
    )
    sequence = next_display_sequence(session, prefix)
    return f"{prefix}-{sequence:0{sequence_width}d}"


def is_display_id_available(
    session: Session,
    display_id: str,
    *,
    exclude_plant_id: str | None = None,
) -> bool:
    normalized = display_id.strip().upper()
    stmt = select(Plant.id).where(func.upper(Plant.display_id) == normalized)
    if exclude_plant_id is not None:
        stmt = stmt.where(Plant.id != exclude_plant_id)
    if session.scalar(stmt) is not None:
        return False

    alias_stmt = select(PlantIdentifierAlias.id).where(
        func.upper(PlantIdentifierAlias.identifier) == normalized
    )
    if session.scalar(alias_stmt) is not None:
        return False
    return True


def get_plant(session: Session, plant_id: str) -> Plant:
    plant = session.scalar(
        select(Plant)
        .where(Plant.id == plant_id)
        .options(
            selectinload(Plant.taxon),
            selectinload(Plant.care_profile),
            selectinload(Plant.current_location),
            selectinload(Plant.container),
            selectinload(Plant.aliases),
            selectinload(Plant.location_history),
            selectinload(Plant.container_history),
            selectinload(Plant.status_history),
            selectinload(Plant.observations).selectinload(Observation.assessment),
            selectinload(Plant.observations).selectinload(Observation.media_assets),
            selectinload(Plant.measurements),
            selectinload(Plant.treatments),
            selectinload(Plant.media_assets),
            selectinload(Plant.propagation_children),
            selectinload(Plant.propagation_descendants),
            selectinload(Plant.task_occurrences),
        ),
    )
    if plant is None:
        raise PlantNotFound(f"Plant {plant_id} not found.")
    return plant


def get_plant_by_display_id(session: Session, display_id: str) -> Plant:
    normalized = display_id.strip().upper()
    plant = session.scalar(
        select(Plant)
        .where(func.upper(Plant.display_id) == normalized)
        .options(
            selectinload(Plant.taxon),
            selectinload(Plant.current_location),
            selectinload(Plant.container),
        ),
    )
    if plant is not None:
        return plant
    alias = session.scalar(
        select(PlantIdentifierAlias).where(
            func.upper(PlantIdentifierAlias.identifier) == normalized
        )
    )
    if alias is not None:
        return get_plant(session, alias.plant_id)
    raise PlantNotFound(f"Plant {display_id} not found.")


def _assign_history_for_creation(session: Session, plant: Plant) -> None:
    session.add(
        PlantStatusHistory(
            plant=plant,
            old_status=None,
            new_status=plant.status,
            changed_at=plant.created_at,
            notes="Initial plant record created.",
        ),
    )
    if plant.current_location_id is not None:
        session.add(
            PlantLocationHistory(
                plant=plant,
                from_location_id=None,
                to_location_id=plant.current_location_id,
                moved_at=plant.created_at,
                notes="Initial placement.",
            ),
        )
    if plant.container_id is not None:
        session.add(
            PlantContainerHistory(
                plant=plant,
                from_container_id=None,
                to_container_id=plant.container_id,
                assigned_at=plant.created_at,
                notes="Initial container assignment.",
            ),
        )


def create_plant(session: Session, settings: Settings, payload: Mapping[str, Any]) -> Plant:
    scientific_name = optional_str(payload.get("scientific_name"))
    taxon_id = optional_str(payload.get("taxon_id"))
    taxon = session.get(Taxon, taxon_id) if taxon_id else None
    if taxon is None and scientific_name:
        taxon = get_or_create_taxon(
            session,
            scientific_name=scientific_name,
            family=optional_str(payload.get("family")),
            genus=optional_str(payload.get("genus")),
            species=optional_str(payload.get("species")),
            subspecies=optional_str(payload.get("subspecies")),
            variety=optional_str(payload.get("variety")),
            cultivar=optional_str(payload.get("taxon_cultivar")),
            common_names=[
                name.strip()
                for name in str(payload.get("common_names", "")).split(",")
                if name.strip()
            ],
            native_range=optional_str(payload.get("native_range")),
            hardiness_min=optional_str(payload.get("hardiness_min")),
            hardiness_max=optional_str(payload.get("hardiness_max")),
            notes=optional_str(payload.get("taxon_notes")),
            display_code=optional_str(payload.get("taxon_display_code")),
        )
    if taxon is None and scientific_name is None:
        raise PlantError("scientific_name or taxon_id is required.")

    cultivar_name = optional_str(payload.get("cultivar_name"))
    display_id = optional_str(payload.get("display_id"))
    parent_plant = _validate_lineage_link(
        session,
        None,
        payload.get("parent_plant_id"),
        "parent_plant_id",
    )
    rootstock_plant = _validate_lineage_link(
        session,
        None,
        payload.get("rootstock_plant_id"),
        "rootstock_plant_id",
    )
    if display_id is None:
        display_id = suggest_display_id(
            session,
            taxon=taxon,
            scientific_name=scientific_name,
            cultivar_name=cultivar_name,
            sequence_width=settings.plant_identifier_sequence_width,
        )
    display_id = _normalize_identifier(display_id)
    if not is_display_id_available(session, display_id):
        raise PlantError(f"Display identifier {display_id} is already in use.")

    plant = Plant(
        display_id=display_id,
        status=_validate_choice(payload.get("status"), PLANT_STATUSES, "status")
        if optional_str(payload.get("status"))
        else "active",
        accession_date=parse_date(payload.get("accession_date")),
        acquisition_type=_validate_choice(
            payload.get("acquisition_type"), ACQUISITION_TYPES, "acquisition_type"
        )
        if optional_str(payload.get("acquisition_type"))
        else "unknown",
        purchase_price=parse_decimal(payload.get("purchase_price")),
        source_name=optional_str(payload.get("source_name")),
        source_reference=optional_str(payload.get("source_reference")),
        notes=optional_str(payload.get("notes")),
        taxon=taxon,
        cultivar_name=cultivar_name,
        common_name=optional_str(payload.get("common_name")),
        care_profile_id=optional_str(payload.get("care_profile_id")),
        current_location_id=optional_str(payload.get("current_location_id")),
        container_id=optional_str(payload.get("container_id")),
        parent_plant=parent_plant,
        rootstock_plant=rootstock_plant,
        is_grafted=parse_bool(payload.get("is_grafted")),
        graft_notes=optional_str(payload.get("graft_notes")),
        is_edible=parse_bool(payload.get("is_edible")),
        is_toxic=parse_bool(payload.get("is_toxic")),
        pollinator_value=parse_bool(payload.get("pollinator_value")),
        wildlife_value=parse_bool(payload.get("wildlife_value")),
    )
    session.add(plant)
    session.flush()
    _assign_history_for_creation(session, plant)
    return plant


def update_plant(
    session: Session, plant: Plant, payload: Mapping[str, Any], settings: Settings
) -> Plant:
    display_id = optional_str(payload.get("display_id"))
    if display_id is not None:
        normalized = _normalize_identifier(display_id)
        if normalized != plant.display_id and not is_display_id_available(
            session, normalized, exclude_plant_id=plant.id
        ):
            raise PlantError(f"Display identifier {normalized} is already in use.")
        if normalized != plant.display_id:
            session.add(
                PlantIdentifierAlias(
                    plant=plant,
                    identifier=plant.display_id,
                    identifier_type="previous_display_id",
                    retired_at=datetime.now(UTC),
                    notes=optional_str(payload.get("display_id_notes")),
                ),
            )
            plant.display_id = normalized

    status = optional_str(payload.get("status"))
    if status is not None and status != plant.status:
        if status not in PLANT_STATUSES:
            raise PlantError(f"Invalid status: {status}.")
        session.add(
            PlantStatusHistory(
                plant=plant,
                old_status=plant.status,
                new_status=status,
                changed_at=datetime.now(UTC),
                notes=optional_str(payload.get("status_notes")),
            ),
        )
        plant.status = status

    accession_date = parse_date(payload.get("accession_date"))
    if "accession_date" in payload:
        plant.accession_date = accession_date

    acquisition_type = optional_str(payload.get("acquisition_type"))
    if acquisition_type is not None:
        if acquisition_type not in ACQUISITION_TYPES:
            raise PlantError(f"Invalid acquisition type: {acquisition_type}.")
        plant.acquisition_type = acquisition_type

    if "purchase_price" in payload:
        plant.purchase_price = cast(Any, parse_decimal(payload.get("purchase_price")))
    for field_name in (
        "source_name",
        "source_reference",
        "notes",
        "cultivar_name",
        "common_name",
        "graft_notes",
    ):
        if field_name in payload:
            setattr(plant, field_name, optional_str(payload.get(field_name)))

    for field_name in (
        "care_profile_id",
        "current_location_id",
        "container_id",
        "parent_plant_id",
        "rootstock_plant_id",
    ):
        if field_name in payload:
            if field_name in {"parent_plant_id", "rootstock_plant_id"}:
                related = _validate_lineage_link(
                    session,
                    plant,
                    payload.get(field_name),
                    field_name,
                )
                setattr(plant, field_name, related.id if related is not None else None)
            else:
                setattr(plant, field_name, optional_str(payload.get(field_name)))

    for field_name in ("is_grafted", "is_edible", "is_toxic", "pollinator_value", "wildlife_value"):
        if field_name in payload:
            setattr(plant, field_name, parse_bool(payload.get(field_name)))

    taxon_id = optional_str(payload.get("taxon_id"))
    if taxon_id is not None:
        taxon = session.get(Taxon, taxon_id)
        if taxon is None:
            raise PlantError(f"Taxon {taxon_id} not found.")
        plant.taxon = taxon
    elif "scientific_name" in payload and optional_str(payload.get("scientific_name")):
        taxon = get_or_create_taxon(
            session,
            scientific_name=optional_str(payload.get("scientific_name")) or "",
            family=optional_str(payload.get("family")),
            genus=optional_str(payload.get("genus")),
            species=optional_str(payload.get("species")),
            subspecies=optional_str(payload.get("subspecies")),
            variety=optional_str(payload.get("variety")),
            cultivar=optional_str(payload.get("taxon_cultivar")),
            display_code=optional_str(payload.get("taxon_display_code")),
        )
        plant.taxon = taxon

    session.add(plant)
    return plant


def move_plant(
    session: Session,
    plant: Plant,
    *,
    location_id: str | None,
    container_id: str | None,
    notes: str | None = None,
    performed_by: str | None = None,
) -> Plant:
    now = datetime.now(UTC)
    if location_id != plant.current_location_id:
        session.add(
            PlantLocationHistory(
                plant=plant,
                from_location_id=plant.current_location_id,
                to_location_id=location_id,
                moved_at=now,
                notes=notes,
                performed_by=performed_by,
            ),
        )
        plant.current_location_id = location_id
    if container_id != plant.container_id:
        session.add(
            PlantContainerHistory(
                plant=plant,
                from_container_id=plant.container_id,
                to_container_id=container_id,
                assigned_at=now,
                notes=notes,
            ),
        )
        plant.container_id = container_id
    session.add(plant)
    return plant


def archive_plant(session: Session, plant: Plant, *, notes: str | None = None) -> Plant:
    if plant.archived_at is not None:
        return plant
    now = datetime.now(UTC)
    session.add(
        PlantStatusHistory(
            plant=plant,
            old_status=plant.status,
            new_status="archived",
            changed_at=now,
            notes=notes,
        ),
    )
    plant.status = "archived"
    plant.archived_at = now
    session.add(plant)
    return plant


def restore_plant(session: Session, plant: Plant, *, notes: str | None = None) -> Plant:
    if plant.archived_at is None:
        return plant
    now = datetime.now(UTC)
    restored_status = "active" if plant.status == "archived" else plant.status
    session.add(
        PlantStatusHistory(
            plant=plant,
            old_status=plant.status,
            new_status=restored_status,
            changed_at=now,
            notes=notes,
        ),
    )
    plant.status = restored_status
    plant.archived_at = None
    session.add(plant)
    return plant


def list_plants(
    session: Session,
    *,
    query: str | None = None,
    status: str | None = None,
    location_id: str | None = None,
    acquisition_year: int | None = None,
    grafted: bool | None = None,
    edible: bool | None = None,
    toxic: bool | None = None,
    pollinator_value: bool | None = None,
    taxonomy_id: str | None = None,
) -> list[Plant]:
    stmt = (
        select(Plant)
        .options(
            selectinload(Plant.taxon),
            selectinload(Plant.current_location),
            selectinload(Plant.container),
            selectinload(Plant.aliases),
        )
        .order_by(Plant.created_at.desc())
    )
    if query:
        term = f"%{query.strip()}%"
        alias_exists = exists(
            select(1).where(
                PlantIdentifierAlias.plant_id == Plant.id,
                func.lower(PlantIdentifierAlias.identifier).like(func.lower(term)),
            ),
        )
        stmt = stmt.where(
            or_(
                func.lower(Plant.display_id).like(func.lower(term)),
                func.lower(Plant.cultivar_name).like(func.lower(term)),
                func.lower(Plant.common_name).like(func.lower(term)),
                func.lower(Plant.source_name).like(func.lower(term)),
                func.lower(Plant.source_reference).like(func.lower(term)),
                alias_exists,
                exists(
                    select(1).where(
                        Taxon.id == Plant.taxon_id,
                        or_(
                            func.lower(Taxon.scientific_name).like(func.lower(term)),
                            func.lower(Taxon.genus).like(func.lower(term)),
                            func.lower(Taxon.species).like(func.lower(term)),
                        ),
                    ),
                ),
                exists(
                    select(1).where(
                        Location.id == Plant.current_location_id,
                        func.lower(Location.name).like(func.lower(term)),
                    ),
                ),
                exists(
                    select(1).where(
                        Container.id == Plant.container_id,
                        func.lower(Container.identifier).like(func.lower(term)),
                    ),
                ),
            ),
        )
    if status:
        stmt = stmt.where(Plant.status == status)
    if location_id:
        stmt = stmt.where(Plant.current_location_id == location_id)
    if acquisition_year is not None:
        stmt = stmt.where(extract("year", Plant.accession_date) == acquisition_year)
    if grafted is not None:
        stmt = stmt.where(Plant.is_grafted.is_(grafted))
    if edible is not None:
        stmt = stmt.where(Plant.is_edible.is_(edible))
    if toxic is not None:
        stmt = stmt.where(Plant.is_toxic.is_(toxic))
    if pollinator_value is not None:
        stmt = stmt.where(Plant.pollinator_value.is_(pollinator_value))
    if taxonomy_id:
        stmt = stmt.where(Plant.taxon_id == taxonomy_id)
    return list(session.scalars(stmt).unique().all())


def plant_summary(plant: Plant) -> dict[str, Any]:
    return {
        "id": plant.id,
        "display_id": plant.display_id,
        "status": plant.status,
        "scientific_name": plant.taxon.scientific_name if plant.taxon else None,
        "cultivar_name": plant.cultivar_name or (plant.taxon.cultivar if plant.taxon else None),
        "common_name": plant.common_name,
        "current_location": plant.current_location.name if plant.current_location else None,
        "container": plant.container.identifier if plant.container else None,
        "source_name": plant.source_name,
        "archived_at": plant.archived_at.isoformat() if plant.archived_at else None,
    }


def _timeline_entry(
    kind: str, at: datetime, title: str, summary: str | None = None, notes: str | None = None
) -> dict[str, Any]:
    if at.tzinfo is None or at.utcoffset() is None:
        at = at.replace(tzinfo=UTC)
    else:
        at = at.astimezone(UTC)
    return {
        "kind": kind,
        "at": at,
        "title": title,
        "summary": summary,
        "notes": notes,
    }


def build_plant_timeline(session: Session, plant: Plant) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    timeline.append(
        _timeline_entry(
            "onboarding",
            plant.created_at,
            "Plant record created",
            summary=f"{plant.display_id}",
            notes=plant.notes,
        ),
    )
    for history in plant.status_history:
        timeline.append(
            _timeline_entry(
                "status",
                history.changed_at,
                f"Status changed to {history.new_status}",
                summary=history.old_status,
                notes=history.notes,
            ),
        )
    for history in plant.location_history:
        timeline.append(
            _timeline_entry(
                "move",
                history.moved_at,
                "Moved plant",
                summary=(
                    f"{history.from_location_id or 'unassigned'} -> "
                    f"{history.to_location_id or 'unassigned'}"
                ),
                notes=history.notes,
            ),
        )
    for history in plant.container_history:
        timeline.append(
            _timeline_entry(
                "container",
                history.assigned_at,
                "Container changed",
                summary=(
                    f"{history.from_container_id or 'unassigned'} -> "
                    f"{history.to_container_id or 'unassigned'}"
                ),
                notes=history.notes,
            ),
        )
    for observation in plant.observations:
        timeline.append(
            _timeline_entry(
                "observation",
                observation.observed_at,
                f"Observation: {observation.observation_type}",
                summary=observation.summary,
                notes=observation.notes,
            ),
        )
        if observation.assessment is not None:
            score_value = (
                observation.assessment.manual_score
                or observation.assessment.calculated_score
                or ""
            )
            timeline.append(
                _timeline_entry(
                    "health",
                    observation.observed_at,
                    "Health assessment recorded",
                    summary=f"Score {score_value}".strip(),
                    notes=observation.assessment.symptoms,
                ),
            )
    for measurement in plant.measurements:
        timeline.append(
            _timeline_entry(
                "measurement",
                measurement.measured_at,
                "Measurement recorded",
                summary=f"Height {measurement.height or 'n/a'}",
                notes=measurement.notes,
            ),
        )
    for treatment in plant.treatments:
        timeline.append(
            _timeline_entry(
                "treatment",
                treatment.applied_at,
                f"Treatment: {treatment.treatment_type}",
                summary=treatment.product_name,
                notes=treatment.notes,
            ),
        )
    for media_asset in plant.media_assets:
        timestamp = media_asset.captured_at or media_asset.created_at
        timeline.append(
            _timeline_entry(
                "media",
                timestamp,
                f"Photo: {media_asset.view_type}",
                summary=media_asset.caption or media_asset.original_filename,
                notes=media_asset.file_path,
            ),
        )
    for propagation in plant.propagation_children:
        timeline.append(
            _timeline_entry(
                "propagation",
                propagation.started_at,
                f"Propagation started: {propagation.method}",
                summary=propagation.status,
                notes=propagation.success_notes or propagation.failure_notes,
            ),
        )
        if propagation.separated_at is not None:
            timeline.append(
                _timeline_entry(
                    "propagation",
                    propagation.separated_at,
                    "Propagation separated",
                    summary=propagation.new_plant_id,
                ),
            )
    for occurrence in plant.task_occurrences:
        timestamp = occurrence.completed_at or occurrence.skipped_at or occurrence.scheduled_for
        title = (
            "Task completed"
            if occurrence.completed_at
            else "Task skipped"
            if occurrence.skipped_at
            else "Task scheduled"
        )
        timeline.append(
            _timeline_entry(
                "task",
                timestamp,
                title,
                summary=occurrence.task_definition.title if occurrence.task_definition else None,
                notes=occurrence.completion_notes,
            ),
        )
    timeline.sort(key=lambda item: item["at"])
    return timeline


def latest_observation(plant: Plant) -> Observation | None:
    if not plant.observations:
        return None
    return max(plant.observations, key=lambda item: item.observed_at)


def latest_health_score(plant: Plant) -> float | None:
    observation = latest_observation(plant)
    if observation is None:
        return None
    if observation.assessment is not None:
        score = observation.assessment.manual_score or observation.assessment.calculated_score
        return float(score) if score is not None else None
    return (
        float(observation.overall_health_score)
        if observation.overall_health_score is not None
        else None
    )


def recent_plants(session: Session, limit: int = 8) -> list[Plant]:
    stmt = (
        select(Plant)
        .options(selectinload(Plant.taxon), selectinload(Plant.current_location))
        .order_by(Plant.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def plants_in_quarantine(session: Session, limit: int = 12) -> list[Plant]:
    stmt = (
        select(Plant)
        .where(or_(Plant.status == "quarantine", Location.location_type == "quarantine"))
        .outerjoin(Location, Location.id == Plant.current_location_id)
        .options(selectinload(Plant.taxon), selectinload(Plant.current_location))
        .order_by(Plant.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).unique().all())
