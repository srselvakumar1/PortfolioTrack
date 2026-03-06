"""
Trade Entry view for TKinter-based PTracker application.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime

from TKinter_Tracker.views.base_view import BaseView, _create_date_input
from TKinter_Tracker.ui_theme import ModernStyle
from TKinter_Tracker.ui_widgets import ModernButton
from TKinter_Tracker.ui_utils import center_window

class TradeEntryView(BaseView):
    """Form for entering new trades."""
    
    def build(self):
        """Build Trade Entry view with Flet-equivalent cards."""
        self._data_loaded = False
        self.pending_import_df = None
        self._dupes = []

        header_frame = tk.Frame(self, bg=ModernStyle.BG_PRIMARY, height=60)
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        tk.Label(header_frame, text="➕ Trade Entry", fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_TITLE).pack(anchor="w")
        tk.Label(header_frame, text="Manual entry or bulk CSV import", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_BODY).pack(anchor="w")

        body = tk.Frame(self, bg=ModernStyle.BG_PRIMARY)
        body.pack(fill="both", expand=True, padx=15, pady=10)
        body.grid_columnconfigure(0, weight=1, uniform="te")
        body.grid_columnconfigure(1, weight=1, uniform="te")
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        right = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right.grid(row=0, column=1, sticky="nsew")

        def _card(parent, title: str):
            frame = tk.Frame(parent, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
            tk.Label(frame, text=title, fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).pack(anchor="w", padx=12, pady=(10, 6))
            inner = tk.Frame(frame, bg=ModernStyle.BG_SECONDARY)
            inner.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            return frame, inner

        # ===== Manual Entry Card =====
        manual_card, manual = _card(left, "Manual Trade Entry")
        manual_card.pack(fill="x", pady=(0, 14))

        self.te_status = tk.Label(manual, text="", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL)
        self.te_status.pack(anchor="w", pady=(0, 6))

        row1 = tk.Frame(manual, bg=ModernStyle.BG_SECONDARY)
        row1.pack(fill="x", pady=6)
        row1.grid_columnconfigure(0, weight=1)
        row1.grid_columnconfigure(1, weight=1)

        self.te_broker_var = tk.StringVar(value="")
        self.te_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        tk.Label(row1, text="Broker", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).grid(row=0, column=0, sticky="w")
        tk.Label(row1, text="Date", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).grid(row=0, column=1, sticky="w")

        self.te_broker_cb = ttk.Combobox(row1, textvariable=self.te_broker_var, state="readonly")
        self.te_broker_cb.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(3, 0))
        
        # Date input with calendar picker
        self.te_date_entry = _create_date_input(row1, self.te_date_var)
        self.te_date_entry.grid(row=1, column=1, sticky="ew", pady=(3, 0))

        row2 = tk.Frame(manual, bg=ModernStyle.BG_SECONDARY)
        row2.pack(fill="x", pady=6)
        row2.grid_columnconfigure(0, weight=1)
        row2.grid_columnconfigure(1, weight=1)

        self.te_symbol_var = tk.StringVar(value="")
        self.te_type_var = tk.StringVar(value="BUY")

        tk.Label(row2, text="Symbol", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).grid(row=0, column=0, sticky="w")
        tk.Label(row2, text="Type", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).grid(row=0, column=1, sticky="w")

        self.te_symbol_entry = tk.Entry(row2, textvariable=self.te_symbol_var, bg=ModernStyle.ENTRY_BG, fg=ModernStyle.TEXT_PRIMARY, font=ModernStyle.FONT_BODY, relief=tk.FLAT)
        self.te_symbol_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(3, 0))

        type_wrap = tk.Frame(row2, bg=ModernStyle.BG_SECONDARY)
        type_wrap.grid(row=1, column=1, sticky="w", pady=(3, 0))

        # Segmented BUY/SELL toggle (colored)
        self.te_buy_rb = tk.Radiobutton(
            type_wrap,
            text="BUY",
            variable=self.te_type_var,
            value="BUY",
            indicatoron=0,
            width=7,
            padx=10,
            pady=6,
            font=ModernStyle.FONT_SUBHEADING,
            relief=tk.FLAT,
            bd=0,
            command=lambda: (self._sync_te_type_buttons(), self._update_summary()),
        )
        self.te_sell_rb = tk.Radiobutton(
            type_wrap,
            text="SELL",
            variable=self.te_type_var,
            value="SELL",
            indicatoron=0,
            width=7,
            padx=10,
            pady=6,
            font=ModernStyle.FONT_SUBHEADING,
            relief=tk.FLAT,
            bd=0,
            command=lambda: (self._sync_te_type_buttons(), self._update_summary()),
        )
        self.te_buy_rb.pack(side="left", padx=(0, 10))
        self.te_sell_rb.pack(side="left")

        row3 = tk.Frame(manual, bg=ModernStyle.BG_SECONDARY)
        row3.pack(fill="x", pady=6)
        row3.grid_columnconfigure(0, weight=1)
        row3.grid_columnconfigure(1, weight=1)

        self.te_qty_var = tk.StringVar(value="")
        self.te_price_var = tk.StringVar(value="")

        tk.Label(row3, text="Quantity", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).grid(row=0, column=0, sticky="w")
        tk.Label(row3, text="Price (₹)", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).grid(row=0, column=1, sticky="w")

        self.te_qty_entry = tk.Entry(row3, textvariable=self.te_qty_var, bg=ModernStyle.ENTRY_BG, fg=ModernStyle.TEXT_PRIMARY, font=ModernStyle.FONT_BODY, relief=tk.FLAT)
        self.te_qty_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(3, 0))
        self.te_price_entry = tk.Entry(row3, textvariable=self.te_price_var, bg=ModernStyle.ENTRY_BG, fg=ModernStyle.TEXT_PRIMARY, font=ModernStyle.FONT_BODY, relief=tk.FLAT)
        self.te_price_entry.grid(row=1, column=1, sticky="ew", pady=(3, 0))

        self.te_fee_label = tk.Label(manual, text="Estimated Fee: ₹0.00", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL)
        self.te_fee_label.pack(anchor="w", pady=(10, 0))

        btns = tk.Frame(manual, bg=ModernStyle.BG_SECONDARY)
        btns.pack(fill="x", pady=(12, 0))
        ModernButton(btns, text="Save Trade", command=self._save_trade, bg=ModernStyle.ACCENT_PRIMARY, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg=ModernStyle.BG_SECONDARY, width=140, height=38).pack(side="left", padx=(0, 8))
        ModernButton(btns, text="Clear", command=self._clear_form, bg=ModernStyle.ACCENT_SECONDARY, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg=ModernStyle.BG_SECONDARY, width=96, height=38).pack(side="left")

        # ===== Bulk Import Card =====
        import_card, import_inner = _card(left, "Bulk Import (CSV)")
        import_card.pack(fill="x", pady=(0, 14))
        tk.Label(import_inner, text="Expected columns: broker(optional), date, symbol, type, qty, price", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL).pack(anchor="w")

        self.import_path_label = tk.Label(import_inner, text="No file selected", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY)
        self.import_path_label.pack(anchor="w", pady=(8, 6))

        imp_btns = tk.Frame(import_inner, bg=ModernStyle.BG_SECONDARY)
        imp_btns.pack(fill="x", pady=(4, 0))
        ModernButton(imp_btns, text="Select CSV File", command=self._select_import_file, bg=ModernStyle.ACCENT_TERTIARY, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg=ModernStyle.BG_SECONDARY, width=160, height=36).pack(side="left", padx=(0, 8))
        self.import_confirm_btn = ModernButton(imp_btns, text="Preview Import", command=self._open_import_preview_dialog, bg=ModernStyle.SUCCESS, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg=ModernStyle.BG_SECONDARY, width=160, height=36)
        self.import_confirm_btn.pack(side="left")

        self.import_broker_row = tk.Frame(import_inner, bg=ModernStyle.BG_SECONDARY)
        self.import_broker_row.pack(fill="x", pady=(10, 0))
        tk.Label(self.import_broker_row, text="Broker (required if CSV has no broker column)", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL).pack(anchor="w")
        self.import_broker_var = tk.StringVar(value="")
        self.import_broker_cb = ttk.Combobox(self.import_broker_row, textvariable=self.import_broker_var, state="readonly")
        self.import_broker_cb.pack(fill="x", pady=(3, 0))
        # Broker selection is handled in the preview popup.
        self.import_broker_row.pack_forget()

        self.import_status = tk.Label(import_inner, text="", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL)
        self.import_status.pack(anchor="w", pady=(10, 0))

        # ===== Skipped Duplicates Card =====
        self.dupe_card, dupe_inner = _card(left, "Skipped Duplicates")
        self.dupe_card.pack(fill="x")
        dupe_cols = ("Date", "Sym", "Qty")
        self.dupe_table = ttk.Treeview(dupe_inner, columns=dupe_cols, show="headings", height=6)
        self.dupe_table.heading("Date", text="Date")
        self.dupe_table.heading("Sym", text="Sym")
        self.dupe_table.heading("Qty", text="Qty")
        self.dupe_table.column("Date", width=120)
        self.dupe_table.column("Sym", width=120)
        self.dupe_table.column("Qty", width=80, anchor="e")
        vsb = ttk.Scrollbar(dupe_inner, orient="vertical", command=self.dupe_table.yview)
        self.dupe_table.configure(yscroll=vsb.set)
        self.dupe_table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        # hide by default
        self.dupe_card.pack_forget()

        # ===== Transaction Summary Card =====
        sum_card, sum_inner = _card(right, "Transaction Summary")
        sum_card.pack(fill="x")

        self.sum_type_label = tk.Label(sum_inner, text="Trade Type: BUY", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY)
        self.sum_type_label.pack(anchor="w")

        self.sum_qty_label = tk.Label(sum_inner, text="Quantity: —", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY)
        self.sum_qty_label.pack(anchor="w", pady=(6, 0))
        self.sum_price_label = tk.Label(sum_inner, text="Unit Price: —", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY)
        self.sum_price_label.pack(anchor="w")
        self.sum_subtotal_label = tk.Label(sum_inner, text="Subtotal: —", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY)
        self.sum_subtotal_label.pack(anchor="w")
        self.sum_fee_label = tk.Label(sum_inner, text="Trading Fee: ₹0.00", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_BODY)
        self.sum_fee_label.pack(anchor="w", pady=(0, 10))

        tk.Frame(sum_inner, bg=ModernStyle.DIVIDER_COLOR, height=1).pack(fill="x", pady=8)
        self.sum_total_label = tk.Label(sum_inner, text="Total Value: ₹0.00", fg=ModernStyle.SUCCESS, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_HEADING)
        self.sum_total_label.pack(anchor="w")

        # Live summary updates
        for v in (self.te_qty_var, self.te_price_var, self.te_symbol_var, self.te_date_var):
            try:
                v.trace_add("write", lambda *_: self._update_summary())
            except Exception:
                pass

        self._update_summary()
        self._sync_te_type_buttons()

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

    def load_data(self):
        if getattr(self, "_data_loaded", False):
            return
        self._data_loaded = True
        try:
            import models.crud as crud
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
            from TKinter_Tracker.common.engine import calculate_trade_fees
            fee = float(calculate_trade_fees(t_type, qty, price, is_delivery=True) or 0.0) if (qty > 0 and price > 0) else 0.0
        except Exception:
            fee = 0.0

        total = subtotal + fee if t_type == "BUY" else max(0.0, subtotal - fee)
        color = ModernStyle.SUCCESS if t_type == "BUY" else ModernStyle.ERROR

        self.te_fee_label.config(text=f"Estimated Fee: ₹{fee:,.2f}")
        self.sum_type_label.config(text=f"Trade Type: {t_type}")
        self.sum_qty_label.config(text=f"Quantity: {qty:g}" if qty > 0 else "Quantity: —")
        self.sum_price_label.config(text=f"Unit Price: ₹{price:,.2f}" if price > 0 else "Unit Price: —")
        self.sum_subtotal_label.config(text=f"Subtotal: ₹{subtotal:,.2f}" if subtotal > 0 else "Subtotal: —")
        self.sum_fee_label.config(text=f"Trading Fee: ₹{fee:,.2f}")
        self.sum_total_label.config(text=f"Total Value: ₹{total:,.2f}", fg=color)

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
        qty = self._parse_float(self.te_qty_var.get())
        price = self._parse_float(self.te_price_var.get())
        if not broker:
            messagebox.showerror("Trade Entry", "Please select a broker")
            return
        if not date:
            messagebox.showerror("Trade Entry", "Please enter a date (YYYY-MM-DD)")
            return
        if not symbol:
            messagebox.showerror("Trade Entry", "Please enter a symbol")
            return
        if qty <= 0:
            messagebox.showerror("Trade Entry", "Quantity must be > 0")
            return
        if price <= 0:
            messagebox.showerror("Trade Entry", "Price must be > 0")
            return

        try:
            from TKinter_Tracker.common.engine import calculate_trade_fees
            fee = float(calculate_trade_fees(t_type, qty, price, is_delivery=True) or 0.0)
        except Exception:
            fee = 0.0

        import time
        manual_id = f"MT_{date.replace('-', '')}_{int(time.time() * 1000)}"

        try:
            import models.crud as crud
            crud.add_trade(broker, date, symbol, t_type, qty, price, fee, manual_id)
        except Exception as e:
            messagebox.showerror("Trade Entry", f"Failed to save trade: {e}")
            return

        self.te_status.config(text=f"Saved {t_type} {symbol} ✓")
        self._clear_form()

        def _bg_refresh():
            try:
                from TKinter_Tracker.common.engine import rebuild_holdings
                rebuild_holdings()
            except Exception:
                pass
            try:
                if self.app_state and hasattr(self.app_state, "refresh_data_cache"):
                    self.app_state.refresh_data_cache()
            except Exception:
                pass

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
                self.after(0, lambda: self.import_status.config(text=f"Import load failed: {e}"))

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
                import models.crud as crud
                from TKinter_Tracker.common.engine import calculate_trade_fees, rebuild_holdings

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
            try:
                if not broker_var.get() and broker_cb["values"]:
                    broker_var.set(broker_cb["values"][0])
            except Exception:
                pass
        else:
            tk.Label(top_row, text="Broker: (from CSV)", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_SMALL).pack(side="left")

        top_row_btns = tk.Frame(top_row, bg=ModernStyle.BG_PRIMARY)
        top_row_btns.pack(side="right")

        # Preview table
        table = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        table.pack(fill="both", expand=True)

        preview_cols = []
        for c in ["broker", "date", "symbol", "type", "qty", "price", "trade_id"]:
            if c in df.columns:
                preview_cols.append(c)
        if not preview_cols:
            preview_cols = list(df.columns[:7])

        tv = ttk.Treeview(table, columns=tuple(preview_cols), show="headings", height=16)
        for c in preview_cols:
            tv.heading(c, text=c)
            tv.column(c, width=120, anchor="w")
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
            for r in sample.itertuples(index=False):
                vals = []
                for c in preview_cols:
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
                status.config(text=f"Import failed: {err}")
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
    
    def _save_trade(self):
        """Save the trade (placeholder)."""
        symbol = self.form_entries["symbol_entry"].get()
        if symbol:
            tk.Label(self, text=f"✓ Trade saved for {symbol}", fg=ModernStyle.SUCCESS, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_BODY).pack(pady=5)
            self._clear_form()
    
    def _clear_form(self):
        """Clear all form fields."""
        for entry in self.form_entries.values():
            entry.delete(0, "end")


