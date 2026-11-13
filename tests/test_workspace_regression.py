from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.care.models import TaskDefinition, TaskOccurrence
from app.locations.models import Location
from app.plants.models import Plant


def _auth_session(client: TestClient) -> dict[str, object]:
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 200
    return response.json()


def _csrf_token(client: TestClient) -> str:
    session = _auth_session(client)
    token = session["csrf_token"]
    assert isinstance(token, str)
    assert token
    return token


def _login_admin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "test-admin-password",
            "csrf_token": _csrf_token(client),
        },
    )
    assert response.status_code == 200


def _seed_workspace_tree(session_factory) -> dict[str, str]:
    with session_factory() as session:
        organization = Location(name="Pineview Organization", location_type="organization")
        nursery = Location(name="Pineview Nursery", location_type="nursery", parent=organization)
        site = Location(name="North Site", location_type="site", parent=nursery)
        zone = Location(name="Zone B", location_type="zone", parent=site)

        plant = Plant(display_id="PV-001", current_location=zone)
        task_definition = TaskDefinition(
            title="Water Zone B",
            task_type="water",
            priority=1,
            scope_type="location",
        )
        task = TaskOccurrence(
            task_definition=task_definition,
            plant=plant,
            scheduled_for=datetime.now(UTC) + timedelta(hours=2),
        )

        session.add_all([organization, nursery, site, zone, plant, task_definition, task])
        session.commit()

        return {
            "organization_id": organization.id,
            "nursery_id": nursery.id,
            "site_id": site.id,
            "zone_id": zone.id,
        }


def test_workspace_bootstrap_returns_location_tree_and_task_badge(
    client: TestClient,
    session_factory,
) -> None:
    _login_admin(client)
    ids = _seed_workspace_tree(session_factory)

    response = client.get(f"/api/v1/workspace?location_id={ids['zone_id']}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["principal"]["kind"] == "user"
    assert payload["selected_location_id"] == ids["zone_id"]

    summary = payload["summary"]
    assert summary["plant_count"] == 1
    assert summary["location_count"] == 4
    assert summary["root_location_count"] == 1
    assert summary["due_task_count"] == 1
    assert summary["overdue_task_count"] == 0

    sidebar = {item["page"]: item for item in payload["sidebar"]}
    assert sidebar["tasks"]["badge"] == "1"

    locations = payload["navigation"]["locations"]
    assert len(locations) == 1

    organization = locations[0]
    nursery = organization["children"][0]
    site = nursery["children"][0]
    zone = site["children"][0]

    assert organization["name"] == "Pineview Organization"
    assert organization["direct_plant_count"] == 0
    assert organization["plant_count"] == 1
    assert organization["child_count"] == 1

    assert nursery["name"] == "Pineview Nursery"
    assert nursery["direct_plant_count"] == 0
    assert nursery["plant_count"] == 1

    assert site["name"] == "North Site"
    assert site["direct_plant_count"] == 0
    assert site["plant_count"] == 1

    assert zone["name"] == "Zone B"
    assert zone["direct_plant_count"] == 1
    assert zone["plant_count"] == 1
    assert zone["is_selected"] is True
    assert zone["path"][-1]["id"] == ids["zone_id"]

    assert payload["tasks"]["due"][0]["title"] == "Water Zone B"
