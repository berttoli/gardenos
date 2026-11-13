from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.forms import optional_str
from app.common.serialization import json_value
from app.platform.models import PlatformEvent, ScopeNode

EVENT_TYPE_PATTERN = re.compile(r"[^a-z0-9._:-]+")
KEY_PATTERN = re.compile(r"[^a-z0-9]+")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_event_type(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("An event type is required.")
    normalized = EVENT_TYPE_PATTERN.sub("-", text.casefold())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("An event type is required.")
    return normalized


def _normalize_key(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("A key is required.")
    normalized = KEY_PATTERN.sub("_", text.casefold()).strip("_")
    if not normalized:
        raise ValueError("A key is required.")
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


def record_platform_event(
    session: Session,
    *,
    event_type: str,
    source_kind: str,
    source_id: str | int,
    scope_node: ScopeNode | str | None = None,
    payload: Mapping[str, Any] | None = None,
    occurred_at: datetime | None = None,
    trace_id: str | None = None,
    correlation_id: str | None = None,
    schema_version: str = "v1",
    consumed_at: datetime | None = None,
) -> PlatformEvent:
    resolved_scope = _resolve_scope_node(session, scope_node)
    if source_id is None:
        raise ValueError("source_id is required.")
    normalized_source_id = optional_str(str(source_id))
    if normalized_source_id is None:
        raise ValueError("source_id is required.")

    event = PlatformEvent(
        scope_node=resolved_scope,
        event_type=_normalize_event_type(event_type),
        source_kind=_normalize_key(source_kind),
        source_id=normalized_source_id,
        schema_version=optional_str(schema_version) or "v1",
        trace_id=optional_str(trace_id),
        correlation_id=optional_str(correlation_id),
        occurred_at=occurred_at or _utc_now(),
        payload_json=json_value(dict(payload or {})),
        consumed_at=consumed_at,
    )
    session.add(event)
    session.flush()
    return event


def list_platform_events(
    session: Session,
    *,
    after_id: str | None = None,
    scope_node_ids: set[str] | None = None,
    limit: int = 200,
) -> list[PlatformEvent]:
    stmt = select(PlatformEvent)
    if scope_node_ids is not None:
        if not scope_node_ids:
            return []
        stmt = stmt.where(PlatformEvent.scope_node_id.in_(sorted(scope_node_ids)))
    normalized_after = optional_str(after_id)
    if normalized_after is not None:
        cursor_event = session.get(PlatformEvent, normalized_after)
        if cursor_event is not None:
            stmt = stmt.where(
                (PlatformEvent.created_at > cursor_event.created_at)
                | (
                    (PlatformEvent.created_at == cursor_event.created_at)
                    & (PlatformEvent.id > cursor_event.id)
                ),
            )
        else:
            stmt = stmt.where(PlatformEvent.id > normalized_after)
    stmt = stmt.order_by(PlatformEvent.created_at.asc(), PlatformEvent.id.asc()).limit(limit)
    return list(session.scalars(stmt).all())


def serialize_platform_event(event: PlatformEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "scope_node_id": event.scope_node_id,
        "event_type": event.event_type,
        "source_kind": event.source_kind,
        "source_id": event.source_id,
        "schema_version": event.schema_version,
        "trace_id": event.trace_id,
        "correlation_id": event.correlation_id,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": json_value(event.payload_json),
        "consumed_at": event.consumed_at.isoformat() if event.consumed_at else None,
        "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(),
    }


def format_platform_event_sse(event: PlatformEvent) -> str:
    data = json.dumps(serialize_platform_event(event), separators=(",", ":"), ensure_ascii=False)
    return f"id: {event.id}\ndata: {data}\n\n"
