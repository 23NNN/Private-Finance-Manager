# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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