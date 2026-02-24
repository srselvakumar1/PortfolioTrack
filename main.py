import flet as ft
import threading
from state import AppState
from components.navigation import create_sidebar

from views.dashboard_view import DashboardView
from views.settings_view import SettingsView
from views.tradehistory_view import TradeHistoryView
from views.holdings_view import HoldingsView
from views.trade_entry_view import TradeEntryView
from views.help_view import HelpView

class StubView(ft.Container):
    def __init__(self, title, app_state=None):
        super().__init__()
        self.expand = True
        self.content = ft.Text(title, size=24)

def main(page: ft.Page):
    # macOS style setup
    page.title = "Portfolio Tracker 1.0.0"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1700
    page.window.height = 1200
    page.run_task(page.window.center)
    page.padding = 0

    # Modern font
    page.fonts = {
        "Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
    }
    page.theme = ft.Theme(font_family="Inter", color_scheme_seed=ft.Colors.YELLOW)

    app_state = AppState(page)

    # ── FIX 2: Stack-based visibility — all views stay mounted, only visible toggles ──
    # Pre-create placeholder containers; actual views injected on first visit
    view_slots: list[ft.Container] = [
        ft.Container(expand=True, visible=(i == 0))
        for i in range(6)
    ]
    view_cache: dict[int, ft.Container] = {}
    _current_idx = [0]

    def _build_view(idx: int):
        """Construct the view lazily and insert into its slot."""
        if idx in view_cache:
            return
        if idx == 0:   v = DashboardView(app_state)
        elif idx == 1: v = HoldingsView(app_state)
        elif idx == 2: v = TradeEntryView(app_state)
        elif idx == 3: v = TradeHistoryView(app_state)
        elif idx == 4: v = SettingsView(app_state)
        elif idx == 5: v = HelpView(app_state)
        else:
            return
        v.expand = True
        view_cache[idx] = v
        view_slots[idx].content = v

    def navigate(idx, **kwargs):
        app_state.nav_kwargs = kwargs
        if hasattr(app_state, 'sidebar'):
            app_state.sidebar.selected_index = idx

        # FIX 1: Ensure view is constructed (might already be done by pre-warmer)
        _build_view(idx)

        # FIX 2: Toggle visibility instead of swapping content + re-rendering
        prev = _current_idx[0]
        if prev != idx:
            view_slots[prev].visible = False
            view_slots[idx].visible = True
            _current_idx[0] = idx
            try:
                view_slots[prev].update()
                view_slots[idx].update()
            except Exception:
                pass

        # Trigger initial data load only once
        active_view = view_cache.get(idx)
        if active_view:
            already_loaded = getattr(active_view, '_has_loaded_initial', False)
            if not already_loaded:
                if idx == 0 and hasattr(active_view, 'load_metrics'):
                    threading.Thread(target=active_view.load_metrics, daemon=True).start()
                    setattr(active_view, '_has_loaded_initial', True)
                elif idx == 1 and hasattr(active_view, 'load_data'):
                    threading.Thread(target=active_view.load_data, daemon=True).start()
                    setattr(active_view, '_has_loaded_initial', True)

    app_state.navigate = navigate

    sidebar_container = ft.Container(
        width=220,
        animate=ft.Animation(200, ft.AnimationCurve.DECELERATE),
    )

    def nav_change(e):
        idx = e.control.selected_index
        navigate(idx)
        
    def toggle_sidebar(e):
        sidebar_container.width = 60 if sidebar_container.width == 220 else 220
        page.update()

    sidebar = create_sidebar(page, nav_change, toggle_sidebar)
    app_state.sidebar = sidebar
    sidebar_container.content = sidebar

    page.appbar = ft.AppBar(
        title=ft.Text("Portfolio Tracker", size=16, color=ft.Colors.GREY),
        bgcolor="#0A0A0A",
        toolbar_height=40,
    )

    # FIX 2: All view slots live in a Stack inside the content area
    content_stack = ft.Stack(controls=view_slots, expand=True)
    content_area = ft.Container(
        content=content_stack,
        expand=True,
        padding=ft.Padding(top=10, left=30, right=30, bottom=30),
        bgcolor="#0A0A0A"
    )

    page.add(
        ft.Row(
            [sidebar_container, content_area],
            expand=True,
            spacing=0
        )
    )

    # FIX 6: Single update after all layout is assembled
    navigate(0)
    page.update()

    # ─── FIX 5: Pre-warm remaining views in background after startup ───
    def _prewarm_views():
        import time
        time.sleep(0.5)  # slight delay so Dashboard loads first
        for idx in [1, 2, 3, 4, 5]:
            try:
                _build_view(idx)
                view_slots[idx].update()
            except Exception:
                pass

    threading.Thread(target=_prewarm_views, daemon=True).start()

    # ─── Background Daily Sync ───
    from engine import auto_sync_if_needed
    def run_sync():
        auto_sync_if_needed()
        if 0 in view_cache:
            try:
                view_cache[0].load_metrics()
            except Exception:
                pass

    threading.Thread(target=run_sync, daemon=True).start()

if __name__ == "__main__":
    ft.run(main)
