# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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