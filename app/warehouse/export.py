from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.config import Settings
from app.database import Base, SessionFactory


def _import_duckdb() -> Any:
    try:
        import duckdb  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - only hit when dependency is missing
        raise RuntimeError(
            "DuckDB support is not installed. "
            "Install the `duckdb` package to export a warehouse snapshot."
        ) from exc
    return duckdb


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _duckdb_type(column: Any) -> str:
    column_type = column.type
    if isinstance(column_type, Boolean):
        return "BOOLEAN"
    if isinstance(column_type, Integer):
        return "BIGINT"
    if isinstance(column_type, (Float, Numeric)):
        return "DOUBLE"
    if isinstance(column_type, Date):
        return "DATE"
    if isinstance(column_type, DateTime):
        return "TIMESTAMPTZ" if getattr(column_type, "timezone", False) else "TIMESTAMP"
    if isinstance(column_type, JSON):
        return "JSON"
    if isinstance(column_type, LargeBinary):
        return "BLOB"
    if isinstance(column_type, (String, Text)):
        return "VARCHAR"
    return "VARCHAR"


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, date):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    if isinstance(value, tuple):
        return json.dumps(list(value), sort_keys=True, default=str)
    return value


def _schema_version(session: Session) -> str | None:
    try:
        row = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    except Exception:
        return None
    if row is None:
        return None
    return str(row)


def _source_backend(session: Session) -> str:
    bind = session.get_bind()
    if bind is None:
        return "unknown"
    return bind.dialect.name


def _create_meta_table(connection: Any, metadata: Mapping[str, str]) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_meta (
          key VARCHAR NOT NULL,
          value VARCHAR NOT NULL
        )
        """,
    )
    if metadata:
        rows = list(metadata.items())
        connection.executemany(
            "INSERT INTO warehouse_meta (key, value) VALUES (?, ?)",
            rows,
        )


def _export_table(session: Session, connection: Any, table: Any) -> None:
    column_defs = ", ".join(
        f"{_quote_identifier(column.name)} {_duckdb_type(column)}" for column in table.columns
    )
    table_name = _quote_identifier(table.name)
    connection.execute(f"DROP TABLE IF EXISTS {table_name}")
    connection.execute(f"CREATE TABLE {table_name} ({column_defs})")
    bind = session.get_bind()
    if bind is None:
        return
    inspector = inspect(bind)
    if not inspector.has_table(table.name):
        return
    rows = session.execute(select(table)).mappings().all()
    if not rows:
        return
    column_names = [column.name for column in table.columns]
    placeholders = ", ".join(["?"] * len(column_names))
    insert_sql = (
        f"INSERT INTO {table_name} ({', '.join(_quote_identifier(name) for name in column_names)}) "
        f"VALUES ({placeholders})"
    )
    values = [
        tuple(_normalize_value(row.get(column_name)) for column_name in column_names)
        for row in rows
    ]
    connection.executemany(insert_sql, values)


def export_warehouse_snapshot(
    session_factory: SessionFactory,
    output_path: Path,
    *,
    settings: Settings | None = None,
) -> Path:
    resolved_path = Path(output_path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    duckdb = _import_duckdb()

    with session_factory() as session:
        metadata = {
            "exported_at": datetime.now(UTC).isoformat(),
            "source_backend": _source_backend(session),
            "schema_version": _schema_version(session) or "",
            "source_app": settings.app_name if settings is not None else "Garden OS",
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / resolved_path.name
            with duckdb.connect(str(tmp_path)) as connection:
                _create_meta_table(connection, metadata)
                for table in Base.metadata.sorted_tables:
                    _export_table(session, connection, table)
                connection.commit()
            if resolved_path.exists():
                resolved_path.unlink()
            shutil.move(str(tmp_path), str(resolved_path))
    return resolved_path
