# scripts/doctor.py
"""Repo/Build/Runtime Healthcheck (Finanzmanager).
import ast

Schwerpunkte:
- Repo-/Packaging-Grundlagen (Layout, Python-Version)
- Dependency- & Kern-Imports
- DTO/Service-Contracts
- Optional: Settings/DB Pfade
- Zusätzlich: UI "cold-import" + statische NameError-Risikoanalyse
  (findet z.B. fehlende Imports von Dialog-/Presenter-Klassen, die erst zur Laufzeit craschen würden)

Hinweis:
Dieses Script ist bewusst dependency-arm (stdlib-only) und wird von pre_build_check.py genutzt.
"""

from __future__ import annotations

import argparse
import builtins
import dis
import re
import importlib
import inspect
import os
import platform
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from types import CodeType, FunctionType
from typing import Iterable, Iterator

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


@dataclass(frozen=True)
class CheckResult:
    level: str  # "OK" | "WARN" | "ERR"
    title: str
    detail: str = ""


class Doctor:
    def __init__(self, root: Path, *, strict: bool) -> None:
        self.root = root
        self.strict = strict
        self.results: list[CheckResult] = []
        self._prepend_root_to_syspath()

    def _prepend_root_to_syspath(self) -> None:
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))

    def ok(self, title: str, detail: str = "") -> None:
        self.results.append(CheckResult("OK", title, detail))

    def warn(self, title: str, detail: str = "") -> None:
        self.results.append(CheckResult("WARN", title, detail))

    def err(self, title: str, detail: str = "") -> None:
        self.results.append(CheckResult("ERR", title, detail))

    def _require(self, p: Path, title: str) -> None:
        if p.exists():
            self.ok(title, str(p))
        else:
            self.err(title, f"Fehlt: {p}")

    def _try_import(self, mod: str, title: str) -> bool:
        try:
            __import__(mod)
            self.ok(title, f"Import ok: {mod}")
            return True
        except Exception as e:  # noqa: BLE001
            msg = f"Import fehlgeschlagen: {mod} ({type(e).__name__}: {e})"
            if self.strict:
                self.err(title, msg)
            else:
                self.warn(title, msg)
            return False

    def run_basics(self) -> None:
        self.ok("System", f"{platform.system()} {platform.release()} ({platform.version()})")
        major, minor = sys.version_info[:2]
        if (major, minor) >= (3, 11):
            self.ok("Python Version", sys.version.split()[0])
        else:
            self.err("Python Version", f"Zu alt: {sys.version.split()[0]} (>= 3.11 benötigt)")

        self._require(self.root / "app.py", "Bootstrap: app.py")
        self._require(self.root / "pyproject.toml", "Build config: pyproject.toml")
        self._require(self.root / "src", "Source Layout: src/")
        self._require(self.root / "src" / "__init__.py", "Python Package: src/__init__.py")

    def run_imports(self, *, include_ui: bool = True) -> None:
        sqlalchemy_ok = self._try_import("sqlalchemy", "Dependency: SQLAlchemy")
        self._try_import("openpyxl", "Dependency: openpyxl")
        tkinter_ok = self._try_import("tkinter", "Dependency: tkinter (stdlib)")
        self._try_import("tkinter.ttk", "Dependency: tkinter.ttk (stdlib)")

        self._try_import("src.config.settings", "Interner Import: src.config.settings")
        self._try_import("src.infrastructure.db.orm_models", "Interner Import: src.infrastructure.db.orm_models")
        self._try_import("src.infrastructure.unit_of_work", "Interner Import: src.infrastructure.unit_of_work")
        self._try_import("src.ui.main_window", "Interner Import: src.ui.main_window")

        if include_ui:
            if not tkinter_ok:
                self.warn("UI Imports", "Übersprungen: tkinter konnte nicht importiert werden.")
            elif not sqlalchemy_ok:
                self.warn("UI Imports", "Übersprungen: SQLAlchemy konnte nicht importiert werden.")
            else:
                self.run_ui_imports()

    def run_contracts(self) -> None:
        try:
            from decimal import Decimal

            from src.application.dto.overview import OverviewVM, PeriodOverviewVM  # type: ignore

            cur = PeriodOverviewVM(
                year=2026,
                month=1,
                incomes=[],
                savings_total=Decimal("0.00"),
                accounts=[],
                loans=[],
                recurring_abos=Decimal("0.00"),
                recurring_insurance=Decimal("0.00"),
                recurring_other_fix=Decimal("0.00"),
                variable_total=Decimal("0.00"),
            )
            nxt = PeriodOverviewVM(
                year=2026,
                month=2,
                incomes=[],
                savings_total=Decimal("0.00"),
                accounts=[],
                loans=[],
                recurring_abos=Decimal("0.00"),
                recurring_insurance=Decimal("0.00"),
                recurring_other_fix=Decimal("0.00"),
                variable_total=Decimal("0.00"),
            )

            vm1 = OverviewVM(current=cur, next=nxt)
            vm2 = OverviewVM(current=cur, nxt=nxt, view_mode="CASHFLOW")

            if vm1.next != nxt or vm1.nxt != nxt:
                raise AssertionError("OverviewVM next/nxt Alias defekt")
            if vm2.next != nxt or vm2.nxt != nxt:
                raise AssertionError("OverviewVM legacy nxt defekt")

            self.ok("Contract: OverviewVM", "OK (view_mode default + next/nxt kompatibel)")
        except Exception as e:  # noqa: BLE001
            if self.strict:
                self.err("Contract: OverviewVM", f"Fehlgeschlagen: {e}")
            else:
                self.warn("Contract: OverviewVM", f"Fehlgeschlagen: {e}")

    def run_settings_paths(self, *, db_check: bool) -> None:
        try:
            from src.config.settings import get_settings  # type: ignore

            settings = get_settings()
            self.ok("Settings laden", "OK")

            db_path = Path(settings.db_path())  # type: ignore[attr-defined]
            self.ok("DB Pfad (Settings)", str(db_path))
            if db_check:
                self._sqlite_check(db_path)

            log_path = Path(settings.log_path())  # type: ignore[attr-defined]
            self.ok("Log Pfad (Settings)", str(log_path))
        except Exception as e:  # noqa: BLE001
            if self.strict:
                self.err("Settings prüfen", str(e))
            else:
                self.warn("Settings prüfen", str(e))

    def _sqlite_check(self, db_path: Path) -> None:
        if not db_path.exists():
            self.warn("SQLite Connect", f"DB Datei existiert noch nicht: {db_path}")
            return
        try:
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("PRAGMA journal_mode;")
                journal = cur.fetchone()
                cur.execute("PRAGMA foreign_keys;")
                fks = cur.fetchone()
                self.ok(
                    "SQLite Connect",
                    f"OK (journal_mode={journal[0] if journal else '?'}, foreign_keys={fks[0] if fks else '?'})",
                )
            finally:
                con.close()
        except Exception as e:  # noqa: BLE001
            self.err("SQLite Connect", f"Fehlgeschlagen: {e}")

    # ---------------- UI cold-imports + NameError-Risiko ----------------
    def run_ui_imports(self) -> None:
        os.environ.setdefault("FINANZMANAGER_DOCTOR", "1")

        ui_root = self.root / "src" / "ui"
        if not ui_root.exists():
            self.err("UI Imports", f"Fehlt: {ui_root}")
            return

        modules = list(self._discover_modules(ui_root))
        if not modules:
            self.warn("UI Imports", "Keine Module gefunden.")
            return

        imported_ok = 0
        name_risk_modules: list[tuple[str, list[str]]] = []

        for mod in modules:
            try:
                m = importlib.import_module(mod)
                imported_ok += 1
            except Exception as e:  # noqa: BLE001
                msg = f"{mod} ({type(e).__name__}: {e})"
                if self.strict:
                    self.err("UI Cold-Import", msg)
                else:
                    self.warn("UI Cold-Import", msg)
                continue

            missing = self._find_potential_missing_globals(m)
            if missing:
                name_risk_modules.append((mod, missing))

        self.ok("UI Imports", f"{imported_ok}/{len(modules)} Module importiert")

        if name_risk_modules:
            for mod, missing in name_risk_modules:
                detail = ", ".join(missing[:25])
                if len(missing) > 25:
                    detail += f", … (+{len(missing) - 25})"
                msg = f"{mod}: mögliche fehlende Globals -> {detail}"
                if self.strict:
                    self.err("UI NameError Risiko", msg)
                else:
                    self.warn("UI NameError Risiko", msg)
        else:
            self.ok("UI NameError Risiko", "Keine offensichtlichen fehlenden Globals gefunden")
        self._check_ui_double_click_bind_add()
        self._check_ui_callback_contracts()

    def _check_ui_double_click_bind_add(self) -> None:
        """Harte Regel: UI-<Double-1>-Bindings müssen add='+' nutzen.

        Hintergrund:
        - Presenter/Views überschreiben sonst globale Bindings (z.B. Sort-Reset per Header-Doppelklick).
        - add='+' sorgt dafür, dass mehrere Handler koexistieren.

        Regel:
        - Für jeden Aufruf `.bind("<Double-1>", ...)` in src/ui/**/*.py muss ein `add=` Argument vorhanden sein.
          - Fehlt `add=...` komplett => ERROR (strict-fail in --strict)
          - `add=` vorhanden aber nicht eindeutig '+' => WARN (ok, falls Variable '+')
        """
        ui_root = self.root / "src" / "ui"
        if not ui_root.exists():
            return

        bind_re = re.compile(r"\.bind\(\s*[\"\']<Double-1>[\"\']", re.MULTILINE)

        def _extract_call(text: str, start_idx: int) -> str:
            paren = 0
            i = start_idx
            while i < len(text) and text[i] != "(":
                i += 1
            if i >= len(text):
                return ""
            j = i
            while j < len(text):
                ch = text[j]
                if ch == "(":
                    paren += 1
                elif ch == ")":
                    paren -= 1
                    if paren == 0:
                        return text[i : j + 1]
                j += 1
            return text[i:]

        missing_add: set[str] = set()
        ambiguous_add: set[str] = set()

        for path in ui_root.rglob("*.py"):
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue

            for m in bind_re.finditer(content):
                call = _extract_call(content, m.start())
                compact = call.replace(" ", "").replace("\n", "")
                rel = path.relative_to(self.root).as_posix()

                if "add=" not in compact:
                    missing_add.add(rel)
                    continue

                # explicit literal plus?
                if 'add="+"' in compact or "add='+'" in compact:
                    continue

                # could still be okay if add is a variable, but warn

                # tkinter accepts add=True and converts internally to '+'
                if "add=True" in compact or "add=1" in compact:
                    continue
                ambiguous_add.add(rel)

        if missing_add:
            msg = "Fehlendes add='+' bei <Double-1> Bindings in:\n" + "\n".join([f"  - {p}" for p in sorted(missing_add)])
            if self.strict:
                self.err("UI Binding Override Risiko", msg)
            else:
                self.warn("UI Binding Override Risiko", msg)
        else:
            self.ok("UI Binding Override Risiko", "Keine <Double-1> Bindings ohne add= gefunden")

        if ambiguous_add:
            msg = "add= vorhanden, aber nicht eindeutig '+' (ok, falls Variable '+'):\n" + "\n".join([f"  - {p}" for p in sorted(ambiguous_add)])
            self.warn("UI Binding add uneindeutig", msg)
        else:
            self.ok("UI Binding add uneindeutig", "Alle <Double-1> Bindings nutzen add='+' (oder sind nicht vorhanden)")

    def _check_ui_callback_contracts(self) -> None:
        """Prüft UI-Callbacks auf Existenz (command=self.<name>, bind(..., self.<name>)).

        Verhindert Runtime-Crashes wie:
        - AttributeError: 'MainWindow' object has no attribute 'open_security_mode'
        """
        ui_root = self.root / "src" / "ui"
        if not ui_root.exists():
            return

        problems: set[str] = set()

        for path in ui_root.rglob("*.py"):
            rel = path.relative_to(self.root).as_posix()
            try:
                code = path.read_text(encoding="utf-8")
                tree = ast.parse(code, filename=rel)
            except Exception:
                continue

            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue

                methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                attrs: set[str] = set()
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Assign):
                        for tgt in sub.targets:
                            if isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id == "self":
                                attrs.add(tgt.attr)

                allowed = methods | attrs

                for call in [n for n in ast.walk(node) if isinstance(n, ast.Call)]:
                    # keyword: command=self.foo
                    for kw in call.keywords or []:
                        if kw.arg not in {"command", "postcommand"}:
                            continue
                        val = kw.value
                        if isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name) and val.value.id == "self":
                            if val.attr not in allowed:
                                problems.add(f"{rel}: {node.name} -> fehlender Callback '{val.attr}' (command=)")

                    # positional: .bind(..., self.foo)
                    if isinstance(call.func, ast.Attribute) and call.func.attr == "bind" and len(call.args) >= 2:
                        val = call.args[1]
                        if isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name) and val.value.id == "self":
                            if val.attr not in allowed:
                                problems.add(f"{rel}: {node.name} -> fehlender Callback '{val.attr}' (bind)")

        if problems:
            msg = "\n".join([f"  - {p}" for p in sorted(problems)])
            if self.strict:
                self.err("UI Callback Contract", msg)
            else:
                self.warn("UI Callback Contract", msg)
        else:
            self.ok("UI Callback Contract", "Alle command=/bind Callbacks vorhanden")

    def _discover_modules(self, base: Path) -> Iterator[str]:
        for p in sorted(base.rglob("*.py")):
            rel = p.relative_to(self.root).as_posix()
            if rel.endswith("/__init__.py"):
                rel = rel[: -len("/__init__.py")]
            else:
                rel = rel[:-3]
            mod = rel.replace("/", ".")
            if mod:
                yield mod

    def _find_potential_missing_globals(self, module) -> list[str]:
        mod_globals = set(getattr(module, "__dict__", {}).keys())
        builtins_names = set(getattr(builtins, "__dict__", {}).keys())

        missing: set[str] = set()

        for obj in self._iter_defined_objects(module):
            code = self._unwrap_to_code(obj)
            if code is None:
                continue
            for c in self._iter_code_objects(code):
                for name in self._load_global_names(c):
                    if name in mod_globals or name in builtins_names:
                        continue
                    if name in {"__annotations__", "__class__", "__qualname__"}:
                        continue
                    missing.add(name)

        return sorted(missing)

    def _iter_defined_objects(self, module) -> Iterator[object]:
        mod_file = getattr(module, "__file__", None)
        mod_file_res = str(Path(mod_file).resolve()) if mod_file else None

        def _is_from_module_file(fn: FunctionType) -> bool:
            if not mod_file_res:
                return True
            try:
                src = inspect.getsourcefile(fn) or inspect.getfile(fn)
            except Exception:  # noqa: BLE001
                return False
            if not src:
                return False
            try:
                return str(Path(src).resolve()) == mod_file_res
            except Exception:  # noqa: BLE001
                return False

        for _name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and getattr(obj, "__module__", None) == module.__name__:
                if _is_from_module_file(obj):
                    yield obj
            elif inspect.isclass(obj) and getattr(obj, "__module__", None) == module.__name__:
                for _m_name, m_obj in inspect.getmembers(obj):
                    fn = self._unwrap_descriptor(m_obj)
                    if fn is None:
                        continue
                    if getattr(fn, "__module__", None) != module.__name__:
                        continue
                    if _is_from_module_file(fn):
                        yield fn

    @staticmethod
    def _unwrap_descriptor(obj: object) -> FunctionType | None:
        if isinstance(obj, staticmethod):
            return obj.__func__
        if isinstance(obj, classmethod):
            return obj.__func__
        if inspect.isfunction(obj):
            return obj
        return None

    @staticmethod
    def _unwrap_to_code(obj: object) -> CodeType | None:
        if inspect.isfunction(obj):
            return obj.__code__
        return None

    @staticmethod
    def _iter_code_objects(code: CodeType) -> Iterator[CodeType]:
        yield code
        for c in code.co_consts:
            if isinstance(c, CodeType):
                yield from Doctor._iter_code_objects(c)

    @staticmethod
    def _load_global_names(code: CodeType) -> set[str]:
        names: set[str] = set()
        try:
            for ins in dis.get_instructions(code):
                if ins.opname == "LOAD_GLOBAL" and isinstance(ins.argval, str):
                    names.add(ins.argval)
        except Exception:  # noqa: BLE001
            return names
        return names

    def summary_exit_code(self) -> int:
        errs = sum(1 for r in self.results if r.level == "ERR")
        warns = sum(1 for r in self.results if r.level == "WARN")
        if errs:
            return 2
        if warns:
            return 1
        return 0

    def print_report(self) -> None:
        def fmt(r: CheckResult) -> str:
            prefix = {"OK": "✅", "WARN": "⚠️", "ERR": "❌"}.get(r.level, "-")
            if r.detail:
                return f"{prefix} {r.title}\n    {r.detail}"
            return f"{prefix} {r.title}"

        print("\n=== Finanzmanager Doctor ===\n")
        for r in self.results:
            print(fmt(r))

        errs = sum(1 for r in self.results if r.level == "ERR")
        warns = sum(1 for r in self.results if r.level == "WARN")
        oks = sum(1 for r in self.results if r.level == "OK")

        print("\n--- Zusammenfassung ---")
        print(f"OK: {oks} | Warnungen: {warns} | Fehler: {errs}")
        print("Exit Codes: 0=OK, 1=Warnungen, 2=Fehler\n")


