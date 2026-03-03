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
from database import initialize_database

def main(page: ft.Page):
    # Ensure database is updated
    initialize_database()

    # macOS style setup
    page.title = "Portfolio Tracker"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1500
    page.window.height = 1200
    page.window.resizable = False
    page.window.maximized = False
    page.padding = 0

    # Modern font
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.YELLOW)

    app_state = AppState(page)
    app_state.views = {}  # Initialize views dictionary for cross-view cache invalidation
    
    # Keyboard shortcuts handler
    def handle_keyboard(e):
        """Handle global keyboard shortcuts: Ctrl+K (search), Ctrl+N (new trade), Esc (close dialogs)"""
        if e.key == "Meta+k" or e.key == "Control+k":  # Ctrl+K or Cmd+K
            # Focus the active view's symbol filter if it has one
            active_idx = getattr(app_state, '_current_view_idx', 0)
            if active_idx == 1:  # Holdings
                from views.holdings_view import HoldingsView
                # TODO: Implement focus
        elif e.key == "Meta+n" or e.key == "Control+n":  # Ctrl+N
            # Navigate to Trade Entry view
            app_state.navigate(2)  # Trade Entry is index 2
        elif e.key == "Escape":  # Esc
            # Close any open dialogs
            if hasattr(page, '_close_dialogs'):
                page._close_dialogs()
    
    page.on_keyboard_event = handle_keyboard

    # ── LAZY VIEW CONSTRUCTION ──
    # Views are created on-demand (lazy loading) to avoid Flet re-rendering
    # a massive Stack with 6 hidden view trees on every navigation.
    # This was the ROOT CAUSE of slowness - even hidden controls in a Stack
    # caused expensive Flutter rendering on page.update()
    
    view_cache: dict[int, ft.Container] = {}
    _current_idx = [-1]  # Start at -1 so first navigate(0) triggers the swap
    
    # View classes in order: Dashboard, Holdings, TradeEntry, TradeHistory, Settings, Help
    view_classes = [DashboardView, HoldingsView, TradeEntryView,
                    TradeHistoryView, SettingsView, HelpView]
    
    # Single container for the active view (instead of Stack with 6 hidden views)
    # Smooth fade transitions when switching views
    active_view_container = ft.Container(
        expand=True,
        content=None,
        animate_opacity=300,  # 300ms fade transition
        opacity=0.0
    )
    
    def _get_or_create_view(idx: int) -> ft.Container:
        """Lazy-load view: create only when first accessed, then cache it."""
        if idx not in view_cache:
            v = view_classes[idx](app_state)
            v.expand = True
            view_cache[idx] = v
            app_state.views[idx] = v  # Also register in app_state for cross-view cache invalidation
        return view_cache[idx]

    def _prefetch_critical_views():
        """Pre-load Holdings and TradeHistory data on app startup (runs in background).
        Only rebuilds holdings when trades have changed since the last rebuild.
        """
        try:
            from engine import rebuild_holdings_if_needed
            rebuild_holdings_if_needed()

            holdings = _get_or_create_view(1)
            if hasattr(holdings, 'load_data'):
                holdings.load_data(_reload_brokers=True, use_cache=True)

            trade_history = _get_or_create_view(3)
            if hasattr(trade_history, '_is_preloading'):
                trade_history._is_preloading = True
            if hasattr(trade_history, 'load_data'):
                trade_history.load_data(_reload_brokers=True, use_cache=True)
            if hasattr(trade_history, '_is_preloading'):
                trade_history._is_preloading = False
        except Exception:
            pass


    def show_loading(idx):
        # Show a loading spinner overlay for the active view
        active_view = view_cache.get(idx)
        if active_view and hasattr(active_view, 'loading_ring'):
            active_view.loading_ring.visible = True
            try:
                active_view.loading_ring.update()
            except Exception:
                pass

    def hide_loading(idx):
        active_view = view_cache.get(idx)
        if active_view and hasattr(active_view, 'loading_ring'):
            active_view.loading_ring.visible = False
            try:
                active_view.loading_ring.update()
            except Exception:
                pass

    def navigate(idx, **kwargs):
        app_state.nav_kwargs = kwargs

        if hasattr(app_state, 'sidebar'):
            app_state.sidebar.selected_index = idx

        prev = _current_idx[0]
        if prev != idx:
            _current_idx[0] = idx

            prev_view = view_cache.get(prev)
            if prev_view and hasattr(prev_view, "did_unmount"):
                prev_view.did_unmount()

            # Get or create new view (lazy loading)
            active_view = _get_or_create_view(idx)

            # Swap view content
            active_view_container.content = active_view
            active_view_container.opacity = 1.0  # Fade in the new view

            # Now that view is in the tree, call did_mount()
            if hasattr(active_view, "did_mount"):
                active_view.did_mount()

            # Show loading indicator right away
            show_loading(idx)
            # Don't call any updates - let Flet handle rendering
            # Views will update themselves when load_data() completes and calls render_table() etc.

        # Load data for the new view
        active_view = view_cache.get(idx)
        if active_view and hasattr(active_view, 'load_data'):
            # Detect upfront whether this view accepts _reload_brokers
            _uses_reload_param = getattr(active_view, '_has_reload_brokers_param', None)
            if _uses_reload_param is None:
                import inspect
                _uses_reload_param = '_reload_brokers' in inspect.signature(active_view.load_data).parameters
                active_view._has_reload_brokers_param = _uses_reload_param

            # If data is already cached, render instantly on the UI thread — no spinner, no thread hop.
            # load_data() detects the cache hit and calls render_table() synchronously.
            # If it's a cache miss (shouldn't happen after prefetch), load_data() spawns its own
            # background thread internally, so we still never block the UI thread.
            has_cache = (
                getattr(active_view, '_data_loaded', False) and
                getattr(active_view, 'current_df', None) is not None
            )
            if has_cache:
                try:
                    if _uses_reload_param:
                        active_view.load_data(_reload_brokers=False)
                    else:
                        active_view.load_data()
                except Exception:
                    pass
            else:
                # First visit or cache invalidated: show spinner, load in background thread
                show_loading(idx)
                def bg_load():
                    try:
                        if _uses_reload_param:
                            active_view.load_data()
                        else:
                            active_view.load_data()
                    finally:
                        hide_loading(idx)
                threading.Thread(target=bg_load, daemon=True).start()
        


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
        try:
            sidebar_container.update()  # Only update the sidebar container, not the entire page
        except Exception:
            pass

    sidebar = create_sidebar(page, nav_change, toggle_sidebar)
    app_state.sidebar = sidebar
    app_state._sidebar = sidebar  # Also store as _sidebar for views to access
    sidebar_container.content = sidebar

    # Single container for active view (instead of Stack with 6 hidden views)
    # This eliminates the Flet rendering bottleneck from having 6 large control
    # trees in the page tree, even when hidden
    content_area = ft.Container(
        content=active_view_container,
        expand=True,
        padding=ft.Padding(top=10, left=30, right=30, bottom=30),
        bgcolor="#0A0A0A"
    )

    # page.add() now has a much simpler tree:
    # Row[
    #   Sidebar,
    #   Container -> active_view_container (initially empty, swapped via navigate())
    # ]

    # page.add() sends the ENTIRE page tree (including all overlay pickers) to
    # the Flutter client in one shot. Every FilePicker is already in page.overlay.
    page.add(
        ft.Row(
            [sidebar_container, content_area],
            expand=True,
            spacing=0
        )
    )

    # Pre-load Holdings data in background while user sees Dashboard
    threading.Thread(target=_prefetch_critical_views, daemon=True).start()

    # Navigate to Dashboard
    navigate(0)

if __name__ == "__main__":
    ft.run(main)