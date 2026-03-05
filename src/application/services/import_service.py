# finanzmanager/application/services/import_service.py
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
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
    PayRule,
    PayRuleType,
    PayRuleUnit,
    PaymentTiming,
    PayoutTiming,
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


def _pay_bucket_from_any(value: Any) -> PayBucket:
    s = _norm(value).lower()
    if not s or s in {"-", "—", "none", "kein", "keine", "nichts"}:
        return PayBucket.NONE
    if s.startswith("anfang") or s in {"beginning", "start"}:
        return PayBucket.BEGINNING
    if s.startswith("mitte") or s == "mid":
        return PayBucket.MID
    raise ValueError(f"Unbekannter Zahlungszeitpunkt (pay_bucket): {value!r}")


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


def _recurring_status_from_any(value: Any) -> RecurringStatus:
    s = _norm(value).lower()
    if not s:
        return RecurringStatus.ACTIVE
    if s in {"aktiv", "active"}:
        return RecurringStatus.ACTIVE
    if s in {"inaktiv", "inactive"}:
        return RecurringStatus.INACTIVE
    return RecurringStatus(_norm(value))


def _variable_status_from_any(value: Any) -> VariableStatus:
    s = _norm(value).lower()
    if not s:
        return VariableStatus.OPEN
    if s in {"offen", "open"}:
        return VariableStatus.OPEN
    if s in {"bezahlt", "paid"}:
        return VariableStatus.PAID
    if s in {"storniert", "cancelled", "canceled"}:
        return VariableStatus.CANCELLED
    return VariableStatus(_norm(value))


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


def _payment_timing_from_any(value: Any) -> PaymentTiming:
    s = _norm(value).lower()
    if not s:
        return PaymentTiming.MID
    if s.startswith("anfang") or s == "beginning":
        return PaymentTiming.BEGINNING
    if s.startswith("mitte") or s == "mid":
        return PaymentTiming.MID
    return PaymentTiming(_norm(value))


_LOAN_STATUS_DE = {"aktiv": LoanStatus.ACTIVE, "geschlossen": LoanStatus.CLOSED}
_EVENT_TYPE_DE = {
    "zahlung": LoanEventType.PAYMENT,
    "extra": LoanEventType.EXTRA_PAYMENT,
    "extra_zahlung": LoanEventType.EXTRA_PAYMENT,
    "notiz": LoanEventType.NOTE,
    "rate_aenderung": LoanEventType.RATE_CHANGE,
    "zins_aenderung": LoanEventType.INTEREST_CHANGE,
}


def _loan_status_from_any(value: Any) -> LoanStatus:
    s = _norm(value).lower()
    if not s:
        return LoanStatus.ACTIVE
    if s in _LOAN_STATUS_DE:
        return _LOAN_STATUS_DE[s]
    return LoanStatus(_norm(value))


