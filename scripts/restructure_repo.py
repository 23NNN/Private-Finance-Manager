# scripts/find_legacy_imports.py
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


INTERNAL_TOPLEVEL = ("application", "config", "domain", "infrastructure", "ui")


@dataclass(frozen=True)
class Finding:
    file: Path
    line_no: int
    line: str
    hint: str


def _is_python_file(p: Path) -> bool:
    return p.is_file() and p.suffix == ".py"


def _should_skip_path(p: Path) -> bool:
    parts = set(p.parts)
    if "__pycache__" in parts:
        return True
    if ".venv" in parts or "venv" in parts:
        return True
    if "build" in parts or "dist" in parts:
        return True
    return False


def _compile_patterns() -> list[tuple[re.Pattern[str], str]]:
    """
    Findet Import-Zeilen, die auf interne Module zeigen, aber NICHT mit src. beginnen.
    - from ui... / import ui...
    - from application... / import application...
    etc.
    Ignoriert bereits korrekte:
    - from src.ui...
    - import src.ui...
    """
    pats: list[tuple[re.Pattern[str], str]] = []
    for m in INTERNAL_TOPLEVEL:
        # from ui.something import X
        pats.append(
            (
                re.compile(rf"^\s*from\s+{m}(\.|(\s+))", re.IGNORECASE),
                f"Nutze: from src.{m} ...",
            )
        )
        # import ui.something (including aliased imports)
        pats.append(
            (
                re.compile(rf"^\s*import\s+{m}(\.|(\s+))", re.IGNORECASE),
                f"Nutze: import src.{m} ...",
            )
        )
    # ignore correct ones explicitly in matcher
    return pats


def _is_already_ok(line: str) -> bool:
    s = line.strip()
    return s.startswith("from src.") or s.startswith("import src.") or s.startswith("from src ")


def scan_file(path: Path, patterns: list[tuple[re.Pattern[str], str]]) -> list[Finding]:
    findings: list[Finding] = []
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings

    for i, line in enumerate(txt.splitlines(), start=1):
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        if _is_already_ok(line):
            continue
        for pat, hint in patterns:
            if pat.search(line):
                findings.append(Finding(file=path, line_no=i, line=line.rstrip("\n"), hint=hint))
                break
    return findings


def scan_repo(root: Path, dirs: Iterable[str]) -> list[Finding]:
    patterns = _compile_patterns()
    out: list[Finding] = []
    for d in dirs:
        base = root / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if _should_skip_path(p):
                continue
            out.extend(scan_file(p, patterns))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Findet interne Imports ohne `src.` Prefix.")
    ap.add_argument("--paths", nargs="*", default=["src", "tests", "scripts"], help="Ordner, die gescannt werden")
    ap.add_argument("--fail", action="store_true", help="Exit-Code 2, wenn Findings existieren")
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    findings = scan_repo(root, args.paths)

    if not findings:
        print("✅ Keine Legacy-Imports gefunden. Alles nutzt `src.` korrekt.")
        return 0

    print(f"⚠️ Gefundene Legacy-Imports: {len(findings)}\n")
    for f in findings:
        rel = f.file.relative_to(root)
        print(f"- {rel}:{f.line_no}")
        print(f"  {f.line}")
        print(f"  Hinweis: {f.hint}\n")

    if args.fail:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
