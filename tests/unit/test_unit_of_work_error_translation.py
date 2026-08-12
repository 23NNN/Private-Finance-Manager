# tests/unit/test_unit_of_work_error_translation.py
"""Unit tests for UnitOfWork translating raw DB exceptions into DomainError."""
from __future__ import annotations

import pytest

from src.domain.errors import DomainError
from src.infrastructure.db.engine import dispose_engine, init_engine
from src.infrastructure.db.orm_models import Base, Employer, PayoutTiming
from src.infrastructure.unit_of_work import UnitOfWork


@pytest.fixture(autouse=True)
def _in_memory_engine():
    init_engine("sqlite:///:memory:")
    from src.infrastructure.db.engine import get_engine

    Base.metadata.create_all(get_engine())
    yield
    dispose_engine()


def test_unique_constraint_violation_raises_domain_error():
    with UnitOfWork() as uow:
        uow.employers.upsert(Employer(name="TestCo", payout_timing=PayoutTiming.BEGINNING))

    with pytest.raises(DomainError):
        with UnitOfWork() as uow:
            uow.employers.upsert(Employer(name="TestCo", payout_timing=PayoutTiming.BEGINNING))


def test_successful_write_is_unaffected():
    with UnitOfWork() as uow:
        uow.employers.upsert(Employer(name="OtherCo", payout_timing=PayoutTiming.MID))

    with UnitOfWork() as uow:
        employers = uow.employers.list_all()
    assert any(e.name == "OtherCo" for e in employers)
