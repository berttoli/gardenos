from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.access.dependencies import get_current_principal
from app.access.services import PrincipalContext, build_user_principal
from app.api.v1.common import request_payload
from app.auth.models import User
from app.dependencies import get_db
from app.platform.events import format_platform_event_sse, list_platform_events
from app.platform.scope_access import resolve_visible_scope_ids
from app.security import get_or_create_csrf_token
from app.workspace.services import build_workspace_payload

router = APIRouter(prefix="/api/v2", tags=["v2"])


def _rpc_result(request_id: Any, data: Any) -> JSONResponse:
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "version": "v2",
                "data": data,
            },
        },
    )


def _rpc_error(
    request_id: Any,
    code: int,
    message: str,
    *,
    data: dict[str, Any] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if data is not None:
        payload["error"]["data"] = data
    return JSONResponse(payload, status_code=status.HTTP_400_BAD_REQUEST)


def _require_jsonrpc(request: dict[str, Any]) -> tuple[str, Any, dict[str, Any]]:
    if request.get("jsonrpc") != "2.0":
        raise ValueError("jsonrpc must be '2.0'.")
    method = request.get("method")
    if not isinstance(method, str) or not method.strip():
        raise ValueError("method is required.")
    params = request.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("params must be an object.")
    return method.strip(), request.get("id"), params


@router.post("/rpc")
async def rpc_dispatch(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    payload = await request_payload(request)
    try:
        method, request_id, params = _require_jsonrpc(payload)
    except ValueError as exc:
        return _rpc_error(None, -32600, str(exc))

    if method == "rpc.query.auth.context":
        settings = request.app.state.settings
        csrf_token = get_or_create_csrf_token(request.session, settings.csrf_session_key)
        user_id = request.session.get("user_id")
        user: User | None = None
        if isinstance(user_id, str) and user_id:
            user = db.get(User, user_id)
        principal = None
        try:
            principal = get_current_principal(request, db)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_401_UNAUTHORIZED:
                raise
        return _rpc_result(
            request_id,
            {
                "authenticated": principal is not None or user is not None,
                "csrf_token": csrf_token,
                "user": None
                if user is None
                else {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "email": user.email,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "role": "admin" if user.is_admin else "user",
                    "last_login_at": (
                        user.last_login_at.isoformat() if user.last_login_at else None
                    ),
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat(),
                },
                "principal": None
                if principal is None
                else {
                    "user_id": principal.user_id,
                    "username": principal.username,
                    "full_name": principal.full_name,
                    "is_admin": principal.is_admin,
                    "permissions": principal.permissions,
                    "scope_node_ids": principal.scope_node_ids,
                },
            },
        )

    if method == "rpc.query.workspace.bootstrap":
        user_id = request.session.get("user_id")
        if not isinstance(user_id, str) or not user_id:
            return _rpc_error(request_id, -32001, "Authentication required.")
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return _rpc_error(request_id, -32001, "Authentication required.")
        scope_node_id = params.get("scope_node_id")
        if scope_node_id is not None and not isinstance(scope_node_id, str):
            return _rpc_error(request_id, -32602, "scope_node_id must be a string or null.")
        selected_location_id = params.get("selected_location_id")
        if selected_location_id is not None and not isinstance(selected_location_id, str):
            return _rpc_error(request_id, -32602, "selected_location_id must be a string or null.")
        return _rpc_result(
            request_id,
            build_workspace_payload(
                db,
                build_user_principal(db, user),
                selected_location_id=selected_location_id,
            ),
        )

    return _rpc_error(request_id, -32601, f"Method not found: {method}")


@router.get("/rpc/stream")
def rpc_stream(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(get_current_principal),
) -> StreamingResponse:
    scope_ids = resolve_visible_scope_ids(db, current_principal)
    after_id = request.query_params.get("after_id")

    events = list_platform_events(db, after_id=after_id, scope_node_ids=scope_ids, limit=200)

    async def event_stream() -> AsyncIterator[str]:
        for event in events:
            yield format_platform_event_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
