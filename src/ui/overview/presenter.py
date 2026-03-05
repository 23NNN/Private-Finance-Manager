# src/ui/overview/presenter.py
from __future__ import annotations

import logging
import traceback
from decimal import Decimal

from src.application.services.overview_service import OverviewService
from src.config.settings import get_settings
from src.ui.common.error_dialog import show_error
from src.ui.common.i18n import tr

logger = logging.getLogger(__name__)


def _m(x: Decimal) -> str:
    return f"{Decimal(x or 0):.2f}"


def _timing_label(timing: str) -> str:
    return {
        "BEGINNING": tr("timing.beginning"),
        "MID": tr("timing.mid"),
    }.get(timing, timing)


class OverviewPresenter:
    def __init__(self, view, overview_service: OverviewService):
        self._view = view
        self._svc = overview_service
        self._settings = get_settings()

        self._view.bind_refresh(self.refresh)

    def refresh(self) -> None:
        try:
            mode = self._view.get_view_mode()
            tf = self._view.get_timeframe()

            if tf == "YEAR":
                year = self._view.get_year()
                vm = self._svc.get_year_overview(year, mode)
                self._render_period("cur", vm)

                # next section cleared in year mode
                self._view.set_incomes("nxt", [], footer=(tr("common.total"), "0.00", "0.00", "0.00"))
                self._view.set_accounts("nxt", [], footer=(tr("common.total"), "0.00", "", "0.00", ""))
                self._view.set_loans("nxt", [], footer=(tr("common.total"), "", "0.00", "0.00", ""))
                self._view.set_payout_summary("nxt", [], footer=(tr("common.total"), "0.00", "0.00", "0.00", "0.00", "0.00"))
                self._view.set_period_data("nxt", savings_total="0.00", fix_total="0.00", var_total="0.00")
                return

            period = self._view.get_period()
            nxt = period.next_month()
            vm = self._svc.get_overview(period, nxt, mode)

            self._render_period("cur", vm.current)
            self._render_period("nxt", vm.next)

        except Exception:
            logger.exception("Overview refresh failed.")
            show_error(
                self._view.winfo_toplevel(),
                tr("common.error"),
                tr("overview.error.load_failed"),
                details=traceback.format_exc(),
                db_path=self._settings.db_path(),
                log_path=self._settings.log_path(),
            )

    def _render_period(self, prefix: str, pvm) -> None:
        fix_total = sum((a.fix_amount for a in pvm.accounts), Decimal("0.00"))
        self._view.set_period_data(
            prefix,
            savings_total=_m(pvm.savings_total),
            fix_total=_m(fix_total),
            var_total=_m(pvm.variable_total),
        )

        incomes = [i for i in pvm.incomes if (i.calc_amount != 0) or (i.actual_amount != 0)]
        incomes_rows = [(i.employer_name, _m(i.calc_amount), _m(i.actual_amount), _m(i.savings_amount)) for i in incomes]
        inc_footer = (
            tr("common.total"),
            _m(sum((i.calc_amount for i in incomes), Decimal("0.00"))),
            _m(sum((i.actual_amount for i in incomes), Decimal("0.00"))),
            _m(sum((i.savings_amount for i in incomes), Decimal("0.00"))),
        )
        self._view.set_incomes(prefix, incomes_rows, footer=inc_footer)

        accounts = [a for a in pvm.accounts if (a.fix_amount != 0) or (a.variable_amount != 0)]
        acc_rows = [
            (a.account_label, _m(a.fix_amount), f"{a.fix_share_pct:.2f}", _m(a.variable_amount), f"{a.variable_share_pct:.2f}")
            for a in accounts
        ]
        acc_footer = (
            tr("common.total"),
            _m(sum((a.fix_amount for a in accounts), Decimal("0.00"))),
            "",
            _m(sum((a.variable_amount for a in accounts), Decimal("0.00"))),
            "",
        )
        self._view.set_accounts(prefix, acc_rows, footer=acc_footer)

        loan_rows = [(l.loan_name, _m(l.open_before), _m(l.payment), _m(l.extra), _m(l.open_after)) for l in pvm.loans]
        loan_footer = (
            tr("common.total"),
            "",
            _m(sum((l.payment for l in pvm.loans), Decimal("0.00"))),
            _m(sum((l.extra for l in pvm.loans), Decimal("0.00"))),
            "",
        )
        self._view.set_loans(prefix, loan_rows, footer=loan_footer)

        rows = []
        for r in getattr(pvm, "payout_summary", []) or []:
            rows.append(
                (
                    _timing_label(r.payout_timing),
                    _m(r.total_income),
                    _m(r.savings),
                    _m(r.debts),
                    _m(r.fix_costs),
                    _m(r.free_available),
                )
            )

        footer = (
            tr("common.total"),
            _m(sum((r.total_income for r in getattr(pvm, "payout_summary", []) or []), Decimal("0.00"))),
            _m(sum((r.savings for r in getattr(pvm, "payout_summary", []) or []), Decimal("0.00"))),
            _m(sum((r.debts for r in getattr(pvm, "payout_summary", []) or []), Decimal("0.00"))),
            _m(sum((r.fix_costs for r in getattr(pvm, "payout_summary", []) or []), Decimal("0.00"))),
            _m(sum((r.free_available for r in getattr(pvm, "payout_summary", []) or []), Decimal("0.00"))),
        )
        self._view.set_payout_summary(prefix, rows, footer=footer)
