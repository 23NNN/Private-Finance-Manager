# src/ui/overview/view.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.ui.common.controls import create_treeview_with_scrollbars
from src.ui.common.period_selector import PeriodSelector
from src.ui.common.i18n import tr, trf

VIEW_MODES = ("CASHFLOW", "BUDGET_MONTH", "BUDGET_QUARTER")
TIMEFRAMES = ("MONTH", "YEAR")


class OverviewView(ttk.Frame):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent, padding=8)

        self._refresh_cb = lambda: None

        top = ttk.Frame(self)
        top.pack(fill="x")

        self._view_mode_labels = {c: tr(f"overview.view_mode.{c.lower()}") for c in VIEW_MODES}
        self._view_mode_labels_rev = {v: k for k, v in self._view_mode_labels.items()}
        self.view_mode_var = tk.StringVar(value=self._view_mode_labels["CASHFLOW"])
        ttk.Label(top, text=tr("overview.label.mode")).pack(side="left")
        self.view_mode = ttk.Combobox(
            top,
            width=22,
            state="readonly",
            values=list(self._view_mode_labels.values()),
            textvariable=self.view_mode_var,
        )
        self.view_mode.pack(side="left", padx=(6, 12))

        self._timeframe_labels = {c: tr(f"overview.timeframe.{c.lower()}") for c in TIMEFRAMES}
        self._timeframe_labels_rev = {v: k for k, v in self._timeframe_labels.items()}
        self.timeframe_var = tk.StringVar(value=self._timeframe_labels["MONTH"])
        ttk.Label(top, text=tr("overview.label.timeframe")).pack(side="left")
        self.timeframe = ttk.Combobox(
            top,
            width=10,
            state="readonly",
            values=list(self._timeframe_labels.values()),
            textvariable=self.timeframe_var,
        )
        self.timeframe.pack(side="left", padx=(6, 12))

        self.period_selector = PeriodSelector(top, on_change=lambda: None)
        self.period_selector.pack(side="left")

        self.refresh_btn = ttk.Button(top, text=tr("common.refresh"))
        self.refresh_btn.pack(side="right")

        ttk.Separator(self).pack(fill="x", pady=8)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        self.current_frame = ttk.LabelFrame(body, text=tr("overview.period.current_month"))
        self.current_frame.pack(fill="both", expand=True, side="left", padx=(0, 6))

        self.next_frame = ttk.LabelFrame(body, text=tr("overview.period.next_month"))
        self.next_frame.pack(fill="both", expand=True, side="left", padx=(6, 0))

        self._build_period_section(self.current_frame, prefix="cur")
        self._build_period_section(self.next_frame, prefix="nxt")

        self._apply_timeframe_ui()

    def bind_refresh(self, fn) -> None:
        self._refresh_cb = fn
        self.refresh_btn.configure(command=fn)
        self.view_mode.bind("<<ComboboxSelected>>", lambda _e: fn())
        self.timeframe.bind("<<ComboboxSelected>>", lambda _e: self._on_timeframe_change())
        self.period_selector._on_change = fn

    def _on_timeframe_change(self) -> None:
        self._apply_timeframe_ui()
        self._refresh_cb()

    def _apply_timeframe_ui(self) -> None:
        tf = self.get_timeframe()
        if tf == "YEAR":
            self.period_selector.set_month_enabled(False)
            try:
                self.next_frame.pack_forget()
            except Exception:
                pass
            self.current_frame.configure(text=trf("overview.period.year", year=self.get_year()))
        else:
            self.period_selector.set_month_enabled(True)
            if not self.next_frame.winfo_ismapped():
                self.next_frame.pack(fill="both", expand=True, side="left", padx=(6, 0))
            self.current_frame.configure(text=tr("overview.period.current_month"))
            self.next_frame.configure(text=tr("overview.period.next_month"))

    def get_view_mode(self) -> str:
        disp = self.view_mode_var.get().strip()
        return self._view_mode_labels_rev.get(disp, "CASHFLOW")

    def get_timeframe(self) -> str:
        disp = self.timeframe_var.get().strip()
        return self._timeframe_labels_rev.get(disp, "MONTH")

    def get_period(self):
        return self.period_selector.get_period()

    def get_year(self) -> int:
        return int(self.period_selector.get_period().year)

    def _build_footer(self, parent: ttk.Frame, columns: list[str]) -> dict[str, ttk.Label]:
        footer = ttk.Frame(parent)
        footer.pack(fill="x", padx=6, pady=(4, 6))

        labels: dict[str, ttk.Label] = {}
        for idx, col in enumerate(columns):
            lbl = ttk.Label(footer, text="", anchor="w")
            lbl.grid(row=0, column=idx, sticky="ew")
            labels[col] = lbl
            footer.columnconfigure(idx, weight=(2 if idx == 0 else 1))
        return labels

    def _build_period_section(self, parent: ttk.Frame, prefix: str) -> None:
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(6, 8), padx=6)

        self.__dict__[f"{prefix}_lbl_savings"] = ttk.Label(top, text=trf("overview.summary.savings_total", amount="0.00"))
        self.__dict__[f"{prefix}_lbl_fix"] = ttk.Label(top, text=trf("overview.summary.fixed", amount="0.00"))
        self.__dict__[f"{prefix}_lbl_var"] = ttk.Label(top, text=trf("overview.summary.variable", amount="0.00"))

        self.__dict__[f"{prefix}_lbl_savings"].pack(side="left")
        self.__dict__[f"{prefix}_lbl_fix"].pack(side="left", padx=(12, 0))
        self.__dict__[f"{prefix}_lbl_var"].pack(side="left", padx=(12, 0))

        pane = ttk.Frame(parent)
        pane.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        lf_inc = ttk.LabelFrame(pane, text=tr("overview.section.income_by_source"))
        lf_acc = ttk.LabelFrame(pane, text=tr("overview.section.expenses_by_account"))
        lf_loan = ttk.LabelFrame(pane, text=tr("overview.section.loans"))
        lf_sum = ttk.LabelFrame(pane, text=tr("overview.section.by_payout"))

        lf_inc.pack(fill="both", expand=True, pady=(0, 6))
        lf_acc.pack(fill="both", expand=True, pady=(0, 6))
        lf_loan.pack(fill="both", expand=True, pady=(0, 6))
        lf_sum.pack(fill="both", expand=True)

        inc_cols = ["quelle", "calc", "actual", "sparen"]
        inc_heads = {"quelle": tr("overview.col.source"), "calc": tr("overview.col.calculated"), "actual": tr("overview.col.actual"), "sparen": tr("overview.col.savings")}
        inc_tree, inc_frame = create_treeview_with_scrollbars(lf_inc, inc_cols, inc_heads, height=5)
        inc_frame.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        self.__dict__[f"{prefix}_tree_incomes"] = inc_tree
        self.__dict__[f"{prefix}_footer_incomes"] = self._build_footer(lf_inc, inc_cols)

        acc_cols = ["konto", "fix", "fix_pct", "var", "var_pct"]
        acc_heads = {"konto": tr("overview.col.account"), "fix": tr("overview.col.fixed"), "fix_pct": tr("overview.col.fixed_pct"), "var": tr("overview.col.variable"), "var_pct": tr("overview.col.variable_pct")}
        acc_tree, acc_frame = create_treeview_with_scrollbars(lf_acc, acc_cols, acc_heads, height=5)
        acc_frame.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        self.__dict__[f"{prefix}_tree_accounts"] = acc_tree
        self.__dict__[f"{prefix}_footer_accounts"] = self._build_footer(lf_acc, acc_cols)

        loan_cols = ["kredit", "open_before", "payment", "extra", "open_after"]
        loan_heads = {
            "kredit": tr("overview.col.loan"),
            "open_before": tr("overview.col.open_before"),
            "payment": tr("overview.col.payment"),
            "extra": tr("overview.col.extra"),
            "open_after": tr("overview.col.open_after"),
        }
        loan_tree, loan_frame = create_treeview_with_scrollbars(lf_loan, loan_cols, loan_heads, height=5)
        loan_frame.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        self.__dict__[f"{prefix}_tree_loans"] = loan_tree
        self.__dict__[f"{prefix}_footer_loans"] = self._build_footer(lf_loan, loan_cols)

        sum_cols = ["auszahlung", "gesamt", "sparen", "schulden", "fixkosten", "frei"]
        sum_heads = {
            "auszahlung": tr("overview.col.payout"),
            "gesamt": tr("overview.col.total"),
            "sparen": tr("overview.col.savings"),
            "schulden": tr("overview.col.debts"),
            "fixkosten": tr("overview.col.fixed_costs"),
            "frei": tr("overview.col.free"),
        }
        sum_tree, sum_frame = create_treeview_with_scrollbars(lf_sum, sum_cols, sum_heads, height=3)
        sum_frame.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        self.__dict__[f"{prefix}_tree_summary"] = sum_tree
        self.__dict__[f"{prefix}_footer_summary"] = self._build_footer(lf_sum, sum_cols)

    def set_period_data(self, prefix: str, *, savings_total: str, fix_total: str, var_total: str) -> None:
        self.__dict__[f"{prefix}_lbl_savings"].configure(text=trf("overview.summary.savings_total", amount=savings_total))
        self.__dict__[f"{prefix}_lbl_fix"].configure(text=trf("overview.summary.fixed", amount=fix_total))
        self.__dict__[f"{prefix}_lbl_var"].configure(text=trf("overview.summary.variable", amount=var_total))

    def set_incomes(self, prefix: str, rows: list[tuple[str, str, str, str]], *, footer: tuple[str, str, str, str]) -> None:
        tree = self.__dict__[f"{prefix}_tree_incomes"]
        tree.delete(*tree.get_children())
        for i, (q, c, a, s) in enumerate(rows):
            tree.insert("", "end", iid=str(i), values=(q, c, a, s))

        f = self.__dict__[f"{prefix}_footer_incomes"]
        f["quelle"].configure(text=footer[0])
        f["calc"].configure(text=footer[1])
        f["actual"].configure(text=footer[2])
        f["sparen"].configure(text=footer[3])

    def set_accounts(self, prefix: str, rows: list[tuple[str, str, str, str, str]], *, footer: tuple[str, str, str, str, str]) -> None:
        tree = self.__dict__[f"{prefix}_tree_accounts"]
        tree.delete(*tree.get_children())
        for i, r in enumerate(rows):
            tree.insert("", "end", iid=str(i), values=r)

        f = self.__dict__[f"{prefix}_footer_accounts"]
        f["konto"].configure(text=footer[0])
        f["fix"].configure(text=footer[1])
        f["fix_pct"].configure(text=footer[2])
        f["var"].configure(text=footer[3])
        f["var_pct"].configure(text=footer[4])

    def set_loans(self, prefix: str, rows: list[tuple[str, str, str, str, str]], *, footer: tuple[str, str, str, str, str]) -> None:
        tree = self.__dict__[f"{prefix}_tree_loans"]
        tree.delete(*tree.get_children())
        for i, r in enumerate(rows):
            tree.insert("", "end", iid=str(i), values=r)

        f = self.__dict__[f"{prefix}_footer_loans"]
        f["kredit"].configure(text=footer[0])
        f["open_before"].configure(text=footer[1])
        f["payment"].configure(text=footer[2])
        f["extra"].configure(text=footer[3])
        f["open_after"].configure(text=footer[4])

    def set_payout_summary(
        self,
        prefix: str,
        rows: list[tuple[str, str, str, str, str, str]],
        *,
        footer: tuple[str, str, str, str, str, str],
    ) -> None:
        tree = self.__dict__[f"{prefix}_tree_summary"]
        tree.delete(*tree.get_children())
        for i, r in enumerate(rows):
            tree.insert("", "end", iid=str(i), values=r)

        f = self.__dict__[f"{prefix}_footer_summary"]
        f["auszahlung"].configure(text=footer[0])
        f["gesamt"].configure(text=footer[1])
        f["sparen"].configure(text=footer[2])
        f["schulden"].configure(text=footer[3])
        f["fixkosten"].configure(text=footer[4])
        f["frei"].configure(text=footer[5])
