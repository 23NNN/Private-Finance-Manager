# Developer Guide

## Repo Layout

- Source Code: `src/` (Package: `src`)
- Tests: `tests/` (adds Repo-Root to `sys.path`)
- Documentation: `docs/`
- Scripts/Tooling: `scripts/`
- Do not commit build/distribution artifacts: `dist/`, `build/`, `.venv/`

## Setup (Windows)

Recommended: local venv (stable for build + SQLCipher).

```powershell
cd Private-Finance-Manager
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip wheel setuptools
.\.venv\Scripts\python -m pip install -e .[dev]
```

Start:
```powershell
.\.venv\Scripts\python app.py
```

### Security Extras (SQLCipher)

```powershell
.\.venv\Scripts\python -m pip install -e .[dev,security]
```

If `pysqlcipher3` cannot be built on Windows, use one of the alternatives:

```powershell
.\.venv\Scripts\python -m pip install sqlcipher3
# or:
.\.venv\Scripts\python -m pip install pysqlcipher3-binary
```

## Architecture Rules

- Strict separation:
  - `src/ui/` (Tkinter/ttk Views + Presenter, MVP)
  - `src/application/` (Services / DTOs)
  - `src/domain/` (Policies / pure logic)
  - `src/infrastructure/` (DB/Repos/UoW/Logging)
  - `src/security/` (Security backend: SQLCipher + Fallback DPAPI)
- Internal imports always use `from src...`.

## Database & Migration

- SQLite + SQLAlchemy 2.x
- Migrations via Alembic under `src/infrastructure/db/migrations/`.
- `upgrade_db_if_possible()` is executed on startup.
- `schema_patch.py` exists as a best-effort supplement for MVP scenarios.

### Security / DB Formats

- Mode **None**: `finanz.db` is plain SQLite.
- Mode **PIN**/**Device Security**: `finanz.db` is SQLCipher (crash-safe encrypted).
- If SQLCipher is not available:
  - Fallback (DPAPI) uses `finanz.db.enc` and a temporary `.work/finanz_work.db`.
  - If `finanz.db` is already SQLCipher, the fallback cannot open it → SQLCipher must be installed.

Config:
- `security.json` is located in the data directory and stores the mode + (hashed) PIN data or device key handle.

## Tooling / Scripts

### Doctor / Pre-Build

- `python scripts/doctor.py --imports --contracts --strict`
  - Import audit (incl. UI cold-import)
  - UI contracts (callback bindings must exist)
  - UI binding rule: `<Double-1>` bindings must be additive (`add="+"`/`add=True`)
- `python scripts/pre_build_check.py` – normalize + audit + doctor

### Normalize Imports

- `python scripts/normalize_imports.py` – converts internal imports to `src.*` (idempotent)
- `python scripts/find_legacy_imports.py` – reports old imports without `src.`

### Demo / Seed

- `python scripts/build_demo_data.py` – full demo
- `python scripts/build_demo_data.py --mini` – 2 months (fast)
- `scripts/run_demo.ps1` / `scripts/run_demo.bat` – demo start (mini)

### Legacy Cleanup (Hourly Wage)

- `python scripts/migrate_hourly_bw_by.py` – migration BW/BY → neutral fields
- `python scripts/finalize_hourly_legacy_cleanup.py --apply` – sets BW/BY permanently to 0 (idempotent)

### Patch Workflow (ZIP Updater)

- `python scripts/apply_zip_update.py` (interactive)
- Default: dry run; with `--apply` writes changes; creates backups under `.patch_backups/`
- Optional: post-checks (normalize_imports, doctor)

## Tests

- Focus: Domain Policies + Services are testable without UI.
- Tests import via `src` (Repo-Root in `sys.path` via `tests/conftest.py`).

Run:
```powershell
pytest -q
```

## Packaging (PyInstaller)

- Use the spec: `scripts/finanzmanager.spec`
- One-liner:
```powershell
.\.venv\Scripts\python -m PyInstaller scripts\finanzmanager.spec
```

- Wrapper (clean build/dist + colored output):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

## Collaboration with AI Assistants (Export)

```powershell
python scripts/export_context.py
```

Generates a ZIP containing:
- `src/`, `tests/`, `docs/`, `scripts/`, `pyproject.toml`, `README.md`, `app.py`
without `.git`, `.venv`, `dist/`, `build`.

---

## Common Tasks (Quick Navigation)

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
