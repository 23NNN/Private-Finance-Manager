# src/infrastructure/repositories/savings.py
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select

from src.infrastructure.db.orm_models import SavingsContribution, SavingsGoal, SavingsRule
from src.infrastructure.repositories.base import Repository


class SavingsGoalRepository(Repository):
    def list_all(self) -> list[SavingsGoal]:
        return list(self.session.scalars(select(SavingsGoal).order_by(SavingsGoal.name)))

    def get(self, goal_id: int) -> SavingsGoal | None:
        return self.session.get(SavingsGoal, goal_id)

    def upsert(self, obj: SavingsGoal) -> SavingsGoal:
        self.session.add(obj)
        return obj

    def delete(self, goal_id: int) -> None:
        obj = self.get(goal_id)
        if obj is not None:
            self.session.delete(obj)


class SavingsRuleRepository(Repository):
    def list_all(self) -> list[SavingsRule]:
        return list(self.session.scalars(select(SavingsRule)))

    def list_by_employer(self, employer_id: int) -> list[SavingsRule]:
        stmt = select(SavingsRule).where(SavingsRule.employer_id == employer_id).order_by(SavingsRule.valid_from.desc())
        return list(self.session.scalars(stmt))

    def list_active_for_date(self, employer_id: int, at_date: date) -> list[SavingsRule]:
        stmt = (
            select(SavingsRule)
            .where(
                and_(
                    SavingsRule.employer_id == employer_id,
                    SavingsRule.valid_from <= at_date,
                    or_(SavingsRule.valid_to.is_(None), SavingsRule.valid_to >= at_date),
                )
            )
            .order_by(SavingsRule.valid_from.desc())
        )
        return list(self.session.scalars(stmt))

    def get(self, rule_id: int | None) -> SavingsRule | None:
        if not rule_id:
            return None
        return self.session.get(SavingsRule, rule_id)

    def upsert(self, obj: SavingsRule) -> SavingsRule:
        self.session.add(obj)
        return obj

    def delete(self, rule_id: int) -> None:
        obj = self.get(rule_id)
        if obj is not None:
            self.session.delete(obj)


class SavingsContributionRepository(Repository):
    def list_for_goal(self, goal_id: int) -> list[SavingsContribution]:
        stmt = select(SavingsContribution).where(SavingsContribution.goal_id == goal_id)
        return list(self.session.scalars(stmt.order_by(SavingsContribution.year, SavingsContribution.month)))

    def get(self, contrib_id: int | None) -> SavingsContribution | None:
        if not contrib_id:
            return None
        return self.session.get(SavingsContribution, contrib_id)

    def upsert(self, obj: SavingsContribution) -> SavingsContribution:
        self.session.add(obj)
        return obj

    def delete(self, contrib_id: int) -> None:
        obj = self.get(contrib_id)
        if obj is not None:
            self.session.delete(obj)
