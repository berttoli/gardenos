from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def parse_date(value: Any) -> date | None:
    text = optional_str(value)
    if text is None:
        return None
    return date.fromisoformat(text)


def parse_datetime(value: Any) -> datetime | None:
    text = optional_str(value)
    if text is None:
        return None
    return datetime.fromisoformat(text)


def parse_decimal(value: Any) -> Decimal | None:
    text = optional_str(value)
    if text is None:
        return None
    return Decimal(text)


def parse_int(value: Any) -> int | None:
    text = optional_str(value)
    if text is None:
        return None
    return int(text)


def payload_from_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}
