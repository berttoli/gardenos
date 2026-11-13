from __future__ import annotations

import json

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
    refreshed = client.get("/api/v1/auth/session")
    client.headers.update({"X-CSRF-Token": refreshed.json()["csrf_token"]})


def test_platform_assistant_chat_proxies_to_container(client: TestClient, monkeypatch) -> None:
    _login_admin(client)

    from app.api.v1 import platform as platform_module

    class _Response:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

    def fake_urlopen(request, timeout: float):  # noqa: ANN001
        assert request.full_url == "http://assistant:8080/chat"
        assert timeout == 10.0
        payload = json.loads(request.data.decode("utf-8"))
        assert payload == {"message": "Summarize the nursery"}
        return _Response({"reply": "Assistant ready"})

    monkeypatch.setattr(platform_module, "urlopen", fake_urlopen)

    response = client.post(
        "/api/v1/platform/assistant/chat",
        json={"message": "Summarize the nursery"},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "Assistant ready"


def test_platform_assistant_chat_rejects_empty_message(client: TestClient) -> None:
    _login_admin(client)

    response = client.post("/api/v1/platform/assistant/chat", json={"message": " "})

    assert response.status_code == 400
