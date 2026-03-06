I have multiple brokerage accounts in INR, help Build a professional Stock Portfolio Tracker using Python Flet version 0.80.5,  and SQLite to track all trades and positions. A  dashboard viewe for consolidated details.
The UI must be high-fidelity,premium,  modern, easy to use and intututive.

 ARCHITECTURE:

1. Database (SQLite): 
   - 'trades' table: (id, Broker, date, symbol, type[BUY/SELL], qty, price, fee ).
   - 'assets' table: Cache for fundamental data ( useful ratios, shareholder patterns and other useful details).
   - holdings table: (id, Broker, symbol, qty, avgprice, RealizedPnl , IV, XIRR )
   - broker details (id, broker)
   - marketdata (Symbol, Price, 52 low, 52 high, PE, EPS, PB, ROE, ROCE,Debt-to-Equity, Dividend, ...and all useful details of a stock)
2. Data Fetching: Use 'yfinance' or similar for  market prices (NSE/BSE & Global) and fundamental ratios. Real-time data not required.
3. Get market data once a day after launch  and store in db

4. UI DESIGN:
- Use a side Nav bar for: [Dashboard, Holdings, Trade Entry, Trade History, Settings, Exit].
- Use Flet's bar chart for Portfolio value over time.
- Ensure the app is responsive and feels like a native Mac desktop application.
- Load all data from DB first and then fet market data and update DB silently
- Implement CRUD for Trade Histrory page
- Implement DELETE for Holdings. While delete a holding, ask for confirmationa and delete the holding and all related trades 
- Add a link to the Asset column in Holdings Page to see all related trades for each holding
- Implement CRUD for broker detauils under settings
- Create separte files for each view for readability and trouble shooting. Break big methods into smaller ones

5. Intrinsic Value (IV) Calc:
   - Calculate IV using a 5-year DCF (Discounted Cash Flow) snapshot.
   - Assumption: 5 years of positive growth (default 12% growth, 10% discount rate).
   - Logic: Compare 'Current Price' to 'IV'. 
     - If Price < 70% of IV -> "ACCUMULATE" (Green).
     - If Price > 110% of IV -> "REDUCE" (Red).

6. Stock Insights & Ratios in Holdings View:
   - Display: Debt-to-Equity, EPS, PE, PB, Dividend, and all useful Ratio.
   - Shareholding Pattern: Show a breakdown of Promoter, FII, and DII holdings.
   - Show stock trend, clean indication for accumulation or reduction

7. Smart Features:
   - Tax-Loss Harvesting Tool: Identify stocks in 'Loss' that could be sold to offset gains.
   - Portfolio Concentration: A chart showing if you are over-exposed to a single stock or sector.
   - Rebalancing Alerts: Flag assets that have drifted ±5% from your target weight.

8. INPUT & UTILITIES:
- Manual Trade Entry: Form with validation.
- CSV Bulk Upload: Robust parser to import history. Preview the export before commiting
- Export: One-click export of the entire database to Excel/CSV.

9. Broker names
Selva-Kite
Bahee-Kite
Mithun-Kite
Upstox
ICICI
Nomura

10. Trade Fee Calculkation;
Equity Delivery, fixed 10
GST         18% on (Brokerage + SEBI + Transaction charges)
SEBI Charges,₹10 
Stamp Duty  ,0.015% 
DP Charges  ,"₹15.34 (Male) — Per company, per day, only when selling delivery shares."


------------


System/Context Prompt: Portfolio Tracker Application

Overview: You are assisting with the development of "PortfolioTrack," a professional, macOS-style desktop application built with Python using the flet UI framework and sqlite3 for local database storage. The app is a consolidated stock and asset portfolio tracker that allows users to monitor their investments across multiple brokerages (e.g., Kite, Upstox, ICICI). It prioritizes a high-fidelity, dark-themed, premium UI with real-time performance metrics and privacy features.

Core Architecture:

Frontend: flet (version 0.80.x). The UI is divided into multiple view components (DashboardView, PositionsView
, etc.) managed by a central 

AppState
 class for state management across the app.
Backend Database: sqlite3 (portfolio.db). Features three main tables: 

trades
 (individual transactions), positions (aggregated holdings), and 

brokers
 (list of active platforms).
Engine: 

engine.py
 handles the financial logic, including parsing the 

trades
 table to calculate average cost basis, realized/unrealized PNL, dividends, and updating the positions table. It uses Yahoo Finance (

yfinance
) to fetch live market data.
Implemented Features & Views:

Dashboard (DashboardView):
Displays high-level portfolio KPIs: Total Value, Total Invested, Overall P&L, Daily Change, XIRR, and Dividend Yield.
Features a 6-month historical performance line chart and an asset allocation pie chart.
Positions (

PositionsView
):
A consolidated, real-time list of all active stock holdings showing total quantity, average price, current price, and live Unrealized P&L.
Drill-down: Clicking a position opens an interactive popup dialog showing the complete chronological transaction history (buys, sells, dividends) that make up that specific position, including a rolling realized P&L calculation.
Deletion: Users can permanently delete an entire position (which cascades and deletes all underlying trades for that symbol/broker).
Trade Entry (

AddTradeView
):
Manual Entry: A form to log new Buy, Sell, or Dividend transactions with Date (using ft.DatePicker), Symbol, Quantity, Price, Fees, and Broker.
Bulk Import: A CSV upload feature (using ft.FilePicker) to import large datasets of trades in one click. Includes a data preview dialog before committing to the database.
Trade History (

TradeHistoryView
):
A comprehensive, searchable, and filterable data table of every historical transaction.
Users can filter by Date Range, Asset Type (Buy/Sell), Broker, and search by Symbol.
Includes individual Row actions to Edit or Delete a specific past trade without deleting the whole position.
Strategy Insights (StrategyView):
Displays fundamental analysis and smart portfolio tools, such as Top Winners/Losers, Portfolio Beta, and intrinsic value calculations (e.g., based on Buffett's methodology).
Settings (SettingsView):
Broker Management: Allows users to add custom broker names or delete existing ones.
Privacy Mode: A global toggle stored in 

AppState
 that masks absolute currency values ($***) across all views for privacy when screen sharing.
Data Controls: Buttons to manually force a li