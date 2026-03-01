import sqlite3
from datetime import datetime, timedelta

# Simulate the search for "COS"
f_symbol = "COS"
f_broker = "All"
f_type = "All"

today = datetime.now()
all_trades_start = today - timedelta(days=1825)  # ~5 years
start_date = all_trades_start.date()
end_date = today.date()

query = """
    SELECT t.trade_id, t.date, t.symbol, t.type, t.qty, t.price, t.fee, t.broker
    FROM trades t
    WHERE 1=1
"""
params = []

if f_broker and f_broker != "All":
    query += " AND t.broker = ?"
    params.append(f_broker)

if f_symbol:
    query += " AND t.symbol LIKE ? COLLATE NOCASE"
    params.append(f"%{f_symbol}%")

if f_type and f_type != "All":
    query += " AND t.type = ?"
    params.append(f_type)

if start_date:
    query += " AND t.date >= ?"
    params.append(start_date.strftime('%Y-%m-%d'))

if end_date:
    query += " AND t.date <= ?"
    params.append(end_date.strftime('%Y-%m-%d'))

query += " ORDER BY t.date ASC"

print("Generated SQL Query:")
print(query)
print("\nParameters:")
print(params)

# Execute the query
conn = sqlite3.connect('portfolio.db')
cursor = conn.cursor()
cursor.execute(query, params)
results = cursor.fetchall()
conn.close()

print(f"\nNumber of results: {len(results)}")
if results:
    print("\nFirst 5 results:")
    for row in results[:5]:
        print(f"  {row}")
else:
    print("\nNo results found")
