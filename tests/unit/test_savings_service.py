# tests/unit/test_savings_service.py
"""Unit tests for SavingsService.

Also guards against a regression of a confirmed bug: add_contribution()/
list_contributions() referenced the non-existent uow.savings_contribs
instead of the registered uow.savings_contributions and raised
AttributeError on every call.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.application.dto.savings import SavingsContributionDTO, SavingsGoalDTO
from src.application.services.savings_service import SavingsService
from src.infrastructure.db.engine import dispose_engine, get_engine, init_engine
from src.infrastructure.db.orm_models import Base


@pytest.fixture(autouse=True)
def _in_memory_engine():
    init_engine("sqlite:///:memory:")
    Base.metadata.create_all(get_engine())
    yield
    dispose_engine()


def test_upsert_goal_and_add_contribution_roundtrip():
    svc = SavingsService()

    goal_id = svc.upsert_goal(
        SavingsGoalDTO(id=None, name="Notgroschen", type="EMERGENCY", linked_to_source=False, notes=None)
    )

    svc.add_contribution(
        SavingsContributionDTO(
            id=None, goal_id=goal_id, year=2026, month=1, amount=Decimal("250.00"), account_id=None, notes=None
        )
    )

    goals = svc.list_goals()
    assert len(goals) == 1
    assert goals[0].name == "Notgroschen"

    contributions = svc.list_contributions(goal_id)
    assert len(contributions) == 1
    assert contributions[0].amount == Decimal("250.00")


def test_list_contributions_for_unknown_goal_returns_empty():
    svc = SavingsService()
    assert svc.list_contributions(999999) == []