def _event_type_from_any(value: Any) -> LoanEventType:
    s = _norm(value).lower()
    if not s:
        return LoanEventType.PAYMENT
    if s in _EVENT_TYPE_DE:
        return _EVENT_TYPE_DE[s]
    return LoanEventType(_norm(value))


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
            already = uow.import_runs.get_by_file_hash(h)
            if already:
                return {"status": "skipped", "reason": "already_imported", "dataset": dataset, "issues": []}

            _ensure_default_categories(uow)

            acc_by_label = {a.label: a for a in uow.accounts.list_all()}
            emp_by_name = {e.name: e for e in uow.employers.list_all()}
            cat_by_name = {c.name: c for c in uow.expense_categories.list_all()}
            loan_by_name = {l.name: l for l in uow.loans.list_all()}

            def ensure_account(label: str) -> Account:
                lbl = (label or "").strip() or "DEFAULT"
                if lbl in acc_by_label:
                    return acc_by_label[lbl]
                obj = Account(
                    account_name=lbl,
                    label=lbl,
                    bank_name=None,
                    iban=None,
                    role_income=True,
                    role_debit=True,
                    role_savings=False,
                    opening_balance=Decimal("0"),
                    is_active=True,
                )
                uow.accounts.add(obj)
                uow.flush()
                acc_by_label[lbl] = obj
                return obj

            def ensure_employer(name: str) -> Employer:
                nm = (name or "").strip() or "Arbeitgeber"
                if nm in emp_by_name:
                    return emp_by_name[nm]
                obj = Employer(name=nm, default_bucket=PayBucket.NETTO)
                uow.employers.add(obj)
                uow.flush()
                emp_by_name[nm] = obj
                return obj

            def ensure_category(name: str, group: ExpenseGroup) -> ExpenseCategory:
                nm = (name or "").strip()
                if not nm:
                    nm = "Allgemein (Fix)" if group == ExpenseGroup.FIX else "Allgemein (Variabel)"
                if nm in cat_by_name:
                    return cat_by_name[nm]
                obj = ExpenseCategory(name=nm, group=group)
                uow.expense_categories.add(obj)
                uow.flush()
                cat_by_name[nm] = obj
                return obj

            def ensure_loan(name: str) -> Loan:
                nm = (name or "").strip() or "Kredit"
                if nm in loan_by_name:
                    return loan_by_name[nm]
                obj = Loan(
                    name=nm,
                    principal=Decimal("0"),
                    status=LoanStatus.ACTIVE,
                )
                uow.loans.add(obj)
                uow.flush()
                loan_by_name[nm] = obj
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
                        opening_balance = parse_decimal(
                            _get(r, "opening_balance", "startsaldo"), default=Decimal("0")
                        )
                        is_active = parse_bool(_get(r, "is_active", "aktiv"), default=True)
                        role_income = parse_bool(_get(r, "role_income", "rolle_einnahmen"), default=True)
                        role_debit = parse_bool(_get(r, "role_debit", "rolle_ausgaben"), default=True)
                        role_savings = parse_bool(_get(r, "role_savings", "rolle_sparen"), default=False)

                        existing = acc_by_label.get(label)
                        if existing:
                            existing.account_name = account_name
                            existing.bank_name = bank_name
                            existing.iban = iban
                            existing.opening_balance = opening_balance
                            existing.is_active = is_active
                            existing.role_income = role_income
                            existing.role_debit = role_debit
                            existing.role_savings = role_savings
                            updated += 1
                        else:
                            obj = Account(
                                account_name=account_name,
                                label=label,
                                bank_name=bank_name,
                                iban=iban,
                                role_income=role_income,
                                role_debit=role_debit,
                                role_savings=role_savings,
                                opening_balance=opening_balance,
                                is_active=is_active,
                            )
                            uow.accounts.add(obj)
                            uow.flush()
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

                        bucket = _pay_bucket_from_any(_get(r, "default_bucket", "bucket", "standard_bucket") or "none")

                        existing = emp_by_name.get(name)
                        if existing:
                            existing.default_bucket = bucket
                            updated += 1
                        else:
                            obj = Employer(name=name, default_bucket=bucket)
                            uow.employers.add(obj)
                            uow.flush()
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
                        bucket = _pay_bucket_from_any(_get(r, "bucket", "pay_bucket") or "none")
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        existing = find_pay_rule(emp.id, rule_type, unit, notes)
                        if existing:
                            existing.value = value
                            existing.bucket = bucket
                            existing.notes = notes
                            updated += 1
                        else:
                            uow.pay_rules.add(
                                PayRule(
                                    employer_id=emp.id,
                                    rule_type=rule_type,
                                    unit=unit,
                                    value=value,
                                    bucket=bucket,
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
                            uow.expense_categories.add(obj)
                            uow.flush()
                            cat_by_name[name] = obj
                            inserted += 1

                    elif dataset == "income_fixed":
                        name = _norm(_get(r, "name", "titel"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        employer_name = _norm(_get(r, "employer", "arbeitgeber")) or ""
                        employer = ensure_employer(employer_name) if employer_name else None

                        amount = parse_decimal(_get(r, "amount", "betrag"), default=Decimal("0"))
                        payout_timing = _payout_timing_from_any(_get(r, "payout_timing", "auszahlung") or "mid")
                        is_active = parse_bool(_get(r, "is_active", "aktiv"), default=True)

                        existing = uow.income_fixed.get_by_name(name)
                        if existing:
                            existing.amount = amount
                            existing.payout_timing = payout_timing
                            existing.is_active = is_active
                            existing.employer_id = employer.id if employer else None
                            updated += 1
                        else:
                            uow.income_fixed.add(
                                IncomeFixed(
                                    name=name,
                                    amount=amount,
                                    payout_timing=payout_timing,
                                    is_active=is_active,
                                    employer_id=employer.id if employer else None,
                                )
                            )
                            inserted += 1

                    elif dataset == "income_hourly":
                        name = _norm(_get(r, "name", "titel"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        employer_name = _norm(_get(r, "employer", "arbeitgeber")) or ""
                        employer = ensure_employer(employer_name) if employer_name else None

                        base_rate = parse_decimal(_get(r, "base_rate", "stundenlohn"), default=Decimal("0"))
                        payout_timing = _payout_timing_from_any(_get(r, "payout_timing", "auszahlung") or "mid")
                        is_active = parse_bool(_get(r, "is_active", "aktiv"), default=True)

                        existing = uow.income_hourly.get_by_name(name)
                        if existing:
                            existing.base_rate = base_rate
                            existing.payout_timing = payout_timing
                            existing.is_active = is_active
                            existing.employer_id = employer.id if employer else None
                            updated += 1
                        else:
                            uow.income_hourly.add(
                                IncomeHourly(
                                    name=name,
                                    base_rate=base_rate,
                                    payout_timing=payout_timing,
                                    is_active=is_active,
                                    employer_id=employer.id if employer else None,
                                )
                            )
                            inserted += 1

                    elif dataset == "expense_recurring":
                        name = _norm(_get(r, "name", "titel"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        group_name = _norm(_get(r, "group", "kategorie", "gruppe"))
                        group = ensure_category(group_name, ExpenseGroup.FIX)

                        amount = parse_decimal(_get(r, "amount", "betrag"), default=Decimal("0"))
                        payment_timing = _payment_timing_from_any(_get(r, "payment_timing", "zahlung") or "mid")
                        status = _recurring_status_from_any(_get(r, "status", "status_text") or "aktiv")
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        existing = uow.expense_recurring.get_by_name(name)
                        if existing:
                            existing.amount = amount
                            existing.payment_timing = payment_timing
                            existing.status = status
                            existing.group_id = group.id
                            existing.notes = notes
                            updated += 1
                        else:
                            uow.expense_recurring.add(
                                ExpenseRecurring(
                                    name=name,
                                    group_id=group.id,
                                    amount=amount,
                                    payment_timing=payment_timing,
                                    status=status,
                                    notes=notes,
                                )
                            )
                            inserted += 1

                    elif dataset == "expense_variable":
                        name = _norm(_get(r, "name", "titel"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        group_name = _norm(_get(r, "group", "kategorie", "gruppe"))
                        group = ensure_category(group_name, ExpenseGroup.VARIABLE)

                        amount = parse_decimal(_get(r, "amount", "betrag"), default=Decimal("0"))
                        status = _variable_status_from_any(_get(r, "status", "status_text") or "offen")
                        month = parse_month(_get(r, "month", "monat"))
                        if not month:
                            issues.append(
                                ImportIssue(dataset, row_idx, "month", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        existing = uow.expense_variable.get_by_name_month(name, month)
                        if existing:
                            existing.amount = amount
                            existing.status = status
                            existing.group_id = group.id
                            updated += 1
                        else:
                            uow.expense_variable.add(
                                ExpenseVariable(
                                    name=name,
                                    group_id=group.id,
                                    amount=amount,
                                    status=status,
                                    month=month,
                                )
                            )
                            inserted += 1

                    elif dataset == "loans":
                        name = _norm(_get(r, "name", "titel"))
                        if not name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "name", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        principal = parse_decimal(_get(r, "principal", "betrag"), default=Decimal("0"))
                        status = _loan_status_from_any(_get(r, "status") or "aktiv")
                        notes = _norm(_get(r, "notes", "notiz")) or None

                        existing = uow.loans.get_by_name(name)
                        if existing:
                            existing.principal = principal
                            existing.status = status
                            existing.notes = notes
                            updated += 1
                        else:
                            uow.loans.add(Loan(name=name, principal=principal, status=status, notes=notes))
                            inserted += 1

                    elif dataset == "loan_events":
                        loan_name = _norm(_get(r, "loan", "kredit"))
                        if not loan_name:
                            issues.append(
                                ImportIssue(dataset, row_idx, "loan", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue
                        loan = loan_by_name.get(loan_name) or ensure_loan(loan_name)

                        event_type = _event_type_from_any(_get(r, "event_type", "typ") or "zahlung")
                        amount = parse_decimal(_get(r, "amount", "betrag"), default=Decimal("0"))
                        when = parse_date(_get(r, "date", "datum"))
                        if not when:
                            issues.append(
                                ImportIssue(dataset, row_idx, "date", "", "Required field missing – row skipped.")
                            )
                            skipped += 1
                            continue

                        uow.loan_events.add(
                            LoanEvent(
                                loan_id=loan.id,
                                event_type=event_type,
                                amount=amount,
                                date=when,
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
                    file_path=str(p),
                    file_hash=h,
                    imported_at=datetime.now(),
                )
            )
            uow.commit()

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
                "opening_balance",
                "startsaldo",
                "is_active",
                "aktiv",
                "role_income",
                "rolle_einnahmen",
                "role_debit",
                "rolle_ausgaben",
                "role_savings",
                "rolle_sparen",
            }

        if dataset == "employers":
            return base | {"default_bucket", "bucket", "standard_bucket", "arbeitgeber"}

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
                "bucket",
                "pay_bucket",
            }

        if dataset == "categories":
            return base | {"group", "gruppe", "kategorie"}

        if dataset == "income_fixed":
            return base | {"employer", "arbeitgeber", "amount", "betrag", "payout_timing", "auszahlung", "is_active", "aktiv"}

        if dataset == "income_hourly":
            return base | {
                "employer",
                "arbeitgeber",
                "base_rate",
                "stundenlohn",
                "payout_timing",
                "auszahlung",
                "is_active",
                "aktiv",
            }

        if dataset == "expense_recurring":
            return base | {"group", "kategorie", "gruppe", "amount", "betrag", "payment_timing", "zahlung", "status", "status_text"}

        if dataset == "expense_variable":
            return base | {"group", "kategorie", "gruppe", "amount", "betrag", "status", "status_text", "month", "monat"}

        if dataset == "loans":
            return base | {"principal", "betrag", "status"}

        if dataset == "loan_events":
            return base | {"loan", "kredit", "event_type", "typ", "amount", "betrag", "date", "datum"}

        return base
