#!/usr/bin/env python3
"""Reusable UI widgets (kept separate to avoid circular imports)."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional
from pathlib import Path

from ui_theme import ModernStyle


class ModernButton(tk.Canvas):
    """Canvas-based button with hover/press effects.

    Works consistently across platforms and allows a more modern look than
    default tk.Button.
    """

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Optional[Callable[[], None]] = None,
        *,
        icon: tk.PhotoImage | None = None,
        icon_path: str | None = None,
        icon_subsample: int = 1,
        invoke_on_press: bool = False,
        bg: str = ModernStyle.ACCENT_PRIMARY,
        fg: str = ModernStyle.TEXT_ON_ACCENT,
        canvas_bg: Optional[str] = None,
        width: int = 120,
        height: int = 38,
        radius: int = 10,
        font=None,
        text_anchor: str = "c",
        text_padx: int = 14,
        disabled: bool = False,
        **kwargs,
    ):
        if canvas_bg is None:
            try:
                canvas_bg = str(parent.cget("bg"))
            except Exception:
                canvas_bg = ModernStyle.BG_PRIMARY

        super().__init__(
            parent,
            width=width,
            height=height,
            bg=canvas_bg,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )

        self._command = command
        self._text = text
        self._width = width
        self._height = height
        self._radius = max(6, int(radius))
        self._icon = icon if icon is not None else self._try_load_icon(icon_path, icon_subsample)
        self._icon_subsample = max(1, int(icon_subsample))
        self._icon_pad = 10

        self._invoke_on_press = bool(invoke_on_press)

        self._font = font if font is not None else ModernStyle.FONT_SUBHEADING
        self._text_anchor = (text_anchor or "c").lower()
        self._text_padx = max(0, int(text_padx))

        self._bg_normal = bg
        self._bg_hover = self._lighten_color(bg, 18)
        self._bg_pressed = self._darken_color(bg, 18)
        self._fg = fg

        self._disabled = disabled
        self._is_pressed = False

        # Some macOS/Tk builds occasionally miss `<ButtonRelease-1>` for
        # custom Canvas widgets during immediate UI swaps. To keep navigation
        # feeling snappy and reliable, we also schedule a command invoke on
        # press with a tiny delay, and guard against double-fires.
        self._press_invoke_after_id: str | None = None
        self._reset_after_id: str | None = None
        self._click_invoked: bool = False

        self.configure(cursor="arrow" if disabled else "hand2")
        self._redraw(self._bg_normal)

        if not disabled:
            self._bind_events()

    def set_disabled(self, disabled: bool) -> None:
        self._disabled = disabled
        self.configure(cursor="arrow" if disabled else "hand2")
        if disabled:
            self._unbind_events()
        else:
            self._bind_events()
        self._redraw(self._bg_normal)

    def set_palette(
        self,
        *,
        bg: str | None = None,
        fg: str | None = None,
        hover_bg: str | None = None,
        pressed_bg: str | None = None,
    ) -> None:
        if bg is not None:
            self._bg_normal = bg
            self._bg_hover = self._lighten_color(bg, 18)
            self._bg_pressed = self._darken_color(bg, 18)
        if fg is not None:
            self._fg = fg
        if hover_bg is not None:
            self._bg_hover = hover_bg
        if pressed_bg is not None:
            self._bg_pressed = pressed_bg
        self._redraw(self._bg_normal)

    def set_text(self, text: str) -> None:
        self._text = text
        self._redraw(self._bg_normal)

    def set_size(self, *, width: int | None = None, height: int | None = None) -> None:
        if width is not None:
            self._width = int(width)
            try:
                self.configure(width=self._width)
            except Exception:
                pass
        if height is not None:
            self._height = int(height)
            try:
                self.configure(height=self._height)
            except Exception:
                pass
        self._redraw(self._bg_normal)

    def _bind_events(self) -> None:
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _unbind_events(self) -> None:
        self.unbind("<Enter>")
        self.unbind("<Leave>")
        self.unbind("<Button-1>")
        self.unbind("<ButtonRelease-1>")

        # Cancel any pending callbacks.
        try:
            if self._press_invoke_after_id:
                self.after_cancel(self._press_invoke_after_id)
        except Exception:
            pass
        self._press_invoke_after_id = None
        try:
            if self._reset_after_id:
                self.after_cancel(self._reset_after_id)
        except Exception:
            pass
        self._reset_after_id = None

    def _redraw(self, fill: str) -> None:
        self.delete("all")

        # Shadow (subtle)
        shadow = "#000000"
        shadow_alpha = 0.08
        shadow_color = self._blend(shadow, ModernStyle.BG_PRIMARY, shadow_alpha)
        self._rounded_rect(2, 3, self._width - 1, self._height - 1, self._radius, fill=shadow_color, outline=shadow_color)

        # Surface
        # Avoid bright outlines (looks like "white lines" on some displays).
        outline = fill
        if self._disabled:
            fill = self._blend(fill, ModernStyle.BG_PRIMARY, 0.55)
        self._rounded_rect(1, 1, self._width - 2, self._height - 2, self._radius, fill=fill, outline=outline)

        # Text
        text_fill = ModernStyle.TEXT_TERTIARY if self._disabled else self._fg
        if self._icon is not None:
            if not str(self._text or "").strip():
                self.create_image(self._width // 2, self._height // 2, image=self._icon)
            else:
                x_icon = self._icon_pad + (self._icon.width() // 2)
                self.create_image(x_icon, self._height // 2, image=self._icon)
                self.create_text(
                    x_icon + (self._icon.width() // 2) + self._icon_pad,
                    self._height // 2,
                    text=self._text,
                    font=self._font,
                    fill=text_fill,
                    anchor="w",
                )
        else:
            if self._text_anchor in {"w", "west", "left"}:
                self.create_text(
                    self._text_padx,
                    self._height // 2,
                    text=self._text,
                    font=self._font,
                    fill=text_fill,
                    anchor="w",
                )
            else:
                self.create_text(
                    self._width // 2,
                    self._height // 2,
                    text=self._text,
                    font=self._font,
                    fill=text_fill,
                    anchor="c",
                )

    @staticmethod
    def _try_load_icon(icon_path: str | None, icon_subsample: int) -> tk.PhotoImage | None:
        if not icon_path:
            return None
        try:
            p = Path(icon_path)
            if not p.is_absolute():
                p = Path(__file__).resolve().parent / p
            if not p.exists():
                return None
            img = tk.PhotoImage(file=str(p))
            s = max(1, int(icon_subsample))
            if s > 1:
                img = img.subsample(s, s)
            return img
        except Exception:
            return None

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, r: int, *, fill: str, outline: str) -> None:
        # corners
        self.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, fill=fill, outline=outline)
        self.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, fill=fill, outline=outline)
        self.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, fill=fill, outline=outline)
        self.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, fill=fill, outline=outline)

        # edges + center
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=outline)
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=outline)

    def _on_hover(self, event=None):
        if not self._is_pressed:
            self._redraw(self._bg_hover)

    def _on_leave(self, event=None):
        if not self._is_pressed:
            self._redraw(self._bg_normal)

    def _on_press(self, event=None):
        self._is_pressed = True
        self._click_invoked = False

        # Cancel any previous click timers.
        try:
            if self._press_invoke_after_id:
                self.after_cancel(self._press_invoke_after_id)
        except Exception:
            pass
        self._press_invoke_after_id = None
        try:
            if self._reset_after_id:
                self.after_cancel(self._reset_after_id)
        except Exception:
            pass
        self._reset_after_id = None
        
        self._redraw(self._bg_pressed)

        # Schedule an invoke shortly after press. This fixes cases where
        # `<ButtonRelease-1>` is not delivered (observed on macOS with
        # immediate view swaps).
        if self._invoke_on_press and self._command:
            try:
                self._press_invoke_after_id = self.after(35, self._invoke_from_press)
            except Exception:
                self._press_invoke_after_id = None

    def _invoke_from_press(self) -> None:
        self._press_invoke_after_id = None
        if self._disabled or self._click_invoked or not self._is_pressed or not self._command:
            return

        self._click_invoked = True
        try:
            self.after(0, self._command)
        except Exception:
            try:
                self._command()
            except Exception:
                return

        # If the release event never arrives, auto-reset visuals so the button
        # doesn't look stuck.
        try:
            self._reset_after_id = self.after(220, self._auto_reset_if_stuck)
        except Exception:
            self._reset_after_id = None

    def _auto_reset_if_stuck(self) -> None:
        self._reset_after_id = None
        if not self._is_pressed:
            return
        self._is_pressed = False
        
        self._redraw(self._bg_normal)

    def _on_release(self, event=None):
        was_pressed = self._is_pressed
        self._is_pressed = False

        # If a press-invoke is pending, cancel it now.
        try:
            if self._press_invoke_after_id:
                self.after_cancel(self._press_invoke_after_id)
        except Exception:
            pass
        self._press_invoke_after_id = None

        # Cancel any auto-reset timer.
        try:
            if self._reset_after_id:
                self.after_cancel(self._reset_after_id)
        except Exception:
            pass
        self._reset_after_id = None
        
        self._redraw(self._bg_hover)
        if was_pressed and self._command and not self._click_invoked:
            self._click_invoked = True
            try:
                # Defer to next tick so Tk can finish handling the mouse event
                # and repaint before potentially heavy callbacks run.
                self.after(0, self._command)
            except Exception:
                self._command()

    @staticmethod
    def _lighten_color(color: str, amount: int) -> str:
        try:
            c = color.lstrip("#")
            r = min(255, int(c[0:2], 16) + amount)
            g = min(255, int(c[2:4], 16) + amount)
            b = min(255, int(c[4:6], 16) + amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return color

    @staticmethod
    def _darken_color(color: str, amount: int) -> str:
        try:
            c = color.lstrip("#")
            r = max(0, int(c[0:2], 16) - amount)
            g = max(0, int(c[2:4], 16) - amount)
            b = max(0, int(c[4:6], 16) - amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return color

    @staticmethod
    def _blend(fg_hex: str, bg_hex: str, alpha: float) -> str:
        """Alpha blend fg over bg (both #RRGGBB)."""
        alpha = max(0.0, min(1.0, float(alpha)))
        f = fg_hex.lstrip("#")
        b = bg_hex.lstrip("#")
        fr, fg, fb = int(f[0:2], 16), int(f[2:4], 16), int(f[4:6], 16)
        br, bg, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
        r = int((fr * alpha) + (br * (1 - alpha)))
        g = int((fg * alpha) + (bg * (1 - alpha)))
        bl = int((fb * alpha) + (bb * (1 - alpha)))
        return f"#{r:02x}{g:02x}{bl:02x}"


class DatePicker(tk.Frame):
    """Modern calendar date picker widget."""

    def __init__(self, parent, on_date_selected=None, **kwargs):
        super().__init__(parent, bg=ModernStyle.BG_SECONDARY, **kwargs)
        self.on_date_selected = on_date_selected
        
        from datetime import datetime, timedelta
        import calendar as cal_module
        
        self.selected_date = datetime.now()
        
        # Header with month navigation
        header = tk.Frame(self, bg=ModernStyle.BG_SECONDARY)
        header.pack(fill=tk.X, padx=8, pady=8)
        
        tk.Button(
            header, text="◀", font=(ModernStyle.FONT_FAMILY, 11, "bold"),
            bg=ModernStyle.ACCENT_PRIMARY, fg=ModernStyle.TEXT_ON_ACCENT,
            relief=tk.FLAT, bd=0, padx=6, pady=2,
            command=self._prev_month
        ).pack(side=tk.LEFT)
        
        self.month_label = tk.Label(
            header, font=(ModernStyle.FONT_FAMILY, 12, "bold"),
            bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY
        )
        self.month_label.pack(side=tk.LEFT, expand=True)
        
        tk.Button(
            header, text="▶", font=(ModernStyle.FONT_FAMILY, 11, "bold"),
            bg=ModernStyle.ACCENT_PRIMARY, fg=ModernStyle.TEXT_ON_ACCENT,
            relief=tk.FLAT, bd=0, padx=6, pady=2,
            command=self._next_month
        ).pack(side=tk.LEFT)
        
        # Weekday labels
        weekdays = tk.Frame(self, bg=ModernStyle.BG_SECONDARY)
        weekdays.pack(fill=tk.X, padx=4, pady=(0, 4))
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            tk.Label(
                weekdays, text=day, font=(ModernStyle.FONT_FAMILY, 9, "bold"),
                bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_SECONDARY,
                width=4, pady=4
            ).pack(side=tk.LEFT, padx=1)
        
        # Calendar grid
        self.grid_frame = tk.Frame(self, bg=ModernStyle.BG_SECONDARY)
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        self.day_buttons = []
        self._update_calendar()
    
    def _prev_month(self):
        from datetime import timedelta
        self.selected_date = (self.selected_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        self._update_calendar()
    
    def _next_month(self):
        from datetime import timedelta
        last_day = (self.selected_date.replace(day=1) - timedelta(days=1)).day if self.selected_date.month == 1 else (self.selected_date.replace(day=1) + timedelta(days=32)).replace(day=1).day
        self.selected_date = (self.selected_date.replace(day=1) + timedelta(days=32)).replace(day=1)
        self._update_calendar()
    
    def _update_calendar(self):
        import calendar as cal_module
        from datetime import datetime
        
        # Update header
        self.month_label.config(text=self.selected_date.strftime("%B %Y"))
        
        # Clear grid
        for btn in self.day_buttons:
            btn.destroy()
        self.day_buttons = []
        
        # Get calendar for this month
        month_cal = cal_module.monthcalendar(self.selected_date.year, self.selected_date.month)
        
        for week in month_cal:
            week_frame = tk.Frame(self.grid_frame, bg=ModernStyle.BG_SECONDARY)
            week_frame.pack(fill=tk.X)
            
            for day in week:
                if day == 0:
                    tk.Label(week_frame, text="", bg=ModernStyle.BG_SECONDARY, width=4).pack(side=tk.LEFT, padx=1, pady=2)
                else:
                    is_today = (
                        day == datetime.now().day and
                        self.selected_date.month == datetime.now().month and
                        self.selected_date.year == datetime.now().year
                    )
                    
                    btn = tk.Button(
                        week_frame, text=str(day), font=(ModernStyle.FONT_FAMILY, 9),
                        bg=ModernStyle.ACCENT_PRIMARY if is_today else ModernStyle.BG_PRIMARY,
                        fg=ModernStyle.TEXT_ON_ACCENT if is_today else ModernStyle.TEXT_PRIMARY,
                        relief=tk.FLAT, bd=0, width=4, padx=0, pady=2,
                        command=lambda d=day: self._select_day(d)
                    )
                    btn.pack(side=tk.LEFT, padx=1, pady=2)
                    self.day_buttons.append(btn)
    
    def _select_day(self, day):
        from datetime import datetime
        selected = self.selected_date.replace(day=day)
        if self.on_date_selected:
            self.on_date_selected(selected.date())
        # Don't close here; let parent handle it


class DatePickerButton(tk.Frame):
    """Button that opens a date picker popup."""
    
    def __init__(self, parent, on_date_selected=None, initial_date=None, **kwargs):
        bg = kwargs.pop("bg", ModernStyle.BG_PRIMARY)
        super().__init__(parent, bg=bg, **kwargs)
        self.on_date_selected = on_date_selected
        self.selected_date = initial_date if initial_date else None
        self.popup = None
        
        # Display frame
        display = tk.Frame(self, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        display.pack(fill=tk.X, padx=0, pady=0)
        
        self.date_label = tk.Label(
            display, text=self.selected_date.strftime("%Y-%m-%d") if self.selected_date else "Select Date",
            font=(ModernStyle.FONT_FAMILY, 10),
            bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY,
            padx=8, pady=6
        )
        self.date_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        tk.Button(
            display, text="📅", font=(ModernStyle.FONT_FAMILY, 11),
            bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.ACCENT_PRIMARY,
            relief=tk.FLAT, bd=0, padx=6, pady=4,
            command=self._open_picker
        ).pack(side=tk.RIGHT)
    
    def _open_picker(self):
        if self.popup is None or not self.popup.winfo_exists():
            self.popup = tk.Toplevel(self)
            self.popup.title("Select Date")
            self.popup.geometry("280x320")
            self.popup.resizable(False, False)
            
            # Configure popup style
            self.popup.configure(bg=ModernStyle.BG_SECONDARY)
            
            picker = DatePicker(self.popup, on_date_selected=self._on_date_selected)
            picker.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            
            # Buttons
            btn_frame = tk.Frame(self.popup, bg=ModernStyle.BG_SECONDARY)
            btn_frame.pack(fill=tk.X, padx=4, pady=4)
            
            tk.Button(
                btn_frame, text="OK", font=ModernStyle.FONT_BODY,
                bg=ModernStyle.ACCENT_PRIMARY, fg=ModernStyle.TEXT_ON_ACCENT,
                relief=tk.FLAT, bd=0, padx=12, pady=6,
                command=self.popup.destroy
            ).pack(side=tk.RIGHT, padx=2)
            
            tk.Button(
                btn_frame, text="Cancel", font=ModernStyle.FONT_BODY,
                bg=ModernStyle.ACCENT_SECONDARY, fg=ModernStyle.TEXT_ON_ACCENT,
                relief=tk.FLAT, bd=0, padx=12, pady=6,
                command=self.popup.destroy
            ).pack(side=tk.RIGHT, padx=2)
    
    def _on_date_selected(self, date):
        self.selected_date = date
        self.date_label.config(text=date.strftime("%Y-%m-%d"))
        if self.on_date_selected:
            self.on_date_selected(date)
    
    def get_date(self):
        return self.selected_date
    
    def set_date(self, date):
        self.selected_date = date
        if date:
            self.date_label.config(text=date.strftime("%Y-%m-%d"))

class PremiumModal(tk.Toplevel):
    """
    A unified base class for all popup modals.
    Provides standard window styling, centering, and a clean light/modern aesthetic.
    """
    def __init__(self, parent, title: str, geometry: str = "500x520", icon: str = "✨"):
        super().__init__(parent)
        self.title(f"{title}")
        self.configure(bg=ModernStyle.BG_PRIMARY)
        self.resizable(False, False)
        self.geometry(geometry)
        
        try:
            self.transient(parent.winfo_toplevel())
            self.grab_set()
        except Exception:
            pass
            
        try:
            from ui_utils import center_window
            center_window(self, parent=parent.winfo_toplevel())
        except Exception:
            pass
            
        # ── Premium header with accent gradient bar ──
        self.header = tk.Frame(self, bg=ModernStyle.BG_PRIMARY)
        self.header.pack(fill="x")

        # Thin accent gradient bar at very top
        tk.Frame(self.header, bg=ModernStyle.ACCENT_PRIMARY, height=3).pack(fill="x")

        self.inner_hdr = tk.Frame(self.header, bg=ModernStyle.BG_PRIMARY)
        self.inner_hdr.pack(fill="x", padx=28, pady=(18, 16))

        # Left block: icon + title
        if icon:
            tk.Label(
                self.inner_hdr, text=icon, bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY,
                font=(ModernStyle.FONT_FAMILY, 26)
            ).pack(side="left", padx=(0, 12))

        self.title_col = tk.Frame(self.inner_hdr, bg=ModernStyle.BG_PRIMARY)
        self.title_col.pack(side="left", fill="y")
        self.title_lbl = tk.Label(
            self.title_col, text=title,
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY,
            font=(ModernStyle.FONT_FAMILY, 20, "bold")
        )
        self.title_lbl.pack(anchor="w")
        
        # Area for child classes to put chips/badges under the title.
        self.chips_row = tk.Frame(self.title_col, bg=ModernStyle.BG_PRIMARY)
        self.chips_row.pack(anchor="w", pady=(4, 0))

        # ── Scrolling content card (Main Body) ──
        self.body_card = tk.Frame(self, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        self.body_card.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Accent separator under header
        tk.Frame(self.body_card, bg=ModernStyle.ACCENT_PRIMARY, height=2).pack(fill="x")
        
        self.content_frame = tk.Frame(self.body_card, bg=ModernStyle.BG_SECONDARY)
        self.content_frame.pack(fill="both", expand=True, padx=24, pady=(20, 8))
        self.content_frame.grid_columnconfigure(0, weight=1)

        # ── Footer / Actions Area ──
        self.status_lbl = tk.Label(
            self.body_card, text="", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_SECONDARY,
            font=(ModernStyle.FONT_FAMILY, 10, "italic"), anchor="w"
        )
        self.status_lbl.pack(anchor="w", padx=24, pady=(0, 8), fill="x")
        
        # Divider before buttons
        tk.Frame(self.body_card, bg=ModernStyle.BORDER_COLOR, height=1).pack(fill="x", padx=20, pady=(0, 12))

        self.actions_frame = tk.Frame(self.body_card, bg=ModernStyle.BG_SECONDARY)
        self.actions_frame.pack(fill="x", padx=24, pady=(0, 20))

    def set_status(self, text: str, is_error: bool = False):
        color = ModernStyle.ERROR if is_error else ModernStyle.TEXT_TERTIARY
        self.status_lbl.configure(text=text, fg=color)
        
    def add_chip(self, emoji: str, text: str, bg_color: str = ModernStyle.ACCENT_PRIMARY_PALE, fg_color: str = ModernStyle.ACCENT_PRIMARY):
        chip = tk.Frame(self.chips_row, bg=bg_color, highlightthickness=1, highlightbackground=fg_color)
        chip.pack(side="left", padx=(0, 6))
        tk.Label(
            chip, text=f"{emoji} {text}", bg=bg_color, fg=fg_color,
            font=(ModernStyle.FONT_FAMILY, 10, "bold"),
            padx=8, pady=2
        ).pack()

class LoadingOverlay(tk.Frame):
    """
    A unified, non-blocking loading overlay to provide feedback during data fetching.
    """
    def __init__(self, parent, text: str = "Loading..."):
        super().__init__(parent, bg=ModernStyle.BG_PRIMARY)
        self.text = text
        self._build()
        
    def _build(self):
        # A simple centered message
        container = tk.Frame(self, bg=ModernStyle.BG_PRIMARY)
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(
            container, text="⏳", bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.ACCENT_PRIMARY,
            font=(ModernStyle.FONT_FAMILY, 32)
        ).pack(pady=(0, 10))
        
        self.lbl = tk.Label(
            container, text=self.text, bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_SECONDARY,
            font=(ModernStyle.FONT_FAMILY, 14, "italic")
        )
        self.lbl.pack()
        
    def show(self):
        self.lift()
        self.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        
    def hide(self):
        self.place_forget()
        
    def set_text(self, text: str):
        self.lbl.configure(text=text)
