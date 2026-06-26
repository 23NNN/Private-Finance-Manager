# src/ui/expenses/loan_event_dialog.py
from __future__ import annotations

import tkinter as tk
from decimal import Decimal
from tkinter import ttk

from src.application.validators.parsers import parse_date
from src.ui.common.i18n import tr
from src.ui.common.validation import ui_decimal

DIRECTION_PLUS = "+"
DIRECTION_MINUS = "−"

# Types shown to the user when creating a new event (ordered).
SELECTABLE_TYPES = [
    "PAYMENT",
    "EXTRA_PAYMENT",
    "RATE_CHANGE",
    "INTEREST",
    "INTEREST_CHANGE",
    "CORRECTION",
    "ORGANIZATIONAL_CHANGE",
]


class LoanEventDialog(tk.Toplevel):
    """Dynamic loan event dialog — fields adapt to the selected event type."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        accounts: list,
        type_labels: dict[str, str],
        initial_type: str = "PAYMENT",
        initial: dict | None = None,
        selectable_types: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(tr("expenses.loan_event.dialog.title"))
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._accounts = accounts
        self._type_labels = type_labels
        self._selectable = selectable_types if selectable_types is not None else SELECTABLE_TYPES
        self._result: dict | None = None
        self._shown = False

        ini = initial or {}

        self._v_date = tk.StringVar(value=str(ini.get("date", "")))
        self._v_type = tk.StringVar(value=str(ini.get("type_label", type_labels.get(initial_type, initial_type))))
        self._v_amount = tk.StringVar(value=str(ini.get("amount", "0.00")))
        self._v_direction = tk.StringVar(value=str(ini.get("direction", DIRECTION_PLUS)))
        self._v_new_rate = tk.StringVar(value=str(ini.get("new_rate", "")))
        self._v_new_interest = tk.StringVar(value=str(ini.get("new_interest_rate", "")))
        self._v_org_type = tk.StringVar(value=str(ini.get("org_type", "")))
        self._v_new_timing = tk.StringVar(value=str(ini.get("new_timing", "")))
        self._v_new_account = tk.StringVar(value=str(ini.get("new_account", "")))
        self._v_notes = tk.StringVar(value=str(ini.get("notes", "")))

        self._rows: dict[str, tuple[tk.Widget, tk.Widget]] = {}
        self._build()
        self._on_type_change()

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        self._frm = frm
        self._next_row = 0

        self._add_always("date", tr("expenses.loan_event.field.date"),
                         ttk.Entry(frm, textvariable=self._v_date, width=28))

        type_vals = [self._type_labels[k] for k in self._selectable if k in self._type_labels]
        type_combo = ttk.Combobox(frm, textvariable=self._v_type, values=type_vals, width=32, state="readonly")
        type_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_type_change())
        self._add_always("type", tr("expenses.loan_event.field.type"), type_combo)

        acc_vals = [""] + [f"{a.id}:{a.label}" for a in self._accounts]

        self._add_dynamic("amount", tr("expenses.loan_event.field.amount"),
                          ttk.Entry(frm, textvariable=self._v_amount, width=24))

        dir_combo = ttk.Combobox(
            frm, textvariable=self._v_direction,
            values=[DIRECTION_PLUS, DIRECTION_MINUS], width=8, state="readonly",
        )
        self._add_dynamic("direction", tr("loan_event.field.direction"), dir_combo)

        self._add_dynamic("new_rate", tr("loan_event.field.new_rate"),
                          ttk.Entry(frm, textvariable=self._v_new_rate, width=24))

        self._add_dynamic("new_interest", tr("loan_event.field.new_interest_rate"),
                          ttk.Entry(frm, textvariable=self._v_new_interest, width=24))

        org_combo = ttk.Combobox(
            frm, textvariable=self._v_org_type,
            values=[tr("loan_event.org_type.period"), tr("loan_event.org_type.account")],
            width=24, state="readonly",
        )
        org_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_org_type_change())
        self._add_dynamic("org_type", tr("loan_event.field.org_type"), org_combo)

        self._add_dynamic("new_timing", tr("loan_event.field.new_timing"),
                          ttk.Combobox(frm, textvariable=self._v_new_timing,
                                       values=["", tr("timing.beginning"), tr("timing.mid")],
                                       width=24, state="readonly"))

        self._add_dynamic("new_account", tr("loan_event.field.new_account"),
                          ttk.Combobox(frm, textvariable=self._v_new_account,
                                       values=acc_vals, width=32, state="readonly"))

        self._add_always("notes", tr("expenses.loan_event.field.notes"),
                         ttk.Entry(frm, textvariable=self._v_notes, width=40))

        r = self._next_row
        self._error_lbl = ttk.Label(frm, text="", foreground="red")
        self._error_lbl.grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 0))

        btn_frm = ttk.Frame(frm)
        btn_frm.grid(row=r + 1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        self._ok_btn = ttk.Button(btn_frm, text=tr("common.ok"), command=self._on_ok)
        self._ok_btn.pack(side="left", padx=(0, 8))
        ttk.Button(btn_frm, text=tr("common.cancel"), command=self._on_cancel).pack(side="left")

        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self._on_cancel())

    def _add_always(self, key: str, label: str, widget: tk.Widget) -> None:
        r = self._next_row
        ttk.Label(self._frm, text=label).grid(row=r, column=0, sticky="w", padx=(0, 12), pady=4)
        widget.grid(row=r, column=1, sticky="ew", pady=4)
        self._next_row += 1

    def _add_dynamic(self, key: str, label: str, widget: tk.Widget) -> None:
        r = self._next_row
        lbl = ttk.Label(self._frm, text=label)
        lbl.grid(row=r, column=0, sticky="w", padx=(0, 12), pady=4)
        widget.grid(row=r, column=1, sticky="ew", pady=4)
        self._rows[key] = (lbl, widget)
        self._next_row += 1

    # ---------------------------------------------------------------- helpers

    def _current_type_code(self) -> str:
        ui_val = self._v_type.get()
        for code, label in self._type_labels.items():
            if label == ui_val:
                return code
        return "PAYMENT"

    def _show_only(self, *keys: str) -> None:
        for k, (lbl, wid) in self._rows.items():
            if k in keys:
                lbl.grid()
                wid.grid()
            else:
                lbl.grid_remove()
                wid.grid_remove()

    # --------------------------------------------------------- type switching

    def _on_type_change(self) -> None:
        code = self._current_type_code()
        if code in {"PAYMENT", "EXTRA_PAYMENT", "INTEREST", "REFINANCING"}:
            self._show_only("amount")
        elif code == "RATE_CHANGE":
            self._show_only("new_rate")
        elif code == "INTEREST_CHANGE":
            self._show_only("new_interest")
        elif code == "CORRECTION":
            self._show_only("amount", "direction")
        elif code == "ORGANIZATIONAL_CHANGE":
            self._show_only("org_type")
            self._on_org_type_change()
        elif code == "NOTE":
            self._show_only()
        else:
            self._show_only("amount")
        self._validate()
        self.update_idletasks()

    def _on_org_type_change(self) -> None:
        org = self._v_org_type.get()
        period_lbl = tr("loan_event.org_type.period")
        account_lbl = tr("loan_event.org_type.account")
        if org == period_lbl:
            self._rows["org_type"][0].grid(); self._rows["org_type"][1].grid()
            self._rows["new_timing"][0].grid(); self._rows["new_timing"][1].grid()
            self._rows["new_account"][0].grid_remove(); self._rows["new_account"][1].grid_remove()
        elif org == account_lbl:
            self._rows["org_type"][0].grid(); self._rows["org_type"][1].grid()
            self._rows["new_timing"][0].grid_remove(); self._rows["new_timing"][1].grid_remove()
            self._rows["new_account"][0].grid(); self._rows["new_account"][1].grid()
        else:
            self._rows["org_type"][0].grid(); self._rows["org_type"][1].grid()
            self._rows["new_timing"][0].grid_remove(); self._rows["new_timing"][1].grid_remove()
            self._rows["new_account"][0].grid_remove(); self._rows["new_account"][1].grid_remove()
        self.update_idletasks()

    # -------------------------------------------------------------- validation

    def _validate(self) -> bool:
        code = self._current_type_code()
        err = ""

        date_str = self._v_date.get().strip()
        if not date_str:
            err = tr("error.required").format(field=tr("expenses.loan_event.field.date"))
        else:
            try:
                parse_date(date_str)
            except Exception:
                err = tr("error.invalid").format(field=tr("expenses.loan_event.field.date"))

        if not err and code in {"PAYMENT", "EXTRA_PAYMENT", "INTEREST", "REFINANCING", "CORRECTION"}:
            if not self._v_amount.get().strip():
                err = tr("error.required").format(field=tr("expenses.loan_event.field.amount"))

        if not err and code == "RATE_CHANGE":
            if not self._v_new_rate.get().strip():
                err = tr("error.required").format(field=tr("loan_event.field.new_rate"))

        if not err and code == "INTEREST_CHANGE":
            if not self._v_new_interest.get().strip():
                err = tr("error.required").format(field=tr("loan_event.field.new_interest_rate"))

        if not err and code == "ORGANIZATIONAL_CHANGE":
            if not self._v_org_type.get().strip():
                err = tr("error.required").format(field=tr("loan_event.field.org_type"))

        self._error_lbl.config(text=err)
        if err:
            self._ok_btn.state(["disabled"])
            return False
        self._ok_btn.state(["!disabled"])
        return True

    # ----------------------------------------------------------------- submit

    def _on_ok(self) -> None:
        if not self._validate():
            return

        code = self._current_type_code()
        result: dict = {
            "event_type": code,
            "date": self._v_date.get().strip(),
            "notes": self._v_notes.get().strip() or None,
        }

        if code in {"PAYMENT", "EXTRA_PAYMENT", "INTEREST", "REFINANCING"}:
            result["amount"] = self._v_amount.get().strip()

        elif code == "CORRECTION":
            raw = ui_decimal(self._v_amount.get().strip(), default=Decimal("0"))
            direction = self._v_direction.get()
            result["amount"] = str(-abs(raw) if direction == DIRECTION_MINUS else abs(raw))

        elif code == "RATE_CHANGE":
            result["new_rate"] = self._v_new_rate.get().strip()

        elif code == "INTEREST_CHANGE":
            result["new_interest_rate"] = self._v_new_interest.get().strip()

        elif code == "ORGANIZATIONAL_CHANGE":
            org = self._v_org_type.get()
            result["org_type"] = org
            if org == tr("loan_event.org_type.period"):
                result["new_timing"] = self._v_new_timing.get().strip()
            elif org == tr("loan_event.org_type.account"):
                result["new_account"] = self._v_new_account.get().strip()

        self._result = result
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = None
        self.destroy()

    @property
    def result(self) -> dict | None:
        if not self._shown:
            self._shown = True
            try:
                self.wait_window(self)
            except Exception:
                pass
        return self._result
