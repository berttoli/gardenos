from __future__ import annotations

from fastapi.testclient import TestClient


def test_legacy_dashboard_route_removed(client: TestClient) -> None:
    response = client.get("/dashboard")

    assert response.status_code == 404
