# src/ui/common/scroll_area.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollArea(ttk.Frame):
    """Scrollable container (vertical + horizontal) with safe mousewheel bindings.

    Usage:
        area = ScrollArea(parent)
        area.pack(fill="both", expand=True)
        content = area.content  # put widgets in here

    Design goals:
    - Works on small monitors: if content is larger than viewport, scrollbars appear.
    - MouseWheel scrolls the area when cursor is inside the area.
    - Does NOT hijack scrolling for Treeview/Text/Listbox widgets (they keep their own scroll behavior).
    - No bind-all leakage: bindings are installed on <Enter> and removed on <Leave>/<Destroy>.
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)

        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self._vbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._hbar = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)

        self._canvas.configure(yscrollcommand=self._vbar.set, xscrollcommand=self._hbar.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vbar.grid(row=0, column=1, sticky="ns")
        self._hbar.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.content = ttk.Frame(self._canvas)
        self._window_id = self._canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._on_content_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Scoped mousewheel: only active when cursor is inside the scroll area
        self._canvas.bind("<Enter>", self._bind_mousewheel, add="+")
        self._canvas.bind("<Leave>", self._unbind_mousewheel, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._mw_bound = False

    # -------------------- Layout helpers --------------------
    def _on_content_configure(self, _evt=None) -> None:
        self._update_scrollregion()
        self._update_scrollbars_visibility()

    def _on_canvas_configure(self, _evt=None) -> None:
        # Expand content to at least canvas size but never shrink below requested size
        try:
            req_w = self.content.winfo_reqwidth()
        except Exception:
            req_w = 1
        canvas_w = max(1, self._canvas.winfo_width())
        new_w = max(canvas_w, req_w)
        self._canvas.itemconfigure(self._window_id, width=new_w)
        self._update_scrollregion()
        self._update_scrollbars_visibility()

    def _update_scrollregion(self) -> None:
        try:
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        except Exception:
            pass

    def _update_scrollbars_visibility(self) -> None:
        # Show/hide scrollbars depending on content size
        try:
            bbox = self._canvas.bbox("all")
            if not bbox:
                return
            x0, y0, x1, y1 = bbox
            content_w = max(0, x1 - x0)
            content_h = max(0, y1 - y0)
            canvas_w = max(1, self._canvas.winfo_width())
            canvas_h = max(1, self._canvas.winfo_height())
        except Exception:
            return

        if content_h <= canvas_h + 2:
            self._vbar.grid_remove()
        else:
            self._vbar.grid()

        if content_w <= canvas_w + 2:
            self._hbar.grid_remove()
        else:
            self._hbar.grid()

    # -------------------- Mousewheel --------------------
    @staticmethod
    def _is_descendant(widget: tk.Widget | None, ancestor: tk.Widget) -> bool:
        w = widget
        while w is not None:
            if w == ancestor:
                return True
            try:
                w = w.master  # type: ignore[assignment]
            except Exception:
                return False
        return False

    @staticmethod
    def _should_ignore_widget(widget: tk.Widget) -> bool:
        # Let typical scrollable widgets keep their own wheel behavior.
        try:
            cls = widget.winfo_class()
        except Exception:
            return False
        return cls in {"Treeview", "Text", "Listbox"}

    def _bind_mousewheel(self, _evt=None) -> None:
        if self._mw_bound:
            return
        root = self.winfo_toplevel()
        root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        root.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel, add="+")
        self._mw_bound = True

    def _unbind_mousewheel(self, _evt=None) -> None:
        if not self._mw_bound:
            return
        root = self.winfo_toplevel()
        try:
            root.unbind_all("<MouseWheel>")
        except Exception:
            pass
        try:
            root.unbind_all("<Shift-MouseWheel>")
        except Exception:
            pass
        self._mw_bound = False

    def _on_destroy(self, _evt=None) -> None:
        self._unbind_mousewheel()

    def _on_mousewheel(self, event) -> None:
        # Only scroll if cursor is inside this scroll area
        w = self.winfo_toplevel().winfo_containing(event.x_root, event.y_root)
        if not self._is_descendant(w, self):
            return
        if w is not None and self._should_ignore_widget(w):
            return
        delta = int(getattr(event, "delta", 0))
        if delta == 0:
            return
        step = -1 if delta > 0 else 1
        try:
            self._canvas.yview_scroll(step, "units")
        except Exception:
            pass

    def _on_shift_mousewheel(self, event) -> None:
        w = self.winfo_toplevel().winfo_containing(event.x_root, event.y_root)
        if not self._is_descendant(w, self):
            return
        if w is not None and self._should_ignore_widget(w):
            return
        delta = int(getattr(event, "delta", 0))
        if delta == 0:
            return
        step = -1 if delta > 0 else 1
        try:
            self._canvas.xview_scroll(step, "units")
        except Exception:
            pass
