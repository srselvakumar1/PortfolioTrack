import flet as ft

# ─── Nav item config: (icon_outlined, icon_filled, label, index) ──────────────
_NAV_ITEMS = [
    (ft.Icons.SPACE_DASHBOARD_OUTLINED,         ft.Icons.SPACE_DASHBOARD,           "Dashboard",     0),
    (ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,  ft.Icons.ACCOUNT_BALANCE_WALLET,    "Holdings",      1),
    (ft.Icons.ADD_CIRCLE_OUTLINE,               ft.Icons.ADD_CIRCLE,                "Trade Entry",   2),
    (ft.Icons.CANDLESTICK_CHART_OUTLINED,       ft.Icons.CANDLESTICK_CHART,         "Trade History", 3),
    (ft.Icons.SETTINGS_OUTLINED,                ft.Icons.SETTINGS,                  "Settings",      4),
    (ft.Icons.HELP_OUTLINE,                     ft.Icons.HELP,                      "Help",          5),
    (ft.Icons.LOGOUT,                           ft.Icons.LOGOUT,                    "Exit",          6),
]

# ─── Colour palette ────────────────────────────────────────────────────────────
_SIDEBAR_BG     = "#0E1117"
_ACTIVE_BG      = "#1A2744"
_ACTIVE_ACCENT  = "#3B82F6"       # vivid blue left border
_TEXT_ACTIVE    = "#FFFFFF"
_TEXT_INACTIVE  = "#8B9CB6"
_ICON_ACTIVE    = "#60A5FA"
_ICON_INACTIVE  = "#4A5568"


class _NavItem(ft.Container):
    """A single sidebar navigation row."""

    def __init__(self, icon_off, icon_on, label: str, index: int,
                 on_click_cb):
        super().__init__()
        self.index = index
        self._icon_off  = icon_off
        self._icon_on   = icon_on
        self._label_str = label
        self._on_click_cb = on_click_cb

        # Sub-controls we need to mutate on select/deselect
        self._left_bar = ft.Container(width=4, border_radius=4,
                                      bgcolor="transparent", height=36)
        self._icon_ctrl = ft.Icon(icon_off, size=22, color=_ICON_INACTIVE)
        self._label_ctrl = ft.Text(
            label,
            size=14,
            weight=ft.FontWeight.W_500,
            color=_TEXT_INACTIVE,
        )

        self.content = ft.Row([
            self._left_bar,
            ft.Container(width=10),
            self._icon_ctrl,
            ft.Container(width=10),
            self._label_ctrl,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)

        self.height       = 48
        self.border_radius = ft.BorderRadius(0, 8, 8, 0)
        self.bgcolor      = "transparent"
        self.margin       = ft.margin.only(right=16, bottom=2)
        self.on_click     = self._handle_click
        self.on_hover     = self._handle_hover

        self._selected = False

    def _handle_click(self, e):
        self._on_click_cb(self.index)

    def _handle_hover(self, e):
        if not self._selected:
            self.bgcolor = "#131B2E" if e.data == "true" else "transparent"
            self.update()

    def set_selected(self, value: bool):
        self._selected = value
        if value:
            self._left_bar.bgcolor   = _ACTIVE_ACCENT
            self._icon_ctrl.color    = _ICON_ACTIVE
            self._icon_ctrl.name     = self._icon_on
            self._label_ctrl.color  = _TEXT_ACTIVE
            self._label_ctrl.weight  = ft.FontWeight.W_600
            self.bgcolor             = _ACTIVE_BG
        else:
            self._left_bar.bgcolor   = "transparent"
            self._icon_ctrl.color    = _ICON_INACTIVE
            self._icon_ctrl.name     = self._icon_off
            self._label_ctrl.color  = _TEXT_INACTIVE
            self._label_ctrl.weight  = ft.FontWeight.W_500
            self.bgcolor             = "transparent"


class PremiumSidebar(ft.Container):
    """
    A fully custom premium sidebar that replaces NavigationRail.
    Exposes `selected_index` so main.py can keep the same API.
    """

    def __init__(self, page: ft.Page, on_nav_change, toggle_sidebar_cb=None):
        super().__init__()
        self._flet_page        = page
        self._on_nav_change    = on_nav_change
        self._selected_index   = 0
        self._prev_item: _NavItem | None = None   # FIX 3: track last selected item
        self._items: list[_NavItem] = []

        # ── Header ──────────────────────────────────────────────────────────
        header = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.SHOW_CHART, size=28, color=_ACTIVE_ACCENT),
                        ft.Container(width=10),
                        ft.Text("PortTrack", size=20, weight=ft.FontWeight.W_800,
                                 color=_TEXT_ACTIVE),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    ft.Text("Portfolio Tracker", size=11, color=_TEXT_INACTIVE,
                            weight=ft.FontWeight.W_400),
                ], spacing=4, tight=True, expand=True),
                ft.IconButton(ft.Icons.MENU_OPEN, 
                              on_click=toggle_sidebar_cb, 
                              icon_color=_ICON_INACTIVE, 
                              tooltip="Toggle Sidebar") if toggle_sidebar_cb else ft.Container()
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=ft.padding.only(left=20, right=10, top=28, bottom=24)
        )

        divider = ft.Container(
            content=ft.Divider(color="#1E2D45", height=1),
            padding=ft.padding.only(left=16, right=16, bottom=12)
        )

        # ── Section label ────────────────────────────────────────────────────
        section_label = ft.Container(
            content=ft.Text("MAIN MENU", size=10, color="#3D5070",
                             weight=ft.FontWeight.W_700),
            padding=ft.padding.only(left=20, bottom=6, top=8)
        )

        # ── Nav items (split: main 0-3, bottom 4-5) ──────────────────────────
        main_items  = []
        footer_items = []
        for icon_off, icon_on, label, idx in _NAV_ITEMS:
            if idx == 6:
                # Direct, high-priority Exit button
                async def force_quit(e):
                    try:
                        await self._flet_page.window.destroy()
                    except Exception as ex:
                        print(f"Error during exit: {ex}")
                
                exit_btn = ft.Container(
                    content=ft.Row([
                        ft.Container(width=14),
                        ft.Icon(icon_off, size=22, color=_ICON_INACTIVE),
                        ft.Container(width=10),
                        ft.Text(label, size=14, weight=ft.FontWeight.W_500, color=_TEXT_INACTIVE),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    height=48,
                    on_click=force_quit,
                    margin=ft.margin.only(right=16, bottom=2),
                    border_radius=ft.BorderRadius(0, 8, 8, 0),
                    tooltip="Close Application"
                )
                footer_items.append(exit_btn)
                continue

            item = _NavItem(icon_off, icon_on, label, idx, self._handle_item_click)
            self._items.append(item)
            if idx < 4:
                main_items.append(item)
            else:
                footer_items.append(item)

        # ── Footer section ───────────────────────────────────────────────────
        footer_divider = ft.Container(
            content=ft.Divider(color="#1E2D45", height=1),
            padding=ft.padding.only(left=16, right=16, top=8, bottom=8)
        )

        footer_label = ft.Container(
            content=ft.Text("SYSTEM", size=10, color="#3D5070",
                             weight=ft.FontWeight.W_700),
            padding=ft.padding.only(left=20, bottom=6)
        )

        # ── Version badge ─────────────────────────────────────────────────────
        version_badge = ft.Container(
            content=ft.Text("v1.0.0", size=10, color="#2A3F5F",
                             weight=ft.FontWeight.W_500),
            padding=ft.padding.only(left=20, bottom=20, top=4)
        )

        # ── Assemble sidebar column ──────────────────────────────────────────
        col = ft.Column(
            controls=[
                header,
                divider,
                section_label,
                *main_items,
                ft.Container(expand=True),   # pushes footer down
                footer_divider,
                footer_label,
                *footer_items,
                version_badge,
            ],
            spacing=0,
            expand=True,
        )

        self.content    = col
        self.expand     = True
        self.bgcolor    = _SIDEBAR_BG
        self.border     = ft.Border(right=ft.border.BorderSide(1, "#1A2744"))

        # Set initial selection
        self._refresh()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def selected_index(self) -> int:
        return self._selected_index

    @selected_index.setter
    def selected_index(self, value: int):
        self._selected_index = value
        self._refresh()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _handle_item_click(self, idx: int):
        # Mimic NavigationRail event by calling on_nav_change with a fake event
        class _FakeEvent:
            def __init__(self, control, idx):
                self.control = control
                self.selected_index = idx
        event = _FakeEvent(self, idx)
        event.control.selected_index = idx
        self._on_nav_change(event)

    def _refresh(self):
        """FIX 3: Only mutate the two items that changed (prev + new)."""
        # Deselect previous
        if self._prev_item and self._prev_item.index != self._selected_index:
            self._prev_item.set_selected(False)
            try:
                self._prev_item.update()
            except Exception:
                pass

        # Select new
        new_item = next((it for it in self._items if it.index == self._selected_index), None)
        if new_item:
            new_item.set_selected(True)
            try:
                new_item.update()
            except Exception:
                pass
            self._prev_item = new_item


# ── Public factory (keeps same API as before) ─────────────────────────────────

def create_sidebar(page: ft.Page, on_nav_change, toggle_sidebar_cb=None) -> PremiumSidebar:
    return PremiumSidebar(page, on_nav_change, toggle_sidebar_cb)
