from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL

from app.access.models import Permission, Role
from app.access.services import (
    ensure_group,
    ensure_group_membership,
    ensure_group_role,
    ensure_role,
    ensure_role_permission,
    ensure_service_account,
    ensure_service_account_role,
    issue_service_account_token,
)
from app.auth.services import create_user
from app.care.models import TaskDefinition, TaskOccurrence
from app.config import Settings
from app.database import Base, SessionFactory, create_session_factory
from app.main import create_app
from app.platform.models import PlatformEvent, ScopeMembership, ScopeNode

# These identities and passwords are synthetic fixtures, never deployment credentials.
OPERATOR_PASSWORD = "fixture-operator-password"


def _login(
    client: TestClient, username: str = "admin", password: str = "test-admin-password"
) -> None:
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": password,
            "csrf_token": session.json()["csrf_token"],
        },
    )
    assert response.status_code == 200
    refreshed = client.get("/api/v1/auth/session")
    client.headers["x-csrf-token"] = refreshed.json()["csrf_token"]


def _task(
    session_factory: SessionFactory,
    *,
    scope_id: str | None = None,
    overdue: bool = False,
    completed: bool = False,
) -> str:
    with session_factory() as session:
        definition = TaskDefinition(
            title="Inspect example nursery task",
            task_type="inspect",
            scope_type="location" if scope_id else "garden",
            scope_id=scope_id,
        )
        occurrence = TaskOccurrence(
            task_definition=definition,
            scheduled_for=datetime.now(UTC) + timedelta(hours=-2 if overdue else 2),
            completed_at=datetime.now(UTC) if completed else None,
        )
        session.add(occurrence)
        session.commit()
        return occurrence.id


def _nurseries(session_factory: SessionFactory) -> tuple[str, str]:
    with session_factory() as session:
        organization = ScopeNode(
            scope_type="organization",
            name="Example Organization",
            slug="example-organization",
        )
        first = ScopeNode(
            scope_type="nursery",
            name="Example Nursery A",
            slug="example-a",
            parent=organization,
        )
        second = ScopeNode(
            scope_type="nursery",
            name="Example Nursery B",
            slug="example-b",
            parent=organization,
        )
        session.add_all([organization, first, second])
        session.commit()
        return first.id, second.id


def _scoped_user(
    session_factory: SessionFactory,
    *,
    scope_id: str,
    operator: bool,
) -> str:
    username = "example-operator" if operator else "example-reader"
    with session_factory() as session:
        user = create_user(
            session,
            username=username,
            full_name="Example Operator" if operator else "Example Reader",
            password=OPERATOR_PASSWORD,
        )
        session.add(
            ScopeMembership(
                scope_node_id=scope_id,
                user_id=user.id,
                role_key="nursery-operator" if operator else "nursery-reader",
                access_level="manage" if operator else "view",
            ),
        )
        if operator:
            group = ensure_group(session, slug="example-operators", name="Example Operators")
            role = session.scalar(select(Role).where(Role.key == "operator"))
            assert role is not None
            ensure_group_role(session, group, role)
            ensure_group_membership(session, group, user)
        session.commit()
    return username


def _assert_not_completed(session_factory: SessionFactory, task_id: str) -> None:
    with session_factory() as session:
        occurrence = session.get(TaskOccurrence, task_id)
        assert occurrence is not None
        assert occurrence.completed_at is None


@pytest.mark.parametrize("overdue", [False, True], ids=["due", "overdue"])
def test_completion_survives_fresh_read_and_leaves_active_queues(
    client: TestClient,
    session_factory: SessionFactory,
    overdue: bool,
) -> None:
    _login(client)
    task_id = _task(session_factory, overdue=overdue)

    before = client.get("/api/v1/workspace")
    assert before.status_code == 200
    active_before = before.json()["tasks"]
    assert task_id in {item["id"] for item in active_before["due"] + active_before["overdue"]}

    response = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        json={"completion_notes": "Completed in the persistence regression fixture."},
    )
    assert response.status_code == 200
    assert response.json()["id"] == task_id
    assert response.json()["completed_at"] is not None
    assert response.json()["status"] == "completed"

    # A separate database session proves the write was committed, not just reflected in JSON.
    with session_factory() as session:
        stored = session.get(TaskOccurrence, task_id)
        assert stored is not None
        assert stored.completed_at is not None
        assert stored.completion_notes == "Completed in the persistence regression fixture."

    # The same canonical bootstrap used on a page reload must retain completed history.
    workspace = client.get("/api/v1/workspace")
    assert workspace.status_code == 200
    payload = workspace.json()
    assert payload["tasks"]["due"] == []
    assert payload["tasks"]["overdue"] == []
    assert [item["id"] for item in payload["tasks"]["completed"]] == [task_id]
    assert payload["tasks"]["completed"][0]["status"] == "completed"
    assert payload["summary"]["due_task_count"] == 0
    assert payload["summary"]["overdue_task_count"] == 0
    task_nav = next(item for item in payload["sidebar"] if item["page"] == "tasks")
    assert task_nav["badge"] is None

    listing = client.get("/api/v1/tasks")
    assert listing.status_code == 200
    assert listing.json()["due_tasks"] == []
    assert listing.json()["overdue_tasks"] == []
    assert [item["id"] for item in listing.json()["completed_tasks"]] == [task_id]


