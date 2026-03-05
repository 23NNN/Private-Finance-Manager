# src/application/dto/savings.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class SavingsGoalDTO:
    id: int | None
    name: str
    type: str
    linked_to_source: bool
    notes: str | None


@dataclass(frozen=True)
class SavingsContributionDTO:
    id: int | None
    goal_id: int
    year: int
    month: int
    amount: Decimal
    account_id: int | None
    notes: str | None


@dataclass(frozen=True)
class SavingsRuleDTO:
    """Savings rate per employer with validity window.

    percentage:
      - Minimum 0.10 (10%)
      - Maximum 0.35 (35%)
    """

    id: int | None
    employer_id: int
    percentage: Decimal
    valid_from: date | None = None
    valid_to: date | None = None
    goal_id: int | None = None
