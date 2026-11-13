from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.access.models import Role
from app.access.services import ensure_group, ensure_group_membership, ensure_group_role
from app.auth.services import create_user
from app.care.models import TaskDefinition, TaskOccurrence
from app.database import SessionFactory
from app.locations.models import Location
from app.observations.models import Observation
from app.plants.models import Plant
from app.platform.models import PlatformEvent, ScopeMembership, ScopeNode

FIXTURE_PASSWORD = "synthetic-scope-operator-password"


def _login(client: TestClient, username: str, password: str = FIXTURE_PASSWORD) -> None:
    csrf = client.get("/api/v1/auth/session").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "csrf_token": csrf},
    )
    assert response.status_code == 200
    client.headers["x-csrf-token"] = client.get("/api/v1/auth/session").json()["csrf_token"]


def _seed(session_factory: SessionFactory, *, own: str = "a") -> dict[str, str]:
    with session_factory() as session:
        organization = ScopeNode(
            name="Example Organization", slug="example-organization", scope_type="organization"
        )
        parent = Location(
            name="Example Organization",
            location_type="organization",
            description="Hidden organization description",
        )
        locations = {
            key: Location(
                name="Example Nursery",
                location_type="nursery",
                parent=parent,
                description=f"Private fixture description {key}",
                latitude=10 if key == "a" else 20,
            )
            for key in ("a", "b", "unmapped")
        }
        session.add_all([organization, parent, *locations.values()])
        session.flush()
        scopes = {
            key: ScopeNode(
                name="Example Nursery",
                slug=f"example-{key}",
                scope_type="nursery",
                parent=organization,
                metadata_json={"source_location_id": locations[key].id},
            )
            for key in ("a", "b")
        }
        plants = {
            key: Plant(
                display_id=f"EXAMPLE-{key.upper()}",
                current_location=location,
                status="active" if key == "a" else "quarantine",
            )
            for key, location in locations.items()
        }
        tasks = {
            key: TaskOccurrence(
                task_definition=TaskDefinition(
                    title=f"Inspect example {key}", scope_type="location", scope_id=location.id
                ),
                scheduled_for=datetime.now(UTC) + timedelta(days=1),
            )
            for key, location in locations.items()
        }
        session.add_all([*scopes.values(), *plants.values(), *tasks.values()])
        session.add(
            Observation(plant=plants["a"], observed_at=datetime.now(UTC), overall_health_score=4)
        )
        user = create_user(
            session,
            username="scope-operator",
            full_name="Example Scope Operator",
            password=FIXTURE_PASSWORD,
        )
        session.flush()
        session.add(
            ScopeMembership(
                scope_node_id=scopes[own].id,
                user_id=user.id,
                role_key="nursery-operator",
                access_level="manage",
            )
        )
        group = ensure_group(session, slug="scope-operators", name="Example Scope Operators")
        role = session.scalar(select(Role).where(Role.key == "operator"))
        assert role is not None
        ensure_group_role(session, group, role)
        ensure_group_membership(session, group, user)
        session.commit()
        return {
            **{f"location_{key}": value.id for key, value in locations.items()},
            **{f"scope_{key}": value.id for key, value in scopes.items()},
            **{f"task_{key}": value.id for key, value in tasks.items()},
            "parent": parent.id,
        }


@pytest.mark.parametrize("own,other", [("a", "b"), ("b", "a")])
@pytest.mark.parametrize("scope_mode", ["location", "plant"])
def test_same_name_nurseries_use_exact_ids_for_reads_writes_and_events(
    client: TestClient, session_factory: SessionFactory, own: str, other: str, scope_mode: str
) -> None:
    ids = _seed(session_factory, own=own)
    if scope_mode == "plant":
        with session_factory() as session:
            for key in ("a", "b"):
                task = session.get(TaskOccurrence, ids[f"task_{key}"])
                plant = session.scalar(
                    select(Plant).where(Plant.current_location_id == ids[f"location_{key}"])
                )
                assert task is not None and plant is not None
                task.task_definition.scope_id = plant.id
                task.task_definition.scope_type = "plant"
                task.plant = plant
            session.commit()
    _login(client, "scope-operator")
    listing = client.get("/api/v1/tasks")
    assert listing.status_code == 200
    assert [task["id"] for task in listing.json()["due_tasks"]] == [ids[f"task_{own}"]]
    assert listing.json()["due_tasks"][0]["scope_node_id"] == ids[f"scope_{own}"]
    denied = client.post(f"/api/v1/tasks/{ids[f'task_{other}']}/complete", json={})
    assert denied.status_code == 404
    completed = client.post(f"/api/v1/tasks/{ids[f'task_{own}']}/complete", json={})
    assert completed.status_code == 200
    assert completed.json()["scope_node_id"] == ids[f"scope_{own}"]
    with session_factory() as session:
        event = session.scalar(
            select(PlatformEvent).where(
                PlatformEvent.source_id == ids[f"task_{own}"],
                PlatformEvent.event_type == "task.occurrence.completed",
            )
        )
        assert event is not None
        assert event.scope_node_id == ids[f"scope_{own}"]
        assert event.payload_json["scope_node_id"] == ids[f"scope_{own}"]
        assert session.get(TaskOccurrence, ids[f"task_{other}"]).completed_at is None
    refreshed = client.get("/api/v1/workspace").json()
    assert [task["id"] for task in refreshed["tasks"]["completed"]] == [ids[f"task_{own}"]]


