from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.auth.services import create_user
from app.care.models import TaskDefinition, TaskOccurrence
from app.care.services import create_task_definition, ensure_task_occurrence
from app.care.updaters import backfill_task_definition_scope
from app.locations.models import Location
from app.plants.models import Plant
from app.platform.models import ScopeNode


def _csrf_token(client: TestClient) -> str:
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 200
    token = response.json()["csrf_token"]
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
    refreshed = client.get("/api/v1/auth/session")
    client.headers.update({"x-csrf-token": refreshed.json()["csrf_token"]})


def _login_user(client: TestClient, *, username: str, password: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": password,
            "csrf_token": _csrf_token(client),
        },
    )
    assert response.status_code == 200
    refreshed = client.get("/api/v1/auth/session")
    client.headers.update({"x-csrf-token": refreshed.json()["csrf_token"]})


def _create_user(session_factory, *, username: str, full_name: str, password: str) -> None:
    with session_factory() as session:
        create_user(
            session,
            username=username,
            full_name=full_name,
            password=password,
        )
        session.commit()


def _create_role(
    client: TestClient,
    *,
    key: str,
    name: str,
    permission_keys: list[str],
) -> dict[str, object]:
    response = client.post(
        "/api/v1/access/roles",
        json={
            "key": key,
            "name": name,
            "permission_keys": permission_keys,
        },
    )
    assert response.status_code == 201
    return response.json()["role"]


def _create_group(
    client: TestClient,
    *,
    slug: str,
    name: str,
    role_keys: list[str],
) -> dict[str, object]:
    response = client.post(
        "/api/v1/access/groups",
        json={
            "slug": slug,
            "name": name,
            "group_type": "team",
            "role_keys": role_keys,
        },
    )
    assert response.status_code == 201
    return response.json()["group"]


def _add_group_member(client: TestClient, *, group_slug: str, username: str) -> None:
    response = client.post(
        f"/api/v1/access/groups/{group_slug}/members",
        json={"username": username},
    )
    assert response.status_code == 201


def _create_scope(
    client: TestClient, *, parent_id: str | None, scope_type: str, name: str, slug: str
) -> dict[str, object]:
    payload: dict[str, object] = {
        "scope_type": scope_type,
        "name": name,
        "slug": slug,
    }
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/api/v1/platform/scopes", json=payload)
    assert response.status_code == 201
    return response.json()["scope_node"]


def test_platform_catalog_is_seeded_and_scope_tree_is_visible(client: TestClient) -> None:
    _login_admin(client)

    response = client.get("/api/v1/platform/catalog")
    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["skill_count"] == 4
    assert payload["summary"]["connector_count"] == 6
    assert payload["summary"]["service_action_count"] == 10

    connector_keys = {item["key"] for item in payload["connectors"]}
    assert {"cameras", "notifications", "email", "weather", "sensors", "calendar"} <= connector_keys

    skill_keys = {item["key"] for item in payload["skills"]}
    assert {"task-manager", "scheduler", "workflow-builder", "alert-router"} <= skill_keys

    scopes = {item["slug"]: item for item in payload["scopes"]}
    root = scopes["gardenos-platform"]
    templates = root["children"][0]

    assert root["scope_type"] == "organization"
    assert root["child_count"] == 1
    assert templates["slug"] == "shared-templates"
    assert {"automation-library", "connector-library", "observability"} <= {
        child["slug"] for child in templates["children"]
    }


