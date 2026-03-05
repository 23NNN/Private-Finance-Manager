# finanzmanager/application/validators/parsers.py
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

__all__ = [
    "safe_str",
    "safe_bool",
    "parse_bool",
    "parse_int",
    "parse_decimal",
    "parse_date",
    "parse_month",
]

_MONTHS = {
    # German
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
    "maerz": 3,
    "marz": 3,
    "mär": 3,
    "mrz": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
    # English (optional)
    "january": 1,
    "jan.": 1,
    "february": 2,
    "feb.": 2,
    "march": 3,
    "mar": 3,
    "mar.": 3,
    "april": 4,
    "apr.": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_DEC_CLEAN_RE = re.compile(r"[^\d,.\-]")


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = safe_str(value).lower()
    if s in {"1", "true", "t", "yes", "y", "ja", "j"}:
        return True
    if s in {"0", "false", "f", "no", "n", "nein"}:
        return False
    return default


def safe_bool(value: Any, default: bool = False) -> bool:
    return parse_bool(value, default=default)


def parse_int(
    value: Any,
    min_value: int | None = None,
    max_value: int | None = None,
    default: int | None = None,
) -> int:
    if value is None or safe_str(value) == "":
        if default is None:
            raise ValueError("Missing int value")
        return default

    try:
        i = int(Decimal(str(value)))
    except Exception as e:
        raise ValueError(f"Invalid int: {value}") from e

    if min_value is not None and i < min_value:
        raise ValueError(f"Int too small: {i} < {min_value}")
    if max_value is not None and i > max_value:
        raise ValueError(f"Int too large: {i} > {max_value}")
    return i


def parse_decimal(value: Any, default: Decimal | None = None) -> Decimal:
    if value is None or safe_str(value) == "":
        if default is None:
            raise ValueError("Missing decimal value")
        return default

    s = _DEC_CLEAN_RE.sub("", safe_str(value))
    # DE: "1.234,56" -> "1234.56"
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")

    try:
        return Decimal(s)
    except InvalidOperation as e:
        if default is not None:
            return default
        raise ValueError(f"Invalid decimal: {value}") from e


def parse_date(value: Any, default: date | None = None) -> date:
    if value is None or safe_str(value) == "":
        if default is None:
            raise ValueError("Missing date value")
        return default

    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    s = safe_str(value)

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    raise ValueError(f"Invalid date: {value}")


def parse_month(value: Any, default: int | None = None) -> int:
    if value is None or safe_str(value) == "":
        if default is None:
            raise ValueError("Missing month value")
        return default

    if isinstance(value, (int, float, Decimal)):
        m = int(value)
        if 1 <= m <= 12:
            return m
        raise ValueError(f"Invalid month: {value}")

    s = safe_str(value).lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = s.replace(".", "").strip()

    if s.isdigit():
        m = int(s)
        if 1 <= m <= 12:
            return m
        raise ValueError(f"Invalid month: {value}")

    m = _MONTHS.get(s)
    if m is None:
        raise ValueError(f"Unknown month: {value}")
    return m
