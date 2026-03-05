# finanzmanager/application/dto/employers.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass(slots=True)
class EmployerDTO:
    id: Optional[int]
    name: str
    payout_timing: str  # "BEGINNING" | "MID"
    default_account_id: Optional[int]
    notes: Optional[str] = None


@dataclass(slots=True)
class PayRuleDTO:
    """
    PayRule with optional validity window.

    valid_from/valid_to:
      - If both are None -> treated as always valid (legacy).
      - If valid_to is None -> valid indefinitely from valid_from.
      - If valid_from is None -> treated as 1900-01-01.
    """
    id: Optional[int]
    employer_id: int
    rule_type: str       # stored enum value (e.g. HOURLY_WAGE, NIGHT, ...)
    unit: str            # EUR_PER_HOUR | EUR_PER_MONTH | MULTIPLIER
    value: Decimal
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    notes: Optional[str] = None
