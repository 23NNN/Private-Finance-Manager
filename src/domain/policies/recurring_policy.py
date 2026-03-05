# finanzmanager/domain/policies/recurring_policy.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from src.domain.models.period import Period


class ViewMode(str):
    CASHFLOW = "CASHFLOW"
    BUDGET_MONTH = "BUDGET_MONTH"
    BUDGET_QUARTER = "BUDGET_QUARTER"


@dataclass(frozen=True)
class RecurringAllocation:
    monthly_budget: Decimal
    quarterly_budget: Decimal
    annualized: Decimal

    @staticmethod
    def from_amount(amount: Decimal, frequency_months: int) -> "RecurringAllocation":
        monthly = (amount / Decimal(frequency_months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        quarterly = (monthly * Decimal(3)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        annualized = (monthly * Decimal(12)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return RecurringAllocation(monthly, quarterly, annualized)


def is_due_in_period(period: Period, frequency_months: int, anchor_month: int | None) -> bool:
    if frequency_months == 1:
        return True
    if anchor_month is None:
        anchor_month = 1
    # months are 1..12
    diff = (period.month - anchor_month) % 12
    return diff % frequency_months == 0


def allocated_amount(
    *,
    amount: Decimal,
    frequency_months: int,
    period: Period,
    anchor_month: int | None,
    global_view_mode: str,
    override: str | None,
) -> Decimal:
    """
    Returns the amount counted for that period depending on CASHFLOW/BUDGET modes and override.
    """
    eff = override or global_view_mode
    alloc = RecurringAllocation.from_amount(amount, frequency_months)

    if eff == ViewMode.CASHFLOW:
        return amount if is_due_in_period(period, frequency_months, anchor_month) else Decimal("0.00")
    if eff == ViewMode.BUDGET_QUARTER:
        return alloc.quarterly_budget
    # default: BUDGET_MONTH
    return alloc.monthly_budget
