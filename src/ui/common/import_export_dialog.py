# ui/common/import_export_dialog.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.ui.common.i18n import tr


class DatasetDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, title: str, datasets: list[str], labels: list[str] | None = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._result: str | None = None
        self._datasets = datasets
        self._labels = labels

        display = labels if labels is not None else datasets

        frm = ttk.Frame(self, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text=tr("io.dataset.choose")).grid(row=0, column=0, sticky="w")

        self.var = tk.StringVar(value=display[0] if display else "")
        self.combo = ttk.Combobox(frm, state="readonly", values=display, textvariable=self.var, width=35)
        self.combo.grid(row=1, column=0, sticky="ew", pady=(6, 10))

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, sticky="e")

        ttk.Button(btns, text=tr("common.ok"), command=self._ok).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text=tr("common.cancel"), command=self._cancel).grid(row=0, column=1)

        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self._cancel())

        self.combo.focus_set()

    def _ok(self):
        sel = self.var.get().strip() or None
        if sel and self._labels is not None:
            try:
                idx = self._labels.index(sel)
                sel = self._datasets[idx]
            except ValueError:
                pass
        self._result = sel
        self.destroy()

    def _cancel(self):
        self._result = None
        self.destroy()

    def show(self) -> str | None:
        self.wait_window(self)
        return self._result
