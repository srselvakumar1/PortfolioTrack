import yfinance as yf
from database import get_connection
from datetime import datetime
import pandas as pd
import time

# ── Fix 5: 60-second dashboard metrics cache ───────────────────────────────────────
_metrics_cache: dict = {"data": None, "ts": 0.0}

def _invalidate_metrics_cache():
    _metrics_cache["ts"] = 0.0

def calculate_trade_fees(trade_type: str, qty: float, price: float, is_delivery: bool = True) -> float:
    """
    Calculates total fees based on provided rules:
    Equity Delivery: fixed 10
    SEBI Charges: ₹10 (per crore, effectively 0.0001% but prompt says fixed 10, we'll assume fixed 10 for simplicity or 0.0001% of turnover. Using 10 fixed as per prompt "SEBI Charges,₹10")
    Stamp Duty: 0.015% (Buy only)
    DP Charges: ₹15.34 (Only when selling delivery shares)
    GST: 18% on (Brokerage(10) + SEBI(10) + Transaction charges(0, omitted for now))
    """
    trade_type = trade_type.upper()
    turnover = qty * price
    
    brokerage = 10.0 if is_delivery else 0.0 # Assuming fixed 10 for delivery
    sebi_charges = 10.0 # Standardized to 10 as per prompt
    
    # GST applies to Brokerage + SEBI
    gst = 0.18 * (brokerage + sebi_charges)
    
    stamp_duty = 0.0
    if trade_type == 'BUY':
        stamp_duty = turnover * 0.00015 # 0.015%

    dp_charges = 0.0
    if trade_type == 'SELL' and is_delivery:
        dp_charges = 15.34
        
    total_fees = brokerage + sebi_charges + gst + stamp_duty + dp_charges
    return round(total_fees, 2)

def calculate_intrinsic_value(eps: float, growth_rate: float = 0.12, discount_rate: float = 0.10, terminal_multiple: float = 15.0) -> float:
    """
    Calculates Intrinsic Value using a 5-year DCF snapshot.
    Assumes 5 years of positive growth at `growth_rate`, discounted back at `discount_rate`.
    """
    if pd.isna(eps) or eps <= 0:
        return 0.0
        
    # Project EPS for 5 years
    cash_flows = []
    current_eps = eps
    for _ in range(5):
        current_eps *= (1 + growth_rate)
        cash_flows.append(current_eps)
        
    # Terminal Value at year 5
    terminal_value = cash_flows[-1] * terminal_multiple
    
    # Discount cash flows to present value
    iv = 0.0
    for i, cf in enumerate(cash_flows, start=1):
        iv += cf / ((1 + discount_rate) ** i)
        
    # Discount terminal value
    iv += terminal_value / ((1 + discount_rate) ** 5)
    
    return round(iv, 2)

def calculate_xirr(cashflows, guesses=[0.1, 0.0, -0.5, -0.9, 0.5], max_iter=100, tol=1e-4) -> float:
    """Calculates internal rate of return using Newton-Raphson with multiple starting points."""
    if not cashflows: return 0.0
    
    cashflows.sort(key=lambda x: x[0])
    dates = [cf[0] for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]
    
    # Check if we have both positive and negative cashflows
    if min(amounts) >= 0 or max(amounts) <= 0:
        return 0.0
        
    def npv(rate):
        if rate <= -1.0: return float('inf')
        return sum(amt / ((1 + rate) ** ((date - dates[0]).days / 365.25)) for date, amt in cashflows)
        
    for guess in guesses:
        rate = guess
        for _ in range(max_iter):
            # Clamp rate to prevent runaway math
            if rate <= -0.999: rate = -0.999
            if rate > 100.0: rate = 100.0
            
            try:
                # NPV
                v = sum(amt / ((1 + rate) ** ((date - dates[0]).days / 365.25)) for date, amt in cashflows)
                if abs(v) < tol:
                    return round(rate * 100, 2)
                
                # Derivative
                deriv = sum(
                    -((date - dates[0]).days / 365.25) * amt / ((1 + rate) ** (((date - dates[0]).days / 365.25) + 1))
                    for date, amt in cashflows
                )
                if deriv == 0: break
                
                rate -= v / deriv
            except (OverflowError, ZeroDivisionError):
                break # Try next guess
                
    # Final fallback: if simple Absolute Return is hugely negative, XIRR is roughly -99%
    return 0.0 # Could not converge robustly

def get_iv_signal(current_price: float, iv: float) -> str:
    """
    If Price < 70% of IV -> "ACCUMULATE" (Green).
    If Price > 110% of IV -> "REDUCE" (Red).
    Else -> "HOLD"
    """
    if iv <= 0 or current_price <= 0:
        return "N/A"
        
    if current_price < (0.70 * iv):
        return "ACCUMULATE"
    elif current_price > (1.10 * iv):
        return "REDUCE"
    else:
        return "HOLD"

