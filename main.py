#!/usr/bin/env python3
"""
PTracker - Portfolio Tracker
Modern Tkinter Implementation with Premium Aesthetic
"""

import tkinter as tk
from tkinter import ttk
import sys
import os
import threading
from pathlib import Path
from typing import Dict, Callable
import atexit


from common.state import AppState
from common.database import initialize_database, close_all_connections
from ui_theme import ModernStyle
from ui_widgets import ModernButton
from ui_utils import center_window


def _install_macos_openpanel_stderr_filter() -> None:
    """Silence a noisy, harmless AppKit log line on macOS.

    Some macOS/Tk builds print to stderr:
      "The class 'NSOpenPanel' overrides the method identifier..."

    This is not a Python warning/exception; it's a Cocoa log line. We filter only
    that specific message to keep terminal output clean.
    """

    if sys.platform != "darwin":
        return

    try:
        original = sys.stderr
    except Exception:
        return

    needle_1 = "The class 'NSOpenPanel' overrides the method identifier"
    needle_2 = "This method is implemented by class 'NSWindow'"

    class _FilteredStderr:
        def __init__(self, wrapped):
            self._wrapped = wrapped
            self._buf = ""

        def write(self, s):
            try:
                text = str(s)
            except Exception:
                return 0

            self._buf += text
            if "\n" not in self._buf:
                return len(text)

            lines = self._buf.splitlines(True)
            self._buf = "" if lines[-1].endswith("\n") else lines.pop()  # keep partial

            out = []
            for line in lines:
                if needle_1 in line and needle_2 in line:
                    continue
                out.append(line)

            if out:
                try:
                    return self._wrapped.write("".join(out))
                except Exception:
                    return len(text)
            return len(text)

        def flush(self):
            try:
                if self._buf:
                    # If there is a partial line, pass it through.
                    self._wrapped.write(self._buf)
                    self._buf = ""
            except Exception:
                pass
            try:
                self._wrapped.flush()
            except Exception:
                pass

        def isatty(self):
            try:
                return self._wrapped.isatty()
            except Exception:
                return False

    try:
        sys.stderr = _FilteredStderr(original)
    except Exception:
        pass


class ViewManager:
    """Manages view lifecycle and navigation."""
    
    def __init__(self, container: tk.Frame, app_state=None):
        self.container = container
        self.app_state = app_state
        self.views: Dict[str, tk.Frame] = {}
        self.current_view: str = None
        self.view_classes: Dict[str, type] = {}
    
    def register_view(self, name: str, view_class: type):
        """Register a view class for lazy loading."""
        self.view_classes[name] = view_class
    
    def show_view(self, name: str):
        """Show a view, creating it if necessary."""
        if name not in self.views:
            # Lazy load: create view on first access
            view_class = self.view_classes.get(name)
            if not view_class:
                raise ValueError(f"View {name} not registered")
            # Pass app_state to view if it accepts it
            try:
                self.views[name] = view_class(self.container, app_state=self.app_state)
            except TypeError:
                # View doesn't accept app_state
                self.views[name] = view_class(self.container)
        
        # Hide current view
        if self.current_view and self.current_view in self.views:
            self.views[self.current_view].pack_forget()
            # Call on_hide if it exists
            if hasattr(self.views[self.current_view], 'on_hide'):
                self.views[self.current_view].on_hide()
        
        # Show new view
        self.views[name].pack(fill=tk.BOTH, expand=True)
        self.current_view = name
        
        # Call on_show if it exists
        if hasattr(self.views[name], 'on_show'):
            self.views[name].on_show()


class ModernFrame(tk.Frame):
    """Custom frame with modern styling."""
    
    def __init__(self, parent, bg: str = ModernStyle.BG_SECONDARY, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)


class Sidebar(tk.Frame):
    """Beautifully designed sidebar navigation with modern aesthetics."""
    
    def __init__(self, parent, on_navigate: Callable):
        # Rich, sophisticated color palette
        sidebar_bg = "#0f1419"  # Deep charcoal
        accent_primary = "#3b82f6"  # Vibrant blue
        accent_hover = "#60a5fa"  # Lighter blue
        accent_pressed = "#2563eb"  # Darker blue for press
        accent_gradient = "#1e3a8a"  # Deep blue gradient
        
        super().__init__(parent, bg=sidebar_bg, width=248)
        self.pack(side=tk.LEFT, fill=tk.Y)
        self.pack_propagate(False)
        
        self.on_navigate = on_navigate
        self.buttons = {}
        self._indicators: dict[int, tk.Frame] = {}
        self._icons: dict[str, tk.PhotoImage] = {}
        self._active_idx: int | None = None
        self._nav_labels: dict[int, str] = {}
        self._nav_has_icon: dict[int, bool] = {}
        self._collapsed = False
        self.sidebar_bg = sidebar_bg
        self.accent_primary = accent_primary
        self.accent_hover = accent_hover
        self.accent_pressed = accent_pressed

        # Size tokens
        self._w_expanded = 240
        self._w_collapsed = 78
        self._btn_w_expanded = 200
        self._btn_w_collapsed = 52
        
        # Elegant header with brand identity
        title_frame = tk.Frame(self, bg=sidebar_bg)
        title_frame.pack(fill=tk.X, padx=16, pady=(20, 16))

        # Refined toggle button with modern styling
        self._toggle_btn = ModernButton(
            title_frame,
            text="☰",
            command=self.toggle,
            invoke_on_press=True,
            bg=accent_primary,
            fg="#ffffff",
            canvas_bg=sidebar_bg,
            width=42,
            height=42,
            radius=10,
            font=(ModernStyle.FONT_FAMILY, 16, "bold"),
        )
        self._toggle_btn.pack(side=tk.LEFT)

        self._title_stack = tk.Frame(title_frame, bg=sidebar_bg)
        self._title_stack.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(14, 0))

        self._title_lbl = tk.Label(
            self._title_stack,
            text="PTracker",
            font=(ModernStyle.FONT_FAMILY, 23, "bold"),
            bg=sidebar_bg,
            fg="#ffffff",
            anchor="w",
        )
        self._title_lbl.pack(anchor="w")
        self._subtitle_lbl = tk.Label(
            self._title_stack,
            text="Portfolio Management",
            font=(ModernStyle.FONT_FAMILY, 12),
            bg=sidebar_bg,
            fg="#64748b",
            anchor="w",
        )
        self._subtitle_lbl.pack(anchor="w", pady=(2, 0))
        
        # Elegant separator with gradient effect
        sep_frame = tk.Frame(self, bg=sidebar_bg, height=3)
        sep_frame.pack(fill=tk.X, padx=16, pady=(12, 16))
        tk.Frame(sep_frame, bg="#1e293b", height=1).pack(fill=tk.X)
        tk.Frame(sep_frame, bg=accent_primary, height=1).pack(fill=tk.X, pady=(1, 0))

        # Refined section label with better typography
        self._menu_lbl = tk.Label(
            self,
            text="NAVIGATION",
            font=(ModernStyle.FONT_FAMILY, 11, "bold"),
            bg=sidebar_bg,
            fg="#64748b",
            anchor="w",
        )
        self._menu_lbl.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        # Navigation items — emoji prefix gives visual context even without PNG icons
        nav_items = [
            ("📊  Dashboard",    0),
            ("💼  My Holdings",  1),
            ("➕  Trade Entry",  2),
            ("📜  Trade History",3),
            ("⚙️  Settings",     4),
            ("❓  Help",         5),
        ]

        self._nav_labels = {idx: label for (label, idx) in nav_items}

        # Optional PNG icons: drop files into `assets/icons/`.
        self._try_load_icon("Dashboard", "dashboard.png")
        self._try_load_icon("My Holdings", "holdings.png")
        self._try_load_icon("Trade Entry", "trade_entry.png")
        self._try_load_icon("Trade History", "trade_history.png")
        self._try_load_icon("Settings", "settings.png")
        self._try_load_icon("Help", "help.png")
        
        for label, idx in nav_items:
            self._add_nav_button(label, idx)
        
        # Spacer with sidebar background
        tk.Frame(self, bg=sidebar_bg).pack(fill=tk.BOTH, expand=True)
        
        # Sophisticated exit button with refined styling
        exit_btn = ModernButton(
            self,
            text="Exit App",
            command=lambda: parent.quit(),
            invoke_on_press=True,
            bg="#dc2626",  # Bold red for exit
            fg="#ffffff",
            canvas_bg=sidebar_bg,
            width=208,
            height=46,
            radius=10,
            font=(ModernStyle.FONT_FAMILY, 14, "bold"),
        )
        exit_btn.pack(padx=20, pady=(10, 20), anchor="s")
        self._exit_btn = exit_btn

    def set_active(self, idx: int) -> None:
        self._active_idx = idx
        for i, btn in self.buttons.items():
            indicator = self._indicators.get(i)
            if i == idx:
                if indicator is not None:
                    indicator.configure(bg=self.accent_primary, width=3)  # Vibrant indicator
                btn.set_palette(
                    bg=self.accent_primary,
                    fg="#ffffff",
                    hover_bg=self.accent_hover,
                    pressed_bg=self.accent_pressed,
                )
            else:
                if indicator is not None:
                    indicator.configure(bg=self.sidebar_bg, width=3)
                btn.set_palette(
                    bg="#1e293b",  # Subtle background
                    fg="#cbd5e1",  # Soft text color
                    hover_bg="#334155",  # Gentle hover
                    pressed_bg="#0f172a",  # Subtle press
                )

    def _try_load_icon(self, label: str, filename: str, *, subsample: int = 2) -> None:
        try:
            path = Path(__file__).resolve().parent.parent / "common" / "assets" / "icons" / filename
            if not path.exists():
                return
            img = tk.PhotoImage(file=str(path))
            s = max(1, int(subsample))
            if s > 1:
                img = img.subsample(s, s)
            self._icons[label] = img
        except Exception:
            return
    
    def _add_nav_button(self, label: str, idx: int):
        """Add a beautifully styled navigation button with smooth interactions."""
        row = tk.Frame(self, bg=self.sidebar_bg)
        row.pack(fill=tk.X, padx=16, pady=3)

        indicator = tk.Frame(row, bg=self.sidebar_bg, width=3)
        indicator.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        self._indicators[idx] = indicator

        icon = self._icons.get(label)
        self._nav_has_icon[idx] = bool(icon)
        btn = ModernButton(
            row,
            text=label,
            command=lambda: self.on_navigate(idx),
            invoke_on_press=True,
            icon=icon,
            bg="#1e293b",  # Refined neutral background
            fg="#cbd5e1",  # Soft text
            canvas_bg=self.sidebar_bg,
            width=self._btn_w_expanded,
            height=46,
            radius=8,
            font=(ModernStyle.FONT_FAMILY, 14, "bold"),
            text_anchor="w",
            text_padx=14,
        )
        btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.buttons[idx] = btn

    def toggle(self) -> None:
        """Collapse/expand the sidebar."""
        self._collapsed = not bool(self._collapsed)

        # Emoji abbreviations used when sidebar is collapsed (no PNG icons)
        abbr = {
            0: "📊",
            1: "💼",
            2: "➕",
            3: "📜",
            4: "⚙️",
            5: "❓",
        }

        if self._collapsed:
            self.configure(width=self._w_collapsed)
            try:
                self._title_stack.pack_forget()
            except Exception:
                pass
            try:
                self._menu_lbl.pack_forget()
            except Exception:
                pass
            try:
                self._toggle_btn.set_text("→")
            except Exception:
                pass

            for idx, btn in self.buttons.items():
                try:
                    if self._nav_has_icon.get(idx, False):
                        btn.set_text("")
                    else:
                        btn.set_text(abbr.get(idx, ""))
                    btn.set_size(width=self._btn_w_collapsed)
                except Exception:
                    pass

            try:
                self._exit_btn.set_text("⏻")
                self._exit_btn.set_size(width=self._btn_w_collapsed)
            except Exception:
                pass
        else:
            self.configure(width=self._w_expanded)
            try:
                self._title_stack.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
            except Exception:
                pass
            try:
                self._menu_lbl.pack(fill=tk.X, padx=16, pady=(6, 8))
            except Exception:
                pass
            try:
                self._toggle_btn.set_text("≡")
            except Exception:
                pass

            for idx, btn in self.buttons.items():
                try:
                    btn.set_text(self._nav_labels.get(idx, ""))
                    btn.set_size(width=self._btn_w_expanded)
                except Exception:
                    pass

            try:
                self._exit_btn.set_text("Exit")
                self._exit_btn.set_size(width=self._btn_w_expanded)
            except Exception:
                pass

        # Ensure active styling remains correct.
        try:
            if self._active_idx is not None:
                self.set_active(self._active_idx)
        except Exception:
            pass


class PTrackerApp:
    """Main application controller."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PTracker - Portfolio Tracker")
        self.root.geometry("1500x1150")

        # Center on screen after initial sizing
        try:
            center_window(self.root)
        except Exception:
            pass

        # Optional: PNG app icon (place it at `assets/app_icon.png`)
        self._app_icon: tk.PhotoImage | None = None
        self._set_app_icon()
        
        # Apply theme
        ModernStyle.apply_theme(root)
        
        # Initialize database
        initialize_database()
        
        # Store for cleanup
        atexit.register(lambda: close_all_connections(optimize=False))
        
        # Create app state
        self.app_state = AppState(root)
        try:
            self.app_state.init_data_cache()
        except Exception as e:
            print(f"Warning: Could not initialize data cache: {e}")
        
        # Main container
        main_frame = ModernFrame(root, bg=ModernStyle.BG_PRIMARY)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Sidebar
        self.sidebar = Sidebar(main_frame, self.navigate)
        
        # Content area
        self.content_frame = ModernFrame(main_frame, bg=ModernStyle.BG_PRIMARY)
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # View manager (with app_state)
        self.view_manager = ViewManager(self.content_frame, app_state=self.app_state)
        
        # Initialize views (import them here to avoid circular imports)
        self._setup_views()
        
        # Show first view
        self.navigate(0)

    def _set_app_icon(self) -> None:
        try:
            from pathlib import Path
            import sys
            base = Path(__file__).resolve().parent / "common"
            candidates = [
                base / "assets" / "app_icon.png",
                # Fallbacks (if you haven’t provided a dedicated app icon yet)
                base / "assets" / "icons" / "app_icon.png",
                base / "assets" / "icons" / "dashboard.png",
            ]
            icon_path = next((p for p in candidates if p.exists()), None)
            if icon_path is None:
                print("[ICON] No valid icon file found in candidates.")
                return

            self._app_icon = tk.PhotoImage(file=str(icon_path))
            # iconphoto affects window icons on Windows/X11
            try:
                self.root.iconphoto(True, self._app_icon)
            except Exception:
                # Some Tk variants prefer the wm call.
                try:
                    self.root.tk.call("wm", "iconphoto", self.root._w, self._app_icon)  # type: ignore
                except Exception:
                    pass
            
            # macOS specific: setting the Dock icon requires a specific Tk call in some Tk wrapper versions
            if sys.platform == "darwin":
                try:
                    # In newer Tk on Mac, you can sometimes set the dock icon specifically
                    self.root.tk.call("tk::mac::iconBitmap", self.root._w, 128, 128, "-kind", "photo", "-photo", self._app_icon)
                except Exception:
                    pass
            print(f"[ICON] Successfully loaded icon from {icon_path}")
        except Exception as e:
            print(f"[ICON] Error setting app icon: {e}")
            self._app_icon = None
    
    def _setup_views(self):
        """Register all views."""
        from views.holdings_view import HoldingsView
        from views.dashboard_view import DashboardView
        from views.trade_entry_view import TradeEntryView
        from views.trade_history_view import TradeHistoryView
        from views.settings_view import SettingsView
        from views.help_view import HelpView
        
        self.view_manager.register_view('dashboard', DashboardView)
        self.view_manager.register_view('holdings', HoldingsView)
        self.view_manager.register_view('trade_entry', TradeEntryView)
        self.view_manager.register_view('trade_history', TradeHistoryView)
        self.view_manager.register_view('settings', SettingsView)
        self.view_manager.register_view('help', HelpView)
    
    def navigate(self, view_idx: int):
        """Navigate to a view by index."""
        views = ['dashboard', 'holdings', 'trade_entry', 'trade_history', 'settings', 'help']
        if 0 <= view_idx < len(views):
            try:
                if hasattr(self, "sidebar") and hasattr(self.sidebar, "set_active"):
                    self.sidebar.set_active(view_idx)
                self.view_manager.show_view(views[view_idx])
            except Exception as e:
                print(f"Error loading view {views[view_idx]}: {e}")


def main():
    """Application entry point."""
    _install_macos_openpanel_stderr_filter()
    root = tk.Tk()
    
    # Cleanup on exit
    def on_closing():
        try:
            close_all_connections(optimize=False)
        except:
            pass
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    app = PTrackerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
