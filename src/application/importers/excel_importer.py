# application/importers/excel_importer.py
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.application.validators.parsers import parse_bool, parse_date, parse_decimal, parse_int, parse_month
from src.infrastructure.db.orm_models import (
    Account,
    AllocationOverride,
    Employer,
    ExpenseCategory,
    ExpenseGroup,
    ExpenseRecurring,
    ExpenseVariable,
    ImportRun,
    IncomeFixed,
    IncomeHourly,
    Loan,
    LoanEvent,
    LoanEventType,
    LoanStatus,
    PayBucket,
    PayRule,
    PayRuleType,
    PayRuleUnit,
    PaymentTiming,
    PayoutTiming,
    RecurringStatus,
    VariableStatus,
)
from src.infrastructure.io.excel_reader import list_sheets, read_sheet_dicts
from src.infrastructure.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportIssue:
    dataset: str
    sheet: str
    row: int
    field: str
    value: str
    message: str


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _pay_bucket_from_any(value: Any) -> PayBucket:
    s = _norm(value).lower()
    if s in {"", "-", "—", "none", "kein", "keine", "nichts"}:
        return PayBucket.NONE
    if s in {"anfang", "beginning", "start"}:
        return PayBucket.BEGINNING
    if s in {"mitte", "mid"}:
        return PayBucket.MID
    return PayBucket(_norm(value))


def _alloc_override_from_any(value: Any) -> AllocationOverride | None:
    s = _norm(value).lower()
    if not s or s in {"-", "—"}:
        return None
    if s in {"cashflow"}:
        return AllocationOverride.CASHFLOW
    if s in {"budgetiert (monat)", "budgetiert_monat", "monat", "monthly", "allocate_monthly"}:
        return AllocationOverride.ALLOCATE_MONTHLY
    if s in {"budgetiert (quartal)", "budgetiert_quartal", "quartal", "quarter", "allocate_quarterly"}:
        return AllocationOverride.ALLOCATE_QUARTERLY
    return AllocationOverride(_norm(value))


_RULE_TYPE_DE = {
    "stundenlohn": PayRuleType.HOURLY_WAGE,
    "festgehalt": PayRuleType.SALARY,
    "nachtzuschlag": PayRuleType.NIGHT,
    "sonntagszuschlag": PayRuleType.SUNDAY,
    "feiertagszuschlag": PayRuleType.HOLIDAY,
    "überstunden": PayRuleType.OVERTIME,
    "ueberstunden": PayRuleType.OVERTIME,
}


def _rule_type_from_any(value: Any) -> PayRuleType:
    s = _norm(value)
    if not s:
        raise ValueError("Regeltyp fehlt")
    low = s.lower()
    if low in _RULE_TYPE_DE:
        return _RULE_TYPE_DE[low]
    return PayRuleType(s)


def _unit_from_any(value: Any) -> PayRuleUnit:
    s = _norm(value)
    if not s:
        raise ValueError("Einheit fehlt")
    low = s.lower()
    if low in {"eur_pro_stunde", "eur/stunde", "eur_per_hour", "eurperhour"}:
        return PayRuleUnit.EUR_PER_HOUR
    if low in {"eur_pro_monat", "eur/monat", "eur_per_month", "eurpermonth"}:
        return PayRuleUnit.EUR_PER_MONTH
    if low in {"multiplikator", "multiplier"}:
        return PayRuleUnit.MULTIPLIER
    return PayRuleUnit(s)


def _ensure_default_categories(uow: UnitOfWork) -> None:
    existing = {c.name: c for c in uow.categories.list_all()}

    def ensure(name: str, group: ExpenseGroup) -> None:
        if name in existing:
            return
        uow.categories.upsert(ExpenseCategory(name=name, group=group))

    ensure("Allgemein (Fix)", ExpenseGroup.FIX)
    ensure("Allgemein (Variabel)", ExpenseGroup.VARIABLE)
    ensure("Kredit", ExpenseGroup.LOAN)


