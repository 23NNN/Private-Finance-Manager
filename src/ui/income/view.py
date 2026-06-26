# src/ui/income/view.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from src.ui.common.controls import create_treeview_with_scrollbars
from src.ui.common.period_selector import PeriodSelector
from src.ui.common.i18n import tr


class IncomeView(ttk.Frame):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent, padding=8)

        top = ttk.Frame(self)
        top.pack(fill="x")

        self.period_selector = PeriodSelector(top, on_change=lambda: None, show_year_toggle=True)
        self.period_selector.pack(side="left")

        self.refresh_btn = ttk.Button(top, text=tr("common.refresh"))
        self.refresh_btn.pack(side="right")

        nb = ctk.CTkTabview(self, corner_radius=4)
        nb.pack(fill="both", expand=True, pady=(8, 0))

        _t_fixed = tr("income.tab.fixed")
        _t_hourly = tr("income.tab.hourly")
        _t_special = tr("income.tab.special")
        _t_employers = tr("income.tab.employers")
        nb.add(_t_fixed)
        nb.add(_t_hourly)
        nb.add(_t_special)
        nb.add(_t_employers)
        self.tab_fixed = nb.tab(_t_fixed)
        self.tab_hourly = nb.tab(_t_hourly)
        self.tab_special = nb.tab(_t_special)
        self.tab_employers = nb.tab(_t_employers)

        # -------------------- Fixed salary --------------------
        btns_f = ttk.Frame(self.tab_fixed)
        btns_f.pack(fill="x", pady=(0, 6))
        self.add_fixed_btn = ttk.Button(btns_f, text=tr("common.new"))
        self.edit_fixed_btn = ttk.Button(btns_f, text=tr("common.edit"))
        self.delete_fixed_btn = ttk.Button(btns_f, text=tr("common.delete"))
        self.add_fixed_btn.pack(side="left")
        self.edit_fixed_btn.pack(side="left", padx=(6, 0))
        self.delete_fixed_btn.pack(side="left", padx=(6, 0))

        flt_f = ttk.LabelFrame(self.tab_fixed, text=tr("common.filter"))
        flt_f.pack(fill="x", pady=(0, 6))

        self.fixed_employer_var = tk.StringVar(value=tr("common.all"))
        self.fixed_timing_var = tk.StringVar(value=tr("common.all"))
        self.fixed_account_var = tk.StringVar(value=tr("common.all"))

        ttk.Label(flt_f, text=tr("income.label.employer")).pack(side="left", padx=(8, 4), pady=4)
        self.fixed_employer_cb = ttk.Combobox(
            flt_f,
            state="readonly",
            width=28,
            textvariable=self.fixed_employer_var,
            values=(tr("common.all"),),
        )
        self.fixed_employer_cb.pack(side="left", pady=4)

        ttk.Label(flt_f, text=tr("income.label.payout")).pack(side="left", padx=(12, 4), pady=4)
        self.fixed_timing_cb = ttk.Combobox(
            flt_f,
            state="readonly",
            width=10,
            textvariable=self.fixed_timing_var,
            values=(tr("common.all"), tr("timing.beginning"), tr("timing.mid")),
        )
        self.fixed_timing_cb.pack(side="left", pady=4)

        ttk.Label(flt_f, text=tr("income.label.account")).pack(side="left", padx=(12, 4), pady=4)
        self.fixed_account_cb = ttk.Combobox(
            flt_f,
            state="readonly",
            width=28,
            textvariable=self.fixed_account_var,
            values=(tr("common.all"),),
        )
        self.fixed_account_cb.pack(side="left", pady=4)

        self.fixed_reset_btn = ttk.Button(flt_f, text=tr("common.reset"))
        self.fixed_reset_btn.pack(side="right", padx=8, pady=4)

        cols_f = ["employer", "base", "special", "calc", "actual", "timing", "account"]
        heads_f = {
            "employer": tr("income.col.employer"),
            "base": tr("income.col.base_amount"),
            "special": tr("income.col.special"),
            "calc": tr("income.col.calculated"),
            "actual": tr("income.col.actual"),
            "timing": tr("income.col.payout"),
            "account": tr("income.col.account"),
        }
        self.fixed_tree, frame_f = create_treeview_with_scrollbars(
            self.tab_fixed, columns=cols_f, headings=heads_f, height=16
        )
        frame_f.pack(fill="both", expand=True)

        # -------------------- Hourly wage --------------------
        btns_h = ttk.Frame(self.tab_hourly)
        btns_h.pack(fill="x", pady=(0, 6))
        self.add_hourly_btn = ttk.Button(btns_h, text=tr("common.new"))
        self.edit_hourly_btn = ttk.Button(btns_h, text=tr("common.edit"))
        self.delete_hourly_btn = ttk.Button(btns_h, text=tr("common.delete"))
        self.recalc_hourly_btn = ttk.Button(btns_h, text=tr("income.recalculate"))
        self.add_hourly_btn.pack(side="left")
        self.edit_hourly_btn.pack(side="left", padx=(6, 0))
        self.delete_hourly_btn.pack(side="left", padx=(6, 0))
        self.recalc_hourly_btn.pack(side="left", padx=(6, 0))

        flt_h = ttk.LabelFrame(self.tab_hourly, text=tr("common.filter"))
        flt_h.pack(fill="x", pady=(0, 6))

        self.hourly_employer_var = tk.StringVar(value=tr("common.all"))
        self.hourly_account_var = tk.StringVar(value=tr("common.all"))

        ttk.Label(flt_h, text=tr("income.label.employer")).pack(side="left", padx=(8, 4), pady=4)
        self.hourly_employer_cb = ttk.Combobox(
            flt_h,
            state="readonly",
            width=28,
            textvariable=self.hourly_employer_var,
            values=(tr("common.all"),),
        )
        self.hourly_employer_cb.pack(side="left", pady=4)

        ttk.Label(flt_h, text=tr("income.label.account")).pack(side="left", padx=(12, 4), pady=4)
        self.hourly_account_cb = ttk.Combobox(
            flt_h,
            state="readonly",
            width=28,
            textvariable=self.hourly_account_var,
            values=(tr("common.all"),),
        )
        self.hourly_account_cb.pack(side="left", pady=4)

        self.hourly_reset_btn = ttk.Button(flt_h, text=tr("common.reset"))
        self.hourly_reset_btn.pack(side="right", padx=8, pady=4)

        cols_h = ["employer", "hours", "night", "sunday", "holiday", "overtime", "calc", "actual", "account"]
        heads_h = {
            "employer": tr("income.col.employer"),
            "hours": tr("income.col.hours"),
            "night": tr("income.col.night"),
            "sunday": tr("income.col.sunday"),
            "holiday": tr("income.col.holiday"),
            "overtime": tr("income.col.overtime"),
            "calc": tr("income.col.calculated"),
            "actual": tr("income.col.actual"),
            "account": tr("income.col.account"),
        }
        self.hourly_tree, frame_h = create_treeview_with_scrollbars(
            self.tab_hourly, columns=cols_h, headings=heads_h, height=16
        )
        frame_h.pack(fill="both", expand=True)

        # -------------------- Special income --------------------
        btns_s = ttk.Frame(self.tab_special)
        btns_s.pack(fill="x", pady=(0, 6))
        self.add_special_btn = ttk.Button(btns_s, text=tr("common.new"))
        self.edit_special_btn = ttk.Button(btns_s, text=tr("common.edit"))
        self.delete_special_btn = ttk.Button(btns_s, text=tr("common.delete"))
        self.move_special_btn = ttk.Button(btns_s, text=tr("income.special.btn.move"))
        self.add_special_btn.pack(side="left")
        self.edit_special_btn.pack(side="left", padx=(6, 0))
        self.delete_special_btn.pack(side="left", padx=(6, 0))
        self.move_special_btn.pack(side="left", padx=(6, 0))

        flt_s = ttk.LabelFrame(self.tab_special, text=tr("common.filter"))
        flt_s.pack(fill="x", pady=(0, 6))

        self.special_timing_var = tk.StringVar(value=tr("common.all"))
        self.special_account_var = tk.StringVar(value=tr("common.all"))

        ttk.Label(flt_s, text=tr("income.label.payout")).pack(side="left", padx=(8, 4), pady=4)
        self.special_timing_cb = ttk.Combobox(
            flt_s,
            state="readonly",
            width=10,
            textvariable=self.special_timing_var,
            values=(tr("common.all"), tr("timing.beginning"), tr("timing.mid")),
        )
        self.special_timing_cb.pack(side="left", pady=4)

        ttk.Label(flt_s, text=tr("income.label.account")).pack(side="left", padx=(12, 4), pady=4)
        self.special_account_cb = ttk.Combobox(
            flt_s,
            state="readonly",
            width=28,
            textvariable=self.special_account_var,
            values=(tr("common.all"),),
        )
        self.special_account_cb.pack(side="left", pady=4)

        self.special_reset_btn = ttk.Button(flt_s, text=tr("common.reset"))
        self.special_reset_btn.pack(side="right", padx=8, pady=4)

        cols_sp = ["name", "amount", "actual", "timing", "account", "notes"]
        heads_sp = {
            "name": tr("income.col.name"),
            "amount": tr("income.col.amount"),
            "actual": tr("income.col.actual"),
            "timing": tr("income.col.payout"),
            "account": tr("income.col.account"),
            "notes": tr("income.col.notes"),
        }
        self.special_tree, frame_sp = create_treeview_with_scrollbars(
            self.tab_special, columns=cols_sp, headings=heads_sp, height=16
        )
        frame_sp.pack(fill="both", expand=True)

        # -------------------- Employers & rules --------------------
        emp_top = ttk.Frame(self.tab_employers)
        emp_top.pack(fill="x", pady=(0, 6))

        self.add_employer_btn = ttk.Button(emp_top, text=tr("income.employer.add"))
        self.edit_employer_btn = ttk.Button(emp_top, text=tr("income.employer.edit"))
        self.delete_employer_btn = ttk.Button(emp_top, text=tr("income.employer.delete"))
        self.add_rule_btn = ttk.Button(emp_top, text=tr("income.rule.add"))
        self.edit_rule_btn = ttk.Button(emp_top, text=tr("income.rule.edit"))
        self.delete_rule_btn = ttk.Button(emp_top, text=tr("income.rule.delete"))

        self.add_employer_btn.pack(side="left")
        self.edit_employer_btn.pack(side="left", padx=(6, 0))
        self.delete_employer_btn.pack(side="left", padx=(6, 0))
        self.delete_rule_btn.pack(side="right")
        self.edit_rule_btn.pack(side="right", padx=(6, 0))
        self.add_rule_btn.pack(side="right", padx=(6, 0))

        emp_filter = ttk.LabelFrame(self.tab_employers, text=tr("income.employer.filter.title"))
        emp_filter.pack(fill="x", pady=(0, 6))

        self.emp_name_q_var = tk.StringVar(value="")
        self.emp_timing_var = tk.StringVar(value=tr("common.all"))
        self.emp_account_var = tk.StringVar(value=tr("common.all"))

        ttk.Label(emp_filter, text=tr("income.employer.filter.name_contains")).pack(side="left", padx=(8, 4), pady=4)
        self.emp_name_q_entry = ttk.Entry(emp_filter, width=26, textvariable=self.emp_name_q_var)
        self.emp_name_q_entry.pack(side="left", pady=4)

        ttk.Label(emp_filter, text=tr("income.label.payout")).pack(side="left", padx=(12, 4), pady=4)
        self.emp_timing_cb = ttk.Combobox(
            emp_filter,
            state="readonly",
            width=10,
            textvariable=self.emp_timing_var,
            values=(tr("common.all"), tr("timing.beginning"), tr("timing.mid")),
        )
        self.emp_timing_cb.pack(side="left", pady=4)

        ttk.Label(emp_filter, text=tr("income.employer.filter.default_account")).pack(side="left", padx=(12, 4), pady=4)
        self.emp_account_cb = ttk.Combobox(
            emp_filter,
            state="readonly",
            width=28,
            textvariable=self.emp_account_var,
            values=(tr("common.all"),),
        )
        self.emp_account_cb.pack(side="left", pady=4)

        self.emp_reset_btn = ttk.Button(emp_filter, text=tr("common.reset"))
        self.emp_reset_btn.pack(side="right", padx=8, pady=4)

        cols_e = ["name", "timing", "default_account"]
        heads_e = {"name": tr("income.col.name"), "timing": tr("income.col.payout"), "default_account": tr("income.col.default_account")}
        self.employer_tree, frame_e = create_treeview_with_scrollbars(
            self.tab_employers, columns=cols_e, headings=heads_e, height=8
        )
        frame_e.pack(fill="both", expand=False)

        rule_filter = ttk.LabelFrame(self.tab_employers, text=tr("income.rule.filter.title"))
        rule_filter.pack(fill="x", pady=(8, 6))

        self.rule_type_var = tk.StringVar(value=tr("common.all"))
        self.rule_active_only_var = tk.BooleanVar(value=True)

        ttk.Label(rule_filter, text=tr("income.rule.filter.type")).pack(side="left", padx=(8, 4), pady=4)
        self.rule_type_cb = ttk.Combobox(
            rule_filter, state="readonly", width=22, textvariable=self.rule_type_var, values=(tr("common.all"),)
        )
        self.rule_type_cb.pack(side="left", pady=4)

        self.rule_active_only_chk = ttk.Checkbutton(
            rule_filter,
            text=tr("income.rule.filter.only_active"),
            variable=self.rule_active_only_var,
        )
        self.rule_active_only_chk.pack(side="left", padx=(12, 0), pady=4)

        self.rule_reset_btn = ttk.Button(rule_filter, text=tr("common.reset"))
        self.rule_reset_btn.pack(side="right", padx=8, pady=4)

        cols_r = ["rule_type", "unit", "value", "valid_from", "valid_to", "notes"]
        heads_r = {
            "rule_type": tr("income.col.rule_type"),
            "unit": tr("income.col.unit"),
            "value": tr("income.col.value"),
            "valid_from": tr("income.col.valid_from"),
            "valid_to": tr("income.col.valid_to"),
            "notes": tr("income.col.notes"),
        }
        self.rules_tree, frame_r = create_treeview_with_scrollbars(
            self.tab_employers, columns=cols_r, headings=heads_r, height=8
        )
        frame_r.pack(fill="both", expand=True)

        sav = ttk.LabelFrame(self.tab_employers, text=tr("income.savings_rate.title"))
        sav.pack(fill="both", expand=False, pady=(8, 0))

        sav_btns = ttk.Frame(sav)
        sav_btns.pack(fill="x", padx=6, pady=(6, 0))
        self.add_savings_rule_btn = ttk.Button(sav_btns, text=tr("income.savings_rate.add"))
        self.edit_savings_rule_btn = ttk.Button(sav_btns, text=tr("income.savings_rate.edit"))
        self.delete_savings_rule_btn = ttk.Button(sav_btns, text=tr("income.savings_rate.delete"))
        self.add_savings_rule_btn.pack(side="left")
        self.edit_savings_rule_btn.pack(side="left", padx=(6, 0))
        self.delete_savings_rule_btn.pack(side="left", padx=(6, 0))

        cols_sr = ["percentage", "valid_from", "valid_to"]
        heads_sr = {"percentage": tr("income.col.savings_rate"), "valid_from": tr("income.col.valid_from"), "valid_to": tr("income.col.valid_to")}
        self.savings_rules_tree, frame_sr = create_treeview_with_scrollbars(
            sav, columns=cols_sr, headings=heads_sr, height=5
        )
        frame_sr.pack(fill="both", expand=True, padx=6, pady=(6, 6))

    # -------- bindings / adapters --------
    def bind_refresh(self, fn) -> None:
        self.refresh_btn.configure(command=fn)
        self.period_selector._on_change = fn

    def bind_filter_change(self, fn) -> None:
        self.fixed_employer_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.fixed_timing_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.fixed_account_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.fixed_reset_btn.configure(command=lambda: self._reset_fixed(fn))

        self.hourly_employer_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.hourly_account_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.hourly_reset_btn.configure(command=lambda: self._reset_hourly(fn))

        self.special_timing_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.special_account_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.special_reset_btn.configure(command=lambda: self._reset_special(fn))

        self.emp_name_q_entry.bind("<KeyRelease>", lambda _e: fn())
        self.emp_timing_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.emp_account_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.emp_reset_btn.configure(command=lambda: self._reset_emp(fn))

        self.rule_type_cb.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.rule_active_only_chk.configure(command=fn)
        self.rule_reset_btn.configure(command=lambda: self._reset_rules(fn))

    def _reset_fixed(self, fn) -> None:
        self.fixed_employer_var.set(tr("common.all"))
        self.fixed_timing_var.set(tr("common.all"))
        self.fixed_account_var.set(tr("common.all"))
        fn()

    def _reset_hourly(self, fn) -> None:
        self.hourly_employer_var.set(tr("common.all"))
        self.hourly_account_var.set(tr("common.all"))
        fn()

    def _reset_special(self, fn) -> None:
        self.special_timing_var.set(tr("common.all"))
        self.special_account_var.set(tr("common.all"))
        fn()

    def _reset_emp(self, fn) -> None:
        self.emp_name_q_var.set("")
        self.emp_timing_var.set(tr("common.all"))
        self.emp_account_var.set(tr("common.all"))
        fn()

    def _reset_rules(self, fn) -> None:
        self.rule_type_var.set(tr("common.all"))
        self.rule_active_only_var.set(True)
        fn()

    def set_filter_options(self, *, employers: list[str], accounts: list[str], rule_types: list[str]) -> None:
        ev = (tr("common.all"), *employers)
        av = (tr("common.all"), *accounts)
        rv = (tr("common.all"), *rule_types)

        self.fixed_employer_cb["values"] = ev
        if self.fixed_employer_var.get() not in ev:
            self.fixed_employer_var.set(tr("common.all"))

        self.hourly_employer_cb["values"] = ev
        if self.hourly_employer_var.get() not in ev:
            self.hourly_employer_var.set(tr("common.all"))

        self.fixed_account_cb["values"] = av
        if self.fixed_account_var.get() not in av:
            self.fixed_account_var.set(tr("common.all"))

        self.hourly_account_cb["values"] = av
        if self.hourly_account_var.get() not in av:
            self.hourly_account_var.set(tr("common.all"))

        self.special_account_cb["values"] = av
        if self.special_account_var.get() not in av:
            self.special_account_var.set(tr("common.all"))

        self.emp_account_cb["values"] = av
        if self.emp_account_var.get() not in av:
            self.emp_account_var.set(tr("common.all"))

        self.rule_type_cb["values"] = rv
        if self.rule_type_var.get() not in rv:
            self.rule_type_var.set(tr("common.all"))

    def get_period(self):
        return self.period_selector.get_period()

    def get_view_mode(self) -> str:
        return self.period_selector.get_view_mode()

    def is_year_view(self) -> bool:
        return self.period_selector.is_year_view()

    def get_filters(self) -> dict:
        return {
            "fixed": {
                "employer": self.fixed_employer_var.get(),
                "timing": self.fixed_timing_var.get(),
                "account": self.fixed_account_var.get(),
            },
            "hourly": {
                "employer": self.hourly_employer_var.get(),
                "account": self.hourly_account_var.get(),
            },
            "special": {
                "timing": self.special_timing_var.get(),
                "account": self.special_account_var.get(),
            },
            "employers": {
                "name_q": self.emp_name_q_var.get(),
                "timing": self.emp_timing_var.get(),
                "account": self.emp_account_var.get(),
            },
            "rules": {
                "type": self.rule_type_var.get(),
                "active_only": bool(self.rule_active_only_var.get()),
            },
        }
