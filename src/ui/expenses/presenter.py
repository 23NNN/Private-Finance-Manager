# src/ui/expenses/presenter.py
from __future__ import annotations

import logging
import tkinter as tk
import traceback
from datetime import date
from decimal import Decimal
from tkinter import messagebox

from src.application.dto.expenses import ExpenseRecurringDTO, ExpenseVariableDTO
from src.application.dto.loans import LoanDTO, LoanEventDTO
from src.application.services.expense_service import ExpenseService
from src.application.services.loan_service import LoanService
from src.application.services.reference_data_service import ReferenceDataService
from src.application.validators.parsers import parse_date
from src.config.settings import get_settings
from src.domain.models.period import Period
from src.ui.common.category_manager import CategoryManagerDialog
from src.ui.common.dialogs import FieldSpec, FormDialog
from src.ui.common.error_dialog import show_error, show_warning
from src.ui.common.i18n import tr
from src.ui.common.validation import ui_decimal, ui_int

logger = logging.getLogger(__name__)


RECURRING_STATUS_KEYS: dict[str, str] = {"ACTIVE": "status.active", "INACTIVE": "status.inactive"}
VARIABLE_STATUS_KEYS: dict[str, str] = {"OPEN": "status.open", "PAID": "status.paid", "CANCELLED": "status.cancelled"}
LOAN_STATUS_KEYS: dict[str, str] = {"ACTIVE": "status.active", "CLOSED": "status.closed"}

PAY_BUCKET_KEYS: dict[str, str] = {"BEGINNING": "timing.beginning", "MID": "timing.mid", "NONE": "timing.none"}

ALLOCATION_OVERRIDE_KEYS: dict[str, str] = {
    "": "",
    "CASHFLOW": "allocation.cashflow",
    "ALLOCATE_MONTHLY": "allocation.allocate_monthly",
    "ALLOCATE_QUARTERLY": "allocation.allocate_quarterly",
}

LOAN_EVENT_KEYS: dict[str, str] = {
    "PAYMENT": "loan_event.payment",
    "EXTRA_PAYMENT": "loan_event.extra_payment",
    "RATE_CHANGE": "loan_event.rate_change",
    "INTEREST_CHANGE": "loan_event.interest_change",
    "NOTE": "loan_event.note",
}


def _bind_row_double_click(tree, fn) -> None:
    """Bind double-click on a row (not on a header).

    - add="+" to keep global bindings (e.g. sort reset via header double click)
    - ignore header region to prevent unintended edit
    """

    def _h(e):
        try:
            if tree.identify_region(e.x, e.y) == "heading":
                return
        except Exception:
            return
        fn()

    tree.bind("<Double-1>", _h, add="+")


def _v(x) -> str:
    return getattr(x, "value", str(x))


def _m(x: Decimal | None) -> str:
    try:
        return f"{Decimal(x or 0):.2f}"
    except Exception:
        return "0.00"


def _code_to_ui(code: str | None, mapping: dict[str, str]) -> str:
    if not code:
        return ""
    k = mapping.get(str(code), "")
    if not k:
        return str(code)
    return tr(k)


def _ui_to_code(ui: str | None, mapping: dict[str, str], *, default: str | None = None) -> str | None:
    ui = (ui or "").strip()
    if not ui:
        return default
    for code, key in mapping.items():
        if key and tr(key) == ui:
            return code
    return default


