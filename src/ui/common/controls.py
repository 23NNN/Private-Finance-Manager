# src/ui/common/controls.py
from __future__ import annotations

import tkinter as tk
from datetime import date
from decimal import Decimal, InvalidOperation
from tkinter import ttk
from typing import Any, Callable


_ARROW_UP = "▲"
_ARROW_DOWN = "▼"


def _to_decimal(s: str) -> Decimal | None:
    """Best-effort parsing for German formatted numbers (e.g. '1.234,56')."""
    s = (s or "").strip()
    if not s:
        return None
    # strip currency-ish
    s = s.replace("€", "").replace("\u00a0", " ").strip()
    # normalize
    s = s.replace(" ", "")
    # common thousands separator handling
    # if both '.' and ',' exist -> '.' thousands, ',' decimal
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    # keep leading minus
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _to_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    # ISO format only (YYYY-MM-DD)
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _sort_key(v: str) -> tuple[int, object]:
    """Return a mixed-type comparable key.

    Order:
      0 -> numbers
      1 -> dates
      2 -> strings
      3 -> empty
    """
    if v is None:
        return (3, "")
    s = str(v).strip()
    if not s:
        return (3, "")
    d = _to_decimal(s)
    if d is not None:
        return (0, d)
    dt = _to_date(s)
    if dt is not None:
        return (1, dt)
    return (2, s.casefold())


def _get_tree_state(tree: ttk.Treeview) -> dict[str, Any]:
    st = getattr(tree, "_fm_sort_state", None)
    if not isinstance(st, dict):
        st = {"col": None, "reverse": False}
        setattr(tree, "_fm_sort_state", st)
    return st


def _get_base_headings(tree: ttk.Treeview) -> dict[str, str]:
    base = getattr(tree, "_fm_heading_base", None)
    if not isinstance(base, dict):
        base = {c: tree.heading(c).get("text", c) for c in tree["columns"]}
        setattr(tree, "_fm_heading_base", base)
    return base


def _apply_heading_arrows(tree: ttk.Treeview, sort_col: str | None, reverse: bool) -> None:
    base = _get_base_headings(tree)
    for c in tree["columns"]:
        txt = base.get(c, c)
        if c == sort_col:
            txt = f"{txt} {_ARROW_DOWN if reverse else _ARROW_UP}"
        tree.heading(c, text=txt)


def _snapshot_default_order(tree: ttk.Treeview) -> None:
    if getattr(tree, "_fm_default_order", None) is None:
        setattr(tree, "_fm_default_order", list(tree.get_children("")))


def _reset_sort(tree: ttk.Treeview) -> None:
    base = _get_base_headings(tree)
    order = getattr(tree, "_fm_default_order", None)

    if isinstance(order, list) and order:
        # only move items that still exist
        cur = set(tree.get_children(""))
        for idx, iid in enumerate([i for i in order if i in cur]):
            tree.move(iid, "", idx)

    st = _get_tree_state(tree)
    st["col"] = None
    st["reverse"] = False

    for c in tree["columns"]:
        tree.heading(c, text=base.get(c, c), command=lambda col=c, t=tree: _sort_tree(t, col))


def _sort_tree(tree: ttk.Treeview, col: str) -> None:
    _snapshot_default_order(tree)
    st = _get_tree_state(tree)

    if st.get("col") == col:
        st["reverse"] = not bool(st.get("reverse"))
    else:
        st["col"] = col
        st["reverse"] = False

    items = list(tree.get_children(""))
    items_with_keys = [(tree.set(iid, col), iid) for iid in items]
    items_with_keys.sort(key=lambda x: _sort_key(x[0]), reverse=bool(st["reverse"]))

    for idx, (_val, iid) in enumerate(items_with_keys):
        tree.move(iid, "", idx)

    _apply_heading_arrows(tree, st["col"], bool(st["reverse"]))


def _bind_header_double_click_to_reset(tree: ttk.Treeview) -> None:
    def on_double(event: tk.Event) -> str | None:
        try:
            region = tree.identify_region(event.x, event.y)
        except Exception:
            return None
        if region == "heading":
            _reset_sort(tree)
            return "break"
        return None

    tree.bind("<Double-1>", on_double, add=True)


def _wrap_delete_to_reset_state(tree: ttk.Treeview) -> None:
    if getattr(tree, "_fm_delete_wrapped", False):
        return
    orig_delete = tree.delete

    def delete_wrapper(*items: Any) -> None:
        orig_delete(*items)
        if not tree.get_children(""):
            setattr(tree, "_fm_default_order", None)
            st = _get_tree_state(tree)
            st["col"] = None
            st["reverse"] = False
            _apply_heading_arrows(tree, None, False)

    tree.delete = delete_wrapper  # type: ignore[assignment]
    setattr(tree, "_fm_delete_wrapped", True)


def create_treeview_with_scrollbars(
    parent: tk.Widget,
    columns: list[str] | None = None,
    headings: dict[str, str] | None = None,
    *args: Any,
    show: str = "headings",
    height: int = 12,
    sortable: bool = True,
    **tree_kwargs: Any,
) -> tuple[ttk.Treeview, ttk.Frame]:
    """
    Creates a ttk.Treeview in a frame with vertical + horizontal scrollbars.

    Additional (default):
    - Click on column header sorts (ascending/descending).
    - Arrows (▲/▼) indicate sort direction.
    - Double-click on column header resets sorting (original order).

    Backwards compatible:
    - create_treeview_with_scrollbars(parent, columns, headings, height=...)
    - create_treeview_with_scrollbars(parent, columns=..., headings=..., height=...)
    """
    # Support legacy positional args: (parent, columns, headings)
    if columns is None and len(args) >= 1:
        columns = args[0]
    if headings is None and len(args) >= 2:
        headings = args[1]

    if columns is None or headings is None:
        raise TypeError("create_treeview_with_scrollbars requires 'columns' and 'headings'.")

    frame = ttk.Frame(parent)

    tree = ttk.Treeview(frame, columns=columns, show=show, height=height, **tree_kwargs)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")

    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)

    for c in columns:
        tree.heading(c, text=headings.get(c, c))
        tree.column(c, width=120, anchor="w", stretch=True)

    if sortable:
        # store base headings once, then attach sorting
        setattr(tree, "_fm_heading_base", {c: headings.get(c, c) for c in columns})
        _wrap_delete_to_reset_state(tree)
        for c in columns:
            tree.heading(c, command=lambda col=c, t=tree: _sort_tree(t, col))
        _bind_header_double_click_to_reset(tree)

    return tree, frame
