from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.dependencies import get_current_principal, require_permission
from app.access.models import Group, Permission, Role, ServiceAccount, ServiceAccountToken
from app.access.services import (
    PrincipalContext,
    ensure_group,
    ensure_group_membership,
    ensure_group_role,
    ensure_role,
    ensure_role_permission,
    ensure_service_account,
    ensure_service_account_role,
    issue_service_account_token,
    list_groups,
    list_permissions,
    list_roles,
    list_service_accounts,
    normalize_key,
    normalize_slug,
    serialize_group,
    serialize_permission,
    serialize_principal,
    serialize_role,
    serialize_service_account,
    serialize_service_account_token,
)
from app.api.v1.common import commit_session, parse_iso_datetime, request_payload
from app.auth.models import User
from app.auth.services import serialize_user
from app.common.forms import optional_str
from app.dependencies import get_db

router = APIRouter(prefix="/access", tags=["access"])


def _normalize_slug_or_400(raw_slug: str) -> str:
    try:
        return normalize_slug(raw_slug)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slug must contain at least one letter or number.",
        ) from exc


def _string_list(raw_value: Any, *, field_name: str) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        values = [item.strip() for item in raw_value.split(",")]
        return [item for item in values if item]
    if isinstance(raw_value, list):
        values = [str(item).strip() for item in raw_value]
        return [item for item in values if item]
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"{field_name} must be a list of strings.",
    )


def _parse_datetime(value: Any) -> datetime | None:
    return parse_iso_datetime(value, field_name="expires_at")


def _resolve_group(session: Session, identifier: str) -> Group | None:
    group = session.get(Group, identifier)
    if group is not None:
        return group
    try:
        normalized = normalize_slug(identifier)
    except ValueError:
        return None
    return session.scalar(select(Group).where(Group.slug == normalized))


def _resolve_role(session: Session, identifier: str) -> Role | None:
    role = session.get(Role, identifier)
    if role is not None:
        return role
    return session.scalar(select(Role).where(Role.key == normalize_key(identifier)))


def _resolve_permission(session: Session, identifier: str) -> Permission | None:
    permission = session.get(Permission, identifier)
    if permission is not None:
        return permission
    return session.scalar(select(Permission).where(Permission.key == normalize_key(identifier)))


def _resolve_service_account(session: Session, identifier: str) -> ServiceAccount | None:
    service_account = session.get(ServiceAccount, identifier)
    if service_account is not None:
        return service_account
    try:
        normalized = normalize_slug(identifier)
    except ValueError:
        return None
    return session.scalar(select(ServiceAccount).where(ServiceAccount.slug == normalized))


def _resolve_user(session: Session, identifier: str) -> User | None:
    user = session.get(User, identifier)
    if user is not None:
        return user
    normalized = optional_str(identifier)
    if normalized is None:
        return None
    return session.scalar(select(User).where(User.username == normalized))


def _serialize_group_detail(group: Group) -> dict[str, Any]:
    return {
        "group": serialize_group(group),
        "members": [serialize_user(membership.user) for membership in group.memberships],
        "service_accounts": [
            serialize_service_account(service_account) for service_account in group.service_accounts
        ],
    }


def _serialize_role_detail(role: Role) -> dict[str, Any]:
    return {
        "role": serialize_role(role),
        "permissions": [
            serialize_permission(role_permission.permission)
            for role_permission in role.role_permissions
        ],
    }


def _serialize_service_account_detail(service_account: ServiceAccount) -> dict[str, Any]:
    return {
        "service_account": serialize_service_account(service_account),
        "tokens": [serialize_service_account_token(token) for token in service_account.tokens],
    }


@router.get("/context")
def access_context(
    principal: PrincipalContext = Depends(get_current_principal),
) -> JSONResponse:
    return JSONResponse({"authenticated": True, "principal": serialize_principal(principal)})


@router.get("/permissions")
def permissions_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("permissions.read")),
) -> JSONResponse:
    del current_principal
    return JSONResponse([serialize_permission(permission) for permission in list_permissions(db)])


