import yfinance as yf
from database import db_session
from datetime import datetime
import pandas as pd
import time
import concurrent.futures

# ── 60-second dashboard metrics cache ───────────────────────────────────────
_metrics_cache: dict = {"data": None, "ts": 0.0}

# ── Cache for expensive UI queries (30-60 second TTL) ─────────────────────
_performers_cache: dict = {"data": None, "ts": 0.0}
_insights_cache: dict = {"data": None, "ts": 0.0}
_harvesting_cache: dict = {"data": None, "ts": 0.0}

def _invalidate_metrics_cache():
    _metrics_cache["ts"] = 0.0

def _invalidate_performers_cache():
    _performers_cache["ts"] = 0.0

def _invalidate_insights_cache():
    _insights_cache["ts"] = 0.0

def _invalidate_harvesting_cache():
    _harvesting_cache["ts"] = 0.0

def invalidate_all_caches():
    """Invalidate all UI caches when data changes."""
    _invalidate_metrics_cache()
    _invalidate_performers_cache()
    _invalidate_insights_cache()
    _invalidate_harvesting_cache()

def save_dashboard_metrics(metrics: dict):
    """Persists dashboard metrics to the database."""
    with db_session() as conn:
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        records = [(k, v, now) for k, v in metrics.items() if isinstance(v, (int, float))]
        cursor.executemany("INSERT OR REPLACE INTO dashboard_metrics (metric_key, metric_value, last_updated) VALUES (?, ?, ?)", records)

