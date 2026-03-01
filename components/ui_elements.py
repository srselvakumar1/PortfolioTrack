import flet as ft
import threading
import time

def premium_card(content: ft.Control, width=None, height=None, padding=20, expand=False, on_click=None) -> ft.Container:
    """Standardized modern card for all views. Clickable if on_click is provided."""
    return ft.Container(
        content=content,
        on_click=on_click,
        width=width,
        height=height,
        padding=padding,
        expand=expand,
        border_radius=12,
        bgcolor="#1E1E1E", # SURFACE VARIANT
        border=ft.border.all(1, "#333333"), # OUTLINE VARIANT
        shadow=ft.BoxShadow(
            spread_radius=1, blur_radius=15, 
            color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK)
        )
    )

def show_toast(page: ft.Page, message: str, color: str = ft.Colors.BLUE, duration_ms: int = 2000):
    """Display a non-blocking toast notification at bottom center.
    
    Args:
        page: Flet page object
        message: Toast message text
        color: Background color (default: BLUE)
        duration_ms: How long to show toast (default: 2000ms)
    """
    toast = ft.SnackBar(
        ft.Text(message, color=ft.Colors.WHITE, size=12),
        bgcolor=color,
        duration=duration_ms,
        behavior=ft.SnackBarBehavior.FLOATING,
        shape=ft.RoundedRectangleBorder(radius=8)
    )
    page.overlay.append(toast)
    toast.open = True
    try:
        page.update()
    except Exception:
        pass
    
    # Auto-close after duration
    def auto_close():
        time.sleep(duration_ms / 1000.0)
        try:
            toast.open = False
            page.update()
        except Exception:
            pass
    
    threading.Thread(target=auto_close, daemon=True).start()

def page_title(title: str) -> ft.Text:
    """Standardized page header string with enhanced styling."""
    return ft.Text(
        title, 
        size=32, 
        weight=ft.FontWeight.W_800,
        color=ft.Colors.WHITE,
        spans=[
            ft.TextSpan(
                "  ▸",
                ft.TextStyle(color=ft.Colors.BLUE_400, weight=ft.FontWeight.W_800)
            )
        ]
    )

def info_metric(title: str, value_control: ft.Control, icon: str = None) -> ft.Column:
    """KPI Metric block for Dashboard/Insights."""
    return ft.Column([
        ft.Row([
            ft.Icon(icon, size=16, color=ft.Colors.BLUE) if icon else ft.Container(),
            ft.Text(title, size=14, color="#AAAAAA", weight=ft.FontWeight.W_500)
        ], spacing=6, alignment=ft.MainAxisAlignment.START),
        value_control
    ], spacing=4)

