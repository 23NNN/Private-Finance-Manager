# Architecture Overview

## Goal
Robust, maintainable Windows desktop app for real-world use:
- stable DB (SQLite)
- optional DB encryption (SQLCipher, crash-safe)
- logging/error handling
- clear separation of UI / Use Cases / Domain / Infrastructure
- high testability

## Layers

### UI (`src/ui/`) — MVP Pattern
- **View**: pure widgets + events. Views contain no DB/business logic.
- **Presenter**: logic, filtering, sorting, dialogs, error handling. Orchestrates UI ↔ Services.

Global UI conventions:
- Sorting by column header (centralized)
- Double-click on column header resets sort order
- Tabs are embedded in scroll areas (small monitors)

### Application (`src/application/`)
- **Services** encapsulate use cases such as: Import/Export, Overview aggregations, Income/Expenses/Loans CRUD, Security Mode/PIN Change (Rekey)
- **DTOs** for data transfer between layers
- **Validators/Parsers** for input handling

### Domain (`src/domain/`)
- **Policies**: pure functions (e.g. loan status per month, hourly wage policy, savings rules)
- No side effects, no DB/IO/GUI dependencies

### Infrastructure (`src/infrastructure/`)
- **SQLAlchemy ORM Models** represent DB tables
- **Repositories** encapsulate SQL/queries
- **UnitOfWork** manages session/transaction
- **Migrations** via Alembic under `src/infrastructure/db/migrations/`
- **Logging** centralized in `src/infrastructure/logging_setup.py`

### Security (`src/security/`)
- Encapsulates security backends: SQLCipher (crash-safe, DB remains encrypted) and Fallback DPAPI wrapper (at-rest encrypted; work DB during runtime)
- Configuration in `security.json`
- UI entry point via the "Security" menu

## Data Flow
```
UI → Presenter → Service → Repository/UoW → DB
```

## Out of Scope

- No cloud/bank sync
- No online accounts

---

## Repo Structure (annotated)

```
Private-Finance-Manager/
├── app.py                              # Entry point – sys.path setup, bootstrap, main loop
├── pyproject.toml                      # Build config; include=["src*"], where=["."]
├── CLAUDE.md                           # Project context for Claude Code sessions
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
│   │   ├── services/                   # 15 service modules (CRUD, import, export, i18n, …)
│   │   ├── dto/                        # 9 DTO modules for inter-layer data transfer
│   │   ├── importers/                  # csv_importer.py, excel_importer.py, utils.py
│   │   └── validators/parsers.py       # Date/number parsing (incl. German month names)
│   ├── domain/
│   │   ├── models/period.py            # Period value object (month/year range)
│   │   ├── policies/                   # hourly_pay_policy, loan_policy, recurring_policy, savings_policy
│   │   └── errors.py                   # Domain exception types
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── engine.py               # SQLAlchemy engine factory (plain + SQLCipher)
│   │   │   ├── orm_models.py           # All ORM models + all Enums
│   │   │   ├── healthcheck.py          # run_healthcheck(), format_report()
│   │   │   └── migrations/             # Alembic env + runner + schema_patch + versions/
│   │   ├── repositories/               # 15 repository modules
│   │   ├── io/                         # csv_reader, csv_writer, excel_reader
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
├── scripts/                            # doctor.py, i18n_audit.py, build_demo_data.py, build_exe.ps1, …
├── tests/
│   ├── conftest.py                     # sys.path setup + shared fixtures
│   ├── unit/                           # Pure unit tests (domain policies + services)
│   └── integration/                    # DB + service integration tests
└── docs/
    ├── architecture/overview.md + data_model.md + components.md
    ├── dev_guide.md + user_guide.md + operations.md
    └── diagnostics/
```
