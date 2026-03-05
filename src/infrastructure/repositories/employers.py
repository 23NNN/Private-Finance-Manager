# infrastructure/repositories/employers.py
from __future__ import annotations

from sqlalchemy import select

from src.infrastructure.db.orm_models import Employer
from src.infrastructure.repositories.base import Repository

__all__ = ["EmployerRepository"]


class EmployerRepository(Repository):
    def list_all(self) -> list[Employer]:
        return list(self.session.scalars(select(Employer).order_by(Employer.name)))

    def get(self, employer_id: int | None) -> Employer | None:
        if not employer_id:
            return None
        return self.session.get(Employer, employer_id)

    def get_by_name(self, name: str) -> Employer | None:
        return self.session.scalar(select(Employer).where(Employer.name == name))

    def upsert(self, obj: Employer) -> Employer:
        self.session.add(obj)
        return obj

    def delete(self, employer_id: int) -> None:
        obj = self.get(employer_id)
        if obj is not None:
            self.session.delete(obj)
