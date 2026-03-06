import flet as ft
import pandas as pd
from datetime import datetime, timedelta
from flet_app.common.state import AppState
from flet_app.components.ui_elements import page_title, premium_card, show_toast, alternating_row_color, styled_modal_dialog, trade_edit_header, trade_edit_field, trade_edit_calculation_card, trade_edit_form_section, trade_edit_divider
from flet_app.common.database import db_session
import threading
import sys
import subprocess
from flet_app.common.data_cache import TradeHistoryFilters

class TradeHistoryView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True
        # Visibility/activation guard: prevents hidden views from doing expensive UI updates
        # while the user is on another tab.
        self._is_active = False
        self._scrolled_left_once = False
        object.__setattr__(self, 'current_df', None)
        self._current_edit_date_tb = None
        self.selected_trades = set() 
        
        # Search debouncing
        self._search_timer = None
        # Date change debouncing: coalesce rapid start/end date changes into one reload
        self._date_reload_timer = None
        
        self.total_records = 0
        
        # Calculate default dates: show all trades (1 month back to today)
        today = datetime.now()
        all_trades_start = today - timedelta(days=30)  # ~1 month
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

        # Monotonic request id for background loads; lets us ignore stale results
        self._load_seq = 0

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

        # Create date buttons with nested Text controls (more reliable updates across Flet versions)
        self.start_date_text = ft.Text(self._start_date.strftime('%Y-%m-%d'), size=13)
        self.end_date_text = ft.Text(self._end_date.strftime('%Y-%m-%d'), size=13)
        self.start_date_btn = ft.ElevatedButton(
            content=self.start_date_text,
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.handle_start_date_click
        )
        self.end_date_btn = ft.ElevatedButton(
            content=self.end_date_text,
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.handle_end_date_click
        )

        self.select_all_chk = ft.Checkbox(on_change=self.handle_select_all)

        # ── Fast grid: fixed-width header + ListView rows (faster than DataTable) ──
        self.col_widths = [36, 40, 92, 92, 80, 64, 72, 86, 84, 86, 110, 80, 86]

        class _SortEvent:
            def __init__(self, column_index: int, ascending: bool):
                self.column_index = column_index
                self.ascending = ascending

        def _toggle_sort(col_idx: int):
            asc = True
            if self.sort_column_index == col_idx:
                asc = not bool(self.sort_ascending)
            self.handle_sort(_SortEvent(col_idx, asc))

        def _header_cell(content: ft.Control, width: int, numeric: bool = False, center: bool = False):
            align = ft.alignment.Alignment(0, 0) if center else (ft.alignment.Alignment(1, 0) if numeric else ft.alignment.Alignment(-1, 0))
            return ft.Container(
                content=content,
                width=int(width),
                alignment=align,
                padding=ft.padding.symmetric(vertical=12, horizontal=8),
            )

        hdr_date = ft.TextButton(
            content=ft.Text("Date", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300),
            on_click=lambda e: _toggle_sort(2),
            style=ft.ButtonStyle(padding=ft.padding.all(0)),
        )
        hdr_sym = ft.TextButton(
            content=ft.Text("Symbol", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300),
            on_click=lambda e: _toggle_sort(4),
            style=ft.ButtonStyle(padding=ft.padding.all(0)),
        )

        self._grid_header_row = ft.Container(
            content=ft.Row(
                controls=[
                    _header_cell(self.select_all_chk, self.col_widths[0], center=True),
                    _header_cell(ft.Text("#", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300), self.col_widths[1], numeric=True),
                    _header_cell(hdr_date, self.col_widths[2]),
                    _header_cell(ft.Text("Trade ID", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300), self.col_widths[3]),
                    _header_cell(hdr_sym, self.col_widths[4]),
                    _header_cell(ft.Text("Type", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300), self.col_widths[5]),
                    _header_cell(ft.Text("Qty", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300, text_align=ft.TextAlign.RIGHT), self.col_widths[6], numeric=True),
                    _header_cell(ft.Text("Price ₹", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300, text_align=ft.TextAlign.RIGHT), self.col_widths[7], numeric=True),
                    _header_cell(ft.Text("Run. Qty", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300, text_align=ft.TextAlign.RIGHT), self.col_widths[8], numeric=True),
                    _header_cell(ft.Text("AvgCost ₹", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300, text_align=ft.TextAlign.RIGHT), self.col_widths[9], numeric=True),
                    _header_cell(ft.Text("Running PnL ₹", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300, text_align=ft.TextAlign.RIGHT), self.col_widths[10], numeric=True),
                    _header_cell(ft.Text("Fees ₹", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300, text_align=ft.TextAlign.RIGHT), self.col_widths[11], numeric=True),
                    _header_cell(ft.Text("Actions", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.CYAN_300), self.col_widths[12], center=True),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#1A2F4A",
            border=ft.border.only(bottom=ft.border.BorderSide(2, "#3B82F6")),
        )

        self._grid_list = ft.ListView(
            expand=True,
            spacing=0,
            padding=0,
            auto_scroll=False,
        )

        # Row pool reused across renders. It expands to fit the largest filtered set.
        # Note: Flet DataTable doesn't virtualize; rendering *all* rows can be heavy on
        # very large datasets, but this matches the requested UX.
        self._row_pool = []

        self.summary_qty_buy_value  = ft.Text("Buy: 0",    size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
        self.summary_qty_sell_value  = ft.Text(" |   Sell: 0",    size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400)
        self.summary_pnl_value       = ft.Text("₹0.00",   size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400)
        self.summary_fees_buy_value  = ft.Text("Buy: ₹0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
        self.summary_fees_sell_value = ft.Text(" |   Sell: ₹0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400)

        self.copy_all_btn = ft.ElevatedButton(
            "Copy All",
            icon=ft.Icons.CONTENT_COPY,
            tooltip="Copy all visible trade rows to clipboard",
            on_click=self._copy_all_rows,
        )

        def _pill(label, label_color, *controls, bg_color, border_color):
            return ft.Container(
                content=ft.Row(
                    [ft.Text(label, size=12, color=label_color, weight=ft.FontWeight.W_600)] +
                    list(controls),
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, bg_color),
                border=ft.border.all(1.5, ft.Colors.with_opacity(0.35, border_color))
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
            ft.Container(expand=True),
            self.copy_all_btn,
        ], spacing=6)

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
            try:
                if self._start_date:
                    self.start_date_text.value = self._start_date.strftime('%Y-%m-%d')
                if self._end_date:
                    self.end_date_text.value = self._end_date.strftime('%Y-%m-%d')
            except Exception:
                if self._start_date:
                    self.start_date_btn.text = self._start_date.strftime('%Y-%m-%d')
                if self._end_date:
                    self.end_date_btn.text = self._end_date.strftime('%Y-%m-%d')
            df = state.get('current_df')
            if df is not None:
                object.__setattr__(self, 'current_df', df)
                self.total_records = len(df)
                self.render_table()
        else:
            # First visit: auto-load with default dates (yesterday to today)
            self._data_loaded = False
            # Will auto-load in did_mount via load_data()

        # Reorganized filter layout for better visibility - all controls in one row with colored pills (compact)
        filter_row = ft.Row([
            # Broker filter pill (compact)
            ft.Container(
                content=ft.Row([ft.Text("🏦", size=13), self.broker_filter], spacing=3),
                width=130,
                padding=ft.padding.symmetric(horizontal=6, vertical=3),
                border_radius=5,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_400),
                border=ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.BLUE_400))
            ),
            # Symbol filter pill (compact)
            ft.Container(
                content=ft.Row([ft.Text("🔍", size=13), self.symbol_filter], spacing=3),
                width=120,
                padding=ft.padding.symmetric(horizontal=6, vertical=3),
                border_radius=5,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PURPLE_400),
                border=ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.PURPLE_400))
            ),
            # Type filter pill (compact)
            ft.Container(
                content=ft.Row([ft.Text("📋", size=13), self.type_filter], spacing=3),
                width=115,
                padding=ft.padding.symmetric(horizontal=6, vertical=3),
                border_radius=5,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN_400),
                border=ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.GREEN_400))
            ),
            # Date range pill (compact)
            ft.Container(
                content=ft.Row([ft.Text("📅", size=13), self.start_date_btn], spacing=3),
                width=145,
                padding=ft.padding.symmetric(horizontal=6, vertical=3),
                border_radius=5,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ORANGE_400),
                border=ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.ORANGE_400))
            ),
            # End date pill (compact)
            ft.Container(
                content=ft.Row([ft.Text("→", size=13), self.end_date_btn], spacing=3),
                width=145,
                padding=ft.padding.symmetric(horizontal=6, vertical=3),
                border_radius=5,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ORANGE_400),
                border=ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.ORANGE_400))
            ),
            # Action buttons (compact)
            ft.ElevatedButton("🔎 Search", bgcolor=ft.Colors.BLUE, on_click=lambda e: self.load_data(_reload_brokers=False), width=105), 
            ft.ElevatedButton("🗑️ Clear", on_click=self.clear_filters, width=92),
            ft.ElevatedButton("⚡ Bulk Del", bgcolor=ft.Colors.RED_600, on_click=self.handle_bulk_delete, width=110),
            ft.ElevatedButton("📥 Export", tooltip="Export CSV", on_click=self.handle_export_click, width=102),
            ft.Container(expand=True),
            self.loading_ring, 
            self.loading_status
        ], 
        alignment=ft.MainAxisAlignment.START, 
        vertical_alignment=ft.CrossAxisAlignment.CENTER, 
        spacing=5,
        wrap=False,
        scroll=ft.ScrollMode.AUTO)

        # Store references to table rows for horizontal scroll management
        self.table_row = ft.Row(
            [ft.Column([self._grid_header_row, self._grid_list], spacing=0, expand=True)],
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        self.content = ft.Column([
            page_title("Trade History Details"),
            premium_card(ft.Column([
                # Wrap your filter_row here:
                ft.Container(
                    content=filter_row, 
                    height=68,  # Reduced from 90 to save space
                    padding=ft.padding.symmetric(vertical=4, horizontal=0)
                ),
                ft.Container(
                    content=self.summary_strip,
                    padding=ft.padding.symmetric(vertical=2, horizontal=0)
                ),
                ft.Divider(color="#27F5B0"),
                self.status_text,
                ft.Container(
                    content=ft.Column([
                        self.table_row
                    ], scroll=ft.ScrollMode.ADAPTIVE),
                    expand=True, clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                )
            ], spacing=3), expand=True)
        ], spacing=18) 

    # --- UNIVERSAL DIALOG / PICKER HELPERS ---
    def _open_picker(self, picker):
        """Open a date picker — compatible with both old and new Flet APIs."""
        if hasattr(self.app_state.page, 'open'):
            self.app_state.page.open(picker)
        else:
            picker.open = True
            try:
                picker.update()
            except Exception:
                # Fallback if picker.update isn't supported in a given runtime
                try:
                    self.app_state.page.update()
                except Exception:
                    pass

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

    def _copy_all_rows(self, e=None):
        df = getattr(self, 'current_df', None)
        if df is None or getattr(df, 'empty', True):
            self.show_snack("No trades to copy. Run a search first.", color=ft.Colors.ORANGE_400)
            return

        try:
            copy_df = df.copy()
            t_type = copy_df.get('type', pd.Series([""] * len(copy_df))).astype(str).str.upper()
            qty = pd.to_numeric(copy_df.get('qty', 0), errors='coerce').fillna(0.0)
            price = pd.to_numeric(copy_df.get('price', 0), errors='coerce').fillna(0.0)
            run_qty = pd.to_numeric(copy_df.get('run_qty', 0), errors='coerce').fillna(0.0)
            avg_cost = pd.to_numeric(copy_df.get('avg_cost', 0), errors='coerce').fillna(0.0)
            running_pnl = pd.to_numeric(copy_df.get('running_pnl', 0), errors='coerce').fillna(0.0)
            fee = pd.to_numeric(copy_df.get('fee', 0), errors='coerce').fillna(0.0)

            pnl_display = running_pnl.where(t_type.eq('SELL'))
            pnl_display = pnl_display.map(lambda v: f"₹{float(v):,.2f}" if pd.notna(v) else "—")

            out = pd.DataFrame({
                'Date': copy_df.get('date', pd.Series([""] * len(copy_df))).astype(str),
                'Trade ID': copy_df.get('trade_id', pd.Series([""] * len(copy_df))).astype(str),
                'Symbol': copy_df.get('symbol', pd.Series([""] * len(copy_df))).astype(str),
                'Type': t_type,
                'Qty': qty.map(lambda v: f"{v:g}"),
                'Price ₹': price.map(lambda v: f"₹{float(v):,.2f}"),
                'Run. Qty': run_qty.map(lambda v: f"{v:g}"),
                'AvgCost ₹': avg_cost.map(lambda v: f"₹{float(v):,.2f}"),
                'Running PnL ₹': pnl_display,
                'Fees ₹': fee.map(lambda v: f"₹{float(v):,.2f}"),
            })

            tsv_data = out.to_csv(sep='\t', index=False)

            page = getattr(self.app_state, 'page', None)
            if page and hasattr(page, 'set_clipboard'):
                try:
                    page.set_clipboard(tsv_data)
                    self.show_snack(f"Copied {len(out)} trades to clipboard.", color=ft.Colors.GREEN_400)
                    return
                except Exception:
                    pass

            if sys.platform == 'darwin':
                subprocess.run('pbcopy', input=tsv_data.encode(), check=True)
            elif sys.platform == 'win32':
                subprocess.run('clip', input=tsv_data.encode(), check=True, shell=True)
            else:
                subprocess.run(['xclip', '-selection', 'clipboard'], input=tsv_data.encode(), check=True)

            self.show_snack(f"Copied {len(out)} trades to clipboard.", color=ft.Colors.GREEN_400)
        except Exception as ex:
            self.show_snack(f"Copy failed: {ex}", color=ft.Colors.RED_400)

    def did_mount(self):
        """Lifecycle hook."""
        self._is_active = True
        self._scrolled_left_once = False
        # Always register pickers in overlay, even when skipping data load
        for dp in [self.start_date_picker, self.end_date_picker]:
            if dp not in self.app_state.page.overlay:
                self.app_state.page.overlay.append(dp)
        if hasattr(self, 'edit_date_picker') and self.edit_date_picker not in self.app_state.page.overlay:
            self.app_state.page.overlay.append(self.edit_date_picker)

        # Skip double load when main.py navigate() already loaded data before mount
        if getattr(self, '_skip_load_in_did_mount', False):
            return

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
        self._is_active = False
        # Cancel pending debounced work so it can't trigger while hidden
        try:
            if self._search_timer:
                self._search_timer.cancel()
                self._search_timer = None
        except Exception:
            pass
        try:
            if self._date_reload_timer:
                self._date_reload_timer.cancel()
                self._date_reload_timer = None
        except Exception:
            pass
        # Bump sequence so in-flight background fetches can't repaint after unmount.
        try:
            self._load_seq += 1
        except Exception:
            pass
        self.app_state.trade_history_state = {
            'broker': self.broker_filter.value,
            'symbol': self.symbol_filter.value,
            'type': self.type_filter.value,
            'start_date': self._start_date,
            'end_date': self._end_date,
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
        try:
            brokers = self.app_state.get_brokers_cached(force_refresh=False)
        except Exception:
            import flet_app.common.models.crud as crud
            brokers = crud.get_all_brokers()
        self.broker_filter.options = ([ft.dropdown.Option("All")] + [ft.dropdown.Option(b) for b in brokers])

    def _on_symbol_search(self, e):
        """Debounced symbol search: wait 150ms after user stops typing."""
        if self._search_timer:
            self._search_timer.cancel()

        # Avoid triggering expensive full-history recalculation for very broad 1-char searches.
        # Users can still press Enter or click Search to run it.
        sym = (self.symbol_filter.value or "").strip()
        if 0 < len(sym) < 2:
            return

        # Pass _reload_brokers=False — no need to re-query brokers on every keystroke
        self._search_timer = threading.Timer(0.35, lambda: self.load_data(_reload_brokers=False))
        self._search_timer.daemon = True
        self._search_timer.start()

    def handle_start_date_click(self, e):
        target_date = self._start_date if self._start_date else datetime.now().date()
        self.start_date_picker.value = datetime.combine(target_date, datetime.min.time())
        self._open_picker(self.start_date_picker)

    def handle_end_date_click(self, e):
        target_date = self._end_date if self._end_date else datetime.now().date()
        self.end_date_picker.value = datetime.combine(target_date, datetime.min.time())
        self._open_picker(self.end_date_picker)

    def _on_start_date_change(self, e):
        selected_val = None
        # Flet DatePicker can deliver the chosen value via e.data (ISO date string)
        try:
            if e and getattr(e, 'data', None):
                raw = str(e.data)
                if raw.endswith('Z'):
                    raw = raw[:-1] + '+00:00'
                selected_val = datetime.fromisoformat(raw)
        except Exception:
            selected_val = None
        if selected_val is None:
            try:
                selected_val = e.control.value if e and getattr(e, 'control', None) else None
            except Exception:
                selected_val = None
        if selected_val is None:
            selected_val = self.start_date_picker.value
        if selected_val:
            # If picker returned timezone-aware datetime (often UTC), convert to local time first
            if isinstance(selected_val, datetime):
                try:
                    if selected_val.tzinfo is not None:
                        local_tz = datetime.now().astimezone().tzinfo
                        new_date = selected_val.astimezone(local_tz).date()
                    else:
                        new_date = selected_val.date()
                except Exception:
                    new_date = selected_val.date()
            else:
                new_date = selected_val
            changed = new_date != self._start_date
            self._start_date = new_date
            new_text = self._start_date.strftime('%Y-%m-%d')
            try:
                self.start_date_text.value = new_text
            except Exception:
                # Fallback for older instances, if any
                self.start_date_btn.text = new_text
            self.start_date_picker.value = datetime.combine(new_date, datetime.min.time())
            try:
                if hasattr(self, 'start_date_text'):
                    self.start_date_text.update()
                self.start_date_btn.update()
            except Exception:
                try:
                    self.app_state.page.update()
                except Exception:
                    pass
            if changed:
                self._data_loaded = False
                self._schedule_date_reload()

    def _on_end_date_change(self, e):
        selected_val = None
        # Flet DatePicker can deliver the chosen value via e.data (ISO date string)
        try:
            if e and getattr(e, 'data', None):
                raw = str(e.data)
                if raw.endswith('Z'):
                    raw = raw[:-1] + '+00:00'
                selected_val = datetime.fromisoformat(raw)
        except Exception:
            selected_val = None
        if selected_val is None:
            try:
                selected_val = e.control.value if e and getattr(e, 'control', None) else None
            except Exception:
                selected_val = None
        if selected_val is None:
            selected_val = self.end_date_picker.value
        if selected_val:
            # If picker returned timezone-aware datetime (often UTC), convert to local time first
            if isinstance(selected_val, datetime):
                try:
                    if selected_val.tzinfo is not None:
                        local_tz = datetime.now().astimezone().tzinfo
                        new_date = selected_val.astimezone(local_tz).date()
                    else:
                        new_date = selected_val.date()
                except Exception:
                    new_date = selected_val.date()
            else:
                new_date = selected_val
            changed = new_date != self._end_date
            self._end_date = new_date
            new_text = self._end_date.strftime('%Y-%m-%d')
            try:
                self.end_date_text.value = new_text
            except Exception:
                self.end_date_btn.text = new_text
            self.end_date_picker.value = datetime.combine(new_date, datetime.min.time())
            try:
                if hasattr(self, 'end_date_text'):
                    self.end_date_text.update()
                self.end_date_btn.update()
            except Exception:
                try:
                    self.app_state.page.update()
                except Exception:
                    pass
            if changed:
                self._data_loaded = False
                self._schedule_date_reload()

    def _on_edit_date_change(self, e):
        if not self._current_edit_date_tb:
            return

        selected_val = None
        # Prefer e.data when provided (ISO string)
        try:
            if e and getattr(e, 'data', None):
                raw = str(e.data)
                if raw.endswith('Z'):
                    raw = raw[:-1] + '+00:00'
                selected_val = datetime.fromisoformat(raw)
        except Exception:
            selected_val = None
        if selected_val is None:
            try:
                selected_val = e.control.value if e and getattr(e, "control", None) else None
            except Exception:
                selected_val = None
        if selected_val is None:
            selected_val = self.edit_date_picker.value

        if selected_val:
            # If picker returned timezone-aware datetime (often UTC), convert to local time first
            if isinstance(selected_val, datetime):
                try:
                    if selected_val.tzinfo is not None:
                        local_tz = datetime.now().astimezone().tzinfo
                        new_date = selected_val.astimezone(local_tz).date()
                    else:
                        new_date = selected_val.date()
                except Exception:
                    new_date = selected_val.date()
            else:
                new_date = selected_val
            self._current_edit_date_tb.value = new_date.strftime('%Y-%m-%d')
            # Normalize picker value for next open (Flet expects datetime)
            try:
                self.edit_date_picker.value = datetime.combine(new_date, datetime.min.time())
            except Exception:
                pass
            try:
                self._current_edit_date_tb.update()  # Targeted update on textfield only
            except Exception:
                pass

    def _schedule_date_reload(self):
        """Debounce date changes: wait 300ms so both start+end changes coalesce into one reload."""
        if self._date_reload_timer:
            self._date_reload_timer.cancel()
        self._date_reload_timer = threading.Timer(0.3, lambda: self.load_data(_reload_brokers=False, use_cache=False))
        self._date_reload_timer.daemon = True
        self._date_reload_timer.start()

    def handle_select_all(self, e):
        is_checked = e.control.value
        if is_checked and self.current_df is not None and not self.current_df.empty:
            self.selected_trades.update(self.current_df['trade_id'].astype(str).tolist())
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
            import flet_app.common.models.crud as crud
            import threading
            
            # Clear caches since data is changing
            self._calc_cache.clear()
            self._data_loaded = False
            self._cached_filters = None
            
            self._close_dialog(dlg)
            self.loading_ring.visible = True
            self.loading_ring.update()

            def bg_bulk_delete():
                try:
                    import flet_app.common.models.crud as crud_module
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

                    self.app_state.page.run_task(finish)
                except Exception as ex:
                    error_msg = str(ex)  # Capture error message to avoid scope issues
                    async def err_finish():
                        self.show_snack(f"Error during bulk delete: {error_msg}", color=ft.Colors.RED_400)
                        self.load_data(_reload_brokers=False, use_cache=False)  # Refresh with search criteria on error
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
        try:
            self.start_date_text.value = self._start_date.strftime('%Y-%m-%d')
            self.end_date_text.value = self._end_date.strftime('%Y-%m-%d')
        except Exception:
            # Fallback if running against an older instance
            self.start_date_btn.text = self._start_date.strftime('%Y-%m-%d')
            self.end_date_btn.text = self._end_date.strftime('%Y-%m-%d')
        self.start_date_picker.value = all_trades_start
        self.end_date_picker.value = today
        try:
            self._grid_list.controls = []
        except Exception:
            pass
        self.status_text.value = "Use the filters above and click Search to load trades."
        self.status_text.visible = True
        self.total_records = 0
        self.selected_trades.clear()
        self.select_all_chk.value = False
        object.__setattr__(self, 'current_df', None)
        # Clear caches when filters change
        self._data_loaded = False
        self._calc_cache.clear()
        self._cached_filters = None

        # Targeted repaint of the updated controls
        try:
            self.broker_filter.update()
            self.symbol_filter.update()
            self.type_filter.update()
            if hasattr(self, 'start_date_text'):
                self.start_date_text.update()
            if hasattr(self, 'end_date_text'):
                self.end_date_text.update()
            self._grid_list.update()
            self.status_text.update()
        except Exception:
            pass

    def handle_sort(self, e):
        self.sort_column_index = e.column_index
        self.sort_ascending = e.ascending
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
        
        cache_ver = getattr(getattr(self.app_state, 'data_cache', None), 'version', 0)
        # If cache exists and filters unchanged and we're re-visiting, display cached data instantly
        if use_cache and self._data_loaded and self._cached_filters == current_filters and self.current_df is not None and getattr(self, '_cache_version', None) == cache_ver:
            self.render_table()  # Instant render from cache
            return
        
        self._cached_filters = current_filters
        self._data_loaded = True

        # New request id; any older background results will be ignored
        self._load_seq += 1
        request_seq = self._load_seq
        
        if _reload_brokers:
            self._load_broker_options()
        
        if not self._is_preloading:
            self.loading_ring.visible = True
            self.loading_status.value = "Fetching trades..."
            try:
                self.loading_ring.update()
                self.loading_status.update()
            except Exception: pass
        # Run heavy DB + stats work on a background thread to keep the UI responsive
        threading.Thread(target=self._fetch_and_render, args=(request_seq,), daemon=True).start()

    def _fetch_and_render(self, request_seq: int):
        f_broker = self.broker_filter.value
        f_symbol = self.symbol_filter.value.strip().upper() if self.symbol_filter.value else ""
        f_type = self.type_filter.value

        # Build cache key FIRST — if we have a hit, skip the DB entirely
        cache_key = (f_broker, f_symbol, f_type,
                     self._start_date.strftime('%Y-%m-%d') if self._start_date else None,
                     self._end_date.strftime('%Y-%m-%d') if self._end_date else None)

        if cache_key in self._calc_cache:
            df, summary_raw = self._calc_cache[cache_key]
        else:
            try:
                filters = TradeHistoryFilters(
                    broker=f_broker or "All",
                    symbol_like=f_symbol or "",
                    trade_type=f_type or "All",
                    start_date=self._start_date.strftime('%Y-%m-%d') if self._start_date else None,
                    end_date=self._end_date.strftime('%Y-%m-%d') if self._end_date else None,
                )
                df, summary_raw = self.app_state.data_cache.get_tradehistory_filtered(filters)
            except Exception:
                df = pd.DataFrame()
                summary_raw = {"qty_buy": 0.0, "qty_sell": 0.0, "fee_buy": 0.0, "fee_sell": 0.0, "total_pnl": 0.0}
            self._calc_cache[cache_key] = (df, summary_raw)

        total_records = len(df)

        total_qty_buy = float(summary_raw.get('qty_buy', 0.0) or 0.0)
        total_qty_sell = float(summary_raw.get('qty_sell', 0.0) or 0.0)
        total_fees_buy = float(summary_raw.get('fee_buy', 0.0) or 0.0)
        total_fees_sell = float(summary_raw.get('fee_sell', 0.0) or 0.0)
        total_pnl = float(summary_raw.get('total_pnl', 0.0) or 0.0)
        pnl_color = ft.Colors.GREEN if total_pnl > 0 else (ft.Colors.RED if total_pnl < 0 else ft.Colors.WHITE)
        summary = {
            'qty_buy':   f"Buy: {total_qty_buy:,.0f}",
            'qty_sell':  f"|   Sell: {total_qty_sell:,.0f}",
            'pnl':       f"₹{total_pnl:,.2f}",
            'pnl_color': pnl_color,
            'fees_buy':  f"Buy: ₹{total_fees_buy:,.2f}",
            'fees_sell': f"|   Sell: ₹{total_fees_sell:,.2f}",
        }
        # Only the latest request is allowed to update UI state.
        if request_seq != getattr(self, '_load_seq', 0):
            return

        object.__setattr__(self, 'current_df', df)
        try:
            object.__setattr__(self, '_cache_version', getattr(self.app_state.data_cache, 'version', 0))
        except Exception:
            object.__setattr__(self, '_cache_version', 0)
        self.total_records = total_records
        self._cached_summary = summary
        self._summary_dirty = True
        # Dispatch all UI updates back to the main thread from the background thread
        async def _finish_on_ui():
            # Ignore stale completions that lost the race
            if request_seq != getattr(self, '_load_seq', 0):
                return
            if not getattr(self, '_is_active', False):
                return
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
            self._grid_list.controls = []
            self.status_text.value = "No trades found for the selected filters."
            self.status_text.visible = True
            self.select_all_chk.value = False
            # Only update table and status, not entire page (much faster)
            try:
                self._grid_list.update()
                self.status_text.update()
                try:
                    self.select_all_chk.update()
                except Exception:
                    pass
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
        visible_df = df

        actual_count = len(visible_df)
        while len(self._row_pool) < actual_count:
            self._row_pool.append(self._create_row_slot())

        # Populate row pool in-place — no new Flet objects created per re-render.
        for i, (slot, row) in enumerate(zip(self._row_pool, visible_df.itertuples(index=False))):
            row_dict    = row._asdict()
            trade_id    = str(row_dict.get('trade_id', ''))
            row_num     = i + 1
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
            row_ctrl = slot['row']
            row_ctrl.bgcolor = alternating_row_color(row_num)
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

            # Subtle selection highlight
            if is_selected:
                row_ctrl.bgcolor = ft.Colors.with_opacity(0.16, ft.Colors.BLUE_500)

        self._grid_list.controls = [self._row_pool[i]['row'] for i in range(actual_count)]

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

        all_visible_selected = visible_df['trade_id'].astype(str).isin(self.selected_trades).all()
        self.select_all_chk.value = bool(len(visible_df) > 0 and all_visible_selected)

        # Targeted updates: updating the entire `content` tree is expensive and
        # can make even small result sets feel sluggish.
        try:
            self._grid_list.update()
        except Exception:
            pass
        try:
            self.status_text.update()
        except Exception:
            pass
        try:
            self.select_all_chk.update()
        except Exception:
            pass
        if _summary_updated:
            for t in (
                self.summary_qty_buy_value,
                self.summary_qty_sell_value,
                self.summary_pnl_value,
                self.summary_fees_buy_value,
                self.summary_fees_sell_value,
            ):
                try:
                    t.update()
                except Exception:
                    pass

        # Keep table scrolled to left so leading columns are visible — but only
        # once per mount/session (avoid doing this on every render).
        async def scroll_to_left_once():
            if self._scrolled_left_once:
                return
            self._scrolled_left_once = True
            try:
                await self.table_row.scroll_to(offset=0, duration=0)
            except Exception:
                pass
        try:
            page = self.app_state.page
            if page:
                page.run_task(scroll_to_left_once)
        except Exception:
            pass

    def _create_row_slot(self):
        """Create one row slot (reused across renders)."""
        chk = ft.Checkbox(value=False)
        t_num = ft.Text("", size=14, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.RIGHT)
        t_date = ft.Text("", size=14)
        t_id = ft.Text("", size=14)
        t_sym = ft.Text("", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
        t_type = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
        t_qty = ft.Text("", size=14, text_align=ft.TextAlign.RIGHT)
        t_price = ft.Text("", size=14, text_align=ft.TextAlign.RIGHT)
        t_rqty = ft.Text("", size=14, text_align=ft.TextAlign.RIGHT)
        t_avg = ft.Text("", size=14, text_align=ft.TextAlign.RIGHT)
        t_pnl = ft.Text("", size=14, text_align=ft.TextAlign.RIGHT)
        t_fee = ft.Text("", size=14, text_align=ft.TextAlign.RIGHT)

        btn_edit = ft.IconButton(ft.Icons.EDIT, icon_size=18, icon_color=ft.Colors.ORANGE_400, tooltip="Edit Trade")
        btn_del = ft.IconButton(ft.Icons.DELETE, icon_size=18, icon_color=ft.Colors.RED_400, tooltip="Delete Trade")
        action_row = ft.Row([btn_edit, btn_del], spacing=4)


        def _cell(ctrl, width: int, numeric: bool = False, center: bool = False):
            align = ft.alignment.Alignment(0, 0) if center else (ft.alignment.Alignment(1, 0) if numeric else ft.alignment.Alignment(-1, 0))
            return ft.Container(
                content=ctrl,
                width=int(width),
                alignment=align,
                padding=ft.padding.symmetric(vertical=12, horizontal=8),
            )

        row = ft.Container(
            content=ft.Row(
                controls=[
                    _cell(chk, self.col_widths[0], center=True),
                    _cell(t_num, self.col_widths[1], numeric=True),
                    _cell(t_date, self.col_widths[2]),
                    _cell(t_id, self.col_widths[3]),
                    _cell(t_sym, self.col_widths[4]),
                    _cell(t_type, self.col_widths[5]),
                    _cell(t_qty, self.col_widths[6], numeric=True),
                    _cell(t_price, self.col_widths[7], numeric=True),
                    _cell(t_rqty, self.col_widths[8], numeric=True),
                    _cell(t_avg, self.col_widths[9], numeric=True),
                    _cell(t_pnl, self.col_widths[10], numeric=True),
                    _cell(t_fee, self.col_widths[11], numeric=True),
                    ft.Container(
                        content=action_row,
                        width=int(self.col_widths[12]),
                        alignment=ft.alignment.Alignment(0, 0),
                        padding=ft.padding.symmetric(vertical=8, horizontal=4),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.TRANSPARENT,
        )

        return {
            'row': row,
            'chk': chk,
            't_num': t_num,
            't_date': t_date,
            't_id': t_id,
            't_sym': t_sym,
            't_type': t_type,
            't_qty': t_qty,
            't_price': t_price,
            't_rqty': t_rqty,
            't_avg': t_avg,
            't_pnl': t_pnl,
            't_fee': t_fee,
            'btn_edit': btn_edit,
            'btn_del': btn_del,
        }

    def delete_trade(self, broker, trade_id):
        import flet_app.common.models.crud as crud
        import threading
        
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

        # Refresh in-memory datasets so view switching stays cache-only.
        try:
            self.app_state.refresh_data_cache_async()
        except Exception:
            pass
        
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

        async def finish():
            # Data changed — force a real reload (avoid rendering cached df)
            object.__setattr__(self, 'current_df', None)
            self._data_loaded = False
            self._cached_filters = None
            self.load_data(_reload_brokers=False, use_cache=False)
        self.app_state.page.run_task(finish)

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

        import flet_app.common.models.crud as crud

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
            try:
                symbol_changed = new_symbol != original_symbol

                # 1. Update the individual trade first (fast DB write)
                crud.update_trade(original_broker, str(trade_id), new_date, new_symbol, new_type, n_qty, n_price, n_fee)

                # 2. If symbol changed, rename remaining trades for this broker/symbol
                if symbol_changed:
                    crud.replace_symbol(original_symbol, new_symbol, original_broker)

                # 3. Invalidate caches
                if hasattr(self.app_state, 'views'):
                    try:
                        if self.app_state.views.get(0):
                            self.app_state.views[0].invalidate_cache()
                    except Exception:
                        pass

                # Refresh in-memory datasets so view switching stays cache-only.
                try:
                    self.app_state.refresh_data_cache_async()
                except Exception:
                    pass
                    try:
                        if self.app_state.views.get(1):
                            self.app_state.views[1].invalidate_cache()
                    except Exception:
                        pass

                # 4. Refresh the table IMMEDIATELY
                async def finish():
                    # Data changed — force a real reload (avoid rendering cached df)
                    object.__setattr__(self, 'current_df', None)
                    self._data_loaded = False
                    self._cached_filters = None
                    self.load_data(_reload_brokers=False, use_cache=False)

                self.app_state.page.run_task(finish)
            except Exception as ex:
                error_msg = str(ex)
                async def err_finish():
                    self.show_snack(f"Error saving trade: {error_msg}", color=ft.Colors.RED_400)
                    self.loading_ring.visible = False
                    try:
                        self.loading_ring.update()
                    except Exception:
                        pass
                self.app_state.page.run_task(err_finish)

        threading.Thread(target=bg_save, daemon=True).start()

