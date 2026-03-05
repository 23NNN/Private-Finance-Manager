# src/ui/accounts/view.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.ui.common.controls import create_treeview_with_scrollbars
from src.ui.common.i18n import tr


class AccountsView(ttk.Frame):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent, padding=8)

        top = ttk.Frame(self)
        top.pack(fill="x")

        self.refresh_btn = ttk.Button(top, text=tr("common.refresh"))
        self.refresh_btn.pack(side="right")

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(8, 6))

        self.add_btn = ttk.Button(btns, text=tr("common.new"))
        self.edit_btn = ttk.Button(btns, text=tr("common.edit"))
        self.delete_btn = ttk.Button(btns, text=tr("common.delete"))

        self.add_btn.pack(side="left")
        self.edit_btn.pack(side="left", padx=(6, 0))
        self.delete_btn.pack(side="left", padx=(6, 0))

        # -------------------- Filter --------------------
        flt = ttk.LabelFrame(self, text=tr("filter.title"))
        flt.pack(fill="x", pady=(0, 6))

        self.filter_account_var = tk.StringVar(value="")
        self.filter_bank_var = tk.StringVar(value="")

        ttk.Label(flt, text=tr("accounts.filter.account_or_label")).pack(side="left", padx=(8, 6), pady=4)
        self.filter_account_entry = ttk.Entry(flt, textvariable=self.filter_account_var, width=28)
        self.filter_account_entry.pack(side="left", pady=4)

        ttk.Label(flt, text=tr("accounts.filter.bank")).pack(side="left", padx=(12, 6), pady=4)
        self.filter_bank_entry = ttk.Entry(flt, textvariable=self.filter_bank_var, width=24)
        self.filter_bank_entry.pack(side="left", pady=4)

        self.filter_reset_btn = ttk.Button(flt, text=tr("common.reset"))
        self.filter_reset_btn.pack(side="right", padx=8, pady=4)

        # -------------------- Table --------------------
        cols = ["label", "account_name", "bank_name", "iban", "role_income", "role_debit"]
        heads = {
            "label": tr("accounts.col.label"),
            "account_name": tr("accounts.col.account_name"),
            "bank_name": tr("accounts.col.bank_name"),
            "iban": tr("accounts.col.iban"),
            "role_income": tr("accounts.col.role_income"),
            "role_debit": tr("accounts.col.role_debit"),
        }
        self.tree, frame = create_treeview_with_scrollbars(self, columns=cols, headings=heads, height=18)
        frame.pack(fill="both", expand=True)

    def bind_refresh(self, fn) -> None:
        self.refresh_btn.configure(command=fn)

    def bind_filter_change(self, fn) -> None:
        self.filter_account_entry.bind("<KeyRelease>", lambda _e: fn())
        self.filter_bank_entry.bind("<KeyRelease>", lambda _e: fn())

        def _reset() -> None:
            self.filter_account_var.set("")
            self.filter_bank_var.set("")
            fn()

        self.filter_reset_btn.configure(command=_reset)

    def get_filters(self) -> dict[str, str]:
        return {
            "account": (self.filter_account_var.get() or "").strip(),
            "bank": (self.filter_bank_var.get() or "").strip(),
        }
