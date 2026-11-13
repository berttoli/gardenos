from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.common.forms import payload_from_mapping
from app.common.serialization import json_value


async def request_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        if isinstance(body, Mapping):
            return dict(body)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON object expected.")
    form = await request.form()
    return payload_from_mapping(dict(form.multi_items()))


def commit_session(session: Session) -> None:
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise


def parse_iso_datetime(
    value: Any,
    *,
    field_name: str,
    plural: bool = False,
) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        suffix = "strings" if plural else "string"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be an ISO 8601 {suffix}.",
        )
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        suffix = "strings" if plural else "string"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be an ISO 8601 {suffix}.",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


__all__ = ["commit_session", "json_value", "parse_iso_datetime", "request_payload"]
