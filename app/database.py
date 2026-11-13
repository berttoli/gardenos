from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

SessionFactory = Callable[[], Session]


class Base(DeclarativeBase):
    pass


def create_engine_from_url(database_url: str, *, echo: bool = False) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("Garden OS operational services require PostgreSQL.")
    kwargs: dict[str, Any] = {
        "echo": echo,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 1800,
        "pool_timeout": 30,
        "json_serializer": lambda value: json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "json_deserializer": json.loads,
    }
    return create_engine(database_url, **kwargs)


def create_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def check_database_ready(session_factory: SessionFactory) -> bool:
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
