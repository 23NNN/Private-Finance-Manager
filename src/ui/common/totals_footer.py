# finanzmanager/ui/common/totals_footer.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.ui.common.i18n import tr


class TotalsFooter(ttk.Frame):
    """
    Small footer bar for totals below a table (Treeview).
    Stays visible because it is not inside the scroll container.
    """

    def __init__(self, parent: tk.Widget, fields: list[tuple[str, str]], *, padding: int = 6):
        """
        fields: list of (key, label)
        """
        super().__init__(parent, padding=padding)

        self._value_labels: dict[str, ttk.Label] = {}

        left = ttk.Frame(self)
        left.pack(side="left", fill="x", expand=True)

        ttk.Label(left, text=tr("common.total"), font=("", 10, "bold")).pack(side="left", padx=(0, 12))

        for key, label in fields:
            ttk.Label(left, text=f"{label}").pack(side="left", padx=(0, 6))
            val = ttk.Label(left, text="0,00", font=("", 10, "bold"))
            val.pack(side="left", padx=(0, 14))
            self._value_labels[key] = val

    def set_values(self, values: dict[str, str]) -> None:
        for k, v in values.items():
            lbl = self._value_labels.get(k)
            if lbl is not None:
                lbl.configure(text=v)
