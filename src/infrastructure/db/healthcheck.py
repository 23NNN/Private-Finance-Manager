# src/infrastructure/db/healthcheck.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import inspect

from src.infrastructure.db.engine import get_engine
from src.infrastructure.db.migrations.schema_patch import ensure_schema


@dataclass(frozen=True)
class HealthIssue:
    severity: str  # "FATAL" | "WARN"
    table: str
    missing_columns: tuple[str, ...]
    message: str


# Minimal: only columns that are practically always needed in SELECTs.
_REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "expense_variable": ("id", "name", "amount", "year", "month", "category_id", "status"),
    "expense_recurring": ("id", "name", "amount", "category_id", "status", "account_id"),
    "income_fixed": ("id", "employer_id", "year", "month"),
    "income_hourly": ("id", "employer_id", "year", "month"),
    "income_special": ("id", "year", "month", "name", "amount", "payout_timing"),
    "loan": ("id", "name", "status"),
    "savings_rule": ("id", "employer_id", "percentage"),
}

# Optional / automatically patchable (WARN)
_PATCHABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "pay_rule": ("valid_from", "valid_to", "notes"),
    "expense_variable": ("pay_bucket", "notes"),
    "expense_recurring": ("pay_bucket", "allocation_override", "notes"),
    "income_fixed": ("payout_timing", "account_id", "notes"),
    "income_hourly": ("payout_timing", "account_id", "notes"),
    "income_special": ("actual_amount", "account_id", "notes"),
    "savings_contribution": ("notes", "account_id"),
    "savings_rule": ("valid_from", "valid_to"),
}


def run_healthcheck(*, auto_fix: bool = True) -> list[HealthIssue]:
    """Checks whether the SQLite DB is broadly compatible.

    - auto_fix=True patches minor schema drifts (schema_patch) before checking.
    """
    if auto_fix:
        ensure_schema()

    engine = get_engine()
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    issues: list[HealthIssue] = []

    # Required (fatal)
    for table, req_cols in _REQUIRED_COLUMNS.items():
        if table not in tables:
            issues.append(
                HealthIssue(
                    severity="FATAL",
                    table=table,
                    missing_columns=tuple(req_cols),
                    message="Table is completely missing.",
                )
            )
            continue

        cols = {c["name"] for c in insp.get_columns(table)}
        missing = tuple([c for c in req_cols if c not in cols])
        if missing:
            issues.append(
                HealthIssue(
                    severity="FATAL",
                    table=table,
                    missing_columns=missing,
                    message="Required columns are missing.",
                )
            )

    # Patchable (warn)
    for table, opt_cols in _PATCHABLE_COLUMNS.items():
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        missing = tuple([c for c in opt_cols if c not in cols])
        if missing:
            issues.append(
                HealthIssue(
                    severity="WARN",
                    table=table,
                    missing_columns=missing,
                    message="Optional columns are missing (auto-fix possible).",
                )
            )

    return issues


def format_report(issues: Iterable[HealthIssue]) -> str:
    out: list[str] = []
    for i in issues:
        out.append(f"[{i.severity}] {i.table}: {i.message} Missing={list(i.missing_columns)}")
    return "\n".join(out) if out else "OK"
