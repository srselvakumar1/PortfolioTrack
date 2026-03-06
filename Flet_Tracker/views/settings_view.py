import flet as ft
from flet_app.common.state import AppState
from flet_app.components.ui_elements import page_title, premium_card, show_toast, styled_modal_dialog
import flet_app.common.models.crud as crud

class SettingsView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True
        self._data_loaded = False
        self._needs_reload = True

        self.broker_input = ft.TextField(
            label="New Broker Name", 
            width=250,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.GREY_900,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400)
        )
        
        # Fast grid: fixed-width header + ListView rows (faster than DataTable)
        self._broker_col_widths = [220, 90]

        def _hdr_cell(text: str, width: int, center: bool = False):
            return ft.Container(
                content=ft.Text(text, weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                width=int(width),
                alignment=ft.alignment.Alignment(0, 0) if center else ft.alignment.Alignment(-1, 0),
                padding=ft.padding.symmetric(vertical=8, horizontal=10),
            )

        self._brokers_header = ft.Container(
            content=ft.Row(
                controls=[
                    _hdr_cell("Broker Name", self._broker_col_widths[0]),
                    _hdr_cell("Actions", self._broker_col_widths[1], center=True),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_400),
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE))),
        )

        self._brokers_list = ft.ListView(expand=True, spacing=0, padding=0)
        self._broker_row_pool = []
        
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
                        ft.Column([self._brokers_header, self._brokers_list], spacing=0, scroll=ft.ScrollMode.ALWAYS, expand=True),
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
        if not self._data_loaded or self._needs_reload:
            self.load_data()

    def invalidate_cache(self):
        """Mark this view's broker list as stale (reload on next mount)."""
        self._needs_reload = True

    def prompt_wipe_data(self, e):
        def on_confirm(e):
            self._close_dialog(dialog)

            # Run wipe in background to avoid UI freeze
            def _do_wipe():
                crud.wipe_all_data()

                async def _finish_wipe():
                    # Refresh in-memory datasets so view switching stays cache-only.
                    try:
                        self.app_state.refresh_data_cache()
                    except Exception:
                        pass

                    # Invalidate all view caches
                    if hasattr(self.app_state, 'views'):
                        for idx in (0, 1, 3):
                            try:
                                v = self.app_state.views.get(idx)
                                if v and hasattr(v, 'invalidate_cache'):
                                    v.invalidate_cache()
                            except Exception:
                                pass

                    show_toast(self.app_state.page, "All trades and holdings wiped. Brokers preserved", color=ft.Colors.GREEN_600)
                    self.app_state.sidebar.selected_index = 0
                    self.app_state.navigate(0)

                self.app_state.page.run_task(_finish_wipe)

            import threading
            threading.Thread(target=_do_wipe, daemon=True).start()

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
        """Load brokers into the brokers list."""
        try:
            brokers = self.app_state.get_brokers_cached(force_refresh=False)
        except Exception:
            brokers = crud.get_all_brokers()

        actual_count = len(brokers)
        while len(self._broker_row_pool) < actual_count:
            self._broker_row_pool.append(self._create_broker_row_slot())

        for i, broker_name in enumerate(brokers):
            slot = self._broker_row_pool[i]
            slot['name'].value = str(broker_name)
            slot['btn_del'].tooltip = f"Delete {broker_name}"
            slot['btn_del'].on_click = lambda e, name=broker_name: self.delete_broker(name)
            slot['row'].bgcolor = ft.Colors.with_opacity(0.04, ft.Colors.WHITE) if i % 2 == 0 else ft.Colors.TRANSPARENT

        self._brokers_list.controls = [self._broker_row_pool[i]['row'] for i in range(actual_count)]
        try:
            self._brokers_list.update()
        except Exception:
            pass

        self._data_loaded = True
        self._needs_reload = False

    def _create_broker_row_slot(self):
        name = ft.Text("", size=12, color=ft.Colors.WHITE)
        btn_del = ft.IconButton(
            ft.Icons.DELETE_OUTLINE,
            tooltip="Delete",
            icon_size=18,
            icon_color=ft.Colors.RED_400,
        )

        def _cell(ctrl: ft.Control, width: int, center: bool = False):
            return ft.Container(
                content=ctrl,
                width=int(width),
                alignment=ft.alignment.Alignment(0, 0) if center else ft.alignment.Alignment(-1, 0),
                padding=ft.padding.symmetric(vertical=8, horizontal=10),
            )

        row = ft.Container(
            content=ft.Row(
                controls=[
                    _cell(name, self._broker_col_widths[0], center=False),
                    _cell(ft.Row([btn_del], spacing=0), self._broker_col_widths[1], center=True),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.TRANSPARENT,
        )

        return {'row': row, 'name': name, 'btn_del': btn_del}

    def _refresh_broker_filters(self):
        """Refresh broker filters in other views after broker changes"""
        try:
            # Reload broker options in Holdings view if it exists
            if hasattr(self.app_state, 'views') and self.app_state.views.get(1):
                holdings_view = self.app_state.views[1]
                if hasattr(holdings_view, '_load_broker_options'):
                    holdings_view._load_broker_options()
            
            # Reload broker options in Trade History view if it exists
            if hasattr(self.app_state, 'views') and self.app_state.views.get(3):
                tradehistory_view = self.app_state.views[3]
                if hasattr(tradehistory_view, '_load_broker_options'):
                    tradehistory_view._load_broker_options()

            # Trade Entry broker dropdown (reload on next visit)
            if hasattr(self.app_state, 'views') and self.app_state.views.get(2):
                trade_entry_view = self.app_state.views[2]
                if hasattr(trade_entry_view, 'invalidate_cache'):
                    trade_entry_view.invalidate_cache()
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

            # Refresh cached broker list immediately
            try:
                self.app_state.get_brokers_cached(force_refresh=True)
            except Exception:
                pass

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

                # Refresh cached broker list immediately
                try:
                    self.app_state.get_brokers_cached(force_refresh=True)
                except Exception:
                    pass

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