def get_stored_dashboard_metrics() -> dict | None:
    """Retrieves cached dashboard metrics from the database."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT metric_key, metric_value FROM dashboard_metrics")
        rows = cursor.fetchall()
        if not rows: return None
        return {row[0]: row[1] for row in rows}

def calculate_trade_fees(trade_type: str, qty: float, price: float, is_delivery: bool = True) -> float:
    """
    Calculates total fees based on Indian stock market rules.
    
    Breakdown:
    - Brokerage: 0.03% of turnover (or flat ₹20 minimum)
    - SEBI charges: 0.0001% of turnover (₹1 per crore)
    - Stamp duty: 0.015% on BUY, 0.001% on SELL
    - DP charges: ₹15.34 on SELL (delivery holding charges)
    - GST: 18% on all charges except stamp duty
    """
    trade_type = trade_type.upper()
    turnover = qty * price
    
    # Brokerage: 0.03% with ₹20 minimum
    brokerage = max(turnover * 0.0003, 20.0) if is_delivery else turnover * 0.0001
    
    # SEBI charges: ₹1 per crore
    sebi_charges = max(turnover / 10000000, 1.0)  # ₹1 per ₹1 crore
    
    # Stamp duty: 0.015% on BUY, 0.001% on SELL
    stamp_duty = 0.0
    if trade_type == 'BUY':
        stamp_duty = turnover * 0.00015  # 0.015%
    elif trade_type == 'SELL':
        stamp_duty = turnover * 0.00001  # 0.001%
    
    # DP (Depository Participant) charges: ₹15.34 on SELL only
    dp_charges = 0.0
    if trade_type == 'SELL' and is_delivery:
        dp_charges = 15.34
    
    # GST: 18% on (brokerage + SEBI + DP charges), NOT on stamp duty
    taxable_amount = brokerage + sebi_charges + dp_charges
    gst = taxable_amount * 0.18
    
    total_fees = brokerage + sebi_charges + stamp_duty + gst + dp_charges
    return round(total_fees, 2)

def calculate_intrinsic_value(eps: float, growth_rate: float = 0.12, discount_rate: float = 0.10, terminal_multiple: float = 15.0) -> float:
    """Calculates Intrinsic Value using a 5-year DCF snapshot."""
    if pd.isna(eps) or eps <= 0:
        return 0.0
        
    cash_flows = []
    current_eps = eps
    for _ in range(5):
        current_eps *= (1 + growth_rate)
        cash_flows.append(current_eps)
        
    terminal_value = cash_flows[-1] * terminal_multiple
    
    iv = 0.0
    for i, cf in enumerate(cash_flows, start=1):
        iv += cf / ((1 + discount_rate) ** i)
        
    iv += terminal_value / ((1 + discount_rate) ** 5)
    return round(iv, 2)

def calculate_xirr(cashflows, guesses=[0.1, 0.0, -0.5, -0.9, 0.5], max_iter=100, tol=1e-4) -> float:
    """Calculates internal rate of return using Newton-Raphson."""
    if not cashflows: return 0.0
    
    cashflows.sort(key=lambda x: x[0])
    dates = [cf[0] for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]
    
    if min(amounts) >= 0 or max(amounts) <= 0:
        return 0.0
        
    for guess in guesses:
        rate = guess
        for _ in range(max_iter):
            if rate <= -0.999: rate = -0.999
            if rate > 100.0: rate = 100.0
            try:
                v = sum(amt / ((1 + rate) ** ((date - dates[0]).days / 365.25)) for date, amt in cashflows)
                if abs(v) < tol: return round(rate * 100, 2)
                
                deriv = sum(
                    -((date - dates[0]).days / 365.25) * amt / ((1 + rate) ** (((date - dates[0]).days / 365.25) + 1))
                    for date, amt in cashflows
                )
                if deriv == 0: break
                rate -= v / deriv
            except (OverflowError, ZeroDivisionError):
                break 
    return 0.0 

def get_iv_signal(current_price: float, iv: float) -> str:
    """Calculates action signal based on Intrinsic Value."""
    if iv <= 0 or current_price <= 0: return "N/A"
    if current_price < (0.70 * iv): return "ACCUMULATE"
    elif current_price > (1.10 * iv): return "REDUCE"
    else: return "HOLD"

# ── Parallel Network Fetching Logic ──────────────────────────────────────────

def _fetch_single_ticker(yf_sym: str, orig_sym: str, now: str):
    """Fetches a single ticker's data from yfinance. Runs isolated in a thread."""
    try:
        ticker = yf.Ticker(yf_sym)
        # Fast info avoids massive payload downloads where possible
        fast_info = ticker.fast_info
        
        current_price = float(getattr(fast_info, 'last_price', 0.0) or 0.0)
        previous_close = float(getattr(fast_info, 'previous_close', current_price) or current_price)
        
        # Trigger full info fetch (this is the blocking network call)
        full_info = ticker.info
        
        # Fallback to .BO if .NS fails to yield a price
        if not full_info.get('currentPrice') and current_price == 0.0 and not yf_sym.endswith('.BO'):
            try:
                bo = yf.Ticker(orig_sym + '.BO')
                current_price = float(getattr(bo.fast_info, 'last_price', 0.0) or 0.0)
                previous_close = float(getattr(bo.fast_info, 'previous_close', current_price) or current_price)
                full_info = bo.info
            except Exception:
                pass

        eps = float(full_info.get('trailingEps', 0.0) or 0.0)
        iv = calculate_intrinsic_value(eps)
        signal = get_iv_signal(current_price, iv)

        mkt_row = (
            orig_sym, current_price, previous_close, 
            float(full_info.get('fiftyTwoWeekLow', 0.0) or 0.0),
            float(full_info.get('fiftyTwoWeekHigh', 0.0) or 0.0),
            float(full_info.get('trailingPE', 0.0) or 0.0),
            eps,
            float(full_info.get('priceToBook', 0.0) or 0.0),
            float(full_info.get('returnOnEquity', 0.0) or 0.0),
            float(full_info.get('returnOnAssets', 0.0) or 0.0),
            float(full_info.get('debtToEquity', 0.0) or 0.0),
            float(full_info.get('dividendYield', 0.0) or 0.0),
            full_info.get('longBusinessSummary') or full_info.get('longName') or '',
            full_info.get('longName') or full_info.get('shortName') or '',
            full_info.get('sector') or '',
            now
        )
        
        asset_row = (
            orig_sym, iv, signal, 
            float((full_info.get('heldPercentInsiders') or 0.0) * 100),
            float((full_info.get('heldPercentInstitutions') or 0.0) * 100),
            0.0, now
        )
        
        return mkt_row, asset_row
    
    except Exception as e:
        print(f"Error fetching data for {orig_sym}: {e}")
        # Return a safe blank record so the app doesn't crash on this symbol
        mkt_row = (orig_sym, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, '', '', '', now)
        asset_row = (orig_sym, 0.0, "N/A", 0.0, 0.0, 0.0, now)
        return mkt_row, asset_row

