# finanzmanager/application/services/expense_service.py
from __future__ import annotations

from src.application.dto.expenses import ExpenseRecurringDTO, ExpenseVariableDTO
from src.infrastructure.db.orm_models import (
    AllocationOverride,
    ExpenseRecurring,
    ExpenseVariable,
    PayBucket,
    RecurringStatus,
    VariableStatus,
)
from src.infrastructure.unit_of_work import UnitOfWork


class ExpenseService:
    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory

    def list_recurring(self) -> list[ExpenseRecurringDTO]:
        with self._uow_factory() as uow:
            out: list[ExpenseRecurringDTO] = []
            for r in uow.expense_recurring.list_all():
                out.append(
                    ExpenseRecurringDTO(
                        id=r.id,
                        name=r.name,
                        category_id=r.category_id,
                        amount=r.amount,
                        frequency_months=r.frequency_months,
                        due_day=r.due_day,
                        anchor_month=r.anchor_month,
                        status=r.status.value,
                        account_id=r.account_id,
                        pay_bucket=r.pay_bucket.value,
                        notes=r.notes,
                        allocation_override=r.allocation_override.value if r.allocation_override else None,
                    )
                )
            return out

    def upsert_recurring(self, dto: ExpenseRecurringDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.expense_recurring.get(dto.id) if dto.id else None
            obj = obj or ExpenseRecurring()

            obj.name = dto.name
            obj.category_id = dto.category_id
            obj.amount = dto.amount
            obj.frequency_months = dto.frequency_months
            obj.due_day = dto.due_day
            obj.anchor_month = dto.anchor_month
            obj.status = RecurringStatus(dto.status)
            obj.account_id = dto.account_id
            obj.pay_bucket = PayBucket(dto.pay_bucket)
            obj.notes = dto.notes
            obj.allocation_override = AllocationOverride(dto.allocation_override) if dto.allocation_override else None

            uow.expense_recurring.upsert(obj)
            return obj.id

    def set_recurring_status(self, recurring_id: int, status: str) -> None:
        with self._uow_factory() as uow:
            obj = uow.expense_recurring.get(recurring_id)
            if not obj:
                return
            obj.status = RecurringStatus(status)
            uow.expense_recurring.upsert(obj)

    def soft_delete_recurring(self, recurring_id: int) -> None:
        self.set_recurring_status(recurring_id, "INACTIVE")

    def undo_recurring(self, recurring_id: int) -> None:
        self.set_recurring_status(recurring_id, "ACTIVE")

    def list_variable(self, period) -> list[ExpenseVariableDTO]:
        with self._uow_factory() as uow:
            out: list[ExpenseVariableDTO] = []
            for r in uow.expense_variable.list_for_period(period.year, period.month):
                out.append(
                    ExpenseVariableDTO(
                        id=r.id,
                        name=r.name,
                        category_id=r.category_id,
                        amount=r.amount,
                        year=r.year,
                        month=r.month,
                        status=r.status.value,
                        account_id=r.account_id,
                        pay_bucket=r.pay_bucket.value,
                        notes=r.notes,
                    )
                )
            return out

    def list_variable_year(self, year: int) -> list[ExpenseVariableDTO]:
        with self._uow_factory() as uow:
            repo = uow.expense_variable
            if hasattr(repo, "list_for_year"):
                rows = repo.list_for_year(year)  # type: ignore[attr-defined]
            else:
                rows = []
                for m in range(1, 13):
                    rows.extend(repo.list_for_period(year, m))

            out: list[ExpenseVariableDTO] = []
            for r in rows:
                out.append(
                    ExpenseVariableDTO(
                        id=r.id,
                        name=r.name,
                        category_id=r.category_id,
                        amount=r.amount,
                        year=r.year,
                        month=r.month,
                        status=r.status.value,
                        account_id=r.account_id,
                        pay_bucket=r.pay_bucket.value,
                        notes=r.notes,
                    )
                )
            return out

    def upsert_variable(self, dto: ExpenseVariableDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.expense_variable.get(dto.id) if dto.id else None
            obj = obj or ExpenseVariable()

            obj.name = dto.name
            obj.category_id = dto.category_id
            obj.amount = dto.amount
            obj.year = dto.year
            obj.month = dto.month
            obj.status = VariableStatus(dto.status)
            obj.account_id = dto.account_id
            obj.pay_bucket = PayBucket(dto.pay_bucket)
            obj.notes = dto.notes

            uow.expense_variable.upsert(obj)
            return obj.id

    def set_variable_status(self, variable_id: int, status: str) -> None:
        with self._uow_factory() as uow:
            obj = uow.expense_variable.get(variable_id)
            if not obj:
                return
            obj.status = VariableStatus(status)
            uow.expense_variable.upsert(obj)

    def soft_delete_variable(self, variable_id: int) -> None:
        self.set_variable_status(variable_id, "CANCELLED")

    def undo_variable(self, variable_id: int) -> None:
        self.set_variable_status(variable_id, "OPEN")
