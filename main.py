import flet as ft
import threading
import time
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
    page.padding = 0

    # Modern font
    page.fonts = {
        "Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
    }
    page.theme = ft.Theme(font_family="Inter", color_scheme_seed=ft.Colors.YELLOW)

    app_state = AppState(page)
    app_state.views = {}  # Initialize views dictionary for cross-view cache invalidation
    
    # Keyboard shortcuts handler
    def handle_keyboard(e):
        """Handle global keyboard shortcuts: Ctrl+K (search), Ctrl+N (new trade), Esc (close dialogs)"""
        if e.key == "Meta+k" or e.key == "Control+k":  # Ctrl+K or Cmd+K
            print("[KEYBOARD] Ctrl+K: Focus search")
            # Focus the active view's symbol filter if it has one
            active_idx = getattr(app_state, '_current_view_idx', 0)
            if active_idx == 1:  # Holdings
                from views.holdings_view import HoldingsView
                # TODO: Implement focus
        elif e.key == "Meta+n" or e.key == "Control+n":  # Ctrl+N
            print("[KEYBOARD] Ctrl+N: Add new trade")
            # Navigate to Trade Entry view
            app_state.navigate(2)  # Trade Entry is index 2
        elif e.key == "Escape":  # Esc
            print("[KEYBOARD] Esc: Close dialogs")
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
            print(f"[VIEW_INIT] Creating view {idx} ({view_classes[idx].__name__})")
            v = view_classes[idx](app_state)
            v.expand = True
            view_cache[idx] = v
            app_state.views[idx] = v  # Also register in app_state for cross-view cache invalidation
        return view_cache[idx]

    def _prefetch_critical_views():
        """Pre-load Holdings and TradeHistory data on app startup (runs in background).
        This ensures fast loading when user first navigates to these views.
        """
        try:
            print("[APP] Pre-loading critical view data in background...")
            
            # Recalculate holdings with corrected fee logic
            from engine import rebuild_holdings
            print("[APP] Rebuilding holdings with corrected fee calculations...")
            rebuild_holdings()
            print("[APP] Holdings rebuilt ✓")
            
            # Pre-load Holdings data
            holdings = _get_or_create_view(1)  # Create Holdings view
            if hasattr(holdings, 'load_data'):
                holdings.load_data(_reload_brokers=True, use_cache=True)
            print("[APP] Holdings data pre-loaded ✓")
            
            # Pre-load TradeHistory data (with default dates: yesterday to today)
            # Skip UI rendering during pre-load for performance
            trade_history = _get_or_create_view(3)  # Create TradeHistory view
            if hasattr(trade_history, '_is_preloading'):
                trade_history._is_preloading = True  # Skip rendering
            if hasattr(trade_history, 'load_data'):
                trade_history.load_data(_reload_brokers=True, use_cache=True)
            if hasattr(trade_history, '_is_preloading'):
                trade_history._is_preloading = False  # Re-enable rendering
            print("[APP] TradeHistory data pre-loaded ✓")
        except Exception as e:
            print(f"[APP] Pre-fetch warning: {e}")  # Non-fatal if it fails


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
        nav_start = time.time()
        app_state.nav_kwargs = kwargs
        
        # Timing: Sidebar update
        t1 = time.time()
        if hasattr(app_state, 'sidebar'):
            app_state.sidebar.selected_index = idx
        t2 = time.time()
        if t2 - t1 > 0.01:
            print(f"[NAV] Sidebar update: {(t2-t1)*1000:.1f}ms")

        prev = _current_idx[0]
        if prev != idx:
            _current_idx[0] = idx

            prev_view = view_cache.get(prev)
            if prev_view and hasattr(prev_view, "did_unmount"):
                prev_view.did_unmount()

            # Get or create new view (lazy loading)
            active_view = _get_or_create_view(idx)

            # Timing: Swap view content (instead of visibility toggle)
            t1 = time.time()
            active_view_container.content = active_view
            active_view_container.opacity = 1.0  # Fade in the new view
            t2 = time.time()
            if t2 - t1 > 0.01:
                print(f"[NAV] View swap: {(t2-t1)*1000:.1f}ms")

            # Now that view is in the tree, call did_mount()
            if hasattr(active_view, "did_mount"):
                active_view.did_mount()

            # Show loading indicator right away
            show_loading(idx)
            # Don't call any updates - let Flet handle rendering
            # Views will update themselves when load_data() completes and calls render_table() etc.

        # Non-blocking data load: show spinner, load in background
        active_view = view_cache.get(idx)
        if active_view and hasattr(active_view, 'load_data'):
            show_loading(idx)
            def bg_load():
                try:
                    load_start = time.time()
                    # Call load_data - if view has _reload_brokers param, only reload on first visit
                    import inspect
                    sig = inspect.signature(active_view.load_data)
                    if '_reload_brokers' in sig.parameters:
                        # Views like HoldingsView that cache data
                        if hasattr(active_view, '_data_loaded') and active_view._data_loaded:
                            active_view.load_data(_reload_brokers=False)
                        else:
                            active_view.load_data()
                    else:
                        # Views like DashboardView that don't have this parameter
                        active_view.load_data()
                    load_end = time.time()
                    if load_end - load_start > 0.05:
                        print(f"[NAV] load_data() for view {idx}: {(load_end-load_start)*1000:.1f}ms")
                finally:
                    hide_loading(idx)
                    # Views handle their own updates via render_table(), table.update(), etc.
                    # No page.update() needed here
            threading.Thread(target=bg_load, daemon=True).start()
        
        nav_end = time.time()
        total = nav_end - nav_start
        print(f"[NAV] Total nav time (main thread): {total*1000:.1f}ms")

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
        except Exception as ex:
            print(f"[SIDEBAR] Toggle error: {ex}")

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

    # Navigate to Dashboard (all views already built, no race possible)
    navigate(0)
    page.update()

if __name__ == "__main__":
    ft.run(main)