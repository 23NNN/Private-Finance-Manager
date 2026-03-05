# src/ui/income/fixed_dialog.py
from __future__ import annotations

import tkinter as tk
from decimal import Decimal, InvalidOperation
from tkinter import ttk
from typing import Callable

from src.ui.common.i18n import tr, trf

SalaryProvider = Callable[[int], Decimal]


def _d(s: str, default: Decimal = Decimal("0.00")) -> Decimal:
    s = (s or "").strip()
    if not s:
        return default
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return default


def _fmt_money(x: Decimal) -> str:
    x = (x or Decimal("0")).quantize(Decimal("0.01"))
    return f"{x:.2f}".replace(".", ",")


class FixedIncomeDialog(tk.Toplevel):
    """Dialog: Fixed salary (month).

    Bugfix:
    - Base amount is automatically taken from the employer rule "Salary" (PayRuleType.SALARY).
    - User only needs to maintain special amount / actual / payout / account / notes.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        title: str,
        employer_values: list[str],
        account_values: list[str],
        payout_values: list[str],
        salary_provider: SalaryProvider,
        initial: dict[str, object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._salary_provider = salary_provider
        self._result: dict[str, object] | None = None
        self._shown = False

        initial = initial or {}

        self._employer = tk.StringVar(value=str(initial.get("employer", employer_values[0] if employer_values else "")))
        self._base = tk.StringVar(value=str(initial.get("base_amount", "0.00")))
        self._special = tk.StringVar(value=str(initial.get("special_amount", "0.00")))
        self._calc = tk.StringVar(value="0,00")
        self._actual = tk.StringVar(value=str(initial.get("actual_amount", "0.00")))
        self._payout = tk.StringVar(value=str(initial.get("payout_timing", payout_values[0] if payout_values else tr("timing.mid"))))
        self._account = tk.StringVar(value=str(initial.get("account", "")))
        self._notes = tk.StringVar(value=str(initial.get("notes", "")))

        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        ttk.Label(root, text=tr("income.fixed.field.employer")).grid(row=0, column=0, sticky="w")
        self._cb_emp = ttk.Combobox(root, state="readonly", width=42, values=employer_values, textvariable=self._employer)
        self._cb_emp.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=2)

        ttk.Label(root, text=tr("income.fixed.field.base_amount")).grid(row=1, column=0, sticky="w")
        self._ent_base = ttk.Entry(root, width=18, textvariable=self._base, state="readonly")
        self._ent_base.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(root, text=tr("income.fixed.field.extra")).grid(row=2, column=0, sticky="w")
        self._ent_special = ttk.Entry(root, width=18, textvariable=self._special)
        self._ent_special.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(root, text=tr("income.fixed.field.calculated")).grid(row=3, column=0, sticky="w")
        ttk.Label(root, textvariable=self._calc).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(root, text=tr("income.fixed.field.actual")).grid(row=4, column=0, sticky="w")
        self._ent_actual = ttk.Entry(root, width=18, textvariable=self._actual)
        self._ent_actual.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(root, text=tr("income.fixed.field.payout")).grid(row=5, column=0, sticky="w")
        self._cb_payout = ttk.Combobox(root, state="readonly", width=12, values=payout_values, textvariable=self._payout)
        self._cb_payout.grid(row=5, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(root, text=tr("income.fixed.field.account")).grid(row=6, column=0, sticky="w")
        self._cb_account = ttk.Combobox(root, state="readonly", width=42, values=account_values, textvariable=self._account)
        self._cb_account.grid(row=6, column=1, sticky="ew", padx=(8, 0), pady=2)

        ttk.Label(root, text=tr("income.fixed.field.notes")).grid(row=7, column=0, sticky="w")
        ttk.Entry(root, width=46, textvariable=self._notes).grid(row=7, column=1, sticky="ew", padx=(8, 0), pady=2)

        self._info = ttk.Label(root, text="")
        self._info.grid(row=8, column=0, columnspan=2, sticky="w", pady=(6, 0))

        btns = ttk.Frame(root)
        btns.grid(row=9, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text=tr("common.cancel"), command=self._cancel).pack(side="right")
        ttk.Button(btns, text=tr("common.save"), command=self._ok).pack(side="right", padx=(0, 8))

        root.columnconfigure(1, weight=1)

        self._cb_emp.bind("<<ComboboxSelected>>", lambda _e: self._refresh_base())
        for v in (self._special, self._actual):
            v.trace_add("write", lambda *_: self._refresh_calc())

        self._refresh_base()
        self._refresh_calc()

    def show(self) -> dict[str, object] | None:
        if not self._shown:
            self._shown = True
            self.wait_window(self)
        return self._result

    def _cancel(self) -> None:
        self._result = None
        self.destroy()

    def _ok(self) -> None:
        _ = _d(self._special.get(), default=Decimal("0.00"))
        _ = _d(self._actual.get(), default=Decimal("0.00"))

        self._result = {
            "employer": self._employer.get().strip(),
            "base_amount": self._base.get().strip(),
            "special_amount": self._special.get().strip(),
            "actual_amount": self._actual.get().strip(),
            "payout_timing": self._payout.get().strip(),
            "account": self._account.get().strip(),
            "notes": self._notes.get().strip(),
        }
        self.destroy()

    def _refresh_base(self) -> None:
        emp = self._employer.get().strip()
        emp_id = None
        if ":" in emp:
            try:
                emp_id = int(emp.split(":", 1)[0])
            except Exception:
                emp_id = None

        if emp_id is None:
            self._base.set("0.00")
            self._info.configure(text=tr("income.fixed.error.no_employer"))
            self._refresh_calc()
            return

        base = self._salary_provider(emp_id)
        self._base.set(_fmt_money(base))
        if base == Decimal("0.00"):
            self._info.configure(text=tr("income.fixed.note.no_rule"))
        else:
            self._info.configure(text="")
        self._refresh_calc()

    def _refresh_calc(self) -> None:
        base = _d(self._base.get(), default=Decimal("0.00"))
        special = _d(self._special.get(), default=Decimal("0.00"))
        total = (base + special).quantize(Decimal("0.01"))
        self._calc.set(_fmt_money(total))
