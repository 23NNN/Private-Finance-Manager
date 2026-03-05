# src/application/services/i18n_service.py
from __future__ import annotations

from dataclasses import dataclass

from src.infrastructure.unit_of_work import UnitOfWork

SUPPORTED_LANG_CODES: tuple[str, ...] = ("de", "en", "fr", "es", "it")
_DEFAULT_LANG = "en"
_FALLBACK_LANG = "en"
_SETTING_KEY = "ui.language"


@dataclass(frozen=True)
class LanguageOption:
    code: str
    name_key: str  # e.g. lang.de


class I18nService:
    """DB-backed i18n service.

    Stores UI strings in the local DB with (key, lang) -> text.
    Stores current language in app_setting(ui.language).

    Fallback order (important: avoid German bleeding into non-German UI):
    - requested lang (or current)
    - English (en)
    - key (as last resort)
    """

    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory
        self._cache: dict[str, dict[str, str]] = {}

    def list_languages(self) -> list[LanguageOption]:
        return [LanguageOption(code=c, name_key=f"lang.{c}") for c in SUPPORTED_LANG_CODES]

    def get_language(self) -> str:
        with self._uow_factory() as uow:
            code = uow.app_settings.get(_SETTING_KEY)
        if not code:
            return _DEFAULT_LANG
        code = code.strip().lower()
        return code if code in SUPPORTED_LANG_CODES else _DEFAULT_LANG

    def set_language(self, code: str) -> None:
        code = (code or "").strip().lower()
        if code not in SUPPORTED_LANG_CODES:
            raise ValueError(f"Unsupported language: {code}")
        with self._uow_factory() as uow:
            uow.app_settings.set(_SETTING_KEY, code)
        self._cache.pop(code, None)  # reload on next t()

    def t(self, key: str, *, lang: str | None = None) -> str:
        if not key:
            return ""
        lang_code = (lang or self.get_language()).strip().lower()
        if lang_code not in SUPPORTED_LANG_CODES:
            lang_code = _DEFAULT_LANG

        txt = self._get_lang_table(lang_code).get(key)
        if txt:
            return txt

        # avoid German bleed: fallback to English always (unless already English)
        if lang_code != _FALLBACK_LANG:
            txt = self._get_lang_table(_FALLBACK_LANG).get(key)
            if txt:
                return txt

        return key

    def _get_lang_table(self, lang_code: str) -> dict[str, str]:
        table = self._cache.get(lang_code)
        if table is None:
            with self._uow_factory() as uow:
                table = uow.i18n_strings.list_by_lang(lang_code)
            self._cache[lang_code] = table
        return table
