# scripts/normalize_imports.py
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


INTERNAL_TOPLEVEL = ("application", "config", "domain", "infrastructure", "ui")


@dataclass(frozen=True)
class FileChange:
    path: Path
    changed_lines: int


def _rewrite_import_line(line: str) -> str:
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]

    if not (stripped.startswith("from ") or stripped.startswith("import ")):
        return line

    # already good
    if "from src." in stripped or stripped.startswith("import src.") or stripped.startswith("from src "):
        return line

    # from X...  -> from src.X...
    if stripped.startswith("from "):
        # e.g. "from ui.main import X"
        for mod in INTERNAL_TOPLEVEL:
            if stripped.startswith(f"from {mod}.") or stripped.startswith(f"from {mod} "):
                return indent + stripped.replace(f"from {mod}", f"from src.{mod}", 1)

    # import X... -> import src.X...
    if stripped.startswith("import "):
        # can be "import ui.main" or "import ui" or "import ui.main as m"
        for mod in INTERNAL_TOPLEVEL:
            if stripped.startswith(f"import {mod}.") or stripped.startswith(f"import {mod} " ) or stripped == f"import {mod}\n":
                return indent + stripped.replace(f"import {mod}", f"import src.{mod}", 1)

    return line


def _process_file(path: Path, apply: bool) -> FileChange | None:
    try:
        original = path.read_text(encoding="utf-8")
    except Exception:
        return None

    lines = original.splitlines(keepends=True)
    new_lines = []
    changed = 0

    for line in lines:
        new_line = _rewrite_import_line(line)
        if new_line != line:
            changed += 1
        new_lines.append(new_line)

    new_text = "".join(new_lines)
    if new_text == original:
        return None

    if apply:
        path.write_text(new_text, encoding="utf-8")

    return FileChange(path=path, changed_lines=changed)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stellt interne Imports repo-weit auf `src.*` um.")
    ap.add_argument("--apply", action="store_true", help="Änderungen schreiben (sonst nur Vorschau)")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    targets = []

    for base in ("src", "tests", "scripts"):
        p = root / base
        if p.exists():
            targets.append(p)

    changes: list[FileChange] = []
    for base in targets:
        for py in base.rglob("*.py"):
            # ignore caches, etc.
            if "__pycache__" in py.parts:
                continue
            c = _process_file(py, apply=bool(args.apply))
            if c:
                changes.append(c)

    total_files = len(changes)
    total_lines = sum(c.changed_lines for c in changes)

    if not args.apply:
        print("DRY-RUN (keine Dateien wurden geändert). Nutze --apply zum Schreiben.\n")

    if total_files == 0:
        print("✅ Keine Änderungen nötig. Alle internen Imports scheinen bereits `src.*` zu nutzen.")
        return 0

    print(f"Gefundene Änderungen: Dateien={total_files}, geänderte Import-Zeilen={total_lines}\n")
    for c in sorted(changes, key=lambda x: str(x.path)):
        rel = c.path.relative_to(root)
        print(f"- {rel}  (Zeilen: {c.changed_lines})")

    if not args.apply:
        print("\n➡️  Zum Anwenden: python scripts/normalize_imports.py --apply")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