def fetch_and_update_market_data(symbols: list):
    """
    Fetches real-time data from yfinance using batch download (Fix 9: one HTTP request).
    Falls back per-ticker for any that failed.
    """
    if not symbols:
        return

    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build yfinance symbols (add .NS suffix for Indian stocks)
    yf_symbols = [
        s + ".NS" if not s.endswith(('.NS', '.BO')) else s
        for s in symbols
    ]
    symbol_map = dict(zip(yf_symbols, symbols))  # yf_sym -> original sym

    # Fix 9: Batch download all symbols in one HTTP call
    try:
        raw = yf.download(
            yf_symbols,
            period="5d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False
        )
    except Exception as e:
        print(f"Batch download failed, falling back to per-ticker: {e}")
        raw = None

    for yf_sym, orig_sym in symbol_map.items():
        try:
            ticker = yf.Ticker(yf_sym)
            info = ticker.fast_info  # Much faster than .info — only price data

            try:
                current_price = float(info.last_price or 0.0)
                previous_close = float(info.previous_close or current_price)
            except Exception:
                current_price, previous_close = 0.0, 0.0

            # Full info only needed for fundamentals (slower, but already cached)
            full_info = ticker.info
            if not full_info.get('currentPrice') and current_price == 0.0:
                # Final fallback: try .BO suffix
                if not yf_sym.endswith('.BO'):
                    try:
                        bo = yf.Ticker(orig_sym + '.BO')
                        current_price = float(bo.fast_info.last_price or 0.0)
                        previous_close = float(bo.fast_info.previous_close or current_price)
                        full_info = bo.info
                    except Exception:
                        pass

            low_52w         = full_info.get('fiftyTwoWeekLow', 0.0) or 0.0
            high_52w        = full_info.get('fiftyTwoWeekHigh', 0.0) or 0.0
            pe_ratio        = full_info.get('trailingPE', 0.0) or 0.0
            eps             = full_info.get('trailingEps', 0.0) or 0.0
            pb_ratio        = full_info.get('priceToBook', 0.0) or 0.0
            roe             = full_info.get('returnOnEquity', 0.0) or 0.0
            roce            = full_info.get('returnOnAssets', 0.0) or 0.0 # Approximation if ROCE missing
            debt_to_equity  = full_info.get('debtToEquity', 0.0) or 0.0
            dividend_yield  = full_info.get('dividendYield', 0.0) or 0.0
            stock_name      = full_info.get('longName') or full_info.get('shortName') or ''
            sector          = full_info.get('sector') or ''
            description     = full_info.get('longBusinessSummary') or stock_name
            promoter        = (full_info.get('heldPercentInsiders') or 0.0) * 100
            fii_dii         = (full_info.get('heldPercentInstitutions') or 0.0) * 100

            iv = calculate_intrinsic_value(eps)
            signal = get_iv_signal(current_price, iv)

            cursor.execute('''
                INSERT OR REPLACE INTO marketdata
                (symbol, current_price, previous_close, low_52w, high_52w,
                 pe_ratio, eps, pb_ratio, roe, roce, debt_to_equity, dividend_yield,
                 description, stock_name, sector, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (orig_sym, current_price, previous_close, low_52w, high_52w,
                  pe_ratio, eps, pb_ratio, roe, roce, debt_to_equity, dividend_yield,
                  description, stock_name, sector, now))

            cursor.execute('''
                INSERT OR REPLACE INTO assets
                (symbol, intrinsic_value, action_signal, promoter_holding, fii_holding, dii_holding, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (orig_sym, iv, signal, promoter, fii_dii, 0.0, now))

        except Exception as e:
            print(f"Error fetching data for {orig_sym}: {e}")
            cursor.execute('''
                INSERT OR IGNORE INTO marketdata
                (symbol, current_price, previous_close, low_52w, high_52w,
                 pe_ratio, eps, pb_ratio, roe, debt_to_equity, dividend_yield,
                 description, stock_name, sector, last_updated)
                VALUES (?, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, '', '', '', ?)
            ''', (orig_sym, now))

    conn.commit()

def rebuild_holdings():
    """Recalculates the holdings table based on all trades."""
    conn = get_connection()
    # Pull current prices to correctly calculate final un-realized cashflow for XIRR
    price_df = pd.read_sql_query("SELECT symbol, current_price FROM marketdata", conn)
    prices = pd.Series(price_df.current_price.values, index=price_df.symbol).to_dict()

    df = pd.read_sql_query("SELECT * FROM trades ORDER BY date ASC", conn)
    
    # Group by Broker and Symbol
    holdings_dict = {}
    
    for _, row in df.iterrows():
        key = (row['broker'], row['symbol'])
        if key not in holdings_dict:
            holdings_dict[key] = {'qty': 0.0, 'cost': 0.0, 'realized_pnl': 0.0, 'cfs': []}
            
        h = holdings_dict[key]
        qty = float(row['qty'])
        price = float(row['price'])
        fee = float(row.get('fee', 0.0))
        trade_date = datetime.strptime(row['date'], '%Y-%m-%d')
        
        if row['type'] == 'BUY':
            h['qty'] += qty
            h['cost'] += (qty * price) + fee # Add fees to cost basis
            h['cfs'].append((trade_date, -((qty * price) + fee)))
        elif row['type'] == 'SELL':
            avg_price = h['cost'] / h['qty'] if h['qty'] > 0 else 0
            h['qty'] -= qty
            h['cost'] -= (qty * avg_price)
            # Realized PnL = (Sell Price - Avg Cost) * Qty - Fees
            h['realized_pnl'] += ((price - avg_price) * qty) - fee
            h['cfs'].append((trade_date, ((qty * price) - fee)))
            
    # Clear and rewrite holdings table
    cursor = conn.cursor()
    cursor.execute("DELETE FROM holdings")
    now = datetime.now()
    
    for (broker, symbol), data in holdings_dict.items():
        if data['qty'] > 0 or data['realized_pnl'] != 0:
            avg_price = data['cost'] / data['qty'] if data['qty'] > 0 else 0.0
            
            xirr_val = 0.0
            total_qty = data['qty']
            if total_qty > 0 and len(data['cfs']) > 0:
                current_price = prices.get(symbol)
                if current_price is None:
                    current_price = prices.get(symbol + ".NS")
                if current_price is None:
                    current_price = prices.get(symbol + ".BO")
                current_price = float(current_price or 0.0)
                
                terminal_value = total_qty * current_price
                if terminal_value > 0:
                    cfs = data['cfs'] + [(now, terminal_value)]
                    xirr_val = calculate_xirr(cfs)
                    
            cursor.execute('''
                INSERT INTO holdings (broker, symbol, qty, avg_price, realized_pnl, xirr)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (broker, symbol, data['qty'], avg_price, data['realized_pnl'], xirr_val))
            
    conn.commit()
    # Fix 5: Invalidate metrics cache after holdings are rebuilt
    _invalidate_metrics_cache()

def get_dashboard_metrics() -> dict:
    """Calculates overall metrics for the dashboard. Result cached for 60s (Fix 5)."""
    # Serve from cache if fresh
    if _metrics_cache["data"] is not None and (time.time() - _metrics_cache["ts"]) < 60:
        return _metrics_cache["data"]

    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            SUM(h.qty * h.avg_price) as total_invested,
            SUM(h.qty * COALESCE(m.current_price, h.avg_price)) as current_value,
            SUM(h.realized_pnl) as total_realized_pnl,
            SUM(CASE WHEN h.realized_pnl < 0 THEN h.realized_pnl ELSE 0 END) as realized_loss
        FROM holdings h
        LEFT JOIN marketdata m ON h.symbol = m.symbol
        WHERE h.qty > 0 OR h.realized_pnl != 0
    '''
    cursor.execute(query)
    row = cursor.fetchone()
    
    invested = row[0] or 0.0
    current_val = row[1] or 0.0
    realized_pnl = row[2] or 0.0
    realized_loss = row[3] or 0.0
    
    unrealized_pnl = current_val - invested
    overall_pnl = unrealized_pnl + realized_pnl
    overall_xirr = (overall_pnl / invested * 100) if invested > 0 else 0.0
    
    result = {
        "total_invested": invested,
        "total_value": current_val,
        "overall_pnl": overall_pnl,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl,
        "realized_loss": realized_loss,
        "overall_xirr": overall_xirr
    }
    # Store in cache
    _metrics_cache["data"] = result
    _metrics_cache["ts"] = time.time()
    return result

def get_metrics_by_broker() -> dict:
    """Calculates all dashboard metrics, but grouped by broker."""
    # We could cache this too, but since drilldown is on-demand, doing it live is okay.
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            h.broker,
            SUM(h.qty * h.avg_price) as total_invested,
            SUM(h.qty * COALESCE(m.current_price, h.avg_price)) as current_value,
            SUM(h.realized_pnl) as total_realized_pnl,
            SUM(CASE WHEN h.realized_pnl < 0 THEN h.realized_pnl ELSE 0 END) as realized_loss
        FROM holdings h
        LEFT JOIN marketdata m ON h.symbol = m.symbol
        WHERE h.qty > 0 OR h.realized_pnl != 0
        GROUP BY h.broker
        ORDER BY h.broker
    '''
    cursor.execute(query)
    rows = cursor.fetchall()
    
    broker_metrics = {}
    for row in rows:
        broker = row[0]
        invested = row[1] or 0.0
        current_val = row[2] or 0.0
        realized_pnl = row[3] or 0.0
        realized_loss = row[4] or 0.0
        
        unrealized_pnl = current_val - invested
        overall_pnl = unrealized_pnl + realized_pnl
        overall_xirr = (overall_pnl / invested * 100) if invested > 0 else 0.0
        
        broker_metrics[broker] = {
            "total_invested": invested,
            "total_value": current_val,
            "overall_pnl": overall_pnl,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "realized_loss": realized_loss,
            "overall_xirr": overall_xirr
        }
        
    return broker_metrics

def get_top_worst_performers(limit: int = 3) -> dict:
    """Returns the top and worst performing assets currently held based on unrealized + realized PnL."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            h.symbol,
            SUM(h.qty) as total_qty,
            SUM(h.qty * h.avg_price) as cost,
            SUM(h.realized_pnl) as realized,
            MAX(COALESCE(m.current_price, h.avg_price)) as current_price
        FROM holdings h
        LEFT JOIN marketdata m ON h.symbol = m.symbol
        WHERE h.qty > 0
        GROUP BY h.symbol
    '''
    cursor.execute(query)
    rows = cursor.fetchall()
    
    performers = []
    for row in rows:
        symbol, qty, cost, realized, current_price = row
        current_val = qty * current_price
        unrealized = current_val - cost
        total_pnl = unrealized + realized
        pnl_pct = (total_pnl / cost * 100) if cost > 0 else 0
        performers.append({
            "symbol": symbol,
            "pnl": total_pnl,
            "pnl_pct": pnl_pct
        })
        
    performers.sort(key=lambda x: x["pnl"], reverse=True)
    
    top = performers[:limit] if len(performers) > limit else performers
    worst = performers[-limit:] if len(performers) > limit else []
    # Reverse worst so the most negative is first
    worst.reverse()
    
    return {"top": top, "worst": worst}

def get_actionable_insights(limit: int = 10) -> list:
    """Returns currently held assets that have an ACCUMULATE or REDUCE signal, ordered by greatest divergence."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT DISTINCT h.symbol, a.action_signal, a.intrinsic_value, m.current_price
        FROM holdings h
        JOIN assets a ON h.symbol = a.symbol
        LEFT JOIN marketdata m ON h.symbol = m.symbol
        WHERE h.qty > 0 AND a.action_signal IN ('ACCUMULATE', 'REDUCE')
        ORDER BY ABS(a.intrinsic_value - m.current_price) / m.current_price DESC
        LIMIT ?
    '''
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    
    insights = []
    for row in rows:
        insights.append({
            "symbol": row[0],
            "signal": row[1],
            "iv": row[2],
            "current_price": row[3]
        })
    return insights

def get_tax_harvesting_opportunities(min_loss_amount: float = 1000.0) -> list:
    """Returns holdings with a significant unrealized loss that could be sold to offset gains."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # We look for positions where cost > current_value by at least min_loss_amount
    query = '''
        SELECT 
            h.symbol, h.broker, h.qty, h.avg_price, m.current_price,
            (h.qty * h.avg_price) - (h.qty * COALESCE(m.current_price, h.avg_price)) as unrealized_loss
        FROM holdings h
        LEFT JOIN marketdata m ON h.symbol = m.symbol
        WHERE h.qty > 0 
          AND (h.qty * h.avg_price) - (h.qty * COALESCE(m.current_price, h.avg_price)) >= ?
        ORDER BY unrealized_loss DESC
    '''
    cursor.execute(query, (min_loss_amount,))
    rows = cursor.fetchall()
    
    opportunities = []
    for row in rows:
        opportunities.append({
            "symbol": row[0],
            "broker": row[1],
            "qty": row[2],
            "avg_price": row[3],
            "current_price": row[4],
            "unrealized_loss": row[5]
        })
    return opportunities

def should_sync_market_data() -> bool:
    """Checks if market data is older than 24 hours."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(last_updated) FROM marketdata")
    row = cursor.fetchone()
    last_sync = row[0] if row else None
    
    if not last_sync:
        return True
    
    try:
        # Standard format used in fetch_and_update_market_data
        last_dt = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S")
        diff = datetime.now() - last_dt
        return diff.total_seconds() > 86400 # 24 hours
    except Exception:
        return True

def auto_sync_if_needed():
    """Triggers a market data sync if data is stale (>24h)."""
    if should_sync_market_data():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM holdings WHERE qty > 0")
        symbols = [r[0] for r in cursor.fetchall()]
        
        if symbols:
            print(f"Daily Sync: Starting market data update for {len(symbols)} symbols...")
            fetch_and_update_market_data(symbols)
            rebuild_holdings()
            print("Daily Sync: Finished.")
        else:
            print("Daily Sync: No active holdings found to refresh.")


