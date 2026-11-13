"""add platform spine tables

Revision ID: 20260811_platform_spine
Revises: 20260810_access_iam
Create Date: 2026-08-11 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260811_platform_spine"
down_revision = "20260810_access_iam"
branch_labels = None
depends_on = None


TIMESTAMPED_TABLES = (
    "scope_nodes",
    "scope_memberships",
    "skill_definitions",
    "connector_definitions",
    "connector_instances",
    "service_actions",
    "automation_definitions",
    "automation_versions",
    "automation_nodes",
    "automation_edges",
    "schedule_rules",
    "telemetry_events",
    "alert_policies",
    "alerts",
    "change_sets",
    "automation_runs",
    "automation_run_events",
    "change_set_entries",
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
        "scope_nodes",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "parent_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("slug", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_template_id", sa.String(length=36), nullable=True),
        sa.Column(
            "is_system_template",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("parent_id", "slug", name="uq_scope_nodes_parent_slug"),
    )

    op.create_table(
        "scope_memberships",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role_key", postgresql.CITEXT(length=64), nullable=False),
        sa.Column("access_level", postgresql.CITEXT(length=32), nullable=False),
        sa.Column(
            "can_view_telemetry",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "can_manage_automations",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "can_approve_mutations",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "inherits_to_descendants",
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
        sa.UniqueConstraint("scope_node_id", "user_id", "role_key", name="uq_scope_memberships"),
    )

    op.create_table(
        "skill_definitions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("skill_kind", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_template_id", sa.String(length=36), nullable=True),
        sa.Column(
            "is_system_template",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
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
        sa.UniqueConstraint("scope_node_id", "key", name="uq_skill_definitions"),
    )

    op.create_table(
        "connector_definitions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("connector_kind", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("auth_kind", sa.String(length=40), nullable=False),
        sa.Column(
            "supports_offline",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("source_template_id", sa.String(length=36), nullable=True),
        sa.Column(
            "is_system_template",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
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
        sa.UniqueConstraint("scope_node_id", "key", name="uq_connector_definitions"),
    )

    op.create_table(
        "connector_instances",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "connector_definition_id",
            sa.String(length=36),
            sa.ForeignKey("connector_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("auth_status", sa.String(length=40), nullable=False),
        sa.Column("external_identifier", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "is_active",
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
    )

    op.create_table(
        "service_actions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("action_kind", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "mutates_data",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "skill_definition_id",
            sa.String(length=36),
            sa.ForeignKey("skill_definitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "connector_definition_id",
            sa.String(length=36),
            sa.ForeignKey("connector_definitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
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
        sa.UniqueConstraint("scope_node_id", "key", name="uq_service_actions"),
    )

    op.create_table(
        "automation_definitions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("automation_kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_template_id", sa.String(length=36), nullable=True),
        sa.Column(
            "is_system_template",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
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
        sa.UniqueConstraint("scope_node_id", "key", name="uq_automation_definitions"),
    )

    op.create_table(
        "automation_versions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "automation_definition_id",
            sa.String(length=36),
            sa.ForeignKey("automation_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("trigger_kind", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("graph_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
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
            "automation_definition_id",
            "version_number",
            name="uq_automation_versions_definition_version",
        ),
    )

    op.create_table(
        "automation_nodes",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "automation_version_id",
            sa.String(length=36),
            sa.ForeignKey("automation_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_key", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("node_kind", sa.String(length=40), nullable=False),
        sa.Column("label", postgresql.CITEXT(length=160), nullable=False),
        sa.Column(
            "service_action_id",
            sa.String(length=36),
            sa.ForeignKey("service_actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("config_json", postgresql.JSONB(), nullable=False),
        sa.Column("position_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "is_entry",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_terminal",
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
        sa.UniqueConstraint(
            "automation_version_id",
            "node_key",
            name="uq_automation_nodes_version_key",
        ),
    )

    op.create_table(
        "automation_edges",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "automation_version_id",
            sa.String(length=36),
            sa.ForeignKey("automation_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_node_id",
            sa.String(length=36),
            sa.ForeignKey("automation_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_node_id",
            sa.String(length=36),
            sa.ForeignKey("automation_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("edge_kind", sa.String(length=40), nullable=False),
        sa.Column("condition_json", postgresql.JSONB(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
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

    op.create_table(
        "schedule_rules",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "automation_definition_id",
            sa.String(length=36),
            sa.ForeignKey("automation_definitions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "task_definition_id",
            sa.String(length=36),
            sa.ForeignKey("task_definitions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "automation_version_id",
            sa.String(length=36),
            sa.ForeignKey("automation_versions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("trigger_kind", sa.String(length=40), nullable=False),
        sa.Column("rrule", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rule_json", postgresql.JSONB(), nullable=False),
        sa.Column("calendar_label", postgresql.CITEXT(length=160), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("event_kind", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
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

    op.create_table(
        "alert_policies",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("name", postgresql.CITEXT(length=160), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("rule_json", postgresql.JSONB(), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column(
            "is_active",
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
        sa.UniqueConstraint("scope_node_id", "key", name="uq_alert_policies"),
    )

    op.create_table(
        "change_sets",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("key", postgresql.CITEXT(length=120), nullable=False),
        sa.Column("summary", postgresql.CITEXT(length=240), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "requested_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "approved_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
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
        sa.UniqueConstraint("scope_node_id", "key", name="uq_change_sets"),
    )

    op.create_table(
        "automation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "automation_version_id",
            sa.String(length=36),
            sa.ForeignKey("automation_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "schedule_rule_id",
            sa.String(length=36),
            sa.ForeignKey("schedule_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("triggered_by", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "requested_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "change_set_id",
            sa.String(length=36),
            sa.ForeignKey("change_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
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

    op.create_table(
        "automation_run_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "automation_run_id",
            sa.String(length=36),
            sa.ForeignKey("automation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "automation_node_id",
            sa.String(length=36),
            sa.ForeignKey("automation_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
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

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "alert_policy_id",
            sa.String(length=36),
            sa.ForeignKey("alert_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "telemetry_event_id",
            sa.String(length=36),
            sa.ForeignKey("telemetry_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "automation_run_event_id",
            sa.String(length=36),
            sa.ForeignKey("automation_run_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "scope_node_id",
            sa.String(length=36),
            sa.ForeignKey("scope_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_table(
        "change_set_entries",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "change_set_id",
            sa.String(length=36),
            sa.ForeignKey("change_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_kind", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column("diff_json", postgresql.JSONB(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_guarded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
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

    _create_updated_at_triggers()


def downgrade() -> None:
    if not _is_postgresql():
        return

    _drop_updated_at_triggers()

    op.drop_table("change_set_entries")
    op.drop_table("alerts")
    op.drop_table("automation_run_events")
    op.drop_table("automation_runs")
    op.drop_table("change_sets")
    op.drop_table("alert_policies")
    op.drop_table("telemetry_events")
    op.drop_table("schedule_rules")
    op.drop_table("automation_edges")
    op.drop_table("automation_nodes")
    op.drop_table("automation_versions")
    op.drop_table("automation_definitions")
    op.drop_table("service_actions")
    op.drop_table("connector_instances")
    op.drop_table("connector_definitions")
    op.drop_table("skill_definitions")
    op.drop_table("scope_memberships")
    op.drop_table("scope_nodes")
