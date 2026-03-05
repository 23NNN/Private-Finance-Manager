# finanzmanager/infrastructure/repositories/incomes.py
from __future__ import annotations

from sqlalchemy import select
from src.infrastructure.db.orm_models import IncomeFixed, IncomeHourly
from src.infrastructure.repositories.base import Repository


class IncomeFixedRepository(Repository):
    def list_for_period(self, year: int, month: int) -> list[IncomeFixed]:
        stmt = select(IncomeFixed).where(IncomeFixed.year == year, IncomeFixed.month == month)
        return list(self.session.scalars(stmt.order_by(IncomeFixed.employer_id)))

    def get_by_emp_period(self, employer_id: int, year: int, month: int) -> IncomeFixed | None:
        stmt = select(IncomeFixed).where(
            IncomeFixed.employer_id == employer_id,
            IncomeFixed.year == year,
            IncomeFixed.month == month,
        )
        return self.session.scalar(stmt)

    def get(self, income_id: int) -> IncomeFixed | None:
        return self.session.get(IncomeFixed, income_id)

    def upsert(self, obj: IncomeFixed) -> IncomeFixed:
        self.session.add(obj)
        return obj


class IncomeHourlyRepository(Repository):
    def list_for_period(self, year: int, month: int) -> list[IncomeHourly]:
        stmt = select(IncomeHourly).where(IncomeHourly.year == year, IncomeHourly.month == month)
        return list(self.session.scalars(stmt.order_by(IncomeHourly.employer_id)))

    def get_by_emp_period(self, employer_id: int, year: int, month: int) -> IncomeHourly | None:
        stmt = select(IncomeHourly).where(
            IncomeHourly.employer_id == employer_id,
            IncomeHourly.year == year,
            IncomeHourly.month == month,
        )
        return self.session.scalar(stmt)

    def get(self, income_id: int) -> IncomeHourly | None:
        return self.session.get(IncomeHourly, income_id)

    def upsert(self, obj: IncomeHourly) -> IncomeHourly:
        self.session.add(obj)
        return obj
