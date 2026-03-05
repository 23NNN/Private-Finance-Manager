# application/services/maintenance_service.py
from __future__ import annotations

from src.infrastructure.unit_of_work import UnitOfWork


class MaintenanceService:
    """Small maintenance utilities for the UI."""

    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory

    def save_now(self) -> None:
        """Forces a DB roundtrip/commit path (trust-building 'Save' button)."""
        with self._uow_factory() as _uow:
            return
