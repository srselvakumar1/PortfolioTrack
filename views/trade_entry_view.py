import flet as ft
import pandas as pd
import os
from state import AppState
from components.ui_elements import page_title, premium_card
import models.crud as crud
import engine
from engine import calculate_trade_fees, rebuild_holdings

class TradeEntryView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True
        self.alignment = ft.alignment.Alignment(-1.0, -1.0)
        object.__setattr__(self, 'pending_import_df', None)

        # FilePicker is a Service — must go in page.services, NOT page.overlay.
        # Flutter only registers invocable services from this list.
        self.import_picker = ft.FilePicker()
        self.app_state.page.services.append(self.import_picker)

        self.broker_dropdown = ft.Dropdown(label="Broker", expand=True)
        self.date_picker = ft.TextField(label="Date (YYYY-MM-DD)", value="2024-01-01", expand=True) # Could use real DatePicker
        self.symbol_input = ft.TextField(label="Symbol (e.g. RELIANCE)", expand=True)
        self.type_radio = ft.RadioGroup(
            ft.Row([
                ft.Radio(value="BUY",  label="  BUY"),
                ft.Radio(value="SELL", label="  SELL"),
            ], spacing=20)
        )
        self.type_radio.value = "BUY"
        self.qty_input = ft.TextField(label="Quantity", expand=True)
        self.price_input = ft.TextField(label="Price (₹)", expand=True)
        
        self.calculated_fee_text = ft.Text("Estimated Fee: ₹0.00", color="#AAAAAA")

        # Triggers auto-fee calc
        self.qty_input.on_change = self.update_fees
        self.price_input.on_change = self.update_fees
        self.type_radio.on_change = self.update_fees

        self.load_brokers()

        self.preview_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Preview Trades"),
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.content = ft.Column([
            page_title("Trade Entry"),
            ft.Row([
                premium_card(
                    ft.Column([
                        ft.Text("Manual Entry", size=20, weight=ft.FontWeight.W_600),
                        ft.Row([self.broker_dropdown, self.date_picker]),
                        ft.Row([self.symbol_input]),
                        ft.Row([
                            ft.Text("Type:", size=13, color="#AAAAAA", width=40),
                            self.type_radio,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Row([self.qty_input, self.price_input]),
                        ft.Row([self.calculated_fee_text, ft.Container(expand=True), ft.ElevatedButton(content=ft.Text("Save Trade"), on_click=self.save_trade, icon=ft.Icons.SAVE)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=20),
                    expand=True
                )
            ]),
            # Stub for CSV upload
            premium_card(
                ft.Column([
                    ft.Text("Bulk Import (CSV)", size=20, weight=ft.FontWeight.W_600),
                    ft.Text("Expected Columns: broker, date, symbol, type, qty, price", color=ft.Colors.GREY_500, size=12),
                    ft.ElevatedButton(content=ft.Text("Select CSV File"), icon=ft.Icons.UPLOAD_FILE, on_click=self.handle_import_click)
                ])
            )
        ], spacing=24, scroll=ft.ScrollMode.AUTO)

    def did_unmount(self):
        """Clean up services when navigating away to prevent Flet control leaks."""
        try:
            if self.import_picker in self.app_state.page.services:
                self.app_state.page.services.remove(self.import_picker)
            self.app_state.page.update()
        except Exception:
            pass

    def load_brokers(self):
        brokers = crud.get_all_brokers()
        self.broker_dropdown.options = [ft.dropdown.Option(b) for b in brokers]
        if brokers:
            self.broker_dropdown.value = brokers[0]

    def update_fees(self, e):
        qty_str = self.qty_input.value or "0"
        price_str = self.price_input.value or "0"
        t_type = self.type_radio.value or "BUY"
        try:
            qty = float(qty_str)
            price = float(price_str)
            # Standardizing all manual trades to delivery per prompt instructions logic
            fee = calculate_trade_fees(t_type, qty, price, is_delivery=True)
            self.calculated_fee_text.value = f"Estimated Fee: ₹{fee:,.2f}"
        except ValueError:
            self.calculated_fee_text.value = "Estimated Fee: ₹0.00"
        self.app_state.refresh_ui()

    def save_trade(self, e):
        try:
            broker = self.broker_dropdown.value
            date = self.date_picker.value
            symbol = self.symbol_input.value.strip().upper()
            t_type = self.type_radio.value
            qty = float(self.qty_input.value)
            price = float(self.price_input.value)
            fee = calculate_trade_fees(t_type, qty, price, is_delivery=True)

            if not all([broker, date, symbol, t_type, qty > 0, price > 0]):
                raise ValueError("Missing/Invalid fields")

            crud.add_trade(broker, date, symbol, t_type, qty, price, fee)
            rebuild_holdings()
            
            self.update_fees(None)
            
            # Simple snackbar
            self.app_state.page.snack_bar = ft.SnackBar(ft.Text("Trade saved successfully!"))
            self.app_state.page.snack_bar.open = True
            self.app_state.refresh_ui()
            
        except Exception as ex:
            self.app_state.page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}", color=ft.Colors.RED_400))
            self.app_state.page.snack_bar.open = True
            self.app_state.refresh_ui()

    async def handle_import_click(self, _):
        """Flet 0.80.5: pick_files() is async and returns files directly.
        Picker was already registered at view init time, so Flutter knows about it."""
        files = await self.import_picker.pick_files(
            allowed_extensions=["csv"], allow_multiple=False
        )
        if not files:
            return

        file_path = files[0].path
        self.app_state.page.snack_bar = ft.SnackBar(ft.Text(f"Loading {os.path.basename(file_path)}..."))
        self.app_state.page.snack_bar.open = True
        self.app_state.page.update()

        try:
            df = None
            for enc in ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, encoding=enc)
                    break
                except Exception:
                    pass
            if df is None:
                raise ValueError("Could not read CSV with common encodings.")

            df.columns = [c.lower().strip() for c in df.columns]
            col_map = {'trade_date': 'date', 'trade_type': 'type', 'quantity': 'qty'}
            df.rename(columns=col_map, inplace=True)

            required = ['date', 'symbol', 'type', 'qty', 'price']
            missing = [col for col in required if col not in df.columns]
            if missing:
                raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

            has_broker = 'broker' in df.columns
            object.__setattr__(self, 'pending_import_df', df)

            preview_rows = []
            for i, (_, row) in enumerate(df.iterrows(), start=1):
                preview_rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(i), color=ft.Colors.GREY_500)),
                    ft.DataCell(ft.Text(str(row['date']))),
                    ft.DataCell(ft.Text(str(row['symbol']).upper(), weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(str(row['type']).upper(),
                                       color=ft.Colors.GREEN if str(row['type']).upper() == 'BUY' else ft.Colors.RED)),
                    ft.DataCell(ft.Text(str(row['qty']))),
                    ft.DataCell(ft.Text(str(row['price']))),
                ]))

            preview_table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("#")),
                    ft.DataColumn(ft.Text("Date")),
                    ft.DataColumn(ft.Text("Symbol")),
                    ft.DataColumn(ft.Text("Type")),
                    ft.DataColumn(ft.Text("Qty")),
                    ft.DataColumn(ft.Text("Price")),
                ],
                rows=preview_rows
            )

            brokers = crud.get_all_brokers()
            self.preview_broker_dropdown = ft.Dropdown(
                label="Select Broker for these trades*",
                options=[ft.dropdown.Option(b) for b in brokers],
                value=None, # Require explicit selection
                visible=not has_broker
            )

            self.preview_dialog.content = ft.Column([
                ft.Text(f"Found {len(df)} trades. All rows shown below:"),
                self.preview_broker_dropdown,
                ft.Container(
                    content=ft.Row([preview_table], scroll=ft.ScrollMode.ADAPTIVE),
                    height=350,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                )
            ], scroll=ft.ScrollMode.AUTO, tight=True, width=720)

            self.preview_dialog.actions = [
                ft.TextButton("Cancel", on_click=self.cancel_import),
                ft.ElevatedButton("Confirm Import", on_click=self.confirm_import, bgcolor=ft.Colors.GREEN_600)
            ]

            self.app_state.page.show_dialog(self.preview_dialog)

        except Exception as ex:
            import traceback; traceback.print_exc()
            self.app_state.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error reading CSV: {str(ex)}"),
                bgcolor=ft.Colors.RED_400
            )
            self.app_state.page.snack_bar.open = True
            self.app_state.page.update()

    def cancel_import(self, e):
        self.app_state.page.pop_dialog()
        object.__setattr__(self, 'pending_import_df', None)

    def confirm_import(self, e):
        if hasattr(self, 'pending_import_df') and self.pending_import_df is not None:
            df = self.pending_import_df
            success_count = 0
            has_broker_col = 'broker' in df.columns
            
            selected_broker = None
            if not has_broker_col:
                selected_broker = self.preview_broker_dropdown.value
                if not selected_broker:
                    # Show error without popping dialog
                    self.app_state.page.snack_bar = ft.SnackBar(
                        ft.Text("You must select a Broker to import trades."), 
                        bgcolor=ft.Colors.RED_700
                    )
                    self.app_state.page.snack_bar.open = True
                    self.app_state.page.update()
                    return

            # Validation passed, close dialog
            self.app_state.page.pop_dialog()

            for _, row in df.iterrows():
                try:
                    broker = str(row['broker']) if has_broker_col else selected_broker
                    date_val = str(row['date']).split(' ')[0]
                    symbol = str(row['symbol']).strip().upper()
                    t_type = str(row['type']).strip().upper()
                    
                    if 'BUY' in t_type: t_type = 'BUY'
                    elif 'SELL' in t_type: t_type = 'SELL'
                    
                    qty = float(row['qty'])
                    price = float(row['price'])
                    
                    if qty <= 0 or price <= 0: continue
                    
                    fee = engine.calculate_trade_fees(t_type, qty, price, is_delivery=True)
                    crud.add_trade(broker, date_val, symbol, t_type, qty, price, fee)
                    success_count += 1
                except Exception as row_ex:
                    print(f"Skipping row error: {row_ex}")
                    continue
                    
            engine.rebuild_holdings()
            
            self.app_state.page.snack_bar = ft.SnackBar(ft.Text(f"Successfully imported {success_count} trades!"))
            self.app_state.page.snack_bar.open = True
            self.app_state.refresh_ui()
            object.__setattr__(self, 'pending_import_df', None)
