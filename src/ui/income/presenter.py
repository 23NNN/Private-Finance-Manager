# src/ui/income/presenter.py
from __future__ import annotations

import logging
import traceback
from datetime import date
from decimal import Decimal

from src.domain.models.period import Period

from tkinter import messagebox

from src.application.dto.employers import EmployerDTO, PayRuleDTO
from src.application.dto.incomes import IncomeFixedDTO, IncomeHourlyDTO, IncomeSpecialDTO
from src.application.dto.savings import SavingsRuleDTO
from src.application.services.employer_service import EmployerService
from src.application.services.income_service import IncomeService
from src.application.services.reference_data_service import ReferenceDataService
from src.application.validators.parsers import parse_date
from src.ui.common.dialogs import FieldSpec, FormDialog
from src.ui.common.validation import ui_decimal
from src.ui.income.fixed_dialog import FixedIncomeDialog
from src.ui.income.hourly_dialog import HourlyIncomeDialog
from src.ui.common.i18n import tr, trf
from src.infrastructure.db.orm_models import PayRuleType

UI_RULE_TYPES: list[str] = [e.value for e in PayRuleType]

logger = logging.getLogger(__name__)

def _bind_row_double_click(tree, fn) -> None:
    """Binds double-click on a row (not on the header).

    - add="+" so that sort-reset and other bindings are preserved
    - Header double-click is ignored (no unintended editing)
    """

    def _h(e):
        try:
            if tree.identify_region(e.x, e.y) == "heading":
                return
        except Exception:
            return
        fn()

    tree.bind("<Double-1>", _h, add="+")

try:
    from src.config.settings import get_settings
    from src.ui.common.error_dialog import show_error, show_warning
except Exception:  # pragma: no cover
    get_settings = None

    def show_error(_parent, title, msg, **_kw):
        messagebox.showerror(title, msg)

    def show_warning(_parent, title, msg, **_kw):
        messagebox.showwarning(title, msg)

def _fmt2(x) -> str:
    try:
        return f"{Decimal(x or 0):.2f}"
    except Exception:
        return "0.00"

def _norm_from(d: date | None) -> date:
    return d or date(1900, 1, 1)

def _to_inf(d: date | None) -> date:
    return d or date.max

def _active_for(d_from: date | None, d_to: date | None, at: date) -> bool:
    return _norm_from(d_from) <= at <= _to_inf(d_to)

TIMING_CODES = ("BEGINNING", "MID")

def timing_label(code: str) -> str:
    return tr(f"timing.{code.lower()}")

def timing_values() -> list[str]:
    return [timing_label(c) for c in TIMING_CODES]

def timing_code(label: str) -> str:
    m = {timing_label(c): c for c in TIMING_CODES}
    return m.get(label, "MID")


RULE_TYPE_TO_KEY = {
    "HOURLY_WAGE": "income.rule_type.hourly_wage",
    "SALARY": "income.rule_type.salary",
    "NIGHT": "income.rule_type.night",
    "SUNDAY": "income.rule_type.sunday",
    "HOLIDAY": "income.rule_type.holiday",
    "OVERTIME": "income.rule_type.overtime",
}
RULE_TYPE_CODES = tuple(RULE_TYPE_TO_KEY.keys())

def rule_type_label(code: str) -> str:
    return tr(RULE_TYPE_TO_KEY.get(code, code))

def rule_type_values() -> list[str]:
    return [rule_type_label(c) for c in RULE_TYPE_CODES]

def rule_type_code(label: str) -> str:
    m = {rule_type_label(c): c for c in RULE_TYPE_CODES}
    return m.get(label, label)


UNIT_TO_KEY = {
    "EUR_PER_HOUR": "income.unit.eur_per_hour",
    "EUR_PER_MONTH": "income.unit.eur_per_month",
    "MULTIPLIER": "income.unit.multiplier",
}
UNIT_CODES = tuple(UNIT_TO_KEY.keys())

def unit_label(code: str) -> str:
    return tr(UNIT_TO_KEY.get(code, code))

def unit_values() -> list[str]:
    return [unit_label(c) for c in UNIT_CODES]

def unit_code(label: str) -> str:
    m = {unit_label(c): c for c in UNIT_CODES}
    return m.get(label, label)


