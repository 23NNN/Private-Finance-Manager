from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from src.application.validators.parsers import parse_decimal, parse_int, parse_month, safe_bool, safe_str

logger = logging.getLogger(__name__)


def pick(row: dict[str, Any], keys: list[str]) -> Any:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def as_decimal(row: dict[str, Any], keys: list[str], default: Decimal = Decimal("0")) -> Decimal:
    v = pick(row, keys)
    try:
        return parse_decimal(v, default=default)
    except Exception:
        return default


def as_int(row: dict[str, Any], keys: list[str], default: int | None = None, *, min_v=None, max_v=None) -> int | None:
    v = pick(row, keys)
    if v in (None, ""):
        return default
    try:
        return parse_int(v, min_value=min_v, max_value=max_v)
    except Exception:
        return default


def as_bool(row: dict[str, Any], keys: list[str]) -> bool:
    return safe_bool(pick(row, keys))


def as_str(row: dict[str, Any], keys: list[str], default: str = "") -> str:
    v = pick(row, keys)
    s = safe_str(v)
    return s if s else default


def as_month(row: dict[str, Any], keys: list[str], default: int | None = None) -> int | None:
    v = pick(row, keys)
    if v in (None, ""):
        return default
    try:
        return parse_month(v)
    except Exception:
        return default
