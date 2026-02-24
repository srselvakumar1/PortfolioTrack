import flet as ft
import pandas as pd
from state import AppState
from components.ui_elements import page_title, premium_card
from database import get_connection

class TradeHistoryView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True
        object.__setattr__(self, 'current_df', None)
        self._current_edit_date_tb = None
        self.selected_trades = set() # Store selected trade IDs
        
        # Pagination state
        self.current_page = 1
        self.page_size = 25  # Fix 6: reduced from 50 to halve control count per render
        self.total_records = 0

        # Local date filter state
        self._start_date = None
        self._end_date = None

        # Services — FilePicker and DatePicker must be in page.services
        self.export_picker = ft.FilePicker()
        self.start_date_picker = ft.DatePicker(on_change=self._on_start_date_change)
        self.end_date_picker = ft.DatePicker(on_change=self._on_end_date_change)
        self.edit_date_picker = ft.DatePicker(on_change=self._on_edit_date_change)
        self.app_state.page.services.extend([
            self.export_picker,
            self.start_date_picker,
            self.end_date_picker,
            self.edit_date_picker,
        ])

        # Search Controls
        self.broker_filter = ft.Dropdown(
            label="Broker", expand=1,
            options=[ft.dropdown.Option("All")],
            value="All"
        )
        self.symbol_filter = ft.TextField(
            label="Symbol", expand=1,
            hint_text="e.g. RELIANCE"
        )
        self.symbol_filter.on_submit = lambda e: self.load_data()
        self.type_filter = ft.Dropdown(
            label="Type", expand=1,
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("BUY"),
                ft.dropdown.Option("SELL"),
            ],
            value="All"
        )

        self.start_date_btn = ft.ElevatedButton(
            "Start Date", icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.handle_start_date_click
        )
        self.end_date_btn = ft.ElevatedButton(
            "End Date", icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.handle_end_date_click
        )

        # Table — empty by default, populated on Search
        self.select_all_chk = ft.Checkbox(on_change=self.handle_select_all)
        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(self.select_all_chk),
                ft.DataColumn(ft.Text("#", text_align=ft.TextAlign.CENTER), numeric=True),
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("Symbol")),
                ft.DataColumn(ft.Text("Type")),
                ft.DataColumn(ft.Text("Qty", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Buy/Sell Price ₹", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Mkt Price ₹", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Fees ₹", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Actions", text_align=ft.TextAlign.CENTER))
            ],
            rows=[]
        )

        self.status_text = ft.Text(
            "Use the filters above and click Search to load trades.",
            italic=True, color=ft.Colors.GREY_500
        )
        self.loading_ring = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)

        self._load_broker_options()

        # Restore State or Handle Nav Kwargs
        f_symbol = self.app_state.nav_kwargs.get('filter_symbol')
        state = getattr(self.app_state, 'trade_history_state', None)

        if f_symbol:
            self.symbol_filter.value = f_symbol
            self.app_state.nav_kwargs.pop('filter_symbol', None)
            self.load_data()   # Auto-load only when navigated with a filter
        elif state:
            self.broker_filter.value = state.get('broker', "All")
            self.symbol_filter.value = state.get('symbol', "")
            self.type_filter.value = state.get('type', "All")
            self._start_date = state.get('start_date')
            self._end_date = state.get('end_date')
            if self._start_date: self.start_date_btn.text = self._start_date.strftime('%Y-%m-%d')
            if self._end_date: self.end_date_btn.text = self._end_date.strftime('%Y-%m-%d')
            self.current_page = state.get('current_page', 1)
            
            df = state.get('current_df')
            if df is not None:
                object.__setattr__(self, 'current_df', df)
                self.total_records = len(df)
                self.render_table()

        filter_row = ft.Row([
            self.broker_filter,
            self.symbol_filter,
            self.type_filter,
            self.start_date_btn,
            self.end_date_btn,
            ft.ElevatedButton(
                "Search", icon=ft.Icons.SEARCH,
                bgcolor=ft.Colors.BLUE,
                on_click=lambda e: self.load_data()
            ),
            ft.ElevatedButton(
                "Clear", icon=ft.Icons.CLEAR_ALL,
                on_click=self.clear_filters
            ),
            ft.Container(expand=True),
            self.loading_ring,
            ft.ElevatedButton(
                "Bulk Delete", icon=ft.Icons.DELETE_SWEEP,
                bgcolor=ft.Colors.RED_700,
                on_click=self.handle_bulk_delete
            ),
            ft.ElevatedButton(
                "Export CSV", icon=ft.Icons.DOWNLOAD,
                on_click=self.handle_export_click
            )
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

        self.content = ft.Column([
            page_title("Trade History"),
            premium_card(ft.Column([
                filter_row,
                ft.Divider(color="#333333"),
                self.status_text,
                ft.Container(
                    content=ft.Column([
                        ft.Row([self.table], scroll=ft.ScrollMode.ADAPTIVE)
                    ], scroll=ft.ScrollMode.ADAPTIVE),
                    expand=True,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                ),
                pagination_row
            ]), expand=True)
        ], spacing=24)

    def did_unmount(self):
        """Clean up services and save view state when navigating away."""
        # Save state
        self.app_state.trade_history_state = {
            'broker': self.broker_filter.value,
            'symbol': self.symbol_filter.value,
            'type': self.type_filter.value,
            'start_date': self._start_date,
            'end_date': self._end_date,
            'current_page': self.current_page,
            'current_df': getattr(self, 'current_df', None)
        }
        
        try:
            if self.export_picker in self.app_state.page.services:
                self.app_state.page.services.remove(self.export_picker)
            if self.start_date_picker in self.app_state.page.services:
                self.app_state.page.services.remove(self.start_date_picker)
            if self.end_date_picker in self.app_state.page.services:
                self.app_state.page.services.remove(self.end_date_picker)
            if self.edit_date_picker in self.app_state.page.services:
                self.app_state.page.services.remove(self.edit_date_picker)
            self.app_state.page.update()
        except Exception:
            pass

    # ── Picker handlers ────────────────────────────────────────────────────

    def _load_broker_options(self):
        import models.crud as crud
        brokers = crud.get_all_brokers()
        self.broker_filter.options = (
            [ft.dropdown.Option("All")] +
            [ft.dropdown.Option(b) for b in brokers]
        )
        self.broker_filter.value = "All"

    def handle_start_date_click(self, e):
        self.app_state.page.show_dialog(self.start_date_picker)

    def handle_end_date_click(self, e):
        self.app_state.page.show_dialog(self.end_date_picker)

    async def handle_export_click(self, e):
        if self.current_df is None or len(self.current_df) == 0:
            self.app_state.page.snack_bar = ft.SnackBar(ft.Text("No data to export. Run a search first."))
            self.app_state.page.snack_bar.open = True
            self.app_state.page.update()
            return

        path = await self.export_picker.save_file(
            allowed_extensions=["csv"], file_name="trades_export.csv"
        )
        if path and self.current_df is not None:
            import os
            try:
                export_df = self.current_df.drop(columns=['id'], errors='ignore')
                export_df.to_csv(path, index=False)
                self.app_state.page.snack_bar = ft.SnackBar(
                    ft.Text(f"Exported {len(export_df)} trades to {os.path.basename(path)}")
                )
                self.app_state.page.snack_bar.open = True
            except Exception as ex:
                self.app_state.page.snack_bar = ft.SnackBar(
                    ft.Text(f"Export Error: {ex}", color=ft.Colors.RED_400)
                )
                self.app_state.page.snack_bar.open = True
                # Update whole page after export finishes
                self.app_state.page.update()

    # ── Pagination callbacks ────────────────────────────────────────────────

    def handle_prev_page(self, e):
        if self.current_page > 1:
            self.current_page -= 1
            self.render_table()

    def handle_next_page(self, e):
        max_page = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        if self.current_page < max_page:
            self.current_page += 1
            self.render_table()

    # ── Bulk Selection Callbacks ───────────────────────────────────────────

    def handle_select_all(self, e):
        is_checked = e.control.value
        if is_checked and self.current_df is not None:
            # Select only visible page IDs
            start_idx = (self.current_page - 1) * self.page_size
            end_idx = start_idx + self.page_size
            page_df = self.current_df.iloc[start_idx:end_idx]
            self.selected_trades.update(page_df['id'].tolist())
        else:
            self.selected_trades.clear()
            
        self.render_table() # Re-render rows to update checkbox visuals

    def handle_row_select(self, trade_id, is_checked):
        if is_checked:
            self.selected_trades.add(trade_id)
        else:
            self.selected_trades.discard(trade_id)
            self.select_all_chk.value = False
        self.app_state.page.update()

    def handle_bulk_delete(self, e):
        if not self.selected_trades:
            self.app_state.page.snack_bar = ft.SnackBar(ft.Text("Select at least one trade to delete."))
            self.app_state.page.snack_bar.open = True
            self.app_state.page.update()
            return
            
        def do_bulk_delete(e):
            import models.crud as crud
            from engine import rebuild_holdings
            try:
                for tid in list(self.selected_trades):
                    # Explicit cast to int to prevent numpy.int64 SQLite crash
                    crud.delete_trade(int(tid))
                rebuild_holdings()
                self.selected_trades.clear()
                self.select_all_chk.value = False
                self.app_state.page.pop_dialog()
                self.load_data()
                
                self.app_state.page.snack_bar = ft.SnackBar(ft.Text("Bulk deletion successful!"))
                self.app_state.page.snack_bar.open = True
            except Exception as ex:
                self.app_state.page.pop_dialog()
                self.app_state.page.snack_bar = ft.SnackBar(ft.Text(f"Error during bulk delete: {ex}", color=ft.Colors.RED_400))
                self.app_state.page.snack_bar.open = True
                
            self.app_state.refresh_ui()

        dlg = ft.AlertDialog(
            title=ft.Text("Confirm Bulk Deletion"),
            content=ft.Text(
                f"Are you sure you want to permanently delete {len(self.selected_trades)} selected trades?"
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.app_state.page.pop_dialog()),
                ft.TextButton(
                    "Delete All",
                    on_click=do_bulk_delete,
                    style=ft.ButtonStyle(color=ft.Colors.RED_400)
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.app_state.page.show_dialog(dlg)

    # ── Date callbacks ─────────────────────────────────────────────────────

    def _on_start_date_change(self, e):
        self._start_date = e.control.value
        if self._start_date:
            self.start_date_btn.text = self._start_date.strftime('%Y-%m-%d')
        self.app_state.page.update()

    def _on_end_date_change(self, e):
        self._end_date = e.control.value
        if self._end_date:
            self.end_date_btn.text = self._end_date.strftime('%Y-%m-%d')
        self.app_state.page.update()

    def _on_edit_date_change(self, e):
        if self._current_edit_date_tb and e.control.value:
            self._current_edit_date_tb.value = e.control.value.strftime('%Y-%m-%d')
            self.app_state.page.update()

    # ── Data ───────────────────────────────────────────────────────────────

    def clear_filters(self, e):
        self.broker_filter.value = "All"
        self.symbol_filter.value = ""
        self.type_filter.value = "All"
        self._start_date = None
        self._end_date = None
        self.start_date_btn.text = "Start Date"
        self.end_date_btn.text = "End Date"
        self.table.rows.clear()
        self.status_text.value = "Use the filters above and click Search to load trades."
        self.status_text.visible = True
        self.current_page = 1
        self.total_records = 0
        self.selected_trades.clear()
        self.select_all_chk.value = False
        self._update_pagination_ui()
        object.__setattr__(self, 'current_df', None)
        self.app_state.page.update()

    def load_data(self):
        """Offloads the DB query to a background thread so the UI stays responsive."""
        self.current_page = 1
        self.loading_ring.visible = True
        try:
            self.loading_ring.update()
        except Exception:
            pass

        import threading
        threading.Thread(target=self._fetch_and_render, daemon=True).start()

    def _fetch_and_render(self):
        """Runs on background thread: queries DB, then schedules render on UI thread."""
        conn = get_connection()

        query = """
            SELECT t.id, t.date, t.symbol, t.type, t.qty, t.price, t.fee, t.broker,
                   COALESCE(m.current_price, 0) as market_price
            FROM trades t
            LEFT JOIN marketdata m ON t.symbol = m.symbol
            WHERE 1=1
        """
        params = []

        f_broker = self.broker_filter.value
        f_symbol = self.symbol_filter.value.strip().upper() if self.symbol_filter.value else ""
        f_type = self.type_filter.value

        if f_broker and f_broker != "All":
            query += " AND t.broker = ?"
            params.append(f_broker)
        if f_symbol:
            query += " AND t.symbol LIKE ?"
            params.append(f"%{f_symbol}%")
        if f_type and f_type != "All":
            query += " AND t.type = ?"
            params.append(f_type)
        if self._start_date:
            query += " AND t.date >= ?"
            params.append(self._start_date.strftime('%Y-%m-%d'))
        if self._end_date:
            query += " AND t.date <= ?"
            params.append(self._end_date.strftime('%Y-%m-%d'))

        query += " ORDER BY t.date DESC"

        df = pd.read_sql_query(query, conn, params=params)

        object.__setattr__(self, 'current_df', df)
        self.total_records = len(df)

        self.app_state.page.run_task(self._render_from_bg)

    async def _render_from_bg(self):
        """Called on UI thread after background fetch completes."""
        self.loading_ring.visible = False
        self.render_table()

    def render_table(self):
        if self.current_df is None:
            return
            
        df = self.current_df

        if df.empty:
            self.table.rows = []  # FIX 3: direct assign clears cleanly
            self.status_text.value = "No trades found for the selected filters."
            self.status_text.visible = True
            self._update_pagination_ui()
            self.app_state.page.update()
            return

        self.status_text.visible = False
        
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_df = df.iloc[start_idx:end_idx]

        # FIX 2: Build list then batch-assign (faster than per-row .append)
        rows = []
        for i, (_, row) in enumerate(page_df.iterrows(), start=1):
            trade_id = row['id']
            row_num = start_idx + i
            mkt_price = row['market_price']
            mkt_display = f"₹{mkt_price:,.2f}" if mkt_price > 0 else "—"
            trade_color = ft.Colors.GREEN if row['type'] == 'BUY' else ft.Colors.RED

            is_selected = trade_id in self.selected_trades
            chk = ft.Checkbox(
                value=is_selected, 
                on_change=lambda e, tid=trade_id: self.handle_row_select(tid, e.control.value)
            )

            rows.append(
                ft.DataRow(
                    selected=is_selected,
                    cells=[
                        ft.DataCell(chk),
                        ft.DataCell(ft.Text(str(row_num), text_align=ft.TextAlign.CENTER, color=ft.Colors.GREY_500)),
                        ft.DataCell(ft.Text(row['date'])),
                        ft.DataCell(ft.Text(row['symbol'], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(row['type'], color=trade_color)),
                        ft.DataCell(ft.Text(f"{row['qty']}", text_align=ft.TextAlign.RIGHT)),
                        ft.DataCell(ft.Text(f"₹{row['price']:,.2f}", text_align=ft.TextAlign.RIGHT)),
                        ft.DataCell(ft.Text(mkt_display, text_align=ft.TextAlign.RIGHT,
                                            color=ft.Colors.CYAN_300 if mkt_price > 0 else ft.Colors.GREY_600)),
                        ft.DataCell(ft.Text(f"₹{row['fee']:,.2f}", text_align=ft.TextAlign.RIGHT)),
                        ft.DataCell(ft.Row([
                            ft.IconButton(
                                ft.Icons.EDIT, tooltip="Edit Trade",
                                icon_size=16, icon_color=ft.Colors.BLUE_400,
                                on_click=lambda e, r=row: self.open_edit_dialog(r)
                            ),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE, tooltip="Delete Trade",
                                icon_size=16, icon_color=ft.Colors.RED_400,
                                on_click=lambda e, tid=trade_id: self.delete_trade(tid)
                            )
                        ], spacing=0))
                ])
            )

        # FIX 2 (cont): Batch assign instead of clear() + append loop
        self.table.rows = rows

        # FIX 6: Vectorized select-all check using pandas .isin()
        all_visible_selected = page_df['id'].isin(self.selected_trades).all()
        self.select_all_chk.value = bool(len(page_df) > 0 and all_visible_selected)
        
        self._update_pagination_ui()
        self.app_state.page.update()

    def _update_pagination_ui(self):
        max_page = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        self.page_text.value = f"Page {self.current_page} of {max_page} ({self.total_records} trades)"
        self.prev_btn.disabled = self.current_page <= 1
        self.next_btn.disabled = self.current_page >= max_page

    def delete_trade(self, trade_id):
        import models.crud as crud
        from engine import rebuild_holdings
        # FIX 4: Cast to int to avoid numpy.int64 SQLite crash
        crud.delete_trade(int(trade_id))
        rebuild_holdings()
        self.load_data()

    def open_edit_dialog(self, row):
        trade_id = row['id']
        current_date = row['date']
        current_type = row['type']
        
        # UI Elements for Dialog
        date_tb = ft.TextField(label="Date", value=current_date, disabled=True, expand=True)
        
        def open_edit_date_picker(e):
            self._current_edit_date_tb = date_tb
            self.edit_date_picker.value = pd.to_datetime(current_date).to_pydatetime() if current_date else None
            self.app_state.page.show_dialog(self.edit_date_picker)
        
        date_btn = ft.IconButton(
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=open_edit_date_picker
        )
        
        type_dropdown = ft.Dropdown(
            label="Type",
            options=[ft.dropdown.Option("BUY"), ft.dropdown.Option("SELL")],
            value=current_type,
            expand=True
        )
        symbol_tb = ft.TextField(label="Symbol", value=row['symbol'], expand=True)
        qty_tb = ft.TextField(label="Qty", value=str(row['qty']), expand=True)
        price_tb = ft.TextField(label="Price", value=str(row['price']), expand=True)
        fee_tb = ft.TextField(label="Fee", value=str(row['fee']), expand=True)

        def save_edit(e):
            # Validate numeric inputs
            try:
                n_qty = float(qty_tb.value)
                n_price = float(price_tb.value)
                n_fee = float(fee_tb.value)
                new_symbol = symbol_tb.value.strip().upper()
                if not new_symbol:
                    raise ValueError
            except ValueError:
                self.app_state.page.snack_bar = ft.SnackBar(ft.Text("Symbol must not be empty, and Qty, Price, Fee must be numeric.", color=ft.Colors.RED_400))
                self.app_state.page.snack_bar.open = True
                self.app_state.page.update()
                return

            import models.crud as crud
            from engine import rebuild_holdings
            
            # If the user renamed the symbol, bulk-update all trades with the old symbol first
            original_symbol = row['symbol']
            original_broker = row['broker']
            if new_symbol != original_symbol:
                crud.replace_symbol(original_symbol, new_symbol, original_broker)
                
            crud.update_trade(trade_id, date_tb.value, new_symbol, type_dropdown.value, n_qty, n_price, n_fee)
            rebuild_holdings()
            self.app_state.page.pop_dialog()
            self.load_data()

        def cancel_edit(e):
            self.app_state.page.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text(f"Edit Trade: {row['symbol']}"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([date_tb, date_btn]),
                    ft.Row([symbol_tb, type_dropdown]),
                    ft.Row([qty_tb, price_tb]),
                    ft.Row([fee_tb])
                ], tight=True),
                width=400
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_edit),
                ft.ElevatedButton("Save Changes", on_click=save_edit, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.app_state.page.show_dialog(dlg)
