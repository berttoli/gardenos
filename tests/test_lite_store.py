from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from app.lite.store import GardenStore


def test_lite_store_bootstrap_and_queries(tmp_path: Path) -> None:
    store = GardenStore(tmp_path / "garden-os.duckdb")
    store.initialize(seed=True)

    dashboard = store.dashboard()
    assert dashboard["summary"]["active_plants"] >= 1
    assert dashboard["recent_plants"]

    plants = store.list_plants(limit=10)
    assert len(plants) >= 1

    plant = store.get_plant(plants[0]["id"])
    assert plant["plant"]["display_id"]
    assert plant["observations"] or plant["tasks"] or plant["events"]

    conversation = store.create_conversation({"title": "Automation thread"})
    conversation_id = conversation["conversation"]["id"]
    message = store.append_message(
        conversation_id,
        {"role": "user", "content": "Show me the watering queue."},
    )
    assert message["conversation_id"] == conversation_id
    assert message["content"] == "Show me the watering queue."


def test_lite_store_zone_crud_and_task_filter(tmp_path: Path) -> None:
    store = GardenStore(tmp_path / "garden-os.duckdb")
    store.initialize(seed=True)

    zone = store.create_zone(
        {
            "name": "West woodland",
            "zone_type": "zone",
            "sun_exposure": "part shade",
            "notes": "Back edge of the property.",
        },
    )
    assert zone["name"] == "West woodland"
    assert zone["sun_exposure"] == "part shade"

    updated = store.update_zone(zone["id"], {"notes": "Northwest edge"})
    assert updated["notes"] == "Northwest edge"

    plant = store.create_plant(
        {
            "scientific_name": "Acer palmatum",
            "common_name": "Japanese maple",
            "zone_name": "West woodland",
        },
    )
    assert plant["plant"]["zone_name"] == "West woodland"

    task = store.create_task(
        {
            "title": "Inspect woodland bed",
            "zone_name": "West woodland",
        },
    )
    assert task["zone_name"] == "West woodland"

    filtered_tasks = store.list_tasks(zone="West woodland")
    assert any(item["id"] == task["id"] for item in filtered_tasks)

    zones = store.list_zones(query="woodland")
    assert any(item["id"] == zone["id"] for item in zones)
