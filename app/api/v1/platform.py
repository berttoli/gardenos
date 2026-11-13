from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.dependencies import require_permission
from app.access.services import PrincipalContext
from app.api.v1.common import commit_session, json_value, parse_iso_datetime, request_payload
from app.auth.models import User
from app.common.forms import optional_str
from app.dependencies import get_db
from app.platform.calendar import (
    build_calendar_projection,
)
from app.platform.events import (
    format_platform_event_sse,
    list_platform_events,
    serialize_platform_event,
)
from app.platform.models import (
    Alert,
    AlertPolicy,
    AutomationDefinition,
    AutomationRun,
    AutomationRunEvent,
    AutomationVersion,
    ChangeSet,
    ConnectorDefinition,
    ConnectorInstance,
    ScheduleRule,
    ScopeNode,
    SkillDefinition,
    TelemetryEvent,
)
from app.platform.scope_access import resolve_visible_scope_ids
from app.platform.services import (
    acknowledge_alert,
    append_change_set_entry,
    build_scope_tree,
    ensure_alert_policy,
    ensure_automation_definition,
    ensure_automation_version,
    ensure_change_set,
    ensure_connector_definition,
    ensure_connector_instance,
    ensure_schedule_rule,
    ensure_scope_membership,
    ensure_scope_node,
    ensure_service_action,
    ensure_skill_definition,
    list_alert_policies,
    list_alerts,
    list_automation_definitions,
    list_automation_run_events,
    list_automation_runs,
    list_change_sets,
    list_connector_definitions,
    list_schedule_rules,
    list_scope_memberships,
    list_service_actions,
    list_skill_definitions,
    list_telemetry_events,
    mute_alert,
    open_alert,
    record_automation_run,
    record_automation_run_event,
    record_telemetry_event,
    resolve_alert,
    serialize_alert,
    serialize_alert_policy,
    serialize_automation_definition,
    serialize_automation_run,
    serialize_automation_run_event,
    serialize_automation_version,
    serialize_change_set,
    serialize_change_set_entry,
    serialize_connector_definition,
    serialize_platform_catalog,
    serialize_schedule_rule,
    serialize_scope_membership,
    serialize_scope_node,
    serialize_service_action,
    serialize_skill_definition,
    serialize_telemetry_event,
    set_alert_status,
    unmute_alert,
)
from app.workspace.services import build_system_services_payload

router = APIRouter(prefix="/platform", tags=["platform"])

_json_value = json_value
_request_payload = request_payload
_commit = commit_session


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    return parse_iso_datetime(value, field_name="Datetime values", plural=True)


def _resolve_scope(session: Session, identifier: str | None) -> ScopeNode | None:
    if identifier is None:
        return None
    return session.get(ScopeNode, identifier)


def _resolve_user(session: Session, identifier: str | None) -> User | None:
    if identifier is None:
        return None
    user = session.get(User, identifier)
    if user is not None:
        return user
    normalized = optional_str(identifier)
    if normalized is None:
        return None
    return session.scalar(select(User).where(User.username == normalized))


def _resolve_skill(session: Session, identifier: str | None) -> SkillDefinition | None:
    if not identifier:
        return None
    return session.get(SkillDefinition, identifier)


def _resolve_connector(session: Session, identifier: str | None) -> ConnectorDefinition | None:
    if not identifier:
        return None
    return session.get(ConnectorDefinition, identifier)


def _resolve_automation_definition(
    session: Session,
    identifier: str | None,
) -> AutomationDefinition | None:
    if not identifier:
        return None
    return session.get(AutomationDefinition, identifier)


def _resolve_automation_version(
    session: Session, identifier: str | None
) -> AutomationVersion | None:
    if not identifier:
        return None
    return session.get(AutomationVersion, identifier)


def _resolve_schedule_rule(session: Session, identifier: str | None) -> ScheduleRule | None:
    if not identifier:
        return None
    return session.get(ScheduleRule, identifier)


def _resolve_change_set(session: Session, identifier: str | None) -> ChangeSet | None:
    if not identifier:
        return None
    return session.get(ChangeSet, identifier)


