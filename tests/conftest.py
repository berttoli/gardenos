from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

import app.models as app_models  # noqa: F401
from app.config import Settings, load_settings
from app.database import Base, SessionFactory, create_session_factory

# Explicit synthetic test configuration is required before importing the ASGI app.
# Application defaults deliberately contain no usable credentials.
os.environ.setdefault("SECRET_KEY", "synthetic-test-secret-key-not-for-runtime")
os.environ.setdefault("ADMIN_PASSWORD", "synthetic-test-password-not-for-runtime")
os.environ.setdefault("DATABASE_URL", "postgresql+pg8000://test:test@localhost/test")

from app.main import create_app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


@pytest.fixture()
def settings() -> Settings:
    return Settings.from_mapping(
        {
            "APP_NAME": "Garden OS Test",
            "ENVIRONMENT": "test",
            "SECRET_KEY": "test-secret-key-change-me-123456",
            "DATABASE_URL": "postgresql+pg8000://garden:garden@localhost:5432/garden",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "test-admin-password",
            "ADMIN_FULL_NAME": "Garden Administrator",
            "SESSION_COOKIE_SECURE": False,
            "CORS_ALLOW_ORIGINS": (
                "http://gardenos.example.test,http://localhost:3000,http://127.0.0.1:3000,"
                "http://localhost:8788,http://127.0.0.1:8788"
            ),
            "TRUSTED_HOSTS": (
                "localhost,127.0.0.1,[::1],testserver,app,frontend,"
                "gardenos.example.test,api.gardenos.example.test"
            ),
            "LOGIN_RATE_LIMIT_ATTEMPTS": 5,
            "LOGIN_RATE_LIMIT_WINDOW_SECONDS": 300,
        },
    )


@pytest.fixture()
def engine() -> Iterator[Engine]:
    # Test-only in-memory SQLite keeps the integration suite fast until a
    # disposable Postgres runner is added.
    db_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(db_engine)
    yield db_engine
    Base.metadata.drop_all(db_engine)
    db_engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> SessionFactory:
    return create_session_factory(engine)


@pytest.fixture()
def application(settings: Settings, engine: Engine, session_factory: SessionFactory) -> FastAPI:
    return create_app(settings=settings, engine=engine, session_factory=session_factory)


@pytest.fixture()
def client(application: FastAPI) -> Iterator[TestClient]:
    with TestClient(application) as test_client:
        yield test_client
