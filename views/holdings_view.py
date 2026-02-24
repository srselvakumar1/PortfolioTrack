import flet as ft
from state import AppState
from components.ui_elements import page_title, premium_card, status_chip
from database import get_connection
import pandas as pd

class HoldingsView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True

        # Pagination state
        self.current_page = 1
        self.page_size = 25  # Fix 6: reduced from 50 to halve control count per render
        self.total_records = 0
        object.__setattr__(self, 'current_df', None)

        # Broker filter dropdown
        self.broker_filter = ft.Dropdown(
            label="Broker", expand=1,
            options=[ft.dropdown.Option("All")],
            value="All"
        )
        self._load_broker_options()

        # IV Signal filter dropdown
        self.iv_filter = ft.Dropdown(
            label="IV Signal", expand=1,
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("ACCUMULATE"),
                ft.dropdown.Option("REDUCE"),
                ft.dropdown.Option("N/A")
            ],
            value="All"
        )

        self.exclude_zero_qty_chk = ft.Checkbox(
            label="Exclude Zero Qty", 
            value=False
        )

        def table_header(text, width=None, numeric=False):
            return ft.DataColumn(
                ft.Container(
                    ft.Text(text, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER if numeric else ft.TextAlign.LEFT),
                    width=width,
                    alignment=ft.alignment.Alignment(0, 0) if numeric else ft.alignment.Alignment(-1, 0)
                ),
                numeric=numeric
            )

        # Column configuration with explicit widths for perfect alignment
        self.col_widths = [30, 80, 160, 60, 90, 90, 80, 100, 70, 70, 100, 100, 50]
        self.columns = [
            ("#", self.col_widths[0], True),
            ("Symbol", self.col_widths[1], False),
            ("Stock Name", self.col_widths[2], False),
            ("Qty", self.col_widths[3], True),
            ("Avg Price ₹", self.col_widths[4], True),
            ("Mkt Price ₹", self.col_widths[5], True),
            ("Daily Chg", self.col_widths[6], True),
            ("Unreal. PnL ₹", self.col_widths[7], True),
            ("Weight%", self.col_widths[8], True),
            ("XIRR%", self.col_widths[9], True),
            ("Realized PnL ₹", self.col_widths[10], True),
            ("IV Signal", self.col_widths[11], False),
            ("Actions", self.col_widths[12], False),
        ]

        # Header Table (Visible only headers)
        self.header_table = ft.DataTable(
            column_spacing=20,
            show_bottom_border=True,
            columns=[table_header(c[0], width=c[1], numeric=c[2]) for c in self.columns],
            rows=[]
        )

        # Data Table (Hidden headers)
        self.table = ft.DataTable(
            column_spacing=20,
            heading_row_height=0, # Use height 0 instead of show_header for compatibility
            columns=[ft.DataColumn(ft.Text(""), numeric=c[2]) for c in self.columns], # Placeholder columns
            rows=[]
        )

        self.refresh_btn = ft.ElevatedButton(
            "Refresh Prices", icon=ft.Icons.REFRESH,
            tooltip="Fetch latest market prices from yfinance"
        )
        self.refresh_btn.on_click = self._handle_refresh_prices

        self.price_status = ft.Text("", size=11, color=ft.Colors.GREY_500, italic=True)
        self.loading_ring = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)

        self.apply_btn = ft.ElevatedButton(
            "Apply", icon=ft.Icons.FILTER_ALT,
            bgcolor=ft.Colors.BLUE,
            on_click=lambda e: self.load_data()
        )

        self.clear_btn = ft.ElevatedButton(
            "Clear", icon=ft.Icons.CLEAR_ALL,
            on_click=self.clear_filters
        )

        filter_row = ft.Row([
            self.broker_filter,
            self.iv_filter,
            self.exclude_zero_qty_chk,
            self.apply_btn,
            self.clear_btn,
            ft.Container(expand=True),
            self.loading_ring,
            self.price_status,
            self.refresh_btn,
        ], alignment=ft.MainAxisAlignment.START)

        # Pagination UI
        self.page_text = ft.Text("Page 1 of 1", size=12, color=ft.Colors.GREY_500)
        self.prev_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT, 
            tooltip="Previous Page",
            on_click=self.handle_prev_page,
            disabled=True
        )
        self.next_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT, 
            tooltip="Next Page",
            on_click=self.handle_next_page,
            disabled=True
        )
        pagination_row = ft.Row([
            self.prev_btn,
            self.page_text,
            self.next_btn
        ], alignment=ft.MainAxisAlignment.CENTER)

        # Sticky Header Layout
        # Both tables are in a Column (vertical), which is in a Row (horizontal scroll)
        # This ensures they scroll horizontally together while the header stays at top vertically.
        self.content = ft.Column([
            page_title("My Holdings"),
            premium_card(ft.Column([
                filter_row,
                ft.Divider(color="#333333"),
                ft.Row(
                    [
                        ft.Column(
                            [
                                self.header_table,
                                ft.Column(
                                    [self.table],
                                    scroll=ft.ScrollMode.ALWAYS,
                                    expand=True,
                                )
                            ],
                            expand=True,
                            spacing=0
                        )
                    ],
                    scroll=ft.ScrollMode.ALWAYS,
                    expand=True,
                ),
                pagination_row
            ], expand=True), expand=True)
        ], spacing=24)

    def _load_broker_options(self):
        import models.crud as crud
        brokers = crud.get_all_brokers()
        self.broker_filter.options = (
            [ft.dropdown.Option("All")] +
            [ft.dropdown.Option(b) for b in brokers]
        )

    async def _handle_refresh_prices(self, e):
        """Fetch live yfinance prices for all symbols in holdings."""
        from engine import fetch_and_update_market_data
        conn = get_connection()
        symbols = [r[0] for r in conn.execute(
            "SELECT DISTINCT symbol FROM holdings WHERE qty > 0"
        ).fetchall()]

        if not symbols:
            self.price_status.value = "No holdings to fetch."
            self.app_state.page.update()
            return

        self.refresh_btn.disabled = True
        self.price_status.value = f"Fetching prices for {len(symbols)} symbols..."
        self.app_state.page.update()

        import asyncio
        await asyncio.to_thread(fetch_and_update_market_data, symbols)

        # Rebuild holdings to trigger XIRR recalculation with new prices
        from engine import rebuild_holdings
        rebuild_holdings()

        self.refresh_btn.disabled = False
        self.price_status.value = f"Updated {len(symbols)} prices ✓"
        self.load_data()

    def clear_filters(self, e):
        self.broker_filter.value = "All"
        self.iv_filter.value = "All"
        self.exclude_zero_qty_chk.value = False
        self.load_data()

    def load_data(self):
        """Offloads the DB query to a background thread so the UI stays responsive."""
        self.current_page = 1
        self.loading_ring.visible = True
        self.apply_btn.disabled = True
        try:
            self.loading_ring.update()
            self.apply_btn.update()
        except Exception:
            pass

        import threading
        threading.Thread(target=self._fetch_and_render, daemon=True).start()

    def _fetch_and_render(self):
        """Runs on background thread: queries DB, then renders on UI thread."""
        f_broker = self.broker_filter.value if self.broker_filter.value else "All"
        f_signal = self.iv_filter.value if self.iv_filter.value else "All"

        query = '''
            SELECT h.broker, h.symbol, h.qty, h.avg_price, h.realized_pnl, h.xirr,
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

        if f_signal and f_signal != "All":
            if f_signal == "N/A":
                query += " AND (a.action_signal IS NULL OR a.action_signal = 'N/A')"
            else:
                query += " AND a.action_signal = ?"
                params.append(f_signal)

        if self.exclude_zero_qty_chk.value:
            query += " AND h.qty > 0"

        conn = get_connection()
        df = pd.read_sql_query(query, conn, params=params)

        # FIX 1: Vectorized current_value instead of apply(axis=1)
        df['current_value'] = df['qty'] * df['market_price'].where(df['market_price'] > 0, df['avg_price'])
        total_val = df['current_value'].sum()

        object.__setattr__(self, 'current_df', df)
        object.__setattr__(self, 'total_portfolio_value', total_val)
        self.total_records = len(df)

        # Re-enter UI thread to render
        self.app_state.page.run_task(self._render_from_bg)

    async def _render_from_bg(self):
        """Called on UI thread after background fetch completes."""
        self.loading_ring.visible = False
        self.apply_btn.disabled = False
        self.render_table()

    def render_table(self):
        if self.current_df is None:
            return
            
        df = self.current_df
        
        # Paginate
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_df = df.iloc[start_idx:end_idx]

        # FIX 2: Pre-compute portfolio weight denominator ONCE outside the loop
        total_val = getattr(self, 'total_portfolio_value', 1.0) or 1.0

        def cell_content(content, width, numeric=False):
            return ft.DataCell(
                ft.Container(
                    content,
                    width=width,
                    alignment=ft.alignment.Alignment(0, 0) if numeric else ft.alignment.Alignment(-1, 0)
                )
            )

        rows = []
        for i, (_, row) in enumerate(page_df.iterrows(), start=1):
            row_num = start_idx + i
            signal = row.get('action_signal') or "N/A"
            sig_color = ft.Colors.GREY
            if signal == "ACCUMULATE": sig_color = ft.Colors.GREEN_700
            elif signal == "REDUCE": sig_color = ft.Colors.RED_700

            avg_price = float(row['avg_price'])
            qty = float(row['qty'])
            mkt_price = float(row['market_price'])
            prev_close = float(row.get('previous_close', 0.0))
            xirr_val = float(row.get('xirr', 0.0))
            
            unreal_pnl = (mkt_price - avg_price) * qty if mkt_price > 0 else 0.0
            mkt_display = f"₹{mkt_price:,.2f}" if mkt_price > 0 else "—"
            unreal_display = f"₹{unreal_pnl:,.2f}" if mkt_price > 0 else "—"
            unreal_color = (ft.Colors.GREEN if unreal_pnl >= 0 else ft.Colors.RED) if mkt_price > 0 else ft.Colors.GREY_600
            xirr_color = (ft.Colors.GREEN if xirr_val >= 0 else ft.Colors.RED) if xirr_val != -100 else ft.Colors.GREY_600

            # Daily Change
            daily_pct = 0.0
            if prev_close > 0 and mkt_price > 0:
                daily_pct = ((mkt_price - prev_close) / prev_close) * 100
            daily_color = ft.Colors.GREEN if daily_pct >= 0 else ft.Colors.RED
            daily_display = f"{daily_pct:+.2f}%" if prev_close > 0 else "—"

            weight_pct = (float(row.get('current_value', 0.0)) / total_val) * 100
            weight_display = f"{weight_pct:.1f}%" if qty > 0 else "0.0%"

            stock_name_str = row.get('stock_name') or "—"
            stock_name_text = ft.Text(
                stock_name_str,
                size=12, # Slightly smaller for better fit
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )

            rows.append(
                ft.DataRow(cells=[
                    cell_content(ft.Text(str(row_num), color=ft.Colors.GREY_500), self.col_widths[0], True),
                    cell_content(
                        ft.TextButton(
                            content=ft.Text(row['symbol'], weight=ft.FontWeight.BOLD, size=12),
                            on_click=lambda e, b=row['broker'], s=row['symbol']: self.show_drilldown_dialog(b, s)
                        ),
                        self.col_widths[1]
                    ),
                    cell_content(stock_name_text, self.col_widths[2]),
                    cell_content(ft.Text(f"{qty:,.0f}"), self.col_widths[3], True),
                    cell_content(ft.Text(f"₹{avg_price:,.2f}"), self.col_widths[4], True),
                    cell_content(ft.Text(mkt_display, color=ft.Colors.CYAN_300 if mkt_price > 0 else ft.Colors.GREY_600), self.col_widths[5], True),
                    cell_content(ft.Text(daily_display, color=daily_color), self.col_widths[6], True),
                    cell_content(ft.Text(unreal_display, color=unreal_color), self.col_widths[7], True),
                    cell_content(ft.Text(weight_display, color=ft.Colors.WHITE70), self.col_widths[8], True),
                    cell_content(ft.Text(f"{xirr_val:.2f}%" if qty > 0 else "—", color=xirr_color), self.col_widths[9], True),
                    cell_content(ft.Text(f"₹{row['realized_pnl']:,.2f}", color=ft.Colors.GREEN if row['realized_pnl'] >= 0 else ft.Colors.RED), self.col_widths[10], True),
                    cell_content(status_chip(signal, sig_color), self.col_widths[11]),
                    cell_content(
                        ft.IconButton(
                            ft.Icons.DELETE_FOREVER,
                            icon_color=ft.Colors.RED_400,
                            icon_size=18,
                            on_click=lambda e, b=row['broker'], s=row['symbol']: self.confirm_delete(b, s)
                        ),
                        self.col_widths[12]
                    )
                ])
            )

        self.table.rows = rows
        self._update_pagination_ui()

        # FIX 3: Single page.update() — removed redundant self.table.update()
        try:
            self.app_state.page.update()
        except Exception:
            pass

    def _update_pagination_ui(self):
        max_page = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        self.page_text.value = f"Page {self.current_page} of {max_page} ({self.total_records} holdings)"
        self.prev_btn.disabled = self.current_page <= 1
        self.next_btn.disabled = self.current_page >= max_page

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
        def do_delete(e):
            import models.crud as crud
            from engine import rebuild_holdings
            crud.delete_holding_and_trades(broker, symbol)
            rebuild_holdings()
            self.app_state.page.pop_dialog()
            self.load_data()
            self.app_state.refresh_ui()

        dlg = ft.AlertDialog(
            title=ft.Text("Confirm Deletion"),
            content=ft.Text(
                f"Delete {symbol} ({broker}) and ALL associated trades permanently?"
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.app_state.page.pop_dialog()),
                ft.TextButton(
                    "Delete",
                    on_click=do_delete,
                    style=ft.ButtonStyle(color=ft.Colors.RED_400)
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.app_state.page.show_dialog(dlg)

    def show_drilldown_dialog(self, broker, symbol):
        from components.drilldown import show_drilldown_dialog
        show_drilldown_dialog(self.app_state, symbol, broker)
