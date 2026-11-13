from __future__ import annotations

from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    session = client.get("/api/v1/auth/session")
    token = session.json()["csrf_token"]

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "test-admin-password",
            "csrf_token": token,
        },
    )

    assert response.status_code == 200
    refreshed = client.get("/api/v1/auth/session")
    client.headers.update({"x-csrf-token": refreshed.json()["csrf_token"]})


def test_conversation_lifecycle(client: TestClient) -> None:
    _login(client)

    created = client.post(
        "/api/v1/conversations",
        json={
            "title": "Garden planning",
            "description": "Live notes for the new plot layout",
        },
        follow_redirects=False,
    )
    assert created.status_code == 201

    conversation = created.json()
    conversation_id = conversation["id"]
    assert conversation["title"] == "Garden planning"
    assert conversation["message_count"] == 0
    assert conversation["created_by_user_id"] is not None

    message_create = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={
            "role": "user",
            "content": "Show me the watering queue.",
            "metadata": {"source": "test"},
        },
        follow_redirects=False,
    )
    assert message_create.status_code == 201

    message = message_create.json()
    assert message["conversation_id"] == conversation_id
    assert message["role"] == "user"
    assert message["content"] == "Show me the watering queue."
    assert message["metadata"]["source"] == "test"

    detail = client.get(f"/api/v1/conversations/{conversation_id}", follow_redirects=False)
    assert detail.status_code == 200

    payload = detail.json()
    assert payload["conversation"]["id"] == conversation_id
    assert payload["conversation"]["message_count"] == 1
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["content"] == "Show me the watering queue."

    listing = client.get("/api/v1/conversations?limit=10", follow_redirects=False)
    assert listing.status_code == 200
    assert listing.json()["count"] == 1
