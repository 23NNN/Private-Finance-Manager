# CLAUDE.md – Finance Manager Project Context

> At the start of a new session: read this file → run `doctor.py` + `i18n_audit.py` → start with Priority 1.

---

## Dokumentationsregeln

- Diese Datei darf NICHT mehr als 300 Zeilen haben.
- Bei Überschreitung: Inhalte in separate Dateien auslagern, in dieser Datei nur darauf verweisen.
- Sensible ausgelagerte Inhalte (Keys, Tokens, private Infos) müssen in `.gitignore` eingetragen werden.
- Beispiel: Lange Architektur-Doku → `docs/architecture/overview.md` (public)
- Beispiel: Private Notizen, Handoff → `HANDOVER.md` (in `.gitignore`)

---

## Project Overview

**Windows Desktop App** (Tkinter/ttk) for managing personal finances.
Architecture: Clean Architecture + MVP Pattern.
Language: Python 3.11 | DB: SQLite + SQLAlchemy 2.x | Optional: SQLCipher (encryption)

> Full annotated repo structure → `docs/architecture/overview.md`

---

## Layer Responsibilities

| Layer | Path | Touch when… |
|-------|------|-------------|
| **UI / View** | `src/ui/<module>/view.py` | Change layout, labels, widgets, button handlers |
| **UI / Presenter** | `src/ui/<module>/presenter.py` | Change what data is loaded/shown or how user actions translate to service calls |
| **Common UI** | `src/ui/common/` | Change shared widgets, dialogs, i18n functions |
| **Service** | `src/application/services/` | Change business rules, orchestration, validation |
| **DTO** | `src/application/dto/` | Add/remove fields passed between layers |
| **Domain Policy** | `src/domain/policies/` | Change calculation algorithms (pay, loan, savings) |
| **Repository** | `src/infrastructure/repositories/` | Change DB queries, add filters, new fetch methods |
| **ORM / Enums** | `src/infrastructure/db/orm_models.py` | Add/change DB columns or enum values |
| **Migration** | `src/infrastructure/db/migrations/` | After every ORM schema change; seed new i18n keys |
| **Security** | `src/security/` | Change encryption mode, key handling, DB access |
| **Config** | `src/config/settings.py` | Change app-wide constants or default paths |

---

## Feature → File Lookup

| Feature | View | Presenter | Service | Repository | ORM/DTO |
|---------|------|-----------|---------|------------|---------|
| **Expenses** | `ui/expenses/view.py` | `ui/expenses/presenter.py` | `services/expense_service.py` | `repositories/expenses.py` | `orm_models.py` · `dto/expenses.py` |
| **Income (fixed)** | `ui/income/view.py` · `fixed_dialog.py` | `ui/income/presenter.py` | `services/income_service.py` | `repositories/income_fixed.py` | `orm_models.py` · `dto/incomes.py` |
| **Income (hourly)** | `ui/income/view.py` · `hourly_dialog.py` | `ui/income/presenter.py` | `services/income_service.py` | `repositories/income_hourly.py` | `domain/policies/hourly_pay_policy.py` |
| **Accounts** | `ui/accounts/view.py` | `ui/accounts/presenter.py` | `services/account_service.py` | `repositories/accounts.py` | `orm_models.py` · `dto/accounts.py` |
| **Overview / Dashboard** | `ui/overview/view.py` | `ui/overview/presenter.py` | `services/overview_service.py` | *(multiple)* | `dto/overview.py` |
| **Loans** | *(no dedicated tab)* | `ui/expenses/presenter.py` | `services/loan_service.py` | `repositories/loans.py` · `loan_events.py` | `dto/loans.py` · `domain/policies/loan_policy.py` |
| **Savings** | *(no dedicated tab)* | *(in overview presenter)* | `services/savings_service.py` | `repositories/savings.py` | `dto/savings.py` · `domain/policies/savings_policy.py` |
| **Employers / Pay rules** | *(in income dialogs)* | `ui/income/presenter.py` | `services/employer_service.py` | `repositories/employers.py` · `pay_rules.py` | `dto/employers.py` |
| **Categories** | `ui/common/category_manager.py` | *(inline)* | `services/expense_service.py` | `repositories/expenses.py` | `orm_models.py` |
| **Import CSV/Excel** | `ui/common/import_export_dialog.py` · `import_report_dialog.py` | *(inline)* | `services/import_service.py` | `repositories/import_runs.py` | `importers/csv_importer.py` · `excel_importer.py` |
| **Export** | `ui/common/import_export_dialog.py` | *(inline)* | `services/export_service.py` | *(multiple)* | `infrastructure/io/csv_writer.py` |
| **i18n / Translations** | `ui/common/i18n.py` | – | `services/i18n_service.py` | `repositories/i18n_strings.py` | `migrations/schema_patch.py` |
| **App settings** | `ui/main_window.py` (menu) | – | *(direct repo access)* | `repositories/app_settings.py` | – |
| **Security mode** | `ui/security/mode_dialog.py` · `lock_overlay.py` | – | `services/security_service.py` | – | `security/manager.py` · `bootstrap.py` |
| **Backup** | `ui/main_window.py` (File menu) | – | `services/backup_service.py` | – | – |
| **DB health / Maintenance** | *(diagnostics menu)* | – | `services/maintenance_service.py` · `diagnostics_service.py` | – | `db/healthcheck.py` |
| **Period / Date filter** | `ui/common/period_selector.py` | *(any presenter)* | *(any service)* | – | `domain/models/period.py` |

> Step-by-step guides for common tasks → `docs/dev_guide.md` (section "Common Tasks")

---

## Import Conventions (critical)

