# src/ui/security/lock_overlay.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from pathlib import Path

from src.security.security_config import load_security_config, verify_pin
from src.ui.common.i18n import tr

_MAX_ATTEMPTS = 3


class LockOverlay(tk.Frame):
    """Full-window overlay that blocks all interaction until the correct PIN is entered."""

    def __init__(self, root: tk.Tk, security_path: Path) -> None:
        super().__init__(root, bg="#2b2b2b")
        self._root = root
        self._security_path = security_path
        self._attempts = 0

        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

        self._build()
        self._entry.focus_set()

    def _build(self) -> None:
        inner = ttk.Frame(self)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(inner, text="🔒", font=("Segoe UI", 36)).pack(pady=(0, 8))
        ttk.Label(inner, text=tr("lock.title"), font=("Segoe UI", 14, "bold")).pack()
        ttk.Label(inner, text=tr("lock.subtitle"), foreground="gray").pack(pady=(4, 16))

        self._entry = ttk.Entry(inner, show="●", width=24, font=("Segoe UI", 12))
        self._entry.pack()
        self._entry.bind("<Return>", lambda _e: self._verify())

        self._error_label = ttk.Label(inner, text="", foreground="red")
        self._error_label.pack(pady=(6, 0))

        btn_frame = ttk.Frame(inner)
        btn_frame.pack(pady=(12, 0))
        ttk.Button(btn_frame, text=tr("common.ok"), command=self._verify, width=12).pack(side="left")

    def _verify(self) -> None:
        pin = self._entry.get()
        cfg = load_security_config(self._security_path)

        if cfg is None or not cfg.has_pin():
            self.destroy()
            return

        if verify_pin(cfg, pin):
            self.destroy()
            return

        self._attempts += 1
        self._entry.delete(0, "end")

        if self._attempts >= _MAX_ATTEMPTS:
            self._root.destroy()
            return

        remaining = _MAX_ATTEMPTS - self._attempts
        self._error_label.config(text=tr("lock.wrong_pin").format(remaining=remaining))
