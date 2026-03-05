# Documentation Guide

This documentation is the **source of truth** for:

- Usage (User Guide)
- Dev setup, tests, packaging (Dev Guide)
- Operations / support / EXE updates (Operations)
- Architecture decisions (ADR) and architecture overview
- Data model / DB behaviour

## Update Rules

- For UI changes (e.g. sorting, scroll handling, new tabs/menus): update `user_guide.md`.
- For new scripts/build processes: update `dev_guide.md` + root `README.md`.
- For DB schema changes: update `architecture/data_model.md` and document the migration.
- For architecture/component changes: update `architecture/overview.md`.
- For EXE build/update procedures: update `operations.md`.
- ADRs are **never** deleted; document changes as an addendum.
