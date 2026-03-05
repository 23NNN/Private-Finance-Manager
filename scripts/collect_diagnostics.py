"""
scripts/collect_diagnostics.py

Collects sanitized diagnostics for the Finanzmanager repo:
- scripts/doctor.py
- scripts/i18n_audit.py

Writes a single report file under docs/diagnostics/ with absolute paths redacted.

Usage (from repo root):
    python scripts/collect_diagnostics.py
    python scripts/collect_diagnostics.py --strict
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Tuple


_WIN_ABS_PATH = re.compile(r"(?i)\b[a-z]:\\[^\s\"\'\)\]]+")
_POSIX_ABS_PATH = re.compile(r"(?<![\w/])/(?:[^ \n\r\t\"\'\)\]]+)")  # best-effort


def _repo_root() -> Path:
    # scripts/collect_diagnostics.py -> scripts/ -> repo root
    return Path(__file__).resolve().parent.parent


def _redact_abs_paths(text: str) -> str:
    text = _WIN_ABS_PATH.sub("<ABS_PATH>", text)
    text = _POSIX_ABS_PATH.sub("<ABS_PATH>", text)
    return text


def _run(cmd: Iterable[str], cwd: Path) -> Tuple[int, str]:
    proc = subprocess.run(
        list(cmd),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, _redact_abs_paths(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect sanitized repo diagnostics.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Pass --strict to scripts/doctor.py (if supported).",
    )
    args = parser.parse_args()

    root = _repo_root()
    scripts_dir = root / "scripts"
    out_dir = root / "docs" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"diagnostics_{stamp}.txt"

    lines: list[str] = []
    lines.append("Finanzmanager diagnostics (sanitized)")
    lines.append(f"Timestamp: {stamp}")
    lines.append(f"Python: {sys.version.splitlines()[0]}")
    lines.append(f"Platform: {sys.platform}")
    lines.append("")
    lines.append("=== doctor.py ===")

    doctor = scripts_dir / "doctor.py"
    if doctor.exists():
        cmd = [sys.executable, str(doctor)]
        if args.strict:
            cmd.append("--strict")
        code, out = _run(cmd, cwd=root)
        lines.append(f"Exit code: {code}")
        lines.append(out.rstrip())
    else:
        lines.append("doctor.py not found under scripts/.")

    lines.append("")
    lines.append("=== i18n_audit.py ===")

    audit = scripts_dir / "i18n_audit.py"
    if audit.exists():
        cmd = [sys.executable, str(audit)]
        code, out = _run(cmd, cwd=root)
        lines.append(f"Exit code: {code}")
        lines.append(out.rstrip())
    else:
        lines.append("i18n_audit.py not found under scripts/.")

    out_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    rel = out_file.relative_to(root).as_posix()
    print(f"Wrote: {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
