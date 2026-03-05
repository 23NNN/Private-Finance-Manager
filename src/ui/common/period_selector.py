# ui/common/period_selector.py
from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import ttk

from src.domain.models.period import Period
from src.ui.common.i18n import tr


class PeriodSelector(ttk.Frame):
    """Period selector (month/year) for views.

    By default month + year are selected.
    Optionally a "Year view" checkbox can be shown that disables the month selector.

    Presenters can use `get_view_mode()` / `is_year_view()` to adjust data queries.
    """

    def __init__(self, parent: tk.Widget, *, on_change, show_year_toggle: bool = False):
        super().__init__(parent)
        now = datetime.now()
        self._on_change = on_change

        ttk.Label(self, text=tr("period.year")).grid(row=0, column=0, padx=(0, 6))
        self.year_var = tk.StringVar(value=str(now.year))
        self.year_spin = ttk.Spinbox(self, from_=2000, to=2100, textvariable=self.year_var, width=6)
        self.year_spin.grid(row=0, column=1, padx=(0, 10))

        ttk.Label(self, text=tr("period.month")).grid(row=0, column=2, padx=(0, 6))
        self.month_var = tk.StringVar(value=str(now.month))
        self.month_combo = ttk.Combobox(
            self,
            width=6,
            state="readonly",
            values=[str(i) for i in range(1, 13)],
            textvariable=self.month_var,
        )
        self.month_combo.grid(row=0, column=3, padx=(0, 10))

        self.year_view_var = tk.BooleanVar(value=False)
        self.year_view_chk: ttk.Checkbutton | None = None
        if show_year_toggle:
            self.year_view_chk = ttk.Checkbutton(
                self,
                text=tr("period.year_view"),
                variable=self.year_view_var,
                command=self._on_year_toggle,
            )
            self.year_view_chk.grid(row=0, column=4, padx=(0, 0))

        self.year_spin.bind("<KeyRelease>", lambda _e: self._emit())
        self.month_combo.bind("<<ComboboxSelected>>", lambda _e: self._emit())

    def get_year(self) -> int:
        return int(self.year_var.get())

    def get_month(self) -> int:
        return int(self.month_var.get())

    def get_period(self) -> Period:
        return Period(self.get_year(), self.get_month())

    def get_view_mode(self) -> str:
        return "YEAR" if self.is_year_view() else "MONTH"

    def is_year_view(self) -> bool:
        try:
            return bool(self.year_view_var.get())
        except Exception:
            return False

    def set_month_enabled(self, enabled: bool) -> None:
        self.month_combo.configure(state=("readonly" if enabled else "disabled"))

    def _on_year_toggle(self) -> None:
        self.set_month_enabled(not self.is_year_view())
        self._emit()

    def _emit(self) -> None:
        try:
            _ = self.get_period()
        except Exception:
            return
        self._on_change()
