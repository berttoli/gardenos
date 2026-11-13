from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast


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


def _get(mapping: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in mapping:
            value = mapping[name]
            if value is not None and str(value).strip() != "":
                return value.strip() if isinstance(value, str) else value
    return default


@dataclass(frozen=True, slots=True)
class LiteSettings:
    app_name: str = "Garden OS"
    environment: str = "development"
    database_path: Path = Path("./garden-os.duckdb")
    media_root: Path = Path("./media")
    backup_root: Path = Path("./backups")
    seed_on_startup: bool = True
    api_token: str | None = None

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> LiteSettings:
        return cls(
            app_name=str(_get(mapping, "APP_NAME", "app_name", default="Garden OS")),
            environment=str(_get(mapping, "ENVIRONMENT", "environment", default="development")),
            database_path=Path(
                str(
                    _get(
                        mapping,
                        "GARDEN_DB_PATH",
                        "DATABASE_PATH",
                        "duckdb_path",
                        default="./garden-os.duckdb",
                    ),
                ),
            ).expanduser(),
            media_root=Path(
                str(_get(mapping, "MEDIA_ROOT", "media_root", default="media")),
            ).expanduser(),
            backup_root=Path(
                str(_get(mapping, "BACKUP_ROOT", "backup_root", default="backups")),
            ).expanduser(),
            seed_on_startup=_coerce_bool(
                _get(mapping, "SEED_ON_STARTUP", "seed_on_startup", default=True),
                default=True,
            ),
            api_token=cast(str | None, _get(mapping, "API_TOKEN", "api_token")),
        )


@lru_cache(maxsize=1)
def load_lite_settings() -> LiteSettings:
    return LiteSettings.from_mapping(cast(Mapping[str, Any], os.environ))
