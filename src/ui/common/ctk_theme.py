# src/ui/common/ctk_theme.py
"""Apply TTK styles matching the active CustomTkinter appearance mode.

Call ``apply_for_mode(root, mode)`` once at startup and whenever the
appearance mode changes.  ``mode`` is "dark", "light", or "system".
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Colour palettes matched to CTk 5.x dark/light defaults
_DARK: dict[str, str] = {
    "bg": "#212121",
    "frame_bg": "#2b2b2b",
    "entry_bg": "#343638",
    "fg": "#dce4ee",
    "heading_bg": "#3b3b3b",
    "selected_bg": "#1f6aa5",
    "selected_fg": "#ffffff",
    "border": "#565b5e",
    "disabled_fg": "#6b6b6b",
}

_LIGHT: dict[str, str] = {
    "bg": "#f0f0f0",
    "frame_bg": "#ebebeb",
    "entry_bg": "#ffffff",
    "fg": "#1a1a1a",
    "heading_bg": "#d8d8d8",
    "selected_bg": "#3b8ed0",
    "selected_fg": "#ffffff",
    "border": "#aaaaaa",
    "disabled_fg": "#888888",
}


def _resolve_palette(mode: str) -> dict[str, str]:
    try:
        import customtkinter as ctk
        resolved = ctk.get_appearance_mode()
    except Exception:
        resolved = mode
    if mode.lower() == "system":
        mode = resolved
    return _DARK if mode.lower() == "dark" else _LIGHT


def apply_for_mode(root: tk.Widget, mode: str) -> None:
    """Apply TTK styles and canvas backgrounds for the given appearance mode."""
    p = _resolve_palette(mode)
    style = ttk.Style(root)
    _apply_ttk_style(style, p)
    _apply_canvas_bg(root, p["bg"])


def _apply_ttk_style(style: ttk.Style, p: dict[str, str]) -> None:
    style.configure("Treeview",
        background=p["frame_bg"], foreground=p["fg"],
        fieldbackground=p["frame_bg"], bordercolor=p["border"], relief="flat",
    )
    style.configure("Treeview.Heading",
        background=p["heading_bg"], foreground=p["fg"], relief="flat",
    )
    style.map("Treeview",
        background=[("selected", p["selected_bg"]), ("focus", p["selected_bg"])],
        foreground=[("selected", p["selected_fg"]), ("focus", p["selected_fg"])],
    )

    style.configure("TLabelframe", background=p["frame_bg"], bordercolor=p["border"])
    style.configure("TLabelframe.Label", background=p["frame_bg"], foreground=p["fg"])

    style.configure("TFrame", background=p["frame_bg"])

    style.configure("TLabel", background=p["frame_bg"], foreground=p["fg"])

    style.configure("TButton",
        background=p["entry_bg"], foreground=p["fg"], bordercolor=p["border"],
    )

    style.configure("TCombobox",
        fieldbackground=p["entry_bg"], background=p["entry_bg"], foreground=p["fg"],
        arrowcolor=p["fg"], bordercolor=p["border"], selectbackground=p["selected_bg"],
        selectforeground=p["selected_fg"],
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", p["entry_bg"]), ("disabled", p["frame_bg"])],
        foreground=[("disabled", p["disabled_fg"])],
    )

    style.configure("TSpinbox",
        fieldbackground=p["entry_bg"], background=p["entry_bg"], foreground=p["fg"],
        arrowcolor=p["fg"], bordercolor=p["border"],
    )

    style.configure("TScrollbar",
        background=p["entry_bg"], troughcolor=p["bg"],
        arrowcolor=p["fg"], bordercolor=p["border"],
    )

    style.configure("TSeparator", background=p["border"])

    style.configure("TCheckbutton",
        background=p["frame_bg"], foreground=p["fg"],
    )
    style.map("TCheckbutton",
        background=[("active", p["frame_bg"])],
        foreground=[("disabled", p["disabled_fg"])],
    )

    style.configure("TEntry",
        fieldbackground=p["entry_bg"], foreground=p["fg"], bordercolor=p["border"],
        insertcolor=p["fg"],
    )


def _apply_canvas_bg(widget: tk.Widget, bg: str) -> None:
    """Recursively set background of Canvas widgets that are children of TFrame (ScrollArea canvases)."""
    try:
        cls = widget.winfo_class()
        if cls == "Canvas":
            parent_cls = getattr(widget.master, "winfo_class", lambda: "")() if widget.master else ""
            if parent_cls == "TFrame":
                widget.configure(bg=bg)  # type: ignore[arg-type]
        for child in widget.winfo_children():
            _apply_canvas_bg(child, bg)
    except Exception:
        pass