def test_platform_scope_membership_flows_into_auth_context(
    client: TestClient,
    session_factory,
) -> None:
    _login_admin(client)
    _create_user(
        session_factory,
        username="nursery-user",
        full_name="Nursery User",
        password="test-user-password",
    )

    organization = _create_scope(
        client,
        parent_id=None,
        scope_type="organization",
        name="Pineview Organization",
        slug="pineview",
    )
    folder = _create_scope(
        client,
        parent_id=organization["id"],
        scope_type="folder",
        name="Shared Operations",
        slug="shared-operations",
    )
    nursery = _create_scope(
        client,
        parent_id=folder["id"],
        scope_type="nursery",
        name="Pineview Nursery",
        slug="pineview-nursery",
    )
    site = _create_scope(
        client,
        parent_id=nursery["id"],
        scope_type="site",
        name="North Site",
        slug="north-site",
    )
    zone = _create_scope(
        client,
        parent_id=site["id"],
        scope_type="zone",
        name="Zone B",
        slug="zone-b",
    )

    membership_response = client.post(
        "/api/v1/platform/scope-memberships",
        json={
            "scope_node_id": zone["id"],
            "username": "nursery-user",
            "role_key": "nursery-editor",
            "access_level": "manage",
            "can_view_telemetry": False,
            "can_manage_automations": False,
            "can_approve_mutations": False,
        },
    )
    assert membership_response.status_code == 201

    scope_tree_response = client.get("/api/v1/platform/scopes")
    assert scope_tree_response.status_code == 200
    roots = scope_tree_response.json()
    pineview = next(item for item in roots if item["slug"] == "pineview")
    assert pineview["child_count"] == 1
    assert pineview["children"][0]["slug"] == "shared-operations"
    assert pineview["children"][0]["children"][0]["slug"] == "pineview-nursery"

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "nursery-user",
            "password": "test-user-password",
            "csrf_token": _csrf_token(client),
        },
    )
    assert login_response.status_code == 200
    refreshed = client.get("/api/v1/auth/session")
    client.headers.update({"x-csrf-token": refreshed.json()["csrf_token"]})

    auth_context_response = client.get("/api/v1/auth/context")
    assert auth_context_response.status_code == 200
    auth_context = auth_context_response.json()
    assert auth_context["principal"]["kind"] == "user"
    assert zone["id"] in auth_context["principal"]["scope_ids"]


