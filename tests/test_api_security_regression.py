from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _csrf_token(client: TestClient) -> str:
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    assert isinstance(token, str)
    assert token
    return token


def _login(client: TestClient, *, attach_csrf_header: bool = True) -> dict[str, object]:
    csrf_token = _csrf_token(client)
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "test-admin-password",
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 200
    if attach_csrf_header:
        refreshed = client.get("/api/v1/auth/session")
        client.headers.update({"x-csrf-token": refreshed.json()["csrf_token"]})
    return response.json()


def _create_onboarding_draft(client: TestClient) -> str:
    response = client.post("/api/v1/onboarding/drafts")
    assert response.status_code == 201
    draft_token = response.json()["draft_token"]
    assert isinstance(draft_token, str)
    assert draft_token
    return draft_token


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/plants", None),
        ("get", "/api/v1/tasks", None),
        ("get", "/api/v1/conversations", None),
        ("post", "/api/v1/plants", {}),
        ("post", "/api/v1/conversations", {"title": "Garden planning"}),
        ("post", "/api/v1/onboarding/drafts", None),
        ("patch", "/api/v1/onboarding/drafts/example-token/steps/1", {"step": 1}),
        ("post", "/api/v1/conversations/example-token/messages", {"content": "hi"}),
    ],
)
def test_protected_api_rejects_unauthenticated_requests(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    request = getattr(client, method)
    if payload is None:
        response = request(path)
    else:
        response = request(path, json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/v1/plants", {"scientific_name": "Acer palmatum"}),
        ("post", "/api/v1/conversations", {"title": "Security review"}),
        ("post", "/api/v1/onboarding/drafts", None),
    ],
)
def test_protected_writes_require_csrf_after_login(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    _login(client, attach_csrf_header=False)
    client.headers.pop("x-csrf-token", None)

    request = getattr(client, method)
    response = request(path, json=payload)

    assert response.status_code == 403
    assert "tampered" in response.json()["detail"].lower()


def test_login_rotates_session_cookie_and_sets_secure_attributes(client: TestClient) -> None:
    initial_token = _csrf_token(client)
    initial_cookie = client.cookies.get("garden_os_session")
    assert initial_cookie

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "test-admin-password",
            "csrf_token": initial_token,
        },
    )
    assert response.status_code == 200

    login_payload = response.json()
    assert login_payload["authenticated"] is True

    rotated_cookie = client.cookies.get("garden_os_session")
    assert rotated_cookie
    assert rotated_cookie != initial_cookie

    cookie_header = response.headers.get("set-cookie", "")
    assert "httponly" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()


def test_login_rate_limit_blocks_repeated_failures(client: TestClient, settings) -> None:
    csrf_token = _csrf_token(client)

    for _attempt in range(settings.login_rate_limit_attempts):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "incorrect-password",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "incorrect-password",
            "csrf_token": csrf_token,
        },
    )
    assert limited.status_code == 429
    assert "too many login attempts" in limited.json()["detail"].lower()


def test_login_rate_limit_applies_per_host_across_usernames(
    client: TestClient,
    settings,
) -> None:
    csrf_token = _csrf_token(client)

    for attempt in range(settings.login_rate_limit_attempts):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": f"unknown-{attempt}",
                "password": "incorrect-password",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/v1/auth/login",
        json={
            "username": "another-unknown-user",
            "password": "incorrect-password",
            "csrf_token": csrf_token,
        },
    )
    assert limited.status_code == 429
    assert "too many login attempts" in limited.json()["detail"].lower()


@pytest.mark.parametrize("origin", ["http://gardenos.example.test", "http://localhost:3000"])
def test_browser_api_allows_configured_frontend_origin(
    client: TestClient,
    origin: str,
) -> None:
    response = client.get("/api/v1/auth/context", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_browser_api_rejects_untrusted_origin(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/context",
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None


@pytest.mark.parametrize("host", ["api.gardenos.example.test", "app:8000"])
def test_backend_accepts_trusted_host_headers(client: TestClient, host: str) -> None:
    response = client.get("/health/live", headers={"Host": host})

    assert response.status_code == 200


def test_backend_rejects_untrusted_host_header(client: TestClient) -> None:
    response = client.get("/health/live", headers={"Host": "evil.example.com"})

    assert response.status_code == 400


def test_logout_requires_csrf(client: TestClient) -> None:
    _login(client, attach_csrf_header=False)

    response = client.post("/api/v1/auth/logout", json={})

    assert response.status_code == 403
    assert "tampered" in response.json()["detail"].lower()


def test_onboarding_media_rejects_unsupported_content_type(client: TestClient) -> None:
    _login(client)
    draft_token = _create_onboarding_draft(client)

    response = client.post(
        f"/api/v1/onboarding/drafts/{draft_token}/media",
        files={"file": ("payload.exe", b"evil", "application/x-msdownload")},
    )

    assert response.status_code == 400
    assert "unsupported media type" in response.json()["detail"].lower()


def test_onboarding_media_rejects_oversized_upload(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    draft_token = _create_onboarding_draft(client)
    monkeypatch.setattr("app.onboarding.services.MAX_UPLOAD_BYTES", 8)

    response = client.post(
        f"/api/v1/onboarding/drafts/{draft_token}/media",
        files={"file": ("payload.jpg", b"0123456789", "image/jpeg")},
    )

    assert response.status_code == 400
    assert "exceeds maximum allowed size" in response.json()["detail"].lower()


def test_plant_media_rejects_unsupported_content_type(client: TestClient) -> None:
    _login(client)

    created = client.post(
        "/api/v1/plants",
        json={"scientific_name": "Acer palmatum"},
    )
    assert created.status_code == 201
    plant_id = created.json()["id"]

    response = client.post(
        f"/api/v1/plants/{plant_id}/media",
        files={"file": ("payload.exe", b"evil", "application/x-msdownload")},
    )

    assert response.status_code == 400
    assert "unsupported media type" in response.json()["detail"].lower()