def test_completion_survives_application_and_database_engine_restart(
    settings: Settings,
    tmp_path: Path,
) -> None:
    database_url = URL.create("sqlite+pysqlite", database=str(tmp_path / "restart.sqlite3"))
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with TestClient(create_app(settings=settings, engine=engine)) as first_client:
        _login(first_client)
        task_id = _task(session_factory)
        completed = first_client.post(
            f"/api/v1/tasks/{task_id}/complete",
            json={"completion_notes": "Saved before the API restarted."},
        )
        assert completed.status_code == 200
        completed_at = completed.json()["completed_at"]

    # TestClient shutdown disposes the original engine. Reconstruct the API and
    # its connection pool from the file, with no shared ORM objects or session.
    restarted_engine = create_engine(database_url, connect_args={"check_same_thread": False})
    with TestClient(create_app(settings=settings, engine=restarted_engine)) as restarted_client:
        _login(restarted_client)
        workspace = restarted_client.get("/api/v1/workspace")
        assert workspace.status_code == 200
        tasks = workspace.json()["tasks"]
        assert tasks["due"] == []
        assert tasks["overdue"] == []
        assert [task["id"] for task in tasks["completed"]] == [task_id]
        assert tasks["completed"][0]["completed_at"] == completed_at
        assert tasks["completed"][0]["status"] == "completed"


def test_repeat_completion_preserves_original_record_and_emits_one_event(
    client: TestClient,
    session_factory: SessionFactory,
) -> None:
    _login(client)
    task_id = _task(session_factory)
    first = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        json={"completion_notes": "First completion."},
    )
    assert first.status_code == 200

    with session_factory() as session:
        occurrence = session.get(TaskOccurrence, task_id)
        assert occurrence is not None
        original_completed_at = occurrence.completed_at

    repeated = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        json={"completion_notes": "A retried request must not overwrite the original."},
    )
    assert repeated.status_code == 200
    with session_factory() as session:
        occurrence = session.get(TaskOccurrence, task_id)
        assert occurrence is not None
        assert occurrence.completed_at == original_completed_at
        assert occurrence.completion_notes == "First completion."
        event_count = session.scalar(
            select(func.count(PlatformEvent.id)).where(
                PlatformEvent.source_id == task_id,
                PlatformEvent.event_type == "task.occurrence.completed",
            ),
        )
        assert event_count == 1


def test_completion_requires_authentication(
    client: TestClient,
    session_factory: SessionFactory,
) -> None:
    task_id = _task(session_factory)
    response = client.post(f"/api/v1/tasks/{task_id}/complete", json={})
    assert response.status_code == 401
    _assert_not_completed(session_factory, task_id)


@pytest.mark.parametrize("csrf", [None, "invalid-fixture-csrf"])
def test_session_completion_requires_valid_csrf(
    client: TestClient,
    session_factory: SessionFactory,
    csrf: str | None,
) -> None:
    _login(client)
    task_id = _task(session_factory)
    del client.headers["x-csrf-token"]
    headers = {"x-csrf-token": csrf} if csrf is not None else {}
    response = client.post(f"/api/v1/tasks/{task_id}/complete", json={}, headers=headers)
    assert response.status_code == 403
    _assert_not_completed(session_factory, task_id)


def test_reader_cannot_complete_even_a_task_in_their_nursery(
    client: TestClient,
    session_factory: SessionFactory,
) -> None:
    nursery_id, _ = _nurseries(session_factory)
    task_id = _task(session_factory, scope_id=nursery_id)
    username = _scoped_user(session_factory, scope_id=nursery_id, operator=False)
    _login(client, username, OPERATOR_PASSWORD)

    response = client.post(f"/api/v1/tasks/{task_id}/complete", json={})
    assert response.status_code == 403
    _assert_not_completed(session_factory, task_id)


