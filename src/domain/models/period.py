# finanzmanager/domain/models/period.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Period:
    year: int
    month: int  # 1..12

    def __post_init__(self) -> None:
        if not (1 <= self.month <= 12):
            raise ValueError("month must be 1..12")

    def next_month(self) -> "Period":
        if self.month == 12:
            return Period(self.year + 1, 1)
        return Period(self.year, self.month + 1)

    def to_key(self) -> tuple[int, int]:
        return (self.year, self.month)
