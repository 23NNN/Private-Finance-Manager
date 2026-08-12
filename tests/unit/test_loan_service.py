# tests/unit/test_loan_service.py
"""Unit tests for LoanService (month status calc, settings-override round trip)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.application.dto.loans import LoanDTO, LoanEventDTO
from src.application.services.loan_service import LoanService
from src.domain.models.period import Period
from src.infrastructure.db.engine import dispose_engine, get_engine, init_engine
from src.infrastructure.db.orm_models import Base


@pytest.fixture(autouse=True)
def _in_memory_engine():
    init_engine("sqlite:///:memory:")
    Base.metadata.create_all(get_engine())
    yield
    dispose_engine()


def _loan_dto(**overrides) -> LoanDTO:
    base = dict(
        id=None,
        name="Testloan",
        start_date=date(2026, 1, 1),
        principal_initial=Decimal("1000.00"),
        annual_interest_rate=Decimal("0"),
        regular_payment=Decimal("100.00"),
        payment_timing="BEGINNING",
        account_id=1,
        status="ACTIVE",
        notes=None,
    )
    base.update(overrides)
    return LoanDTO(**base)


def test_upsert_loan_and_get_month_status_reflects_payment_event():
    svc = LoanService()
    loan_id = svc.upsert_loan(_loan_dto())

    svc.upsert_event(
        LoanEventDTO(
            id=None, loan_id=loan_id, event_date=date(2026, 1, 1), event_type="PAYMENT",
            amount=Decimal("100.00"), new_regular_payment=None, new_annual_interest_rate=None, notes=None,
        )
    )

    status = svc.get_month_status(loan_id, Period(2026, 1))
    assert status["open_before"] == Decimal("1000.00")
    assert status["payment"] == Decimal("100.00")
    assert status["open_after"] == Decimal("900.00")


def test_get_month_status_for_unknown_loan_returns_zero_status():
    svc = LoanService()
    status = svc.get_month_status(999999, Period(2026, 1))
    assert status == {
        "open_before": Decimal("0"),
        "payment": Decimal("0"),
        "extra": Decimal("0"),
        "open_after": Decimal("0"),
    }


def test_get_effective_settings_applies_event_override():
    svc = LoanService()
    loan_id = svc.upsert_loan(_loan_dto(account_id=1, payment_timing="BEGINNING"))

    svc.upsert_event(
        LoanEventDTO(
            id=None, loan_id=loan_id, event_date=date(2026, 3, 1), event_type="NOTE",
            amount=None, new_regular_payment=None, new_annual_interest_rate=None,
            notes="Umgezogen", override_account_id=7, override_payment_timing="MID",
        )
    )

    settings = svc.get_effective_settings(loan_id, Period(2026, 3))
    assert settings == {"account_id": 7, "payment_timing": "MID"}

    # before the override event, the loan's own defaults still apply
    settings_before = svc.get_effective_settings(loan_id, Period(2026, 2))
    assert settings_before == {"account_id": 1, "payment_timing": "BEGINNING"}