@router.get("/permissions/{permission_identifier}")
def permissions_show(
    permission_identifier: str,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("permissions.read")),
) -> JSONResponse:
    del current_principal
    permission = _resolve_permission(db, permission_identifier)
    if permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")
    return JSONResponse(serialize_permission(permission))


@router.get("/roles")
def roles_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("roles.read")),
) -> JSONResponse:
    del current_principal
    return JSONResponse([serialize_role(role) for role in list_roles(db)])


@router.get("/roles/{role_identifier}")
def roles_show(
    role_identifier: str,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("roles.read")),
) -> JSONResponse:
    del current_principal
    role = _resolve_role(db, role_identifier)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
    return JSONResponse(_serialize_role_detail(role))


@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def roles_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("roles.manage")),
) -> JSONResponse:
    del current_principal
    payload = await request_payload(request)
    raw_key = str(payload.get("key") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not raw_key or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="key and name are required."
        )
    key = normalize_key(raw_key)

    description = optional_str(payload.get("description"))
    permission_keys = _string_list(payload.get("permission_keys"), field_name="permission_keys")
    role = ensure_role(
        db,
        key=key,
        name=name,
        description=description,
        is_system=bool(payload.get("is_system", False)),
    )
    for permission_key in permission_keys:
        permission = _resolve_permission(db, permission_key)
        if permission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Permission not found: {permission_key}",
            )
        ensure_role_permission(db, role, permission)
    commit_session(db)
    return JSONResponse(_serialize_role_detail(role), status_code=status.HTTP_201_CREATED)


@router.get("/groups")
def groups_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("groups.read")),
) -> JSONResponse:
    del current_principal
    return JSONResponse([serialize_group(group) for group in list_groups(db)])


@router.get("/groups/{group_identifier}")
def groups_show(
    group_identifier: str,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("groups.read")),
) -> JSONResponse:
    del current_principal
    group = _resolve_group(db, group_identifier)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
    return JSONResponse(_serialize_group_detail(group))


@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def groups_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("groups.manage")),
) -> JSONResponse:
    del current_principal
    payload = await request_payload(request)
    raw_slug = str(payload.get("slug") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not raw_slug or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="slug and name are required."
        )
    slug = _normalize_slug_or_400(raw_slug)

    group = ensure_group(
        db,
        slug=slug,
        name=name,
        group_type=optional_str(payload.get("group_type")) or "team",
        description=optional_str(payload.get("description")),
        scope_type=optional_str(payload.get("scope_type")),
        scope_id=optional_str(payload.get("scope_id")),
        is_system=bool(payload.get("is_system", False)),
    )
    for role_key in _string_list(payload.get("role_keys"), field_name="role_keys"):
        role = _resolve_role(db, role_key)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role not found: {role_key}",
            )
        ensure_group_role(db, group, role)
    commit_session(db)
    return JSONResponse(_serialize_group_detail(group), status_code=status.HTTP_201_CREATED)


@router.post("/groups/{group_identifier}/members", status_code=status.HTTP_201_CREATED)
async def groups_add_member(
    group_identifier: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("groups.manage")),
) -> JSONResponse:
    del current_principal
    payload = await request_payload(request)
    group = _resolve_group(db, group_identifier)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    user_identifier = str(payload.get("user_id") or payload.get("username") or "").strip()
    if not user_identifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required.")
    user = _resolve_user(db, user_identifier)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    ensure_group_membership(db, group, user)
    commit_session(db)
    return JSONResponse(_serialize_group_detail(group), status_code=status.HTTP_201_CREATED)


@router.post("/groups/{group_identifier}/roles", status_code=status.HTTP_201_CREATED)
async def groups_add_role(
    group_identifier: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("groups.manage")),
) -> JSONResponse:
    del current_principal
    payload = await request_payload(request)
    group = _resolve_group(db, group_identifier)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    role_identifier = str(payload.get("role_id") or payload.get("role_key") or "").strip()
    if not role_identifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role_id is required.")
    role = _resolve_role(db, role_identifier)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    ensure_group_role(db, group, role)
    commit_session(db)
    return JSONResponse(_serialize_group_detail(group), status_code=status.HTTP_201_CREATED)