def _find_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Repo/Build/Runtime Healthcheck (Finanzmanager)")
    ap.add_argument("--imports", action="store_true", help="Imports prüfen (Dependencies + Kernmodule)")
    ap.add_argument("--ui-imports", action="store_true", help="Nur UI-Module cold-importen + NameError-Risiko prüfen")
    ap.add_argument("--no-ui-imports", action="store_true", help="Bei --imports: UI-Imports überspringen")
    ap.add_argument("--contracts", action="store_true", help="Contract Checks (DTO/Service Schnittstellen)")
    ap.add_argument("--settings", action="store_true", help="Settings laden und DB/Log Pfade prüfen")
    ap.add_argument("--db-check", action="store_true", help="Wenn Settings aktiv: SQLite Connect testen")
    ap.add_argument("--strict", action="store_true", help="Strenger Modus: Fehler = ERR (statt WARN)")

    args = ap.parse_args(list(argv) if argv is not None else None)

    root = _find_repo_root()
    doc = Doctor(root, strict=bool(args.strict))

    doc.run_basics()

    if args.imports:
        doc.run_imports(include_ui=not bool(args.no_ui_imports))
        doc.run_contracts()

    if args.ui_imports and not args.imports:
        doc.run_ui_imports()

    if args.contracts and not args.imports:
        doc.run_contracts()

    if args.settings:
        doc.run_settings_paths(db_check=bool(args.db_check))

    doc.print_report()
    return doc.summary_exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
