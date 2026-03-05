# src/ui/common/i18n.py
from __future__ import annotations

from src.application.services.i18n_service import I18nService

_i18n: I18nService | None = None


def init_i18n(service: I18nService) -> None:
    global _i18n
    _i18n = service


def get_i18n() -> I18nService | None:
    return _i18n


def tr(key: str) -> str:
    """Translate a key using the global I18nService."""
    if _i18n is None:
        return key
    return _i18n.t(key)


def trf(key: str, /, **kwargs) -> str:
    """Translate and format with `str.format(**kwargs)`.

    Use DB values like: "Delete '{name}'?".
    """
    txt = tr(key)
    try:
        return txt.format(**kwargs)
    except Exception:
        return txt
