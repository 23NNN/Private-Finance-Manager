# finanzmanager/domain/policies/loan_policy.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class LoanMonthStatus:
    open_before: Decimal
    payment: Decimal
    extra: Decimal
    open_after: Decimal


def _r2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_month_status(
    *,
    principal_initial: Decimal,
    regular_payment: Decimal,
    events: list[dict],
    year: int,
    month: int,
) -> LoanMonthStatus:
    """
    Apply payment, refinancing and interest events to compute remaining balance.

    - PAYMENT / EXTRA_PAYMENT: reduce principal
    - REFINANCING: increase principal (new money borrowed)
    - INTEREST: increase principal (accrued interest added to debt)
    - CORRECTION: adjust principal by signed amount (positive=increase, negative=decrease)
    - RATE_CHANGE: update regular_payment for future PAYMENT events
    """
    principal = principal_initial
    current_payment = regular_payment

    payment_this = Decimal("0.00")
    extra_this = Decimal("0.00")

    for e in events:
        et = e["event_type"]
        ey = e["year"]
        em = e["month"]

        if et == "RATE_CHANGE" and e.get("new_regular_payment") is not None:
            current_payment = e["new_regular_payment"]

        if et in {"PAYMENT", "EXTRA_PAYMENT"}:
            amt = e.get("amount")
            if amt is None and et == "PAYMENT":
                amt = current_payment
            if amt is None:
                continue

            if (ey < year) or (ey == year and em < month):
                principal -= amt
            elif ey == year and em == month:
                principal -= amt
                if et == "PAYMENT":
                    payment_this += amt
                else:
                    extra_this += amt

        elif et in {"REFINANCING", "INTEREST", "CORRECTION"}:
            amt = e.get("amount")
            if amt is None:
                continue
            if (ey < year) or (ey == year and em <= month):
                principal += amt

    open_before = _r2(principal + payment_this + extra_this)
    open_after = _r2(open_before - payment_this - extra_this)
    return LoanMonthStatus(_r2(open_before), _r2(payment_this), _r2(extra_this), _r2(open_after))
