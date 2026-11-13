from __future__ import annotations

import secrets
from collections.abc import MutableMapping
from hmac import compare_digest

from passlib.context import CryptContext

PASSWORD_CONTEXT = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return PASSWORD_CONTEXT.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_CONTEXT.verify(password, password_hash)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def get_or_create_csrf_token(session: MutableMapping[str, object], session_key: str) -> str:
    token = session.get(session_key)
    if not isinstance(token, str) or not token:
        token = generate_csrf_token()
        session[session_key] = token
    return token


def validate_csrf_token(
    session: MutableMapping[str, object],
    session_key: str,
    submitted_token: str | None,
) -> bool:
    token = session.get(session_key)
    if not isinstance(token, str) or not token:
        return False
    if not submitted_token:
        return False
    return compare_digest(token, submitted_token)