def _scope_ids_for_principal(
    session: Session,
    principal: PrincipalContext,
    scope_node_id: str | None = None,
) -> set[str] | None:
    return resolve_visible_scope_ids(session, principal, scope_node_id=scope_node_id)


def _require_scope_access(
    session: Session,
    principal: PrincipalContext,
    scope_node: ScopeNode | None,
) -> None:
    if scope_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scope node not found.")
    resolve_visible_scope_ids(session, principal, scope_node_id=scope_node.id)


async def _invoke_assistant_service(request: Request, message: str) -> dict[str, Any]:
    settings = request.app.state.settings
    assistant_url = getattr(settings, "assistant_service_url", "http://assistant:8080").rstrip("/")
    payload = json.dumps({"message": message}).encode("utf-8")

    def sync_request() -> dict[str, Any]:
        req = UrlRequest(
            f"{assistant_url}/chat",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=10.0) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        return await asyncio.to_thread(sync_request)
    except URLError as exc:  # pragma: no cover - exercised by integration failures
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Assistant service is unavailable.",
        ) from exc


@router.get("/catalog")
def catalog_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    catalog = serialize_platform_catalog(db, scope_node_ids=scope_ids)
    catalog["system_services"] = build_system_services_payload(db, current_principal)
    return JSONResponse(_json_value(catalog))


@router.get("/system-services")
def system_services_index(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    system_services = build_system_services_payload(db, current_principal)
    return JSONResponse(
        {
            "system_services": system_services,
            "summary": {
                "ready_count": sum(1 for item in system_services if item["status"] == "ready"),
                "service_count": len(system_services),
            },
        },
    )


@router.post("/assistant/chat")
async def assistant_chat(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    del db, current_principal
    payload = await _request_payload(request)
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message is required.",
        )
    reply = await _invoke_assistant_service(request, message)
    return JSONResponse(_json_value(reply))


@router.get("/scopes")
def scopes_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(_json_value(build_scope_tree(db, scope_node_ids=scope_ids)))


@router.post("/scopes", status_code=status.HTTP_201_CREATED)
async def scopes_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_type = str(payload.get("scope_type") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not scope_type or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_type and name are required.",
        )
    parent = _resolve_scope(db, optional_str(payload.get("parent_id")))
    if parent is None and not current_principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Top-level scopes require platform admin access.",
        )
    if parent is not None:
        _require_scope_access(db, current_principal, parent)
    node = ensure_scope_node(
        db,
        scope_type=scope_type,
        name=name,
        slug=optional_str(payload.get("slug")),
        parent=parent,
        timezone=optional_str(payload.get("timezone")),
        metadata=payload.get("metadata_json")
        if isinstance(payload.get("metadata_json"), Mapping)
        else None,
        source_template_id=optional_str(payload.get("source_template_id")),
        is_system_template=bool(payload.get("is_system_template", False)),
    )
    _commit(db)
    return JSONResponse(
        {"scope_node": _json_value(serialize_scope_node(node))}, status_code=status.HTTP_201_CREATED
    )


@router.get("/scope-memberships")
def scope_memberships_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_scope_membership(item))
            for item in list_scope_memberships(db, scope_node_ids=scope_ids)
        ]
    )


@router.post("/scope-memberships", status_code=status.HTTP_201_CREATED)
async def scope_memberships_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_node_id = optional_str(payload.get("scope_node_id"))
    role_key = optional_str(payload.get("role_key"))
    if not scope_node_id or not role_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_node_id and role_key are required.",
    )
    scope_node = _resolve_scope(db, scope_node_id)
    if scope_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scope node not found.")
    _require_scope_access(db, current_principal, scope_node)
    user = _resolve_user(
        db, optional_str(payload.get("user_id")) or optional_str(payload.get("username"))
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    membership = ensure_scope_membership(
        db,
        scope_node=scope_node,
        user=user,
        role_key=role_key,
        access_level=optional_str(payload.get("access_level")) or "viewer",
        can_view_telemetry=bool(payload.get("can_view_telemetry", False)),
        can_manage_automations=bool(payload.get("can_manage_automations", False)),
        can_approve_mutations=bool(payload.get("can_approve_mutations", False)),
        inherits_to_descendants=bool(payload.get("inherits_to_descendants", True)),
    )
    _commit(db)
    return JSONResponse(
        {"scope_membership": _json_value(serialize_scope_membership(membership))},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/skills")
def skills_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_skill_definition(skill))
            for skill in list_skill_definitions(db, scope_node_ids=scope_ids)
        ]
    )


