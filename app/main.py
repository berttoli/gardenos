from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.access.services import ensure_default_access
from app.api.v1.router import router as api_router
from app.api.v2.router import router as rpc_v2_router
from app.auth.services import ensure_admin_user
from app.config import Settings, load_settings
from app.core.rate_limit import LoginRateLimiter
from app.database import Engine, SessionFactory, create_engine_from_url, create_session_factory
from app.health.routes import router as health_router
from app.labels.services import ensure_default_label_templates
from app.media.routes import router as media_router
from app.models import User  # noqa: F401
from app.platform.services import ensure_default_platform_catalog
from app.startup import run_database_migrations


def _build_services(
    settings: Settings,
    engine: Engine | None = None,
    session_factory: SessionFactory | None = None,
) -> tuple[Engine | None, SessionFactory]:
    if session_factory is not None:
        return engine, session_factory
    if engine is None:
        engine = create_engine_from_url(settings.database_url, echo=settings.database_echo)
    return engine, create_session_factory(engine)


def create_app(
    *,
    settings: Settings | None = None,
    engine: Engine | None = None,
    session_factory: SessionFactory | None = None,
) -> FastAPI:
    resolved_settings = settings or load_settings()
    resolved_engine, resolved_session_factory = _build_services(
        resolved_settings,
        engine=engine,
        session_factory=session_factory,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if resolved_session_factory is not None:
            run_database_migrations(resolved_settings)
            with resolved_session_factory() as db:
                admin_user = ensure_admin_user(db, resolved_settings)
                ensure_default_access(db, admin_user=admin_user)
                ensure_default_platform_catalog(db)
                ensure_default_label_templates(db)
                db.commit()
        yield
        if resolved_engine is not None:
            resolved_engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version="v1",
        summary="Garden OS operational API",
        description=(
            "Garden OS v1 is the canonical Postgres-backed HTTP/JSON contract for the "
            "frontend shell, operational workflows, and platform services."
        ),
        openapi_tags=[
            {"name": "v1", "description": "Top-level v1 API namespace."},
            {"name": "auth", "description": "Session, CSRF, and bootstrap authentication."},
            {"name": "workspace", "description": "Frontend shell bootstrap payloads."},
            {"name": "access", "description": "Roles, groups, permissions, and service accounts."},
            {"name": "onboarding", "description": "Onboarding drafts and media capture."},
            {
                "name": "platform",
                "description": "Scopes, automations, telemetry, alerts, and calendar.",
            },
        ],
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.engine = resolved_engine
    app.state.session_factory = resolved_session_factory
    app.state.login_rate_limiter = LoginRateLimiter(
        max_attempts=resolved_settings.login_rate_limit_attempts,
        window_seconds=resolved_settings.login_rate_limit_window_seconds,
    )

    if resolved_settings.trusted_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=list(resolved_settings.trusted_hosts),
        )

    if resolved_settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_allow_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(
        SessionMiddleware,
        secret_key=resolved_settings.secret_key,
        session_cookie=resolved_settings.session_cookie_name,
        same_site=resolved_settings.session_same_site,
        https_only=resolved_settings.session_https_only,
        max_age=resolved_settings.session_max_age_seconds,
    )
    app.include_router(api_router)
    app.include_router(rpc_v2_router)
    app.include_router(media_router)
    app.include_router(health_router)
    return app


app = create_app()
