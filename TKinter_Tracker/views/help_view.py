"""
Help view for TKinter-based PTracker application.
"""

import tkinter as tk
from tkinter import ttk

from TKinter_Tracker.views.base_view import BaseView, _enable_canvas_mousewheel
from TKinter_Tracker.ui_theme import ModernStyle
from TKinter_Tracker.ui_widgets import ModernButton

class HelpView(BaseView):
    """Help and documentation view."""
    
    def build(self):
        """Build help documentation view (rich, sectioned like the Flet help page)."""

        self._help_font_scale = 0

        header_frame = tk.Frame(self, bg=ModernStyle.BG_PRIMARY, height=60)
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        left = tk.Frame(header_frame, bg=ModernStyle.BG_PRIMARY)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="❓ Help & Documentation", fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_TITLE).pack(anchor="w")
        tk.Label(left, text="Comprehensive documentation and formulas used in PTracker.", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_BODY).pack(anchor="w")

        right = tk.Frame(header_frame, bg=ModernStyle.BG_PRIMARY)
        right.pack(side="right")
        tk.Label(right, text="Text Size", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_SMALL).pack(side="left", padx=(0, 8))
        ModernButton(right, text="-", command=lambda: self._help_adjust_font(-1), bg=ModernStyle.BG_TERTIARY, fg=ModernStyle.TEXT_PRIMARY, canvas_bg=ModernStyle.BG_PRIMARY, width=42, height=34).pack(side="left", padx=(0, 6))
        ModernButton(right, text="+", command=lambda: self._help_adjust_font(1), bg=ModernStyle.BG_TERTIARY, fg=ModernStyle.TEXT_PRIMARY, canvas_bg=ModernStyle.BG_PRIMARY, width=42, height=34).pack(side="left")

        # Scrollable container
        canvas = tk.Canvas(self, bg=ModernStyle.BG_PRIMARY, highlightthickness=0)
        vscroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=15, pady=10)

        self._help_content = tk.Frame(canvas, bg=ModernStyle.BG_PRIMARY)
        cid = canvas.create_window((0, 0), window=self._help_content, anchor="nw")

        def _on_cfg(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(cid, width=canvas.winfo_width())

        self._help_content.bind("<Configure>", _on_cfg)
        canvas.bind("<Configure>", _on_cfg)

        # Mouse wheel scrolling over the help content
        _enable_canvas_mousewheel(canvas, include_widget=self._help_content)

        # Build content
        self._help_text_widgets: list[tk.Widget] = []
        self._help_title_widgets: list[tk.Widget] = []

        self._build_help_sections(self._help_content)
        self._help_apply_font_scale()

    def _help_adjust_font(self, delta: int) -> None:
        self._help_font_scale = max(-3, min(6, int(self._help_font_scale) + int(delta)))
        self._help_apply_font_scale()

    def _help_apply_font_scale(self) -> None:
        # Scale base fonts by +/- a few points.
        try:
            base = int(ModernStyle.FONT_BODY[1])
            small = int(ModernStyle.FONT_SMALL[1])
            heading = int(ModernStyle.FONT_SUBHEADING[1])
        except Exception:
            base, small, heading = 11, 10, 12
        s = int(self._help_font_scale)
        f_body = (ModernStyle.FONT_FAMILY, max(9, base + s))
        f_small = (ModernStyle.FONT_FAMILY, max(8, small + s))
        f_head = (ModernStyle.FONT_FAMILY, max(10, heading + s), "bold")

        for w in getattr(self, "_help_text_widgets", []):
            try:
                w.configure(font=f_body)
            except Exception:
                pass
        for w in getattr(self, "_help_title_widgets", []):
            try:
                w.configure(font=f_head)
            except Exception:
                pass

    def _help_card(self, parent: tk.Misc, title: str) -> tk.Frame:
        card = tk.Frame(parent, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        card.pack(fill="x", pady=(0, 12))
        title_lbl = tk.Label(card, text=title, fg=ModernStyle.ACCENT_PRIMARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_HEADING)
        title_lbl.pack(anchor="w", padx=12, pady=(10, 6))
        self._help_title_widgets.append(title_lbl)
        inner = tk.Frame(card, bg=ModernStyle.BG_SECONDARY)
        inner.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        return inner

    def _help_paragraph(self, parent: tk.Misc, text: str) -> tk.Label:
        lbl = tk.Label(
            parent,
            text=text,
            fg=ModernStyle.TEXT_SECONDARY,
            bg=ModernStyle.BG_SECONDARY,
            font=ModernStyle.FONT_BODY,
            justify="left",
            wraplength=1100,
        )
        lbl.pack(anchor="w", pady=(0, 8))
        self._help_text_widgets.append(lbl)
        return lbl

    def _help_item(self, parent: tk.Misc, title: str, desc: str) -> None:
        t = tk.Label(parent, text=title, fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING)
        t.pack(anchor="w", pady=(8, 2))
        self._help_title_widgets.append(t)
        self._help_paragraph(parent, desc)

    def _help_table(self, parent: tk.Misc, cols: list[str], rows: list[list[str]]) -> None:
        wrap = tk.Frame(parent, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        wrap.pack(fill="x", pady=(6, 0))

        grid = tk.Frame(wrap, bg=ModernStyle.BG_SECONDARY)
        grid.pack(fill="x", padx=10, pady=10)

        # Header
        for c, name in enumerate(cols):
            grid.grid_columnconfigure(c, weight=1, uniform="ht")
            h = tk.Label(grid, text=name, fg=ModernStyle.TEXT_ON_ACCENT, bg=ModernStyle.ACCENT_PRIMARY, font=ModernStyle.FONT_SMALL)
            h.grid(row=0, column=c, sticky="ew", padx=(0, 6 if c < len(cols) - 1 else 0))
            self._help_text_widgets.append(h)

        # Rows
        for r_i, r in enumerate(rows):
            bg = ModernStyle.BG_PRIMARY if (r_i % 2 == 0) else ModernStyle.BG_SECONDARY
            for c_i, val in enumerate(r):
                cell = tk.Label(grid, text=str(val), fg=ModernStyle.TEXT_SECONDARY, bg=bg, font=ModernStyle.FONT_SMALL, justify="left", wraplength=240)
                cell.grid(row=r_i + 1, column=c_i, sticky="ew", padx=(0, 6 if c_i < len(cols) - 1 else 0), pady=(4, 0))
                self._help_text_widgets.append(cell)

    def _build_help_sections(self, parent: tk.Misc) -> None:
        # Example data (mirrors the Flet help page)
        pnl_run_cols = ["Date", "Type", "Qty", "Price", "Current", "Running PnL"]
        pnl_run_rows = [
            ["2023-01-01", "BUY", "10", "₹100", "₹120", "+₹200"],
            ["2023-01-05", "BUY", "5", "₹110", "₹120", "+₹150"],
            ["Total", "-", "15", "₹103.33", "₹120", "+₹250"],
        ]

        pnl_real_cols = ["Date", "Action", "Qty", "Price", "Avg Cost", "Realized"]
        pnl_real_rows = [
            ["2023-01-01", "BUY", "10", "₹100", "-", "-"],
            ["2023-02-01", "SELL", "5", "₹150", "₹100", "+₹250"],
            ["Balance", "-", "5", "-", "₹100", "-"],
        ]

        cagr_cols = ["Year", "Investment", "Value", "Return", "CAGR"]
        cagr_rows = [
            ["Start", "₹10,000", "₹10,000", "-", "-"],
            ["Year 1", "₹10,000", "₹11,500", "15%", "15.0%"],
            ["Year 3", "₹10,000", "₹15,000", "50%", "14.47%"],
        ]

        iv_cols = ["Year", "Proj. EPS", "Disc. Factor", "Pres. Value"]
        iv_rows = [
            ["Base", "₹10.00", "1.000", "₹10.00"],
            ["Year 1", "₹11.20", "0.909", "₹10.18"],
            ["Year 5", "₹17.62", "0.621", "₹10.94"],
            ["TV", "₹264.30", "0.621", "₹164.13"],
            ["Total IV", "-", "-", "₹214.25"],
        ]

        fees_cols = ["Charge Name", "Rate / Logic", "Sample (₹1L Buy)"]
        fees_rows = [
            ["Brokerage", "Fixed ₹10", "₹10.00"],
            ["STT", "0.1% on Turnover", "₹100.00"],
            ["Stamp Duty", "0.015% (Buy)", "₹15.00"],
            ["SEBI", "Fixed ₹10", "₹10.00"],
            ["GST", "18% on (Brkg+SEBI)", "₹3.60"],
            ["Total Fees", "-", "₹138.60"],
        ]

        calc_levels_cols = ["Calculation", "Level", "Reason"]
        calc_levels_rows = [
            ["Running Quantity", "Transaction", "Evolves with each trade"],
            ["Cost Basis", "Transaction", "Accumulates through each trade"],
            ["Realized PnL", "Transaction", "Only occurs per SELL"],
            ["Fee Accumulation", "Transaction", "Sums stored fees per trade"],
            ["Cash Flows", "Transaction", "Collected per trade for XIRR"],
            ["Average Price", "Holding", "Computed from final totals"],
            ["Unrealized PnL", "Holding", "Uses current market price + final state"],
            ["Running PnL", "Holding", "Combines all realized + unrealized"],
            ["XIRR/CAGR", "Holding", "Uses complete cash flow history"],
            ["Total Fees", "Holding", "Sum of all trade fees"],
        ]

        shortcuts_cols = ["Shortcut", "Platform", "Action"]
        shortcuts_rows = [
            ["Ctrl+N", "Windows/Linux | Cmd+N on Mac", "Add new trade (Trade Entry)"],
            ["Esc", "All Platforms", "Close open dialogs"],
            ["Ctrl+K", "Windows/Linux | Cmd+K on Mac", "Focus symbol search (Holdings/Trade History)"],
        ]

        # Sections
        s = self._help_card(parent, "Keyboard Shortcuts & Quick Navigation")
        self._help_item(s, "Available Shortcuts", "Use these keyboard shortcuts to navigate faster and perform common actions without clicking.")
        self._help_table(s, shortcuts_cols, shortcuts_rows)

        s = self._help_card(parent, "Project Overview")
        self._help_item(
            s,
            "About PTracker",
            "PTracker is a portfolio management tool for tracking holdings and trades, computing performance metrics, and surfacing actionable insights.",
        )

        s = self._help_card(parent, "Application Views")
        self._help_item(s, "Dashboard", "High-level financial summary with key metrics, performers, actionable insights, and tax harvesting opportunities.")
        self._help_item(s, "Holdings", "Current portfolio holdings. Double-click a row to open drilldown and view the trade history for that holding.")
        self._help_item(s, "Trade Entry", "Add new trades manually or import a CSV. Duplicate entries are skipped during bulk import.")
        self._help_item(s, "Trade History", "Search and filter every transaction. Supports copy/export, edit on double-click, and bulk deletion.")

        s = self._help_card(parent, "Metric Formulas & Tabular Examples")
        self._help_item(s, "Avg Purchase Price", "Calculated as: Total Cost Basis / Current Quantity. Fees are included in the cost basis for BUY trades and deducted for SELL trades.")
        self._help_item(s, "Running (Unrealized) PnL", "(Current Price - Avg Purchase Price) × Current Quantity.")
        self._help_table(s, pnl_run_cols, pnl_run_rows)
        self._help_item(s, "Running PnL", "Combines realized gains (SELL) and unrealized gains/losses from open quantity.")
        self._help_table(s, pnl_real_cols, pnl_real_rows)
        self._help_item(s, "Overall CAGR", "(Ending Value / Beginning Value)^(1/Years) - 1")
        self._help_table(s, cagr_cols, cagr_rows)
        self._help_item(s, "Overall XIRR", "Annualized return using dated cashflows (IRR/XIRR).")

        s = self._help_card(parent, "Calculation Levels: Transaction vs Holding")
        self._help_item(s, "Understanding Where Calculations Happen", "Some values evolve per trade, while others are computed after aggregating a holding.")
        self._help_table(s, calc_levels_cols, calc_levels_rows)

        s = self._help_card(parent, "Intrinsic Value & Action Signals")
        self._help_item(s, "Intrinsic Value (DCF)", "Discounted Cash Flow style intrinsic value based on projected EPS and discount factors.")
        self._help_table(s, iv_cols, iv_rows)
        self._help_item(s, "ACCUMULATE", "Current Market Price < 70% of Intrinsic Value.")
        self._help_item(s, "REDUCE", "Current Market Price > 110% of Intrinsic Value.")
        self._help_item(s, "HOLD", "Price is between 70% and 110% of Intrinsic Value.")

        s = self._help_card(parent, "Trade Fees (Indian Equity Rules)")
        self._help_item(s, "Charge Breakdown", "A simplified fee table for delivery trades.")
        self._help_table(s, fees_cols, fees_rows)
        self._help_item(s, "DP Charges", "DP charges typically apply on SELL delivery trades.")

        s = self._help_card(parent, "Market Data & Sync")
        self._help_item(s, "Data Source", "Market data is fetched via yfinance. Indian symbols may be suffixed with .NS or .BO.")
        self._help_item(s, "Syncing", "Market data sync runs in the background to keep the UI responsive.")
