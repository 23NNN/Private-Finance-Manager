# src/ui/income/hourly_dialog.py
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from tkinter import ttk
from typing import Callable

from src.domain.policies.hourly_pay_policy import PayRule, calc_hourly_income
from src.ui.common.i18n import tr, trf


@dataclass(frozen=True)
class EffectiveRule:
    rule_type: str
    unit: str
    value: Decimal


RulesProvider = Callable[[int], dict[str, tuple[str, Decimal]]]


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


class HourlyIncomeDialog(tk.Toplevel):
    """
    Dialog: Hourly wage (month)

    - compact (2 columns)
    - shows active surcharges/hourly wage automatically
    - live preview of the calculated amount (including special)
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        title: str,
        employer_values: list[str],
        account_values: list[str],
        payout_values: list[str],
        rules_provider: RulesProvider,
        initial: dict[str, object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._rules_provider = rules_provider
        self._result: dict[str, object] | None = None
        self._shown = False

        initial = initial or {}

        self._employer = tk.StringVar(value=str(initial.get("employer", employer_values[0] if employer_values else "")))
        self._hours = tk.StringVar(value=str(initial.get("hours", "0.00")))
        self._night = tk.StringVar(value=str(initial.get("night", "0.00")))
        self._sunday = tk.StringVar(value=str(initial.get("sunday", "0.00")))
        self._holiday = tk.StringVar(value=str(initial.get("holiday", "0.00")))
        self._overtime = tk.StringVar(value=str(initial.get("overtime", "0.00")))
        self._special_amount = tk.StringVar(value=str(initial.get("special_amount", "0.00")))
        self._actual_amount = tk.StringVar(value=str(initial.get("actual_amount", "0.00")))
        self._payout_timing = tk.StringVar(value=str(initial.get("payout_timing", payout_values[0] if payout_values else "")))
        self._account = tk.StringVar(value=str(initial.get("account", "")))
        self._notes = tk.StringVar(value=str(initial.get("notes", "")))

        self._rule_labels: dict[str, ttk.Label] = {}
        self._calc_label: ttk.Label | None = None
        self._warn_label: ttk.Label | None = None
        self._err_label: ttk.Label | None = None

        root = ttk.Frame(self, padding=10)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)

        top = ttk.Frame(root)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text=tr("income.hourly.field.employer")).grid(row=0, column=0, sticky="w", padx=(0, 8))
        cb = ttk.Combobox(top, textvariable=self._employer, values=employer_values, state="readonly", width=40)
        cb.grid(row=0, column=1, sticky="ew")
        top.columnconfigure(1, weight=1)

        rules = ttk.Labelframe(root, text=tr("income.hourly.section.active_rules"), padding=8)
        rules.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        rules.columnconfigure(1, weight=1)

        for i, key in enumerate(["HOURLY_WAGE", "NIGHT", "SUNDAY", "HOLIDAY", "OVERTIME"]):
            label = {
                "HOURLY_WAGE": tr("income.rule_type.hourly_wage"),
                "NIGHT": tr("income.rule_type.night"),
                "SUNDAY": tr("income.rule_type.sunday"),
                "HOLIDAY": tr("income.rule_type.holiday"),
                "OVERTIME": tr("income.rule_type.overtime"),
            }[key]
            ttk.Label(rules, text=label).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=2)
            v = ttk.Label(rules, text="-")
            v.grid(row=i, column=1, sticky="w", pady=2)
            self._rule_labels[key] = v

        self._warn_label = ttk.Label(rules, text="", foreground="red")
        self._warn_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

        grid = ttk.Frame(root)
        grid.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        left = ttk.Labelframe(grid, text=tr("income.hourly.field.hours"), padding=8)
        right = ttk.Labelframe(grid, text=tr("income.hourly.section.amounts"), padding=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew")

        def add_row(frm: ttk.Frame, r: int, text: str, var: tk.StringVar) -> None:
            ttk.Label(frm, text=text).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
            e = ttk.Entry(frm, textvariable=var, width=16)
            e.grid(row=r, column=1, sticky="w", pady=3)
            e.bind("<KeyRelease>", lambda _e: self._recalc_preview())

        add_row(left, 0, tr("income.hourly.field.hours_normal"), self._hours)
        add_row(left, 1, tr("income.hourly.field.night_hours"), self._night)
        add_row(left, 2, tr("income.hourly.field.sunday_hours"), self._sunday)
        add_row(left, 3, tr("income.hourly.field.holiday_hours"), self._holiday)
        add_row(left, 4, tr("income.hourly.field.overtime"), self._overtime)

        add_row(right, 0, tr("income.hourly.field.special_optional"), self._special_amount)
        add_row(right, 1, tr("income.hourly.field.actual_optional"), self._actual_amount)

        ttk.Label(right, text=tr("income.hourly.field.payout")).grid(row=2, column=0, sticky="w", pady=(10, 3), padx=(0, 10))
        ttk.Combobox(right, textvariable=self._payout_timing, values=payout_values, state="readonly", width=16).grid(
            row=2, column=1, sticky="w", pady=(10, 3)
        )

        ttk.Label(right, text=tr("income.hourly.field.account_optional")).grid(row=3, column=0, sticky="w", pady=3, padx=(0, 10))
        ttk.Combobox(right, textvariable=self._account, values=account_values, state="readonly", width=26).grid(
            row=3, column=1, sticky="w", pady=3
        )

        ttk.Label(right, text=tr("income.hourly.field.notes_optional")).grid(row=4, column=0, sticky="w", pady=3, padx=(0, 10))
        ttk.Entry(right, textvariable=self._notes, width=28).grid(row=4, column=1, sticky="w", pady=3)

        preview = ttk.Frame(root)
        preview.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(preview, text=tr("income.hourly.field.calculated")).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self._calc_label = ttk.Label(preview, text=tr("common.amount.zero_eur"))
        self._calc_label.grid(row=0, column=1, sticky="w")

        self._err_label = ttk.Label(root, text="", foreground="red")
        self._err_label.grid(row=4, column=0, sticky="w", pady=(8, 0))

        btns = ttk.Frame(root)
        btns.grid(row=5, column=0, sticky="e", pady=(12, 0))
        ttk.Button(btns, text=tr("common.ok"), command=self._on_ok).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text=tr("common.cancel"), command=self._on_cancel).grid(row=0, column=1)

        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self._on_cancel())
        cb.bind("<<ComboboxSelected>>", lambda _e: self._reload_rules())

        self.geometry("720x520")
        self._reload_rules()

    @staticmethod
    def _parse_id(v: str) -> int:
        return int(str(v).split(":")[0].strip())

    def _get_rules(self) -> dict[str, EffectiveRule]:
        try:
            emp_id = self._parse_id(self._employer.get())
        except Exception:
            return {}

        raw = self._rules_provider(emp_id) if emp_id else {}
        out: dict[str, EffectiveRule] = {}
        for rt, (unit, value) in raw.items():
            out[rt] = EffectiveRule(rule_type=rt, unit=unit, value=value)
        return out

    def _reload_rules(self) -> None:
        self._err_label.config(text="")
        self._warn_label.config(text="")

        rules = self._get_rules()

        base = rules.get("HOURLY_WAGE")
        if base and base.unit == "EUR_PER_HOUR":
            self._rule_labels["HOURLY_WAGE"].config(text=f"{_fmt_money(base.value)} {tr('income.hourly.unit.eur_per_hour')}")
        else:
            self._rule_labels["HOURLY_WAGE"].config(text="-")
            self._warn_label.config(text=tr("income.hourly.note.no_rate"))

        def fmt_rule(r: EffectiveRule | None) -> str:
            if not r:
                return "-"
            if r.unit == "EUR_PER_HOUR":
                return f"+{_fmt_money(r.value)} {tr('income.hourly.unit.eur_per_hour')}"
            if r.unit == "MULTIPLIER":
                mult = r.value
                try:
                    pct = (mult - Decimal("1.0")) * Decimal("100")
                    return f"x{mult} ({pct:.0f}%)"
                except Exception:
                    return f"x{mult}"
            return f"{r.value} ({r.unit})"

        for k in ["NIGHT", "SUNDAY", "HOLIDAY", "OVERTIME"]:
            self._rule_labels[k].config(text=fmt_rule(rules.get(k)))

        self._recalc_preview()

    def _recalc_preview(self) -> None:
        if not self._calc_label:
            return

        rules = self._get_rules()
        pay_rules = [PayRule(rule_type=r.rule_type, unit=r.unit, value=r.value) for r in rules.values()]

        hours = {
            "hours_normal": _d(self._hours.get()),
            "night": _d(self._night.get()),
            "sunday": _d(self._sunday.get()),
            "holiday": _d(self._holiday.get()),
            "overtime": _d(self._overtime.get()),
        }
        special = _d(self._special_amount.get())

        amount = calc_hourly_income(pay_rules, hours) + special
        self._calc_label.config(text=f"{_fmt_money(amount)} EUR")

    def _validate(self) -> bool:
        if not self._employer.get().strip():
            self._err_label.config(text=tr("income.hourly.error.no_employer"))
            return False

        numeric = [
            (tr("income.hourly.field.hours_normal"), self._hours.get()),
            (tr("income.hourly.field.night_hours"), self._night.get()),
            (tr("income.hourly.field.sunday_hours"), self._sunday.get()),
            (tr("income.hourly.field.holiday_hours"), self._holiday.get()),
            (tr("income.hourly.field.overtime"), self._overtime.get()),
            (tr("income.col.special"), self._special_amount.get()),
            (tr("income.col.actual"), self._actual_amount.get()),
        ]
        for label, val in numeric:
            s = (val or "").strip()
            if not s:
                continue
            s2 = s.replace(",", ".")
            try:
                Decimal(s2)
            except InvalidOperation:
                self._err_label.config(text=trf("income.hourly.error.invalid_number", field=label))
                return False

        self._err_label.config(text="")
        return True

    def _on_ok(self) -> None:
        if not self._validate():
            return

        self._result = {
            "employer": self._employer.get().strip(),
            "hours": self._hours.get().strip(),
            "night": self._night.get().strip(),
            "sunday": self._sunday.get().strip(),
            "holiday": self._holiday.get().strip(),
            "overtime": self._overtime.get().strip(),
            "special_amount": self._special_amount.get().strip(),
            "actual_amount": self._actual_amount.get().strip(),
            "payout_timing": self._payout_timing.get().strip(),
            "account": self._account.get().strip(),
            "notes": self._notes.get().strip(),
        }
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = None
        self.destroy()

    def show(self) -> dict[str, object] | None:
        if not self._shown:
            self._shown = True
            self.wait_window(self)
        return self._result
