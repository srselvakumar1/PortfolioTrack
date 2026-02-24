import flet as ft
from state import AppState
from components.ui_elements import page_title, premium_card
import models.crud as crud

class SettingsView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True

        self.broker_input = ft.TextField(label="New Broker Name", expand=True)
        self.brokers_list = ft.ListView(expand=True, spacing=10)
        
        self.load_brokers()

        self.content = ft.Column([
            page_title("Settings"),
            premium_card(
                ft.Column([
                    ft.Row([
                        self.broker_input,
                        ft.ElevatedButton(content=ft.Text("Add Broker"), icon=ft.Icons.ADD, on_click=self.add_broker)
                    ]),
                    ft.Divider(),
                    ft.Container(self.brokers_list, height=200)
                ])
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

    def prompt_wipe_data(self, e):
        async def on_confirm(e):
            # Close dialog immediately
            dialog.open = False
            self.app_state.page.update()
            
            # Perform wipe
            crud.wipe_all_data()
            from engine import rebuild_holdings
            rebuild_holdings()
            
            # Show toast
            self.app_state.page.snack_bar = ft.SnackBar(ft.Text("All trades and holdings wiped. Brokers were preserved."), bgcolor=ft.Colors.GREEN_700)
            self.app_state.page.snack_bar.open = True
            
            # Force everything to refresh including sidebar
            self.app_state.refresh_ui()
            self.app_state.sidebar.selected_index = 0
            self.app_state.navigate(0)
            self.app_state.page.update()

        def on_cancel(e):
            dialog.open = False
            self.app_state.page.update()
            if dialog in self.app_state.page.overlay:
                self.app_state.page.overlay.remove(dialog)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.RED), ft.Text("Wipe All Data?")]),
            content=ft.Text("Are you absolutely sure? This will delete ALL trades, market data, and holdings. Brokers are EXCLUDED and will not be deleted."),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton("Yes, Wipe Everything", color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_700, on_click=on_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.app_state.page.overlay.append(dialog)
        dialog.open = True
        self.app_state.page.update()

    def load_brokers(self):
        self.brokers_list.controls.clear()
        brokers = crud.get_all_brokers()
        for b in brokers:
            self.brokers_list.controls.append(
                ft.Row([
                    ft.Text(b, expand=True, size=16),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip=f"Delete {b}", 
                                  icon_color=ft.Colors.RED_400, on_click=lambda e, name=b: self.delete_broker(name))
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
        self.app_state.refresh_ui()

    def add_broker(self, e):
        val = self.broker_input.value.strip()
        if val:
            crud.add_broker(val)
            self.broker_input.value = ""
            self.load_brokers()

    def delete_broker(self, name):
        crud.delete_broker(name)
        self.load_brokers()
