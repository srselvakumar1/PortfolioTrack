import flet as ft

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

def page_title(title: str) -> ft.Text:
    """Standardized page header string."""
    return ft.Text(title, size=32, weight=ft.FontWeight.W_800)

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
