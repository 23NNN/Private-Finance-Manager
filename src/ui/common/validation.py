# finanzmanager/ui/common/validation.py
from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.application.validators.parsers import parse_date, parse_decimal, parse_int, parse_month


def ui_decimal(s: str, default: Decimal | None = None) -> Decimal:
    return parse_decimal(s, default=default)


def ui_int(s: str, min_v: int | None = None, max_v: int | None = None) -> int:
    return parse_int(s, min_value=min_v, max_value=max_v)


def ui_month(s: str) -> int:
    return parse_month(s)


def ui_date(s: str, default: date | None = None) -> date:
    return parse_date(s, default=default)
