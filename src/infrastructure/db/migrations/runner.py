# infrastructure/db/migrations/runner.py
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from src.infrastructure.db.migrations.schema_patch import ensure_schema

logger = logging.getLogger(__name__)


def _find_alembic_ini() -> Path | None:
    candidates = [
        Path("infrastructure/db/migrations/alembic.ini"),
        Path(__file__).resolve().parent / "alembic.ini",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _fallback_create_all() -> None:
    from src.infrastructure.db.engine import get_engine
    from src.infrastructure.db.orm_models import Base

    Base.metadata.create_all(get_engine())
    logger.warning("Fallback: Tabellen via metadata.create_all() erstellt.")


def upgrade_db_if_possible() -> None:
    ini = _find_alembic_ini()
    if not ini:
        logger.warning("Alembic config nicht gefunden; nutze fallback create_all().")
        _fallback_create_all()
        ensure_schema()
        return

    try:
        cfg = Config(str(ini))
        cfg.set_main_option("script_location", str(ini.parent.resolve()))
        command.upgrade(cfg, "head")
        logger.info("Alembic upgrade complete.")
    except Exception:
        logger.exception("Alembic upgrade failed; nutze fallback create_all().")
        _fallback_create_all()
    finally:
        ensure_schema()
