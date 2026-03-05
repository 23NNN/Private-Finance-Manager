# scripts/export_context.py
from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path


EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "*.egg-info",
    ".idea",
}


INCLUDE_DEFAULT = [
    "src",
    "tests",
    "docs",
    "scripts",
    "pyproject.toml",
    "README.md",
    "app.py",
]


def _is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    if parts & {".git", ".venv", "venv", "__pycache__", "build", "dist", ".idea", ".pytest_cache", ".ruff_cache"}:
        return True
    if any(p.endswith(".egg-info") for p in path.parts):
        return True
    return False


def _iter_files(root: Path, includes: list[str]) -> list[Path]:
    out: list[Path] = []
    for item in includes:
        p = root / item
        if not p.exists():
            continue
        if p.is_file():
            out.append(p)
            continue
        for fp in p.rglob("*"):
            if fp.is_file() and not _is_excluded(fp):
                out.append(fp)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="finanzmanager_context.zip", help="Name der ZIP-Datei")
    ap.add_argument("--include-resources", action="store_true", help="resources/ mit einpacken")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    includes = list(INCLUDE_DEFAULT)
    if args.include_resources:
        includes.append("resources")

    files = _iter_files(root, includes)
    out_path = root / args.out

    if out_path.exists():
        out_path.unlink()

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for fp in files:
            rel = fp.relative_to(root)
            z.write(fp, arcname=str(rel))

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"✅ Export erstellt: {out_path} ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
