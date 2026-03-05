<p align="center">
  <h1 align="center">💰 Private Finance Manager</h1>
  <p align="center">
    <strong>A privacy-first desktop app for personal finance management — built with AI-assisted development.</strong>
  </p>
  <p align="center">
    Replace your fragile Excel sheets with a real application. Your data stays local. Always.
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white" alt="Windows">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT License">
    <img src="https://img.shields.io/badge/Architecture-Clean%20Architecture-ff6b35" alt="Clean Architecture">
    <img src="https://img.shields.io/badge/Built%20with-AI%20Tools-8b5cf6" alt="Built with AI">
    <img src="https://img.shields.io/badge/UI-5%20Languages-f59e0b" alt="Multi-language">
  </p>
</p>

---

## The Problem

Managing personal finances in Excel works — until it doesn't. Formulas break silently, macros become unmaintainable, and one wrong cell reference can cascade through your entire budget. Cloud-based alternatives? They require handing your most sensitive financial data to a third party.

**Private Finance Manager** replaces your Excel workflow with a proper desktop application. Import your existing data once, then manage everything locally with a real database, proper validation, and clean separation of concerns.

---

## ✨ Features

**Income Tracking**
- Fixed salary and hourly income with separate workflows
- Premium/surcharge rules per employer (night, Sunday, holiday rates)
- Calculated vs. actual income comparison (Soll/Ist)
- Multi-employer support with individual payout timing

**Expense Management**
- Recurring costs with flexible frequencies (monthly, quarterly, yearly)
- Variable expenses with status tracking (open, paid, cancelled)
- Three view modes: **Cashflow** (real due dates), **Monthly Budget** (smoothed), **Quarterly Budget**
- Per-item allocation override for mixed budgeting strategies

**Loan Tracking**
- Event-based loan history (payments, extra payments, rate changes)
- Automatic monthly status: opening balance → payments → closing balance
- Full audit trail via LoanEvent log

**Accounts & Savings**
- Multi-account management with role-based categorization
- Savings goals with automated 10% allocation per income source
- Account-level expense attribution with percentage breakdown

**Data Management**
- One-time Excel/CSV import with smart column mapping
- CSV export for reports and backups
- Template downloads for clean data entry
- SHA256-based deduplication (no accidental double imports)

**Security & Privacy**
- All data stored locally in SQLite — no cloud, no sync, no tracking
- Optional encryption at rest via SQLCipher
- PIN and device-based protection modes (DPAPI on Windows)
- Portable mode available (DB next to executable)

**Multi-Language UI**
- German, English, French, Spanish, Italian
- Switchable at runtime via menu — no restart required

---

## 🏗️ Architecture

Clean Architecture + MVP (Model-View-Presenter). Storage: local SQLite DB (SQLAlchemy 2.x), optionally **SQLCipher** (encrypted at rest).

```
┌─────────────────────────────────────────────────┐
│                    UI Layer                      │
│         Views (Tkinter/ttk) + Presenters         │
│         No business logic — only widgets          │
├─────────────────────────────────────────────────┤
│               Application Layer                  │
│     Services (Use Cases) · DTOs · Validators      │
│     Importers · Each service = one transaction    │
├─────────────────────────────────────────────────┤
│                 Domain Layer                     │
│      Models · Policies (Strategy Pattern)         │
│      Hourly Pay · Loans · Recurring · Savings     │
├─────────────────────────────────────────────────┤
│             Infrastructure Layer                 │
│    SQLAlchemy ORM · Repositories · Unit of Work   │
│    Alembic Migrations · Excel/CSV I/O Adapters    │
└─────────────────────────────────────────────────┘
```

**Key architectural decisions:**
- **Views** contain zero business logic — all event handling goes through Presenters
- **Each use case** runs inside a single `UnitOfWork` transaction
- **Policies** encapsulate business rules (savings percentage, premium calculations, recurring cost schedules)
- **Repositories** abstract all database access — services never touch SQL directly
- **Long-running operations** (imports, aggregations) run in worker threads to keep the UI responsive

> 📐 For detailed architecture documentation, see [`docs/architecture/`](docs/architecture/)

---

## 🚀 Quick Start

### Prerequisites
- Windows 10/11
- Python 3.11+

### Installation

> Recommended: use a local `.venv` inside the repo for a clean, isolated environment.

```powershell
git clone https://github.com/23NNN/Private-Finance-Manager.git
cd Private-Finance-Manager

py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip wheel setuptools
.\.venv\Scripts\python -m pip install -e .[dev]
```

<details>
<summary><strong>With security extras (SQLCipher / PIN / device protection)</strong></summary>

```powershell
.\.venv\Scripts\python -m pip install -e .[dev,security]
```

> Note: on Windows `pysqlcipher3` may fail to build from source.
> More stable alternatives: `sqlcipher3` or `pysqlcipher3-binary`. See [`docs/dev_guide.md`](docs/dev_guide.md).

</details>

### Run

```powershell
.\.venv\Scripts\python app.py
```

### Try with demo data

```powershell
.\.venv\Scripts\python scripts/build_demo_data.py
.\.venv\Scripts\python app.py
```

---

## 📦 Build (EXE, PyInstaller)

> ⚠️ Important: **never** use `pyinstaller app.py` directly. Always use the spec file: `scripts/finanzmanager.spec`.

**Direct (one-liner):**
```powershell
.\.venv\Scripts\python -m PyInstaller scripts\finanzmanager.spec
```

**Via build script (clean build/dist, coloured warnings/errors):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

Output: `dist\Finanzmanager\Finanzmanager.exe`

---

## 📥 Import / Export

Menu: **File → Import Excel…** / **Import CSV…** / **Export CSV…**

