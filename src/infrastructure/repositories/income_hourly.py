# finanzmanager/infrastructure/repositories/income_hourly.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.orm_models import IncomeHourly


class IncomeHourlyRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def new(self) -> IncomeHourly:
        return IncomeHourly()

    def get(self, row_id: int | None) -> IncomeHourly | None:
        if not row_id:
            return None
        return self._s.get(IncomeHourly, row_id)

    def list_for_period(self, year: int, month: int) -> list[IncomeHourly]:
        stmt = select(IncomeHourly).where(IncomeHourly.year == year, IncomeHourly.month == month)
        return list(self._s.execute(stmt).scalars().all())

    def list_for_year(self, year: int) -> list[IncomeHourly]:
        stmt = select(IncomeHourly).where(IncomeHourly.year == year).order_by(IncomeHourly.month, IncomeHourly.employer_id)
        return list(self._s.execute(stmt).scalars().all())

    def get_by_emp_period(self, employer_id: int, year: int, month: int) -> IncomeHourly | None:
        return self._s.execute(
            select(IncomeHourly).where(
                IncomeHourly.employer_id == employer_id,
                IncomeHourly.year == year,
                IncomeHourly.month == month,
            )
        ).scalar_one_or_none()

    def upsert(self, obj: IncomeHourly) -> None:
        if obj.id is None:
            self._s.add(obj)
        else:
            self._s.merge(obj)

    def delete(self, row_id: int) -> None:
        obj = self.get(row_id)
        if obj:
            self._s.delete(obj)
