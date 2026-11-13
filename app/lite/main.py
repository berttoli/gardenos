from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.lite.admin import build_store
from app.lite.api import api_router, router
from app.lite.config import LiteSettings, load_lite_settings


def create_app(*, settings: LiteSettings | None = None) -> FastAPI:
    resolved_settings = settings or load_lite_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.store = build_store(resolved_settings)
        yield

    app = FastAPI(
        title=resolved_settings.app_name,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.settings = resolved_settings
    app.include_router(router)
    app.include_router(api_router)
    return app


app = create_app()
