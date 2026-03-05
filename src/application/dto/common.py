from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PeriodDTO:
    year: int
    month: int


@dataclass(frozen=True)
class MoneyDTO:
    amount: Decimal
