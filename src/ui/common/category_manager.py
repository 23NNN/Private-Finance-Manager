# ui/common/category_manager.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from src.application.services.reference_data_service import ReferenceDataService
from src.ui.common.controls import create_treeview_with_scrollbars
from src.ui.common.dialogs import FieldSpec, FormDialog
from src.ui.common.i18n import tr


_GROUP_KEY_BY_CODE: dict[str, str] = {
    "FIX": "category.group.fix",
    "VARIABLE": "category.group.variable",
    "LOAN": "category.group.loan",
}


def _group_label(code: str) -> str:
    key = _GROUP_KEY_BY_CODE.get(code)
    return tr(key) if key else code


class CategoryManagerDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, ref_service: ReferenceDataService):
        super().__init__(parent)
        self.title(tr("category_manager.title"))
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self._ref = ref_service

        group_items = [("FIX", _group_label("FIX")), ("VARIABLE", _group_label("VARIABLE")), ("LOAN", _group_label("LOAN"))]
        self._group_labels = [label for _code, label in group_items]
        self._label_to_group = {label: code for code, label in group_items}

        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        btns = ttk.Frame(root)
        btns.pack(fill="x", pady=(0, 8))

        ttk.Button(btns, text=tr("common.new"), command=self._new).pack(side="left")
        ttk.Button(btns, text=tr("common.edit"), command=self._edit).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text=tr("common.delete"), command=self._delete).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text=tr("common.close"), command=self.destroy).pack(side="right")

        cols = ["name", "group"]
        heads = {"name": tr("common.name"), "group": tr("common.group")}
        self.tree, frame = create_treeview_with_scrollbars(root, columns=cols, headings=heads, height=14)
        frame.pack(fill="both", expand=True)

        self.tree.bind(
            "<Double-1>",
            lambda e: None if self.tree.identify_region(e.x, e.y) == "heading" else self._edit(),
            add="+",
        )
        self.tree.bind("<Delete>", lambda _e: self._delete())

        self._refresh()

        self.update_idletasks()
        self.minsize(520, 420)

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for c in self._ref.list_categories():
            self.tree.insert("", "end", iid=str(c.id), values=(c.name, _group_label(c.group)))

    def _new(self) -> None:
        fields = [
            FieldSpec("name", tr("common.name"), "entry", required=True, width=40),
            FieldSpec("group_ui", tr("common.group"), "combo", required=True, values=self._group_labels),
        ]
        dlg = FormDialog(self, tr("category_manager.dialog.new.title"), fields, initial={"group_ui": _group_label("VARIABLE")})
        data = dlg.show()
        if not data:
            return
        try:
            group_ui = str(data.get("group_ui", "")).strip()
            group = self._label_to_group.get(group_ui, "VARIABLE")
            self._ref.upsert_category(str(data["name"]).strip(), group, None)
            self._refresh()
        except Exception as e:
            messagebox.showerror(tr("common.error"), str(e))

    def _edit(self) -> None:
        cid = self._selected_id()
        if not cid:
            messagebox.showinfo(tr("common.notice"), tr("category_manager.msg.select_one"))
            return

        cats = {c.id: c for c in self._ref.list_categories()}
        c = cats.get(cid)
        if not c:
            return

        fields = [
            FieldSpec("name", tr("common.name"), "entry", required=True, width=40),
            FieldSpec("group_ui", tr("common.group"), "combo", required=True, values=self._group_labels),
        ]
        dlg = FormDialog(
            self,
            tr("category_manager.dialog.edit.title"),
            fields,
            initial={"name": c.name, "group_ui": _group_label(c.group)},
        )
        data = dlg.show()
        if not data:
            return
        try:
            group_ui = str(data.get("group_ui", "")).strip()
            group = self._label_to_group.get(group_ui, c.group)
            self._ref.upsert_category(str(data["name"]).strip(), group, cid)
            self._refresh()
        except Exception as e:
            messagebox.showerror(tr("common.error"), str(e))

    def _delete(self) -> None:
        cid = self._selected_id()
        if not cid:
            messagebox.showinfo(tr("common.notice"), tr("category_manager.msg.select_one"))
            return

        if not messagebox.askyesno(tr("common.irreversible_delete"), tr("category_manager.msg.confirm_delete")):
            return

        try:
            self._ref.delete_category(cid)
            self._refresh()
        except Exception as e:
            messagebox.showerror(tr("common.error"), str(e))
