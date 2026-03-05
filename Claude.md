# CLAUDE.md – Finance Manager Project Context

> At the start of a new session: read this file → run `doctor.py` + `i18n_audit.py` → start with Priority 1.

---

## Project Overview

**Windows Desktop App** (Tkinter/ttk) for managing personal finances.
Architecture: Clean Architecture + MVP Pattern.
Language: Python 3.11 | DB: SQLite + SQLAlchemy 2.x | Optional: SQLCipher (encryption)

---

## Repo Structure (actual files)

```
Private-Finance-Manager/
├── app.py                              # Entry point – sys.path setup, bootstrap, main loop
├── pyproject.toml                      # Build config; include=["src*"], where=["."]
├── CLAUDE.md                           # This file
├── src/
│   ├── config/settings.py              # App-wide constants (paths, defaults)
│   ├── ui/
│   │   ├── main_window.py              # Root Tk window, tab layout, menu bar
│   │   ├── common/
│   │   │   ├── i18n.py                 # tr(), trf(), init_i18n() – translation entry point
│   │   │   ├── controls.py             # Reusable form widgets (LabeledEntry, etc.)
│   │   │   ├── dialogs.py              # Generic confirm/info/input dialogs
│   │   │   ├── validation.py           # UI-side input validation helpers
│   │   │   ├── scroll_area.py          # Scrollable frame wrapper
│   │   │   ├── treeview_sort.py        # Sortable Treeview (header click/double-click)
│   │   │   ├── period_selector.py      # Month/year filter widget
│   │   │   ├── error_dialog.py         # Error display with traceback
│   │   │   ├── totals_footer.py        # Sum row shown below Treeview
│   │   │   ├── dataset_dialog.py       # DB file / dataset switcher dialog
│   │   │   ├── category_manager.py     # CRUD dialog for expense categories
│   │   │   ├── import_export_dialog.py # CSV/Excel import + template download dialog
│   │   │   └── import_report_dialog.py # Shows result after import run
│   │   ├── accounts/
│   │   │   ├── view.py                 # Accounts tab – list + CRUD buttons
│   │   │   └── presenter.py            # Accounts business logic bridge
│   │   ├── expenses/
│   │   │   ├── view.py                 # Expenses tab – Treeview, filter, totals
│   │   │   └── presenter.py            # Expenses business logic bridge
│   │   ├── income/
│   │   │   ├── view.py                 # Income tab – fixed + hourly sections
│   │   │   ├── presenter.py            # Income business logic bridge
│   │   │   ├── fixed_dialog.py         # Add/edit fixed income entry dialog
│   │   │   └── hourly_dialog.py        # Add/edit hourly income entry dialog
│   │   ├── overview/
│   │   │   ├── view.py                 # Dashboard tab – charts + KPI tiles
│   │   │   └── presenter.py            # Overview aggregation bridge
│   │   └── security/
│   │       └── mode_dialog.py          # Security mode setup dialog (PIN, Device, None)
│   ├── application/
│   │   ├── services/
│   │   │   ├── account_service.py      # Account CRUD + balance calculations
│   │   │   ├── expense_service.py      # Expense CRUD + category handling
│   │   │   ├── income_service.py       # Fixed + hourly income CRUD + pay calc
│   │   │   ├── loan_service.py         # Loan lifecycle + event management
│   │   │   ├── savings_service.py      # Savings goals + contribution tracking
│   │   │   ├── overview_service.py     # Dashboard aggregation queries
│   │   │   ├── import_service.py       # Orchestrates CSV/Excel import pipeline
│   │   │   ├── export_service.py       # Data export to CSV/Excel
│   │   │   ├── i18n_service.py         # Translation lookup + fallback chain
│   │   │   ├── employer_service.py     # Employer/pay-rule management
│   │   │   ├── reference_data_service.py # Dropdowns: categories, employers, etc.
│   │   │   ├── security_service.py     # Security mode switching
│   │   │   ├── backup_service.py       # DB backup/restore
│   │   │   ├── maintenance_service.py  # DB vacuum, integrity checks
│   │   │   └── diagnostics_service.py  # Health report generation
│   │   ├── dto/
│   │   │   ├── common.py               # Shared DTO base types
│   │   │   ├── accounts.py             # AccountDTO
│   │   │   ├── expenses.py             # ExpenseDTO, CategoryDTO
│   │   │   ├── incomes.py              # FixedIncomeDTO, HourlyIncomeDTO
│   │   │   ├── employers.py            # EmployerDTO, PayRuleDTO
│   │   │   ├── loans.py                # LoanDTO, LoanEventDTO
│   │   │   ├── savings.py              # SavingsGoalDTO
│   │   │   ├── overview.py             # DashboardDTO, KpiDTO
│   │   │   └── security.py             # SecurityConfigDTO
│   │   ├── importers/
│   │   │   ├── csv_importer.py         # CSV → domain objects
│   │   │   ├── excel_importer.py       # Excel → domain objects (German column headers)
│   │   │   └── utils.py                # Import helper functions
│   │   └── validators/parsers.py       # Date/number parsing (incl. German month names)
│   ├── domain/
│   │   ├── models/period.py            # Period value object (month/year range)
│   │   ├── policies/
│   │   │   ├── hourly_pay_policy.py    # Gross pay calc for hourly workers
│   │   │   ├── loan_policy.py          # Loan amortization rules
│   │   │   ├── recurring_policy.py     # Recurring expense/income logic
│   │   │   └── savings_policy.py       # Savings contribution rules
│   │   └── errors.py                   # Domain exception types
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── engine.py               # SQLAlchemy engine factory (plain + SQLCipher)
│   │   │   ├── orm_models.py           # All ORM models + all Enums
│   │   │   ├── healthcheck.py          # run_healthcheck(), format_report()
│   │   │   └── migrations/
│   │   │       ├── runner.py           # upgrade_db_if_possible() – Alembic entry point
│   │   │       ├── schema_patch.py     # Seed data for i18n strings + app_settings
│   │   │       ├── env.py              # Alembic environment config
│   │   │       └── versions/           # 0001–0004 migration scripts
│   │   ├── repositories/
│   │   │   ├── base.py                 # BaseRepository with common query helpers
│   │   │   ├── accounts.py             # AccountRepository
│   │   │   ├── expenses.py             # ExpenseRepository
│   │   │   ├── incomes.py              # IncomeRepository (unified)
│   │   │   ├── income_fixed.py         # FixedIncomeRepository
│   │   │   ├── income_hourly.py        # HourlyIncomeRepository
│   │   │   ├── income_special.py       # SpecialIncomeRepository
│   │   │   ├── employers.py            # EmployerRepository
│   │   │   ├── pay_rules.py            # PayRuleRepository
│   │   │   ├── loans.py                # LoanRepository
│   │   │   ├── loan_events.py          # LoanEventRepository
│   │   │   ├── savings.py              # SavingsRepository
│   │   │   ├── import_runs.py          # ImportRunRepository (audit log)
│   │   │   ├── app_settings.py         # AppSettingsRepository (key-value store)
│   │   │   └── i18n_strings.py         # I18nStringRepository
│   │   ├── io/
│   │   │   ├── csv_reader.py           # Low-level CSV file reading
│   │   │   ├── csv_writer.py           # Low-level CSV file writing
│   │   │   └── excel_reader.py         # Low-level Excel reading (openpyxl)
│   │   ├── logging_setup.py            # Logging config (file + console)
│   │   └── unit_of_work.py             # UnitOfWork – transaction scope
│   └── security/
│       ├── bootstrap.py                # Security init on app start
│       ├── manager.py                  # SecurityManager – mode switching entry point
│       ├── secure_db.py                # Encrypted DB handling
│       ├── sqlcipher_db.py             # SQLCipher connection wrapper
│       ├── sqlcipher_driver.py         # SQLCipher dialect for SQLAlchemy
│       ├── dpapi.py                    # Windows DPAPI fallback encryption
│       └── security_config.py          # security.json read/write
├── scripts/
│   ├── doctor.py                       # Full codebase health check (imports, contracts)
│   ├── i18n_audit.py                   # Find non-tr() UI strings
│   ├── pre_build_check.py              # Pre-EXE build validation
│   ├── normalize_imports.py            # Auto-fix import prefixes
│   ├── find_legacy_imports.py          # Report legacy import patterns
│   ├── build_demo_data.py              # Seed DB with demo data
│   ├── export_context.py               # Did generate context ZIP for old GPT-Workflow
│   ├── collect_diagnostics.py          # Collect diagnostics report
│   ├── apply_zip_update.py             # Apply patch ZIP
│   ├── restructure_repo.py             # One-time repo restructure helper
│   ├── migrate_hourly_bw_by.py         # One-time hourly data migration
│   ├── finalize_hourly_legacy_cleanup.py # One-time legacy cleanup
│   ├── build_exe.ps1                   # PowerShell EXE build script
│   └── finanzmanager.spec              # PyInstaller spec
├── tests/
│   ├── conftest.py                     # sys.path setup + shared fixtures
│   ├── unit/                           # Pure unit tests
│   └── integration/                    # DB + service integration tests
└── docs/
    ├── architecture/overview.md + data_model.md + components.md
    ├── dev_guide.md + user_guide.md + operations.md
    └── diagnostics/
```

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
| **Loans** | *(no dedicated tab)* | *(in income presenter)* | `services/loan_service.py` | `repositories/loans.py` · `loan_events.py` | `dto/loans.py` · `domain/policies/loan_policy.py` |
| **Savings** | *(no dedicated tab)* | *(in overview presenter)* | `services/savings_service.py` | `repositories/savings.py` | `dto/savings.py` · `domain/policies/savings_policy.py` |
| **Employers / Pay rules** | *(in income dialogs)* | `ui/income/presenter.py` | `services/employer_service.py` | `repositories/employers.py` · `pay_rules.py` | `dto/employers.py` |
| **Categories** | `ui/common/category_manager.py` | *(inline)* | `services/expense_service.py` | `repositories/expenses.py` | `orm_models.py` |
| **Import CSV/Excel** | `ui/common/import_export_dialog.py` · `import_report_dialog.py` | *(inline)* | `services/import_service.py` | `repositories/import_runs.py` | `importers/csv_importer.py` · `excel_importer.py` |
| **Export** | `ui/common/import_export_dialog.py` | *(inline)* | `services/export_service.py` | *(multiple)* | `infrastructure/io/csv_writer.py` |
| **i18n / Translations** | `ui/common/i18n.py` | – | `services/i18n_service.py` | `repositories/i18n_strings.py` | `migrations/schema_patch.py` |
| **App settings** | `ui/main_window.py` (menu) | – | *(direct repo access)* | `repositories/app_settings.py` | – |
| **Security mode** | `ui/security/mode_dialog.py` | – | `services/security_service.py` | – | `security/manager.py` · `bootstrap.py` |
| **DB health / Maintenance** | *(diagnostics menu)* | – | `services/maintenance_service.py` · `diagnostics_service.py` | – | `db/healthcheck.py` |
| **Period / Date filter** | `ui/common/period_selector.py` | *(any presenter)* | *(any service)* | – | `domain/models/period.py` |

