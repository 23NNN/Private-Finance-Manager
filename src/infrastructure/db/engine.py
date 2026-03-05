# infrastructure/db/engine.py
from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_ENGINE: Engine | None = None
_SessionFactory: sessionmaker | None = None


def init_engine(
    sqlalchemy_url: str,
    *,
    creator: Callable[[], Any] | None = None,
    connect_args: dict[str, Any] | None = None,
) -> None:
    """Initialises the global SQLAlchemy engine.

    Important:
    - `creator` must only be passed when it is actually set.
      SQLAlchemy treats a provided `creator=` as the authoritative connection creator.
      `creator=None` then leads to: TypeError: 'NoneType' object is not callable.
    """
    global _ENGINE, _SessionFactory

    kwargs: dict[str, Any] = {
        "future": True,
        "echo": False,
    }

    if connect_args:
        kwargs["connect_args"] = dict(connect_args)

    if creator is not None:
        kwargs["creator"] = creator

    _ENGINE = create_engine(sqlalchemy_url, **kwargs)
    _SessionFactory = sessionmaker(bind=_ENGINE, autoflush=False, expire_on_commit=False, future=True)


def dispose_engine() -> None:
    """Closes all pooled DB connections (important before re-encryption/close)."""
    global _ENGINE
    if _ENGINE is not None:
        try:
            _ENGINE.dispose()
        except Exception:
            pass


def get_engine() -> Engine:
    if _ENGINE is None:
        raise RuntimeError("DB engine not initialized. Call init_engine() first.")
    return _ENGINE


def get_session_factory() -> sessionmaker:
    if _SessionFactory is None:
        raise RuntimeError("Session factory not initialized. Call init_engine() first.")
    return _SessionFactory


def SessionLocal() -> Session:
    """Compatibility helper used across the app."""
    return get_session_factory()()
