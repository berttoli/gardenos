from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from fastapi.testclient import TestClient

from app.lite.config import LiteSettings
from app.lite.main import create_app


def test_lite_api_exposes_plants_and_functions(tmp_path: Path) -> None:
    settings = LiteSettings(
        app_name="Garden OS Lite Test",
        database_path=tmp_path / "garden-os.duckdb",
        media_root=tmp_path / "media",
        backup_root=tmp_path / "backups",
        seed_on_startup=True,
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["backend"] == "duckdb"

        functions = client.get("/api/v1/functions")
        assert functions.status_code == 200
        assert functions.json()["functions"]

        plants = client.get("/api/v1/plants")
        assert plants.status_code == 200
        assert plants.json()["count"] >= 1

        zones = client.get("/api/v1/zones")
        assert zones.status_code == 200
        assert zones.json()["count"] >= 1

        created_zone = client.post(
            "/api/v1/zones",
            json={
                "name": "West woodland",
                "sun_exposure": "part shade",
            },
        )
        assert created_zone.status_code == 201
        zone_id = created_zone.json()["id"]

        fetched_zone = client.get(f"/api/v1/zones/{zone_id}")
        assert fetched_zone.status_code == 200
        assert fetched_zone.json()["name"] == "West woodland"

        updated_zone = client.patch(
            f"/api/v1/zones/{zone_id}",
            json={"notes": "Northwest edge"},
        )
        assert updated_zone.status_code == 200
        assert updated_zone.json()["notes"] == "Northwest edge"

        task = client.post(
            "/api/v1/tasks",
            json={
                "title": "Inspect woodland bed",
                "zone_name": "West woodland",
            },
        )
        assert task.status_code == 201
        assert task.json()["zone_name"] == "West woodland"

        filtered_tasks = client.get("/api/v1/tasks?zone=West woodland")
        assert filtered_tasks.status_code == 200
        assert filtered_tasks.json()["count"] >= 1

        query = client.post("/api/v1/query", json={"sql": "select 1 as value"})
        assert query.status_code == 200
        assert query.json()["rows"][0]["value"] == 1
