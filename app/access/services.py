from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.models import (
    Group,
    GroupMembership,
    GroupRole,
    Permission,
    Role,
    RolePermission,
    ServiceAccount,
    ServiceAccountRole,
    ServiceAccountToken,
)
from app.auth.models import User
from app.platform.models import ScopeMembership

PrincipalKind = Literal["user", "service_account"]
AuthMethod = Literal["session", "service_token"]


@dataclass(slots=True)
class PrincipalContext:
    kind: PrincipalKind
    id: str
    label: str
    auth_method: AuthMethod
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    group_ids: tuple[str, ...] = ()
    scope_ids: tuple[str, ...] = ()
    username: str | None = None
    service_account_slug: str | None = None
    is_admin: bool = False


DEFAULT_PERMISSION_SPECS: tuple[tuple[str, str, str], ...] = (
    ("access.read", "Read access metadata", "View roles, groups, permissions, and principals."),
    (
        "access.manage",
        "Manage access metadata",
        "Create and manage groups, roles, service accounts, and tokens.",
    ),
    ("groups.read", "Read groups", "Inspect group membership and assigned roles."),
    ("groups.manage", "Manage groups", "Create and update groups and memberships."),
    ("roles.read", "Read roles", "Inspect the role catalog and attached permissions."),
    ("roles.manage", "Manage roles", "Create and update roles and role permissions."),
    (
        "permissions.read",
        "Read permissions",
        "Inspect the permission catalog used by roles and groups.",
    ),
    (
        "service_accounts.read",
        "Read service accounts",
        "Inspect service accounts and token metadata without exposing secrets.",
    ),
    (
        "service_accounts.manage",
        "Manage service accounts",
        "Create, update, and disable service accounts.",
    ),
    (
        "service_tokens.manage",
        "Manage service tokens",
        "Mint, revoke, and rotate service account tokens.",
    ),
    ("users.read", "Read users", "Inspect user identities."),
    ("users.manage", "Manage users", "Create and update users and memberships."),
    ("plants.read", "Read plants", "Inspect garden plant state."),
    ("plants.write", "Write plants", "Mutate plant records and placement state."),
    ("tasks.read", "Read tasks", "Inspect task state and schedules."),
    ("tasks.write", "Write tasks", "Create and complete tasks."),
    ("conversations.read", "Read conversations", "Inspect conversation threads and messages."),
    (
        "conversations.write",
        "Write conversations",
        "Create conversations and append messages.",
    ),
    ("onboarding.read", "Read onboarding", "Inspect draft onboarding state."),
    ("onboarding.write", "Write onboarding", "Create and update onboarding drafts."),
    ("media.read", "Read media", "Inspect media assets and download metadata."),
    ("media.write", "Write media", "Upload and promote media assets."),
    ("monitoring.read", "Read monitoring", "Inspect telemetry, logs, and alerts."),
    ("monitoring.write", "Write monitoring", "Record telemetry and emit alerts."),
    ("logs.read", "Read logs", "Inspect structured logs and audit events."),
    ("automation.execute", "Execute automations", "Run scheduled workflows and automations."),
    (
        "platform.read",
        "Read platform scaffolding",
        "Inspect scopes, automations, skills, connectors, telemetry, and change sets.",
    ),
    (
        "platform.manage",
        "Manage platform scaffolding",
        "Create and update platform scopes, workflows, connectors, and safety records.",
    ),
)

DEFAULT_ROLE_PERMISSION_KEYS: dict[str, tuple[str, ...]] = {
    "user": (
        "access.read",
        "conversations.read",
        "conversations.write",
        "media.read",
        "media.write",
        "onboarding.write",
        "plants.read",
        "tasks.read",
    ),
    "observer": (
        "access.read",
        "conversations.read",
        "logs.read",
        "media.read",
        "monitoring.read",
        "plants.read",
        "tasks.read",
    ),
    "operator": (
        "access.read",
        "conversations.read",
        "conversations.write",
        "media.read",
        "media.write",
        "onboarding.write",
        "plants.read",
        "plants.write",
        "tasks.read",
        "tasks.write",
    ),
    "automation": (
        "access.read",
        "automation.execute",
        "conversations.read",
        "monitoring.read",
        "plants.read",
        "tasks.read",
        "tasks.write",
    ),
    "service_account": (
        "access.read",
        "automation.execute",
        "logs.read",
        "monitoring.read",
        "tasks.read",
    ),
}

