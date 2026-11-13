from __future__ import annotations

from fastapi.testclient import TestClient


def test_rpc_query_workspace_bootstrap(client: TestClient) -> None:
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    csrf_token = session.json()["csrf_token"]

    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "test-admin-password",
            "csrf_token": csrf_token,
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/v2/rpc",
        json={
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "rpc.query.workspace.bootstrap",
            "params": {"version": "v2"},
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == "req-1"
    assert payload["result"]["version"] == "v2"
    assert "sidebar" in payload["result"]["data"]


def test_rpc_query_auth_context(client: TestClient) -> None:
    response = client.post(
        "/api/v2/rpc",
        json={
            "jsonrpc": "2.0",
            "id": "req-2",
            "method": "rpc.query.auth.context",
            "params": {"version": "v2"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["version"] == "v2"
    assert payload["result"]["data"]["authenticated"] is False


def test_rpc_rejects_unknown_method(client: TestClient) -> None:
    response = client.post(
        "/api/v2/rpc",
        json={
            "jsonrpc": "2.0",
            "id": "req-3",
            "method": "rpc.query.missing.method",
            "params": {"version": "v2"},
        },
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == -32601
