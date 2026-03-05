import flet as ft
from flet_app.common.state import AppState
from flet_app.components.ui_elements import (
    page_title, premium_card, status_chip, show_toast,
    create_column_tooltip_header, stock_name_with_badge, holdings_stats_card,
    enhanced_filter_panel, sort_indicator, quick_action_buttons,
    color_coded_value_cell, mini_sparkline_cell,
    holdings_view_header, holding_edit_header, holding_edit_field, holding_edit_summary
)
from flet_app.common.database import db_session
from models import crud
import pandas as pd
import threading
import time
import sys
import subprocess
import os
from flet_app.common.data_cache import HoldingsFilters

class HoldingsView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True

        # Visibility/activation guard: prevents hidden views from doing expensive UI updates
        # while the user is on another tab.
        self._is_active = False

        # Caching: Store whether we've already loaded data on first visit
        self._data_loaded = False

        # Search debouncing: delay search queries by 300ms after user stops typing
        self._search_timer = None
        self._search_query = ""

        # Filter tracking for smart caching: only reload if filters actually changed
        self._cached_filters = None

        # Request sequencing: ignore stale background fetches when filters change rapidly
        self._load_seq = 0

        # Sorting support (Improvement #6)
        self._sort_column = None
        self._sort_ascending = True

        self.total_records = 0
        object.__setattr__(self, 'current_df', None)

        # ---- Style filter inputs ----
        self.broker_filter = ft.Dropdown(
            label="🏦 Broker", expand=1,
            options=[ft.dropdown.Option("All")],
            value="All",
            bgcolor=ft.Colors.GREY_900,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400)
        )

        self.iv_filter = ft.Dropdown(
            label="📊 IV Signal", expand=1,
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("ACCUMULATE"),
                ft.dropdown.Option("REDUCE"),
                ft.dropdown.Option("N/A")
            ],
            value="All",
            bgcolor=ft.Colors.GREY_900,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400)
        )

        self.symbol_filter = ft.TextField(
            label="🔍 Symbol", expand=1,
            hint_text="e.g. ITC, TCS, INFY",
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.GREY_900,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400)
        )
        self.symbol_filter.on_change = self._on_symbol_search  # Debounced search
        self.symbol_filter.on_submit = lambda e: self._apply_with_reload()  # Also search on Enter

        self.exclude_zero_qty_chk = ft.Checkbox(label="Exclude Zero Qty", value=False)
        self.exclude_zero_qty_chk.on_change = lambda e: self.load_data(_reload_brokers=False, use_cache=True, show_loading=False)


        self.col_widths = [30, 115, 160, 80, 80, 80, 80, 100, 80, 80, 90, 100, 80, 80, 120]
        self.columns = [
            ("#", self.col_widths[0], True), ("Symbol", self.col_widths[1], True), ("Name", self.col_widths[2], False),
            ("Qty", self.col_widths[3], True), ("Avg Prc ₹", self.col_widths[4], True), ("Mkt Prc ₹", self.col_widths[5], True),
            ("Daily Chg", self.col_widths[6], True), ("Flash PnL ₹", self.col_widths[7], True), ("Weight%", self.col_widths[8], True),
            ("XIRR%", self.col_widths[9], True), ("CAGR%", self.col_widths[10], True), ("Real PnL ₹", self.col_widths[11], True),
            ("Fees ₹", self.col_widths[12], True), ("IV Signal", self.col_widths[13], True), ("Actions", self.col_widths[14], False),
        ]

        # ── Fast grid: fixed-width header + ListView rows (faster than DataTable) ──
        def _header_cell(text: str, width: int, numeric: bool):
            return ft.Container(
                content=ft.Text(
                    text,
                    size=13,
                    weight=ft.FontWeight.W_800,
                    color=ft.Colors.BLUE_200,
                    text_align=ft.TextAlign.RIGHT if numeric else ft.TextAlign.LEFT,
                ),
                width=width,
                alignment=ft.alignment.Alignment(1, 0) if numeric else ft.alignment.Alignment(-1, 0),
                padding=ft.padding.symmetric(vertical=10, horizontal=6),
            )

        self._grid_header_row = ft.Container(
            content=ft.Row(
                controls=[_header_cell(c[0], int(c[1]), bool(c[2])) for c in self.columns],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#111827",
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#334155")),
        )

        self._grid_list = ft.ListView(
            expand=True,
            spacing=0,
            padding=0,
            auto_scroll=False,
        )

        # Row pool reused across renders. It expands to fit the largest filtered set.
        self._row_pool = []

        self.refresh_btn = ft.ElevatedButton("Refresh", icon=ft.Icons.REFRESH, bgcolor=ft.Colors.DEEP_ORANGE_600, tooltip="Fetch latest market prices from yfinance")
        self.refresh_btn.on_click = self._handle_refresh_prices
        self.price_status = ft.Text("", size=11, color=ft.Colors.GREY_500, italic=True)
        self.loading_ring = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)
        self.loading_status = ft.Text("", size=11, color=ft.Colors.GREY_400, italic=True)

        # Apply button with hover effects
        self.apply_btn = ft.ElevatedButton(
            "Apply",
            icon=ft.Icons.FILTER_ALT,
            bgcolor=ft.Colors.BLUE,
            color=ft.Colors.WHITE,  # White text
            on_click=self._on_apply_click,  # Now with click effect
            on_hover=self._on_apply_hover,
            tooltip="Apply filters and refresh data"
        )
        self.clear_btn = ft.ElevatedButton("Clear", icon=ft.Icons.CLEAR_ALL, bgcolor=ft.Colors.TEAL_600, on_click=self._clear_with_reload)

        # Enhanced filter panel (Improvement #1)
        self.filter_panel = enhanced_filter_panel(
            self.broker_filter, self.symbol_filter, self.iv_filter, self.exclude_zero_qty_chk,
            self.apply_btn, self.clear_btn, self.refresh_btn
        )

        # ── Persistent stats card: Text controls created once, values updated in-place ──
        self._stats_holdings_val = ft.Text("0", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.BLUE_300)
        self._stats_invested_val = ft.Text("₹ 0", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.CYAN_300)
        self._stats_current_val = ft.Text("₹ 0", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE)
        self._stats_pnl_val = ft.Text("₹ 0", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.GREY_400)
        self._stats_filter_text = ft.Text("ALL", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.GREY_500)
        self._stats_filter_badge = ft.Container(
            content=self._stats_filter_text,
            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.GREY_500),
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=6
        )

        self.copy_all_btn = ft.ElevatedButton(
            "Copy All",
            icon=ft.Icons.CONTENT_COPY,
            tooltip="Copy all visible holdings rows to clipboard",
            on_click=self._copy_all_rows,
        )

        self.stats_card = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Text("Holdings", size=15, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                    self._stats_holdings_val,
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.VerticalDivider(width=1),
                ft.Row([
                    ft.Text("Invested", size=15, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                    self._stats_invested_val,
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.VerticalDivider(width=1),
                ft.Row([
                    ft.Text("Current", size=15, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                    self._stats_current_val,
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.VerticalDivider(width=1),
                ft.Row([
                    ft.Text("P&L", size=15, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                    self._stats_pnl_val,
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(expand=True),
                self._stats_filter_badge,
                self.copy_all_btn,
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=16),
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            bgcolor="#252525",
            border_radius=8,
            margin=ft.margin.only(bottom=4)
        )

        # Filter feedback text (Improvement #9)
        self.filter_feedback = ft.Text("", size=10, color=ft.Colors.GREY_600, italic=True)

        # ── Pre-built edit dialog (built ONCE, field values swapped on every open) ──
        self._edit_broker = ""
        self._edit_symbol = ""

        # Header controls (inner text refs so we can update without rebuilding)
        self._ed_hdr_symbol = ft.Text("", size=22, weight=ft.FontWeight.BOLD)
        self._ed_hdr_subtitle = ft.Text("", size=11, color="#9CA3AF")
        self._ed_hdr_holdings = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color="#3B82F6")
        self._ed_hdr_total_value = ft.Text("", size=16, weight=ft.FontWeight.BOLD, color="#06B6D4")
        _ed_header = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([self._ed_hdr_symbol, self._ed_hdr_subtitle], spacing=2),
                    ft.Column([
                        ft.Text("Current Holdings", size=11, color="#9CA3AF", weight=ft.FontWeight.W_500),
                        self._ed_hdr_holdings
                    ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=10, color="transparent"),
                ft.Row([
                    ft.Text("Total Value", size=10, color="#9CA3AF"),
                    self._ed_hdr_total_value
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=6),
            bgcolor="#1A2A3A", padding=15, border_radius=8, border=ft.border.all(1, "#334155")
        )

        # Form fields
        _tf = lambda lbl, kb=ft.KeyboardType.TEXT, helper="": ft.TextField(
            label=lbl, expand=True, keyboard_type=kb,
            label_style=ft.TextStyle(color="#9CA3AF", size=11),
            text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
            bgcolor="#0F172A", border_color="#334155", border_radius=6,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10)
        )
        self._ed_qty_tb = _tf("Quantity", ft.KeyboardType.NUMBER)
        self._ed_price_tb = _tf("Average Price", ft.KeyboardType.NUMBER)
        self._ed_realized_pnl_tb = _tf("Realized PnL", ft.KeyboardType.NUMBER)

        # Summary card with persistent text controls
        self._ed_summary_shares = ft.Text("0", size=13, weight=ft.FontWeight.BOLD, color="#E5E7EB")
        self._ed_summary_avg = ft.Text("₹0.00", size=13, weight=ft.FontWeight.BOLD, color="#E5E7EB")
        self._ed_summary_total = ft.Text("₹0.00", size=13, weight=ft.FontWeight.BOLD, color="#06B6D4")
        _ed_summary_card = ft.Container(
            content=ft.Column([
                ft.Text("Summary", size=12, weight=ft.FontWeight.BOLD, color="#3B82F6"),
                ft.Row([
                    ft.Column([
                        ft.Text("Shares", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                        self._ed_summary_shares
                    ], expand=1),
                    ft.Column([
                        ft.Text("Avg Price", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                        self._ed_summary_avg
                    ], expand=1),
                    ft.Column([
                        ft.Text("Total Value", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                        self._ed_summary_total
                    ], expand=1),
                ], spacing=12)
            ], spacing=10),
            bgcolor="#0F172A", padding=12, border_radius=6, border=ft.border.all(1, "#1E293B")
        )

        def _ed_on_change(e):
            try:
                qty = float(self._ed_qty_tb.value or 0)
                price = float(self._ed_price_tb.value or 0)
                total_value = qty * price
                self._ed_summary_shares.value = f"{qty:,.0f}"
                self._ed_summary_avg.value = f"₹{price:,.2f}"
                self._ed_summary_total.value = f"₹{total_value:,.2f}"
                _ed_summary_card.update()
            except Exception:
                pass

        self._ed_qty_tb.on_change = _ed_on_change
        self._ed_price_tb.on_change = _ed_on_change

        self._edit_dlg = ft.AlertDialog(
            title=None,
            content=ft.Container(
                content=ft.Column([
                    _ed_header,
                    ft.Divider(height=12, color="#334155"),
                    ft.Text("Edit Holdings", size=12, weight=ft.FontWeight.BOLD, color="#3B82F6"),
                    ft.Column([
                        self._ed_qty_tb,
                        ft.Text("Number of shares held", size=9, color="#6B7280", italic=True)
                    ], spacing=2),
                    ft.Column([
                        self._ed_price_tb,
                        ft.Text("Average cost per share in ₹", size=9, color="#6B7280", italic=True)
                    ], spacing=2),
                    ft.Container(height=8),
                    _ed_summary_card,
                ], tight=True, spacing=10),
                width=420,
                padding=ft.padding.symmetric(horizontal=20, vertical=20)
            ),
            actions_alignment=ft.MainAxisAlignment.END,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(self._edit_dlg)),
                ft.ElevatedButton("Save Changes", on_click=self._save_edit_dialog,
                                  bgcolor="#10B981", color=ft.Colors.WHITE)
            ]
        )
        # ── end pre-built edit dialog ──

        # Table area (kept as refs so we can update table without updating the entire page tree)
        self._table_block = ft.Row(
            [
                ft.Column(
                    [self._grid_header_row, self._grid_list],
                    spacing=0,
                    expand=True,
                )
            ],
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
        )

        self._table_card = premium_card(
            ft.Column(
                [
                    ft.Row([
                        ft.Column([self._table_block], expand=True, spacing=0)
                    ], expand=True),
                ],
                expand=True,
                spacing=4,
            ),
            expand=True,
            padding=10,
        )

        # Main content layout — compact spacing to maximize table real estate
        self._main_column = ft.Column([
            holdings_view_header(),
            self.filter_panel,
            self.stats_card,
            self.filter_feedback,
            self._table_card,
        ], spacing=2)
        self.content = self._main_column

    def _truncate_stock_name(self, name, max_chars=20):
        """Truncate stock name to max_chars, keeping only whole words."""
        # Convert to string and handle None/NaN values
        if name is None or (isinstance(name, float) and pd.isna(name)):
            return "—"

        name = str(name).strip()

        # If empty or dash, return as is
        if not name or name == "—":
            return name

        # If already short enough, return as is
        if len(name) <= max_chars:
            return name

        # Find the last whole word within max_chars
        truncated = name[:max_chars]
        last_space = truncated.rfind(' ')

        if last_space > 0:  # Keep at least some text before the space
            return truncated[:last_space]
        else:
            # No space found, just truncate at max_chars
            return truncated

    def _load_broker_options(self):
        try:
            brokers = self.app_state.get_brokers_cached(force_refresh=False)
        except Exception:
            import flet_app.common.models.crud as crud
            brokers = crud.get_all_brokers()
        self.broker_filter.options = ([ft.dropdown.Option("All")] + [ft.dropdown.Option(b) for b in brokers])

    def _on_symbol_search(self, e):
        """Debounced symbol search: wait briefly after user stops typing."""
        if self._search_timer:
            self._search_timer.cancel()

        self._search_query = e.control.value
        _profile = os.environ.get("PTRACKER_NAV_PROFILE")
        if _profile:
            print(f"[search] symbol changed to: '{self._search_query}'")

        def _apply_silent():
            # Run without showing the loading spinner on each keypress.
            # Use cache=True: the fast in-memory filter will handle symbol changes
            # (cache automatically detects filter changes via _cached_filters comparison)
            _t_before = time.perf_counter() if _profile else None
            try:
                self.load_data(_reload_brokers=False, use_cache=True, show_loading=False)
            except Exception:
                pass
            if _t_before and _profile:
                print(f"[search] load_data completed in {time.perf_counter() - _t_before:.3f}s")

        self._search_timer = threading.Timer(0.2, _apply_silent)  # Faster response: 200ms instead of 450ms
        self._search_timer.daemon = True
        self._search_timer.start()

    def _on_apply_hover(self, e):
        """Apply button hover effect: brighten and scale on hover, dim on leave."""
        try:
            if e.data == "true":  # Mouse is hovering
                # Hover state: brighter blue, slight scale
                self.apply_btn.bgcolor = ft.Colors.BLUE_400
                self.apply_btn.scale = ft.transform.Scale(scale=1.05, alignment=ft.alignment.center)
                self.apply_btn.shadow = ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.3, ft.Colors.BLUE))
            else:  # Mouse left
                # Normal state: original blue, no scale
                self.apply_btn.bgcolor = ft.Colors.BLUE
                self.apply_btn.scale = None
                self.apply_btn.shadow = None
            self.apply_btn.update()
        except Exception:
            pass

    def _on_apply_click(self, e):
        """Apply button click effect: press animation followed by reload."""
        try:
            # Press effect: darker blue, scale down
            self.apply_btn.bgcolor = ft.Colors.BLUE_700
            self.apply_btn.scale = ft.transform.Scale(scale=0.98, alignment=ft.alignment.center)
            self.apply_btn.update()
            
            # Small delay then execute action
            import time
            time.sleep(0.05)
            
            # Reset to hover state (since mouse is still on button)
            self.apply_btn.bgcolor = ft.Colors.BLUE_400
            self.apply_btn.scale = ft.transform.Scale(scale=1.05, alignment=ft.alignment.center)
            self.apply_btn.update()
        except Exception:
            pass
        
        # Execute filter action
        self._apply_with_reload()

    async def _handle_refresh_prices(self, e):
        from flet_app.common.engine import fetch_and_update_market_data
        try:
            symbols = self.app_state.data_cache.get_holdings_symbols()
        except Exception:
            with db_session() as conn:
                symbols = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM holdings").fetchall()]
        if not symbols:
            show_toast(self.app_state.page, "No holdings to fetch", color=ft.Colors.ORANGE_700)
            return
        self.refresh_btn.disabled = True
        show_toast(self.app_state.page, f"Fetching prices for {len(symbols)} symbols...", color=ft.Colors.BLUE_600, duration_ms=1000)
        try:
            self.refresh_btn.update()
        except Exception: pass

        import asyncio
        await asyncio.to_thread(fetch_and_update_market_data, symbols)
        from flet_app.common.engine import rebuild_holdings
        rebuild_holdings()

        # Refresh in-memory cache after rebuild so all views use updated data.
        try:
            await asyncio.to_thread(self.app_state.refresh_data_cache)
        except Exception:
            pass

        # Invalidate Dashboard cache since market prices affect P&L and current values
        if hasattr(self.app_state, 'views'):
            try:
                if self.app_state.views.get(0):  # Dashboard
                    self.app_state.views[0].invalidate_cache()
            except: pass

        self.refresh_btn.disabled = False
        show_toast(self.app_state.page, f"Updated {len(symbols)} prices ✓", color=ft.Colors.GREEN_600)
        self.load_data(use_cache=False)

    def clear_filters(self, e):
        self.broker_filter.value = "All"
        self.iv_filter.value = "All"
        self.exclude_zero_qty_chk.value = False
        # Force reload when filters are cleared
        self._data_loaded = False
        self._clear_with_reload(e)

    def _apply_with_reload(self):
        """Apply filters."""
        # Use cache: even though filters changed, cache will instantly filter in-memory (2-3ms)
        # The cache check (_cached_filters == current_filters) will detect filter changes and spawn
        # a background thread to fetch from cache, which is blazingly fast.
        self.load_data(_reload_brokers=False, use_cache=True, show_loading=True)

    def _get_current_filters(self):
        """Get current filter state as a hashable tuple for comparison."""
        return (
            self.broker_filter.value,
            self.symbol_filter.value.strip().upper() if self.symbol_filter.value else "",
            self.iv_filter.value,
            self.exclude_zero_qty_chk.value
        )

    def _clear_with_reload(self, e):
        """Clear filters - clear cache to force reload."""
        self.broker_filter.value = "All"
        self.symbol_filter.value = ""
        self.iv_filter.value = "All"
        self.exclude_zero_qty_chk.value = False
        self._data_loaded = False
        self._cached_filters = None
        self.load_data(_reload_brokers=False)

    def invalidate_cache(self):
        """Mark cache stale — fresh DB query will run next time this view is navigated to.
        Does NOT trigger an immediate load (the view may not even be visible)."""
        self._data_loaded = False
        self._cached_filters = None
        self.current_df = None

    def did_mount(self):
        """Lifecycle hook — skip load if main.py already handles it."""
        self._is_active = True
        # If we navigated away mid-load, the completion callback may have bailed
        # due to `_is_active` guard. Ensure the view isn't stuck in a loading state.
        try:
            self.loading_ring.visible = False
            self.loading_status.value = ""
            self.apply_btn.disabled = False
            self.loading_ring.update()
            self.loading_status.update()
            self.apply_btn.update()
        except Exception:
            pass
        if getattr(self, '_skip_load_in_did_mount', False):
            return

    def did_unmount(self):
        """Lifecycle hook — cancel pending work when navigating away."""
        self._is_active = False
        # Cancel pending debounced searches so they don't fire while hidden.
        try:
            if self._search_timer:
                self._search_timer.cancel()
                self._search_timer = None
        except Exception:
            pass
        # Bump sequence so in-flight background fetches can't repaint after unmount.
        try:
            self._load_seq += 1
        except Exception:
            pass

        # Don't leave the UI in a disabled/loading state when hidden.
        try:
            self.loading_ring.visible = False
            self.loading_status.value = ""
            self.apply_btn.disabled = False
        except Exception:
            pass

    def show_snack(self, message: str, color=None):
        sb = ft.SnackBar(ft.Text(message, color=color))
        if hasattr(self.app_state.page, 'open'):
            self.app_state.page.open(sb)
        else:
            self.app_state.page.snack_bar = sb
            sb.open = True
            try:
                sb.update()
            except Exception: pass

    def _copy_all_rows(self, e=None):
        df = getattr(self, 'current_df', None)
        if df is None or getattr(df, 'empty', True):
            self.show_snack("No holdings to copy. Load data first.", color=ft.Colors.ORANGE_400)
            return

        try:
            copy_df = df.copy()

            symbol = copy_df.get('symbol', pd.Series([""] * len(copy_df))).astype(str)
            name = copy_df.get('stock_name', pd.Series(["—"] * len(copy_df))).fillna("—").astype(str)
            qty = pd.to_numeric(copy_df.get('qty', 0), errors='coerce').fillna(0.0)
            avg_price = pd.to_numeric(copy_df.get('avg_price', 0), errors='coerce').fillna(0.0)
            mkt_price = pd.to_numeric(copy_df.get('market_price', 0), errors='coerce').fillna(0.0)
            prev_close = pd.to_numeric(copy_df.get('previous_close', 0), errors='coerce').fillna(0.0)
            running_pnl = pd.to_numeric(copy_df.get('running_pnl', 0), errors='coerce').fillna(0.0)
            total_fees = pd.to_numeric(copy_df.get('total_fees', 0), errors='coerce').fillna(0.0)
            xirr = pd.to_numeric(copy_df.get('xirr', 0), errors='coerce').fillna(0.0)
            cagr = pd.to_numeric(copy_df.get('cagr', 0), errors='coerce').fillna(0.0)
            current_value = pd.to_numeric(copy_df.get('current_value', qty * mkt_price), errors='coerce').fillna(qty * mkt_price)
            signal = copy_df.get('action_signal', pd.Series([None] * len(copy_df))).fillna('N/A').replace('', 'N/A').astype(str)

            daily_pct = (((mkt_price - prev_close) / prev_close) * 100.0).where((prev_close > 0) & (mkt_price > 0))
            daily_disp = daily_pct.map(lambda v: f"{v:+.2f}%" if pd.notna(v) else "—")

            flash_pnl = ((mkt_price - avg_price) * qty).where(mkt_price > 0)
            flash_disp = flash_pnl.map(lambda v: f"₹{v:,.2f}" if pd.notna(v) else "—")

            total_val = float(current_value.sum()) if len(current_value) else 0.0
            weight_pct = ((current_value / total_val) * 100.0).where(total_val > 0, other=0.0)
            weight_disp = weight_pct.map(lambda v: f"{v:.1f}%" if pd.notna(v) else "0.0%")

            xirr_disp = xirr.map(lambda v: "—" if float(v) == -100 else f"{float(v):.2f}%")
            cagr_disp = cagr.map(lambda v: f"{float(v):.2f}%")

            out = pd.DataFrame({
                'Symbol': symbol,
                'Name': name,
                'Qty': qty.map(lambda v: f"{v:,.0f}"),
                'Avg Prc ₹': avg_price.map(lambda v: f"₹{float(v):,.2f}"),
                'Mkt Prc ₹': mkt_price.map(lambda v: f"₹{float(v):,.2f}" if float(v) > 0 else "—"),
                'Daily Chg': daily_disp,
                'Flash PnL ₹': flash_disp,
                'Weight%': weight_disp,
                'XIRR%': xirr_disp,
                'CAGR%': cagr_disp,
                'Real PnL ₹': running_pnl.map(lambda v: f"₹{float(v):,.2f}"),
                'Fees ₹': total_fees.map(lambda v: f"₹{float(v):,.2f}"),
                'IV Signal': signal,
            })

            tsv_data = out.to_csv(sep='\t', index=False)

            page = getattr(self.app_state, 'page', None)
            if page and hasattr(page, 'set_clipboard'):
                try:
                    page.set_clipboard(tsv_data)
                    self.show_snack(f"Copied {len(out)} holdings to clipboard.", color=ft.Colors.GREEN_400)
                    return
                except Exception:
                    pass

            if sys.platform == 'darwin':
                subprocess.run('pbcopy', input=tsv_data.encode(), check=True)
            elif sys.platform == 'win32':
                subprocess.run('clip', input=tsv_data.encode(), check=True, shell=True)
            else:
                subprocess.run(['xclip', '-selection', 'clipboard'], input=tsv_data.encode(), check=True)

            self.show_snack(f"Copied {len(out)} holdings to clipboard.", color=ft.Colors.GREEN_400)
        except Exception as ex:
            self.show_snack(f"Copy failed: {ex}", color=ft.Colors.RED_400)

    def load_data(self, _reload_brokers=True, use_cache=True, show_loading: bool = True):
        """Load data with smart filter-aware caching.

        Args:
            _reload_brokers: Reload broker options if True
            use_cache: If True and cached data exists with same filters, display instantly
            show_loading: If False, do not toggle spinners/disable Apply (useful for debounced typing)
        """
        # Thread guard: if called from a background thread, redispatch to the UI thread
        if threading.current_thread() is not threading.main_thread():
            page = getattr(self.app_state, 'page', None)
            if page:
                async def _dispatch():
                    self.load_data(_reload_brokers=_reload_brokers, use_cache=use_cache)
                page.run_task(_dispatch)
            return

        current_filters = self._get_current_filters()

        # OPTIMIZATION: Smart caching - only reload if filters actually changed and
        # the underlying in-memory cache hasn't been refreshed.
        cache_ver = getattr(getattr(self.app_state, 'data_cache', None), 'version', 0)
        if use_cache and self._data_loaded and self.current_df is not None and self._cached_filters == current_filters and not _reload_brokers and getattr(self, '_cache_version', None) == cache_ver:
            self.render_table()  # Instant render from cache - no DB query!
            return

        # Bump request sequence so in-flight background fetches can't repaint stale results
        self._load_seq += 1
        seq = self._load_seq

        self._data_loaded = True
        self._cached_filters = current_filters  # Remember current filters for next comparison
        if _reload_brokers: self._load_broker_options()
        if show_loading:
            self.loading_ring.visible = True
            self.loading_status.value = "Loading data..."
            self.apply_btn.disabled = True
            try:
                self.loading_ring.update()
                self.loading_status.update()
                self.apply_btn.update()
            except Exception:
                pass
        # Run heavy DB work on a background thread to keep the UI responsive
        threading.Thread(target=self._fetch_and_render, args=(seq,), daemon=True).start()

    def _close_dialog(self, dlg=None):
        try:
            if dlg:
                dlg.open = False
                dlg.update()
            if hasattr(self.app_state.page, 'close'):
                self.app_state.page.close(dlg)
            elif hasattr(self.app_state.page, 'close_dialog'):
                self.app_state.page.close_dialog()
            # Dialog closing doesn't need full page update - dialog.update() handles it
        except: pass

    def _fetch_and_render(self, seq: int):
        _profile = os.environ.get("PTRACKER_NAV_PROFILE")
        _t0 = time.perf_counter() if _profile else None
        
        # Snapshot filter values (safe to read from background thread — they are already set)
        f_broker = self.broker_filter.value if self.broker_filter.value else "All"
        f_symbol = self.symbol_filter.value.strip().upper() if self.symbol_filter.value else ""
        f_signal = self.iv_filter.value if self.iv_filter.value else "All"
        exclude_zero = self.exclude_zero_qty_chk.value

        # Filter/summarize entirely in-memory (no SQLite reads).
        _t_cache = time.perf_counter() if _profile else None
        try:
            filters = HoldingsFilters(
                broker=f_broker or "All",
                symbol_like=f_symbol or "",
                iv_signal=f_signal or "All",
                exclude_zero_qty=bool(exclude_zero),
            )
            df, summary = self.app_state.data_cache.get_holdings_filtered(filters)
            if _t_cache:
                print(f"    [holdings-cache] filter took {time.perf_counter() - _t_cache:.3f}s")
            total_records = int(summary.get("cnt", 0) or 0)
            invested_total = float(summary.get("invested", 0.0) or 0.0)
            pnl_total = float(summary.get("pnl", 0.0) or 0.0)
            total_portfolio_value = float(summary.get("current", 0.0) or 0.0)
            if total_portfolio_value <= 0:
                total_portfolio_value = 1.0
        except Exception:
            # Fallback to empty dataset if cache is unavailable
            df = pd.DataFrame()
            total_records = 0
            invested_total = 0.0
            pnl_total = 0.0
            total_portfolio_value = 1.0

        # Drop stale results if a newer request started while we were fetching
        if seq != self._load_seq:
            return

        # Persist summary + page data
        self.total_records = total_records
        object.__setattr__(self, 'total_portfolio_value', total_portfolio_value)
        object.__setattr__(self, '_summary_invested_total', invested_total)
        object.__setattr__(self, '_summary_pnl_total', pnl_total)

        object.__setattr__(self, 'current_df', df)
        try:
            object.__setattr__(self, '_cache_version', getattr(self.app_state.data_cache, 'version', 0))
        except Exception:
            object.__setattr__(self, '_cache_version', 0)

        # Dispatch UI updates back to the main thread (only if still active)
        async def _finish_on_ui():
            # If this request is stale, do nothing
            if seq != self._load_seq:
                return
            if not getattr(self, '_is_active', False):
                return
            # Only touch spinners/buttons if they were used for this load.
            try:
                if getattr(self.loading_ring, 'visible', False):
                    self.loading_ring.visible = False
                    self.loading_status.value = ""
                    self.apply_btn.disabled = False
                    try:
                        self.loading_ring.update()
                        self.loading_status.update()
                        self.apply_btn.update()
                    except Exception:
                        pass
            except Exception:
                pass
            
            _t_render = time.perf_counter() if _profile else None
            self.render_table()
            if _t_render:
                print(f"    [holdings-render-table] took {time.perf_counter() - _t_render:.3f}s")
            
            if _t0:
                print(f"  [holdings-total-fetch-render] took {time.perf_counter() - _t0:.3f}s")
        page = getattr(self.app_state, 'page', None)
        if page:
            page.run_task(_finish_on_ui)

    def render_table(self):
        _profile = os.environ.get("PTRACKER_NAV_PROFILE")
        _t_start = time.perf_counter() if _profile else None
        
        if self.current_df is None: return
        df = self.current_df
        total_val = getattr(self, 'total_portfolio_value', 1.0) or 1.0

        # Calculate stats for summary card
        active_filters = (self.broker_filter.value != "All" or
                         self.symbol_filter.value.strip() != "" or
                         self.iv_filter.value != "All" or
                         self.exclude_zero_qty_chk.value)

        total_invested = float(getattr(self, '_summary_invested_total', 0.0) or 0.0)
        total_pnl = float(getattr(self, '_summary_pnl_total', 0.0) or 0.0)

        # Update persistent stats card text controls in-place (no widget tree rebuild)
        pnl_color = ft.Colors.GREEN_600 if total_pnl >= 0 else ft.Colors.RED_600
        pnl_icon = "📈" if total_pnl >= 0 else "📉"
        filter_status = "FILTERED" if active_filters else "ALL"
        filter_color = ft.Colors.YELLOW_600 if active_filters else ft.Colors.GREY_500

        self._stats_holdings_val.value = f"{len(df)}"
        self._stats_invested_val.value = f"₹ {total_invested:,.0f}"
        self._stats_current_val.value = f"₹ {total_val:,.0f}"
        self._stats_pnl_val.value = f"{pnl_icon} ₹ {total_pnl:,.0f}"
        self._stats_pnl_val.color = pnl_color
        self._stats_filter_text.value = filter_status
        self._stats_filter_text.color = filter_color
        self._stats_filter_badge.bgcolor = ft.Colors.with_opacity(0.2, filter_color)

        # Update filter feedback in-place
        if active_filters:
            self.filter_feedback.value = f"🔍 Showing {len(df)} results (filtered from {self.total_records})"
            self.filter_feedback.color = ft.Colors.ORANGE_600
        else:
            self.filter_feedback.value = f"📊 All {self.total_records} holdings"
            self.filter_feedback.color = ft.Colors.GREY_600

        # Ensure row pool is large enough for all rows
        _t_pool = time.perf_counter() if _profile else None
        needed = len(df)
        pool_grew = False
        old_pool_len = len(self._row_pool)
        while len(self._row_pool) < needed:
            pool_grew = True
            slot = self._create_row_slot()
            self._row_pool.append(slot)
            # Keep ListView.controls stable: only append when we grow the pool.
            try:
                self._grid_list.controls.append(slot['row'])
            except Exception:
                pass
        if _t_pool and pool_grew:
            print(f"      [row-pool] grew from {old_pool_len} to {needed} took {time.perf_counter() - _t_pool:.3f}s")

        # Populate row pool in-place
        _t_populate = time.perf_counter() if _profile else None
        actual_count = len(df)
        for i, row in enumerate(df.itertuples(index=False)):
            slot = self._row_pool[i]
            row_num = i + 1

            # Avoid row._asdict() during frequent re-renders.
            r_broker = str(getattr(row, 'broker', '') or '')
            r_symbol = str(getattr(row, 'symbol', '') or '')
            stock_name = getattr(row, 'stock_name', None) or "—"
            qty = float(getattr(row, 'qty', 0.0) or 0.0)
            avg_price = float(getattr(row, 'avg_price', 0.0) or 0.0)
            mkt_price = float(getattr(row, 'market_price', 0.0) or 0.0)
            prev_close = float(getattr(row, 'previous_close', 0.0) or 0.0)
            running_pnl = float(getattr(row, 'running_pnl', 0.0) or 0.0)
            total_fees = float(getattr(row, 'total_fees', 0.0) or 0.0)
            xirr_val = float(getattr(row, 'xirr', 0.0) or 0.0)
            cagr_val = float(getattr(row, 'cagr', 0.0) or 0.0)
            current_value = float(getattr(row, 'current_value', 0.0) or 0.0)
            signal = getattr(row, 'action_signal', None) or "N/A"

            # Pre-calculate display values
            unreal_pnl = (mkt_price - avg_price) * qty if mkt_price > 0 else 0.0
            mkt_display = f"₹{mkt_price:,.2f}" if mkt_price > 0 else "—"
            unreal_display = f"₹{unreal_pnl:,.2f}" if mkt_price > 0 else "—"
            unreal_color = (ft.Colors.GREEN_400 if unreal_pnl >= 0 else ft.Colors.RED_400) if mkt_price > 0 else ft.Colors.GREY_600
            xirr_color = (ft.Colors.GREEN_400 if xirr_val >= 0 else ft.Colors.RED_400) if xirr_val != -100 else ft.Colors.GREY_600

            cagr_display = f"{cagr_val:.2f}%" if qty > 0 else "—"
            cagr_color = ft.Colors.GREEN_400 if cagr_val >= 0 else ft.Colors.RED_400

            daily_pct = 0.0
            if prev_close > 0 and mkt_price > 0: daily_pct = ((mkt_price - prev_close) / prev_close) * 100
            daily_color = ft.Colors.GREEN_400 if daily_pct >= 0 else ft.Colors.RED_400
            daily_display = f"{daily_pct:+.2f}%" if prev_close > 0 else "—"

            weight_pct = (current_value / total_val) * 100
            weight_display = f"{weight_pct:.1f}%" if qty > 0 else "0.0%"

            stock_name = self._truncate_stock_name(stock_name)

            running_pnl_color = ft.Colors.GREEN_400 if running_pnl >= 0 else ft.Colors.RED_400
            fees_color = ft.Colors.GREY_500 if total_fees <= 0 else ft.Colors.ORANGE_400

            sig_color = ft.Colors.GREEN_700 if signal == "ACCUMULATE" else (ft.Colors.RED_700 if signal == "REDUCE" else ft.Colors.GREY)

            # Update all text controls in-place
            slot['t_num'].value = str(row_num)
            slot['t_symbol'].value = r_symbol
            slot['t_name'].value = stock_name
            slot['t_qty'].value = f"{qty:,.0f}"
            slot['t_avg_price'].value = f"₹{avg_price:,.2f}"
            slot['t_mkt_price'].value = mkt_display
            slot['t_mkt_price'].color = ft.Colors.CYAN_300 if mkt_price > 0 else ft.Colors.GREY_600
            slot['t_daily_chg'].value = daily_display
            slot['t_daily_chg'].color = daily_color
            slot['t_flash_pnl'].value = unreal_display
            slot['t_flash_pnl'].color = unreal_color
            slot['t_weight'].value = weight_display
            slot['t_xirr'].value = f"{xirr_val:.2f}%" if qty > 0 else "—"
            slot['t_xirr'].color = xirr_color
            slot['t_cagr'].value = cagr_display
            slot['t_cagr'].color = cagr_color
            slot['t_real_pnl'].value = f"₹{running_pnl:,.2f}"
            slot['t_real_pnl'].color = running_pnl_color
            slot['t_fees'].value = f"₹{total_fees:,.2f}"
            slot['t_fees'].color = fees_color
            slot['t_signal_text'].value = signal
            slot['t_signal_chip'].bgcolor = sig_color

            # Update action callbacks only when the row key changes (avoids creating
            # lots of new closures during frequent re-renders).
            row_key = (r_broker, r_symbol)
            if slot.get('_key') != row_key:
                slot['_key'] = row_key
                slot['t_symbol_gd'].on_tap = lambda e, b=r_broker, s=r_symbol: self.show_drilldown_dialog(b, s)
                slot['btn_view'].on_click = lambda e, b=r_broker, s=r_symbol: self.show_drilldown_dialog(b, s)
                slot['btn_edit'].on_click = lambda e, b=r_broker, s=r_symbol, q=qty, p=avg_price, sn=stock_name: self.open_edit_holding(b, s, q, p, sn)
                slot['btn_del'].on_click = lambda e, b=r_broker, s=r_symbol: self.confirm_delete(b, s)

        if _t_populate:
            print(f"      [row-populate] {actual_count} rows took {time.perf_counter() - _t_populate:.3f}s")

        # Show only the rows we populated; keep ListView.controls stable to avoid
        # expensive diffs and re-layout on every render.
        # Zebra striping: alternate subtle background for readability across 15 columns
        _t_toggle = time.perf_counter() if _profile else None
        for i in range(len(self._row_pool)):
            row_ctrl = self._row_pool[i]['row']
            is_visible = i < actual_count
            row_ctrl.visible = is_visible
            if is_visible:
                row_ctrl.bgcolor = "#1A1A1A" if i % 2 == 0 else ft.Colors.TRANSPARENT
        
        if _t_toggle:
            print(f"      [row-visibility] toggle {len(self._row_pool)} rows took {time.perf_counter() - _t_toggle:.3f}s")

        # Targeted updates: avoid re-updating the entire view tree
        _t_update = time.perf_counter() if _profile else None
        
        # Batch all control updates and only call once if possible
        try:
            # Update stats first
            self.stats_card.update()
            self.filter_feedback.update()
        except Exception:
            pass
        
        try:
            # Update ListView last (this is the expensive one)
            self._grid_list.update()
        except Exception:
            pass
        
        if _t_update:
            print(f"      [update-controls] took {time.perf_counter() - _t_update:.3f}s")
        
        if _t_start:
            print(f"    [render-table-total] took {time.perf_counter() - _t_start:.3f}s")

    def _create_row_slot(self):
        """Create one row slot (reused across renders)."""
        _t_num = ft.Text("", size=13, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_symbol = ft.Text("", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.BLUE_400)
        _t_symbol_gd = ft.GestureDetector(mouse_cursor=ft.MouseCursor.CLICK, content=_t_symbol)
        _t_name = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500)
        _t_qty = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_avg_price = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_mkt_price = ft.Text("", size=13, color=ft.Colors.CYAN_300, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_daily_chg = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_flash_pnl = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_weight = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_xirr = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_cagr = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_real_pnl = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_fees = ft.Text("", size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        _t_signal_text = ft.Text("", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        _t_signal_chip = ft.Container(
            content=_t_signal_text,
            bgcolor=ft.Colors.GREY,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=16,
        )

        _btn_view = ft.IconButton(ft.Icons.OPEN_IN_NEW, icon_size=16, icon_color=ft.Colors.BLUE_400, tooltip="View Details")
        _btn_edit = ft.IconButton(ft.Icons.EDIT, icon_size=16, icon_color=ft.Colors.ORANGE_400, tooltip="Edit Holding")
        _btn_del = ft.IconButton(ft.Icons.DELETE, icon_size=16, icon_color=ft.Colors.RED_400, tooltip="Delete")
        _action_row = ft.Row([_btn_view, _btn_edit, _btn_del], spacing=4)

        def _cell(ctrl, width: int, numeric: bool = False):
            return ft.Container(
                content=ctrl,
                width=int(width),
                alignment=ft.alignment.Alignment(1, 0) if numeric else ft.alignment.Alignment(-1, 0),
                padding=ft.padding.symmetric(vertical=10, horizontal=6),
            )

        row = ft.Container(
            content=ft.Row(
                controls=[
                    _cell(_t_num, self.col_widths[0], True),
                    _cell(_t_symbol_gd, self.col_widths[1], False),
                    _cell(_t_name, self.col_widths[2], False),
                    _cell(_t_qty, self.col_widths[3], True),
                    _cell(_t_avg_price, self.col_widths[4], True),
                    _cell(_t_mkt_price, self.col_widths[5], True),
                    _cell(_t_daily_chg, self.col_widths[6], True),
                    _cell(_t_flash_pnl, self.col_widths[7], True),
                    _cell(_t_weight, self.col_widths[8], True),
                    _cell(_t_xirr, self.col_widths[9], True),
                    _cell(_t_cagr, self.col_widths[10], True),
                    _cell(_t_real_pnl, self.col_widths[11], True),
                    _cell(_t_fees, self.col_widths[12], True),
                    _cell(_t_signal_chip, self.col_widths[13], False),
                    ft.Container(
                        content=_action_row,
                        width=int(self.col_widths[14]),
                        alignment=ft.alignment.Alignment(0, 0),
                        padding=ft.padding.symmetric(vertical=6, horizontal=4),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.TRANSPARENT,
        )

        return {
            'row': row,
            't_num': _t_num, 't_symbol': _t_symbol, 't_symbol_gd': _t_symbol_gd,
            't_name': _t_name, 't_qty': _t_qty, 't_avg_price': _t_avg_price,
            't_mkt_price': _t_mkt_price, 't_daily_chg': _t_daily_chg,
            't_flash_pnl': _t_flash_pnl, 't_weight': _t_weight,
            't_xirr': _t_xirr, 't_cagr': _t_cagr, 't_real_pnl': _t_real_pnl,
            't_fees': _t_fees, 't_signal_text': _t_signal_text,
            't_signal_chip': _t_signal_chip,
            'btn_view': _btn_view, 'btn_edit': _btn_edit, 'btn_del': _btn_del,
            '_key': None,
        }

    def confirm_delete(self, broker, symbol):
        from flet_app.components.ui_elements import styled_modal_dialog

        def do_delete(e):
            import threading

            self._close_dialog(dlg)
            self.loading_ring.visible = True
            try: self.loading_ring.update()
            except Exception: pass

            def bg_delete():
                crud.delete_holding_and_trades(broker, symbol)

                # Refresh in-memory datasets so view switching stays cache-only.
                try:
                    self.app_state.refresh_data_cache_async()
                except Exception:
                    pass

                # CRITICAL: Invalidate all view caches when holding deleted
                if hasattr(self.app_state, 'views'):
                    try:
                        if self.app_state.views.get(0):  # Dashboard
                            self.app_state.views[0].invalidate_cache()
                    except: pass
                    try:
                        if self.app_state.views.get(3):  # Trade History
                            self.app_state.views[3].invalidate_cache()
                    except: pass

                async def finish():
                    self.load_data()
                    # Removed redundant refresh_ui() — load_data() already updates the view

                self.app_state.page.run_task(finish)

            threading.Thread(target=bg_delete, daemon=True).start()

        dlg = styled_modal_dialog(
            title="Delete Holding",
            content=ft.Text(f"Delete {symbol} ({broker}) and ALL associated trades permanently?\n\nThis action cannot be undone.", color=ft.Colors.WHITE),
            confirm_text="Delete",
            cancel_text="Cancel",
            on_confirm=do_delete,
            on_cancel=lambda _: self._close_dialog(dlg),
            is_dangerous=True
        )
        self.app_state.page.show_dialog(dlg)

    def open_edit_holding(self, broker, symbol, current_qty, current_price, stock_name):
        """Open the pre-built edit dialog by updating field values (no new AlertDialog created)."""
        self._edit_broker = broker
        self._edit_symbol = symbol

        # Update header in-place
        self._ed_hdr_symbol.value = symbol
        self._ed_hdr_subtitle.value = f"{stock_name} • {broker}"
        self._ed_hdr_holdings.value = f"{current_qty:,.0f} shares @ ₹{current_price:,.2f}"
        current_value = current_qty * current_price
        self._ed_hdr_total_value.value = f"₹{current_value:,.2f}"

        # Update form fields in-place
        self._ed_qty_tb.value = str(current_qty)
        self._ed_price_tb.value = str(current_price)

        # Update summary card
        self._ed_summary_shares.value = f"{current_qty:,.0f}"
        self._ed_summary_avg.value = f"₹{current_price:,.2f}"
        self._ed_summary_total.value = f"₹{current_value:,.2f}"

        # Open pre-built dialog
        if hasattr(self.app_state.page, 'open'):
            self.app_state.page.open(self._edit_dlg)
        else:
            self.app_state.page.show_dialog(self._edit_dlg)

    def _save_edit_dialog(self, e):
        """Save the edit dialog changes."""
        try:
            new_qty = float(self._ed_qty_tb.value)
            new_price = float(self._ed_price_tb.value)

            if new_qty <= 0 or new_price <= 0:
                raise ValueError("Quantity and price must be positive")
        except ValueError:
            self.show_snack("Invalid inputs. Please enter positive numbers.", color=ft.Colors.RED_400)
            return

        broker = self._edit_broker
        symbol = self._edit_symbol

        self._close_dialog(self._edit_dlg)
        self.loading_ring.visible = True
        try:
            self.loading_ring.update()
        except Exception:
            pass

        def bg_save_edit():
            try:
                import flet_app.common.models.crud as crud

                # Update the holding quantity and average price
                crud.update_holding_quantity_and_price(broker, symbol, new_qty, new_price)

                # Refresh in-memory datasets so view switching stays cache-only.
                try:
                    self.app_state.refresh_data_cache_async()
                except Exception:
                    pass

                # Invalidate all view caches
                if hasattr(self.app_state, 'views'):
                    try:
                        if self.app_state.views.get(0):  # Dashboard
                            self.app_state.views[0].invalidate_cache()
                    except: pass

                async def finish():
                    self.load_data()
                    # Removed redundant refresh_ui() — load_data() already updates the view
                    self.show_snack(f"✓ {symbol} holdings updated!", color=ft.Colors.GREEN_400)

                self.app_state.page.run_task(finish)
            except Exception as ex:
                self.show_snack(f"Error updating holding: {str(ex)}", color=ft.Colors.RED_400)

        import threading
        threading.Thread(target=bg_save_edit, daemon=True).start()

    def show_drilldown_dialog(self, broker, symbol):
        from flet_app.components.drilldown import show_drilldown_dialog
        show_drilldown_dialog(self.app_state, symbol, broker)
