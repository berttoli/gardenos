from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.services import create_user


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


def _create_user(session_factory, *, username: str, full_name: str, password: str) -> None:
    with session_factory() as session:
        create_user(session, username=username, full_name=full_name, password=password)
        session.commit()


def _create_scope(
    client: TestClient,
    *,
    parent_id: str | None,
    scope_type: str,
    name: str,
    slug: str,
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


def test_monitoring_routes_support_alert_lifecycle_and_telemetry_drilldown(
    client: TestClient,
) -> None:
    _login_admin(client)

    root = next(
        item
        for item in client.get("/api/v1/platform/catalog").json()["scopes"]
        if item["slug"] == "gardenos-platform"
    )
    nursery = _create_scope(
        client,
        parent_id=root["id"],
        scope_type="nursery",
        name="North Nursery",
        slug="north-nursery",
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
        name="Zone A",
        slug="zone-a",
    )

    policy_response = client.post(
        "/api/v1/platform/alert-policies",
        json={
            "scope_node_id": nursery["id"],
            "key": "low-moisture",
            "name": "Low Moisture",
            "source_kind": "sensor",
            "severity": "critical",
            "rule_json": {"match": "moisture"},
        },
    )
    assert policy_response.status_code == 201
    policy_id = policy_response.json()["alert_policy"]["id"]

    telemetry_response = client.post(
        "/api/v1/platform/telemetry",
        json={
            "scope_node_id": zone["id"],
            "source_kind": "sensor",
            "event_kind": "moisture",
            "severity": "warning",
            "source_id": "sensor-01",
            "payload_json": {"moisture": 0.11, "trace_id": "trace-123"},
        },
    )
    assert telemetry_response.status_code == 201
    telemetry_id = telemetry_response.json()["telemetry_event"]["id"]

    alert_response = client.post(
        "/api/v1/platform/alerts",
        json={
            "alert_policy_id": policy_id,
            "scope_node_id": nursery["id"],
            "telemetry_event_id": telemetry_id,
            "summary": "Zone A moisture is low.",
        },
    )
    assert alert_response.status_code == 201
    alert_id = alert_response.json()["alert"]["id"]

    filtered_telemetry = client.get(
        "/api/v1/platform/telemetry",
        params={
            "scope_node_id": nursery["id"],
            "source_kind": "sensor",
            "severity": "warning",
        },
    )
    assert filtered_telemetry.status_code == 200
    assert [item["id"] for item in filtered_telemetry.json()] == [telemetry_id]

    telemetry_detail = client.get(f"/api/v1/platform/telemetry/{telemetry_id}")
    assert telemetry_detail.status_code == 200
    assert telemetry_detail.json()["id"] == telemetry_id

    alert_detail = client.get(f"/api/v1/platform/alerts/{alert_id}")
    assert alert_detail.status_code == 200
    assert alert_detail.json()["status"] == "open"

    acknowledged = client.post(f"/api/v1/platform/alerts/{alert_id}/acknowledge")
    assert acknowledged.status_code == 200
    assert acknowledged.json()["alert"]["status"] == "acknowledged"
    assert acknowledged.json()["alert"]["acknowledged_at"] is not None

    resolved = client.post(f"/api/v1/platform/alerts/{alert_id}/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["alert"]["status"] == "resolved"
    assert resolved.json()["alert"]["resolved_at"] is not None

    muted = client.post(f"/api/v1/platform/alerts/{alert_id}/mute")
    assert muted.status_code == 200
    assert muted.json()["alert"]["status"] == "muted"

    unmuted = client.post(f"/api/v1/platform/alerts/{alert_id}/unmute")
    assert unmuted.status_code == 200
    assert unmuted.json()["alert"]["status"] == "open"


def test_monitoring_routes_reject_under_privileged_service_tokens(
    client: TestClient,
    session_factory,
) -> None:
    _login_admin(client)
    _create_user(
        session_factory,
        username="observer-user",
        full_name="Observer User",
        password="test-observer-password",
    )

    service_account_response = client.post(
        "/api/v1/access/service-accounts",
        json={
            "slug": "observer-services",
            "name": "Observer Services",
            "role_keys": ["observer"],
        },
    )
    assert service_account_response.status_code == 201

    token_response = client.post(
        "/api/v1/access/service-accounts/observer-services/tokens",
        json={"label": "observer"},
    )
    assert token_response.status_code == 201
    client.headers.update({"authorization": f"Bearer {token_response.json()['token']}"})

    denied = client.post("/api/v1/platform/alerts/example-alert/acknowledge")
    assert denied.status_code == 403


def test_monitoring_routes_validate_missing_alerts_and_telemetry(client: TestClient) -> None:
    _login_admin(client)

    missing_alert = client.get("/api/v1/platform/alerts/does-not-exist")
    assert missing_alert.status_code == 404

    missing_telemetry = client.get("/api/v1/platform/telemetry/does-not-exist")
    assert missing_telemetry.status_code == 404
