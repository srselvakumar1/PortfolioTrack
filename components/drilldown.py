import flet as ft
import pandas as pd
import time
from database import get_connection

# Fix 8: 30-second TTL cache for drilldown DB queries
_drilldown_cache: dict = {}
_CACHE_TTL = 30  # seconds

def _get_drilldown_data(symbol: str, broker: str | None):
    """Fetch (df, m_row) from cache or DB."""
    key = (symbol, broker or "All")
    cached = _drilldown_cache.get(key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["df"], cached["m_row"]

    conn = get_connection()
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

    # Fix 8: Use cached data (30s TTL) instead of a fresh DB query each open
    df, m_row = _get_drilldown_data(symbol, broker)

    sector = m_row[0] if m_row and m_row[0] else ""
    description = m_row[1] if m_row and m_row[1] else "No description available."
    current_price = float(m_row[2]) if m_row and m_row[2] else 0.0
    stock_name = m_row[3] if m_row and m_row[3] else symbol

    # Fundamental Data
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
            if current_price > 0:
                pnl_for_trade = (current_price - price) * qty
                is_unrealized = True
        elif t_type == 'SELL':
            avg_price = running_cost / running_qty if running_qty > 0 else 0
            running_qty -= qty
            running_cost -= (qty * avg_price)
            pnl_for_trade = ((price - avg_price) * qty) - fee
            running_pnl += pnl_for_trade
            is_unrealized = False

        pnl_text = f"₹{pnl_for_trade:,.2f}"
        if is_unrealized: pnl_text += " (U)"

        # Calculate Running PnL (Realized + Unrealized for currently held shares)
        current_running_unrealized = 0.0
        if running_qty > 0 and current_price > 0:
            current_avg_cost = running_cost / running_qty
            current_running_unrealized = (current_price - current_avg_cost) * running_qty
            
        display_running_pnl = running_pnl + current_running_unrealized

        # Use broker alias in table if cross-broker
        cells = [
            ft.DataCell(ft.Text(row['date'])),
        ]
        if not broker or broker == "All":
             cells.append(ft.DataCell(ft.Text(row['broker'])))
             
        cells.extend([
            ft.DataCell(ft.Text(t_type, color=ft.Colors.GREEN if t_type == 'BUY' else ft.Colors.RED)),
            ft.DataCell(ft.Text(f"{qty:,.0f}")),
            ft.DataCell(ft.Text(f"₹{price:,.2f}")),
            ft.DataCell(ft.Text(f"₹{fee:,.2f}")),
            ft.DataCell(
                ft.Text(pnl_text,
                        color=ft.Colors.GREEN if pnl_for_trade >= 0 else ft.Colors.RED)
                if t_type == 'SELL' or (t_type == 'BUY' and current_price > 0) else ft.Text("—")
            ),
            ft.DataCell(ft.Text(f"{running_qty:,.0f}")),
            ft.DataCell(ft.Text(f"₹{display_running_pnl:,.2f}", weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREEN if display_running_pnl >= 0 else ft.Colors.RED))
        ])
        rows.append(ft.DataRow(cells=cells))

    # Reverse rows to show descending order visually
    rows.reverse()

    columns = [
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

    table = ft.DataTable(
        columns=columns,
        rows=rows
    )

    def copy_to_clipboard(e):
        copy_df = df.copy()
        if not broker or broker == "All":
            cols_to_keep = ['date', 'broker', 'type', 'qty', 'price', 'fee']
        else:
            cols_to_keep = ['date', 'type', 'qty', 'price', 'fee']
            
        tsv_data = copy_df[cols_to_keep].to_csv(sep='\t', index=False)

        try:
            import subprocess, sys
            if sys.platform == "darwin":
                subprocess.run("pbcopy", input=tsv_data.encode(), check=True)
            elif sys.platform == "win32":
                subprocess.run("clip", input=tsv_data.encode(), check=True, shell=True)
            else:
                subprocess.run(["xclip", "-selection", "clipboard"], input=tsv_data.encode(), check=True)
            msg = "Trade history copied to clipboard!"
        except Exception as ex:
            msg = f"Copy failed: {ex}"

        app_state.page.snack_bar = ft.SnackBar(ft.Text(msg))
        app_state.page.snack_bar.open = True
        app_state.page.update()

    history_container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(broker_text, weight=ft.FontWeight.W_500),
                ft.IconButton(
                    icon=ft.Icons.CONTENT_COPY,
                    tooltip="Copy to Clipboard",
                    icon_color=ft.Colors.BLUE_300,
                    icon_size=18,
                    on_click=copy_to_clipboard
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(
                content=ft.Row([table], scroll=ft.ScrollMode.ADAPTIVE),
                expand=True,
            )
        ], scroll=ft.ScrollMode.ADAPTIVE),
        visible=True,
        padding=ft.padding.only(top=15, bottom=10),
        expand=True
    )

    def make_metric_card(title, value, color=ft.Colors.WHITE):
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500),
                ft.Text(str(value), size=16, color=color, weight=ft.FontWeight.BOLD)
            ], spacing=2),
            bgcolor="#1A1A1A",
            padding=15,
            border_radius=8,
            expand=1
        )

    fundamentals_container = ft.Container(
        content=ft.Column([
            ft.Text("Company Overview", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_300),
            ft.Text(description, size=12, color=ft.Colors.GREY_400),
            ft.Divider(height=20, color="transparent"),
            ft.Text("Valuation & Growth", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_300),
            ft.Row([
                make_metric_card("P/E Ratio", pe_ratio),
                make_metric_card("EPS (TTM)", eps),
                make_metric_card("P/B Ratio", pb_ratio),
            ]),
            ft.Row([
                make_metric_card("ROE", roe, ft.Colors.GREEN_300 if "—" not in str(roe) and float(str(roe).strip('%')) > 15 else ft.Colors.WHITE),
                make_metric_card("Debt to Equity", debt_to_equity, ft.Colors.RED_300 if "—" not in str(debt_to_equity) and float(str(debt_to_equity)) > 1 else ft.Colors.WHITE),
                make_metric_card("Dividend Yield", div_yield, ft.Colors.CYAN_300),
            ]),
            ft.Divider(height=20, color="transparent"),
            ft.Text("Price Action", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_300),
            ft.Row([
                make_metric_card("52-Week High", high_52w),
                make_metric_card("52-Week Low", low_52w),
                make_metric_card("Intrinsic Value", intrinsic_val, ft.Colors.PURPLE_300),
            ])
        ], scroll=ft.ScrollMode.ADAPTIVE),
        visible=False,
        padding=ft.padding.only(top=15, bottom=10),
        expand=True
    )

    # Tab Switching Logic
    def switch_tab(e):
        is_history = e.control.data == "history"
        history_container.visible = is_history
        fundamentals_container.visible = not is_history
        
        # Update button styles
        btn_history.style = ft.ButtonStyle(
            color=ft.Colors.BLUE_300 if is_history else ft.Colors.WHITE70,
            bgcolor=ft.Colors.BLUE_900 if is_history else ft.Colors.TRANSPARENT
        )
        btn_fundamentals.style = ft.ButtonStyle(
            color=ft.Colors.BLUE_300 if not is_history else ft.Colors.WHITE70,
            bgcolor=ft.Colors.BLUE_900 if not is_history else ft.Colors.TRANSPARENT
        )
        
        history_container.update()
        fundamentals_container.update()
        btn_history.update()
        btn_fundamentals.update()

    btn_history = ft.TextButton(
        "Trade History", 
        data="history",
        style=ft.ButtonStyle(color=ft.Colors.BLUE_300, bgcolor=ft.Colors.BLUE_900),
        on_click=switch_tab
    )
    btn_fundamentals = ft.TextButton(
        "Fundamentals", 
        data="fundamentals",
        style=ft.ButtonStyle(color=ft.Colors.WHITE70),
        on_click=switch_tab
    )

    tab_row = ft.Row([btn_history, btn_fundamentals], spacing=10)

    dlg = ft.AlertDialog(
        title=ft.Row([
            ft.Text(f"{stock_name} ({symbol})", weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Text(sector, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                bgcolor=ft.Colors.BLUE_900,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border_radius=4,
                visible=bool(sector)
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        content=ft.Container(
            content=ft.Column([
                tab_row,
                ft.Divider(height=10, color="#333333"),
                history_container,
                fundamentals_container
            ], spacing=0, expand=True),
            width=850, height=500,
            padding=10
        ),
        actions=[ft.TextButton("Close", on_click=lambda e: app_state.page.pop_dialog())]
    )
    app_state.page.show_dialog(dlg)
