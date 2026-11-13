"""add platform event outbox

Revision ID: 20260813_platform_events
Revises: 20260811_platform_spine
Create Date: 2026-08-13 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260813_platform_events"
down_revision = "20260811_platform_spine"
branch_labels = None
depends_on = None


TIMESTAMPED_TABLES = ("platform_events",)


def _is_postgresql() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def _create_updated_at_triggers() -> None:
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


def _drop_updated_at_triggers() -> None:
    for table in TIMESTAMPED_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_set_updated_at ON {table}")


def upgrade() -> None:
    if not _is_postgresql():
        return

    op.create_table(
        "platform_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.String(length=24), nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=True),
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_events_created_at",
        "platform_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_platform_events_scope_created_at",
        "platform_events",
        ["scope_node_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_platform_events_event_type",
        "platform_events",
        ["event_type"],
        unique=False,
    )
    _create_updated_at_triggers()


def downgrade() -> None:
    if not _is_postgresql():
        return

    _drop_updated_at_triggers()
    op.drop_index("ix_platform_events_event_type", table_name="platform_events")
    op.drop_index("ix_platform_events_scope_created_at", table_name="platform_events")
    op.drop_index("ix_platform_events_created_at", table_name="platform_events")
    op.drop_table("platform_events")
