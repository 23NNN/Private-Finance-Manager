# infrastructure/repositories/expenses.py
from __future__ import annotations

from sqlalchemy import select

from src.infrastructure.db.orm_models import ExpenseCategory, ExpenseRecurring, ExpenseVariable
from src.infrastructure.repositories.base import Repository

__all__ = [
    "ExpenseCategoryRepository",
    "CategoryRepository",
    "ExpenseRecurringRepository",
    "ExpenseVariableRepository",
]


class ExpenseCategoryRepository(Repository):
    def list_all(self) -> list[ExpenseCategory]:
        return list(self.session.scalars(select(ExpenseCategory).order_by(ExpenseCategory.name)))

    def get(self, category_id: int) -> ExpenseCategory | None:
        return self.session.get(ExpenseCategory, category_id)

    def get_by_name(self, name: str) -> ExpenseCategory | None:
        return self.session.scalar(select(ExpenseCategory).where(ExpenseCategory.name == name))

    def upsert(self, obj: ExpenseCategory) -> ExpenseCategory:
        self.session.add(obj)
        return obj

    def delete(self, category_id: int) -> None:
        obj = self.session.get(ExpenseCategory, category_id)
        if obj is not None:
            self.session.delete(obj)


# Backwards-compatible alias
CategoryRepository = ExpenseCategoryRepository


class ExpenseRecurringRepository(Repository):
    def list_all(self) -> list[ExpenseRecurring]:
        return list(self.session.scalars(select(ExpenseRecurring).order_by(ExpenseRecurring.name)))

    def get(self, rid: int) -> ExpenseRecurring | None:
        return self.session.get(ExpenseRecurring, rid)

    def upsert(self, obj: ExpenseRecurring) -> ExpenseRecurring:
        self.session.add(obj)
        return obj


class ExpenseVariableRepository(Repository):
    def list_for_period(self, year: int, month: int) -> list[ExpenseVariable]:
        stmt = select(ExpenseVariable).where(ExpenseVariable.year == year, ExpenseVariable.month == month)
        return list(self.session.scalars(stmt.order_by(ExpenseVariable.name)))

    def list_for_year(self, year: int) -> list[ExpenseVariable]:
        stmt = select(ExpenseVariable).where(ExpenseVariable.year == year)
        return list(self.session.scalars(stmt.order_by(ExpenseVariable.month, ExpenseVariable.name)))

    def get(self, vid: int) -> ExpenseVariable | None:
        return self.session.get(ExpenseVariable, vid)

    def upsert(self, obj: ExpenseVariable) -> ExpenseVariable:
        self.session.add(obj)
        return obj
