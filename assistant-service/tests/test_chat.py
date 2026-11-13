from __future__ import annotations

from fastapi.testclient import TestClient

from assistant_service import main as assistant_main
from assistant_service.main import app


def test_health_live() -> None:
    client = TestClient(app)
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_responds_with_system_services(monkeypatch) -> None:
    async def fake_auth_context() -> dict[str, object]:
        return {"authenticated": True}

    async def fake_workspace() -> dict[str, object]:
        return {"summary": {"due_task_count": 2}}

    async def fake_system_services() -> dict[str, object]:
        return {"system_services": [{"key": "postgres"}, {"key": "api"}]}

    monkeypatch.setattr(assistant_main.api_client, "auth_context", fake_auth_context)
    monkeypatch.setattr(assistant_main.api_client, "workspace", fake_workspace)
    monkeypatch.setattr(assistant_main.api_client, "system_services", fake_system_services)

    client = TestClient(app)
    response = client.post("/chat", json={"message": "status"})

    assert response.status_code == 200
    payload = response.json()
    assert "Tasks due: 2" in payload["reply"]
    assert "postgres" in payload["reply"]
