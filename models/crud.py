import sqlite3
import pandas as pd
from database import get_connection

# Note: get_connection() returns a thread-local pooled connection — do NOT call conn.close()

def add_trade(broker: str, date: str, symbol: str, trade_type: str, qty: float, price: float, fee: float):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trades (broker, date, symbol, type, qty, price, fee)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (broker, date, symbol, trade_type, qty, price, fee))
    conn.commit()

def update_trade(trade_id: int, date: str, symbol: str, trade_type: str, qty: float, price: float, fee: float):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE trades
        SET date = ?, symbol = ?, type = ?, qty = ?, price = ?, fee = ?
        WHERE id = ?
    ''', (date, symbol, trade_type, qty, price, fee, trade_id))
    conn.commit()

def replace_symbol(old_symbol: str, new_symbol: str, broker: str):
    """Bulk rename a symbol across all trades for a specific broker."""
    if old_symbol == new_symbol: return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE trades SET symbol = ? WHERE symbol = ? AND broker = ?", (new_symbol, old_symbol, broker))
    
    # Remove the old holding entry for this broker/symbol as it's being renamed
    cursor.execute("DELETE FROM holdings WHERE symbol = ? AND broker = ?", (old_symbol, broker))

    # Cleanup market data only if the old symbol is completely gone
    cursor.execute("SELECT COUNT(*) FROM trades WHERE symbol = ?", (old_symbol,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("DELETE FROM marketdata WHERE symbol = ?", (old_symbol,))
        cursor.execute("DELETE FROM assets WHERE symbol = ?", (old_symbol,))
    conn.commit()

def delete_trade(trade_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()

def delete_holding_and_trades(broker: str, symbol: str):
    """Deletes a holding and ALL its underlying trades (cascading)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades WHERE broker = ? AND symbol = ?", (broker, symbol))
    cursor.execute("DELETE FROM holdings WHERE broker = ? AND symbol = ?", (broker, symbol))
    cursor.execute("DELETE FROM marketdata WHERE symbol = ?", (symbol,))
    cursor.execute("DELETE FROM assets WHERE symbol = ?", (symbol,))
    conn.commit()

def get_all_brokers() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM brokers ORDER BY name")
    return [row[0] for row in cursor.fetchall()]

def add_broker(name: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO brokers (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already exists

def delete_broker(name: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM brokers WHERE name = ?", (name,))
    conn.commit()

def wipe_all_data():
    """Wipes all trades, holdings, and cached market/asset data. Leaves brokers intact."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades")
    cursor.execute("DELETE FROM holdings")
    cursor.execute("DELETE FROM marketdata")
    cursor.execute("DELETE FROM assets")
    conn.commit()
