import flet as ft
import pandas as pd
from datetime import datetime, timedelta
from state import AppState
from components.ui_elements import page_title, premium_card, show_toast, alternating_row_color, styled_modal_dialog, trade_edit_header, trade_edit_field, trade_edit_calculation_card, trade_edit_form_section, trade_edit_divider
from database import db_session
import threading

class TradeHistoryView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True
        object.__setattr__(self, 'current_df', None)
        self._current_edit_date_tb = None
        self.selected_trades = set() 
        
        # Search debouncing
        self._search_timer = None
        
        self.current_page = 1
        self.page_size = 25  
        self.total_records = 0
        
        # Calculate default dates: show all trades (5 years back to today)
        today = datetime.now()
        all_trades_start = today - timedelta(days=1825)  # ~5 years
        self._start_date = all_trades_start.date()  # Store as date for filter logic
        self._end_date = today.date()
        
        self.sort_column_index = 2 # Date as default
        self.sort_ascending = True
        
        # Cache for pre-calculated running stats to avoid re-computation on every filter change
        self._calc_cache = {}
        self._cache_key = None
        
        # Data caching: store loaded data and filters to avoid re-querying on nav
        self._data_loaded = False
        self._cached_df = None
        self._cached_filters = None
        self._is_preloading = False  # Flag to skip rendering during pre-load

        self.export_picker = ft.FilePicker()
        
        # Initialize date pickers with default values (all trades visible by default)
        self.start_date_picker = ft.DatePicker(
            value=all_trades_start,
            on_change=self._on_start_date_change
        )
        self.end_date_picker = ft.DatePicker(
            value=today,
            on_change=self._on_end_date_change
        )
        self.edit_date_picker = ft.DatePicker(on_change=self._on_edit_date_change)
        
        self.broker_filter = ft.Dropdown(
            label="Broker", expand=1,
            options=[ft.dropdown.Option("All")],
            value="All",
            label_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_300),
            dense=False,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=12)
        )
        self._load_broker_options()

        self.symbol_filter = ft.TextField(
            label="Symbol", expand=1,
            hint_text="e.g. ITC",
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.GREY_900,
            label_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_300)
        )
        self.symbol_filter.on_change = self._on_symbol_search  # Debounced search
        self.symbol_filter.on_submit = lambda e: self.load_data()  # Also search on Enter
        
        self.type_filter = ft.Dropdown(
            label="Type", expand=1,
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("BUY"),
                ft.dropdown.Option("SELL"),
            ],
            value="All",
            label_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_300),
            dense=False,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=12)
        )

        # Create date buttons with default date text
        self.start_date_btn = ft.ElevatedButton(
            self._start_date.strftime('%Y-%m-%d'),
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.handle_start_date_click
        )
        self.end_date_btn = ft.ElevatedButton(
            self._end_date.strftime('%Y-%m-%d'),
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.handle_end_date_click
        )

        self.select_all_chk = ft.Checkbox(on_change=self.handle_select_all)
        self.table = ft.DataTable(
            sort_column_index=self.sort_column_index,
            sort_ascending=self.sort_ascending,
            columns=[
                ft.DataColumn(self.select_all_chk),
                ft.DataColumn(ft.Text("#", text_align=ft.TextAlign.CENTER), numeric=True),
                ft.DataColumn(ft.Text("Date"), on_sort=self.handle_sort),
                ft.DataColumn(ft.Text("Trade ID")),
                ft.DataColumn(ft.Text("Symbol"), on_sort=self.handle_sort),
                ft.DataColumn(ft.Text("Type")),
                ft.DataColumn(ft.Text("Qty", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Price ₹", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Run. Qty", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("AvgCost ₹", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Running PnL ₹", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Fees ₹", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Actions", text_align=ft.TextAlign.CENTER))
            ],
            rows=[]
        )

        self.summary_table = ft.DataTable(
            heading_row_height=1,
            columns=[
                ft.DataColumn(ft.Text("")), # chk
                ft.DataColumn(ft.Text("")), # #
                ft.DataColumn(ft.Text("")), # Date
                ft.DataColumn(ft.Text("")), # ID
                ft.DataColumn(ft.Text("")), # Symbol
                ft.DataColumn(ft.Text("")), # Type
                ft.DataColumn(ft.Text("Qty", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("")), # Price
                ft.DataColumn(ft.Text("")), # Run Qty
                ft.DataColumn(ft.Text("")), # Avg Cost
                ft.DataColumn(ft.Text("PnL", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text("Fees", text_align=ft.TextAlign.RIGHT), numeric=True),
                ft.DataColumn(ft.Text(""))  # Actions
            ],
            rows=[]
        )

        self.status_text = ft.Text("Loading trades with default filters...", italic=True, color=ft.Colors.GREY_500)
        self.loading_ring = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)
        self.loading_status = ft.Text("", size=11, color=ft.Colors.GREY_400, italic=True)

        f_symbol = self.app_state.nav_kwargs.get('filter_symbol')
        state = getattr(self.app_state, 'trade_history_state', None)

        if f_symbol:
            self.symbol_filter.value = f_symbol
            self.app_state.nav_kwargs.pop('filter_symbol', None)
            # ONLY load if explicitly coming from drilldown; for normal first visit, don't auto-load
            self.load_data(_reload_brokers=False, use_cache=True)
        elif state:
            self.broker_filter.value = state.get('broker', "All")
            self.symbol_filter.value = state.get('symbol', "")
            self.type_filter.value = state.get('type', "All")
            self._start_date = state.get('start_date', self._start_date)
            self._end_date = state.get('end_date', self._end_date)
            if self._start_date: self.start_date_btn.text = self._start_date.strftime('%Y-%m-%d')
            if self._end_date: self.end_date_btn.text = self._end_date.strftime('%Y-%m-%d')
            self.current_page = state.get('current_page', 1)
            df = state.get('current_df')
            if df is not None:
                object.__setattr__(self, 'current_df', df)
                self.total_records = len(df)
                self.render_table()
        else:
            # First visit: auto-load with default dates (yesterday to today)
            self._data_loaded = False
            # Will auto-load in did_mount via load_data()

        # Reorganized filter layout for better visibility - all controls in one row
        filter_row = ft.Row([
            ft.Container(self.broker_filter, width=120),
            ft.Container(self.symbol_filter, width=98),
            ft.Container(self.type_filter, width=98),
            ft.Container(
                content=ft.Column([
                    ft.Text("Start Date", size=14, color=ft.Colors.GREY_400),
                    self.start_date_btn
                ], spacing=3, tight=True),
                width=155
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("End Date", size=14, color=ft.Colors.GREY_400),
                    self.end_date_btn
                ], spacing=3, tight=True),
                width=150
            ),
            ft.ElevatedButton("Search", icon=ft.Icons.SEARCH, bgcolor=ft.Colors.BLUE, on_click=lambda e: self.load_data(_reload_brokers=False), width=115), 
            ft.ElevatedButton("Clear", icon=ft.Icons.CLEAR_ALL, bgcolor=ft.Colors.GREY_600, on_click=self.clear_filters, width=102),
            ft.ElevatedButton("Bulk Del", icon=ft.Icons.DELETE_SWEEP, bgcolor=ft.Colors.RED_600, on_click=self.handle_bulk_delete, width=125),
            ft.ElevatedButton("Export", icon=ft.Icons.DOWNLOAD, tooltip="Export CSV", on_click=self.handle_export_click, width=112),
            ft.Container(expand=True),
            self.loading_ring, 
            self.loading_status
        ], 
        alignment=ft.MainAxisAlignment.START, 
        vertical_alignment=ft.CrossAxisAlignment.CENTER, 
        spacing=10,
        wrap=False,
        scroll=ft.ScrollMode.AUTO)

        self.page_text = ft.Text("Page 1 of 1", size=12, color=ft.Colors.GREY_500)
        self.prev_btn = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, tooltip="Previous Page", on_click=self.handle_prev_page, disabled=True)
        self.next_btn = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip="Next Page", on_click=self.handle_next_page, disabled=True)
        pagination_row = ft.Row([self.prev_btn, self.page_text, self.next_btn], alignment=ft.MainAxisAlignment.CENTER)

        # Store references to table rows for horizontal scroll management
        self.table_row = ft.Row([self.table], scroll=ft.ScrollMode.ADAPTIVE)
        self.summary_row = ft.Row([self.summary_table], scroll=ft.ScrollMode.ADAPTIVE)

        self.content = ft.Column([
            page_title("Trade History Details"),
            premium_card(ft.Column([
                # Wrap your filter_row here:
                ft.Container(
                    content=filter_row, 
                    height=90,  # Increased from 70 to give more vertical space
                    padding=ft.padding.symmetric(vertical=10, horizontal=0)
                ),
                ft.Divider(color="#27F5B0"),
                self.status_text,
                ft.Container(
                    content=ft.Column([
                        self.table_row,
                        self.summary_row
                    ], scroll=ft.ScrollMode.ADAPTIVE),
                    expand=True, clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                ),
                pagination_row
            ]), expand=True)
        ], spacing=24) 

    # --- UNIVERSAL DIALOG / PICKER HELPERS ---
    def _open_dialog(self, dlg):
        if hasattr(self.app_state.page, 'open'):
            self.app_state.page.open(dlg)
        else:
            self.app_state.page.show_dialog(dlg)

    def _close_dialog(self, dlg=None):
        try:
            if dlg:
                dlg.open = False
                dlg.update()
            if hasattr(self.app_state.page, 'close'):
                self.app_state.page.close(dlg)
            elif hasattr(self.app_state.page, 'close_dialog'):
                self.app_state.page.close_dialog()
            # Dialog closing handled by dlg.update() - no page update needed
        except: pass

    def show_snack(self, message: str, color=None):
        sb = ft.SnackBar(ft.Text(message, color=color))
        if hasattr(self.app_state.page, 'open'):
            self.app_state.page.open(sb)
        else:
            self.app_state.page.snack_bar = sb
            sb.open = True
            try:
                sb.update()  # Targeted update on snack bar only
            except Exception: pass

    def did_mount(self):
        """Lifecycle hook."""
        for dp in [self.start_date_picker, self.end_date_picker]:
            if dp not in self.app_state.page.overlay:
                self.app_state.page.overlay.append(dp)
        if hasattr(self, 'edit_date_picker') and self.edit_date_picker not in self.app_state.page.overlay:
            self.app_state.page.overlay.append(self.edit_date_picker)
        
        # Auto-load data with default dates on first visit - but skip on re-mounts if already loaded
        if not self._data_loaded and self.current_df is None:
            self.loading_ring.visible = True
            self.loading_status.value = "Loading trades..."
            try:
                self.loading_ring.update()
                self.loading_status.update()
            except Exception: pass
            self.load_data(_reload_brokers=True, use_cache=True)

    def did_unmount(self):
        """Save filter state when navigating away."""
        self.app_state.trade_history_state = {
            'broker': self.broker_filter.value,
            'symbol': self.symbol_filter.value,
            'type': self.type_filter.value,
            'start_date': self._start_date,
            'end_date': self._end_date,
            'current_page': self.current_page,
            'current_df': getattr(self, 'current_df', None)
        }
    
    async def handle_export_click(self, e):
        """Triggers the Save File picker for exporting trades."""
        if self.current_df is None or len(self.current_df) == 0:
            self.show_snack("No data to export. Run a search first.")
            return
        try:
            path = await self.export_picker.save_file(
                allowed_extensions=["csv"],
                file_name="trades_export.csv"
            )
            if path:
                import os
                export_df = self.current_df.drop(columns=['id'], errors='ignore')
                export_df.to_csv(path, index=False)
                self.show_snack(f"Exported {len(export_df)} trades to {os.path.basename(path)}")
        except Exception as ex:
            self.show_snack(f"Export Error: {ex}", color=ft.Colors.RED_400)

    def _load_broker_options(self):
        import models.crud as crud
        brokers = crud.get_all_brokers()
        self.broker_filter.options = ([ft.dropdown.Option("All")] + [ft.dropdown.Option(b) for b in brokers])

    def _on_symbol_search(self, e):
        """Debounced symbol search: wait 300ms after user stops typing."""
        search_val = self.symbol_filter.value.strip().upper() if self.symbol_filter.value else ""
        print(f"[TRADE_HISTORY] _on_symbol_search triggered, value='{search_val}', debouncing for 300ms...")
        
        if self._search_timer:
            self._search_timer.cancel()
        
        self._search_timer = threading.Timer(0.3, self.load_data)
        self._search_timer.daemon = True
        self._search_timer.start()

    async def handle_start_date_click(self, e):
        # Ensure picker has current value before opening
        try:
            if self._start_date:
                self.start_date_picker.value = self._start_date
            else:
                import datetime
                self.start_date_picker.value = datetime.date.today()
        except Exception as ex:
            print(f"[ERROR] Failed to set start_date_picker value: {ex}")
        
        # Open the picker
        try:
            if hasattr(self.app_state.page, 'open'):
                self.app_state.page.open(self.start_date_picker)
            else:
                self.start_date_picker.open = True
                self.start_date_picker.update()
        except Exception as ex:
            print(f"[ERROR] Failed to open start_date_picker: {ex}")

    async def handle_end_date_click(self, e):
        # Ensure picker has current value before opening
        try:
            if self._end_date:
                self.end_date_picker.value = self._end_date
            else:
                import datetime
                self.end_date_picker.value = datetime.date.today()
        except Exception as ex:
            print(f"[ERROR] Failed to set end_date_picker value: {ex}")
        
        # Open the picker
        try:
            if hasattr(self.app_state.page, 'open'):
                self.app_state.page.open(self.end_date_picker)
            else:
                self.end_date_picker.open = True
                self.end_date_picker.update()
        except Exception as ex:
            print(f"[ERROR] Failed to open end_date_picker: {ex}")

    def _on_start_date_change(self, e):
        print(f"[TRADE_HISTORY] _on_start_date_change triggered, picker.value={self.start_date_picker.value}")
        if self.start_date_picker.value:
            # Extract date from picker value (could be datetime or date)
            new_date = self.start_date_picker.value.date() if hasattr(self.start_date_picker.value, 'date') else self.start_date_picker.value
            
            # Only update and reload if date actually changed
            if new_date != self._start_date:
                print(f"[TRADE_HISTORY] Start date changed: {self._start_date} → {new_date}")
                self._start_date = new_date
                new_text = self._start_date.strftime('%Y-%m-%d')
                print(f"[TRADE_HISTORY] Updating start_date_btn.text to: {new_text}")
                self.start_date_btn.text = new_text
                
                # Clear cache to force reload with new date
                self._data_loaded = False
                
                # Defer reload to after event is fully processed
                async def deferred_reload():
                    try:
                        self.load_data(_reload_brokers=False, use_cache=False)
                    except Exception as ex:
                        print(f"[TRADE_HISTORY] Error loading data after date change: {ex}")
                
                if hasattr(self.app_state, 'page') and self.app_state.page:
                    self.app_state.page.run_task(deferred_reload)
            else:
                print(f"[TRADE_HISTORY] Start date unchanged: {self._start_date}")

    def _on_end_date_change(self, e):
        print(f"[TRADE_HISTORY] _on_end_date_change triggered, picker.value={self.end_date_picker.value}")
        if self.end_date_picker.value:
            # Extract date from picker value (could be datetime or date)
            new_date = self.end_date_picker.value.date() if hasattr(self.end_date_picker.value, 'date') else self.end_date_picker.value
            
            # Only update and reload if date actually changed
            if new_date != self._end_date:
                print(f"[TRADE_HISTORY] End date changed: {self._end_date} → {new_date}")
                self._end_date = new_date
                new_text = self._end_date.strftime('%Y-%m-%d')
                print(f"[TRADE_HISTORY] Updating end_date_btn.text to: {new_text}")
                self.end_date_btn.text = new_text
                
                # Clear cache to force reload with new date
                self._data_loaded = False
                
                # Defer reload to after event is fully processed
                async def deferred_reload():
                    try:
                        self.load_data(_reload_brokers=False, use_cache=False)
                    except Exception as ex:
                        print(f"[TRADE_HISTORY] Error loading data after date change: {ex}")
                
                if hasattr(self.app_state, 'page') and self.app_state.page:
                    self.app_state.page.run_task(deferred_reload)
            else:
                print(f"[TRADE_HISTORY] End date unchanged: {self._end_date}")

    def _on_edit_date_change(self, e):
        if self._current_edit_date_tb and self.edit_date_picker.value:
            self._current_edit_date_tb.value = self.edit_date_picker.value.strftime('%Y-%m-%d')
            try:
                self._current_edit_date_tb.update()  # Targeted update on textfield only
            except Exception: pass

    def handle_prev_page(self, e):
        if self.current_page > 1:
            self.current_page -= 1
            self.render_table()

    def handle_next_page(self, e):
        max_page = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        if self.current_page < max_page:
            self.current_page += 1
            self.render_table()

    def handle_select_all(self, e):
        is_checked = e.control.value
        if is_checked and self.current_df is not None:
            start_idx = (self.current_page - 1) * self.page_size
            end_idx = start_idx + self.page_size
            page_df = self.current_df.iloc[start_idx:end_idx]
            self.selected_trades.update(page_df['trade_id'].astype(str).tolist())
        else:
            self.selected_trades.clear()
        self.render_table() 

    def handle_row_select(self, trade_id, is_checked):
        if is_checked: self.selected_trades.add(str(trade_id))
        else:
            self.selected_trades.discard(str(trade_id))
            self.select_all_chk.value = False
        # Row selection just updates state - table.rows already updated, no page.update() needed

    def handle_bulk_delete(self, e):
        if not self.selected_trades:
            self.show_snack("Select at least one trade to delete.")
            return

        dlg = ft.AlertDialog(
            title=ft.Text("Confirm Bulk Deletion"),
            content=ft.Text(f"Are you sure you want to permanently delete {len(self.selected_trades)} selected trades?"),
            actions_alignment=ft.MainAxisAlignment.END,
        )
            
        def do_bulk_delete(e):
            import models.crud as crud
            import threading
            from engine import rebuild_holdings
            
            # Clear caches since data is changing
            self._calc_cache.clear()
            self._data_loaded = False
            self._cached_filters = None
            
            self._close_dialog(dlg)
            self.loading_ring.visible = True
            self.loading_ring.update()

            def bg_bulk_delete():
                try:
                    import models.crud as crud_module
                    # Get broker info for each trade being deleted
                    trade_ids_to_delete = list(self.selected_trades)
                    trade_brokers = {}
                    
                    with db_session() as conn:
                        placeholders = ','.join('?' * len(trade_ids_to_delete))
                        query = f"SELECT trade_id, broker FROM trades WHERE trade_id IN ({placeholders})"
                        cursor = conn.cursor()
                        cursor.execute(query, trade_ids_to_delete)
                        for row in cursor.fetchall():
                            trade_brokers[row[0]] = row[1]
                    
                    # Delete each trade with its broker
                    for tid in trade_ids_to_delete:
                        broker = trade_brokers.get(tid)
                        if broker:
                            crud_module.delete_trade(broker, str(tid))
                    
                    rebuild_holdings()
                    
                    # CRITICAL: Invalidate all view caches when trades bulk deleted
                    if hasattr(self.app_state, 'views'):
                        try:
                            if self.app_state.views.get(0):  # Dashboard
                                self.app_state.views[0].invalidate_cache()
                        except: pass
                        try:
                            if self.app_state.views.get(1):  # Holdings
                                self.app_state.views[1].invalidate_cache()
                        except: pass
                    
                    async def finish():
                        self.selected_trades.clear()
                        self.select_all_chk.value = False
                        self.load_data(_reload_brokers=False, use_cache=False)  # Force fresh query with same filters
                        self.show_snack("Bulk deletion successful!")
                        self.app_state.refresh_ui()

                    self.app_state.page.run_task(finish)
                except Exception as ex:
                    error_msg = str(ex)  # Capture error message to avoid scope issues
                    async def err_finish():
                        self.show_snack(f"Error during bulk delete: {error_msg}", color=ft.Colors.RED_400)
                        self.load_data(_reload_brokers=False, use_cache=False)  # Refresh with search criteria on error
                        self.app_state.refresh_ui()
                    self.app_state.page.run_task(err_finish)
                    
            threading.Thread(target=bg_bulk_delete, daemon=True).start()

        dlg.actions = [
            ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
            ft.TextButton("Delete All", on_click=do_bulk_delete, style=ft.ButtonStyle(color=ft.Colors.RED_400)),
        ]
        self._open_dialog(dlg)

    def invalidate_cache(self):
        """Clear all caches when external data changes (broker deleted, portfolio wiped)."""
        self._calc_cache.clear()
        self._data_loaded = False
        self._cached_df = None
        self._cached_filters = None
        self.current_df = None
        # Force reload next time this view is accessed
        try:
            self.load_data(_reload_brokers=True, use_cache=False)
        except Exception:
            pass  # Silently handle if view not fully initialized

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
        # Clear caches when filters change
        self._data_loaded = False
        self._calc_cache.clear()
        self._cached_filters = None

    def handle_sort(self, e):
        self.sort_column_index = e.column_index
        self.sort_ascending = e.ascending
        self.table.sort_column_index = e.column_index
        self.table.sort_ascending = e.ascending
        self.load_data(_reload_brokers=False)

    def load_data(self, _reload_brokers=True, use_cache=True):
        """Load data with instant cache display on re-navigation.
        
        Args:
            _reload_brokers: Reload broker options if True
            use_cache: If True and cached data exists, display it instantly (no spinner)
        """
        # Check if filters have changed - if not, use cached data
        current_filters = (
            self.broker_filter.value,
            self.symbol_filter.value.strip().upper() if self.symbol_filter.value else "",
            self.type_filter.value,
            self._start_date.strftime('%Y-%m-%d') if self._start_date else None,
            self._end_date.strftime('%Y-%m-%d') if self._end_date else None
        )
        
        print(f"[TRADE_HISTORY] load_data called: broker={current_filters[0]}, symbol={current_filters[1]}, type={current_filters[2]}, dates={current_filters[3]} to {current_filters[4]}")
        
        # If cache exists and filters unchanged and we're re-visiting, display cached data instantly
        if use_cache and self._data_loaded and self._cached_filters == current_filters and self.current_df is not None:
            if not self._is_preloading:
                print(f"[TRADE_HISTORY] Using cached data - instant display (filters unchanged)")
            self.current_page = 1
            self.render_table()  # Instant render from cache
            return
        
        self._cached_filters = current_filters
        self._data_loaded = True
        
        if _reload_brokers: self._load_broker_options()
        self.current_page = 1
        
        if not self._is_preloading:
            self.loading_ring.visible = True
            self.loading_status.value = "Fetching trades..."
            try:
                self.loading_ring.update()
                self.loading_status.update()
            except Exception: pass
        self._fetch_and_render()

    def _fetch_and_render(self):
        import time
        start_time = time.time()
        
        query = """
            SELECT t.trade_id, t.date, t.symbol, t.type, t.qty, t.price, t.fee, t.broker
            FROM trades t
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
            query += " AND t.symbol LIKE ? COLLATE NOCASE"
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

        # Add ORDER BY for chronological calculations
        query += " ORDER BY t.date ASC"
        
        # DEBUG: Print the full SQL query with parameters
        if not self._is_preloading:
            print(f"[TRADE_HISTORY] SQL Query: {query}")
            print(f"[TRADE_HISTORY] SQL Params: {params}")
        
        t1 = time.time()
        with db_session() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        t2 = time.time()
        query_time = (t2 - t1) * 1000
        if not self._is_preloading:
            print(f"[TRADE_HISTORY] Query executed in {query_time:.1f}ms, returned {len(df)} rows")

        # Create cache key from current filters
        cache_key = (f_broker, f_symbol, f_type, 
                     self._start_date.strftime('%Y-%m-%d') if self._start_date else None,
                     self._end_date.strftime('%Y-%m-%d') if self._end_date else None)
        
        if not self._is_preloading:
            self.loading_status.value = "Calculating running stats..."
            try: self.loading_status.update()
            except Exception: pass
        
        t3 = time.time()
        # Check if we've already calculated for these filters
        if cache_key in self._calc_cache:
            calculated_data = self._calc_cache[cache_key]
            if not self._is_preloading:
                print(f"[TRADE_HISTORY] Using calc cache (hit)")
        else:
            # Optimized calculation using pandas operations where possible
            df['qty'] = df['qty'].astype(float)
            df['price'] = df['price'].astype(float)
            df['fee'] = df['fee'].astype(float)
            df['type'] = df['type'].str.upper()
            
            running_qty = 0.0
            avg_cost = 0.0
            run_qty_list = []
            avg_cost_list = []
            running_pnl_list = []
            cumulative_realized_pnl = 0.0
            
            # Get current market prices for unrealized PnL calculation
            symbol_prices = {}
            with db_session() as conn:
                prices_df = pd.read_sql_query("SELECT symbol, current_price FROM marketdata", conn)
                for _, row in prices_df.iterrows():
                    symbol_prices[row['symbol']] = float(row['current_price'])
            
            # Optimized loop with pre-converted types (faster iteration)
            for symbol, qty, price, fee, trade_type in zip(df['symbol'], df['qty'], df['price'], df['fee'], df['type']):
                row_running_pnl = 0.0
                
                if trade_type == 'BUY':
                    new_qty = running_qty + qty
                    avg_cost = ((running_qty * avg_cost) + (qty * price) + fee) / new_qty if new_qty != 0 else 0
                    running_qty = new_qty
                    # Running PnL includes accumulated realized + current unrealized for active holdings
                    current_price = symbol_prices.get(symbol, avg_cost)
                    unrealized = (current_price - avg_cost) * running_qty if running_qty > 0 else 0
                    row_running_pnl = cumulative_realized_pnl + unrealized
                else:  # SELL
                    realized = (price - avg_cost) * qty - fee if avg_cost > 0 else 0
                    cumulative_realized_pnl += realized
                    running_qty = max(0, running_qty - qty)
                    if running_qty == 0:
                        avg_cost = 0
                        row_running_pnl = cumulative_realized_pnl
                    else:
                        # Still have holdings, add unrealized
                        current_price = symbol_prices.get(symbol, avg_cost)
                        unrealized = (current_price - avg_cost) * running_qty if running_qty > 0 else 0
                        row_running_pnl = cumulative_realized_pnl + unrealized
                
                run_qty_list.append(running_qty)
                avg_cost_list.append(avg_cost)
                running_pnl_list.append(row_running_pnl)
            
            # Assign calculated columns back to dataframe
            df['run_qty'] = run_qty_list
            df['avg_cost'] = avg_cost_list
            df['running_pnl'] = running_pnl_list
            
            calculated_data = df.to_dict('records')
            t_calc = time.time()
            calc_elapsed = (t_calc - t3) * 1000
            if not self._is_preloading:
                print(f"[TRADE_HISTORY] Running stats loop ({len(df)} trades): {calc_elapsed:.1f}ms")
            self._calc_cache[cache_key] = calculated_data

        df = pd.DataFrame(calculated_data)
        object.__setattr__(self, 'current_df', df)
        self.total_records = len(df)
        self.loading_ring.visible = False
        self.loading_status.value = ""
        try: self.loading_status.update()
        except Exception: pass
        self.render_table()

    def render_table(self):
        # Skip rendering during pre-load - data is cached but UI isn't shown yet
        if self._is_preloading:
            return
            
        if self.current_df is None:
            print("[TRADE_HISTORY] render_table called but current_df is None!")
            return
        df = self.current_df
        
        print(f"[TRADE_HISTORY] render_table called with {len(df)} rows, page_size={self.page_size}, current_page={self.current_page}")

        if df.empty:
            print("[TRADE_HISTORY] DataFrame is empty!")
            self.table.rows = []
            self.status_text.value = "No trades found for the selected filters."
            self.status_text.visible = True
            self._update_pagination_ui()
            # Only update table and status, not entire page (much faster)
            try:
                self.table.update()
                self.status_text.update()
                # Scroll tables to the right using page.run_task to handle async coroutine
                async def scroll_to_right():
                    try:
                        await self.table_row.scroll_to(offset=float('inf'), duration=0)
                        await self.summary_row.scroll_to(offset=float('inf'), duration=0)
                    except Exception:
                        pass
                if hasattr(self.app_state, 'page') and self.app_state.page:
                    self.app_state.page.run_task(scroll_to_right)
            except Exception:
                pass
            return

        self.status_text.visible = False
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_df = df.iloc[start_idx:end_idx]

        print(f"[TRADE_HISTORY] render_table building rows from index {start_idx} to {end_idx}, page_df length = {len(page_df)}")
        
        rows = []
        try:
            for i, row in enumerate(page_df.itertuples(index=False), start=1):
                row_dict = row._asdict()
                trade_id = str(row_dict.get('trade_id', ''))
                row_num = start_idx + i
                row_type = row_dict['type']
                trade_color = ft.Colors.GREEN if row_type == 'BUY' else ft.Colors.RED

                is_selected = trade_id in self.selected_trades
                chk = ft.Checkbox(value=is_selected, on_change=lambda e, tid=trade_id: self.handle_row_select(tid, e.control.value))

                row_data = {
                    'trade_id': trade_id, 'date': str(row_dict['date']), 'symbol': str(row_dict['symbol']),
                    'type': row_type, 'qty': float(row_dict['qty']), 'price': float(row_dict['price']),
                    'fee': float(row_dict.get('fee', 0.0)), 'run_qty': float(row_dict['run_qty']),
                    'avg_cost': float(row_dict['avg_cost']), 'running_pnl': float(row_dict['running_pnl']),
                    'broker': str(row_dict['broker'])
                }

                pnl_val = row_data['running_pnl']
                pnl_color = ft.Colors.GREEN_400 if pnl_val > 0 else (ft.Colors.RED_400 if pnl_val < 0 else ft.Colors.GREY_400)
                pnl_display = f"₹{pnl_val:,.2f}" if row_type == 'SELL' else "—"

                rows.append(
                    ft.DataRow(
                        selected=is_selected,
                        cells=[
                            ft.DataCell(chk),
                            ft.DataCell(ft.Text(str(row_num), text_align=ft.TextAlign.CENTER, color=ft.Colors.GREY_500)),
                            ft.DataCell(ft.Text(row_data['date'])),
                            ft.DataCell(ft.Text(str(trade_id), size=11, color=ft.Colors.GREY_400)),
                            ft.DataCell(ft.Text(row_data['symbol'], weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text(row_data['type'], color=trade_color)),
                            ft.DataCell(ft.Text(f"{row_data['qty']}", text_align=ft.TextAlign.RIGHT)),
                            ft.DataCell(ft.Text(f"₹{row_data['price']:,.2f}", text_align=ft.TextAlign.RIGHT)),
                            ft.DataCell(ft.Text(f"{row_data['run_qty']}", text_align=ft.TextAlign.RIGHT, color=ft.Colors.BLUE_200)),
                            ft.DataCell(ft.Text(f"₹{row_data['avg_cost']:,.2f}", text_align=ft.TextAlign.RIGHT, color=ft.Colors.AMBER_200)),
                            ft.DataCell(ft.Text(pnl_display, text_align=ft.TextAlign.RIGHT, color=pnl_color)),
                            ft.DataCell(ft.Text(f"₹{row_data['fee']:,.2f}", text_align=ft.TextAlign.RIGHT)),
                            ft.DataCell(ft.Row([
                                ft.IconButton(ft.Icons.EDIT, tooltip="Edit Trade", icon_size=16, icon_color=ft.Colors.BLUE_400, on_click=lambda e, r=row_data: self.open_edit_dialog(r)),
                                ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Delete Trade", icon_size=16, icon_color=ft.Colors.RED_400, on_click=lambda e, b=row_data['broker'], tid=trade_id: self.delete_trade(b, tid))
                            ], spacing=0))
                    ])
                )
        except Exception as ex:
            print(f"[TRADE_HISTORY] ERROR building rows: {ex}")
            import traceback
            traceback.print_exc()
            rows = []

        self.table.rows = rows
        print(f"[TRADE_HISTORY] Setting table.rows to {len(rows)} rows")
        
        # Summary Row Calculation
        total_qty = df['qty'].sum()
        total_fees = df['fee'].sum()
        total_pnl = df['running_pnl'].sum()
        pnl_sum_color = ft.Colors.GREEN if total_pnl > 0 else (ft.Colors.RED if total_pnl < 0 else ft.Colors.WHITE)

        self.summary_table.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text("")), # chk
                ft.DataCell(ft.Text("")), # #
                ft.DataCell(ft.Text("SUMMARY", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY_200, size=14)),
                ft.DataCell(ft.Text("")), # ID
                ft.DataCell(ft.Text("")), # Symbol
                ft.DataCell(ft.Text("")), # Type
                ft.DataCell(ft.Text(f"Total Qty: {total_qty:,.0f}", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT, size=13)),
                ft.DataCell(ft.Text("")), # Price
                ft.DataCell(ft.Text("")), # Run Qty
                ft.DataCell(ft.Text("")), # Avg Cost
                ft.DataCell(ft.Text(f"Total PnL: ₹{total_pnl:,.2f}", weight=ft.FontWeight.BOLD, color=pnl_sum_color, text_align=ft.TextAlign.RIGHT, size=13)),
                ft.DataCell(ft.Text(f"Total Fees: ₹{total_fees:,.2f}", weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400, text_align=ft.TextAlign.RIGHT, size=13)),
                ft.DataCell(ft.Text(""))  # Actions
            ])
        ]

        all_visible_selected = page_df['trade_id'].astype(str).isin(self.selected_trades).all()
        self.select_all_chk.value = bool(len(page_df) > 0 and all_visible_selected)
        
        self._update_pagination_ui()
        # Only update table/summary/status, not entire page (much faster)
        try:
            print(f"[TRADE_HISTORY] Updating table with {len(rows)} rows")
            # Only update if control is already on the page; during initial load it won't be
            if hasattr(self.table, 'page') and self.table.page:
                self.table.update()
                self.summary_table.update()
                self.status_text.update()
                print(f"[TRADE_HISTORY] Table update successful!")
            else:
                print(f"[TRADE_HISTORY] Table not yet on page, skipping update (data is loaded)")
            
            # Scroll tables to the right using page.run_task to handle async coroutine
            async def scroll_to_right():
                try:
                    await self.table_row.scroll_to(offset=float('inf'), duration=0)
                    await self.summary_row.scroll_to(offset=float('inf'), duration=0)
                except Exception:
                    pass
            if hasattr(self.app_state, 'page') and self.app_state.page:
                self.app_state.page.run_task(scroll_to_right)
        except Exception as ex:
            print(f"[TRADE_HISTORY] ERROR updating table: {ex}")
            import traceback
            traceback.print_exc()
            pass

    def _update_pagination_ui(self):
        max_page = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        self.page_text.value = f"Page {self.current_page} of {max_page} ({self.total_records} trades)"
        self.prev_btn.disabled = self.current_page <= 1
        self.next_btn.disabled = self.current_page >= max_page

    def delete_trade(self, broker, trade_id):
        import models.crud as crud
        import threading
        from engine import rebuild_holdings
        
        # Show loading state
        self.loading_ring.visible = True
        try:
            self.loading_ring.update()
        except Exception:
            pass
        
        # Clear calculation cache since data is changing
        self._calc_cache.clear()
        
        try:
            crud.delete_trade(str(broker), str(trade_id))
            self.show_snack("Trade deleted!")
        except Exception as ex:
            self.loading_ring.visible = False
            try:
                self.loading_ring.update()
            except Exception:
                pass
            self.show_snack(f"Error deleting trade: {str(ex)}", color=ft.Colors.RED_400)
            return
        
        def bg_delete():
            try:
                rebuild_holdings()
                
                # CRITICAL: Invalidate all view caches when trade deleted
                if hasattr(self.app_state, 'views'):
                    try:
                        if self.app_state.views.get(0):  # Dashboard
                            self.app_state.views[0].invalidate_cache()
                    except: pass
                    try:
                        if self.app_state.views.get(1):  # Holdings
                            self.app_state.views[1].invalidate_cache()
                    except: pass
            finally:
                async def finish():
                    self.load_data(_reload_brokers=False)
                self.app_state.page.run_task(finish)
        
        threading.Thread(target=bg_delete, daemon=True).start()

    def _filter_numeric(self, e):
        """Filter out non-numeric characters from input"""
        if e.control.value:
            # Allow only digits and decimal point
            filtered = ''.join(c for c in e.control.value if c.isdigit() or c == '.')
            # Prevent multiple decimal points
            if filtered.count('.') > 1:
                filtered = filtered[:filtered.rfind('.')]
            e.control.value = filtered
            e.control.update()

    def open_edit_dialog(self, row):
        trade_id = row['trade_id']
        current_date = row['date']
        current_type = row['type']
        
        date_tb = ft.TextField(label="Date", value=current_date, disabled=True, expand=True, label_style=ft.TextStyle(color="#9CA3AF", size=11), text_style=ft.TextStyle(weight=ft.FontWeight.W_600), bgcolor="#0F172A", border_color="#334155", border_radius=6, content_padding=ft.padding.symmetric(horizontal=12, vertical=10))
        
        async def open_edit_date_picker(e):
            self._current_edit_date_tb = date_tb
            
            # Set the picker to show the current trade date
            try:
                if isinstance(current_date, str):
                    parsed_date = pd.to_datetime(current_date).to_pydatetime()
                else:
                    parsed_date = current_date
                self.edit_date_picker.value = parsed_date
            except Exception as ex:
                print(f"[ERROR] Failed to set edit_date_picker value: {ex}")
                self.edit_date_picker.value = pd.to_datetime('today').to_pydatetime()
            
            # Open the date picker
            try:
                if hasattr(self.app_state.page, 'open'):
                    self.app_state.page.open(self.edit_date_picker)
                else:
                    self.edit_date_picker.open = True
                    self.edit_date_picker.update()
            except Exception as ex:
                print(f"[ERROR] Failed to open edit_date_picker: {ex}")
        
        date_btn = ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=open_edit_date_picker, icon_color="#3B82F6")
        
        type_dropdown = ft.Dropdown(
            label="Type", 
            options=[ft.dropdown.Option("BUY"), ft.dropdown.Option("SELL")], 
            value=current_type, 
            expand=True,
            label_style=ft.TextStyle(color="#9CA3AF", size=11),
            text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
            bgcolor="#0F172A",
            border_color="#334155",
            border_radius=6
        )
        
        symbol_tb = trade_edit_field("Symbol", row['symbol'], helper_text="Company ticker symbol")
        qty_tb = trade_edit_field("Quantity", str(row['qty']), ft.KeyboardType.NUMBER, lambda e: self._filter_numeric(e), helper_text="Number of shares")
        price_tb = trade_edit_field("Price", str(row['price']), ft.KeyboardType.NUMBER, lambda e: self._filter_numeric(e), helper_text="Price per share in ₹")
        fee_tb = trade_edit_field("Fee", str(row['fee']), ft.KeyboardType.NUMBER, lambda e: self._filter_numeric(e), helper_text="Trading fees/charges in ₹")
        
        # Calculate total cost for display
        try:
            qty = float(row['qty'])
            price = float(row['price'])
            fee = float(row['fee'])
            total_cost = (qty * price) + fee
            cost_icon = "🛒" if current_type == "BUY" else "💰"
        except:
            total_cost = 0
            cost_icon = "📊"
        
        total_cost_card = trade_edit_calculation_card("Total Cost", f"₹{total_cost:,.2f}", cost_icon, "#3B82F6")
        
        def update_total_cost(e):
            try:
                qty = float(qty_tb.value if isinstance(qty_tb, ft.TextField) else qty_tb.controls[0].value)
                price = float(price_tb.value if isinstance(price_tb, ft.TextField) else price_tb.controls[0].value)
                fee = float(fee_tb.value if isinstance(fee_tb, ft.TextField) else fee_tb.controls[0].value)
                new_total = (qty * price) + fee
                total_cost_card.content.controls[1].controls[1].value = f"₹{new_total:,.2f}"
                total_cost_card.update()
            except:
                pass
        
        # Add change listeners to update total
        if isinstance(qty_tb, ft.TextField):
            qty_tb.on_change = lambda e: (self._filter_numeric(e), update_total_cost(e))
            price_tb.on_change = lambda e: (self._filter_numeric(e), update_total_cost(e))
            fee_tb.on_change = lambda e: (self._filter_numeric(e), update_total_cost(e))
        else:
            qty_tb.controls[0].on_change = lambda e: (self._filter_numeric(e), update_total_cost(e))
            price_tb.controls[0].on_change = lambda e: (self._filter_numeric(e), update_total_cost(e))
            fee_tb.controls[0].on_change = lambda e: (self._filter_numeric(e), update_total_cost(e))

        dlg = ft.AlertDialog(
            title=None,
            content=ft.Container(
                content=ft.Column([
                    trade_edit_header(row['symbol'], current_type, current_date),
                    trade_edit_divider(),
                    
                    # Trade Details Section
                    trade_edit_form_section("Trade Details", [
                        ft.Row([date_tb, date_btn], spacing=8),
                        ft.Row([type_dropdown], spacing=8)
                    ]),
                    
                    # Trade Edit Divider
                    ft.Container(height=8),
                    
                    # Security Details Section
                    trade_edit_form_section("Security Details", [
                        symbol_tb,
                    ]),
                    
                    # Trade Edit Divider
                    ft.Container(height=8),
                    
                    # Trade Quantities Section
                    trade_edit_form_section("Trade Quantities", [
                        qty_tb,
                        price_tb,
                        fee_tb
                    ]),
                    
                    # Trade Edit Divider
                    ft.Container(height=8),
                    
                    # Summary
                    total_cost_card,
                    
                ], tight=True, spacing=12),
                width=480,
                padding=ft.padding.symmetric(horizontal=20, vertical=20)
            ),
            actions_alignment=ft.MainAxisAlignment.END,
        )

        def save_edit(e):
            try:
                # Extract values properly whether wrapped in Column or not
                qty_val = qty_tb.value if isinstance(qty_tb, ft.TextField) else qty_tb.controls[0].value
                price_val = price_tb.value if isinstance(price_tb, ft.TextField) else price_tb.controls[0].value
                fee_val = fee_tb.value if isinstance(fee_tb, ft.TextField) else fee_tb.controls[0].value
                
                n_qty = float(qty_val)
                n_price = float(price_val)
                n_fee = float(fee_val)
                new_symbol = symbol_tb.value.strip().upper() if isinstance(symbol_tb, ft.TextField) else symbol_tb.controls[0].value.strip().upper()
                if not new_symbol: raise ValueError
            except ValueError:
                self.show_snack("Invalid inputs.", color=ft.Colors.RED_400)
                return

            import models.crud as crud
            import threading
            from engine import rebuild_holdings
            
            # Clear calculation cache since data is changing
            self._calc_cache.clear()
            
            self._close_dialog(dlg)
            self.loading_ring.visible = True
            self.loading_ring.update()
            
            def bg_save_edit():
                original_symbol = row['symbol']
                original_broker = row['broker']
                if new_symbol != original_symbol:
                    crud.replace_symbol(original_symbol, new_symbol, original_broker)
                    from engine import fetch_and_update_market_data
                    fetch_and_update_market_data([new_symbol])
                    
                crud.update_trade(original_broker, str(trade_id), date_tb.value, new_symbol, type_dropdown.value, n_qty, n_price, n_fee)
                rebuild_holdings()
                
                # CRITICAL: Invalidate all view caches when trade updated
                if hasattr(self.app_state, 'views'):
                    try:
                        if self.app_state.views.get(0):  # Dashboard
                            self.app_state.views[0].invalidate_cache()
                    except: pass
                    try:
                        if self.app_state.views.get(1):  # Holdings
                            self.app_state.views[1].invalidate_cache()
                    except: pass
                
                async def finish():
                    self.load_data(_reload_brokers=False)
                    self.app_state.refresh_ui()
                    
                self.app_state.page.run_task(finish)
                
            threading.Thread(target=bg_save_edit, daemon=True).start()

        dlg.actions = [
            ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
            ft.ElevatedButton("Save Changes", on_click=save_edit, bgcolor="#10B981", color=ft.Colors.WHITE)
        ]
        self._open_dialog(dlg)
