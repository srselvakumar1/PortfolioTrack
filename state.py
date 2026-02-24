import flet as ft

class AppState:
    """Central state manager avoiding Flet lifecycle bugs."""
    def __init__(self, page: ft.Page):
        self.page = page
        self.nav_kwargs = {}
        self.navigate = None # Populated in main.py
        
    def refresh_ui(self):
        """Standardized way to refresh the active page safely."""
        self.page.update()
