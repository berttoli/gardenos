from __future__ import annotations

from sqlalchemy.engine import Engine

from app.config import Settings, load_settings
from app.database import SessionFactory, create_engine_from_url, create_session_factory


def runtime() -> tuple[Settings, Engine, SessionFactory]:
    import app.models  # noqa: F401

    settings = load_settings()
    engine = create_engine_from_url(settings.database_url, echo=settings.database_echo)
    session_factory = create_session_factory(engine)
    return settings, engine, session_factory
