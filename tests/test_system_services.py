from __future__ import annotations

from fastapi.testclient import TestClient


def _login_admin(client: TestClient) -> None:
    session = client.get("/api/v1/auth/session")
    csrf_token = session.json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "test-admin-password",
            "csrf_token": csrf_token,
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200


def test_system_services_surface_builtin_health(client: TestClient) -> None:
    _login_admin(client)

    response = client.get("/api/v1/platform/system-services")

    assert response.status_code == 200
    payload = response.json()
    keys = [item["key"] for item in payload["system_services"]]
    assert {"postgres", "api", "platform-catalog", "telemetry", "event-stream"} <= set(keys)
    postgres = next(item for item in payload["system_services"] if item["key"] == "postgres")
    api = next(item for item in payload["system_services"] if item["key"] == "api")
    assert postgres["status"] == "ready"
    assert api["details"]["health_endpoint"] == "/health/ready"
    assert payload["summary"]["service_count"] == 5
