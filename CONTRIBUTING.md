# Contributing to Private Finance Manager

Thank you for your interest in contributing! Whether it's a bug report, feature request, or code contribution — all input is appreciated.

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/23NNN/Private-Finance-Manager/issues) to avoid duplicates
2. Use the **Bug Report** template when creating a new issue
3. Include steps to reproduce, expected vs. actual behavior, and your environment details

### Suggesting Features

1. Open a **Feature Request** issue
2. Describe the problem you're trying to solve (not just the solution)
3. Explain how this fits the project's goal of privacy-first, local-only finance management

### Submitting Code

1. **Fork** the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Follow the coding standards below
4. Run tests and linting before committing
5. Submit a **Pull Request** using the PR template

## Development Setup

```powershell
cd Private-Finance-Manager
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip wheel setuptools
.\.venv\Scripts\python -m pip install -e .[dev]
```

See [`docs/dev_guide.md`](docs/dev_guide.md) for the full developer guide.

## Coding Standards

### Architecture

This project follows **Clean Architecture**. Before making changes, understand which layer your code belongs to:

| Layer | Path | Responsibility |
|-------|------|----------------|
| UI | `src/ui/` | Views (widgets) + Presenters (logic) |
| Application | `src/application/` | Services, DTOs, validators |
| Domain | `src/domain/` | Pure business rules (no I/O) |
| Infrastructure | `src/infrastructure/` | DB, repositories, file I/O |
| Security | `src/security/` | Encryption, PIN, DPAPI |

### Code Style

- **Language**: All code, comments, and documentation in **English**
- **Imports**: Always use the `src.` prefix (`from src.ui.common.i18n import tr`)
- **Type hints**: Required on all public functions
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes

### Pre-Commit Checks

Run these before every commit:

```powershell
# Linting
python -m ruff check src/

# Tests
python -m pytest -q

# Import + contract checks
python scripts/doctor.py --imports --contracts --strict

# i18n audit (no hardcoded UI strings)
python scripts/i18n_audit.py
```

### i18n Rules

- All user-facing strings must use `tr("key")` or `trf("key", **kwargs)`
- New keys must be seeded in **all 5 languages** (DE, EN, FR, ES, IT) in `schema_patch.py`
- Run `python scripts/i18n_audit.py` to verify

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add quarterly savings report
fix: correct loan event date calculation
docs: update architecture overview
chore: update dependencies
refactor: extract premium calculation to policy
```

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include a description of **what** and **why**
- Reference related issues (`Closes #123`)
- Ensure all checks pass before requesting review
- Update documentation if your change affects user-facing behavior

## What We're Looking For

Contributions that align with the project's goals are most welcome:

- Bug fixes with clear reproduction steps
- Performance improvements
- Additional language support (i18n)
- Test coverage improvements
- Documentation improvements
- Accessibility enhancements

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this standard.

## Questions?

If you're unsure about something, open an issue and ask. There are no bad questions.