def test_platform_scope_views_roll_up_by_nursery_and_organization(
    client: TestClient,
    session_factory,
) -> None:
    _login_admin(client)
    _create_role(
        client,
        key="platform-observer",
        name="Platform Observer",
        permission_keys=["platform.read"],
    )
    _create_group(
        client,
        slug="nursery-observers",
        name="Nursery Observers",
        role_keys=["platform-observer"],
    )
    _create_user(
        session_factory,
        username="nursery-user",
        full_name="Nursery User",
        password="test-user-password",
    )
    _create_user(
        session_factory,
        username="org-user",
        full_name="Org User",
        password="test-org-password",
    )
    _add_group_member(client, group_slug="nursery-observers", username="nursery-user")
    _add_group_member(client, group_slug="nursery-observers", username="org-user")

    organization = _create_scope(
        client,
        parent_id=None,
        scope_type="organization",
        name="Pineview Organization",
        slug="pineview-org",
    )
    folder = _create_scope(
        client,
        parent_id=organization["id"],
        scope_type="folder",
        name="Operations",
        slug="operations",
    )
    nursery_a = _create_scope(
        client,
        parent_id=folder["id"],
        scope_type="nursery",
        name="North Nursery",
        slug="north-nursery",
    )
    site_a = _create_scope(
        client,
        parent_id=nursery_a["id"],
        scope_type="site",
        name="North Site",
        slug="north-site",
    )
    zone_a = _create_scope(
        client,
        parent_id=site_a["id"],
        scope_type="zone",
        name="Zone A",
        slug="zone-a",
    )
    nursery_b = _create_scope(
        client,
        parent_id=folder["id"],
        scope_type="nursery",
        name="South Nursery",
        slug="south-nursery",
    )
    site_b = _create_scope(
        client,
        parent_id=nursery_b["id"],
        scope_type="site",
        name="South Site",
        slug="south-site",
    )
    zone_b = _create_scope(
        client,
        parent_id=site_b["id"],
        scope_type="zone",
        name="Zone B",
        slug="zone-b",
    )

    nursery_membership = client.post(
        "/api/v1/platform/scope-memberships",
        json={
            "scope_node_id": zone_a["id"],
            "username": "nursery-user",
            "role_key": "nursery-reader",
            "access_level": "view",
            "can_view_telemetry": True,
        },
    )
    assert nursery_membership.status_code == 201

    org_membership = client.post(
        "/api/v1/platform/scope-memberships",
        json={
            "scope_node_id": organization["id"],
            "username": "org-user",
            "role_key": "org-reader",
            "access_level": "view",
            "can_view_telemetry": True,
        },
    )
    assert org_membership.status_code == 201

    alert_policy_a_response = client.post(
        "/api/v1/platform/alert-policies",
        json={
            "scope_node_id": nursery_a["id"],
            "key": "nursery-a-alert",
            "name": "Nursery A Alert",
            "source_kind": "sensor",
            "severity": "critical",
            "rule_json": {"match": "low-moisture"},
        },
    )
    assert alert_policy_a_response.status_code == 201
    alert_policy_a_id = alert_policy_a_response.json()["alert_policy"]["id"]

    alert_policy_b_response = client.post(
        "/api/v1/platform/alert-policies",
        json={
            "scope_node_id": nursery_b["id"],
            "key": "nursery-b-alert",
            "name": "Nursery B Alert",
            "source_kind": "sensor",
            "severity": "critical",
            "rule_json": {"match": "low-moisture"},
        },
    )
    assert alert_policy_b_response.status_code == 201
    alert_policy_b_id = alert_policy_b_response.json()["alert_policy"]["id"]

    telemetry_a_response = client.post(
        "/api/v1/platform/telemetry",
        json={
            "scope_node_id": zone_a["id"],
            "source_kind": "sensor",
            "event_kind": "moisture",
            "severity": "warning",
            "source_id": "sensor-a",
            "payload_json": {"moisture": 0.12},
        },
    )
    assert telemetry_a_response.status_code == 201
    telemetry_a_id = telemetry_a_response.json()["telemetry_event"]["id"]

    telemetry_b_response = client.post(
        "/api/v1/platform/telemetry",
        json={
            "scope_node_id": zone_b["id"],
            "source_kind": "sensor",
            "event_kind": "moisture",
            "severity": "warning",
            "source_id": "sensor-b",
            "payload_json": {"moisture": 0.18},
        },
    )
    assert telemetry_b_response.status_code == 201
    telemetry_b_id = telemetry_b_response.json()["telemetry_event"]["id"]

    alert_a_response = client.post(
        "/api/v1/platform/alerts",
        json={
            "alert_policy_id": alert_policy_a_id,
            "scope_node_id": nursery_a["id"],
            "telemetry_event_id": telemetry_a_id,
            "summary": "Nursery A moisture is low.",
        },
    )
    assert alert_a_response.status_code == 201
    alert_a_id = alert_a_response.json()["alert"]["id"]

    alert_b_response = client.post(
        "/api/v1/platform/alerts",
        json={
            "alert_policy_id": alert_policy_b_id,
            "scope_node_id": nursery_b["id"],
            "telemetry_event_id": telemetry_b_id,
            "summary": "Nursery B moisture is low.",
        },
    )
    assert alert_b_response.status_code == 201
    alert_b_id = alert_b_response.json()["alert"]["id"]

    _login_user(client, username="nursery-user", password="test-user-password")

    nursery_scopes_response = client.get("/api/v1/platform/scopes")
    assert nursery_scopes_response.status_code == 200
    nursery_scopes = nursery_scopes_response.json()
    assert len(nursery_scopes) == 1
    assert nursery_scopes[0]["slug"] == "north-nursery"
    assert nursery_scopes[0]["children"][0]["slug"] == "north-site"
    assert nursery_scopes[0]["children"][0]["children"][0]["slug"] == "zone-a"

    nursery_catalog_response = client.get("/api/v1/platform/catalog")
    assert nursery_catalog_response.status_code == 200
    nursery_catalog = nursery_catalog_response.json()
    assert len(nursery_catalog["scopes"]) == 1
    assert nursery_catalog["scopes"][0]["slug"] == "north-nursery"

    nursery_events_response = client.get("/api/v1/platform/events")
    assert nursery_events_response.status_code == 200
    nursery_events = nursery_events_response.json()
    assert {item["event_type"] for item in nursery_events} == {
        "telemetry.recorded",
        "alert.opened",
    }
    assert {item["source_id"] for item in nursery_events} == {telemetry_a_id, alert_a_id}
    assert all(item["scope_node_id"] in {zone_a["id"], nursery_a["id"]} for item in nursery_events)

    blocked_events_query = f"/api/v1/platform/events?scope_node_id={organization['id']}"
    blocked_events_response = client.get(blocked_events_query)
    assert blocked_events_response.status_code == 404

    nursery_alerts_response = client.get("/api/v1/platform/alerts")
    assert nursery_alerts_response.status_code == 200
    nursery_alerts = nursery_alerts_response.json()
    assert [item["id"] for item in nursery_alerts] == [alert_a_id]

    _login_user(client, username="org-user", password="test-org-password")

    org_scopes_response = client.get("/api/v1/platform/scopes")
    assert org_scopes_response.status_code == 200
    org_scopes = org_scopes_response.json()
    assert org_scopes[0]["slug"] == "pineview-org"
    assert {child["slug"] for child in org_scopes[0]["children"]} >= {"operations"}

    org_events_response = client.get("/api/v1/platform/events")
    assert org_events_response.status_code == 200
    org_events = org_events_response.json()
    assert {item["source_id"] for item in org_events} == {
        telemetry_a_id,
        telemetry_b_id,
        alert_a_id,
        alert_b_id,
    }

    org_alerts_response = client.get("/api/v1/platform/alerts")
    assert org_alerts_response.status_code == 200
    org_alerts = org_alerts_response.json()
    assert {item["id"] for item in org_alerts} == {alert_a_id, alert_b_id}


