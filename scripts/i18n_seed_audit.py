# scripts/i18n_seed_audit.py
"""Audit i18n seed translation quality in schema_patch.py.

Flags fr/es/it seed values that are byte-identical to the en value (an
untranslated placeholder), after filtering out known-good loanwords/cognates
via an explicit allowlist. This is a different check than i18n_audit.py,
which only looks for missing tr()/trf() wrapping in UI code -- this script
checks the quality of existing seed *values*, not whether they're wrapped.
Does NOT modify code.

Usage:
  python scripts/i18n_seed_audit.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

_SCHEMA_PATCH = (
    Path(__file__).resolve().parents[1] / "src" / "infrastructure" / "db" / "migrations" / "schema_patch.py"
)

_LANGS = ("fr", "es", "it")

# Values that are legitimately identical to the English value in fr/es/it
# (universal loanwords, symbols, or real cognates confirmed during the
# Zyklus 4 review) -- these are NOT translation bugs.
_ALLOWED_VALUES = {
    "OK",
    "PIN",
    "CSV",
    "IBAN",
    "EUR",
    "Info",
    "Total",
    "Extra",
    "Type",
    "Date",
    "Note",
    "Notes",
    "Message",
    "Correction",
    "Direction",
    "Mode",
    "Source",
    "No",
    "Error",
    "Principal",
    "—",
    "-",
    "",
}

# Keys that are intentionally identical across all languages (e.g. the
# product name) regardless of value.
_ALLOWED_KEYS = {"app.title"}

# (key, lang) pairs that are intentionally identical to en for that specific
# language only (e.g. "File" is standard Italian software-menu convention,
# unlike French/Spanish which do translate it).
_ALLOWED_KEY_LANGS = {("menu.file", "it")}


def _find_seed_dict(tree: ast.Module) -> ast.Dict:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            targets = node.targets
            if len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id == "seed":
                return node.value
    raise RuntimeError("Could not find 'seed = {...}' dict literal in schema_patch.py")


def main() -> int:
    if not _SCHEMA_PATCH.exists():
        print(f"Not found: {_SCHEMA_PATCH}")
        return 2

    src = _SCHEMA_PATCH.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(_SCHEMA_PATCH))
    seed_node = _find_seed_dict(tree)
    seed: dict[str, dict[str, str]] = ast.literal_eval(seed_node)

    findings: list[tuple[str, str]] = []
    for key, langs in seed.items():
        if key in _ALLOWED_KEYS:
            continue
        en = langs.get("en", "")
        for lang in _LANGS:
            val = langs.get(lang, "")
            if val == en and val not in _ALLOWED_VALUES and (key, lang) not in _ALLOWED_KEY_LANGS:
                findings.append((key, lang))

    if not findings:
        print("i18n seed audit: no untranslated placeholder values found.")
        return 0

    by_key: dict[str, list[str]] = {}
    for key, lang in findings:
        by_key.setdefault(key, []).append(lang)

    print(f"i18n seed audit: {len(by_key)} keys / {len(findings)} key×lang gaps (fr/es/it == en):\n")
    for key in sorted(by_key):
        langs = ",".join(by_key[key])
        en = seed[key]["en"]
        print(f"  {key}  [{langs}]  en={en!r}")

    print(f"\nTotal: {len(by_key)} keys, {len(findings)} gaps.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
