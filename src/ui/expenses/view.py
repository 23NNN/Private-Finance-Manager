# ui/expenses/view.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.ui.common.controls import create_treeview_with_scrollbars
from src.ui.common.i18n import tr
from src.ui.common.period_selector import PeriodSelector


class ExpensesView(ttk.Frame):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent, padding=8)

        self._all_label = tr("common.all")

        top = ttk.Frame(self)
        top.pack(fill="x")

        self.period_selector = PeriodSelector(top, on_change=lambda: None, show_year_toggle=True)
        self.period_selector.pack(side="left")

        self.refresh_btn = ttk.Button(top, text=tr("common.refresh"))
        self.refresh_btn.pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, pady=(8, 0))

        self.tab_loans = ttk.Frame(nb)
        self.tab_recurring = ttk.Frame(nb)
        self.tab_variable = ttk.Frame(nb)

        nb.add(self.tab_loans, text=tr("expenses.tab.loans"))
        nb.add(self.tab_recurring, text=tr("expenses.tab.recurring"))
        nb.add(self.tab_variable, text=tr("expenses.tab.variable"))

        # -------------------- Loans --------------------
        btns_l = ttk.Frame(self.tab_loans)
        btns_l.pack(fill="x", pady=(0, 6))

        self.add_loan_btn = ttk.Button(btns_l, text=tr("expenses.loan.btn.new"))
        self.add_loan_event_btn = ttk.Button(btns_l, text=tr("expenses.loan.btn.add_event"))
        self.edit_loan_event_btn = ttk.Button(btns_l, text=tr("expenses.loan.btn.edit_event"))
        self.show_loan_events_btn = ttk.Button(btns_l, text=tr("expenses.loan.btn.show_events"))
        self.delete_event_btn = ttk.Button(btns_l, text=tr("expenses.loan.btn.delete_event"))
        self.close_loan_btn = ttk.Button(btns_l, text=tr("expenses.loan.btn.close"))
        self.reopen_loan_btn = ttk.Button(btns_l, text=tr("expenses.loan.btn.reopen"))
        self.delete_loan_btn = ttk.Button(btns_l, text=tr("expenses.loan.btn.delete"))

        self.add_loan_btn.pack(side="left")
        self.add_loan_event_btn.pack(side="left", padx=(6, 0))
        self.edit_loan_event_btn.pack(side="left", padx=(6, 0))
        self.show_loan_events_btn.pack(side="left", padx=(6, 0))
        self.delete_event_btn.pack(side="left", padx=(6, 0))
        self.close_loan_btn.pack(side="left", padx=(6, 0))
        self.reopen_loan_btn.pack(side="left", padx=(6, 0))
        self.delete_loan_btn.pack(side="left", padx=(6, 0))

        # Filters (Loans)
        fl = ttk.LabelFrame(self.tab_loans, text=tr("common.filter"))
        fl.pack(fill="x", pady=(0, 6))

        self.loan_status_var = tk.StringVar(value=self._all_label)
        self.loan_account_var = tk.StringVar(value=self._all_label)
        self.loan_timing_var = tk.StringVar(value=self._all_label)
        self.loan_only_relevant_var = tk.BooleanVar(value=True)

        ttk.Label(fl, text=f'{tr("common.status")}:').pack(side="left", padx=(8, 4), pady=4)
        self.loan_status_filter = ttk.Combobox(fl, textvariable=self.loan_status_var, state="readonly", width=12)
        self.loan_status_filter["values"] = (self._all_label, tr("status.active"), tr("status.closed"))
        self.loan_status_filter.pack(side="left", pady=4)

        ttk.Label(fl, text=f'{tr("common.account")}:').pack(side="left", padx=(12, 4), pady=4)
        self.loan_account_filter = ttk.Combobox(fl, textvariable=self.loan_account_var, state="readonly", width=28)
        self.loan_account_filter["values"] = (self._all_label,)
        self.loan_account_filter.pack(side="left", pady=4)

        ttk.Label(fl, text=f'{tr("common.timing")}:').pack(side="left", padx=(12, 4), pady=4)
        self.loan_timing_filter = ttk.Combobox(fl, textvariable=self.loan_timing_var, state="readonly", width=10)
        self.loan_timing_filter["values"] = (self._all_label, tr("timing.beginning"), tr("timing.mid"))
        self.loan_timing_filter.pack(side="left", pady=4)

        self.loan_only_relevant_chk = ttk.Checkbutton(
            fl,
            text=tr("expenses.loan.filter.only_relevant"),
            variable=self.loan_only_relevant_var,
        )
        self.loan_only_relevant_chk.pack(side="left", padx=(12, 0), pady=4)

        self.loan_filter_reset_btn = ttk.Button(fl, text=tr("common.reset"))
        self.loan_filter_reset_btn.pack(side="right", padx=8, pady=4)

        cols_l = ["loan", "status", "account", "timing", "open_before", "payment", "extra", "open_after"]
        heads_l = {
            "loan": tr("expenses.loan.col.loan"),
            "status": tr("expenses.loan.col.status"),
            "account": tr("expenses.loan.col.account"),
            "timing": tr("expenses.loan.col.timing"),
            "open_before": tr("expenses.loan.col.open_before"),
            "payment": tr("expenses.loan.col.payment"),
            "extra": tr("expenses.loan.col.extra"),
            "open_after": tr("expenses.loan.col.open_after"),
        }
        self.loan_tree, frame_l = create_treeview_with_scrollbars(
            self.tab_loans,
            columns=cols_l,
            headings=heads_l,
            height=10,
        )
        frame_l.pack(fill="both", expand=True)

        cols_e = ["date", "type", "amount", "override_account", "override_timing", "note"]
        heads_e = {
            "date": tr("expenses.loan_event.col.date"),
            "type": tr("expenses.loan_event.col.type"),
            "amount": tr("expenses.loan_event.col.amount"),
            "override_account": tr("expenses.loan_event.col.override_account"),
            "override_timing": tr("expenses.loan_event.col.override_timing"),
            "note": tr("expenses.loan_event.col.note"),
        }
        self.loan_events_tree, frame_e = create_treeview_with_scrollbars(
            self.tab_loans,
            columns=cols_e,
            headings=heads_e,
            height=10,
        )
        frame_e.pack(fill="both", expand=True, pady=(8, 0))

        # -------------------- Recurring --------------------
        btns_r = ttk.Frame(self.tab_recurring)
        btns_r.pack(fill="x", pady=(0, 6))
        self.add_rec_btn = ttk.Button(btns_r, text=tr("common.new"))
        self.edit_rec_btn = ttk.Button(btns_r, text=tr("common.edit"))
        self.delete_rec_btn = ttk.Button(btns_r, text=tr("expenses.recurring.btn.deactivate"))
        self.undo_rec_btn = ttk.Button(btns_r, text=tr("expenses.recurring.btn.reactivate"))
        self.manage_categories_btn = ttk.Button(btns_r, text=tr("expenses.recurring.btn.categories"))

        self.add_rec_btn.pack(side="left")
        self.edit_rec_btn.pack(side="left", padx=(6, 0))
        self.delete_rec_btn.pack(side="left", padx=(6, 0))
        self.undo_rec_btn.pack(side="left", padx=(6, 0))
        self.manage_categories_btn.pack(side="right")

        fr = ttk.LabelFrame(self.tab_recurring, text=tr("common.filter"))
        fr.pack(fill="x", pady=(0, 6))

        self.rec_status_var = tk.StringVar(value=self._all_label)
        self.rec_account_var = tk.StringVar(value=self._all_label)
        self.rec_category_var = tk.StringVar(value=self._all_label)
        self.rec_freq_var = tk.StringVar(value=self._all_label)

        ttk.Label(fr, text=f'{tr("common.status")}:').pack(side="left", padx=(8, 4), pady=4)
        self.rec_status_filter = ttk.Combobox(fr, textvariable=self.rec_status_var, state="readonly", width=12)
        self.rec_status_filter["values"] = (self._all_label, tr("status.active"), tr("status.inactive"))
        self.rec_status_filter.pack(side="left", pady=4)

        ttk.Label(fr, text=f'{tr("common.account")}:').pack(side="left", padx=(12, 4), pady=4)
        self.rec_account_filter = ttk.Combobox(fr, textvariable=self.rec_account_var, state="readonly", width=28)
        self.rec_account_filter["values"] = (self._all_label,)
        self.rec_account_filter.pack(side="left", pady=4)

        ttk.Label(fr, text=f'{tr("common.category")}:').pack(side="left", padx=(12, 4), pady=4)
        self.rec_category_filter = ttk.Combobox(fr, textvariable=self.rec_category_var, state="readonly", width=28)
        self.rec_category_filter["values"] = (self._all_label,)
        self.rec_category_filter.pack(side="left", pady=4)

        ttk.Label(fr, text=f'{tr("expenses.recurring.col.frequency")}:').pack(side="left", padx=(12, 4), pady=4)
        self.rec_freq_filter = ttk.Combobox(fr, textvariable=self.rec_freq_var, state="readonly", width=10)
        self.rec_freq_filter["values"] = (self._all_label,)
        self.rec_freq_filter.pack(side="left", pady=4)

        self.rec_filter_reset_btn = ttk.Button(fr, text=tr("common.reset"))
        self.rec_filter_reset_btn.pack(side="right", padx=8, pady=4)

        cols_r = ["name", "category", "amount", "freq", "anchor_month", "due", "status", "account", "override"]
        heads_r = {
            "name": tr("expenses.recurring.col.name"),
            "category": tr("expenses.recurring.col.category"),
            "amount": tr("expenses.recurring.col.amount"),
            "freq": tr("expenses.recurring.col.frequency"),
            "anchor_month": tr("expenses.recurring.col.anchor_month"),
            "due": tr("expenses.recurring.col.due_day"),
            "status": tr("expenses.recurring.col.status"),
            "account": tr("expenses.recurring.col.account"),
            "override": tr("expenses.recurring.col.override"),
        }
        self.rec_tree, frame_r = create_treeview_with_scrollbars(
            self.tab_recurring, columns=cols_r, headings=heads_r, height=18
        )
        frame_r.pack(fill="both", expand=True)
        self.rec_sum_label = ttk.Label(self.tab_recurring, text="", anchor="e")
        self.rec_sum_label.pack(fill="x", padx=8, pady=(2, 4))

        # -------------------- Variable --------------------
        btns_v = ttk.Frame(self.tab_variable)
        btns_v.pack(fill="x", pady=(0, 6))
        self.add_var_btn = ttk.Button(btns_v, text=tr("common.new"))
        self.edit_var_btn = ttk.Button(btns_v, text=tr("common.edit"))
        self.pay_var_btn = ttk.Button(btns_v, text=tr("expenses.variable.btn.mark_paid"))
        self.delete_var_btn = ttk.Button(btns_v, text=tr("expenses.variable.btn.cancel"))
        self.undo_var_btn = ttk.Button(btns_v, text=tr("expenses.variable.btn.reopen"))
        self.move_var_btn = ttk.Button(btns_v, text=tr("expenses.variable.btn.move"))

        self.add_var_btn.pack(side="left")
        self.edit_var_btn.pack(side="left", padx=(6, 0))
        self.pay_var_btn.pack(side="left", padx=(6, 0))
        self.delete_var_btn.pack(side="left", padx=(6, 0))
        self.undo_var_btn.pack(side="left", padx=(6, 0))
        self.move_var_btn.pack(side="left", padx=(6, 0))

        fv = ttk.LabelFrame(self.tab_variable, text=tr("common.filter"))
        fv.pack(fill="x", pady=(0, 6))

        self.var_status_var = tk.StringVar(value=self._all_label)
        self.var_account_var = tk.StringVar(value=self._all_label)
        self.var_category_var = tk.StringVar(value=self._all_label)

        ttk.Label(fv, text=f'{tr("common.status")}:').pack(side="left", padx=(8, 4), pady=4)
        self.var_status_filter = ttk.Combobox(fv, textvariable=self.var_status_var, state="readonly", width=12)
        self.var_status_filter["values"] = (self._all_label, tr("status.open"), tr("status.paid"), tr("status.cancelled"))
        self.var_status_filter.pack(side="left", pady=4)

        ttk.Label(fv, text=f'{tr("common.account")}:').pack(side="left", padx=(12, 4), pady=4)
        self.var_account_filter = ttk.Combobox(fv, textvariable=self.var_account_var, state="readonly", width=28)
        self.var_account_filter["values"] = (self._all_label,)
        self.var_account_filter.pack(side="left", pady=4)

        ttk.Label(fv, text=f'{tr("common.category")}:').pack(side="left", padx=(12, 4), pady=4)
        self.var_category_filter = ttk.Combobox(fv, textvariable=self.var_category_var, state="readonly", width=28)
        self.var_category_filter["values"] = (self._all_label,)
        self.var_category_filter.pack(side="left", pady=4)

        self.var_filter_reset_btn = ttk.Button(fv, text=tr("common.reset"))
        self.var_filter_reset_btn.pack(side="right", padx=8, pady=4)

        cols_v = ["name", "category", "amount", "status", "pay_bucket", "account"]
        heads_v = {
            "name": tr("expenses.variable.col.name"),
            "category": tr("expenses.variable.col.category"),
            "amount": tr("expenses.variable.col.amount"),
            "status": tr("expenses.variable.col.status"),
            "pay_bucket": tr("expenses.variable.col.pay_bucket"),
            "account": tr("expenses.variable.col.account"),
        }
        self.var_tree, frame_v = create_treeview_with_scrollbars(
            self.tab_variable, columns=cols_v, headings=heads_v, height=18
        )
        frame_v.pack(fill="both", expand=True)
        self.var_sum_label = ttk.Label(self.tab_variable, text="", anchor="e")
        self.var_sum_label.pack(fill="x", padx=8, pady=(2, 4))

    # -------------------- bindings / getters --------------------
    def bind_refresh(self, fn) -> None:
        self.refresh_btn.configure(command=fn)
        self.period_selector._on_change = fn

    def bind_filter_change(self, fn) -> None:
        for cb in (
            self.loan_status_filter,
            self.loan_account_filter,
            self.loan_timing_filter,
            self.rec_status_filter,
            self.rec_account_filter,
            self.rec_category_filter,
            self.rec_freq_filter,
            self.var_status_filter,
            self.var_account_filter,
            self.var_category_filter,
        ):
            cb.bind("<<ComboboxSelected>>", lambda _e: fn())

        self.loan_only_relevant_chk.configure(command=fn)

        self.loan_filter_reset_btn.configure(command=self._reset_loan_filters(fn))
        self.rec_filter_reset_btn.configure(command=self._reset_rec_filters(fn))
        self.var_filter_reset_btn.configure(command=self._reset_var_filters(fn))

    def _reset_loan_filters(self, fn):
        def _do():
            self.loan_status_var.set(self._all_label)
            self.loan_account_var.set(self._all_label)
            self.loan_timing_var.set(self._all_label)
            self.loan_only_relevant_var.set(True)
            fn()

        return _do

    def _reset_rec_filters(self, fn):
        def _do():
            self.rec_status_var.set(self._all_label)
            self.rec_account_var.set(self._all_label)
            self.rec_category_var.set(self._all_label)
            self.rec_freq_var.set(self._all_label)
            fn()

        return _do

    def _reset_var_filters(self, fn):
        def _do():
            self.var_status_var.set(self._all_label)
            self.var_account_var.set(self._all_label)
            self.var_category_var.set(self._all_label)
            fn()

        return _do

    def set_filter_options(
        self,
        *,
        accounts: list[str],
        rec_categories: list[str],
        var_categories: list[str],
        rec_freqs: list[str] = (),
    ) -> None:
        self.loan_account_filter["values"] = (self._all_label, *accounts)
        if self.loan_account_var.get() not in self.loan_account_filter["values"]:
            self.loan_account_var.set(self._all_label)

        self.rec_account_filter["values"] = (self._all_label, *accounts)
        if self.rec_account_var.get() not in self.rec_account_filter["values"]:
            self.rec_account_var.set(self._all_label)

        self.var_account_filter["values"] = (self._all_label, *accounts)
        if self.var_account_var.get() not in self.var_account_filter["values"]:
            self.var_account_var.set(self._all_label)

        self.rec_category_filter["values"] = (self._all_label, *rec_categories)
        if self.rec_category_var.get() not in self.rec_category_filter["values"]:
            self.rec_category_var.set(self._all_label)

        self.var_category_filter["values"] = (self._all_label, *var_categories)
        if self.var_category_var.get() not in self.var_category_filter["values"]:
            self.var_category_var.set(self._all_label)

        self.rec_freq_filter["values"] = (self._all_label, *rec_freqs)
        if self.rec_freq_var.get() not in self.rec_freq_filter["values"]:
            self.rec_freq_var.set(self._all_label)

    def get_period(self):
        return self.period_selector.get_period()

    def get_view_mode(self) -> str:
        return self.period_selector.get_view_mode()

    def is_year_view(self) -> bool:
        return self.period_selector.is_year_view()

    def get_filters(self) -> dict:
        return {
            "loan": {
                "status": self.loan_status_var.get(),
                "account": self.loan_account_var.get(),
                "timing": self.loan_timing_var.get(),
                "only_relevant": bool(self.loan_only_relevant_var.get()),
            },
            "recurring": {
                "status": self.rec_status_var.get(),
                "account": self.rec_account_var.get(),
                "category": self.rec_category_var.get(),
                "freq": self.rec_freq_var.get(),
            },
            "variable": {
                "status": self.var_status_var.get(),
                "account": self.var_account_var.get(),
                "category": self.var_category_var.get(),
            },
        }