def test_platform_execution_alert_and_change_set_routes_record_state(
    client: TestClient,
) -> None:
    _login_admin(client)

    catalog_response = client.get("/api/v1/platform/catalog")
    assert catalog_response.status_code == 200
    root_scope_id = next(
        item for item in catalog_response.json()["scopes"] if item["slug"] == "gardenos-platform"
    )["id"]

    automation_response = client.post(
        "/api/v1/platform/automations",
        json={
            "scope_node_id": root_scope_id,
            "key": "water-zones",
            "name": "Water Zones",
            "description": "Schedule and execute zone watering.",
        },
    )
    assert automation_response.status_code == 201
    automation_definition_id = automation_response.json()["automation_definition"]["id"]

    version_response = client.post(
        f"/api/v1/platform/automations/{automation_definition_id}/versions",
        json={
            "status": "active",
            "trigger_kind": "rrule",
            "summary": "Initial workflow version",
            "graph_json": {"nodes": [{"key": "water-zone"}], "edges": []},
        },
    )
    assert version_response.status_code == 201
    version_payload = version_response.json()["automation_version"]
    automation_version_id = version_payload["id"]

    schedule_response = client.post(
        "/api/v1/platform/schedule-rules",
        json={
            "scope_node_id": root_scope_id,
            "automation_version_id": automation_version_id,
            "trigger_kind": "rrule",
            "rrule": "FREQ=DAILY;INTERVAL=1",
            "calendar_label": "Daily watering",
        },
    )
    assert schedule_response.status_code == 201
    schedule_rule_id = schedule_response.json()["schedule_rule"]["id"]

    run_response = client.post(
        "/api/v1/platform/automation-runs",
        json={
            "automation_version_id": automation_version_id,
            "schedule_rule_id": schedule_rule_id,
            "triggered_by": "schedule",
            "reason": "daily watering window",
        },
    )
    assert run_response.status_code == 201
    automation_run_id = run_response.json()["automation_run"]["id"]

    run_event_response = client.post(
        f"/api/v1/platform/automation-runs/{automation_run_id}/events",
        json={
            "event_kind": "started",
            "status": "info",
            "payload_json": {"step": "queue"},
        },
    )
    assert run_event_response.status_code == 201
    automation_run_event_id = run_event_response.json()["automation_run_event"]["id"]

    telemetry_response = client.post(
        "/api/v1/platform/telemetry",
        json={
            "scope_node_id": root_scope_id,
            "source_kind": "sensor",
            "event_kind": "soil-moisture",
            "severity": "info",
            "source_id": "sensor-001",
            "payload_json": {"moisture": 0.31},
        },
    )
    assert telemetry_response.status_code == 201
    telemetry_event_id = telemetry_response.json()["telemetry_event"]["id"]

    alert_policy_response = client.post(
        "/api/v1/platform/alert-policies",
        json={
            "scope_node_id": root_scope_id,
            "key": "watering-failed",
            "name": "Watering Failed",
            "source_kind": "automation",
            "severity": "critical",
            "rule_json": {"match": "failed"},
        },
    )
    assert alert_policy_response.status_code == 201
    alert_policy_id = alert_policy_response.json()["alert_policy"]["id"]

    alert_response = client.post(
        "/api/v1/platform/alerts",
        json={
            "alert_policy_id": alert_policy_id,
            "scope_node_id": root_scope_id,
            "telemetry_event_id": telemetry_event_id,
            "automation_run_event_id": automation_run_event_id,
            "summary": "Watering workflow requires attention",
        },
    )
    assert alert_response.status_code == 201

    change_set_response = client.post(
        "/api/v1/platform/change-sets",
        json={
            "scope_node_id": root_scope_id,
            "key": "watering-update",
            "summary": "Adjust watering schedule",
            "reason": "Runtime change review",
        },
    )
    assert change_set_response.status_code == 201
    change_set_id = change_set_response.json()["change_set"]["id"]

    entry_response = client.post(
        f"/api/v1/platform/change-sets/{change_set_id}/entries",
        json={
            "entity_kind": "automation",
            "entity_id": automation_definition_id,
            "operation": "update",
            "diff_json": {"summary": "Adjust watering schedule"},
        },
    )
    assert entry_response.status_code == 201

    automation_runs_response = client.get("/api/v1/platform/automation-runs")
    assert automation_runs_response.status_code == 200
    assert automation_run_id in {item["id"] for item in automation_runs_response.json()}

    run_events_response = client.get("/api/v1/platform/automation-run-events")
    assert run_events_response.status_code == 200
    assert automation_run_event_id in {item["id"] for item in run_events_response.json()}

    telemetry_list_response = client.get("/api/v1/platform/telemetry")
    assert telemetry_list_response.status_code == 200
    assert telemetry_event_id in {item["id"] for item in telemetry_list_response.json()}

    alerts_response = client.get("/api/v1/platform/alerts")
    assert alerts_response.status_code == 200
    assert alert_policy_id in {item["alert_policy_id"] for item in alerts_response.json()}

    change_sets_list_response = client.get("/api/v1/platform/change-sets")
    assert change_sets_list_response.status_code == 200
    change_sets = change_sets_list_response.json()
    assert change_set_id in {item["id"] for item in change_sets}
    assert any(item["entry_count"] == 1 for item in change_sets if item["id"] == change_set_id)


