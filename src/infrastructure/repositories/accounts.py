# finanzmanager/infrastructure/repositories/accounts.py
from __future__ import annotations

from sqlalchemy import select

from src.infrastructure.db.orm_models import Account
from src.infrastructure.repositories.base import Repository

__all__ = ["AccountRepository"]


class AccountRepository(Repository):
    def list_all(self) -> list[Account]:
        return list(self.session.scalars(select(Account).order_by(Account.label)))

    def get(self, account_id: int | None) -> Account | None:
        if not account_id:
            return None
        return self.session.get(Account, account_id)

    def get_by_label(self, label: str) -> Account | None:
        return self.session.scalar(select(Account).where(Account.label == label))

    def upsert(self, obj: Account) -> Account:
        # Works for both new and existing instances.
        self.session.add(obj)
        return obj

    def delete(self, account_id: int) -> None:
        obj = self.get(account_id)
        if obj is not None:
            self.session.delete(obj)
