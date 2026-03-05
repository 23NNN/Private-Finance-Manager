from __future__ import annotations

import tkinter as tk
from src.ui.common.i18n import tr
from tkinter import ttk


class SecurityModeDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, *, current_mode: str):
        super().__init__(parent)
        self.title(tr("menu.security.mode"))
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result: str | None = None

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text=tr("security.mode.select_prompt")).pack(anchor="w")

        self.var = tk.StringVar(value=current_mode.upper() if current_mode else "NONE")
        modes = [
            (tr("security.mode.none"), "NONE"),
            (tr("security.mode.pin"), "PIN"),
            (tr("security.mode.device"), "DEVICE"),
        ]
        for text, value in modes:
            ttk.Radiobutton(frm, text=text, value=value, variable=self.var).pack(anchor="w", pady=2)

        ttk.Separator(frm).pack(fill="x", pady=10)

        btns = ttk.Frame(frm)
        btns.pack(fill="x")

        ttk.Button(btns, text=tr("common.cancel"), command=self._cancel).pack(side="right")
        ttk.Button(btns, text=tr("common.ok"), command=self._ok).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._center(parent)

    def _center(self, parent: tk.Widget) -> None:
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _ok(self) -> None:
        self.result = (self.var.get() or "NONE").upper()
        self.grab_release()
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.grab_release()
        self.destroy()
