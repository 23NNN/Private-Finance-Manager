# src/security/manager.py
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.config.settings import Settings
from src.security.security_config import SecurityConfig
from src.security.secure_db import SecureDbManager


@dataclass(frozen=True)
class DbEngineConfig:
    url: str
    creator: Callable[[], Any] | None = None
    connect_args: dict[str, Any] | None = None


def _is_plain_sqlite(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 16:
        return False
    try:
        head = path.read_bytes()[:16]
    except Exception:
        return False
    return head.startswith(b"SQLite format 3\x00")


class SecurityManager:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def security_path(self) -> Path:
        return (self._s.data_dir / "security.json").resolve()

    def db_path(self) -> Path:
        return self._s.db_path()

    # DPAPI fallback files
    def legacy_enc_path(self) -> Path:
        return (self._s.data_dir / "finanz.db.enc").resolve()

    def legacy_work_path(self) -> Path:
        return (self._s.data_dir / ".work" / "finanz_work.db").resolve()

    def is_sqlcipher_available(self) -> bool:
        try:
            from src.security.sqlcipher_driver import load_sqlcipher_dbapi  # noqa: WPS433
            load_sqlcipher_dbapi()
            return True
        except Exception:
            return False

    def db_is_probably_sqlcipher(self) -> bool:
        # SQLCipher file does NOT have SQLite header; plain sqlite does.
        p = self.db_path()
        return p.exists() and not _is_plain_sqlite(p) and p.stat().st_size > 0

    def make_dpapi_fallback_engine(self, cfg: SecurityConfig, *, pin: str | None) -> tuple[DbEngineConfig, callable]:
        entropy = cfg.derive_dpapi_entropy(pin)
        sdm = SecureDbManager(
            encrypted_path=self.legacy_enc_path(),
            legacy_plain_path=self.db_path(),
            work_path=self.legacy_work_path(),
            entropy=entropy,
        )
        sdm.prepare_work_db()

        def on_before_close() -> None:
            from src.infrastructure.db.engine import dispose_engine  # local
            dispose_engine()
            sdm.persist_and_lock()

        return DbEngineConfig(url=f"sqlite:///{sdm.work_path.as_posix()}"), on_before_close

    def migrate_legacy_if_needed(self, cfg: SecurityConfig, *, pin: str | None, sqlcipher_available: bool) -> None:
        # If mode is NONE: no migration needed
        if cfg.mode_norm() == "NONE":
            return

        # If SQLCipher not available, do NOT try SQLCipher migrations here.
        # Fallback will handle DPAPI wrapping for plain SQLite DB.
        if not sqlcipher_available:
            return

        # SQLCipher available -> ensure db is SQLCipher if we are in PIN/DEVICE mode
        db = self.db_path()
        if not db.exists() or db.stat().st_size == 0:
            return

        if _is_plain_sqlite(db):
            from src.security.sqlcipher_db import encrypt_plain_to_sqlcipher  # noqa: WPS433
            encrypt_plain_to_sqlcipher(db, key=cfg.derive_sqlcipher_key(pin))
            return

        # Already SQLCipher (or unknown). Do nothing.

    def make_engine_config(self, cfg: SecurityConfig, *, pin: str | None, sqlcipher_available: bool) -> DbEngineConfig:
        mode = cfg.mode_norm()
        if mode == "NONE":
            return DbEngineConfig(url=f"sqlite:///{self.db_path().as_posix()}")

        if not sqlcipher_available:
            raise ImportError("SQLCipher DBAPI nicht gefunden")

        from src.security.sqlcipher_driver import make_sqlcipher_creator  # noqa: WPS433
        key = cfg.derive_sqlcipher_key(pin)
        creator = make_sqlcipher_creator(self.db_path(), key=key)
        return DbEngineConfig(url="sqlite://", creator=creator, connect_args={})
