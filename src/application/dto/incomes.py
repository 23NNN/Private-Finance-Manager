# src/application/dto/incomes.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class IncomeFixedDTO:
    id: int | None
    employer_id: int
    year: int
    month: int
    base_amount: Decimal
    special_amount: Decimal
    calc_amount: Decimal
    actual_amount: Decimal
    payout_timing: str = "MID"
    account_id: int | None = None
    notes: str | None = None


@dataclass(frozen=True)
class IncomeHourlyDTO:
    id: int | None
    employer_id: int
    year: int
    month: int

    hours_bw: Decimal
    hours_by: Decimal
    hours_normal: Decimal
    night_bw: Decimal
    sunday_bw: Decimal
    night_by: Decimal
    sunday_by: Decimal
    night: Decimal
    sunday: Decimal
    holiday: Decimal
    overtime: Decimal

    special_amount: Decimal
    calc_amount: Decimal
    actual_amount: Decimal
    payout_timing: str = "MID"
    account_id: int | None = None
    notes: str | None = None


@dataclass(frozen=True)
class IncomeSpecialDTO:
    """Special income (without employer).

    amount: planned amount
    actual_amount: actual (optional, 0.00 if unknown)
    payout_timing: BEGINNING/MID
    """

    id: int | None
    year: int
    month: int
    name: str
    amount: Decimal
    actual_amount: Decimal
    payout_timing: str = "MID"
    account_id: int | None = None
    notes: str | None = None
