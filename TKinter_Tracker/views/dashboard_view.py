"""
Dashboard view for TKinter-based PTracker application.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime

from TKinter_Tracker.views.base_view import BaseView, _enable_canvas_mousewheel
from TKinter_Tracker.ui_theme import ModernStyle
from TKinter_Tracker.ui_widgets import ModernButton
from TKinter_Tracker.ui_utils import center_window

class DashboardView(BaseView):
    """Portfolio dashboard with summary metrics and overview."""
    
    def build(self):
        """Build dashboard UI (match Flet: KPI cards + performers + insights + harvesting)."""
        self._ui_built = False
        self._data_loaded = False
        self._refresh_inflight = False

        # Scroll container (dashboard has many cards)
        canvas = tk.Canvas(self, bg=ModernStyle.BG_PRIMARY, highlightthickness=0)
        vscroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._content = tk.Frame(canvas, bg=ModernStyle.BG_PRIMARY)
        self._content_id = canvas.create_window((0, 0), window=self._content, anchor="nw")

        def _on_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(self._content_id, width=canvas.winfo_width())

        self._content.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)

        # Mouse wheel scrolling over the dashboard content
        _enable_canvas_mousewheel(canvas, include_widget=self._content)

        # Header row
        header = tk.Frame(self._content, bg=ModernStyle.BG_PRIMARY)
        header.pack(fill="x", padx=18, pady=(18, 10))
        tk.Label(header, text="📊 Dashboard", fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_TITLE).pack(side="left")

        self.refresh_status = tk.Label(header, text="", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_SMALL)
        self.refresh_status.pack(side="right")
        self.refresh_btn = ModernButton(
            header,
            text="Refresh Market Data",
            command=self._on_refresh_market_data,
            icon_path="assets/icons/refresh.png",
            icon_subsample=2,
            bg=ModernStyle.ACCENT_TERTIARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=190,
            height=38,
        )
        self.refresh_btn.pack(side="right", padx=10)

        # KPI cards
        self.kpi_labels = {}
        self._kpi_cards = {}

        def _card(parent, title: str, key: str, *, color: str, metric_key: str | None, is_currency: bool = True):
            frame = tk.Frame(parent, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1, relief=tk.RAISED, bd=2)
            frame.pack_propagate(False)
            frame.grid_propagate(False)
            frame.configure(height=ModernStyle.KPI_CARD_HEIGHT)

            # Color accent bar for a more modern look.
            tk.Frame(frame, bg=color, height=ModernStyle.KPI_ACCENT_BAR_HEIGHT).pack(fill="x", side="top")
            
            # Icon + Title row
            title_row = tk.Frame(frame, bg=ModernStyle.BG_SECONDARY)
            title_row.pack(anchor="w", padx=12, pady=(10, 2), fill="x")
            
            # Icon mapping for KPI cards
            icon_map = {"total_value": "💰", "total_invested": "📊", "overall_pnl": "📈", "unrealized_pnl": "📉", "realized_pnl": "✓", "realized_loss": "✗", "overall_xirr": "🎯", "overall_cagr": "📊"}
            icon = icon_map.get(key, "•")
            tk.Label(title_row, text=icon, fg=color, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 18)).pack(side="left", padx=(0, 6))
            tk.Label(title_row, text=title, fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(side="left")
            
            val = tk.Label(frame, text="—", fg=color, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 22, "bold"))
            val.pack(anchor="w", padx=12, pady=(0, 10))
            self.kpi_labels[key] = val

            if metric_key:
                def _click(_e=None, t=title, mk=metric_key, cur=is_currency):
                    self._show_broker_breakdown(t, mk, is_currency=cur)
                def _hover_enter(_e=None):
                    frame.configure(bg=ModernStyle.BG_TERTIARY, relief=tk.RAISED, bd=3)
                def _hover_leave(_e=None):
                    frame.configure(bg=ModernStyle.BG_SECONDARY, relief=tk.RAISED, bd=2)
                frame.bind("<Button-1>", _click)  # Single click drill-down
                frame.bind("<Enter>", _hover_enter)
                frame.bind("<Leave>", _hover_leave)
                for w in (frame, val):
                    w.bind("<Button-1>", _click)
                    w.bind("<Enter>", _hover_enter)
                    w.bind("<Leave>", _hover_leave)
                frame.configure(cursor="hand2")
            return frame

        # row 1
        row1 = tk.Frame(self._content, bg=ModernStyle.BG_PRIMARY)
        row1.pack(fill="x", padx=18, pady=8)
        for i in range(3):
            row1.grid_columnconfigure(i, weight=1, uniform="kpi1")

        self._kpi_cards["total_value"] = _card(row1, "Total Value", "total_value", color=ModernStyle.ACCENT_PRIMARY, metric_key="total_value", is_currency=True)
        self._kpi_cards["total_invested"] = _card(row1, "Total Invested", "total_invested", color=ModernStyle.ACCENT_SECONDARY, metric_key="total_invested", is_currency=True)
        self._kpi_cards["overall_pnl"] = _card(row1, "Overall P&L", "overall_pnl", color=ModernStyle.ACCENT_TERTIARY, metric_key="overall_pnl", is_currency=True)

        self._kpi_cards["total_value"].grid(row=0, column=0, sticky="nsew", padx=6, pady=6, ipady=8)
        self._kpi_cards["total_invested"].grid(row=0, column=1, sticky="nsew", padx=6, pady=6, ipady=8)
        self._kpi_cards["overall_pnl"].grid(row=0, column=2, sticky="nsew", padx=6, pady=6, ipady=8)

        # row 2
        row2 = tk.Frame(self._content, bg=ModernStyle.BG_PRIMARY)
        row2.pack(fill="x", padx=18, pady=8)
        for i in range(5):
            row2.grid_columnconfigure(i, weight=1, uniform="kpi2")

        self._kpi_cards["unrealized_pnl"] = _card(row2, "Unrealized P&L", "unrealized_pnl", color=ModernStyle.ACCENT_PRIMARY, metric_key="unrealized_pnl", is_currency=True)
        self._kpi_cards["realized_pnl"] = _card(row2, "Realized P&L", "realized_pnl", color=ModernStyle.ACCENT_SECONDARY, metric_key="realized_pnl", is_currency=True)
        self._kpi_cards["realized_loss"] = _card(row2, "Realized Loss", "realized_loss", color=ModernStyle.ERROR, metric_key="realized_loss", is_currency=True)
        self._kpi_cards["overall_xirr"] = _card(row2, "Overall XIRR", "overall_xirr", color=ModernStyle.ACCENT_TERTIARY, metric_key="overall_xirr", is_currency=False)
        self._kpi_cards["overall_cagr"] = _card(row2, "Overall CAGR", "overall_cagr", color=ModernStyle.ACCENT_TERTIARY, metric_key="overall_cagr", is_currency=False)

        keys2 = ["unrealized_pnl", "realized_pnl", "realized_loss", "overall_xirr", "overall_cagr"]
        for c, k in enumerate(keys2):
            self._kpi_cards[k].grid(row=0, column=c, sticky="nsew", padx=6, pady=6, ipady=8)

        # Performers + insights cards (two rows, two columns)
        grid = tk.Frame(self._content, bg=ModernStyle.BG_PRIMARY)
        grid.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        grid.grid_columnconfigure(0, weight=1, uniform="p")
        grid.grid_columnconfigure(1, weight=1, uniform="p")
        grid.grid_rowconfigure(0, weight=1, uniform="p")
        grid.grid_rowconfigure(1, weight=1, uniform="p")

        self.top_card = tk.Frame(grid, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        self.worst_card = tk.Frame(grid, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        self.insights_card = tk.Frame(grid, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        self.harvest_card = tk.Frame(grid, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)

        # Keep cards visually consistent while still allowing expansion.
        for card in (self.top_card, self.worst_card, self.insights_card, self.harvest_card):
            card.grid_propagate(False)
            card.configure(height=ModernStyle.DASH_GRID_CARD_HEIGHT)

        self.top_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.worst_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        self.insights_card.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.harvest_card.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)

        def _section(frame: tk.Frame, title: str):
            tk.Label(frame, text=title, fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).pack(anchor="w", padx=12, pady=(10, 6))
            body = tk.Frame(frame, bg=ModernStyle.BG_SECONDARY)
            body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            return body

        self.top_body = _section(self.top_card, "Top Performers")
        self.worst_body = _section(self.worst_card, "Worst Performers")
        self.insights_body = _section(self.insights_card, "Actionable Insights")
        self.harvest_body = _section(self.harvest_card, "Tax Harvesting Ops")

        self._ui_built = True
    
    def load_data(self):
        """Load dashboard data (engine metrics + performers + insights + harvesting)."""
        if getattr(self, "_data_loaded", False):
            return
        self._data_loaded = True

        def _bg():
            try:
                from TKinter_Tracker.common.engine import get_dashboard_metrics, get_top_worst_performers, get_actionable_insights, get_tax_harvesting_opportunities
                metrics = get_dashboard_metrics()
                performers = get_top_worst_performers(10)
                insights = get_actionable_insights()
                harvesting = get_tax_harvesting_opportunities(500.0)
                self.after(0, lambda: self._apply_payload(metrics, performers, insights, harvesting))
            except Exception as e:
                print(f"Dashboard load error: {e}")

        threading.Thread(target=_bg, daemon=True).start()
    
    def _apply_payload(self, metrics: dict, performers: dict, insights: list, harvesting: list) -> None:
        def _money(v: float) -> str:
            return f"₹{float(v or 0.0):,.2f}"

        def _pct(v: float) -> str:
            return f"{float(v or 0.0):,.2f}%"

        # KPI values
        try:
            self.kpi_labels["total_value"].config(text=_money(metrics.get("total_value", 0.0)))
            self.kpi_labels["total_invested"].config(text=_money(metrics.get("total_invested", 0.0)))

            pnl = float(metrics.get("overall_pnl", 0.0) or 0.0)
            self.kpi_labels["overall_pnl"].config(text=_money(pnl), fg=ModernStyle.SUCCESS if pnl >= 0 else ModernStyle.ERROR)

            upnl = float(metrics.get("unrealized_pnl", 0.0) or 0.0)
            self.kpi_labels["unrealized_pnl"].config(text=_money(upnl), fg=ModernStyle.SUCCESS if upnl >= 0 else ModernStyle.ERROR)

            rpnl = float(metrics.get("realized_pnl", 0.0) or 0.0)
            self.kpi_labels["realized_pnl"].config(text=_money(rpnl), fg=ModernStyle.SUCCESS if rpnl >= 0 else ModernStyle.ERROR)

            rloss = float(metrics.get("realized_loss", 0.0) or 0.0)
            self.kpi_labels["realized_loss"].config(text=_money(rloss), fg=ModernStyle.ERROR)

            xirr = float(metrics.get("overall_xirr", 0.0) or 0.0)
            self.kpi_labels["overall_xirr"].config(text=_pct(xirr), fg=ModernStyle.SUCCESS if xirr >= 0 else ModernStyle.ERROR)

            cagr = float(metrics.get("overall_cagr", 0.0) or 0.0)
            self.kpi_labels["overall_cagr"].config(text=_pct(cagr), fg=ModernStyle.SUCCESS if cagr >= 0 else ModernStyle.ERROR)
        except Exception:
            pass

        # Lists
        self._render_performers(self.top_body, performers.get("top", []) or [], is_top=True)
        self._render_performers(self.worst_body, performers.get("worst", []) or [], is_top=False)
        self._render_simple_list(self.insights_body, insights or [], kind="insight")
        self._render_simple_list(self.harvest_body, harvesting or [], kind="harvest")

    def _clear_frame(self, frame: tk.Frame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    def _render_performers(self, frame: tk.Frame, data: list, *, is_top: bool) -> None:
        self._clear_frame(frame)
        data = (data or [])[:10]

        if not data:
            tk.Label(frame, text="No data available.", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY).pack(anchor="w")
            return
        
        base_color = ModernStyle.SUCCESS if is_top else ModernStyle.ERROR
        for i, item in enumerate(data):
            sym = str(item.get("symbol", ""))
            pnl = float(item.get("pnl", 0.0) or 0.0)
            pnl_pct = float(item.get("pnl_pct", 0.0) or 0.0)
            invested = float(item.get("invested", 1.0) or 1.0)
            
            # Calculate ROI
            roi = (pnl / invested * 100.0) if invested > 0 else 0.0
            
            # Color intensity based on magnitude
            if abs(pnl) > 50000:
                row_color = ModernStyle.SUCCESS if pnl >= 0 else ModernStyle.ERROR
            else:
                row_color = ModernStyle.ACCENT_PRIMARY
            
            # Compact row with less padding
            row = tk.Frame(frame, bg=ModernStyle.BG_SECONDARY, relief=tk.FLAT, bd=0)
            row.pack(fill="x", pady=1)  # Was pady=4 - reduced
            
            # Left side: Ranking badge + Symbol (more compact)
            left = tk.Frame(row, bg=ModernStyle.BG_SECONDARY)
            left.pack(side="left", padx=6, pady=4)  # Was padx=10, pady=8 - reduced
            
            # Ranking badge with emoji for top 3 (larger font)
            badge_emoji = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, f"#{i+1}")
            badge_color = {0: "#FFD700", 1: "#C0C0C0", 2: "#CD7F32"}.get(i, ModernStyle.BG_TERTIARY)
            badge_fg = "#000" if i < 3 else ModernStyle.TEXT_PRIMARY
            tk.Label(left, text=badge_emoji, fg=badge_fg, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 12, "bold")).pack(side="left", padx=(0, 4))
            
            # Symbol (larger font)
            tk.Label(left, text=sym, fg=ModernStyle.ACCENT_PRIMARY, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 12, "bold")).pack(side="left")
            
            # Right side: Values (compact)
            right = tk.Frame(row, bg=ModernStyle.BG_SECONDARY)
            right.pack(side="right", padx=6, pady=4)  # Was padx=8, pady=6 - reduced
            
            # Trending arrow (larger font)
            arrow = "↑" if pnl >= 0 else "↓"
            arrow_color = ModernStyle.SUCCESS if pnl >= 0 else ModernStyle.ERROR
            tk.Label(right, text=arrow, fg=arrow_color, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 13, "bold")).pack(side="left", padx=(0, 3))
            
            # Values: Format as compact (50K instead of 50000) - larger font
            pnl_display = f"₹{abs(pnl)/1000:.0f}K" if abs(pnl) >= 1000 else f"₹{pnl:,.0f}"
            values_text = f"{pnl_display} ({roi:+.1f}%)"
            tk.Label(right, text=values_text, fg=row_color, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 11)).pack(side="left")

            # Trade drilldown on SINGLE CLICK (was Double-1)
            try:
                row.bind("<Button-1>", lambda _e=None, s=sym: self._open_trade_drilldown(s))
                for w in row.winfo_children():
                    w.bind("<Button-1>", lambda _e=None, s=sym: self._open_trade_drilldown(s))
                # Hover effect
                def _hover_enter(event, r=row):
                    r.configure(bg=ModernStyle.BG_TERTIARY, relief=tk.FLAT, bd=0)
                def _hover_leave(event, r=row):
                    r.configure(bg=ModernStyle.BG_SECONDARY, relief=tk.FLAT, bd=0)
                row.bind("<Enter>", _hover_enter)
                row.bind("<Leave>", _hover_leave)
                for w in row.winfo_children():
                    w.bind("<Enter>", _hover_enter)
                    w.bind("<Leave>", _hover_leave)
                row.configure(cursor="hand2")
            except Exception:
                pass
            
            # Subtle divider (skip last row)
            if i != len(data) - 1:
                tk.Frame(frame, bg=ModernStyle.DIVIDER_COLOR, height=1).pack(fill="x", pady=0)

    def _render_simple_list(self, frame: tk.Frame, data: list, *, kind: str) -> None:
        self._clear_frame(frame)
        if not data:
            tk.Label(frame, text="No data available.", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY).pack(anchor="w")
            return

        # Special formatting for Tax Harvesting (structured rows)
        if kind == "harvest":
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                sym = str(item.get("symbol", "")).strip()
                loss = float(item.get("unrealized_loss", 0.0) or 0.0)
                qty = item.get("qty", "")
                avg = float(item.get("avg_price", 0.0) or 0.0)

                broker = str(item.get("broker", "") or "").strip()

                row = tk.Frame(frame, bg=ModernStyle.BG_SECONDARY, relief=tk.RAISED, bd=1)
                row.pack(fill="x", pady=3)

                top_line = tk.Frame(row, bg=ModernStyle.BG_SECONDARY)
                top_line.pack(fill="x", padx=8, pady=(6, 2))
                
                # Loss icon
                tk.Label(top_line, text="⚠️", fg=ModernStyle.ERROR, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 12)).pack(side="left", padx=(0, 6))
                tk.Label(
                    top_line,
                    text=sym or "—",
                    fg=ModernStyle.ACCENT_PRIMARY,
                    bg=ModernStyle.BG_SECONDARY,
                    font=ModernStyle.FONT_SUBHEADING,
                ).pack(side="left")
                tk.Label(
                    top_line,
                    text=f"₹{loss:,.2f}",
                    fg=ModernStyle.ERROR if loss < 0 else ModernStyle.SUCCESS,
                    bg=ModernStyle.BG_SECONDARY,
                    font=(ModernStyle.FONT_FAMILY, 11, "bold"),
                ).pack(side="right")

                tk.Label(
                    row,
                    text=f"Qty {qty} @ ₹{avg:,.2f}",
                    fg=ModernStyle.TEXT_SECONDARY,
                    bg=ModernStyle.BG_SECONDARY,
                    font=ModernStyle.FONT_SMALL,
                ).pack(anchor="w", padx=8, pady=(0, 6))

                # Trade drilldown on double-click (prefer broker if present)
                try:
                    def _hover_enter(event, r=row):
                        r.configure(bg=ModernStyle.BG_TERTIARY, relief=tk.RAISED, bd=2)
                    def _hover_leave(event, r=row):
                        r.configure(bg=ModernStyle.BG_SECONDARY, relief=tk.RAISED, bd=1)
                    row.bind("<Double-1>", lambda _e=None, s=sym, b=broker: self._open_trade_drilldown(s, broker=b or None))
                    row.bind("<Enter>", _hover_enter)
                    row.bind("<Leave>", _hover_leave)
                    for w in row.winfo_children():
                        w.bind("<Double-1>", lambda _e=None, s=sym, b=broker: self._open_trade_drilldown(s, broker=b or None))
                        w.bind("<Enter>", _hover_enter)
                        w.bind("<Leave>", _hover_leave)
                    row.configure(cursor="hand2")
                except Exception:
                    pass

                if i != len(data) - 1:
                    tk.Frame(frame, bg=ModernStyle.DIVIDER_COLOR, height=1).pack(fill="x", pady=1)
            return

        # Special formatting for Actionable Insights
        if kind == "insight":
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    text = str(item)
                    tk.Label(frame, text=f"• {text}", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY, justify="left", wraplength=720).pack(anchor="w", pady=2)
                    continue

                sym = str(item.get("symbol", "")).strip()
                signal = str(item.get("signal", "") or "").strip().upper()
                iv = float(item.get("iv", 0.0) or 0.0)
                cp = float(item.get("current_price", 0.0) or 0.0)
                diff_pct = ((iv - cp) / cp * 100.0) if cp else 0.0

                # Signal styling with icons
                signal_icon = "📈" if signal == "ACCUMULATE" else ("📉" if signal == "REDUCE" else "⏸️")
                chip_bg = ModernStyle.SUCCESS if signal == "ACCUMULATE" else (ModernStyle.WARNING if signal == "REDUCE" else ModernStyle.BG_TERTIARY)
                chip_fg = ModernStyle.TEXT_ON_ACCENT if signal in ("ACCUMULATE", "REDUCE") else ModernStyle.TEXT_SECONDARY

                row = tk.Frame(frame, bg=ModernStyle.BG_SECONDARY, relief=tk.RAISED, bd=1)
                row.pack(fill="x", pady=3)

                top_line = tk.Frame(row, bg=ModernStyle.BG_SECONDARY)
                top_line.pack(fill="x", padx=8, pady=(6, 2))
                
                # Signal icon + Symbol
                tk.Label(top_line, text=signal_icon, fg=chip_bg, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 12)).pack(side="left", padx=(0, 6))
                tk.Label(top_line, text=sym or "—", fg=ModernStyle.ACCENT_PRIMARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).pack(side="left")
                
                # Signal badge
                tk.Label(
                    top_line,
                    text=f" {signal_icon} {signal} ",
                    fg=chip_fg,
                    bg=chip_bg,
                    font=(ModernStyle.FONT_FAMILY, 9, "bold"),
                    padx=6,
                    pady=2,
                    relief=tk.RAISED,
                    bd=1,
                ).pack(side="right")

                # Details: IV, Current, Gap %
                detail_text = f"IV ₹{iv:,.0f} • Curr ₹{cp:,.0f} • Gap {diff_pct:+.1f}%"
                tk.Label(
                    row,
                    text=detail_text,
                    fg=ModernStyle.TEXT_SECONDARY,
                    bg=ModernStyle.BG_SECONDARY,
                    font=ModernStyle.FONT_SMALL,
                ).pack(anchor="w", padx=8, pady=(0, 6))

                # Trade drilldown on double-click
                try:
                    def _hover_enter(event, r=row):
                        r.configure(bg=ModernStyle.BG_TERTIARY, relief=tk.RAISED, bd=2)
                    def _hover_leave(event, r=row):
                        r.configure(bg=ModernStyle.BG_SECONDARY, relief=tk.RAISED, bd=1)
                    row.bind("<Double-1>", lambda _e=None, s=sym: self._open_trade_drilldown(s))
                    row.bind("<Enter>", _hover_enter)
                    row.bind("<Leave>", _hover_leave)
                    for w in row.winfo_children():
                        w.bind("<Double-1>", lambda _e=None, s=sym: self._open_trade_drilldown(s))
                        w.bind("<Enter>", _hover_enter)
                        w.bind("<Leave>", _hover_leave)
                    row.configure(cursor="hand2")
                except Exception:
                    pass

                if i != len(data) - 1:
                    tk.Frame(frame, bg=ModernStyle.DIVIDER_COLOR, height=1).pack(fill="x", pady=1)
            return

        # Default: defensive bullet list for other cards
        for i, item in enumerate(data):
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                text = str(item.get("text") or item.get("message") or item)
            else:
                text = str(item)
            tk.Label(frame, text=f"• {text}", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY, justify="left", wraplength=720).pack(anchor="w", pady=2)
            if i != len(data) - 1:
                tk.Frame(frame, bg=ModernStyle.DIVIDER_COLOR, height=1).pack(fill="x", pady=(2, 2))

    def _open_trade_drilldown(self, symbol: str, *, broker: str | None = None) -> None:
        symbol = (symbol or "").strip()
        if not symbol:
            return

        top = tk.Toplevel(self)
        top.title(f"Trade Drilldown - {symbol}")
        top.configure(bg=ModernStyle.BG_PRIMARY)
        top.geometry("980x560")

        try:
            top.transient(self.winfo_toplevel())
        except Exception:
            pass
        try:
            center_window(top, parent=self.winfo_toplevel())
        except Exception:
            pass

        hdr = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        hdr.pack(fill="x", padx=16, pady=14)
        title_row = tk.Frame(hdr, bg=ModernStyle.BG_PRIMARY)
        title_row.pack(fill="x")
        tk.Label(title_row, text=symbol, fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_TITLE).pack(side="left", anchor="w")

        tk.Label(
            hdr,
            text=f"Broker: {broker}" if broker else "Broker: All",
            fg=ModernStyle.TEXT_SECONDARY,
            bg=ModernStyle.BG_PRIMARY,
            font=ModernStyle.FONT_BODY,
        ).pack(anchor="w")

        body = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        act = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        act.pack(fill="x", pady=(0, 8))

        cols = ("Date", "Trade ID", "Type", "Qty", "Price ₹", "Fees ₹", "Run Qty", "AvgCost ₹", "Running PnL ₹", "Broker")
        table = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        table.pack(fill="both", expand=True)

        tv = ttk.Treeview(table, columns=cols, show="headings", height=16)
        widths = [100, 90, 60, 70, 90, 80, 80, 95, 120, 120]
        for c, w in zip(cols, widths):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor="w")

        def _copy():
            try:
                lines = ["\t".join(cols)]
                for iid in tv.get_children():
                    vals = tv.item(iid, "values")
                    lines.append("\t".join(str(v) for v in vals))
                self.clipboard_clear()
                self.clipboard_append("\n".join(lines))
                messagebox.showinfo("Drilldown", "Copied trades to clipboard.")
            except Exception as e:
                messagebox.showerror("Drilldown", f"Failed to copy: {e}")

        ModernButton(
            act,
            text="Copy Trades",
            command=_copy,
            bg=ModernStyle.ACCENT_PRIMARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=130,
            height=36,
        ).pack(side="left")

        ModernButton(
            act,
            text="Close",
            command=lambda: top.destroy(),
            bg=ModernStyle.SALMON,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=92,
            height=36,
        ).pack(side="right")

        vsb = ttk.Scrollbar(table, orient="vertical", command=tv.yview)
        hsb = ttk.Scrollbar(table, orient="horizontal", command=tv.xview)
        tv.configure(yscroll=vsb.set, xscroll=hsb.set)
        tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)

        def _load():
            try:
                from TKinter_Tracker.common.data_cache import TradeHistoryFilters
                if self.app_state is not None and hasattr(self.app_state, "data_cache"):
                    cache = self.app_state.data_cache
                else:
                    from TKinter_Tracker.common.data_cache import DataCache
                    cache = DataCache()
                    cache.refresh_from_db()

                f = TradeHistoryFilters(
                    broker=(broker if broker else "All"),
                    symbol_like=symbol,
                    trade_type="All",
                    start_date=None,
                    end_date=None,
                )
                df, _ = cache.get_tradehistory_filtered(f)
            except Exception:
                df = None

            def _apply():
                for it in tv.get_children():
                    tv.delete(it)
                if df is None or getattr(df, "empty", True):
                    return
                for r in df.itertuples(index=False):
                    rtype = str(getattr(r, "type", "")).upper()
                    qty = float(getattr(r, "qty", 0.0) or 0.0)
                    price = float(getattr(r, "price", 0.0) or 0.0)
                    fee = float(getattr(r, "fee", 0.0) or 0.0)
                    run_qty = float(getattr(r, "run_qty", 0.0) or 0.0)
                    avg_cost = float(getattr(r, "avg_cost", 0.0) or 0.0)
                    rpnl = float(getattr(r, "running_pnl", 0.0) or 0.0)
                    vals = (
                        str(getattr(r, "date", "")),
                        str(getattr(r, "trade_id", "")),
                        rtype,
                        f"{qty:g}",
                        f"₹{price:,.2f}",
                        f"₹{fee:,.2f}",
                        f"{run_qty:g}",
                        f"₹{avg_cost:,.2f}",
                        f"₹{rpnl:,.2f}",
                        str(getattr(r, "broker", "")),
                    )
                    tv.insert("", "end", values=vals)

            self.after(0, _apply)

        threading.Thread(target=_load, daemon=True).start()

    def _show_broker_breakdown(self, title: str, metric_key: str, *, is_currency: bool = True) -> None:
        try:
            from TKinter_Tracker.common.engine import get_metrics_by_broker
            broker_metrics = get_metrics_by_broker()
        except Exception as e:
            messagebox.showerror("Breakdown", f"Failed to load broker breakdown: {e}")
            return

        rows = []
        total = 0.0
        for broker, m in (broker_metrics or {}).items():
            v = float((m or {}).get(metric_key, 0.0) or 0.0)
            rows.append((str(broker), v))
            total += v
        rows.sort(key=lambda x: x[1], reverse=True)

        top = tk.Toplevel(self)
        top.title(f"{title} by Broker")
        top.configure(bg=ModernStyle.BG_PRIMARY)
        top.geometry("600x500")

        try:
            top.transient(self.winfo_toplevel())
            top.grab_set()
        except Exception:
            pass
        try:
            center_window(top, parent=self.winfo_toplevel())
        except Exception:
            pass

        # Enhanced header with close button
        hdr = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        hdr.pack(fill="x", padx=16, pady=(14, 10))
        
        # Title and total
        title_frame = tk.Frame(hdr, bg=ModernStyle.BG_PRIMARY)
        title_frame.pack(side="left", fill="x", expand=True)
        tk.Label(title_frame, text=f"{title} by Broker", fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=(ModernStyle.FONT_FAMILY, 16, "bold")).pack(anchor="w")
        fmt_total = f"₹{total:,.2f}" if is_currency else f"{total:,.2f}%"
        tk.Label(title_frame, text=f"Total: {fmt_total}", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_PRIMARY, font=(ModernStyle.FONT_FAMILY, 11)).pack(anchor="w", pady=(2, 0))
        
        # Close button on header right
        close_btn = ModernButton(
            hdr,
            text="✕ Close",
            command=top.destroy,
            bg=ModernStyle.ACCENT_TERTIARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=80,
            height=32
        )
        close_btn.pack(side="right")

        # Data table
        table_frame = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        
        cols = ("Broker", "Value", "% of Total")
        tv = ttk.Treeview(table_frame, columns=cols, show="headings", height=16)
        for c in cols:
            tv.heading(c, text=c)
            if c == "Broker":
                tv.column(c, width=200, anchor="w")
            else:
                tv.column(c, width=180, anchor="e")
        
        # Styling
        try:
            tv.tag_configure("odd", background=ModernStyle.BG_SECONDARY)
            tv.tag_configure("even", background=ModernStyle.BG_PRIMARY)
        except Exception:
            pass
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tv.yview)
        tv.configure(yscroll=vsb.set)
        tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for idx, (broker, v) in enumerate(rows):
            pct = (v / total * 100.0) if total > 0 else 0.0
            disp = f"₹{v:,.2f}" if is_currency else f"{v:,.2f}%"
            pct_text = f"{pct:.1f}%"
            tag = "odd" if idx % 2 == 0 else "even"
            tv.insert("", "end", values=(broker, disp, pct_text), tags=(tag,))
        
        # Footer with summary
        footer = tk.Frame(top, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        footer.pack(fill="x", padx=16, pady=(0, 14))
        
        top_broker = rows[0][0] if rows else "N/A"
        top_value = rows[0][1] if rows else 0.0
        top_pct = (top_value / total * 100.0) if total > 0 and rows else 0.0
        disp_top = f"₹{top_value:,.2f}" if is_currency else f"{top_value:,.2f}%"
        
        summary_text = f"Largest: {top_broker} ({disp_top}, {top_pct:.1f}%) | Brokers: {len(rows)}"
        tk.Label(footer, text=summary_text, fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 10)).pack(anchor="w", padx=12, pady=8)

    def _on_refresh_market_data(self) -> None:
        if getattr(self, "_refresh_inflight", False):
            return
        self._refresh_inflight = True
        self.refresh_status.config(text="Refreshing…")
        try:
            self.refresh_btn.set_disabled(True)
        except Exception:
            pass

        def _bg():
            try:
                from TKinter_Tracker.common.database import db_session
                from TKinter_Tracker.common.engine import fetch_and_update_market_data, rebuild_holdings
                with db_session() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT DISTINCT symbol FROM holdings WHERE qty > 0")
                    symbols = [r[0] for r in cur.fetchall()]
                if symbols:
                    fetch_and_update_market_data(symbols)
                rebuild_holdings()
                # refresh cache so views update
                if self.app_state and hasattr(self.app_state, "refresh_data_cache"):
                    self.app_state.refresh_data_cache()
                # reload dashboard
                self.after(0, self._finish_refresh)
            except Exception as e:
                self.after(0, lambda err_msg=str(e): self._finish_refresh(err=err_msg))

        threading.Thread(target=_bg, daemon=True).start()

    def _finish_refresh(self, err: str | None = None) -> None:
        self._refresh_inflight = False
        try:
            self.refresh_btn.set_disabled(False)
        except Exception:
            pass
        if err:
            self.refresh_status.config(text=f"Refresh failed: {err}")
        else:
            self.refresh_status.config(text=f"Updated {datetime.now().strftime('%H:%M:%S')}")
            self._data_loaded = False
            self.load_data()


