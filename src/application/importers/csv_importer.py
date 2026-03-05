from __future__ import annotations

import logging
from pathlib import Path

from src.application.importers.utils import as_bool, as_str
from src.infrastructure.db.orm_models import Account
from src.infrastructure.unit_of_work import UnitOfWork
from src.infrastructure.io.csv_reader import read_csv

logger = logging.getLogger(__name__)


class CsvImporter:
    """
    MVP: best-effort CSV import.
    Supported CSV types (heuristic via headers):
    - Accounts: label, account_name, bank_name, iban, role_income, role_debit, notes
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def import_file(self, path: Path) -> dict:
        rows = read_csv(path)
        if not rows:
            return {"rows": 0, "imported": 0, "type": "unknown"}

        headers = {h.lower() for h in rows[0].keys()}

        if "label" in headers and "account_name" in headers:
            return self._import_accounts(rows)

        return {"rows": len(rows), "imported": 0, "type": "unknown"}

    def _import_accounts(self, rows: list[dict[str, str]]) -> dict:
        existing = {a.label.lower(): a for a in self.uow.accounts.list_all()}
        imported = 0
        for r in rows:
            label = as_str(r, ["label"])
            if not label:
                continue
            obj = existing.get(label.lower()) or Account()
            obj.label = label
            obj.account_name = as_str(r, ["account_name", "konto_name"], default=label)
            obj.bank_name = as_str(r, ["bank_name", "bank"], default="") or None
            obj.iban = as_str(r, ["iban"], default="") or None
            obj.role_income = as_bool(r, ["role_income", "income"])
            obj.role_debit = as_bool(r, ["role_debit", "debit"])
            obj.notes = as_str(r, ["notes", "notizen"], default="") or None

            self.uow.accounts.upsert(obj)
            existing[label.lower()] = obj
            imported += 1

        logger.info("CSV accounts imported: %s", imported)
        return {"type": "accounts", "rows": len(rows), "imported": imported}
