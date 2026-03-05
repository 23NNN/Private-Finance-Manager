# scripts/pre_build_check.py
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], *, title: str) -> int:
    print(f"\n=== {title} ===")
    print(" ".join(cmd))
    p = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[1]))
    return int(p.returncode)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pre-Build Checks: normalize imports + audit + doctor.")
    ap.add_argument("--apply-normalize", action="store_true", help="normalize_imports.py --apply ausführen")
    ap.add_argument("--fail-on-warn", action="store_true", help="Bei Doctor-Warnungen Exit-Code != 0")
    ap.add_argument("--strict", action="store_true", help="Doctor strict (Import/Settings Fehler = ERR)")
    ap.add_argument("--with-settings", action="store_true", help="Doctor prüft auch Settings Pfade")
    ap.add_argument("--db-check", action="store_true", help="Doctor testet SQLite Connect (nur mit --with-settings)")
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    py = sys.executable

    # 1) Normalize imports
    if args.apply_normalize:
        rc = _run([py, str(root / "scripts" / "normalize_imports.py"), "--apply"], title="Normalize Imports (apply)")
        if rc != 0:
            print("❌ Normalize Imports fehlgeschlagen.")
            return rc
    else:
        rc = _run([py, str(root / "scripts" / "normalize_imports.py")], title="Normalize Imports (dry-run)")
        if rc != 0:
            print("❌ Normalize Imports (dry-run) fehlgeschlagen.")
            return rc

    # 2) Audit: Legacy imports report
    # --fail is optional, depending on whether you want hard blocking
    rc = _run([py, str(root / "scripts" / "find_legacy_imports.py")], title="Audit: Legacy Imports Report")
    if rc != 0:
        print("❌ Legacy Import Audit fehlgeschlagen.")
        return rc

    # 3) Doctor
    doctor_cmd = [py, str(root / "scripts" / "doctor.py"), "--imports"]
    if args.with_settings:
        doctor_cmd.append("--settings")
        if args.db_check:
            doctor_cmd.append("--db-check")
    if args.strict:
        doctor_cmd.append("--strict")

    doctor_rc = _run(doctor_cmd, title="Doctor")

    # doctor exit codes: 0 ok, 1 warn, 2 error
    if doctor_rc == 2:
        print("❌ Doctor meldet Fehler. Build stoppen.")
        return 2
    if doctor_rc == 1 and args.fail_on_warn:
        print("❌ Doctor meldet Warnungen (fail-on-warn aktiv). Build stoppen.")
        return 1

    print("\n✅ Pre-Build Checks erfolgreich.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
