# src/ui/common/dialogs.py
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from src.ui.common.i18n import tr
from typing import Callable


@dataclass(frozen=True)
class FieldSpec:
    """
    Field descriptor for FormDialog.

    Convention:
    - kind="entry"  -> single-line
    - kind="combo"  -> read-only Combobox
    - kind="spin"   -> Spinbox
    - kind="check"  -> Checkbox
    - kind="text"   -> default SINGLE-LINE (like entry), only multi-line (Text) when height > 1

    validator:
      - Optional: validator(str) -> object
      - Raises an exception on invalid value (dialog then shows the error).
    """

    key: str
    label: str
    kind: str  # entry|combo|spin|check|text
    required: bool = False
    values: list[str] | None = None
    from_: int | None = None
    to: int | None = None
    width: int = 28
    height: int = 1  # default 1 -> prevents oversized text boxes
    validator: Callable[[str], object] | None = None


class FormDialog(tk.Toplevel):
    """
    Modal form dialog.

    Fixes:
    - Scroll handling is robust: no permanent bind_all (prevents errors when scrolling after close).
    - Vertical + horizontal scrollbar on the canvas (in case content is wider than the window).
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        fields: list[FieldSpec] | None = None,
        initial: dict[str, object] | None = None,
        *,
        specs: list[FieldSpec] | None = None,
    ):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()

        self._fields = fields if fields is not None else specs
        if not self._fields:
            raise ValueError("FormDialog requires `fields` or `specs`.")

        self._vars: dict[str, object] = {}
        self._widgets: dict[str, tk.Widget] = {}
        self._result: dict[str, object] | None = None
        self._shown = False

        self._mw_bound = False  # mousewheel binding active?

        initial = initial or {}

        # ---------- Layout Root ----------
        root = ttk.Frame(self, padding=10)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Scroll Container
        sc = ttk.Frame(root)
        sc.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        canvas = tk.Canvas(sc, highlightthickness=0)
        vbar = ttk.Scrollbar(sc, orient="vertical", command=canvas.yview)
        hbar = ttk.Scrollbar(sc, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")

        sc.rowconfigure(0, weight=1)
        sc.columnconfigure(0, weight=1)

        inner = ttk.Frame(canvas)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_config(_e=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except tk.TclError:
                # Canvas already destroyed
                return

        def _on_canvas_config(e):
            # Dynamic: content adapts to the width -> less horizontal scrolling needed.
            try:
                canvas.itemconfigure(inner_id, width=e.width)
                canvas.configure(scrollregion=canvas.bbox("all"))
            except tk.TclError:
                return

        inner.bind("<Configure>", _on_inner_config)
        canvas.bind("<Configure>", _on_canvas_config)

        def _mousewheel_y(event):
            # Windows: event.delta is typically in 120-step increments; trackpads may deliver smaller values.
            try:
                delta = int(getattr(event, "delta", 0) or 0)
                if delta == 0:
                    return
                step = -1 if delta > 0 else 1
                canvas.yview_scroll(step, "units")
            except tk.TclError:
                return

        def _mousewheel_x(event):
            try:
                delta = int(getattr(event, "delta", 0) or 0)
                if delta == 0:
                    return
                step = -1 if delta > 0 else 1
                canvas.xview_scroll(step, "units")
            except tk.TclError:
                return

        def _bind_mousewheel(_e=None):
            if self._mw_bound:
                return
            # bind_all is fine here, but ONLY while the mouse pointer is over the canvas
            self.bind_all("<MouseWheel>", _mousewheel_y)
            self.bind_all("<Shift-MouseWheel>", _mousewheel_x)
            self._mw_bound = True

        def _unbind_mousewheel(_e=None):
            if not self._mw_bound:
                return
            try:
                self.unbind_all("<MouseWheel>")
                self.unbind_all("<Shift-MouseWheel>")
            finally:
                self._mw_bound = False

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        # Ensure no global binding remains after the dialog is closed
        self.bind("<Destroy>", lambda _e: _unbind_mousewheel())

        # ---------- Build Fields ----------
        inner.columnconfigure(1, weight=1)

        row = 0
        for f in self._fields:
            ttk.Label(inner, text=f.label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)

            if f.kind == "entry":
                v = tk.StringVar(value=str(initial.get(f.key, "") or ""))
                w = ttk.Entry(inner, textvariable=v, width=f.width)
                self._vars[f.key] = v

            elif f.kind == "combo":
                v = tk.StringVar(value=str(initial.get(f.key, "") or ""))
                w = ttk.Combobox(inner, textvariable=v, values=f.values or [], width=f.width, state="readonly")
                self._vars[f.key] = v

            elif f.kind == "spin":
                v = tk.StringVar(value=str(initial.get(f.key, "") or ""))
                w = ttk.Spinbox(inner, from_=f.from_ or 0, to=f.to or 9999, textvariable=v, width=f.width)
                self._vars[f.key] = v

            elif f.kind == "check":
                v = tk.BooleanVar(value=bool(initial.get(f.key, False)))
                w = ttk.Checkbutton(inner, variable=v)
                self._vars[f.key] = v

            elif f.kind == "text":
                # default height==1 -> like Entry (single-line)
                if (f.height or 1) > 1:
                    w = tk.Text(inner, width=f.width, height=f.height)
                    w.insert("1.0", str(initial.get(f.key, "") or ""))
                    self._vars[f.key] = w
                else:
                    v = tk.StringVar(value=str(initial.get(f.key, "") or ""))
                    w = ttk.Entry(inner, textvariable=v, width=f.width)
                    self._vars[f.key] = v

            else:
                raise ValueError(f"Unknown field kind: {f.kind}")

            w.grid(row=row, column=1, sticky="ew", pady=4)
            self._widgets[f.key] = w
            row += 1

        # Error label (non-scroll, always visible)
        self._error = ttk.Label(root, text="", foreground="red")
        self._error.grid(row=1, column=0, sticky="w", pady=(8, 0))

        # Buttons (non-scroll, always visible)
        btns = ttk.Frame(root)
        btns.grid(row=2, column=0, sticky="e", pady=(12, 0))

        self._ok = ttk.Button(btns, text=tr("common.ok"), command=self._on_ok)
        self._ok.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text=tr("common.cancel"), command=self._on_cancel).grid(row=0, column=1)

        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self._on_cancel())

        # live validation bindings
        for f in self._fields:
            w = self._widgets[f.key]

            if isinstance(w, (ttk.Entry, ttk.Spinbox)):
                w.bind("<KeyRelease>", lambda _e: self._validate())
                w.bind("<FocusOut>", lambda _e: self._validate())

            if isinstance(w, ttk.Combobox):
                w.bind("<<ComboboxSelected>>", lambda _e: self._validate())
                w.bind("<FocusOut>", lambda _e: self._validate())

            if isinstance(w, ttk.Checkbutton):
                v = self._vars[f.key]
                if isinstance(v, tk.BooleanVar):
                    v.trace_add("write", lambda *_: self._validate())

            if isinstance(w, tk.Text):
                w.bind("<KeyRelease>", lambda _e: self._validate())
                w.bind("<FocusOut>", lambda _e: self._validate())

        # Size: stable + scroll
        if len(self._fields) >= 10:
            self.geometry("560x650")
        else:
            self.geometry("560x420")

        self._validate()
        try:
            self._widgets[self._fields[0].key].focus_set()
        except Exception:
            pass

    def _read_value(self, f: FieldSpec) -> object:
        v = self._vars[f.key]
        if isinstance(v, tk.Text):
            return v.get("1.0", "end").strip()
        if isinstance(v, tk.StringVar):
            return v.get().strip()
        if isinstance(v, tk.BooleanVar):
            return bool(v.get())
        return ""

    def _validate(self) -> None:
        for f in self._fields:
            val = self._read_value(f)

            if f.required and f.kind in ("entry", "combo", "spin", "text") and str(val).strip() == "":
                self._error.config(text=tr('error.required').format(field=f.label))
                self._ok.state(["disabled"])
                return

            if f.validator and str(val).strip() != "":
                try:
                    f.validator(str(val))
                except Exception:
                    self._error.config(text=tr('error.invalid').format(field=f.label))
                    self._ok.state(["disabled"])
                    return

        self._error.config(text="")
        self._ok.state(["!disabled"])

    def _on_ok(self) -> None:
        self._validate()
        if "disabled" in self._ok.state():
            return

        data: dict[str, object] = {}
        for f in self._fields:
            data[f.key] = self._read_value(f)

        self._result = data
        try:
            self.destroy()
        finally:
            # Safety: in case <Destroy> didn't fire in time
            if self._mw_bound:
                try:
                    self.unbind_all("<MouseWheel>")
                    self.unbind_all("<Shift-MouseWheel>")
                except Exception:
                    pass
                self._mw_bound = False

    def _on_cancel(self) -> None:
        self._result = None
        try:
            self.destroy()
        finally:
            if self._mw_bound:
                try:
                    self.unbind_all("<MouseWheel>")
                    self.unbind_all("<Shift-MouseWheel>")
                except Exception:
                    pass
                self._mw_bound = False

    def show(self) -> dict[str, object] | None:
        if not self._shown:
            self._shown = True
            try:
                self.wait_window(self)
            except Exception:
                pass
        return self._result

    @property
    def result(self) -> dict[str, object] | None:
        return self.show()
