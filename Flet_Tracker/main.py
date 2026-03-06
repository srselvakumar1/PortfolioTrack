import flet as ft
import os
import time
import threading
import inspect
import atexit
from flet_app.common.state import AppState
from flet_app.components.navigation import create_sidebar

from flet_app.views.dashboard_view import DashboardView
from flet_app.views.settings_view import SettingsView
from flet_app.views.tradehistory_view import TradeHistoryView
from flet_app.views.holdings_view import HoldingsView
from flet_app.views.trade_entry_view import TradeEntryView
from flet_app.views.help_view import HelpView
from flet_app.common.database import initialize_database, close_all_connections

def main(page: ft.Page):
    # Ensure database is updated
    initialize_database()

    # Always close pooled DB connections on process exit.
    try:
        atexit.register(lambda: close_all_connections(optimize=False))
    except Exception:
        pass

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

    # ── Shutdown handling ──
    # Do NOT block the OS title-bar close button. Some Flet builds don't reliably
    # emit a close-request event, which would leave the app unable to close if
    # prevent_close=True.
    page.window.prevent_close = False

    def request_exit(reason: str = "", _from_ui_dispatch: bool = False):
        """Best-effort app shutdown across Flet versions/platforms.

        Important: some Flet builds expose close APIs that return successfully but
        don't actually terminate the process (or are blocked by prevent_close).
        To guarantee exit, we always schedule a short hard-exit fallback.
        """
        if getattr(page, "_exiting", False):
            return
        page._exiting = True

        # Always schedule a hard-exit fallback FIRST. If any cleanup or UI close
        # path blocks/hangs, we still guarantee termination.
        def _hard_exit():
            os._exit(0)
        try:
            threading.Timer(0.35, _hard_exit).start()
        except Exception:
            os._exit(0)

        # Best-effort: close pooled DB connections without blocking the UI.
        def _close_db_best_effort():
            try:
                close_all_connections(optimize=False)
            except Exception:
                pass
        try:
            threading.Thread(target=_close_db_best_effort, daemon=True).start()
        except Exception:
            pass

        # UI operations must run on the UI thread. If Exit is triggered from a
        # background thread (e.g., sidebar click handler), dispatch the UI close
        # logic via page.run_task and return.
        try:
            if not _from_ui_dispatch and threading.current_thread() is not threading.main_thread() and hasattr(page, "run_task"):
                async def _ui_dispatch():
                    try:
                        request_exit(reason, _from_ui_dispatch=True)
                    except Exception:
                        pass
                try:
                    page.run_task(_ui_dispatch)
                except Exception:
                    pass
                return
        except Exception:
            pass

        # Allow OS close to proceed.
        try:
            page.window.prevent_close = False
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass

        # Try the most compatible close APIs. Important: call them from an async
        # task so any coroutine return values are awaited and don't trigger warnings.
        if hasattr(page, "run_task"):
            async def _attempt_close_async():
                for fn in (
                    getattr(page, "window_close", None),
                    getattr(getattr(page, "window", None), "close", None),
                    getattr(getattr(page, "window", None), "destroy", None),
                ):
                    if not callable(fn):
                        continue
                    try:
                        res = fn()
                        if inspect.isawaitable(res):
                            await res
                    except Exception:
                        pass
            try:
                page.run_task(_attempt_close_async)
            except Exception:
                pass
        else:
            # Fallback for older runtimes without run_task.
            try:
                if hasattr(page, "window_close"):
                    page.window_close()
            except Exception:
                pass
            try:
                if hasattr(page.window, "close"):
                    page.window.close()
            except Exception:
                pass
            try:
                if hasattr(page.window, "destroy"):
                    page.window.destroy()
            except Exception:
                pass

    # Expose to other components (e.g., sidebar Exit)
    page._request_exit = request_exit

    def on_window_event(e):
        # Flet can emit slightly different close event strings across platforms/versions.
        data = str(getattr(e, "data", "") or "").lower()
        if "close" in data:
            request_exit("window")

    # Wire multiple hooks for compatibility across Flet versions.
    try:
        page.window.on_event = on_window_event
    except Exception:
        pass
    try:
        page.on_window_event = on_window_event
    except Exception:
        pass
    try:
        page.on_close = lambda e: request_exit("page")
    except Exception:
        pass

    app_state = AppState(page)
    app_state.views = {}  # Initialize views dictionary for cross-view cache invalidation

    # Load all small datasets into memory once so view switching doesn't touch SQLite.
    # This is intentionally blocking; the DB is small and this keeps first navigation snappy.
    try:
        app_state.init_data_cache()
    except Exception:
        # If cache init fails for any reason, views can still fall back to their own caches.
        pass

    # Keyboard shortcuts handler
    def handle_keyboard(e):
        """Handle global keyboard shortcuts: Ctrl+K (search), Ctrl+N (new trade), Esc (close dialogs)"""
        if e.key == "Meta+k" or e.key == "Control+k":  # Ctrl+K or Cmd+K
            pass  # TODO: focus symbol search
        elif e.key == "Meta+n" or e.key == "Control+n":  # Ctrl+N
            app_state.navigate(2)  # Trade Entry is index 2
        elif e.key == "Escape":  # Esc
            if hasattr(page, '_close_dialogs'):
                page._close_dialogs()

    page.on_keyboard_event = handle_keyboard

    # ── LAZY VIEW CONSTRUCTION ──
    # Views are created on-demand (lazy loading) to avoid Flet re-rendering
    # a massive Stack with 6 hidden view trees on every navigation.

    view_cache: dict[int, ft.Container] = {}
    _current_idx = [-1]  # Start at -1 so first navigate(0) triggers the swap
    _prefetch_lock = threading.Lock()  # Protect view creation during prefetch

    # View classes in order: Dashboard, Holdings, TradeEntry, TradeHistory, Settings, Help
    view_classes = [DashboardView, HoldingsView, TradeEntryView,
                    TradeHistoryView, SettingsView, HelpView]

    # Single active host: only the current view is mounted in the tree.
    # This avoids hidden heavy views participating in layout/diff.
    active_view_host = ft.Container(expand=True)


    def _get_or_create_view(idx: int) -> ft.Container:
        """Lazy-load view: create only when first accessed, then cache it.
        Thread-safe via _prefetch_lock to prevent double-creation during prefetch."""
        with _prefetch_lock:
            if idx not in view_cache:
                try:
                    v = view_classes[idx](app_state)
                    v.expand = True
                    view_cache[idx] = v
                    app_state.views[idx] = v
                except Exception as ex:
                    # Surface the error in the UI so "click does nothing" becomes debuggable.
                    try:
                        msg = ft.SnackBar(ft.Text(f"Failed to open view: {ex}"))
                        if hasattr(app_state.page, 'open'):
                            app_state.page.open(msg)
                        else:
                            app_state.page.snack_bar = msg
                            msg.open = True
                            msg.update()
                    except Exception:
                        pass
                    raise
        return view_cache[idx]

    def _warm_startup_db_state():
        """Warm up DB-derived state only (no UI/view rendering).

        Keeps the app responsive on startup by avoiding heavy pandas work
        in background threads while the user is interacting.
        """
        try:
            from engine import rebuild_holdings_on_startup
            rebuild_holdings_on_startup()
        except Exception:
            pass

        # Precompute Trade History running stats once at startup (DB-only, no UI)
        try:
            from engine import rebuild_trade_calcs_on_startup
            rebuild_trade_calcs_on_startup()
        except Exception:
            pass

        # Warm dashboard caches once so switching to Dashboard does not trigger calculations.
        try:
            from engine import (
                get_dashboard_metrics,
                get_metrics_by_broker,
                get_top_worst_performers,
                get_actionable_insights,
                get_tax_harvesting_opportunities,
            )
            get_dashboard_metrics(force_refresh=False)
            get_metrics_by_broker()
            get_top_worst_performers(3)
            get_actionable_insights()
            get_tax_harvesting_opportunities(500.0)
        except Exception:
            pass

        # Re-sync in-memory datasets after any startup rebuilds.
        try:
            app_state.refresh_data_cache()
        except Exception:
            pass

    def show_loading(idx):
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
        _profile = os.environ.get("PTRACKER_NAV_PROFILE")
        _nav_start = time.perf_counter() if _profile else None

        if hasattr(app_state, 'sidebar'):
            app_state.sidebar.selected_index = idx

        prev = _current_idx[0]
        if prev != idx:
            _current_idx[0] = idx

            prev_view = view_cache.get(prev)
            if prev_view and hasattr(prev_view, "did_unmount"):
                prev_view.did_unmount()

            # Lazily create the target view (first visit only)
            _t_create = time.perf_counter() if _profile else None
            active_view = _get_or_create_view(idx)
            if _t_create:
                print(f"  [create-view] idx={idx} took {time.perf_counter() - _t_create:.3f}s")

            # Swap the active view content.
            _t_swap = time.perf_counter() if _profile else None
            try:
                active_view_host.content = active_view
                active_view_host.update()
            except Exception:
                pass
            if _t_swap:
                print(f"  [swap-view] idx={idx} took {time.perf_counter() - _t_swap:.3f}s")

            # Call did_mount — but set a flag so it does NOT call load_data()
            # (we handle data loading below to prevent double-loading)
            _t_mount = time.perf_counter() if _profile else None
            active_view._skip_load_in_did_mount = True
            if hasattr(active_view, "did_mount"):
                active_view.did_mount()
            active_view._skip_load_in_did_mount = False
            if _t_mount:
                print(f"  [did-mount] idx={idx} took {time.perf_counter() - _t_mount:.3f}s")

        # Load data for the view
        active_view = view_cache.get(idx)
        if active_view and hasattr(active_view, 'load_data'):
            # Detect upfront whether this view accepts _reload_brokers
            _uses_reload_param = getattr(active_view, '_has_reload_brokers_param', None)
            if _uses_reload_param is None:
                import inspect
                _uses_reload_param = '_reload_brokers' in inspect.signature(active_view.load_data).parameters
                active_view._has_reload_brokers_param = _uses_reload_param

            # "Calculate once" policy: do NOT refresh/re-render during view switching.
            # Only load when first opened or after cache invalidation.
            if hasattr(active_view, 'current_df'):
                has_cache = (
                    getattr(active_view, '_data_loaded', False)
                    and getattr(active_view, 'current_df', None) is not None
                )
            else:
                has_cache = bool(getattr(active_view, '_data_loaded', False))

            if not has_cache:
                # First visit or cache invalidated: show spinner, load in background
                show_loading(idx)

                # IMPORTANT: call load_data() on the UI thread.
                # Individual views are responsible for spawning background work as needed.
                _t_load = time.perf_counter() if _profile else None
                try:
                    if _uses_reload_param:
                        # Reload broker options only if the dropdown has not been populated yet.
                        _need_brokers = False
                        try:
                            bf = getattr(active_view, 'broker_filter', None)
                            if bf is not None:
                                opts = getattr(bf, 'options', None)
                                if not opts or len(opts) <= 1:
                                    _need_brokers = True
                        except Exception:
                            _need_brokers = True
                        active_view.load_data(_reload_brokers=_need_brokers)
                    else:
                        active_view.load_data()
                finally:
                    if _t_load:
                        print(f"  [load-data] idx={idx} took {time.perf_counter() - _t_load:.3f}s")
                    hide_loading(idx)
        
        if _nav_start:
            print(f"[nav-total] idx={idx} took {time.perf_counter() - _nav_start:.3f}s")


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
            sidebar_container.update()
        except Exception:
            pass

    sidebar = create_sidebar(page, nav_change, toggle_sidebar)
    app_state.sidebar = sidebar
    app_state._sidebar = sidebar
    sidebar_container.content = sidebar

    content_area = ft.Container(
        content=active_view_host,
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

    # Warm DB-derived state in the background (no view rendering)
    threading.Thread(target=_warm_startup_db_state, daemon=True).start()

    # Navigate to Dashboard
    navigate(0)

if __name__ == "__main__":
    ft.run(main)
