from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.sql.type_api import TypeEngine


def ci_text(length: int | None = None) -> TypeEngine[Any]:
    return String(length).with_variant(CITEXT(), "postgresql")


def jsonb_type() -> TypeEngine[Any]:
    return JSON().with_variant(JSONB(), "postgresql")
