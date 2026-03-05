# Operations / Support

## Storage Locations (Windows)

Storage locations are determined via `src/config/settings.py`.

- **Data directory (DB + security.json):**
  - Default: `%APPDATA%\Finanzmanager` (via `platformdirs`)
  - Override: `FINANZMANAGER_DATA_DIR`
  - Portable: `FINANZMANAGER_PORTABLE=1` (stores in `data/` next to the EXE)

- **Logs:**
  - Default: `%LOCALAPPDATA%\Finanzmanager\Logs` (via `platformdirs`)
  - Override: `FINANZMANAGER_LOG_DIR`
  - Portable: `data/logs`

When an error dialog appears, the DB and log paths are directly visible.

## Security & Backups

Depending on the mode, different files are relevant:

- **None:** `finanz.db` (plain SQLite)
- **PIN / Device Security:** `finanz.db` (SQLCipher)
- **Fallback (SQLCipher missing):**
  - `finanz.db.enc` (DPAPI encrypted)
  - `.work/finanz_work.db` (temporary only during runtime; encrypted on exit)

Additionally:
- `security.json` (mode + PIN hash / device key handle)

**Backup recommendation:**
- Close the app
- Copy the following files:
  - `finanz.db` (or `finanz.db.enc` in fallback mode)
  - `security.json`

## Recovery

- Close the app
- Copy DB file + `security.json` back from backup
- Start the app

## EXE Update

An EXE cannot be patched in-place - rebuild it from the updated source.

### Update Procedure

1. Update the code: git pull (or replace files manually)
2. Update dependencies: pip install -e .[dev]
3. Quick test: python app.py (optional: File > Check database)
4. Rebuild EXE: .\.venv\Scripts\python -m PyInstaller scripts\finanzmanager.spec
5. Replace EXE: Copy from dist\Finanzmanager\ to target location

### What happens to the DB during an update?

- Default mode: DB is in %LOCALAPPDATA% -> preserved across updates
- Schema changes handled by migrations on startup (best-effort)
- If problems occur: File > Check database or run from source

### Backup recommendation

Back up periodically:
- %LOCALAPPDATA%\Finanzmanager\finanz.db
- security.json (if using PIN/Device mode)

## Troubleshooting

### SQLCipher missing
- The message "SQLCipher missing" means:
  - The app is either running in fallback mode (DPAPI) **or**
  - cannot open an already SQLCipher-encrypted DB (install SQLCipher in that case)

Install (in the build/run venv):
- `sqlcipher3` or `pysqlcipher3-binary`

### "file is not a database"
- Usually caused by:
  - wrong key (SQLCipher/PIN)
  - corrupted DB
  - SQLCipher DB being opened with plain sqlite (driver missing)

### Import/Export
- Excel/CSV import is for initial loading only; afterwards the DB is the source of truth.
- Export/backup: save the DB file + `security.json` (see above).
