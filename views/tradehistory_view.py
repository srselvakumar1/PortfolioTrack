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
        # Summary metrics cache — computed once after data load, reused on every page flip
        self._cached_summary = {}
        self._summary_dirty = False
        
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

        # ── Pre-built edit dialog (built ONCE, field values swapped on every open) ──
        self._edit_row: dict = {}   # current row being edited

        # Header controls (inner text refs so we can update without rebuilding)
        self._ed_hdr_symbol   = ft.Text("", size=22, weight=ft.FontWeight.BOLD)
        self._ed_hdr_subtitle = ft.Text("", size=11, color="#9CA3AF")
        self._ed_hdr_badge_txt = ft.Text("", size=12, weight=ft.FontWeight.BOLD)
        self._ed_hdr_badge = ft.Container(
            content=self._ed_hdr_badge_txt,
            padding=ft.padding.symmetric(horizontal=12, vertical=6), border_radius=20
        )
        _ed_header = ft.Container(
            content=ft.Row([
                ft.Column([self._ed_hdr_symbol, self._ed_hdr_subtitle], spacing=2),
                self._ed_hdr_badge
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=15),
            bgcolor="#1A2A3A", padding=15, border_radius=8,
            border=ft.border.all(1, "#334155")
        )

        # Form fields
        _tf = lambda lbl: ft.TextField(
            label=lbl, expand=True,
            label_style=ft.TextStyle(color="#9CA3AF", size=11),
            text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
            bgcolor="#0F172A", border_color="#334155", border_radius=6,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10)
        )
        self._ed_date_tb  = _tf("Date");  self._ed_date_tb.disabled = True
        self._ed_symbol_tb = _tf("Symbol")
        self._ed_qty_tb   = _tf("Quantity"); self._ed_qty_tb.keyboard_type   = ft.KeyboardType.NUMBER
        self._ed_price_tb = _tf("Price");   self._ed_price_tb.keyboard_type = ft.KeyboardType.NUMBER
        self._ed_fee_tb   = _tf("Fee");     self._ed_fee_tb.keyboard_type   = ft.KeyboardType.NUMBER
        self._ed_qty_tb.on_change   = self._ed_on_number_change
        self._ed_price_tb.on_change = self._ed_on_number_change
        self._ed_fee_tb.on_change   = self._ed_on_number_change

        self._ed_type_dd = ft.Dropdown(
            label="Type",
            options=[ft.dropdown.Option("BUY"), ft.dropdown.Option("SELL")],
            expand=True,
            label_style=ft.TextStyle(color="#9CA3AF", size=11),
            text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
            bgcolor="#0F172A", border_color="#334155", border_radius=6
        )

        self._ed_total_cost_txt = ft.Text("\u20b90.00", size=13, weight=ft.FontWeight.BOLD, color="#3B82F6")
        self._ed_cost_icon_txt  = ft.Text("\U0001f6d2", size=14)  # 🛒
        _ed_total_card = ft.Container(
            content=ft.Row([
                self._ed_cost_icon_txt,
                ft.Column([
                    ft.Text("Total Cost", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                    self._ed_total_cost_txt
                ], spacing=1, expand=1)
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor="#0F172A", padding=12, border_radius=6, border=ft.border.all(1, "#1E293B")
        )

        def _section(title, controls):
            return ft.Container(
                content=ft.Column([
                    ft.Text(title, size=12, weight=ft.FontWeight.BOLD, color="#3B82F6"),
                    ft.Column(controls, spacing=8)
                ], spacing=10), padding=0
            )

        def _hint(tb, text):
            return ft.Column([tb, ft.Text(text, size=9, color="#6B7280", italic=True)], spacing=2)

        _ed_date_btn = ft.IconButton(
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self._open_edit_date_picker_from_dialog,
            icon_color="#3B82F6"
        )

        self._edit_dlg = ft.AlertDialog(
            title=None,
            content=ft.Container(
                content=ft.Column([
                    _ed_header,
                    ft.Divider(height=1, color="#334155"),
                    _section("Trade Details", [
                        ft.Row([self._ed_date_tb, _ed_date_btn], spacing=8),
                        ft.Row([self._ed_type_dd], spacing=8)
                    ]),
                    ft.Container(height=8),
                    _section("Security Details", [
                        _hint(self._ed_symbol_tb, "Company ticker symbol")
                    ]),
                    ft.Container(height=8),
                    _section("Trade Quantities", [
                        _hint(self._ed_qty_tb,   "Number of shares"),
                        _hint(self._ed_price_tb, "Price per share in \u20b9"),
                        _hint(self._ed_fee_tb,   "Trading fees/charges in \u20b9")
                    ]),
                    ft.Container(height=8),
                    _ed_total_card
                ], tight=True, spacing=12),
                width=480,
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
            rows=[],
            expand=True
        )

        # Pre-built row pool: 25 stable DataRow objects reused on every page flip.
        # Avoids creating/GC-ing 325 new Flet objects per page navigation — only
        # property values are updated in-place, so Flet sends a tiny delta instead
        # of a full tree replacement.
        self._row_pool = []
        for _ in range(self.page_size):
            _chk      = ft.Checkbox(value=False)
            _t_num    = ft.Text("", size=11, text_align=ft.TextAlign.CENTER, color=ft.Colors.GREY_500)
            _t_date   = ft.Text("", color=ft.Colors.WHITE)
            _t_id     = ft.Text("", size=11, color=ft.Colors.GREY_400)
            _t_sym    = ft.Text("", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
            _t_type   = ft.Text("", color=ft.Colors.WHITE)
            _t_qty    = ft.Text("", text_align=ft.TextAlign.RIGHT, color=ft.Colors.WHITE)
            _t_price  = ft.Text("", text_align=ft.TextAlign.RIGHT, color=ft.Colors.WHITE)
            _t_rqty   = ft.Text("", text_align=ft.TextAlign.RIGHT, color=ft.Colors.BLUE_200)
            _t_avg    = ft.Text("", text_align=ft.TextAlign.RIGHT, color=ft.Colors.AMBER_200)
            _t_pnl    = ft.Text("", text_align=ft.TextAlign.RIGHT, color=ft.Colors.GREY_400)
            _t_fee    = ft.Text("", text_align=ft.TextAlign.RIGHT, color=ft.Colors.WHITE)
            _btn_edit = ft.IconButton(ft.Icons.EDIT, tooltip="Edit Trade", icon_size=16, icon_color=ft.Colors.BLUE_400)
            _btn_del  = ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Delete Trade", icon_size=16, icon_color=ft.Colors.RED_400)
            _drow = ft.DataRow(cells=[
                ft.DataCell(_chk),
                ft.DataCell(_t_num),
                ft.DataCell(_t_date),
                ft.DataCell(_t_id),
                ft.DataCell(_t_sym),
                ft.DataCell(_t_type),
                ft.DataCell(_t_qty),
                ft.DataCell(_t_price),
                ft.DataCell(_t_rqty),
                ft.DataCell(_t_avg),
                ft.DataCell(_t_pnl),
                ft.DataCell(_t_fee),
                ft.DataCell(ft.Row([_btn_edit, _btn_del], spacing=0)),
            ])
            self._row_pool.append({
                'row': _drow, 'chk': _chk,
                't_num': _t_num, 't_date': _t_date, 't_id': _t_id,
                't_sym': _t_sym, 't_type': _t_type, 't_qty': _t_qty,
                't_price': _t_price, 't_rqty': _t_rqty, 't_avg': _t_avg,
                't_pnl': _t_pnl, 't_fee': _t_fee,
                'btn_edit': _btn_edit, 'btn_del': _btn_del,
            })

        self.summary_qty_buy_value  = ft.Text("Buy: 0",    size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
        self.summary_qty_sell_value  = ft.Text(" |   Sell: 0",    size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400)
        self.summary_pnl_value       = ft.Text("₹0.00",   size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400)
        self.summary_fees_buy_value  = ft.Text("Buy: ₹0.00", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
        self.summary_fees_sell_value = ft.Text(" |   Sell: ₹0.00", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400)

        def _pill(label, label_color, *controls, bg_color, border_color):
            return ft.Container(
                content=ft.Row(
                    [ft.Text(label, size=10, color=label_color, weight=ft.FontWeight.W_500)] +
                    list(controls),
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.symmetric(horizontal=10, vertical=5),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.08, bg_color),
                border=ft.border.all(1, ft.Colors.with_opacity(0.25, border_color))
            )

        _sep = lambda: ft.Text("|", size=11, color=ft.Colors.GREY_700)

        self.summary_strip = ft.Row([
            _pill("Total Qty",  ft.Colors.GREY_400,
                  self.summary_qty_buy_value,  _sep(), self.summary_qty_sell_value,
                  bg_color=ft.Colors.BLUE_400,  border_color=ft.Colors.BLUE_400),
            _pill("Running PnL",  ft.Colors.GREY_400,
                  self.summary_pnl_value,
                  bg_color=ft.Colors.GREEN_400, border_color=ft.Colors.GREEN_400),
            _pill("Total Fees", ft.Colors.GREY_400,
                  self.summary_fees_buy_value, _sep(), self.summary_fees_sell_value,
                  bg_color=ft.Colors.AMBER_400, border_color=ft.Colors.AMBER_400),
        ], spacing=10)

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
                    ft.Text("Start Date", size=13, color=ft.Colors.GREY_400),
                    self.start_date_btn
                ], spacing=2, tight=True),
                width=153
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("End Date", size=13, color=ft.Colors.GREY_400),
                    self.end_date_btn
                ], spacing=2, tight=True),
                width=153
            ),
            ft.ElevatedButton("Search", icon=ft.Icons.SEARCH, bgcolor=ft.Colors.BLUE, on_click=lambda e: self.load_data(_reload_brokers=False), width=115), 
            ft.ElevatedButton("Clear", icon=ft.Icons.CLEAR_ALL, on_click=self.clear_filters, width=102),
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
        self.table_row = ft.Row([self.table], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
        self.content = ft.Column([
            page_title("Trade History Details"),
            premium_card(ft.Column([
                # Wrap your filter_row here:
                ft.Container(
                    content=filter_row, 
                    height=90,  # Increased from 70 to give more vertical space
                    padding=ft.padding.symmetric(vertical=10, horizontal=0)
                ),
                ft.Container(
                    content=self.summary_strip,
                    padding=ft.padding.symmetric(vertical=0, horizontal=0)
                ),
                ft.Divider(color="#27F5B0"),
                self.status_text,
                ft.Container(
                    content=ft.Column([
                        self.table_row
                    ], scroll=ft.ScrollMode.ADAPTIVE),
                    expand=True, clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                ),
                pagination_row
            ], spacing=4), expand=True)
        ], spacing=24) 

    # --- UNIVERSAL DIALOG / PICKER HELPERS ---
    def _open_picker(self, picker):
        """Open a date picker — compatible with both old and new Flet APIs."""
        if hasattr(self.app_state.page, 'open'):
            self.app_state.page.open(picker)
        else:
            picker.open = True
            self.app_state.page.update()

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
        """Debounced symbol search: wait 150ms after user stops typing."""
        if self._search_timer:
            self._search_timer.cancel()
        # Pass _reload_brokers=False — no need to re-query brokers on every keystroke
        self._search_timer = threading.Timer(0.15, lambda: self.load_data(_reload_brokers=False))
        self._search_timer.daemon = True
        self._search_timer.start()

    def handle_start_date_click(self, e):
        target_date = self._start_date if self._start_date else datetime.now().date()
        target_datetime = datetime.combine(target_date, datetime.min.time())
        
        # Force Flet to recognize a state change by clearing it first
        self.start_date_picker.value = None
        try:
            self.start_date_picker.update()
        except:
            pass
            
        self.start_date_picker.value = target_datetime
        try:
            self.start_date_picker.update()
        except:
            pass
            
        self._open_picker(self.start_date_picker)

    def handle_end_date_click(self, e):
        target_date = self._end_date if self._end_date else datetime.now().date()
        target_datetime = datetime.combine(target_date, datetime.min.time())
        
        # Force Flet to recognize a state change by clearing it first
        self.end_date_picker.value = None
        try:
            self.end_date_picker.update()
        except:
            pass
            
        self.end_date_picker.value = target_datetime
        try:
            self.end_date_picker.update()
        except:
            pass
            
        self._open_picker(self.end_date_picker)

    def _on_start_date_change(self, e):
        selected_val = e.control.value if e and getattr(e, 'control', None) else self.start_date_picker.value
        if selected_val:
            new_date = selected_val.date() if hasattr(selected_val, 'date') else selected_val
            changed = new_date != self._start_date
            self._start_date = new_date
            new_text = self._start_date.strftime('%Y-%m-%d')
            self.start_date_btn.text = new_text
            self.start_date_picker.value = datetime.combine(new_date, datetime.min.time())
            try:
                self.start_date_btn.update()
                self.start_date_picker.update()
            except Exception:
                pass
            if changed:
                self._data_loaded = False
                async def deferred_reload():
                    try:
                        self.load_data(_reload_brokers=False, use_cache=False)
                    except Exception:
                        pass
                if hasattr(self.app_state, 'page') and self.app_state.page:
                    self.app_state.page.run_task(deferred_reload)

    def _on_end_date_change(self, e):
        selected_val = e.control.value if e and getattr(e, 'control', None) else self.end_date_picker.value
        if selected_val:
            new_date = selected_val.date() if hasattr(selected_val, 'date') else selected_val
            changed = new_date != self._end_date
            self._end_date = new_date
            new_text = self._end_date.strftime('%Y-%m-%d')
            self.end_date_btn.text = new_text
            self.end_date_picker.value = datetime.combine(new_date, datetime.min.time())
            try:
                self.end_date_btn.update()
                self.end_date_picker.update()
            except Exception:
                pass
            if changed:
                self._data_loaded = False
                async def deferred_reload():
                    try:
                        self.load_data(_reload_brokers=False, use_cache=False)
                    except Exception:
                        pass
                if hasattr(self.app_state, 'page') and self.app_state.page:
                    self.app_state.page.run_task(deferred_reload)

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
        """Mark cache stale — fresh DB query will run next time this view is navigated to.
        Does NOT trigger an immediate load (the view may not even be visible)."""
        self._calc_cache.clear()
        self._data_loaded = False
        self._cached_df = None
        self._cached_filters = None
        self.current_df = None

    def clear_filters(self, e):
        self.broker_filter.value = "All"
        self.symbol_filter.value = ""
        self.type_filter.value = "All"
        # Reset dates to default (5 years back to today)
        today = datetime.now()
        all_trades_start = today - timedelta(days=1825)
        self._start_date = all_trades_start.date()
        self._end_date = today.date()
        self.start_date_btn.text = self._start_date.strftime('%Y-%m-%d')
        self.end_date_btn.text = self._end_date.strftime('%Y-%m-%d')
        self.start_date_btn.update()
        self.end_date_btn.update()
        self.start_date_picker.value = all_trades_start
        self.end_date_picker.value = today
        self.start_date_picker.update()
        self.end_date_picker.update()
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

    def load_data(self, _reload_brokers=True, use_cache=True, _from_ui_dispatch=False):
        """Load data with instant cache display on re-navigation.
        
        Args:
            _reload_brokers: Reload broker options if True
            use_cache: If True and cached data exists, display it instantly (no spinner)
        """
        # Ensure UI mutations happen on the UI thread even when called from background threads
        if not _from_ui_dispatch and threading.current_thread() is not threading.main_thread():
            page = getattr(self.app_state, 'page', None)
            if page:
                async def _deferred_ui_load():
                    self.load_data(_reload_brokers=_reload_brokers, use_cache=use_cache, _from_ui_dispatch=True)
                page.run_task(_deferred_ui_load)
                return

        # Check if filters have changed - if not, use cached data
        current_filters = (
            self.broker_filter.value,
            self.symbol_filter.value.strip().upper() if self.symbol_filter.value else "",
            self.type_filter.value,
            self._start_date.strftime('%Y-%m-%d') if self._start_date else None,
            self._end_date.strftime('%Y-%m-%d') if self._end_date else None
        )
        
        # If cache exists and filters unchanged and we're re-visiting, display cached data instantly
        if use_cache and self._data_loaded and self._cached_filters == current_filters and self.current_df is not None:
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
        # Run heavy DB + stats work on a background thread to keep the UI responsive
        threading.Thread(target=self._fetch_and_render, daemon=True).start()

    def _fetch_and_render(self):
        f_broker = self.broker_filter.value
        f_symbol = self.symbol_filter.value.strip().upper() if self.symbol_filter.value else ""
        f_type = self.type_filter.value

        # Build cache key FIRST — if we have a hit, skip the DB entirely
        cache_key = (f_broker, f_symbol, f_type,
                     self._start_date.strftime('%Y-%m-%d') if self._start_date else None,
                     self._end_date.strftime('%Y-%m-%d') if self._end_date else None)

        if cache_key in self._calc_cache:
            # Cache hit: skip DB query and skip running-stats calculation
            calculated_data = self._calc_cache[cache_key]
        else:
            # Cache miss: hit the DB exactly once, compute stats, then cache
            query = """
                SELECT t.trade_id, t.date, t.symbol, t.type, t.qty, t.price, t.fee, t.broker
                FROM trades t
                WHERE 1=1
            """
            params = []

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
                query += " AND date(t.date) >= date(?)"
                params.append(self._start_date.strftime('%Y-%m-%d'))
            if self._end_date:
                query += " AND date(t.date) <= date(?)"
                params.append(self._end_date.strftime('%Y-%m-%d'))

            query += " ORDER BY t.date ASC"

            with db_session() as conn:
                df = pd.read_sql_query(query, conn, params=params)

            # Optimized calculation using pandas operations where possible
            df['qty'] = df['qty'].astype(float)
            df['price'] = df['price'].astype(float)
            df['fee'] = df['fee'].astype(float)
            df['type'] = df['type'].str.upper()
            
            # Per-symbol running state — critical when results span multiple symbols
            sym_running_qty:   dict = {}   # symbol -> running qty
            sym_avg_cost:      dict = {}   # symbol -> avg cost
            sym_realized_pnl:  dict = {}   # symbol -> cumulative realized PnL

            run_qty_list = []
            avg_cost_list = []
            running_pnl_list = []

            # Get current market prices — use to_dict for fast O(1) lookups
            with db_session() as conn:
                prices_df = pd.read_sql_query("SELECT symbol, current_price FROM marketdata", conn)
            symbol_prices = prices_df.set_index('symbol')['current_price'].astype(float).to_dict()

            # Iterate chronologically; each symbol maintains its own independent state
            for symbol, qty, price, fee, trade_type in zip(df['symbol'], df['qty'], df['price'], df['fee'], df['type']):
                running_qty        = sym_running_qty.get(symbol, 0.0)
                avg_cost           = sym_avg_cost.get(symbol, 0.0)
                cumulative_realized = sym_realized_pnl.get(symbol, 0.0)

                if trade_type == 'BUY':
                    new_qty = running_qty + qty
                    avg_cost = ((running_qty * avg_cost) + (qty * price) + fee) / new_qty if new_qty != 0 else 0
                    running_qty = new_qty
                    current_price = symbol_prices.get(symbol, avg_cost)
                    unrealized = (current_price - avg_cost) * running_qty if running_qty > 0 else 0
                    row_running_pnl = cumulative_realized + unrealized
                else:  # SELL
                    realized = (price - avg_cost) * qty - fee if avg_cost > 0 else 0
                    cumulative_realized += realized
                    running_qty = max(0.0, running_qty - qty)
                    if running_qty == 0:
                        avg_cost = 0.0
                        row_running_pnl = cumulative_realized
                    else:
                        current_price = symbol_prices.get(symbol, avg_cost)
                        unrealized = (current_price - avg_cost) * running_qty
                        row_running_pnl = cumulative_realized + unrealized

                sym_running_qty[symbol]  = running_qty
                sym_avg_cost[symbol]     = avg_cost
                sym_realized_pnl[symbol] = cumulative_realized

                run_qty_list.append(running_qty)
                avg_cost_list.append(avg_cost)
                running_pnl_list.append(row_running_pnl)
            
            # Assign calculated columns back to dataframe
            df['run_qty'] = run_qty_list
            df['avg_cost'] = avg_cost_list
            df['running_pnl'] = running_pnl_list
            
            calculated_data = df.to_dict('records')
            self._calc_cache[cache_key] = calculated_data

        df = pd.DataFrame(calculated_data)
        object.__setattr__(self, 'current_df', df)
        self.total_records = len(df)

        # Pre-compute summary metrics here so render_table never runs pandas on page flip
        if not df.empty:
            type_col = df['type'].astype(str).str.upper()
            buy_mask = type_col == 'BUY'
            sell_mask = type_col == 'SELL'
            total_qty_buy   = float(df.loc[buy_mask, 'qty'].sum())
            total_qty_sell  = float(df.loc[sell_mask, 'qty'].sum())
            total_fees_buy  = float(df.loc[buy_mask, 'fee'].sum())
            total_fees_sell = float(df.loc[sell_mask, 'fee'].sum())
            total_pnl       = float(df.groupby('symbol')['running_pnl'].last().sum())
        else:
            total_qty_buy = total_qty_sell = total_fees_buy = total_fees_sell = total_pnl = 0.0
        pnl_color = ft.Colors.GREEN if total_pnl > 0 else (ft.Colors.RED if total_pnl < 0 else ft.Colors.WHITE)
        self._cached_summary = {
            'qty_buy':   f"Buy: {total_qty_buy:,.0f}",
            'qty_sell':  f"|   Sell: {total_qty_sell:,.0f}",
            'pnl':       f"₹{total_pnl:,.2f}",
            'pnl_color': pnl_color,
            'fees_buy':  f"Buy: ₹{total_fees_buy:,.2f}",
            'fees_sell': f"|   Sell: ₹{total_fees_sell:,.2f}",
        }
        self._summary_dirty = True
        # Dispatch all UI updates back to the main thread from the background thread
        async def _finish_on_ui():
            self.loading_ring.visible = False
            self.loading_status.value = ""
            try:
                self.loading_ring.update()
                self.loading_status.update()
            except Exception: pass
            self.render_table()
        page = getattr(self.app_state, 'page', None)
        if page:
            page.run_task(_finish_on_ui)

    def render_table(self):
        # Skip rendering during pre-load - data is cached but UI isn't shown yet
        if self._is_preloading:
            return
            
        if self.current_df is None:
            return
        df = self.current_df

        if df.empty:
            self.table.rows = []
            self.status_text.value = "No trades found for the selected filters."
            self.status_text.visible = True
            self._update_pagination_ui()
            # Only update table and status, not entire page (much faster)
            try:
                self.table.update()
                self.status_text.update()
                # Keep tables scrolled to the left so leading columns are visible
                async def scroll_to_left():
                    try:
                        await self.table_row.scroll_to(offset=0, duration=0)
                    except Exception:
                        pass
                if hasattr(self.app_state, 'page') and self.app_state.page:
                    self.app_state.page.run_task(scroll_to_left)
            except Exception:
                pass
            return

        self.status_text.visible = False
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_df = df.iloc[start_idx:end_idx]

        # Populate pre-built row pool in-place — no new Flet objects created per page flip.
        # Flet receives only property-value deltas instead of a full 325-object tree replacement.
        actual_count = len(page_df)
        for i, (slot, row) in enumerate(zip(self._row_pool, page_df.itertuples(index=False))):
            row_dict    = row._asdict()
            trade_id    = str(row_dict.get('trade_id', ''))
            row_num     = start_idx + i + 1
            row_type    = str(row_dict['type']).upper()
            trade_color = ft.Colors.GREEN if row_type == 'BUY' else ft.Colors.RED
            is_selected = trade_id in self.selected_trades
            pnl_val     = float(row_dict['running_pnl'])
            pnl_color   = ft.Colors.GREEN_400 if pnl_val > 0 else (ft.Colors.RED_400 if pnl_val < 0 else ft.Colors.GREY_400)
            pnl_display = f"₹{pnl_val:,.2f}" if row_type == 'SELL' else "—"
            broker      = str(row_dict['broker'])
            row_data    = {
                'trade_id': trade_id, 'date': str(row_dict['date']), 'symbol': str(row_dict['symbol']),
                'type': row_type, 'qty': float(row_dict['qty']), 'price': float(row_dict['price']),
                'fee': float(row_dict.get('fee', 0.0)), 'run_qty': float(row_dict['run_qty']),
                'avg_cost': float(row_dict['avg_cost']), 'running_pnl': pnl_val, 'broker': broker
            }
            drow = slot['row']
            drow.color    = alternating_row_color(row_num)
            drow.selected = is_selected
            slot['chk'].value     = is_selected
            slot['chk'].on_change = lambda e, tid=trade_id: self.handle_row_select(tid, e.control.value)
            slot['t_num'].value   = str(row_num)
            slot['t_date'].value  = row_data['date']
            slot['t_id'].value    = trade_id
            slot['t_sym'].value   = row_data['symbol']
            slot['t_type'].value  = row_type
            slot['t_type'].color  = trade_color
            slot['t_qty'].value   = f"{row_data['qty']}"
            slot['t_price'].value = f"₹{row_data['price']:,.2f}"
            slot['t_rqty'].value  = f"{row_data['run_qty']}"
            slot['t_avg'].value   = f"₹{row_data['avg_cost']:,.2f}"
            slot['t_pnl'].value   = pnl_display
            slot['t_pnl'].color   = pnl_color
            slot['t_fee'].value   = f"₹{row_data['fee']:,.2f}"
            slot['btn_edit'].on_click = lambda e, r=dict(row_data): self.open_edit_dialog(r)
            slot['btn_del'].on_click  = lambda e, b=broker, tid=trade_id: self.delete_trade(b, tid)

        self.table.rows = [self._row_pool[i]['row'] for i in range(actual_count)]

        # Summary Metrics — use pre-computed cache to avoid per-page pandas work
        _summary_updated = False
        if self._summary_dirty and self._cached_summary:
            s = self._cached_summary
            self.summary_qty_buy_value.value   = s['qty_buy']
            self.summary_qty_sell_value.value  = s['qty_sell']
            self.summary_pnl_value.value        = s['pnl']
            self.summary_pnl_value.color        = s['pnl_color']
            self.summary_fees_buy_value.value   = s['fees_buy']
            self.summary_fees_sell_value.value  = s['fees_sell']
            self._summary_dirty = False
            _summary_updated = True

        all_visible_selected = page_df['trade_id'].astype(str).isin(self.selected_trades).all()
        self.select_all_chk.value = bool(len(page_df) > 0 and all_visible_selected)
        
        self._update_pagination_ui()
        # Targeted updates — faster than full page.update() since only dirty controls are re-sent
        try:
            self.table.update()
            self.status_text.update()
            if _summary_updated:
                self.summary_qty_buy_value.update()
                self.summary_qty_sell_value.update()
                self.summary_pnl_value.update()
                self.summary_fees_buy_value.update()
                self.summary_fees_sell_value.update()
            self.page_text.update()
            self.prev_btn.update()
            self.next_btn.update()
        except RuntimeError:
            pass
        except Exception:
            pass
        # Keep table scrolled to left so leading columns are visible
        async def scroll_to_left():
            try:
                await self.table_row.scroll_to(offset=0, duration=0)
            except Exception:
                pass
        try:
            page = self.app_state.page
            if page:
                page.run_task(scroll_to_left)
        except Exception:
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

    def _open_edit_date_picker_from_dialog(self, e):
        """Open the edit date picker, syncing it to the current date field value."""
        self._current_edit_date_tb = self._ed_date_tb
        try:
            date_str = self._ed_date_tb.value
            parsed_date = pd.to_datetime(date_str).to_pydatetime() if isinstance(date_str, str) else date_str
            target_date = parsed_date
        except Exception:
            target_date = pd.to_datetime('today').to_pydatetime()
            
        # Force Flet to recognize a state change by clearing it first
        self.edit_date_picker.value = None
        try:
            self.edit_date_picker.update()
        except:
            pass
            
        self.edit_date_picker.value = target_date
        try:
            self.edit_date_picker.update()
        except:
            pass
            
        self._open_picker(self.edit_date_picker)

    def _ed_on_number_change(self, e):
        """Filter non-numeric input and update the running total cost display."""
        self._filter_numeric(e)
        try:
            total = (
                float(self._ed_qty_tb.value or 0) * float(self._ed_price_tb.value or 0)
            ) + float(self._ed_fee_tb.value or 0)
            self._ed_total_cost_txt.value = f"₹{total:,.2f}"
            self._ed_total_cost_txt.update()
        except Exception:
            pass

    def open_edit_dialog(self, row):
        """Populate the pre-built dialog with this row's values and open it instantly."""
        self._edit_row = row
        current_type = row['type']

        # Update header
        self._ed_hdr_symbol.value   = row['symbol']
        self._ed_hdr_subtitle.value = f"Trade ID • {row['date']}"
        type_color    = "#10B981" if current_type == "BUY" else "#EF4444"
        type_badge_bg = "#0D4E2F" if current_type == "BUY" else "#4B0E0E"
        self._ed_hdr_badge_txt.value = current_type
        self._ed_hdr_badge_txt.color = type_color
        self._ed_hdr_badge.bgcolor   = type_badge_bg

        # Update form fields
        self._ed_date_tb.value   = str(row['date'])
        self._ed_type_dd.value   = current_type
        self._ed_symbol_tb.value = row['symbol']
        self._ed_qty_tb.value    = str(row['qty'])
        self._ed_price_tb.value  = str(row['price'])
        self._ed_fee_tb.value    = str(row['fee'])

        # Update total cost card
        try:
            total = (float(row['qty']) * float(row['price'])) + float(row['fee'])
            self._ed_total_cost_txt.value = f"₹{total:,.2f}"
            self._ed_cost_icon_txt.value  = "🛒" if current_type == "BUY" else "💰"
        except Exception:
            self._ed_total_cost_txt.value = "₹0.00"

        self._open_dialog(self._edit_dlg)

    def _save_edit_dialog(self, e):
        """Save the edit dialog changes."""
        row = self._edit_row
        try:
            n_qty    = float(self._ed_qty_tb.value)
            n_price  = float(self._ed_price_tb.value)
            n_fee    = float(self._ed_fee_tb.value)
            new_symbol = self._ed_symbol_tb.value.strip().upper()
            if not new_symbol:
                raise ValueError("Empty symbol")
        except ValueError:
            self.show_snack("Invalid inputs.", color=ft.Colors.RED_400)
            return

        import models.crud as crud
        from engine import rebuild_holdings

        self._calc_cache.clear()
        self._close_dialog(self._edit_dlg)
        self.loading_ring.visible = True
        self.loading_ring.update()

        trade_id        = row['trade_id']
        original_symbol = row['symbol']
        original_broker = row['broker']
        new_date        = self._ed_date_tb.value
        new_type        = self._ed_type_dd.value

        def bg_save():
            if new_symbol != original_symbol:
                crud.replace_symbol(original_symbol, new_symbol, original_broker)
                from engine import fetch_and_update_market_data
                fetch_and_update_market_data([new_symbol])
            crud.update_trade(original_broker, str(trade_id), new_date, new_symbol, new_type, n_qty, n_price, n_fee)
            rebuild_holdings()
            if hasattr(self.app_state, 'views'):
                try:
                    if self.app_state.views.get(0):
                        self.app_state.views[0].invalidate_cache()
                except Exception:
                    pass
                try:
                    if self.app_state.views.get(1):
                        self.app_state.views[1].invalidate_cache()
                except Exception:
                    pass

            async def finish():
                self.load_data(_reload_brokers=False)
                self.app_state.refresh_ui()

            self.app_state.page.run_task(finish)

        threading.Thread(target=bg_save, daemon=True).start()