@router.post("/skills", status_code=status.HTTP_201_CREATED)
async def skills_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id")))
    key = optional_str(payload.get("key"))
    name = optional_str(payload.get("name"))
    skill_kind = optional_str(payload.get("skill_kind"))
    if scope_node is None or not key or not name or not skill_kind:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_node_id, key, name, and skill_kind are required.",
        )
    _require_scope_access(db, current_principal, scope_node)
    skill = ensure_skill_definition(
        db,
        scope_node=scope_node,
        key=key,
        name=name,
        skill_kind=skill_kind,
        description=optional_str(payload.get("description")),
        source_template_id=optional_str(payload.get("source_template_id")),
        is_system_template=bool(payload.get("is_system_template", False)),
        metadata=payload.get("metadata_json")
        if isinstance(payload.get("metadata_json"), Mapping)
        else None,
    )
    _commit(db)
    return JSONResponse(
        {"skill": _json_value(serialize_skill_definition(skill))},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/connectors")
def connectors_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_connector_definition(connector))
            for connector in list_connector_definitions(db, scope_node_ids=scope_ids)
        ]
    )


@router.post("/connectors", status_code=status.HTTP_201_CREATED)
async def connectors_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id")))
    key = optional_str(payload.get("key"))
    name = optional_str(payload.get("name"))
    connector_kind = optional_str(payload.get("connector_kind"))
    if scope_node is None or not key or not name or not connector_kind:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_node_id, key, name, and connector_kind are required.",
        )
    _require_scope_access(db, current_principal, scope_node)
    connector = ensure_connector_definition(
        db,
        scope_node=scope_node,
        key=key,
        name=name,
        connector_kind=connector_kind,
        description=optional_str(payload.get("description")),
        auth_kind=optional_str(payload.get("auth_kind")) or "manual",
        supports_offline=bool(payload.get("supports_offline", False)),
        source_template_id=optional_str(payload.get("source_template_id")),
        is_system_template=bool(payload.get("is_system_template", False)),
        metadata=payload.get("metadata_json")
        if isinstance(payload.get("metadata_json"), Mapping)
        else None,
    )
    _commit(db)
    return JSONResponse(
        {"connector": _json_value(serialize_connector_definition(connector))},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/connector-instances")
def connector_instances_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    instances = list(
        db.scalars(
            select(ConnectorInstance).order_by(ConnectorInstance.created_at.desc()),
        ).all(),
    )
    if scope_ids is not None:
        instances = [instance for instance in instances if instance.scope_node_id in scope_ids]
    return JSONResponse(
        [
            {
                "id": instance.id,
                "connector_definition_id": instance.connector_definition_id,
                "scope_node_id": instance.scope_node_id,
                "display_name": instance.display_name,
                "auth_status": instance.auth_status,
                "external_identifier": instance.external_identifier,
                "metadata": instance.metadata_json,
                "is_active": instance.is_active,
                "created_at": instance.created_at.isoformat(),
                "updated_at": instance.updated_at.isoformat(),
            }
            for instance in instances
        ],
    )


@router.post("/connector-instances", status_code=status.HTTP_201_CREATED)
async def connector_instances_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id")))
    connector = _resolve_connector(db, optional_str(payload.get("connector_definition_id")) or "")
    display_name = optional_str(payload.get("display_name"))
    if scope_node is None or connector is None or not display_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_node_id, connector_definition_id, and display_name are required.",
        )
    _require_scope_access(db, current_principal, scope_node)
    _require_scope_access(db, current_principal, connector.scope_node)
    instance = ensure_connector_instance(
        db,
        connector_definition=connector,
        scope_node=scope_node,
        display_name=display_name,
        auth_status=optional_str(payload.get("auth_status")) or "pending",
        external_identifier=optional_str(payload.get("external_identifier")),
        metadata=payload.get("metadata_json")
        if isinstance(payload.get("metadata_json"), Mapping)
        else None,
        is_active=bool(payload.get("is_active", True)),
    )
    _commit(db)
    return JSONResponse(
        {
            "connector_instance": _json_value(
                {
                    "id": instance.id,
                    "connector_definition_id": instance.connector_definition_id,
                    "scope_node_id": instance.scope_node_id,
                    "display_name": instance.display_name,
                    "auth_status": instance.auth_status,
                    "external_identifier": instance.external_identifier,
                    "metadata": instance.metadata_json,
                    "is_active": instance.is_active,
                    "created_at": instance.created_at.isoformat(),
                    "updated_at": instance.updated_at.isoformat(),
                }
            )
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/service-actions")
def service_actions_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_service_action(action))
            for action in list_service_actions(db, scope_node_ids=scope_ids)
        ]
    )


