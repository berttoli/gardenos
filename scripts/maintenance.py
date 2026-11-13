from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from secrets import token_hex
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.access.services import ensure_default_access
from app.auth.services import ensure_admin_user
from app.care.services import initial_tasks_for_plant
from app.config import Settings
from app.containers.models import Container
from app.database import Base
from app.labels.services import ensure_default_label_templates
from app.locations.models import Location
from app.media.services import store_upload
from app.observations.services import create_observation, record_measurement
from app.plants.models import Plant
from app.plants.services import (
    PlantNotFound,
    create_plant,
    get_plant_by_display_id,
)
from app.propagation.models import PropagationEvent
from app.propagation.services import complete_propagation, start_propagation
from app.taxonomy.models import CareProfile, Taxon
from app.warehouse.export import export_warehouse_snapshot
from scripts.common import runtime


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(tar: tarfile.TarFile, target_dir: Path) -> None:
    base = target_dir.resolve()
    for member in tar.getmembers():
        member_path = (base / member.name).resolve()
        if base not in member_path.parents and member_path != base:
            raise ValueError(f"Unsafe path in backup archive: {member.name}")
    tar.extractall(target_dir)


def _schema_version(session: Session) -> str | None:
    try:
        row = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    except Exception:
        return None
    return str(row) if row is not None else None


def _manifest_files(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    if not root.exists():
        return records
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256_path(path),
            },
        )
    return records


def _warehouse_database_file(settings: Settings) -> Path:
    return Path(settings.warehouse_db_path).expanduser().resolve()


def _postgresql_client_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        return database_url
    return str(url.set(drivername="postgresql"))


def create_backup(output_path: Path | None = None) -> Path:
    settings, engine, session_factory = runtime()
    backup_root = Path(settings.backup_root).expanduser().resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    target = output_path or backup_root / safe_backup_name()

    with session_factory() as session:
        schema_version = _schema_version(session)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        database_backend = "postgresql"
        db_export = tmp_dir / "database.dump"
        subprocess.run(
            [
                "pg_dump",
                "--dbname",
                _postgresql_client_url(settings.database_url),
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(db_export),
            ],
            check=True,
        )

        warehouse_export = tmp_dir / "warehouse.duckdb"
        export_warehouse_snapshot(session_factory, warehouse_export, settings=settings)

        media_root = Path(settings.media_root).expanduser().resolve()
        media_export = tmp_dir / "media"
        if media_root.exists():
            shutil.copytree(media_root, media_export)
        else:
            media_export.mkdir(parents=True, exist_ok=True)

        manifest = {
            "app_version": "0.1.0",
            "created_at": datetime.now(UTC).isoformat(),
            "schema_version": schema_version,
            "database_backend": database_backend,
            "database_file": db_export.name,
            "database_sha256": _sha256_path(db_export),
            "warehouse_backend": "duckdb",
            "warehouse_file": warehouse_export.name,
            "warehouse_sha256": _sha256_path(warehouse_export),
            "warehouse_db_path": settings.warehouse_db_path,
            "media_root": media_root.as_posix(),
            "media_files": _manifest_files(media_export),
        }
        manifest_path = tmp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        with tarfile.open(target, "w:gz") as archive:
            archive.add(manifest_path, arcname="manifest.json")
            archive.add(db_export, arcname=db_export.name)
            archive.add(warehouse_export, arcname=warehouse_export.name)
            archive.add(media_export, arcname="media")

    engine.dispose()
    return target


