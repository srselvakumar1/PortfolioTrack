"""
Dashboard view for TKinter-based PTracker application.
Enhanced with better readability, visual hierarchy, and refined aesthetics.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime

from views.base_view import BaseView, _enable_canvas_mousewheel
from ui_theme import ModernStyle
from ui_widgets import ModernButton
from ui_utils import center_window


# ── Small utility helpers ──────────────────────────────────────────────────────

def _money(v) -> str:
    """Format a float as ₹ with commas."""
    try:
        return f"₹{float(v or 0.0):,.2f}"
    except Exception:
        return "₹0.00"


def _pct(v) -> str:
    """Format a float as percentage."""
    try:
        return f"{float(v or 0.0):,.2f}%"
    except Exception:
        return "0.00%"


def _compact_money(v) -> str:
    """Format large rupee amounts as 1.2L / 50K / etc."""
    try:
        f = float(v or 0.0)
        if abs(f) >= 1_00_000:
            return f"₹{f/1_00_000:.2f}L"
        if abs(f) >= 1_000:
            return f"₹{f/1_000:.1f}K"
        return f"₹{f:,.0f}"
    except Exception:
        return "₹0"


class DashboardView(BaseView):
    """Portfolio dashboard with summary metrics and overview."""

    def build(self):
        """Build the dashboard UI."""
        self._ui_built = False
        self._data_loaded = False
        self._refresh_inflight = False

        # ── Scrollable canvas container ────────────────────────────────────────
        canvas = tk.Canvas(self, bg=ModernStyle.BG_PRIMARY, highlightthickness=0)
        # vscroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        # canvas.configure(yscrollcommand=vscroll.set)
        # vscroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._content = tk.Frame(canvas, bg=ModernStyle.BG_PRIMARY)
        self._content_id = canvas.create_window((0, 0), window=self._content, anchor="nw")

        def _on_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(self._content_id, width=canvas.winfo_width())

        self._content.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)
        _enable_canvas_mousewheel(canvas, include_widget=self._content)

        # ── Header row ─────────────────────────────────────────────────────────
        header = tk.Frame(self._content, bg=ModernStyle.BG_PRIMARY)
        header.pack(fill="x", padx=20, pady=(20, 4))

        left_hdr = tk.Frame(header, bg=ModernStyle.BG_PRIMARY)
        left_hdr.pack(side="left", fill="y")
        tk.Label(
            left_hdr,
            text="🇮🇳 Portfolio Dashboard",
            fg=ModernStyle.TEXT_PRIMARY,
            bg=ModernStyle.BG_PRIMARY,
            font=(ModernStyle.FONT_FAMILY, 24, "bold"),
        ).pack(anchor="w")
        self._header_subtitle = tk.Label(
            left_hdr,
            text="Loading portfolio data…",
            fg=ModernStyle.TEXT_TERTIARY,
            bg=ModernStyle.BG_PRIMARY,
            font=(ModernStyle.FONT_FAMILY, 11),
        )
        self._header_subtitle.pack(anchor="w", pady=(2, 0))

        right_hdr = tk.Frame(header, bg=ModernStyle.BG_PRIMARY)
        right_hdr.pack(side="right", fill="y")

        self.refresh_status = tk.Label(
            right_hdr,
            text="",
            fg=ModernStyle.TEXT_TERTIARY,
            bg=ModernStyle.BG_PRIMARY,
            font=(ModernStyle.FONT_FAMILY, 10),
        )
        self.refresh_status.pack(anchor="e", pady=(0, 4))

        self.refresh_btn = ModernButton(
            right_hdr,
            text="🔷  Refresh",
            command=self._on_refresh_market_data,
            bg=ModernStyle.ACCENT_TERTIARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=100,
            height=32,
            radius=10,
            font=(ModernStyle.FONT_FAMILY, 12, "bold"),
        )
        self.refresh_btn.pack(anchor="e")

        # Thin accent divider under header
        tk.Frame(self._content, bg=ModernStyle.ACCENT_PRIMARY, height=2).pack(
            fill="x", padx=20, pady=(10, 0)
        )

        # ── KPI Cards ─────────────────────────────────────────────────────────
        self.kpi_labels = {}
        self._kpi_cards = {}

        def _kpi_card(
            parent,
            title: str,
            key: str,
            *,
            color: str,
            icon: str,
            metric_key: str | None,
            is_currency: bool = True,
        ) -> tk.Frame:
            """Create a premium KPI card with accent bar, icon, value, and trend."""
            card = tk.Frame(
                parent,
                bg=ModernStyle.BG_SECONDARY,
                highlightbackground=ModernStyle.BORDER_COLOR,
                highlightthickness=1,
            )
            card.pack_propagate(False)
            card.grid_propagate(False)
            card.configure(height=ModernStyle.KPI_CARD_HEIGHT)

            # Top accent bar (thick + branded color)
            tk.Frame(card, bg=color, height=5).pack(fill="x")

            # Body
            body = tk.Frame(card, bg=ModernStyle.BG_SECONDARY)
            body.pack(fill="both", expand=True, padx=14, pady=10)

            # Icon + Title row
            title_row = tk.Frame(body, bg=ModernStyle.BG_SECONDARY)
            title_row.pack(fill="x")
            tk.Label(
                title_row,
                text=icon,
                fg=color,
                bg=ModernStyle.BG_SECONDARY,
                font=(ModernStyle.FONT_FAMILY, 15),
            ).pack(side="left", padx=(0, 6))
            tk.Label(
                title_row,
                text=title,
                fg=ModernStyle.TEXT_SECONDARY,
                bg=ModernStyle.BG_SECONDARY,
                font=(ModernStyle.FONT_FAMILY, 10, "bold"),
            ).pack(side="left", pady=(2, 0))

            # Value label (large, bold, colored)
            val = tk.Label(
                body,
                text="—",
                fg=color,
                bg=ModernStyle.BG_SECONDARY,
                font=(ModernStyle.FONT_FAMILY, 20, "bold"),
            )
            val.pack(anchor="w", pady=(6, 0))
            self.kpi_labels[key] = val

            # Trend label (small, below value)
            trend_lbl = tk.Label(
                body,
                text="",
                fg=ModernStyle.TEXT_TERTIARY,
                bg=ModernStyle.BG_SECONDARY,
                font=(ModernStyle.FONT_FAMILY, 9),
            )
            trend_lbl.pack(anchor="w")
            # Store a ref so we can update it later
            setattr(val, "_trend_lbl", trend_lbl)

            if metric_key:
                def _click(_e=None, t=title, mk=metric_key, cur=is_currency):
                    self._show_broker_breakdown(t, mk, is_currency=cur)

                def _hover_in(_e=None):
                    card.configure(highlightbackground=color, highlightthickness=2)

                def _hover_out(_e=None):
                    card.configure(highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)

                card.configure(cursor="hand2")
                for w in (card, body, val, trend_lbl, title_row):
                    try:
                        w.bind("<Double-1>", _click)
                        w.bind("<Enter>", _hover_in)
                        w.bind("<Leave>", _hover_out)
                    except Exception:
                        pass

            return card

        # ── KPI Row 1: Primary metrics ─────────────────────────────────────────
        row1 = tk.Frame(self._content, bg=ModernStyle.BG_PRIMARY)
        row1.pack(fill="x", padx=20, pady=(18, 6))
        for i in range(3):
            row1.grid_columnconfigure(i, weight=1, uniform="kpi1")

        kpi_row1_specs = [
            ("Total Portfolio Value", "total_value",  ModernStyle.ACCENT_PRIMARY,    "💼", True),
            ("Total Invested",        "total_invested",ModernStyle.ACCENT_SECONDARY,  "📥", True),
            ("Overall P&L",           "overall_pnl",   "#7C3AED",                     "📊", True),
        ]
        for col, (title, key, color, icon, cur) in enumerate(kpi_row1_specs):
            c = _kpi_card(row1, title, key, color=color, icon=icon, metric_key=key, is_currency=cur)
            self._kpi_cards[key] = c
            c.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)

        # ── KPI Row 2: Detail metrics ──────────────────────────────────────────
        row2 = tk.Frame(self._content, bg=ModernStyle.BG_PRIMARY)
        row2.pack(fill="x", padx=20, pady=(0, 6))
        for i in range(5):
            row2.grid_columnconfigure(i, weight=1, uniform="kpi2")

        kpi_row2_specs = [
            ("Unrealized P&L",  "unrealized_pnl", ModernStyle.ACCENT_PRIMARY,    "📈", True),
            ("Realized P&L",    "realized_pnl",   ModernStyle.ACCENT_SECONDARY,  "🔷", True),
            ("Realized Loss",   "realized_loss",  ModernStyle.ERROR,             "🔻",True),
            ("XIRR",            "overall_xirr",   ModernStyle.ACCENT_TERTIARY,   "🎯", False),
            ("CAGR",            "overall_cagr",   "#0891B2",                     "📐", False),
        ]
        for col, (title, key, color, icon, cur) in enumerate(kpi_row2_specs):
            c = _kpi_card(row2, title, key, color=color, icon=icon, metric_key=key, is_currency=cur)
            self._kpi_cards[key] = c
            c.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)

        # ── 2×2 Section grid ──────────────────────────────────────────────────
        grid = tk.Frame(self._content, bg=ModernStyle.BG_PRIMARY)
        grid.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        grid.grid_columnconfigure(0, weight=1, uniform="p")
        grid.grid_columnconfigure(1, weight=1, uniform="p")
        grid.grid_rowconfigure(0, weight=0)
        grid.grid_rowconfigure(1, weight=0)

        def _section_card(parent, title: str, icon: str, accent: str) -> tuple[tk.Frame, tk.Frame]:
            """Create a section card with fixed-height scrollable body."""
            card = tk.Frame(
                parent,
                bg=ModernStyle.BG_SECONDARY,
                highlightbackground=ModernStyle.BORDER_COLOR,
                highlightthickness=1,
            )

            # Accent bar
            tk.Frame(card, bg=accent, height=4).pack(fill="x")

            # Header row
            hdr = tk.Frame(card, bg=ModernStyle.BG_SECONDARY)
            hdr.pack(fill="x", padx=14, pady=(10, 6))
            tk.Label(
                hdr,
                text=icon,
                fg=accent,
                bg=ModernStyle.BG_SECONDARY,
                font=(ModernStyle.FONT_FAMILY, 14),
            ).pack(side="left", padx=(0, 6))
            tk.Label(
                hdr,
                text=title,
                fg=ModernStyle.TEXT_PRIMARY,
                bg=ModernStyle.BG_SECONDARY,
                font=(ModernStyle.FONT_FAMILY, 13, "bold"),
            ).pack(side="left")

            # Thin divider
            tk.Frame(card, bg=ModernStyle.DIVIDER_COLOR, height=1).pack(fill="x", padx=12)

            # Fixed-height scrollable body area
            body_outer = tk.Frame(card, bg=ModernStyle.BG_SECONDARY, height=260)
            body_outer.pack(fill="x", padx=0, pady=(4, 8))
            body_outer.pack_propagate(False)

            body_canvas = tk.Canvas(
                body_outer, bg=ModernStyle.BG_SECONDARY, highlightthickness=0, bd=0
            )
            body_vsb = ttk.Scrollbar(body_outer, orient="vertical", command=body_canvas.yview)
            body_canvas.configure(yscrollcommand=body_vsb.set)
            body_vsb.pack(side="right", fill="y")
            body_canvas.pack(side="left", fill="both", expand=True)

            body = tk.Frame(body_canvas, bg=ModernStyle.BG_SECONDARY)
            body_win = body_canvas.create_window((0, 0), window=body, anchor="nw")

            def _on_body_cfg(e):
                body_canvas.configure(scrollregion=body_canvas.bbox("all"))
                body_canvas.itemconfigure(body_win, width=body_canvas.winfo_width())

            def _on_canvas_cfg(e):
                body_canvas.itemconfigure(body_win, width=e.width)

            body.bind("<Configure>", _on_body_cfg)
            body_canvas.bind("<Configure>", _on_canvas_cfg)
            _enable_canvas_mousewheel(body_canvas, include_widget=body)

            return card, body

        self.top_card, self.top_body = _section_card(grid, "Top Performers",       "🏆", ModernStyle.ACCENT_SECONDARY)
        self.worst_card, self.worst_body = _section_card(grid, "Worst Performers",  "📉", ModernStyle.ERROR)
        self.insights_card, self.insights_body = _section_card(grid, "Actionable Insights", "💡", ModernStyle.ACCENT_TERTIARY)
        self.harvest_card, self.harvest_body = _section_card(grid, "Tax Harvesting Ops",    "🔄", "#7C3AED")

        self.top_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.worst_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        self.insights_card.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.harvest_card.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)

        self._ui_built = True

    # ──────────────────────────────────────────────────────────────────────────
    # Data loading
    # ──────────────────────────────────────────────────────────────────────────

    def load_data(self):
        """Load dashboard data (engine metrics + performers + insights + harvesting)."""
        if getattr(self, "_data_loaded", False):
            return
        self._data_loaded = True

        def _bg():
            try:
                from common.engine import (
                    get_dashboard_metrics, get_top_worst_performers,
                    get_actionable_insights, get_tax_harvesting_opportunities,
                )
                metrics   = get_dashboard_metrics()
                performers = get_top_worst_performers(10)
                insights  = get_actionable_insights()
                harvesting = get_tax_harvesting_opportunities(500.0)
                self.after(0, lambda: self._apply_payload(metrics, performers, insights, harvesting))
            except Exception as e:
                print(f"Dashboard load error: {e}")

        threading.Thread(target=_bg, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────────────
    # Payload application
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_payload(
        self,
        metrics: dict,
        performers: dict,
        insights: list,
        harvesting: list,
    ) -> None:

        # KPI values
        try:
            def _set(key: str, text: str, fg: str | None = None):
                lbl = self.kpi_labels.get(key)
                if lbl is None:
                    return
                lbl.config(text=text)
                if fg:
                    lbl.config(fg=fg)

            total_v   = float(metrics.get("total_value", 0.0) or 0.0)
            total_inv = float(metrics.get("total_invested", 0.0) or 0.0)
            pnl       = float(metrics.get("overall_pnl", 0.0) or 0.0)
            upnl      = float(metrics.get("unrealized_pnl", 0.0) or 0.0)
            rpnl      = float(metrics.get("realized_pnl", 0.0) or 0.0)
            rloss     = float(metrics.get("realized_loss", 0.0) or 0.0)
            xirr      = float(metrics.get("overall_xirr", 0.0) or 0.0)
            cagr      = float(metrics.get("overall_cagr", 0.0) or 0.0)

            _set("total_value",   _money(total_v))
            _set("total_invested",_money(total_inv))
            _set("overall_pnl",  _money(pnl),  ModernStyle.SUCCESS if pnl >= 0 else ModernStyle.ERROR)
            _set("unrealized_pnl",_money(upnl), ModernStyle.SUCCESS if upnl >= 0 else ModernStyle.ERROR)
            _set("realized_pnl", _money(rpnl),  ModernStyle.SUCCESS if rpnl >= 0 else ModernStyle.ERROR)
            _set("realized_loss",_money(rloss),  ModernStyle.ERROR)
            _set("overall_xirr", _pct(xirr),    ModernStyle.SUCCESS if xirr >= 0 else ModernStyle.ERROR)
            _set("overall_cagr", _pct(cagr),    ModernStyle.SUCCESS if cagr >= 0 else ModernStyle.ERROR)

            # Trend labels
            def _set_trend(key: str, text: str):
                lbl = self.kpi_labels.get(key)
                if lbl is None:
                    return
                trend = getattr(lbl, "_trend_lbl", None)
                if trend:
                    trend.config(text=text)

            pnl_pct = ((pnl / total_inv) * 100.0) if total_inv else 0.0
            arrow = "▲" if pnl >= 0 else "▼"
            _set_trend("total_value",    f"Invested {_compact_money(total_inv)}")
            _set_trend("total_invested", f"{len(performers.get('top', []) or [])} Positions")
            _set_trend("overall_pnl",    f"{arrow} {pnl_pct:+.2f}% overall return")
            _set_trend("unrealized_pnl", f"{'▲' if upnl >= 0 else '▼'} Open positions")
            _set_trend("realized_pnl",   f"{'▲' if rpnl >= 0 else '▼'} Closed trades")
            _set_trend("realized_loss",  "Losses from closed trades")
            _set_trend("overall_xirr",   "Annualized return (XIRR)")
            _set_trend("overall_cagr",   "Compound annual growth")

            # Update header subtitle
            try:
                self._header_subtitle.config(
                    text=f"Total Portfolio: {_money(total_v)}  •  P&L: {_money(pnl)} ({pnl_pct:+.2f}%)"
                          f"  •  Updated {datetime.now().strftime('%H:%M')}"
                )
            except Exception:
                pass

        except Exception as e:
            print(f"KPI apply error: {e}")

        # Section lists
        self._render_performers(self.top_body, performers.get("top", []) or [],   is_top=True)
        self._render_performers(self.worst_body, performers.get("worst", []) or [], is_top=False)
        self._render_simple_list(self.insights_body, insights or [],    kind="insight")
        self._render_simple_list(self.harvest_body, harvesting or [],   kind="harvest")

    # ──────────────────────────────────────────────────────────────────────────
    # Section renderers
    # ──────────────────────────────────────────────────────────────────────────

    def _clear_frame(self, frame: tk.Frame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    def _empty_state(self, frame: tk.Frame, msg: str = "No data available") -> None:
        """Show a friendly empty-state message."""
        tk.Label(
            frame,
            text=f"—  {msg}",
            fg=ModernStyle.TEXT_TERTIARY,
            bg=ModernStyle.BG_SECONDARY,
            font=(ModernStyle.FONT_FAMILY, 10),
        ).pack(anchor="w", pady=4)

    def _render_performers(self, frame: tk.Frame, data: list, *, is_top: bool) -> None:
        self._clear_frame(frame)
        data = (data or [])[:10]

        if not data:
            self._empty_state(frame)
            return

        # Compute max |pnl| for bar scaling
        max_abs = max((abs(float(d.get("pnl", 0.0) or 0.0)) for d in data), default=1) or 1

        for i, item in enumerate(data):
            sym       = str(item.get("symbol", ""))
            pnl       = float(item.get("pnl", 0.0) or 0.0)
            invested  = float(item.get("invested", 1.0) or 1.0)
            roi       = (pnl / invested * 100.0) if invested > 0 else 0.0
            bar_frac  = min(1.0, abs(pnl) / max_abs)  # 0‥1

            accent  = ModernStyle.SUCCESS if pnl >= 0 else ModernStyle.ERROR
            
            # Ultra-thin zebra striping
            row_bg = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"
            
            # ── Row container ─────────────────────────────────────────────────
            row = tk.Frame(frame, bg=row_bg)
            row.pack(fill="x", pady=0)

            content = tk.Frame(row, bg=row_bg)
            content.pack(fill="x", padx=10, pady=(8, 8))

            # Left: rank + symbol
            left = tk.Frame(content, bg=row_bg)
            left.pack(side="left")

            badge   = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, f"#{i+1}")
            badge_f = "(ModernStyle.FONT_FAMILY, 13)" if i < 3 else "(ModernStyle.FONT_FAMILY, 11)"
            tk.Label(
                left,
                text=badge,
                fg=ModernStyle.TEXT_PRIMARY,
                bg=row_bg,
                font=(ModernStyle.FONT_FAMILY, 12 if i < 3 else 10),
            ).pack(side="left", padx=(0, 6))
            tk.Label(
                left,
                text=sym,
                fg=ModernStyle.ACCENT_PRIMARY,
                bg=row_bg,
                font=(ModernStyle.FONT_FAMILY, 12, "bold"),
            ).pack(side="left")

            # Right: arrow + P&L + ROI%
            right = tk.Frame(content, bg=row_bg)
            right.pack(side="right")
            arrow = "▲" if pnl >= 0 else "▼"
            pnl_disp = _compact_money(abs(pnl))
            tk.Label(
                right,
                text=f"{arrow} {pnl_disp}",
                fg=accent,
                bg=row_bg,
                font=(ModernStyle.FONT_FAMILY, 12, "bold"),
            ).pack(side="left", padx=(0, 4))
            tk.Label(
                right,
                text=f"({roi:+.1f}%)",
                fg=accent,
                bg=row_bg,
                font=(ModernStyle.FONT_FAMILY, 10),
            ).pack(side="left")

            # Click drilldown + hover
            def _click_fn(e=None, s=sym): self._open_trade_drilldown(s)
            def _hover_in(e=None, f=row):
                f.configure(bg=ModernStyle.BG_TERTIARY)
                for w in f.winfo_children():
                    w.configure(bg=ModernStyle.BG_TERTIARY)
                    if w.winfo_children():
                        for cw in w.winfo_children():
                            cw.configure(bg=ModernStyle.BG_TERTIARY)
            def _hover_out(e=None, f=row, base_bg=row_bg):
                f.configure(bg=base_bg)
                for w in f.winfo_children():
                    w.configure(bg=base_bg)
                    if w.winfo_children():
                        for cw in w.winfo_children():
                            cw.configure(bg=base_bg)

            row.configure(cursor="hand2")
            for w in (row, content, left, right):
                try:
                    w.bind("<Double-1>", _click_fn)
                    w.bind("<Enter>", _hover_in)
                    w.bind("<Leave>", _hover_out)
                except Exception:
                    pass

    def _render_simple_list(self, frame: tk.Frame, data: list, *, kind: str) -> None:
        self._clear_frame(frame)

        if not data:
            self._empty_state(frame)
            return

        # ── Tax Harvesting ─────────────────────────────────────────────────────
        if kind == "harvest":
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                sym   = str(item.get("symbol", "")).strip()
                loss  = float(item.get("unrealized_loss", 0.0) or 0.0)
                qty   = item.get("qty", "")
                avg   = float(item.get("avg_price", 0.0) or 0.0)
                broker = str(item.get("broker", "") or "").strip()

                # Ultra-thin zebra striping
                row_bg = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"

                row = tk.Frame(frame, bg=row_bg)
                row.pack(fill="x", pady=0)

                top_line = tk.Frame(row, bg=row_bg)
                top_line.pack(fill="x", padx=10, pady=(8, 2))

                tk.Label(top_line, text="⚠️", bg=row_bg, font=(ModernStyle.FONT_FAMILY, 12)).pack(side="left", padx=(0, 6))
                tk.Label(top_line, text=sym or "—", fg=ModernStyle.ACCENT_PRIMARY, bg=row_bg, font=(ModernStyle.FONT_FAMILY, 12, "bold")).pack(side="left")
                tk.Label(
                    top_line,
                    text=f"₹{loss:,.2f}",
                    fg=ModernStyle.ERROR if loss < 0 else ModernStyle.SUCCESS,
                    bg=row_bg,
                    font=(ModernStyle.FONT_FAMILY, 11, "bold"),
                ).pack(side="right")

                tk.Label(row, text=f"Qty {qty}  •  Avg ₹{avg:,.2f}",
                         fg=ModernStyle.TEXT_SECONDARY, bg=row_bg,
                         font=(ModernStyle.FONT_FAMILY, 9)).pack(anchor="w", padx=36, pady=(0, 8))


                try:
                    def _hover_in(e=None, r=row):
                        r.configure(bg=ModernStyle.BG_TERTIARY)
                        for w in r.winfo_children():
                            w.configure(bg=ModernStyle.BG_TERTIARY)
                            if w.winfo_children():
                                for cw in w.winfo_children():
                                    cw.configure(bg=ModernStyle.BG_TERTIARY)
                    def _hover_out(e=None, r=row, base_bg=row_bg):
                        r.configure(bg=base_bg)
                        for w in r.winfo_children():
                            w.configure(bg=base_bg)
                            if w.winfo_children():
                                for cw in w.winfo_children():
                                    cw.configure(bg=base_bg)
                    row.bind("<Double-1>", lambda e=None, s=sym, b=broker: self._open_trade_drilldown(s, broker=b or None))
                    row.bind("<Enter>", _hover_in)
                    row.bind("<Leave>", _hover_out)
                    for w in row.winfo_children():
                        w.bind("<Double-1>", lambda e=None, s=sym, b=broker: self._open_trade_drilldown(s, broker=b or None))
                        w.bind("<Enter>", _hover_in)
                        w.bind("<Leave>", _hover_out)
                    row.configure(cursor="hand2")
                except Exception:
                    pass
            return

        # ── Actionable Insights ────────────────────────────────────────────────
        if kind == "insight":
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    tk.Label(
                        frame, text=f"•  {item}",
                        fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY,
                        font=ModernStyle.FONT_BODY, justify="left", wraplength=520,
                    ).pack(anchor="w", pady=2)
                    continue

                sym     = str(item.get("symbol", "")).strip()
                signal  = str(item.get("signal", "") or "").strip().upper()
                iv      = float(item.get("iv", 0.0) or 0.0)
                cp      = float(item.get("current_price", 0.0) or 0.0)
                diff_pct = ((iv - cp) / cp * 100.0) if cp else 0.0

                if signal == "ACCUMULATE":
                    sig_icon = "📈"
                    sig_color  = ModernStyle.SUCCESS
                elif signal == "REDUCE":
                    sig_icon = "📉"
                    sig_color  = ModernStyle.ERROR
                else:
                    sig_icon = "⏸️"
                    sig_color  = ModernStyle.TEXT_SECONDARY

                # Ultra-thin zebra striping
                row_bg = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"

                row = tk.Frame(frame, bg=row_bg)
                row.pack(fill="x", pady=0)

                top_line = tk.Frame(row, bg=row_bg)
                top_line.pack(fill="x", padx=10, pady=(8, 2))

                tk.Label(top_line, text=sig_icon, bg=row_bg, font=(ModernStyle.FONT_FAMILY, 12)).pack(side="left", padx=(0, 6))
                tk.Label(top_line, text=sym or "—", fg=ModernStyle.ACCENT_PRIMARY, bg=row_bg, font=(ModernStyle.FONT_FAMILY, 12, "bold")).pack(side="left")

                # Signal text without a chip background
                chip = tk.Label(
                    top_line,
                    text=signal,
                    fg=sig_color, bg=row_bg,
                    font=(ModernStyle.FONT_FAMILY, 10, "bold")
                )
                chip.pack(side="right", padx=(0, 2))

                detail = f"IV ₹{iv:,.0f}  •  Curr ₹{cp:,.0f}  •  Gap {diff_pct:+.1f}%"
                tk.Label(row, text=detail, fg=ModernStyle.TEXT_TERTIARY, bg=row_bg, font=(ModernStyle.FONT_FAMILY, 9)).pack(anchor="w", padx=36, pady=(0, 8))


                try:
                    def _hover_in(e=None, r=row):
                        r.configure(bg=ModernStyle.BG_TERTIARY)
                        for w in r.winfo_children():
                            w.configure(bg=ModernStyle.BG_TERTIARY)
                            if w.winfo_children():
                                for cw in w.winfo_children():
                                    cw.configure(bg=ModernStyle.BG_TERTIARY)
                    def _hover_out(e=None, r=row, base_bg=row_bg):
                        r.configure(bg=base_bg)
                        for w in r.winfo_children():
                            w.configure(bg=base_bg)
                            if w.winfo_children():
                                for cw in w.winfo_children():
                                    cw.configure(bg=base_bg)

                    row.bind("<Double-1>", lambda e=None, s=sym: self._open_trade_drilldown(s))
                    row.bind("<Enter>", _hover_in)
                    row.bind("<Leave>", _hover_out)
                    for w in row.winfo_children():
                        w.bind("<Double-1>", lambda e=None, s=sym: self._open_trade_drilldown(s))
                        w.bind("<Enter>", _hover_in)
                        w.bind("<Leave>", _hover_out)
                    row.configure(cursor="hand2")
                except Exception:
                    pass
            return

        # Default bullet list
        for i, item in enumerate(data):
            text = item.get("text") or item.get("message") or str(item) if isinstance(item, dict) else str(item)
            tk.Label(
                frame, text=f"•  {text}",
                fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY,
                font=ModernStyle.FONT_BODY, justify="left", wraplength=520,
            ).pack(anchor="w", pady=2)

    # ──────────────────────────────────────────────────────────────────────────
    # Trade Drilldown popup
    # ──────────────────────────────────────────────────────────────────────────

    def _open_trade_drilldown(self, symbol: str, *, broker: str | None = None) -> None:
        symbol = (symbol or "").strip()
        if not symbol:
            return

        top = tk.Toplevel(self)
        top.title(f"Trade Drilldown — {symbol}")
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

        # Header
        hdr = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        hdr.pack(fill="x", padx=16, pady=14)
        tk.Frame(hdr, bg=ModernStyle.ACCENT_PRIMARY, width=5).pack(side="left", fill="y", padx=(0, 12))
        title_col = tk.Frame(hdr, bg=ModernStyle.BG_PRIMARY)
        title_col.pack(side="left", fill="y")
        tk.Label(title_col, text=symbol, fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_TITLE).pack(anchor="w")
        tk.Label(
            title_col,
            text=f"Broker: {broker}" if broker else "All Brokers",
            fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_PRIMARY,
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
        try:
            tv.tag_configure("odd",  background="#FFFFFF")
            tv.tag_configure("even", background="#F8FAFC")
            tv.tag_configure("buy",  foreground=ModernStyle.ACCENT_SECONDARY)
            tv.tag_configure("sell", foreground=ModernStyle.ERROR)
        except Exception:
            pass

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

        ModernButton(act, text="📋  Copy Trades", command=_copy, bg=ModernStyle.ACCENT_PRIMARY, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg=ModernStyle.BG_PRIMARY, width=140, height=36).pack(side="left")
        ModernButton(act, text="✕  Close", command=lambda: top.destroy(), bg=ModernStyle.SALMON, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg=ModernStyle.BG_PRIMARY, width=100, height=36).pack(side="right")

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
                from common.data_cache import TradeHistoryFilters
                if self.app_state is not None and hasattr(self.app_state, "data_cache"):
                    cache = self.app_state.data_cache
                else:
                    from common.data_cache import DataCache
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
                for idx, r in enumerate(df.itertuples(index=False)):
                    rtype = str(getattr(r, "type", "")).upper()
                    qty   = float(getattr(r, "qty", 0.0) or 0.0)
                    price = float(getattr(r, "price", 0.0) or 0.0)
                    fee   = float(getattr(r, "fee", 0.0) or 0.0)
                    run_qty = float(getattr(r, "run_qty", 0.0) or 0.0)
                    avg_cost = float(getattr(r, "avg_cost", 0.0) or 0.0)
                    rpnl  = float(getattr(r, "running_pnl", 0.0) or 0.0)
                    vals  = (
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
                    stripe   = "odd" if idx % 2 else "even"
                    type_tag = "buy" if rtype == "BUY" else "sell"
                    tv.insert("", "end", values=vals, tags=(stripe, type_tag))

            self.after(0, _apply)

        threading.Thread(target=_load, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────────────
    # Broker breakdown popup
    # ──────────────────────────────────────────────────────────────────────────

    def _show_broker_breakdown(self, title: str, metric_key: str, *, is_currency: bool = True) -> None:
        try:
            from common.engine import get_metrics_by_broker
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

        # Header
        hdr = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        hdr.pack(fill="x", padx=16, pady=(14, 10))
        title_col = tk.Frame(hdr, bg=ModernStyle.BG_PRIMARY)
        title_col.pack(side="left", fill="x", expand=True)
        tk.Label(title_col, text=f"{title} by Broker", fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=(ModernStyle.FONT_FAMILY, 16, "bold")).pack(anchor="w")
        fmt_total = _money(total) if is_currency else _pct(total)
        tk.Label(title_col, text=f"Total: {fmt_total}", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_PRIMARY, font=(ModernStyle.FONT_FAMILY, 11)).pack(anchor="w", pady=(2, 0))

        ModernButton(hdr, text="✕ Close", command=top.destroy, bg=ModernStyle.SALMON, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg=ModernStyle.BG_PRIMARY, width=90, height=32).pack(side="right")

        # Table
        table_frame = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        cols = ("Broker", "Value", "% of Total")
        tv = ttk.Treeview(table_frame, columns=cols, show="headings", height=16)
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=200 if c == "Broker" else 180, anchor="w" if c == "Broker" else "e")

        try:
            tv.tag_configure("odd",  background="#FFFFFF")
            tv.tag_configure("even", background="#F8FAFC")
        except Exception:
            pass

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tv.yview)
        tv.configure(yscroll=vsb.set)
        tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for idx, (broker, v) in enumerate(rows):
            pct  = (v / total * 100.0) if total > 0 else 0.0
            disp = _money(v) if is_currency else _pct(v)
            tag  = "odd" if idx % 2 == 0 else "even"
            tv.insert("", "end", values=(broker, disp, f"{pct:.1f}%"), tags=(tag,))

        # Footer
        footer = tk.Frame(top, bg=ModernStyle.BG_TERTIARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        footer.pack(fill="x", padx=16, pady=(0, 14))
        top_broker = rows[0][0] if rows else "N/A"
        top_value  = rows[0][1] if rows else 0.0
        top_pct    = (top_value / total * 100.0) if total > 0 and rows else 0.0
        disp_top   = _money(top_value) if is_currency else _pct(top_value)
        tk.Label(
            footer,
            text=f"Largest: {top_broker}  ({disp_top}, {top_pct:.1f}%)    |    Brokers: {len(rows)}",
            fg=ModernStyle.TEXT_SECONDARY,
            bg=ModernStyle.BG_TERTIARY,
            font=(ModernStyle.FONT_FAMILY, 10),
        ).pack(anchor="w", padx=12, pady=8)

    # ──────────────────────────────────────────────────────────────────────────
    # Market Data Refresh
    # ──────────────────────────────────────────────────────────────────────────

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
                from common.database import db_session
                from common.engine import fetch_and_update_market_data, rebuild_holdings
                with db_session() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT DISTINCT symbol FROM holdings WHERE qty > 0")
                    symbols = [r[0] for r in cur.fetchall()]
                if symbols:
                    fetch_and_update_market_data(symbols)
                rebuild_holdings()
                if self.app_state and hasattr(self.app_state, "refresh_data_cache"):
                    self.app_state.refresh_data_cache()
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
            self.refresh_status.config(text=f"⚠️ Refresh failed: {err[:60]}")
        else:
            self.refresh_status.config(text=f"✅ Updated {datetime.now().strftime('%H:%M:%S')}")
            self._data_loaded = False
            self.load_data()
