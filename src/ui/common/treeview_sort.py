# finanzmanager/ui/common/treeview_sort.py
from __future__ import annotations

from decimal import Decimal
from typing import Callable


def parse_str(value: str) -> str:
    return (value or "").strip().lower()


def parse_int(value: str) -> int:
    s = (value or "").strip()
    try:
        return int(s)
    except Exception:
        return 0


def parse_money_de(value: str) -> Decimal:
    """
    Expects e.g.: '123,45' or '1.234,56' (optional).
    """
    s = (value or "").strip()
    if not s:
        return Decimal("0")
    s = s.replace("€", "").replace(" ", "")
    s = s.replace(".", "")      # thousands separator
    s = s.replace(",", ".")     # decimal comma
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def parse_pct_de(value: str) -> Decimal:
    """
    Expects e.g.: '12,34' or '12,34 %' (optional).
    """
    s = (value or "").strip()
    if not s:
        return Decimal("0")
    s = s.replace("%", "").replace(" ", "")
    s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def make_treeview_sortable(
    tree,
    parsers: dict[str, Callable[[str], object]],
    *,
    show_arrows: bool = True,
) -> None:
    """
    Makes a ttk.Treeview sortable by clicking on a column header.
    Optionally shows ▲/▼ in the header.

    parsers: map of column name -> parser that produces a sort key from the cell text.
    """

    sort_state = {"col": None, "desc": False}
    base_headers = {c: tree.heading(c, "text") for c in tree["columns"]}

    def _set_header_arrows(active_col: str | None, desc: bool) -> None:
        if not show_arrows:
            return
        for c in tree["columns"]:
            txt = base_headers.get(c, "")
            if active_col == c:
                txt = f"{txt} {'▼' if desc else '▲'}"
            tree.heading(c, text=txt)

    def sort_by(col: str) -> None:
        if sort_state["col"] == col:
            sort_state["desc"] = not sort_state["desc"]
        else:
            sort_state["col"] = col
            sort_state["desc"] = False

        desc = bool(sort_state["desc"])
        parser = parsers.get(col, parse_str)

        children = list(tree.get_children(""))
        if not children:
            _set_header_arrows(sort_state["col"], desc)
            return

        selected = set(tree.selection())

        def key_func(iid: str):
            try:
                raw = tree.set(iid, col)
            except Exception:
                raw = ""
            return parser(raw)

        children.sort(key=key_func, reverse=desc)

        for idx, iid in enumerate(children):
            tree.move(iid, "", idx)

        for iid in selected:
            if tree.exists(iid):
                tree.selection_add(iid)

        _set_header_arrows(sort_state["col"], desc)

    for c in tree["columns"]:
        tree.heading(c, command=lambda col=c: sort_by(col))

    _set_header_arrows(None, False)
