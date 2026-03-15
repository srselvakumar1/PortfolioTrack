"""
Trade Entry view for TKinter-based PTracker application.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime

from views.base_view import BaseView, _create_date_input
from ui_theme import ModernStyle
from ui_widgets import ModernButton, PremiumModal
from ui_utils import center_window, add_treeview_copy_menu
from common.database import close_all_connections
import common.database as db

class TradeEntryView(BaseView):
    """Form for entering new trades."""
    
    def build(self):
        """Build Trade Entry view with premium look."""
        self._data_loaded = False
        self.pending_import_df = None
        self._dupes = []

        # ── Premium Header ──────────────────────────────────────────────────────
        hdr_frame = tk.Frame(self, bg=ModernStyle.BG_PRIMARY)
        hdr_frame.pack(fill="x", padx=20, pady=(16, 0))

        tk.Label(
            hdr_frame,
            text="➕ Trade Entry",
            fg=ModernStyle.TEXT_PRIMARY,
            bg=ModernStyle.BG_PRIMARY,
            font=(ModernStyle.FONT_FAMILY, 24, "bold"),
        ).pack(anchor="w")
        tk.Label(
            hdr_frame,
            text="Record a manual trade or bulk-import via CSV",
            fg=ModernStyle.TEXT_SECONDARY,
            bg=ModernStyle.BG_PRIMARY,
            font=ModernStyle.FONT_BODY,
        ).pack(anchor="w", pady=(2, 0))
        # Accent divider
        tk.Frame(self, bg="#D4AF37", height=1).pack(fill="x", padx=20, pady=(10, 10))

        # ── Body grid ──────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=ModernStyle.BG_PRIMARY)
        body.pack(fill="both", expand=True, padx=20, pady=14)
        body.grid_columnconfigure(0, weight=3, uniform="te")
        body.grid_columnconfigure(1, weight=2, uniform="te")
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        right = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew")

        # Numeric-only validation command
        vcmd = (self.register(self._validate_number), "%P")

        def _card(parent, title: str, icon: str = "", accent: str = ModernStyle.ACCENT_PRIMARY):
            """Premium section card with accent bar."""
            frame = tk.Frame(
                parent,
                bg=ModernStyle.BG_SECONDARY,
                highlightbackground=ModernStyle.BORDER_COLOR,
                highlightthickness=1,
            )
            tk.Frame(frame, bg=accent, height=1).pack(fill="x")
            hdr = tk.Frame(frame, bg=ModernStyle.BG_SECONDARY)
            hdr.pack(fill="x", padx=14, pady=(10, 6))
            if icon:
                tk.Label(hdr, text=icon, fg=accent, bg=ModernStyle.BG_SECONDARY,
                         font=(ModernStyle.FONT_FAMILY, 14)).pack(side="left", padx=(0, 6))
            tk.Label(hdr, text=title, fg=ModernStyle.TEXT_PRIMARY,
                     bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).pack(side="left")
            tk.Frame(frame, bg=ModernStyle.DIVIDER_COLOR, height=1).pack(fill="x", padx=12)
            inner = tk.Frame(frame, bg=ModernStyle.BG_SECONDARY)
            inner.pack(fill="both", expand=True, padx=14, pady=(10, 14))
            return frame, inner

        def _field_row(parent, labels: list[tuple[str, str]]):
            """Build a row of labelled fields with focus-ring entry boxes."""
            row = tk.Frame(parent, bg=ModernStyle.BG_SECONDARY)
            row.pack(fill="x", pady=(0, 10))
            for i, (lbl_text, _) in enumerate(labels):
                row.grid_columnconfigure(i, weight=1, uniform="fr")
            for i, (lbl_text, _) in enumerate(labels):
                col = tk.Frame(row, bg=ModernStyle.BG_SECONDARY)
                col.grid(row=0, column=i, sticky="nsew", padx=(0, 10) if i < len(labels) - 1 else 0)
                tk.Label(col, text=lbl_text, fg=ModernStyle.TEXT_SECONDARY,
                         bg=ModernStyle.BG_SECONDARY,
                         font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(anchor="w", pady=(0, 4))
            return row

        def _styled_entry(parent, textvariable, validate=None, vcmd=None, **kwargs):
            """Entry with thick focus ring."""
            wrap = tk.Frame(parent, bg="#CBD5E1", padx=1, pady=1)
            wrap.pack(fill="x")
            kw = dict(
                textvariable=textvariable,
                bg=ModernStyle.ENTRY_BG,
                fg=ModernStyle.TEXT_PRIMARY,
                font=(ModernStyle.FONT_FAMILY, 13),
                relief=tk.FLAT,
                insertbackground=ModernStyle.ACCENT_PRIMARY,
                highlightthickness=0,
            )
            if validate:
                kw["validate"] = validate
            if vcmd:
                kw["validatecommand"] = vcmd
            kw.update(kwargs)
            ent = tk.Entry(wrap, **kw)

            def _fi(e, w=wrap):
                w.configure(bg=ModernStyle.ACCENT_PRIMARY)
            def _fo(e, w=wrap):
                w.configure(bg="#CBD5E1")

            ent.bind("<FocusIn>", _fi)
            ent.bind("<FocusOut>", _fo)
            ent.pack(fill="x", ipady=7, padx=6)
            return ent, wrap

        # ===== Manual Entry Card =====
        manual_card, manual = _card(left, "Manual Trade Entry", "✍️", ModernStyle.ACCENT_PRIMARY)
        manual_card.pack(fill="x", pady=(0, 14))

        self.te_status = tk.Label(
            manual, text="", fg=ModernStyle.TEXT_TERTIARY,
            bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL
        )
        self.te_status.pack(anchor="w", pady=(0, 8))

        # Row 1: Broker + Date
        r1 = tk.Frame(manual, bg=ModernStyle.BG_SECONDARY)
        r1.pack(fill="x", pady=(0, 10))
        r1.grid_columnconfigure(0, weight=1, uniform="r1")
        r1.grid_columnconfigure(1, weight=1, uniform="r1")

        self.te_broker_var = tk.StringVar(value="")
        self.te_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        broker_col = tk.Frame(r1, bg=ModernStyle.BG_SECONDARY)
        broker_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tk.Label(broker_col, text="🏦 Broker", fg=ModernStyle.TEXT_SECONDARY,
                 bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(anchor="w", pady=(0, 4))
        self.te_broker_cb = ttk.Combobox(broker_col, textvariable=self.te_broker_var, state="readonly",
                                          font=(ModernStyle.FONT_FAMILY, 12))
        self.te_broker_cb.pack(fill="x")

        date_col = tk.Frame(r1, bg=ModernStyle.BG_SECONDARY)
        date_col.grid(row=0, column=1, sticky="nsew")
        tk.Label(date_col, text="📅 Date", fg=ModernStyle.TEXT_SECONDARY,
                 bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(anchor="w", pady=(0, 4))
        self.te_date_entry = _create_date_input(date_col, self.te_date_var)
        self.te_date_entry.pack(fill="x")

        # Row 2: Symbol + Type
        r2 = tk.Frame(manual, bg=ModernStyle.BG_SECONDARY)
        r2.pack(fill="x", pady=(0, 10))
        r2.grid_columnconfigure(0, weight=1, uniform="r2")
        r2.grid_columnconfigure(1, weight=1, uniform="r2")

        self.te_symbol_var = tk.StringVar(value="")
        self.te_type_var = tk.StringVar(value="BUY")

        sym_col = tk.Frame(r2, bg=ModernStyle.BG_SECONDARY)
        sym_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tk.Label(sym_col, text="📈 Symbol", fg=ModernStyle.TEXT_SECONDARY,
                 bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(anchor="w", pady=(0, 4))
        self.te_symbol_entry, self._sym_wrap = _styled_entry(sym_col, self.te_symbol_var)

        type_col = tk.Frame(r2, bg=ModernStyle.BG_SECONDARY)
        type_col.grid(row=0, column=1, sticky="nsew")
        tk.Label(type_col, text="🔄 Type", fg=ModernStyle.TEXT_SECONDARY,
                 bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(anchor="w", pady=(0, 4))

        type_wrap = tk.Frame(type_col, bg=ModernStyle.BG_SECONDARY)
        type_wrap.pack(fill="x")
        self.te_buy_rb = tk.Radiobutton(
            type_wrap, text="  BUY  ",
            variable=self.te_type_var, value="BUY",
            indicatoron=0, pady=7,
            font=(ModernStyle.FONT_FAMILY, 12, "bold"),
            relief=tk.FLAT, bd=0,
            command=lambda: (self._sync_te_type_buttons(), self._update_summary()),
        )
        self.te_sell_rb = tk.Radiobutton(
            type_wrap, text="  SELL  ",
            variable=self.te_type_var, value="SELL",
            indicatoron=0, pady=7,
            font=(ModernStyle.FONT_FAMILY, 12, "bold"),
            relief=tk.FLAT, bd=0,
            command=lambda: (self._sync_te_type_buttons(), self._update_summary()),
        )
        self.te_buy_rb.pack(side="left", fill="x", expand=True)
        self.te_sell_rb.pack(side="left", fill="x", expand=True)

        # Row 3: Qty + Price
        r3 = tk.Frame(manual, bg=ModernStyle.BG_SECONDARY)
        r3.pack(fill="x", pady=(0, 10))
        r3.grid_columnconfigure(0, weight=1, uniform="r3")
        r3.grid_columnconfigure(1, weight=1, uniform="r3")

        self.te_qty_var = tk.StringVar(value="")
        self.te_price_var = tk.StringVar(value="")

        qty_col = tk.Frame(r3, bg=ModernStyle.BG_SECONDARY)
        qty_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tk.Label(qty_col, text="🔢 Quantity", fg=ModernStyle.TEXT_SECONDARY,
                 bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(anchor="w", pady=(0, 4))
        self.te_qty_entry, self._qty_wrap = _styled_entry(
            qty_col, self.te_qty_var, validate="key", vcmd=vcmd
        )

        price_col = tk.Frame(r3, bg=ModernStyle.BG_SECONDARY)
        price_col.grid(row=0, column=1, sticky="nsew")
        tk.Label(price_col, text="💰 Price (₹)", fg=ModernStyle.TEXT_SECONDARY,
                 bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(anchor="w", pady=(0, 4))
        self.te_price_entry, self._price_wrap = _styled_entry(
            price_col, self.te_price_var, validate="key", vcmd=vcmd
        )

        # Estimated fee
        self.te_fee_label = tk.Label(
            manual, text="💸  Estimated Fee: ₹0.00",
            fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY,
            font=ModernStyle.FONT_SMALL
        )
        self.te_fee_label.pack(anchor="w", pady=(4, 0))

        # Buttons
        btns = tk.Frame(manual, bg=ModernStyle.BG_SECONDARY)
        btns.pack(fill="x", pady=(14, 0))
        ModernButton(
            btns, text="✔  Save Trade", command=self._save_trade,
            bg=ModernStyle.ACCENT_PRIMARY, fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_SECONDARY, width=148, height=40
        ).pack(side="left", padx=(0, 8))
        ModernButton(
            btns, text="✕  Clear", command=self._clear_form,
            bg=ModernStyle.TEXT_TERTIARY, fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_SECONDARY, width=96, height=40
        ).pack(side="left")

        # ===== Bulk Import Card =====
        import_card, import_inner = _card(left, "Bulk Import (CSV)", "📥", ModernStyle.ACCENT_TERTIARY)
        import_card.pack(fill="x", pady=(0, 14))

        tk.Label(
            import_inner,
            text="Expected columns: broker (optional), date, symbol, type, qty, price",
            fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL
        ).pack(anchor="w")

        self.import_path_label = tk.Label(
            import_inner, text="No file selected",
            fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY
        )
        self.import_path_label.pack(anchor="w", pady=(8, 6))

        imp_btns = tk.Frame(import_inner, bg=ModernStyle.BG_SECONDARY)
        imp_btns.pack(fill="x", pady=(4, 0))
        ModernButton(
            imp_btns, text="📂  Select CSV", command=self._select_import_file,
            bg=ModernStyle.ACCENT_TERTIARY, fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_SECONDARY, width=148, height=36
        ).pack(side="left", padx=(0, 8))
        self.import_confirm_btn = ModernButton(
            imp_btns, text="👁  Preview Import", command=self._open_import_preview_dialog,
            bg=ModernStyle.SUCCESS, fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_SECONDARY, width=160, height=36
        )
        self.import_confirm_btn.pack(side="left")

        self.import_broker_row = tk.Frame(import_inner, bg=ModernStyle.BG_SECONDARY)
        self.import_broker_row.pack(fill="x", pady=(10, 0))
        tk.Label(
            self.import_broker_row,
            text="Broker (required if CSV has no broker column)",
            fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL
        ).pack(anchor="w")
        self.import_broker_var = tk.StringVar(value="")
        self.import_broker_cb = ttk.Combobox(
            self.import_broker_row, textvariable=self.import_broker_var, state="readonly"
        )
        self.import_broker_cb.pack(fill="x", pady=(3, 0))
        self.import_broker_row.pack_forget()

        self.import_status = tk.Label(
            import_inner, text="",
            fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL
        )
        self.import_status.pack(anchor="w", pady=(8, 0))

        # ===== Skipped Duplicates Card =====
        self.dupe_card, dupe_inner = _card(left, "Skipped Duplicates", "⚠️", ModernStyle.WARNING)
        self.dupe_card.pack(fill="x")
        dupe_cols = ("Date", "Sym", "Qty")
        self.dupe_table = ttk.Treeview(dupe_inner, columns=dupe_cols, show="headings", height=6)
        for c in dupe_cols:
            self.dupe_table.heading(c, text=c, anchor="w")
            self.dupe_table.column(c, width=80, anchor="w")
            
        add_treeview_copy_menu(self.dupe_table)

        vsb = ttk.Scrollbar(dupe_inner, orient="vertical", command=self.dupe_table.yview)
        self.dupe_table.configure(yscroll=vsb.set)
        self.dupe_table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.dupe_card.pack_forget()

        # ===== Transaction Summary Card (right column) =====
        sum_card, sum_inner = _card(right, "Transaction Summary", "📋", "#7C3AED")
        sum_card.pack(fill="x")

        def _sum_row(lbl: str, init: str, key: str, color=None):
            row = tk.Frame(sum_inner, bg=ModernStyle.BG_SECONDARY)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=lbl, fg=ModernStyle.TEXT_TERTIARY,
                     bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 10)).pack(side="left")
            val = tk.Label(row, text=init, fg=color or ModernStyle.TEXT_PRIMARY,
                           bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 11, "bold"))
            val.pack(side="right")
            return val

        self.sum_type_label  = _sum_row("Trade type",  "BUY",   "type")
        self.sum_qty_label   = _sum_row("Quantity",     "—",     "qty")
        self.sum_price_label = _sum_row("Unit price",   "—",     "price")
        self.sum_subtotal_label = _sum_row("Subtotal",  "—",     "sub")
        self.sum_fee_label   = _sum_row("Est. fee",     "₹0.00", "fee")

        tk.Frame(sum_inner, bg=ModernStyle.DIVIDER_COLOR, height=1).pack(fill="x", pady=(8, 6))

        total_row = tk.Frame(sum_inner, bg=ModernStyle.BG_SECONDARY)
        total_row.pack(fill="x")
        tk.Label(total_row, text="Total value", fg=ModernStyle.TEXT_PRIMARY,
                 bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 12, "bold")).pack(side="left")
        self.sum_total_label = tk.Label(
            total_row, text="₹0.00", fg=ModernStyle.SUCCESS,
            bg=ModernStyle.BG_SECONDARY, font=(ModernStyle.FONT_FAMILY, 16, "bold")
        )
        self.sum_total_label.pack(side="right")

        # Wire live updates
        for v in (self.te_qty_var, self.te_price_var, self.te_symbol_var, self.te_date_var):
            try:
                v.trace_add("write", lambda *_: self._update_summary())
            except Exception:
                pass

        self._update_summary()
        self._sync_te_type_buttons()


    def _validate_number(self, value: str) -> bool:
        """Allow only numeric input (integers or decimals) in entry fields."""
        if value == "":
            return True
        try:
            float(value)
            return True
        except ValueError:
            # Allow a single trailing decimal point
            return value.count(".") == 1 and value.replace(".", "").isdigit()

    def _sync_te_type_buttons(self) -> None:
        """Color the BUY/SELL segmented radio buttons based on selection."""
        t = (self.te_type_var.get() or "BUY").upper()
        try:
            if t == "BUY":
                self.te_buy_rb.configure(bg=ModernStyle.ACCENT_SECONDARY, fg=ModernStyle.TEXT_ON_ACCENT, activebackground=ModernStyle.ACCENT_SECONDARY, activeforeground=ModernStyle.TEXT_ON_ACCENT)
                self.te_sell_rb.configure(bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY, activebackground=ModernStyle.BG_PRIMARY, activeforeground=ModernStyle.TEXT_PRIMARY)
            else:
                self.te_sell_rb.configure(bg=ModernStyle.ERROR, fg=ModernStyle.TEXT_ON_ACCENT, activebackground=ModernStyle.ERROR, activeforeground=ModernStyle.TEXT_ON_ACCENT)
                self.te_buy_rb.configure(bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY, activebackground=ModernStyle.BG_PRIMARY, activeforeground=ModernStyle.TEXT_PRIMARY)
        except Exception:
            pass

    def _open_simple_date_picker(self) -> None:
        """Open a simple calendar grid date picker."""
        top = tk.Toplevel(self)
        top.title("Select Date")
        top.transient(self)
        top.grab_set()
        top.configure(bg=ModernStyle.BG_PRIMARY)
        
        try:
            current_date = datetime.strptime(self.te_date_var.get(), "%Y-%m-%d")
        except:
            current_date = datetime.now()
        
        display_year = current_date.year
        display_month = current_date.month
        
        def show_calendar(year, month):
            # Clear previous widgets
            for widget in calendar_frame.winfo_children():
                widget.destroy()
            
            # Month/Year header
            header = tk.Frame(calendar_frame, bg=ModernStyle.BG_PRIMARY)
            header.pack(fill="x", padx=10, pady=10)
            
            tk.Button(header, text="◀", command=lambda: prev_month(), bg=ModernStyle.ACCENT_TERTIARY, fg=ModernStyle.TEXT_ON_ACCENT, relief=tk.FLAT, font=(ModernStyle.FONT_FAMILY, 10), padx=5).pack(side="left")
            tk.Label(header, text=f"{datetime(year, month, 1).strftime('%B %Y')}", fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(side="left", expand=True)
            tk.Button(header, text="▶", command=lambda: next_month(), bg=ModernStyle.ACCENT_TERTIARY, fg=ModernStyle.TEXT_ON_ACCENT, relief=tk.FLAT, font=(ModernStyle.FONT_FAMILY, 10), padx=5).pack(side="right")
            
            # Days of week
            days_frame = tk.Frame(calendar_frame, bg=ModernStyle.BG_PRIMARY)
            days_frame.pack(fill="x", padx=10)
            for day_name in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
                tk.Label(days_frame, text=day_name, fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_PRIMARY, font=(ModernStyle.FONT_FAMILY, 9, "bold"), width=6).pack(side="left")
            
            # Calendar grid
            grid_frame = tk.Frame(calendar_frame, bg=ModernStyle.BG_PRIMARY)
            grid_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            
            # Get first day and days in month
            first_day = datetime(year, month, 1).weekday()
            first_day = (first_day + 1) % 7  # Convert to Sunday=0
            
            if month == 12:
                next_month_obj = datetime(year + 1, 1, 1)
            else:
                next_month_obj = datetime(year, month + 1, 1)
            days_in_month = (next_month_obj - datetime(year, month, 1)).days
            
            week_frame = None
            col = 0
            
            # Empty cells before month starts
            if first_day > 0:
                week_frame = tk.Frame(grid_frame, bg=ModernStyle.BG_PRIMARY)
                week_frame.pack(fill="x")
                for _ in range(first_day):
                    tk.Label(week_frame, text="", bg=ModernStyle.BG_PRIMARY, width=6, height=3).pack(side="left")
                col = first_day
            
            # Days of month
            for day in range(1, days_in_month + 1):
                if col == 0:
                    week_frame = tk.Frame(grid_frame, bg=ModernStyle.BG_PRIMARY)
                    week_frame.pack(fill="x")
                
                is_today = (day == current_date.day and month == current_date.month and year == current_date.year)
                bg_color = ModernStyle.ACCENT_PRIMARY if is_today else ModernStyle.BG_SECONDARY
                fg_color = ModernStyle.TEXT_ON_ACCENT if is_today else ModernStyle.TEXT_PRIMARY
                
                def make_click(d):
                    def click():
                        selected = datetime(year, month, d).strftime("%Y-%m-%d")
                        self.te_date_var.set(selected)
                        top.destroy()
                    return click
                
                tk.Button(week_frame, text=str(day), command=make_click(day), bg=bg_color, fg=fg_color, relief=tk.FLAT, font=(ModernStyle.FONT_FAMILY, 10), width=6, height=3).pack(side="left")
                col += 1
                
                if col == 7:
                    col = 0
        
        def prev_month():
            nonlocal display_year, display_month
            display_month -= 1
            if display_month < 1:
                display_month = 12
                display_year -= 1
            show_calendar(display_year, display_month)
        
        def next_month():
            nonlocal display_year, display_month
            display_month += 1
            if display_month > 12:
                display_month = 1
                display_year += 1
            show_calendar(display_year, display_month)
        
        calendar_frame = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        calendar_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        show_calendar(display_year, display_month)
        top.geometry("280x320")

    def _invalidate_other_views(self):
        try:
            # Safely navigate to view manager
            vm = getattr(getattr(self.winfo_toplevel(), '_ptracker_app', self), 'view_manager', None)
            if not vm:
                # Try finding app via widget master chain
                w = self
                while w:
                    if hasattr(w, 'view_manager'):
                        vm = w.view_manager
                        break
                    try:
                        w = w.master
                    except:
                        break
            
            if vm and hasattr(vm, 'views'):
                for key, view in vm.views.items():
                    if view is not self and hasattr(view, '_data_loaded'):
                        view._data_loaded = False
        except Exception:
            pass

    def load_data(self):
        if getattr(self, "_data_loaded", False):
            return
        self._data_loaded = True
        try:
            import common.models.crud as crud
            brokers = crud.get_all_brokers()
        except Exception:
            brokers = []

        self.te_broker_cb["values"] = brokers
        self.import_broker_cb["values"] = brokers
        if brokers:
            if not self.te_broker_var.get():
                self.te_broker_var.set(brokers[0])
            if not self.import_broker_var.get():
                self.import_broker_var.set(brokers[0])

    def _parse_float(self, s: str) -> float:
        try:
            return float(str(s).strip())
        except Exception:
            return 0.0

    def _update_summary(self) -> None:
        t_type = (self.te_type_var.get() or "BUY").upper()
        qty = self._parse_float(self.te_qty_var.get())
        price = self._parse_float(self.te_price_var.get())
        subtotal = qty * price
        try:
            from common.engine import calculate_trade_fees
            fee = float(calculate_trade_fees(t_type, qty, price, is_delivery=True) or 0.0) if (qty > 0 and price > 0) else 0.0
        except Exception:
            fee = 0.0

        total = subtotal + fee if t_type == "BUY" else max(0.0, subtotal - fee)
        color = ModernStyle.SUCCESS if t_type == "BUY" else ModernStyle.ERROR

        self.te_fee_label.config(text=f"💸  Estimated Fee: ₹{fee:,.2f}")
        self.sum_type_label.config(text=t_type, fg=ModernStyle.SUCCESS if t_type == "BUY" else ModernStyle.ERROR)
        self.sum_qty_label.config(text=f"{qty:g}" if qty > 0 else "—")
        self.sum_price_label.config(text=f"₹{price:,.2f}" if price > 0 else "—")
        self.sum_subtotal_label.config(text=f"₹{subtotal:,.2f}" if subtotal > 0 else "—")
        self.sum_fee_label.config(text=f"₹{fee:,.2f}")
        self.sum_total_label.config(text=f"₹{total:,.2f}", fg=color)

    def _clear_form(self) -> None:
        self.te_symbol_var.set("")
        self.te_qty_var.set("")
        self.te_price_var.set("")
        self.te_type_var.set("BUY")
        self.te_status.config(text="")
        self._update_summary()

    def _save_trade(self) -> None:
        broker = (self.te_broker_var.get() or "").strip()
        date = (self.te_date_var.get() or "").strip()
        symbol = (self.te_symbol_var.get() or "").strip().upper()
        t_type = (self.te_type_var.get() or "BUY").strip().upper()
        
        qty_str = self.te_qty_var.get().strip()
        price_str = self.te_price_var.get().strip()

        # Basic presence checks
        if not broker:
            messagebox.showerror("Trade Entry Error", "Please select a broker.")
            return
            
        if not date:
            messagebox.showerror("Trade Entry Error", "Please select or enter a date.")
            return
            
        # Date format validation
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Trade Entry Error", f"Invalid date format: '{date}'.\nPlease use YYYY-MM-DD format.")
            return

        if not symbol:
            messagebox.showerror("Trade Entry Error", "Please enter a trading symbol.")
            return
            
        if not qty_str:
            messagebox.showerror("Trade Entry Error", "Please enter a quantity.")
            return
            
        if not price_str:
            messagebox.showerror("Trade Entry Error", "Please enter a price.")
            return

        # Numeric and Fat-finger validation
        qty = self._parse_float(qty_str)
        price = self._parse_float(price_str)
        
        if qty <= 0:
            messagebox.showerror("Trade Entry Error", "Quantity must be greater than 0.")
            return
        if qty > 500:
            messagebox.showerror("Trade Entry Error", f"Quantity ({qty:,.0f}) exceeds maximum allowed (500).\nPlease check for fat-finger errors.")
            return
            
        if price <= 0:
            messagebox.showerror("Trade Entry Error", "Price must be greater than 0.")
            return
        if price > 12000:
            messagebox.showerror("Trade Entry Error", f"Price (₹{price:,.2f}) exceeds maximum allowed (₹12,000).\nPlease check for fat-finger errors.")
            return

        try:
            from common.engine import calculate_trade_fees
            fee = float(calculate_trade_fees(t_type, qty, price, is_delivery=True) or 0.0)
        except Exception:
            fee = 0.0

        import time
        manual_id = f"MT_{date.replace('-', '')}_{int(time.time() * 1000)}"

        try:
            import common.models.crud as crud
            crud.add_trade(broker, date, symbol, t_type, qty, price, fee, manual_id)
        except Exception as e:
            messagebox.showerror("Trade Entry", f"Failed to save trade: {e}")
            return

        self.te_status.config(text=f"Saved {t_type} {symbol} ✓")
        self._clear_form()

        def _bg_refresh():
            try:
                from common.engine import rebuild_holdings
                rebuild_holdings()
            except Exception:
                pass
            try:
                if self.app_state and hasattr(self.app_state, "refresh_data_cache"):
                    self.app_state.refresh_data_cache()
            except Exception:
                pass
            
            # Invalidate other views so they reload fresh data
            self.after(0, self._invalidate_other_views)

        threading.Thread(target=_bg_refresh, daemon=True).start()

    def _select_import_file(self) -> None:
        from tkinter import filedialog

        path = filedialog.askopenfilename(title="Select CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*")])
        if not path:
            return
        self.import_status.config(text="Loading CSV…")

        def _bg():
            try:
                import os
                import pandas as pd

                df = None
                for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
                    try:
                        df = pd.read_csv(path, encoding=enc)
                        break
                    except Exception:
                        pass
                if df is None:
                    raise ValueError("Could not read CSV")

                df.columns = [str(c).lower().strip() for c in df.columns]
                df.rename(columns={"trade_date": "date", "trade_type": "type", "quantity": "qty"}, inplace=True)

                required = ["date", "symbol", "type", "qty", "price"]
                missing = [c for c in required if c not in df.columns]
                if missing:
                    raise ValueError(f"CSV missing columns: {', '.join(missing)}")

                if "trade_id" not in df.columns:
                    import time
                    t_base = int(time.time())
                    df["trade_id"] = [f"BT_{t_base}_{i}" for i in range(len(df))]

                self.pending_import_df = df
                has_broker = "broker" in df.columns
                self.after(0, lambda: self._apply_import_selected(os.path.basename(path), len(df), has_broker))
            except Exception as e:
                err = str(e)
                self.after(0, lambda e=err: self.import_status.config(text=f"Import load failed: {e}"))

        threading.Thread(target=_bg, daemon=True).start()

    def _apply_import_selected(self, filename: str, row_count: int, has_broker: bool) -> None:
        self.import_path_label.config(text=f"{filename} • {row_count} rows")
        self.import_status.config(text="Preview ready")
        # Broker selection is done in the preview popup.
        try:
            self.import_broker_row.pack_forget()
        except Exception:
            pass

        # Auto-open the preview dialog once the CSV is loaded.
        try:
            self._open_import_preview_dialog(auto=True)
        except Exception:
            pass

    def _start_bulk_import(self, df, chosen_broker: str, on_finish) -> None:
        """Run bulk import in background and call on_finish(inserted, dupes, err) on UI thread."""

        def _bg():
            dupes = []
            inserted = 0
            err = None
            try:
                import pandas as pd
                import common.models.crud as crud
                from common.engine import calculate_trade_fees, rebuild_holdings

                has_broker = "broker" in df.columns

                # Normalize
                dfx = df.copy()
                dfx["symbol"] = dfx["symbol"].astype(str).str.upper().str.strip()
                dfx["type"] = dfx["type"].astype(str).str.upper().str.strip()
                if not has_broker:
                    dfx["broker"] = chosen_broker
                else:
                    dfx["broker"] = dfx["broker"].astype(str).str.strip()



                trades_to_insert = []
                existing_by_broker: dict[str, set] = {}

                for r in dfx.itertuples(index=False):
                    broker = str(getattr(r, "broker", "")).strip()
                    if not broker:
                        continue
                    if broker not in existing_by_broker:
                        existing_by_broker[broker] = crud.get_existing_trade_ids(broker)

                    trade_id = str(getattr(r, "trade_id", "") or "").strip()
                    date = str(getattr(r, "date", "") or "").strip()
                    symbol = str(getattr(r, "symbol", "") or "").strip().upper()
                    t_type = str(getattr(r, "type", "") or "").strip().upper()
                    qty = float(getattr(r, "qty", 0.0) or 0.0)
                    price = float(getattr(r, "price", 0.0) or 0.0)
                    if not trade_id or not date or not symbol or t_type not in ("BUY", "SELL") or qty <= 0 or price <= 0:
                        continue
                    if trade_id in existing_by_broker[broker]:
                        dupes.append((date, symbol, qty))
                        continue

                    fee = float(calculate_trade_fees(t_type, qty, price, is_delivery=True) or 0.0)
                    trades_to_insert.append((trade_id, broker, date, symbol, t_type, qty, price, fee))
                    existing_by_broker[broker].add(trade_id)

                if trades_to_insert:
                    crud.add_trades_batch(trades_to_insert)
                    inserted = len(trades_to_insert)

                try:
                    rebuild_holdings()
                except Exception:
                    pass
                try:
                    if self.app_state and hasattr(self.app_state, "refresh_data_cache"):
                        self.app_state.refresh_data_cache()
                except Exception:
                    pass

            except Exception as e:
                err = str(e)

            self.after(0, lambda: on_finish(inserted, dupes, err))

        threading.Thread(target=_bg, daemon=True).start()

    def _open_import_preview_dialog(self, auto: bool = False) -> None:
        df = getattr(self, "pending_import_df", None)
        if df is None:
            if not auto:
                messagebox.showerror("Bulk Import", "Select a CSV file first")
            return

        # Avoid stacking multiple preview windows
        try:
            win = getattr(self, "_import_preview_win", None)
            if win is not None and win.winfo_exists():
                try:
                    win.lift()
                    win.focus_force()
                except Exception:
                    pass
                return
        except Exception:
            pass

        has_broker = "broker" in df.columns

        top = tk.Toplevel(self)
        self._import_preview_win = top
        top.title("Bulk Import Preview")
        top.configure(bg=ModernStyle.BG_PRIMARY)
        top.geometry("980x560")
        try:
            top.transient(self.winfo_toplevel())
            top.grab_set()
        except Exception:
            pass

        try:
            center_window(top, parent=self.winfo_toplevel())
        except Exception:
            pass

        hdr = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        hdr.pack(fill="x", padx=16, pady=14)
        tk.Label(hdr, text="Bulk Import • Preview", fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_TITLE).pack(anchor="w")
        tk.Label(
            hdr,
            text="Review rows and confirm import.",
            fg=ModernStyle.TEXT_SECONDARY,
            bg=ModernStyle.BG_PRIMARY,
            font=ModernStyle.FONT_BODY,
        ).pack(anchor="w")

        body = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Top row: compact broker dropdown + actions
        top_row = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        top_row.pack(fill="x", pady=(0, 10))

        broker_var = tk.StringVar(value=(self.import_broker_var.get() or ""))
        broker_cb = None
        if not has_broker:
            tk.Label(top_row, text="Broker:", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_SMALL).pack(side="left")
            broker_cb = ttk.Combobox(top_row, textvariable=broker_var, state="readonly", width=18)
            try:
                broker_cb["values"] = list(self.import_broker_cb["values"])
            except Exception:
                broker_cb["values"] = []
            broker_cb.pack(side="left", padx=(8, 12))
            pass
        else:
            tk.Label(top_row, text="Broker: (from CSV)", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_SMALL).pack(side="left")

        top_row_btns = tk.Frame(top_row, bg=ModernStyle.BG_PRIMARY)
        top_row_btns.pack(side="right")

        # Preview table
        table = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        table.pack(fill="both", expand=True)

        preview_cols = ["#"]
        for c in ["broker", "date", "symbol", "type", "qty", "price", "trade_id"]:
            if c in df.columns:
                preview_cols.append(c)
        if len(preview_cols) == 1: # only "#"
            preview_cols.extend(list(df.columns[:7]))

        tv = ttk.Treeview(table, columns=tuple(preview_cols), show="headings", height=16)
        for c in preview_cols:
            tv.heading(c, text=c)
            tv.column(c, width=80)
            
        add_treeview_copy_menu(tv)

        vsb = ttk.Scrollbar(table, orient="vertical", command=tv.yview)
        hsb = ttk.Scrollbar(table, orient="horizontal", command=tv.xview)
        tv.configure(yscroll=vsb.set, xscroll=hsb.set)
        tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)

        max_rows = 200
        try:
            sample = df.head(max_rows)
        except Exception:
            sample = df
        try:
            for idx, r in enumerate(sample.itertuples(index=False)):
                vals = []
                for c in preview_cols:
                    if c == "#":
                        vals.append(str(idx + 1))
                    else:
                        vals.append(str(getattr(r, c, "")))
                tv.insert("", "end", values=tuple(vals))
        except Exception:
            pass

        footer = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        footer.pack(fill="x", pady=(10, 0))
        note = f"Showing first {min(len(df), max_rows)} of {len(df)} row(s)."
        tk.Label(footer, text=note, fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_SMALL).pack(side="left")

        status = tk.Label(footer, text="", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_SMALL)
        status.pack(side="left", padx=(10, 0))

        def _close_only() -> None:
            try:
                top.destroy()
            except Exception:
                pass

        close_btn = ModernButton(
            top_row_btns,
            text="Close",
            command=_close_only,
            bg=ModernStyle.SALMON,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=96,
            height=36,
        )
        close_btn.pack(side="right")

        def _on_finish(inserted: int, dupes: list, err: str | None) -> None:
            try:
                self.import_confirm_btn.set_disabled(False)
            except Exception:
                pass
            try:
                confirm_btn.set_disabled(False)
                close_btn.set_disabled(False)
            except Exception:
                pass

            if err:
                status.config(text=f"❌ {err}", fg=ModernStyle.ERROR)
                self.import_status.config(text=f"Import failed: {err}")
                return

            self._finish_import(inserted, dupes, err=None)
            try:
                top.destroy()
            except Exception:
                pass

        def _confirm() -> None:
            chosen = (broker_var.get() or "").strip()
            if not has_broker and not chosen:
                status.config(text="Select a broker")
                return

            status.config(text="Importing…")
            self.import_status.config(text="Importing…")
            try:
                self.import_confirm_btn.set_disabled(True)
            except Exception:
                pass
            try:
                confirm_btn.set_disabled(True)
                close_btn.set_disabled(True)
            except Exception:
                pass

            self._start_bulk_import(df, chosen, _on_finish)

        confirm_btn = ModernButton(
            top_row_btns,
            text="Confirm Import",
            command=_confirm,
            bg=ModernStyle.SUCCESS,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=150,
            height=36,
        )
        confirm_btn.pack(side="right", padx=(0, 10))

    def _confirm_import(self) -> None:
        df = getattr(self, "pending_import_df", None)
        if df is None:
            messagebox.showerror("Bulk Import", "Select a CSV file first")
            return

        has_broker = "broker" in df.columns
        chosen_broker = (self.import_broker_var.get() or "").strip()
        if not has_broker and not chosen_broker:
            messagebox.showerror("Bulk Import", "Select a broker for this import")
            return

        self.import_status.config(text="Importing…")
        try:
            self.import_confirm_btn.set_disabled(True)
        except Exception:
            pass

        self._start_bulk_import(df, chosen_broker, lambda inserted, dupes, err: self._finish_import(inserted, dupes, err))

    def _finish_import(self, inserted: int, dupes: list, err: str | None) -> None:
        try:
            self.import_confirm_btn.set_disabled(False)
        except Exception:
            pass
        if err:
            self.import_status.config(text=f"Import failed: {err}")
            return

        self.import_status.config(text=f"Imported {inserted} trades")
        self._set_dupes(dupes)

        # Invalidate cached views so they reload fresh data on next navigate
        if inserted > 0:
            self._invalidate_other_views()

    def _set_dupes(self, dupes: list) -> None:
        for item in self.dupe_table.get_children():
            self.dupe_table.delete(item)
        if not dupes:
            try:
                self.dupe_card.pack_forget()
            except Exception:
                pass
            return
        for d, s, q in dupes[:200]:
            self.dupe_table.insert("", "end", values=(str(d), str(s), f"{float(q):g}"))
        # show card
        try:
            self.dupe_card.pack(fill="x")
        except Exception:
            pass
    

