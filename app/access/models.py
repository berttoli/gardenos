from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.common.pg import ci_text
from app.database import Base


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    key: Mapped[str] = mapped_column(ci_text(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role_permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="permission",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Permission(id={self.id!r}, key={self.key!r})"


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    key: Mapped[str] = mapped_column(ci_text(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role_permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    group_roles: Mapped[list[GroupRole]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    service_account_roles: Mapped[list[ServiceAccountRole]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Role(id={self.id!r}, key={self.key!r})"


class RolePermission(TimestampMixin, Base):
    __tablename__ = "role_permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[str] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[Role] = relationship(back_populates="role_permissions")
    permission: Mapped[Permission] = relationship(back_populates="role_permissions")

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )

    def __repr__(self) -> str:
        return f"RolePermission(role_id={self.role_id!r}, permission_id={self.permission_id!r})"


class Group(TimestampMixin, Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    slug: Mapped[str] = mapped_column(ci_text(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    group_type: Mapped[str] = mapped_column(String(32), nullable=False, default="team")
    scope_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    memberships: Mapped[list[GroupMembership]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    roles: Mapped[list[GroupRole]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    service_accounts: Mapped[list[ServiceAccount]] = relationship(back_populates="group")

    def __repr__(self) -> str:
        return f"Group(id={self.id!r}, slug={self.slug!r})"


class GroupMembership(TimestampMixin, Base):
    __tablename__ = "group_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    group_id: Mapped[str] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    group: Mapped[Group] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_memberships_group_user"),
    )

    def __repr__(self) -> str:
        return f"GroupMembership(group_id={self.group_id!r}, user_id={self.user_id!r})"


class GroupRole(TimestampMixin, Base):
    __tablename__ = "group_roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    group_id: Mapped[str] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )

    group: Mapped[Group] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship(back_populates="group_roles")

    __table_args__ = (UniqueConstraint("group_id", "role_id", name="uq_group_roles_group_role"),)

    def __repr__(self) -> str:
        return f"GroupRole(group_id={self.group_id!r}, role_id={self.role_id!r})"


class ServiceAccount(TimestampMixin, Base):
    __tablename__ = "service_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    slug: Mapped[str] = mapped_column(ci_text(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False, default="automation")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_id: Mapped[str | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group: Mapped[Group | None] = relationship(back_populates="service_accounts")
    created_by_user: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
    roles: Mapped[list[ServiceAccountRole]] = relationship(
        back_populates="service_account",
        cascade="all, delete-orphan",
    )
    tokens: Mapped[list[ServiceAccountToken]] = relationship(
        back_populates="service_account",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"ServiceAccount(id={self.id!r}, slug={self.slug!r})"


class ServiceAccountRole(TimestampMixin, Base):
    __tablename__ = "service_account_roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    service_account_id: Mapped[str] = mapped_column(
        ForeignKey("service_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    service_account: Mapped[ServiceAccount] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship(back_populates="service_account_roles")

    __table_args__ = (
        UniqueConstraint(
            "service_account_id",
            "role_id",
            name="uq_service_account_roles_service_account_role",
        ),
    )

    def __repr__(self) -> str:
        return (
            "ServiceAccountRole("
            f"service_account_id={self.service_account_id!r}, role_id={self.role_id!r})"
        )


class ServiceAccountToken(TimestampMixin, Base):
    __tablename__ = "service_account_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    service_account_id: Mapped[str] = mapped_column(
        ForeignKey("service_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    service_account: Mapped[ServiceAccount] = relationship(back_populates="tokens")

    def __repr__(self) -> str:
        return (
            f"ServiceAccountToken(id={self.id!r}, service_account_id={self.service_account_id!r})"
        )
