from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from .chat import ChatEngine
from .client import GardenApiClient
from .config import load_settings

settings = load_settings()
api_client = GardenApiClient(settings)
chat_engine = ChatEngine(api_client)

app = FastAPI(title=settings.assistant_name, version="v1")


class ChatRequest(BaseModel):
    message: str


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    await api_client.auth_context()
    return {"status": "ready"}


@app.post("/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    return await chat_engine.respond(request.message)
