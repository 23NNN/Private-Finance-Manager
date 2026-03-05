# src/application/dto/overview.py
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class EmployerIncomeLineVM:
    employer_id: int
    employer_name: str
    calc_amount: Decimal
    actual_amount: Decimal
    savings_amount: Decimal


@dataclass(frozen=True)
class AccountExpenseLineVM:
    account_id: int
    account_label: str
    fix_amount: Decimal
    variable_amount: Decimal
    fix_share_pct: Decimal
    variable_share_pct: Decimal


@dataclass(frozen=True)
class LoanMonthLineVM:
    loan_id: int
    loan_name: str
    open_before: Decimal
    payment: Decimal
    extra: Decimal
    open_after: Decimal


@dataclass(frozen=True)
class PayoutSummaryLineVM:
    """Summary per payout timing (beginning/mid)."""

    payout_timing: str  # "BEGINNING" | "MID"
    total_income: Decimal
    savings: Decimal
    debts: Decimal
    fix_costs: Decimal
    free_available: Decimal


@dataclass(frozen=True)
class PeriodOverviewVM:
    year: int
    month: int
    incomes: list[EmployerIncomeLineVM]
    savings_total: Decimal
    accounts: list[AccountExpenseLineVM]
    loans: list[LoanMonthLineVM]
    recurring_abos: Decimal
    recurring_insurance: Decimal
    recurring_other_fix: Decimal
    variable_total: Decimal
    payout_summary: list[PayoutSummaryLineVM] = field(default_factory=list)


@dataclass(frozen=True, init=False)
class OverviewVM:
    """
    Contract:
    - Primary attribute is `next`.
    - Backwards compatible alias: `nxt`.
    - `view_mode` has a safe default to prevent runtime crashes if a call forgets it.
    """

    view_mode: str
    current: PeriodOverviewVM
    next: PeriodOverviewVM

    def __init__(
        self,
        *,
        current: PeriodOverviewVM,
        next: PeriodOverviewVM | None = None,
        nxt: PeriodOverviewVM | None = None,
        view_mode: str = "CASHFLOW",
    ) -> None:
        if next is None and nxt is None:
            raise TypeError("OverviewVM requires `next` or `nxt`.")
        if next is not None and nxt is not None:
            raise TypeError("OverviewVM: please pass only one of `next` or `nxt`.")
        object.__setattr__(self, "view_mode", view_mode)
        object.__setattr__(self, "current", current)
        object.__setattr__(self, "next", next if next is not None else nxt)

    @property
    def nxt(self) -> PeriodOverviewVM:
        return self.next
