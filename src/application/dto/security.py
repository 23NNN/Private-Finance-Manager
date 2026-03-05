from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityStatusDTO:
    mode: str  # NONE|PIN|DEVICE
