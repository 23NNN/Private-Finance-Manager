# src/infrastructure/repositories/income_special.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.orm_models import IncomeSpecial


class IncomeSpecialRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, row_id: int | None) -> IncomeSpecial | None:
        if not row_id:
            return None
        return self._s.get(IncomeSpecial, row_id)

    def list_for_period(self, year: int, month: int) -> list[IncomeSpecial]:
        stmt = (
            select(IncomeSpecial)
            .where(IncomeSpecial.year == year, IncomeSpecial.month == month)
            .order_by(IncomeSpecial.name)
        )
        return list(self._s.execute(stmt).scalars().all())

    def list_for_year(self, year: int) -> list[IncomeSpecial]:
        stmt = select(IncomeSpecial).where(IncomeSpecial.year == year).order_by(IncomeSpecial.month, IncomeSpecial.name)
        return list(self._s.execute(stmt).scalars().all())

    def upsert(self, obj: IncomeSpecial) -> None:
        if obj.id is None:
            self._s.add(obj)
        else:
            self._s.merge(obj)

    def delete(self, row_id: int) -> None:
        obj = self.get(row_id)
        if obj is not None:
            self._s.delete(obj)
