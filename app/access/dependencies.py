from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.access.services import (
    PrincipalContext,
    authenticate_service_account_token,
    build_service_account_principal,
    build_user_principal,
    normalize_key,
)
from app.dependencies import get_current_user, get_db

SERVICE_TOKEN_HEADER = "x-garden-service-token"
AUTHORIZATION_HEADER = "authorization"


def _extract_service_token(request: Request) -> str | None:
    header = request.headers.get(AUTHORIZATION_HEADER)
    if isinstance(header, str):
        scheme, _, token = header.partition(" ")
        if scheme.casefold() == "bearer" and token.strip():
            return token.strip()

    fallback = request.headers.get(SERVICE_TOKEN_HEADER)
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return None


def get_current_principal(
    request: Request,
    db: Session = Depends(get_db),
) -> PrincipalContext:
    service_token = _extract_service_token(request)
    if service_token is not None:
        service_account = authenticate_service_account_token(db, service_token)
        if service_account is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            ) from None
        return build_service_account_principal(db, service_account)

    user = get_current_user(request, db)
    return build_user_principal(db, user)


def require_permission(*permission_keys: str) -> Callable[[PrincipalContext], PrincipalContext]:
    required = {
        normalize_key(permission_key)
        for permission_key in permission_keys
        if permission_key.strip()
    }

    def dependency(
        principal: PrincipalContext = Depends(get_current_principal),
    ) -> PrincipalContext:
        if required.issubset(set(principal.permissions)):
            return principal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions.",
        ) from None

    return dependency
