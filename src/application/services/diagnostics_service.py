# application/services/diagnostics_service.py
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import inspect, text

from src.config.settings import get_settings
from src.infrastructure.db.engine import get_engine
from src.infrastructure.db.migrations.schema_patch import ensure_schema


@dataclass(frozen=True)
class DiagnosticsReport:
    ok: bool
    title: str
    text: str


class DiagnosticsService:
    """Runs a lightweight health-check and provides actionable hints."""

    def run(self) -> DiagnosticsReport:
        settings = get_settings()
        engine = get_engine()
        insp = inspect(engine)

        lines: list[str] = []
        ok = True

        is_frozen = bool(getattr(sys, "frozen", False))
        lines.append(f"Mode: {'EXE (PyInstaller)' if is_frozen else 'Source (Python)'}")
        lines.append(f"Database: {settings.db_path()}")
        lines.append(f"Logs: {settings.log_path()}")

        # Best-effort schema auto-fix
        changes = ensure_schema()
        if changes:
            lines.append("")
            lines.append("Auto-fix applied:")
            lines.extend([f"- {c}" for c in changes])

        try:
            tables = set(insp.get_table_names())
            lines.append("")
            lines.append(f"Tables found: {len(tables)}")

            def has_col(table: str, col: str) -> bool:
                if table not in tables:
                    return False
                cols = {c['name'] for c in insp.get_columns(table)}
                return col in cols

            required_tables = [
                "account",
                "employer",
                "pay_rule",
                "income_fixed",
                "income_hourly",
                "expense_category",
                "expense_recurring",
                "expense_variable",
                "loan",
                "loan_event",
                "savings_goal",
                "savings_rule",
                "savings_contribution",
                "import_run",
            ]
            missing = [t for t in required_tables if t not in tables]
            if missing:
                ok = False
                lines.append("Missing tables:")
                lines.extend([f"- {t}" for t in missing])

            pr_notes = has_col("pay_rule", "notes")
            lines.append(f"Column pay_rule.notes: {'OK' if pr_notes else 'MISSING'}")
            if not pr_notes:
                ok = False

            # row counts (best-effort)
            with engine.connect() as conn:
                lines.append("")
                for t in ["account", "employer", "pay_rule", "income_fixed", "income_hourly", "expense_recurring", "expense_variable", "loan", "loan_event"]:
                    if t not in tables:
                        continue
                    n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one()
                    lines.append(f"{t}: {n}")

        except Exception as e:
            ok = False
            lines.append("")
            lines.append(f"Diagnostics failed: {e}")

        hints: list[str] = []
        if is_frozen:
            hints.append("If you changed code: rebuild the EXE (PyInstaller).")
        if not ok:
            hints.append("If DB schema is outdated: run the app once from source or execute migrations.")

        if hints:
            lines.append("")
            lines.append("Hints:")
            lines.extend([f"- {h}" for h in hints])

        title = "System check OK" if ok else "System check: problems found"
        return DiagnosticsReport(ok=ok, title=title, text="\n".join(lines))