@router.post("/service-actions", status_code=status.HTTP_201_CREATED)
async def service_actions_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id")))
    key = optional_str(payload.get("key"))
    name = optional_str(payload.get("name"))
    action_kind = optional_str(payload.get("action_kind"))
    if scope_node is None or not key or not name or not action_kind:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_node_id, key, name, and action_kind are required.",
        )
    _require_scope_access(db, current_principal, scope_node)
    skill = (
        _resolve_skill(db, optional_str(payload.get("skill_definition_id")) or "")
        if optional_str(payload.get("skill_definition_id"))
        else None
    )
    connector = (
        _resolve_connector(db, optional_str(payload.get("connector_definition_id")) or "")
        if optional_str(payload.get("connector_definition_id"))
        else None
    )
    if skill is not None:
        _require_scope_access(db, current_principal, skill.scope_node)
    if connector is not None:
        _require_scope_access(db, current_principal, connector.scope_node)
    action = ensure_service_action(
        db,
        scope_node=scope_node,
        key=key,
        name=name,
        action_kind=action_kind,
        description=optional_str(payload.get("description")),
        mutates_data=bool(payload.get("mutates_data", False)),
        requires_approval=bool(payload.get("requires_approval", False)),
        skill_definition=skill,
        connector_definition=connector,
        metadata=payload.get("metadata_json")
        if isinstance(payload.get("metadata_json"), Mapping)
        else None,
    )
    _commit(db)
    return JSONResponse(
        {"service_action": _json_value(serialize_service_action(action))},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/automations")
def automations_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_automation_definition(item))
            for item in list_automation_definitions(db, scope_node_ids=scope_ids)
        ]
    )


@router.post("/automations", status_code=status.HTTP_201_CREATED)
async def automations_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id")))
    key = optional_str(payload.get("key"))
    name = optional_str(payload.get("name"))
    if scope_node is None or not key or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_node_id, key, and name are required.",
        )
    _require_scope_access(db, current_principal, scope_node)
    definition = ensure_automation_definition(
        db,
        scope_node=scope_node,
        key=key,
        name=name,
        description=optional_str(payload.get("description")),
        automation_kind=optional_str(payload.get("automation_kind")) or "workflow",
        status=optional_str(payload.get("status")) or "draft",
        source_template_id=optional_str(payload.get("source_template_id")),
        is_system_template=bool(payload.get("is_system_template", False)),
        metadata=payload.get("metadata_json")
        if isinstance(payload.get("metadata_json"), Mapping)
        else None,
    )
    _commit(db)
    return JSONResponse(
        {"automation_definition": _json_value(serialize_automation_definition(definition))},
        status_code=status.HTTP_201_CREATED,
    )


