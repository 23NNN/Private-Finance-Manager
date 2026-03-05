# infrastructure/repositories/pay_rules.py
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select

from src.infrastructure.db.orm_models import PayRule
from src.infrastructure.repositories.base import Repository

__all__ = ["PayRuleRepository"]


class PayRuleRepository(Repository):
    def list_by_employer(self, employer_id: int) -> list[PayRule]:
        stmt = (
            select(PayRule)
            .where(PayRule.employer_id == employer_id)
            .order_by(PayRule.rule_type, PayRule.valid_from.desc())
        )
        return list(self.session.scalars(stmt))

    def list_active_for_date(self, employer_id: int, at_date: date) -> list[PayRule]:
        stmt = (
            select(PayRule)
            .where(
                and_(
                    PayRule.employer_id == employer_id,
                    PayRule.valid_from <= at_date,
                    or_(PayRule.valid_to.is_(None), PayRule.valid_to >= at_date),
                )
            )
            .order_by(PayRule.rule_type, PayRule.valid_from.desc())
        )
        return list(self.session.scalars(stmt))

    def list_by_employer_and_type(self, employer_id: int, rule_type) -> list[PayRule]:
        stmt = (
            select(PayRule)
            .where(and_(PayRule.employer_id == employer_id, PayRule.rule_type == rule_type))
            .order_by(PayRule.valid_from.desc())
        )
        return list(self.session.scalars(stmt))

    def get(self, rule_id: int | None) -> PayRule | None:
        if not rule_id:
            return None
        return self.session.get(PayRule, rule_id)

    def upsert(self, obj: PayRule) -> PayRule:
        self.session.add(obj)
        return obj

    def delete(self, rule_id: int) -> None:
        obj = self.get(rule_id)
        if obj is not None:
            self.session.delete(obj)
