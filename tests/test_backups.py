from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.maintenance as maintenance
from app.config import Settings

duckdb = pytest.importorskip("duckdb")


@contextmanager
def _fake_session() -> object:
    yield SimpleNamespace(rollback=lambda: None)


def _fake_export_warehouse_snapshot(
    session_factory: object,
    output_path: Path,
    *,
    settings: Settings,
) -> None:
    connection = duckdb.connect(str(output_path))
    try:
        connection.execute("CREATE TABLE warehouse_meta (key TEXT, value TEXT)")
        connection.execute(
            "INSERT INTO warehouse_meta VALUES ('source', 'test'), ('settings', ?)",
            [settings.app_name],
        )
    finally:
        connection.close()


def _fake_runtime(
    settings: Settings,
) -> tuple[Settings, object, object]:
    return settings, SimpleNamespace(dispose=lambda: None), _fake_session


def _fake_subprocess_run(cmd: list[str], check: bool) -> SimpleNamespace:
    output_path = Path(cmd[cmd.index("--file") + 1]) if "--file" in cmd else None
    if cmd[0] == "pg_dump":
        assert output_path is not None
        output_path.write_bytes(b"fake postgres dump")
    elif cmd[0] == "pg_restore":
        pass
    else:
        raise AssertionError(f"unexpected command: {cmd[0]}")
    return SimpleNamespace(returncode=0)


def test_backup_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_root = tmp_path / "media"
    backup_root = tmp_path / "backups"
    warehouse_path = tmp_path / "warehouse" / "garden-os-warehouse.duckdb"
    media_root.mkdir()
    (media_root / "sample.txt").write_text("hello from Garden OS", encoding="utf-8")

    settings = Settings.from_mapping(
        {
            "APP_NAME": "Garden OS Test",
            "ENVIRONMENT": "test",
            "SECRET_KEY": "test-secret-key-change-me-123456",
            "DATABASE_URL": "postgresql+pg8000://garden:garden@localhost:5432/garden",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "test-admin-password",
            "ADMIN_FULL_NAME": "Garden Administrator",
            "MEDIA_ROOT": str(media_root),
            "BACKUP_ROOT": str(backup_root),
            "WAREHOUSE_DB_PATH": str(warehouse_path),
        },
    )

    monkeypatch.setattr(maintenance, "runtime", lambda: _fake_runtime(settings))
    monkeypatch.setattr(maintenance, "_schema_version", lambda session: "schema-1")
    monkeypatch.setattr(maintenance, "export_warehouse_snapshot", _fake_export_warehouse_snapshot)
    monkeypatch.setattr(maintenance.subprocess, "run", _fake_subprocess_run)

    archive_path = maintenance.create_backup()
    manifest = maintenance.verify_backup(archive_path)

    assert archive_path.exists()
    assert manifest["database_backend"] == "postgresql"
    assert manifest["database_file"] == "database.dump"
    assert manifest["warehouse_backend"] == "duckdb"
    assert manifest["warehouse_file"] == "warehouse.duckdb"
    assert manifest["media_files"][0]["path"] == "sample.txt"

    (media_root / "sample.txt").unlink()
    maintenance.restore_backup(archive_path)

    restored_text = (media_root / "sample.txt").read_text(encoding="utf-8")
    assert restored_text == "hello from Garden OS"
    assert warehouse_path.exists()

    connection = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        meta_rows = connection.execute("SELECT COUNT(*) FROM warehouse_meta").fetchone()[0]
    finally:
        connection.close()

    assert meta_rows >= 1
