#!/usr/bin/env python3
"""Small UI utilities shared across views.

Kept separate to avoid circular imports.
"""

from __future__ import annotations

import tkinter as tk


def center_window(win: tk.Misc, *, parent: tk.Misc | None = None) -> None:
    """Center a Tk/Toplevel window.

    If parent is provided, centers relative to the parent window.
    Otherwise centers on screen.
    """

    try:
        win.update_idletasks()
    except Exception:
        pass

    # Determine the window's target size.
    try:
        width = int(win.winfo_width())
        height = int(win.winfo_height())
        if width <= 1 or height <= 1:
            width = int(win.winfo_reqwidth())
            height = int(win.winfo_reqheight())
    except Exception:
        width, height = 800, 600

    # Determine the reference rect.
    if parent is not None:
        try:
            parent.update_idletasks()
        except Exception:
            pass
        try:
            px = int(parent.winfo_rootx())
            py = int(parent.winfo_rooty())
            pw = int(parent.winfo_width())
            ph = int(parent.winfo_height())
            if pw <= 1 or ph <= 1:
                pw = int(parent.winfo_reqwidth())
                ph = int(parent.winfo_reqheight())
            x = px + (pw // 2) - (width // 2)
            y = py + (ph // 2) - (height // 2)
        except Exception:
            parent = None

    if parent is None:
        try:
            sw = int(win.winfo_screenwidth())
            sh = int(win.winfo_screenheight())
            x = (sw // 2) - (width // 2)
            y = (sh // 2) - (height // 2)
        except Exception:
            x, y = 50, 50

    # Clamp to visible screen area (basic safety).
    try:
        x = max(0, int(x))
        y = max(0, int(y))
    except Exception:
        x, y = 0, 0

    try:
        win.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass
