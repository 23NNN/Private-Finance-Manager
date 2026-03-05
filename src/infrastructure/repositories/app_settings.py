# src/infrastructure/repositories/app_settings.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.orm_models import AppSetting


class AppSettingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str) -> str | None:
        obj = self.session.get(AppSetting, key)
        return obj.value if obj else None

    def set(self, key: str, value: str) -> None:
        obj = self.session.get(AppSetting, key)
        if obj is None:
            obj = AppSetting(key=key, value=value)
            self.session.add(obj)
        else:
            obj.value = value

    def list_all(self) -> dict[str, str]:
        rows = self.session.execute(select(AppSetting)).scalars().all()
        return {r.key: r.value for r in rows}
