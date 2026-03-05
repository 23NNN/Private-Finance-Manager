# src/security/secure_db.py
from __future__ import annotations

from pathlib import Path

from src.security import dpapi


class SecureDbManager:
    """Encrypts the SQLite DB at rest (Windows DPAPI) and provides a working decrypted DB file.

    Fallback backend used when SQLCipher is not available.
    """

    def __init__(self, *, encrypted_path: Path, legacy_plain_path: Path, work_path: Path, entropy: bytes | None) -> None:
        self._enc = encrypted_path
        self._legacy = legacy_plain_path
        self._work = work_path
        self._entropy = entropy

    @property
    def work_path(self) -> Path:
        return self._work

    def prepare_work_db(self) -> None:
        # Cleanup stale plaintext work DB from previous crash
        try:
            if self._work.exists():
                self._work.unlink()
        except Exception:
            pass
        self._work.parent.mkdir(parents=True, exist_ok=True)

        if self._enc.exists():
            data = self._enc.read_bytes()
            plain = dpapi.unprotect(data, entropy=self._entropy)
            self._work.write_bytes(plain)
            return

        # Migration from plaintext DB
        if self._legacy.exists() and self._legacy.stat().st_size > 0:
            plain = self._legacy.read_bytes()
            self._work.write_bytes(plain)
            enc = dpapi.protect(plain, entropy=self._entropy)
            self._enc.write_bytes(enc)
            try:
                self._legacy.unlink()
            except Exception:
                pass
            return

        # No DB yet -> create empty work file (migrations will populate)
        self._work.write_bytes(b"")

    def persist_and_lock(self) -> None:
        """Encrypts the current work DB and deletes plaintext work file."""
        if not self._work.exists():
            return
        plain = self._work.read_bytes()
        enc = dpapi.protect(plain, entropy=self._entropy)
        self._enc.parent.mkdir(parents=True, exist_ok=True)
        self._enc.write_bytes(enc)
        try:
            self._work.unlink()
        except Exception:
            pass
