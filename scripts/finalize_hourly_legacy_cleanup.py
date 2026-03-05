# scripts/finalize_hourly_legacy_cleanup.py
from __future__ import annotations

"""Finale Bereinigung: BW/BY-Legacy Werte in income_hourly entfernen.

Warum:
- Alte DBs können noch Werte in hours_bw/hours_by/night_bw/night_by/sunday_bw/sunday_by enthalten.
- Die UI nutzt diese Felder nicht mehr (neutraler Stundenlohn), aber Altwerte können Berechnungen/Export verwirren.

Was macht das Script:
- Rollup:
  - hours_normal += hours_bw + hours_by
  - night       += night_bw + night_by
  - sunday      += sunday_bw + sunday_by
- Danach setzt es alle BW/BY Felder dauerhaft auf 0.

Eigenschaften:
- Idempotent: mehrfach ausführbar.
- Default ist Dry-Run (zeigt nur an, was passieren würde).
- Mit --apply wird wirklich geschrieben.

Beispiele:
- Dry-Run:  python scripts/finalize_hourly_legacy_cleanup.py
- Apply:    python scripts/finalize_hourly_legacy_cleanup.py --apply
- Anderer DB-Pfad: python scripts/finalize_hourly_legacy_cleanup.py --db .\demo_data\finanzmanager.sqlite --apply
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_syspath(root: Path) -> None:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    cur = con.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def _get_default_db_path() -> Path:
    root = _repo_root()
    _ensure_syspath(root)
    from src.config.settings import get_settings  # noqa: WPS433

    return get_settings().db_path()


def _count_dirty(con: sqlite3.Connection) -> int:
    cur = con.execute(
        """
        SELECT COUNT(*)
        FROM income_hourly
        WHERE
            COALESCE(hours_bw,0) != 0 OR COALESCE(hours_by,0) != 0 OR
            COALESCE(night_bw,0) != 0 OR COALESCE(night_by,0) != 0 OR
            COALESCE(sunday_bw,0) != 0 OR COALESCE(sunday_by,0) != 0
        """
    )
    row = cur.fetchone()
    return int(row[0] if row else 0)


def _apply_rollup(con: sqlite3.Connection) -> None:
    con.execute(
        """
        UPDATE income_hourly
        SET
            hours_normal = COALESCE(hours_normal,0) + COALESCE(hours_bw,0) + COALESCE(hours_by,0),
            night = COALESCE(night,0) + COALESCE(night_bw,0) + COALESCE(night_by,0),
            sunday = COALESCE(sunday,0) + COALESCE(sunday_bw,0) + COALESCE(sunday_by,0),

            hours_bw = 0,
            hours_by = 0,
            night_bw = 0,
            night_by = 0,
            sunday_bw = 0,
            sunday_by = 0
        """
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Finale Bereinigung: BW/BY-Legacy Werte in income_hourly entfernen")
    ap.add_argument("--apply", action="store_true", help="Änderungen wirklich schreiben")
    ap.add_argument("--db", type=str, default="", help="Optionaler SQLite DB-Pfad (sonst Settings)")
    args = ap.parse_args(argv)

    db_path = Path(args.db).expanduser().resolve() if args.db else _get_default_db_path()
    if not db_path.exists():
        print(f"❌ DB nicht gefunden: {db_path}")
        return 2

    con = sqlite3.connect(str(db_path))
    try:
        cols = _table_columns(con, "income_hourly")
        needed = {"hours_bw", "hours_by", "night_bw", "night_by", "sunday_bw", "sunday_by", "hours_normal"}
        missing = sorted([c for c in needed if c not in cols])
        if missing:
            print("✅ income_hourly hat keine Legacy-BW/BY Spalten mehr (oder DB ist neu).")
            print(f"DB: {db_path}")
            return 0

        dirty = _count_dirty(con)
        print(f"DB: {db_path}")
        print(f"Betroffene Zeilen (BW/BY != 0): {dirty}")

        if dirty == 0:
            print("✅ Keine Legacy-Werte vorhanden. Nichts zu tun.")
            return 0

        if not args.apply:
            print("\nDRY-RUN: keine Änderungen geschrieben.")
            print("Tipp: erneut ausführen mit --apply")
            return 1

        con.execute("BEGIN")
        _apply_rollup(con)
        con.commit()

        dirty2 = _count_dirty(con)
        print(f"✅ Bereinigung abgeschlossen. Verbleibende Legacy-Zeilen: {dirty2}")
        return 0 if dirty2 == 0 else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())