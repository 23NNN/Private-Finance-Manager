from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ExpenseCategoryDTO:
    id: int | None
    name: str
    group: str


@dataclass(frozen=True)
class ExpenseRecurringDTO:
    id: int | None
    name: str
    category_id: int
    amount: Decimal
    frequency_months: int
    due_day: int
    anchor_month: int | None
    status: str
    account_id: int
    pay_bucket: str
    notes: str | None
    allocation_override: str | None


@dataclass(frozen=True)
class ExpenseVariableDTO:
    id: int | None
    name: str
    category_id: int
    amount: Decimal
    year: int
    month: int
    status: str
    account_id: int | None
    pay_bucket: str
    notes: str | None
