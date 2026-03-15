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


def add_treeview_copy_menu(tv) -> None:
    """Attach a right-click context menu to a ttk.Treeview for copying data."""
    try:
        from tkinter import Menu
        from tkinter import ttk
        
        # We need a reference to the main app clipboard, so we can use tv's master
        app = tv.winfo_toplevel()
        
        menu = Menu(tv, tearoff=0)
        
        def _copy_row():
            try:
                selected_item = tv.selection()[0]
                values = tv.item(selected_item, "values")
                if values:
                    text = "\t".join(str(v).replace("₹", "").replace(",", "").replace("%", "").strip() for v in values)
                    app.clipboard_clear()
                    app.clipboard_append(text)
            except IndexError:
                pass
                
        def _copy_all():
            try:
                cols = list(tv["columns"])
                lines = ["\t".join(cols)]
                for iid in tv.get_children():
                    vals = tv.item(iid, "values")
                    lines.append("\t".join(str(v).replace("₹", "").replace(",", "").replace("%", "").strip() for v in vals))
                text = "\n".join(lines)
                app.clipboard_clear()
                app.clipboard_append(text)
            except Exception:
                pass
                
        menu.add_command(label="📋 Copy Selected Row", command=_copy_row)
        menu.add_command(label="📝 Copy All Rows", command=_copy_all)
        
        def _show_menu(event):
            # Select the row under cursor before showing menu
            iid = tv.identify_row(event.y)
            if iid:
                tv.selection_set(iid)
            menu.tk_popup(event.x_root, event.y_root)
            
        # Bind right click (Button-2 on Mac, Button-3 on Windows)
        tv.bind("<Button-2>", _show_menu)
        tv.bind("<Button-3>", _show_menu)
    except Exception:
        pass


def treeview_sort_column(tv, col: str, reverse: bool) -> None:
    """Sort a ttk.Treeview clicking on its header, dealing with numeric and text values."""
    try:
        from views.base_view import _apply_zebra_stripes
    except ImportError:
        _apply_zebra_stripes = None

    try:
        # Get all children (since we may have items not fully loaded, though usually they are)
        # We also need to get the values to sort by.
        l = [(tv.set(k, col), k) for k in tv.get_children('')]

        def convert(val):
            # Try parsing as float for numeric sorting
            try:
                # Remove currency, percentage, commas, and other non-numeric symbols
                v = str(val).replace('₹', '').replace('%', '').replace(',', '').strip()
                if not v or v in ("—", "-", "N/A"):
                    return float('-inf') if not reverse else float('inf')
                return float(v)
            except ValueError:
                # Fallback: case-insensitive string sorting
                return str(val).lower()

        l.sort(key=lambda t: convert(t[0]), reverse=reverse)

        # Rearrange items in sorted positions
        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)

        # Reverse sort direction for next click
        tv.heading(col, command=lambda: treeview_sort_column(tv, col, not reverse))

        # Optionally apply group-based zebra striping
        try:
            current_group_val = None
            current_stripe = "odd" # Start with white
            
            for item in tv.get_children(''):
                val_str = str(tv.set(item, col))
                if val_str != current_group_val:
                    current_group_val = val_str
                    current_stripe = "even" if current_stripe == "odd" else "odd"
                
                tags = tv.item(item, 'tags')
                # Filter out old odd/even tags
                tags = [t for t in tags if t not in ('odd', 'even')]
                # Re-apply
                tags.append(current_stripe)
                tv.item(item, tags=tags)
        except Exception:
            pass

    except Exception as e:
        print(f"Sort Error on {col}: {e}")

