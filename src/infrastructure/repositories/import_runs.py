# finanzmanager/infrastructure/repositories/import_runs.py
from __future__ import annotations

from sqlalchemy import select
from src.infrastructure.db.orm_models import ImportRun
from src.infrastructure.repositories.base import Repository


class ImportRunRepository(Repository):
    def exists_hash(self, file_hash: str) -> bool:
        stmt = select(ImportRun.id).where(ImportRun.file_hash == file_hash)
        return self.session.scalar(stmt) is not None

    def add(self, run: ImportRun) -> ImportRun:
        self.session.add(run)
        return run