---

## Quick Navigation: Common Tasks

### Add/change a UI label or text
1. Find `tr("key")` call in `src/ui/<module>/view.py`
2. Add key seed to `src/infrastructure/db/migrations/schema_patch.py` (all 5 langs)
3. Run `python scripts/i18n_audit.py` to verify

### Add a new field to Expenses / Income / Accounts
1. `src/infrastructure/db/orm_models.py` – add column
2. `src/infrastructure/db/migrations/versions/` – new Alembic file
3. `src/application/dto/<module>.py` – add field to DTO
4. `src/infrastructure/repositories/<module>.py` – update queries
5. `src/application/services/<module>_service.py` – expose in service
6. `src/ui/<module>/presenter.py` + `view.py` – display/edit

### Change income calculation logic
→ `src/domain/policies/hourly_pay_policy.py` or `recurring_policy.py`
→ `src/application/services/income_service.py`

### Fix/change a dialog or popup
→ `src/ui/common/dialogs.py` (generic) OR `src/ui/<module>/view.py` (module-specific)

### Add a new i18n translation key
→ Add seed in `src/infrastructure/db/migrations/schema_patch.py` (5 langs)
→ Run `python scripts/i18n_audit.py`

### Change CSV/Excel import behavior
→ `src/application/importers/csv_importer.py` or `excel_importer.py`
→ `src/application/services/import_service.py`
→ `src/ui/common/import_export_dialog.py`

### Change security / encryption behavior
→ `src/security/manager.py` → `src/security/bootstrap.py` → `src/security/secure_db.py`

### Change DB schema
→ `src/infrastructure/db/orm_models.py` + new migration in `migrations/versions/`
→ `src/infrastructure/db/migrations/runner.py` (auto-runs on startup)

### Fix startup / import error
→ `app.py` (sys.path, bootstrap order)
→ `src/infrastructure/db/engine.py`
→ `src/security/bootstrap.py`

### Change application settings/constants
→ `src/config/settings.py`

### Change treeview sort or display behavior
→ `src/ui/common/treeview_sort.py` + `src/ui/<module>/view.py`

### Change period/date filter behavior
→ `src/ui/common/period_selector.py` + `src/domain/models/period.py`

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

*(No open tasks — update this section before starting new development)*

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

# Generate context ZIP
python scripts/export_context.py
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