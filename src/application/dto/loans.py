# finanzmanager/application/dto/loans.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class LoanDTO:
    id: int | None
    name: str
    start_date: date
    principal_initial: Decimal
    annual_interest_rate: Decimal
    regular_payment: Decimal
    payment_timing: str
    account_id: int
    status: str
    notes: str | None


@dataclass(frozen=True)
class LoanEventDTO:
    id: int | None
    loan_id: int
    event_date: date
    event_type: str
    amount: Decimal | None
    new_regular_payment: Decimal | None
    new_annual_interest_rate: Decimal | None
    notes: str | None

    # MVP: settings overrides are stored as markers in notes (dedicated DB columns possible later)
    override_account_id: int | None = None
    override_payment_timing: str | None = None
