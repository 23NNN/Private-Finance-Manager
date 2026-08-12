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

from src.application.validators.parsers import parse_bool, parse_decimal
from src.infrastructure.db.orm_models import (
    Account,
    AllocationOverride,
    Employer,
    ExpenseCategory,
    ExpenseGroup,
    ImportRun,
    PayoutTiming,
    PayRule,
    PayRuleType,
    PayRuleUnit,
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
    _UNSUPPORTED_CSV_DATASETS = {
        "income_fixed",
        "income_hourly",
        "expense_recurring",
        "expense_variable",
        "loans",
        "loan_events",
    }

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

            def ensure_employer(name: str) -> Employer:
                nm = (name or "").strip() or "Arbeitgeber"
                if nm in emp_by_name:
                    return emp_by_name[nm]
                obj = Employer(name=nm, payout_timing=PayoutTiming.MID)
                uow.employers.upsert(obj)
                emp_by_name[nm] = obj
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

        return base
