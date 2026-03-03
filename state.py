import flet as ft
from typing import Callable, Any, Dict

class AppState:
    """Central state manager avoiding Flet lifecycle bugs."""
    
    def __init__(self, page: ft.Page):
        self.page: ft.Page = page
        
        # Navigation State
        self.nav_kwargs: Dict[str, Any] = {}
        self.navigate: Callable | None = None  # Populated in main.py
        self.sidebar: ft.Control | None = None # Populated in main.py
        
        # View State Storage (prevents data loss when switching tabs)
        self.trade_history_state: Dict[str, Any] = {}
        
    def refresh_ui(self):
        """Standardized way to refresh the active page safely."""
        try:
            self.page.update()
        except Exception:
            pass