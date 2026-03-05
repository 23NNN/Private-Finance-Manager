# ADR 0001 – Clean Architecture + MVP + SQLite as Source of Truth

## Context
Building a local Windows desktop app for real-world use.
Requirements:
- robust error handling / logging
- clear separation of UI, business logic, data access
- testability
- one-time Excel/CSV import; afterwards DB is the source of truth

## Decision
- Architecture:
  - UI in MVP pattern (Presenter drives the view)
  - Application Services as use cases
  - Domain Policies as pure logic
  - Infrastructure as SQLAlchemy/SQLite access (Repos + UoW)
- Data storage:
  - Local SQLite as the single source of truth
  - Import only on initial setup or manually via tooling

## Consequences
- good testability (Domain/Services without UI)
- clear responsibilities
- more stable build/packaging
- schema changes require clean migration/SchemaPatch and doc update

## Alternatives
- "Everything in Tkinter code": too hard to maintain
- Cloud sync: excluded in MVP

## Update (Security)
Since the initial ADR, security was extended: optional local DB encryption (SQLCipher, crash-safe) plus PIN/device protection. The core architecture (Clean Architecture + MVP + local DB as source of truth) remains unchanged.