@router.post(
    "/automations/{automation_definition_id}/versions", status_code=status.HTTP_201_CREATED
)
async def automation_versions_create(
    automation_definition_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    definition = _resolve_automation_definition(db, automation_definition_id)
    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation definition not found.",
        )
    _require_scope_access(db, current_principal, definition.scope_node)
    payload = await _request_payload(request)
    version = ensure_automation_version(
        db,
        automation_definition=definition,
        version_number=int(payload["version_number"])
        if payload.get("version_number") is not None
        else None,
        status=optional_str(payload.get("status")) or "draft",
        trigger_kind=optional_str(payload.get("trigger_kind")) or "manual",
        summary=optional_str(payload.get("summary")),
        created_by_user=_resolve_user(db, optional_str(payload.get("created_by_user_id"))),
        graph=payload.get("graph_json") if isinstance(payload.get("graph_json"), Mapping) else None,
        metadata=payload.get("metadata_json")
        if isinstance(payload.get("metadata_json"), Mapping)
        else None,
        published_at=_parse_datetime(payload.get("published_at")),
    )
    _commit(db)
    return JSONResponse(
        {"automation_version": _json_value(serialize_automation_version(version))},
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/schedule-rules", status_code=status.HTTP_201_CREATED)
async def schedule_rules_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id")))
    if scope_node is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="scope_node_id is required."
        )
    _require_scope_access(db, current_principal, scope_node)
    automation_definition = (
        _resolve_automation_definition(db, optional_str(payload.get("automation_definition_id")))
        if optional_str(payload.get("automation_definition_id"))
        else None
    )
    automation_version = (
        _resolve_automation_version(db, optional_str(payload.get("automation_version_id")))
        if optional_str(payload.get("automation_version_id"))
        else None
    )
    if (
        automation_definition is None
        and automation_version is None
        and optional_str(payload.get("task_definition_id")) is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Provide automation_definition_id, automation_version_id, or task_definition_id"
            ),
        )
    if automation_definition is not None:
        _require_scope_access(db, current_principal, automation_definition.scope_node)
    if automation_version is not None:
        _require_scope_access(
            db,
            current_principal,
            automation_version.automation_definition.scope_node,
        )
    schedule_rule = ensure_schedule_rule(
        db,
        scope_node=scope_node,
        trigger_kind=optional_str(payload.get("trigger_kind")) or "rrule",
        rrule=optional_str(payload.get("rrule")),
        timezone=optional_str(payload.get("timezone")),
        automation_definition=automation_definition,
        automation_version=automation_version,
        task_definition_id=optional_str(payload.get("task_definition_id")),
        next_run_at=_parse_datetime(payload.get("next_run_at")),
        rule=payload.get("rule_json") if isinstance(payload.get("rule_json"), Mapping) else None,
        calendar_label=optional_str(payload.get("calendar_label")),
        paused_at=_parse_datetime(payload.get("paused_at")),
    )
    _commit(db)
    return JSONResponse(
        {"schedule_rule": _json_value(serialize_schedule_rule(schedule_rule))},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/telemetry")
def telemetry_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
    source_kind: str | None = None,
    event_kind: str | None = None,
    severity: str | None = None,
    scope_node_id: str | None = None,
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal, scope_node_id=scope_node_id)
    return JSONResponse(
        [
            _json_value(serialize_telemetry_event(event))
            for event in list_telemetry_events(
                db,
                scope_node_ids=scope_ids,
                source_kind=source_kind,
                event_kind=event_kind,
                severity=severity,
            )
        ]
    )


@router.get("/telemetry/{telemetry_event_id}")
def telemetry_show(
    telemetry_event_id: str,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    telemetry_event = db.get(TelemetryEvent, telemetry_event_id)
    if telemetry_event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telemetry event not found.",
        )
    _require_scope_access(db, current_principal, telemetry_event.scope_node)
    return JSONResponse(_json_value(serialize_telemetry_event(telemetry_event)))


@router.post("/telemetry", status_code=status.HTTP_201_CREATED)
async def telemetry_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id")))
    source_kind = optional_str(payload.get("source_kind"))
    event_kind = optional_str(payload.get("event_kind"))
    if scope_node is None or not source_kind or not event_kind:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_node_id, source_kind, and event_kind are required.",
        )
    _require_scope_access(db, current_principal, scope_node)
    event = record_telemetry_event(
        db,
        scope_node=scope_node,
        source_kind=source_kind,
        event_kind=event_kind,
        severity=optional_str(payload.get("severity")) or "info",
        source_id=optional_str(payload.get("source_id")),
        occurred_at=_parse_datetime(payload.get("occurred_at")),
        payload=payload.get("payload_json")
        if isinstance(payload.get("payload_json"), Mapping)
        else None,
    )
    _commit(db)
    return JSONResponse(
        {"telemetry_event": _json_value(serialize_telemetry_event(event))},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/schedule-rules")
def schedule_rules_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_schedule_rule(item))
            for item in list_schedule_rules(db, scope_node_ids=scope_ids)
        ]
    )