def status_chip(label: str, color: str) -> ft.Container:
    """Small pill/chip for statuses like 'ACCUMULATE' or 'REDUCE'."""
    return ft.Container(
        content=ft.Text(label, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        bgcolor=color,
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        border_radius=16
    )
def styled_modal_dialog(title: str, content: ft.Control, confirm_text: str = "Confirm", 
                       cancel_text: str = "Cancel", on_confirm=None, on_cancel=None, 
                       is_dangerous: bool = False) -> ft.AlertDialog:
    """Create a styled modal dialog with rounded corners and better layout.
    
    Args:
        title: Dialog title
        content: Dialog content control
        confirm_text: Confirm button text
        cancel_text: Cancel button text
        on_confirm: Callback for confirm button
        on_cancel: Callback for cancel button
        is_dangerous: If True, confirm button is red (for delete operations)
    """
    confirm_color = ft.Colors.RED_600 if is_dangerous else ft.Colors.BLUE_600
    
    return ft.AlertDialog(
        title=ft.Container(
            content=ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            padding=ft.padding.only(bottom=8)
        ),
        content=ft.Container(
            content=content,
            padding=ft.padding.symmetric(vertical=12, horizontal=0)
        ),
        actions=[
            ft.TextButton(
                cancel_text,
                on_click=on_cancel,
                style=ft.ButtonStyle(color=ft.Colors.GREY_400)
            ),
            ft.TextButton(
                confirm_text,
                on_click=on_confirm,
                style=ft.ButtonStyle(color=confirm_color)
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=12),
        inset_padding=30
    )

def alternating_row_color(row_index: int) -> str:
    """Get background color for alternating row colors in tables.
    
    Args:
        row_index: Row number (0-based)
    
    Returns:
        Hex color code: alternates between lighter and slightly darker shades
    """
    return "#333333" if row_index % 2 == 0 else "#2A2A2A"

def create_column_tooltip_header(text: str, tooltip: str, width: int = None, numeric: bool = False) -> ft.DataColumn:
    """Create a data column header with tooltip on hover.
    
    Args:
        text: Column header text
        tooltip: Hover tooltip text
        width: Column width
        numeric: If True, right-align the text
    """
    return ft.DataColumn(
        ft.Container(
            ft.Text(
                text,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER if numeric else ft.TextAlign.LEFT,
                size=12,
                color=ft.Colors.BLUE_300,
                tooltip=tooltip
            ),
            width=width,
            alignment=ft.alignment.Alignment(0, 0) if numeric else ft.alignment.Alignment(-1, 0)
        ),
        numeric=numeric
    )


# ───────────────────────────────────────────────────────────────────────────────
# HOLDINGS VIEW ENHANCEMENT HELPERS (12 Improvements)
# ───────────────────────────────────────────────────────────────────────────────

def stock_name_with_badge(symbol: str, stock_name: str, sector: str = None) -> ft.Row:
    """Stock name display with logo emoji and sector badge (Improvement #4)"""
    # Simple emoji sectors for visual distinction
    sector_emojis = {
        "TECH": "⚙️", "FINANCE": "💰", "AUTO": "🚗", "PHARMA": "💊",
        "ENERGY": "⚡", "REALTY": "🏢", "CONSUMER": "🛒", "TELECOM": "📡"
    }
    emoji = sector_emojis.get(sector.upper() if sector else "", "📈")
    
    return ft.Row([
        ft.Text(emoji, size=14),
        ft.Column([
            ft.Text(symbol.upper(), weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_300),
            ft.Text(stock_name, size=9, color=ft.Colors.GREY_400, italic=True),
        ], spacing=2, tight=True)
    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def holdings_stats_card(total_holdings: int, total_invested: float, current_value: float, total_pnl: float, active_filters: bool = False) -> ft.Container:
    """Summary statistics card for portfolio overview (Improvement #5)"""
    pnl_color = ft.Colors.GREEN_600 if total_pnl >= 0 else ft.Colors.RED_600
    pnl_icon = "📈" if total_pnl >= 0 else "📉"
    filter_status = "FILTERED" if active_filters else "ALL"
    filter_color = ft.Colors.YELLOW_600 if active_filters else ft.Colors.GREY_500
    
    return ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text("Holdings", size=10, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                ft.Text(f"{total_holdings}", size=18, weight=ft.FontWeight.W_800, color=ft.Colors.BLUE_300),
            ], spacing=2),
            ft.VerticalDivider(width=1),
            ft.Column([
                ft.Text("Invested", size=10, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                ft.Text(f"₹ {total_invested:,.0f}", size=14, weight=ft.FontWeight.W_700, color=ft.Colors.CYAN_300),
            ], spacing=2),
            ft.VerticalDivider(width=1),
            ft.Column([
                ft.Text("Current Value", size=10, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                ft.Text(f"₹ {current_value:,.0f}", size=14, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
            ], spacing=2),
            ft.VerticalDivider(width=1),
            ft.Column([
                ft.Text("Total P&L", size=10, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                ft.Text(f"{pnl_icon} ₹ {total_pnl:,.0f}", size=14, weight=ft.FontWeight.W_700, color=pnl_color),
            ], spacing=2),
            ft.Container(expand=True),
            ft.Container(
                content=ft.Text(filter_status, size=10, weight=ft.FontWeight.W_700, color=filter_color),
                bgcolor=ft.Colors.with_opacity(0.2, filter_color),
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border_radius=6
            )
        ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=16),
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        bgcolor="#252525",
        border_radius=8,
        margin=ft.margin.only(bottom=12)
    )


def enhanced_filter_panel(broker_dropdown, symbol_input, iv_dropdown, exclude_checkbox, apply_btn, clear_btn, active_count: int = 0) -> ft.Container:
    """Enhanced filter panel with visual organization (Improvements #1, #9)"""
    filter_badge = ft.Container(
        content=ft.Text(str(active_count), size=9, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
        width=20, height=20, border_radius=10,
        bgcolor=ft.Colors.ORANGE_600 if active_count > 0 else "transparent",
        alignment=ft.alignment.Alignment(0, 0),
        visible=active_count > 0
    )
    
    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("🔍 FILTERS", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.BLUE_300),
                filter_badge,
                ft.Container(expand=True),
            ]),
            ft.Divider(height=12, color="#404040"),
            ft.Row([
                broker_dropdown, symbol_input, iv_dropdown, exclude_checkbox,
                ft.Container(expand=True),
                apply_btn, clear_btn
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=8),
        padding=ft.padding.all(12),
        bgcolor="#1A1A1A",
        border_radius=8,
        border=ft.border.all(1, "#333333")
    )


def sort_indicator(column_name: str, is_active: bool = False, is_ascending: bool = True) -> ft.Row:
    """Column header with sort indicator (Improvement #6)"""
    arrow = "▲" if is_ascending else "▼" if is_active else "─"
    color = ft.Colors.BLUE_300 if is_active else ft.Colors.GREY_600
    
    return ft.Row([
        ft.Text(column_name, weight=ft.FontWeight.BOLD, color=color, size=11),
        ft.Text(arrow, size=9, weight=ft.FontWeight.W_600, color=color) if is_active else ft.Container(width=8),
    ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def quick_action_buttons(broker: str, symbol: str, on_view_details=None, on_edit=None, on_delete=None) -> ft.Row:
    """Quick action buttons for table row (Improvement #7)"""
    return ft.Row([
        ft.IconButton(ft.Icons.OPEN_IN_NEW, icon_size=16, icon_color=ft.Colors.BLUE_400, on_click=on_view_details, tooltip="View Details"),
        ft.IconButton(ft.Icons.EDIT, icon_size=16, icon_color=ft.Colors.ORANGE_400, on_click=on_edit, tooltip="Edit Holding"),
        ft.IconButton(ft.Icons.DELETE, icon_size=16, icon_color=ft.Colors.RED_400, on_click=on_delete, tooltip="Delete"),
    ], spacing=4)


def enhanced_pagination_control(current_page: int, total_records: int, page_size: int = 25) -> ft.Container:
    """Enhanced pagination display with better formatting (Improvement #8)"""
    max_page = max(1, (total_records + page_size - 1) // page_size)
    showing_start = ((current_page - 1) * page_size) + 1 if total_records > 0 else 0
    showing_end = min(current_page * page_size, total_records)
    
    return ft.Container(
        content=ft.Text(
            f"Showing {showing_start}–{showing_end} of {total_records} holdings • Page {current_page}/{max_page}",
            size=11, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500, italic=True
        ),
        alignment=ft.alignment.Alignment(0, 0)
    )


def color_coded_value_cell(value: float, prefix: str = "₹", decimals: int = 2, show_sign: bool = False) -> ft.Text:
    """Color-coded value cell (green for positive, red for negative) (Improvement #2)"""
    color = ft.Colors.GREEN_400 if value >= 0 else ft.Colors.RED_400
    sign = "+" if (value > 0 and show_sign) else ""
    display = f"{sign}{prefix}{abs(value):,.{decimals}f}"
    
    return ft.Text(display, color=color, size=11, weight=ft.FontWeight.W_600)


def mini_sparkline_cell(values_list: list, height: int = 20, width: int = 30) -> ft.Container:
    """Mini sparkline for trends (Improvement #10)"""
    if not values_list or len(values_list) < 2:
        return ft.Container(width=width, height=height)
    
    # Determine trend direction
    first, last = values_list[0], values_list[-1]
    trend_up = last > first
    color = ft.Colors.GREEN_600 if trend_up else ft.Colors.RED_600
    arrow = "📈" if trend_up else "📉"
    pct_change = ((last - first) / abs(first) * 100) if first != 0 else 0
    
    return ft.Container(
        content=ft.Text(arrow, size=14, color=color, weight=ft.FontWeight.W_700),
        tooltip=f"Trend: {pct_change:+.1f}%"
    )


def holdings_view_header() -> ft.Container:
    """Enhanced view header with subtitle and stats (Improvement #12)"""
    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("My Holdings", size=28, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                ft.Text("📊", size=28),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(
                "Portfolio Holdings • Real-time Market Data • Advanced Filtering",
                size=11, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500, italic=True
            ),
        ], spacing=4),
        padding=ft.padding.all(0)
    )


def sidebar_stats_card() -> tuple:
    """Create sidebar stats card with updatable text controls (Returns: Container, dict of text controls)"""
    # Create text controls with identifiers
    portfolio_text = ft.Text("₹ 0", size=18, weight=ft.FontWeight.W_700, color="#3B82F6")
    invested_text = ft.Text("₹ 0", size=13, weight=ft.FontWeight.W_600, color="#06B6D4")
    pnl_text = ft.Text("₹ 0", size=13, weight=ft.FontWeight.W_600, color="#10B981")
    
    # Store references in a dict for easy access
    text_refs = {
        "portfolio_value": portfolio_text,
        "invested": invested_text,
        "pnl": pnl_text
    }
    
    card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Portfolio Value", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                ft.Container(expand=True),
            ]),
            portfolio_text,
            ft.Divider(height=12, color="#27404A"),
            ft.Row([
                ft.Column([
                    ft.Text("Invested", size=9, color=ft.Colors.GREY_500),
                    invested_text,
                ], spacing=2),
                ft.Column([
                    ft.Text("P&L", size=9, color=ft.Colors.GREY_500),
                    pnl_text,
                ], spacing=2),
            ], spacing=8),
        ], spacing=4),
        padding=ft.padding.only(left=16, right=16, top=12, bottom=12),
        bgcolor="#1B2638",
        border_radius=8,
        margin=ft.margin.only(left=12, right=16, bottom=16),
    )
    
    return card, text_refs