```python
# ALWAYS with src. prefix
from src.ui.common.i18n import tr, trf
from src.application.services.i18n_service import I18nService

# NEVER without src. prefix
from ui.common.i18n import tr  # WRONG
```

- `app.py` appends **Repo-Root** (not `src/`) to `sys.path`
- `tests/conftest.py` sets sys.path to Repo-Root

---

## Working Rules (mandatory)

- **No questions** – make reasonable assumptions and implement immediately
- **Edit files directly** – Claude Code writes to the repo, no ZIP workflow needed
- **FULL-REPLACE per file** – always write complete file content
- **No absolute system paths** in output
- **Git as backup:** `git checkout -b feature/xyz` before major changes
- **Save completed tasks to CLAUDE.md** – update this file after each task is done

---

## i18n System

### Functions (`src/ui/common/i18n.py`)
```python
tr(key: str) -> str               # Translation via DB
trf(key: str, /, **kwargs) -> str # Translate + str.format(**kwargs)
```

### Service (`src/application/services/i18n_service.py`)
Fallback chain: `selected language → English (en) → key`
Supported languages: `de`, `en`, `fr`, `es`, `it` — stored in `app_setting` key `ui.language`

**Rule:** With non-German languages, NO German word must be visible (no German leak).

### i18n Pattern for new UI strings
```python
from src.ui.common.i18n import tr, trf
label = tk.Label(text=tr("income.title"))
msg = trf("dialog.delete_confirm", name=entry_name)
```
New keys must be seeded for **all 5 languages** in `schema_patch.py`.

---

## i18n Status (all complete ✅)

Patches 1–006b + Tasks 1a–3 all done. 108 audit candidates remaining – all confirmed false positives (enum values, Tkinter types, font names, dev-only logger strings).

**Intentionally German data (do NOT translate):**
- `excel_importer.py` / `import_service.py` → German Excel column headers
- `parsers.py` → German month name parsing
- `schema_patch.py` `"de": "..."` entries → German seed translations
- `import_report_dialog.py` `_SHEET_KEY_MAP` → Excel sheet name keys

---

## Open Issues / Next Priorities

**Aktueller Stand:** `main` = v1.2.0 (released 2026-06-26)

v1.2.0 enthält:
- IDEA-03: Intervall-Filter für Fixkosten ✅
- IDEA-02: Verschieben-Button + vollständiges Kontextmenü ✅
- IDEA-01: CustomTkinter Integration ✅ (CTkTabview, dark mode default, Appearance-Menü)
- fix: visuelle Lücken (Canvas-bg, Höhenfüllung, apply_for_mode Timing) ✅

### Offenes / Nächste Schritte
- Optional: CTkButton für Toolbar-Buttons (aktuell ttk.Button, dark via TTK-Styling)
- Budgetplanung, Reporting/Charts als nächstes größeres Feature

---

## Security

| Mode | DB Format |
|------|-----------|
| None | Plain SQLite `finanz.db` |
| PIN / Device protection | SQLCipher `finanz.db` |
| SQLCipher not available | DPAPI fallback: `finanz.db.enc` + `.work/finanz_work.db` |

- `sqlcipher3` preferred; `pysqlcipher3` only if buildable
- `security.json` in data directory, NEVER commit → add to .gitignore
- `.work/` → temporary encrypted DB → add to .gitignore

---

## UI Features

### Treeview Sorting
- Header click: sort + arrow ▲/▼ | Header double-click: reset | Row double-click: edit dialog

### Binding Rule (Doctor checks this)
```python
widget.bind("<Double-1>", handler, add="+")  # add="+" is mandatory
```

---

## Data Model (Core Enums) – all in `orm_models.py`

```python
class PayoutTiming(str, enum.Enum): BEGINNING, MID
PaymentTiming = PayoutTiming  # Compatibility alias

class PayRuleType(str, enum.Enum):
    HOURLY_WAGE, SALARY, NIGHT, SUNDAY, HOLIDAY, OVERTIME

class PayRuleUnit(str, enum.Enum):
    EUR_PER_HOUR, EUR_PER_MONTH, MULTIPLIER

class ExpenseGroup(str, enum.Enum): FIX, VARIABLE, LOAN
class RecurringStatus(str, enum.Enum): ACTIVE, INACTIVE
class VariableStatus(str, enum.Enum): OPEN, PAID, CANCELLED
class PayBucket(str, enum.Enum): BEGINNING, MID, NONE
class AllocationOverride(str, enum.Enum): CASHFLOW, ALLOCATE_MONTHLY, ALLOCATE_QUARTERLY

class LoanEventType(str, enum.Enum):
    PAYMENT, EXTRA_PAYMENT, RATE_CHANGE, INTEREST_CHANGE
    INTEREST    # auto-generated monthly accrual (v1.1)
    REFINANCING # increase loan principal (v1.1)
    NOTE
```

---

## Tooling Reference

```powershell
# Health checks (before every commit/build)
python scripts/doctor.py --imports --contracts --strict
python scripts/i18n_audit.py
python scripts/pre_build_check.py

# Fix imports
python scripts/normalize_imports.py
python scripts/find_legacy_imports.py

# Tests
pytest -q

# Demo data
python scripts/build_demo_data.py --mini

# Build EXE
.\.venv\Scripts\python -m PyInstaller scripts\finanzmanager.spec
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

---

## Setup (Windows)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip wheel setuptools
.\.venv\Scripts\python -m pip install -e .[dev]
.\.venv\Scripts\python -m pip install sqlcipher3   # optional
.\.venv\Scripts\python app.py
```

---

## Session-Start Checklist

```bash
python scripts/doctor.py --imports --contracts --strict
python scripts/i18n_audit.py
# → Check "Open Issues / Next Priorities" for next task
```
