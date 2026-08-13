# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.4] — 2026-08-13

### Fixed

- **57 i18n seed keys had untranslated English placeholder text for `fr`/`es`/`it`** (menu items,
  tab labels, common actions, dataset picker labels, error-dialog text, and — most visibly — the
  language switcher's own display names for German/English/French/Spanish/Italian). Discovered
  and left unfixed in v1.2.3. All corrected with real translations, cross-checked against already-
  correctly-translated sibling keys in the same file for consistency (e.g. `filter.*` now reuses
  `common.filter`/`common.all`, `dataset.*` reuses `io.dataset.*` where the concept overlaps).
  Includes a French grammatical-gender fix for `status.active`/`status.inactive` ("Actif"/
  "Inactif", agreeing with "statut").
- **Already-provisioned databases now receive the corrected values, not just new ones**:
  `schema_patch.py`'s i18n seed loop is insert-only (skips existing rows), so fixing the seed
  dict alone would only have helped brand-new installs. Added a narrow, explicit force-refresh
  list (`_I18N_FORCE_REFRESH_KEYS`, the 57 corrected keys) that gets re-applied via `UPDATE` on
  every `ensure_schema()` run, instead of switching the whole seed mechanism to a general upsert.

### Added

- `scripts/i18n_seed_audit.py`: new tooling that flags seed values in `schema_patch.py` where
  `fr`/`es`/`it` is byte-identical to `en` (i.e. never actually translated), filtered by a
  curated allowlist of legitimate loanwords/cognates. Complements `i18n_audit.py`, which only
  checks for missing `tr()`/`trf()` wrapping, not seed-value translation quality. Currently 0
  findings across all 579 seed keys.

## [1.2.3] — 2026-08-13

### Fixed

- **`doctor.py` UI-callback-contract check was silently broken**: `import ast` sat inside the module docstring instead of the real import block, so the check never ran (the resulting `NameError` was swallowed by a broad `except Exception`). Fixed the import placement and added an allowlist for inherited Tk widget methods (`destroy`, `quit`) the check would otherwise false-positive on.
- **Duplicate dict/set keys (F601)**: `parsers.py`'s month-name map and 5 i18n seed keys in `schema_patch.py` were defined twice in the same literal. For the i18n keys, the earlier (dead) definitions had untranslated English placeholder text for `fr`/`es`/`it`, silently shadowed by later, correctly localized entries — removed the dead duplicates, runtime-effective values unchanged.
- **`scripts/build_demo_data.py`, `scripts/i18n_audit.py`, `scripts/finalize_hourly_legacy_cleanup.py` lost their module docstrings**: `from __future__ import annotations` was placed before the docstring, demoting it to a dead string-expression statement invisible to `ast.get_docstring()`. Restored correct order.
- Removed a dead `I18nService` re-export from `src/application/services/__init__.py` (nothing imported it that way) and a stray `ftrf = trf` alias that had been sitting between two import blocks in `main_window.py`, both of which caused `E402`.

### Changed

- Resolved all pre-existing Ruff findings on `main` except `E501` (line-too-long, tracked as a separate follow-up) and the handful inside `src/security/` (AI-edit-locked path, left for manual maintainer review).
- CI's `ruff` step now runs full-repo (`ruff check . --exclude src/security --ignore E501`) instead of diff-scoped, so regressions in untouched files are caught too.

### Known Issues

- Discovered (not fixed in this release): ~60 i18n seed keys in `schema_patch.py` carry untranslated English placeholder text for `fr`/`es`/`it` (menu items, tab labels, common actions). Not caught by `i18n_audit.py`, which only checks for missing `tr()` wrapping, not translation quality of seed values.

## [1.2.2] — 2026-08-13

### Fixed

- **CSV import was comprehensively broken**: every dataset type in `ImportService.import_csv()` called nonexistent repository/`UnitOfWork` methods (`.add()` instead of `.upsert()`, `uow.flush()`/`uow.commit()`, neither of which exist), and 6 of 10 dataset types constructed ORM objects using fields from an older, no-longer-existing schema. `accounts`, `employers`, `pay_rules`, and `categories` CSV import now work correctly. `income_fixed`, `income_hourly`, `expense_recurring`, `expense_variable`, `loans`, and `loan_events` are explicitly rejected with a clear error (use the Excel import instead) rather than crashing or silently producing wrong data — repairing them requires designing a new CSV column contract, tracked as a follow-up.
- `ImportRun` creation used a nonexistent `file_path` field and local time instead of the model's UTC convention; fixed to match the working Excel-import path.

## [1.2.1] — 2026-08-12

### Fixed

- **Repository upsert returns real IDs**: `upsert_*()` methods across 7 services returned `None` instead of the new row's ID because the DB session runs with `autoflush=False` and no flush happened before the ID was read. Repositories now flush after `add()`.
- **SavingsService crash**: `add_contribution()`/`list_contributions()` referenced a non-existent `UnitOfWork` attribute and raised `AttributeError` on every call.
- **Silent exception swallowing**: engine dispose and loan-event settings parsing now log via `logging.exception()` instead of discarding the error.

### Security

- Added a non-negotiable rule (CLAUDE.md) that personal financial data and DB files must never be committed and that the security boundary must never be weakened by an AI agent, enforced by `tests/unit/test_repo_security_invariants.py` and technical `.claude/settings.json` permission-deny rules on `.gitignore`, `src/security/**`, and the invariant test itself.

### Added

- `.github/workflows/ci.yml`: runs `pytest` and diff-scoped `ruff` on every PR/push to `main`.

### Changed

- `UnitOfWork` now translates SQLAlchemy `IntegrityError`/`OperationalError` into `DomainError` instead of letting them propagate raw.
- Dependencies in `pyproject.toml` pinned (exact pins for dev tools, upper bounds for runtime deps).
- Removed 6 `.idea/*.xml` files from version control (predated the `.idea/` gitignore rule).

## [1.2.0] — 2026-06-26

### Added

- **Dark Mode (default)**: App launches in dark mode by default; switchable to Light or System-default at runtime via the new "Erscheinungsbild" menu — persists across restarts
- **CustomTkinter UI**: All tab bars (main window, Expenses, Income) replaced with `CTkTabview` for a modern rounded-pill appearance; full TTK dark/light palette applied to Treeview, filters, labels, buttons, and scrollbars
- **Interval Filter**: Dropdown filter for the recurring-costs (Fixkosten) list — filter by payment frequency (monthly, quarterly, yearly, etc.)
- **Move Button**: Dedicated toolbar button "Verschieben" added to the Variable Expenses and Special Income toolbars
- **Full Context Menu**: Right-click on Variable Expenses now shows Edit / Mark Paid / Cancel / Move; right-click on Special Income shows Edit / Delete / Move

### Fixed

- **Visual gaps**: ScrollArea canvas background now set to the correct dark/light colour at init — no more white flash or colour-mismatch stripes when the window is taller than the content
- **Dynamic filling**: Content frame now expands to fill the full canvas height when the window is larger than the content, eliminating coloured gaps at the bottom

---

## [1.1.1] — 2026-06-26

### Fixed

- **Lock Screen**: Startup PIN dialog now uses the same styled `LockOverlay` as the in-app lock — consistent UI with dark background, emoji lock icon, and attempt countdown
- **Overview — LOAN costs**: Recurring expenses categorised as LOAN were counted as Fixkosten in the account breakdown *and* as Schulden in the payout summary simultaneously; they now appear only in Schulden, matching the payout calculation

### Changed

- **Loan Event Categories**: Replaced the static all-fields-visible form with a dynamic dialog that shows only the fields relevant to the selected event type
  - New type **Korrektur** (`CORRECTION`): signed amount adjustment (+ increases balance, − decreases)
  - New type **Organisatorische Änderung** (`ORGANIZATIONAL_CHANGE`): change debit period or account without a financial transaction
  - Legacy types `REFINANCING` and `NOTE` removed from the new-event dropdown; existing records remain fully readable

---

## [1.1.0] — 2026-06-25

### Added

- **Backup**: Database backup via File → "Datenbank sichern…" with timestamp filename suggestion
- **In-App Lock**: Security → "App sperren" shows a styled PIN overlay; max. 3 attempts then exit
- **Sum Row**: Filter-dependent count + total amount below fixed-cost and variable-cost trees
- **Move Variable Costs**: Right-click context menu to move variable expenses and special income between months
- **Year View Add**: Variable expenses can now be created directly from the year view with a month picker
- **Pay Bucket Column**: `pay_bucket` (Anfang/Mitte) displayed in the variable-expense treeview
- **Loan Refinancing**: New `REFINANCING` event type increases the loan principal (new money drawn)
- **Auto Interest**: `LoanService.apply_pending_interest_events()` auto-generates monthly `INTEREST` events for active loans with a rate > 0

### Fixed

- **Pay-Rule Overlap**: `employer_service.upsert_pay_rule/upsert_savings_rule` now automatically resolves three overlap scenarios (trim predecessor, cap new rule, reject same start date)
- **Pay Button**: "Bezahlt" button in expenses was disconnected — now wired up with multi-selection support
- **Loan Event Dialog**: Last payment amount is now pre-filled when opening the event dialog

---

## [1.0.0] — 2026-03-03

### Added

- **Income Management**: Fixed salary and hourly income tracking with multi-employer support
- **Hourly Income**: Premium/surcharge rules per employer (night, Sunday, holiday, overtime rates)
- **Expense Management**: Recurring costs (monthly, quarterly, yearly) and variable expenses with status tracking
- **Three View Modes**: Cashflow (real due dates), Monthly Budget (smoothed), Quarterly Budget
- **Loan Tracking**: Event-based loan history with automatic monthly status calculation
- **Accounts**: Multi-account management with role-based categorization
- **Savings Goals**: Automated savings allocation (10% per income source) with goal tracking
- **Excel/CSV Import**: One-time data migration from Excel with smart column mapping and SHA256 deduplication
- **CSV Export**: Data export for reports and backups with template downloads
- **Multi-Language UI**: German, English, French, Spanish, Italian — switchable at runtime
- **Security**: Optional SQLCipher encryption at rest, PIN and device-based protection (DPAPI)
- **Portable Mode**: Run with database next to executable (`--portable` flag)
- **Database Health Check**: Built-in diagnostics via File menu
- **Clean Architecture**: Full MVP pattern with separated UI, Application, Domain, and Infrastructure layers
- **Developer Tooling**: doctor.py, i18n_audit.py, demo data generator, import normalizer
- **PyInstaller Build**: Standalone Windows executable packaging