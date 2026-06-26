# src/application/services/overview_service.py
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from src.application.dto.overview import (
    AccountExpenseLineVM,
    EmployerIncomeLineVM,
    LoanMonthLineVM,
    OverviewVM,
    PayoutSummaryLineVM,
    PeriodOverviewVM,
)
from src.domain.models.period import Period
from src.domain.policies.loan_policy import compute_month_status
from src.domain.policies.recurring_policy import allocated_amount
from src.domain.policies.savings_policy import calc_savings_per_employer
from src.infrastructure.db.orm_models import ExpenseGroup, LoanStatus, PayBucket, RecurringStatus, VariableStatus
from src.infrastructure.unit_of_work import UnitOfWork

_MIN_SAVINGS = Decimal("0.10")
_MAX_SAVINGS = Decimal("0.35")

_SETTINGS_RE = re.compile(r"\[\[SETTINGS(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL)


def _r2(x: Decimal) -> Decimal:
    return (x or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _contains_any(s: str, needles: list[str]) -> bool:
    ls = (s or "").lower()
    return any(n in ls for n in needles)


def _norm_from(d: date | None) -> date:
    return d or date(1900, 1, 1)


def _to_inf(d: date | None) -> date:
    return d or date.max


def _active_for(d_from: date | None, d_to: date | None, at: date) -> bool:
    return _norm_from(d_from) <= at <= _to_inf(d_to)


def _bucket_from_paybucket(pb) -> str:
    v = getattr(pb, "value", pb)
    if v == PayBucket.BEGINNING.value:
        return "BEGINNING"
    if v == PayBucket.MID.value:
        return "MID"
    return "MID"  # NONE -> MID


def _bucket_from_timing(t) -> str:
    v = getattr(t, "value", t)
    return "BEGINNING" if v == "BEGINNING" else "MID"


class OverviewService:
    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory


    def _parse_settings(self, notes: str | None) -> dict[str, str]:
        if not notes:
            return {}
        m = _SETTINGS_RE.search(notes)
        if not m:
            return {}
        body = (m.group("body") or "").strip()
        out: dict[str, str] = {}
        for part in body.split():
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.strip()
        return out

    def _effective_loan_timing_for_month(self, uow, loan, year: int, month: int) -> str:
        """Determines the timing for debt allocation (BEGINNING/MID).

        Priority:
        1) Event override (timing change) in this month (if set)
        2) Loan.payment_timing
        """
        try:
            ev_month = uow.loan_events.list_for_loan_month(loan.id, year, month)
        except Exception:
            ev_month = []

        for e in ev_month or []:
            settings = self._parse_settings(getattr(e, "notes", None))
            t = settings.get("payment_timing")
            if t in {"BEGINNING", "MID"}:
                return t

        v = getattr(getattr(loan, "payment_timing", None), "value", getattr(loan, "payment_timing", "MID"))
        return "BEGINNING" if v == "BEGINNING" else "MID"

    def get_overview(self, period_current: Period, period_next: Period, view_mode: str) -> OverviewVM:
        with self._uow_factory() as uow:
            current = self._build_period(uow, period_current, view_mode)
            nxt = self._build_period(uow, period_next, view_mode)
            return OverviewVM(view_mode=view_mode, current=current, next=nxt)

    def get_year_overview(self, year: int, view_mode: str) -> PeriodOverviewVM:
        """Year overview (month=0)."""
        with self._uow_factory() as uow:
            accounts = {a.id: a for a in uow.accounts.list_all()}
            employers = {e.id: e for e in uow.employers.list_all()}
            savings_rules = list(uow.savings_rules.list_all())
            categories = {c.id: c for c in uow.expense_categories.list_all()}

            by_emp_calc: dict[int, Decimal] = {}
            by_emp_actual: dict[int, Decimal] = {}
            savings_by_emp: dict[int, Decimal] = {}
            savings_total = Decimal("0.00")

            bucket_income = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}
            bucket_savings = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}
            bucket_fix = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}
            bucket_debt = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}

            recurring_all = [r for r in uow.expense_recurring.list_all() if r.status == RecurringStatus.ACTIVE]

            for m in range(1, 13):
                at = date(year, m, 1)

                inc_fixed = uow.income_fixed.list_for_period(year, m)
                inc_hourly = uow.income_hourly.list_for_period(year, m)
                inc_special = uow.income_special.list_for_period(year, m)

                for r in inc_fixed:
                    base = r.actual_amount if (r.actual_amount or Decimal("0")) != Decimal("0.00") else r.calc_amount
                    bucket_income[_bucket_from_timing(r.payout_timing)] += base
                    by_emp_calc[r.employer_id] = by_emp_calc.get(r.employer_id, Decimal("0")) + r.calc_amount
                    by_emp_actual[r.employer_id] = by_emp_actual.get(r.employer_id, Decimal("0")) + r.actual_amount

                for r in inc_hourly:
                    base = r.actual_amount if (r.actual_amount or Decimal("0")) != Decimal("0.00") else r.calc_amount
                    bucket_income[_bucket_from_timing(r.payout_timing)] += base
                    by_emp_calc[r.employer_id] = by_emp_calc.get(r.employer_id, Decimal("0")) + r.calc_amount
                    by_emp_actual[r.employer_id] = by_emp_actual.get(r.employer_id, Decimal("0")) + r.actual_amount

                for r in inc_special:
                    base = r.actual_amount if (r.actual_amount or Decimal("0")) != Decimal("0.00") else r.amount
                    bucket_income[_bucket_from_timing(r.payout_timing)] += base

                emp_ids_m = set([r.employer_id for r in inc_fixed] + [r.employer_id for r in inc_hourly])
                for emp_id in emp_ids_m:
                    calc_m = sum((x.calc_amount for x in inc_fixed if x.employer_id == emp_id), Decimal("0")) + sum(
                        (x.calc_amount for x in inc_hourly if x.employer_id == emp_id), Decimal("0")
                    )
                    act_m = sum((x.actual_amount for x in inc_fixed if x.employer_id == emp_id), Decimal("0")) + sum(
                        (x.actual_amount for x in inc_hourly if x.employer_id == emp_id), Decimal("0")
                    )
                    base_m = act_m if act_m != Decimal("0.00") else calc_m
                    if base_m == Decimal("0.00"):
                        continue

                    pct = self._savings_pct_for_employer(savings_rules, emp_id, at)
                    sav_amt = calc_savings_per_employer([(emp_id, "", base_m)], pct)[0].savings_amount
                    savings_by_emp[emp_id] = savings_by_emp.get(emp_id, Decimal("0")) + sav_amt
                    savings_total += sav_amt

                    bucket = _bucket_from_timing(getattr(employers.get(emp_id), "payout_timing", "MID"))
                    bucket_savings[bucket] += sav_amt

                # recurring split (fixed vs debt)
                for r in recurring_all:
                    amt = allocated_amount(
                        amount=r.amount,
                        frequency_months=r.frequency_months,
                        period=Period(year, m),
                        anchor_month=r.anchor_month,
                        global_view_mode=view_mode,
                        override=r.allocation_override.value if r.allocation_override else None,
                    )
                    bucket = _bucket_from_paybucket(getattr(r, "pay_bucket", PayBucket.NONE))
                    cat = categories.get(r.category_id)
                    group = getattr(getattr(cat, "group", None), "value", None) if cat else None
                    if group == ExpenseGroup.LOAN.value:
                        bucket_debt[bucket] += amt
                    else:
                        bucket_fix[bucket] += amt

                # variable expenses -> treated as debts/special expenses in the payout summary
                vars_ = [v for v in uow.expense_variable.list_for_period(year, m) if v.status != VariableStatus.CANCELLED]
                for v in vars_:
                    bucket = _bucket_from_paybucket(getattr(v, "pay_bucket", PayBucket.NONE))
                    bucket_debt[bucket] += (v.amount or Decimal("0"))

            # loans for year summary (payment+extra aggregated)
            loan_lines, loan_debt_bucket = self._build_loan_year_lines(uow, year)
            bucket_debt["BEGINNING"] += loan_debt_bucket.get("BEGINNING", Decimal("0.00"))
            bucket_debt["MID"] += loan_debt_bucket.get("MID", Decimal("0.00"))

            incomes_vm: list[EmployerIncomeLineVM] = []
            emp_ids = sorted(set(by_emp_calc.keys()) | set(by_emp_actual.keys()))
            for emp_id in emp_ids:
                name = employers.get(emp_id).name if emp_id in employers else f"#{emp_id}"
                calc_amt = _r2(by_emp_calc.get(emp_id, Decimal("0")))
                actual_amt = _r2(by_emp_actual.get(emp_id, Decimal("0")))
                sav_amt = _r2(savings_by_emp.get(emp_id, Decimal("0")))
                incomes_vm.append(
                    EmployerIncomeLineVM(
                        employer_id=emp_id,
                        employer_name=name,
                        calc_amount=calc_amt,
                        actual_amount=actual_amt,
                        savings_amount=sav_amt,
                    )
                )
            incomes_vm.sort(key=lambda x: x.employer_name.lower())

            # account totals
            fix_by_acc: dict[int, Decimal] = {}
            abo_sum = Decimal("0.00")
            ins_sum = Decimal("0.00")
            other_fix = Decimal("0.00")

            for r in recurring_all:
                cat = categories.get(r.category_id)
                group = getattr(getattr(cat, "group", None), "value", None) if cat else None
                if group == ExpenseGroup.LOAN.value:
                    continue
                total = Decimal("0.00")
                for m in range(1, 13):
                    total += allocated_amount(
                        amount=r.amount,
                        frequency_months=r.frequency_months,
                        period=Period(year, m),
                        anchor_month=r.anchor_month,
                        global_view_mode=view_mode,
                        override=r.allocation_override.value if r.allocation_override else None,
                    )
                total = _r2(total)
                fix_by_acc[r.account_id] = fix_by_acc.get(r.account_id, Decimal("0")) + total

                if _contains_any(r.name, ["abo", "netflix", "spotify", "prime", "vertrag"]):
                    abo_sum += total
                elif _contains_any(r.name, ["versicherung", "haftpflicht", "kranken", "kfz"]):
                    ins_sum += total
                else:
                    other_fix += total

            var_by_acc: dict[int, Decimal] = {}
            var_total = Decimal("0.00")
            for m in range(1, 13):
                vars_ = [v for v in uow.expense_variable.list_for_period(year, m) if v.status != VariableStatus.CANCELLED]
                for v in vars_:
                    if v.account_id:
                        var_by_acc[v.account_id] = var_by_acc.get(v.account_id, Decimal("0")) + v.amount
                    var_total += v.amount

            fix_total = sum(fix_by_acc.values(), Decimal("0.00"))
            var_total = _r2(var_total)

            acc_lines: list[AccountExpenseLineVM] = []
            for acc_id, acc in accounts.items():
                fix_amt = _r2(fix_by_acc.get(acc_id, Decimal("0.00")))
                var_amt = _r2(var_by_acc.get(acc_id, Decimal("0.00")))
                fix_share = _r2((fix_amt / fix_total * Decimal("100")) if fix_total > 0 else Decimal("0.00"))
                var_share = _r2((var_amt / var_total * Decimal("100")) if var_total > 0 else Decimal("0.00"))
                acc_lines.append(
                    AccountExpenseLineVM(
                        account_id=acc_id,
                        account_label=acc.label,
                        fix_amount=fix_amt,
                        variable_amount=var_amt,
                        fix_share_pct=fix_share,
                        variable_share_pct=var_share,
                    )
                )
            acc_lines.sort(key=lambda x: x.account_label.lower())

            payout_summary = self._build_payout_summary(bucket_income, bucket_savings, bucket_debt, bucket_fix)

            return PeriodOverviewVM(
                year=year,
                month=0,
                incomes=incomes_vm,
                savings_total=_r2(savings_total),
                accounts=acc_lines,
                loans=loan_lines,
                recurring_abos=_r2(abo_sum),
                recurring_insurance=_r2(ins_sum),
                recurring_other_fix=_r2(other_fix),
                variable_total=_r2(var_total),
                payout_summary=payout_summary,
            )

    def _build_loan_year_lines(self, uow, year: int) -> tuple[list[LoanMonthLineVM], dict[str, Decimal]]:
        loans = uow.loans.list_all()
        out: list[LoanMonthLineVM] = []
        debt_bucket = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}

        for loan in loans:
            if loan.status == LoanStatus.CLOSED and not self._has_event_in_year(uow, loan.id, year):
                continue

            events_until_jan = uow.loan_events.list_for_loan_until(loan.id, Period(year, 1))
            ev_dicts_jan = [
                {"event_type": e.event_type.value, "year": e.year, "month": e.month, "amount": e.amount, "new_regular_payment": e.new_regular_payment}
                for e in events_until_jan
            ]
            st_jan = compute_month_status(
                principal_initial=loan.principal_initial,
                regular_payment=loan.regular_payment,
                events=ev_dicts_jan,
                year=year,
                month=1,
            )

            events_until_dez = uow.loan_events.list_for_loan_until(loan.id, Period(year, 12))
            ev_dicts_dez = [
                {"event_type": e.event_type.value, "year": e.year, "month": e.month, "amount": e.amount, "new_regular_payment": e.new_regular_payment}
                for e in events_until_dez
            ]
            st_dez = compute_month_status(
                principal_initial=loan.principal_initial,
                regular_payment=loan.regular_payment,
                events=ev_dicts_dez,
                year=year,
                month=12,
            )

            payment_sum = Decimal("0.00")
            extra_sum = Decimal("0.00")
            for mth in range(1, 13):
                events = uow.loan_events.list_for_loan_until(loan.id, Period(year, mth))
                ev_dicts = [
                    {"event_type": e.event_type.value, "year": e.year, "month": e.month, "amount": e.amount, "new_regular_payment": e.new_regular_payment}
                    for e in events
                ]
                st_m = compute_month_status(
                    principal_initial=loan.principal_initial,
                    regular_payment=loan.regular_payment,
                    events=ev_dicts,
                    year=year,
                    month=mth,
                )
                payment_sum += st_m.payment
                extra_sum += st_m.extra

                timing = self._effective_loan_timing_for_month(uow, loan, year, mth)
                debt_bucket[timing] += (st_m.payment + st_m.extra)

            out.append(
                LoanMonthLineVM(
                    loan_id=loan.id,
                    loan_name=loan.name,
                    open_before=_r2(st_jan.open_before),
                    payment=_r2(payment_sum),
                    extra=_r2(extra_sum),
                    open_after=_r2(st_dez.open_after),
                )
            )

        out.sort(key=lambda x: x.loan_name.lower())
        debt_bucket["BEGINNING"] = _r2(debt_bucket["BEGINNING"])
        debt_bucket["MID"] = _r2(debt_bucket["MID"])
        return out, debt_bucket


    def _has_event_in_year(self, uow, loan_id: int, year: int) -> bool:
        for m in range(1, 13):
            if uow.loan_events.list_for_loan_month(loan_id, year, m):
                return True
        return False

    def _build_period(self, uow, period: Period, view_mode: str) -> PeriodOverviewVM:
        accounts = {a.id: a for a in uow.accounts.list_all()}
        employers = {e.id: e for e in uow.employers.list_all()}
        savings_rules = list(uow.savings_rules.list_all())
        categories = {c.id: c for c in uow.expense_categories.list_all()}

        inc_fixed = uow.income_fixed.list_for_period(period.year, period.month)
        inc_hourly = uow.income_hourly.list_for_period(period.year, period.month)
        inc_special = uow.income_special.list_for_period(period.year, period.month)

        by_emp_calc: dict[int, Decimal] = {}
        by_emp_actual: dict[int, Decimal] = {}

        for r in inc_fixed:
            by_emp_calc[r.employer_id] = by_emp_calc.get(r.employer_id, Decimal("0")) + r.calc_amount
            by_emp_actual[r.employer_id] = by_emp_actual.get(r.employer_id, Decimal("0")) + r.actual_amount

        for r in inc_hourly:
            by_emp_calc[r.employer_id] = by_emp_calc.get(r.employer_id, Decimal("0")) + r.calc_amount
            by_emp_actual[r.employer_id] = by_emp_actual.get(r.employer_id, Decimal("0")) + r.actual_amount

        at = date(period.year, period.month, 1)

        incomes_vm: list[EmployerIncomeLineVM] = []
        savings_total = Decimal("0.00")
        bucket_savings = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}

        emp_ids = sorted(set(by_emp_calc.keys()) | set(by_emp_actual.keys()))
        for emp_id in emp_ids:
            name = employers.get(emp_id).name if emp_id in employers else f"#{emp_id}"
            calc_amt = _r2(by_emp_calc.get(emp_id, Decimal("0")))
            actual_amt = _r2(by_emp_actual.get(emp_id, Decimal("0")))
            savings_base = actual_amt if actual_amt != Decimal("0.00") else calc_amt

            pct = self._savings_pct_for_employer(savings_rules, emp_id, at)
            savings_line = calc_savings_per_employer([(emp_id, name, savings_base)], pct)[0]
            savings_total += savings_line.savings_amount

            bucket = _bucket_from_timing(getattr(employers.get(emp_id), "payout_timing", "MID"))
            bucket_savings[bucket] += savings_line.savings_amount

            incomes_vm.append(
                EmployerIncomeLineVM(
                    employer_id=emp_id,
                    employer_name=name,
                    calc_amount=_r2(calc_amt),
                    actual_amount=_r2(actual_amt),
                    savings_amount=_r2(savings_line.savings_amount),
                )
            )
        incomes_vm.sort(key=lambda x: x.employer_name.lower())

        recurring = [r for r in uow.expense_recurring.list_all() if r.status == RecurringStatus.ACTIVE]
        vars_ = [v for v in uow.expense_variable.list_for_period(period.year, period.month) if v.status != VariableStatus.CANCELLED]

        fix_by_acc: dict[int, Decimal] = {}
        abo_sum = Decimal("0.00")
        ins_sum = Decimal("0.00")
        other_fix = Decimal("0.00")

        for r in recurring:
            amt = allocated_amount(
                amount=r.amount,
                frequency_months=r.frequency_months,
                period=period,
                anchor_month=r.anchor_month,
                global_view_mode=view_mode,
                override=r.allocation_override.value if r.allocation_override else None,
            )
            cat = categories.get(r.category_id)
            group = getattr(getattr(cat, "group", None), "value", None) if cat else None
            if group == ExpenseGroup.LOAN.value:
                # LOAN-category recurring are tracked as debts in the payout summary,
                # not as fixed costs — exclude them from the Fixkosten account breakdown.
                continue
            fix_by_acc[r.account_id] = fix_by_acc.get(r.account_id, Decimal("0")) + amt

            if _contains_any(r.name, ["abo", "netflix", "spotify", "prime", "vertrag"]):
                abo_sum += amt
            elif _contains_any(r.name, ["versicherung", "haftpflicht", "kranken", "kfz"]):
                ins_sum += amt
            else:
                other_fix += amt

        var_by_acc: dict[int, Decimal] = {}
        var_total = Decimal("0.00")
        for v in vars_:
            if v.account_id:
                var_by_acc[v.account_id] = var_by_acc.get(v.account_id, Decimal("0")) + v.amount
            var_total += v.amount

        fix_total = sum(fix_by_acc.values(), Decimal("0.00"))
        var_total = _r2(var_total)

        acc_lines: list[AccountExpenseLineVM] = []
        for acc_id, acc in accounts.items():
            fix_amt = _r2(fix_by_acc.get(acc_id, Decimal("0.00")))
            var_amt = _r2(var_by_acc.get(acc_id, Decimal("0.00")))
            fix_share = _r2((fix_amt / fix_total * Decimal("100")) if fix_total > 0 else Decimal("0.00"))
            var_share = _r2((var_amt / var_total * Decimal("100")) if var_total > 0 else Decimal("0.00"))
            acc_lines.append(
                AccountExpenseLineVM(
                    account_id=acc_id,
                    account_label=acc.label,
                    fix_amount=fix_amt,
                    variable_amount=var_amt,
                    fix_share_pct=fix_share,
                    variable_share_pct=var_share,
                )
            )
        acc_lines.sort(key=lambda x: x.account_label.lower())

        loan_lines, loan_debt_bucket = self._build_loan_month_lines(uow, period)

        # -------- payout summary (BEGINNING / MID) --------
        bucket_income = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}
        for r in inc_fixed:
            base = r.actual_amount if (r.actual_amount or Decimal("0")) != Decimal("0.00") else r.calc_amount
            bucket_income[_bucket_from_timing(r.payout_timing)] += base
        for r in inc_hourly:
            base = r.actual_amount if (r.actual_amount or Decimal("0")) != Decimal("0.00") else r.calc_amount
            bucket_income[_bucket_from_timing(r.payout_timing)] += base
        for r in inc_special:
            base = r.actual_amount if (r.actual_amount or Decimal("0")) != Decimal("0.00") else r.amount
            bucket_income[_bucket_from_timing(r.payout_timing)] += base

        bucket_fix = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}
        bucket_debt = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}

        for r in recurring:
            amt = allocated_amount(
                amount=r.amount,
                frequency_months=r.frequency_months,
                period=period,
                anchor_month=r.anchor_month,
                global_view_mode=view_mode,
                override=r.allocation_override.value if r.allocation_override else None,
            )
            bucket = _bucket_from_paybucket(getattr(r, "pay_bucket", PayBucket.NONE))
            cat = categories.get(r.category_id)
            group = getattr(getattr(cat, "group", None), "value", None) if cat else None
            if group == ExpenseGroup.LOAN.value:
                bucket_debt[bucket] += amt
            else:
                bucket_fix[bucket] += amt

        for v in vars_:
            # variable expenses are tracked as special expenses/"debts" in the payout summary
            bucket = _bucket_from_paybucket(getattr(v, "pay_bucket", PayBucket.NONE))
            bucket_debt[bucket] += (v.amount or Decimal("0"))

        # loan payments -> assigned correctly by timing (BEGINNING/MID)
        bucket_debt["BEGINNING"] += loan_debt_bucket.get("BEGINNING", Decimal("0.00"))
        bucket_debt["MID"] += loan_debt_bucket.get("MID", Decimal("0.00"))

        payout_summary = self._build_payout_summary(bucket_income, bucket_savings, bucket_debt, bucket_fix)

        return PeriodOverviewVM(
            year=period.year,
            month=period.month,
            incomes=incomes_vm,
            savings_total=_r2(savings_total),
            accounts=acc_lines,
            loans=loan_lines,
            recurring_abos=_r2(abo_sum),
            recurring_insurance=_r2(ins_sum),
            recurring_other_fix=_r2(other_fix),
            variable_total=_r2(var_total),
            payout_summary=payout_summary,
        )

    def _build_loan_month_lines(self, uow, period: Period) -> tuple[list[LoanMonthLineVM], dict[str, Decimal]]:
        loans = uow.loans.list_all()
        out: list[LoanMonthLineVM] = []
        debt_bucket = {"BEGINNING": Decimal("0.00"), "MID": Decimal("0.00")}

        for loan in loans:
            if loan.status == LoanStatus.CLOSED:
                ev_month = uow.loan_events.list_for_loan_month(loan.id, period.year, period.month)
                if not ev_month:
                    continue

            events = uow.loan_events.list_for_loan_until(loan.id, period)
            ev_dicts = [
                {"event_type": e.event_type.value, "year": e.year, "month": e.month, "amount": e.amount, "new_regular_payment": e.new_regular_payment}
                for e in events
            ]
            st = compute_month_status(
                principal_initial=loan.principal_initial,
                regular_payment=loan.regular_payment,
                events=ev_dicts,
                year=period.year,
                month=period.month,
            )
            out.append(
                LoanMonthLineVM(
                    loan_id=loan.id,
                    loan_name=loan.name,
                    open_before=st.open_before,
                    payment=st.payment,
                    extra=st.extra,
                    open_after=st.open_after,
                )
            )

            timing = self._effective_loan_timing_for_month(uow, loan, period.year, period.month)
            debt_bucket[timing] += (st.payment + st.extra)

        out.sort(key=lambda x: x.loan_name.lower())
        debt_bucket["BEGINNING"] = _r2(debt_bucket["BEGINNING"])
        debt_bucket["MID"] = _r2(debt_bucket["MID"])
        return out, debt_bucket


    def _savings_pct_for_employer(self, rules, employer_id: int, at: date) -> Decimal:
        best = None
        best_vf = date(1900, 1, 1)

        for r in rules:
            if getattr(r, "employer_id", None) != employer_id:
                continue
            vf = getattr(r, "valid_from", None)
            vt = getattr(r, "valid_to", None)
            if not _active_for(vf, vt, at):
                continue
            vf_n = _norm_from(vf)
            if vf_n >= best_vf:
                best = r
                best_vf = vf_n

        pct = getattr(best, "percentage", None) if best else None
        pct = Decimal(pct) if pct is not None else _MIN_SAVINGS
        if pct < _MIN_SAVINGS:
            pct = _MIN_SAVINGS
        if pct > _MAX_SAVINGS:
            pct = _MAX_SAVINGS
        return pct

    def _build_payout_summary(
        self,
        bucket_income: dict[str, Decimal],
        bucket_savings: dict[str, Decimal],
        bucket_debt: dict[str, Decimal],
        bucket_fix: dict[str, Decimal],
    ) -> list[PayoutSummaryLineVM]:
        out: list[PayoutSummaryLineVM] = []
        for bucket in ("BEGINNING", "MID"):
            total = _r2(bucket_income.get(bucket, Decimal("0.00")))
            sav = _r2(bucket_savings.get(bucket, Decimal("0.00")))
            debt = _r2(bucket_debt.get(bucket, Decimal("0.00")))
            fix = _r2(bucket_fix.get(bucket, Decimal("0.00")))
            free = _r2(total - sav - debt - fix)
            out.append(
                PayoutSummaryLineVM(
                    payout_timing=bucket,
                    total_income=total,
                    savings=sav,
                    debts=debt,
                    fix_costs=fix,
                    free_available=free,
                )
            )
        return out