@router.get("/calendar")
def calendar_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=200, ge=1, le=1000),
    scope_node_id: str | None = None,
) -> JSONResponse:
    scope_node = _resolve_scope(db, optional_str(scope_node_id))
    if scope_node_id is not None and scope_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scope node not found.")
    if scope_node is not None:
        _require_scope_access(db, current_principal, scope_node)

    window_start = start_at or datetime.now(UTC)
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=UTC)
    window_end = end_at or (window_start + timedelta(days=days))
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=UTC)
    if window_end < window_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_at must be greater than or equal to start_at.",
        )

    projection = build_calendar_projection(
        db,
        start_at=window_start,
        end_at=window_end,
        scope_node_id=scope_node.id if scope_node is not None else None,
        limit=limit,
    )
    return JSONResponse(_json_value(projection))


@router.get("/events")
def events_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
    after_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    scope_node_id: str | None = None,
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal, scope_node_id=scope_node_id)
    events = list_platform_events(
        db,
        after_id=after_id,
        scope_node_ids=scope_ids,
        limit=limit,
    )
    return JSONResponse([_json_value(serialize_platform_event(event)) for event in events])


@router.get("/events/stream")
async def events_stream(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
    after_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    scope_node_id: str | None = None,
) -> StreamingResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal, scope_node_id=scope_node_id)
    session_factory = request.app.state.session_factory
    cursor = optional_str(after_id) or optional_str(request.headers.get("last-event-id"))

    async def event_stream() -> Any:
        nonlocal cursor
        while True:
            if await request.is_disconnected():
                break

            with session_factory() as stream_db:
                events = list_platform_events(
                    stream_db,
                    after_id=cursor,
                    scope_node_ids=scope_ids,
                    limit=limit,
                )

            if events:
                for event in events:
                    cursor = event.id
                    yield format_platform_event_sse(event)
                continue

            yield ": keep-alive\n\n"
            await asyncio.sleep(1.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/automation-runs")
def automation_runs_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_automation_run(item))
            for item in list_automation_runs(db, scope_node_ids=scope_ids)
        ]
    )


@router.post("/automation-runs", status_code=status.HTTP_201_CREATED)
async def automation_runs_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    version = _resolve_automation_version(
        db, optional_str(payload.get("automation_version_id")) or ""
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Automation version not found."
        )
    scope_node = (
        _resolve_scope(db, optional_str(payload.get("scope_node_id")))
        or version.automation_definition.scope_node
    )
    _require_scope_access(db, current_principal, scope_node)
    run = record_automation_run(
        db,
        automation_version=version,
        scope_node=scope_node,
        schedule_rule=_resolve_schedule_rule(
            db, optional_str(payload.get("schedule_rule_id")) or ""
        )
        if optional_str(payload.get("schedule_rule_id"))
        else None,
        triggered_by=optional_str(payload.get("triggered_by")) or "manual",
        status=optional_str(payload.get("status")) or "queued",
        requested_by_user=_resolve_user(db, optional_str(payload.get("requested_by_user_id"))),
        change_set=_resolve_change_set(db, optional_str(payload.get("change_set_id"))),
        reason=optional_str(payload.get("reason")),
        started_at=_parse_datetime(payload.get("started_at")),
        ended_at=_parse_datetime(payload.get("ended_at")),
        metadata=payload.get("metadata_json")
        if isinstance(payload.get("metadata_json"), Mapping)
        else None,
    )
    _commit(db)
    return JSONResponse(
        {"automation_run": _json_value(serialize_automation_run(run))},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/automation-run-events")
def automation_run_events_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_automation_run_event(item))
            for item in list_automation_run_events(db, scope_node_ids=scope_ids)
        ]
    )


