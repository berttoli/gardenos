"""add access control catalog and service accounts

Revision ID: 20260810_access_iam
Revises: 20260805_postgres_v1_foundations
Create Date: 2026-08-10 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260810_access_iam"
down_revision = "20260805_postgres_v1_foundations"
branch_labels = None
depends_on = None


TIMESTAMPED_TABLES = (
    "permissions",
    "roles",
    "role_permissions",
    "groups",
    "group_memberships",
    "group_roles",
    "service_accounts",
    "service_account_roles",
    "service_account_tokens",
)


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

    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "permissions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("key", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
        sa.UniqueConstraint("key", name="uq_permissions_key"),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("key", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
        sa.UniqueConstraint("key", name="uq_roles_key"),
    )

    op.create_table(
        "groups",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("slug", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("group_type", sa.String(length=32), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=True),
        sa.Column("scope_id", sa.String(length=36), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
        sa.UniqueConstraint("slug", name="uq_groups_slug"),
    )

    op.create_table(
        "service_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("slug", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("account_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "group_id",
            sa.String(length=36),
            sa.ForeignKey("groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("slug", name="uq_service_accounts_slug"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "role_id",
            sa.String(length=36),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            sa.String(length=36),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.UniqueConstraint(
            "role_id",
            "permission_id",
            name="uq_role_permissions_role_permission",
        ),
    )

    op.create_table(
        "group_memberships",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "group_id",
            sa.String(length=36),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_memberships_group_user"),
    )

    op.create_table(
        "group_roles",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "group_id",
            sa.String(length=36),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.String(length=36),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.UniqueConstraint("group_id", "role_id", name="uq_group_roles_group_role"),
    )

    op.create_table(
        "service_account_roles",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "service_account_id",
            sa.String(length=36),
            sa.ForeignKey("service_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.String(length=36),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.UniqueConstraint(
            "service_account_id",
            "role_id",
            name="uq_service_account_roles_service_account_role",
        ),
    )

    op.create_table(
        "service_account_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "service_account_id",
            sa.String(length=36),
            sa.ForeignKey("service_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("token_hash", name="uq_service_account_tokens_token_hash"),
    )

    op.create_index("ix_group_memberships_group_id", "group_memberships", ["group_id"])
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"])
    op.create_index("ix_group_roles_group_id", "group_roles", ["group_id"])
    op.create_index("ix_group_roles_role_id", "group_roles", ["role_id"])
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index(
        "ix_role_permissions_permission_id",
        "role_permissions",
        ["permission_id"],
    )
    op.create_index("ix_service_accounts_group_id", "service_accounts", ["group_id"])
    op.create_index(
        "ix_service_accounts_created_by_user_id",
        "service_accounts",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_service_account_roles_service_account_id",
        "service_account_roles",
        ["service_account_id"],
    )
    op.create_index("ix_service_account_roles_role_id", "service_account_roles", ["role_id"])
    op.create_index(
        "ix_service_account_tokens_service_account_id",
        "service_account_tokens",
        ["service_account_id"],
    )
    op.create_index(
        "ix_service_account_tokens_token_prefix", "service_account_tokens", ["token_prefix"]
    )

    _create_updated_at_triggers()


def downgrade() -> None:
    if not _is_postgresql():
        return

    _drop_updated_at_triggers()

    op.drop_index("ix_service_account_tokens_token_prefix", table_name="service_account_tokens")
    op.drop_index(
        "ix_service_account_tokens_service_account_id",
        table_name="service_account_tokens",
    )
    op.drop_index("ix_service_account_roles_role_id", table_name="service_account_roles")
    op.drop_index(
        "ix_service_account_roles_service_account_id",
        table_name="service_account_roles",
    )
    op.drop_index("ix_service_accounts_created_by_user_id", table_name="service_accounts")
    op.drop_index("ix_service_accounts_group_id", table_name="service_accounts")
    op.drop_index("ix_role_permissions_permission_id", table_name="role_permissions")
    op.drop_index("ix_role_permissions_role_id", table_name="role_permissions")
    op.drop_index("ix_group_roles_role_id", table_name="group_roles")
    op.drop_index("ix_group_roles_group_id", table_name="group_roles")
    op.drop_index("ix_group_memberships_user_id", table_name="group_memberships")
    op.drop_index("ix_group_memberships_group_id", table_name="group_memberships")

    op.drop_table("service_account_tokens")
    op.drop_table("service_account_roles")
    op.drop_table("group_roles")
    op.drop_table("group_memberships")
    op.drop_table("role_permissions")
    op.drop_table("service_accounts")
    op.drop_table("groups")
    op.drop_table("roles")
    op.drop_table("permissions")