@pytest.mark.parametrize("inconsistency", ["foreign_plant", "unknown_scope"])
def test_task_scope_cannot_override_a_foreign_plant_or_unknown_identifier(
    client: TestClient, session_factory: SessionFactory, inconsistency: str
) -> None:
    ids = _seed(session_factory)
    with session_factory() as session:
        task = session.get(TaskOccurrence, ids["task_a"])
        assert task is not None
        plant_location = (
            ids["location_b"] if inconsistency == "foreign_plant" else ids["location_a"]
        )
        task.plant = session.scalar(
            select(Plant).where(Plant.current_location_id == plant_location)
        )
        task.task_definition.scope_id = (
            ids["scope_a"] if inconsistency == "foreign_plant" else "unknown-example-scope"
        )
        session.commit()
    _login(client, "scope-operator")
    listing = client.get("/api/v1/tasks").json()
    assert listing["due_tasks"] == []
    assert client.post(f"/api/v1/tasks/{ids['task_a']}/complete", json={}).status_code == 404


def test_workspace_prunes_hidden_ancestors_and_scopes_every_plant_count(
    client: TestClient, session_factory: SessionFactory
) -> None:
    ids = _seed(session_factory)
    _login(client, "scope-operator")
    response = client.get(f"/api/v1/workspace?location_id={ids['location_b']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_location_id"] is None
    locations = payload["navigation"]["locations"]
    assert [item["id"] for item in locations] == [ids["location_a"]]
    assert locations[0]["parent_id"] is None
    assert locations[0]["path"] == [
        {
            "id": ids["location_a"],
            "name": "Example Nursery",
            "type": "nursery",
        }
    ]
    assert locations[0]["plant_count"] == 1
    assert payload["summary"]["plant_count"] == 1
    assert payload["summary"]["quarantine_plant_count"] == 0
    assert payload["summary"]["follow_up_plant_count"] == 1
    assert payload["summary"]["location_count"] == 1
    assert payload["summary"]["root_location_count"] == 1
    serialized = json.dumps(payload)
    for forbidden in (
        ids["parent"],
        ids["location_b"],
        ids["location_unmapped"],
        "Private fixture description b",
        "Hidden organization description",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize("mapping", ["unmapped", "ambiguous"])
def test_unmapped_or_ambiguous_locations_fail_closed_but_admin_keeps_visibility(
    client: TestClient, session_factory: SessionFactory, mapping: str
) -> None:
    ids = _seed(session_factory, own="b")
    with session_factory() as session:
        scope = session.get(ScopeNode, ids["scope_b"])
        if mapping == "unmapped":
            scope.metadata_json = {}
        else:
            session.add(
                ScopeNode(
                    name="Conflicting Example Mapping",
                    slug="conflicting-example",
                    scope_type="nursery",
                    metadata_json={"source_location_id": ids["location_b"]},
                )
            )
        session.commit()
    _login(client, "scope-operator")
    payload = client.get("/api/v1/workspace").json()
    assert payload["navigation"]["locations"] == []
    assert payload["summary"]["plant_count"] == 0
    assert payload["summary"]["quarantine_plant_count"] == 0
    assert payload["summary"]["follow_up_plant_count"] == 0
    assert payload["tasks"] == {"due": [], "overdue": [], "completed": []}
    assert client.post(f"/api/v1/tasks/{ids['task_b']}/complete", json={}).status_code == 404
    _login(client, "admin", "test-admin-password")
    admin = client.get("/api/v1/workspace").json()
    assert admin["summary"]["plant_count"] == 3
    assert admin["summary"]["location_count"] == 4
    assert {task["id"] for task in admin["tasks"]["due"]} == {
        ids["task_a"],
        ids["task_b"],
        ids["task_unmapped"],
    }
