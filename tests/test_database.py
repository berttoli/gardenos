from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.exc import SQLAlchemyError

from app.database import check_database_ready, create_engine_from_url


@contextmanager
def _successful_session_factory() -> object:
    class _Session:
        def execute(self, statement: object) -> object:
            return statement

    yield _Session()


@contextmanager
def _failing_session_factory() -> object:
    class _Session:
        def execute(self, statement: object) -> object:
            raise SQLAlchemyError("database unavailable")

    yield _Session()


def test_database_readiness() -> None:
    engine = create_engine_from_url("postgresql+pg8000://garden:garden@localhost:5432/garden")
    assert engine.dialect.name == "postgresql"
    engine.dispose()

    assert check_database_ready(_successful_session_factory) is True
    assert check_database_ready(_failing_session_factory) is False
