# src/security/security_config.py
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from hashlib import pbkdf2_hmac
from pathlib import Path

from src.security import dpapi

_PIN_ITERS_DEFAULT = 200_000


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def _pbkdf2(text: str, salt: bytes, iters: int) -> bytes:
    return pbkdf2_hmac("sha256", text.encode("utf-8"), salt, iters, dklen=32)


@dataclass
class SecurityConfig:
    mode: str  # "NONE" | "PIN" | "DEVICE"
    pin_salt_b64: str | None = None
    pin_hash_b64: str | None = None
    pin_iters: int = _PIN_ITERS_DEFAULT
    device_key_dpapi_b64: str | None = None

    def mode_norm(self) -> str:
        return (self.mode or "NONE").strip().upper()

    def has_pin(self) -> bool:
        return self.mode_norm() == "PIN"

    def ensure_device_key(self) -> "SecurityConfig":
        if self.mode_norm() != "DEVICE":
            return self
        if self.device_key_dpapi_b64:
            return self
        # generate random SQLCipher key (32 bytes) and protect via DPAPI
        key_bytes = os.urandom(32)
        protected = dpapi.protect(key_bytes)
        self.device_key_dpapi_b64 = _b64e(protected)
        return self

    def derive_sqlcipher_key(self, pin: str | None) -> str:
        mode = self.mode_norm()
        if mode == "NONE":
            return ""
        if mode == "DEVICE":
            if not self.device_key_dpapi_b64:
                raise ValueError("Device-Key fehlt")
            raw = dpapi.unprotect(_b64d(self.device_key_dpapi_b64))
            return raw.hex()
        # PIN
        if pin is None:
            raise ValueError("PIN fehlt")
        if not self.pin_salt_b64:
            raise ValueError("PIN-Salt fehlt")
        salt = _b64d(self.pin_salt_b64)
        return _pbkdf2(pin, salt, self.pin_iters).hex()

    def derive_dpapi_entropy(self, pin: str | None) -> bytes | None:
        # For DPAPI fallback: use stable entropy for PIN mode; none for DEVICE (already bound to user)
        if self.mode_norm() != "PIN" or pin is None:
            return None
        if not self.pin_salt_b64:
            return None
        salt = _b64d(self.pin_salt_b64)
        return _pbkdf2(pin, salt, self.pin_iters)


def make_pin_config(pin: str, *, iters: int = _PIN_ITERS_DEFAULT) -> SecurityConfig:
    pin_salt = os.urandom(16)
    pin_hash = _pbkdf2(pin, pin_salt, iters)
    return SecurityConfig(
        mode="PIN",
        pin_salt_b64=_b64e(pin_salt),
        pin_hash_b64=_b64e(pin_hash),
        pin_iters=iters,
    )


def verify_pin(cfg: SecurityConfig, pin: str) -> bool:
    if not cfg.has_pin():
        return True
    if not (cfg.pin_salt_b64 and cfg.pin_hash_b64):
        return False
    salt = _b64d(cfg.pin_salt_b64)
    expected = _b64d(cfg.pin_hash_b64)
    got = _pbkdf2(pin, salt, cfg.pin_iters)
    return got == expected


def load_security_config(path: Path) -> SecurityConfig | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    cfg = SecurityConfig(
        mode=str(raw.get("mode") or "NONE"),
        pin_salt_b64=raw.get("pin_salt_b64"),
        pin_hash_b64=raw.get("pin_hash_b64"),
        pin_iters=int(raw.get("pin_iters") or _PIN_ITERS_DEFAULT),
        device_key_dpapi_b64=raw.get("device_key_dpapi_b64"),
    )
    if cfg.mode_norm() == "DEVICE":
        cfg.ensure_device_key()
    return cfg


def save_security_config(path: Path, cfg: SecurityConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "mode": cfg.mode_norm(),
        "pin_salt_b64": cfg.pin_salt_b64,
        "pin_hash_b64": cfg.pin_hash_b64,
        "pin_iters": cfg.pin_iters,
        "device_key_dpapi_b64": cfg.device_key_dpapi_b64,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