DEFAULT_GROUP_SPECS: tuple[dict[str, Any], ...] = (
    {
        "slug": "platform-admins",
        "name": "Platform Admins",
        "group_type": "system",
        "description": "Administrative operators for the GardenOS platform.",
        "roles": ("admin",),
    },
    {
        "slug": "garden-users",
        "name": "Garden Users",
        "group_type": "team",
        "description": "Default human user access group.",
        "roles": ("user",),
    },
    {
        "slug": "garden-operators",
        "name": "Garden Operators",
        "group_type": "team",
        "description": "Operational users with write access to garden data.",
        "roles": ("operator",),
    },
    {
        "slug": "automation-services",
        "name": "Automation Services",
        "group_type": "system",
        "description": "Machine accounts that execute automation workflows.",
        "roles": ("automation", "service_account"),
    },
    {
        "slug": "observability-services",
        "name": "Observability Services",
        "group_type": "system",
        "description": "Machine accounts that inspect telemetry and alerts.",
        "roles": ("observer", "service_account"),
    },
)

DEFAULT_SERVICE_ACCOUNT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "slug": "garden-automation",
        "name": "Garden Automation",
        "group_slug": "automation-services",
        "account_type": "automation",
        "description": "Default automation runner for scheduler and workflow tasks.",
    },
    {
        "slug": "garden-monitoring",
        "name": "Garden Monitoring",
        "group_slug": "observability-services",
        "account_type": "monitoring",
        "description": "Default telemetry and alert ingestion account.",
    },
)

SERVICE_TOKEN_PREFIX = "gsat_"


def normalize_key(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("A key is required.")
    return re.sub(r"\s+", "_", text.casefold())


def normalize_slug(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("A slug is required.")
    normalized = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    if not normalized:
        raise ValueError("A slug is required.")
    return normalized


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _first_or_none(items: list[Any]) -> Any | None:
    return items[0] if items else None


def _optional_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def ensure_permission(
    session: Session,
    *,
    key: str,
    name: str,
    description: str | None = None,
    is_system: bool = True,
) -> Permission:
    normalized_key = normalize_key(key)
    permission = session.scalar(select(Permission).where(Permission.key == normalized_key))
    if permission is None:
        permission = Permission(
            key=normalized_key,
            name=name.strip(),
            description=_optional_text(description),
            is_system=is_system,
        )
        session.add(permission)
        session.flush()
        return permission

    permission.name = name.strip()
    permission.description = _optional_text(description)
    permission.is_system = is_system
    session.add(permission)
    session.flush()
    return permission


def ensure_role(
    session: Session,
    *,
    key: str,
    name: str,
    description: str | None = None,
    is_system: bool = True,
) -> Role:
    normalized_key = normalize_key(key)
    role = session.scalar(select(Role).where(Role.key == normalized_key))
    if role is None:
        role = Role(
            key=normalized_key,
            name=name.strip(),
            description=_optional_text(description),
            is_system=is_system,
        )
        session.add(role)
        session.flush()
        return role

    role.name = name.strip()
    role.description = _optional_text(description)
    role.is_system = is_system
    session.add(role)
    session.flush()
    return role


def ensure_role_permission(session: Session, role: Role, permission: Permission) -> RolePermission:
    existing = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id,
        ),
    )
    if existing is not None:
        return existing

    link = RolePermission(role=role, permission=permission)
    session.add(link)
    session.flush()
    return link


