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

        self.content = ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.HELP_CENTER_ROUNDED, size=32, color=self.accent_color),
                ft.Text("Help & Documentation", size=28, weight=ft.FontWeight.W_700),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            
            ft.Text("Documentation of formulas and market data used in PortfolioTrack.", 
                    color=self.text_secondary, size=16),
            
            ft.Container(height=20),
            
            ft.ListView(
                expand=True,
                spacing=20,
                controls=[
                    self._create_section(
                        "Investment Formulas",
                        [
                            ("Avg Purchase Price", "Calculated as: Total Cost Basis / Current Quantity. Fees are included in the cost basis for BUY trades and deducted for SELL trades."),
                            ("Unrealized PnL", "Calculated as: (Current Price - Avg Purchase Price) * Current Quantity."),
                            ("Realized PnL", "Calculated as: Sum of ((Sell Price - Avg Cost at time of sell) * Qty - Fees) for all closed portions of positions."),
                            ("Overall PnL", "The sum of Unrealized PnL and Realized PnL."),
                            ("XIRR (Extended Internal Rate of Return)", "A measure of the annual return of your investments, taking into account the timing of each cash flow (BUYs, SELLs, Dividends). We use the Newton-Raphson numerical method to solve for the rate that makes the Net Present Value (NPV) of all cash flows equal to zero.")
                        ]
                    ),
                    self._create_section(
                        "Intrinsic Value & Action Signals",
                        [
                            ("Intrinsic Value (DCF)", "Calculated using a 5-year Discounted Cash Flow (DCF) model. It projects EPS for 5 years at a 12% growth rate, discounts them back at 10%, and adds a terminal value based on a 15x multiple."),
                            ("ACCUMULATE Signal", "Triggered when the Current Market Price is less than 70% of the calculated Intrinsic Value. Suggests the stock is undervalued."),
                            ("REDUCE Signal", "Triggered when the Current Market Price is greater than 110% of the calculated Intrinsic Value. Suggests the stock may be overvalued."),
                            ("HOLD Signal", "Triggered when the price is between 70% and 110% of the Intrinsic Value.")
                        ]
                    ),
                    self._create_section(
                        "Trade Fees (India Equity Market Logic)",
                        [
                            ("Equity Delivery Brokerage", "Fixed ₹10 per delivery trade."),
                            ("STT (Securities Transaction Tax)", "0.1% on buy and sell (applicable to turnover)."),
                            ("SEBI Charges", "Fixed ₹10 (standardized)."),
                            ("Stamp Duty", "0.015% (on BUY turnover only)."),
                            ("DP Charges", "₹15.34 (charged ONLY on SELL delivery trades)."),
                            ("GST", "18% applied to the sum of Brokerage and SEBI charges.")
                        ]
                    ),
                    self._create_section(
                        "Market Data & Sync",
                        [
                            ("Data Source", "Real-time market data is fetched via the Yahoo Finance (yfinance) API. Indian stock symbols are automatically suffixed with '.NS' (NSE) or '.BO' (BSE) if not specified."),
                            ("Sync Frequency", "Market data (Price, PE, EPS, 52w High/Low) is automatically synchronized every 24 hours upon app launch. You can also trigger manual refreshes in the Settings menu."),
                            ("Fundamental Data", "PE Ratio, EPS, PB Ratio, ROE, Debt/Equity, and Dividend Yield are updated during the daily sync.")
                        ]
                    ),
                ]
            )
        ], scroll=None, spacing=10)

    def _create_section(self, title, items):
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=18, weight=ft.FontWeight.W_600, color=self.accent_color),
                ft.Divider(color="#2A3F5F", height=1),
                ft.Column([
                    ft.Container(
                        content=ft.Column([
                            ft.Text(label, size=14, weight=ft.FontWeight.W_700, color="#FFFFFF"),
                            ft.Text(description, size=13, color=self.text_secondary),
                        ], spacing=4),
                        padding=ft.padding.only(left=10, top=5, bottom=5)
                    ) for label, description in items
                ], spacing=10)
            ], spacing=10),
            bgcolor=self.card_bg,
            padding=20,
            border_radius=12,
            border=ft.border.all(1, "#2A3F5F")
        )
