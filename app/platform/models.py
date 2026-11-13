from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.common.pg import ci_text, jsonb_type
from app.database import Base

SCOPE_TYPES = ("organization", "folder", "nursery", "site", "zone")
AUTOMATION_STATUSES = ("draft", "active", "paused", "archived")
RUN_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")
ALERT_STATUSES = ("open", "acknowledged", "resolved", "muted")
CHANGE_SET_STATUSES = ("draft", "pending", "approved", "committed", "rolled_back")


class ScopeNode(TimestampMixin, Base):
    __tablename__ = "scope_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    slug: Mapped[str] = mapped_column(ci_text(120), nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    source_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    parent: Mapped[ScopeNode | None] = relationship(
        "ScopeNode",
        remote_side="ScopeNode.id",
        back_populates="children",
    )
    children: Mapped[list[ScopeNode]] = relationship(
        "ScopeNode",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    memberships: Mapped[list[ScopeMembership]] = relationship(
        back_populates="scope_node",
        cascade="all, delete-orphan",
    )
    skills: Mapped[list[SkillDefinition]] = relationship(back_populates="scope_node")
    connectors: Mapped[list[ConnectorDefinition]] = relationship(back_populates="scope_node")
    service_actions: Mapped[list[ServiceAction]] = relationship(back_populates="scope_node")
    automation_definitions: Mapped[list[AutomationDefinition]] = relationship(
        back_populates="scope_node",
    )
    schedule_rules: Mapped[list[ScheduleRule]] = relationship(back_populates="scope_node")
    telemetry_events: Mapped[list[TelemetryEvent]] = relationship(back_populates="scope_node")
    platform_events: Mapped[list[PlatformEvent]] = relationship(back_populates="scope_node")
    alert_policies: Mapped[list[AlertPolicy]] = relationship(back_populates="scope_node")
    change_sets: Mapped[list[ChangeSet]] = relationship(back_populates="scope_node")

    __table_args__ = (UniqueConstraint("parent_id", "slug", name="uq_scope_nodes_parent_slug"),)


class ScopeMembership(TimestampMixin, Base):
    __tablename__ = "scope_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_key: Mapped[str] = mapped_column(ci_text(64), nullable=False)
    access_level: Mapped[str] = mapped_column(ci_text(32), nullable=False, default="viewer")
    can_view_telemetry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_automations: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_approve_mutations: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    inherits_to_descendants: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    scope_node: Mapped[ScopeNode] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()

    __table_args__ = (
        UniqueConstraint("scope_node_id", "user_id", "role_key", name="uq_scope_memberships"),
    )


class SkillDefinition(TimestampMixin, Base):
    __tablename__ = "skill_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(ci_text(120), nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    skill_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )

    scope_node: Mapped[ScopeNode] = relationship(back_populates="skills")
    service_actions: Mapped[list[ServiceAction]] = relationship(back_populates="skill_definition")

    __table_args__ = (UniqueConstraint("scope_node_id", "key", name="uq_skill_definitions"),)


class ConnectorDefinition(TimestampMixin, Base):
    __tablename__ = "connector_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(ci_text(120), nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    connector_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    supports_offline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )

    scope_node: Mapped[ScopeNode] = relationship(back_populates="connectors")
    instances: Mapped[list[ConnectorInstance]] = relationship(back_populates="connector_definition")
    service_actions: Mapped[list[ServiceAction]] = relationship(
        back_populates="connector_definition"
    )

    __table_args__ = (UniqueConstraint("scope_node_id", "key", name="uq_connector_definitions"),)


class ConnectorInstance(TimestampMixin, Base):
    __tablename__ = "connector_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    connector_definition_id: Mapped[str] = mapped_column(
        ForeignKey("connector_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    auth_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    external_identifier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    connector_definition: Mapped[ConnectorDefinition] = relationship(back_populates="instances")
    scope_node: Mapped[ScopeNode] = relationship()


class ServiceAction(TimestampMixin, Base):
    __tablename__ = "service_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(ci_text(120), nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    action_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mutates_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skill_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("skill_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    connector_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("connector_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )

    scope_node: Mapped[ScopeNode] = relationship(back_populates="service_actions")
    skill_definition: Mapped[SkillDefinition | None] = relationship(
        back_populates="service_actions"
    )
    connector_definition: Mapped[ConnectorDefinition | None] = relationship(
        back_populates="service_actions",
    )

    __table_args__ = (UniqueConstraint("scope_node_id", "key", name="uq_service_actions"),)


class AutomationDefinition(TimestampMixin, Base):
    __tablename__ = "automation_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(ci_text(120), nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    automation_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="workflow")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    source_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )

    scope_node: Mapped[ScopeNode] = relationship(back_populates="automation_definitions")
    versions: Mapped[list[AutomationVersion]] = relationship(
        back_populates="automation_definition",
        cascade="all, delete-orphan",
    )
    schedule_rules: Mapped[list[ScheduleRule]] = relationship(
        back_populates="automation_definition"
    )

    __table_args__ = (UniqueConstraint("scope_node_id", "key", name="uq_automation_definitions"),)


class AutomationVersion(TimestampMixin, Base):
    __tablename__ = "automation_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    automation_definition_id: Mapped[str] = mapped_column(
        ForeignKey("automation_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    trigger_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    graph_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )

    automation_definition: Mapped[AutomationDefinition] = relationship(back_populates="versions")
    created_by_user: Mapped[User | None] = relationship()
    nodes: Mapped[list[AutomationNode]] = relationship(
        back_populates="automation_version",
        cascade="all, delete-orphan",
    )
    edges: Mapped[list[AutomationEdge]] = relationship(
        back_populates="automation_version",
        cascade="all, delete-orphan",
    )
    schedule_rules: Mapped[list[ScheduleRule]] = relationship(back_populates="automation_version")
    runs: Mapped[list[AutomationRun]] = relationship(back_populates="automation_version")

    __table_args__ = (
        UniqueConstraint(
            "automation_definition_id",
            "version_number",
            name="uq_automation_versions_definition_version",
        ),
    )


class AutomationNode(TimestampMixin, Base):
    __tablename__ = "automation_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    automation_version_id: Mapped[str] = mapped_column(
        ForeignKey("automation_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_key: Mapped[str] = mapped_column(ci_text(120), nullable=False)
    node_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    service_action_id: Mapped[str | None] = mapped_column(
        ForeignKey("service_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    config_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    position_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    is_entry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    automation_version: Mapped[AutomationVersion] = relationship(back_populates="nodes")
    service_action: Mapped[ServiceAction | None] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "automation_version_id",
            "node_key",
            name="uq_automation_nodes_version_key",
        ),
    )


class AutomationEdge(TimestampMixin, Base):
    __tablename__ = "automation_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    automation_version_id: Mapped[str] = mapped_column(
        ForeignKey("automation_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_node_id: Mapped[str] = mapped_column(
        ForeignKey("automation_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_node_id: Mapped[str] = mapped_column(
        ForeignKey("automation_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="next")
    condition_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    automation_version: Mapped[AutomationVersion] = relationship(back_populates="edges")
    from_node: Mapped[AutomationNode] = relationship(
        foreign_keys=[from_node_id],
        post_update=True,
    )
    to_node: Mapped[AutomationNode] = relationship(foreign_keys=[to_node_id], post_update=True)


class ScheduleRule(TimestampMixin, Base):
    __tablename__ = "schedule_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    automation_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("automation_definitions.id", ondelete="CASCADE"),
        nullable=True,
    )
    task_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("task_definitions.id", ondelete="CASCADE"),
        nullable=True,
    )
    automation_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("automation_versions.id", ondelete="CASCADE"),
        nullable=True,
    )
    trigger_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="rrule")
    rrule: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rule_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    calendar_label: Mapped[str | None] = mapped_column(ci_text(160), nullable=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scope_node: Mapped[ScopeNode] = relationship(back_populates="schedule_rules")
    automation_definition: Mapped[AutomationDefinition | None] = relationship(
        back_populates="schedule_rules"
    )
    automation_version: Mapped[AutomationVersion | None] = relationship(
        back_populates="schedule_rules"
    )


class AutomationRun(TimestampMixin, Base):
    __tablename__ = "automation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str | None] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    automation_version_id: Mapped[str] = mapped_column(
        ForeignKey("automation_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    schedule_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("schedule_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    triggered_by: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    requested_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    change_set_id: Mapped[str | None] = mapped_column(
        ForeignKey("change_sets.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )

    automation_version: Mapped[AutomationVersion] = relationship(back_populates="runs")
    requested_by_user: Mapped[User | None] = relationship(
        foreign_keys=[requested_by_user_id],
    )
    events: Mapped[list[AutomationRunEvent]] = relationship(
        back_populates="automation_run",
        cascade="all, delete-orphan",
    )


class AutomationRunEvent(TimestampMixin, Base):
    __tablename__ = "automation_run_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    automation_run_id: Mapped[str] = mapped_column(
        ForeignKey("automation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    automation_node_id: Mapped[str | None] = mapped_column(
        ForeignKey("automation_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="info")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )

    automation_run: Mapped[AutomationRun] = relationship(back_populates="events")
    automation_node: Mapped[AutomationNode | None] = relationship()


class TelemetryEvent(TimestampMixin, Base):
    __tablename__ = "telemetry_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False, default="info")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )

    scope_node: Mapped[ScopeNode] = relationship(back_populates="telemetry_events")


class PlatformEvent(TimestampMixin, Base):
    __tablename__ = "platform_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str | None] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(ci_text(120), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(24), nullable=False, default="v1")
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scope_node: Mapped[ScopeNode | None] = relationship(back_populates="platform_events")

    __table_args__ = (
        Index("ix_platform_events_created_at", "created_at"),
        Index("ix_platform_events_scope_created_at", "scope_node_id", "created_at"),
        Index("ix_platform_events_event_type", "event_type"),
    )


class AlertPolicy(TimestampMixin, Base):
    __tablename__ = "alert_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(ci_text(120), nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    severity: Mapped[str] = mapped_column(String(24), nullable=False, default="warning")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    scope_node: Mapped[ScopeNode] = relationship(back_populates="alert_policies")

    __table_args__ = (UniqueConstraint("scope_node_id", "key", name="uq_alert_policies"),)


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    alert_policy_id: Mapped[str] = mapped_column(
        ForeignKey("alert_policies.id", ondelete="CASCADE"),
        nullable=False,
    )
    telemetry_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("telemetry_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    automation_run_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("automation_run_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    scope_node_id: Mapped[str] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChangeSet(TimestampMixin, Base):
    __tablename__ = "change_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    scope_node_id: Mapped[str | None] = mapped_column(
        ForeignKey("scope_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    key: Mapped[str] = mapped_column(ci_text(120), nullable=False)
    summary: Mapped[str] = mapped_column(ci_text(240), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    requested_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )

    scope_node: Mapped[ScopeNode | None] = relationship(back_populates="change_sets")
    requested_by_user: Mapped[User | None] = relationship(foreign_keys=[requested_by_user_id])
    approved_by_user: Mapped[User | None] = relationship(foreign_keys=[approved_by_user_id])
    entries: Mapped[list[ChangeSetEntry]] = relationship(
        back_populates="change_set",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("scope_node_id", "key", name="uq_change_sets"),)


class ChangeSetEntry(TimestampMixin, Base):
    __tablename__ = "change_set_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    change_set_id: Mapped[str] = mapped_column(
        ForeignKey("change_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation: Mapped[str] = mapped_column(String(24), nullable=False)
    diff_json: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_guarded: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")

    change_set: Mapped[ChangeSet] = relationship(back_populates="entries")