- **Excel import:** full template (xlsx) covering all data types
- **CSV import/export:** select dataset (accounts, employers, income, expenses, loans …)
- **Template download:** File → Download CSV Template… / Download Excel Template…

CSV delimiter: `;` (Excel-friendly for European locales).

---

## 💾 Data Paths

Default (non-portable):
- Database: `%LOCALAPPDATA%\Finanzmanager\finanz.db`
- Logs: `%LOCALAPPDATA%\Finanzmanager\Logs\app.log`

**Portable mode** (DB/logs next to EXE in `data/`):
```powershell
.\.venv\Scripts\python app.py --portable
```

---

## 🔍 Database Check

Menu: **File → Check database…**

- Verifies DB connection, tables, and critical columns
- Shows DB and log paths
- Runs best-effort auto-fixes (SQLite ALTER TABLE)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.11+ |
| **UI** | Tkinter / ttk |
| **Database** | SQLite (+ optional SQLCipher) |
| **ORM** | SQLAlchemy 2.x |
| **Migrations** | Alembic |
| **Platform paths** | platformdirs |
| **Excel I/O** | openpyxl |
| **Testing** | pytest + pytest-cov |
| **Linting** | ruff |
| **Packaging** | PyInstaller |

---

## 🔧 Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/doctor.py --imports --contracts --strict` | Repo/UI checks (imports, UI contracts, binding rules) |
| `scripts/i18n_audit.py` | Audit hardcoded UI strings |
| `scripts/pre_build_check.py` | Normalize + audit + doctor before build |
| `scripts/normalize_imports.py` | Normalize internal imports to `src.*` prefix |
| `scripts/find_legacy_imports.py` | Audit legacy import paths |
| `scripts/build_demo_data.py [--mini]` | Generate demo data |
| `scripts/apply_zip_update.py` | Apply patch ZIPs safely (with backup + post-checks) |
| `scripts/export_context.py` | Export repo ZIP for review/ChatGPT |
| `scripts/collect_diagnostics.py` | Collect doctor + i18n audit into a shareable report |

---

## 📁 Project Structure

```
Private-Finance-Manager/
├── app.py                          # Application entry point
├── pyproject.toml                  # Project config & dependencies
├── src/
│   ├── ui/                         # Views (ttk) + Presenters
│   │   ├── overview/               #   Dashboard: current & next month
│   │   ├── income/                 #   Fixed & hourly income management
│   │   ├── expenses/               #   Recurring, variable, loans
│   │   ├── accounts/               #   Account & savings management
│   │   ├── common/                 #   Shared widgets, i18n, dialogs
│   │   └── main_window.py          #   Tab notebook + menu bar
│   ├── application/
│   │   ├── services/               # Use cases (15 service classes)
│   │   ├── dto/                    # Data transfer objects
│   │   ├── importers/              # Excel & CSV import logic
│   │   └── validators/             # Input parsing & validation
│   ├── domain/
│   │   ├── models/                 # Core entities (Period, etc.)
│   │   ├── policies/               # Business rules (pay, loans, savings)
│   │   └── errors.py               # Domain exceptions
│   ├── infrastructure/
│   │   ├── db/                     # Engine, ORM models, migrations
│   │   ├── repositories/           # Data access (15 repository classes)
│   │   ├── io/                     # File readers/writers
│   │   └── unit_of_work.py         # Transaction boundary
│   └── security/                   # Encryption, PIN, DPAPI
├── tests/
│   ├── unit/                       # Domain policy tests
│   └── integration/                # Repository CRUD tests
├── scripts/                        # Build, demo data, diagnostics
└── docs/                           # Architecture, guides, ADRs
```

---

## 🧪 Testing

```powershell
# Run all tests
.\.venv\Scripts\python -m pytest -q

# With coverage
.\.venv\Scripts\python -m pytest --cov=src -q
```

Tests cover domain policies (hourly pay calculation, loan events, recurring cost scheduling, savings rules) and repository CRUD operations.

---

## 📤 Export Context for Review

```powershell
python scripts\export_context.py
```

Generates `finanzmanager_context.zip` (excluding `.git`, `.venv`, `dist/`, `build/`).

---

## 🤖 Built with AI — The Vibe Coding Story

This project was built using AI-assisted development throughout the entire lifecycle:

- **Architecture & Design** → Specifications and architectural decisions developed with AI collaboration
- **Implementation** → Code written with Claude and ChatGPT as pair programming partners
- **Code Review** → AI-powered review for quality, patterns, and edge cases
- **Documentation** → Technical docs, ADRs, and this README crafted with AI assistance
- **i18n** → Five-language UI localization bootstrapped with AI translation

**This is what "Vibe Coding" looks like in practice** — not a toy demo, but a production-grade desktop application with Clean Architecture, proper testing, database migrations, and security features.

The entire development process demonstrates that AI-assisted development can produce professional, maintainable software when guided by sound engineering principles.

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [`docs/index.md`](docs/index.md) | Getting started guide |
| [`docs/user_guide.md`](docs/user_guide.md) | End-user documentation |
| [`docs/dev_guide.md`](docs/dev_guide.md) | Developer setup & contribution guide |
| [`docs/operations.md`](docs/operations.md) | Operations & troubleshooting |
| [`docs/architecture/`](docs/architecture/) | Architecture overview, components, data model |
| [`docs/adr/`](docs/adr/) | Architecture Decision Records |

---

## 🤝 Contributing

Contributions are welcome! Whether it's bug reports, feature requests, or pull requests — all input is appreciated.

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before submitting changes.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 👤 Author

**Built with curiosity, coffee, and AI.**

[LinkedIn](https://www.linkedin.com/in/nafi-nuruddin-9308752b5) · [GitHub](https://github.com/23NNN)

⭐ If this project is useful to you, consider giving it a star — it helps others discover it.