# finanzmanager/application/services/backup_service.py
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.config.settings import Settings


@dataclass(frozen=True)
class BackupResult:
    source_db: str
    backup_path: str


class BackupService:
    """Database backup utilities (MVP)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def backup_database(self, target_path: str) -> BackupResult:
        src = self._settings.db_path()
        if not src.exists():
            raise FileNotFoundError(f"Database not found: {src}")

        dst = Path(target_path).expanduser().resolve()
        dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(src, dst)
        return BackupResult(source_db=str(src), backup_path=str(dst))

    def suggest_backup_name(self) -> str:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        return f"finanz_backup_{ts}.db"