def drilldown_stock_header(symbol: str, stock_name: str, sector: str, current_price: float) -> ft.Container:
    """Create professional stock overview header for drilldown dialog"""
    sector_badge = ft.Container(
        content=ft.Text(sector, size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
        bgcolor="#10B981", padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=4
    ) if sector else ft.Container()
    
    return ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Row([ft.Text(symbol, size=20, weight=ft.FontWeight.BOLD), sector_badge], spacing=8),
                ft.Text(stock_name, size=13, color="#9CA3AF")
            ], spacing=2),
            ft.Column([
                ft.Text("Current Price", size=11, color="#6B7280", weight=ft.FontWeight.W_500),
                ft.Text(f"₹{current_price:,.2f}", size=18, weight=ft.FontWeight.BOLD, color="#3B82F6")
            ], horizontal_alignment=ft.CrossAxisAlignment.END)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor="#1A2A3A", padding=15, border_radius=8, border=ft.border.all(1, "#334155")
    )


def drilldown_trade_stats(total_trades: int, shares_held: float, total_invested: float, realized_pnl: float) -> ft.Container:
    """Create trade statistics summary card"""
    def stat_item(title, value, color="#E5E7EB"):
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                ft.Text(str(value), size=14, weight=ft.FontWeight.BOLD, color=color)
            ], spacing=2),
            expand=1
        )
    
    pnl_color = "#10B981" if realized_pnl >= 0 else "#EF4444"
    
    return ft.Container(
        content=ft.Row([
            stat_item("Total Trades", total_trades),
            stat_item("Shares Held", f"{shares_held:,.0f}"),
            stat_item("Total Invested", f"₹{total_invested:,.0f}", "#3B82F6"),
            stat_item("Realized P&L", f"₹{realized_pnl:,.0f}", pnl_color)
        ], spacing=12),
        bgcolor="#1A2A3A", padding=12, border_radius=8, border=ft.border.all(1, "#334155"), margin=ft.margin.only(top=10)
    )


