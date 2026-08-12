# tests/unit/test_income_service.py
"""Unit tests for IncomeService (fixed-income upsert, hourly recalculation)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.application.dto.incomes import IncomeFixedDTO, IncomeHourlyDTO
from src.application.services.income_service import IncomeService
from src.domain.models.period import Period
from src.infrastructure.db.engine import dispose_engine, get_engine, init_engine
from src.infrastructure.db.orm_models import Base, Employer, PayoutTiming, PayRule, PayRuleType, PayRuleUnit
from src.infrastructure.unit_of_work import UnitOfWork


@pytest.fixture(autouse=True)
def _in_memory_engine():
    init_engine("sqlite:///:memory:")
    Base.metadata.create_all(get_engine())
    yield
    dispose_engine()


def _seed_employer() -> int:
    with UnitOfWork() as uow:
        uow.employers.upsert(Employer(name="TestCo", payout_timing=PayoutTiming.BEGINNING))
    with UnitOfWork() as uow:
        return uow.employers.get_by_name("TestCo").id


def _hourly_dto(employer_id: int, *, hours_normal: Decimal, night: Decimal) -> IncomeHourlyDTO:
    return IncomeHourlyDTO(
        id=None,
        employer_id=employer_id,
        year=2026,
        month=1,
        hours_bw=Decimal("0"),
        hours_by=Decimal("0"),
        hours_normal=hours_normal,
        night_bw=Decimal("0"),
        sunday_bw=Decimal("0"),
        night_by=Decimal("0"),
        sunday_by=Decimal("0"),
        night=night,
        sunday=Decimal("0"),
        holiday=Decimal("0"),
        overtime=Decimal("0"),
        special_amount=Decimal("0"),
        calc_amount=Decimal("0"),
        actual_amount=Decimal("0"),
    )


def test_upsert_fixed_income_computes_calc_amount():
    svc = IncomeService()
    emp_id = _seed_employer()

    dto = IncomeFixedDTO(
        id=None,
        employer_id=emp_id,
        year=2026,
        month=1,
        base_amount=Decimal("2000.00"),
        special_amount=Decimal("150.00"),
        calc_amount=Decimal("0"),
        actual_amount=Decimal("0"),
    )
    svc.upsert_fixed(dto)

    rows = svc.list_fixed(Period(2026, 1))
    assert len(rows) == 1
    assert rows[0].calc_amount == Decimal("2150.00")


def test_recalculate_hourly_applies_active_pay_rule():
    svc = IncomeService()
    emp_id = _seed_employer()

    with UnitOfWork() as uow:
        uow.pay_rules.upsert(
            PayRule(
                employer_id=emp_id,
                rule_type=PayRuleType.HOURLY_WAGE,
                unit=PayRuleUnit.EUR_PER_HOUR,
                value=Decimal("20.00"),
                valid_from=date(2020, 1, 1),
            )
        )
        uow.pay_rules.upsert(
            PayRule(
                employer_id=emp_id,
                rule_type=PayRuleType.NIGHT,
                unit=PayRuleUnit.MULTIPLIER,
                value=Decimal("1.25"),
                valid_from=date(2020, 1, 1),
            )
        )

    hourly_id = svc.upsert_hourly(_hourly_dto(emp_id, hours_normal=Decimal("10"), night=Decimal("4")))

    rows = svc.list_hourly(Period(2026, 1))
    # base: (10+4)*20 = 280, night premium: 4*20*(1.25-1) = 20 -> 300
    assert rows[0].calc_amount == Decimal("300.00")

    svc.recalculate_hourly(hourly_id)
    rows = svc.list_hourly(Period(2026, 1))
    assert rows[0].calc_amount == Decimal("300.00")


def test_recalculate_hourly_for_unknown_id_does_not_raise():
    svc = IncomeService()
    svc.recalculate_hourly(999999)
