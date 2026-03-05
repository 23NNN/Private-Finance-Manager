# infrastructure/repositories/base.py
from __future__ import annotations

from sqlalchemy.orm import Session


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def delete(self, obj) -> None:
        """Generic delete helper."""
        if obj is not None:
            self.session.delete(obj)
