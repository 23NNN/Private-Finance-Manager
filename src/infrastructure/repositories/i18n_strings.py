# src/infrastructure/repositories/i18n_strings.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.orm_models import I18nString


class I18nStringRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str, lang: str) -> str | None:
        obj = self.session.get(I18nString, {"key": key, "lang": lang})
        return obj.text if obj else None

    def list_by_lang(self, lang: str) -> dict[str, str]:
        rows = self.session.execute(select(I18nString).where(I18nString.lang == lang)).scalars().all()
        return {r.key: r.text for r in rows}

    def upsert(self, key: str, lang: str, text: str) -> None:
        obj = self.session.get(I18nString, {"key": key, "lang": lang})
        if obj is None:
            obj = I18nString(key=key, lang=lang, text=text)
            self.session.add(obj)
        else:
            obj.text = text
