from __future__ import annotations

from dataclasses import dataclass

from src.config.settings import get_settings
from src.infrastructure.db.engine import dispose_engine, init_engine
from src.security.bootstrap import bootstrap_security_and_db
from src.security.manager import SecurityManager
from src.security.security_config import load_security_config, save_security_config, SecurityConfig


@dataclass(frozen=True)
class SecurityStatus:
    mode: str  # NONE|PIN|DEVICE


class SecurityService:
    """Application service wrapper around security operations."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._mgr = SecurityManager(self._settings)

    def get_status(self) -> SecurityStatus:
        cfg = load_security_config(self._mgr.security_path())
        mode = cfg.mode_norm() if cfg else "NONE"
        return SecurityStatus(mode=mode)

    def change_pin(self, *, old_pin: str, new_pin: str) -> None:
        cfg = load_security_config(self._mgr.security_path())
        if cfg is None:
            raise ValueError("Keine Sicherheits-Konfiguration vorhanden.")
        dispose_engine()
        self._mgr.change_pin(old_cfg=cfg, old_pin=old_pin, new_pin=new_pin)

    def set_mode(self, *, new_mode: str, current_pin: str | None, new_pin: str | None) -> None:
        cfg = load_security_config(self._mgr.security_path())
        if cfg is None:
            cfg = SecurityConfig(mode="NONE", pin_salt_b64=None, pin_hash_b64=None, pin_iters=200_000, device_key_dpapi_b64=None)
            save_security_config(self._mgr.security_path(), cfg)
        dispose_engine()
        self._mgr.set_mode(old_cfg=cfg, new_mode=new_mode, current_pin=current_pin, new_pin=new_pin)
