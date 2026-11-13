from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.lite.config import LiteSettings
from app.lite.store import GardenStore


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


def build_store(settings: LiteSettings) -> GardenStore:
    store = GardenStore(settings.database_path)
    store.initialize(seed=settings.seed_on_startup)
    return store


def seed_database(settings: LiteSettings) -> dict[str, Any]:
    store = GardenStore(settings.database_path)
    store.initialize(seed=True)
    return store.dashboard()


def create_backup(settings: LiteSettings, output_path: Path | None = None) -> Path:
    store = GardenStore(settings.database_path)
    store.initialize(seed=False)
    backup_root = settings.backup_root.expanduser().resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    target = output_path or (
        backup_root / f"garden-os-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.tar.gz"
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        db_export = tmp_dir / settings.database_path.name
        shutil.copy2(settings.database_path, db_export)

        media_root = settings.media_root.expanduser().resolve()
        media_export = tmp_dir / "media"
        if media_root.exists():
            shutil.copytree(media_root, media_export)
        else:
            media_export.mkdir(parents=True, exist_ok=True)

        manifest = {
            "app_version": "0.1.0",
            "created_at": datetime.now(UTC).isoformat(),
            "schema_version": store.schema_version,
            "database_backend": "duckdb",
            "database_file": db_export.name,
            "database_sha256": _sha256_path(db_export),
            "media_root": media_root.as_posix(),
            "media_files": _manifest_files(media_export),
        }
        manifest_path = tmp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        with tarfile.open(target, "w:gz") as archive:
            archive.add(manifest_path, arcname="manifest.json")
            archive.add(db_export, arcname=db_export.name)
            archive.add(media_export, arcname="media")

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

        media_root = tmp_dir / "media"
        expected_files = {item["path"]: item["sha256"] for item in manifest.get("media_files", [])}
        for path in expected_files:
            file_path = media_root / path
            if not file_path.exists():
                raise RuntimeError(f"Missing media file in backup: {path}")
            if _sha256_path(file_path) != expected_files[path]:
                raise RuntimeError(f"Media hash mismatch: {path}")

        return manifest


def restore_backup(settings: LiteSettings, archive_path: Path) -> dict[str, Any]:
    manifest = verify_backup(archive_path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with tarfile.open(archive_path, "r:gz") as archive:
            _safe_extract(archive, tmp_dir)

        database_file = tmp_dir / str(manifest["database_file"])
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_file, settings.database_path)

        source_media = tmp_dir / "media"
        media_root = settings.media_root.expanduser().resolve()
        if source_media.exists():
            shutil.copytree(source_media, media_root, dirs_exist_ok=True)

    GardenStore(settings.database_path).initialize(seed=False)
    return manifest
