import sqlite3
import pandas as pd
from database import db_session

# Database operations now use the db_session() context manager for clean connections.

def add_trade(broker: str, date: str, symbol: str, trade_type: str, qty: float, price: float, fee: float, trade_id: str):
    sql = 'INSERT INTO trades (trade_id, broker, date, symbol, type, qty, price, fee) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    params = (trade_id, broker, date, symbol, trade_type, qty, price, fee)
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)

def update_trade(broker: str, trade_id: str, date: str, symbol: str, trade_type: str, qty: float, price: float, fee: float):
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE trades
            SET date = ?, symbol = ?, type = ?, qty = ?, price = ?, fee = ?
            WHERE broker = ? AND trade_id = ?
        ''', (date, symbol, trade_type, qty, price, fee, broker, trade_id))

def update_holding_quantity_and_price(broker: str, symbol: str, new_qty: float, new_price: float):
    """Update holding quantity and average price for a broker/symbol pair."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE holdings
            SET qty = ?, avg_price = ?
            WHERE broker = ? AND symbol = ?
        ''', (new_qty, new_price, broker, symbol))

def is_duplicate_trade(broker: str, trade_id: str) -> bool:
    """Returns True if a trade with identical trade_id already exists for this broker."""
    if not trade_id: return False
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM trades WHERE broker=? AND trade_id=?', (broker, trade_id))
        return cursor.fetchone()[0] > 0

def get_existing_trade_ids(broker: str) -> set:
    """Efficiently get all existing trade_ids for a broker in one query (for batch import validation)."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT trade_id FROM trades WHERE broker=?', (broker,))
        return {row[0] for row in cursor.fetchall()}

def replace_symbol(old_symbol: str, new_symbol: str, broker: str):
    """Bulk rename a symbol across all trades for a specific broker."""
    if old_symbol == new_symbol: return
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE trades SET symbol = ? WHERE symbol = ? AND broker = ?", (new_symbol, old_symbol, broker))
        
        # Remove the old holding entry for this broker/symbol as it's being renamed
        cursor.execute("DELETE FROM holdings WHERE symbol = ? AND broker = ?", (old_symbol, broker))

        # Cleanup market data only if the old symbol is completely gone
        cursor.execute("SELECT COUNT(*) FROM trades WHERE symbol = ?", (old_symbol,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("DELETE FROM marketdata WHERE symbol = ?", (old_symbol,))
            cursor.execute("DELETE FROM assets WHERE symbol = ?", (old_symbol,))

def delete_trade(broker: str, trade_id: str):
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE broker = ? AND trade_id = ?", (broker, trade_id))

def delete_holding_and_trades(broker: str, symbol: str):
    """Deletes a holding and ALL its underlying trades (cascading)."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE broker = ? AND symbol = ?", (broker, symbol))
        cursor.execute("DELETE FROM holdings WHERE broker = ? AND symbol = ?", (broker, symbol))
        cursor.execute("DELETE FROM marketdata WHERE symbol = ?", (symbol,))
        cursor.execute("DELETE FROM assets WHERE symbol = ?", (symbol,))

def get_all_brokers() -> list:
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM brokers ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

def add_broker(name: str):
    with db_session() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO brokers (name) VALUES (?)", (name,))
        except sqlite3.IntegrityError:
            pass  # Already exists

def delete_broker(name: str):
    """Delete a broker and all its associated trades and holdings (cascading)."""
    with db_session() as conn:
        cursor = conn.cursor()
        # Get all symbols for this broker to potentially delete unused market data
        cursor.execute("SELECT DISTINCT symbol FROM trades WHERE broker = ?", (name,))
        symbols_for_broker = [row[0] for row in cursor.fetchall()]
        
        # Delete all trades for this broker
        cursor.execute("DELETE FROM trades WHERE broker = ?", (name,))
        
        # Delete all holdings for this broker
        cursor.execute("DELETE FROM holdings WHERE broker = ?", (name,))
        
        # Delete broker record
        cursor.execute("DELETE FROM brokers WHERE name = ?", (name,))
        
        # Cleanup unused market data (only if no other trades reference these symbols)
        for symbol in symbols_for_broker:
            cursor.execute("SELECT COUNT(*) FROM trades WHERE symbol = ?", (symbol,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("DELETE FROM marketdata WHERE symbol = ?", (symbol,))
                cursor.execute("DELETE FROM assets WHERE symbol = ?", (symbol,))

def wipe_all_data():
    """Wipes all trades, holdings, and cached market/asset data. Leaves brokers intact."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades")
        cursor.execute("DELETE FROM holdings")
        cursor.execute("DELETE FROM marketdata")
        cursor.execute("DELETE FROM assets")
