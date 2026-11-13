from __future__ import annotations

from fastapi.testclient import TestClient


def test_legacy_ui_routes_removed(client: TestClient) -> None:
    assert client.get("/login").status_code == 404
    assert client.get("/ui").status_code == 404
