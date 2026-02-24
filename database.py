import sqlite3
import os
import threading

DB_PATH = "portfolio.db"

# ── Thread-local connection pool (Fix 2: one reused conn per thread) ──────────
_local = threading.local()

def get_connection() -> sqlite3.Connection:
    """Returns a thread-local SQLite connection with WAL mode enabled."""
    conn = getattr(_local, 'conn', None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        # Fix 1: WAL mode for concurrent reads + faster writes
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        _local.conn = conn
    return conn

def initialize_database():
    """Initializes the database schema if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Brokers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS brokers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Seed default Brokers
    cursor.execute("SELECT COUNT(*) FROM brokers")
    if cursor.fetchone()[0] == 0:
        default_brokers = ['Selva-Kite', 'Bahee-Kite', 'Mithun-Kite', 'Upstox', 'ICICI', 'Nomura']
        for broker in default_brokers:
            cursor.execute("INSERT INTO brokers (name) VALUES (?)", (broker,))

    # 2. Trades Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broker TEXT NOT NULL,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            type TEXT NOT NULL, -- BUY, SELL
            qty REAL NOT NULL,
            price REAL NOT NULL,
            fee REAL DEFAULT 0.0,
            FOREIGN KEY(broker) REFERENCES brokers(name)
        )
    ''')

    # 3. MarketData Table (Global cache updated daily)
    # marketdata (Symbol, Price, 52 low, 52 high, PE, EPS, PB, ROE, ROCE, Debt-to-Equity, Dividend, ...and all useful details of a stock)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marketdata (
            symbol TEXT PRIMARY KEY,
            current_price REAL,
            previous_close REAL,
            low_52w REAL,
            high_52w REAL,
            pe_ratio REAL,
            eps REAL,
            pb_ratio REAL,
            roe REAL,
            roce REAL,
            debt_to_equity REAL,
            dividend_yield REAL,
            description TEXT,
            stock_name TEXT,
            sector TEXT,
            last_updated TEXT
        )
    ''')

    # Migration for existing DBs
    try:
        cursor.execute("ALTER TABLE marketdata ADD COLUMN description TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE marketdata ADD COLUMN stock_name TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE marketdata ADD COLUMN sector TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE marketdata ADD COLUMN previous_close REAL;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE marketdata ADD COLUMN roce REAL;")
    except sqlite3.OperationalError:
        pass # Columns might already exist

    # 4. Assets Table (Fundamental ratios & IV specific caching)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            symbol TEXT PRIMARY KEY,
            intrinsic_value REAL,
            action_signal TEXT, -- ACCUMULATE, REDUCE, HOLD
            promoter_holding REAL,
            fii_holding REAL,
            dii_holding REAL,
            last_updated TEXT
        )
    ''')

    # 5. Holdings Table (Calculated positions based on trades)
    # holdings table: (id, Broker, symbol, qty, avgprice, RealizedPnl , IV, XIRR )
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broker TEXT NOT NULL,
            symbol TEXT NOT NULL,
            qty REAL NOT NULL,
            avg_price REAL NOT NULL,
            realized_pnl REAL DEFAULT 0.0,
            xirr REAL DEFAULT 0.0,
            FOREIGN KEY(broker) REFERENCES brokers(name)
        )
    ''')

    # 6. Indexes for Performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_broker ON trades(broker)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_broker_symbol ON trades(broker, symbol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_symbol ON holdings(symbol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_broker ON holdings(broker)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_broker_symbol ON holdings(broker, symbol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_marketdata_symbol ON marketdata(symbol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol)")
    
    # Fix 3: Run PRAGMA optimize once after schema is ready
    conn.execute("PRAGMA optimize")
    conn.commit()
    conn.close()
    # Reset thread-local so the next call gets a fresh optimized connection
    _local.conn = None

if __name__ == "__main__":
    initialize_database()
