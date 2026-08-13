# tests/unit/test_import_service_csv.py
"""Unit tests for ImportService.import_csv().

Regression coverage for a comprehensively broken feature: every branch of
import_csv() called nonexistent repository/UnitOfWork methods
(uow.<repo>.add() instead of .upsert(), uow.flush()/uow.commit() which
don't exist) and, for 6 of 10 dataset types, constructed ORM objects with
fields that no longer exist on the current schema. Fixed the 4 dataset
types still compatible with the schema (accounts, employers, pay_rules,
categories); the other 6 are now explicitly rejected instead of silently
crashing or corrupting data.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.application.services.export_service import ExportService
from src.application.services.import_service import ImportService
from src.domain.models.period import Period
from src.infrastructure.db.engine import dispose_engine, get_engine, init_engine
from src.infrastructure.db.orm_models import Base, PayoutTiming
from src.infrastructure.unit_of_work import UnitOfWork


@pytest.fixture(autouse=True)
def _in_memory_engine():
    init_engine("sqlite:///:memory:")
    Base.metadata.create_all(get_engine())
    yield
    dispose_engine()


def _write_csv(tmp_path: Path, name: str, header: list[str], rows: list[list[str]]) -> str:
    path = tmp_path / name
    lines = [";".join(header)] + [";".join(row) for row in rows]
    path.write_text("\n".join(lines), encoding="utf-8-sig")
    return str(path)


def test_import_accounts_creates_and_then_updates(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(
        tmp_path,
        "accounts.csv",
        ["label", "account_name", "bank_name", "role_income", "role_debit"],
        [["GIRO", "Girokonto", "Sparkasse", "true", "true"]],
    )
    result = svc.import_csv(path, "accounts")
    assert result["status"] == "ok"
    assert result["inserted"] == 1
    assert result["updated"] == 0

    with UnitOfWork() as uow:
        acc = uow.accounts.get_by_label("GIRO")
        assert acc is not None
        assert acc.bank_name == "Sparkasse"

    path2 = _write_csv(
        tmp_path,
        "accounts2.csv",
        ["label", "account_name", "bank_name", "role_income", "role_debit"],
        [["GIRO", "Girokonto", "Neue Bank", "true", "false"]],
    )
    result2 = svc.import_csv(path2, "accounts")
    assert result2["inserted"] == 0
    assert result2["updated"] == 1

    with UnitOfWork() as uow:
        acc = uow.accounts.get_by_label("GIRO")
        assert acc.bank_name == "Neue Bank"
        assert acc.role_debit is False


def test_import_employers_creates_and_then_updates(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(tmp_path, "employers.csv", ["name", "payout_timing"], [["TestCo", "beginning"]])
    result = svc.import_csv(path, "employers")
    assert result["inserted"] == 1

    with UnitOfWork() as uow:
        emp = uow.employers.get_by_name("TestCo")
        assert emp is not None
        assert emp.payout_timing == PayoutTiming.BEGINNING

    path2 = _write_csv(tmp_path, "employers2.csv", ["name", "payout_timing"], [["TestCo", "mid"]])
    result2 = svc.import_csv(path2, "employers")
    assert result2["updated"] == 1

    with UnitOfWork() as uow:
        emp = uow.employers.get_by_name("TestCo")
        assert emp.payout_timing == PayoutTiming.MID


def test_import_pay_rules_auto_creates_employer(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(
        tmp_path,
        "pay_rules.csv",
        ["employer", "rule_type", "unit", "value"],
        [["NewCo", "HOURLY_WAGE", "EUR_PER_HOUR", "20.00"]],
    )
    result = svc.import_csv(path, "pay_rules")
    assert result["status"] == "ok"
    assert result["inserted"] == 1

    with UnitOfWork() as uow:
        emp = uow.employers.get_by_name("NewCo")
        assert emp is not None
        rules = uow.pay_rules.list_by_employer(emp.id)
        assert len(rules) == 1
        assert rules[0].value == Decimal("20.0000")


def test_import_categories_creates_and_then_updates(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(tmp_path, "categories.csv", ["name", "group"], [["Freizeit", "variabel"]])
    result = svc.import_csv(path, "categories")
    assert result["inserted"] == 1

    path2 = _write_csv(tmp_path, "categories2.csv", ["name", "group"], [["Freizeit", "fix"]])
    result2 = svc.import_csv(path2, "categories")
    assert result2["updated"] == 1


def test_import_csv_skips_already_imported_file(tmp_path: Path):
    svc = ImportService()
    path = _write_csv(tmp_path, "accounts.csv", ["label"], [["GIRO"]])

    first = svc.import_csv(path, "accounts")
    assert first["status"] == "ok"

    second = svc.import_csv(path, "accounts")
    assert second["status"] == "skipped"
    assert second["reason"] == "already_imported"


def test_import_income_fixed_creates_and_then_updates(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(
        tmp_path,
        "income_fixed.csv",
        ["employer_name", "year", "month", "base_amount", "special_amount", "actual_amount", "payout_timing"],
        [["Firma Beispiel", "2026", "3", "3000.00", "0.00", "0.00", "MID"]],
    )
    result = svc.import_csv(path, "income_fixed")
    assert result["status"] == "ok"
    assert result["inserted"] == 1
    assert result["updated"] == 0

    with UnitOfWork() as uow:
        emp = uow.employers.get_by_name("Firma Beispiel")
        assert emp is not None
        row = uow.income_fixed.get_by_emp_period(emp.id, 2026, 3)
        assert row is not None
        assert row.base_amount == Decimal("3000.00")
        assert row.calc_amount == Decimal("3000.00")
        assert row.payout_timing == PayoutTiming.MID

    path2 = _write_csv(
        tmp_path,
        "income_fixed2.csv",
        ["employer_name", "year", "month", "base_amount", "special_amount", "actual_amount", "payout_timing"],
        [["Firma Beispiel", "2026", "3", "3200.00", "100.00", "3300.00", "BEGINNING"]],
    )
    result2 = svc.import_csv(path2, "income_fixed")
    assert result2["inserted"] == 0
    assert result2["updated"] == 1

    with UnitOfWork() as uow:
        emp = uow.employers.get_by_name("Firma Beispiel")
        row = uow.income_fixed.get_by_emp_period(emp.id, 2026, 3)
        assert row.base_amount == Decimal("3200.00")
        assert row.calc_amount == Decimal("3300.00")
        assert row.payout_timing == PayoutTiming.BEGINNING


def test_import_income_fixed_round_trips_with_export(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(
        tmp_path,
        "income_fixed.csv",
        [
            "employer_name",
            "year",
            "month",
            "base_amount",
            "special_amount",
            "actual_amount",
            "payout_timing",
            "account_label",
        ],
        [["RoundTrip Co", "2026", "5", "2500.00", "50.00", "2550.00", "BEGINNING", "GIRO"]],
    )
    svc.import_csv(path, "income_fixed")

    export_path = str(tmp_path / "income_fixed_export.csv")
    ExportService().export_csv(export_path, "income_fixed", period=Period(2026, 5))

    result = svc.import_csv(export_path, "income_fixed")
    assert result["status"] == "ok"
    assert result["inserted"] == 0
    assert result["updated"] == 1

    with UnitOfWork() as uow:
        emp = uow.employers.get_by_name("RoundTrip Co")
        row = uow.income_fixed.get_by_emp_period(emp.id, 2026, 5)
        assert row.base_amount == Decimal("2500.00")
        assert row.special_amount == Decimal("50.00")
        assert row.actual_amount == Decimal("2550.00")
        assert row.payout_timing == PayoutTiming.BEGINNING
        acc = uow.accounts.get(row.account_id)
        assert acc.label == "GIRO"


def test_import_income_hourly_creates_and_then_updates(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(
        tmp_path,
        "income_hourly.csv",
        ["employer_name", "year", "month", "hours_normal", "night", "sunday", "holiday", "overtime"],
        [["Firma Beispiel", "2026", "4", "160", "10", "0", "0", "5"]],
    )
    result = svc.import_csv(path, "income_hourly")
    assert result["status"] == "ok"
    assert result["inserted"] == 1
    assert result["updated"] == 0

    with UnitOfWork() as uow:
        emp = uow.employers.get_by_name("Firma Beispiel")
        assert emp is not None
        row = uow.income_hourly.get_by_emp_period(emp.id, 2026, 4)
        assert row is not None
        assert row.hours_normal == Decimal("160")
        assert row.night == Decimal("10")
        assert row.overtime == Decimal("5")
        assert row.calc_amount == Decimal("0.00")

    path2 = _write_csv(
        tmp_path,
        "income_hourly2.csv",
        ["employer_name", "year", "month", "hours_normal", "night", "sunday", "holiday", "overtime"],
        [["Firma Beispiel", "2026", "4", "170", "12", "0", "0", "8"]],
    )
    result2 = svc.import_csv(path2, "income_hourly")
    assert result2["inserted"] == 0
    assert result2["updated"] == 1

    with UnitOfWork() as uow:
        emp = uow.employers.get_by_name("Firma Beispiel")
        row = uow.income_hourly.get_by_emp_period(emp.id, 2026, 4)
        assert row.hours_normal == Decimal("170")
        assert row.overtime == Decimal("8")


def test_import_income_hourly_round_trips_with_export(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(
        tmp_path,
        "income_hourly.csv",
        [
            "employer_name",
            "year",
            "month",
            "hours_normal",
            "night",
            "sunday",
            "holiday",
            "overtime",
            "payout_timing",
            "account_label",
        ],
        [["RoundTrip Co", "2026", "6", "150", "5", "2", "1", "3", "BEGINNING", "GIRO"]],
    )
    svc.import_csv(path, "income_hourly")

    export_path = str(tmp_path / "income_hourly_export.csv")
    ExportService().export_csv(export_path, "income_hourly", period=Period(2026, 6))

    result = svc.import_csv(export_path, "income_hourly")
    assert result["status"] == "ok"
    assert result["inserted"] == 0
    assert result["updated"] == 1

    with UnitOfWork() as uow:
        emp = uow.employers.get_by_name("RoundTrip Co")
        row = uow.income_hourly.get_by_emp_period(emp.id, 2026, 6)
        assert row.hours_normal == Decimal("150")
        assert row.night == Decimal("5")
        assert row.sunday == Decimal("2")
        assert row.holiday == Decimal("1")
        assert row.overtime == Decimal("3")
        assert row.payout_timing == PayoutTiming.BEGINNING
        acc = uow.accounts.get(row.account_id)
        assert acc.label == "GIRO"


def test_import_expense_recurring_always_inserts(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(
        tmp_path,
        "expense_recurring.csv",
        ["name", "category_name", "amount", "frequency_months", "due_day", "status", "pay_bucket"],
        [["Netflix", "Abos", "12.99", "1", "5", "ACTIVE", "NONE"]],
    )
    result = svc.import_csv(path, "expense_recurring")
    assert result["status"] == "ok"
    assert result["inserted"] == 1

    with UnitOfWork() as uow:
        rows = uow.expense_recurring.list_all()
        assert len(rows) == 1
        row = rows[0]
        assert row.name == "Netflix"
        assert row.amount == Decimal("12.99")
        assert row.frequency_months == 1
        assert row.due_day == 5
        assert row.status.value == "ACTIVE"
        assert row.account is not None  # required FK, auto-created via DEFAULT fallback
        assert row.category.name == "Abos"

    # No natural key for this dataset (matches excel_importer.py) -- a second
    # import of equivalent content always inserts a new row, it never updates.
    path2 = _write_csv(
        tmp_path,
        "expense_recurring2.csv",
        ["name", "category_name", "amount", "frequency_months", "due_day", "status", "pay_bucket"],
        [["Netflix", "Abos", "13.99", "1", "5", "ACTIVE", "NONE"]],
    )
    result2 = svc.import_csv(path2, "expense_recurring")
    assert result2["inserted"] == 1
    assert result2["updated"] == 0

    with UnitOfWork() as uow:
        rows = uow.expense_recurring.list_all()
        assert len(rows) == 2


def test_import_expense_recurring_round_trips_with_export(tmp_path: Path):
    svc = ImportService()

    path = _write_csv(
        tmp_path,
        "expense_recurring.csv",
        [
            "name",
            "category_name",
            "amount",
            "frequency_months",
            "due_day",
            "anchor_month",
            "status",
            "account_label",
            "pay_bucket",
            "allocation_override",
        ],
        [["Miete", "Wohnen", "850.00", "1", "1", "", "ACTIVE", "GIRO", "MID", "CASHFLOW"]],
    )
    svc.import_csv(path, "expense_recurring")

    export_path = str(tmp_path / "expense_recurring_export.csv")
    ExportService().export_csv(export_path, "expense_recurring")

    result = svc.import_csv(export_path, "expense_recurring")
    assert result["status"] == "ok"
    assert result["inserted"] == 1

    with UnitOfWork() as uow:
        rows = [r for r in uow.expense_recurring.list_all() if r.name == "Miete"]
        assert len(rows) == 2
        row = rows[0]
        assert row.amount == Decimal("850.00")
        assert row.pay_bucket.value == "MID"
        assert row.allocation_override.value == "CASHFLOW"
        assert row.account.label == "GIRO"


@pytest.mark.parametrize(
    "dataset",
    ["expense_variable", "loans", "loan_events"],
)
def test_import_csv_rejects_unsupported_datasets(tmp_path: Path, dataset: str):
    svc = ImportService()
    path = _write_csv(tmp_path, "data.csv", ["name"], [["whatever"]])

    with pytest.raises(ValueError, match="nicht unterstützt"):
        svc.import_csv(path, dataset)