@router.post("/automation-runs/{automation_run_id}/events", status_code=status.HTTP_201_CREATED)
async def automation_run_events_create(
    automation_run_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    run = db.get(AutomationRun, automation_run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Automation run not found."
        )
    run_scope = _resolve_scope(db, optional_str(run.scope_node_id))
    if run_scope is None:
        run_scope = run.automation_version.automation_definition.scope_node
    if run_scope is None and not current_principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unscoped automation runs require platform admin access.",
        )
    if run_scope is not None:
        _require_scope_access(db, current_principal, run_scope)
    payload = await _request_payload(request)
    event_kind = optional_str(payload.get("event_kind"))
    if not event_kind:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="event_kind is required."
        )
    event = record_automation_run_event(
        db,
        automation_run=run,
        event_kind=event_kind,
        status=optional_str(payload.get("status")) or "info",
        occurred_at=_parse_datetime(payload.get("occurred_at")),
        payload=payload.get("payload_json")
        if isinstance(payload.get("payload_json"), Mapping)
        else None,
    )
    _commit(db)
    return JSONResponse(
        {"automation_run_event": _json_value(serialize_automation_run_event(event))},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/alert-policies")
def alert_policies_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_alert_policy(policy))
            for policy in list_alert_policies(db, scope_node_ids=scope_ids)
        ]
    )


@router.post("/alert-policies", status_code=status.HTTP_201_CREATED)
async def alert_policies_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id")))
    key = optional_str(payload.get("key"))
    name = optional_str(payload.get("name"))
    source_kind = optional_str(payload.get("source_kind"))
    if scope_node is None or not key or not name or not source_kind:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_node_id, key, name, and source_kind are required.",
        )
    _require_scope_access(db, current_principal, scope_node)
    policy = ensure_alert_policy(
        db,
        scope_node=scope_node,
        key=key,
        name=name,
        source_kind=source_kind,
        rule=payload.get("rule_json") if isinstance(payload.get("rule_json"), Mapping) else None,
        severity=optional_str(payload.get("severity")) or "warning",
        is_active=bool(payload.get("is_active", True)),
    )
    _commit(db)
    return JSONResponse(
        {"alert_policy": _json_value(serialize_alert_policy(policy))},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/alerts")
def alerts_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
    status: str | None = None,
    scope_node_id: str | None = None,
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal, scope_node_id=scope_node_id)
    return JSONResponse(
        [
            _json_value(serialize_alert(item))
            for item in list_alerts(db, scope_node_ids=scope_ids, status=status)
        ]
    )


