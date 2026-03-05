# src/application/services/employer_service.py
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from src.application.dto.employers import EmployerDTO, PayRuleDTO
from src.application.dto.savings import SavingsRuleDTO
from src.application.services.reference_data_service import AccountRef
from src.infrastructure.db.orm_models import (
    Account,
    Employer,
    PayRule,
    PayRuleType,
    PayRuleUnit,
    PayoutTiming,
    SavingsRule,
)
from src.infrastructure.unit_of_work import UnitOfWork


_MIN_SAVINGS = Decimal("0.10")
_MAX_SAVINGS = Decimal("0.35")


def _norm_from(d: date | None) -> date:
    return d or date(1900, 1, 1)


def _to_inf(d: date | None) -> date:
    return d or date.max


def _overlaps(a_from: date | None, a_to: date | None, b_from: date | None, b_to: date | None) -> bool:
    return _norm_from(a_from) <= _to_inf(b_to) and _norm_from(b_from) <= _to_inf(a_to)


class EmployerService:
    """Employer + PayRules CRUD + SavingsRate (SavingsRule) CRUD."""

    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory

    # -------------------- reference helpers --------------------
    def list_accounts(self) -> list[AccountRef]:
        with self._uow_factory() as uow:
            accounts: list[Account] = uow.accounts.list_all()
            return [AccountRef(a.id, a.label) for a in accounts]

    # -------------------- employers --------------------
    def list_employers(self) -> list[EmployerDTO]:
        with self._uow_factory() as uow:
            out: list[EmployerDTO] = []
            for e in uow.employers.list_all():
                out.append(
                    EmployerDTO(
                        id=e.id,
                        name=e.name,
                        payout_timing=e.payout_timing.value,
                        default_account_id=e.default_account_id,
                        notes=e.notes,
                    )
                )
            return out

    def upsert_employer(self, dto: EmployerDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.employers.get(dto.id) if dto.id else None
            obj = obj or Employer()
            obj.name = dto.name
            obj.payout_timing = PayoutTiming(dto.payout_timing)
            obj.default_account_id = dto.default_account_id
            obj.notes = dto.notes
            uow.employers.upsert(obj)
            return obj.id

    def delete_employer(self, employer_id: int) -> None:
        with self._uow_factory() as uow:
            uow.employers.delete(employer_id)

    # -------------------- pay rules --------------------
    def list_pay_rules(self, employer_id: int) -> list[PayRuleDTO]:
        with self._uow_factory() as uow:
            out: list[PayRuleDTO] = []
            for r in uow.pay_rules.list_by_employer(employer_id):
                out.append(
                    PayRuleDTO(
                        id=r.id,
                        employer_id=r.employer_id,
                        rule_type=r.rule_type.value,
                        unit=r.unit.value,
                        value=r.value,
                        valid_from=getattr(r, "valid_from", None),
                        valid_to=getattr(r, "valid_to", None),
                        notes=getattr(r, "notes", None),
                    )
                )
            return out

    def upsert_pay_rule(self, dto: PayRuleDTO) -> int:
        """Rules of the same type can exist multiple times (history).

        Overlaps are handled:
          - If new_from is after an overlapping old rule -> old.valid_to is set to new_from - 1 day.
          - Else -> error (user must adjust).
        """
        with self._uow_factory() as uow:
            obj = uow.pay_rules.get(dto.id) if dto.id else None
            obj = obj or PayRule()

            new_from = _norm_from(dto.valid_from)
            new_to = dto.valid_to
            if new_to is not None and new_to < new_from:
                raise ValueError("Invalid date range: 'Valid to' is before 'Valid from'.")

            # adjust overlapping rules of same type
            for other in uow.pay_rules.list_by_employer_and_type(dto.employer_id, PayRuleType(dto.rule_type)):
                if dto.id and other.id == dto.id:
                    continue
                if not _overlaps(getattr(other, "valid_from", None), getattr(other, "valid_to", None), new_from, new_to):
                    continue

                other_from = _norm_from(getattr(other, "valid_from", None))
                if new_from > other_from:
                    other.valid_to = new_from - timedelta(days=1)
                    uow.pay_rules.upsert(other)
                else:
                    raise ValueError(
                        "Overlapping rule found. Please adjust 'Valid from/to' "
                        "so that the date ranges do not overlap."
                    )

            obj.employer_id = dto.employer_id
            obj.rule_type = PayRuleType(dto.rule_type)
            obj.value = dto.value
            obj.unit = PayRuleUnit(dto.unit)
            obj.valid_from = new_from
            obj.valid_to = new_to
            if hasattr(obj, "notes"):
                obj.notes = getattr(dto, "notes", None)

            uow.pay_rules.upsert(obj)
            return obj.id

    def delete_pay_rule(self, rule_id: int) -> None:
        with self._uow_factory() as uow:
            uow.pay_rules.delete(rule_id)

    # -------------------- savings rules (sparrate) --------------------
    def list_savings_rules(self, employer_id: int) -> list[SavingsRuleDTO]:
        with self._uow_factory() as uow:
            out: list[SavingsRuleDTO] = []
            for r in uow.savings_rules.list_by_employer(employer_id):
                out.append(
                    SavingsRuleDTO(
                        id=r.id,
                        employer_id=r.employer_id,
                        percentage=r.percentage,
                        valid_from=getattr(r, "valid_from", None),
                        valid_to=getattr(r, "valid_to", None),
                        goal_id=r.goal_id,
                    )
                )
            return out

    def upsert_savings_rule(self, dto: SavingsRuleDTO) -> int:
        """Savings rate per employer (10% – 35%) with validity window."""
        pct = Decimal(dto.percentage)

        if pct < _MIN_SAVINGS:
            raise ValueError("Savings rate must not fall below 10%.")
        if pct > _MAX_SAVINGS:
            raise ValueError("Savings rate must not exceed 35%.")

        with self._uow_factory() as uow:
            obj = uow.savings_rules.get(dto.id) if dto.id else None
            obj = obj or SavingsRule()

            new_from = _norm_from(dto.valid_from)
            new_to = dto.valid_to
            if new_to is not None and new_to < new_from:
                raise ValueError("Invalid date range: 'Valid to' is before 'Valid from'.")

            for other in uow.savings_rules.list_by_employer(dto.employer_id):
                if dto.id and other.id == dto.id:
                    continue
                if not _overlaps(getattr(other, "valid_from", None), getattr(other, "valid_to", None), new_from, new_to):
                    continue

                other_from = _norm_from(getattr(other, "valid_from", None))
                if new_from > other_from:
                    other.valid_to = new_from - timedelta(days=1)
                    uow.savings_rules.upsert(other)
                else:
                    raise ValueError(
                        "Overlapping savings rate found. Please adjust 'Valid from/to' "
                        "so that the date ranges do not overlap."
                    )

            obj.employer_id = dto.employer_id
            obj.goal_id = dto.goal_id
            obj.percentage = pct
            obj.valid_from = new_from
            obj.valid_to = new_to

            uow.savings_rules.upsert(obj)
            return obj.id

    def delete_savings_rule(self, rule_id: int) -> None:
        with self._uow_factory() as uow:
            uow.savings_rules.delete(rule_id)
