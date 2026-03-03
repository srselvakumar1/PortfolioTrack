import flet as ft
from state import AppState
from components.ui_elements import page_title, premium_card, info_metric, status_chip, dashboard_breakdown_header, dashboard_broker_stats, dashboard_broker_row_item
from engine import get_dashboard_metrics, get_metrics_by_broker, get_top_worst_performers, get_actionable_insights, get_tax_harvesting_opportunities, fetch_and_update_market_data
from database import db_session
import threading
import concurrent.futures

class DashboardView(ft.Container):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.expand = True
        self.alignment = ft.alignment.Alignment(-1.0, -1.0)
        
        self.val_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.inv_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.pnl_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.unrealized_pnl_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.realized_pnl_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.realized_loss_text = ft.Text("₹0.00", size=24, weight=ft.FontWeight.BOLD)
        self.xirr_text = ft.Text("0.00%", size=24, weight=ft.FontWeight.BOLD)
        self.cagr_text = ft.Text("0.00%", size=24, weight=ft.FontWeight.BOLD)
        self.refresh_progress = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)
        
        # Caching: Store whether we've already loaded data on first visit
        self._data_loaded = False
        
        # Cached UI sections (built once, updated only values in load_data)
        self.header_row = None
        self.kpi_row_1 = None
        self.kpi_row_2 = None
        self.performers_row = None
        self.insights_row = None
        self._ui_built = False
        
        # Enforce alignment strictly to the top
        self.content_col = ft.Column(
            scroll=ft.ScrollMode.AUTO, 
            spacing=24,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            controls=[]
        )
        
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
            ft.Container(content=self.content_col, padding=0, alignment=ft.alignment.Alignment(-1.0, -1.0)),
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
        
        # Prepare broker data for display
        broker_data = []
        total_value = 0.0
        for broker, metrics in broker_metrics.items():
            val = metrics.get(metric_key, 0.0)
            broker_data.append({"broker": broker, "value": val})
            total_value += val
        
        # Determine icon based on metric_key
        icon_map = {
            "total_value": ft.Icons.ACCOUNT_BALANCE_WALLET,
            "total_invested": ft.Icons.ACCOUNT_BALANCE,
            "overall_pnl": ft.Icons.TRENDING_UP,
            "unrealized_pnl": ft.Icons.SHOW_CHART,
            "realized_pnl": ft.Icons.MONETIZATION_ON,
            "realized_loss": ft.Icons.MONEY_OFF,
            "overall_xirr": ft.Icons.AUTO_GRAPH,
            "overall_cagr": ft.Icons.PERCENT,
        }
        icon = icon_map.get(metric_key, ft.Icons.INFO)

        # Build breakdown items using helper function
        breakdown_items = []
        for item in broker_data:
            breakdown_items.append(
                dashboard_broker_row_item(item["broker"], item["value"], is_currency)
            )

        popover = ft.Container(
            content=ft.Column([
                dashboard_breakdown_header(title, icon, total_value, is_currency),
                ft.Divider(height=12, color="#334155"),
                dashboard_broker_stats(broker_data),
                ft.Divider(height=12, color="#334155"),
                ft.Text("Broker Details", size=12, weight=ft.FontWeight.BOLD, color="#3B82F6"),
                ft.Column(breakdown_items, spacing=8),
                ft.Row([
                    ft.IconButton(ft.Icons.CLOSE, on_click=self.hide_broker_drilldown, icon_size=18)
                ], alignment=ft.MainAxisAlignment.END)
            ], tight=True, spacing=8),
            bgcolor="#1A2A3A",
            padding=15,
            border_radius=10,
            border=ft.border.all(1, "#334155"),
            width=400,
        )

        self.popover_container.content = popover
        self.popover_container.top = top_pos
        self.popover_container.left = 180 
        
        self.popover_container.visible = True
        self.backdrop.visible = True
        self.update()

    def load_data(self):
        # OPTIMIZATION: Only load on first visit - don't reload on every navigation
        if self._data_loaded:
            return
        self._data_loaded = True
        # Spawn background thread so the UI thread is never blocked waiting for DB queries.
        # All 4 queries run concurrently inside the thread; UI updates dispatched back via
        # page.run_task() once data is ready.
        threading.Thread(target=self._fetch_and_render, daemon=True).start()

    def _fetch_and_render(self):
        """Background thread: fetch all dashboard data concurrently, then update UI."""
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                f_metrics    = ex.submit(get_dashboard_metrics)
                f_performers = ex.submit(get_top_worst_performers, 3)
                f_insights   = ex.submit(get_actionable_insights)
                f_harvesting = ex.submit(get_tax_harvesting_opportunities, 500.0)
                metrics    = f_metrics.result()
                performers = f_performers.result()
                insights   = f_insights.result()
                harvesting = f_harvesting.result()
        except Exception:
            return

        async def _finish_on_ui():
            # Update metric text values (controls already exist, no recreation)
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

            cagr = metrics['overall_cagr']
            self.cagr_text.value = f"{cagr:,.2f}%"
            self.cagr_text.color = ft.Colors.GREEN if cagr >= 0 else ft.Colors.RED

            # Update sidebar stats
            try:
                from components.navigation import PremiumSidebar
                sidebar = getattr(self.app_state, '_sidebar', None)
                if sidebar and isinstance(sidebar, PremiumSidebar):
                    sidebar.set_stats(
                        portfolio_value=metrics['total_value'],
                        invested=metrics['total_invested'],
                        pnl=metrics['overall_pnl']
                    )
            except Exception:
                pass

            # Build UI tree once on first load
            if not self._ui_built:
                self.header_row = ft.Row([
                    page_title("Dashboard"),
                    ft.Row([
                        self.refresh_progress,
                        ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh Market Data", on_click=self.on_refresh_data, icon_color=ft.Colors.WHITE)
                    ], alignment=ft.MainAxisAlignment.END)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

                self.kpi_row_1 = ft.Row([
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
                ])

                self.kpi_row_2 = ft.Row([
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
                        info_metric("Overall XIRR", self.xirr_text, ft.Icons.AUTO_GRAPH),
                        expand=True,
                        on_click=lambda _: self.show_broker_breakdown_dialog("Overall XIRR", "overall_xirr", is_currency=False, top_pos=260)
                    ),
                    premium_card(
                        info_metric("Overall CAGR", self.cagr_text, ft.Icons.PERCENT),
                        expand=True,
                        on_click=lambda _: self.show_broker_breakdown_dialog("Overall CAGR", "overall_cagr", is_currency=False, top_pos=260)
                    ),
                ])

                self.performers_row = ft.Row([
                    premium_card(ft.Column([], expand=True), expand=True),
                    premium_card(ft.Column([], expand=True), expand=True),
                ], alignment=ft.MainAxisAlignment.START)

                self.insights_row = ft.Row([
                    premium_card(ft.Column([], expand=True), expand=True),
                    premium_card(ft.Column([], expand=True), expand=True),
                ], alignment=ft.MainAxisAlignment.START)

                self.content_col.controls = [
                    self.header_row,
                    self.kpi_row_1,
                    self.kpi_row_2,
                    self.performers_row,
                    self.insights_row,
                    ft.Container(height=40)
                ]
                self._ui_built = True

            # Swap content of the 4 panel cards
            self.performers_row.controls[0].content = self.build_performers_list("Top Performers", performers["top"], is_top=True)
            self.performers_row.controls[1].content = self.build_performers_list("Worst Performers", performers["worst"], is_top=False)
            self.insights_row.controls[0].content = self.build_insights_list("Actionable Insights", insights)
            self.insights_row.controls[1].content = self.build_harvesting_list("Tax Harvesting Ops", harvesting)

            try:
                self.update()  # Single call updates the full dashboard tree
            except Exception:
                pass

        page = getattr(self.app_state, 'page', None)
        if page:
            page.run_task(_finish_on_ui)

    def invalidate_cache(self):
        """Clear all caches when external data changes (broker deleted, portfolio wiped)."""
        self._data_loaded = False

    def build_performers_list(self, title, data, is_top):
        color = ft.Colors.GREEN if is_top else ft.Colors.RED
        icon = ft.Icons.ARROW_UPWARD if is_top else ft.Icons.ARROW_DOWNWARD

        rows = [ft.Text(title, size=20, weight=ft.FontWeight.BOLD)]
        if not data:
            rows.append(ft.Text("No data available.", italic=True, color=ft.Colors.GREY))
        for item in data:
            rows.append(
                ft.Row([
                    ft.Container(
                        content=ft.Text(item["symbol"], size=16, weight=ft.FontWeight.W_600, color=ft.Colors.BLUE_300),
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
            rows.pop() 
            
        return ft.Column(rows, spacing=10)

    def build_insights_list(self, title, data):
        rows = [ft.Text(title, size=20, weight=ft.FontWeight.BOLD)]
        if not data:
            rows.append(ft.Text("No active signals right now.", italic=True, color=ft.Colors.GREY))
        for item in data:
            sig_color = ft.Colors.GREEN if item["signal"] == "ACCUMULATE" else ft.Colors.RED
            rows.append(
                ft.Row([
                    ft.Container(
                        content=ft.Text(item["symbol"], size=16, weight=ft.FontWeight.W_600, color=ft.Colors.BLUE_300),
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
        for item in data[:5]:
            rows.append(
                ft.Row([
                    ft.Column([
                        ft.Container(
                            content=ft.Text(item["symbol"], size=16, weight=ft.FontWeight.W_700, color=ft.Colors.BLUE_300),
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
        if self.refresh_progress.visible: return
        self.refresh_progress.visible = True
        self.update()
        
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT symbol FROM holdings WHERE qty > 0")
            symbols = [r[0] for r in cursor.fetchall()]

        def fetch_wrapper():
            if symbols:
                fetch_and_update_market_data(symbols)
            # CRITICAL: Rebuild holdings to update the DB cache for all views
            from engine import rebuild_holdings
            rebuild_holdings()
            self.app_state.page.run_task(self.finish_refresh)
            
        threading.Thread(target=fetch_wrapper, daemon=True).start()

    async def finish_refresh(self):
        # Clear cache so load_data() actually reloads
        self._data_loaded = False
        self.refresh_progress.visible = False
        self.load_data()
        self.update()