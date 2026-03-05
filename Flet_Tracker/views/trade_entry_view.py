import flet as ft
import pandas as pd
import os
import asyncio
from datetime import datetime
from flet_app.common.state import AppState
from flet_app.components.ui_elements import page_title, premium_card
import flet_app.common.models.crud as crud
import engine
from flet_app.common.engine import calculate_trade_fees

class TradeEntryView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True
        self.alignment = ft.alignment.Alignment(-1.0, -1.0)
        object.__setattr__(self, 'pending_import_df', None)
        self._data_loaded = False
        self._needs_reload = True

        # Initialize the pickers as part of the class instance
        today = datetime.now()
        self.date_picker = ft.DatePicker(
            on_change=self.on_date_change,
            value=today
        )
        # Flet 0.81: FilePicker is a Service. Must be in page.overlay before calling pick_files().
        self.import_picker = ft.FilePicker()
        # Remember last import folder
        self._last_import_path = None
        
        # Create date button with Text control so we can update it
        self.date_text = ft.Text(today.strftime("%Y-%m-%d"), size=13)
        self.date_btn = ft.ElevatedButton(
            content=self.date_text,
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.open_date_picker,
            width=150
        )

        self.broker_dropdown = ft.Dropdown(
            label="Broker", 
            expand=True,
            border_radius=8
        )
        self.symbol_input = ft.TextField(
            label="Symbol (e.g. ITC)", 
            expand=True,
            prefix_icon=ft.Icons.TRENDING_UP,
            border_radius=8
        )
        self.type_radio = ft.RadioGroup(
            ft.Row([
                ft.Radio(value="BUY",  label="  Buy"),
                ft.Radio(value="SELL", label="  Sell"),
            ], spacing=20)
        )
        self.type_radio.value = "BUY"
        self.type_radio.on_change = self.update_summary  # Update summary on trade type change
        
        self.qty_input = ft.TextField(
            label="Quantity", 
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons.INVENTORY,
            border_radius=8
        )
        self.price_input = ft.TextField(
            label="Price (₹)", 
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons.CURRENCY_RUPEE,
            border_radius=8
        )
        self.calculated_fee_text = ft.Text("Estimated Fee: ₹0.00", color="#AAAAAA", size=12)
        
        # Validation indicators
        self.qty_valid = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_600, size=18, visible=False)
        self.price_valid = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_600, size=18, visible=False)
        
        # Transaction summary elements (updated dynamically)
        self.summary_total_text = ft.Text("₹0.00", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN)
        self.summary_breakdown = ft.Text("", size=12, color=ft.Colors.GREY_400)
        self.summary_type_icon = ft.Icon(ft.Icons.TRENDING_UP, color=ft.Colors.GREEN, size=32)

        def _qty_change(e):
            self._filter_numeric(e)
            self.update_summary(e)
        
        def _price_change(e):
            self._filter_numeric(e)
            self.update_summary(e)
        
        self.qty_input.on_change = _qty_change
        self.price_input.on_change = _price_change

        # Modal dialog for import preview (instead of inline container)
        self.preview_modal = None

        # Skipped duplicates list (faster than DataTable)
        self._dupe_col_widths = [110, 90, 60]

        def _dupe_hdr_cell(text: str, width: int, numeric: bool = False):
            return ft.Container(
                content=ft.Text(text, size=11, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_600,
                                text_align=ft.TextAlign.RIGHT if numeric else ft.TextAlign.LEFT),
                width=int(width),
                alignment=ft.alignment.Alignment(1, 0) if numeric else ft.alignment.Alignment(-1, 0),
                padding=ft.padding.symmetric(vertical=6, horizontal=8),
            )

        self._dupe_header = ft.Container(
            content=ft.Row(
                controls=[
                    _dupe_hdr_cell("Date", self._dupe_col_widths[0]),
                    _dupe_hdr_cell("Sym", self._dupe_col_widths[1]),
                    _dupe_hdr_cell("Qty", self._dupe_col_widths[2], numeric=True),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.BLUE_400),
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.18, ft.Colors.WHITE))),
        )
        self._dupe_list = ft.ListView(expand=True, spacing=0, padding=0)
        self._dupe_row_pool = []
        self.dupe_container = ft.Container(
            content=premium_card(
                ft.Column([
                    ft.Text("Skipped Duplicates", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.RED_400),
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Column([self._dupe_header, self._dupe_list], spacing=0, expand=True)
                            ], scroll=ft.ScrollMode.ADAPTIVE)
                        ], scroll=ft.ScrollMode.ADAPTIVE),
                        height=150
                    )
                ], tight=True)
            ),
            visible=False
        )

        left_pane = ft.Column([
            # ===== MANUAL ENTRY CARD =====
            premium_card(
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.EDIT, size=24, color=ft.Colors.BLUE_400),
                        ft.Text("Manual Trade Entry", size=18, weight=ft.FontWeight.W_600),
                    ], spacing=10),
                    ft.Divider(color="#333333"),
                    
                    # Broker & Date Row
                    ft.Row([
                        ft.Column([
                            ft.Text("Broker", size=11, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_500),
                            self.broker_dropdown
                        ], width=160),
                        ft.Column([
                            ft.Text("Date", size=11, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_500),
                            self.date_btn
                        ], width=160),
                    ], spacing=20),
                    
                    # Symbol & Type Row
                    ft.Row([
                        ft.Column([
                            ft.Text("Symbol", size=11, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_500),
                            self.symbol_input
                        ], width=160),
                        ft.Column([
                            ft.Text("Type", size=11, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_500),
                            self.type_radio
                        ], width=200),
                    ], spacing=20),
                    
                    # Quantity & Price Row  
                    ft.Row([
                        ft.Column([
                            ft.Text("Quantity", size=11, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_500),
                            ft.Row([self.qty_input, self.qty_valid], spacing=8, expand=False)
                        ], width=160),
                        ft.Column([
                            ft.Text("Price (₹)", size=11, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_500),
                            ft.Row([self.price_input, self.price_valid], spacing=8, expand=False)
                        ], width=160),
                    ], spacing=20),
                    
                    # Fee Info
                    ft.Container(
                        ft.Row([
                            ft.Icon(ft.Icons.LOCAL_OFFER, size=16, color=ft.Colors.ORANGE),
                            self.calculated_fee_text
                        ], spacing=8),
                        bgcolor="#2A2A2A",
                        padding=12,
                        border_radius=8
                    ),
                    
                    # Save Button
                    ft.Row([
                        ft.ElevatedButton(
                            content=ft.Row([
                                ft.Icon(ft.Icons.SAVE, size=18),
                                ft.Text("Save Trade", size=14, weight=ft.FontWeight.W_600)
                            ], spacing=8),
                            on_click=self.save_trade,
                            bgcolor=ft.Colors.BLUE_600,
                            color=ft.Colors.WHITE,
                            width=200,
                            height=50
                        )
                    ], alignment=ft.MainAxisAlignment.CENTER)
                ], spacing=16)
            ),
            
            # ===== BULK IMPORT CARD =====
            premium_card(
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.CLOUD_UPLOAD, size=24, color=ft.Colors.PURPLE),
                        ft.Text("Bulk Import (CSV)", size=18, weight=ft.FontWeight.W_600),
                    ], spacing=10),
                    ft.Divider(color="#333333"),
                    ft.Text("Expected Columns: broker, date, symbol, type, qty, price", color=ft.Colors.GREY_500, size=12),
                    ft.Container(
                        ft.ElevatedButton(
                            content=ft.Row([
                                ft.Icon(ft.Icons.UPLOAD_FILE, size=18),
                                ft.Text("Select CSV File", size=13, weight=ft.FontWeight.W_600)
                            ], spacing=8),
                            on_click=self.handle_import_click,
                            bgcolor=ft.Colors.PURPLE_600,
                            color=ft.Colors.WHITE,
                            width=220,
                            height=45
                        ),
                        alignment=ft.alignment.Alignment(0, 0)
                    )
                ], spacing=12)
            ),
            self.dupe_container
        ], expand=4, spacing=20)  # Removed preview_container - now using modal
        
        right_pane = ft.Column([
            # Transaction Summary Card
            premium_card(
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.ANALYTICS, size=24, color=ft.Colors.BLUE_400),
                        ft.Text("Transaction Summary", size=16, weight=ft.FontWeight.W_600),
                    ], spacing=10),
                    ft.Divider(color="#333333"),
                    
                    # Type indicator
                    ft.Row([
                        self.summary_type_icon,
                        ft.Column([
                            ft.Text("Trade Type", size=12, color=ft.Colors.GREY_400),
                            ft.Text(self.type_radio.value or "N/A", size=14, weight=ft.FontWeight.W_600, ref=ft.Ref())
                        ], spacing=2)
                    ], spacing=16),
                    
                    ft.Container(height=2, bgcolor="#333333"),
                    
                    # Summary breakdown
                    ft.Column([
                        ft.Row([
                            ft.Text("Quantity", color=ft.Colors.GREY_400, size=12),
                            ft.Text("", size=12, ref=ft.Ref())
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Text("Unit Price", color=ft.Colors.GREY_400, size=12),
                            ft.Text("", size=12, ref=ft.Ref())
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Text("Subtotal", color=ft.Colors.GREY_400, size=12),
                            ft.Text("", size=12, ref=ft.Ref())
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(color="#333333"),
                        ft.Row([
                            ft.Text("Trading Fee", color=ft.Colors.ORANGE_600, size=12, weight=ft.FontWeight.W_600),
                            ft.Text("₹0.00", size=12, color=ft.Colors.ORANGE_600, ref=ft.Ref())
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=8, ref=ft.Ref()),
                    
                    ft.Container(height=2, bgcolor="#333333"),
                    
                    # Total
                    ft.Row([
                        ft.Column([
                            ft.Text("Total Value", size=11, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_600),
                        ]),
                        ft.Column([
                            self.summary_total_text
                        ], alignment=ft.MainAxisAlignment.END)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    
                ], spacing=12)
            )
        ], expand=8, spacing=16)

        self.content = ft.Column([
            page_title("Trade Entry"),
            ft.Row([
                left_pane,
                right_pane
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START, expand=True),
        ], spacing=24, scroll=ft.ScrollMode.AUTO)

    def _filter_numeric(self, e):
        """Filter out non-numeric characters from input"""
        if e.control.value:
            # Allow only digits and decimal point
            filtered = ''.join(c for c in e.control.value if c.isdigit() or c == '.')
            # Prevent multiple decimal points
            if filtered.count('.') > 1:
                filtered = filtered[:filtered.rfind('.')]
            if filtered != e.control.value:
                e.control.value = filtered
                e.control.update()

    def did_mount(self):
        """Lifecycle hook called when the view is navigated to."""
        # Skip double load when main.py navigate() already handles data loading
        if getattr(self, '_skip_load_in_did_mount', False):
            # Still register pickers in overlay even when skipping load
            if self.date_picker not in self.app_state.page.overlay:
                self.app_state.page.overlay.append(self.date_picker)
            return
        if self._needs_reload or not self._data_loaded:
            self.load_data()
        if self.date_picker not in self.app_state.page.overlay:
            self.app_state.page.overlay.append(self.date_picker)

    def did_unmount(self):
        """Lifecycle hook called when navigating away."""
        pass

    def invalidate_cache(self):
        """Mark broker dropdown as stale (reload on next mount)."""
        self._needs_reload = True

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

    def open_date_picker(self, e):
        # Sync picker value to a proper datetime before opening
        try:
            if self.date_picker.value:
                val = self.date_picker.value
                if hasattr(val, 'hour'):
                    # Already a datetime — use as-is
                    pass
                else:
                    # It's a date object — convert to datetime for Flet
                    self.date_picker.value = datetime.combine(val, datetime.min.time())
            else:
                self.date_picker.value = datetime.now()
        except Exception:
            self.date_picker.value = datetime.now()

        # Open the date picker
        try:
            if hasattr(self.app_state.page, 'open'):
                self.app_state.page.open(self.date_picker)
            else:
                self.date_picker.open = True
                self.date_picker.update()
        except Exception:
            pass

    def on_date_change(self, e):
        selected_val = None
        # Flet DatePicker can deliver the chosen value via e.data (ISO date string)
        try:
            if e and getattr(e, "data", None):
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
            selected_val = self.date_picker.value

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
            new_text = new_date.strftime("%Y-%m-%d")
            self.date_text.value = new_text
            # Keep picker value normalized as datetime for reliable reopen behavior
            try:
                self.date_picker.value = datetime.combine(new_date, datetime.min.time())
            except Exception:
                pass
            try:
                self.date_text.update()
                # Some Flet versions don't repaint button content unless the parent updates.
                self.date_btn.update()
            except Exception:
                pass

    def load_data(self):
        try:
            brokers = self.app_state.get_brokers_cached(force_refresh=False)
        except Exception:
            brokers = crud.get_all_brokers()
        current_options = [o.key for o in self.broker_dropdown.options] if self.broker_dropdown.options else []
        if brokers == current_options:
            self._data_loaded = True
            self._needs_reload = False
            return  # No change — skip update
        self.broker_dropdown.options = [ft.dropdown.Option(b) for b in brokers]
        if brokers and not self.broker_dropdown.value:
            self.broker_dropdown.value = brokers[0]
        try:
            self.broker_dropdown.update()
        except Exception:
            pass
        self._data_loaded = True
        self._needs_reload = False

    def update_summary(self, e=None):
        """Update transaction summary with real-time calculations and color coding"""
        qty_str = self.qty_input.value or "0"
        price_str = self.price_input.value or "0"
        t_type = self.type_radio.value or "BUY"
        
        try:
            qty = float(qty_str) if qty_str else 0
            price = float(price_str) if price_str else 0
        except ValueError:
            qty = price = 0
        
        # Calculate subtotal and fee
        subtotal = qty * price
        fee = calculate_trade_fees(t_type, qty, price, is_delivery=True)
        total = subtotal + fee
        
        # Color code based on trade type
        if t_type == "BUY":
            color = ft.Colors.GREEN
            icon = ft.Icons.TRENDING_UP
        else:
            color = ft.Colors.RED
            icon = ft.Icons.TRENDING_DOWN
        
        # Update summary display
        self.summary_total_text.value = f"₹{total:,.2f}"
        self.summary_total_text.color = color
        self.summary_type_icon.name = icon
        self.summary_type_icon.color = color
        
        # Update calculated fee
        self.calculated_fee_text.value = f"Estimated Fee: ₹{fee:,.2f}"
        
        # Show validation checkmarks
        self.qty_valid.visible = qty > 0
        self.price_valid.visible = price > 0
        
        # Update UI
        try:
            self.summary_total_text.update()
            self.summary_type_icon.update()
            self.calculated_fee_text.update()
            self.qty_valid.update()
            self.price_valid.update()
        except Exception:
            pass
    
    def _set_type(self, trade_type: str):
        """Set trade type (BUY/SELL)"""
        self.type_radio.value = trade_type
        self.update_summary()
    
    def update_fees(self, e):
        """Legacy method - calls update_summary for compatibility"""
        self.update_summary(e)

    def save_trade(self, e):
        try:
            broker = self.broker_dropdown.value
            date = self.date_text.value
            symbol = self.symbol_input.value.strip().upper()
            t_type = self.type_radio.value
            
            # Validate broker
            if not broker:
                raise ValueError("Please select a broker")
            
            # Validate date (should always have a value - defaults to today)
            if not date:
                raise ValueError("Please select a date")
            
            # Validate symbol
            if not symbol:
                raise ValueError("Please enter a symbol")
            
            # Validate quantity
            if not self.qty_input.value or self.qty_input.value.strip() == "":
                raise ValueError("Please enter quantity")
            try:
                qty = float(self.qty_input.value)
            except ValueError:
                raise ValueError("Quantity must be a valid number")
            if qty <= 0:
                raise ValueError("Quantity must be greater than 0")
            
            # Validate price
            if not self.price_input.value or self.price_input.value.strip() == "":
                raise ValueError("Please enter price")
            try:
                price = float(self.price_input.value)
            except ValueError:
                raise ValueError("Price must be a valid number")
            if price <= 0:
                raise ValueError("Price must be greater than 0")
            
            # Validate trade type
            if not t_type:
                raise ValueError("Please select trade type (BUY/SELL)")
            
            fee = calculate_trade_fees(t_type, qty, price, is_delivery=True)

            import time
            timestamp = int(time.time() * 1000)
            manual_id = f"MT_{date.replace('-', '')}_{timestamp}"
            crud.add_trade(broker, date, symbol, t_type, qty, price, fee, manual_id)
            
            # Reset form fields after successful save
            self.symbol_input.value = ""
            self.qty_input.value = ""
            self.price_input.value = ""
            self.type_radio.value = "BUY"
            self.calculated_fee_text.value = "Estimated Fee: ₹0.00"
            
            try:
                self.symbol_input.update()
                self.qty_input.update()
                self.price_input.update()
                self.type_radio.update()
                self.calculated_fee_text.update()
            except Exception:
                pass
            
            self.show_snack("Trade saved successfully! ✓", color=ft.Colors.GREEN_600)
            
            import threading
            def finish_refresh():
                # Rebuild holdings to update all calculations
                try:
                    from flet_app.common.engine import rebuild_holdings
                    rebuild_holdings()
                except Exception:
                    pass
                
                # CRITICAL: Invalidate all view caches when trade added
                if hasattr(self.app_state, 'views'):
                    try:
                        if self.app_state.views.get(0):  # Dashboard
                            self.app_state.views[0].invalidate_cache()
                    except: pass
                    try:
                        if self.app_state.views.get(1):  # Holdings
                            self.app_state.views[1].invalidate_cache()
                    except: pass
                    try:
                        if self.app_state.views.get(3):  # Trade History
                            self.app_state.views[3].invalidate_cache()
                    except: pass

                # Refresh in-memory datasets so view switching stays cache-only.
                try:
                    self.app_state.refresh_data_cache_async()
                except Exception:
                    pass

            threading.Thread(target=finish_refresh, daemon=True).start()
        except Exception as ex:
            self.show_snack(f"Error: {str(ex)}", color=ft.Colors.RED_600)

    async def handle_import_click(self, _):
        """Triggers the file picker for CSV import."""
        try:
            # Use last imported directory if available, otherwise use home directory
            initial_dir = None
            if self._last_import_path and os.path.isdir(os.path.dirname(self._last_import_path)):
                initial_dir = os.path.dirname(self._last_import_path)
            
            files = await self.import_picker.pick_files(
                allowed_extensions=["csv"],
                allow_multiple=False,
                initial_directory=initial_dir
            )
        except Exception:
            return

        if not files or not files[0].path:
            return

        file_path = files[0].path
        # Remember this folder for next time
        self._last_import_path = file_path
        self.show_snack(f"Loading {os.path.basename(file_path)}...")

        try:
            df = None
            for enc in ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, encoding=enc)
                    break
                except Exception: pass
            if df is None: raise ValueError("Could not read CSV.")

            df.columns = [c.lower().strip() for c in df.columns]
            col_map = {'trade_date': 'date', 'trade_type': 'type', 'quantity': 'qty'}
            df.rename(columns=col_map, inplace=True)

            required = ['date', 'symbol', 'type', 'qty', 'price']
            missing = [col for col in required if col not in df.columns]
            if missing: raise ValueError(f"CSV missing columns: {', '.join(missing)}")

            if 'trade_id' not in df.columns:
                import time
                t_base = int(time.time())
                df['trade_id'] = [f"BT_{t_base}_{i}" for i in range(len(df))]

            has_broker = 'broker' in df.columns
            object.__setattr__(self, 'pending_import_df', df)

            # Only build preview for first 50 rows to avoid slow rendering
            preview_items = []
            for i, row in enumerate(df.itertuples(index=False), start=1):
                if i > 50:  # Limit preview to first 50 rows
                    break
                rd = row._asdict()

                preview_items.append({
                    '#': str(i),
                    'date': str(rd['date']),
                    'sym': str(rd['symbol']).upper(),
                    'type': str(rd['type']).upper(),
                    'qty': str(rd['qty']),
                    'price': str(rd['price']),
                    'id': str(rd.get('trade_id', '')),
                    '_is_note': False,
                })
            
            if len(df) > 50:
                preview_items.append({
                    '#': '...',
                    'date': f"Showing first 50 of {len(df)} trades",
                    'sym': '', 'type': '', 'qty': '', 'price': '', 'id': '',
                    '_is_note': True,
                })

            self.preview_broker_dropdown = ft.Dropdown(
                label="Select Broker for these trades*",
                options=[ft.dropdown.Option(b) for b in crud.get_all_brokers()],
                visible=not has_broker
            )
            self.preview_progress_bar = ft.ProgressBar(value=0.0, visible=False)
            self.preview_status_text = ft.Text("")

            self.confirm_btn = ft.ElevatedButton(
                "Confirm Import", 
                on_click=self.confirm_import, 
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE,
                width=140,
                height=40
            )
            
            # Build preview grid (fixed header + ListView rows)
            p_cols = ["#", "Date", "Sym", "Type", "Qty", "Price", "ID"]
            p_widths = [40, 110, 90, 70, 70, 80, 240]

            def _p_hdr_cell(text: str, width: int, numeric: bool = False):
                return ft.Container(
                    content=ft.Text(text, weight=ft.FontWeight.W_600, size=12,
                                    text_align=ft.TextAlign.RIGHT if numeric else ft.TextAlign.LEFT),
                    width=int(width),
                    alignment=ft.alignment.Alignment(1, 0) if numeric else ft.alignment.Alignment(-1, 0),
                    padding=ft.padding.symmetric(vertical=10, horizontal=8),
                )

            preview_header = ft.Container(
                content=ft.Row(
                    controls=[
                        _p_hdr_cell(p_cols[0], p_widths[0], numeric=True),
                        _p_hdr_cell(p_cols[1], p_widths[1]),
                        _p_hdr_cell(p_cols[2], p_widths[2]),
                        _p_hdr_cell(p_cols[3], p_widths[3]),
                        _p_hdr_cell(p_cols[4], p_widths[4], numeric=True),
                        _p_hdr_cell(p_cols[5], p_widths[5], numeric=True),
                        _p_hdr_cell(p_cols[6], p_widths[6]),
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
                border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE))),
            )

            def _p_cell(text: str, width: int, numeric: bool = False, bold: bool = False, color=None):
                return ft.Container(
                    content=ft.Text(text, size=12, weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
                                    color=color, text_align=ft.TextAlign.RIGHT if numeric else ft.TextAlign.LEFT),
                    width=int(width),
                    alignment=ft.alignment.Alignment(1, 0) if numeric else ft.alignment.Alignment(-1, 0),
                    padding=ft.padding.symmetric(vertical=8, horizontal=8),
                )

            preview_list = ft.ListView(expand=True, spacing=0, padding=0)
            rows_controls = []
            for idx, item in enumerate(preview_items):
                is_note = bool(item.get('_is_note'))
                row = ft.Container(
                    content=ft.Row(
                        controls=[
                            _p_cell(item['#'], p_widths[0], numeric=True, color=ft.Colors.GREY_600 if is_note else None),
                            _p_cell(item['date'], p_widths[1], color=ft.Colors.GREY_600 if is_note else None),
                            _p_cell(item['sym'], p_widths[2], bold=True if item['sym'] else False),
                            _p_cell(item['type'], p_widths[3]),
                            _p_cell(item['qty'], p_widths[4], numeric=True),
                            _p_cell(item['price'], p_widths[5], numeric=True),
                            _p_cell(item['id'], p_widths[6], color=ft.Colors.GREY_400 if item['id'] else None),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE) if idx % 2 == 0 else ft.Colors.TRANSPARENT,
                )
                rows_controls.append(row)
            preview_list.controls = rows_controls

            preview_table = ft.Row(
                [ft.Column([preview_header, preview_list], spacing=0, expand=True)],
                scroll=ft.ScrollMode.ADAPTIVE,
            )
            
            # Create modal dialog for better visual appeal
            self.preview_modal = ft.AlertDialog(
                title=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=28, color=ft.Colors.GREEN_400),
                            ft.Column([
                                ft.Text("Import Preview", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                                ft.Text(f"Found {len(df)} trades - Review before importing", size=12, color=ft.Colors.GREY_400)
                            ], spacing=2)
                        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
                        ft.Divider(color=ft.Colors.with_opacity(0.2, ft.Colors.WHITE))
                    ], spacing=8, tight=True),
                    padding=20
                ),
                content=ft.Container(
                    content=ft.Column([
                        self.preview_broker_dropdown,
                        ft.Container(
                            content=ft.Column([
                                preview_table
                            ], scroll=ft.ScrollMode.AUTO),
                            expand=True,
                            border=ft.border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),
                            border_radius=8,
                            height=400
                        ),
                        self.preview_status_text,
                        self.preview_progress_bar
                    ], spacing=12, tight=False),
                    width=900,
                    height=500,
                    padding=20
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=self.cancel_import, style=ft.ButtonStyle(color=ft.Colors.GREY_400)),
                    ft.Container(width=8),  # Spacer
                    self.confirm_btn
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                inset_padding=20,
                actions_padding=20
            )
            
            # Show the modal
            if hasattr(self.app_state.page, 'open'):
                self.app_state.page.open(self.preview_modal)
            else:
                self.app_state.page.show_dialog(self.preview_modal)

        except Exception as ex:
            self.show_snack(f"Error reading CSV: {str(ex)}", color=ft.Colors.RED_400)

    def cancel_import(self, e):
        # Close the modal dialog
        if self.preview_modal:
            try:
                if hasattr(self.app_state.page, 'close'):
                    self.app_state.page.close(self.preview_modal)
                else:
                    self.preview_modal.open = False
                    self.preview_modal.update()
            except Exception:
                pass
        object.__setattr__(self, 'pending_import_df', None)

    def _create_dupe_row_slot(self):
        t_date = ft.Text("", size=11, color=ft.Colors.GREY_300)
        t_sym = ft.Text("", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_300)
        t_qty = ft.Text("", size=11, color=ft.Colors.GREY_300, text_align=ft.TextAlign.RIGHT)

        def _cell(ctrl: ft.Control, width: int, numeric: bool = False):
            return ft.Container(
                content=ctrl,
                width=int(width),
                alignment=ft.alignment.Alignment(1, 0) if numeric else ft.alignment.Alignment(-1, 0),
                padding=ft.padding.symmetric(vertical=6, horizontal=8),
            )

        row = ft.Container(
            content=ft.Row(
                controls=[
                    _cell(t_date, self._dupe_col_widths[0], numeric=False),
                    _cell(t_sym, self._dupe_col_widths[1], numeric=False),
                    _cell(t_qty, self._dupe_col_widths[2], numeric=True),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.TRANSPARENT,
        )

        return {'row': row, 't_date': t_date, 't_sym': t_sym, 't_qty': t_qty}

    def _set_skipped_duplicates(self, skipped_details):
        try:
            details = skipped_details or []
            actual_count = len(details)
            while len(self._dupe_row_pool) < actual_count:
                self._dupe_row_pool.append(self._create_dupe_row_slot())

            for i, d in enumerate(details):
                slot = self._dupe_row_pool[i]
                slot['t_date'].value = str(d.get('date', ''))
                slot['t_sym'].value = str(d.get('symbol', ''))
                slot['t_qty'].value = str(d.get('qty', ''))
                slot['row'].bgcolor = ft.Colors.with_opacity(0.04, ft.Colors.WHITE) if i % 2 == 0 else ft.Colors.TRANSPARENT

            self._dupe_list.controls = [self._dupe_row_pool[i]['row'] for i in range(actual_count)]
            try:
                self._dupe_list.update()
            except Exception:
                pass
        except Exception:
            pass

    async def confirm_import(self, e):
        df = getattr(self, 'pending_import_df', None)
        if df is None: return
        
        has_broker_col = 'broker' in df.columns
        selected_broker = self.preview_broker_dropdown.value if not has_broker_col else None
        if not has_broker_col and not selected_broker:
            self.preview_broker_dropdown.error_text = "Please select a broker"
            try:
                self.preview_broker_dropdown.update()  # Targeted update on dropdown only
            except Exception: pass
            return

        self.confirm_btn.disabled = True
        self.preview_progress_bar.visible = True
        self.preview_progress_bar.update()

        import threading
        
        def bg_import():
            """Background import: batch duplicate checks, limit UI updates."""
            total = len(df)
            success = 0
            skipped = 0
            skipped_details = []
            
            # OPTIMIZATION 1: Batch duplicate check - get all existing trade_ids once
            # instead of querying DB for each row
            brokers_in_import = set()
            for row in df.itertuples(index=False):
                rd = row._asdict()
                broker = str(rd['broker']) if has_broker_col else selected_broker
                brokers_in_import.add(broker)
            
            # Pre-load all existing trade_ids for each broker (single query per broker)
            existing_ids = {}
            for broker in brokers_in_import:
                existing_ids[broker] = crud.get_existing_trade_ids(broker)
            
            # OPTIMIZATION 2: Process all trades with O(1) duplicate checks
            # Collect valid trades for batch insert instead of inserting one-by-one
            batch_trades = []
            for i, row in enumerate(df.itertuples(index=False), start=1):
                rd = row._asdict()
                broker = str(rd['broker']) if has_broker_col else selected_broker
                t_id = str(rd.get('trade_id', ''))

                # O(1) lookup instead of DB query per row
                if t_id in existing_ids.get(broker, set()):
                    skipped += 1
                    rd['symbol'] = str(rd.get('symbol', 'UNKNOWN')).upper()
                    rd['date'] = str(rd.get('date', ''))
                    rd['qty'] = str(rd.get('qty', ''))
                    skipped_details.append(rd)
                else:
                    # Calculate fee at import time
                    t_type = str(rd['type']).upper()
                    qty = float(rd['qty'])
                    price = float(rd['price'])
                    fee = calculate_trade_fees(t_type, qty, price, is_delivery=True)

                    batch_trades.append((t_id, broker, str(rd['date']), str(rd['symbol']).upper(), t_type, qty, price, fee))
                    success += 1

                # OPTIMIZATION 3: Update progress less frequently (every 50 trades instead of 5)
                if i % 50 == 0 or i == total:
                    self.preview_progress_bar.value = i/total
                    self.preview_status_text.value = f"Processed {i}/{total} trades..."
                    self.preview_progress_bar.update()

            # OPTIMIZATION: Batch insert all trades in a single transaction
            if batch_trades:
                crud.add_trades_batch(batch_trades)
            
            # Rebuild holdings to update all calculations
            try:
                from flet_app.common.engine import rebuild_holdings
                rebuild_holdings()
            except Exception:
                pass
            
            # CRITICAL: Invalidate all view caches when trades imported
            if hasattr(self.app_state, 'views'):
                try:
                    if self.app_state.views.get(0):  # Dashboard
                        self.app_state.views[0].invalidate_cache()
                except: pass
                try:
                    if self.app_state.views.get(1):  # Holdings
                        self.app_state.views[1].invalidate_cache()
                except: pass
                try:
                    if self.app_state.views.get(3):  # Trade History
                        self.app_state.views[3].invalidate_cache()
                except: pass

            # Refresh in-memory datasets so view switching stays cache-only.
            try:
                self.app_state.refresh_data_cache_async()
            except Exception:
                pass
            
            # Show results on main thread
            async def finish():
                # Close the import modal
                if self.preview_modal:
                    try:
                        if hasattr(self.app_state.page, 'close'):
                            self.app_state.page.close(self.preview_modal)
                        else:
                            self.preview_modal.open = False
                            self.preview_modal.update()
                    except Exception:
                        pass
                
                if skipped > 0:
                    self._set_skipped_duplicates(skipped_details[:30])
                    self.dupe_container.visible = True
                else:
                    self.dupe_container.visible = False

                msg = f"✅ Imported {success} trades."
                if skipped > 0:
                    msg += f" (Skipped {skipped} duplicates)"
                self.show_snack(msg)
            
            self.app_state.page.run_task(finish)
        
        # Run import in background thread
        threading.Thread(target=bg_import, daemon=True).start()