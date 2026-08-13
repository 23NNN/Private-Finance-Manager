# finanzmanager/application/services/import_service.py
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

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
    PayoutTiming,
    PayRule,
    PayRuleType,
    PayRuleUnit,
    RecurringStatus,
    VariableStatus,
)
from src.infrastructure.io.csv_reader import read_csv_dicts
from src.infrastructure.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class ImportIssue:
    dataset: str
    row: int
    field: str
    value: str
    message: str


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _keynorm(k: str) -> str:
    k = str(k or "").replace("\ufeff", "").strip().lower()
    k = (
        k.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    k = k.replace(" ", "_").replace("-", "_").replace("/", "_")
    k = re.sub(r"[^a-z0-9_]+", "", k)
    return k


def _rownorm(row: dict) -> dict[str, str]:
    return {_keynorm(k): _norm(v) for k, v in (row or {}).items()}


def _get(row: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        kk = _keynorm(k)
        if kk in row:
            return row.get(kk)
    return None


def _alloc_override_from_any(value: Any) -> AllocationOverride | None:
    s = _norm(value).lower()
    if not s or s in {"-", "—"}:
        return None
    if s == "cashflow":
        return AllocationOverride.CASHFLOW
    if s in {"budgetiert (monat)", "budgetiert_monat", "monat", "monthly", "allocate_monthly"}:
        return AllocationOverride.ALLOCATE_MONTHLY
    if s in {"budgetiert (quartal)", "budgetiert_quartal", "quartal", "quarter", "allocate_quarterly"}:
        return AllocationOverride.ALLOCATE_QUARTERLY
    raise ValueError(f"Unbekannter Override (allocation_override): {value!r}")


_RULE_TYPE_DE = {
    "stundenlohn": PayRuleType.HOURLY_WAGE,
    "festgehalt": PayRuleType.SALARY,
    "nachtzuschlag": PayRuleType.NIGHT,
    "sonntagszuschlag": PayRuleType.SUNDAY,
    "feiertagszuschlag": PayRuleType.HOLIDAY,
    "uberstunden": PayRuleType.OVERTIME,
    "ueberstunden": PayRuleType.OVERTIME,
    "überstunden": PayRuleType.OVERTIME,
}


def _rule_type_from_any(value: Any) -> PayRuleType:
    s = _norm(value)
    if not s:
        raise ValueError("Regeltyp fehlt")
    low = s.lower()
    if low in _RULE_TYPE_DE:
        return _RULE_TYPE_DE[low]
    try:
        return PayRuleType(s)
    except Exception as e:
        raise ValueError(f"Unbekannter Regeltyp: {s!r}") from e


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
    try:
        return PayRuleUnit(s)
    except Exception as e:
        raise ValueError(f"Unbekannte Einheit: {s!r}") from e


def _expense_group_from_any(value: Any) -> ExpenseGroup:
    s = _norm(value).lower()
    if not s:
        return ExpenseGroup.VARIABLE
    if s in {"fix", "fixed"}:
        return ExpenseGroup.FIX
    if s in {"variabel", "variable"}:
        return ExpenseGroup.VARIABLE
    if s in {"kredit", "loan"}:
        return ExpenseGroup.LOAN
    raise ValueError(f"Unbekannte Gruppe: {value!r}")


def _payout_timing_from_any(value: Any) -> PayoutTiming:
    s = _norm(value).lower()
    if not s:
        return PayoutTiming.MID
    if s.startswith("anfang") or s == "beginning":
        return PayoutTiming.BEGINNING
    if s.startswith("mitte") or s == "mid":
        return PayoutTiming.MID
    return PayoutTiming(_norm(value))


def _pay_bucket_from_any(value: Any) -> PayBucket:
    s = _norm(value).lower()
    if s in {"", "-", "—", "none", "kein", "keine", "nichts"}:
        return PayBucket.NONE
    if s in {"anfang", "beginning", "start"}:
        return PayBucket.BEGINNING
    if s in {"mitte", "mid"}:
        return PayBucket.MID
    return PayBucket(_norm(value))


def _recurring_status_from_any(value: Any) -> RecurringStatus:
    s = _norm(value).lower()
    if not s or s in {"active", "aktiv"}:
        return RecurringStatus.ACTIVE
    if s in {"inactive", "inaktiv"}:
        return RecurringStatus.INACTIVE
    return RecurringStatus(_norm(value).upper())


def _variable_status_from_any(value: Any) -> VariableStatus:
    s = _norm(value).lower()
    if not s or s in {"open", "offen"}:
        return VariableStatus.OPEN
    if s in {"paid", "bezahlt"}:
        return VariableStatus.PAID
    if s in {"cancelled", "canceled", "storniert"}:
        return VariableStatus.CANCELLED
    return VariableStatus(_norm(value).upper())


def _loan_status_from_any(value: Any) -> LoanStatus:
    s = _norm(value).lower()
    if not s or s in {"active", "aktiv"}:
        return LoanStatus.ACTIVE
    if s in {"closed", "geschlossen"}:
        return LoanStatus.CLOSED
    return LoanStatus(_norm(value).upper())


def _ensure_default_categories(uow: UnitOfWork) -> None:
    existing = {c.name: c for c in uow.expense_categories.list_all()}

    def ensure(name: str, group: ExpenseGroup) -> None:
        if name in existing:
            return
        uow.expense_categories.upsert(ExpenseCategory(name=name, group=group))

    ensure("Allgemein (Fix)", ExpenseGroup.FIX)
    ensure("Allgemein (Variabel)", ExpenseGroup.VARIABLE)
    ensure("Kredit", ExpenseGroup.LOAN)


class ImportService:
    CSV_DATASETS = [
        "accounts",
        "employers",
        "pay_rules",
        "categories",
        "income_fixed",
        "income_hourly",
        "expense_recurring",
        "expense_variable",
        "loans",
        "loan_events",
    ]

    # These target an older data model (e.g. name+is_active based income
    # rows) that no longer matches the current schema (period/account/FK
    # based). Fixing them requires designing a new CSV column contract per
    # dataset, not a bug fix — rejected explicitly instead of silently
    # producing wrong or crashing imports. Use the Excel import instead.
    _UNSUPPORTED_CSV_DATASETS: set[str] = set()

    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory

    def import_excel(self, path: str) -> dict:
        from src.application.importers.excel_importer import import_excel_template

        return import_excel_template(path, self._uow_factory)

    def import_csv(self, path: str, dataset: str) -> dict:
        if dataset == "expense_categories":
            dataset = "categories"
        if dataset not in self.CSV_DATASETS:
            raise ValueError(f"Unbekannter Datensatz: {dataset}")
        if dataset in self._UNSUPPORTED_CSV_DATASETS:
            raise ValueError(
                f"CSV-Import für '{dataset}' wird aktuell nicht unterstützt "
                "(Datenmodell nicht kompatibel) — bitte den Excel-Import verwenden."
            )

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(str(p))

        content = p.read_bytes()
        h = hashlib.sha256(content + dataset.encode("utf-8")).hexdigest()

        inserted = 0
        updated = 0
        skipped = 0
        issues: list[ImportIssue] = []

        with self._uow_factory() as uow:
            if uow.import_runs.exists_hash(h):
                return {"status": "skipped", "reason": "already_imported", "dataset": dataset, "issues": []}

            _ensure_default_categories(uow)

            acc_by_label = {a.label: a for a in uow.accounts.list_all()}
            emp_by_name = {e.name: e for e in uow.employers.list_all()}
            cat_by_name = {c.name: c for c in uow.expense_categories.list_all()}
            loan_by_name = {ln.name: ln for ln in uow.loans.list_all()}

            def ensure_employer(name: str) -> Employer:
                nm = (name or "").strip() or "Arbeitgeber"
                if nm in emp_by_name:
                    return emp_by_name[nm]
                obj = Employer(name=nm, payout_timing=PayoutTiming.MID)
                uow.employers.upsert(obj)
                emp_by_name[nm] = obj
                return obj

            def ensure_account(label: str) -> Account:
                lbl = (label or "").strip() or "DEFAULT"
                if lbl in acc_by_label:
                    return acc_by_label[lbl]
                obj = Account(
                    account_name=lbl,
                    label=lbl,
                    role_income=True,
                    role_debit=True,
                    notes="Auto-created by CSV import",
                )
                uow.accounts.upsert(obj)
                acc_by_label[lbl] = obj
                return obj

            def ensure_category(name: str, group: ExpenseGroup) -> ExpenseCategory:
                nm = (name or "").strip() or "Allgemein"
                if nm in cat_by_name:
                    return cat_by_name[nm]
                obj = ExpenseCategory(name=nm, group=group)
                uow.expense_categories.upsert(obj)
                cat_by_name[nm] = obj
                return obj

            def find_pay_rule(
                employer_id: int, rule_type: PayRuleType, unit: PayRuleUnit, notes: str | None
            ) -> PayRule | None:
                # simple de-dup: employer + rule_type + unit + notes (case-insensitive notes)
                s = uow._session  # MVP: ok
                stmt = (
                    select(PayRule).where(
                        PayRule.employer_id == employer_id,
                        PayRule.rule_type == rule_type,
                        PayRule.unit == unit,
                    )
                )
                cand = s.scalars(stmt).all()
                nlow = (notes or "").strip().lower()
                for c in cand:
                    clow = (c.notes or "").strip().lower()
                    if clow == nlow:
                        return c
                return None

            rows = list(read_csv_dicts(p))
            rows = [_rownorm(r) for r in rows]

            unknown_keys = set()
            allowed = self._allowed_keys(dataset)
            for r in rows:
                for k in r.keys():
                    if k not in allowed:
                        unknown_keys.add(k)

            if unknown_keys:
                issues.append(
                    ImportIssue(
                        dataset,
                        0,
                        "header",
                        ", ".join(sorted(unknown_keys)),
                        "Unbekannte Spalten erkannt (werden ignoriert).",
                    )
                )

            for row_idx, r in enumerate(rows, start=1):
                try:
                    if dataset == "accounts":
                        label = _norm(_get(r, "label", "konto", "account"))
                        if not label:
                            issues.append(
                                ImportIssue(dataset, row_idx, "label", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        account_name = _norm(_get(r, "account_name", "kontoname")) or label
                        bank_name = _norm(_get(r, "bank_name", "bank")) or None
                        iban = _norm(_get(r, "iban")) or None
                        role_income = parse_bool(_get(r, "role_income", "rolle_einnahmen"), default=True)
                        role_debit = parse_bool(_get(r, "role_debit", "rolle_ausgaben"), default=True)
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        existing = acc_by_label.get(label)
                        if existing:
                            existing.account_name = account_name
                            existing.bank_name = bank_name
                            existing.iban = iban
                            existing.role_income = role_income
                            existing.role_debit = role_debit
                            existing.notes = notes
                            updated += 1
                        else:
                            obj = Account(
                                account_name=account_name,
                                label=label,
                                bank_name=bank_name,
                                iban=iban,
                                role_income=role_income,
                                role_debit=role_debit,
                                notes=notes,
                            )
                            uow.accounts.upsert(obj)
                            acc_by_label[label] = obj
                            inserted += 1

                    elif dataset == "employers":
                        name = _norm(_get(r, "name", "arbeitgeber"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        payout_timing = _payout_timing_from_any(_get(r, "payout_timing", "auszahlung") or "mid")

                        existing = emp_by_name.get(name)
                        if existing:
                            existing.payout_timing = payout_timing
                            updated += 1
                        else:
                            obj = Employer(name=name, payout_timing=payout_timing)
                            uow.employers.upsert(obj)
                            emp_by_name[name] = obj
                            inserted += 1

                    elif dataset == "pay_rules":
                        emp_name = _norm(_get(r, "employer", "arbeitgeber", "employer_name"))
                        if not emp_name:
                            issues.append(
                                ImportIssue(
                                    dataset,
                                    row_idx,
                                    "employer_name",
                                    "",
                                    "Required field missing – row skipped.",
                                )
                            )
                            skipped += 1
                            continue
                        emp = ensure_employer(emp_name)

                        rule_type = _rule_type_from_any(_get(r, "rule_type", "regeltyp", "typ"))
                        unit = _unit_from_any(_get(r, "unit", "einheit"))
                        value = parse_decimal(_get(r, "value", "wert"), default=Decimal("0"))
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        existing = find_pay_rule(emp.id, rule_type, unit, notes)
                        if existing:
                            existing.value = value
                            existing.notes = notes
                            updated += 1
                        else:
                            uow.pay_rules.upsert(
                                PayRule(
                                    employer_id=emp.id,
                                    rule_type=rule_type,
                                    unit=unit,
                                    value=value,
                                    notes=notes,
                                )
                            )
                            inserted += 1

                    elif dataset == "categories":
                        name = _norm(_get(r, "name", "kategorie"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue
                        group = _expense_group_from_any(_get(r, "group", "gruppe") or "variabel")

                        existing = cat_by_name.get(name)
                        if existing:
                            existing.group = group
                            updated += 1
                        else:
                            obj = ExpenseCategory(name=name, group=group)
                            uow.expense_categories.upsert(obj)
                            cat_by_name[name] = obj
                            inserted += 1

                    elif dataset == "income_fixed":
                        emp_name = _norm(_get(r, "employer_name", "employer", "arbeitgeber"))
                        if not emp_name:
                            issues.append(
                                ImportIssue(
                                    dataset,
                                    row_idx,
                                    "employer_name",
                                    "",
                                    "Required field missing – row skipped.",
                                )
                            )
                            skipped += 1
                            continue
                        emp = ensure_employer(emp_name)

                        year = parse_int(_get(r, "year", "jahr"))
                        month = parse_month(_get(r, "month", "monat"))

                        base_amount = parse_decimal(_get(r, "base_amount", "grundbetrag"), default=Decimal("0"))
                        special_amount = parse_decimal(_get(r, "special_amount", "sonder"), default=Decimal("0"))
                        actual_amount = parse_decimal(_get(r, "actual_amount", "ist"), default=Decimal("0"))
                        payout_timing = _payout_timing_from_any(_get(r, "payout_timing", "auszahlung"))

                        acc_label = _norm(_get(r, "account_label", "konto"))
                        account = ensure_account(acc_label) if acc_label else None
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        existing = uow.income_fixed.get_by_emp_period(emp.id, year, month)
                        if existing:
                            existing.base_amount = base_amount
                            existing.special_amount = special_amount
                            existing.calc_amount = base_amount + special_amount
                            existing.actual_amount = actual_amount
                            existing.payout_timing = payout_timing
                            existing.account_id = account.id if account else None
                            existing.notes = notes
                            updated += 1
                        else:
                            uow.income_fixed.upsert(
                                IncomeFixed(
                                    employer_id=emp.id,
                                    year=year,
                                    month=month,
                                    base_amount=base_amount,
                                    special_amount=special_amount,
                                    calc_amount=base_amount + special_amount,
                                    actual_amount=actual_amount,
                                    payout_timing=payout_timing,
                                    account_id=account.id if account else None,
                                    notes=notes,
                                )
                            )
                            inserted += 1

                    elif dataset == "income_hourly":
                        emp_name = _norm(_get(r, "employer_name", "employer", "arbeitgeber"))
                        if not emp_name:
                            issues.append(
                                ImportIssue(
                                    dataset,
                                    row_idx,
                                    "employer_name",
                                    "",
                                    "Required field missing – row skipped.",
                                )
                            )
                            skipped += 1
                            continue
                        emp = ensure_employer(emp_name)

                        year = parse_int(_get(r, "year", "jahr"))
                        month = parse_month(_get(r, "month", "monat"))

                        hours_normal = parse_decimal(_get(r, "hours_normal", "stunden"), default=Decimal("0"))
                        night = parse_decimal(_get(r, "night", "nacht"), default=Decimal("0"))
                        sunday = parse_decimal(_get(r, "sunday", "sonntag"), default=Decimal("0"))
                        holiday = parse_decimal(_get(r, "holiday", "feiertag"), default=Decimal("0"))
                        overtime = parse_decimal(_get(r, "overtime", "ueberstunden"), default=Decimal("0"))
                        special_amount = parse_decimal(_get(r, "special_amount", "sonder"), default=Decimal("0"))
                        actual_amount = parse_decimal(_get(r, "actual_amount", "ist"), default=Decimal("0"))
                        payout_timing = _payout_timing_from_any(_get(r, "payout_timing", "auszahlung"))

                        acc_label = _norm(_get(r, "account_label", "konto"))
                        account = ensure_account(acc_label) if acc_label else None
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        existing = uow.income_hourly.get_by_emp_period(emp.id, year, month)
                        if existing:
                            existing.hours_normal = hours_normal
                            existing.night = night
                            existing.sunday = sunday
                            existing.holiday = holiday
                            existing.overtime = overtime
                            existing.special_amount = special_amount
                            existing.actual_amount = actual_amount
                            existing.payout_timing = payout_timing
                            existing.account_id = account.id if account else None
                            existing.notes = notes
                            updated += 1
                        else:
                            uow.income_hourly.upsert(
                                IncomeHourly(
                                    employer_id=emp.id,
                                    year=year,
                                    month=month,
                                    hours_normal=hours_normal,
                                    night=night,
                                    sunday=sunday,
                                    holiday=holiday,
                                    overtime=overtime,
                                    special_amount=special_amount,
                                    calc_amount=Decimal("0.00"),
                                    actual_amount=actual_amount,
                                    payout_timing=payout_timing,
                                    account_id=account.id if account else None,
                                    notes=notes,
                                )
                            )
                            inserted += 1

                    elif dataset == "expense_recurring":
                        name = _norm(_get(r, "name", "bezeichnung"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        cat_name = _norm(_get(r, "category_name", "kategorie")) or "Allgemein (Fix)"
                        category = ensure_category(cat_name, ExpenseGroup.FIX)

                        amount = parse_decimal(_get(r, "amount", "betrag"), default=Decimal("0"))
                        freq = parse_int(_get(r, "frequency_months", "intervall"), default=1)
                        if freq not in (1, 3, 12):
                            freq = 1
                        due_day = parse_int(_get(r, "due_day", "faellig", "tag"), default=1)
                        anchor_raw = _get(r, "anchor_month", "startmonat")
                        anchor_month = parse_int(anchor_raw, min_value=1, max_value=12) if _norm(anchor_raw) else None
                        status = _recurring_status_from_any(_get(r, "status"))
                        acc_label = _norm(_get(r, "account_label", "konto"))
                        account = ensure_account(acc_label)
                        pay_bucket = _pay_bucket_from_any(_get(r, "pay_bucket", "zahlungszeitpunkt"))
                        override = _alloc_override_from_any(_get(r, "allocation_override", "modusoverride"))
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        uow.expense_recurring.upsert(
                            ExpenseRecurring(
                                name=name,
                                category_id=category.id,
                                amount=amount,
                                frequency_months=freq,
                                due_day=due_day,
                                anchor_month=anchor_month,
                                status=status,
                                account_id=account.id,
                                pay_bucket=pay_bucket,
                                notes=notes,
                                allocation_override=override,
                            )
                        )
                        inserted += 1

                    elif dataset == "expense_variable":
                        name = _norm(_get(r, "name", "bezeichnung"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        cat_name = _norm(_get(r, "category_name", "kategorie")) or "Allgemein (Variabel)"
                        category = ensure_category(cat_name, ExpenseGroup.VARIABLE)

                        amount = parse_decimal(_get(r, "amount", "betrag"), default=Decimal("0"))
                        year = parse_int(_get(r, "year", "jahr"))
                        month = parse_month(_get(r, "month", "monat"))
                        status = _variable_status_from_any(_get(r, "status"))
                        acc_label = _norm(_get(r, "account_label", "konto"))
                        account = ensure_account(acc_label) if acc_label else None
                        pay_bucket = _pay_bucket_from_any(_get(r, "pay_bucket", "zahlungszeitpunkt"))
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        uow.expense_variable.upsert(
                            ExpenseVariable(
                                name=name,
                                category_id=category.id,
                                amount=amount,
                                year=year,
                                month=month,
                                status=status,
                                account_id=account.id if account else None,
                                pay_bucket=pay_bucket,
                                notes=notes,
                            )
                        )
                        inserted += 1

                    elif dataset == "loans":
                        name = _norm(_get(r, "name", "kredit"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        start_date = parse_date(_get(r, "start_date", "startdatum"))
                        principal_initial = parse_decimal(
                            _get(r, "principal_initial", "startbetrag"), default=Decimal("0")
                        )
                        annual_interest_rate = parse_decimal(
                            _get(r, "annual_interest_rate", "zinssatz"), default=Decimal("0")
                        )
                        regular_payment = parse_decimal(_get(r, "regular_payment", "rate"), default=Decimal("0"))
                        payment_timing = _payout_timing_from_any(_get(r, "payment_timing", "auszahlung"))
                        status = _loan_status_from_any(_get(r, "status"))
                        acc_label = _norm(_get(r, "account_label", "konto"))
                        account = ensure_account(acc_label)
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        existing = loan_by_name.get(name)
                        if existing:
                            existing.start_date = start_date
                            existing.principal_initial = principal_initial
                            existing.annual_interest_rate = annual_interest_rate
                            existing.regular_payment = regular_payment
                            existing.payment_timing = payment_timing
                            existing.account_id = account.id
                            existing.status = status
                            existing.notes = notes
                            updated += 1
                        else:
                            obj = Loan(
                                name=name,
                                start_date=start_date,
                                principal_initial=principal_initial,
                                annual_interest_rate=annual_interest_rate,
                                regular_payment=regular_payment,
                                payment_timing=payment_timing,
                                account_id=account.id,
                                status=status,
                                notes=notes,
                            )
                            uow.loans.upsert(obj)
                            loan_by_name[name] = obj
                            inserted += 1

                    elif dataset == "loan_events":
                        loan_name = _norm(_get(r, "loan_name", "kredit"))
                        if not loan_name:
                            issues.append(
                                ImportIssue(
                                    dataset, row_idx, "loan_name", "", "Required field missing – row skipped."
                                )
                            )
                            skipped += 1
                            continue
                        loan = loan_by_name.get(loan_name)
                        if loan is None:
                            issues.append(
                                ImportIssue(
                                    dataset,
                                    row_idx,
                                    "loan_name",
                                    loan_name,
                                    f"Kredit '{loan_name}' nicht gefunden — bitte zuerst per "
                                    "'loans'-Import oder in der UI anlegen.",
                                )
                            )
                            skipped += 1
                            continue

                        event_date = parse_date(_get(r, "event_date"))
                        year = parse_int(_get(r, "year", "jahr"))
                        month = parse_month(_get(r, "month", "monat"))

                        event_type_raw = _norm(_get(r, "event_type"))
                        if not event_type_raw:
                            issues.append(
                                ImportIssue(
                                    dataset, row_idx, "event_type", "", "Required field missing – row skipped."
                                )
                            )
                            skipped += 1
                            continue
                        event_type = LoanEventType(event_type_raw.upper())

                        amount_raw = _get(r, "amount")
                        amount = parse_decimal(amount_raw) if _norm(amount_raw) else None
                        new_payment_raw = _get(r, "new_regular_payment")
                        new_regular_payment = parse_decimal(new_payment_raw) if _norm(new_payment_raw) else None
                        new_rate_raw = _get(r, "new_annual_interest_rate")
                        new_annual_interest_rate = parse_decimal(new_rate_raw) if _norm(new_rate_raw) else None
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        uow.loan_events.upsert(
                            LoanEvent(
                                loan_id=loan.id,
                                event_date=event_date,
                                year=year,
                                month=month,
                                event_type=event_type,
                                amount=amount,
                                new_regular_payment=new_regular_payment,
                                new_annual_interest_rate=new_annual_interest_rate,
                                notes=notes,
                            )
                        )
                        inserted += 1

                    else:
                        raise ValueError(f"Nicht implementiert: {dataset}")

                except Exception as e:
                    issues.append(ImportIssue(dataset, row_idx, "row", "", f"{e} – row skipped."))
                    skipped += 1

            uow.import_runs.add(
                ImportRun(
                    filename=str(p.name),
                    file_hash=h,
                    imported_at=datetime.utcnow(),
                )
            )

        return {
            "status": "ok",
            "dataset": dataset,
            "rows": len(rows),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "issues": issues,
        }

    def _allowed_keys(self, dataset: str) -> set[str]:
        base = {"name", "titel", "notes", "notiz"}

        if dataset == "accounts":
            return base | {
                "label",
                "konto",
                "account",
                "account_name",
                "kontoname",
                "bank_name",
                "bank",
                "iban",
                "role_income",
                "rolle_einnahmen",
                "role_debit",
                "rolle_ausgaben",
            }

        if dataset == "employers":
            return base | {"payout_timing", "auszahlung", "arbeitgeber"}

        if dataset == "pay_rules":
            return base | {
                "employer",
                "arbeitgeber",
                "employer_name",
                "rule_type",
                "regeltyp",
                "typ",
                "unit",
                "einheit",
                "value",
                "wert",
            }

        if dataset == "categories":
            return base | {"group", "gruppe", "kategorie"}

        if dataset == "income_fixed":
            return base | {
                "employer_name",
                "employer",
                "arbeitgeber",
                "year",
                "jahr",
                "month",
                "monat",
                "base_amount",
                "grundbetrag",
                "special_amount",
                "sonder",
                "actual_amount",
                "ist",
                "payout_timing",
                "auszahlung",
                "account_label",
                "konto",
            }

        if dataset == "income_hourly":
            return base | {
                "employer_name",
                "employer",
                "arbeitgeber",
                "year",
                "jahr",
                "month",
                "monat",
                "hours_normal",
                "stunden",
                "night",
                "nacht",
                "sunday",
                "sonntag",
                "holiday",
                "feiertag",
                "overtime",
                "ueberstunden",
                "special_amount",
                "sonder",
                "actual_amount",
                "ist",
                "payout_timing",
                "auszahlung",
                "account_label",
                "konto",
            }

        if dataset == "expense_recurring":
            return base | {
                "bezeichnung",
                "category_name",
                "kategorie",
                "amount",
                "betrag",
                "frequency_months",
                "intervall",
                "due_day",
                "faellig",
                "tag",
                "anchor_month",
                "startmonat",
                "status",
                "account_label",
                "konto",
                "pay_bucket",
                "zahlungszeitpunkt",
                "allocation_override",
                "modusoverride",
            }

        if dataset == "expense_variable":
            return base | {
                "bezeichnung",
                "category_name",
                "kategorie",
                "amount",
                "betrag",
                "year",
                "jahr",
                "month",
                "monat",
                "status",
                "account_label",
                "konto",
                "pay_bucket",
                "zahlungszeitpunkt",
            }

        if dataset == "loans":
            return base | {
                "kredit",
                "start_date",
                "startdatum",
                "principal_initial",
                "startbetrag",
                "annual_interest_rate",
                "zinssatz",
                "regular_payment",
                "rate",
                "payment_timing",
                "auszahlung",
                "account_label",
                "konto",
                "status",
            }

        if dataset == "loan_events":
            return base | {
                "loan_name",
                "kredit",
                "event_date",
                "year",
                "jahr",
                "month",
                "monat",
                "event_type",
                "amount",
                "new_regular_payment",
                "new_annual_interest_rate",
            }

        return base
