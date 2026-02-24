# PortfolioTrack 📈

A professional, macOS-style Portfolio Tracker built with Python, Flet, and SQLite. Track your trades, view real-time holdings, calculate XIRR, and perform fundamental analysis with intrinsic value insights.

## Project Structure

### Core Application
- **[main.py](/main.py)**: The application's entry point. It initializes the Flet window, handles high-level routing, manages the view cache for instant navigation, and triggers the background daily market data sync.
- **[engine.py](/engine.py)**: The brains of the app. Contains the mathematical engines for XIRR (using Newton-Raphson), Intrinsic Value (DCF-based), and the batch market data fetcher using `yfinance`.
- **[database.py](/database.py)**: Database manager. Handles schema initialization, thread-local connection pooling, and automatic migrations (e.g., adding new columns like `roce`).
- **[state.py](/state.py)**: Manages the shared application state, including navigation indices, global UI refresh triggers, and user-specific session data.

### UI Components (`components/`)
- **[navigation.py](/components/navigation.py)**: Implements the modern sidebar. It maps the navigation icons to their respective view indices and handles the visual state of the menu.
- **[ui_elements.py](/components/ui_elements.py)**: A library of reusable UI widgets including premium glassmorphism cards, stylized page headers, and dynamic status chips.
- **[drilldown.py](/components/drilldown.py)**: A detailed modal dialog that appears when clicking a stock symbol, showing historical trades and full fundamental details for that specific asset.

### Application Views (`views/`)
- **[dashboard_view.py](/views/dashboard_view.py)**: The home screen. Displays key portfolio metrics (Total Invested, Unrealized P&L, etc.) and visual charts of your asset distribution.
- **[holdings_view.py](/views/holdings_view.py)**: Your main portfolio table. Features live pricing refresh, XIRR per asset, and "Action Signals" based on intrinsic value analysis.
- **[tradeentry_view.py](/views/tradeentry_view.py)**: Interface for manual trade entry (BUY/SELL) and the foundation for bulk CSV importing.
- **[tradehistory_view.py](/views/tradehistory_view.py)**: A full searchable log of all transactions. Includes powerful tools for editing trades and bulk-renaming symbols (e.g., handling stock name changes).
- **[settings_view.py](/views/settings_view.py)**: Where you manage your brokers and perform maintenance tasks like wiping data or recalibrating the portfolio.
- **[help_view.py](/views/help_view.py)**: The built-in documentation center explaining the financial formulas (XIRR, Avg Price) and market data sources used by the app.

### Data Model (`models/`)
- **[crud.py](/models/crud.py)**: Contains all Create, Read, Update, and Delete functions. It abstracts the SQL logic for trade modifications, symbol replacements, and portfolio-wide data management.

## Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the App**:
   ```bash
   python main.py
   ```

3. **Database**:
   The app will automatically create `portfolio.db` on your first run and seed the default broker list.


PortfolioTrack/
├── main.py                # Main entry point & App routing
├── engine.py              # Financial logic, XIRR, & Market data sync
├── database.py            # SQLite schema and connection management
├── state.py               # Application-level state (Page, User info)
├── portfolio.db           # SQLite database file
│
├── components/            # Reusable UI widgets
│   ├── navigation.py      # Sidebar and menu items
│   ├── ui_elements.py     # Cards, Titles, and Status chips
│   └── drilldown.py       # Deep-dive Stock details dialog
│
├── views/                 # Full-page application screens
│   ├── dashboard_view.py  # Portfolio overview and charts
│   ├── holdings_view.py   # Main table of active stocks
│   ├── tradeentry_view.py # Manual transaction form
│   ├── tradehistory_view.py # Full historical log (with rename tool)
│   ├── settings_view.py   # Broker management and data cleanup
│   └── help_view.py       # Documentation for formulas & data
│
├── models/                # Database interactions
│   └── crud.py            # Create/Read/Update/Delete functions
│
├── exported_data/         # CSV backups (if exported)
└── requirements.txt       # Project dependencies (Flet, yfinance, etc.)


Prompt:

If you were to start this project from scratch, the most effective prompt would be one that clearly defines the Architecture, Financial Mathematics, and Aesthetic Standards.

Here is a comprehensive "Master Prompt" that encapsulates everything we have built:

Master Prompt: Professional macOS-style Portfolio Tracker
Objective: Build a high-performance, professional-grade Stock Portfolio Tracker using Python, Flet (UI), and SQLite (Database). The application must feature a modern, macOS-style "Glassmorphism" dark theme and provide deep financial insights.

1. Core Architecture & Tech Stack
UI Framework: Python Flet with a sidebar-based navigation system and view caching for instant switching.
Data Storage: SQLite with a relational schema consisting of trades, holdings, marketdata (daily cache), assets (fundamentals), and brokers.
Market Data: Use yfinance for batch fetching. Implement fallback logic (e.g., if .NS ticker fails, try .BO).
Data Engine: Use Pandas for heavy calculations and vectorized portfolio weighting.

2. Financial Logic Requirements
XIRR Engine: Implement a robust Internal Rate of Return (XIRR) solver using the Newton-Raphson method to calculate annualized returns for every holding and the overall portfolio.
Intrinsic Value (DCF): Create a valuation engine that calculates intrinsic value. Based on the current price vs. intrinsic value, generate "Action Signals": ACCUMULATE (undervalued), REDUCE (overvalued), or HOLD.
Average Costing: Implement a chronologically accurate cost-basis calculator that handles partial sells and includes trading fees in the cost basis.

3. Screen-by-Screen Features
Dashboard: Modern aggregate cards for Total Invested, Current Value, Unrealized P&L, and Realized P&L. Include charts for Asset Allocation.
Holdings View: A professional DataTable with sticky headers. Columns should include Symbol, Qty, Avg Price, Market Price, Daily Change %, Weight %, XIRR, and the IV Signal.
Trade History: A searchable log where every trade is editable. Crucial: Implement a "Bulk Rename" feature—if a user edits a symbol, it must rename that symbol across all historical trades for that broker.
Settings: CRUD for Broker management and "Maintenance" tools to rebuild holdings from trade history or force-sync market data.
Help View: A dedicated documentation page explaining the investment formulas and data sources.

4. Aesthetic & UX Standards
Theme: Dark Mode by default. Use a consistent color palette (e.g., Slate/Coal backgrounds, Neon Blue/Cyan accents).
UX Features:
Perform all DB and API calls in background threads with Progress Rings to keep the UI fluid.
Use "Glass" cards (semi-transparent backgrounds with subtle borders).
Implement a "Drill Down" dialog: clicking any stock symbol should open a modal showing every trade related to that stock.

5. Database Maintenance Logic
The app must follow a "Rebuild on Change" strategy. Rather than patching holdings, provide a rebuild_holdings()
 method that wipes the holdings table and recalculates the entire portfolio state from the trades
 table to ensure 100% data integrity after renames or deletions.