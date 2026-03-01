import flet as ft
from state import AppState
from components.ui_elements import (
    page_title, premium_card, status_chip, show_toast, alternating_row_color, 
    create_column_tooltip_header, stock_name_with_badge, holdings_stats_card, 
    enhanced_filter_panel, sort_indicator, quick_action_buttons, 
    enhanced_pagination_control, color_coded_value_cell, mini_sparkline_cell,
    holdings_view_header, holding_edit_header, holding_edit_field, holding_edit_summary
)
from database import db_session
from models import crud
import pandas as pd
import threading
import time

class HoldingsView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True

        # Caching: Store whether we've already loaded data on first visit
        self._data_loaded = False
        
        # Search debouncing: delay search queries by 300ms after user stops typing
        self._search_timer = None
        self._search_query = ""
        
        # Filter tracking for smart caching: only reload if filters actually changed
        self._cached_filters = None
        
        # Sorting support (Improvement #6)
        self._sort_column = None
        self._sort_ascending = True

        self.current_page = 1
        self.page_size = 25 
        self.total_records = 0
        object.__setattr__(self, 'current_df', None)

        # ✨ ENHANCEMENT: Style filter inputs
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
            hint_text="e.g. AAPL, TCS, INFY",
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.GREY_900,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400)
        )
        self.symbol_filter.on_change = self._on_symbol_search  # Debounced search
        self.symbol_filter.on_submit = lambda e: self._apply_with_reload()  # Also search on Enter

        self.exclude_zero_qty_chk = ft.Checkbox(label="Exclude Zero Qty", value=False)


        def table_header(text, width=None, numeric=False):
            return ft.DataColumn(
                ft.Container(
                    ft.Text(text, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER if numeric else ft.TextAlign.LEFT, color=ft.Colors.BLUE_300),
                    width=width,
                    alignment=ft.alignment.Alignment(0, 0) if numeric else ft.alignment.Alignment(-1, 0)
                ), numeric=numeric
            )

        self.col_widths = [30, 80, 160, 60, 90, 90, 80, 100, 70, 70, 70, 100, 80, 100, 120]
        self.columns = [
            ("#", self.col_widths[0], True), ("Symbol", self.col_widths[1], False), ("Name", self.col_widths[2], False),
            ("Qty", self.col_widths[3], True), ("Avg Prc ₹", self.col_widths[4], True), ("Mkt Prc ₹", self.col_widths[5], True),
            ("Daily Chg", self.col_widths[6], True), ("Flash PnL ₹", self.col_widths[7], True), ("Weight%", self.col_widths[8], True),
            ("XIRR%", self.col_widths[9], True), ("CAGR%", self.col_widths[10], True), ("Real PnL ₹", self.col_widths[11], True),
            ("Fees ₹", self.col_widths[12], True), ("IV Signal", self.col_widths[13], False), ("Actions", self.col_widths[14], False),
        ]

        self.header_table = ft.DataTable(
            column_spacing=20, show_bottom_border=True,
            columns=[table_header(c[0], width=c[1], numeric=c[2]) for c in self.columns], rows=[]
        )

        # Data table columns must match header structure with width constraints for alignment
        def data_column(width=None, numeric=False):
            return ft.DataColumn(
                ft.Container(ft.Text(""), width=width),
                numeric=numeric
            )
        
        self.table = ft.DataTable(
            column_spacing=20, heading_row_height=0, 
            columns=[data_column(width=c[1], numeric=c[2]) for c in self.columns], rows=[]
        )

        self.refresh_btn = ft.ElevatedButton("Refresh Prices", icon=ft.Icons.REFRESH, tooltip="Fetch latest market prices from yfinance")
        self.refresh_btn.on_click = self._handle_refresh_prices
        self.price_status = ft.Text("", size=11, color=ft.Colors.GREY_500, italic=True)
        self.loading_ring = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)
        self.loading_status = ft.Text("", size=11, color=ft.Colors.GREY_400, italic=True)

        self.apply_btn = ft.ElevatedButton("Apply", icon=ft.Icons.FILTER_ALT, bgcolor=ft.Colors.BLUE, on_click=lambda e: self._apply_with_reload())
        self.clear_btn = ft.ElevatedButton("Clear", icon=ft.Icons.CLEAR_ALL, on_click=self._clear_with_reload)

        # ✨ ENHANCEMENT: Use enhanced filter panel (Improvement #1)
        self.filter_panel = enhanced_filter_panel(
            self.broker_filter, self.symbol_filter, self.iv_filter, self.exclude_zero_qty_chk,
            self.apply_btn, self.clear_btn
        )

        # ✨ ENHANCEMENT: Stats card placeholder (Improvement #5)
        self.stats_card = ft.Container()
        
        # ✨ ENHANCEMENT: Filter feedback text (Improvement #9)
        self.filter_feedback = ft.Text("", size=10, color=ft.Colors.GREY_600, italic=True)

        self.page_text = ft.Text("Page 1 of 1", size=12, color=ft.Colors.GREY_500)
        self.prev_btn = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, tooltip="Previous Page", on_click=self.handle_prev_page, disabled=True)
        self.next_btn = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip="Next Page", on_click=self.handle_next_page, disabled=True)
        
        # ✨ ENHANCEMENT: Enhanced pagination display (Improvement #8)
        self.pagination_info = ft.Container()
        pagination_row = ft.Row([self.prev_btn, self.pagination_info, self.next_btn], alignment=ft.MainAxisAlignment.CENTER)

        # ✨ ENHANCEMENT: Enhanced header (Improvement #12)
        self.content = ft.Column([
            holdings_view_header(),
            self.filter_panel,
            self.stats_card,
            self.filter_feedback,
            premium_card(ft.Column([
                ft.Row([ft.Column([self.header_table, ft.Column([self.table], scroll=ft.ScrollMode.ALWAYS, expand=True)], expand=True, spacing=0)], scroll=ft.ScrollMode.ALWAYS, expand=True),
                pagination_row
            ], expand=True), expand=True)
        ], spacing=12)


    def _load_broker_options(self):
        import models.crud as crud
        brokers = crud.get_all_brokers()
        self.broker_filter.options = ([ft.dropdown.Option("All")] + [ft.dropdown.Option(b) for b in brokers])

    def _on_symbol_search(self, e):
        """Debounced symbol search: wait 300ms after user stops typing."""
        if self._search_timer:
            self._search_timer.cancel()
        
        self._search_query = e.control.value
        self._search_timer = threading.Timer(0.3, self._apply_with_reload)
        self._search_timer.daemon = True
        self._search_timer.start()

    async def _handle_refresh_prices(self, e):
        from engine import fetch_and_update_market_data
        with db_session() as conn:
            symbols = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM holdings WHERE qty > 0").fetchall()]
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
        from engine import rebuild_holdings
        rebuild_holdings()

        self.refresh_btn.disabled = False
        show_toast(self.app_state.page, f"Updated {len(symbols)} prices ✓", color=ft.Colors.GREEN_600)
        self.load_data()

    def clear_filters(self, e):
        self.broker_filter.value = "All"
        self.iv_filter.value = "All"
        self.exclude_zero_qty_chk.value = False
        # Force reload when filters are cleared
        self._data_loaded = False
        self._clear_with_reload(e)
    
    def _apply_with_reload(self):
        """Apply filters - clear cache to force reload."""
        self._data_loaded = False
        self._cached_filters = None  # Force filter re-evaluation
        self.load_data(_reload_brokers=False)
    
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
        """Clear all caches when external data changes (broker deleted, portfolio wiped)."""
        self._data_loaded = False
        self._cached_filters = None
        self.current_df = None
        # Force reload next time this view is accessed
        try:
            self.load_data(_reload_brokers=True, use_cache=False)
        except Exception:
            pass  # Silently handle if view not fully initialized

    def load_data(self, _reload_brokers=True, use_cache=True):
        """Load data with smart filter-aware caching.
        
        Args:
            _reload_brokers: Reload broker options if True
            use_cache: If True and cached data exists with same filters, display instantly
        """
        current_filters = self._get_current_filters()
        
        # OPTIMIZATION: Smart caching - only reload if filters actually changed
        # When switching between views without filter changes, use cache
        if use_cache and self._data_loaded and self.current_df is not None and self._cached_filters == current_filters and not _reload_brokers:
            self.current_page = 1
            self.render_table()  # Instant render from cache - no DB query!
            return
        
        self._data_loaded = True
        self._cached_filters = current_filters  # Remember current filters for next comparison
        if _reload_brokers: self._load_broker_options() 
        self.current_page = 1
        self.loading_ring.visible = True
        self.loading_status.value = "Loading data..."
        self.apply_btn.disabled = True
        try:
            self.loading_ring.update()
            self.loading_status.update()
            self.apply_btn.update()
        except Exception: pass
        self._fetch_and_render()

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

    def _fetch_and_render(self):
        f_broker = self.broker_filter.value if self.broker_filter.value else "All"
        f_symbol = self.symbol_filter.value.strip().upper() if self.symbol_filter.value else ""
        f_signal = self.iv_filter.value if self.iv_filter.value else "All"

        # OPTIMIZATION: Get total count for pagination
        count_query = "SELECT COUNT(*) as cnt FROM holdings h WHERE 1=1"
        count_params = []
        if f_broker and f_broker != "All":
            count_query += " AND h.broker = ?"
            count_params.append(f_broker)
        if f_symbol:
            count_query += " AND h.symbol LIKE ? COLLATE NOCASE"
            count_params.append(f"%{f_symbol}%")
        
        # Also get total portfolio value in separate efficient aggregation query
        total_value_query = '''
            SELECT SUM(h.qty * COALESCE(NULLIF(m.current_price, 0), h.avg_price)) as total_value
            FROM holdings h
            LEFT JOIN marketdata m ON h.symbol = m.symbol
            WHERE 1=1
        '''
        total_value_params = []
        if f_broker and f_broker != "All":
            total_value_query += " AND h.broker = ?"
            total_value_params.append(f_broker)
        if f_symbol:
            total_value_query += " AND h.symbol LIKE ? COLLATE NOCASE"
            total_value_params.append(f"%{f_symbol}%")
        if self.exclude_zero_qty_chk.value: 
            count_query += " AND h.qty > 0"
            total_value_query += " AND h.qty > 0"
        
        with db_session() as conn:
            total_count_result = conn.execute(count_query, count_params).fetchone()
            self.total_records = total_count_result[0] if total_count_result else 0
            
            # Get total portfolio value
            total_val_result = conn.execute(total_value_query, total_value_params).fetchone()
            total_portfolio_value = total_val_result[0] if total_val_result and total_val_result[0] else 1.0
            object.__setattr__(self, 'total_portfolio_value', total_portfolio_value)

        # OPTIMIZATION: Fetch ONLY current page + filters using LIMIT/OFFSET at DB level
        # This avoids loading entire portfolio into memory
        start_idx = (self.current_page - 1) * self.page_size
        
        query = '''
            SELECT h.broker, h.symbol, h.qty, h.avg_price, h.running_pnl, h.xirr, h.cagr, h.earliest_date, h.total_fees,
                   a.action_signal,
                   COALESCE(m.current_price, 0) as market_price,
                   COALESCE(m.previous_close, 0) as previous_close,
                   m.stock_name
            FROM holdings h
            LEFT JOIN assets a ON h.symbol = a.symbol
            LEFT JOIN marketdata m ON h.symbol = m.symbol
            WHERE 1=1
        '''
        params = []
        if f_broker and f_broker != "All":
            query += " AND h.broker = ?"
            params.append(f_broker)
        if f_symbol:
            query += " AND h.symbol LIKE ? COLLATE NOCASE"
            params.append(f"%{f_symbol}%")
        if f_signal and f_signal != "All":
            if f_signal == "N/A": query += " AND (a.action_signal IS NULL OR a.action_signal = 'N/A')"
            else:
                query += " AND a.action_signal = ?"
                params.append(f_signal)
        if self.exclude_zero_qty_chk.value: query += " AND h.qty > 0"

        # Add LIMIT/OFFSET at DB level for pagination
        query += f" LIMIT {self.page_size} OFFSET {start_idx}"

        with db_session() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        # Pre-calculate current_value for display
        df['current_value'] = df['qty'] * df['market_price'].where(df['market_price'] > 0, df['avg_price'])

        object.__setattr__(self, 'current_df', df)
        
        self.loading_ring.visible = False
        self.loading_status.value = ""
        self.apply_btn.disabled = False
        try:
            self.loading_status.update()
        except Exception: pass
        self.render_table()

    def render_table(self):
        if self.current_df is None: return
        df = self.current_df
        total_val = getattr(self, 'total_portfolio_value', 1.0) or 1.0

        # ✨ ENHANCEMENT: Calculate stats for summary card (Improvement #5)
        active_filters = (self.broker_filter.value != "All" or 
                         self.symbol_filter.value.strip() != "" or 
                         self.iv_filter.value != "All" or
                         self.exclude_zero_qty_chk.value)
        
        total_invested = df['avg_price'].fillna(0).astype(float).sum() * df['qty'].fillna(0).astype(float).sum() if len(df) > 0 else 0
        total_pnl = df['running_pnl'].fillna(0).astype(float).sum() if len(df) > 0 else 0
        
        self.stats_card.content = holdings_stats_card(
            total_holdings=len(df),
            total_invested=total_invested,
            current_value=total_val,
            total_pnl=total_pnl,
            active_filters=active_filters
        )

        # ✨ ENHANCEMENT: Update filter feedback (Improvement #9)
        if active_filters:
            self.filter_feedback.value = f"🔍 Showing {len(df)} results (filtered from {self.total_records})"
            self.filter_feedback.color = ft.Colors.ORANGE_600
        else:
            self.filter_feedback.value = f"📊 All {self.total_records} holdings"
            self.filter_feedback.color = ft.Colors.GREY_600

        def simple_cell(text, width=None, color=None, numeric=False, row_idx=0):
            """Cell with width constraint, alternating background, and better styling."""
            bg_color = alternating_row_color(row_idx)
            return ft.DataCell(
                ft.Container(
                    ft.Text(text, size=11, color=color or ft.Colors.WHITE, 
                           text_align=ft.TextAlign.RIGHT if numeric else ft.TextAlign.LEFT),
                    width=width,
                    alignment=ft.alignment.Alignment(0, 0) if numeric else ft.alignment.Alignment(-1, 0),
                    bgcolor=bg_color,
                    padding=ft.padding.symmetric(vertical=8, horizontal=4)
                )
            )
        
        def signal_cell(signal, width=None, row_idx=0):
            """Status chip cell with width constraint and alternating background."""
            sig_color = ft.Colors.GREEN_700 if signal == "ACCUMULATE" else (ft.Colors.RED_700 if signal == "REDUCE" else ft.Colors.GREY)
            bg_color = alternating_row_color(row_idx)
            return ft.DataCell(
                ft.Container(
                    status_chip(signal, sig_color),
                    width=width,
                    alignment=ft.alignment.Alignment(-1, 0),
                    bgcolor=bg_color,
                    padding=ft.padding.symmetric(vertical=8, horizontal=4)
                )
            )

        rows = []
        start_idx = (self.current_page - 1) * self.page_size
        for i, row in enumerate(df.itertuples(index=False), start=1):
            row_dict = row._asdict()
            row_num = start_idx + i
            signal = row_dict.get('action_signal', None) or "N/A"

            avg_price = float(row_dict['avg_price'])
            qty = float(row_dict['qty'])
            mkt_price = float(row_dict['market_price'])
            prev_close = float(row_dict.get('previous_close', 0.0))
            xirr_val = float(row_dict.get('xirr', 0.0))
            running_pnl = float(row_dict['running_pnl'])
            total_fees = float(row_dict.get('total_fees', 0.0))
            
            # Pre-calculate display values
            unreal_pnl = (mkt_price - avg_price) * qty if mkt_price > 0 else 0.0
            mkt_display = f"₹{mkt_price:,.2f}" if mkt_price > 0 else "—"
            unreal_display = f"₹{unreal_pnl:,.2f}" if mkt_price > 0 else "—"
            unreal_color = (ft.Colors.GREEN_400 if unreal_pnl >= 0 else ft.Colors.RED_400) if mkt_price > 0 else ft.Colors.GREY_600
            xirr_color = (ft.Colors.GREEN_400 if xirr_val >= 0 else ft.Colors.RED_400) if xirr_val != -100 else ft.Colors.GREY_600

            cagr_val = float(row_dict.get('cagr', 0.0))
            cagr_display = f"{cagr_val:.2f}%" if qty > 0 else "—"
            cagr_color = ft.Colors.GREEN_400 if cagr_val >= 0 else ft.Colors.RED_400

            daily_pct = 0.0
            if prev_close > 0 and mkt_price > 0: daily_pct = ((mkt_price - prev_close) / prev_close) * 100
            daily_color = ft.Colors.GREEN_400 if daily_pct >= 0 else ft.Colors.RED_400
            daily_display = f"{daily_pct:+.2f}%" if prev_close > 0 else "—"

            weight_pct = (float(row_dict.get('current_value', 0.0)) / total_val) * 100
            weight_display = f"{weight_pct:.1f}%" if qty > 0 else "0.0%"
            
            r_broker, r_symbol = str(row_dict['broker']), str(row_dict['symbol'])
            stock_name = row_dict.get('stock_name', None) or "—"

            # ✨ ENHANCEMENT: Color-coded P&L values (Improvement #2)
            running_pnl_color = ft.Colors.GREEN_400 if running_pnl >= 0 else ft.Colors.RED_400
            fees_color = ft.Colors.GREY_500 if total_fees <= 0 else ft.Colors.ORANGE_400

            # Build row with alternating colors (0-indexed here)
            row_idx = i - 1
            
            # ✨ ENHANCEMENT: Quick action buttons (Improvement #7)
            action_buttons = quick_action_buttons(
                r_broker, r_symbol,
                on_view_details=lambda e, b=r_broker, s=r_symbol: self.show_drilldown_dialog(b, s),
                on_edit=lambda e, b=r_broker, s=r_symbol, q=qty, p=avg_price, sn=stock_name: self.open_edit_holding(b, s, q, p, sn),
                on_delete=lambda e, b=r_broker, s=r_symbol: self.confirm_delete(b, s)
            )
            
            rows.append(
                ft.DataRow(cells=[
                    simple_cell(str(row_num), width=self.col_widths[0], color=ft.Colors.GREY_500, numeric=True, row_idx=row_idx),
                    ft.DataCell(ft.Container(
                        ft.GestureDetector(
                            mouse_cursor=ft.MouseCursor.CLICK,
                            on_tap=lambda e, b=r_broker, s=r_symbol: self.show_drilldown_dialog(b, s),
                            content=ft.Text(r_symbol, weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_400)
                        ),
                        width=self.col_widths[1],
                        bgcolor=alternating_row_color(row_idx),
                        padding=ft.padding.symmetric(vertical=8, horizontal=4)
                    )),
                    # ✨ ENHANCEMENT: Stock name with badge (Improvement #4) - simplified for table
                    simple_cell(stock_name, width=self.col_widths[2], row_idx=row_idx),
                    simple_cell(f"{qty:,.0f}", width=self.col_widths[3], numeric=True, row_idx=row_idx),
                    simple_cell(f"₹{avg_price:,.2f}", width=self.col_widths[4], numeric=True, row_idx=row_idx),
                    simple_cell(mkt_display, width=self.col_widths[5], color=ft.Colors.CYAN_300 if mkt_price > 0 else ft.Colors.GREY_600, numeric=True, row_idx=row_idx),
                    simple_cell(daily_display, width=self.col_widths[6], color=daily_color, numeric=True, row_idx=row_idx),
                    simple_cell(unreal_display, width=self.col_widths[7], color=unreal_color, numeric=True, row_idx=row_idx),
                    simple_cell(weight_display, width=self.col_widths[8], numeric=True, row_idx=row_idx),
                    simple_cell(f"{xirr_val:.2f}%" if qty > 0 else "—", width=self.col_widths[9], color=xirr_color, numeric=True, row_idx=row_idx),
                    simple_cell(cagr_display, width=self.col_widths[10], color=cagr_color, numeric=True, row_idx=row_idx),
                    simple_cell(f"₹{running_pnl:,.2f}", width=self.col_widths[11], color=running_pnl_color, numeric=True, row_idx=row_idx),
                    simple_cell(f"₹{total_fees:,.2f}", width=self.col_widths[12], color=fees_color, numeric=True, row_idx=row_idx),
                    signal_cell(signal, width=self.col_widths[13], row_idx=row_idx),
                    ft.DataCell(ft.Container(
                        action_buttons,
                        width=self.col_widths[14],
                        bgcolor=alternating_row_color(row_idx),
                        padding=ft.padding.symmetric(vertical=4, horizontal=4),
                        alignment=ft.alignment.Alignment(0, 0)
                    ))
                ])
            )

        self.table.rows = rows
        self._update_pagination_ui()
        try: 
            self.table.update()
            self.stats_card.update()
            self.filter_feedback.update()
            self.pagination_info.update()
        except Exception: 
            pass


    def _update_pagination_ui(self):
        """Update pagination display with enhanced info (Improvement #8)"""
        max_page = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        self.page_text.value = f"Page {self.current_page} of {max_page} ({self.total_records} holdings)"
        self.prev_btn.disabled = self.current_page <= 1
        self.next_btn.disabled = self.current_page >= max_page
        
        # ✨ ENHANCEMENT: Enhanced pagination info (Improvement #8)
        self.pagination_info.content = enhanced_pagination_control(self.current_page, self.total_records, self.page_size)

    def handle_prev_page(self, e):
        if self.current_page > 1:
            self.current_page -= 1
            self.render_table()

    def handle_next_page(self, e):
        max_page = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        if self.current_page < max_page:
            self.current_page += 1
            self.render_table()

    def confirm_delete(self, broker, symbol):
        from components.ui_elements import styled_modal_dialog
        
        def do_delete(e):
            import threading
            from engine import rebuild_holdings
            
            self._close_dialog(dlg)
            self.loading_ring.visible = True
            try: self.loading_ring.update()
            except Exception: pass

            def bg_delete():
                crud.delete_holding_and_trades(broker, symbol)
                rebuild_holdings()
                
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
                    self.app_state.refresh_ui()
                    
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
        """Open dialog to edit holding quantity and average price"""
        qty_tb = holding_edit_field("Quantity", str(current_qty), ft.KeyboardType.NUMBER, helper_text="Number of shares held")
        price_tb = holding_edit_field("Average Price", str(current_price), ft.KeyboardType.NUMBER, helper_text="Average cost per share in ₹")
        
        summary_card = holding_edit_summary(current_qty, current_price, broker)
        
        def update_summary(e):
            try:
                qty = float(qty_tb.value if isinstance(qty_tb, ft.TextField) else qty_tb.controls[0].value)
                price = float(price_tb.value if isinstance(price_tb, ft.TextField) else price_tb.controls[0].value)
                
                total_value = qty * price
                summary_card.content.controls[1].controls[2].controls[1].value = f"₹{total_value:,.2f}"
                summary_card.update()
            except:
                pass
        
        if isinstance(qty_tb, ft.TextField):
            qty_tb.on_change = update_summary
            price_tb.on_change = update_summary
        else:
            qty_tb.controls[0].on_change = update_summary
            price_tb.controls[0].on_change = update_summary

        dlg = ft.AlertDialog(
            title=None,
            content=ft.Container(
                content=ft.Column([
                    holding_edit_header(symbol, stock_name, broker, current_qty, current_price),
                    ft.Divider(height=12, color="#334155"),
                    
                    ft.Text("Edit Holdings", size=12, weight=ft.FontWeight.BOLD, color="#3B82F6"),
                    qty_tb,
                    price_tb,
                    
                    ft.Container(height=8),
                    summary_card,
                ], tight=True, spacing=10),
                width=420,
                padding=ft.padding.symmetric(horizontal=20, vertical=20)
            ),
            actions_alignment=ft.MainAxisAlignment.END,
        )

        def save_edit(e):
            try:
                qty_val = qty_tb.value if isinstance(qty_tb, ft.TextField) else qty_tb.controls[0].value
                price_val = price_tb.value if isinstance(price_tb, ft.TextField) else price_tb.controls[0].value
                
                new_qty = float(qty_val)
                new_price = float(price_val)
                
                if new_qty <= 0 or new_price <= 0:
                    raise ValueError("Quantity and price must be positive")
            except ValueError:
                self.show_snack("Invalid inputs. Please enter positive numbers.", color=ft.Colors.RED_400)
                return

            self._close_dialog(dlg)
            self.loading_ring.visible = True
            self.loading_ring.update()
            
            def bg_save_edit():
                try:
                    import models.crud as crud
                    from engine import rebuild_holdings
                    
                    # Update the holding quantity and average price
                    crud.update_holding_quantity_and_price(broker, symbol, new_qty, new_price)
                    rebuild_holdings()
                    
                    # Invalidate all view caches
                    if hasattr(self.app_state, 'views'):
                        try:
                            if self.app_state.views.get(0):  # Dashboard
                                self.app_state.views[0].invalidate_cache()
                        except: pass
                    
                    async def finish():
                        self.load_data()
                        self.app_state.refresh_ui()
                        self.show_snack(f"✓ {symbol} holdings updated!", color=ft.Colors.GREEN_400)
                    
                    self.app_state.page.run_task(finish)
                except Exception as ex:
                    self.show_snack(f"Error updating holding: {str(ex)}", color=ft.Colors.RED_400)
            
            import threading
            threading.Thread(target=bg_save_edit, daemon=True).start()

        dlg.actions = [
            ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
            ft.ElevatedButton("Save Changes", on_click=save_edit, bgcolor="#10B981", color=ft.Colors.WHITE)
        ]
        self.app_state.page.show_dialog(dlg)

    def show_drilldown_dialog(self, broker, symbol):
        from components.drilldown import show_drilldown_dialog
        show_drilldown_dialog(self.app_state, symbol, broker)