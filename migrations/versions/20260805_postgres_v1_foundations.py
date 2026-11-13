"""postgres v1 foundations

Revision ID: 20260805_postgres_v1_foundations
Revises: 0f0d112a9c11
Create Date: 2026-08-05 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260805_postgres_v1_foundations"
down_revision = "0f0d112a9c11"
branch_labels = None
depends_on = None


TIMESTAMPED_TABLES = (
    "users",
    "care_profiles",
    "containers",
    "label_templates",
    "locations",
    "onboarding_drafts",
    "task_definitions",
    "task_occurrences",
    "taxa",
    "plants",
    "plant_identifier_aliases",
    "plant_location_history",
    "plant_container_history",
    "plant_status_history",
    "observations",
    "health_assessments",
    "measurements",
    "treatments",
    "media_assets",
    "propagation_events",
)

CITEXT_COLUMNS: tuple[tuple[str, str, int], ...] = (
    ("users", "username", 64),
    ("care_profiles", "name", 160),
    ("containers", "identifier", 120),
    ("label_templates", "name", 160),
    ("plants", "display_id", 48),
    ("taxa", "scientific_name", 255),
)

JSONB_COLUMNS: tuple[tuple[str, str], ...] = (
    ("taxa", "common_names"),
    ("label_templates", "layout_definition"),
    ("onboarding_drafts", "state"),
    ("media_assets", "metadata"),
)

JSONB_NULLABLE_COLUMNS = {
    ("media_assets", "metadata"),
}


def _is_postgresql() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def _existing_tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _set_updated_at_triggers(enable: bool) -> None:
    if enable:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION set_updated_at()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
              NEW.updated_at = CURRENT_TIMESTAMP;
              RETURN NEW;
            END;
            $$;
            """,
        )
        for table in TIMESTAMPED_TABLES:
            op.execute(f"DROP TRIGGER IF EXISTS {table}_set_updated_at ON {table}")
            op.execute(
                f"""
                CREATE TRIGGER {table}_set_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION set_updated_at()
                """,
            )
    else:
        for table in TIMESTAMPED_TABLES:
            op.execute(f"DROP TRIGGER IF EXISTS {table}_set_updated_at ON {table}")
        op.execute("DROP FUNCTION IF EXISTS set_updated_at()")


def _set_timestamp_defaults(enable: bool) -> None:
    existing_tables = _existing_tables()
    for table in TIMESTAMPED_TABLES:
        if table not in existing_tables:
            continue
        for column in ("created_at", "updated_at"):
            if enable:
                op.alter_column(
                    table,
                    column,
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                )
            else:
                op.alter_column(
                    table,
                    column,
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    server_default=None,
                )


def _convert_text_columns(to_postgres: bool) -> None:
    existing_tables = _existing_tables()
    for table, column, length in CITEXT_COLUMNS:
        if table not in existing_tables:
            continue
        if to_postgres:
            op.alter_column(
                table,
                column,
                existing_type=sa.String(length=length),
                existing_nullable=False,
                type_=postgresql.CITEXT(),
                postgresql_using=f"{column}::citext",
            )
        else:
            op.alter_column(
                table,
                column,
                existing_type=postgresql.CITEXT(),
                existing_nullable=False,
                type_=sa.String(length=length),
                postgresql_using=f"{column}::varchar({length})",
            )


def _convert_json_columns(to_postgres: bool) -> None:
    existing_tables = _existing_tables()
    for table, column in JSONB_COLUMNS:
        if table not in existing_tables:
            continue
        if to_postgres:
            op.alter_column(
                table,
                column,
                existing_type=sa.JSON(),
                existing_nullable=(table, column) in JSONB_NULLABLE_COLUMNS,
                type_=postgresql.JSONB(),
                postgresql_using=f"{column}::jsonb",
            )
        else:
            op.alter_column(
                table,
                column,
                existing_type=postgresql.JSONB(),
                existing_nullable=(table, column) in JSONB_NULLABLE_COLUMNS,
                type_=sa.JSON(),
                postgresql_using=f"{column}::json",
            )


def _create_search_indexes() -> None:
    op.create_index(
        "ix_locations_name_trgm",
        "locations",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_task_definitions_title_trgm",
        "task_definitions",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )


def _drop_search_indexes() -> None:
    op.drop_index("ix_task_definitions_title_trgm", table_name="task_definitions")
    op.drop_index("ix_locations_name_trgm", table_name="locations")


def upgrade() -> None:
    if not _is_postgresql():
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    _convert_text_columns(to_postgres=True)
    _convert_json_columns(to_postgres=True)
    _set_timestamp_defaults(enable=True)
    _set_updated_at_triggers(enable=True)
    _create_search_indexes()


def downgrade() -> None:
    if not _is_postgresql():
        return

    _drop_search_indexes()
    _set_updated_at_triggers(enable=False)
    _set_timestamp_defaults(enable=False)
    _convert_json_columns(to_postgres=False)
    _convert_text_columns(to_postgres=False)
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS citext")
