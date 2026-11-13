from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.access.dependencies import get_current_principal
from app.access.services import build_user_principal, serialize_principal
from app.api.v1.common import commit_session, json_value, request_payload
from app.auth.models import User
from app.auth.services import (
    authenticate_user,
    mark_login_success,
    normalize_username,
    serialize_user,
)
from app.core.rate_limit import LoginRateLimiter
from app.dependencies import get_db
from app.security import get_or_create_csrf_token, validate_csrf_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_identifier(request: Request, username: str) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if isinstance(forwarded, str) and forwarded.strip():
        host = forwarded.split(",", 1)[0].strip() or "unknown"
    else:
        host = request.client.host if request.client else "unknown"
    return f"{host}:{normalize_username(username)}"


def _host_identifier(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if isinstance(forwarded, str) and forwarded.strip():
        host = forwarded.split(",", 1)[0].strip() or "unknown"
    else:
        host = request.client.host if request.client else "unknown"
    return f"{host}:*"


def _current_session_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, str) or not user_id:
        request.session.clear()
        return None

    try:
        user = db.get(User, user_id)
    except (TypeError, ValueError):
        request.session.clear()
        return None

    if user is None or not user.is_active:
        request.session.clear()
        return None
    return user


def _session_payload(request: Request, db: Session) -> dict[str, Any]:
    settings = request.app.state.settings
    user = _current_session_user(request, db)
    csrf_token = get_or_create_csrf_token(request.session, settings.csrf_session_key)
    principal = build_user_principal(db, user) if user is not None else None
    return {
        "authenticated": user is not None,
        "csrf_token": csrf_token,
        "user": serialize_user(user) if user is not None else None,
        "principal": serialize_principal(principal) if principal is not None else None,
    }


def _auth_context_payload(request: Request, db: Session) -> dict[str, Any]:
    settings = request.app.state.settings
    user = _current_session_user(request, db)
    principal = None
    try:
        principal = get_current_principal(request, db)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_401_UNAUTHORIZED:
            raise

    # Authentication may clear an absent or expired session. Issue the token
    # afterwards so the returned value is also persisted in the session cookie.
    csrf_token = get_or_create_csrf_token(request.session, settings.csrf_session_key)
    authenticated = principal is not None or user is not None
    return {
        "authenticated": authenticated,
        "csrf_token": csrf_token,
        "user": serialize_user(user) if user is not None else None,
        "principal": serialize_principal(principal) if principal is not None else None,
    }


def _submitted_csrf_token(request: Request, payload: Mapping[str, Any]) -> str | None:
    header_token = request.headers.get("x-csrf-token")
    if isinstance(header_token, str) and header_token.strip():
        return header_token.strip()
    submitted = payload.get("csrf_token")
    if submitted is None:
        return None
    text = str(submitted).strip()
    return text or None


@router.get("/session")
def session_status(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(_session_payload(request, db))


@router.get("/context")
def auth_context(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(json_value(_auth_context_payload(request, db)))


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    payload = await request_payload(request)
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    settings = request.app.state.settings
    rate_limiter: LoginRateLimiter = request.app.state.login_rate_limiter
    submitted_token = _submitted_csrf_token(request, payload)

    if not validate_csrf_token(request.session, settings.csrf_session_key, submitted_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The login request expired or was tampered with.",
        )

    next_url = payload.get("next")
    if not isinstance(next_url, str):
        next_url = None
    sanitized_next = (
        next_url if next_url and next_url.startswith("/") and not next_url.startswith("//") else "/"
    )

    client_key = _client_identifier(request, username or "unknown")
    host_key = _host_identifier(request)
    limited, retry_after = rate_limiter.is_limited(client_key)
    if not limited:
        limited, retry_after = rate_limiter.is_limited(host_key)
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {retry_after} seconds.",
        )

    user = authenticate_user(db, username, password)
    if user is None:
        rate_limiter.record_failure(client_key)
        rate_limiter.record_failure(host_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    request.session.clear()
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["full_name"] = user.full_name
    request.session["is_admin"] = user.is_admin
    request.session["authenticated"] = True
    get_or_create_csrf_token(request.session, settings.csrf_session_key)
    mark_login_success(db, user)
    commit_session(db)
    rate_limiter.clear(client_key)
    rate_limiter.clear(host_key)
    payload = _session_payload(request, db)
    payload["next_url"] = sanitized_next
    return JSONResponse(json_value(payload))


@router.post("/logout")
async def logout(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    payload = await request_payload(request)
    submitted_token = _submitted_csrf_token(request, payload)
    if not validate_csrf_token(request.session, settings.csrf_session_key, submitted_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The logout request expired or was tampered with.",
        )
    request.session.clear()
    return JSONResponse({"authenticated": False})
