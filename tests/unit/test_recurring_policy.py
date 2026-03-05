from decimal import Decimal
from src.domain.models.period import Period
from src.domain.policies.recurring_policy import allocated_amount, is_due_in_period, ViewMode


def test_due_quarterly_anchor_month():
    assert is_due_in_period(Period(2026, 1), 3, 1) is True
    assert is_due_in_period(Period(2026, 2), 3, 1) is False
    assert is_due_in_period(Period(2026, 4), 3, 1) is True


def test_allocated_cashflow():
    amt = allocated_amount(
        amount=Decimal("120.00"),
        frequency_months=3,
        period=Period(2026, 2),
        anchor_month=1,
        global_view_mode=ViewMode.CASHFLOW,
        override=None,
    )
    assert amt == Decimal("0.00")

    amt2 = allocated_amount(
        amount=Decimal("120.00"),
        frequency_months=3,
        period=Period(2026, 4),
        anchor_month=1,
        global_view_mode=ViewMode.CASHFLOW,
        override=None,
    )
    assert amt2 == Decimal("120.00")


def test_allocated_budget_month():
    amt = allocated_amount(
        amount=Decimal("120.00"),
        frequency_months=3,
        period=Period(2026, 2),
        anchor_month=1,
        global_view_mode=ViewMode.BUDGET_MONTH,
        override=None,
    )
    assert amt == Decimal("40.00")
