import flet as ft
from state import AppState
from components.ui_elements import page_title, premium_card, show_toast, styled_modal_dialog
import models.crud as crud

class SettingsView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True

        self.broker_input = ft.TextField(
            label="New Broker Name", 
            width=250,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.GREY_900,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400)
        )
        
        # Compact DataTable for brokers
        self.brokers_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Broker Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", weight=ft.FontWeight.BOLD), numeric=False),
            ],
            rows=[],
            column_spacing=20,
        )
        
        self.broker_status = ft.Text("", size=11, color=ft.Colors.GREY_500)

        self.content = ft.Column([
            page_title("Settings"),
            premium_card(
                ft.Column([
                    ft.Text("Broker Management", size=14, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        self.broker_input,
                        ft.ElevatedButton(content=ft.Text("Add Broker"), icon=ft.Icons.ADD, on_click=self.add_broker)
                    ]),
                    self.broker_status,
                    ft.Container(
                        ft.Column([self.brokers_table], scroll=ft.ScrollMode.ALWAYS, expand=True),
                        height=250, 
                        border=ft.border.all(1, ft.Colors.GREY_300), 
                        border_radius=5
                    ),
                ], spacing=12)
            ),
            ft.Text("Danger Zone", size=20, weight=ft.FontWeight.W_600, color=ft.Colors.RED_400),
            premium_card(
                ft.Row([
                    ft.Column([
                        ft.Text("Wipe Portfolio Data", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.RED_400),
                        ft.Text("Permanently deletes all trades, market data, and holdings. Brokers are kept.", size=12, color=ft.Colors.GREY)
                    ], expand=True),
                    ft.ElevatedButton(
                        "Delete All Data", 
                        icon=ft.Icons.DELETE_FOREVER, 
                        color=ft.Colors.WHITE, 
                        bgcolor=ft.Colors.RED_700,
                        on_click=self.prompt_wipe_data
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
        ], spacing=24)

    def _close_dialog(self, dlg=None):
        """Helper to close dialogs consistently"""
        try:
            if dlg:
                dlg.open = False
                dlg.update()
            if hasattr(self.app_state.page, 'close'):
                self.app_state.page.close(dlg)
            elif hasattr(self.app_state.page, 'close_dialog'):
                self.app_state.page.close_dialog()
        except:
            pass

    def did_mount(self):
        """Load brokers when view is mounted"""
        self.load_data()

    def prompt_wipe_data(self, e):
        def on_confirm(e):
            self._close_dialog(dialog)
            
            # Perform wipe
            crud.wipe_all_data()
            from engine import rebuild_holdings
            rebuild_holdings()
            
            # CRITICAL: Invalidate all view caches when data wiped
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
                    if self.app_state.views.get(2):  # TradeEntry 
                        pass  # TradeEntry doesn't have cache, just data
                except: pass
                try:
                    if self.app_state.views.get(3):  # Trade History
                        self.app_state.views[3].invalidate_cache()
                except: pass
            
            # Show toast
            show_toast(self.app_state.page, "All trades and holdings wiped. Brokers preserved ✓", color=ft.Colors.GREEN_600)
            
            # Force everything to refresh
            self.app_state.refresh_ui()
            self.app_state.sidebar.selected_index = 0
            self.app_state.navigate(0)

        dialog = styled_modal_dialog(
            title="Wipe All Data",
            content=ft.Text("Are you absolutely sure? This will delete ALL trades, market data, and holdings.\n\nBrokers are EXCLUDED and will not be deleted.", color=ft.Colors.WHITE),
            confirm_text="Yes, Wipe Everything",
            cancel_text="Cancel",
            on_confirm=on_confirm,
            on_cancel=lambda _: self._close_dialog(dialog),
            is_dangerous=True
        )
        self.app_state.page.show_dialog(dialog)

    def load_data(self):
        """Load brokers into the compact DataTable"""
        self.brokers_table.rows.clear()
        brokers = crud.get_all_brokers()
        
        for broker_name in brokers:
            self.brokers_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(broker_name, size=12)),
                    ft.DataCell(
                        ft.Row([
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE, 
                                tooltip=f"Delete {broker_name}", 
                                icon_size=18,
                                icon_color=ft.Colors.RED_400, 
                                on_click=lambda e, name=broker_name: self.delete_broker(name)
                            )
                        ], spacing=0)
                    )
                ])
            )
        
        # Update table with new rows
        try:
            self.brokers_table.update()
        except Exception:
            pass

    def _refresh_broker_filters(self):
        """Refresh broker filters in other views after broker changes"""
        try:
            # Reload broker options in Holdings view if it exists
            if hasattr(self.app_state, 'views') and self.app_state.views.get(1):
                holdings_view = self.app_state.views[1]
                if hasattr(holdings_view, '_load_broker_options'):
                    holdings_view._load_broker_options()
            
            # Reload broker options in Trade History view if it exists
            if hasattr(self.app_state, 'views') and self.app_state.views.get(2):
                tradehistory_view = self.app_state.views[2]
                if hasattr(tradehistory_view, '_load_broker_options'):
                    tradehistory_view._load_broker_options()
        except Exception:
            pass  # Silently fail if views aren't initialized yet

    def add_broker(self, e):
        """Add a new broker with validation and error handling"""
        val = self.broker_input.value.strip().upper() if self.broker_input.value else ""
        
        if not val:
            show_toast(self.app_state.page, "Please enter a broker name", color=ft.Colors.ORANGE_700)
            return
        
        # Check if broker already exists (case-insensitive comparison)
        existing_brokers = crud.get_all_brokers()
        existing_brokers_upper = [b.upper() for b in existing_brokers]
        if val in existing_brokers_upper:
            show_toast(self.app_state.page, f"Broker '{val}' already exists", color=ft.Colors.RED_600)
            return
        
        # Add broker
        try:
            crud.add_broker(val)
            self.broker_input.value = ""
            self.load_data()
            self._refresh_broker_filters()  # Refresh brokers in other views
            show_toast(self.app_state.page, f"Broker '{val}' added ✓", color=ft.Colors.GREEN_600)
            try:
                self.broker_input.update()
            except Exception:
                pass
        except Exception as ex:
            show_toast(self.app_state.page, f"Error: {str(ex)}", color=ft.Colors.RED_600)

    def delete_broker(self, name):
        """Delete a broker with confirmation dialog and reload the table"""
        def do_delete(e):
            try:
                crud.delete_broker(name)
                self.load_data()
                self._refresh_broker_filters()  # Refresh brokers in other views
                
                # CRITICAL: Invalidate all view caches when broker deleted
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
                
                show_toast(self.app_state.page, f"Broker '{name}' deleted ✓", color=ft.Colors.GREEN_600)
            except Exception as ex:
                show_toast(self.app_state.page, f"Error deleting broker: {str(ex)}", color=ft.Colors.RED_600)
            self._close_dialog(dlg)
        
        dlg = styled_modal_dialog(
            title="Delete Broker",
            content=ft.Text(f"Delete '{name}' broker?\n\nEnsure no active trades use this broker.", color=ft.Colors.WHITE),
            confirm_text="Delete",
            cancel_text="Cancel",
            on_confirm=do_delete,
            on_cancel=lambda _: self._close_dialog(dlg),
            is_dangerous=True
        )
        self.app_state.page.show_dialog(dlg)