def drilldown_metric_card(title: str, value: str, color: str = "#E5E7EB", icon: str = None) -> ft.Container:
    """Enhanced metric card with optional icon for drilldown fundamentals"""
    content_row = []
    if icon:
        content_row.append(ft.Text(icon, size=16))
    content_row.append(ft.Column([
        ft.Text(title, size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
        ft.Text(value, size=14, weight=ft.FontWeight.BOLD, color=color)
    ], spacing=2, expand=1))
    
    return ft.Container(
        content=ft.Row(content_row, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor="#0F172A", padding=12, border_radius=6, border=ft.border.all(1, "#1E293B"), expand=1
    )


def dashboard_breakdown_header(title: str, icon: str, total_value: float, is_currency: bool = True) -> ft.Container:
    """Create header for dashboard broker breakdown dialog"""
    value_str = f"₹{total_value:,.2f}" if is_currency else f"{total_value:,.2f}%"
    value_color = "#10B981" if total_value >= 0 else "#EF4444"
    
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Text(icon, size=20),
                bgcolor="#1E40AF", padding=10, border_radius=6
            ),
            ft.Column([
                ft.Text(title, size=12, color="#9CA3AF", weight=ft.FontWeight.W_500),
                ft.Text("Broker Breakdown", size=14, weight=ft.FontWeight.BOLD)
            ], spacing=1),
            ft.Column([
                ft.Text("Total", size=11, color="#9CA3AF", weight=ft.FontWeight.W_500),
                ft.Text(value_str, size=16, weight=ft.FontWeight.BOLD, color=value_color)
            ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=1)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=15),
        bgcolor="#1A2A3A", padding=15, border_radius=8, border=ft.border.all(1, "#334155")
    )


