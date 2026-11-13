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


def _login_admin(client: TestClient) -> dict[str, object]:
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
    return response.json()


def _create_user(session_factory, *, username: str, full_name: str, password: str) -> None:
    with session_factory() as session:
        create_user(
            session,
            username=username,
            full_name=full_name,
            password=password,
        )
        session.commit()


def test_admin_can_view_seeded_access_catalog(client: TestClient) -> None:
    _login_admin(client)

    context_response = client.get("/api/v1/auth/context")
    assert context_response.status_code == 200
    context = context_response.json()
    assert context["principal"]["kind"] == "user"
    assert context["principal"]["is_admin"] is True

    roles_response = client.get("/api/v1/access/roles")
    assert roles_response.status_code == 200
    role_keys = {item["key"] for item in roles_response.json()}
    assert {"admin", "user", "observer", "operator", "automation", "service_account"} <= role_keys

    groups_response = client.get("/api/v1/access/groups")
    assert groups_response.status_code == 200
    groups = {item["slug"]: item for item in groups_response.json()}
    assert {"platform-admins", "garden-users", "garden-operators"} <= set(groups)
    assert "automation-services" in groups
    assert "observability-services" in groups

    service_accounts_response = client.get("/api/v1/access/service-accounts")
    assert service_accounts_response.status_code == 200
    service_account_slugs = {item["slug"] for item in service_accounts_response.json()}
    assert {"garden-automation", "garden-monitoring"} <= service_account_slugs


def test_admin_can_provision_service_account_and_service_token_authenticates(
    client: TestClient,
) -> None:
    _login_admin(client)

    service_account_response = client.post(
        "/api/v1/access/service-accounts",
        json={
            "slug": "weather-bridge",
            "name": "Weather Bridge",
            "account_type": "connector",
            "group_slug": "automation-services",
            "role_keys": ["automation"],
        },
    )
    assert service_account_response.status_code == 201
    service_account = service_account_response.json()["service_account"]
    assert service_account["slug"] == "weather-bridge"
    assert "automation" in service_account["role_keys"]

    token_response = client.post(
        "/api/v1/access/service-accounts/weather-bridge/tokens",
        json={
            "label": "bootstrap",
        },
    )
    assert token_response.status_code == 201
    token_payload = token_response.json()
    token_value = token_payload["token"]
    assert isinstance(token_value, str)
    assert token_value.startswith("gsat_")

    client.headers.update({"authorization": f"Bearer {token_value}"})

    auth_context_response = client.get("/api/v1/auth/context")
    assert auth_context_response.status_code == 200
    auth_context = auth_context_response.json()
    assert auth_context["principal"]["kind"] == "service_account"
    assert auth_context["principal"]["auth_method"] == "service_token"
    assert auth_context["principal"]["service_account_slug"] == "weather-bridge"
    assert "automation.execute" in auth_context["principal"]["permissions"]

    catalog_response = client.get("/api/v1/access/context")
    assert catalog_response.status_code == 200
    assert catalog_response.json()["principal"]["kind"] == "service_account"

    denied_response = client.post(
        "/api/v1/access/service-accounts",
        json={
            "slug": "blocked-account",
            "name": "Blocked Account",
        },
    )
    assert denied_response.status_code == 403
    assert "permissions" in denied_response.json()["detail"].lower()


def test_under_privileged_service_token_cannot_hit_admin_mutation_routes(
    client: TestClient,
) -> None:
    _login_admin(client)

    service_account_response = client.post(
        "/api/v1/access/service-accounts",
        json={
            "slug": "observer-bridge",
            "name": "Observer Bridge",
            "role_keys": ["observer"],
        },
    )
    assert service_account_response.status_code == 201

    token_response = client.post(
        "/api/v1/access/service-accounts/observer-bridge/tokens",
        json={"label": "observer"},
    )
    assert token_response.status_code == 201
    token_value = token_response.json()["token"]
    client.headers.update({"authorization": f"Bearer {token_value}"})

    mutation_attempts = [
        (
            "/api/v1/access/roles",
            {"key": "blocked-role", "name": "Blocked Role"},
        ),
        (
            "/api/v1/access/groups",
            {"slug": "blocked-group", "name": "Blocked Group"},
        ),
        (
            "/api/v1/access/service-accounts",
            {"slug": "blocked-account", "name": "Blocked Account"},
        ),
    ]

    for path, payload in mutation_attempts:
        response = client.post(path, json=payload)
        assert response.status_code == 403


def test_group_membership_and_role_assignment_routes_work(
    client: TestClient,
    session_factory,
) -> None:
    _login_admin(client)
    _create_user(
        session_factory,
        username="nursery-user",
        full_name="Nursery User",
        password="test-user-password",
    )

    group_response = client.post(
        "/api/v1/access/groups",
        json={
            "slug": "pineview-nursery",
            "name": "Pineview Nursery",
            "group_type": "nursery",
            "scope_type": "organization",
            "scope_id": "pineview",
            "role_keys": ["user"],
        },
    )
    assert group_response.status_code == 201
    group = group_response.json()["group"]
    assert group["slug"] == "pineview-nursery"
    assert "user" in group["role_keys"]

    add_member_response = client.post(
        "/api/v1/access/groups/pineview-nursery/members",
        json={
            "username": "nursery-user",
        },
    )
    assert add_member_response.status_code == 201
    detail = add_member_response.json()
    assert detail["group"]["member_count"] == 1
    assert detail["members"][0]["username"] == "nursery-user"

    add_role_response = client.post(
        "/api/v1/access/groups/pineview-nursery/roles",
        json={
            "role_key": "observer",
        },
    )
    assert add_role_response.status_code == 201
    updated = add_role_response.json()
    assert {"user", "observer"} <= set(updated["group"]["role_keys"])
