# finanzmanager/application/services/account_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update

from src.application.dto.accounts import AccountDTO
from src.infrastructure.db.orm_models import (
    Account,
    Employer,
    IncomeFixed,
    IncomeHourly,
    ExpenseRecurring,
    ExpenseVariable,
    Loan,
    SavingsContribution,
)
from src.infrastructure.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class AccountUsage:
    employers_default: int
    income_fixed: int
    income_hourly: int
    expense_recurring: int
    expense_variable: int
    loans: int
    savings_contributions: int

    def total(self) -> int:
        return (
            self.employers_default
            + self.income_fixed
            + self.income_hourly
            + self.expense_recurring
            + self.expense_variable
            + self.loans
            + self.savings_contributions
        )

    def requires_replacement(self) -> bool:
        # NOT NULL FKs
        return (self.expense_recurring > 0) or (self.loans > 0)

    def is_empty(self) -> bool:
        return self.total() == 0


class AccountService:
    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory

    def list_accounts(self) -> list[AccountDTO]:
        with self._uow_factory() as uow:
            out: list[AccountDTO] = []
            for a in uow.accounts.list_all():
                out.append(
                    AccountDTO(
                        id=a.id,
                        bank_name=a.bank_name,
                        account_name=a.account_name,
                        label=a.label,
                        iban=a.iban,
                        role_income=a.role_income,
                        role_debit=a.role_debit,
                        notes=a.notes,
                    )
                )
            return out

    def upsert_account(self, dto: AccountDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.accounts.get(dto.id) if dto.id else None
            obj = obj or Account()
            obj.bank_name = dto.bank_name
            obj.account_name = dto.account_name
            obj.label = dto.label
            obj.iban = dto.iban
            obj.role_income = dto.role_income
            obj.role_debit = dto.role_debit
            obj.notes = dto.notes
            uow.accounts.upsert(obj)
            return obj.id

    def get_usage(self, account_id: int) -> AccountUsage:
        with self._uow_factory() as uow:
            s = getattr(uow, "_session", None)
            if s is None:
                raise RuntimeError("UnitOfWork session not available.")

            def count_where(model, col) -> int:
                return int(s.execute(select(func.count()).select_from(model).where(col == account_id)).scalar_one())

            return AccountUsage(
                employers_default=count_where(Employer, Employer.default_account_id),
                income_fixed=count_where(IncomeFixed, IncomeFixed.account_id),
                income_hourly=count_where(IncomeHourly, IncomeHourly.account_id),
                expense_recurring=count_where(ExpenseRecurring, ExpenseRecurring.account_id),
                expense_variable=count_where(ExpenseVariable, ExpenseVariable.account_id),
                loans=count_where(Loan, Loan.account_id),
                savings_contributions=count_where(SavingsContribution, SavingsContribution.account_id),
            )

    def delete_account(
        self,
        account_id: int,
        *,
        replacement_account_id: int | None = None,
        nullify_nullable: bool = True,
    ) -> dict[str, Any]:
        """
        FK-safe account deletion:
        - If referenced by NOT NULL FKs (Loan, ExpenseRecurring) => replacement_account_id required.
        - Nullable FKs are either reassigned (if replacement given) or set to NULL (if nullify_nullable).
        """
        if replacement_account_id is not None and replacement_account_id == account_id:
            raise ValueError("replacement_account_id must be different from account_id")

        with self._uow_factory() as uow:
            s = getattr(uow, "_session", None)
            if s is None:
                raise RuntimeError("UnitOfWork session not available.")

            account = uow.accounts.get(account_id)
            if not account:
                return {"status": "missing", "account_id": account_id}

            usage = self.get_usage(account_id)
            if usage.requires_replacement() and replacement_account_id is None:
                raise ValueError("Account is referenced by loans/recurring expenses. Replacement account is required.")

            if replacement_account_id is not None:
                repl = uow.accounts.get(replacement_account_id)
                if not repl:
                    raise ValueError("Replacement account does not exist.")

            changed = {}

            # NOT NULL FKs => must reassign
            if usage.expense_recurring > 0:
                res = s.execute(
                    update(ExpenseRecurring)
                    .where(ExpenseRecurring.account_id == account_id)
                    .values(account_id=replacement_account_id)
                )
                changed["expense_recurring_reassigned"] = int(res.rowcount or 0)

            if usage.loans > 0:
                res = s.execute(update(Loan).where(Loan.account_id == account_id).values(account_id=replacement_account_id))
                changed["loans_reassigned"] = int(res.rowcount or 0)

            # Nullable FKs => reassign or nullify
            def reassign_or_nullify(model, col, label: str) -> None:
                nonlocal changed
                if replacement_account_id is not None:
                    res = s.execute(update(model).where(col == account_id).values({col.key: replacement_account_id}))
                    changed[f"{label}_reassigned"] = int(res.rowcount or 0)
                elif nullify_nullable:
                    res = s.execute(update(model).where(col == account_id).values({col.key: None}))
                    changed[f"{label}_nullified"] = int(res.rowcount or 0)

            reassign_or_nullify(Employer, Employer.default_account_id, "employers_default")
            reassign_or_nullify(IncomeFixed, IncomeFixed.account_id, "income_fixed")
            reassign_or_nullify(IncomeHourly, IncomeHourly.account_id, "income_hourly")
            reassign_or_nullify(ExpenseVariable, ExpenseVariable.account_id, "expense_variable")
            reassign_or_nullify(SavingsContribution, SavingsContribution.account_id, "savings_contributions")

            # Finally delete
            uow.accounts.delete(account_id)

            return {
                "status": "deleted",
                "account_id": account_id,
                "replacement_account_id": replacement_account_id,
                "usage": usage,
                "changes": changed,
            }