def dashboard_broker_stats(broker_data: list) -> ft.Container:
    """Create summary statistics for broker breakdown (best, worst, average)"""
    if not broker_data:
        return ft.Container()
    
    values = [item['value'] for item in broker_data]
    total = sum(values)
    avg = total / len(values) if values else 0
    best_item = max(broker_data, key=lambda x: x['value'])
    worst_item = min(broker_data, key=lambda x: x['value'])
    
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Text("Average", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                    ft.Text(f"₹{avg:,.0f}", size=13, weight=ft.FontWeight.BOLD, color="#06B6D4")
                ], spacing=2), expand=1
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Best", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                    ft.Text(best_item['broker'], size=13, weight=ft.FontWeight.BOLD, color="#10B981")
                ], spacing=2), expand=1
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Worst", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                    ft.Text(worst_item['broker'], size=13, weight=ft.FontWeight.BOLD, color="#EF4444")
                ], spacing=2), expand=1
            ),
        ], spacing=12),
        bgcolor="#0F172A", padding=12, border_radius=6, border=ft.border.all(1, "#1E293B")
    )


def dashboard_broker_row_item(broker: str, value: float, is_currency: bool = True, icon: str = None) -> ft.Container:
    """Create individual broker row for breakdown list"""
    value_str = f"₹{value:,.2f}" if is_currency else f"{value:,.2f}%"
    value_color = "#10B981" if value >= 0 else "#EF4444"
    
    content_items = []
    if icon:
        content_items.append(ft.Text(icon, size=14))
    
    content_items.extend([
        ft.Text(broker, size=12, weight=ft.FontWeight.W_600, expand=1),
        ft.Container(width=5),
        ft.Text(value_str, size=12, weight=ft.FontWeight.BOLD, color=value_color)
    ])
    
    return ft.Container(
        content=ft.Row(content_items, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor="#0F172A", padding=12, border_radius=6, border=ft.border.all(1, "#1E293B")
    )


def trade_edit_header(symbol: str, trade_type: str, trade_date: str) -> ft.Container:
    """Create header for trade edit dialog"""
    type_color = "#10B981" if trade_type == "BUY" else "#EF4444"
    type_badge_bg = "#0D4E2F" if trade_type == "BUY" else "#4B0E0E"
    
    return ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(symbol, size=22, weight=ft.FontWeight.BOLD),
                ft.Text(f"Trade ID • {trade_date}", size=11, color="#9CA3AF")
            ], spacing=2),
            ft.Container(
                content=ft.Text(trade_type, size=12, color=type_color, weight=ft.FontWeight.BOLD),
                bgcolor=type_badge_bg, padding=ft.padding.symmetric(horizontal=12, vertical=6), border_radius=20
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=15),
        bgcolor="#1A2A3A", padding=15, border_radius=8, border=ft.border.all(1, "#334155")
    )


def trade_edit_field(label: str, value: str, keyboard_type=ft.KeyboardType.TEXT, on_change=None, expand=True, helper_text="") -> ft.Container:
    """Create enhanced edit field for trade dialog"""
    field = ft.TextField(
        label=label,
        value=value,
        expand=expand,
        keyboard_type=keyboard_type,
        on_change=on_change,
        label_style=ft.TextStyle(color="#9CA3AF", size=11),
        text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
        bgcolor="#0F172A",
        border_color="#334155",
        border_radius=6,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=10)
    )
    
    if helper_text:
        return ft.Column([
            field,
            ft.Text(helper_text, size=9, color="#6B7280", italic=True)
        ], spacing=2)
    
    return field


