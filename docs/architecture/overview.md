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
