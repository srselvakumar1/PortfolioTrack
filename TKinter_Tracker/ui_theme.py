#!/usr/bin/env python3
"""Central UI theme tokens and ttk styling.

Kept separate from `main.py` to avoid circular imports between
app entrypoint and individual views.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk


class ModernStyle:
    """Readable light theme with a modern, premium feel."""

    # Colors (Light)
    BG_PRIMARY = "#F8FAFC"        # App background
    BG_SECONDARY = "#FFFFFF"      # Cards / surfaces
    BG_TERTIARY = "#F1F5F9"       # Sidebar / headers

    ENTRY_BG = "#FFFFFF"

    ACCENT_PRIMARY = "#2563EB"    # Blue 600
    ACCENT_SECONDARY = "#16A34A"  # Green 600
    ACCENT_TERTIARY = "#D97706"   # Amber 600

    TEXT_PRIMARY = "#0F172A"      # Slate 900
    TEXT_SECONDARY = "#475569"    # Slate 600
    TEXT_TERTIARY = "#64748B"     # Slate 500
    TEXT_ON_ACCENT = "#FFFFFF"

    BORDER_COLOR = "#E5E7EB"      # Gray 200
    DIVIDER_COLOR = "#E2E8F0"     # Slate 200

    SUCCESS = ACCENT_SECONDARY
    WARNING = ACCENT_TERTIARY
    ERROR = "#DC2626"             # Red 600
    SALMON = "#FA8072"            # Salmon (for cancel/close actions)

    # Fonts
    FONT_FAMILY = (
        "Segoe UI" if sys.platform == "win32" else ("SF Pro Display" if sys.platform == "darwin" else "Ubuntu")
    )
    FONT_TITLE = (FONT_FAMILY, 18, "bold")
    FONT_HEADING = (FONT_FAMILY, 14, "bold")
    FONT_SUBHEADING = (FONT_FAMILY, 12, "bold")
    FONT_BODY = (FONT_FAMILY, 11)
    FONT_SMALL = (FONT_FAMILY, 10)

    # Layout / component tokens ("stylesheet" layer)
    NAV_ITEM_BG = BG_TERTIARY
    NAV_ITEM_HOVER_BG = BG_SECONDARY
    NAV_ITEM_ACTIVE_BG = ACCENT_PRIMARY
    NAV_ITEM_ACTIVE_FG = TEXT_ON_ACCENT
    NAV_ITEM_FG = TEXT_PRIMARY
    NAV_ITEM_PADX = 14
    NAV_ITEM_PADY = 10
    NAV_ITEM_OUTER_PADX = 10

    KPI_CARD_HEIGHT = 118
    KPI_ACCENT_BAR_HEIGHT = 4
    DASH_GRID_CARD_HEIGHT = 240

    @classmethod
    def apply_theme(cls, root: tk.Tk) -> None:
        """Apply the light theme to ttk widgets and the root window."""
        style = ttk.Style(root)
        # Force a consistent ttk base theme when possible.
        try:
            themes = set(style.theme_names() or [])
            if "clam" in themes:
                style.theme_use("clam")
            else:
                # Keep whatever the platform chose (e.g. aqua on macOS).
                print(f"Warning: ttk theme 'clam' not available. Available: {sorted(themes)}")
        except Exception as e:
            print(f"Warning: could not set ttk theme to 'clam': {e}")

        style.configure("TFrame", background=cls.BG_PRIMARY)
        style.configure(
            "TLabel",
            background=cls.BG_PRIMARY,
            foreground=cls.TEXT_PRIMARY,
            font=cls.FONT_BODY,
        )
        style.configure("TButton", font=cls.FONT_BODY)

        style.configure(
            "TEntry",
            fieldbackground=cls.ENTRY_BG,
            foreground=cls.TEXT_PRIMARY,
            insertcolor=cls.TEXT_PRIMARY,
            bordercolor=cls.BORDER_COLOR,
            lightcolor=cls.BORDER_COLOR,
            darkcolor=cls.BORDER_COLOR,
        )

        style.configure(
            "TCombobox",
            fieldbackground=cls.ENTRY_BG,
            foreground=cls.TEXT_PRIMARY,
            background=cls.ENTRY_BG,
            arrowcolor=cls.TEXT_SECONDARY,
            bordercolor=cls.BORDER_COLOR,
        )

        # Treeview readability
        style.configure(
            "Treeview",
            background=cls.BG_SECONDARY,
            foreground=cls.TEXT_PRIMARY,
            fieldbackground=cls.BG_SECONDARY,
            bordercolor=cls.BORDER_COLOR,
            rowheight=32,
            font=(cls.FONT_FAMILY, 11),
        )
        style.configure(
            "Treeview.Heading",
            background=cls.ACCENT_PRIMARY,
            foreground=cls.TEXT_ON_ACCENT,
            font=(cls.FONT_FAMILY, 11, "bold"),
            relief="flat",
        )
        try:
            style.map(
                "Treeview.Heading",
                background=[("active", cls.ACCENT_PRIMARY)],
                foreground=[("active", cls.TEXT_ON_ACCENT)],
            )
        except Exception:
            pass
        style.map(
            "Treeview",
            background=[("selected", cls.ACCENT_PRIMARY)],
            foreground=[("selected", cls.TEXT_ON_ACCENT)],
        )

        root.configure(bg=cls.BG_PRIMARY)