def trade_edit_calculation_card(label: str, value: str, icon: str = "📊", color: str = "#E5E7EB") -> ft.Container:
    """Create calculation display card (read-only) for trade form"""
    return ft.Container(
        content=ft.Row([
            ft.Text(icon, size=14),
            ft.Column([
                ft.Text(label, size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                ft.Text(value, size=13, weight=ft.FontWeight.BOLD, color=color)
            ], spacing=1, expand=1)
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor="#0F172A", padding=12, border_radius=6, border=ft.border.all(1, "#1E293B")
    )


def trade_edit_form_section(title: str, controls: list) -> ft.Container:
    """Create organized form section with title"""
    return ft.Container(
        content=ft.Column([
            ft.Text(title, size=12, weight=ft.FontWeight.BOLD, color="#3B82F6"),
            ft.Column(controls, spacing=8)
        ], spacing=10),
        padding=0
    )


def trade_edit_divider() -> ft.Divider:
    """Create styled divider for trade edit dialog"""
    return ft.Divider(height=1, color="#334155")


def holding_edit_header(symbol: str, stock_name: str, broker: str, current_qty: float, current_price: float) -> ft.Container:
    """Create header for holding edit dialog"""
    current_value = current_qty * current_price
    
    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(symbol, size=22, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{stock_name} • {broker}", size=11, color="#9CA3AF")
                ], spacing=2),
                ft.Column([
                    ft.Text("Current Holdings", size=11, color="#9CA3AF", weight=ft.FontWeight.W_500),
                    ft.Text(f"{current_qty:,.0f} shares @ ₹{current_price:,.2f}", size=13, weight=ft.FontWeight.BOLD, color="#3B82F6")
                ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=10, color="transparent"),
            ft.Row([
                ft.Text("Total Value", size=10, color="#9CA3AF"),
                ft.Text(f"₹{current_value:,.2f}", size=16, weight=ft.FontWeight.BOLD, color="#06B6D4")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ], spacing=6),
        bgcolor="#1A2A3A", padding=15, border_radius=8, border=ft.border.all(1, "#334155")
    )


def holding_edit_field(label: str, value: str, keyboard_type=ft.KeyboardType.TEXT, on_change=None, helper_text="") -> ft.Container:
    """Create enhanced field for holding edit dialog"""
    field = ft.TextField(
        label=label,
        value=value,
        keyboard_type=keyboard_type,
        on_change=on_change,
        label_style=ft.TextStyle(color="#9CA3AF", size=11),
        text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
        bgcolor="#0F172A",
        border_color="#334155",
        border_radius=6,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=10)
    )
    
    if helper_text:
        return ft.Column([
            field,
            ft.Text(helper_text, size=9, color="#6B7280", italic=True)
        ], spacing=2)
    
    return field


def holding_edit_summary(qty: float, price: float, broker: str) -> ft.Container:
    """Create summary card for holding edit"""
    total_value = qty * price
    
    return ft.Container(
        content=ft.Column([
            ft.Text("Summary", size=12, weight=ft.FontWeight.BOLD, color="#3B82F6"),
            ft.Row([
                ft.Column([
                    ft.Text("Shares", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                    ft.Text(f"{qty:,.0f}", size=13, weight=ft.FontWeight.BOLD, color="#E5E7EB")
                ], expand=1),
                ft.Column([
                    ft.Text("Avg Price", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                    ft.Text(f"₹{price:,.2f}", size=13, weight=ft.FontWeight.BOLD, color="#E5E7EB")
                ], expand=1),
                ft.Column([
                    ft.Text("Total Value", size=10, color="#9CA3AF", weight=ft.FontWeight.W_500),
                    ft.Text(f"₹{total_value:,.2f}", size=13, weight=ft.FontWeight.BOLD, color="#06B6D4")
                ], expand=1),
            ], spacing=12)
        ], spacing=10),
        bgcolor="#0F172A", padding=12, border_radius=6, border=ft.border.all(1, "#1E293B")
    )