def test_platform_calendar_projection_materializes_schedule_and_tasks(
    client: TestClient,
    session_factory,
) -> None:
    _login_admin(client)

    catalog_response = client.get("/api/v1/platform/catalog")
    assert catalog_response.status_code == 200
    root_scope_id = next(
        item for item in catalog_response.json()["scopes"] if item["slug"] == "gardenos-platform"
    )["id"]

    with session_factory() as session:
        task_definition = create_task_definition(
            session,
            {
                "title": "Inspect moisture trend",
                "description": "Review the next moisture window.",
                "task_type": "inspect",
                "priority": 2,
                "scope_type": "garden",
                "scope_id": root_scope_id,
                "estimated_minutes": 20,
                "is_active": True,
            },
        )
        ensure_task_occurrence(
            session,
            task_definition,
            scheduled_for=datetime.now(UTC) + timedelta(days=2),
            performed_by="test-suite",
        )
        session.commit()

    automation_response = client.post(
        "/api/v1/platform/automations",
        json={
            "scope_node_id": root_scope_id,
            "key": "calendar-projection",
            "name": "Calendar Projection",
            "description": "Projection used by the schedule calendar.",
        },
    )
    assert automation_response.status_code == 201
    automation_definition_id = automation_response.json()["automation_definition"]["id"]

    version_response = client.post(
        f"/api/v1/platform/automations/{automation_definition_id}/versions",
        json={
            "status": "active",
            "trigger_kind": "rrule",
            "summary": "Calendar version",
            "graph_json": {"nodes": [{"key": "project"}], "edges": []},
        },
    )
    assert version_response.status_code == 201
    automation_version_id = version_response.json()["automation_version"]["id"]

    schedule_response = client.post(
        "/api/v1/platform/schedule-rules",
        json={
            "scope_node_id": root_scope_id,
            "automation_version_id": automation_version_id,
            "trigger_kind": "rrule",
            "rrule": "FREQ=DAILY;INTERVAL=1",
            "calendar_label": "Calendar projection",
        },
    )
    assert schedule_response.status_code == 201
    schedule_rule = schedule_response.json()["schedule_rule"]
    assert schedule_rule["next_run_at"] is not None

    calendar_response = client.get("/api/v1/platform/calendar?days=14")
    assert calendar_response.status_code == 200
    calendar_payload = calendar_response.json()

    assert calendar_payload["summary"]["schedule_entry_count"] >= 1
    assert calendar_payload["summary"]["task_entry_count"] >= 1

    kinds = {entry["kind"] for entry in calendar_payload["entries"]}
    assert "schedule" in kinds
    assert "task" in kinds