def verify_backup(archive_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with tarfile.open(archive_path, "r:gz") as archive:
            _safe_extract(archive, tmp_dir)

        manifest = json.loads((tmp_dir / "manifest.json").read_text(encoding="utf-8"))
        database_file = tmp_dir / str(manifest["database_file"])
        if _sha256_path(database_file) != manifest["database_sha256"]:
            raise RuntimeError("Database hash mismatch.")

        warehouse_file_name = manifest.get("warehouse_file")
        if warehouse_file_name is not None:
            warehouse_file = tmp_dir / str(warehouse_file_name)
            if not warehouse_file.exists():
                raise RuntimeError("Missing warehouse file in backup archive.")
            expected_warehouse_sha = manifest.get("warehouse_sha256")
            if expected_warehouse_sha and _sha256_path(warehouse_file) != expected_warehouse_sha:
                raise RuntimeError("Warehouse hash mismatch.")

        media_root = tmp_dir / "media"
        expected_files = {item["path"]: item["sha256"] for item in manifest.get("media_files", [])}
        for path in expected_files:
            file_path = media_root / path
            if not file_path.exists():
                raise RuntimeError(f"Missing media file in backup: {path}")
            if _sha256_path(file_path) != expected_files[path]:
                raise RuntimeError(f"Media hash mismatch: {path}")

        return manifest


def restore_backup(archive_path: Path) -> dict[str, Any]:
    settings, engine, session_factory = runtime()
    manifest = verify_backup(archive_path)
    if manifest.get("database_backend") != "postgresql":
        raise RuntimeError("Only PostgreSQL backup archives are supported.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with tarfile.open(archive_path, "r:gz") as archive:
            _safe_extract(archive, tmp_dir)

        database_file = tmp_dir / str(manifest["database_file"])
        subprocess.run(
            [
                "pg_restore",
                "--dbname",
                _postgresql_client_url(settings.database_url),
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-acl",
                str(database_file),
            ],
            check=True,
        )

        warehouse_file_name = manifest.get("warehouse_file")
        if warehouse_file_name is not None:
            warehouse_file = tmp_dir / str(warehouse_file_name)
            target_warehouse = _warehouse_database_file(settings)
            target_warehouse.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(warehouse_file, target_warehouse)

        media_root = Path(settings.media_root).expanduser().resolve()
        source_media = tmp_dir / "media"
        if source_media.exists():
            shutil.copytree(source_media, media_root, dirs_exist_ok=True)

    with session_factory() as session:
        session.rollback()
    engine.dispose()
    return manifest


CARE_PROFILE_DATA: tuple[dict[str, Any], ...] = (
    {
        "name": "Japanese maple",
        "watering_guidance": "Keep evenly moist; avoid drying out between waterings.",
        "sun_guidance": "Morning sun and afternoon shade are ideal.",
        "soil_guidance": "Use well-drained, slightly acidic soil.",
        "warning_notes": "Sensitive to drought and hot wind.",
        "preferred_sun": "part shade",
        "moisture_preference": "evenly moist",
    },
    {
        "name": "Willow",
        "watering_guidance": "Water generously and do not allow the root zone to dry completely.",
        "sun_guidance": "Full sun to light shade.",
        "soil_guidance": "Moist, fertile soil.",
        "warning_notes": "Fast growth and high water use.",
        "preferred_sun": "full sun",
        "moisture_preference": "wet",
    },
    {
        "name": "Fruit tree",
        "watering_guidance": "Deep water during establishment and dry spells.",
        "sun_guidance": "Full sun.",
        "soil_guidance": "Well-drained soil with compost.",
        "warning_notes": "Watch for graft unions and rootstock shoots.",
        "preferred_sun": "full sun",
        "moisture_preference": "moderate",
    },
    {
        "name": "Vegetable annual",
        "watering_guidance": "Keep soil evenly moist and feed lightly.",
        "sun_guidance": "Full sun.",
        "soil_guidance": "Rich, fertile, well-drained soil.",
        "warning_notes": "Short lived and responsive to heat stress.",
        "preferred_sun": "full sun",
        "moisture_preference": "moderate",
    },
    {
        "name": "Pollinator perennial",
        "watering_guidance": "Water during establishment and extended drought.",
        "sun_guidance": "Full sun with good air movement.",
        "soil_guidance": "Average garden soil.",
        "warning_notes": "Deadhead spent blooms to extend flowering.",
        "preferred_sun": "full sun",
        "moisture_preference": "average",
    },
    {
        "name": "Container plant",
        "watering_guidance": "Monitor moisture closely; containers dry quickly.",
        "sun_guidance": "Match exposure to species needs.",
        "soil_guidance": "Free-draining potting mix.",
        "warning_notes": "Check drainage holes and repot as roots fill the container.",
        "preferred_sun": "variable",
        "moisture_preference": "container monitored",
    },
)

LOCATION_DATA: tuple[dict[str, Any], ...] = (
    {"name": "Property", "location_type": "property"},
    {"name": "Quarantine Bench", "location_type": "quarantine"},
    {"name": "Recovery Bench", "location_type": "bench"},
    {"name": "Orchard Row", "location_type": "orchard"},
    {"name": "Vegetable Bed", "location_type": "bed"},
    {"name": "Pollinator Border", "location_type": "bed"},
)

CONTAINER_DATA: tuple[dict[str, Any], ...] = (
    {"identifier": "Loop Pot A", "container_type": "loop", "material": "plastic"},
    {"identifier": "Nursery Pot 10in", "container_type": "pot", "material": "plastic"},
    {"identifier": "Grow Bag 5gal", "container_type": "bag", "material": "fabric"},
)

PLANT_DATA: tuple[dict[str, Any], ...] = (
    {
        "display_id": "AP-GT-001",
        "scientific_name": "Acer palmatum",
        "taxon_display_code": "AP",
        "cultivar_name": "Garnet Tower",
        "common_name": "Japanese maple",
        "status": "quarantine",
        "acquisition_type": "purchased",
        "source_name": "Maple House Nursery",
        "source_reference": "MAPLE-2026-001",
        "current_location_name": "Quarantine Bench",
        "container_identifier": "Loop Pot A",
        "notes": "Primary specimen for the label and propagation demos.",
    },
    {
        "display_id": "AP-HR-001",
        "scientific_name": "Acer palmatum",
        "taxon_display_code": "AP",
        "cultivar_name": "Hefner's Red",
        "common_name": "Japanese maple",
        "status": "active",
        "acquisition_type": "gifted",
        "source_name": "Friend exchange",
        "source_reference": "FRIEND-2026-014",
        "current_location_name": "Recovery Bench",
        "container_identifier": "Nursery Pot 10in",
        "notes": "Shows the naming and search flow.",
    },
    {
        "display_id": "SAL-UNK-001",
        "scientific_name": "Salix babylonica",
        "taxon_display_code": "SAL",
        "common_name": "Willow specimen",
        "status": "active",
        "acquisition_type": "found",
        "source_name": "River edge",
        "source_reference": "FIELD-2026-001",
        "current_location_name": "Orchard Row",
        "container_identifier": "Grow Bag 5gal",
        "notes": "Example willow specimen.",
    },
    {
        "display_id": "MAL-UNK-001",
        "scientific_name": "Malus domestica",
        "taxon_display_code": "MAL",
        "common_name": "Fruit tree",
        "status": "active",
        "acquisition_type": "transplanted",
        "source_name": "Old orchard",
        "source_reference": "ORCH-2026-009",
        "current_location_name": "Orchard Row",
        "container_identifier": None,
        "notes": "Fruit tree example for the dashboard.",
    },
    {
        "display_id": "SOL-UNK-001",
        "scientific_name": "Solanum lycopersicum",
        "taxon_display_code": "SOL",
        "common_name": "Vegetable crop",
        "status": "active",
        "acquisition_type": "seed-grown",
        "source_name": "Seed packet",
        "source_reference": "SEED-2026-003",
        "current_location_name": "Vegetable Bed",
        "container_identifier": None,
        "notes": "Annual crop example.",
    },
    {
        "display_id": "ECH-UNK-001",
        "scientific_name": "Echinacea purpurea",
        "taxon_display_code": "ECH",
        "common_name": "Pollinator plant",
        "status": "active",
        "acquisition_type": "purchased",
        "source_name": "Native plant nursery",
        "source_reference": "NATIVE-2026-007",
        "current_location_name": "Pollinator Border",
        "container_identifier": None,
        "notes": "Pollinator support example.",
    },
)


def _ensure_care_profile(session: Session, payload: dict[str, Any]) -> CareProfile:
    existing = session.scalar(select(CareProfile).where(CareProfile.name == payload["name"]))
    if existing is not None:
        return existing
    profile = CareProfile(**payload)
    session.add(profile)
    session.flush()
    return profile


def _ensure_location(
    session: Session,
    payload: dict[str, Any],
    parent: Location | None = None,
) -> Location:
    existing = session.scalar(select(Location).where(Location.name == payload["name"]))
    if existing is not None:
        return existing
    location = Location(parent=parent, **payload)
    session.add(location)
    session.flush()
    return location


def _ensure_container(session: Session, payload: dict[str, Any]) -> Container:
    existing = session.scalar(
        select(Container).where(Container.identifier == payload["identifier"])
    )
    if existing is not None:
        return existing
    container = Container(**payload)
    session.add(container)
    session.flush()
    return container


def _ensure_taxon(session: Session, payload: dict[str, Any]) -> Taxon:
    from app.plants.services import get_or_create_taxon

    return get_or_create_taxon(
        session,
        scientific_name=payload["scientific_name"],
        genus=payload.get("genus"),
        species=payload.get("species"),
        cultivar=payload.get("taxon_cultivar"),
        display_code=payload.get("taxon_display_code"),
        common_names=[payload["common_name"]] if payload.get("common_name") else None,
    )


def _placeholder_media(filename: str, label: str) -> SimpleNamespace:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600">'
        '<rect width="800" height="600" fill="#f3efe7"/>'
        '<rect x="24" y="24" width="752" height="552" fill="none" '
        'stroke="#1f1a17" stroke-width="8"/>'
        f'<text x="400" y="300" text-anchor="middle" font-family="monospace" '
        f'font-size="42" fill="#1f1a17">{label}</text>'
        "</svg>"
    )
    return SimpleNamespace(
        file=BytesIO(svg.encode("utf-8")),
        filename=filename,
        content_type="image/svg+xml",
    )


def _ensure_plant(
    session: Session,
    settings: Settings,
    payload: dict[str, Any],
    *,
    current_location: Location | None,
    container: Container | None,
) -> Plant:
    try:
        return get_plant_by_display_id(session, payload["display_id"])
    except PlantNotFound:
        plant_payload = {
            "display_id": payload["display_id"],
            "scientific_name": payload["scientific_name"],
            "taxon_display_code": payload["taxon_display_code"],
            "cultivar_name": payload.get("cultivar_name"),
            "common_name": payload.get("common_name"),
            "status": payload["status"],
            "acquisition_type": payload["acquisition_type"],
            "source_name": payload.get("source_name"),
            "source_reference": payload.get("source_reference"),
            "current_location_id": current_location.id if current_location else None,
            "container_id": container.id if container else None,
            "notes": payload.get("notes"),
        }
        return create_plant(session, settings, plant_payload)


def seed_database() -> dict[str, int]:
    settings, engine, session_factory = runtime()
    Base.metadata.create_all(engine)
    counts = {
        "care_profiles": 0,
        "locations": 0,
        "containers": 0,
        "plants": 0,
        "access_permissions": 0,
        "access_roles": 0,
        "access_groups": 0,
        "access_service_accounts": 0,
    }

    with session_factory() as session:
        admin_user = ensure_admin_user(session, settings)
        access_counts = ensure_default_access(session, admin_user=admin_user)
        ensure_default_label_templates(session)
        counts["access_permissions"] = access_counts["permissions"]
        counts["access_roles"] = access_counts["roles"]
        counts["access_groups"] = access_counts["groups"]
        counts["access_service_accounts"] = access_counts["service_accounts"]
        care_profiles = {
            profile["name"]: _ensure_care_profile(session, profile) for profile in CARE_PROFILE_DATA
        }
        counts["care_profiles"] = len(care_profiles)

        locations = {
            payload["name"]: _ensure_location(session, payload) for payload in LOCATION_DATA
        }
        counts["locations"] = len(locations)

        containers = {
            payload["identifier"]: _ensure_container(session, payload) for payload in CONTAINER_DATA
        }
        counts["containers"] = len(containers)

        plants: dict[str, Plant] = {}
        for payload in PLANT_DATA:
            taxon = _ensure_taxon(session, payload)
            current_location = locations.get(payload.get("current_location_name", ""))
            container_identifier = payload.get("container_identifier")
            container = containers.get(container_identifier) if container_identifier else None
            plant = _ensure_plant(
                session,
                settings,
                payload,
                current_location=current_location,
                container=container,
            )
            plant.taxon = taxon
            plant.care_profile = care_profiles.get(
                "Japanese maple"
                if payload["scientific_name"] == "Acer palmatum"
                else "Willow"
                if payload["scientific_name"].startswith("Salix")
                else "Fruit tree"
                if payload["scientific_name"] == "Malus domestica"
                else "Vegetable annual"
                if payload["scientific_name"] == "Solanum lycopersicum"
                else "Pollinator perennial"
            )
            if current_location is not None:
                plant.current_location = current_location
            if container is not None:
                plant.container = container
            session.add(plant)
            plants[payload["display_id"]] = plant
            counts["plants"] += 1

        garnet = plants["AP-GT-001"]
        if not garnet.observations:
            create_observation(
                session,
                garnet,
                {
                    "observation_type": "shipping_arrival",
                    "summary": "Arrived with slight leaf dryness and minor shipping scuffing.",
                    "notes": "Inspect graft union and water status on arrival.",
                    "observer": "Seed script",
                    "assessment": {
                        "leaf_color": 7,
                        "leaf_integrity": 8,
                        "leaf_density": 7,
                        "new_growth": 6,
                        "branch_vigor": 8,
                        "stem_bark_health": 8,
                        "root_vigor": 7,
                        "hydration": 6,
                        "pest_freedom": 10,
                        "disease_freedom": 10,
                        "overall_vigor": 7,
                    },
                },
            )
        if not garnet.measurements:
            record_measurement(
                session,
                garnet,
                {
                    "height": 92,
                    "canopy_width": 64,
                    "trunk_diameter": 18,
                    "soil_moisture": 42,
                    "soil_ph": 6.2,
                    "notes": "Baseline nursery measurement.",
                },
            )
        if not garnet.media_assets:
            store_upload(
                session,
                settings,
                garnet,
                _placeholder_media("garnet-tower.svg", "AP-GT-001"),
                view_type="whole_plant",
                caption="Seed placeholder photo",
            )
        if not garnet.task_occurrences:
            initial_tasks_for_plant(session, garnet)

        if not session.scalar(
            select(PropagationEvent).where(PropagationEvent.source_plant_id == garnet.id),
        ):
            event = start_propagation(
                session,
                garnet,
                {
                    "method": "air_layer",
                    "status": "in_progress",
                    "success_notes": "Starting air-layer lineage example.",
                },
            )
            complete_propagation(
                session,
                settings,
                garnet,
                event,
                {
                    "status": "completed",
                    "separated_at": datetime.now(UTC).isoformat(),
                    "rooted_at": datetime.now(UTC).isoformat(),
                    "success_notes": "Air layer rooted successfully.",
                },
            )

        session.commit()
    engine.dispose()
    return counts


def safe_backup_name(prefix: str = "garden-os-backup") -> str:
    return f"{prefix}-{datetime.now(UTC):%Y%m%d%H%M%S}-{token_hex(4)}.tar.gz"


def cli_backup(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a Garden OS backup archive.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    target = create_backup(args.output)
    print(target)
    return 0


def cli_verify(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a Garden OS backup archive.")
    parser.add_argument("backup", type=Path)
    args = parser.parse_args(argv)
    manifest = verify_backup(args.backup)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def cli_restore(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restore a Garden OS backup archive.")
    parser.add_argument("backup", type=Path)
    args = parser.parse_args(argv)
    manifest = restore_backup(args.backup)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def cli_seed(argv: list[str] | None = None) -> int:
    del argv
    summary = seed_database()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0
