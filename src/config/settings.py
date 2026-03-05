# finanzmanager/config/settings.py
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir, user_log_dir


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _exe_dir() -> Path:
    return Path(sys.executable).resolve().parent


def resolve_data_dir(app_name: str) -> Path:
    override = os.getenv("FINANZMANAGER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if _bool_env("FINANZMANAGER_PORTABLE"):
        return (_exe_dir() / "data").resolve()
    return Path(user_data_dir(app_name, appauthor=False)).resolve()


def resolve_log_dir(app_name: str, data_dir: Path) -> Path:
    override = os.getenv("FINANZMANAGER_LOG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if _bool_env("FINANZMANAGER_PORTABLE"):
        return (data_dir / "logs").resolve()
    return Path(user_log_dir(app_name, appauthor=False)).resolve()


@dataclass(frozen=True)
class Settings:
    app_name: str
    data_dir: Path
    log_dir: Path

    # Main DB file (plaintext for mode=NONE, SQLCipher for PIN/DEVICE)
    db_filename: str = "finanz.db"

    # Legacy DPAPI wrapper (older security patch)
    legacy_enc_filename: str = "finanz.db.enc"

    log_filename: str = "app.log"

    def db_path(self) -> Path:
        return (self.data_dir / self.db_filename).resolve()

    def legacy_enc_db_path(self) -> Path:
        return (self.data_dir / self.legacy_enc_filename).resolve()

    def log_path(self) -> Path:
        return (self.log_dir / self.log_filename).resolve()

    def sqlite_url(self) -> str:
        return f"sqlite:///{self.db_path().as_posix()}"


def get_settings() -> Settings:
    app_name = "Finanzmanager"
    data_dir = resolve_data_dir(app_name)
    log_dir = resolve_log_dir(app_name, data_dir)
    return Settings(app_name=app_name, data_dir=data_dir, log_dir=log_dir)