def test_legacy_task_scope_is_backfilled_into_nursery_rollups(
    client: TestClient,
    session_factory,
) -> None:
    _login_admin(client)

    organization = _create_scope(
        client,
        parent_id=None,
        scope_type="organization",
        name="Pineview Organization",
        slug="pineview-org",
    )
    folder = _create_scope(
        client,
        parent_id=organization["id"],
        scope_type="folder",
        name="Shared Operations",
        slug="shared-operations",
    )
    nursery = _create_scope(
        client,
        parent_id=folder["id"],
        scope_type="nursery",
        name="Pineview Nursery",
        slug="pineview-nursery",
    )
    site = _create_scope(
        client,
        parent_id=nursery["id"],
        scope_type="site",
        name="North Site",
        slug="north-site",
    )
    zone = _create_scope(
        client,
        parent_id=site["id"],
        scope_type="zone",
        name="Zone B",
        slug="zone-b",
    )

    with session_factory() as session:
        location_root = Location(name="Pineview Organization", location_type="organization")
        location_nursery = Location(
            name="Pineview Nursery",
            location_type="nursery",
            parent=location_root,
        )
        location_site = Location(
            name="North Site",
            location_type="site",
            parent=location_nursery,
        )
        location_zone = Location(
            name="Zone B",
            location_type="zone",
            parent=location_site,
        )
        plant = Plant(display_id="PV-LEGACY", current_location=location_zone)
        session.add_all(
            [
                location_root,
                location_nursery,
                location_site,
                location_zone,
                plant,
            ],
        )
        session.flush()
        # Legacy location IDs require an explicit binding; matching display names
        # must never establish an authorization relationship.
        scope_zone = session.get(ScopeNode, zone["id"])
        assert scope_zone is not None
        scope_zone.metadata_json = {"source_location_id": location_zone.id}
        task_definition = TaskDefinition(
            title="Water legacy zone",
            description="Legacy plant-scoped task that should roll into the scope tree.",
            task_type="water",
            priority=1,
            scope_type="plant",
            scope_id=plant.id,
            estimated_minutes=15,
            is_active=True,
        )
        task_occurrence = TaskOccurrence(
            task_definition=task_definition,
            plant=plant,
            scheduled_for=datetime.now(UTC) + timedelta(days=1),
        )
        session.add_all([task_definition, task_occurrence])
        session.flush()
        assert backfill_task_definition_scope(session, task_definition) is True
        session.commit()

    calendar_response = client.get(
        f"/api/v1/platform/calendar?scope_node_id={nursery['id']}&days=14",
    )
    assert calendar_response.status_code == 200
    calendar_payload = calendar_response.json()
    assert calendar_payload["summary"]["task_entry_count"] == 1
    task_entry = next(item for item in calendar_payload["entries"] if item["kind"] == "task")
    assert task_entry["scope_node_id"] == zone["id"]
    assert task_entry["metadata"]["scope_node_id"] == zone["id"]
    assert task_entry["metadata"]["scope_source_kind"] == "scope_node"

    tasks_response = client.get("/api/v1/tasks")
    assert tasks_response.status_code == 200
    tasks_payload = tasks_response.json()
    assert tasks_payload["due_tasks"][0]["scope_node_id"] == zone["id"]
    assert tasks_payload["due_tasks"][0]["scope_source_kind"] == "scope_node"


