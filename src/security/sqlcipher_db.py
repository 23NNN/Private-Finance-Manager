# src/security/sqlcipher_db.py
from __future__ import annotations

import sqlite3
from pathlib import Path


def _is_plain_sqlite(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 16:
        return False
    try:
        head = path.read_bytes()[:16]
    except Exception:
        return False
    return head.startswith(b"SQLite format 3\x00")


def encrypt_plain_to_sqlcipher(db_path: Path, *, key: str) -> None:
    """Converts a plain SQLite DB to SQLCipher format (in-place).

    Important:
    - PRAGMA statements (e.g. `PRAGMA key`) do NOT support parameter placeholders.
    - The key is set exclusively in `connect_sqlcipher()` (string literal);
      no additional `PRAGMA key = ?` is executed here.

    Process:
    1) Open plain DB via built-in sqlite3 and create a dump (iterdump).
    2) Create a temporary SQLCipher DB and import the dump via executescript.
    3) Replace the original file atomically (tmp -> db_path).

    Raises:
      ValueError: if the source is not a plain SQLite DB or is corrupted.
    """
    if not _is_plain_sqlite(db_path):
        raise ValueError(f"Source is not a plain SQLite DB: {db_path}")

    try:
        plain = sqlite3.connect(str(db_path))
    except sqlite3.DatabaseError as e:
        raise ValueError(f"Plain SQLite DB cannot be opened: {e}") from e

    try:
        dump_sql = "\n".join(plain.iterdump())
    except sqlite3.DatabaseError as e:
        raise ValueError(f"Plain SQLite DB is corrupted / not a DB format: {e}") from e
    finally:
        try:
            plain.close()
        except Exception:
            pass

    from src.security.sqlcipher_driver import connect_sqlcipher  # local import

    tmp = db_path.with_suffix(db_path.suffix + ".tmp_sqlcipher")
    try:
        if tmp.exists():
            tmp.unlink()
    except Exception:
        pass

    enc = connect_sqlcipher(tmp, key=key)
    try:
        cur = enc.cursor()
        # Key is already set in connect_sqlcipher(); no placeholder PRAGMA here!
        cur.executescript(dump_sql)
        enc.commit()
    finally:
        try:
            enc.close()
        except Exception:
            pass

    try:
        db_path.unlink()
    except FileNotFoundError:
        pass
    tmp.replace(db_path)