@router.get("/service-accounts")
def service_accounts_index(
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("service_accounts.read")),
) -> JSONResponse:
    del current_principal
    return JSONResponse(
        [
            serialize_service_account(service_account)
            for service_account in list_service_accounts(db)
        ]
    )


@router.get("/service-accounts/{service_account_identifier}")
def service_accounts_show(
    service_account_identifier: str,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("service_accounts.read")),
) -> JSONResponse:
    del current_principal
    service_account = _resolve_service_account(db, service_account_identifier)
    if service_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service account not found.",
        )
    return JSONResponse(_serialize_service_account_detail(service_account))


@router.post("/service-accounts", status_code=status.HTTP_201_CREATED)
async def service_accounts_create(
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("service_accounts.manage")),
) -> JSONResponse:
    del current_principal
    payload = await request_payload(request)
    raw_slug = str(payload.get("slug") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not raw_slug or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="slug and name are required."
        )
    slug = _normalize_slug_or_400(raw_slug)

    group_identifier = optional_str(payload.get("group_id")) or optional_str(
        payload.get("group_slug")
    )
    group = _resolve_group(db, group_identifier) if group_identifier else None
    if group_identifier and group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    service_account = ensure_service_account(
        db,
        slug=slug,
        name=name,
        account_type=optional_str(payload.get("account_type")) or "automation",
        description=optional_str(payload.get("description")),
        group=group,
        is_system=bool(payload.get("is_system", False)),
        is_active=bool(payload.get("is_active", True)),
    )

    for role_key in _string_list(payload.get("role_keys"), field_name="role_keys"):
        role = _resolve_role(db, role_key)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role not found: {role_key}",
            )
        ensure_service_account_role(db, service_account, role)

    created_by_identifier = optional_str(payload.get("created_by_user_id"))
    if created_by_identifier:
        creator = _resolve_user(db, created_by_identifier)
        if creator is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Creator user not found."
            )
        service_account.created_by_user = creator
    commit_session(db)
    return JSONResponse(
        _serialize_service_account_detail(service_account), status_code=status.HTTP_201_CREATED
    )


@router.get("/service-accounts/{service_account_identifier}/tokens")
def service_account_tokens_index(
    service_account_identifier: str,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("service_accounts.read")),
) -> JSONResponse:
    del current_principal
    service_account = _resolve_service_account(db, service_account_identifier)
    if service_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service account not found.",
        )
    return JSONResponse(
        [serialize_service_account_token(token) for token in service_account.tokens]
    )


@router.post(
    "/service-accounts/{service_account_identifier}/tokens", status_code=status.HTTP_201_CREATED
)
async def service_account_tokens_create(
    service_account_identifier: str,
    request: Request,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("service_tokens.manage")),
) -> JSONResponse:
    del current_principal
    service_account = _resolve_service_account(db, service_account_identifier)
    if service_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service account not found.",
        )

    payload = await request_payload(request)
    token, token_value = issue_service_account_token(
        db,
        service_account,
        label=optional_str(payload.get("label")),
        expires_at=_parse_datetime(payload.get("expires_at")),
    )
    commit_session(db)
    return JSONResponse(
        {
            "token": token_value,
            "token_record": serialize_service_account_token(token),
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.delete("/service-accounts/{service_account_identifier}/tokens/{token_identifier}")
def service_account_tokens_delete(
    service_account_identifier: str,
    token_identifier: str,
    db: Session = Depends(get_db),
    current_principal: PrincipalContext = Depends(require_permission("service_tokens.manage")),
) -> JSONResponse:
    del current_principal
    service_account = _resolve_service_account(db, service_account_identifier)
    if service_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service account not found.",
        )
    token = db.get(ServiceAccountToken, token_identifier)
    if token is None or token.service_account_id != service_account.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found.")
    token.revoked_at = datetime.now(UTC)
    db.add(token)
    commit_session(db)
    return JSONResponse(serialize_service_account_token(token))
