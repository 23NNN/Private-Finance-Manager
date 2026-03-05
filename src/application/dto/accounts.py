from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountDTO:
    id: int | None
    bank_name: str | None
    account_name: str
    label: str
    iban: str | None
    role_income: bool
    role_debit: bool
    notes: str | None
