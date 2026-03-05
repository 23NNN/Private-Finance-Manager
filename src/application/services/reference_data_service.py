# finanzmanager/application/services/reference_data_service.py
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from src.infrastructure.db.orm_models import ExpenseCategory, ExpenseGroup, ExpenseRecurring, ExpenseVariable
from src.infrastructure.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class AccountRef:
    id: int
    label: str


@dataclass(frozen=True)
class EmployerRef:
    """
    Reference/Lookup DTO used by UI combo-boxes etc.

    IMPORTANT:
    Some presenters expect payout_timing/default_account_id, therefore these
    fields must exist for backward/forward compatibility.
    """
    id: int
    name: str
    payout_timing: str = "MID"
    default_account_id: int | None = None
    notes: str | None = None


@dataclass(frozen=True)
class CategoryRef:
    id: int
    name: str
    group: str


class ReferenceDataService:
    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory

    def list_accounts(self) -> list[AccountRef]:
        with self._uow_factory() as uow:
            return [AccountRef(a.id, a.label) for a in uow.accounts.list_all()]

    def list_employers(self) -> list[EmployerRef]:
        """
        Returns employers for UI selections. Includes payout_timing etc. so that
        presenters can show 'Auszahlung' without crashing.
        """
        with self._uow_factory() as uow:
            out: list[EmployerRef] = []
            for e in uow.employers.list_all():
                out.append(
                    EmployerRef(
                        id=e.id,
                        name=e.name,
                        payout_timing=getattr(e.payout_timing, "value", str(e.payout_timing)),
                        default_account_id=getattr(e, "default_account_id", None),
                        notes=getattr(e, "notes", None),
                    )
                )
            return out

    def ensure_default_categories(self) -> None:
        with self._uow_factory() as uow:
            existing = {c.name: c for c in uow.expense_categories.list_all()}

            def ensure(name: str, group: ExpenseGroup) -> None:
                if name in existing:
                    return
                uow.expense_categories.upsert(ExpenseCategory(name=name, group=group))

            ensure("Allgemein (Fix)", ExpenseGroup.FIX)
            ensure("Allgemein (Variabel)", ExpenseGroup.VARIABLE)
            ensure("Kredit", ExpenseGroup.LOAN)

    def list_categories(self) -> list[CategoryRef]:
        self.ensure_default_categories()
        with self._uow_factory() as uow:
            cats = uow.expense_categories.list_all()
            return [CategoryRef(c.id, c.name, c.group.value) for c in cats]

    def upsert_category(self, name: str, group: str, category_id: int | None = None) -> int:
        name = (name or "").strip()
        if not name:
            raise ValueError("Name darf nicht leer sein.")

        group = (group or "").strip().upper()
        if group not in {"FIX", "VARIABLE", "LOAN"}:
            raise ValueError("Gruppe muss FIX, VARIABLE oder LOAN sein.")

        with self._uow_factory() as uow:
            stmt = select(ExpenseCategory).where(func.lower(ExpenseCategory.name) == name.lower())
            existing = uow._session.scalar(stmt)  # MVP: ok

            if existing and (category_id is None or existing.id != category_id):
                raise ValueError(f"Kategorie existiert bereits: {name}")

            if category_id is None:
                obj = ExpenseCategory(name=name, group=ExpenseGroup(group))
            else:
                obj = uow.expense_categories.get(category_id)
                if not obj:
                    raise ValueError("Kategorie nicht gefunden.")
                obj.name = name
                obj.group = ExpenseGroup(group)

            uow.expense_categories.upsert(obj)
            return obj.id

    def delete_category(self, category_id: int) -> None:
        with self._uow_factory() as uow:
            obj = uow.expense_categories.get(category_id)
            if not obj:
                return

            used_rec = uow._session.scalar(
                select(func.count()).select_from(ExpenseRecurring).where(ExpenseRecurring.category_id == category_id)
            ) or 0
            used_var = uow._session.scalar(
                select(func.count()).select_from(ExpenseVariable).where(ExpenseVariable.category_id == category_id)
            ) or 0

            if used_rec > 0 or used_var > 0:
                raise ValueError("Category cannot be deleted because it is already in use.")

            uow.expense_categories.delete(category_id)
