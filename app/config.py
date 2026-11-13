from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    return int(str(value).strip())


def _split_csv(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = str(value).split(",")
    normalized = tuple(part.strip() for part in items if str(part).strip())
    return normalized


def _get(mapping: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in mapping:
            value = mapping[name]
            if value is not None and str(value).strip() != "":
                return value.strip() if isinstance(value, str) else value
    return default


class Settings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    app_name: str = Field(default="Garden OS", min_length=1)
    environment: Literal["development", "test", "production"] = "development"
    secret_key: str = Field(min_length=16, repr=False)
    database_url: str = Field(min_length=1, repr=False)
    admin_username: str = Field(default="admin", min_length=1)
    admin_password: str = Field(min_length=8, repr=False)
    admin_full_name: str = Field(default="Garden Administrator", min_length=1)
    admin_email: str | None = None
    session_cookie_name: str = Field(default="garden_os_session", min_length=1)
    session_same_site: Literal["lax", "strict", "none"] = "lax"
    session_https_only: bool = False
    session_max_age_seconds: int = Field(default=60 * 60 * 24 * 14, ge=60)
    csrf_session_key: str = Field(default="_csrf_token", min_length=1)
    cors_allow_origins: tuple[str, ...] = ()
    trusted_hosts: tuple[str, ...] = ()
    login_rate_limit_attempts: int = Field(default=5, ge=1)
    login_rate_limit_window_seconds: int = Field(default=300, ge=1)
    plant_identifier_sequence_width: int = Field(default=3, ge=1, le=6)
    media_root: str = Field(default="media", min_length=1)
    backup_root: str = Field(default="backups", min_length=1)
    warehouse_db_path: str = Field(default="warehouse/garden-os-warehouse.duckdb", min_length=1)
    assistant_service_url: str = Field(default="http://assistant:8080", min_length=1)
    database_echo: bool = False

    @model_validator(mode="after")
    def _validate_production_settings(self) -> Settings:
        if self.environment == "production":
            if not self.database_url.startswith("postgresql"):
                raise ValueError("DATABASE_URL must point to PostgreSQL in production.")
            if any("*" in host for host in self.trusted_hosts):
                raise ValueError("TRUSTED_HOSTS must list exact hosts in production.")
        return self

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> Settings:
        data = {
            "app_name": _get(mapping, "APP_NAME", "app_name", default="Garden OS"),
            "environment": _get(mapping, "ENVIRONMENT", "environment", default="development"),
            "secret_key": _get(mapping, "SECRET_KEY", "secret_key"),
            "database_url": _get(mapping, "DATABASE_URL", "database_url"),
            "admin_username": _get(mapping, "ADMIN_USERNAME", "admin_username", default="admin"),
            "admin_password": _get(
                mapping,
                "ADMIN_PASSWORD",
                "admin_password",
            ),
            "admin_full_name": _get(
                mapping,
                "ADMIN_FULL_NAME",
                "admin_full_name",
                default="Garden Administrator",
            ),
            "admin_email": _get(mapping, "ADMIN_EMAIL", "admin_email"),
            "session_cookie_name": _get(
                mapping,
                "SESSION_COOKIE_NAME",
                "session_cookie_name",
                default="garden_os_session",
            ),
            "session_same_site": _get(
                mapping,
                "SESSION_COOKIE_SAMESITE",
                "session_same_site",
                default="lax",
            ),
            "session_https_only": _coerce_bool(
                _get(mapping, "SESSION_COOKIE_SECURE", "session_https_only", default=False),
            ),
            "session_max_age_seconds": _coerce_int(
                _get(
                    mapping,
                    "SESSION_MAX_AGE_SECONDS",
                    "session_max_age_seconds",
                    default=60 * 60 * 24 * 14,
                ),
                60 * 60 * 24 * 14,
            ),
            "csrf_session_key": _get(
                mapping,
                "CSRF_SESSION_KEY",
                "csrf_session_key",
                default="_csrf_token",
            ),
            "cors_allow_origins": _split_csv(
                _get(mapping, "CORS_ALLOW_ORIGINS", "cors_allow_origins", default=""),
            ),
            "trusted_hosts": _split_csv(
                _get(
                    mapping,
                    "TRUSTED_HOSTS",
                    "trusted_hosts",
                    default="localhost,127.0.0.1,[::1],testserver,app,frontend",
                ),
            ),
            "login_rate_limit_attempts": _coerce_int(
                _get(
                    mapping,
                    "LOGIN_RATE_LIMIT_ATTEMPTS",
                    "login_rate_limit_attempts",
                    default=5,
                ),
                5,
            ),
            "login_rate_limit_window_seconds": _coerce_int(
                _get(
                    mapping,
                    "LOGIN_RATE_LIMIT_WINDOW_SECONDS",
                    "login_rate_limit_window_seconds",
                    default=300,
                ),
                300,
            ),
            "plant_identifier_sequence_width": _coerce_int(
                _get(
                    mapping,
                    "PLANT_IDENTIFIER_SEQUENCE_WIDTH",
                    "plant_identifier_sequence_width",
                    default=3,
                ),
                3,
            ),
            "media_root": _get(mapping, "MEDIA_ROOT", "media_root", default="media"),
            "backup_root": _get(mapping, "BACKUP_ROOT", "backup_root", default="backups"),
            "warehouse_db_path": _get(
                mapping,
                "WAREHOUSE_DB_PATH",
                "warehouse_db_path",
                default="warehouse/garden-os-warehouse.duckdb",
            ),
            "assistant_service_url": _get(
                mapping,
                "ASSISTANT_SERVICE_URL",
                "assistant_service_url",
                default="http://assistant:8080",
            ),
            "database_echo": _coerce_bool(
                _get(mapping, "DATABASE_ECHO", "database_echo", default=False),
            ),
        }
        return cls.model_validate(data)


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings.from_mapping(cast(Mapping[str, Any], os.environ))