def ensure_group(
    session: Session,
    *,
    slug: str,
    name: str,
    group_type: str = "team",
    description: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
    is_system: bool = False,
) -> Group:
    normalized_slug = normalize_slug(slug)
    group = session.scalar(select(Group).where(Group.slug == normalized_slug))
    if group is None:
        group = Group(
            slug=normalized_slug,
            name=name.strip(),
            group_type=normalize_key(group_type),
            scope_type=normalize_key(scope_type) if scope_type else None,
            scope_id=_optional_text(scope_id),
            description=_optional_text(description),
            is_system=is_system,
        )
        session.add(group)
        session.flush()
        return group

    group.name = name.strip()
    group.group_type = normalize_key(group_type)
    group.scope_type = normalize_key(scope_type) if scope_type else None
    group.scope_id = _optional_text(scope_id)
    group.description = _optional_text(description)
    group.is_system = is_system
    session.add(group)
    session.flush()
    return group


def ensure_group_membership(session: Session, group: Group, user: User) -> GroupMembership:
    existing = session.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.user_id == user.id,
        ),
    )
    if existing is not None:
        return existing

    membership = GroupMembership(group=group, user=user)
    session.add(membership)
    session.flush()
    return membership


def ensure_group_role(session: Session, group: Group, role: Role) -> GroupRole:
    existing = session.scalar(
        select(GroupRole).where(
            GroupRole.group_id == group.id,
            GroupRole.role_id == role.id,
        ),
    )
    if existing is not None:
        return existing

    link = GroupRole(group=group, role=role)
    session.add(link)
    session.flush()
    return link


def ensure_service_account(
    session: Session,
    *,
    slug: str,
    name: str,
    account_type: str = "automation",
    description: str | None = None,
    group: Group | None = None,
    created_by_user: User | None = None,
    is_system: bool = False,
    is_active: bool = True,
) -> ServiceAccount:
    normalized_slug = normalize_slug(slug)
    service_account = session.scalar(
        select(ServiceAccount).where(ServiceAccount.slug == normalized_slug),
    )
    if service_account is None:
        service_account = ServiceAccount(
            slug=normalized_slug,
            name=name.strip(),
            account_type=normalize_key(account_type),
            description=_optional_text(description),
            group=group,
            created_by_user=created_by_user,
            is_system=is_system,
            is_active=is_active,
        )
        session.add(service_account)
        session.flush()
        return service_account

    service_account.name = name.strip()
    service_account.account_type = normalize_key(account_type)
    service_account.description = _optional_text(description)
    service_account.group = group
    service_account.created_by_user = created_by_user
    service_account.is_system = is_system
    service_account.is_active = is_active
    session.add(service_account)
    session.flush()
    return service_account


def ensure_service_account_role(
    session: Session,
    service_account: ServiceAccount,
    role: Role,
) -> ServiceAccountRole:
    existing = session.scalar(
        select(ServiceAccountRole).where(
            ServiceAccountRole.service_account_id == service_account.id,
            ServiceAccountRole.role_id == role.id,
        ),
    )
    if existing is not None:
        return existing

    link = ServiceAccountRole(service_account=service_account, role=role)
    session.add(link)
    session.flush()
    return link


def issue_service_account_token(
    session: Session,
    service_account: ServiceAccount,
    *,
    label: str | None = None,
    expires_at: datetime | None = None,
) -> tuple[ServiceAccountToken, str]:
    plaintext = f"{SERVICE_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    token = ServiceAccountToken(
        service_account=service_account,
        token_prefix=plaintext[:12],
        token_hash=_token_hash(plaintext),
        label=label.strip() if isinstance(label, str) and label.strip() else None,
        expires_at=expires_at,
    )
    session.add(token)
    session.flush()
    return token, plaintext


def revoke_service_account_token(
    session: Session,
    token: ServiceAccountToken,
) -> ServiceAccountToken:
    token.revoked_at = _utc_now()
    session.add(token)
    session.flush()
    return token