def import_excel_template(path: str, uow_factory=UnitOfWork) -> dict:
    """
    Best-effort import of the Excel template.
    Rows with unknown/invalid values are skipped and returned as issues.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    content = p.read_bytes()
    file_hash = hashlib.sha256(content + b":excel").hexdigest()

    issues: list[ImportIssue] = []
    stats = {
        "accounts": 0,
        "employers": 0,
        "pay_rules": 0,
        "income_fixed": 0,
        "income_hourly": 0,
        "expense_recurring": 0,
        "expense_variable": 0,
        "loans": 0,
        "loan_events": 0,
    }

    with uow_factory() as uow:
        if uow.import_runs.exists_hash(file_hash):
            return {
                "status": "skipped",
                "reason": "already_imported",
                "source": str(p.name),
                "issues": [],
            }

        _ensure_default_categories(uow)

        acc_by_label = {a.label: a for a in uow.accounts.list_all()}
        emp_by_name = {e.name: e for e in uow.employers.list_all()}
        cat_by_name = {c.name: c for c in uow.categories.list_all()}
        loan_by_name = {l.name: l for l in uow.loans.list_all()}

        def ensure_account(label: str) -> Account:
            label = (label or "").strip() or "DEFAULT"
            if label in acc_by_label:
                return acc_by_label[label]
            obj = Account(
                account_name=label,
                label=label,
                bank_name=None,
                iban=None,
                role_income=True,
                role_debit=True,
                notes="Auto-created by Excel import",
            )
            uow.accounts.upsert(obj)
            acc_by_label[obj.label] = obj
            return obj

        def get_account_id(label: Any) -> int | None:
            lbl = _norm(label)
            if not lbl:
                return None
            return ensure_account(lbl).id

        def ensure_employer(name: Any) -> Employer:
            n = _norm(name)
            if n in emp_by_name:
                return emp_by_name[n]
            obj = Employer(name=n, payout_timing=PayoutTiming.MID, default_account_id=None, notes=None)
            uow.employers.upsert(obj)
            emp_by_name[obj.name] = obj
            return obj

        def ensure_category(name: Any, group: ExpenseGroup) -> ExpenseCategory:
            n = _norm(name) or ("Allgemein (Fix)" if group == ExpenseGroup.FIX else "Allgemein (Variabel)")
            if n in cat_by_name:
                return cat_by_name[n]
            obj = ExpenseCategory(name=n, group=group)
            uow.categories.upsert(obj)
            cat_by_name[obj.name] = obj
            return obj

        def ensure_loan(name: Any) -> Loan:
            n = _norm(name)
            if n in loan_by_name:
                return loan_by_name[n]
            acc = ensure_account("DEFAULT")
            obj = Loan(
                name=n,
                start_date=date.today(),
                principal_initial=Decimal("0"),
                annual_interest_rate=Decimal("0"),
                regular_payment=Decimal("0"),
                payment_timing=PaymentTiming.MID,
                account_id=acc.id,
                status=LoanStatus.ACTIVE,
                notes="Auto-created by Excel import",
            )
            uow.loans.upsert(obj)
            loan_by_name[obj.name] = obj
            return obj

        existing_sheets = set(list_sheets(p))

        def read_sheet(sheet: str) -> list[dict[str, Any]]:
            if sheet not in existing_sheets:
                return []
            return read_sheet_dicts(p, sheet, header_row=1)

        # Accounts
        for i, row in enumerate(read_sheet("Konten"), start=2):
            try:
                label = _norm(_pick(row, "label", "Label", "Kürzel", "Kurz"))
                if not label:
                    continue
                obj = acc_by_label.get(label) or Account()
                obj.label = label
                obj.account_name = _norm(_pick(row, "account_name", "Kontoname", "Name")) or label
                obj.bank_name = _norm(_pick(row, "bank_name", "Bank")) or None
                obj.iban = _norm(_pick(row, "iban", "IBAN")) or None
                obj.role_income = parse_bool(_pick(row, "role_income", "Einnahmen", "Income"), default=True)
                obj.role_debit = parse_bool(_pick(row, "role_debit", "Ausgaben", "Debit"), default=True)
                obj.notes = _norm(_pick(row, "notes", "Notiz", "Notizen")) or None
                uow.accounts.upsert(obj)
                acc_by_label[obj.label] = obj
                stats["accounts"] += 1
            except Exception as e:
                issues.append(ImportIssue("accounts", "Konten", i, "", "", f"{e} – row skipped."))
                continue

        # Infos (employers + rules - heuristic)
        for i, row in enumerate(read_sheet("Infos"), start=2):
            try:
                emp_name = _norm(_pick(row, "employer", "Employer", "Arbeitgeber", "Firma", "Name"))
                if not emp_name:
                    continue
                emp = ensure_employer(emp_name)

                timing_raw = _norm(_pick(row, "payout_timing", "Auszahlung", "Timing", "Payout"))
                if timing_raw:
                    t = timing_raw.lower()
                    emp.payout_timing = PayoutTiming.BEGINNING if t in {"anfang", "beginning"} else PayoutTiming.MID

                default_acc = _norm(_pick(row, "default_account", "Standardkonto", "Konto"))
                if default_acc:
                    emp.default_account_id = get_account_id(default_acc)

                note = _norm(_pick(row, "notes", "Notiz", "Notizen"))
                if note:
                    emp.notes = note

                uow.employers.upsert(emp)
                stats["employers"] += 1

                # Pay rules: either explicit (rule_type/unit/value) or wide columns
                rt = _pick(row, "rule_type", "Regeltyp", "Typ")
                if rt:
                    pr = PayRule(
                        employer_id=emp.id,
                        rule_type=_rule_type_from_any(rt),
                        unit=_unit_from_any(_pick(row, "unit", "Einheit")),
                        value=parse_decimal(_pick(row, "value", "Wert"), default=Decimal("0")),
                        notes=_norm(_pick(row, "rule_note", "Notiz Regel", "Regelnotiz")) or None,
                    )
                    uow.pay_rules.upsert(pr)
                    stats["pay_rules"] += 1
                else:
                    wide = [
                        ("Stundenlohn", PayRuleType.HOURLY_WAGE, PayRuleUnit.EUR_PER_HOUR),
                        ("Festgehalt", PayRuleType.SALARY, PayRuleUnit.EUR_PER_MONTH),
                        ("Nachtzuschlag", PayRuleType.NIGHT, PayRuleUnit.MULTIPLIER),
                        ("Sonntagszuschlag", PayRuleType.SUNDAY, PayRuleUnit.MULTIPLIER),
                        ("Feiertagszuschlag", PayRuleType.HOLIDAY, PayRuleUnit.MULTIPLIER),
                        ("Überstunden", PayRuleType.OVERTIME, PayRuleUnit.MULTIPLIER),
                    ]
                    for col, rtype, unit in wide:
                        v = _pick(row, col)
                        if v in (None, ""):
                            continue
                        pr = PayRule(
                            employer_id=emp.id,
                            rule_type=rtype,
                            unit=unit,
                            value=parse_decimal(v, default=Decimal("0")),
                            notes=None,
                        )
                        uow.pay_rules.upsert(pr)
                        stats["pay_rules"] += 1

            except Exception as e:
                issues.append(ImportIssue("employers/pay_rules", "Infos", i, "", "", f"{e} – row skipped."))
                continue

        # Fixed income
        for i, row in enumerate(read_sheet("Einkommen_Fest"), start=2):
            try:
                emp_name = _norm(_pick(row, "Employer", "Arbeitgeber", "Firma"))
                if not emp_name:
                    continue
                emp = ensure_employer(emp_name)

                year = parse_int(_pick(row, "Jahr", "Year"))
                month = parse_month(_pick(row, "Monat", "Month"))
                base_amount = parse_decimal(_pick(row, "Grundbetrag", "Basis", "Base", "base_amount"), default=Decimal("0"))
                special_amount = parse_decimal(_pick(row, "Sonder", "Sondereinnahmen", "special_amount"), default=Decimal("0"))
                actual_amount = parse_decimal(_pick(row, "IST", "actual_amount"), default=Decimal("0"))

                timing_raw = _pick(row, "Auszahlung", "Timing", "payout_timing")
                payout_timing = PayoutTiming.BEGINNING if _norm(timing_raw).lower() in {"anfang", "beginning"} else PayoutTiming.MID

                acc_label = _pick(row, "Konto", "Account", "account_label")
                account_id = get_account_id(acc_label) if acc_label else None

                obj = uow.income_fixed.get_by_emp_period(emp.id, year, month) or IncomeFixed()
                obj.employer_id = emp.id
                obj.year = year
                obj.month = month
                obj.base_amount = base_amount
                obj.special_amount = special_amount
                obj.calc_amount = base_amount + special_amount
                obj.actual_amount = actual_amount
                obj.payout_timing = payout_timing
                obj.account_id = account_id
                obj.notes = _norm(_pick(row, "Notiz", "Notes")) or None

                uow.income_fixed.upsert(obj)
                stats["income_fixed"] += 1
            except Exception as e:
                issues.append(ImportIssue("income_fixed", "Einkommen_Fest", i, "", "", f"{e} – row skipped."))
                continue

        # Hourly income
        for i, row in enumerate(read_sheet("Einkommen_Stunden"), start=2):
            try:
                emp_name = _norm(_pick(row, "Employer", "Arbeitgeber", "Firma"))
                if not emp_name:
                    continue
                emp = ensure_employer(emp_name)

                year = parse_int(_pick(row, "Jahr", "Year"))
                month = parse_month(_pick(row, "Monat", "Month"))

                def dec(*keys: str) -> Decimal:
                    return parse_decimal(_pick(row, *keys), default=Decimal("0"))

                obj = uow.income_hourly.get_by_emp_period(emp.id, year, month) or IncomeHourly()
                obj.employer_id = emp.id
                obj.year = year
                obj.month = month

                obj.hours_normal = dec("Stunden", "Normal", "hours_normal")
                obj.night = dec("Nacht", "night")
                obj.sunday = dec("Sonntag", "sunday")
                obj.holiday = dec("Feiertag", "holiday")
                obj.overtime = dec("Überstunden", "Ueberstunden", "overtime")

                obj.special_amount = dec("Sonder", "special_amount")
                obj.actual_amount = dec("IST", "actual_amount")

                timing_raw = _pick(row, "Auszahlung", "Timing", "payout_timing")
                obj.payout_timing = PayoutTiming.BEGINNING if _norm(timing_raw).lower() in {"anfang", "beginning"} else PayoutTiming.MID

                acc_label = _pick(row, "Konto", "Account", "account_label")
                obj.account_id = get_account_id(acc_label) if acc_label else None
                obj.notes = _norm(_pick(row, "Notiz", "Notes")) or None

                obj.calc_amount = Decimal("0.00")  # will be recalculated by the system
                uow.income_hourly.upsert(obj)
                stats["income_hourly"] += 1
            except Exception as e:
                issues.append(ImportIssue("income_hourly", "Einkommen_Stunden", i, "", "", f"{e} – row skipped."))
                continue

        # Subscriptions & contracts -> recurring
        for i, row in enumerate(read_sheet("Abo & Verträge"), start=2):
            try:
                name = _norm(_pick(row, "Name", "Bezeichnung", "name"))
                if not name:
                    continue

                cat_name = _norm(_pick(row, "Kategorie", "category_name")) or "Allgemein (Fix)"
                cat = ensure_category(cat_name, ExpenseGroup.FIX)

                amount = parse_decimal(_pick(row, "Betrag", "amount"), default=Decimal("0"))
                freq = parse_int(_pick(row, "Intervall", "frequency_months"), default=1)
                due = parse_int(_pick(row, "Tag", "Fällig", "due_day"), default=1)

                anchor_raw = _norm(_pick(row, "Startmonat", "anchor_month"))
                anchor = parse_int(anchor_raw, min_value=1, max_value=12, default=None) if anchor_raw else None

                status_raw = _norm(_pick(row, "Status", "status")) or "ACTIVE"
                status = RecurringStatus(status_raw.upper() if status_raw.isalpha() else status_raw)

                acc_label = _pick(row, "Konto", "account_label")
                account_id = get_account_id(acc_label) if acc_label else ensure_account("DEFAULT").id

                pay_bucket = _pay_bucket_from_any(_pick(row, "Zahlungszeitpunkt", "pay_bucket"))
                override = _alloc_override_from_any(_pick(row, "ModusOverride", "allocation_override"))
                notes = _norm(_pick(row, "Notiz", "notes")) or None

                obj = ExpenseRecurring(
                    name=name,
                    category_id=cat.id,
                    amount=amount,
                    frequency_months=freq if freq in (1, 3, 12) else 1,
                    due_day=due,
                    anchor_month=anchor,
                    status=status,
                    account_id=account_id,
                    pay_bucket=pay_bucket,
                    allocation_override=override,
                    notes=notes,
                )
                uow.expense_recurring.upsert(obj)
                stats["expense_recurring"] += 1
            except Exception as e:
                issues.append(ImportIssue("expense_recurring", "Abo & Verträge", i, "", "", f"{e} – row skipped."))
                continue

        # Special expenses -> variable
        for i, row in enumerate(read_sheet("Sonder_Ausgaben"), start=2):
            try:
                name = _norm(_pick(row, "Name", "Bezeichnung", "name"))
                if not name:
                    continue

                cat_name = _norm(_pick(row, "Kategorie", "category_name")) or "Allgemein (Variabel)"
                cat = ensure_category(cat_name, ExpenseGroup.VARIABLE)

                amount = parse_decimal(_pick(row, "Betrag", "amount"), default=Decimal("0"))
                year = parse_int(_pick(row, "Jahr", "year"))
                month = parse_month(_pick(row, "Monat", "month"))

                status_raw = _norm(_pick(row, "Status", "status")) or "OPEN"
                st = status_raw.lower()
                if st == "bezahlt":
                    status = VariableStatus.PAID
                elif st == "storniert":
                    status = VariableStatus.CANCELLED
                else:
                    status = VariableStatus.OPEN if st in {"open", "offen"} else VariableStatus(status_raw)

                acc_label = _pick(row, "Konto", "account_label")
                account_id = get_account_id(acc_label) if acc_label else None

                pay_bucket = _pay_bucket_from_any(_pick(row, "Zahlungszeitpunkt", "pay_bucket"))
                notes = _norm(_pick(row, "Notiz", "notes")) or None

                obj = ExpenseVariable(
                    name=name,
                    category_id=cat.id,
                    amount=amount,
                    year=year,
                    month=month,
                    status=status,
                    account_id=account_id,
                    pay_bucket=pay_bucket,
                    notes=notes,
                )
                uow.expense_variable.upsert(obj)
                stats["expense_variable"] += 1
            except Exception as e:
                issues.append(ImportIssue("expense_variable", "Sonder_Ausgaben", i, "", "", f"{e} – row skipped."))
                continue

        # Loans + events (best effort)
        for i, row in enumerate(read_sheet("Kredit"), start=2):
            try:
                loan_name = _norm(_pick(row, "Kredit", "Loan", "Name"))
                if not loan_name:
                    continue
                loan = ensure_loan(loan_name)

                start_date_raw = _pick(row, "Startdatum", "start_date")
                if start_date_raw:
                    loan.start_date = parse_date(start_date_raw)

                principal = _pick(row, "Startbetrag", "principal_initial", "Betrag")
                if principal not in (None, ""):
                    loan.principal_initial = parse_decimal(principal, default=Decimal("0"))

                payment = _pick(row, "Rate", "regular_payment")
                if payment not in (None, ""):
                    loan.regular_payment = parse_decimal(payment, default=Decimal("0"))

                acc_label = _pick(row, "Konto", "account_label")
                if acc_label:
                    loan.account_id = get_account_id(acc_label) or loan.account_id

                status_raw = _norm(_pick(row, "Status", "status")) or "ACTIVE"
                loan.status = LoanStatus(status_raw)

                timing_raw = _norm(_pick(row, "Auszahlung", "payment_timing"))
                if timing_raw:
                    loan.payment_timing = PaymentTiming.BEGINNING if timing_raw.lower() in {"anfang", "beginning"} else PaymentTiming.MID

                uow.loans.upsert(loan)
                stats["loans"] += 1

                year_val = _pick(row, "Jahr", "year")
                month_val = _pick(row, "Monat", "month")
                pay_val = _pick(row, "Zahlung", "payment", "PAYMENT")
                extra_val = _pick(row, "Extra", "extra", "EXTRA")

                if year_val and month_val and (pay_val or extra_val):
                    y = parse_int(year_val)
                    m = parse_month(month_val)

                    if pay_val not in (None, ""):
                        ev = LoanEvent(
                            loan_id=loan.id,
                            event_date=date(y, m, 1),
                            year=y,
                            month=m,
                            event_type=LoanEventType.PAYMENT,
                            amount=parse_decimal(pay_val, default=Decimal("0")),
                        )
                        uow.loan_events.upsert(ev)
                        stats["loan_events"] += 1

                    if extra_val not in (None, ""):
                        ev = LoanEvent(
                            loan_id=loan.id,
                            event_date=date(y, m, 1),
                            year=y,
                            month=m,
                            event_type=LoanEventType.EXTRA_PAYMENT,
                            amount=parse_decimal(extra_val, default=Decimal("0")),
                        )
                        uow.loan_events.upsert(ev)
                        stats["loan_events"] += 1

            except Exception as e:
                issues.append(ImportIssue("loans/loan_events", "Kredit", i, "", "", f"{e} – row skipped."))
                continue

        uow.import_runs.add(ImportRun(filename=str(p.name), file_hash=file_hash, imported_at=datetime.utcnow()))

    return {
        "status": "ok",
        "source": str(p.name),
        "stats": stats,
        "issues": [issue.__dict__ for issue in issues],
    }
