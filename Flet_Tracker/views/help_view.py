import flet as ft

class HelpView(ft.Container):
    def __init__(self, app_state):
        super().__init__()
        self.app_state = app_state
        self.expand = True
        
        # UI Colors
        self.card_bg = "#1A1C1E"
        self.accent_color = "#3B82F6"
        self.text_secondary = "#8B9CB6"

        # Font properties
        self.base_font_size = 14
        self.title_font_size = 18

        # UI Elements that need scaling
        self.dynamic_texts = []
        self.dynamic_titles = []

        # Font size controls
        self.font_decrease_btn = ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, on_click=self.decrease_font_size, tooltip="Decrease Font Size")
        self.font_increase_btn = ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, on_click=self.increase_font_size, tooltip="Increase Font Size")

        self.content_list = ft.ListView(
            expand=True,
            spacing=20,
            controls=self._build_content()
        )

        self.content = ft.Column([
            ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.HELP_CENTER_ROUNDED, size=32, color=self.accent_color),
                    ft.Text("Help & Documentation", size=28, weight=ft.FontWeight.W_700),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    ft.Text("Text Size:", color=self.text_secondary),
                    self.font_decrease_btn,
                    self.font_increase_btn
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Text("Comprehensive documentation and formulas used in PortfolioTrack.", 
                    color=self.text_secondary, size=16),
            
            ft.Container(height=10),
            
            self.content_list
        ], spacing=10)

    def _build_content(self):
        self.dynamic_texts.clear()
        self.dynamic_titles.clear()
        
        # Example Data for Tables
        pnl_run_cols = ["Date", "Type", "Qty", "Price", "Current", "Running PnL"]
        pnl_run_rows = [
            ["2023-01-01", "BUY", 10, "₹100", "₹120", "+₹200"],
            ["2023-01-05", "BUY", 5, "₹110", "₹120", "+₹150"],
            ["Total", "-", 15, "₹103.33", "₹120", "+₹250"]
        ]
        
        pnl_real_cols = ["Date", "Action", "Qty", "Price", "Avg Cost", "Realized"]
        pnl_real_rows = [
            ["2023-01-01", "BUY", 10, "₹100", "-", "-"],
            ["2023-02-01", "SELL", 5, "₹150", "₹100", "+₹250"],
            ["Balance", "-", 5, "-", "₹100", "-"]
        ]
        
        cagr_cols = ["Year", "Investment", "Value", "Return", "CAGR"]
        cagr_rows = [
            ["Start", "₹10,000", "₹10,000", "-", "-"],
            ["Year 1", "₹10,000", "₹11,500", "15%", "15.0%"],
            ["Year 3", "₹10,000", "₹15,000", "50%", "14.47%"]
        ]
        
        iv_cols = ["Year", "Proj. EPS", "Disc. Factor", "Pres. Value"]
        iv_rows = [
            ["Base", "₹10.00", "1.000", "₹10.00"],
            ["Year 1", "₹11.20", "0.909", "₹10.18"],
            ["Year 5", "₹17.62", "0.621", "₹10.94"],
            ["TV", "₹264.30", "0.621", "₹164.13"],
            ["Total IV", "-", "-", "₹214.25"]
        ]
        
        fees_cols = ["Charge Name", "Rate / Logic", "Sample (₹1L Buy)"]
        fees_rows = [
            ["Brokerage", "Fixed ₹10", "₹10.00"],
            ["STT", "0.1% on Turnover", "₹100.00"],
            ["Stamp Duty", "0.015% (Buy)", "₹15.00"],
            ["SEBI", "Fixed ₹10", "₹10.00"],
            ["GST", "18% on (Brkg+SEBI)", "₹3.60"],
            ["Total Fees", "-", "₹138.60"]
        ]
        
        live_trade_cols = ["#", "Date", "Type", "Qty", "Price", "Run. Qty", "Avg Cost", "Running PnL", "Formula"]
        live_trade_rows = [
            ["1", "2023-09-21", "buy", "2", "5,144.65", "2", "5,144.65", "0", "Avg Cost = (0 + (2 * 5144.65)) / 2"],
            ["2", "2023-09-21", "buy", "2", "5,139.85", "4", "5,142.25", "0", "Avg Cost = (10289.30 + (2 * 5139.85)) / 4"],
            ["3", "2023-09-21", "buy", "1", "5,120.00", "5", "5,137.80", "0", "Avg Cost = (20569.00 + (1 * 5120)) / 5"],
            ["4", "2023-09-21", "buy", "1", "5,120.00", "6", "5,134.83", "0", "Avg Cost = (25689.00 + (1 * 5120)) / 6"],
            ["5", "2023-09-21", "buy", "1", "5,101.15", "7", "5,130.02", "0", "Avg Cost = (30809.00 + (1 * 5101.15)) / 7"],
            ["6", "2023-09-21", "buy", "1", "5,101.15", "8", "5,126.41", "0", "Avg Cost = (35910.15 + (1 * 5101.15)) / 8"],
            ["7", "2023-09-22", "buy", "1", "5,052.00", "9", "5,118.14", "0", "Avg Cost = (41011.30 + (1 * 5052)) / 9"],
            ["8", "2023-09-22", "buy", "1", "5,052.00", "10", "5,111.53", "0", "Avg Cost = (46063.30 + (1 * 5052)) / 10"],
            ["9", "2023-09-22", "buy", "2", "5,035.60", "12", "5,098.88", "0", "Avg Cost = (51115.30 + (2 * 5035.6)) / 12"],
            ["10", "2023-09-22", "buy", "1", "5,004.35", "13", "5,091.60", "0", "Avg Cost = (61186.50 + (1 * 5004.35)) / 13"],
            ["11", "2023-09-28", "buy", "1", "5,044.00", "14", "5,088.20", "0", "Avg Cost = (66190.85 + (1 * 5044)) / 14"],
            ["12", "2023-09-28", "buy", "1", "5,044.00", "15", "5,085.26", "0", "Avg Cost = (71234.85 + (1 * 5044)) / 15"],
            ["13", "2024-02-23", "sell", "2", "8,450.00", "13", "5,085.26", "+6,729.49", "PnL = (8450 - 5085.26) * 2"],
            ["14", "2024-02-23", "sell", "2", "8,450.00", "11", "5,085.26", "+6,729.49", "PnL = (8450 - 5085.26) * 2"],
            ["15", "2024-02-23", "sell", "1", "8,450.00", "10", "5,085.26", "+3,364.74", "PnL = (8450 - 5085.26) * 1"],
            ["16", "2024-03-19", "sell", "1", "10,000.00", "9", "5,085.26", "+4,914.74", "PnL = (10000 - 5085.26) * 1"],
            ["17", "2024-03-19", "sell", "1", "10,000.00", "8", "5,085.26", "+4,914.74", "PnL = (10000 - 5085.26) * 1"],
            ["18", "2024-04-19", "sell", "1", "8,804.00", "7", "5,085.26", "+3,718.74", "PnL = (8804 - 5085.26) * 1"],
            ["19", "2024-04-19", "sell", "1", "8,804.00", "6", "5,085.26", "+3,718.74", "PnL = (8804 - 5085.26) * 1"],
            ["20", "2024-04-19", "sell", "1", "8,804.00", "5", "5,085.26", "+3,718.74", "PnL = (8804 - 5085.26) * 1"],
            ["21", "2024-04-19", "sell", "2", "8,804.00", "3", "5,085.26", "+7,437.49", "PnL = (8804 - 5085.26) * 2"],
            ["22", "2024-04-19", "sell", "1", "8,804.00", "2", "5,085.26", "+3,718.74", "PnL = (8804 - 5085.26) * 1"],
            ["23", "2024-04-19", "sell", "1", "8,804.00", "1", "5,085.26", "+3,718.74", "PnL = (8804 - 5085.26) * 1"],
            ["24", "2024-06-03", "sell", "1", "9,373.90", "0", "0", "+4,288.64", "PnL = (9373.9 - 5085.26) * 1"],
            ["-", "Summary", "-", "15 Net", "-", "0", "-", "+56,973.05", "Total Running PnL"]
        ]
        
        calc_levels_cols = ["Calculation", "Level", "Reason"]
        calc_levels_rows = [
            ["Running Quantity", "Transaction", "Evolves with each trade"],
            ["Cost Basis", "Transaction", "Accumulates through each trade"],
            ["Realized PnL", "Transaction", "Only occurs per SELL"],
            ["Fee Accumulation", "Transaction", "Sums stored fees per trade"],
            ["Cash Flows", "Transaction", "Collected per trade for XIRR"],
            ["Average Price", "Holding", "Computed from final totals"],
            ["Unrealized PnL", "Holding", "Uses current market price + final state"],
            ["Running PnL", "Holding", "Combines all realized + unrealized"],
            ["XIRR/CAGR", "Holding", "Uses complete cash flow history"],
            ["Total Fees", "Holding", "Sum of all trade fees"],
        ]
        
        shortcuts_cols = ["Shortcut", "Platform", "Action"]
        shortcuts_rows = [
            ["Ctrl+N", "Windows/Linux | Cmd+N on Mac", "Add new trade (Opens Trade Entry)"],
            ["Esc", "All Platforms", "Close open dialogs"],
            ["Ctrl+K", "Windows/Linux | Cmd+K on Mac", "Focus symbol search (Holdings/Trade History)"]
        ]
        
        return [
            self._create_section(
                "Keyboard Shortcuts & Quick Navigation",
                [
                    ("Available Shortcuts", "Use these keyboard shortcuts to navigate faster and perform common actions without clicking.",
                     self._create_example_table(shortcuts_cols, shortcuts_rows))
                ]
            ),
            self._create_section(
                "Project Overview",
                [
                    ("About PortfolioTrack", "PortfolioTrack is a comprehensive Indian equity portfolio management system. It allows you to monitor your investments, calculate critical performance metrics, keep track of corporate actions, and identify actionable insights powered by fundamentally calculated intrinsic values.")
                ]
            ),
            self._create_section(
                "Application Views",
                [
                    ("Dashboard", "Your high-level financial summary. It displays key metrics like Total Invested, Overall Return, XIRR, and CAGR. You can view Top/Worst Performers, get Actionable Insights based on intrinsic valuation, and discover Tax Harvesting Opportunities."),
                    ("Holdings", "A granular breakdown of your current active portfolio. Click on any stock symbol here to open the Drilldown View, which provides historical charts, fundamental data, margin of safety, and complete transaction history."),
                    ("Trade Entry", "The hub to record new trades. You can manually enter a trade on the left or use the powerful Bulk Import feature to upload an entire CSV ledger. The system intelligently skips duplicate entries."),
                    ("Trade History", "A fully searchable and filterable database of every transaction you've made. Supports exporting data and bulk deletion.")
                ]
            ),
            self._create_section(
                "Metric Formulas & Tabular Examples",
                [
                    ("Avg Purchase Price", "Calculated as: Total Cost Basis / Current Quantity. Fees are included in the cost basis for BUY trades and deducted for SELL trades.\nExample: Buy 10 shares at ₹100 with ₹10 fee = Cost basis is ₹1,010. Avg Price = ₹101."),
                    ("Running (Unrealized) PnL", "Calculated as: (Current Price - Avg Purchase Price) * Current Quantity. Shows the profit/loss if you sold your current position today.", 
                     self._create_example_table(pnl_run_cols, pnl_run_rows)),
                    ("Running PnL", "Accumulated profit/loss combining realized gains from completed SELL trades and unrealized gains/losses from open positions (unrealized = current market price - avg cost).",
                     self._create_example_table(pnl_real_cols, pnl_real_rows)),
                    ("Overall CAGR", "Compound Annual Growth Rate. Measures the annual growth rate over time.\nFormula: (Ending Value / Beginning Value) ^ (1 / Years) - 1",
                     self._create_example_table(cagr_cols, cagr_rows)),
                    ("Overall XIRR", "Extended Internal Rate of Return. Evaluates annualized return taking exact cash flow dates into account using the Newton-Raphson method.\nExample: You invest ₹1,000 in Jan and ₹500 in June. Current value in Dec is ₹1,800. XIRR accurately weighs the time the ₹500 was exposed vs the ₹1,000.")
                ]
            ),
            self._create_section(
                "Detailed Performance Walkthrough (Live Example)",
                [
                    ("Running Quantity & Running PnL Logic", "This table illustrates a series of BUY trades throughout 2023, building an average cost, followed by various SELL trades in 2024 to lock in profit. Running PnL shows the cumulative P&L including both realized gains from sales and unrealized gains from holdings.",
                     self._create_example_table(live_trade_cols, live_trade_rows))
                ]
            ),
            self._create_section(
                "Calculation Levels: Transaction vs Holding",
                [
                    ("Understanding Where Calculations Happen", "Different calculations occur at different levels during portfolio reconstruction. Transaction-level calculations track the progression through each trade, while holding-level calculations work with aggregated totals. This table shows where each calculation is performed and why.",
                     self._create_example_table(calc_levels_cols, calc_levels_rows))
                ]
            ),
            self._create_section(
                "Intrinsic Value & Action Signals",
                [
                    ("Intrinsic Value (DCF)", "Calculated using a 5-year Discounted Cash Flow model. It projects EPS for 5 years at a 12% growth rate, discounts them back at 10%, and adds a terminal value based on a 15x multiple.",
                     self._create_example_table(iv_cols, iv_rows)),
                    ("ACCUMULATE", "Triggered when Current Market Price < 70% of Intrinsic Value. Suggests a margin of safety indicating it's Undervalued."),
                    ("REDUCE", "Triggered when Current Market Price > 110% of Intrinsic Value. Suggests stock may be overvalued."),
                    ("HOLD", "Price is between 70% and 110% of the Intrinsic Value.")
                ]
            ),
            self._create_section(
                "Trade Fees (Indian Equity Rules)",
                [
                    ("Charge Breakdown", "A detailed look at how fees are calculated for delivery trades in the Indian market.",
                     self._create_example_table(fees_cols, fees_rows)),
                    ("DP Charges", "₹15.34 (charged ONLY on SELL delivery trades)."),
                    ("DP Charge Detail", "Depository Participant charges are applied by NSDL/CDSL for debits from your demat account. This occurs on Sell transactions only.")
                ]
            ),
            self._create_section(
                "Market Data & Sync",
                [
                    ("Data Source", "Real-time market data is fetched via the Yahoo Finance (yfinance) API. Indian stock symbols are automatically suffixed with '.NS' (NSE) or '.BO' (BSE) if not specified."),
                    ("Syncing", "Market data synchronization is parallelized to fetch up to 10 stocks simultaneously, drastically reducing UI freezes.")
                ]
            )
        ]

    def _create_section(self, title, items):
        title_text = ft.Text(title, size=self.title_font_size, weight=ft.FontWeight.W_600, color=self.accent_color)
        self.dynamic_titles.append(title_text)
        
        col_items = []
        for item in items:
            if len(item) == 2:
                label, description = item
                custom_control = None
            else:
                label, description, custom_control = item

            t_label = ft.Text(label, size=self.base_font_size, weight=ft.FontWeight.W_700, color="#FFFFFF")
            t_desc = ft.Text(description, size=max(8, self.base_font_size - 1), color=self.text_secondary)
            self.dynamic_titles.append(t_label)
            self.dynamic_texts.append(t_desc)
            
            content_col = ft.Column([t_label, t_desc], spacing=4)
            if custom_control:
                content_col.controls.append(custom_control)
                
            col_items.append(
                ft.Container(
                    content=content_col,
                    padding=ft.padding.only(left=10, top=5, bottom=5)
                )
            )

        return ft.Container(
            content=ft.Column([
                title_text,
                ft.Divider(color="#2A3F5F", height=1),
                ft.Column(col_items, spacing=10)
            ], spacing=10),
            bgcolor=self.card_bg,
            padding=20,
            border_radius=12,
            border=ft.border.all(1, "#2A3F5F")
        )

    def _create_example_table(self, columns, rows_data):
        # Fixed header + ListView rows (lighter than DataTable)
        safe_rows = rows_data or []

        # Rough width estimate based on max text length
        col_widths = []
        for ci, c in enumerate(columns):
            max_len = len(str(c))
            for r in safe_rows:
                try:
                    max_len = max(max_len, len(str(r[ci])))
                except Exception:
                    pass
            col_widths.append(min(260, max(80, (max_len * 9) + 24)))

        def _hdr_cell(text: str, width: int):
            return ft.Container(
                content=ft.Text(text, color=self.text_secondary, weight=ft.FontWeight.BOLD, size=12),
                width=int(width),
                alignment=ft.alignment.Alignment(-1, 0),
                padding=ft.padding.symmetric(vertical=8, horizontal=10),
            )

        def _cell(text: str, width: int):
            return ft.Container(
                content=ft.Text(text, color="#FFFFFF", size=12),
                width=int(width),
                alignment=ft.alignment.Alignment(-1, 0),
                padding=ft.padding.symmetric(vertical=8, horizontal=10),
            )

        header = ft.Container(
            content=ft.Row(
                controls=[_hdr_cell(str(c), col_widths[i]) for i, c in enumerate(columns)],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#121212",
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#2A3F5F")),
        )

        lv = ft.ListView(expand=True, spacing=0, padding=0)
        row_controls = []
        for ri, row in enumerate(safe_rows):
            row_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[_cell(str(row[i]) if i < len(row) else "", col_widths[i]) for i in range(len(columns))],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE) if ri % 2 == 0 else ft.Colors.TRANSPARENT,
                )
            )
        lv.controls = row_controls

        grid = ft.Container(
            content=ft.Row(
                [ft.Column([header, lv], spacing=0)],
                scroll=ft.ScrollMode.ADAPTIVE,
            ),
            bgcolor="#121212",
            border=ft.border.all(1, "#2A3F5F"),
            border_radius=8,
        )

        return ft.Container(
            content=grid,
            margin=ft.margin.only(top=8, bottom=8)
        )

    def increase_font_size(self, e):
        if self.base_font_size < 30:
            self.base_font_size += 2
            self.title_font_size += 2
            self.update_fonts()

    def decrease_font_size(self, e):
        if self.base_font_size > 10:
            self.base_font_size -= 2
            self.title_font_size -= 2
            self.update_fonts()

    def update_fonts(self):
        for t in self.dynamic_titles:
            if t.color == self.accent_color:
                t.size = self.title_font_size
            else:
                t.size = self.base_font_size
        for t in self.dynamic_texts:
            t.size = max(8, self.base_font_size - 1)
        self.content_list.update()
