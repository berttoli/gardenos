from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.request import Request, urlopen

from .config import Settings


class GardenApiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def _request(
        self,
        method: str,
        path: str,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        headers: dict[str, str] = {}
        if self._settings.garden_api_token:
            headers["Authorization"] = f"Bearer {self._settings.garden_api_token}"

        def sync_request() -> Any:
            payload = None
            if json_body is not None:
                payload = json.dumps(json_body).encode("utf-8")
                headers["Content-Type"] = "application/json"
            request = Request(
                f"{self._settings.garden_api_base_url}{path}",
                data=payload,
                headers=headers,
                method=method,
            )
            with urlopen(request, timeout=10.0) as response:
                return json.loads(response.read().decode("utf-8"))

        from asyncio import to_thread

        return await to_thread(sync_request)

    async def auth_context(self) -> dict[str, Any]:
        return await self._request("GET", "/auth/context")

    async def workspace(self) -> dict[str, Any]:
        return await self._request("GET", "/workspace")

    async def system_services(self) -> dict[str, Any]:
        return await self._request("GET", "/platform/system-services")
