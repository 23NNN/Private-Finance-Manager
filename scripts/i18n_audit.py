# scripts/i18n_audit.py
from __future__ import annotations

"""Audit UI hardcoded strings (helper for migration to DB-backed i18n).

This script scans src/ui/**/*.py for likely user-facing string literals and prints a report.
It does NOT modify code.

Usage:
  python scripts/i18n_audit.py
"""

import ast
import re
from pathlib import Path


def _docstring_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    if isinstance(tree, ast.Module) and tree.body:
        n = tree.body[0]
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
            lines.add(n.lineno)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            n = node.body[0]
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                lines.add(n.lineno)
    return lines


def _is_candidate(s: str) -> bool:
    if not s or not s.strip():
        return False
    if s.startswith(("sqlite:", "SELECT", "PRAGMA")) or "://" in s:
        return False
    if re.fullmatch(r"[a-z0-9_.-]+", s) and "." in s:
        # likely i18n key already
        return False
    if s.isupper() and len(s) > 3:
        return False
    if any(ch in s for ch in "äöüÄÖÜß"):
        return True
    return bool(re.search(r"[A-Za-z]", s) and (" " in s or s[0].isupper()))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ui_root = root / "src" / "ui"
    if not ui_root.exists():
        print("src/ui not found.")
        return 2

    total = 0
    for path in sorted(ui_root.rglob("*.py")):
        src = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue
        doc_lines = _docstring_lines(tree)
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.lineno not in doc_lines:
                s = node.value
                if _is_candidate(s):
                    hits.append((node.lineno, s))
        if hits:
            rel = path.relative_to(root).as_posix()
            print(f"\n{rel} ({len(hits)}):")
            for ln, s in hits[:50]:
                print(f"  L{ln}: {s!r}")
            if len(hits) > 50:
                print(f"  ... (+{len(hits)-50})")
            total += len(hits)

    print(f"\nTotal candidate UI strings: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
