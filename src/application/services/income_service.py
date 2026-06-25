# src/application/services/income_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.application.dto.employers import EmployerDTO, PayRuleDTO
from src.application.dto.incomes import IncomeFixedDTO, IncomeHourlyDTO, IncomeSpecialDTO
from src.domain.policies.hourly_pay_policy import PayRule, calc_hourly_income
from src.infrastructure.db.orm_models import (
    Employer,
    IncomeFixed,
    IncomeHourly,
    IncomeSpecial,
    PayRule as PayRuleORM,
    PayoutTiming,
)
from src.infrastructure.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class _Period:
    year: int
    month: int


class IncomeService:
    """
    Income CRUD + Hourly recalculation + Special incomes.
    Hourly recalculation uses active PayRules for the selected month (valid_from/valid_to).
    """

    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory

    # -------------------- lookups --------------------
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

    # -------------------- fixed --------------------
    def list_fixed(self, period: _Period) -> list[IncomeFixedDTO]:
        with self._uow_factory() as uow:
            rows = uow.income_fixed.list_for_period(period.year, period.month)
            out: list[IncomeFixedDTO] = []
            for r in rows:
                out.append(
                    IncomeFixedDTO(
                        id=r.id,
                        employer_id=r.employer_id,
                        year=r.year,
                        month=r.month,
                        base_amount=r.base_amount,
                        special_amount=r.special_amount,
                        calc_amount=r.calc_amount,
                        actual_amount=r.actual_amount,
                        payout_timing=r.payout_timing.value,
                        account_id=r.account_id,
                        notes=r.notes,
                    )
                )
            return out

    def upsert_fixed(self, dto: IncomeFixedDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.income_fixed.get(dto.id) if dto.id else None
            if obj is None:
                obj = uow.income_fixed.get_by_emp_period(dto.employer_id, dto.year, dto.month)
            if obj is None:
                obj = IncomeFixed()

            obj.employer_id = dto.employer_id
            obj.year = dto.year
            obj.month = dto.month
            obj.base_amount = dto.base_amount
            obj.special_amount = dto.special_amount
            obj.calc_amount = (dto.base_amount + dto.special_amount)
            obj.actual_amount = dto.actual_amount
            obj.payout_timing = PayoutTiming(dto.payout_timing)
            obj.account_id = dto.account_id
            obj.notes = dto.notes

            uow.income_fixed.upsert(obj)
            return obj.id

    def delete_fixed(self, fixed_id: int) -> None:
        with self._uow_factory() as uow:
            uow.income_fixed.delete(fixed_id)

    # -------------------- hourly --------------------
    def list_hourly(self, period: _Period) -> list[IncomeHourlyDTO]:
        with self._uow_factory() as uow:
            rows = uow.income_hourly.list_for_period(period.year, period.month)
            out: list[IncomeHourlyDTO] = []
            for r in rows:
                out.append(
                    IncomeHourlyDTO(
                        id=r.id,
                        employer_id=r.employer_id,
                        year=r.year,
                        month=r.month,
                        hours_bw=r.hours_bw,
                        hours_by=r.hours_by,
                        hours_normal=r.hours_normal,
                        night_bw=r.night_bw,
                        sunday_bw=r.sunday_bw,
                        night_by=r.night_by,
                        sunday_by=r.sunday_by,
                        night=r.night,
                        sunday=r.sunday,
                        holiday=r.holiday,
                        overtime=r.overtime,
                        special_amount=r.special_amount,
                        calc_amount=r.calc_amount,
                        actual_amount=r.actual_amount,
                        payout_timing=r.payout_timing.value,
                        account_id=r.account_id,
                        notes=r.notes,
                    )
                )
            return out

    def upsert_hourly(self, dto: IncomeHourlyDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.income_hourly.get(dto.id) if dto.id else None
            if obj is None:
                obj = uow.income_hourly.get_by_emp_period(dto.employer_id, dto.year, dto.month)
            if obj is None:
                obj = IncomeHourly()

            obj.employer_id = dto.employer_id
            obj.year = dto.year
            obj.month = dto.month

            # Force legacy fields to 0 (final removal of those values)
            obj.hours_bw = Decimal("0")
            obj.hours_by = Decimal("0")
            obj.night_bw = Decimal("0")
            obj.sunday_bw = Decimal("0")
            obj.night_by = Decimal("0")
            obj.sunday_by = Decimal("0")

            # Neutral (Source of Truth)
            obj.hours_normal = dto.hours_normal
            obj.night = dto.night
            obj.sunday = dto.sunday
            obj.holiday = dto.holiday
            obj.overtime = dto.overtime

            obj.special_amount = dto.special_amount
            obj.actual_amount = dto.actual_amount
            obj.payout_timing = PayoutTiming(dto.payout_timing)
            obj.account_id = dto.account_id
            obj.notes = dto.notes

            obj.calc_amount = self._recalc_hourly_amount(uow, obj)
            uow.income_hourly.upsert(obj)
            return obj.id

    def delete_hourly(self, hourly_id: int) -> None:
        with self._uow_factory() as uow:
            uow.income_hourly.delete(hourly_id)

    def recalculate_hourly(self, hourly_id: int) -> None:
        with self._uow_factory() as uow:
            obj = uow.income_hourly.get(hourly_id)
            if obj is None:
                return
            obj.calc_amount = self._recalc_hourly_amount(uow, obj)
            uow.income_hourly.upsert(obj)

    def recalculate_hourly_for_period(self, year: int, month: int) -> int:
        with self._uow_factory() as uow:
            rows = uow.income_hourly.list_for_period(year, month)
            n = 0
            for obj in rows:
                obj.calc_amount = self._recalc_hourly_amount(uow, obj)
                uow.income_hourly.upsert(obj)
                n += 1
            return n

    # -------------------- special --------------------
    def list_special(self, period: _Period) -> list[IncomeSpecialDTO]:
        with self._uow_factory() as uow:
            rows = uow.income_special.list_for_period(period.year, period.month)
            out: list[IncomeSpecialDTO] = []
            for r in rows:
                out.append(
                    IncomeSpecialDTO(
                        id=r.id,
                        year=r.year,
                        month=r.month,
                        name=r.name,
                        amount=r.amount,
                        actual_amount=r.actual_amount,
                        payout_timing=r.payout_timing.value,
                        account_id=r.account_id,
                        notes=r.notes,
                    )
                )
            return out

    def list_special_for_year(self, year: int) -> list[IncomeSpecialDTO]:
        with self._uow_factory() as uow:
            rows = uow.income_special.list_for_year(year)
            out: list[IncomeSpecialDTO] = []
            for r in rows:
                out.append(
                    IncomeSpecialDTO(
                        id=r.id,
                        year=r.year,
                        month=r.month,
                        name=r.name,
                        amount=r.amount,
                        actual_amount=r.actual_amount,
                        payout_timing=r.payout_timing.value,
                        account_id=r.account_id,
                        notes=r.notes,
                    )
                )
            return out

    def upsert_special(self, dto: IncomeSpecialDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.income_special.get(dto.id) if dto.id else None
            obj = obj or IncomeSpecial()

            obj.year = dto.year
            obj.month = dto.month
            obj.name = dto.name
            obj.amount = dto.amount
            obj.actual_amount = dto.actual_amount
            obj.payout_timing = PayoutTiming(dto.payout_timing)
            obj.account_id = dto.account_id
            obj.notes = dto.notes

            uow.income_special.upsert(obj)
            return obj.id

    def move_special(self, special_id: int, new_year: int, new_month: int) -> None:
        with self._uow_factory() as uow:
            obj = uow.income_special.get(special_id)
            if not obj:
                return
            obj.year = new_year
            obj.month = new_month
            uow.income_special.upsert(obj)

    def delete_special(self, special_id: int) -> None:
        with self._uow_factory() as uow:
            uow.income_special.delete(special_id)

    # -------------------- internals --------------------
    def _recalc_hourly_amount(self, uow: UnitOfWork, obj: IncomeHourly) -> Decimal:
        at = date(int(obj.year), int(obj.month), 1)
        try:
            rules_orm: list[PayRuleORM] = uow.pay_rules.list_active_for_date(obj.employer_id, at)
        except Exception:
            rules_orm = uow.pay_rules.list_by_employer(obj.employer_id)

        best: dict[str, PayRuleORM] = {}
        for r in rules_orm:
            rt = r.rule_type.value
            vf = getattr(r, "valid_from", date(1900, 1, 1)) or date(1900, 1, 1)
            cur = best.get(rt)
            if cur is None:
                best[rt] = r
            else:
                cur_vf = getattr(cur, "valid_from", date(1900, 1, 1)) or date(1900, 1, 1)
                if vf > cur_vf:
                    best[rt] = r

        rules = [PayRule(rule_type=r.rule_type.value, value=r.value, unit=r.unit.value) for r in best.values()]

        # Legacy BW/BY is neutralised (rollup)
        hours_normal = (obj.hours_normal or Decimal("0")) + (obj.hours_bw or Decimal("0")) + (obj.hours_by or Decimal("0"))
        night = (obj.night or Decimal("0")) + (obj.night_bw or Decimal("0")) + (obj.night_by or Decimal("0"))
        sunday = (obj.sunday or Decimal("0")) + (obj.sunday_bw or Decimal("0")) + (obj.sunday_by or Decimal("0"))

        # Fix: calc_hourly_income(rules, hours_dict) – no keyword args!
        amount = calc_hourly_income(
            rules,
            {
                "hours_normal": hours_normal,
                "night": night,
                "sunday": sunday,
                "holiday": (obj.holiday or Decimal("0")),
                "overtime": (obj.overtime or Decimal("0")),
            },
        )
        return (amount or Decimal("0")) + (obj.special_amount or Decimal("0"))