def test_operator_can_complete_only_tasks_in_their_nursery(
    client: TestClient,
    session_factory: SessionFactory,
) -> None:
    own_nursery, other_nursery = _nurseries(session_factory)
    own_task = _task(session_factory, scope_id=own_nursery)
    other_task = _task(session_factory, scope_id=other_nursery)
    username = _scoped_user(session_factory, scope_id=own_nursery, operator=True)
    _login(client, username, OPERATOR_PASSWORD)

    denied = client.post(f"/api/v1/tasks/{other_task}/complete", json={})
    assert denied.status_code == 404
    _assert_not_completed(session_factory, other_task)

    allowed = client.post(f"/api/v1/tasks/{own_task}/complete", json={})
    assert allowed.status_code == 200
    assert allowed.json()["completed_at"] is not None


def test_active_and_completed_task_lists_do_not_expose_other_nurseries(
    client: TestClient,
    session_factory: SessionFactory,
) -> None:
    own_nursery, other_nursery = _nurseries(session_factory)
    own_active = _task(session_factory, scope_id=own_nursery)
    own_completed = _task(session_factory, scope_id=own_nursery, completed=True)
    other_active = _task(session_factory, scope_id=other_nursery, overdue=True)
    other_completed = _task(session_factory, scope_id=other_nursery, completed=True)
    username = _scoped_user(session_factory, scope_id=own_nursery, operator=False)
    _login(client, username, OPERATOR_PASSWORD)

    for path, keys in (
        ("/api/v1/tasks", ("due_tasks", "overdue_tasks", "completed_tasks")),
        ("/api/v1/workspace", ("due", "overdue", "completed")),
    ):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()["tasks"] if path.endswith("workspace") else response.json()
        visible = {item["id"] for key in keys for item in payload[key]}
        assert visible == {own_active, own_completed}
        assert other_active not in visible
        assert other_completed not in visible


def test_missing_task_returns_not_found(client: TestClient) -> None:
    _login(client)
    response = client.post("/api/v1/tasks/00000000-0000-4000-8000-000000000000/complete", json={})
    assert response.status_code == 404


def test_workspace_access_does_not_imply_permission_to_read_tasks(
    client: TestClient,
    session_factory: SessionFactory,
) -> None:
    nursery_id, _ = _nurseries(session_factory)
    _task(session_factory, scope_id=nursery_id)
    _task(session_factory, scope_id=nursery_id, completed=True)
    with session_factory() as session:
        role = ensure_role(session, key="example-workspace-only", name="Example Workspace Only")
        permission = session.scalar(select(Permission).where(Permission.key == "access.read"))
        assert permission is not None
        ensure_role_permission(session, role, permission)
        group = ensure_group(
            session,
            slug="example-workspace-readers",
            name="Example Workspace Readers",
            scope_type="nursery",
            scope_id=nursery_id,
        )
        account = ensure_service_account(
            session,
            slug="example-workspace-service",
            name="Example Workspace Service",
            group=group,
        )
        ensure_service_account_role(session, account, role)
        _, token = issue_service_account_token(session, account, label="synthetic-test-token")
        session.commit()
    client.headers["authorization"] = f"Bearer {token}"

    assert client.get("/api/v1/tasks").status_code == 403
    response = client.get("/api/v1/workspace")
    assert response.status_code == 200
    assert response.json()["tasks"] == {"due": [], "overdue": [], "completed": []}
    assert response.json()["summary"]["due_task_count"] == 0
    assert response.json()["summary"]["overdue_task_count"] == 0


def test_skipped_task_cannot_be_completed(
    client: TestClient,
    session_factory: SessionFactory,
) -> None:
    _login(client)
    task_id = _task(session_factory)
    with session_factory() as session:
        occurrence = session.get(TaskOccurrence, task_id)
        assert occurrence is not None
        occurrence.skipped_at = datetime.now(UTC)
        session.commit()

    response = client.post(f"/api/v1/tasks/{task_id}/complete", json={})
    assert response.status_code == 409
    with session_factory() as session:
        occurrence = session.get(TaskOccurrence, task_id)
        assert occurrence is not None
        assert occurrence.skipped_at is not None
        assert occurrence.completed_at is None
        event_count = session.scalar(
            select(func.count(PlatformEvent.id)).where(
                PlatformEvent.source_id == task_id,
                PlatformEvent.event_type == "task.occurrence.completed",
            ),
        )
        assert event_count == 0