def test_platform_event_outbox_and_stream_expose_realtime_contract(
    client: TestClient,
    session_factory,
    monkeypatch,
) -> None:
    _login_admin(client)

    catalog_response = client.get("/api/v1/platform/catalog")
    assert catalog_response.status_code == 200
    root_scope_id = next(
        item for item in catalog_response.json()["scopes"] if item["slug"] == "gardenos-platform"
    )["id"]

    with session_factory() as session:
        task_definition = create_task_definition(
            session,
            {
                "title": "Verify telemetry relay",
                "description": "Confirm realtime event delivery is working.",
                "task_type": "inspect",
                "priority": 2,
                "scope_type": "garden",
                "scope_id": root_scope_id,
                "estimated_minutes": 15,
                "is_active": True,
            },
        )
        task_occurrence = ensure_task_occurrence(
            session,
            task_definition,
            scheduled_for=datetime.now(UTC) + timedelta(days=1),
            performed_by="test-suite",
        )
        session.commit()

    automation_response = client.post(
        "/api/v1/platform/automations",
        json={
            "scope_node_id": root_scope_id,
            "key": "realtime-contract",
            "name": "Realtime Contract",
            "description": "Platform event regression coverage.",
        },
    )
    assert automation_response.status_code == 201
    automation_definition_id = automation_response.json()["automation_definition"]["id"]

    version_response = client.post(
        f"/api/v1/platform/automations/{automation_definition_id}/versions",
        json={
            "status": "active",
            "trigger_kind": "rrule",
            "summary": "Realtime contract version",
            "graph_json": {"nodes": [{"key": "relay"}], "edges": []},
        },
    )
    assert version_response.status_code == 201
    automation_version_id = version_response.json()["automation_version"]["id"]

    schedule_response = client.post(
        "/api/v1/platform/schedule-rules",
        json={
            "scope_node_id": root_scope_id,
            "automation_version_id": automation_version_id,
            "trigger_kind": "rrule",
            "rrule": "FREQ=DAILY;INTERVAL=1",
            "calendar_label": "Realtime contract",
        },
    )
    assert schedule_response.status_code == 201
    schedule_rule_id = schedule_response.json()["schedule_rule"]["id"]

    run_response = client.post(
        "/api/v1/platform/automation-runs",
        json={
            "automation_version_id": automation_version_id,
            "schedule_rule_id": schedule_rule_id,
            "triggered_by": "schedule",
            "reason": "realtime contract regression",
        },
    )
    assert run_response.status_code == 201
    automation_run_id = run_response.json()["automation_run"]["id"]

    run_event_response = client.post(
        f"/api/v1/platform/automation-runs/{automation_run_id}/events",
        json={
            "event_kind": "started",
            "status": "info",
            "payload_json": {"step": "queue"},
        },
    )
    assert run_event_response.status_code == 201
    automation_run_event_id = run_event_response.json()["automation_run_event"]["id"]

    telemetry_response = client.post(
        "/api/v1/platform/telemetry",
        json={
            "scope_node_id": root_scope_id,
            "source_kind": "sensor",
            "event_kind": "soil-moisture",
            "severity": "info",
            "source_id": "sensor-002",
            "payload_json": {"moisture": 0.29},
        },
    )
    assert telemetry_response.status_code == 201
    telemetry_event_id = telemetry_response.json()["telemetry_event"]["id"]

    alert_policy_response = client.post(
        "/api/v1/platform/alert-policies",
        json={
            "scope_node_id": root_scope_id,
            "key": "realtime-contract-alert",
            "name": "Realtime Contract Alert",
            "source_kind": "automation",
            "severity": "critical",
            "rule_json": {"match": "failed"},
        },
    )
    assert alert_policy_response.status_code == 201
    alert_policy_id = alert_policy_response.json()["alert_policy"]["id"]

    alert_response = client.post(
        "/api/v1/platform/alerts",
        json={
            "alert_policy_id": alert_policy_id,
            "scope_node_id": root_scope_id,
            "telemetry_event_id": telemetry_event_id,
            "automation_run_event_id": automation_run_event_id,
            "summary": "Realtime contract check requires attention",
        },
    )
    assert alert_response.status_code == 201
    alert_id = alert_response.json()["alert"]["id"]

    change_set_response = client.post(
        "/api/v1/platform/change-sets",
        json={
            "scope_node_id": root_scope_id,
            "key": "realtime-contract-change",
            "summary": "Validate realtime event emission",
            "reason": "Regression coverage",
        },
    )
    assert change_set_response.status_code == 201
    change_set_id = change_set_response.json()["change_set"]["id"]

    entry_response = client.post(
        f"/api/v1/platform/change-sets/{change_set_id}/entries",
        json={
            "entity_kind": "automation",
            "entity_id": automation_definition_id,
            "operation": "update",
            "diff_json": {"summary": "Validate realtime event emission"},
        },
    )
    assert entry_response.status_code == 201

    task_complete_response = client.post(
        f"/api/v1/tasks/{task_occurrence.id}/complete",
        json={
            "completion_notes": "Marked complete in regression test.",
            "performed_by": "test-suite",
        },
    )
    assert task_complete_response.status_code == 200

    events_response = client.get("/api/v1/platform/events")
    assert events_response.status_code == 200
    events = events_response.json()
    assert events

    event_types = {item["event_type"] for item in events}
    assert {
        "scheduler.schedule_rule.created",
        "automation.run.created",
        "automation.run.event.recorded",
        "telemetry.recorded",
        "alert.opened",
        "changeset.created",
        "changeset.entry.added",
        "task.occurrence.scheduled",
        "task.occurrence.completed",
    } <= event_types

    assert any(
        item["source_id"] == schedule_rule_id
        and item["event_type"] == "scheduler.schedule_rule.created"
        for item in events
    )
    assert any(
        item["source_id"] == alert_id and item["event_type"] == "alert.opened"
        for item in events
    )
    assert any(
        item["source_id"] == task_occurrence.id
        and item["event_type"] == "task.occurrence.completed"
        for item in events
    )

    latest_event_id = events[-1]["id"]

    follow_up_telemetry_response = client.post(
        "/api/v1/platform/telemetry",
        json={
            "scope_node_id": root_scope_id,
            "source_kind": "sensor",
            "event_kind": "air-temperature",
            "severity": "info",
            "source_id": "sensor-002",
            "payload_json": {"temperature_c": 28.4},
        },
    )
    assert follow_up_telemetry_response.status_code == 201
    follow_up_event_id = follow_up_telemetry_response.json()["telemetry_event"]["id"]

    from app.api.v1 import platform as platform_api

    disconnect_calls = {"count": 0}

    async def fake_is_disconnected(self) -> bool:
        disconnect_calls["count"] += 1
        return disconnect_calls["count"] > 1

    monkeypatch.setattr(platform_api.Request, "is_disconnected", fake_is_disconnected)

    response = client.get(
        f"/api/v1/platform/events/stream?after_id={latest_event_id}&limit=1",
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "id: " in response.text
    assert "data:" in response.text
    assert follow_up_event_id in response.text
