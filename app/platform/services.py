from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.models import User
from app.common.forms import optional_str
from app.platform.calendar import calculate_schedule_rule_next_run
from app.platform.events import record_platform_event
from app.platform.models import (
    SCOPE_TYPES,
    Alert,
    AlertPolicy,
    AutomationDefinition,
    AutomationEdge,
    AutomationNode,
    AutomationRun,
    AutomationRunEvent,
    AutomationVersion,
    ChangeSet,
    ChangeSetEntry,
    ConnectorDefinition,
    ConnectorInstance,
    ScheduleRule,
    ScopeMembership,
    ScopeNode,
    ServiceAction,
    SkillDefinition,
    TelemetryEvent,
)

DEFAULT_PLATFORM_SCOPE_SLUG = "gardenos-platform"
DEFAULT_PLATFORM_SCOPE_NAME = "GardenOS Platform"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_key(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("A key is required.")
    return re.sub(r"\s+", "_", text.casefold())


def normalize_slug(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("A slug is required.")
    normalized = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    if not normalized:
        raise ValueError("A slug is required.")
    return normalized


def _scope_type(value: str) -> str:
    normalized = normalize_key(value)
    if normalized not in SCOPE_TYPES:
        raise ValueError(f"Invalid scope_type: {value}")
    return normalized


def _resolve_scope_node(session: Session, value: ScopeNode | str | None) -> ScopeNode | None:
    if value is None:
        return None
    if isinstance(value, ScopeNode):
        return value
    node = session.get(ScopeNode, value)
    if node is None:
        raise ValueError(f"Scope node not found: {value}")
    return node


def _metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if value is not None else {}


def ensure_scope_node(
    session: Session,
    *,
    scope_type: str,
    name: str,
    slug: str | None = None,
    parent: ScopeNode | str | None = None,
    timezone: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    source_template_id: str | None = None,
    is_system_template: bool = False,
) -> ScopeNode:
    normalized_scope_type = _scope_type(scope_type)
    parent_node = _resolve_scope_node(session, parent)
    normalized_slug = normalize_slug(slug or name)
    node = session.scalar(
        select(ScopeNode).where(
            ScopeNode.parent_id == (parent_node.id if parent_node else None),
            ScopeNode.slug == normalized_slug,
        ),
    )
    if node is None:
        node = ScopeNode(
            parent=parent_node,
            scope_type=normalized_scope_type,
            name=name.strip(),
            slug=normalized_slug,
            timezone=timezone.strip() if isinstance(timezone, str) and timezone.strip() else None,
            metadata_json=_metadata(metadata),
            source_template_id=source_template_id,
            is_system_template=is_system_template,
        )
        session.add(node)
        session.flush()
        return node

    node.parent = parent_node
    node.scope_type = normalized_scope_type
    node.name = name.strip()
    node.slug = normalized_slug
    node.timezone = timezone.strip() if isinstance(timezone, str) and timezone.strip() else None
    node.metadata_json = _metadata(metadata)
    node.source_template_id = source_template_id
    node.is_system_template = is_system_template
    session.add(node)
    session.flush()
    return node


def ensure_scope_membership(
    session: Session,
    *,
    scope_node: ScopeNode,
    user: User,
    role_key: str,
    access_level: str = "viewer",
    can_view_telemetry: bool = False,
    can_manage_automations: bool = False,
    can_approve_mutations: bool = False,
    inherits_to_descendants: bool = True,
) -> ScopeMembership:
    normalized_role_key = normalize_key(role_key)
    normalized_access_level = normalize_key(access_level)
    membership = session.scalar(
        select(ScopeMembership).where(
            ScopeMembership.scope_node_id == scope_node.id,
            ScopeMembership.user_id == user.id,
            ScopeMembership.role_key == normalized_role_key,
        ),
    )
    if membership is None:
        membership = ScopeMembership(
            scope_node=scope_node,
            user=user,
            role_key=normalized_role_key,
            access_level=normalized_access_level,
            can_view_telemetry=can_view_telemetry,
            can_manage_automations=can_manage_automations,
            can_approve_mutations=can_approve_mutations,
            inherits_to_descendants=inherits_to_descendants,
        )
        session.add(membership)
        session.flush()
        return membership

    membership.scope_node = scope_node
    membership.user = user
    membership.role_key = normalized_role_key
    membership.access_level = normalized_access_level
    membership.can_view_telemetry = can_view_telemetry
    membership.can_manage_automations = can_manage_automations
    membership.can_approve_mutations = can_approve_mutations
    membership.inherits_to_descendants = inherits_to_descendants
    session.add(membership)
    session.flush()
    return membership


def ensure_skill_definition(
    session: Session,
    *,
    scope_node: ScopeNode,
    key: str,
    name: str,
    skill_kind: str,
    description: str | None = None,
    source_template_id: str | None = None,
    is_system_template: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> SkillDefinition:
    normalized_key = normalize_key(key)
    skill = session.scalar(
        select(SkillDefinition).where(
            SkillDefinition.scope_node_id == scope_node.id,
            SkillDefinition.key == normalized_key,
        ),
    )
    if skill is None:
        skill = SkillDefinition(
            scope_node=scope_node,
            key=normalized_key,
            name=name.strip(),
            skill_kind=normalize_key(skill_kind),
            description=optional_str(description),
            source_template_id=source_template_id,
            is_system_template=is_system_template,
            metadata_json=_metadata(metadata),
        )
        session.add(skill)
        session.flush()
        return skill

    skill.scope_node = scope_node
    skill.key = normalized_key
    skill.name = name.strip()
    skill.skill_kind = normalize_key(skill_kind)
    skill.description = optional_str(description)
    skill.source_template_id = source_template_id
    skill.is_system_template = is_system_template
    skill.metadata_json = _metadata(metadata)
    session.add(skill)
    session.flush()
    return skill


def ensure_connector_definition(
    session: Session,
    *,
    scope_node: ScopeNode,
    key: str,
    name: str,
    connector_kind: str,
    description: str | None = None,
    auth_kind: str = "manual",
    supports_offline: bool = False,
    source_template_id: str | None = None,
    is_system_template: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> ConnectorDefinition:
    normalized_key = normalize_key(key)
    connector = session.scalar(
        select(ConnectorDefinition).where(
            ConnectorDefinition.scope_node_id == scope_node.id,
            ConnectorDefinition.key == normalized_key,
        ),
    )
    if connector is None:
        connector = ConnectorDefinition(
            scope_node=scope_node,
            key=normalized_key,
            name=name.strip(),
            connector_kind=normalize_key(connector_kind),
            description=optional_str(description),
            auth_kind=normalize_key(auth_kind),
            supports_offline=supports_offline,
            source_template_id=source_template_id,
            is_system_template=is_system_template,
            metadata_json=_metadata(metadata),
        )
        session.add(connector)
        session.flush()
        return connector

    connector.scope_node = scope_node
    connector.key = normalized_key
    connector.name = name.strip()
    connector.connector_kind = normalize_key(connector_kind)
    connector.description = optional_str(description)
    connector.auth_kind = normalize_key(auth_kind)
    connector.supports_offline = supports_offline
    connector.source_template_id = source_template_id
    connector.is_system_template = is_system_template
    connector.metadata_json = _metadata(metadata)
    session.add(connector)
    session.flush()
    return connector


def ensure_connector_instance(
    session: Session,
    *,
    connector_definition: ConnectorDefinition,
    scope_node: ScopeNode,
    display_name: str,
    auth_status: str = "pending",
    external_identifier: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    is_active: bool = True,
) -> ConnectorInstance:
    instance = session.scalar(
        select(ConnectorInstance).where(
            ConnectorInstance.connector_definition_id == connector_definition.id,
            ConnectorInstance.scope_node_id == scope_node.id,
            ConnectorInstance.display_name == display_name.strip(),
        ),
    )
    if instance is None:
        instance = ConnectorInstance(
            connector_definition=connector_definition,
            scope_node=scope_node,
            display_name=display_name.strip(),
            auth_status=normalize_key(auth_status),
            external_identifier=external_identifier.strip() if external_identifier else None,
            metadata_json=_metadata(metadata),
            is_active=is_active,
        )
        session.add(instance)
        session.flush()
        return instance

    instance.connector_definition = connector_definition
    instance.scope_node = scope_node
    instance.display_name = display_name.strip()
    instance.auth_status = normalize_key(auth_status)
    instance.external_identifier = external_identifier.strip() if external_identifier else None
    instance.metadata_json = _metadata(metadata)
    instance.is_active = is_active
    session.add(instance)
    session.flush()
    return instance


def ensure_service_action(
    session: Session,
    *,
    scope_node: ScopeNode,
    key: str,
    name: str,
    action_kind: str,
    description: str | None = None,
    mutates_data: bool = False,
    requires_approval: bool = False,
    skill_definition: SkillDefinition | None = None,
    connector_definition: ConnectorDefinition | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ServiceAction:
    normalized_key = normalize_key(key)
    action = session.scalar(
        select(ServiceAction).where(
            ServiceAction.scope_node_id == scope_node.id,
            ServiceAction.key == normalized_key,
        ),
    )
    if action is None:
        action = ServiceAction(
            scope_node=scope_node,
            key=normalized_key,
            name=name.strip(),
            action_kind=normalize_key(action_kind),
            description=optional_str(description),
            mutates_data=mutates_data,
            requires_approval=requires_approval,
            skill_definition=skill_definition,
            connector_definition=connector_definition,
            metadata_json=_metadata(metadata),
        )
        session.add(action)
        session.flush()
        return action

    action.scope_node = scope_node
    action.key = normalized_key
    action.name = name.strip()
    action.action_kind = normalize_key(action_kind)
    action.description = optional_str(description)
    action.mutates_data = mutates_data
    action.requires_approval = requires_approval
    action.skill_definition = skill_definition
    action.connector_definition = connector_definition
    action.metadata_json = _metadata(metadata)
    session.add(action)
    session.flush()
    return action


def ensure_automation_definition(
    session: Session,
    *,
    scope_node: ScopeNode,
    key: str,
    name: str,
    description: str | None = None,
    automation_kind: str = "workflow",
    status: str = "draft",
    source_template_id: str | None = None,
    is_system_template: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> AutomationDefinition:
    normalized_key = normalize_key(key)
    definition = session.scalar(
        select(AutomationDefinition).where(
            AutomationDefinition.scope_node_id == scope_node.id,
            AutomationDefinition.key == normalized_key,
        ),
    )
    if definition is None:
        definition = AutomationDefinition(
            scope_node=scope_node,
            key=normalized_key,
            name=name.strip(),
            description=optional_str(description),
            automation_kind=normalize_key(automation_kind),
            status=normalize_key(status),
            source_template_id=source_template_id,
            is_system_template=is_system_template,
            metadata_json=_metadata(metadata),
        )
        session.add(definition)
        session.flush()
        return definition

    definition.scope_node = scope_node
    definition.key = normalized_key
    definition.name = name.strip()
    definition.description = optional_str(description)
    definition.automation_kind = normalize_key(automation_kind)
    definition.status = normalize_key(status)
    definition.source_template_id = source_template_id
    definition.is_system_template = is_system_template
    definition.metadata_json = _metadata(metadata)
    session.add(definition)
    session.flush()
    return definition


def ensure_automation_version(
    session: Session,
    *,
    automation_definition: AutomationDefinition,
    version_number: int | None = None,
    status: str = "draft",
    trigger_kind: str = "manual",
    summary: str | None = None,
    created_by_user: User | None = None,
    graph: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    published_at: datetime | None = None,
) -> AutomationVersion:
    if version_number is None:
        version_number = (
            session.scalar(
                select(func.max(AutomationVersion.version_number)).where(
                    AutomationVersion.automation_definition_id == automation_definition.id,
                ),
            )
            or 0
        ) + 1

    version = session.scalar(
        select(AutomationVersion).where(
            AutomationVersion.automation_definition_id == automation_definition.id,
            AutomationVersion.version_number == version_number,
        ),
    )
    if version is None:
        version = AutomationVersion(
            automation_definition=automation_definition,
            version_number=version_number,
            status=normalize_key(status),
            trigger_kind=normalize_key(trigger_kind),
            summary=optional_str(summary),
            created_by_user=created_by_user,
            graph_json=_metadata(graph),
            metadata_json=_metadata(metadata),
            published_at=published_at,
        )
        session.add(version)
        session.flush()
        return version

    version.automation_definition = automation_definition
    version.version_number = version_number
    version.status = normalize_key(status)
    version.trigger_kind = normalize_key(trigger_kind)
    version.summary = optional_str(summary)
    version.created_by_user = created_by_user
    version.graph_json = _metadata(graph)
    version.metadata_json = _metadata(metadata)
    version.published_at = published_at
    session.add(version)
    session.flush()
    return version


def ensure_automation_node(
    session: Session,
    *,
    automation_version: AutomationVersion,
    node_key: str,
    node_kind: str,
    label: str,
    service_action: ServiceAction | None = None,
    config: Mapping[str, Any] | None = None,
    position: Mapping[str, Any] | None = None,
    is_entry: bool = False,
    is_terminal: bool = False,
) -> AutomationNode:
    normalized_key = normalize_key(node_key)
    node = session.scalar(
        select(AutomationNode).where(
            AutomationNode.automation_version_id == automation_version.id,
            AutomationNode.node_key == normalized_key,
        ),
    )
    if node is None:
        node = AutomationNode(
            automation_version=automation_version,
            node_key=normalized_key,
            node_kind=normalize_key(node_kind),
            label=label.strip(),
            service_action=service_action,
            config_json=_metadata(config),
            position_json=_metadata(position),
            is_entry=is_entry,
            is_terminal=is_terminal,
        )
        session.add(node)
        session.flush()
        return node

    node.automation_version = automation_version
    node.node_key = normalized_key
    node.node_kind = normalize_key(node_kind)
    node.label = label.strip()
    node.service_action = service_action
    node.config_json = _metadata(config)
    node.position_json = _metadata(position)
    node.is_entry = is_entry
    node.is_terminal = is_terminal
    session.add(node)
    session.flush()
    return node


def ensure_automation_edge(
    session: Session,
    *,
    automation_version: AutomationVersion,
    from_node: AutomationNode,
    to_node: AutomationNode,
    edge_kind: str = "next",
    condition: Mapping[str, Any] | None = None,
    order_index: int = 0,
) -> AutomationEdge:
    edge = session.scalar(
        select(AutomationEdge).where(
            AutomationEdge.automation_version_id == automation_version.id,
            AutomationEdge.from_node_id == from_node.id,
            AutomationEdge.to_node_id == to_node.id,
            AutomationEdge.edge_kind == normalize_key(edge_kind),
        ),
    )
    if edge is None:
        edge = AutomationEdge(
            automation_version=automation_version,
            from_node=from_node,
            to_node=to_node,
            edge_kind=normalize_key(edge_kind),
            condition_json=_metadata(condition),
            order_index=order_index,
        )
        session.add(edge)
        session.flush()
        return edge

    edge.automation_version = automation_version
    edge.from_node = from_node
    edge.to_node = to_node
    edge.edge_kind = normalize_key(edge_kind)
    edge.condition_json = _metadata(condition)
    edge.order_index = order_index
    session.add(edge)
    session.flush()
    return edge


def ensure_schedule_rule(
    session: Session,
    *,
    scope_node: ScopeNode,
    trigger_kind: str,
    rrule: str | None = None,
    timezone: str | None = None,
    automation_definition: AutomationDefinition | None = None,
    automation_version: AutomationVersion | None = None,
    task_definition_id: str | None = None,
    next_run_at: datetime | None = None,
    rule: Mapping[str, Any] | None = None,
    calendar_label: str | None = None,
    paused_at: datetime | None = None,
) -> ScheduleRule:
    schedule_rule = ScheduleRule(
        scope_node=scope_node,
        automation_definition=automation_definition,
        automation_version=automation_version,
        task_definition_id=task_definition_id,
        trigger_kind=normalize_key(trigger_kind),
        rrule=optional_str(rrule),
        timezone=timezone.strip() if isinstance(timezone, str) and timezone.strip() else None,
        next_run_at=next_run_at,
        paused_at=paused_at,
        rule_json=_metadata(rule),
        calendar_label=optional_str(calendar_label),
    )
    session.add(schedule_rule)
    session.flush()
    if schedule_rule.paused_at is None and schedule_rule.next_run_at is None:
        next_run_at = calculate_schedule_rule_next_run(schedule_rule)
        if next_run_at is not None:
            schedule_rule.next_run_at = next_run_at
            session.add(schedule_rule)
            session.flush()
    record_platform_event(
        session,
        event_type="scheduler.schedule_rule.created",
        source_kind="scheduler",
        source_id=schedule_rule.id,
        scope_node=schedule_rule.scope_node,
        payload={
            "scope_node_id": schedule_rule.scope_node_id,
            "automation_definition_id": schedule_rule.automation_definition_id,
            "automation_version_id": schedule_rule.automation_version_id,
            "task_definition_id": schedule_rule.task_definition_id,
            "trigger_kind": schedule_rule.trigger_kind,
            "rrule": schedule_rule.rrule,
            "timezone": schedule_rule.timezone,
            "next_run_at": schedule_rule.next_run_at.isoformat()
            if schedule_rule.next_run_at is not None
            else None,
            "calendar_label": schedule_rule.calendar_label,
        },
    )
    return schedule_rule


def record_automation_run(
    session: Session,
    *,
    automation_version: AutomationVersion,
    scope_node: ScopeNode | None = None,
    schedule_rule: ScheduleRule | None = None,
    triggered_by: str = "manual",
    status: str = "queued",
    requested_by_user: User | None = None,
    change_set: ChangeSet | None = None,
    reason: str | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> AutomationRun:
    run = AutomationRun(
        scope_node_id=scope_node.id if scope_node is not None else None,
        automation_version=automation_version,
        schedule_rule_id=schedule_rule.id if schedule_rule is not None else None,
        triggered_by=normalize_key(triggered_by),
        status=normalize_key(status),
        requested_by_user=requested_by_user,
        change_set_id=change_set.id if change_set is not None else None,
        reason=optional_str(reason),
        started_at=started_at,
        ended_at=ended_at,
        metadata_json=_metadata(metadata),
    )
    session.add(run)
    session.flush()
    record_platform_event(
        session,
        event_type="automation.run.created",
        source_kind="automation",
        source_id=run.id,
        scope_node=scope_node or automation_version.automation_definition.scope_node,
        payload={
            "automation_version_id": automation_version.id,
            "schedule_rule_id": run.schedule_rule_id,
            "triggered_by": run.triggered_by,
            "status": run.status,
            "requested_by_user_id": run.requested_by_user_id,
            "change_set_id": run.change_set_id,
            "reason": run.reason,
        },
    )
    return run


def record_automation_run_event(
    session: Session,
    *,
    automation_run: AutomationRun,
    event_kind: str,
    status: str = "info",
    automation_node: AutomationNode | None = None,
    occurred_at: datetime | None = None,
    payload: Mapping[str, Any] | None = None,
) -> AutomationRunEvent:
    event = AutomationRunEvent(
        automation_run=automation_run,
        automation_node=automation_node,
        event_kind=normalize_key(event_kind),
        status=normalize_key(status),
        occurred_at=occurred_at or _utc_now(),
        payload_json=_metadata(payload),
    )
    session.add(event)
    session.flush()
    record_platform_event(
        session,
        event_type="automation.run.event.recorded",
        source_kind="automation",
        source_id=event.id,
        scope_node=automation_run.scope_node_id
        or automation_run.automation_version.automation_definition.scope_node_id,
        payload={
            "automation_run_id": automation_run.id,
            "automation_node_id": event.automation_node_id,
            "event_kind": event.event_kind,
            "status": event.status,
            "occurred_at": event.occurred_at.isoformat(),
        },
    )
    return event


def record_telemetry_event(
    session: Session,
    *,
    scope_node: ScopeNode,
    source_kind: str,
    event_kind: str,
    severity: str = "info",
    source_id: str | None = None,
    occurred_at: datetime | None = None,
    payload: Mapping[str, Any] | None = None,
) -> TelemetryEvent:
    event = TelemetryEvent(
        scope_node=scope_node,
        source_kind=normalize_key(source_kind),
        source_id=source_id,
        event_kind=normalize_key(event_kind),
        severity=normalize_key(severity),
        occurred_at=occurred_at or _utc_now(),
        payload_json=_metadata(payload),
    )
    session.add(event)
    session.flush()
    record_platform_event(
        session,
        event_type="telemetry.recorded",
        source_kind=source_kind,
        source_id=event.id,
        scope_node=scope_node,
        payload={
            "scope_node_id": scope_node.id,
            "source_kind": source_kind,
            "source_id": event.source_id,
            "event_kind": event.event_kind,
            "severity": event.severity,
            "occurred_at": event.occurred_at.isoformat(),
        },
    )
    return event


def ensure_alert_policy(
    session: Session,
    *,
    scope_node: ScopeNode,
    key: str,
    name: str,
    source_kind: str,
    rule: Mapping[str, Any] | None = None,
    severity: str = "warning",
    is_active: bool = True,
) -> AlertPolicy:
    normalized_key = normalize_key(key)
    policy = session.scalar(
        select(AlertPolicy).where(
            AlertPolicy.scope_node_id == scope_node.id,
            AlertPolicy.key == normalized_key,
        ),
    )
    if policy is None:
        policy = AlertPolicy(
            scope_node=scope_node,
            key=normalized_key,
            name=name.strip(),
            source_kind=normalize_key(source_kind),
            rule_json=_metadata(rule),
            severity=normalize_key(severity),
            is_active=is_active,
        )
        session.add(policy)
        session.flush()
        return policy

    policy.scope_node = scope_node
    policy.key = normalized_key
    policy.name = name.strip()
    policy.source_kind = normalize_key(source_kind)
    policy.rule_json = _metadata(rule)
    policy.severity = normalize_key(severity)
    policy.is_active = is_active
    session.add(policy)
    session.flush()
    return policy


def open_alert(
    session: Session,
    *,
    alert_policy: AlertPolicy,
    scope_node: ScopeNode,
    telemetry_event: TelemetryEvent | None = None,
    automation_run_event: AutomationRunEvent | None = None,
    summary: str | None = None,
    opened_at: datetime | None = None,
    status: str = "open",
) -> Alert:
    alert = Alert(
        alert_policy_id=alert_policy.id,
        telemetry_event_id=telemetry_event.id if telemetry_event is not None else None,
        automation_run_event_id=automation_run_event.id
        if automation_run_event is not None
        else None,
        scope_node_id=scope_node.id,
        status=normalize_key(status),
        summary=optional_str(summary),
        opened_at=opened_at or _utc_now(),
    )
    session.add(alert)
    session.flush()
    record_platform_event(
        session,
        event_type="alert.opened",
        source_kind="alert",
        source_id=alert.id,
        scope_node=scope_node,
        payload={
            "alert_policy_id": alert.alert_policy_id,
            "telemetry_event_id": alert.telemetry_event_id,
            "automation_run_event_id": alert.automation_run_event_id,
            "status": alert.status,
            "summary": alert.summary,
        },
    )
    return alert


def set_alert_status(
    session: Session,
    *,
    alert: Alert,
    status: str,
    touched_at: datetime | None = None,
) -> Alert:
    normalized_status = normalize_key(status)
    if normalized_status not in {"acknowledged", "resolved", "muted", "open"}:
        raise ValueError(f"Unsupported alert status: {status}")
    alert.status = normalized_status
    touched = touched_at or _utc_now()
    if normalized_status == "acknowledged":
        alert.acknowledged_at = touched
        alert.resolved_at = None
    elif normalized_status == "resolved":
        alert.resolved_at = touched
    elif normalized_status == "muted":
        alert.resolved_at = None
    elif normalized_status == "open":
        alert.acknowledged_at = None
        alert.resolved_at = None
    session.add(alert)
    session.flush()
    return alert


def acknowledge_alert(
    session: Session,
    *,
    alert: Alert,
    acknowledged_at: datetime | None = None,
) -> Alert:
    scope_node = session.get(ScopeNode, alert.scope_node_id)
    if scope_node is None:
        raise ValueError("Alert scope node not found.")
    alert = set_alert_status(
        session,
        alert=alert,
        status="acknowledged",
        touched_at=acknowledged_at,
    )
    record_platform_event(
        session,
        event_type="alert.acknowledged",
        source_kind="alert",
        source_id=alert.id,
        scope_node=scope_node,
        payload={"alert_id": alert.id, "status": alert.status},
    )
    return alert


def resolve_alert(session: Session, *, alert: Alert, resolved_at: datetime | None = None) -> Alert:
    scope_node = session.get(ScopeNode, alert.scope_node_id)
    if scope_node is None:
        raise ValueError("Alert scope node not found.")
    alert = set_alert_status(session, alert=alert, status="resolved", touched_at=resolved_at)
    record_platform_event(
        session,
        event_type="alert.resolved",
        source_kind="alert",
        source_id=alert.id,
        scope_node=scope_node,
        payload={"alert_id": alert.id, "status": alert.status},
    )
    return alert


def mute_alert(session: Session, *, alert: Alert, muted_at: datetime | None = None) -> Alert:
    scope_node = session.get(ScopeNode, alert.scope_node_id)
    if scope_node is None:
        raise ValueError("Alert scope node not found.")
    alert = set_alert_status(session, alert=alert, status="muted", touched_at=muted_at)
    record_platform_event(
        session,
        event_type="alert.muted",
        source_kind="alert",
        source_id=alert.id,
        scope_node=scope_node,
        payload={"alert_id": alert.id, "status": alert.status},
    )
    return alert


def unmute_alert(session: Session, *, alert: Alert, unmuted_at: datetime | None = None) -> Alert:
    scope_node = session.get(ScopeNode, alert.scope_node_id)
    if scope_node is None:
        raise ValueError("Alert scope node not found.")
    alert = set_alert_status(session, alert=alert, status="open", touched_at=unmuted_at)
    record_platform_event(
        session,
        event_type="alert.unmuted",
        source_kind="alert",
        source_id=alert.id,
        scope_node=scope_node,
        payload={"alert_id": alert.id, "status": alert.status},
    )
    return alert


def ensure_change_set(
    session: Session,
    *,
    key: str,
    summary: str,
    scope_node: ScopeNode | None = None,
    requested_by_user: User | None = None,
    reason: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    status: str = "draft",
) -> ChangeSet:
    normalized_key = normalize_key(key)
    change_set = session.scalar(
        select(ChangeSet).where(
            ChangeSet.scope_node_id == (scope_node.id if scope_node is not None else None),
            ChangeSet.key == normalized_key,
        ),
    )
    created = change_set is None
    if change_set is None:
        change_set = ChangeSet(
            scope_node=scope_node,
            key=normalized_key,
            summary=summary.strip(),
            status=normalize_key(status),
            requested_by_user=requested_by_user,
            reason=optional_str(reason),
            metadata_json=_metadata(metadata),
            requested_at=_utc_now(),
        )
        session.add(change_set)
    else:
        change_set.scope_node = scope_node
        change_set.key = normalized_key
        change_set.summary = summary.strip()
        change_set.status = normalize_key(status)
        change_set.requested_by_user = requested_by_user
        change_set.reason = optional_str(reason)
        change_set.metadata_json = _metadata(metadata)
        session.add(change_set)
    session.flush()
    record_platform_event(
        session,
        event_type="changeset.created" if created else "changeset.updated",
        source_kind="changeset",
        source_id=change_set.id,
        scope_node=change_set.scope_node,
        payload={
            "scope_node_id": change_set.scope_node_id,
            "key": change_set.key,
            "summary": change_set.summary,
            "status": change_set.status,
            "requested_by_user_id": change_set.requested_by_user_id,
            "reason": change_set.reason,
        },
    )
    return change_set


def append_change_set_entry(
    session: Session,
    *,
    change_set: ChangeSet,
    entity_kind: str,
    entity_id: str,
    operation: str,
    diff: Mapping[str, Any] | None = None,
    is_guarded: bool = True,
    status: str = "pending",
    applied_at: datetime | None = None,
    reverted_at: datetime | None = None,
) -> ChangeSetEntry:
    entry = ChangeSetEntry(
        change_set=change_set,
        entity_kind=normalize_key(entity_kind),
        entity_id=entity_id,
        operation=normalize_key(operation),
        diff_json=_metadata(diff),
        is_guarded=is_guarded,
        status=normalize_key(status),
        applied_at=applied_at,
        reverted_at=reverted_at,
    )
    session.add(entry)
    session.flush()
    record_platform_event(
        session,
        event_type="changeset.entry.added",
        source_kind="changeset",
        source_id=entry.id,
        scope_node=change_set.scope_node,
        payload={
            "change_set_id": change_set.id,
            "entity_kind": entry.entity_kind,
            "entity_id": entry.entity_id,
            "operation": entry.operation,
            "status": entry.status,
            "is_guarded": entry.is_guarded,
        },
    )
    return entry


def build_scope_tree(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    nodes = list(
        session.scalars(
            select(ScopeNode)
            .options(selectinload(ScopeNode.memberships))
            .order_by(ScopeNode.scope_type, ScopeNode.name),
        ).all(),
    )
    if scope_node_ids is not None:
        nodes = [node for node in nodes if node.id in scope_node_ids]
    visible_ids = {node.id for node in nodes}
    children_by_parent: dict[str | None, list[ScopeNode]] = defaultdict(list)
    for node in nodes:
        parent_id = node.parent_id if node.parent_id in visible_ids else None
        children_by_parent[parent_id].append(node)

    def build(node: ScopeNode, ancestors: list[dict[str, str]]) -> dict[str, Any]:
        child_nodes = sorted(
            children_by_parent.get(node.id, []),
            key=lambda child: child.name.casefold(),
        )
        children = [
            build(child, [*ancestors, {"id": node.id, "name": node.name, "type": node.scope_type}])
            for child in child_nodes
        ]
        return {
            "id": node.id,
            "parent_id": node.parent_id,
            "scope_type": node.scope_type,
            "name": node.name,
            "slug": node.slug,
            "timezone": node.timezone,
            "metadata": node.metadata_json,
            "source_template_id": node.source_template_id,
            "is_system_template": node.is_system_template,
            "archived_at": node.archived_at.isoformat() if node.archived_at else None,
            "depth": len(ancestors),
            "path": [*ancestors, {"id": node.id, "name": node.name, "type": node.scope_type}],
            "member_count": len(node.memberships),
            "child_count": len(children),
            "children": children,
        }

    return [build(node, []) for node in children_by_parent.get(None, [])]


def serialize_scope_node(node: ScopeNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "parent_id": node.parent_id,
        "scope_type": node.scope_type,
        "name": node.name,
        "slug": node.slug,
        "timezone": node.timezone,
        "metadata": node.metadata_json,
        "source_template_id": node.source_template_id,
        "is_system_template": node.is_system_template,
        "archived_at": node.archived_at.isoformat() if node.archived_at else None,
        "member_count": len(node.memberships),
        "child_count": len(node.children),
        "children": [
            serialize_scope_node(child)
            for child in sorted(node.children, key=lambda item: item.name.casefold())
        ],
    }


def serialize_scope_membership(membership: ScopeMembership) -> dict[str, Any]:
    return {
        "id": membership.id,
        "scope_node_id": membership.scope_node_id,
        "user_id": membership.user_id,
        "role_key": membership.role_key,
        "access_level": membership.access_level,
        "can_view_telemetry": membership.can_view_telemetry,
        "can_manage_automations": membership.can_manage_automations,
        "can_approve_mutations": membership.can_approve_mutations,
        "inherits_to_descendants": membership.inherits_to_descendants,
        "created_at": membership.created_at.isoformat(),
        "updated_at": membership.updated_at.isoformat(),
    }


def serialize_skill_definition(skill: SkillDefinition) -> dict[str, Any]:
    return {
        "id": skill.id,
        "scope_node_id": skill.scope_node_id,
        "key": skill.key,
        "name": skill.name,
        "skill_kind": skill.skill_kind,
        "description": skill.description,
        "source_template_id": skill.source_template_id,
        "is_system_template": skill.is_system_template,
        "metadata": skill.metadata_json,
        "created_at": skill.created_at.isoformat(),
        "updated_at": skill.updated_at.isoformat(),
    }


def serialize_connector_definition(connector: ConnectorDefinition) -> dict[str, Any]:
    return {
        "id": connector.id,
        "scope_node_id": connector.scope_node_id,
        "key": connector.key,
        "name": connector.name,
        "connector_kind": connector.connector_kind,
        "description": connector.description,
        "auth_kind": connector.auth_kind,
        "supports_offline": connector.supports_offline,
        "source_template_id": connector.source_template_id,
        "is_system_template": connector.is_system_template,
        "metadata": connector.metadata_json,
        "created_at": connector.created_at.isoformat(),
        "updated_at": connector.updated_at.isoformat(),
    }


def serialize_service_action(action: ServiceAction) -> dict[str, Any]:
    return {
        "id": action.id,
        "scope_node_id": action.scope_node_id,
        "key": action.key,
        "name": action.name,
        "action_kind": action.action_kind,
        "description": action.description,
        "mutates_data": action.mutates_data,
        "requires_approval": action.requires_approval,
        "skill_definition_id": action.skill_definition_id,
        "connector_definition_id": action.connector_definition_id,
        "metadata": action.metadata_json,
        "created_at": action.created_at.isoformat(),
        "updated_at": action.updated_at.isoformat(),
    }


def serialize_automation_definition(definition: AutomationDefinition) -> dict[str, Any]:
    return {
        "id": definition.id,
        "scope_node_id": definition.scope_node_id,
        "key": definition.key,
        "name": definition.name,
        "description": definition.description,
        "automation_kind": definition.automation_kind,
        "status": definition.status,
        "source_template_id": definition.source_template_id,
        "is_system_template": definition.is_system_template,
        "metadata": definition.metadata_json,
        "version_count": len(definition.versions),
        "created_at": definition.created_at.isoformat(),
        "updated_at": definition.updated_at.isoformat(),
    }


def serialize_automation_version(version: AutomationVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "automation_definition_id": version.automation_definition_id,
        "version_number": version.version_number,
        "status": version.status,
        "trigger_kind": version.trigger_kind,
        "summary": version.summary,
        "graph": version.graph_json,
        "created_by_user_id": version.created_by_user_id,
        "published_at": version.published_at.isoformat() if version.published_at else None,
        "metadata": version.metadata_json,
        "node_count": len(version.nodes),
        "edge_count": len(version.edges),
        "created_at": version.created_at.isoformat(),
        "updated_at": version.updated_at.isoformat(),
    }


def serialize_schedule_rule(schedule_rule: ScheduleRule) -> dict[str, Any]:
    return {
        "id": schedule_rule.id,
        "scope_node_id": schedule_rule.scope_node_id,
        "automation_definition_id": schedule_rule.automation_definition_id,
        "automation_version_id": schedule_rule.automation_version_id,
        "task_definition_id": schedule_rule.task_definition_id,
        "trigger_kind": schedule_rule.trigger_kind,
        "rrule": schedule_rule.rrule,
        "timezone": schedule_rule.timezone,
        "next_run_at": schedule_rule.next_run_at.isoformat() if schedule_rule.next_run_at else None,
        "paused_at": schedule_rule.paused_at.isoformat() if schedule_rule.paused_at else None,
        "calendar_label": schedule_rule.calendar_label,
        "rule": schedule_rule.rule_json,
        "last_fired_at": schedule_rule.last_fired_at.isoformat()
        if schedule_rule.last_fired_at
        else None,
        "created_at": schedule_rule.created_at.isoformat(),
        "updated_at": schedule_rule.updated_at.isoformat(),
    }


def serialize_telemetry_event(event: TelemetryEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "scope_node_id": event.scope_node_id,
        "source_kind": event.source_kind,
        "source_id": event.source_id,
        "event_kind": event.event_kind,
        "severity": event.severity,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload_json,
        "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(),
    }


def serialize_automation_run(run: AutomationRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "scope_node_id": run.scope_node_id,
        "automation_version_id": run.automation_version_id,
        "schedule_rule_id": run.schedule_rule_id,
        "triggered_by": run.triggered_by,
        "status": run.status,
        "requested_by_user_id": run.requested_by_user_id,
        "change_set_id": run.change_set_id,
        "reason": run.reason,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "metadata": run.metadata_json,
        "event_count": len(run.events),
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


def serialize_automation_run_event(event: AutomationRunEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "automation_run_id": event.automation_run_id,
        "automation_node_id": event.automation_node_id,
        "event_kind": event.event_kind,
        "status": event.status,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload_json,
        "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(),
    }


def serialize_alert_policy(policy: AlertPolicy) -> dict[str, Any]:
    return {
        "id": policy.id,
        "scope_node_id": policy.scope_node_id,
        "key": policy.key,
        "name": policy.name,
        "source_kind": policy.source_kind,
        "rule": policy.rule_json,
        "severity": policy.severity,
        "is_active": policy.is_active,
        "created_at": policy.created_at.isoformat(),
        "updated_at": policy.updated_at.isoformat(),
    }


def serialize_alert(alert: Alert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "alert_policy_id": alert.alert_policy_id,
        "telemetry_event_id": alert.telemetry_event_id,
        "automation_run_event_id": alert.automation_run_event_id,
        "scope_node_id": alert.scope_node_id,
        "status": alert.status,
        "summary": alert.summary,
        "opened_at": alert.opened_at.isoformat(),
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "created_at": alert.created_at.isoformat(),
        "updated_at": alert.updated_at.isoformat(),
    }


def serialize_change_set(change_set: ChangeSet) -> dict[str, Any]:
    return {
        "id": change_set.id,
        "scope_node_id": change_set.scope_node_id,
        "key": change_set.key,
        "summary": change_set.summary,
        "status": change_set.status,
        "requested_by_user_id": change_set.requested_by_user_id,
        "approved_by_user_id": change_set.approved_by_user_id,
        "requested_at": change_set.requested_at.isoformat() if change_set.requested_at else None,
        "approved_at": change_set.approved_at.isoformat() if change_set.approved_at else None,
        "committed_at": change_set.committed_at.isoformat() if change_set.committed_at else None,
        "rolled_back_at": change_set.rolled_back_at.isoformat()
        if change_set.rolled_back_at
        else None,
        "reason": change_set.reason,
        "metadata": change_set.metadata_json,
        "entry_count": len(change_set.entries),
        "created_at": change_set.created_at.isoformat(),
        "updated_at": change_set.updated_at.isoformat(),
    }


def serialize_change_set_entry(entry: ChangeSetEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "change_set_id": entry.change_set_id,
        "entity_kind": entry.entity_kind,
        "entity_id": entry.entity_id,
        "operation": entry.operation,
        "diff": entry.diff_json,
        "applied_at": entry.applied_at.isoformat() if entry.applied_at else None,
        "reverted_at": entry.reverted_at.isoformat() if entry.reverted_at else None,
        "is_guarded": entry.is_guarded,
        "status": entry.status,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def list_scope_memberships(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[ScopeMembership]:
    stmt = select(ScopeMembership).options(
        selectinload(ScopeMembership.scope_node),
        selectinload(ScopeMembership.user),
    )
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(ScopeMembership.scope_node_id.in_(sorted(scope_node_ids)))
    stmt = stmt.order_by(ScopeMembership.created_at.asc())
    return list(session.scalars(stmt).all())


def list_skill_definitions(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[SkillDefinition]:
    stmt = select(SkillDefinition)
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(SkillDefinition.scope_node_id.in_(sorted(scope_node_ids)))
    stmt = stmt.order_by(SkillDefinition.key)
    return list(session.scalars(stmt).all())


def list_connector_definitions(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[ConnectorDefinition]:
    stmt = select(ConnectorDefinition)
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(ConnectorDefinition.scope_node_id.in_(sorted(scope_node_ids)))
    stmt = stmt.order_by(ConnectorDefinition.key)
    return list(session.scalars(stmt).all())


def list_service_actions(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[ServiceAction]:
    stmt = select(ServiceAction)
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(ServiceAction.scope_node_id.in_(sorted(scope_node_ids)))
    stmt = stmt.order_by(ServiceAction.key)
    return list(session.scalars(stmt).all())


def list_automation_definitions(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[AutomationDefinition]:
    stmt = select(AutomationDefinition).options(selectinload(AutomationDefinition.versions))
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(AutomationDefinition.scope_node_id.in_(sorted(scope_node_ids)))
    stmt = stmt.order_by(AutomationDefinition.key)
    return list(session.scalars(stmt).all())


def list_schedule_rules(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[ScheduleRule]:
    stmt = select(ScheduleRule)
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(ScheduleRule.scope_node_id.in_(sorted(scope_node_ids)))
    stmt = stmt.order_by(ScheduleRule.created_at.desc())
    return list(session.scalars(stmt).all())


def list_telemetry_events(
    session: Session,
    scope_node_ids: set[str] | None = None,
    *,
    source_kind: str | None = None,
    event_kind: str | None = None,
    severity: str | None = None,
) -> list[TelemetryEvent]:
    stmt = select(TelemetryEvent)
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(TelemetryEvent.scope_node_id.in_(sorted(scope_node_ids)))
    if source_kind:
        stmt = stmt.where(TelemetryEvent.source_kind == normalize_key(source_kind))
    if event_kind:
        stmt = stmt.where(TelemetryEvent.event_kind == normalize_key(event_kind))
    if severity:
        stmt = stmt.where(TelemetryEvent.severity == normalize_key(severity))
    stmt = stmt.order_by(TelemetryEvent.occurred_at.desc())
    return list(session.scalars(stmt).all())


def list_automation_runs(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[AutomationRun]:
    stmt = select(AutomationRun).options(selectinload(AutomationRun.events))
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        scope_values = sorted(scope_node_ids)
        stmt = stmt.where(
            or_(
                AutomationRun.scope_node_id.in_(scope_values),
                AutomationRun.automation_version.has(
                    AutomationVersion.automation_definition.has(
                        AutomationDefinition.scope_node_id.in_(scope_values),
                    ),
                ),
            ),
        )
    stmt = stmt.order_by(AutomationRun.created_at.desc())
    return list(session.scalars(stmt).all())


def list_automation_run_events(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[AutomationRunEvent]:
    stmt = select(AutomationRunEvent).options(
        selectinload(AutomationRunEvent.automation_run).selectinload(AutomationRun.automation_version).selectinload(
            AutomationVersion.automation_definition,
        ),
    )
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        scope_values = sorted(scope_node_ids)
        stmt = (
            stmt.join(AutomationRunEvent.automation_run)
            .join(AutomationRun.automation_version)
            .join(AutomationVersion.automation_definition)
        )
        stmt = stmt.where(
            or_(
                AutomationRun.scope_node_id.in_(scope_values),
                AutomationDefinition.scope_node_id.in_(scope_values),
            ),
        )
    stmt = stmt.order_by(AutomationRunEvent.occurred_at.desc())
    return list(session.scalars(stmt).all())


def list_alert_policies(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[AlertPolicy]:
    stmt = select(AlertPolicy)
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(AlertPolicy.scope_node_id.in_(sorted(scope_node_ids)))
    stmt = stmt.order_by(AlertPolicy.key)
    return list(session.scalars(stmt).all())


def list_alerts(
    session: Session,
    scope_node_ids: set[str] | None = None,
    *,
    status: str | None = None,
) -> list[Alert]:
    stmt = select(Alert)
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(Alert.scope_node_id.in_(sorted(scope_node_ids)))
    if status:
        stmt = stmt.where(Alert.status == normalize_key(status))
    stmt = stmt.order_by(Alert.opened_at.desc())
    return list(session.scalars(stmt).all())


def list_change_sets(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> list[ChangeSet]:
    stmt = select(ChangeSet).options(selectinload(ChangeSet.entries))
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(ChangeSet.scope_node_id.in_(sorted(scope_node_ids)))
    stmt = stmt.order_by(ChangeSet.created_at.desc())
    return list(session.scalars(stmt).all())


def serialize_platform_catalog(
    session: Session,
    scope_node_ids: set[str] | None = None,
) -> dict[str, Any]:
    scopes = build_scope_tree(session, scope_node_ids=scope_node_ids)
    skills = [
        serialize_skill_definition(skill)
        for skill in list_skill_definitions(session, scope_node_ids=scope_node_ids)
    ]
    connectors = [
        serialize_connector_definition(connector)
        for connector in list_connector_definitions(session, scope_node_ids=scope_node_ids)
    ]
    actions = [
        serialize_service_action(action)
        for action in list_service_actions(session, scope_node_ids=scope_node_ids)
    ]
    automations = [
        serialize_automation_definition(item)
        for item in list_automation_definitions(session, scope_node_ids=scope_node_ids)
    ]
    return {
        "scopes": scopes,
        "skills": skills,
        "connectors": connectors,
        "service_actions": actions,
        "automation_definitions": automations,
        "summary": {
            "scope_count": len(scopes),
            "skill_count": len(skills),
            "connector_count": len(connectors),
            "service_action_count": len(actions),
            "automation_definition_count": len(automations),
        },
    }


def ensure_default_platform_catalog(session: Session) -> dict[str, int]:
    root_scope = ensure_scope_node(
        session,
        scope_type="organization",
        name=DEFAULT_PLATFORM_SCOPE_NAME,
        slug=DEFAULT_PLATFORM_SCOPE_SLUG,
        metadata={"purpose": "platform_root"},
        is_system_template=True,
    )
    templates_scope = ensure_scope_node(
        session,
        scope_type="folder",
        name="Shared Templates",
        slug="shared-templates",
        parent=root_scope,
        metadata={"purpose": "shared_system_templates"},
        is_system_template=True,
    )
    automation_scope = ensure_scope_node(
        session,
        scope_type="folder",
        name="Automation Library",
        slug="automation-library",
        parent=templates_scope,
        metadata={"purpose": "workflow_templates"},
        is_system_template=True,
    )
    connectors_scope = ensure_scope_node(
        session,
        scope_type="folder",
        name="Connector Library",
        slug="connector-library",
        parent=templates_scope,
        metadata={"purpose": "connector_templates"},
        is_system_template=True,
    )
    observability_scope = ensure_scope_node(
        session,
        scope_type="folder",
        name="Observability",
        slug="observability",
        parent=templates_scope,
        metadata={"purpose": "telemetry_templates"},
        is_system_template=True,
    )

    skills = {
        "task-manager": ensure_skill_definition(
            session,
            scope_node=automation_scope,
            key="task-manager",
            name="Task Manager",
            skill_kind="workflow",
            description="Human-in-the-loop task orchestration and review queues.",
            is_system_template=True,
            metadata={"surface": "tasks"},
        ),
        "scheduler": ensure_skill_definition(
            session,
            scope_node=automation_scope,
            key="scheduler",
            name="Scheduler",
            skill_kind="workflow",
            description="Recurrence evaluation and job dispatch.",
            is_system_template=True,
            metadata={"surface": "schedule"},
        ),
        "workflow-builder": ensure_skill_definition(
            session,
            scope_node=automation_scope,
            key="workflow-builder",
            name="Workflow Builder",
            skill_kind="workflow",
            description="No-code automation graph authoring and review.",
            is_system_template=True,
            metadata={"surface": "automations"},
        ),
        "alert-router": ensure_skill_definition(
            session,
            scope_node=observability_scope,
            key="alert-router",
            name="Alert Router",
            skill_kind="observability",
            description="Routes alerts to notification endpoints and app surfaces.",
            is_system_template=True,
            metadata={"surface": "alerts"},
        ),
    }

    connectors = {
        "cameras": ensure_connector_definition(
            session,
            scope_node=connectors_scope,
            key="cameras",
            name="Cameras",
            connector_kind="media",
            description="Photo and video capture systems.",
            auth_kind="token",
            supports_offline=True,
            is_system_template=True,
            metadata={"surface": "cameras"},
        ),
        "notifications": ensure_connector_definition(
            session,
            scope_node=connectors_scope,
            key="notifications",
            name="Notifications",
            connector_kind="notification",
            description="Push notification and app alert delivery.",
            auth_kind="internal",
            supports_offline=True,
            is_system_template=True,
            metadata={"surface": "notifications"},
        ),
        "email": ensure_connector_definition(
            session,
            scope_node=connectors_scope,
            key="email",
            name="Email",
            connector_kind="email",
            description="Outbound email delivery for alerts and approvals.",
            auth_kind="smtp",
            supports_offline=False,
            is_system_template=True,
            metadata={"surface": "email"},
        ),
        "weather": ensure_connector_definition(
            session,
            scope_node=connectors_scope,
            key="weather",
            name="Weather",
            connector_kind="weather",
            description="Weather API and physical weather station integration.",
            auth_kind="api_key",
            supports_offline=True,
            is_system_template=True,
            metadata={"surface": "weather"},
        ),
        "sensors": ensure_connector_definition(
            session,
            scope_node=connectors_scope,
            key="sensors",
            name="Sensors",
            connector_kind="sensor",
            description="Soil moisture and environmental sensor integrations.",
            auth_kind="internal",
            supports_offline=True,
            is_system_template=True,
            metadata={"surface": "sensors"},
        ),
        "calendar": ensure_connector_definition(
            session,
            scope_node=connectors_scope,
            key="calendar",
            name="Calendar",
            connector_kind="calendar",
            description="Global nursery calendar and schedule projection.",
            auth_kind="internal",
            supports_offline=True,
            is_system_template=True,
            metadata={"surface": "calendar"},
        ),
    }

    ensure_service_action(
        session,
        scope_node=automation_scope,
        key="task.create",
        name="Create Task",
        action_kind="task",
        description="Create a human-in-the-loop task record.",
        mutates_data=True,
        requires_approval=True,
        skill_definition=skills["task-manager"],
        metadata={"surface": "tasks"},
    )
    ensure_service_action(
        session,
        scope_node=automation_scope,
        key="task.complete",
        name="Complete Task",
        action_kind="task",
        description="Mark a task as completed.",
        mutates_data=True,
        requires_approval=True,
        skill_definition=skills["task-manager"],
        metadata={"surface": "tasks"},
    )
    ensure_service_action(
        session,
        scope_node=automation_scope,
        key="workflow.run",
        name="Run Workflow",
        action_kind="workflow",
        description="Execute a workflow graph.",
        mutates_data=True,
        requires_approval=True,
        skill_definition=skills["workflow-builder"],
        metadata={"surface": "automations"},
    )
    ensure_service_action(
        session,
        scope_node=automation_scope,
        key="schedule.enqueue",
        name="Enqueue Schedule",
        action_kind="scheduler",
        description="Queue a scheduled job for execution.",
        mutates_data=False,
        requires_approval=False,
        skill_definition=skills["scheduler"],
        metadata={"surface": "schedule"},
    )
    ensure_service_action(
        session,
        scope_node=connectors_scope,
        key="camera.capture",
        name="Capture Camera Frame",
        action_kind="connector",
        description="Capture a still image or short clip from a camera connector.",
        connector_definition=connectors["cameras"],
        metadata={"surface": "cameras"},
    )
    ensure_service_action(
        session,
        scope_node=connectors_scope,
        key="notification.send",
        name="Send Notification",
        action_kind="connector",
        description="Send a push notification to app or mobile surfaces.",
        connector_definition=connectors["notifications"],
        metadata={"surface": "notifications"},
    )
    ensure_service_action(
        session,
        scope_node=connectors_scope,
        key="email.send",
        name="Send Email",
        action_kind="connector",
        description="Send an email through the configured mail connector.",
        connector_definition=connectors["email"],
        metadata={"surface": "email"},
    )
    ensure_service_action(
        session,
        scope_node=connectors_scope,
        key="weather.lookup",
        name="Lookup Weather",
        action_kind="connector",
        description="Query weather forecasts or a local weather station.",
        connector_definition=connectors["weather"],
        metadata={"surface": "weather"},
    )
    ensure_service_action(
        session,
        scope_node=connectors_scope,
        key="sensor.read",
        name="Read Sensor",
        action_kind="connector",
        description="Read moisture, temperature, or other sensor measurements.",
        connector_definition=connectors["sensors"],
        metadata={"surface": "sensors"},
    )
    ensure_service_action(
        session,
        scope_node=connectors_scope,
        key="calendar.fetch",
        name="Fetch Calendar",
        action_kind="connector",
        description="Fetch the shared nursery calendar projection.",
        connector_definition=connectors["calendar"],
        metadata={"surface": "calendar"},
    )

    return {
        "scopes": 5,
        "skills": len(skills),
        "connectors": len(connectors),
        "service_actions": 10,
    }
