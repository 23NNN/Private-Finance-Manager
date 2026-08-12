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

from src.application.services.import_service import ImportService
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
        tmp_path, "accounts.csv",
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
        tmp_path, "accounts2.csv",
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
        tmp_path, "pay_rules.csv",
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


@pytest.mark.parametrize(
    "dataset",
    ["income_fixed", "income_hourly", "expense_recurring", "expense_variable", "loans", "loan_events"],
)
def test_import_csv_rejects_unsupported_datasets(tmp_path: Path, dataset: str):
    svc = ImportService()
    path = _write_csv(tmp_path, "data.csv", ["name"], [["whatever"]])

    with pytest.raises(ValueError, match="nicht unterstützt"):
        svc.import_csv(path, dataset)
