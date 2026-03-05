# scripts/migrate_hourly_bw_by.py
from __future__ import annotations

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
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in cur.fetchall()}  # name


def _count_legacy_rows(con: sqlite3.Connection) -> int:
    cur = con.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM income_hourly
        WHERE
            COALESCE(hours_bw,0) != 0 OR COALESCE(hours_by,0) != 0
            OR COALESCE(night_bw,0) != 0 OR COALESCE(night_by,0) != 0
            OR COALESCE(sunday_bw,0) != 0 OR COALESCE(sunday_by,0) != 0
        """
    )
    return int(cur.fetchone()[0])


def _migrate(con: sqlite3.Connection) -> int:
    cur = con.cursor()
    cur.execute(
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
        WHERE
            COALESCE(hours_bw,0) != 0 OR COALESCE(hours_by,0) != 0
            OR COALESCE(night_bw,0) != 0 OR COALESCE(night_by,0) != 0
            OR COALESCE(sunday_bw,0) != 0 OR COALESCE(sunday_by,0) != 0
        """
    )
    return int(cur.rowcount)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Migriert alte Stundenlohn BW/BY Felder in die neuen Felder.")
    ap.add_argument("--apply", action="store_true", help="Änderungen wirklich schreiben (sonst Dry-Run).")
    args = ap.parse_args(argv)

    root = _repo_root()
    _ensure_syspath(root)

    from src.config.settings import get_settings  # noqa: WPS433

    settings = get_settings()
    db_path = Path(settings.db_path())

    if not db_path.exists():
        print(f"❌ DB Datei nicht gefunden: {db_path}")
        return 2

    con = sqlite3.connect(str(db_path))
    try:
        cols = _table_columns(con, "income_hourly")
        required = {
            "hours_bw", "hours_by", "night_bw", "night_by", "sunday_bw", "sunday_by",
            "hours_normal", "night", "sunday",
        }
        missing = required - cols
        if missing:
            print("✅ Migration nicht nötig: Spalten fehlen bereits (Schema ist schon modern).")
            print(f"Fehlende Spalten: {sorted(missing)}")
            return 0

        legacy = _count_legacy_rows(con)
        print(f"Gefundene Legacy-Zeilen (BW/BY != 0): {legacy}")
        if legacy == 0:
            print("✅ Nichts zu migrieren.")
            return 0

        if not args.apply:
            print("Dry-Run: keine Änderungen geschrieben. Starte mit --apply zum Anwenden.")
            return 0

        n = _migrate(con)
        con.commit()
        print(f"✅ Migriert: {n} Zeilen aktualisiert.")
        print("Hinweis: calc_amount bleibt korrekt, da die Berechnung BW/BY ohnehin schon summiert hat.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
