from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import Settings
from app.database import SessionFactory
from app.security import validate_csrf_token

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_factory(request: Request) -> SessionFactory:
    return request.app.state.session_factory


def get_db(request: Request) -> Iterator[Session]:
    session_factory = get_session_factory(request)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, str) or not user_id:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required."
        ) from None

    try:
        user = db.get(User, user_id)
    except (ValueError, TypeError):
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required."
        ) from None

    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required."
        ) from None

    if request.method.upper() not in SAFE_METHODS:
        settings = get_settings(request)
        submitted_token = request.headers.get("x-csrf-token")
        if not validate_csrf_token(request.session, settings.csrf_session_key, submitted_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The request expired or was tampered with.",
            ) from None
    return user
