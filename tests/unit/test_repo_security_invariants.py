# tests/unit/test_repo_security_invariants.py
"""Guards the repo's non-negotiable security boundary — see CLAUDE.md.

This test must never be weakened or removed to make a change pass.
It exists to guarantee that no database or personal financial data can
ever be committed to this repository, regardless of how a request is
phrased.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_GITIGNORE_PATTERNS = [
    "security.json",
    ".work/",
    "*.enc",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
]

FORBIDDEN_TRACKED_SUFFIXES = (".db", ".db.enc", ".sqlite", ".sqlite3", ".enc")
FORBIDDEN_TRACKED_NAMES = ("security.json",)


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_gitignore_contains_required_security_patterns():
    gitignore_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    missing = [p for p in REQUIRED_GITIGNORE_PATTERNS if p not in gitignore_text]
    assert not missing, f".gitignore is missing required security patterns: {missing}"


def test_no_forbidden_files_tracked_in_git():
    tracked = _tracked_files()
    offenders = [
        f
        for f in tracked
        if f.endswith(FORBIDDEN_TRACKED_SUFFIXES) or Path(f).name in FORBIDDEN_TRACKED_NAMES
    ]
    assert not offenders, f"Forbidden files are tracked in git: {offenders}"
