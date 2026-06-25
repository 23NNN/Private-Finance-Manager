# tests/unit/test_employer_service_overlap.py
"""Unit tests for EmployerService pay-rule overlap resolution."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.application.dto.employers import PayRuleDTO
from src.application.services.employer_service import EmployerService
from src.infrastructure.db.orm_models import Base, Employer, PayoutTiming, PayRule, PayRuleType, PayRuleUnit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine


def _make_uow_factory(engine):
    """Returns a context-manager factory that mimics UnitOfWork for a given engine."""
    # autoflush=True so that session.add() + obj.id access works correctly
    SessionFactory = sessionmaker(bind=engine, future=True, expire_on_commit=False, autoflush=True)

    class FakeUoW:
        def __init__(self):
            self._session: Session | None = None

        def __enter__(self):
            self._session = SessionFactory()
            from src.infrastructure.repositories.accounts import AccountRepository
            from src.infrastructure.repositories.employers import EmployerRepository
            from src.infrastructure.repositories.pay_rules import PayRuleRepository
            from src.infrastructure.repositories.savings import SavingsRuleRepository

            self.accounts = AccountRepository(self._session)
            self.employers = EmployerRepository(self._session)
            self.pay_rules = PayRuleRepository(self._session)
            self.savings_rules = SavingsRuleRepository(self._session)
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc_type is None:
                self._session.commit()
            else:
                self._session.rollback()
            self._session.close()

    return FakeUoW


def _seed_employer(engine) -> int:
    SessionFactory = sessionmaker(bind=engine, future=True, expire_on_commit=False, autoflush=True)
    with SessionFactory() as s:
        emp = Employer(name="TestCo", payout_timing=PayoutTiming.BEGINNING)
        s.add(emp)
        s.flush()
        emp_id = emp.id
        s.commit()
        return emp_id


def _night_dto(employer_id: int, value: Decimal, valid_from, valid_to, rule_id=None) -> PayRuleDTO:
    return PayRuleDTO(
        id=rule_id,
        employer_id=employer_id,
        rule_type=PayRuleType.NIGHT.value,
        unit=PayRuleUnit.MULTIPLIER.value,
        value=value,
        valid_from=valid_from,
        valid_to=valid_to,
    )


# ---------------------------------------------------------------------------
# Tests – new rule triggers auto-trim of existing open-ended older rule
# ---------------------------------------------------------------------------

def test_add_newer_rule_trims_older_open_rule():
    """Adding a rule starting after an open-ended older rule should auto-trim the older rule."""
    engine = _make_engine()
    svc = EmployerService(uow_factory=_make_uow_factory(engine))
    emp_id = _seed_employer(engine)

    # older rule, no end date
    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.25"), date(2022, 1, 1), None))

    # newer rule starting 2023-01-01 → should auto-trim older to 2022-12-31
    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.30"), date(2023, 1, 1), None))

    rules = svc.list_pay_rules(emp_id)
    assert len(rules) == 2
    # older rule (valid_from=2022-01-01) must have been trimmed
    old = next(r for r in rules if r.valid_from == date(2022, 1, 1))
    assert old.valid_to == date(2022, 12, 31)


# ---------------------------------------------------------------------------
# Tests – editing an older rule that has a newer sibling (the reported bug)
# ---------------------------------------------------------------------------

def test_edit_older_rule_value_does_not_raise():
    """Editing an older rule (changing only value) must not raise when a newer rule exists."""
    engine = _make_engine()
    svc = EmployerService(uow_factory=_make_uow_factory(engine))
    emp_id = _seed_employer(engine)

    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.25"), date(2022, 1, 1), None))
    # adding newer rule auto-trims old to 2022-12-31
    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.30"), date(2023, 1, 1), None))

    rules = svc.list_pay_rules(emp_id)
    old = next(r for r in rules if r.valid_from == date(2022, 1, 1))

    # should not raise when editing the older rule (only value changes)
    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.27"), old.valid_from, old.valid_to, rule_id=old.id))

    rules = svc.list_pay_rules(emp_id)
    updated = next(r for r in rules if r.valid_from == date(2022, 1, 1))
    assert updated.value == Decimal("1.27")


def test_edit_older_open_rule_auto_caps_valid_to():
    """If an older open-ended rule is edited and overlaps a newer rule, valid_to is auto-capped."""
    engine = _make_engine()
    svc = EmployerService(uow_factory=_make_uow_factory(engine))
    emp_id = _seed_employer(engine)

    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.25"), date(2022, 1, 1), None))
    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.30"), date(2023, 1, 1), None))

    rules = svc.list_pay_rules(emp_id)
    old = next(r for r in rules if r.valid_from == date(2022, 1, 1))
    old_id = old.id

    # Simulate stale data: reset old rule's valid_to back to None
    SessionFactory = sessionmaker(bind=engine, future=True, expire_on_commit=False, autoflush=True)
    with SessionFactory() as s:
        obj = s.get(PayRule, old_id)
        obj.valid_to = None
        s.commit()

    # Edit the old rule with valid_to=None → should auto-cap to 2022-12-31
    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.27"), date(2022, 1, 1), None, rule_id=old_id))

    rules = svc.list_pay_rules(emp_id)
    updated = next(r for r in rules if r.id == old_id)
    assert updated.valid_to == date(2022, 12, 31)


def test_same_start_date_raises():
    """Two rules of the same type with identical valid_from must raise ValueError."""
    engine = _make_engine()
    svc = EmployerService(uow_factory=_make_uow_factory(engine))
    emp_id = _seed_employer(engine)

    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.25"), date(2022, 1, 1), None))

    with pytest.raises(ValueError, match="Overlapping"):
        svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.30"), date(2022, 1, 1), None))


def test_non_overlapping_rules_are_accepted():
    """Two rules with non-overlapping date ranges must be saved without modification."""
    engine = _make_engine()
    svc = EmployerService(uow_factory=_make_uow_factory(engine))
    emp_id = _seed_employer(engine)

    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.25"), date(2022, 1, 1), date(2022, 12, 31)))
    svc.upsert_pay_rule(_night_dto(emp_id, Decimal("1.30"), date(2023, 1, 1), None))

    rules = svc.list_pay_rules(emp_id)
    assert len(rules) == 2
    # both rules must remain unchanged
    assert next(r for r in rules if r.valid_from == date(2022, 1, 1)).valid_to == date(2022, 12, 31)
    assert next(r for r in rules if r.valid_from == date(2023, 1, 1)).valid_to is None