class IncomePresenter:
    def __init__(
        self,
        view,
        income_service: IncomeService,
        ref_service: ReferenceDataService,
        employer_service: EmployerService,
    ) -> None:
        self._view = view
        self._income = income_service
        self._ref = ref_service
        self._emp = employer_service
        self._settings = get_settings() if get_settings else None

        self._accounts = []
        self._employers: list[EmployerDTO] = []

        self._fixed: list[IncomeFixedDTO] = []
        self._hourly: list[IncomeHourlyDTO] = []
        self._special: list[IncomeSpecialDTO] = []

        self._fixed_by_id: dict[int, IncomeFixedDTO] = {}
        self._hourly_by_id: dict[int, IncomeHourlyDTO] = {}
        self._special_by_id: dict[int, IncomeSpecialDTO] = {}

        self._pay_rules_by_id: dict[int, PayRuleDTO] = {}
        self._savings_rules_by_id: dict[int, SavingsRuleDTO] = {}

        self._bind()
        self.refresh()

    # ----------------- wiring -----------------
    def _bind(self) -> None:
        self._view.bind_refresh(self.refresh)
        self._view.bind_filter_change(self.refresh)

        # Fixed
        self._view.add_fixed_btn.configure(command=self.add_fixed)
        self._view.edit_fixed_btn.configure(command=self.edit_fixed)
        self._view.delete_fixed_btn.configure(command=self.delete_fixed)

        # Hourly
        self._view.add_hourly_btn.configure(command=self.add_hourly)
        self._view.edit_hourly_btn.configure(command=self.edit_hourly)
        self._view.delete_hourly_btn.configure(command=self.delete_hourly)
        self._view.recalc_hourly_btn.configure(command=self.recalc_hourly)

        # Special
        self._view.add_special_btn.configure(command=self.add_special)
        self._view.edit_special_btn.configure(command=self.edit_special)
        self._view.delete_special_btn.configure(command=self.delete_special)

        # Employer
        self._view.add_employer_btn.configure(command=self.add_employer)
        self._view.edit_employer_btn.configure(command=self.edit_employer)
        self._view.delete_employer_btn.configure(command=self.delete_employer)
        self._view.employer_tree.bind("<<TreeviewSelect>>", lambda _e: self._on_employer_select())

        # Pay rules
        self._view.add_rule_btn.configure(command=self.add_rule)
        self._view.edit_rule_btn.configure(command=self.edit_rule)
        self._view.delete_rule_btn.configure(command=self.delete_rule)

        # Savings rules
        self._view.add_savings_rule_btn.configure(command=self.add_savings_rule)
        self._view.edit_savings_rule_btn.configure(command=self.edit_savings_rule)
        self._view.delete_savings_rule_btn.configure(command=self.delete_savings_rule)

        # Double click edit
        _bind_row_double_click(self._view.fixed_tree, self.edit_fixed)
        _bind_row_double_click(self._view.hourly_tree, self.edit_hourly)
        _bind_row_double_click(self._view.special_tree, self.edit_special)
        _bind_row_double_click(self._view.rules_tree, self.edit_rule)
        _bind_row_double_click(self._view.savings_rules_tree, self.edit_savings_rule)

        # Delete key
        self._view.fixed_tree.bind("<Delete>", lambda _e: self.delete_fixed())
        self._view.hourly_tree.bind("<Delete>", lambda _e: self.delete_hourly())
        self._view.special_tree.bind("<Delete>", lambda _e: self.delete_special())
        self._view.rules_tree.bind("<Delete>", lambda _e: self.delete_rule())
        self._view.savings_rules_tree.bind("<Delete>", lambda _e: self.delete_savings_rule())

    # ----------------- helpers -----------------
    def _root(self):
        return self._view.winfo_toplevel()

    def _err(self, title: str, msg: str, *, details: str | None = None) -> None:
        show_error(
            self._root(),
            title,
            msg,
            details=(details or traceback.format_exc()),
            db_path=(self._settings.db_path() if self._settings else None),
            log_path=(self._settings.log_path() if self._settings else None),
        )

    def _warn(self, title: str, msg: str) -> None:
        show_warning(
            self._root(),
            title,
            msg,
            db_path=(self._settings.db_path() if self._settings else None),
            log_path=(self._settings.log_path() if self._settings else None),
        )

    @staticmethod
    def _selected_id(tree) -> int | None:
        sel = tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    @staticmethod
    def _parse_id(v: str) -> int:
        return int(str(v).split(":", 1)[0].strip())

    @staticmethod
    def _parse_optional_id(v: str) -> int | None:
        s = (v or "").strip()
        if not s or s == tr("common.all"):
            return None
        return int(s.split(":", 1)[0].strip())

    def _acc_vals(self) -> list[str]:
        return [f"{a.id}:{a.label}" for a in self._accounts]

    def _emp_vals(self) -> list[str]:
        return [f"{e.id}:{e.name}" for e in self._employers]

    def _filters(self) -> dict:
        try:
            return self._view.get_filters()
        except Exception:
            return {}

    def _is_year_view(self) -> bool:
        try:
            return bool(self._view.is_year_view())
        except Exception:
            return False

    def refresh(self) -> None:
        try:
            self._accounts = self._ref.list_accounts()
            self._employers = self._ref.list_employers()

            self._view.set_filter_options(
                employers=self._emp_vals(),
                accounts=self._acc_vals(),
                rule_types=UI_RULE_TYPES,
            )

            emp_name = {e.id: e.name for e in self._employers}
            acc_label = {a.id: a.label for a in self._accounts}

            period = self._view.get_period()
            f = self._filters()

            if self._is_year_view():
                self._fixed = []
                for m in range(1, 13):
                    self._fixed.extend(self._income.list_fixed(Period(period.year, m)))
                self._hourly = []
                for m in range(1, 13):
                    self._hourly.extend(self._income.list_hourly(Period(period.year, m)))
                self._special = self._income.list_special_for_year(period.year)
            else:
                self._fixed = self._income.list_fixed(period)
                self._hourly = self._income.list_hourly(period)
                self._special = self._income.list_special(period)

            self._fixed_by_id = {x.id: x for x in self._fixed if x.id is not None}
            self._hourly_by_id = {x.id: x for x in self._hourly if x.id is not None}
            self._special_by_id = {x.id: x for x in self._special if x.id is not None}

            self._render_fixed(emp_name, acc_label, f.get("fixed", {}))
            self._render_hourly(emp_name, acc_label, f.get("hourly", {}))
            self._render_special(acc_label, f.get("special", {}))

            self.refresh_employers()
            self.refresh_rules()
            self.refresh_savings_rules()

        except Exception:
            logger.exception("Income refresh failed")
            self._err(tr("common.error"), tr("income.error.load_failed"))

    # ----------------- renderers -----------------
    def _render_fixed(self, emp_name: dict[int, str], acc_label: dict[int, str], flt: dict) -> None:
        tree = self._view.fixed_tree
        tree.delete(*tree.get_children())

        emp_filter = (flt.get("employer") or tr("common.all")).strip()
        timing_filter = (flt.get("timing") or tr("common.all")).strip()
        acc_filter = (flt.get("account") or tr("common.all")).strip()

        for r in self._fixed:
            if emp_filter != tr("common.all") and self._parse_id(emp_filter) != r.employer_id:
                continue
            if timing_filter != tr("common.all"):
                if timing_label(r.payout_timing) != timing_filter:
                    continue
            if acc_filter != tr("common.all"):
                if self._parse_optional_id(acc_filter) != r.account_id:
                    continue

            tree.insert(
                "",
                "end",
                iid=str(r.id),
                values=(
                    emp_name.get(r.employer_id, f"#{r.employer_id}"),
                    _fmt2(r.base_amount),
                    _fmt2(r.special_amount),
                    _fmt2(r.calc_amount),
                    _fmt2(r.actual_amount),
                    timing_label(r.payout_timing),
                    acc_label.get(r.account_id, "") if r.account_id else "",
                ),
            )

    def _render_hourly(self, emp_name: dict[int, str], acc_label: dict[int, str], flt: dict) -> None:
        tree = self._view.hourly_tree
        tree.delete(*tree.get_children())

        emp_filter = (flt.get("employer") or tr("common.all")).strip()
        acc_filter = (flt.get("account") or tr("common.all")).strip()

        for r in self._hourly:
            if emp_filter != tr("common.all") and self._parse_id(emp_filter) != r.employer_id:
                continue
            if acc_filter != tr("common.all"):
                if self._parse_optional_id(acc_filter) != r.account_id:
                    continue

            hours = (r.hours_normal or Decimal("0")) + (r.hours_bw or Decimal("0")) + (r.hours_by or Decimal("0"))
            night = (r.night or Decimal("0")) + (r.night_bw or Decimal("0")) + (r.night_by or Decimal("0"))
            sunday = (r.sunday or Decimal("0")) + (r.sunday_bw or Decimal("0")) + (r.sunday_by or Decimal("0"))

            tree.insert(
                "",
                "end",
                iid=str(r.id),
                values=(
                    emp_name.get(r.employer_id, f"#{r.employer_id}"),
                    _fmt2(hours),
                    _fmt2(night),
                    _fmt2(sunday),
                    _fmt2(r.holiday),
                    _fmt2(r.overtime),
                    _fmt2(r.calc_amount),
                    _fmt2(r.actual_amount),
                    acc_label.get(r.account_id, "") if r.account_id else "",
                ),
            )

    def _render_special(self, acc_label: dict[int, str], flt: dict) -> None:
        tree = self._view.special_tree
        tree.delete(*tree.get_children())

        timing_filter = (flt.get("timing") or tr("common.all")).strip()
        acc_filter = (flt.get("account") or tr("common.all")).strip()

        for r in self._special:
            if timing_filter != tr("common.all"):
                if timing_label(r.payout_timing) != timing_filter:
                    continue
            if acc_filter != tr("common.all"):
                if self._parse_optional_id(acc_filter) != r.account_id:
                    continue

            tree.insert(
                "",
                "end",
                iid=str(r.id),
                values=(
                    r.name,
                    _fmt2(r.amount),
                    _fmt2(r.actual_amount),
                    timing_label(r.payout_timing),
                    acc_label.get(r.account_id, "") if r.account_id else "",
                    r.notes or "",
                ),
            )

    # ----------------- Fixed CRUD -----------------
    def add_fixed(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.month_view_only"))
            return
        self._open_fixed_dialog(None)

    def edit_fixed(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.edit_month_view_only"))
            return
        rid = self._selected_id(self._view.fixed_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("common.select_row_first"))
            return
        self._open_fixed_dialog(rid)

    def delete_fixed(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.delete_month_view_only"))
            return
        rid = self._selected_id(self._view.fixed_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("common.select_row_first"))
            return
        if not messagebox.askyesno(tr("common.delete"), tr("common.confirm_delete_entry")):
            return
        try:
            self._income.delete_fixed(rid)
            self.refresh()
        except Exception:
            logger.exception("delete_fixed failed")
            self._err(tr("common.error"), tr("income.error.delete_failed"))

    def _salary_provider(self, employer_id: int) -> Decimal:
        period = self._view.get_period()
        at = date(int(period.year), int(period.month), 1)
        try:
            rules = self._emp.list_pay_rules(employer_id)
        except Exception:
            return Decimal("0.00")

        best = None
        best_vf = date(1900, 1, 1)
        for r in rules:
            if r.rule_type != "SALARY":
                continue
            if not _active_for(r.valid_from, r.valid_to, at):
                continue
            vf = _norm_from(r.valid_from)
            if vf >= best_vf:
                best = r
                best_vf = vf
        if best is None:
            return Decimal("0.00")
        return Decimal(best.value).quantize(Decimal("0.01"))

    def _open_fixed_dialog(self, rid: int | None) -> None:
        period = self._view.get_period()
        existing = self._fixed_by_id.get(rid) if rid else None

        acc_label = {a.id: a.label for a in self._accounts}

        initial = {
            "employer": (self._emp_vals()[0] if self._emp_vals() else ""),
            "base_amount": "0.00",
            "special_amount": "0.00",
            "actual_amount": "0.00",
            "payout_timing": timing_label("MID"),
            "account": "",
            "notes": "",
        }

        # Default: auto-fill payout timing + account from employer (prevents wrong assignment in overview)
        if not existing:
            try:
                emp_choice = str(initial.get("employer") or "").strip()
                emp_id = self._parse_id(emp_choice) if emp_choice else None
                emp = next((e for e in self._employers if int(e.id) == int(emp_id)), None) if emp_id else None
                if emp:
                    initial["payout_timing"] = timing_label(getattr(emp, "payout_timing", "MID"))
                    if getattr(emp, "default_account_id", None):
                        aid = int(emp.default_account_id)
                        initial["account"] = f"{aid}:{acc_label.get(aid, aid)}"
            except Exception:
                pass

        if existing:
            initial.update(
                {
                    "employer": f"{existing.employer_id}:{next((e.name for e in self._employers if e.id == existing.employer_id), existing.employer_id)}",
                    "base_amount": _fmt2(existing.base_amount),
                    "special_amount": _fmt2(existing.special_amount),
                    "actual_amount": _fmt2(existing.actual_amount),
                    "payout_timing": timing_label(existing.payout_timing),
                    "account": (
                        f"{existing.account_id}:{acc_label.get(existing.account_id, existing.account_id)}"
                        if existing.account_id
                        else ""
                    ),
                    "notes": existing.notes or "",
                }
            )

        dlg = FixedIncomeDialog(
            self._view,
            title=tr("income.dialog.fixed.title"),
            employer_values=self._emp_vals(),
            account_values=[""] + self._acc_vals(),
            payout_values=timing_values(),
            salary_provider=self._salary_provider,
            initial=initial,
        )
        data = dlg.show()
        if not data:
            return

        try:
            emp_id = self._parse_id(str(data["employer"]))
            base = ui_decimal(str(data.get("base_amount", "")), default=Decimal("0"))
            # If base amount is missing from rule, fetch again
            if base == Decimal("0"):
                base = self._salary_provider(emp_id)

            special = ui_decimal(str(data.get("special_amount", "")), default=Decimal("0"))
            actual = ui_decimal(str(data.get("actual_amount", "")), default=Decimal("0"))

            dto = IncomeFixedDTO(
                id=existing.id if existing else None,
                employer_id=emp_id,
                year=period.year,
                month=period.month,
                base_amount=base,
                special_amount=special,
                calc_amount=base + special,
                actual_amount=actual,
                payout_timing=timing_code(str(data["payout_timing"]).strip()),
                account_id=self._parse_optional_id(str(data.get("account", ""))),
                notes=str(data.get("notes", "")).strip() or None,
            )
            self._income.upsert_fixed(dto)
            self.refresh()
        except Exception:
            logger.exception("upsert_fixed failed")
            self._err(tr("common.error"), tr("income.error.save_failed"))

    # ----------------- Hourly CRUD -----------------
    def add_hourly(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.month_view_only"))
            return
        self._open_hourly_dialog(None)

    def edit_hourly(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.edit_month_view_only"))
            return
        rid = self._selected_id(self._view.hourly_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("common.select_row_first"))
            return
        self._open_hourly_dialog(rid)

    def delete_hourly(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.delete_month_view_only"))
            return
        rid = self._selected_id(self._view.hourly_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("common.select_row_first"))
            return
        if not messagebox.askyesno(tr("common.delete"), tr("common.confirm_delete_entry")):
            return
        try:
            self._income.delete_hourly(rid)
            self.refresh()
        except Exception:
            logger.exception("delete_hourly failed")
            self._err(tr("common.error"), tr("income.error.delete_failed"))

    def recalc_hourly(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.recalc_month_view_only"))
            return
        rid = self._selected_id(self._view.hourly_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("common.select_row_first"))
            return
        try:
            self._income.recalculate_hourly(rid)
            self.refresh()
        except Exception:
            logger.exception("recalc_hourly failed")
            self._err(tr("common.error"), tr("income.error.recalc_failed"))

    def _open_hourly_dialog(self, rid: int | None) -> None:
        period = self._view.get_period()
        existing = self._hourly_by_id.get(rid) if rid else None

        acc_label = {a.id: a.label for a in self._accounts}
        initial = {
            "employer": (self._emp_vals()[0] if self._emp_vals() else ""),
            "hours": "0.00",
            "night": "0.00",
            "sunday": "0.00",
            "holiday": "0.00",
            "overtime": "0.00",
            "special_amount": "0.00",
            "actual_amount": "0.00",
            "payout_timing": timing_label("MID"),
            "account": "",
            "notes": "",
        }

        # Default: auto-fill payout timing + account from employer (prevents wrong assignment in overview)
        if not existing:
            try:
                emp_choice = str(initial.get("employer") or "").strip()
                emp_id = self._parse_id(emp_choice) if emp_choice else None
                emp = next((e for e in self._employers if int(e.id) == int(emp_id)), None) if emp_id else None
                if emp:
                    initial["payout_timing"] = timing_label(getattr(emp, "payout_timing", "MID"))
                    if getattr(emp, "default_account_id", None):
                        aid = int(emp.default_account_id)
                        initial["account"] = f"{aid}:{acc_label.get(aid, aid)}"
            except Exception:
                pass

        if existing:
            hours = (existing.hours_normal or Decimal("0")) + (existing.hours_bw or Decimal("0")) + (existing.hours_by or Decimal("0"))
            night = (existing.night or Decimal("0")) + (existing.night_bw or Decimal("0")) + (existing.night_by or Decimal("0"))
            sunday = (existing.sunday or Decimal("0")) + (existing.sunday_bw or Decimal("0")) + (existing.sunday_by or Decimal("0"))

            initial.update(
                {
                    "employer": f"{existing.employer_id}:{next((e.name for e in self._employers if e.id == existing.employer_id), existing.employer_id)}",
                    "hours": _fmt2(hours),
                    "night": _fmt2(night),
                    "sunday": _fmt2(sunday),
                    "holiday": _fmt2(existing.holiday),
                    "overtime": _fmt2(existing.overtime),
                    "special_amount": _fmt2(existing.special_amount),
                    "actual_amount": _fmt2(existing.actual_amount),
                    "payout_timing": timing_label(existing.payout_timing),
                    "account": (
                        f"{existing.account_id}:{acc_label.get(existing.account_id, existing.account_id)}"
                        if existing.account_id
                        else ""
                    ),
                    "notes": existing.notes or "",
                }
            )

        at = date(int(period.year), int(period.month), 1)

        def rules_provider(emp_id: int) -> dict[str, tuple[str, Decimal]]:
            try:
                rules = self._emp.list_pay_rules(emp_id)
            except Exception:
                return {}

            active = []
            for r in rules:
                if _active_for(r.valid_from, r.valid_to, at):
                    active.append(r)

            best: dict[str, PayRuleDTO] = {}
            for r in active:
                rt = r.rule_type
                vf = _norm_from(r.valid_from)
                if rt not in best:
                    best[rt] = r
                else:
                    cur_vf = _norm_from(best[rt].valid_from)
                    if vf > cur_vf:
                        best[rt] = r

            return {rt: (obj.unit, obj.value) for rt, obj in best.items()}

        dlg = HourlyIncomeDialog(
            self._view,
            title=tr("income.dialog.hourly.title"),
            employer_values=self._emp_vals(),
            account_values=[""] + self._acc_vals(),
            payout_values=timing_values(),
            rules_provider=rules_provider,
            initial=initial,
        )
        data = dlg.show()
        if not data:
            return

        try:
            dto = IncomeHourlyDTO(
                id=existing.id if existing else None,
                employer_id=self._parse_id(str(data["employer"])),
                year=period.year,
                month=period.month,
                # BW/BY dauerhaft 0
                hours_bw=Decimal("0"),
                hours_by=Decimal("0"),
                hours_normal=ui_decimal(str(data.get("hours", "")), default=Decimal("0")),
                night_bw=Decimal("0"),
                sunday_bw=Decimal("0"),
                night_by=Decimal("0"),
                sunday_by=Decimal("0"),
                night=ui_decimal(str(data.get("night", "")), default=Decimal("0")),
                sunday=ui_decimal(str(data.get("sunday", "")), default=Decimal("0")),
                holiday=ui_decimal(str(data.get("holiday", "")), default=Decimal("0")),
                overtime=ui_decimal(str(data.get("overtime", "")), default=Decimal("0")),
                special_amount=ui_decimal(str(data.get("special_amount", "")), default=Decimal("0")),
                calc_amount=Decimal("0"),
                actual_amount=ui_decimal(str(data.get("actual_amount", "")), default=Decimal("0")),
                payout_timing=timing_code(str(data["payout_timing"]).strip()),
                account_id=self._parse_optional_id(str(data.get("account", ""))),
                notes=str(data.get("notes", "")).strip() or None,
            )
            self._income.upsert_hourly(dto)
            self.refresh()
        except Exception:
            logger.exception("upsert_hourly failed")
            self._err(tr("common.error"), tr("income.error.save_failed"))

    # ----------------- Special CRUD -----------------
    def add_special(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.month_view_only"))
            return
        self._open_special_dialog(None)

    def edit_special(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.edit_month_view_only"))
            return
        rid = self._selected_id(self._view.special_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("common.select_row_first"))
            return
        self._open_special_dialog(rid)

    def delete_special(self) -> None:
        if self._is_year_view():
            self._warn(tr("common.notice"), tr("income.warn.delete_month_view_only"))
            return
        rid = self._selected_id(self._view.special_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("common.select_row_first"))
            return
        if not messagebox.askyesno(tr("common.delete"), tr("common.confirm_delete_entry")):
            return
        try:
            self._income.delete_special(rid)
            self.refresh()
        except Exception:
            logger.exception("delete_special failed")
            self._err(tr("common.error"), tr("income.error.delete_failed"))

    def _open_special_dialog(self, rid: int | None) -> None:
        period = self._view.get_period()
        existing = self._special_by_id.get(rid) if rid else None
        acc_label = {a.id: a.label for a in self._accounts}

        initial = {
            "name": "",
            "amount": "0.00",
            "actual_amount": "0.00",
            "payout_timing": timing_label("MID"),
            "account": "",
            "notes": "",
        }
        if existing:
            initial.update(
                {
                    "name": existing.name,
                    "amount": _fmt2(existing.amount),
                    "actual_amount": _fmt2(existing.actual_amount),
                    "payout_timing": timing_label(existing.payout_timing),
                    "account": (
                        f"{existing.account_id}:{acc_label.get(existing.account_id, existing.account_id)}"
                        if existing.account_id
                        else ""
                    ),
                    "notes": existing.notes or "",
                }
            )

        specs = [
            FieldSpec("name", tr("income.special.field.name"), "entry", required=True, width=44),
            FieldSpec("amount", tr("income.special.field.amount"), "entry", required=True, validator=ui_decimal),
            FieldSpec("actual_amount", tr("income.special.field.actual"), "entry", required=False, validator=ui_decimal),
            FieldSpec("payout_timing", tr("income.label.payout"), "combo", required=True, values=timing_values()),
            FieldSpec("account", tr("income.label.account"), "combo", required=False, values=[""] + self._acc_vals(), width=44),
            FieldSpec("notes", tr("common.notes"), "text", required=False, width=50, height=1),
        ]
        dlg = FormDialog(self._view, tr("income.dialog.special.title"), specs=specs, initial=initial)
        data = dlg.result
        if not data:
            return

        try:
            dto = IncomeSpecialDTO(
                id=existing.id if existing else None,
                year=period.year,
                month=period.month,
                name=str(data["name"]).strip(),
                amount=ui_decimal(str(data.get("amount", "")), default=Decimal("0")),
                actual_amount=ui_decimal(str(data.get("actual_amount", "")), default=Decimal("0")),
                payout_timing=timing_code(str(data["payout_timing"]).strip()),
                account_id=self._parse_optional_id(str(data.get("account", ""))),
                notes=str(data.get("notes", "")).strip() or None,
            )
            self._income.upsert_special(dto)
            self.refresh()
        except Exception:
            logger.exception("upsert_special failed")
            self._err(tr("common.error"), tr("income.error.save_failed"))

    # ----------------- Employer CRUD -----------------
    def refresh_employers(self) -> None:
        tree = self._view.employer_tree
        tree.delete(*tree.get_children())

        f = self._filters().get("employers", {})
        q = (f.get("name_q") or "").strip().lower()
        timing = (f.get("timing") or tr("common.all")).strip()
        acc = (f.get("account") or tr("common.all")).strip()

        acc_label = {a.id: a.label for a in self._accounts}

        for e in self._employers:
            if q and q not in (e.name or "").lower():
                continue
            if timing != tr("common.all") and timing_label(e.payout_timing) != timing:
                continue
            if acc != tr("common.all") and self._parse_optional_id(acc) != e.default_account_id:
                continue

            tree.insert(
                "",
                "end",
                iid=str(e.id),
                values=(
                    e.name,
                    timing_label(e.payout_timing),
                    acc_label.get(e.default_account_id, "") if e.default_account_id else "",
                ),
            )

    def _on_employer_select(self) -> None:
        self.refresh_rules()
        self.refresh_savings_rules()

    def add_employer(self) -> None:
        self._open_employer_dialog(None)

    def edit_employer(self) -> None:
        rid = self._selected_id(self._view.employer_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("income.warn.select_employer"))
            return
        self._open_employer_dialog(rid)

    def delete_employer(self) -> None:
        rid = self._selected_id(self._view.employer_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("income.warn.select_employer"))
            return
        if not messagebox.askyesno(tr("common.delete"), tr("income.employer.confirm_delete")):
            return
        try:
            self._emp.delete_employer(rid)
            self.refresh()
        except Exception:
            logger.exception("delete_employer failed")
            self._err(tr("common.error"), tr("income.error.delete_employer_failed"))

    def _open_employer_dialog(self, rid: int | None) -> None:
        existing = next((e for e in self._employers if e.id == rid), None) if rid else None
        initial = {
            "name": existing.name if existing else "",
            "payout_timing": timing_label(existing.payout_timing) if existing else timing_label("MID"),
            "default_account": "",
            "notes": existing.notes or "" if existing else "",
        }
        if existing and existing.default_account_id:
            acc_label = {a.id: a.label for a in self._accounts}
            initial["default_account"] = f"{existing.default_account_id}:{acc_label.get(existing.default_account_id, existing.default_account_id)}"

        specs = [
            FieldSpec("name", tr("income.employer.field.name"), "entry", required=True, width=40),
            FieldSpec("payout_timing", tr("income.label.payout"), "combo", required=True, values=timing_values()),
            FieldSpec("default_account", tr("income.employer.field.default_account"), "combo", required=False, values=[""] + self._acc_vals(), width=44),
            FieldSpec("notes", tr("common.notes"), "text", required=False, width=50, height=1),
        ]
        dlg = FormDialog(self._view, tr("income.dialog.employer.title"), specs=specs, initial=initial)
        data = dlg.result
        if not data:
            return
        try:
            dto = EmployerDTO(
                id=existing.id if existing else None,
                name=str(data["name"]).strip(),
                payout_timing=timing_code(str(data["payout_timing"]).strip()),
                default_account_id=self._parse_optional_id(str(data.get("default_account", ""))),
                notes=str(data.get("notes", "")).strip() or None,
            )
            self._emp.upsert_employer(dto)
            self.refresh()
        except Exception:
            logger.exception("upsert_employer failed")
            self._err(tr("common.error"), tr("income.error.save_employer_failed"))

    # ----------------- Pay rules CRUD -----------------
    def refresh_rules(self) -> None:
        self._pay_rules_by_id = {}

        emp_id = self._selected_id(self._view.employer_tree)
        if not emp_id:
            self._view.rules_tree.delete(*self._view.rules_tree.get_children())
            return

        try:
            rules = self._emp.list_pay_rules(emp_id)
        except Exception:
            rules = []

        period = self._view.get_period()
        at = date(int(period.year), int(period.month), 1)

        f = self._filters().get("rules", {})
        typ = (f.get("type") or tr("common.all")).strip()
        active_only = bool(f.get("active_only", True))

        tree = self._view.rules_tree
        tree.delete(*tree.get_children())

        for r in rules:
            if r.id is not None:
                self._pay_rules_by_id[r.id] = r

            if typ != tr("common.all") and rule_type_label(r.rule_type) != typ:
                continue
            if active_only and not _active_for(r.valid_from, r.valid_to, at):
                continue

            tree.insert(
                "",
                "end",
                iid=str(r.id),
                values=(
                    rule_type_label(r.rule_type),
                    unit_label(r.unit),
                    _fmt2(r.value),
                    r.valid_from.isoformat() if r.valid_from else "",
                    r.valid_to.isoformat() if r.valid_to else "",
                    (r.notes or ""),
                ),
            )

    def add_rule(self) -> None:
        emp_id = self._selected_id(self._view.employer_tree)
        if not emp_id:
            self._warn(tr("common.notice"), tr("income.error.select_employer_first"))
            return
        self._open_rule_dialog(None, emp_id)

    def edit_rule(self) -> None:
        emp_id = self._selected_id(self._view.employer_tree)
        rid = self._selected_id(self._view.rules_tree)
        if not emp_id or not rid:
            self._warn(tr("common.notice"), tr("income.warn.select_rule"))
            return
        self._open_rule_dialog(rid, emp_id)

    def delete_rule(self) -> None:
        rid = self._selected_id(self._view.rules_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("income.warn.select_rule"))
            return
        if not messagebox.askyesno(tr("common.delete"), tr("income.rule.confirm_delete_rule")):
            return
        try:
            self._emp.delete_pay_rule(rid)
            self.refresh_rules()
        except Exception:
            logger.exception("delete_rule failed")
            self._err(tr("common.error"), tr("income.error.delete_rule_failed"))

    def _open_rule_dialog(self, rid: int | None, employer_id: int) -> None:
        existing = self._pay_rules_by_id.get(rid) if rid else None
        initial = {
            "rule_type": rule_type_label(existing.rule_type) if existing else rule_type_label("HOURLY_WAGE"),
            "unit": unit_label(existing.unit) if existing else unit_label("EUR_PER_HOUR"),
            "value": _fmt2(existing.value) if existing else "0.00",
            "valid_from": existing.valid_from.isoformat() if existing and existing.valid_from else "",
            "valid_to": existing.valid_to.isoformat() if existing and existing.valid_to else "",
            "notes": existing.notes or "" if existing else "",
        }
        specs = [
            FieldSpec("rule_type", tr("income.rule.field.rule_type"), "combo", required=True, values=rule_type_values(), width=28),
            FieldSpec("unit", tr("income.label.unit"), "combo", required=True, values=unit_values(), width=28),
            FieldSpec("value", tr("income.rule.field.value"), "entry", required=True, validator=ui_decimal),
            FieldSpec("valid_from", tr("income.rule.field.valid_from"), "entry", required=False, width=16),
            FieldSpec("valid_to", tr("income.rule.field.valid_to"), "entry", required=False, width=16),
            FieldSpec("notes", tr("common.notes"), "text", required=False, width=50, height=1),
        ]
        dlg = FormDialog(self._view, tr("income.dialog.rule.title"), specs=specs, initial=initial)
        data = dlg.result
        if not data:
            return

        try:
            vf = parse_date(str(data.get("valid_from", "")).strip()) if str(data.get("valid_from", "")).strip() else None
            vt = parse_date(str(data.get("valid_to", "")).strip()) if str(data.get("valid_to", "")).strip() else None
            dto = PayRuleDTO(
                id=existing.id if existing else None,
                employer_id=employer_id,
                rule_type=rule_type_code(str(data["rule_type"]).strip()),
                unit=unit_code(str(data["unit"]).strip()),
                value=ui_decimal(str(data.get("value", "")), default=Decimal("0")),
                valid_from=vf,
                valid_to=vt,
                notes=str(data.get("notes", "")).strip() or None,
            )
            self._emp.upsert_pay_rule(dto)
            self.refresh_rules()
        except Exception as e:
            logger.exception("upsert_pay_rule failed")
            self._err(tr("common.error"), trf("income.error.save_rule_failed", error=e))

    # ----------------- Savings rules CRUD -----------------
    def refresh_savings_rules(self) -> None:
        self._savings_rules_by_id = {}
        emp_id = self._selected_id(self._view.employer_tree)
        tree = self._view.savings_rules_tree
        tree.delete(*tree.get_children())

        if not emp_id:
            return

        try:
            rules = self._emp.list_savings_rules(emp_id)
        except Exception:
            rules = []

        for r in rules:
            if r.id is not None:
                self._savings_rules_by_id[r.id] = r
            pct = (Decimal(r.percentage) * Decimal("100")).quantize(Decimal("0.01"))
            tree.insert(
                "",
                "end",
                iid=str(r.id),
                values=(
                    f"{pct:.2f}%".replace(".", ","),
                    r.valid_from.isoformat() if r.valid_from else "",
                    r.valid_to.isoformat() if r.valid_to else "",
                ),
            )

    def add_savings_rule(self) -> None:
        emp_id = self._selected_id(self._view.employer_tree)
        if not emp_id:
            self._warn(tr("common.notice"), tr("income.error.select_employer_first"))
            return
        self._open_savings_rule_dialog(None, emp_id)

    def edit_savings_rule(self) -> None:
        emp_id = self._selected_id(self._view.employer_tree)
        rid = self._selected_id(self._view.savings_rules_tree)
        if not emp_id or not rid:
            self._warn(tr("common.notice"), tr("income.warn.select_savings_rule"))
            return
        self._open_savings_rule_dialog(rid, emp_id)

    def delete_savings_rule(self) -> None:
        rid = self._selected_id(self._view.savings_rules_tree)
        if not rid:
            self._warn(tr("common.notice"), tr("income.warn.select_savings_rule"))
            return
        if not messagebox.askyesno(tr("common.delete"), tr("income.savings_rate.confirm_delete")):
            return
        try:
            self._emp.delete_savings_rule(rid)
            self.refresh_savings_rules()
        except Exception:
            logger.exception("delete_savings_rule failed")
            self._err(tr("common.error"), tr("income.error.delete_savings_rule_failed"))

    def _open_savings_rule_dialog(self, rid: int | None, employer_id: int) -> None:
        existing = self._savings_rules_by_id.get(rid) if rid else None
        initial = {
            "percentage": "",
            "valid_from": existing.valid_from.isoformat() if existing and existing.valid_from else "",
            "valid_to": existing.valid_to.isoformat() if existing and existing.valid_to else "",
        }
        if existing:
            pct = (Decimal(existing.percentage) * Decimal("100")).quantize(Decimal("0.01"))
            initial["percentage"] = f"{pct:.2f}".replace(".", ",")
        else:
            initial["percentage"] = "10,00"

        specs = [
            FieldSpec("percentage", tr("income.savings_rate.field.percentage"), "entry", required=True),
            FieldSpec("valid_from", tr("income.savings_rate.field.valid_from"), "entry", required=False, width=16),
            FieldSpec("valid_to", tr("income.savings_rate.field.valid_to"), "entry", required=False, width=16),
        ]
        dlg = FormDialog(self._view, tr("income.savings_rate.dialog.title"), specs=specs, initial=initial)
        data = dlg.result
        if not data:
            return
        try:
            raw = str(data.get("percentage", "")).strip().replace(" ", "")
            raw = raw[:-1] if raw.endswith("%") else raw
            raw = raw.replace(",", ".")
            pct = Decimal(raw)
            if pct > 1:
                pct = pct / Decimal("100")

            vf = parse_date(str(data.get("valid_from", "")).strip()) if str(data.get("valid_from", "")).strip() else None
            vt = parse_date(str(data.get("valid_to", "")).strip()) if str(data.get("valid_to", "")).strip() else None

            dto = SavingsRuleDTO(
                id=existing.id if existing else None,
                employer_id=employer_id,
                percentage=pct,
                valid_from=vf,
                valid_to=vt,
                goal_id=None,
            )
            self._emp.upsert_savings_rule(dto)
            self.refresh_savings_rules()
        except Exception as e:
            logger.exception("upsert_savings_rule failed")
            self._err(tr("common.error"), trf("income.error.save_savings_rule_failed", error=e))

