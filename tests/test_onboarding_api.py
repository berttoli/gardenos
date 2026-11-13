from __future__ import annotations

from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    session = client.get("/api/v1/auth/session")
    csrf_token = session.json()["csrf_token"]

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "test-admin-password",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 200
    refreshed = client.get("/api/v1/auth/session")
    client.headers.update({"x-csrf-token": refreshed.json()["csrf_token"]})


def test_onboarding_draft_lifecycle(client: TestClient) -> None:
    _login(client)

    created = client.post("/api/v1/onboarding/drafts")
    assert created.status_code == 201

    draft = created.json()
    draft_token = draft["draft_token"]
    assert draft["current_step"] == 1

    saved = client.patch(
        f"/api/v1/onboarding/drafts/{draft_token}/steps/1",
        json={
            "scientific_name": "Acer palmatum",
            "common_name": "Japanese maple",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["state"]["plant"]["scientific_name"] == "Acer palmatum"

    detail = client.get(f"/api/v1/onboarding/drafts/{draft_token}")
    assert detail.status_code == 200
    assert detail.json()["current_step"] == 1

    completed = client.post(f"/api/v1/onboarding/drafts/{draft_token}/complete")
    assert completed.status_code == 201
    payload = completed.json()
    assert payload["draft"]["completed_at"] is not None
    assert payload["plant"]["display_id"]
