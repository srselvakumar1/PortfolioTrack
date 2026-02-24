import flet as ft
from state import AppState
from components.ui_elements import page_title, premium_card, info_metric, status_chip
from engine import get_dashboard_metrics, get_metrics_by_broker, get_top_worst_performers, get_actionable_insights, get_tax_harvesting_opportunities, fetch_and_update_market_data
from database import get_connection
import threading

class DashboardView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True
        
        self.val_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.inv_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.pnl_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.unrealized_pnl_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.realized_pnl_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.realized_loss_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.xirr_text = ft.Text("0.00%", size=24, weight=ft.FontWeight.BOLD)
        self.refresh_progress = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)
        
        self.content_col = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=24)
        
        # Backdrop (Clickable background to hide overlay)
        self.backdrop = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.4, ft.Colors.BLACK),
            on_click=self.hide_broker_drilldown,
            visible=False,
            expand=True
        )

        # Popover Content
        self.popover_container = ft.Container(
            visible=False,
            animate_opacity=300,
            shadow=ft.BoxShadow(blur_radius=25, color=ft.Colors.with_opacity(0.8, ft.Colors.BLACK)),
        )

        self.content = ft.Stack([
            ft.Container(content=self.content_col, padding=0),
            self.backdrop,
            self.popover_container,
        ], expand=True)

    def show_drilldown(self, symbol):
        from components.drilldown import show_drilldown_dialog
        show_drilldown_dialog(self.app_state, symbol)

    def hide_broker_drilldown(self, e):
        self.popover_container.visible = False
        self.backdrop.visible = False
        self.update()

    def show_broker_breakdown_dialog(self, title: str, metric_key: str, is_currency: bool = True, top_pos: int = 150):
        broker_metrics = get_metrics_by_broker()
        
        rows = []
        for broker, metrics in broker_metrics.items():
            val = metrics.get(metric_key, 0.0)
            val_str = f"₹{val:,.2f}" if is_currency else f"{val:,.2f}%"
                
            color = ft.Colors.WHITE
            if "pnl" in metric_key or "xirr" in metric_key:
                color = ft.Colors.GREEN if val >= 0 else ft.Colors.RED
            if "loss" in metric_key:
                color = ft.Colors.RED
                
            rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(broker, weight=ft.FontWeight.W_500)),
                    ft.DataCell(ft.Text(val_str, color=color, weight=ft.FontWeight.W_600))
                ])
            )
            
        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Broker", color=ft.Colors.GREY)),
                ft.DataColumn(ft.Text("Value", color=ft.Colors.GREY), numeric=True)
            ],
            rows=rows,
            border=ft.border.all(1, "#2A2A2A"),
            border_radius=8,
            horizontal_margin=20,
            column_spacing=60
        )

        # Build Popover UI
        popover = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"{title} by Broker", size=18, weight=ft.FontWeight.BOLD),
                    ft.IconButton(ft.Icons.CLOSE, on_click=self.hide_broker_drilldown, icon_size=18)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=1, color="#2A2A2A"),
                table
            ], tight=True, spacing=15),
            bgcolor="#1A1A1A",
            padding=20,
            border_radius=12,
            border=ft.border.all(1, "#333333"),
            width=360,
        )

        # Position the popover over the card area
        self.popover_container.content = popover
        self.popover_container.top = top_pos
        self.popover_container.left = 180 # Offset to center over cards roughly
        
        self.popover_container.visible = True
        self.backdrop.visible = True
        self.update()

    def load_metrics(self):
        # FIX: Construct all logic first, then update UI on main thread to prevent RuntimeError
        metrics = get_dashboard_metrics()
        performers = get_top_worst_performers(limit=3)
        insights = get_actionable_insights()
        harvesting = get_tax_harvesting_opportunities(min_loss_amount=500.0)

        async def _update_ui():
            self.val_text.value = f"₹{metrics['total_value']:,.2f}"
            self.inv_text.value = f"₹{metrics['total_invested']:,.2f}"
            
            pnl = metrics['overall_pnl']
            self.pnl_text.value = f"₹{pnl:,.2f}"
            self.pnl_text.color = ft.Colors.GREEN if pnl >= 0 else ft.Colors.RED
            
            upnl = metrics['unrealized_pnl']
            self.unrealized_pnl_text.value = f"₹{upnl:,.2f}"
            self.unrealized_pnl_text.color = ft.Colors.GREEN if upnl >= 0 else ft.Colors.RED
            
            rpnl = metrics['realized_pnl']
            self.realized_pnl_text.value = f"₹{rpnl:,.2f}"
            self.realized_pnl_text.color = ft.Colors.GREEN if rpnl >= 0 else ft.Colors.RED
            
            rloss = metrics['realized_loss']
            self.realized_loss_text.value = f"₹{rloss:,.2f}"
            self.realized_loss_text.color = ft.Colors.RED 
            
            xirr = metrics['overall_xirr']
            self.xirr_text.value = f"{xirr:,.2f}%"
            self.xirr_text.color = ft.Colors.GREEN if xirr >= 0 else ft.Colors.RED

            self.content_col.controls = [
                ft.Row([
                    page_title("Dashboard"),
                    ft.Row([
                        self.refresh_progress,
                        ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh Market Data", on_click=self.on_refresh_data, icon_color=ft.Colors.WHITE)
                    ], alignment=ft.MainAxisAlignment.END)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                # Row 1: Core Metrics 1
                ft.Row([
                    premium_card(
                        info_metric("Total Value", self.val_text, ft.Icons.ACCOUNT_BALANCE_WALLET), 
                        expand=True, 
                        on_click=lambda _: self.show_broker_breakdown_dialog("Total Value", "total_value", top_pos=100)
                    ),
                    premium_card(
                        info_metric("Total Invested", self.inv_text, ft.Icons.ACCOUNT_BALANCE), 
                        expand=True,
                        on_click=lambda _: self.show_broker_breakdown_dialog("Total Invested", "total_invested", top_pos=100)
                    ),
                    premium_card(
                        info_metric("Overall P&L", self.pnl_text, ft.Icons.TRENDING_UP), 
                        expand=True,
                        on_click=lambda _: self.show_broker_breakdown_dialog("Overall P&L", "overall_pnl", top_pos=100)
                    ),
                ]),
                # Row 1b: Core Metrics 2
                ft.Row([
                    premium_card(
                        info_metric("Unrealized P&L", self.unrealized_pnl_text, ft.Icons.SHOW_CHART), 
                        expand=True,
                        on_click=lambda _: self.show_broker_breakdown_dialog("Unrealized P&L", "unrealized_pnl", top_pos=260)
                    ),
                    premium_card(
                        info_metric("Realized P&L", self.realized_pnl_text, ft.Icons.MONETIZATION_ON), 
                        expand=True,
                        on_click=lambda _: self.show_broker_breakdown_dialog("Realized P&L", "realized_pnl", top_pos=260)
                    ),
                    premium_card(
                        info_metric("Realized Loss", self.realized_loss_text, ft.Icons.MONEY_OFF), 
                        expand=True,
                        on_click=lambda _: self.show_broker_breakdown_dialog("Realized Loss", "realized_loss", top_pos=260)
                    ),
                    premium_card(
                        info_metric("Overall XIRR", self.xirr_text, ft.Icons.PERCENT), 
                        expand=True,
                        on_click=lambda _: self.show_broker_breakdown_dialog("Overall XIRR", "overall_xirr", is_currency=False, top_pos=260)
                    ),
                ]),
                # Row 2: Top / Worst
                ft.Row([
                    premium_card(self.build_performers_list("Top Performers", performers["top"], is_top=True), expand=True),
                    premium_card(self.build_performers_list("Worst Performers", performers["worst"], is_top=False), expand=True),
                ], alignment=ft.MainAxisAlignment.START),
                # Row 3: Insights / Tax
                ft.Row([
                    premium_card(self.build_insights_list("Actionable Insights", insights), expand=True),
                    premium_card(self.build_harvesting_list("Tax Harvesting Ops", harvesting), expand=True),
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=40)
            ]
            self.update()

        self.app_state.page.run_task(_update_ui)


    def build_performers_list(self, title, data, is_top):
        color = ft.Colors.GREEN if is_top else ft.Colors.RED
        icon = ft.Icons.ARROW_UPWARD if is_top else ft.Icons.ARROW_DOWNWARD

        rows = [ft.Text(title, size=18, weight=ft.FontWeight.BOLD)]
        if not data:
            rows.append(ft.Text("No data available.", italic=True, color=ft.Colors.GREY))
        for item in data:
            rows.append(
                ft.Row([
                    ft.Container(
                        content=ft.Text(item["symbol"], weight=ft.FontWeight.W_600, color=ft.Colors.BLUE_300),
                        on_click=lambda e, sym=item["symbol"]: self.show_drilldown(sym),
                        tooltip="View Details",
                        expand=True
                    ),
                    ft.Text(f"₹{item['pnl']:,.2f}", color=color),
                    ft.Icon(icon, size=14, color=color)
                ])
            )
            rows.append(ft.Divider(height=1, color="#2A2A2A"))
        if data:
            rows.pop() # Remove last divider
            
        return ft.Column(rows, spacing=10)

    def build_insights_list(self, title, data):
        rows = [ft.Text(title, size=18, weight=ft.FontWeight.BOLD)]
        if not data:
            rows.append(ft.Text("No active signals right now.", italic=True, color=ft.Colors.GREY))
        for item in data:
            sig_color = ft.Colors.GREEN if item["signal"] == "ACCUMULATE" else ft.Colors.RED
            rows.append(
                ft.Row([
                    ft.Container(
                        content=ft.Text(item["symbol"], size=18, weight=ft.FontWeight.W_700, color=ft.Colors.BLUE_300),
                        on_click=lambda e, sym=item["symbol"]: self.show_drilldown(sym),
                        tooltip="View Details",
                        expand=True
                    ),
                    ft.Text(f"₹{item['current_price']:,.2f}", size=15, color=ft.Colors.GREY),
                    status_chip(item["signal"], sig_color)
                ])
            )
            rows.append(ft.Divider(height=1, color="#2A2A2A"))
        if data:
            rows.pop()
        return ft.Column(rows, spacing=10)

    def build_harvesting_list(self, title, data):
        rows = [
            ft.Row([
                ft.Text(title, size=18, weight=ft.FontWeight.BOLD),
                 ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.GREY, tooltip="Positions with significant unrealized loss.")
            ])
        ]
        if not data:
            rows.append(ft.Text("No tax harvesting opportunities.", italic=True, color=ft.Colors.GREY))
        for item in data[:5]: # Show top 5
            rows.append(
                ft.Row([
                    ft.Column([
                        ft.Container(
                            content=ft.Text(item["symbol"], size=18, weight=ft.FontWeight.W_700, color=ft.Colors.BLUE_300),
                            on_click=lambda e, sym=item["symbol"]: self.show_drilldown(sym),
                            tooltip="View Details"
                        ),
                        ft.Text(item["broker"], size=13, color=ft.Colors.GREY),
                    ], spacing=2, expand=True),
                    ft.Column([
                        ft.Text(f"Loss: ₹{item['unrealized_loss']:,.2f}", size=15, color=ft.Colors.RED, weight=ft.FontWeight.W_600),
                        ft.Text(f"Qty: {item['qty']} @ ₹{item['avg_price']:.2f}", size=13, color=ft.Colors.GREY)
                    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END)
                ])
            )
            rows.append(ft.Divider(height=1, color="#2A2A2A"))
        if data:
            rows.pop()
        return ft.Column(rows, spacing=10)

    def on_refresh_data(self, e):
        # Prevent multiple clicks
        if self.refresh_progress.visible: return
        
        self.refresh_progress.visible = True
        self.update()
        
        # Get all distinct symbols from holdings
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM holdings WHERE qty > 0")
        symbols = [r[0] for r in cursor.fetchall()]

        def fetch_wrapper():
            if symbols:
                fetch_and_update_market_data(symbols)
            # Update UI back on main thread
            self.app_state.page.run_task(self.finish_refresh)
            
        threading.Thread(target=fetch_wrapper, daemon=True).start()

    async def finish_refresh(self):
        self.refresh_progress.visible = False
        self.load_metrics() # this calls self.update() internally
