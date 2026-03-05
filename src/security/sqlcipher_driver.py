# src/security/sqlcipher_driver.py
from __future__ import annotations

"""SQLCipher DB-API loader + connector.

Why this file exists:
- SQLite PRAGMA statements do NOT support parameter placeholders ("?").
  A call like `conn.execute("PRAGMA key = ?", (key,))` leads to:
    OperationalError: near "?": syntax error
- Some SQLCipher packages have different names:
  - pysqlcipher3 (recommended on Windows when available)
  - sqlcipher3

This implementation:
- finds an installed SQLCipher DB-API driver
- sets the key via string literal (with clean escaping)
- validates the key by accessing sqlite_master (otherwise "file is not a database")
"""

import importlib
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class SqlCipherNotAvailable(ImportError):
    pass


def _load_dbapi() -> tuple[Any, str]:
    """Returns (dbapi_module, name)."""
    candidates = [
        "pysqlcipher3.dbapi2",
        "sqlcipher3.dbapi2",
        "sqlcipher3",
    ]
    last_err: Exception | None = None
    for modname in candidates:
        try:
            mod = importlib.import_module(modname)
            # DB-API module must have connect()
            if not hasattr(mod, "connect"):
                continue
            return mod, modname
        except Exception as e:  # noqa: BLE001 - we want to try all
            last_err = e
            continue
    raise SqlCipherNotAvailable(
        "SQLCipher DBAPI not found. Install e.g. 'pysqlcipher3-binary' (Windows) or 'sqlcipher3'."
    ) from last_err


def _quote_sqlite_string(value: str) -> str:
    # SQLite string literal escaping: ' -> ''
    return "'" + value.replace("'", "''") + "'"


def connect_sqlcipher(db_path: Path, key: str) -> Any:
    """Open SQLCipher connection and apply key.

    Raises:
      - SqlCipherNotAvailable if no driver
      - RuntimeError if the key is wrong or DB is corrupted/unreadable
    """
    dbapi, name = _load_dbapi()

    conn = dbapi.connect(str(db_path))
    try:
        # PRAGMA key cannot use bound parameters.
        conn.execute("PRAGMA key = " + _quote_sqlite_string(key))
        # Optional: ensure compatibility (harmless if not supported)
        try:
            conn.execute("PRAGMA cipher_compatibility = 4")
        except Exception:
            pass

        # Validate key: accessing sqlite_master fails with wrong key.
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return conn
    except Exception as e:  # noqa: BLE001
        try:
            conn.close()
        except Exception:
            pass
        raise RuntimeError(f"SQLCipher connection failed ({name}). Possible wrong key or corrupted DB.") from e


def make_creator(db_path: Path, key: str) -> Callable[[], Any]:
    """Returns a SQLAlchemy `creator` callable."""

    def _creator():
        return connect_sqlcipher(db_path, key)

    return _creator



def load_sqlcipher_dbapi() -> Any:
    """Public API: returns the installed SQLCipher DB-API module.

    Used by SecurityManager to probe availability without opening a DB.
    """
    mod, _name = _load_dbapi()
    return mod


def make_sqlcipher_creator(db_path: Path, *, key: str) -> Callable[[], Any]:
    """Public API: SQLAlchemy creator factory (compat alias)."""
    return make_creator(db_path, key)

def rekey(db_path: Path, old_key: str, new_key: str) -> None:
    """Re-encrypts SQLCipher DB with a new key (PRAGMA rekey)."""
    dbapi, _name = _load_dbapi()
    conn = dbapi.connect(str(db_path))
    try:
        conn.execute("PRAGMA key = " + _quote_sqlite_string(old_key))
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        conn.execute("PRAGMA rekey = " + _quote_sqlite_string(new_key))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass
