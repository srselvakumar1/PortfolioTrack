import flet as ft
import time
import os
import threading
from flet_app.components.ui_elements import sidebar_stats_card

# ─── Nav item config: (icon_outlined, icon_filled, label, index, section) ─────
_NAV_ITEMS = [
    (ft.Icons.SPACE_DASHBOARD_OUTLINED,         ft.Icons.SPACE_DASHBOARD,           "Dashboard",     0, "PORTFOLIO"),
    (ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,  ft.Icons.ACCOUNT_BALANCE_WALLET,    "Holdings",      1, "PORTFOLIO"),
    (ft.Icons.ADD_CIRCLE_OUTLINE,               ft.Icons.ADD_CIRCLE,                "Trade Entry",   2, "TRANSACTIONS"),
    (ft.Icons.CANDLESTICK_CHART_OUTLINED,       ft.Icons.CANDLESTICK_CHART,         "Trade History", 3, "TRANSACTIONS"),
    (ft.Icons.SETTINGS_OUTLINED,                ft.Icons.SETTINGS,                  "Settings",      4, "ADMIN"),
    (ft.Icons.HELP_OUTLINE,                     ft.Icons.HELP,                      "Help",          5, "ADMIN"),
]

# ─── Colour palette ────────────────────────────────────────────────────────────
_SIDEBAR_BG     = "#0A0E16"
_SIDEBAR_ACCENT = "#1318AB"
_ACTIVE_BG      = "#1A3A5C"
_ACTIVE_ACCENT  = "#3B82F6"
_HOVER_BG       = "#1B2638"
_TEXT_ACTIVE    = "#FFFFFF"
_TEXT_INACTIVE  = "#8B9CB6"
_TEXT_SECTION   = "#60A5FA"
_ICON_ACTIVE    = "#60A5FA"
_ICON_INACTIVE  = "#4A5568"
_GRADIENT_1     = "#3B82F6"
_GRADIENT_2     = "#1E40AF"
_SECTION_COLOR  = "#10B981"


class _NavItem(ft.Container):
    """Enhanced sidebar navigation item with hover effects, badges, and animations."""

    def __init__(self, icon_off, icon_on, label: str, index: int, on_click_cb, special_color: str = None):
        super().__init__()
        self.index = index
        self._icon_off  = icon_off
        self._icon_on   = icon_on
        self._label_str = label
        self._on_click_cb = on_click_cb
        self._special_color = special_color
        self._badge_count = 0
        self._is_hovering = False

        # Left accent bar (animated)
        self._left_bar = ft.Container(width=4, border_radius=4, bgcolor="transparent", height=36)
        
        # Icon with hover scaling
        icon_color = special_color if special_color else _ICON_INACTIVE
        self._icon_ctrl = ft.Icon(icon_off, size=24, color=icon_color)
        self._icon_container = ft.Container(self._icon_ctrl, width=28, height=28, alignment=ft.alignment.Alignment(0, 0))
        
        # Label
        text_color = special_color if special_color else _TEXT_INACTIVE
        self._label_ctrl = ft.Text(label, size=15, weight=ft.FontWeight.W_500, color=text_color)

        # Badge (notification style)
        self._badge = ft.Container(
            content=ft.Text("0", size=10, weight=ft.FontWeight.W_700, color=_TEXT_ACTIVE),
            width=20, height=20, border_radius=10,
            bgcolor=ft.Colors.RED_400,
            alignment=ft.alignment.Alignment(0, 0),
            visible=False
        )

        self.content = ft.Row([
            self._left_bar,
            ft.Container(width=8),
            self._icon_container,
            ft.Container(width=8),
            self._label_ctrl,
            ft.Container(expand=True),
            self._badge,
            ft.Container(width=8),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)

        self.height       = 48
        self.border_radius = ft.BorderRadius(8, 8, 8, 8)
        self.bgcolor      = "transparent"
        self.margin       = ft.margin.only(right=16, bottom=4, left=12)
        self.on_click     = self._handle_click
        self.on_hover     = self._handle_hover
        self._selected = False

    def _handle_click(self, e):
        self._on_click_cb(self.index)

    def _handle_hover(self, e):
        self._is_hovering = e.data == "true"
        if not self._selected:
            if self._is_hovering:
                self.bgcolor = _HOVER_BG
                self._icon_container.scale = 1.15
            else:
                self.bgcolor = "transparent"
                self._icon_container.scale = 1.0
            self.update()

    def set_badge(self, count: int):
        """Show badge with count"""
        self._badge_count = count
        if count > 0:
            self._badge.content.value = str(min(count, 99)) + ("+" if count > 99 else "")
            self._badge.visible = True
        else:
            self._badge.visible = False
        try:
            self.update()
        except:
            pass

    def set_selected(self, value: bool):
        self._selected = value
        if value:
            self._left_bar.bgcolor = _ACTIVE_ACCENT
            self._left_bar.width = 6
            base_icon_color = self._special_color if self._special_color else _ICON_ACTIVE
            base_text_color = self._special_color if self._special_color else _TEXT_ACTIVE
            self._icon_ctrl.color = base_icon_color
            self._icon_ctrl.name = self._icon_on
            self._label_ctrl.color = base_text_color
            self._label_ctrl.weight = ft.FontWeight.W_600
            self.bgcolor = _ACTIVE_BG
            self._icon_container.scale = 1.2
        else:
            self._left_bar.bgcolor = "transparent"
            self._left_bar.width = 4
            base_icon_color = self._special_color if self._special_color else _ICON_INACTIVE
            base_text_color = self._special_color if self._special_color else _TEXT_INACTIVE
            self._icon_ctrl.color = base_icon_color
            self._icon_ctrl.name = self._icon_off
            self._label_ctrl.color = base_text_color
            self._label_ctrl.weight = ft.FontWeight.W_500
            self.bgcolor = "transparent"
            self._icon_container.scale = 1.0



class _CollapsibleSection(ft.Column):
    """Collapsible navigation section with expand/collapse animation."""
    
    def __init__(self, title: str, icon: str, items: list, on_item_click):
        super().__init__(spacing=2)
        self.title = title
        self.icon = icon
        self.items = items
        self.is_expanded = True
        self._items_container = ft.Column(controls=items, spacing=2, visible=True)
        
        def toggle_section(e):
            self.is_expanded = not self.is_expanded
            self._items_container.visible = self.is_expanded
            toggle_btn.rotate = 0.5 if self.is_expanded else 0
            toggle_btn.update()
            self._items_container.update()
        
        toggle_btn = ft.IconButton(
            ft.Icons.KEYBOARD_ARROW_DOWN,
            icon_size=20,
            icon_color=_SECTION_COLOR,
            on_click=toggle_section,
            rotate=0
        )
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=18, color=_SECTION_COLOR),
                ft.Container(width=8),
                ft.Text(title, size=12, weight=ft.FontWeight.W_700, color=_SECTION_COLOR),
                ft.Container(expand=True),
                toggle_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.only(left=16, right=8, top=12, bottom=8),
        )
        
        gradient_divider = ft.Container(
            content=ft.Divider(height=1, color=_SECTION_COLOR),
            padding=ft.padding.only(left=16, right=16, bottom=8)
        )
        
        self.controls = [header, gradient_divider, self._items_container]


class PremiumSidebar(ft.Container):
    """Enhanced premium sidebar with all 10 beautification features."""
    
    def __init__(self, page: ft.Page, on_nav_change, toggle_sidebar_cb=None):
        super().__init__()
        self._flet_page        = page
        self._on_nav_change    = on_nav_change
        self._selected_index   = 0
        self._prev_item: _NavItem | None = None  
        self._items: list[_NavItem] = []
        self._theme_dark = True
        self._current_breadcrumb = "Dashboard"
        self._section_items = {}

        # ──────────────────────────────────────────────────────────────────────
        # 9. ENHANCED HEADER with animated logo, dynamic subtitle, search bar
        # ──────────────────────────────────────────────────────────────────────
        logo_icon = ft.Icon(ft.Icons.SHOW_CHART, size=28, color=_ACTIVE_ACCENT)
        
        # Dynamic subtitle (changes based on time of day)
        current_hour = time.localtime().tm_hour
        if current_hour < 12:
            subtitle = "☀️ Good Morning"
        elif current_hour < 18:
            subtitle = "🌤️ Good Afternoon"
        else:
            subtitle = "🌙 Good Evening"
        
        header = ft.Container(
            content=ft.Column([
                ft.Row([
                    logo_icon,
                    ft.Container(width=10),
                    ft.Text("PT Tracker", size=20, weight=ft.FontWeight.W_800, color=_TEXT_ACTIVE),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                ft.Text(subtitle, size=11, color=_TEXT_INACTIVE, weight=ft.FontWeight.W_400, italic=True),
            ], spacing=4, tight=True),
            padding=ft.padding.only(left=20, right=10, top=20, bottom=16)
        )

        # ──────────────────────────────────────────────────────────────────────
        # 8. STATS/INFO CARDS - Quick portfolio info
        # ──────────────────────────────────────────────────────────────────────
        # 8. STATS/INFO CARDS - Quick portfolio info with updatable text refs
        # ──────────────────────────────────────────────────────────────────────
        self.stats_card, self.stats_text_refs = sidebar_stats_card()

        # ──────────────────────────────────────────────────────────────────────
        # 10. NAVIGATION BREADCRUMB - Current location display
        # ──────────────────────────────────────────────────────────────────────
        self.breadcrumb = ft.Container(
            content=ft.Text("Dashboard", size=10, color=_TEXT_SECTION, weight=ft.FontWeight.W_600, italic=True),
            padding=ft.padding.only(left=20, right=16, bottom=8),
        )

        # ──────────────────────────────────────────────────────────────────────
        # 2. RICH SECTION SEPARATORS (via _CollapsibleSection)
        # ──────────────────────────────────────────────────────────────────────
        
        portfolio_items = []
        transactions_items = []
        admin_items = []
        
        for icon_off, icon_on, label, idx, section in _NAV_ITEMS:
            item = _NavItem(icon_off, icon_on, label, idx, self._handle_item_click)
            self._items.append(item)
            self._section_items[idx] = item
            
            if section == "PORTFOLIO":
                portfolio_items.append(item)
            elif section == "TRANSACTIONS":
                transactions_items.append(item)
            elif section == "ADMIN":
                admin_items.append(item)

        portfolio_section = _CollapsibleSection("PORTFOLIO", ft.Icons.ACCOUNT_BALANCE, portfolio_items, self._handle_item_click)
        transactions_section = _CollapsibleSection("TRANSACTIONS", ft.Icons.TRENDING_UP, transactions_items, self._handle_item_click)
        admin_section = _CollapsibleSection("SYSTEM", ft.Icons.SETTINGS, admin_items, self._handle_item_click)

        # ──────────────────────────────────────────────────────────────────────
        # 6. THEME SWITCHER - Light/Dark mode toggle
        # ──────────────────────────────────────────────────────────────────────
        def toggle_theme(e):
            self._theme_dark = not self._theme_dark
            theme_btn.icon = ft.Icons.DARK_MODE if self._theme_dark else ft.Icons.LIGHT_MODE
            theme_btn.icon_color = "#FDB813" if not self._theme_dark else "#60A5FA"
            try:
                theme_btn.update()
            except Exception:
                try:
                    self.update()
                except Exception:
                    pass

        theme_btn = ft.IconButton(
            ft.Icons.DARK_MODE,
            icon_size=20,
            icon_color=_ACTIVE_ACCENT,
            on_click=toggle_theme,
            tooltip="Toggle Theme"
        )

        # ──────────────────────────────────────────────────────────────────────
        # EXIT BUTTON (Enhanced styling)
        # ──────────────────────────────────────────────────────────────────────
        def force_quit(e):
            # Single-shot guard
            try:
                if getattr(self._flet_page, "_exiting", False):
                    return
                self._flet_page._exiting = True
            except Exception:
                pass

            cb = getattr(self._flet_page, "_request_exit", None)
            if callable(cb):
                try:
                    # Call directly; request_exit now self-dispatches UI work
                    # and closes DB connections in the background.
                    cb("sidebar")
                except Exception:
                    try:
                        cb()
                    except Exception:
                        pass
                return

            # Guarantee termination even if shutdown callback is unavailable.
            try:
                threading.Timer(0.35, lambda: os._exit(0)).start()
            except Exception:
                try:
                    os._exit(0)
                except Exception:
                    pass

            # Fallback: best-effort close
            try:
                self._flet_page.window.prevent_close = False
            except Exception:
                pass
            try:
                if hasattr(self._flet_page, "window_close"):
                    self._flet_page.window_close()
                    return
            except Exception:
                pass
            try:
                res = self._flet_page.window.close()
                # Some builds expose an awaitable close; handle both.
                if hasattr(res, "__await__"):
                    try:
                        # Best-effort: schedule awaiting on the page loop if possible
                        if hasattr(self._flet_page, "run_task"):
                            async def _await_close():
                                try:
                                    await res
                                except Exception:
                                    pass
                            self._flet_page.run_task(_await_close)
                    except Exception:
                        pass
            except Exception:
                pass

        def exit_hover(e):
            exit_btn.bgcolor = "#3A1A1A" if e.data == "true" else "transparent"
            exit_btn.update()

        exit_btn = ft.Container(
            content=ft.Row([
                ft.Container(width=10),
                ft.Icon(ft.Icons.LOGOUT, size=24, color=ft.Colors.RED_400),
                ft.Container(width=10),
                ft.Text("Exit", size=15, weight=ft.FontWeight.W_500, color=ft.Colors.RED_400),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
            height=48,
            on_click=force_quit,
            on_hover=exit_hover,
            margin=ft.margin.only(right=16, bottom=4, left=12),
            border_radius=8,
            tooltip="Close Application"
        )

        # ──────────────────────────────────────────────────────────────────────
        # GRADIENT DIVIDERS (2. Rich Section Separators)
        # ──────────────────────────────────────────────────────────────────────
        header_divider = ft.Container(
            content=ft.Divider(color=_SECTION_COLOR, height=1),
            padding=ft.padding.only(left=16, right=16, bottom=12)
        )

        footer_divider = ft.Container(
            content=ft.Divider(color=_SECTION_COLOR, height=1),
            padding=ft.padding.only(left=16, right=16, top=12, bottom=12)
        )

        version_info = ft.Container(
            content=ft.Column([
                ft.Text("Build v2.0", size=10, color=_TEXT_SECTION, weight=ft.FontWeight.W_600),
                ft.Text("Enhanced Edition", size=9, color=_TEXT_INACTIVE, weight=ft.FontWeight.W_400),
            ], spacing=2),
            padding=ft.padding.only(left=20, bottom=16, top=8),
            alignment=ft.alignment.Alignment(-1, 0)
        )

        # ──────────────────────────────────────────────────────────────────────
        # 7. MOUSE POSITION GLOW EFFECT (simulated via hover glow on items)
        # ──────────────────────────────────────────────────────────────────────
        # Implemented via _NavItem._handle_hover with bgcolor glow

        col = ft.Column(
            controls=[
                header,
                header_divider,
                self.stats_card,
                self.breadcrumb,
                portfolio_section,
                transactions_section,
                admin_section,
                ft.Container(expand=True),
                footer_divider,
                ft.Container(
                    content=ft.Row([
                        ft.Text("Settings", size=11, color=_TEXT_INACTIVE, weight=ft.FontWeight.W_600),
                        ft.Container(expand=True),
                        theme_btn,
                        ft.IconButton(ft.Icons.MENU_OPEN, icon_size=20, icon_color=_ICON_INACTIVE, 
                                    on_click=toggle_sidebar_cb, tooltip="Toggle Sidebar") if toggle_sidebar_cb else ft.Container()
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.only(left=20, right=8)
                ),
                exit_btn,
                version_info,
            ],
            spacing=0, expand=True,
        )

        self.content    = col
        self.expand     = True
        self.bgcolor    = _SIDEBAR_BG
        self.border     = ft.Border(right=ft.border.BorderSide(1, _SIDEBAR_ACCENT))
        self._refresh()

    @property
    def selected_index(self) -> int:
        return self._selected_index

    @selected_index.setter
    def selected_index(self, value: int):
        self._selected_index = value
        # Update breadcrumb
        nav_labels = {0: "Dashboard", 1: "Holdings", 2: "Trade Entry", 3: "Trade History", 4: "Settings", 5: "Help"}
        self.breadcrumb.content.value = nav_labels.get(value, "Dashboard")
        self._refresh()

    def _handle_item_click(self, idx: int):
        class _FakeEvent:
            def __init__(self, control, idx):
                self.control = control
                self.selected_index = idx
        event = _FakeEvent(self, idx)
        event.control.selected_index = idx
        self._on_nav_change(event)

    def set_stats(self, portfolio_value: float, invested: float, pnl: float):
        """Update portfolio stats in sidebar"""
        try:
            # Use stored text references for direct updates
            self.stats_text_refs["portfolio_value"].value = f"₹ {portfolio_value:,.0f}"
            self.stats_text_refs["invested"].value = f"₹ {invested:,.0f}"
            
            # PnL with color coding
            pnl_color = "#10B981" if pnl >= 0 else "#EF4444"
            self.stats_text_refs["pnl"].value = f"₹ {pnl:,.0f}"
            self.stats_text_refs["pnl"].color = pnl_color
            
            # Update the card
            try:
                self.stats_card.update()
            except:
                pass
        except Exception as e:
            pass

    def _refresh(self):
        if self._prev_item and self._prev_item.index != self._selected_index:
            try:
                self._prev_item.set_selected(False)
                self._prev_item.update()
            except Exception:
                pass

        new_item = next((it for it in self._items if it.index == self._selected_index), None)
        if new_item:
            try:
                new_item.set_selected(True)
                new_item.update()
            except Exception:
                pass
            self._prev_item = new_item
        
        try:
            self.breadcrumb.update()
        except:
            pass


def create_sidebar(page: ft.Page, on_nav_change, toggle_sidebar_cb=None) -> PremiumSidebar:
    return PremiumSidebar(page, on_nav_change, toggle_sidebar_cb)