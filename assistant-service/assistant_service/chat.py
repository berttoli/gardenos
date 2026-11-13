from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .client import GardenApiClient


@dataclass(slots=True)
class ChatTurn:
    role: str
    content: str


class ChatEngine:
    def __init__(self, api: GardenApiClient) -> None:
        self._api = api

    async def respond(self, message: str) -> dict[str, Any]:
        auth = await self._api.auth_context()
        workspace = await self._api.workspace() if auth.get("authenticated") else None
        system_services = await self._api.system_services()

        summary_lines = [
            "Assistant: GardenOS Local Assistant",
            f"Authenticated: {bool(auth.get('authenticated'))}",
            f"Input: {message}",
        ]
        if workspace is not None:
            summary_lines.append(
                f"Tasks due: {workspace.get('summary', {}).get('due_task_count', 0)}"
            )
        summary_lines.append(
            "System services: "
            + ", ".join(item["key"] for item in system_services.get("system_services", []))
        )
        return {
            "reply": "\n".join(summary_lines),
            "auth_context": auth,
            "workspace": workspace,
            "system_services": system_services,
        }
