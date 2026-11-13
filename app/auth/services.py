from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import Settings
from app.security import hash_password, verify_password

UserRole = Literal["admin", "user"]


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def get_user_by_username(session: Session, username: str) -> User | None:
    normalized = normalize_username(username)
    stmt = select(User).where(User.username == normalized)
    return session.scalar(stmt)


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(session, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def user_role(user: User) -> UserRole:
    return "admin" if user.is_admin else "user"


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "role": user_role(user),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def create_user(
    session: Session,
    *,
    username: str,
    full_name: str,
    password: str,
    email: str | None = None,
    is_active: bool = True,
    is_admin: bool = False,
) -> User:
    normalized_username = normalize_username(username)
    if not normalized_username:
        raise ValueError("username is required.")

    normalized_full_name = full_name.strip()
    if not normalized_full_name:
        raise ValueError("full_name is required.")

    if not password:
        raise ValueError("password is required.")

    existing = session.scalar(select(User).where(User.username == normalized_username))
    if existing is not None:
        return existing

    normalized_email = email.strip() if isinstance(email, str) and email.strip() else None
    user = User(
        username=normalized_username,
        full_name=normalized_full_name,
        email=normalized_email,
        password_hash=hash_password(password),
        is_active=is_active,
        is_admin=is_admin,
    )
    session.add(user)
    session.flush()
    return user


def ensure_admin_user(session: Session, settings: Settings) -> User:
    normalized_username = normalize_username(settings.admin_username)
    existing = session.scalar(select(User).where(User.username == normalized_username))
    if existing is not None:
        existing.full_name = settings.admin_full_name.strip()
        existing.email = settings.admin_email.strip() if settings.admin_email else None
        existing.password_hash = hash_password(settings.admin_password)
        existing.is_active = True
        existing.is_admin = True
        session.add(existing)
        session.flush()
        return existing

    return create_user(
        session,
        username=settings.admin_username,
        full_name=settings.admin_full_name,
        password=settings.admin_password,
        email=settings.admin_email,
        is_active=True,
        is_admin=True,
    )


def mark_login_success(session: Session, user: User) -> None:
    user.last_login_at = datetime.now(UTC)
    session.add(user)
