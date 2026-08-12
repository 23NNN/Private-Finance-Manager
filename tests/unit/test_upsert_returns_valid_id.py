# tests/unit/test_upsert_returns_valid_id.py
"""Regression test for a confirmed production bug.

SessionLocal() runs with autoflush=False (src/infrastructure/db/engine.py).
Every upsert_*() service method that did `session.add(obj); return obj.id`
right after adding a brand-new object returned None instead of the real
database id, because no flush had happened yet. Fixed by flushing inside
each repository's upsert(). This test pins the fix across every affected
service so a future change cannot silently reintroduce it.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.application.dto.accounts import AccountDTO
from src.application.dto.employers import EmployerDTO, PayRuleDTO
from src.application.dto.expenses import ExpenseRecurringDTO
from src.application.dto.incomes import IncomeFixedDTO, IncomeHourlyDTO, IncomeSpecialDTO
from src.application.dto.loans import LoanDTO
from src.application.dto.savings import SavingsContributionDTO, SavingsGoalDTO
from src.application.services.account_service import AccountService
from src.application.services.employer_service import EmployerService
from src.application.services.expense_service import ExpenseService
from src.application.services.income_service import IncomeService
from src.application.services.loan_service import LoanService
from src.application.services.reference_data_service import ReferenceDataService
from src.application.services.savings_service import SavingsService
from src.infrastructure.db.engine import dispose_engine, get_engine, init_engine
from src.infrastructure.db.orm_models import Base


@pytest.fixture(autouse=True)
def _in_memory_engine():
    init_engine("sqlite:///:memory:")
    Base.metadata.create_all(get_engine())
    yield
    dispose_engine()


def _employer_id() -> int:
    return EmployerService().upsert_employer(
        EmployerDTO(id=None, name="TestCo", payout_timing="BEGINNING", default_account_id=None, notes=None)
    )


def _account_id() -> int:
    return AccountService().upsert_account(
        AccountDTO(
            id=None, account_name="Giro", label="GIRO", bank_name="Bank", iban=None,
            role_income=True, role_debit=True, notes=None,
        )
    )


def test_employer_upsert_returns_valid_id():
    assert _employer_id() is not None


def test_pay_rule_upsert_returns_valid_id():
    emp_id = _employer_id()
    rule_id = EmployerService().upsert_pay_rule(
        PayRuleDTO(
            id=None, employer_id=emp_id, rule_type="HOURLY_WAGE", unit="EUR_PER_HOUR",
            value=Decimal("20.00"), valid_from=date(2026, 1, 1), valid_to=None,
        )
    )
    assert rule_id is not None


def test_account_upsert_returns_valid_id():
    assert _account_id() is not None


def test_loan_upsert_returns_valid_id():
    account_id = _account_id()
    loan_id = LoanService().upsert_loan(
        LoanDTO(
            id=None, name="Testloan", start_date=date(2026, 1, 1), principal_initial=Decimal("1000"),
            annual_interest_rate=Decimal("0"), regular_payment=Decimal("100"), payment_timing="BEGINNING",
            account_id=account_id, status="ACTIVE", notes=None,
        )
    )
    assert loan_id is not None


def test_income_fixed_upsert_returns_valid_id():
    emp_id = _employer_id()
    fixed_id = IncomeService().upsert_fixed(
        IncomeFixedDTO(
            id=None, employer_id=emp_id, year=2026, month=1,
            base_amount=Decimal("100"), special_amount=Decimal("0"),
            calc_amount=Decimal("0"), actual_amount=Decimal("0"),
        )
    )
    assert fixed_id is not None


def test_income_hourly_upsert_returns_valid_id():
    emp_id = _employer_id()
    hourly_id = IncomeService().upsert_hourly(
        IncomeHourlyDTO(
            id=None, employer_id=emp_id, year=2026, month=1,
            hours_bw=Decimal("0"), hours_by=Decimal("0"), hours_normal=Decimal("10"),
            night_bw=Decimal("0"), sunday_bw=Decimal("0"), night_by=Decimal("0"), sunday_by=Decimal("0"),
            night=Decimal("0"), sunday=Decimal("0"), holiday=Decimal("0"), overtime=Decimal("0"),
            special_amount=Decimal("0"), calc_amount=Decimal("0"), actual_amount=Decimal("0"),
        )
    )
    assert hourly_id is not None


def test_income_special_upsert_returns_valid_id():
    special_id = IncomeService().upsert_special(
        IncomeSpecialDTO(
            id=None, year=2026, month=1, name="Bonus", amount=Decimal("500"), actual_amount=Decimal("0"),
        )
    )
    assert special_id is not None


def test_savings_goal_upsert_returns_valid_id():
    goal_id = SavingsService().upsert_goal(
        SavingsGoalDTO(id=None, name="Notgroschen", type="EMERGENCY", linked_to_source=False, notes=None)
    )
    assert goal_id is not None


def test_savings_contribution_upsert_returns_valid_id():
    goal_id = SavingsService().upsert_goal(
        SavingsGoalDTO(id=None, name="Notgroschen", type="EMERGENCY", linked_to_source=False, notes=None)
    )
    contrib_id = SavingsService().add_contribution(
        SavingsContributionDTO(
            id=None, goal_id=goal_id, year=2026, month=1, amount=Decimal("50"), account_id=None, notes=None
        )
    )
    assert contrib_id is not None


def test_expense_category_upsert_returns_valid_id():
    category_id = ReferenceDataService().upsert_category("Freizeit", "VARIABLE")
    assert category_id is not None


def test_expense_recurring_upsert_returns_valid_id():
    category_id = ReferenceDataService().upsert_category("Miete", "FIX")
    account_id = _account_id()
    recurring_id = ExpenseService().upsert_recurring(
        ExpenseRecurringDTO(
            id=None, name="Miete", category_id=category_id, amount=Decimal("800"),
            frequency_months=1, due_day=1, anchor_month=None, status="ACTIVE",
            account_id=account_id, pay_bucket="NONE", notes=None, allocation_override=None,
        )
    )
    assert recurring_id is not None
