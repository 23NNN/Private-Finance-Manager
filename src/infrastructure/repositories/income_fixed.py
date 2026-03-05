# finanzmanager/infrastructure/repositories/income_fixed.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.orm_models import IncomeFixed


class IncomeFixedRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def new(self) -> IncomeFixed:
        return IncomeFixed()

    def get(self, row_id: int | None) -> IncomeFixed | None:
        if not row_id:
            return None
        return self._s.get(IncomeFixed, row_id)

    def list_for_period(self, year: int, month: int) -> list[IncomeFixed]:
        stmt = select(IncomeFixed).where(IncomeFixed.year == year, IncomeFixed.month == month)
        return list(self._s.execute(stmt).scalars().all())

    def list_for_year(self, year: int) -> list[IncomeFixed]:
        stmt = select(IncomeFixed).where(IncomeFixed.year == year).order_by(IncomeFixed.month, IncomeFixed.employer_id)
        return list(self._s.execute(stmt).scalars().all())

    def get_by_emp_period(self, employer_id: int, year: int, month: int) -> IncomeFixed | None:
        return self._s.execute(
            select(IncomeFixed).where(
                IncomeFixed.employer_id == employer_id,
                IncomeFixed.year == year,
                IncomeFixed.month == month,
            )
        ).scalar_one_or_none()

    def upsert(self, obj: IncomeFixed) -> None:
        if obj.id is None:
            self._s.add(obj)
        else:
            self._s.merge(obj)

    def delete(self, row_id: int) -> None:
        obj = self.get(row_id)
        if obj:
            self._s.delete(obj)
