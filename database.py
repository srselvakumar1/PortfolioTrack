import sqlite3
import os
from contextlib import contextmanager

DB_PATH = "portfolio.db"

@contextmanager
def db_session():
    """Context manager for SQLite connections with WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA temp_store=MEMORY")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize_database(reset=False):
    """Initializes the database schema. If reset=True, wipes all tables except brokers."""
    with db_session() as conn:
        cursor = conn.cursor()

        if reset:
            cursor.execute("DROP TABLE IF EXISTS trades")
            cursor.execute("DROP TABLE IF EXISTS holdings")
            cursor.execute("DROP TABLE IF EXISTS marketdata")
            cursor.execute("DROP TABLE IF EXISTS assets")
            cursor.execute("DROP TABLE IF EXISTS dashboard_metrics")

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

        # 2. Trades Table (Composite Primary Key)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                broker TEXT NOT NULL,
                trade_id TEXT NOT NULL,
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                type TEXT NOT NULL, 
                qty REAL NOT NULL,
                price REAL NOT NULL,
                fee REAL DEFAULT 0.0,
                PRIMARY KEY (broker, trade_id),
                FOREIGN KEY(broker) REFERENCES brokers(name)
            )
        ''')

        # 3. MarketData Table 
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
        
        # 4. Global Dashboard Metrics Cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dashboard_metrics (
                metric_key TEXT PRIMARY KEY,
                metric_value REAL,
                last_updated TEXT
            )
        ''')

        # 5. Assets Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                symbol TEXT PRIMARY KEY,
                intrinsic_value REAL,
                action_signal TEXT, 
                promoter_holding REAL,
                fii_holding REAL,
                dii_holding REAL,
                last_updated TEXT
            )
        ''')

        # 6. Holdings Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS holdings (
                broker TEXT NOT NULL,
                symbol TEXT NOT NULL,
                qty REAL NOT NULL,
                avg_price REAL NOT NULL,
                realized_pnl REAL DEFAULT 0.0,
                running_pnl REAL DEFAULT 0.0,
                xirr REAL DEFAULT 0.0,
                cagr REAL DEFAULT 0.0,
                earliest_date TEXT,
                total_fees REAL DEFAULT 0.0,
                PRIMARY KEY (broker, symbol),
                FOREIGN KEY(broker) REFERENCES brokers(name)
            )
        ''')
        
        # Migration: Add running_pnl column if it doesn't exist (for existing databases)
        try:
            cursor.execute("PRAGMA table_info(holdings)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'running_pnl' not in columns:
                cursor.execute("ALTER TABLE holdings ADD COLUMN running_pnl REAL DEFAULT 0.0")
                cursor.execute("UPDATE holdings SET running_pnl = realized_pnl")
        except Exception:
            pass

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_broker ON trades(broker)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_broker_symbol ON trades(broker, symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_symbol ON holdings(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_broker ON holdings(broker)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_broker_symbol ON holdings(broker, symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_marketdata_symbol ON marketdata(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol)")
        
        # Additional indexes for faster filtering in TradeHistory and Holdings views
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_broker_date ON trades(broker, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_date ON trades(symbol, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_symbol_broker ON holdings(symbol, broker)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assets_action_signal ON assets(action_signal)")
        
        conn.execute("PRAGMA optimize")

if __name__ == "__main__":
    # Run with reset=True to fulfill user request
    initialize_database(reset=True)