@router.get("/alerts/{alert_id}")
def alerts_show(
    alert_id: str,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    scope_node = _resolve_scope(db, alert.scope_node_id)
    _require_scope_access(db, current_principal, scope_node)
    return JSONResponse(_json_value(serialize_alert(alert)))


def _mutate_alert(
    request: Request,
    alert_id: str,
    db: Session,
    current_principal: PrincipalContext,
    status_name: str,
) -> JSONResponse:
    del request
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    scope_node = _resolve_scope(db, alert.scope_node_id)
    _require_scope_access(db, current_principal, scope_node)
    if status_name == "acknowledged":
        acknowledge_alert(db, alert=alert)
    elif status_name == "resolved":
        resolve_alert(db, alert=alert)
    elif status_name == "muted":
        mute_alert(db, alert=alert)
    elif status_name == "open":
        unmute_alert(db, alert=alert)
    else:
        set_alert_status(db, alert=alert, status=status_name)
    _commit(db)
    return JSONResponse({"alert": _json_value(serialize_alert(alert))})


@router.post("/alerts/{alert_id}/acknowledge")
def alerts_acknowledge(
    alert_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    return _mutate_alert(request, alert_id, db, current_principal, "acknowledged")


@router.post("/alerts/{alert_id}/resolve")
def alerts_resolve(
    alert_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    return _mutate_alert(request, alert_id, db, current_principal, "resolved")


@router.post("/alerts/{alert_id}/mute")
def alerts_mute(
    alert_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    return _mutate_alert(request, alert_id, db, current_principal, "muted")


@router.post("/alerts/{alert_id}/unmute")
def alerts_unmute(
    alert_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    return _mutate_alert(request, alert_id, db, current_principal, "open")


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
async def alerts_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    policy = db.get(AlertPolicy, optional_str(payload.get("alert_policy_id")) or "")
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert policy not found.")
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id"))) or policy.scope_node
    _require_scope_access(db, current_principal, scope_node)
    _require_scope_access(db, current_principal, policy.scope_node)
    telemetry_event = (
        db.get(TelemetryEvent, optional_str(payload.get("telemetry_event_id")) or "")
        if optional_str(payload.get("telemetry_event_id"))
        else None
    )
    if telemetry_event is not None:
        _require_scope_access(db, current_principal, telemetry_event.scope_node)
    automation_run_event = (
        db.get(AutomationRunEvent, optional_str(payload.get("automation_run_event_id")) or "")
        if optional_str(payload.get("automation_run_event_id"))
        else None
    )
    if automation_run_event is not None:
        run_scope = _resolve_scope(
            db,
            optional_str(automation_run_event.automation_run.scope_node_id),
        )
        if run_scope is None:
            run_scope = (
                automation_run_event.automation_run.automation_version.automation_definition.scope_node
            )
        if run_scope is not None:
            _require_scope_access(db, current_principal, run_scope)
    alert = open_alert(
        db,
        alert_policy=policy,
        scope_node=scope_node,
        telemetry_event=telemetry_event,
        automation_run_event=automation_run_event,
        summary=optional_str(payload.get("summary")),
        opened_at=_parse_datetime(payload.get("opened_at")),
        status=optional_str(payload.get("status")) or "open",
    )
    _commit(db)
    return JSONResponse(
        {"alert": _json_value(serialize_alert(alert))}, status_code=status.HTTP_201_CREATED
    )


@router.get("/change-sets")
def change_sets_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.read")),
) -> JSONResponse:
    scope_ids = _scope_ids_for_principal(db, current_principal)
    return JSONResponse(
        [
            _json_value(serialize_change_set(change_set))
            for change_set in list_change_sets(db, scope_node_ids=scope_ids)
        ]
    )


@router.post("/change-sets", status_code=status.HTTP_201_CREATED)
async def change_sets_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    payload = await _request_payload(request)
    key = optional_str(payload.get("key"))
    summary = optional_str(payload.get("summary"))
    if not key or not summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="key and summary are required.",
        )
    scope_node = _resolve_scope(db, optional_str(payload.get("scope_node_id")))
    if scope_node is not None:
        _require_scope_access(db, current_principal, scope_node)
    elif not current_principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scoped change sets require nursery or organization access.",
        )
    change_set = ensure_change_set(
        db,
        key=key,
        summary=summary,
        scope_node=scope_node,
        requested_by_user=_resolve_user(db, optional_str(payload.get("requested_by_user_id"))),
        reason=optional_str(payload.get("reason")),
        metadata=payload.get("metadata_json")
        if isinstance(payload.get("metadata_json"), Mapping)
        else None,
        status=optional_str(payload.get("status")) or "draft",
    )
    _commit(db)
    return JSONResponse(
        {"change_set": _json_value(serialize_change_set(change_set))},
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/change-sets/{change_set_id}/entries", status_code=status.HTTP_201_CREATED)
async def change_set_entries_create(
    change_set_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("platform.manage")),
) -> JSONResponse:
    change_set = _resolve_change_set(db, change_set_id)
    if change_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change set not found.")
    if change_set.scope_node is not None:
        _require_scope_access(db, current_principal, change_set.scope_node)
    elif not current_principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unscoped change sets require platform admin access.",
        )
    payload = await _request_payload(request)
    entity_kind = optional_str(payload.get("entity_kind"))
    entity_id = optional_str(payload.get("entity_id"))
    operation = optional_str(payload.get("operation"))
    if not entity_kind or not entity_id or not operation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_kind, entity_id, and operation are required.",
        )
    entry = append_change_set_entry(
        db,
        change_set=change_set,
        entity_kind=entity_kind,
        entity_id=entity_id,
        operation=operation,
        diff=payload.get("diff_json") if isinstance(payload.get("diff_json"), Mapping) else None,
        is_guarded=bool(payload.get("is_guarded", True)),
        status=optional_str(payload.get("status")) or "pending",
        applied_at=_parse_datetime(payload.get("applied_at")),
        reverted_at=_parse_datetime(payload.get("reverted_at")),
    )
    _commit(db)
    return JSONResponse(
        {"entry": _json_value(serialize_change_set_entry(entry))},
        status_code=status.HTTP_201_CREATED,
    )