def list_permissions(session: Session) -> list[Permission]:
    return list(session.scalars(select(Permission).order_by(Permission.key)).all())


def list_roles(session: Session) -> list[Role]:
    return list(session.scalars(select(Role).order_by(Role.key)).all())


def list_groups(session: Session) -> list[Group]:
    return list(session.scalars(select(Group).order_by(Group.slug)).all())


def list_service_accounts(session: Session) -> list[ServiceAccount]:
    return list(session.scalars(select(ServiceAccount).order_by(ServiceAccount.slug)).all())


def get_group(session: Session, group_id: str) -> Group | None:
    return session.get(Group, group_id)


def get_service_account(session: Session, service_account_id: str) -> ServiceAccount | None:
    return session.get(ServiceAccount, service_account_id)


def get_service_account_token(session: Session, token_id: str) -> ServiceAccountToken | None:
    return session.get(ServiceAccountToken, token_id)


def _permissions_for_role_keys(session: Session, role_keys: set[str]) -> set[str]:
    if not role_keys:
        return set()
    stmt = (
        select(Permission.key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .where(Role.key.in_(sorted(role_keys)))
    )
    return {key for key in session.scalars(stmt).all()}


def _group_role_keys(session: Session, group_ids: list[str]) -> set[str]:
    if not group_ids:
        return set()
    stmt = (
        select(Role.key)
        .join(GroupRole, GroupRole.role_id == Role.id)
        .where(GroupRole.group_id.in_(group_ids))
    )
    return {key for key in session.scalars(stmt).all()}


def _user_group_ids(session: Session, user: User) -> list[str]:
    stmt = select(GroupMembership.group_id).where(GroupMembership.user_id == user.id)
    return list(session.scalars(stmt).all())


def _service_account_group_ids(service_account: ServiceAccount) -> list[str]:
    return [service_account.group_id] if service_account.group_id else []


def _user_scope_ids(session: Session, user: User) -> list[str]:
    scope_ids = list(
        session.scalars(
            select(ScopeMembership.scope_node_id).where(ScopeMembership.user_id == user.id),
        ).all(),
    )
    scope_ids.extend(
        session.scalars(
            select(Group.scope_id)
            .join(GroupMembership, GroupMembership.group_id == Group.id)
            .where(GroupMembership.user_id == user.id, Group.scope_id.is_not(None)),
        ).all(),
    )
    return sorted({scope_id for scope_id in scope_ids if scope_id})


def resolve_user_role_keys(session: Session, user: User) -> tuple[str, ...]:
    role_keys = {"admin" if user.is_admin else "user"}
    role_keys.update(_group_role_keys(session, _user_group_ids(session, user)))
    return tuple(sorted(role_keys))


def resolve_service_account_role_keys(
    session: Session, service_account: ServiceAccount
) -> tuple[str, ...]:
    role_keys = _group_role_keys(session, _service_account_group_ids(service_account))
    role_keys.update(
        session.scalars(
            select(Role.key)
            .join(ServiceAccountRole, ServiceAccountRole.role_id == Role.id)
            .where(ServiceAccountRole.service_account_id == service_account.id),
        ).all(),
    )
    if not role_keys:
        role_keys.add("service_account")
    return tuple(sorted(role_keys))


def resolve_user_permissions(session: Session, user: User) -> tuple[str, ...]:
    if user.is_admin:
        return tuple(sorted(permission.key for permission in list_permissions(session)))
    role_keys = set(resolve_user_role_keys(session, user))
    return tuple(sorted(_permissions_for_role_keys(session, role_keys)))


def resolve_service_account_permissions(
    session: Session, service_account: ServiceAccount
) -> tuple[str, ...]:
    role_keys = set(resolve_service_account_role_keys(session, service_account))
    permissions = _permissions_for_role_keys(session, role_keys)
    return tuple(sorted(permissions))


def build_user_principal(
    session: Session,
    user: User,
    *,
    auth_method: AuthMethod = "session",
) -> PrincipalContext:
    return PrincipalContext(
        kind="user",
        id=user.id,
        label=user.full_name,
        auth_method=auth_method,
        roles=resolve_user_role_keys(session, user),
        permissions=resolve_user_permissions(session, user),
        group_ids=tuple(sorted(_user_group_ids(session, user))),
        scope_ids=tuple(_user_scope_ids(session, user)),
        username=user.username,
        is_admin=user.is_admin,
    )


def build_service_account_principal(
    session: Session,
    service_account: ServiceAccount,
    *,
    auth_method: AuthMethod = "service_token",
) -> PrincipalContext:
    group_ids = tuple(sorted(_service_account_group_ids(service_account)))
    scope_ids = (
        (service_account.group.scope_id,)
        if service_account.group is not None and service_account.group.scope_id is not None
        else ()
    )
    return PrincipalContext(
        kind="service_account",
        id=service_account.id,
        label=service_account.name,
        auth_method=auth_method,
        roles=resolve_service_account_role_keys(session, service_account),
        permissions=resolve_service_account_permissions(session, service_account),
        group_ids=group_ids,
        scope_ids=scope_ids,
        service_account_slug=service_account.slug,
    )


def serialize_permission(permission: Permission) -> dict[str, Any]:
    return {
        "id": permission.id,
        "key": permission.key,
        "name": permission.name,
        "description": permission.description,
        "is_system": permission.is_system,
        "created_at": permission.created_at.isoformat(),
        "updated_at": permission.updated_at.isoformat(),
    }


def serialize_role(role: Role) -> dict[str, Any]:
    return {
        "id": role.id,
        "key": role.key,
        "name": role.name,
        "description": role.description,
        "is_system": role.is_system,
        "permission_keys": sorted(
            role_permission.permission.key for role_permission in role.role_permissions
        ),
        "created_at": role.created_at.isoformat(),
        "updated_at": role.updated_at.isoformat(),
    }


def serialize_group(group: Group) -> dict[str, Any]:
    return {
        "id": group.id,
        "slug": group.slug,
        "name": group.name,
        "group_type": group.group_type,
        "scope_type": group.scope_type,
        "scope_id": group.scope_id,
        "description": group.description,
        "is_system": group.is_system,
        "member_count": len(group.memberships),
        "service_account_count": len(group.service_accounts),
        "role_keys": sorted(group_role.role.key for group_role in group.roles),
        "created_at": group.created_at.isoformat(),
        "updated_at": group.updated_at.isoformat(),
    }


def serialize_service_account(service_account: ServiceAccount) -> dict[str, Any]:
    return {
        "id": service_account.id,
        "slug": service_account.slug,
        "name": service_account.name,
        "account_type": service_account.account_type,
        "description": service_account.description,
        "group_id": service_account.group_id,
        "group_slug": service_account.group.slug if service_account.group else None,
        "created_by_user_id": service_account.created_by_user_id,
        "is_system": service_account.is_system,
        "is_active": service_account.is_active,
        "last_used_at": service_account.last_used_at.isoformat()
        if service_account.last_used_at
        else None,
        "role_keys": sorted(role.role.key for role in service_account.roles),
        "token_count": len(service_account.tokens),
        "created_at": service_account.created_at.isoformat(),
        "updated_at": service_account.updated_at.isoformat(),
    }


def serialize_service_account_token(token: ServiceAccountToken) -> dict[str, Any]:
    return {
        "id": token.id,
        "service_account_id": token.service_account_id,
        "token_prefix": token.token_prefix,
        "label": token.label,
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        "revoked_at": token.revoked_at.isoformat() if token.revoked_at else None,
        "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
        "created_at": token.created_at.isoformat(),
        "updated_at": token.updated_at.isoformat(),
    }


def serialize_principal(principal: PrincipalContext) -> dict[str, Any]:
    return {
        "kind": principal.kind,
        "id": principal.id,
        "label": principal.label,
        "auth_method": principal.auth_method,
        "roles": list(principal.roles),
        "permissions": list(principal.permissions),
        "group_ids": list(principal.group_ids),
        "scope_ids": list(principal.scope_ids),
        "username": principal.username,
        "service_account_slug": principal.service_account_slug,
        "is_admin": principal.is_admin,
    }


def authenticate_service_account_token(
    session: Session,
    token_value: str,
) -> ServiceAccount | None:
    normalized = token_value.strip()
    if not normalized:
        return None
    token = session.scalar(
        select(ServiceAccountToken).where(
            ServiceAccountToken.token_hash == _token_hash(normalized)
        ),
    )
    if token is None:
        return None
    if token.revoked_at is not None:
        return None
    if token.expires_at is not None and token.expires_at <= _utc_now():
        return None
    service_account = token.service_account
    if service_account is None or not service_account.is_active:
        return None
    return service_account


def ensure_default_access(
    session: Session,
    *,
    admin_user: User | None = None,
) -> dict[str, int]:
    permissions = {
        spec[0]: ensure_permission(
            session,
            key=spec[0],
            name=spec[1],
            description=spec[2],
            is_system=True,
        )
        for spec in DEFAULT_PERMISSION_SPECS
    }

    roles = {
        "admin": ensure_role(
            session,
            key="admin",
            name="Platform Admin",
            description="Full control over the GardenOS platform.",
            is_system=True,
        ),
        "user": ensure_role(
            session,
            key="user",
            name="Garden User",
            description="Baseline access for nursery users.",
            is_system=True,
        ),
        "observer": ensure_role(
            session,
            key="observer",
            name="Observer",
            description="Read-only inspection access for telemetry and garden state.",
            is_system=True,
        ),
        "operator": ensure_role(
            session,
            key="operator",
            name="Operator",
            description="Writable operational access for standard garden workflows.",
            is_system=True,
        ),
        "automation": ensure_role(
            session,
            key="automation",
            name="Automation",
            description="Workflow execution access for scheduled jobs and connectors.",
            is_system=True,
        ),
        "service_account": ensure_role(
            session,
            key="service_account",
            name="Service Account",
            description="Baseline machine identity role.",
            is_system=True,
        ),
    }

    for role_key, permission_keys in DEFAULT_ROLE_PERMISSION_KEYS.items():
        role = roles[role_key]
        for permission_key in permission_keys:
            ensure_role_permission(session, role, permissions[permission_key])

    admin_role = roles["admin"]
    for permission in permissions.values():
        ensure_role_permission(session, admin_role, permission)

    groups = {
        spec["slug"]: ensure_group(
            session,
            slug=spec["slug"],
            name=spec["name"],
            group_type=spec["group_type"],
            description=spec["description"],
            is_system=True,
        )
        for spec in DEFAULT_GROUP_SPECS
    }

    for spec in DEFAULT_GROUP_SPECS:
        group = groups[spec["slug"]]
        for role_key in spec["roles"]:
            ensure_group_role(session, group, roles[role_key])

    if admin_user is not None:
        ensure_group_membership(session, groups["platform-admins"], admin_user)

    service_accounts = {
        spec["slug"]: ensure_service_account(
            session,
            slug=spec["slug"],
            name=spec["name"],
            account_type=spec["account_type"],
            description=spec["description"],
            group=groups[spec["group_slug"]],
            is_system=True,
        )
        for spec in DEFAULT_SERVICE_ACCOUNT_SPECS
    }

    for service_account in service_accounts.values():
        ensure_service_account_role(session, service_account, roles["service_account"])
    ensure_service_account_role(session, service_accounts["garden-automation"], roles["automation"])
    ensure_service_account_role(session, service_accounts["garden-monitoring"], roles["observer"])

    summary = {
        "permissions": len(permissions),
        "roles": len(roles),
        "groups": len(groups),
        "service_accounts": len(service_accounts),
    }
    return summary
