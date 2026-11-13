from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.services import create_user


def _auth_session(client: TestClient) -> dict[str, object]:
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 200
    return response.json()


def _csrf_token(client: TestClient) -> str:
    session = _auth_session(client)
    csrf_token = session["csrf_token"]
    assert isinstance(csrf_token, str)
    assert csrf_token
    return csrf_token


def _login(
    client: TestClient,
    *,
    username: str,
    password: str,
    next_url: str = "/",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": password,
            "csrf_token": _csrf_token(client),
            "next": next_url,
        },
    )
    assert response.status_code == 200
    return response.json()


def _create_user(
    session_factory,
    *,
    username: str,
    full_name: str,
    password: str,
    email: str | None = None,
    is_active: bool = True,
    is_admin: bool = False,
) -> None:
    with session_factory() as session:
        create_user(
            session,
            username=username,
            full_name=full_name,
            password=password,
            email=email,
            is_active=is_active,
            is_admin=is_admin,
        )
        session.commit()


def test_session_starts_unauthenticated(client: TestClient) -> None:
    payload = _auth_session(client)

    assert payload["authenticated"] is False
    assert payload["user"] is None
    assert payload["csrf_token"]


def test_auth_context_starts_unauthenticated(client: TestClient) -> None:
    payload = client.get("/api/v1/auth/context")

    assert payload.status_code == 200
    context = payload.json()
    assert context["authenticated"] is False
    assert context["principal"] is None
    assert context["user"] is None
    assert context["csrf_token"]


def test_admin_login_exposes_admin_role(client: TestClient) -> None:
    payload = _login(
        client,
        username="admin",
        password="test-admin-password",
    )

    assert payload["authenticated"] is True
    assert payload["next_url"] == "/"
    assert payload["user"]["username"] == "admin"
    assert payload["user"]["full_name"] == "Garden Administrator"
    assert payload["user"]["is_admin"] is True
    assert payload["user"]["role"] == "admin"

    session = _auth_session(client)
    assert session["authenticated"] is True
    assert session["user"]["role"] == "admin"

    auth_context = client.get("/api/v1/auth/context")
    assert auth_context.status_code == 200
    context = auth_context.json()
    assert context["authenticated"] is True
    assert context["principal"]["kind"] == "user"
    assert context["principal"]["is_admin"] is True


def test_standard_user_login_exposes_user_role(
    client: TestClient,
    session_factory,
) -> None:
    _create_user(
        session_factory,
        username="nursery-user",
        full_name="Nursery User",
        password="test-user-password",
        email="nursery-user@example.com",
    )

    payload = _login(
        client,
        username="nursery-user",
        password="test-user-password",
    )

    assert payload["authenticated"] is True
    assert payload["user"]["username"] == "nursery-user"
    assert payload["user"]["full_name"] == "Nursery User"
    assert payload["user"]["is_admin"] is False
    assert payload["user"]["role"] == "user"

    session = _auth_session(client)
    assert session["authenticated"] is True
    assert session["user"]["role"] == "user"


def test_login_failure(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "incorrect-password",
            "csrf_token": _csrf_token(client),
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_login_rejects_inactive_user(client: TestClient, session_factory) -> None:
    _create_user(
        session_factory,
        username="disabled-user",
        full_name="Disabled User",
        password="test-user-password",
        is_active=False,
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "disabled-user",
            "password": "test-user-password",
            "csrf_token": _csrf_token(client),
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_login_csrf_rejection(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "test-admin-password",
            "csrf_token": "tampered-token",
        },
    )

    assert response.status_code == 403
    assert "tampered" in response.json()["detail"].lower()


def test_login_next_url_is_sanitized(client: TestClient) -> None:
    payload = _login(
        client,
        username="admin",
        password="test-admin-password",
        next_url="https://example.com/phish",
    )

    assert payload["next_url"] == "/"


def test_login_next_url_rejects_protocol_relative_redirect(client: TestClient) -> None:
    payload = _login(
        client,
        username="admin",
        password="test-admin-password",
        next_url="//example.com/phish",
    )

    assert payload["next_url"] == "/"


def test_login_success_and_logout(client: TestClient) -> None:
    _login(
        client,
        username="admin",
        password="test-admin-password",
    )

    session = _auth_session(client)
    assert session["authenticated"] is True

    logout = client.post("/api/v1/auth/logout", json={"csrf_token": session["csrf_token"]})
    assert logout.status_code == 200
    assert logout.json() == {"authenticated": False}

    final_session = _auth_session(client)
    assert final_session["authenticated"] is False
    assert final_session["user"] is None


def test_login_rate_limit_uses_forwarded_client_identity(client: TestClient) -> None:
    csrf_token = _csrf_token(client)
    headers = {"X-Forwarded-For": "203.0.113.9"}

    for _attempt in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "incorrect-password",
                "csrf_token": csrf_token,
            },
            headers=headers,
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "incorrect-password",
            "csrf_token": csrf_token,
        },
        headers=headers,
    )

    assert limited.status_code == 429
