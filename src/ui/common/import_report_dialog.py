# ui/common/import_report_dialog.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from src.ui.common.controls import create_treeview_with_scrollbars
from src.ui.common.i18n import tr, trf


_DATASET_KEY_MAP: dict[str, str] = {
    "accounts": "io.dataset.accounts",
    "employers/pay_rules": "io.dataset.employers_pay_rules",
    "income_fixed": "io.dataset.income_fixed",
    "income_hourly": "io.dataset.income_hourly",
    "expense_recurring": "io.dataset.expense_recurring",
    "expense_variable": "io.dataset.expense_variable",
    "loans/loan_events": "io.dataset.loans_loan_events",
}

_SHEET_KEY_MAP: dict[str, str] = {
    "Konten": "io.sheet.accounts",
    "Infos": "io.sheet.info",
    "Einkommen_Fest": "io.sheet.income_fixed",
    "Einkommen_Stunden": "io.sheet.income_hourly",
    "Abo & Verträge": "io.sheet.expense_recurring",
    "Sonder_Ausgaben": "io.sheet.expense_variable",
    "Kredit": "io.sheet.loans",
}


def _maybe_tr(map_: dict[str, str], value: str) -> str:
    key = map_.get(value)
    return tr(key) if key else value


class ImportReportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, issues: list[dict], title: str | None = None):
        super().__init__(parent)
        self.title(title or tr("io.import.report.title"))
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self._issues = issues or []

        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        ttk.Label(
            root,
            text=trf("io.import.report.summary", count=len(self._issues)),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        cols = ["dataset", "sheet", "row", "field", "value", "message"]
        headings = {
            "dataset": tr("common.dataset"),
            "sheet": tr("common.sheet"),
            "row": tr("common.row"),
            "field": tr("common.field"),
            "value": tr("common.value"),
            "message": tr("common.message"),
        }
        self.tree, frame = create_treeview_with_scrollbars(root, columns=cols, headings=headings, height=16)
        frame.pack(fill="both", expand=True)

        for idx, it in enumerate(self._issues, start=1):
            ds = _maybe_tr(_DATASET_KEY_MAP, str(it.get("dataset", "") or ""))
            sh = _maybe_tr(_SHEET_KEY_MAP, str(it.get("sheet", "") or ""))
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    ds,
                    sh,
                    it.get("row", ""),
                    it.get("field", ""),
                    it.get("value", ""),
                    it.get("message", ""),
                ),
            )

        btns = ttk.Frame(root)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text=tr("io.import.report.copy_all"), command=self._copy_all).pack(side="left")
        ttk.Button(btns, text=tr("common.close"), command=self.destroy).pack(side="right")

        self.update_idletasks()
        self.minsize(900, 420)

    def _copy_all(self) -> None:
        if not self._issues:
            messagebox.showinfo(tr("common.notice"), tr("io.import.report.none_to_copy"))
            return

        header = "\t".join(
            [
                tr("common.dataset"),
                tr("common.sheet"),
                tr("common.row"),
                tr("common.field"),
                tr("common.value"),
                tr("common.message"),
            ]
        )
        lines = [header]

        for it in self._issues:
            ds = _maybe_tr(_DATASET_KEY_MAP, str(it.get("dataset", "") or ""))
            sh = _maybe_tr(_SHEET_KEY_MAP, str(it.get("sheet", "") or ""))
            lines.append(
                f"{ds}\t{sh}\t{it.get('row','')}\t{it.get('field','')}\t{it.get('value','')}\t{it.get('message','')}"
            )

        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        messagebox.showinfo(tr("io.import.report.copied.title"), tr("io.import.report.copied.msg"))
