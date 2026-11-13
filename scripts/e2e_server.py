"""Run a loopback-only API with disposable, entirely synthetic browser-test data.

The default SQLite database and media live in a temporary directory. To exercise
real migrations, GARDENOS_E2E_DATABASE_URL may name an empty local PostgreSQL
database called gardenos_e2e_test. Existing databases are never cleared or reset.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL, Engine, make_url

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.care.models import TaskDefinition, TaskOccurrence  # noqa: E402
from app.config import Settings  # noqa: E402
from app.database import Base, create_engine_from_url, create_session_factory  # noqa: E402

FIXTURE_DATABASE = "gardenos_e2e_test"


def validate_postgres_url(value: str) -> URL:
    """Reject production targets and connection-query overrides before connecting."""
    url = make_url(value)
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database != FIXTURE_DATABASE
        or url.query
    ):
        raise ValueError(
            "GARDENOS_E2E_DATABASE_URL must target an empty PostgreSQL database named "
            "gardenos_e2e_test on localhost or 127.0.0.1, without query parameters."
        )
    return url.set(drivername="postgresql+pg8000")


def prepare_postgres(url: URL, environment: dict[str, str]) -> Engine:
    engine = create_engine_from_url(url.render_as_string(hide_password=False))
    try:
        inspector = inspect(engine)
        schemas = [
            schema
            for schema in inspector.get_schema_names()
            if schema != "information_schema" and not schema.startswith("pg_")
        ]
        if schemas != ["public"] or any(
            inspector.get_table_names(schema=schema)
            or inspector.get_view_names(schema=schema)
            or inspector.get_materialized_view_names(schema=schema)
            for schema in schemas
        ):
            raise ValueError(
                "The E2E PostgreSQL database must be empty. Provision a fresh test database; "
                "this runner never drops or resets existing data."
            )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        return engine
    except Exception:
        engine.dispose()
        raise


def seed_tasks(engine: Engine) -> None:
    now = datetime.now(UTC)
    with create_session_factory(engine)() as session:
        for task_id, title, task_type, scheduled_for in (
            ("e2e-task", "Inspect example nursery", "inspect", now + timedelta(days=1)),
            ("e2e-overdue", "Water example seedlings", "water", now - timedelta(days=1)),
        ):
            session.add(
                TaskOccurrence(
                    id=task_id,
                    task_definition=TaskDefinition(
                        id=f"{task_id}-definition",
                        title=title,
                        task_type=task_type,
                        scope_type="garden",
                    ),
                    scheduled_for=scheduled_for,
                ),
            )
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--empty", action="store_true", help="Start with no task fixtures.")
    args = parser.parse_args()
    supplied_url = os.environ.get("GARDENOS_E2E_DATABASE_URL")
    postgres_url = validate_postgres_url(supplied_url) if supplied_url else None

    with TemporaryDirectory(prefix="gardenos-e2e-") as temporary_directory:
        state_dir = Path(temporary_directory)
        # app.main also constructs its module-level ASGI app on import. Give it
        # explicit synthetic settings before importing; never inherit real ones.
        configuration = {
            "APP_NAME": "GardenOS Browser Test",
            "ENVIRONMENT": "test",
            "DATABASE_URL": (
                postgres_url.render_as_string(hide_password=False)
                if postgres_url
                else "postgresql+pg8000://fixture:fixture@127.0.0.1/gardenos_e2e_test"
            ),
            "SECRET_KEY": "synthetic-e2e-secret-key-not-for-deployment",
            "ADMIN_USERNAME": "fixture-admin",
            "ADMIN_PASSWORD": "fixture-admin-password",
            "ADMIN_FULL_NAME": "Example Administrator",
            "ADMIN_EMAIL": "",
            "SESSION_COOKIE_NAME": "gardenos_e2e_session",
            "SESSION_COOKIE_SECURE": "false",
            "SESSION_COOKIE_SAMESITE": "lax",
            "CORS_ALLOW_ORIGINS": "http://127.0.0.1:3138,http://localhost:3138",
            "TRUSTED_HOSTS": "localhost,127.0.0.1",
            "MEDIA_ROOT": str(state_dir / "media"),
            "BACKUP_ROOT": str(state_dir / "backups"),
            "WAREHOUSE_DB_PATH": str(state_dir / "warehouse.duckdb"),
            "ASSISTANT_SERVICE_URL": "http://127.0.0.1:9",
            "DATABASE_ECHO": "false",
        }
        os.environ.update(configuration)
        from app.main import create_app

        settings = Settings.from_mapping(configuration)
        if postgres_url:
            engine = prepare_postgres(postgres_url, os.environ.copy())
        else:
            engine = create_engine(
                URL.create("sqlite+pysqlite", database=str(state_dir / "fixture.sqlite3")),
                connect_args={"check_same_thread": False},
            )
            Base.metadata.create_all(engine)

        try:
            if not args.empty:
                seed_tasks(engine)
            application = create_app(settings=settings, engine=engine)
            uvicorn.run(application, host="127.0.0.1", port=8138)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
