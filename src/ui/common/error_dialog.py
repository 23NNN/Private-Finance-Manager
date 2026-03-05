# ui/common/error_dialog.py
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from src.ui.common.i18n import tr, trf


def _open_path(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606
            return
        subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607
    except Exception:
        pass


def _open_in_explorer_select(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603,S607
            return
        _open_path(path)
    except Exception:
        pass


class ErrorDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        message: str,
        *,
        details: str | None = None,
        log_path: Path | None = None,
        db_path: Path | None = None,
        severity: str = "ERROR",  # "ERROR" | "WARN" | "INFO"
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self._details = details or ""
        self._details_visible = False
        self._log_path = log_path
        self._db_path = db_path

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        hdr = ttk.Frame(root)
        hdr.pack(fill="x")

        icon = "❌" if severity == "ERROR" else ("⚠️" if severity == "WARN" else "ℹ️")
        ttk.Label(hdr, text=icon, font=("Segoe UI", 18)).pack(side="left", padx=(0, 10))
        ttk.Label(hdr, text=message, justify="left", wraplength=720).pack(side="left", fill="x", expand=True)

        # Paths
        if log_path or db_path:
            pf = ttk.LabelFrame(root, text=tr("error.paths"))
            pf.pack(fill="x", pady=(10, 0))

            if db_path:
                row = ttk.Frame(pf)
                row.pack(fill="x", pady=2)
                ttk.Label(row, text=tr("error.database"), width=12).pack(side="left")
                e = ttk.Entry(row)
                e.insert(0, str(db_path))
                e.configure(state="readonly")
                e.pack(side="left", fill="x", expand=True, padx=(0, 6))
                ttk.Button(row, text=tr("common.open_in_explorer"), command=lambda: _open_in_explorer_select(db_path)).pack(side="left")

            if log_path:
                row = ttk.Frame(pf)
                row.pack(fill="x", pady=2)
                ttk.Label(row, text=tr("error.log"), width=12).pack(side="left")
                e = ttk.Entry(row)
                e.insert(0, str(log_path))
                e.configure(state="readonly")
                e.pack(side="left", fill="x", expand=True, padx=(0, 6))
                ttk.Button(row, text=tr("common.open_in_explorer"), command=lambda: _open_in_explorer_select(log_path)).pack(side="left")
                ttk.Button(row, text=tr("common.open_log"), command=lambda: _open_path(log_path)).pack(side="left", padx=(6, 0))

        # Details (collapsible)
        self._details_frame = ttk.LabelFrame(root, text=tr("error.details"))
        self._details_text = tk.Text(self._details_frame, height=14, wrap="none")
        self._details_text.insert("1.0", self._details.strip() or tr("error_dialog.no_details"))
        self._details_text.configure(state="disabled")
        self._details_text.pack(fill="both", expand=True, padx=6, pady=6)

        btns = ttk.Frame(root)
        btns.pack(fill="x", pady=(12, 0))

        self._toggle_btn = ttk.Button(btns, text=tr("common.show_details"), command=self._toggle_details)
        self._toggle_btn.pack(side="left")

        ttk.Button(btns, text=tr("common.copy"), command=self._copy_all).pack(side="left", padx=(6, 0))

        ttk.Button(btns, text=tr("common.ok"), command=self.destroy).pack(side="right")

        self.update_idletasks()
        self.minsize(760, 220)

    def _toggle_details(self) -> None:
        if not self._details_visible:
            self._details_frame.pack(fill="both", expand=True, pady=(10, 0))
            self._toggle_btn.configure(text=tr("common.hide_details"))
            self._details_visible = True
        else:
            self._details_frame.pack_forget()
            self._toggle_btn.configure(text=tr("common.show_details"))
            self._details_visible = False

    def _copy_all(self) -> None:
        chunks = []
        if self._db_path:
            chunks.append(trf("error_dialog.copy.db_label", path=self._db_path))
        if self._log_path:
            chunks.append(trf("error_dialog.copy.log_label", path=self._log_path))
        if self._details.strip():
            chunks.append(tr("error_dialog.copy.details_separator") + self._details.strip())
        text = "\n".join(chunks).strip() or tr("error_dialog.no_details_short")

        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass


def show_error(
    parent: tk.Widget,
    title: str,
    message: str,
    *,
    details: str | None = None,
    log_path: Path | None = None,
    db_path: Path | None = None,
) -> None:
    ErrorDialog(parent, title, message, details=details, log_path=log_path, db_path=db_path, severity="ERROR").wait_window()


def show_warning(
    parent: tk.Widget,
    title: str,
    message: str,
    *,
    details: str | None = None,
    log_path: Path | None = None,
    db_path: Path | None = None,
) -> None:
    ErrorDialog(parent, title, message, details=details, log_path=log_path, db_path=db_path, severity="WARN").wait_window()
