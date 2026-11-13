from fastapi.testclient import TestClient


def test_signed_out_auth_context_issues_a_usable_login_csrf_cookie(client: TestClient) -> None:
    context = client.get("/api/v1/auth/context")
    assert context.status_code == 200
    assert context.json()["authenticated"] is False
    response = client.post(
        "/api/v1/auth/login",
        headers={"x-csrf-token": context.json()["csrf_token"]},
        json={"username": "admin", "password": "test-admin-password"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/context").json()["authenticated"] is True
