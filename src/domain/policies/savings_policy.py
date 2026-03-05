# finanzmanager/domain/policies/savings_policy.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class SavingsResult:
    employer_id: int
    employer_name: str
    income_calc: Decimal
    savings_amount: Decimal


def calc_savings_per_employer(incomes: list[tuple[int, str, Decimal]], percentage: Decimal) -> list[SavingsResult]:
    """
    incomes: list of (employer_id, employer_name, calc_income)
    """
    results: list[SavingsResult] = []
    for emp_id, emp_name, calc_income in incomes:
        amt = (calc_income * percentage).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        results.append(SavingsResult(emp_id, emp_name, calc_income, amt))
    return results
