import flet as ft
import pandas as pd
import time
from database import db_session
from components.ui_elements import drilldown_stock_header, drilldown_trade_stats, drilldown_metric_card

_drilldown_cache: dict = {}
_CACHE_TTL = 30  

def _get_drilldown_data(symbol: str, broker: str | None):
    key = (symbol, broker or "All")
    cached = _drilldown_cache.get(key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["df"], cached["m_row"]

    with db_session() as conn:
        if broker and broker != "All":
            df = pd.read_sql_query(
                "SELECT * FROM trades WHERE broker = ? AND symbol = ? ORDER BY date ASC",
                conn, params=[broker, symbol]
            )
        else:
            df = pd.read_sql_query(
                "SELECT * FROM trades WHERE symbol = ? ORDER BY date ASC",
                conn, params=[symbol]
            )

        m_query = '''
            SELECT m.sector, m.description, m.current_price, m.stock_name,
                   m.pe_ratio, m.eps, m.pb_ratio, m.roe, m.debt_to_equity, m.dividend_yield,
                   m.high_52w, m.low_52w, a.intrinsic_value
            FROM marketdata m
            LEFT JOIN assets a ON m.symbol = a.symbol
            WHERE m.symbol = ?
        '''
        m_row = conn.execute(m_query, (symbol,)).fetchone()
    
    _drilldown_cache[key] = {"df": df, "m_row": m_row, "ts": time.time()}
    return df, m_row

def show_drilldown_dialog(app_state, symbol: str, broker: str = None):
    broker_text = f"Trades via {broker}" if (broker and broker != "All") else "All Trades"
    df, m_row = _get_drilldown_data(symbol, broker)

    sector = m_row[0] if m_row and m_row[0] else ""
    description = m_row[1] if m_row and m_row[1] else "No description available."
    current_price = float(m_row[2]) if m_row and m_row[2] else 0.0
    stock_name = m_row[3] if m_row and m_row[3] else symbol

    pe_ratio = f"{m_row[4]:.2f}" if m_row and m_row[4] else "—"
    eps = f"₹{m_row[5]:.2f}" if m_row and m_row[5] else "—"
    pb_ratio = f"{m_row[6]:.2f}" if m_row and m_row[6] else "—"
    roe = f"{m_row[7] * 100:.2f}%" if m_row and m_row[7] else "—"
    debt_to_equity = f"{m_row[8]:.2f}" if m_row and m_row[8] else "—"
    div_yield = f"{m_row[9] * 100:.2f}%" if m_row and m_row[9] else "—"
    high_52w = f"₹{m_row[10]:.2f}" if m_row and m_row[10] else "—"
    low_52w = f"₹{m_row[11]:.2f}" if m_row and m_row[11] else "—"
    intrinsic_val = f"₹{m_row[12]:.2f}" if m_row and m_row[12] else "—"

    rows = []
    running_qty = 0.0
    running_cost = 0.0
    running_pnl = 0.0
    total_shares_held = 0.0
    total_invested = 0.0
    buy_trades = 0
    sell_trades = 0

    for _, row in df.iterrows():
        qty = float(row['qty'])
        price = float(row['price'])
        fee = float(row.get('fee', 0.0))
        t_type = row['type']
        pnl_for_trade = 0.0
        is_unrealized = False

        if t_type == 'BUY':
            running_qty += qty
            running_cost += (qty * price) + fee
            total_shares_held = running_qty
            total_invested = running_cost
            buy_trades += 1
            running_avg = running_cost / running_qty if running_qty > 0 else price
            if current_price > 0:
                pnl_for_trade = (current_price - running_avg) * running_qty
                is_unrealized = True
        elif t_type == 'SELL':
            avg_price = running_cost / running_qty if running_qty > 0 else 0
            running_qty -= qty
            running_cost -= (qty * avg_price)
            total_shares_held = running_qty
            pnl_for_trade = ((price - avg_price) * qty) - fee
            running_pnl += pnl_for_trade
            sell_trades += 1
            is_unrealized = False

        pnl_text = f"₹{pnl_for_trade:,.2f}"
        if is_unrealized: pnl_text += " (U)"

        current_running_unrealized = 0.0
        if running_qty > 0 and current_price > 0:
            current_avg_cost = running_cost / running_qty
            current_running_unrealized = (current_price - current_avg_cost) * running_qty
            
        display_running_pnl = running_pnl + current_running_unrealized

        cells = [
            ft.DataCell(ft.Text("?", color=ft.Colors.GREY_500)), 
            ft.DataCell(ft.Text(row['date'])),
        ]
        if not broker or broker == "All":
             cells.append(ft.DataCell(ft.Text(row['broker'])))
        
        # Color text based on BUY/SELL for better visual appeal
        row_text_color = "#10B981" if t_type == 'BUY' else "#EF4444"
             
        cells.extend([
            ft.DataCell(ft.Text(t_type, color=ft.Colors.GREEN if t_type == 'BUY' else ft.Colors.RED, weight=ft.FontWeight.BOLD)),
            ft.DataCell(ft.Text(f"{qty:,.0f}", color=row_text_color)),
            ft.DataCell(ft.Text(f"₹{price:,.2f}", color=row_text_color)),
            ft.DataCell(ft.Text(f"₹{fee:,.2f}", color=row_text_color)),
            ft.DataCell(
                ft.Text(pnl_text, color=ft.Colors.GREEN if pnl_for_trade >= 0 else ft.Colors.RED, weight=ft.FontWeight.W_600)
                if t_type == 'SELL' or (t_type == 'BUY' and current_price > 0) else ft.Text("—")
            ),
            ft.DataCell(ft.Text(f"{running_qty:,.0f}", color=row_text_color)),
            ft.DataCell(ft.Text(f"₹{display_running_pnl:,.2f}", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN if display_running_pnl >= 0 else ft.Colors.RED))
        ])
        
        # No background color - use text color instead for better appeal
        data_row = ft.DataRow(cells=cells)
        rows.append(data_row)

    rows.reverse()
    for idx, r in enumerate(rows, start=1):
        r.cells[0] = ft.DataCell(ft.Text(str(idx), color=ft.Colors.GREY_500))

    columns = [
        ft.DataColumn(ft.Text("#")),
        ft.DataColumn(ft.Text("Date")),
    ]
    if not broker or broker == "All":
        columns.append(ft.DataColumn(ft.Text("Broker")))
        
    columns.extend([
        ft.DataColumn(ft.Text("Type")),
        ft.DataColumn(ft.Text("Qty")),
        ft.DataColumn(ft.Text("Price")),
        ft.DataColumn(ft.Text("Fees")),
        ft.DataColumn(ft.Text("Trade PnL")),
        ft.DataColumn(ft.Text("Running Qty")),
        ft.DataColumn(ft.Text("Running PnL")),
    ])

    table = ft.DataTable(columns=columns, rows=rows)

    def copy_to_clipboard(e):
        copy_df = df.copy()
        if not broker or broker == "All":
            cols_to_keep = ['date', 'broker', 'type', 'qty', 'price', 'fee']
        else:
            cols_to_keep = ['date', 'type', 'qty', 'price', 'fee']
            
        tsv_data = copy_df[cols_to_keep].to_csv(sep='\t', index=False)
        try:
            import subprocess, sys
            if sys.platform == "darwin": subprocess.run("pbcopy", input=tsv_data.encode(), check=True)
            elif sys.platform == "win32": subprocess.run("clip", input=tsv_data.encode(), check=True, shell=True)
            else: subprocess.run(["xclip", "-selection", "clipboard"], input=tsv_data.encode(), check=True)
            msg = "Trade history copied to clipboard!"
        except Exception as ex:
            msg = f"Copy failed: {ex}"

        sb = ft.SnackBar(ft.Text(msg))
        app_state.page.snack_bar = sb
        sb.open = True
        try:
            sb.update()  # Targeted update on snack bar only
        except Exception: pass

    history_container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(broker_text, weight=ft.FontWeight.W_500),
                ft.IconButton(icon=ft.Icons.CONTENT_COPY, tooltip="Copy to Clipboard", icon_color=ft.Colors.BLUE_300, icon_size=18, on_click=copy_to_clipboard)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(content=ft.Row([table], scroll=ft.ScrollMode.ADAPTIVE), expand=True)
        ], scroll=ft.ScrollMode.ADAPTIVE),
        visible=True, padding=ft.padding.only(top=15, bottom=10), expand=True
    )

    def make_metric_card(title, value, color=ft.Colors.WHITE):
        return drilldown_metric_card(title, value, color)

    fundamentals_container = ft.Container(
        content=ft.Column([
            ft.Text("Company Overview", size=13, weight=ft.FontWeight.BOLD, color="#3B82F6"),
            ft.Text(description, size=11, color="#9CA3AF"),
            ft.Divider(height=15, color="transparent"),
            
            ft.Text("Valuation Metrics", size=13, weight=ft.FontWeight.BOLD, color="#3B82F6"),
            ft.Row([
                drilldown_metric_card("P/E Ratio", pe_ratio),
                drilldown_metric_card("EPS (TTM)", eps),
                drilldown_metric_card("P/B Ratio", pb_ratio),
            ]),
            
            ft.Row([
                drilldown_metric_card("ROE", roe, "#10B981" if "—" not in str(roe) and float(str(roe).strip('%')) > 15 else "#E5E7EB"),
                drilldown_metric_card("Debt/Equity", debt_to_equity, "#EF4444" if "—" not in str(debt_to_equity) and float(str(debt_to_equity)) > 1 else "#E5E7EB"),
                drilldown_metric_card("Div Yield", div_yield, "#06B6D4"),
            ]),
            
            ft.Divider(height=15, color="transparent"),
            ft.Text("Price Action", size=13, weight=ft.FontWeight.BOLD, color="#3B82F6"),
            ft.Row([
                drilldown_metric_card("52W High", high_52w),
                drilldown_metric_card("52W Low", low_52w),
                drilldown_metric_card("Intrinsic Value", intrinsic_val, "#A78BFA"),
            ])
        ], scroll=ft.ScrollMode.ADAPTIVE, spacing=8),
        visible=False, padding=10, expand=True
    )

    def switch_tab(e):
        is_history = e.control.data == "history"
        history_container.visible = is_history
        fundamentals_container.visible = not is_history
        btn_history.style = ft.ButtonStyle(color=ft.Colors.BLUE_300 if is_history else ft.Colors.WHITE70, bgcolor=ft.Colors.BLUE_900 if is_history else ft.Colors.TRANSPARENT)
        btn_fundamentals.style = ft.ButtonStyle(color=ft.Colors.BLUE_300 if not is_history else ft.Colors.WHITE70, bgcolor=ft.Colors.BLUE_900 if not is_history else ft.Colors.TRANSPARENT)
        history_container.update(); fundamentals_container.update(); btn_history.update(); btn_fundamentals.update()

    btn_history = ft.TextButton("Trade History", data="history", style=ft.ButtonStyle(color=ft.Colors.BLUE_300, bgcolor=ft.Colors.BLUE_900), on_click=switch_tab)
    btn_fundamentals = ft.TextButton("Fundamentals", data="fundamentals", style=ft.ButtonStyle(color=ft.Colors.WHITE70), on_click=switch_tab)
    tab_row = ft.Row([btn_history, btn_fundamentals], spacing=10)

    def close_dlg(e):
        try:
            dlg.open = False
            dlg.update()  # Targeted update on dialog only
        except Exception: pass

    # Create header and stats cards
    stock_header = drilldown_stock_header(symbol, stock_name, sector, current_price)
    trade_stats = drilldown_trade_stats(buy_trades + sell_trades, total_shares_held, total_invested, running_pnl)

    dlg = ft.AlertDialog(
        title=ft.Text(f"{stock_name} ({symbol})", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column([
                stock_header,
                trade_stats,
                ft.Divider(height=12, color="#334155"),
                tab_row, 
                ft.Divider(height=8, color="#27F5B0"), 
                history_container, 
                fundamentals_container
            ], spacing=0, expand=True),
            width=900, height=550, padding=10
        ),
        actions=[ft.TextButton("Close", on_click=close_dlg)]
    )
    
    app_state.page.show_dialog(dlg)