class ExpensesPresenter:
    """
    UX improvements:
    - Loan events auto-load when a loan is selected.
    - Selection (loan + event) is preserved on refresh when possible.
    - Double-click workflows.
    - Filters are applied consistently.
    - Year view:
      - Variable expenses: show all entries of the year (month is visible in name)
      - Loans: aggregated year values (payment/extra summed)
      - Events: in year mode only show events of that year
    """

    def __init__(
        self,
        view,
        expense_service: ExpenseService,
        loan_service: LoanService,
        ref_service: ReferenceDataService,
    ):
        self._view = view
        self._exp = expense_service
        self._loan = loan_service
        self._ref = ref_service
        self._settings = get_settings()

        self._accounts = []
        self._cats = []
        self._loans: list[LoanDTO] = []

        self._var_by_id: dict[int, ExpenseVariableDTO] = {}
        self._rec_by_id: dict[int, ExpenseRecurringDTO] = {}

        self._view.bind_refresh(self.refresh)
        if hasattr(self._view, "bind_filter_change"):
            self._view.bind_filter_change(self.refresh)

        # Recurring
        self._view.add_rec_btn.configure(command=self.add_recurring)
        self._view.edit_rec_btn.configure(command=self.edit_recurring)
        self._view.delete_rec_btn.configure(command=self.soft_delete_recurring)
        self._view.undo_rec_btn.configure(command=self.undo_recurring)

        # Variable
        self._view.add_var_btn.configure(command=self.add_variable)
        self._view.edit_var_btn.configure(command=self.edit_variable)
        self._view.pay_var_btn.configure(command=self.pay_variable)
        self._view.delete_var_btn.configure(command=self.soft_delete_variable)
        self._view.undo_var_btn.configure(command=self.undo_variable)

        # Loans
        self._view.add_loan_btn.configure(command=self.add_loan)
        self._view.add_loan_event_btn.configure(command=self.add_loan_event)
        self._view.show_loan_events_btn.configure(command=self.show_events_for_selected)
        self._view.edit_loan_event_btn.configure(command=self.edit_selected_event)
        self._view.delete_event_btn.configure(command=self.delete_selected_event)
        self._view.close_loan_btn.configure(command=self.close_selected_loan)
        self._view.reopen_loan_btn.configure(command=self.reopen_selected_loan)
        self._view.delete_loan_btn.configure(command=self.delete_selected_loan)

        if hasattr(self._view, "manage_categories_btn"):
            self._view.manage_categories_btn.configure(command=self.manage_categories)

        # UI events
        _bind_row_double_click(self._view.rec_tree, lambda: self.edit_recurring())
        _bind_row_double_click(self._view.var_tree, lambda: self.edit_variable())
        _bind_row_double_click(self._view.loan_tree, lambda: self.add_loan_event())
        _bind_row_double_click(self._view.loan_events_tree, lambda: self.edit_selected_event())

        self._view.rec_tree.bind("<Delete>", lambda _e: self.soft_delete_recurring())
        self._view.var_tree.bind("<Delete>", lambda _e: self.soft_delete_variable())
        self._view.var_tree.bind("<Button-3>", self._show_var_context_menu, add="+")
        self._view.loan_events_tree.bind("<Delete>", lambda _e: self.delete_selected_event())

        # UX: load events on loan select
        self._view.loan_tree.bind("<<TreeviewSelect>>", lambda _e: self.show_events_for_selected())

        self.refresh()

    # -------------------- helpers --------------------
    def _root(self):
        return self._view.winfo_toplevel()

    def _err(self, title: str, msg: str) -> None:
        show_error(
            self._root(),
            title,
            msg,
            details=traceback.format_exc(),
            db_path=self._settings.db_path(),
            log_path=self._settings.log_path(),
        )

    def _warn(self, title: str, msg: str) -> None:
        show_warning(
            self._root(),
            title,
            msg,
            db_path=self._settings.db_path(),
            log_path=self._settings.log_path(),
        )

    def _is_year_view(self) -> bool:
        try:
            return bool(self._view.is_year_view())
        except Exception:
            return False

    @staticmethod
    def _selected_id(tree) -> int | None:
        sel = tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def _fmt_acc(self, acc_id: int | None) -> str:
        if not acc_id:
            return ""
        for a in self._accounts:
            if a.id == acc_id:
                return f"{a.id}:{a.label}"
        return f"{acc_id}"

    def _acc_label(self, acc_id: int | None) -> str:
        if not acc_id:
            return ""
        for a in self._accounts:
            if a.id == acc_id:
                return a.label
        return str(acc_id)

    def _cat_name(self, cid: int) -> str:
        for c in self._cats:
            if c.id == cid:
                return c.name
        return f"#{cid}"

    def _all_label(self) -> str:
        return tr("common.all")

    def _parse_id_choice(self, s: str) -> int | None:
        s = (s or "").strip()
        if not s or s == self._all_label():
            return None
        try:
            return int(s.split(":")[0])
        except Exception:
            return None

    def _parse_timing_ui(self, s: str) -> str | None:
        s = (s or "").strip()
        if not s or s == self._all_label():
            return None
        if s == tr(PAY_BUCKET_KEYS["BEGINNING"]):
            return "BEGINNING"
        if s == tr(PAY_BUCKET_KEYS["MID"]):
            return "MID"
        return None

    def _timing_to_ui(self, t: str | None) -> str:
        if not t:
            return ""
        return _code_to_ui(str(t), PAY_BUCKET_KEYS)

    def _alloc_override_to_ui(self, code: str | None) -> str:
        code = str(code or "")
        if not code:
            return ""
        return _code_to_ui(code, ALLOCATION_OVERRIDE_KEYS)

    def _alloc_override_from_ui(self, ui: str | None) -> str:
        ui = (ui or "").strip()
        if not ui:
            return ""
        code = _ui_to_code(ui, ALLOCATION_OVERRIDE_KEYS, default="")
        return str(code or "")

    def _loan_event_to_ui(self, code: str | None) -> str:
        return _code_to_ui(str(code or ""), LOAN_EVENT_KEYS)

    # -------------------- refresh --------------------
    def refresh(self) -> None:
        """Refresh all tables and re-apply filters."""
        sel_loan_before = self._selected_id(self._view.loan_tree)
        sel_event_before = self._selected_id(self._view.loan_events_tree)

        try:
            self._accounts = self._ref.list_accounts()
            self._cats = self._ref.list_categories()
            self._loans = self._loan.list_loans()

            accounts_ui = [f"{a.id}:{a.label}" for a in self._accounts]
            rec_cats_ui = [f"{c.id}:{c.name}" for c in self._cats if _v(c.group) == "FIX"]
            var_cats_ui = [f"{c.id}:{c.name}" for c in self._cats if _v(c.group) == "VARIABLE"]

            if hasattr(self._view, "set_filter_options"):
                self._view.set_filter_options(accounts=accounts_ui, rec_categories=rec_cats_ui, var_categories=var_cats_ui)

            acc_label = {a.id: a.label for a in self._accounts}
            cat_name = {c.id: c.name for c in self._cats}

            period = self._view.get_period()
            filters = self._view.get_filters() if hasattr(self._view, "get_filters") else {}

            # -------------------- Recurring --------------------
            rec = self._exp.list_recurring()
            self._rec_by_id = {int(r.id): r for r in rec if getattr(r, "id", None) is not None}

            f_rec = (filters.get("recurring") or {})
            rec_status_ui = (f_rec.get("status") or self._all_label()).strip()
            rec_acc_id = self._parse_id_choice(f_rec.get("account") or "")
            rec_cat_id = self._parse_id_choice(f_rec.get("category") or "")

            self._view.rec_tree.delete(*self._view.rec_tree.get_children())
            rec_count = 0
            rec_total = Decimal(0)
            for r in rec:
                if rec_status_ui != self._all_label():
                    want = _ui_to_code(rec_status_ui, RECURRING_STATUS_KEYS, default=None)
                    if want and _v(r.status) != want:
                        continue
                if rec_acc_id is not None and getattr(r, "account_id", None) != rec_acc_id:
                    continue
                if rec_cat_id is not None and getattr(r, "category_id", None) != rec_cat_id:
                    continue

                status = _code_to_ui(_v(r.status), RECURRING_STATUS_KEYS)
                override = _v(r.allocation_override) if getattr(r, "allocation_override", None) else ""
                override_disp = self._alloc_override_to_ui(override)

                self._view.rec_tree.insert(
                    "",
                    "end",
                    iid=str(r.id),
                    values=(
                        r.name,
                        cat_name.get(r.category_id, f"#{r.category_id}"),
                        _m(r.amount),
                        str(r.frequency_months),
                        str(r.anchor_month),
                        str(r.due_day),
                        status,
                        acc_label.get(r.account_id, ""),
                        override_disp,
                    ),
                )
                rec_count += 1
                try:
                    rec_total += Decimal(r.amount or 0)
                except Exception:
                    pass

            if hasattr(self._view, "rec_sum_label"):
                self._view.rec_sum_label.config(
                    text=f"{rec_count} {tr('common.entries')}  |  {tr('common.total')}: {rec_total:.2f} €"
                )

            # -------------------- Variable --------------------
            f_var = (filters.get("variable") or {})
            var_status_ui = (f_var.get("status") or self._all_label()).strip()
            var_acc_id = self._parse_id_choice(f_var.get("account") or "")
            var_cat_id = self._parse_id_choice(f_var.get("category") or "")

            if self._is_year_view():
                var = self._exp.list_variable_year(period.year)
            else:
                var = self._exp.list_variable(period)

            self._var_by_id = {int(v.id): v for v in var if getattr(v, "id", None) is not None}

            self._view.var_tree.delete(*self._view.var_tree.get_children())
            var_count = 0
            var_total = Decimal(0)
            for v in var:
                if var_status_ui != self._all_label():
                    want = _ui_to_code(var_status_ui, VARIABLE_STATUS_KEYS, default=None)
                    if want and _v(v.status) != want:
                        continue
                if var_acc_id is not None and getattr(v, "account_id", None) != var_acc_id:
                    continue
                if var_cat_id is not None and getattr(v, "category_id", None) != var_cat_id:
                    continue

                status = _code_to_ui(_v(v.status), VARIABLE_STATUS_KEYS)

                name_disp = v.name
                if self._is_year_view():
                    try:
                        name_disp = f"{int(v.month):02d} - {v.name}"
                    except Exception:
                        name_disp = v.name

                self._view.var_tree.insert(
                    "",
                    "end",
                    iid=str(v.id),
                    values=(
                        name_disp,
                        cat_name.get(v.category_id, f"#{v.category_id}"),
                        _m(v.amount),
                        status,
                        acc_label.get(v.account_id, "") if getattr(v, "account_id", None) else "",
                    ),
                )
                var_count += 1
                try:
                    var_total += Decimal(v.amount or 0)
                except Exception:
                    pass

            if hasattr(self._view, "var_sum_label"):
                self._view.var_sum_label.config(
                    text=f"{var_count} {tr('common.entries')}  |  {tr('common.total')}: {var_total:.2f} €"
                )

            # -------------------- Loans --------------------
            f_loan = (filters.get("loan") or {})
            loan_status_ui = (f_loan.get("status") or self._all_label()).strip()
            loan_acc_id = self._parse_id_choice(f_loan.get("account") or "")
            loan_timing = self._parse_timing_ui(f_loan.get("timing") or "")
            only_relevant = bool(f_loan.get("only_relevant", True))

            self._view.loan_tree.delete(*self._view.loan_tree.get_children())
            inserted_loan_ids: set[int] = set()

            if self._is_year_view():
                y = period.year
                for l in self._loans:
                    if loan_status_ui != self._all_label():
                        want = _ui_to_code(loan_status_ui, LOAN_STATUS_KEYS, default=None)
                        if want and _v(l.status) != want:
                            continue

                    if only_relevant and _v(l.status) == "CLOSED":
                        try:
                            ev = self._loan.list_events(l.id)
                            if not any(getattr(e, "event_date", None) and e.event_date.year == y for e in ev):
                                continue
                        except Exception:
                            continue

                    eff_acc_ids: set[int | None] = set()
                    eff_timings: set[str | None] = set()
                    for m in range(1, 13):
                        try:
                            eff = self._loan.get_effective_settings(l.id, Period(y, m))
                            eff_acc_ids.add(
                                int(eff.get("account_id")) if eff.get("account_id") is not None else getattr(l, "account_id", None)
                            )
                            eff_timings.add(str(eff.get("payment_timing") or getattr(l, "payment_timing", "MID")))
                        except Exception:
                            eff_acc_ids.add(getattr(l, "account_id", None))
                            eff_timings.add(getattr(l, "payment_timing", "MID"))

                    eff_acc_id = next(iter(eff_acc_ids)) if len(eff_acc_ids) == 1 else None
                    eff_timing = next(iter(eff_timings)) if len(eff_timings) == 1 else None

                    if loan_acc_id is not None:
                        if len(eff_acc_ids) == 1 and eff_acc_id != loan_acc_id:
                            continue
                        if len(eff_acc_ids) > 1:
                            continue
                    if loan_timing is not None:
                        if len(eff_timings) == 1 and eff_timing != loan_timing:
                            continue
                        if len(eff_timings) > 1:
                            continue

                    st_jan = self._loan.get_month_status(l.id, Period(y, 1))
                    st_dez = self._loan.get_month_status(l.id, Period(y, 12))

                    pay_sum = Decimal("0")
                    extra_sum = Decimal("0")
                    for m in range(1, 13):
                        st_m = self._loan.get_month_status(l.id, Period(y, m))
                        pay_sum += Decimal(st_m.get("payment") or 0)
                        extra_sum += Decimal(st_m.get("extra") or 0)

                    status = _code_to_ui(_v(l.status), LOAN_STATUS_KEYS)
                    dash = tr("common.dash")
                    self._view.loan_tree.insert(
                        "",
                        "end",
                        iid=str(l.id),
                        values=(
                            l.name,
                            status,
                            dash if len(eff_acc_ids) > 1 else self._acc_label(eff_acc_id),
                            dash if len(eff_timings) > 1 else self._timing_to_ui(eff_timing),
                            _m(Decimal(st_jan.get("open_before") or 0)),
                            _m(pay_sum),
                            _m(extra_sum),
                            _m(Decimal(st_dez.get("open_after") or 0)),
                        ),
                    )
                    inserted_loan_ids.add(int(l.id))

            else:
                for l in self._loans:
                    if loan_status_ui != self._all_label():
                        want = _ui_to_code(loan_status_ui, LOAN_STATUS_KEYS, default=None)
                        if want and _v(l.status) != want:
                            continue

                    if only_relevant and _v(l.status) == "CLOSED":
                        try:
                            if hasattr(self._loan, "has_event_in_period") and not self._loan.has_event_in_period(l.id, period):
                                continue
                        except Exception:
                            pass

                    eff: dict = {}
                    try:
                        if hasattr(self._loan, "get_effective_settings"):
                            eff = self._loan.get_effective_settings(l.id, period)
                    except Exception:
                        eff = {}

                    eff_acc_id = int(eff.get("account_id")) if eff.get("account_id") is not None else getattr(l, "account_id", None)
                    eff_timing = str(eff.get("payment_timing") or getattr(l, "payment_timing", "MID"))

                    if loan_acc_id is not None and eff_acc_id != loan_acc_id:
                        continue
                    if loan_timing is not None and eff_timing != loan_timing:
                        continue

                    st = self._loan.get_month_status(l.id, period)
                    status = _code_to_ui(_v(l.status), LOAN_STATUS_KEYS)

                    self._view.loan_tree.insert(
                        "",
                        "end",
                        iid=str(l.id),
                        values=(
                            l.name,
                            status,
                            self._acc_label(eff_acc_id),
                            self._timing_to_ui(eff_timing),
                            _m(st.get("open_before")),
                            _m(st.get("payment")),
                            _m(st.get("extra")),
                            _m(st.get("open_after")),
                        ),
                    )
                    inserted_loan_ids.add(int(l.id))

            # restore selection
            if sel_loan_before and sel_loan_before in inserted_loan_ids:
                self._view.loan_tree.selection_set(str(sel_loan_before))
                self._view.loan_tree.focus(str(sel_loan_before))
                self._view.loan_tree.see(str(sel_loan_before))
                self.show_events_for_selected(prefer_event_id=sel_event_before)
            else:
                self._view.loan_events_tree.delete(*self._view.loan_events_tree.get_children())

        except Exception:
            logger.exception("Expenses refresh failed.")
            self._err(tr("common.error"), tr("expenses.error.refresh_failed"))

    # -------------------- categories --------------------
    def manage_categories(self) -> None:
        try:
            CategoryManagerDialog(self._view, self._ref)
            self.refresh()
        except Exception:
            logger.exception("manage_categories failed.")
            self._err(tr("common.error"), tr("expenses.error.categories_open_failed"))

    # -------------------- status flips: recurring --------------------
    def soft_delete_recurring(self) -> None:
        rid = self._selected_id(self._view.rec_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("expenses.warn.select_recurring"))
            return
        if not messagebox.askyesno(tr("common.confirm"), tr("expenses.confirm.deactivate_recurring")):
            return
        try:
            if hasattr(self._exp, "set_recurring_status"):
                self._exp.set_recurring_status(rid, "INACTIVE")
            else:
                self._exp.soft_delete_recurring(rid)
            self.refresh()
        except Exception:
            logger.exception("soft_delete_recurring failed.")
            self._err(tr("common.error"), tr("expenses.error.deactivate_failed"))

    def undo_recurring(self) -> None:
        rid = self._selected_id(self._view.rec_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("expenses.warn.select_recurring"))
            return
        try:
            if hasattr(self._exp, "set_recurring_status"):
                self._exp.set_recurring_status(rid, "ACTIVE")
            else:
                self._exp.undo_recurring(rid)
            self.refresh()
        except Exception:
            logger.exception("undo_recurring failed.")
            self._err(tr("common.error"), tr("expenses.error.reactivate_failed"))

    # -------------------- status flips: variable --------------------
    def pay_variable(self) -> None:
        ids = [int(i) for i in self._view.var_tree.selection() if i]
        if not ids:
            self._warn(tr("common.notice"), tr("expenses.warn.select_variable"))
            return
        try:
            for vid in ids:
                self._exp.set_variable_status(vid, "PAID")
            self.refresh()
        except Exception:
            logger.exception("pay_variable failed.")
            self._err(tr("common.error"), tr("expenses.error.pay_failed"))

    def soft_delete_variable(self) -> None:
        vid = self._selected_id(self._view.var_tree)
        if not vid:
            self._warn(tr("common.notice"), tr("expenses.warn.select_variable"))
            return
        if not messagebox.askyesno(tr("common.confirm"), tr("expenses.confirm.cancel_variable")):
            return
        try:
            if hasattr(self._exp, "set_variable_status"):
                self._exp.set_variable_status(vid, "CANCELLED")
            else:
                self._exp.soft_delete_variable(vid)
            self.refresh()
        except Exception:
            logger.exception("soft_delete_variable failed.")
            self._err(tr("common.error"), tr("expenses.error.cancel_failed"))

    def undo_variable(self) -> None:
        vid = self._selected_id(self._view.var_tree)
        if not vid:
            self._warn(tr("common.notice"), tr("expenses.warn.select_variable"))
            return
        try:
            if hasattr(self._exp, "set_variable_status"):
                self._exp.set_variable_status(vid, "OPEN")
            else:
                self._exp.undo_variable(vid)
            self.refresh()
        except Exception:
            logger.exception("undo_variable failed.")
            self._err(tr("common.error"), tr("expenses.error.reopen_failed"))

    def _show_var_context_menu(self, event) -> None:
        item = self._view.var_tree.identify_row(event.y)
        if not item:
            return
        self._view.var_tree.selection_set(item)
        menu = tk.Menu(self._root(), tearoff=False)
        menu.add_command(label=tr("expenses.variable.ctx.move"), command=self._move_variable_dialog)
        menu.tk_popup(event.x_root, event.y_root)

    def _move_variable_dialog(self) -> None:
        vid = self._selected_id(self._view.var_tree)
        if not vid:
            return
        dto = self._var_by_id.get(vid)
        if not dto:
            return

        fields = [
            FieldSpec("year", tr("expenses.variable.move.year"), "entry", required=True, validator=ui_int, width=8),
            FieldSpec(
                "month",
                tr("expenses.variable.move.month"),
                "combo",
                required=True,
                values=[str(m) for m in range(1, 13)],
                width=8,
            ),
        ]
        initial = {"year": str(dto.year), "month": str(dto.month)}
        dlg = FormDialog(self._root(), tr("expenses.variable.move.title"), fields, initial=initial)
        if not dlg.result:
            return
        try:
            new_year = int(dlg.result["year"])
            new_month = int(dlg.result["month"])
            self._exp.move_variable(vid, new_year, new_month)
            self.refresh()
        except Exception:
            logger.exception("move_variable failed.")
            self._err(tr("common.error"), tr("expenses.error.move_failed"))

    # -------------------- loan events --------------------
    def show_events_for_selected(self, prefer_event_id: int | None = None) -> None:
        loan_id = self._selected_id(self._view.loan_tree)
        if not loan_id:
            self._view.loan_events_tree.delete(*self._view.loan_events_tree.get_children())
            return

        current_selected_event = prefer_event_id or self._selected_id(self._view.loan_events_tree)

        try:
            period = self._view.get_period()
            year = period.year
            events = self._loan.list_events(loan_id)

            if self._is_year_view():
                events = [e for e in events if getattr(e, "event_date", None) and e.event_date.year == year]

            self._view.loan_events_tree.delete(*self._view.loan_events_tree.get_children())

            inserted = []
            for e in events:
                etype = self._loan_event_to_ui(_v(e.event_type))
                oacc = self._acc_label(getattr(e, "override_account_id", None))
                otim = self._timing_to_ui(getattr(e, "override_payment_timing", None))

                eid = int(e.id) if getattr(e, "id", None) is not None else None
                if eid is None:
                    continue

                self._view.loan_events_tree.insert(
                    "",
                    "end",
                    iid=str(eid),
                    values=(
                        str(e.event_date),
                        etype,
                        _m(getattr(e, "amount", None)),
                        oacc,
                        otim,
                        (e.notes or ""),
                    ),
                )
                inserted.append(eid)

            if current_selected_event and current_selected_event in inserted:
                self._view.loan_events_tree.selection_set(str(current_selected_event))
                self._view.loan_events_tree.focus(str(current_selected_event))
                self._view.loan_events_tree.see(str(current_selected_event))
            elif inserted:
                self._view.loan_events_tree.selection_set(str(inserted[0]))
                self._view.loan_events_tree.focus(str(inserted[0]))

        except Exception:
            logger.exception("show_events_for_selected failed.")
            self._err(tr("common.error"), tr("expenses.error.load_events_failed"))

    def delete_selected_event(self) -> None:
        eid = self._selected_id(self._view.loan_events_tree)
        if not eid:
            self._warn(tr("common.notice"), tr("expenses.warn.select_event"))
            return
        if not messagebox.askyesno(tr("common.irreversible_delete"), tr("expenses.confirm.delete_event")):
            return
        try:
            self._loan.delete_event(eid)
            self.refresh()
        except Exception:
            logger.exception("delete_selected_event failed.")
            self._err(tr("common.error"), tr("expenses.error.delete_event_failed"))

    def edit_selected_event(self) -> None:
        eid = self._selected_id(self._view.loan_events_tree)
        if not eid:
            self._warn(tr("common.notice"), tr("expenses.warn.select_event"))
            return
        loan_id = self._selected_id(self._view.loan_tree)
        if not loan_id:
            self._warn(tr("common.notice"), tr("expenses.warn.select_loan"))
            return
        self._open_loan_event_dialog(loan_id, eid)

    # -------------------- dialogs: recurring --------------------
    def add_recurring(self) -> None:
        self._open_rec_dialog(None)

    def edit_recurring(self) -> None:
        rid = self._selected_id(self._view.rec_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("expenses.warn.select_recurring"))
            return
        self._open_rec_dialog(rid)

    def _open_rec_dialog(self, rid: int | None) -> None:
        acc_vals = [""] + [f"{a.id}:{a.label}" for a in self._accounts]
        cat_vals = [f"{c.id}:{c.name}" for c in self._cats if _v(c.group) == "FIX"] or [
            f"{c.id}:{c.name}" for c in self._cats
        ]

        initial = {
            "name": "",
            "category": (cat_vals[0] if cat_vals else ""),
            "amount": "0.00",
            "freq": "1",
            "due": "1",
            "anchor_month": "1",
            "status_ui": _code_to_ui("ACTIVE", RECURRING_STATUS_KEYS),
            "account": (acc_vals[1] if len(acc_vals) > 1 else ""),
            "pay_bucket_ui": _code_to_ui("NONE", PAY_BUCKET_KEYS),
            "override_ui": "",
            "notes": "",
        }

        existing: ExpenseRecurringDTO | None = None
        if rid and rid in self._rec_by_id:
            existing = self._rec_by_id[rid]
            initial.update(
                {
                    "name": existing.name,
                    "category": f"{existing.category_id}:{self._cat_name(existing.category_id)}",
                    "amount": str(existing.amount),
                    "freq": str(existing.frequency_months),
                    "due": str(existing.due_day),
                    "anchor_month": str(existing.anchor_month),
                    "status_ui": _code_to_ui(_v(existing.status), RECURRING_STATUS_KEYS),
                    "account": self._fmt_acc(getattr(existing, "account_id", None)),
                    "pay_bucket_ui": _code_to_ui(_v(existing.pay_bucket), PAY_BUCKET_KEYS),
                    "override_ui": self._alloc_override_to_ui(
                        _v(existing.allocation_override) if getattr(existing, "allocation_override", None) else ""
                    ),
                    "notes": (existing.notes or ""),
                }
            )

        fields = [
            FieldSpec("name", tr("expenses.recurring.field.name"), "entry", required=True, width=40),
            FieldSpec("category", tr("expenses.recurring.field.category"), "combo", required=True, values=cat_vals, width=40),
            FieldSpec("amount", tr("expenses.recurring.field.amount"), "entry", required=True),
            FieldSpec("freq", tr("expenses.recurring.field.frequency_months"), "spin", required=True, from_=1, to=120),
            FieldSpec("due", tr("expenses.recurring.field.due_day"), "spin", required=True, from_=1, to=31),
            FieldSpec("anchor_month", tr("expenses.recurring.field.anchor_month"), "spin", required=True, from_=1, to=12),
            FieldSpec(
                "status_ui",
                tr("expenses.recurring.field.status"),
                "combo",
                required=True,
                values=[_code_to_ui(k, RECURRING_STATUS_KEYS) for k in RECURRING_STATUS_KEYS.keys()],
            ),
            FieldSpec("account", tr("expenses.recurring.field.account"), "combo", required=False, values=acc_vals, width=40),
            FieldSpec(
                "pay_bucket_ui",
                tr("expenses.recurring.field.pay_bucket"),
                "combo",
                required=True,
                values=[_code_to_ui(k, PAY_BUCKET_KEYS) for k in PAY_BUCKET_KEYS.keys()],
            ),
            FieldSpec(
                "override_ui",
                tr("expenses.recurring.field.override"),
                "combo",
                required=False,
                values=[""] + [tr(k) for c, k in ALLOCATION_OVERRIDE_KEYS.items() if c and k],
            ),
            FieldSpec("notes", tr("expenses.recurring.field.notes"), "text", required=False, width=40),
        ]

        dlg = FormDialog(self._root(), tr("expenses.recurring.dialog.title"), fields, initial=initial)
        if not dlg.result:
            return

        try:
            cat_id = self._parse_id_choice(dlg.result["category"]) or 0
            acc_id = self._parse_id_choice(dlg.result.get("account") or "") or None
            status = _ui_to_code(dlg.result["status_ui"], RECURRING_STATUS_KEYS, default="ACTIVE") or "ACTIVE"
            pay_bucket = _ui_to_code(dlg.result["pay_bucket_ui"], PAY_BUCKET_KEYS, default="NONE") or "NONE"
            override = self._alloc_override_from_ui(dlg.result.get("override_ui") or "")

            dto = ExpenseRecurringDTO(
                id=rid,
                name=str(dlg.result["name"]).strip(),
                category_id=int(cat_id),
                amount=ui_decimal(str(dlg.result["amount"])),
                frequency_months=ui_int(str(dlg.result["freq"]), min_v=1, max_v=120),
                due_day=ui_int(str(dlg.result["due"]), min_v=1, max_v=31),
                anchor_month=ui_int(str(dlg.result["anchor_month"]), min_v=1, max_v=12),
                status=status,
                account_id=acc_id,
                pay_bucket=pay_bucket,
                notes=str(dlg.result.get("notes") or "").strip() or None,
                allocation_override=override or None,
            )
            self._exp.upsert_recurring(dto)
            self.refresh()
        except Exception:
            logger.exception("_open_rec_dialog failed.")
            self._err(tr("common.error"), tr("expenses.error.save_recurring_failed"))

    # -------------------- dialogs: variable --------------------
    def add_variable(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("expenses.warn.create_variable_in_month_view"))
            return
        self._open_var_dialog(None)

    def edit_variable(self) -> None:
        vid = self._selected_id(self._view.var_tree)
        if not vid:
            self._warn(tr("common.notice"), tr("expenses.warn.select_variable"))
            return
        self._open_var_dialog(vid)

    def _open_var_dialog(self, vid: int | None) -> None:
        period = self._view.get_period()
        acc_vals = [""] + [f"{a.id}:{a.label}" for a in self._accounts]
        cat_vals = [f"{c.id}:{c.name}" for c in self._cats if _v(c.group) == "VARIABLE"] or [
            f"{c.id}:{c.name}" for c in self._cats
        ]

        initial = {
            "name": "",
            "category": (cat_vals[0] if cat_vals else ""),
            "amount": "0.00",
            "status_ui": _code_to_ui("OPEN", VARIABLE_STATUS_KEYS),
            "account": (acc_vals[1] if len(acc_vals) > 1 else ""),
            "pay_bucket_ui": _code_to_ui("NONE", PAY_BUCKET_KEYS),
            "notes": "",
        }

        existing: ExpenseVariableDTO | None = None
        if vid and vid in self._var_by_id:
            existing = self._var_by_id[vid]
            initial.update(
                {
                    "name": existing.name,
                    "category": f"{existing.category_id}:{self._cat_name(existing.category_id)}",
                    "amount": str(existing.amount),
                    "status_ui": _code_to_ui(_v(existing.status), VARIABLE_STATUS_KEYS),
                    "account": self._fmt_acc(getattr(existing, "account_id", None)),
                    "pay_bucket_ui": _code_to_ui(_v(existing.pay_bucket), PAY_BUCKET_KEYS),
                    "notes": (existing.notes or ""),
                }
            )

        fields = [
            FieldSpec("name", tr("expenses.variable.field.name"), "entry", required=True, width=40),
            FieldSpec("category", tr("expenses.variable.field.category"), "combo", required=True, values=cat_vals, width=40),
            FieldSpec("amount", tr("expenses.variable.field.amount"), "entry", required=True),
            FieldSpec(
                "status_ui",
                tr("expenses.variable.field.status"),
                "combo",
                required=True,
                values=[_code_to_ui(k, VARIABLE_STATUS_KEYS) for k in VARIABLE_STATUS_KEYS.keys()],
            ),
            FieldSpec("account", tr("expenses.variable.field.account"), "combo", required=False, values=acc_vals, width=40),
            FieldSpec(
                "pay_bucket_ui",
                tr("expenses.variable.field.pay_bucket"),
                "combo",
                required=True,
                values=[_code_to_ui(k, PAY_BUCKET_KEYS) for k in PAY_BUCKET_KEYS.keys()],
            ),
            FieldSpec("notes", tr("expenses.variable.field.notes"), "text", required=False, width=40),
        ]

        dlg = FormDialog(self._root(), tr("expenses.variable.dialog.title"), fields, initial=initial)
        if not dlg.result:
            return

        try:
            cat_id = self._parse_id_choice(dlg.result["category"]) or 0
            acc_id = self._parse_id_choice(dlg.result.get("account") or "") or None
            status = _ui_to_code(dlg.result["status_ui"], VARIABLE_STATUS_KEYS, default="OPEN") or "OPEN"
            pay_bucket = _ui_to_code(dlg.result["pay_bucket_ui"], PAY_BUCKET_KEYS, default="NONE") or "NONE"

            year = period.year
            month = period.month
            if existing:
                year = int(existing.year)
                month = int(existing.month)

            dto = ExpenseVariableDTO(
                id=vid,
                name=str(dlg.result["name"]).strip(),
                category_id=int(cat_id),
                amount=ui_decimal(str(dlg.result["amount"])),
                year=int(year),
                month=int(month),
                status=status,
                account_id=acc_id,
                pay_bucket=pay_bucket,
                notes=str(dlg.result.get("notes") or "").strip() or None,
            )
            self._exp.upsert_variable(dto)
            self.refresh()
        except Exception:
            logger.exception("_open_var_dialog failed.")
            self._err(tr("common.error"), tr("expenses.error.save_variable_failed"))

    # -------------------- dialogs: loans --------------------
    def add_loan(self) -> None:
        self._open_loan_dialog(None)

    def delete_selected_loan(self) -> None:
        loan_id = self._selected_id(self._view.loan_tree)
        if not loan_id:
            self._warn(tr("common.notice"), tr("expenses.warn.select_loan"))
            return
        if not messagebox.askyesno(tr("common.irreversible_delete"), tr("expenses.confirm.delete_loan")):
            return
        try:
            self._loan.delete_loan(loan_id)
            self.refresh()
        except Exception:
            logger.exception("delete_selected_loan failed.")
            self._err(tr("common.error"), tr("expenses.error.delete_loan_failed"))

    def close_selected_loan(self) -> None:
        loan_id = self._selected_id(self._view.loan_tree)
        if not loan_id:
            self._warn(tr("common.notice"), tr("expenses.warn.select_loan"))
            return
        try:
            self._loan.set_loan_status(loan_id, "CLOSED")
            self.refresh()
        except Exception:
            logger.exception("close_selected_loan failed.")
            self._err(tr("common.error"), tr("expenses.error.close_loan_failed"))

    def reopen_selected_loan(self) -> None:
        loan_id = self._selected_id(self._view.loan_tree)
        if not loan_id:
            self._warn(tr("common.notice"), tr("expenses.warn.select_loan"))
            return
        try:
            self._loan.set_loan_status(loan_id, "ACTIVE")
            self.refresh()
        except Exception:
            logger.exception("reopen_selected_loan failed.")
            self._err(tr("common.error"), tr("expenses.error.reopen_loan_failed"))

    def add_loan_event(self) -> None:
        loan_id = self._selected_id(self._view.loan_tree)
        if not loan_id:
            self._warn(tr("common.notice"), tr("expenses.warn.select_loan"))
            return
        self._open_loan_event_dialog(loan_id, None)

    def _open_loan_dialog(self, loan_id: int | None) -> None:
        acc_vals = [""] + [f"{a.id}:{a.label}" for a in self._accounts]
        initial = {
            "name": "",
            "start_date": str(date.today()),
            "principal": "0.00",
            "interest": "0.00",
            "regular_payment": "0.00",
            "timing_ui": _code_to_ui("MID", PAY_BUCKET_KEYS),
            "account": (acc_vals[1] if len(acc_vals) > 1 else ""),
            "notes": "",
        }

        existing: LoanDTO | None = None
        if loan_id:
            existing = next((x for x in self._loans if int(x.id) == int(loan_id)), None)
            if existing:
                initial.update(
                    {
                        "name": existing.name,
                        "start_date": str(existing.start_date),
                        "principal": str(existing.principal_initial),
                        "interest": str(existing.annual_interest_rate),
                        "regular_payment": str(existing.regular_payment),
                        "timing_ui": self._timing_to_ui(existing.payment_timing),
                        "account": self._fmt_acc(existing.account_id),
                        "notes": existing.notes or "",
                    }
                )

        fields = [
            FieldSpec("name", tr("expenses.loan.field.name"), "entry", required=True, width=40),
            FieldSpec("start_date", tr("expenses.loan.field.start_date"), "entry", required=True, width=24),
            FieldSpec("principal", tr("expenses.loan.field.principal"), "entry", required=True),
            FieldSpec("interest", tr("expenses.loan.field.interest"), "entry", required=True),
            FieldSpec("regular_payment", tr("expenses.loan.field.regular_payment"), "entry", required=True),
            FieldSpec(
                "timing_ui",
                tr("expenses.loan.field.timing"),
                "combo",
                required=True,
                values=[_code_to_ui("BEGINNING", PAY_BUCKET_KEYS), _code_to_ui("MID", PAY_BUCKET_KEYS)],
            ),
            FieldSpec("account", tr("expenses.loan.field.account"), "combo", required=False, values=acc_vals, width=40),
            FieldSpec("notes", tr("expenses.loan.field.notes"), "text", required=False, width=40),
        ]

        dlg = FormDialog(self._root(), tr("expenses.loan.dialog.title"), fields, initial=initial)
        if not dlg.result:
            return

        try:
            timing = self._parse_timing_ui(dlg.result["timing_ui"]) or "MID"
            acc_id = self._parse_id_choice(dlg.result.get("account") or "") or None

            dto = LoanDTO(
                id=loan_id,
                name=str(dlg.result["name"]).strip(),
                start_date=parse_date(str(dlg.result["start_date"])),
                principal_initial=ui_decimal(str(dlg.result["principal"])),
                annual_interest_rate=ui_decimal(str(dlg.result["interest"])),
                regular_payment=ui_decimal(str(dlg.result["regular_payment"])),
                payment_timing=timing,
                account_id=acc_id,
                status="ACTIVE" if not existing else _v(existing.status),
                notes=str(dlg.result.get("notes") or "").strip() or None,
            )
            self._loan.upsert_loan(dto)
            self.refresh()
        except Exception:
            logger.exception("_open_loan_dialog failed.")
            self._err(tr("common.error"), tr("expenses.error.save_loan_failed"))

    def _open_loan_event_dialog(self, loan_id: int, event_id: int | None) -> None:
        acc_vals = [""] + [f"{a.id}:{a.label}" for a in self._accounts]
        initial = {
            "date": str(date.today()),
            "type_ui": _code_to_ui("PAYMENT", LOAN_EVENT_KEYS),
            "amount": "0.00",
            "new_regular_payment": "",
            "new_interest": "",
            "override_account": "",
            "override_timing_ui": "",
            "notes": "",
        }

        existing: LoanEventDTO | None = None
        events = self._loan.list_events(loan_id)

        if not event_id:
            last_payment = next(
                (e for e in reversed(events) if _v(getattr(e, "event_type", "")) == "PAYMENT" and e.amount),
                None,
            )
            if last_payment:
                initial["amount"] = str(last_payment.amount)

        if event_id:
            existing = next((e for e in events if int(e.id) == int(event_id)), None)
            if existing:
                initial.update(
                    {
                        "date": str(existing.event_date),
                        "type_ui": _code_to_ui(_v(existing.event_type), LOAN_EVENT_KEYS),
                        "amount": str(existing.amount or 0),
                        "new_regular_payment": (
                            str(existing.new_regular_payment) if existing.new_regular_payment is not None else ""
                        ),
                        "new_interest": (
                            str(existing.new_annual_interest_rate) if existing.new_annual_interest_rate is not None else ""
                        ),
                        "override_account": (
                            self._fmt_acc(existing.override_account_id)
                            if getattr(existing, "override_account_id", None)
                            else ""
                        ),
                        "override_timing_ui": (
                            self._timing_to_ui(existing.override_payment_timing)
                            if getattr(existing, "override_payment_timing", None)
                            else ""
                        ),
                        "notes": existing.notes or "",
                    }
                )

        fields = [
            FieldSpec("date", tr("expenses.loan_event.field.date"), "entry", required=True),
            FieldSpec(
                "type_ui",
                tr("expenses.loan_event.field.type"),
                "combo",
                required=True,
                values=[_code_to_ui(k, LOAN_EVENT_KEYS) for k in LOAN_EVENT_KEYS.keys()],
            ),
            FieldSpec("amount", tr("expenses.loan_event.field.amount"), "entry", required=True),
            FieldSpec("new_regular_payment", tr("expenses.loan_event.field.new_regular_payment"), "entry", required=False),
            FieldSpec("new_interest", tr("expenses.loan_event.field.new_interest"), "entry", required=False),
            FieldSpec(
                "override_account",
                tr("expenses.loan_event.field.override_account"),
                "combo",
                required=False,
                values=acc_vals,
                width=40,
            ),
            FieldSpec(
                "override_timing_ui",
                tr("expenses.loan_event.field.override_timing"),
                "combo",
                required=False,
                values=["", _code_to_ui("BEGINNING", PAY_BUCKET_KEYS), _code_to_ui("MID", PAY_BUCKET_KEYS)],
            ),
            FieldSpec("notes", tr("expenses.loan_event.field.notes"), "text", required=False, width=40),
        ]

        dlg = FormDialog(self._root(), tr("expenses.loan_event.dialog.title"), fields, initial=initial)
        if not dlg.result:
            return

        try:
            etype = _ui_to_code(dlg.result["type_ui"], LOAN_EVENT_KEYS, default="PAYMENT") or "PAYMENT"
            amount = ui_decimal(str(dlg.result["amount"]), default=Decimal("0"))
            new_rate = str(dlg.result.get("new_regular_payment") or "").strip()
            new_interest = str(dlg.result.get("new_interest") or "").strip()

            override_acc = (
                self._parse_id_choice(dlg.result.get("override_account") or "") if dlg.result.get("override_account") else None
            )
            override_tim = (
                self._parse_timing_ui(dlg.result.get("override_timing_ui") or "") if dlg.result.get("override_timing_ui") else None
            )

            dto = LoanEventDTO(
                id=event_id,
                loan_id=loan_id,
                event_date=parse_date(str(dlg.result["date"])),
                event_type=etype,
                amount=amount,
                new_regular_payment=(ui_decimal(new_rate) if new_rate else None),
                new_annual_interest_rate=(ui_decimal(new_interest) if new_interest else None),
                notes=str(dlg.result.get("notes") or "").strip() or None,
                override_account_id=override_acc,
                override_payment_timing=override_tim,
            )
            self._loan.upsert_event(dto)
            self.refresh()
        except Exception:
            logger.exception("_open_loan_event_dialog failed.")
            self._err(tr("common.error"), tr("expenses.error.save_event_failed"))

