# tests/unit/test_overview_vm_contract.py
from __future__ import annotations

from decimal import Decimal

from src.application.dto.overview import OverviewVM, PeriodOverviewVM


def _p(year: int, month: int) -> PeriodOverviewVM:
    return PeriodOverviewVM(
        year=year,
        month=month,
        incomes=[],
        savings_total=Decimal("0.00"),
        accounts=[],
        loans=[],
        recurring_abos=Decimal("0.00"),
        recurring_insurance=Decimal("0.00"),
        recurring_other_fix=Decimal("0.00"),
        variable_total=Decimal("0.00"),
    )


def test_overview_vm_accepts_next_and_has_default_view_mode():
    cur = _p(2026, 1)
    nxt = _p(2026, 2)

    vm = OverviewVM(current=cur, next=nxt)  # default view_mode
    assert vm.view_mode
    assert vm.current == cur
    assert vm.next == nxt
    assert vm.nxt == nxt


def test_overview_vm_accepts_legacy_nxt_kw():
    cur = _p(2026, 1)
    nxt = _p(2026, 2)

    vm = OverviewVM(current=cur, nxt=nxt, view_mode="ALLOCATE_MONTHLY")
    assert vm.view_mode == "ALLOCATE_MONTHLY"
    assert vm.next == nxt
    assert vm.nxt == nxt