def fetch_and_update_market_data(symbols: list):
    """
    Fetches real-time data from yfinance concurrently to prevent UI freezing.
    Writes to the database in one lightning-fast bulk transaction.
    """
    if not symbols: return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    yf_symbols = [s + ".NS" if not s.endswith(('.NS', '.BO')) else s for s in symbols]
    
    marketdata_records = []
    assets_records = []

    # 1. Fetch from network concurrently (10 at a time)
    # This prevents the UI from freezing sequentially over 30 seconds
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for yf_sym, orig_sym in zip(yf_symbols, symbols):
            futures.append(executor.submit(_fetch_single_ticker, yf_sym, orig_sym, now))
            
        for future in concurrent.futures.as_completed(futures):
            m_row, a_row = future.result()
            marketdata_records.append(m_row)
            assets_records.append(a_row)

    # 2. Write to DB in a fraction of a second
    # Separating DB from Network prevents "database is locked" errors entirely
    with db_session() as conn:
        cursor = conn.cursor()
        
        cursor.executemany('''
            INSERT OR REPLACE INTO marketdata
            (symbol, current_price, previous_close, low_52w, high_52w,
             pe_ratio, eps, pb_ratio, roe, roce, debt_to_equity, dividend_yield,
             description, stock_name, sector, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', marketdata_records)

        cursor.executemany('''
            INSERT OR REPLACE INTO assets
            (symbol, intrinsic_value, action_signal, promoter_holding, fii_holding, dii_holding, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', assets_records)


# ── Database Rebuild Logic ───────────────────────────────────────────────────

def rebuild_holdings():
    """Recalculates the holdings table based on all trades.
    Uses stored fees from trades - does NOT recalculate fees.
    Fees are only calculated when trades are entered/imported or amended.
    """
    with db_session() as conn:
        price_df = pd.read_sql_query("SELECT symbol, current_price FROM marketdata", conn)
        prices = pd.Series(price_df.current_price.values, index=price_df.symbol).to_dict()

        df = pd.read_sql_query("SELECT * FROM trades ORDER BY date ASC", conn)
        holdings_dict = {}
    
        for row in df.itertuples(index=False):
            row_dict = row._asdict()
            key = (row_dict['broker'], row_dict['symbol'])
            if key not in holdings_dict:
                holdings_dict[key] = {'qty': 0.0, 'cost': 0.0, 'realized_pnl': 0.0, 'cfs': [], 'earliest_date': row_dict['date'], 'total_fees': 0.0}
                
            h = holdings_dict[key]
            qty, price = float(row_dict['qty']), float(row_dict['price'])
            t_type = row_dict['type']
            fee = float(row_dict.get('fee', 0.0) or 0.0)  # Use stored fee, don't recalculate
            
            trade_date_str = row_dict['date']
            trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d')
            if trade_date_str < h['earliest_date']:
                h['earliest_date'] = trade_date_str

            h['total_fees'] += fee
            
            if t_type == 'BUY':
                h['qty'] += qty
                h['cost'] += (qty * price) + fee
                h['cfs'].append((trade_date, -((qty * price) + fee)))
            elif t_type == 'SELL':
                avg_price = h['cost'] / h['qty'] if h['qty'] > 0 else 0
                h['qty'] -= qty
                h['cost'] -= (qty * avg_price)
                h['realized_pnl'] += ((price - avg_price) * qty) - fee
                h['cfs'].append((trade_date, ((qty * price) - fee)))
                
        now = datetime.now()
        records_to_insert = []
        
        for (broker, symbol), data in holdings_dict.items():
            avg_price = 0.0
            xirr_val = 0.0
            cagr_val = 0.0
            unrealized_pnl = 0.0
            running_pnl = 0.0

            if data['qty'] > 0 or data['realized_pnl'] != 0 or data['total_fees'] > 0:
                avg_price = data['cost'] / data['qty'] if data['qty'] > 0 else 0.0
                
                if data['qty'] > 0 and len(data['cfs']) > 0:
                    current_price = prices.get(symbol) or prices.get(symbol + ".NS") or prices.get(symbol + ".BO") or 0.0
                    terminal_value = data['qty'] * float(current_price)
                    if terminal_value > 0:
                        # Calculate unrealized PnL for active holdings
                        unrealized_pnl = (float(current_price) - avg_price) * data['qty']
                        # Running PnL = Realized (from SELL trades) + Unrealized (from active holdings)
                        running_pnl = data['realized_pnl'] + unrealized_pnl
                        
                        # XIRR
                        cfs = data['cfs'] + [(now, terminal_value)]
                        xirr_val = calculate_xirr(cfs)
                        
                        # CAGR
                        try:
                            start_dt = datetime.strptime(data['earliest_date'], '%Y-%m-%d')
                            years = (now - start_dt).days / 365.25
                            if years > 0:
                                invested = data['cost']
                                total_return_val = terminal_value + data['realized_pnl']
                                if invested > 0:
                                    ratio = total_return_val / invested
                                    if ratio > 0:
                                        cagr_val = (ratio ** (1/years) - 1) * 100
                                    else:
                                        cagr_val = -100.0
                        except Exception: pass
                else:
                    # For closed positions (qty = 0), running_pnl = realized_pnl only
                    running_pnl = data['realized_pnl']
                        
            records_to_insert.append((broker, symbol, data['qty'], avg_price, data['realized_pnl'], running_pnl, xirr_val, cagr_val, data['earliest_date'], data['total_fees']))
                
        
        # Rebuild holdings table (using stored fees, not recalculating)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM holdings")
        cursor.executemany('''
            INSERT INTO holdings (broker, symbol, qty, avg_price, realized_pnl, running_pnl, xirr, cagr, earliest_date, total_fees)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', records_to_insert)
    
    # After rebuilding holdings, also update and save dashboard metrics
    new_metrics = get_dashboard_metrics(force_refresh=True)
    save_dashboard_metrics(new_metrics)
    _invalidate_metrics_cache()


# ── Metric Retrievers ────────────────────────────────────────────────────────

def get_dashboard_metrics(force_refresh: bool = False) -> dict:
    # 1. Check in-memory cache
    if not force_refresh and _metrics_cache["data"] is not None and (time.time() - _metrics_cache["ts"]) < 60:
        return _metrics_cache["data"]

    # 2. Check DB stored metrics if not forcing a recalc
    if not force_refresh:
        stored = get_stored_dashboard_metrics()
        if stored:
            _metrics_cache["data"], _metrics_cache["ts"] = stored, time.time()
            return stored

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                SUM(h.qty * h.avg_price),
                SUM(h.qty * COALESCE(m.current_price, h.avg_price)),
                SUM(h.running_pnl),
                SUM(CASE WHEN h.running_pnl < 0 THEN h.running_pnl ELSE 0 END),
                MIN(h.earliest_date)
            FROM holdings h
            LEFT JOIN marketdata m ON h.symbol = m.symbol
            WHERE h.qty > 0 OR h.running_pnl != 0
        ''')
        row = cursor.fetchone()
    
    invested, current_val = row[0] or 0.0, row[1] or 0.0
    overall_pnl = row[2] or 0.0
    overall_loss = row[3] or 0.0
    earliest_date = row[4]
    
    # For backward compatibility, calculate realized and unrealized from current market values
    unrealized_pnl = current_val - invested
    realized_pnl = overall_pnl - unrealized_pnl
    realized_loss = overall_loss
    
    overall_xirr = (overall_pnl / invested * 100) if invested > 0 else 0.0

    overall_cagr = 0.0
    if invested > 0 and earliest_date:
        try:
            days = (datetime.now() - datetime.strptime(earliest_date, '%Y-%m-%d')).days
            years = max(days / 365.25, 0.001)
            total_ret = (invested + overall_pnl) / invested
            if total_ret > 0:
                overall_cagr = (total_ret ** (1 / years) - 1) * 100
        except Exception:
            pass
    
    result = {
        "total_invested": invested, "total_value": current_val,
        "overall_pnl": overall_pnl, "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl, "realized_loss": realized_loss,
        "overall_xirr": overall_xirr, "overall_cagr": overall_cagr
    }
    _metrics_cache["data"], _metrics_cache["ts"] = result, time.time()
    return result

def get_metrics_by_broker() -> dict:
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT h.broker, SUM(h.qty * h.avg_price), SUM(h.qty * COALESCE(m.current_price, h.avg_price)),
                   SUM(h.running_pnl), SUM(CASE WHEN h.running_pnl < 0 THEN h.running_pnl ELSE 0 END),
                   MIN(h.earliest_date)
            FROM holdings h
            LEFT JOIN marketdata m ON h.symbol = m.symbol
            WHERE h.qty > 0 OR h.running_pnl != 0
            GROUP BY h.broker
        ''')
        rows = cursor.fetchall()
    
    broker_metrics = {}
    for row in rows:
        invested, current_val = row[1] or 0.0, row[2] or 0.0
        overall_pnl, overall_loss = row[3] or 0.0, row[4] or 0.0
        earliest_date = row[5]
        
        unrealized_pnl = current_val - invested
        realized_pnl = overall_pnl - unrealized_pnl
        overall_xirr = (overall_pnl / invested * 100) if invested > 0 else 0.0
        
        overall_cagr = 0.0
        if invested > 0 and earliest_date:
            try:
                days = (datetime.now() - datetime.strptime(earliest_date, '%Y-%m-%d')).days
                years = max(days / 365.25, 0.001)
                total_ret = (invested + overall_pnl) / invested
                if total_ret > 0:
                    overall_cagr = (total_ret ** (1 / years) - 1) * 100
            except Exception:
                pass

        broker_metrics[row[0]] = {
            "total_invested": invested, "total_value": current_val,
            "overall_pnl": overall_pnl, "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl, "realized_loss": overall_loss,
            "overall_xirr": overall_xirr, "overall_cagr": overall_cagr
        }
    return broker_metrics

def get_top_worst_performers(limit: int = 3) -> dict:
    # Check cache first (30-second TTL)
    if _performers_cache["data"] is not None and (time.time() - _performers_cache["ts"]) < 30:
        return _performers_cache["data"]
    
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT h.symbol, SUM(h.qty), SUM(h.qty * h.avg_price), SUM(h.realized_pnl),
                   MAX(COALESCE(m.current_price, h.avg_price))
            FROM holdings h LEFT JOIN marketdata m ON h.symbol = m.symbol
            WHERE h.qty > 0 GROUP BY h.symbol
        ''')
        rows = cursor.fetchall()
    
    performers = []
    for row in rows:
        cost, total_pnl = row[2], (row[1] * row[4] - row[2]) + row[3]
        performers.append({"symbol": row[0], "pnl": total_pnl, "pnl_pct": (total_pnl / cost * 100) if cost > 0 else 0})
        
    performers.sort(key=lambda x: x["pnl"], reverse=True)
    result = {
        "top": performers[:limit], 
        "worst": list(reversed(performers[-limit:])) if performers else []
    }
    _performers_cache["data"], _performers_cache["ts"] = result, time.time()
    return result

def get_actionable_insights(limit: int = 10) -> list:
    # Check cache first (30-second TTL)
    if _insights_cache["data"] is not None and (time.time() - _insights_cache["ts"]) < 30:
        return _insights_cache["data"]
    
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT h.symbol, a.action_signal, a.intrinsic_value, m.current_price
            FROM holdings h JOIN assets a ON h.symbol = a.symbol
            LEFT JOIN marketdata m ON h.symbol = m.symbol
            WHERE h.qty > 0 AND a.action_signal IN ('ACCUMULATE', 'REDUCE')
            ORDER BY ABS(a.intrinsic_value - m.current_price) / m.current_price DESC LIMIT ?
        ''', (limit,))
        result = [{"symbol": r[0], "signal": r[1], "iv": r[2], "current_price": r[3]} for r in cursor.fetchall()]
    
    _insights_cache["data"], _insights_cache["ts"] = result, time.time()
    return result

def get_tax_harvesting_opportunities(min_loss_amount: float = 1000.0) -> list:
    # Check cache first (60-second TTL for this expensive query)
    cache_key = f"harvesting_{min_loss_amount}"
    if _harvesting_cache["data"] is not None and (time.time() - _harvesting_cache["ts"]) < 60:
        return _harvesting_cache["data"]
    
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT h.symbol, h.broker, h.qty, h.avg_price, m.current_price,
                   (h.qty * h.avg_price) - (h.qty * COALESCE(m.current_price, h.avg_price)) as unrealized_loss
            FROM holdings h LEFT JOIN marketdata m ON h.symbol = m.symbol
            WHERE h.qty > 0 AND (h.qty * h.avg_price) - (h.qty * COALESCE(m.current_price, h.avg_price)) >= ?
            ORDER BY unrealized_loss DESC
        ''', (min_loss_amount,))
        result = [{"symbol": r[0], "broker": r[1], "qty": r[2], "avg_price": r[3], "current_price": r[4], "unrealized_loss": r[5]} for r in cursor.fetchall()]
    
    _harvesting_cache["data"], _harvesting_cache["ts"] = result, time.time()
    return result

def auto_sync_if_needed():
    """
    Intentionally disabled by user request. 
    Market data will only refresh manually via Dashboard/Holdings views.
    """
    pass

def should_sync_market_data() -> bool:
    return False