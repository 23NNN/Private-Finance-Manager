# finanzmanager/infrastructure/repositories/loan_events.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.infrastructure.db.orm_models import LoanEvent


def _extract_year_month(obj: Any) -> tuple[int, int]:
    if obj is None:
        raise ValueError("until/year must not be None")

    if isinstance(obj, (date, datetime)):
        return int(obj.year), int(obj.month)

    if hasattr(obj, "year") and hasattr(obj, "month"):
        return int(getattr(obj, "year")), int(getattr(obj, "month"))

    if isinstance(obj, (tuple, list)) and len(obj) >= 2:
        return int(obj[0]), int(obj[1])

    if isinstance(obj, dict) and "year" in obj and "month" in obj:
        return int(obj["year"]), int(obj["month"])

    raise ValueError(f"Unsupported type for year/month extraction: {type(obj)!r}")


class LoanEventRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list_all(self) -> list[LoanEvent]:
        return list(self._s.execute(select(LoanEvent)).scalars().all())

    def list_by_loan(self, loan_id: int) -> list[LoanEvent]:
        stmt = (
            select(LoanEvent)
            .where(LoanEvent.loan_id == loan_id)
            .order_by(LoanEvent.year.asc(), LoanEvent.month.asc(), LoanEvent.event_date.asc(), LoanEvent.id.asc())
        )
        return list(self._s.execute(stmt).scalars().all())

    def list_for_loan_month(self, loan_id: int, year: int, month: int) -> list[LoanEvent]:
        stmt = (
            select(LoanEvent)
            .where(
                LoanEvent.loan_id == loan_id,
                LoanEvent.year == int(year),
                LoanEvent.month == int(month),
            )
            .order_by(LoanEvent.event_date.asc(), LoanEvent.id.asc())
        )
        return list(self._s.execute(stmt).scalars().all())

    def list_for_loan_until(self, loan_id: int, until_or_year: Any, *args: Any, **kwargs: Any) -> list[LoanEvent]:
        """
        Kompatibel zu verschiedenen Aufrufvarianten:
          - (loan_id, period/date/datetime)
          - (loan_id, year, month)
          - (loan_id, year, month, include_current)
          - (loan_id, period, include_current)
        """
        include_current = bool(kwargs.get("include_current", True))

        # (loan_id, period, include_current?)
        if args and isinstance(args[0], bool) and not isinstance(until_or_year, (int, str)):
            include_current = bool(args[0])
            args = args[1:]

        # (loan_id, year, month, include_current?)
        if isinstance(until_or_year, (int, str)) and args:
            y = int(until_or_year)
            m = int(args[0])
            if len(args) >= 2 and isinstance(args[1], bool):
                include_current = bool(args[1])
        else:
            y, m = _extract_year_month(until_or_year)

        if include_current:
            cutoff = or_(LoanEvent.year < y, and_(LoanEvent.year == y, LoanEvent.month <= m))
        else:
            cutoff = or_(LoanEvent.year < y, and_(LoanEvent.year == y, LoanEvent.month < m))

        stmt = (
            select(LoanEvent)
            .where(LoanEvent.loan_id == loan_id, cutoff)
            .order_by(LoanEvent.year.asc(), LoanEvent.month.asc(), LoanEvent.event_date.asc(), LoanEvent.id.asc())
        )
        return list(self._s.execute(stmt).scalars().all())

    def get(self, event_id: int | None) -> LoanEvent | None:
        if not event_id:
            return None
        return self._s.get(LoanEvent, event_id)

    def upsert(self, obj: LoanEvent) -> None:
        if obj.id is None:
            self._s.add(obj)
        else:
            self._s.merge(obj)

    def delete(self, event_id: int) -> None:
        obj = self.get(event_id)
        if obj:
            self._s.delete(obj)
