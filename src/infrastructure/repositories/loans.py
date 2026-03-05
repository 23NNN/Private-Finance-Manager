# finanzmanager/infrastructure/repositories/loans.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.orm_models import Loan, LoanStatus


class LoanRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list_all(self) -> list[Loan]:
        return list(self._s.execute(select(Loan).order_by(Loan.name)).scalars().all())

    def get(self, loan_id: int | None) -> Loan | None:
        if not loan_id:
            return None
        return self._s.get(Loan, loan_id)

    def get_by_name(self, name: str) -> Loan | None:
        return self._s.execute(select(Loan).where(Loan.name == name)).scalar_one_or_none()

    def upsert(self, obj: Loan) -> None:
        if obj.id is None:
            self._s.add(obj)
        else:
            self._s.merge(obj)

    def set_status(self, loan_id: int, status: LoanStatus) -> None:
        obj = self.get(loan_id)
        if obj:
            obj.status = status
            self.upsert(obj)

    def delete(self, loan_id: int) -> None:
        obj = self.get(loan_id)
        if obj:
            self._s.delete(obj)
