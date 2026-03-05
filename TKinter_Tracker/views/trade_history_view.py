"""
Trade History view for TKinter-based PTracker application.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime, timedelta

from TKinter_Tracker.views.base_view import BaseView, _create_date_input
from TKinter_Tracker.ui_theme import ModernStyle
from TKinter_Tracker.ui_widgets import ModernButton
from TKinter_Tracker.ui_utils import center_window

class TradeHistoryView(BaseView):
    """View all trades in history."""
    
    def build(self):
        """Build trade history view with full Flet-equivalent columns."""
        self._th_edit_popup = None
        header_frame = tk.Frame(self, bg=ModernStyle.BG_PRIMARY, height=60)
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        tk.Label(header_frame, text="📜 Trade History", fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_TITLE).pack(anchor="w")
        tk.Label(header_frame, text="All trades with running stats", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_BODY).pack(anchor="w")

        # Filters card (enhanced with quick date filters and better styling)
        filters = tk.Frame(self, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=1)
        filters.pack(fill="x", padx=15, pady=(0, 10))
        
        # Header with title and info
        header_row = tk.Frame(filters, bg=ModernStyle.BG_SECONDARY)
        header_row.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(header_row, text="🔍 Filters", fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SUBHEADING).pack(side="left")
        info_lbl = tk.Label(header_row, text="", fg=ModernStyle.TEXT_TERTIARY, bg=ModernStyle.BG_SECONDARY, font=ModernStyle.FONT_SMALL)
        info_lbl.pack(side="right", padx=(10, 0))
        self.th_date_range_info = info_lbl

        today = datetime.now()
        # Start date: exactly one month ago (using timedelta)
        one_month_ago = today - timedelta(days=30)
        start_default = one_month_ago.strftime("%Y-%m-%d")
        end_default = today.strftime("%Y-%m-%d")
        print(f"[DATE_INIT] today={today.strftime('%Y-%m-%d')}, one_month_ago={start_default}, end={end_default}")

        self.th_broker_var = tk.StringVar(value="All")
        self.th_symbol_var = tk.StringVar(value="")
        self.th_type_var = tk.StringVar(value="All")
        self.th_start_var = tk.StringVar(value=start_default)
        self.th_end_var = tk.StringVar(value=end_default)
        self._th_search_timer = None

        # Filter row with colored pills (matching Holdings view)
        filter_row = tk.Frame(filters, bg=ModernStyle.BG_SECONDARY)
        filter_row.pack(fill=tk.X, padx=12, pady=10)
        
        # Broker filter with background pill
        broker_pill = tk.Frame(filter_row, bg=ModernStyle.BG_SECONDARY, highlightbackground="#DBEAFE", highlightthickness=1)
        broker_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(broker_pill, text="🏦 Broker:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 13)).pack(side=tk.LEFT, padx=3, pady=3)
        self.th_broker_cb = ttk.Combobox(broker_pill, textvariable=self.th_broker_var, state="readonly", font=(ModernStyle.FONT_FAMILY, 13), height=5, width=11)
        self.th_broker_cb.pack(side=tk.LEFT, padx=3, pady=3)
        self.th_broker_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_filters())
        
        # Symbol filter with background pill
        symbol_pill = tk.Frame(filter_row, bg=ModernStyle.BG_SECONDARY, highlightbackground="#E9D5FF", highlightthickness=1)
        symbol_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(symbol_pill, text="📌 Symbol:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 13)).pack(side=tk.LEFT, padx=3, pady=3)
        self.th_symbol_entry = tk.Entry(symbol_pill, textvariable=self.th_symbol_var, bg=ModernStyle.ENTRY_BG, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 13), relief=tk.FLAT, width=11)
        self.th_symbol_entry.pack(side=tk.LEFT, padx=3, pady=3)
        
        # Type filter with background pill (segmented radios)
        type_pill = tk.Frame(filter_row, bg=ModernStyle.BG_SECONDARY, highlightbackground="#DCFCE7", highlightthickness=1)
        type_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(type_pill, text="📊 Type:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 13)).pack(side=tk.LEFT, padx=3, pady=3)
        self.th_type_wrap = tk.Frame(type_pill, bg=ModernStyle.BG_SECONDARY)
        self.th_type_wrap.pack(side=tk.LEFT, padx=3, pady=3)
        
        self.th_type_all_rb = tk.Radiobutton(
            self.th_type_wrap,
            text="All",
            variable=self.th_type_var,
            value="All",
            indicatoron=0,
            width=4,
            padx=6,
            pady=4,
            font=(ModernStyle.FONT_FAMILY, 11),
            relief=tk.FLAT,
            bd=0,
            bg="#2a5a8a",
            fg="#ffffff",
            selectcolor="#3d7ba8",
            activebackground="#3d7ba8",
            command=lambda: (self._sync_th_type_buttons(), self._apply_filters()),
        )
        self.th_type_buy_rb = tk.Radiobutton(
            self.th_type_wrap,
            text="BUY",
            variable=self.th_type_var,
            value="BUY",
            indicatoron=0,
            width=4,
            padx=6,
            pady=4,
            font=(ModernStyle.FONT_FAMILY, 11),
            relief=tk.FLAT,
            bd=0,
            bg="#2a5a8a",
            fg="#ffffff",
            selectcolor="#3d7ba8",
            activebackground="#3d7ba8",
            command=lambda: (self._sync_th_type_buttons(), self._apply_filters()),
        )
        self.th_type_sell_rb = tk.Radiobutton(
            self.th_type_wrap,
            text="SELL",
            variable=self.th_type_var,
            value="SELL",
            indicatoron=0,
            width=4,
            padx=6,
            pady=4,
            font=(ModernStyle.FONT_FAMILY, 11),
            relief=tk.FLAT,
            bd=0,
            bg="#2a5a8a",
            fg="#ffffff",
            selectcolor="#3d7ba8",
            activebackground="#3d7ba8",
            command=lambda: (self._sync_th_type_buttons(), self._apply_filters()),
        )
        self.th_type_all_rb.pack(side="left", padx=(0, 3))
        self.th_type_buy_rb.pack(side="left", padx=(0, 3))
        self.th_type_sell_rb.pack(side="left")
        
        # Date range filters with colored pills
        start_pill = tk.Frame(filter_row, bg=ModernStyle.BG_SECONDARY, highlightbackground="#FEF3C7", highlightthickness=1)
        start_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(start_pill, text="📅 Start:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 13)).pack(side=tk.LEFT, padx=3, pady=3)
        self.th_start_entry = _create_date_input(start_pill, self.th_start_var)
        self.th_start_entry.pack(side=tk.LEFT, padx=3, pady=3)
        
        end_pill = tk.Frame(filter_row, bg=ModernStyle.BG_SECONDARY, highlightbackground="#FEF3C7", highlightthickness=1)
        end_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(end_pill, text="📅 End:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 13)).pack(side=tk.LEFT, padx=3, pady=3)
        self.th_end_entry = _create_date_input(end_pill, self.th_end_var)
        self.th_end_entry.pack(side=tk.LEFT, padx=3, pady=3)
        
        # Spacer
        tk.Frame(filter_row, bg=ModernStyle.BG_SECONDARY).pack(side=tk.LEFT, expand=True)
        
        # Apply button at end of filter row
        ModernButton(
            filter_row,
            text="Apply",
            command=self._apply_filters,
            bg=ModernStyle.ACCENT_PRIMARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_SECONDARY,
            width=80,
            height=28,
        ).pack(side=tk.LEFT, padx=2, pady=3)

        # Trace date changes to update info label and reload data
        def _on_date_change(*_):
            print(f"[TRACE] Date changed: start={self.th_start_var.get()}, end={self.th_end_var.get()}")
            self._update_date_range_info()
            self._apply_filters()
        
        try:
            self.th_start_var.trace_add("write", _on_date_change)
            self.th_end_var.trace_add("write", _on_date_change)
            print(f"[BIND] StringVar trace callbacks registered")
        except Exception as e:
            print(f"[BIND_ERROR] StringVar trace failed: {e}")
        
        # Also bind to widget events to catch date picker changes (for tkcalendar.DateEntry)
        try:
            # Try multiple events that DateEntry might fire
            for event in ["<<Change>>", "<FocusOut>", "<KeyRelease>"]:
                self.th_start_entry.bind(event, lambda _,  event=event: print(f"[EVENT] start_entry {event}") or _on_date_change())
                self.th_end_entry.bind(event, lambda _, event=event: print(f"[EVENT] end_entry {event}") or _on_date_change())
            print(f"[BIND] Widget event bindings registered for date entries")
        except Exception as e:
            print(f"[BIND_ERROR] Widget event binding failed: {e}")
        
        # Initialize date range info and load data
        print(f"[INIT] Start date: {self.th_start_var.get()}, End date: {self.th_end_var.get()}")
        self._update_date_range_info()
        self._apply_filters()  # Load initial data

        def _debounced_symbol(*_):
            try:
                if self._th_search_timer is not None:
                    self.after_cancel(self._th_search_timer)
            except Exception:
                pass
            self._th_search_timer = self.after(180, self._apply_filters)

        try:
            self.th_symbol_var.trace_add("write", _debounced_symbol)
        except Exception:
            pass

        self._sync_th_type_buttons()

        # Summary card (pill-style metrics - matching Holdings view)
        summary = tk.Frame(self, bg=ModernStyle.BG_PRIMARY, highlightbackground=ModernStyle.BORDER_COLOR, highlightthickness=0)
        summary.pack(fill="x", padx=15, pady=3)

        # Metrics and buttons in same row
        sum_row = tk.Frame(summary, bg=ModernStyle.BG_PRIMARY)
        sum_row.pack(fill="x", padx=0, pady=4)
        
        # Define colored pills for each stat (matching Holdings view)
        stat_configs = [
            ("Trades", "trades", ModernStyle.ACCENT_PRIMARY, "#DBEAFE"),        # Blue
            ("Net Qty", "qty", ModernStyle.ACCENT_SECONDARY, "#DCFCE7"),        # Green
            ("Fees", "fees", ModernStyle.ACCENT_TERTIARY, "#FEF3C7"),           # Amber
            ("Running PnL", "pnl", "#0891B2", "#CFFAFE"),                       # Cyan
        ]
        
        for label, key, color, pill_bg in stat_configs:
            stat_pill = tk.Frame(sum_row, bg=ModernStyle.BG_SECONDARY, highlightbackground=pill_bg, highlightthickness=2)
            stat_pill.pack(side=tk.LEFT, padx=4, pady=4, expand=True, fill=tk.X, ipady=4, ipadx=8)
            
            tk.Label(stat_pill, text=label, bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_SECONDARY, font=(ModernStyle.FONT_FAMILY, 9, "bold")).pack()
            
            val_label = tk.Label(stat_pill, text="—", bg=ModernStyle.BG_SECONDARY, fg=color, font=(ModernStyle.FONT_FAMILY, 18, "bold"))
            val_label.pack(pady=(2, 0))
            
            setattr(self, f"sum_{key}", val_label)

        # Spacer
        tk.Frame(sum_row, bg=ModernStyle.BG_PRIMARY).pack(side=tk.LEFT, expand=True)
        
        # Action buttons on same row as metrics (right side)
        actions = tk.Frame(sum_row, bg=ModernStyle.BG_PRIMARY)
        actions.pack(side=tk.RIGHT, padx=4)

        ModernButton(
            actions,
            text="Copy Selected",
            command=self._copy_selected,
            bg=ModernStyle.ACCENT_TERTIARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=120,
            height=28,
        ).pack(side=tk.LEFT, padx=(0, 4))
        
        ModernButton(
            actions,
            text="Copy All",
            command=self._copy_all,
            bg=ModernStyle.ACCENT_PRIMARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=90,
            height=28,
        ).pack(side=tk.LEFT, padx=(0, 4))
        
        ModernButton(
            actions,
            text="Delete Trade",
            command=self._delete_selected,
            bg=ModernStyle.ERROR,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=110,
            height=28,
        ).pack(side=tk.LEFT)

        # Table frame
        table_frame = tk.Frame(self, bg=ModernStyle.BG_PRIMARY)
        table_frame.pack(fill="both", expand=True, padx=15, pady=10)

        columns = (
            "Sel",
            "#",
            "Date",
            "Trade ID",
            "Symbol",
            "Type",
            "Qty",
            "Price ₹",
            "Run. Qty",
            "AvgCost ₹",
            "Running PnL ₹",
            "Fees ₹",
        )
        self.trade_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=18, selectmode="extended")

        widths = [42, 40, 100, 95, 80, 60, 70, 90, 80, 90, 120, 80]
        for col, w in zip(columns, widths):
            self.trade_table.heading(col, text=col)
            self.trade_table.column(col, width=w)

        try:
            self.trade_table.tag_configure("odd", background=ModernStyle.BG_SECONDARY)
            self.trade_table.tag_configure("even", background=ModernStyle.BG_PRIMARY)
        except Exception:
            pass

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.trade_table.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.trade_table.xview)
        self.trade_table.configure(yscroll=vsb.set, xscroll=hsb.set)

        self.trade_table.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Edit on double-click
        try:
            self.trade_table.bind("<Double-1>", self._on_double_click)
        except Exception:
            pass
        
        # Right-click context menu (Button-2 for macOS 3-button mouse, Button-3 for others)
        try:
            self.trade_table.bind("<Button-2>", self._show_trade_context_menu)
            self.trade_table.bind("<Button-3>", self._show_trade_context_menu)
        except Exception:
            pass

    @staticmethod
    def _make_trade_iid(broker: str, trade_id: str) -> str:
        # Keep an internal unique ID so we can edit/delete reliably.
        b = (broker or "").replace("|", "/").strip()
        t = (trade_id or "").replace("|", "/").strip()
        return f"{b}|{t}"

    @staticmethod
    def _split_trade_iid(iid: str) -> tuple[str, str]:
        s = str(iid or "")
        if "|" not in s:
            return "", s
        b, t = s.split("|", 1)
        return b, t

    @staticmethod
    def _parse_money(s: str) -> float:
        v = (s or "").strip().replace("₹", "").replace(",", "")
        if v in ("", "—"):
            return 0.0
        return float(v)

    @staticmethod
    def _parse_float(s: str) -> float:
        v = (s or "").strip().replace(",", "")
        if not v:
            return 0.0
        return float(v)

    def _on_double_click(self, event=None) -> None:
        try:
            if self.trade_table.identify_region(event.x, event.y) != "cell":
                return
        except Exception:
            pass

        iid = None
        try:
            iid = self.trade_table.focus()
        except Exception:
            iid = None
        if not iid:
            return

        broker, trade_id = self._split_trade_iid(iid)
        vals = self.trade_table.item(iid, "values") or ()
        if len(vals) < 12:
            return

        date = str(vals[2])
        symbol = str(vals[4])
        t_type = str(vals[5]).upper()
        qty = str(vals[6])
        price = str(vals[7])
        fee = str(vals[11])

        self._open_edit_trade_dialog(
            broker=broker,
            trade_id=str(trade_id),
            date=date,
            symbol=symbol,
            trade_type=t_type,
            qty=qty,
            price=price,
            fee=fee,
        )

    def _open_edit_trade_dialog(
        self,
        *,
        broker: str,
        trade_id: str,
        date: str,
        symbol: str,
        trade_type: str,
        qty: str,
        price: str,
        fee: str,
    ) -> None:
        if not broker or not trade_id:
            messagebox.showerror("Edit Trade", "Missing broker/trade id for this row.")
            return

        try:
            if self._th_edit_popup is not None and self._th_edit_popup.winfo_exists():
                self._th_edit_popup.destroy()
        except Exception:
            pass

        win = tk.Toplevel(self)
        self._th_edit_popup = win
        win.title("✏️ Edit Trade")
        win.configure(bg="#0f1419")
        win.resizable(False, False)
        win.geometry("580x620")
        try:
            win.transient(self.winfo_toplevel())
            win.grab_set()
        except Exception:
            pass

        try:
            center_window(win, parent=self.winfo_toplevel())
        except Exception:
            pass

        # Elegant header with gradient-like effect
        header = tk.Frame(win, bg="#1e293b", height=70)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)
        
        tk.Label(
            header, 
            text="✏️ Edit Trade", 
            bg="#1e293b", 
            fg="#ffffff", 
            font=(ModernStyle.FONT_FAMILY, 20, "bold")
        ).pack(anchor="w", padx=24, pady=(16, 4))
        
        tk.Label(
            header, 
            text=f"Trade ID: {trade_id}", 
            bg="#1e293b", 
            fg="#94a3b8", 
            font=(ModernStyle.FONT_FAMILY, 11)
        ).pack(anchor="w", padx=24, pady=(0, 12))

        # Main content card with refined styling
        card = tk.Frame(win, bg=ModernStyle.BG_SECONDARY, highlightbackground="#334155", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        form = tk.Frame(card, bg=ModernStyle.BG_SECONDARY)
        form.pack(fill="x", padx=20, pady=20)
        for i in range(2):
            form.grid_columnconfigure(i, weight=1)

        def _field(label: str, emoji: str, r: int, c: int, var: tk.StringVar, *, readonly: bool = False, is_date: bool = False):
            # Label with emoji - larger, more readable
            label_frame = tk.Frame(form, bg=ModernStyle.BG_SECONDARY)
            label_frame.grid(row=r * 2, column=c, sticky="w", pady=(8 if r > 0 else 0, 6), padx=(0, 12 if c == 0 else 0))
            
            tk.Label(
                label_frame, 
                text=f"{emoji} {label}", 
                bg=ModernStyle.BG_SECONDARY, 
                fg="#1e293b", 
                font=(ModernStyle.FONT_FAMILY, 13, "bold")
            ).pack(side="left")
            
            # Entry with enhanced styling - light background
            if is_date:
                ent = _create_date_input(form, var)
                ent.grid(row=r * 2 + 1, column=c, sticky="ew", pady=(0, 14), padx=(0, 12 if c == 0 else 0))
            else:
                ent = tk.Entry(
                    form, 
                    textvariable=var, 
                    bg="#ffffff", 
                    fg="#1e293b", 
                    font=(ModernStyle.FONT_FAMILY, 14, "bold"), 
                    relief=tk.SOLID,
                    insertbackground="#3b82f6",
                    borderwidth=2,
                    highlightthickness=0
                )
                if readonly:
                    try:
                        ent.configure(state="readonly", bg="#f1f5f9", fg="#64748b")
                    except Exception:
                        pass
                ent.grid(row=r * 2 + 1, column=c, sticky="ew", pady=(0, 14), padx=(0, 12 if c == 0 else 0), ipady=8)
            return ent

        self._edit_broker_var = tk.StringVar(value=(broker or "").strip())
        self._edit_date_var = tk.StringVar(value=(date or "").strip())
        self._edit_symbol_var = tk.StringVar(value=(symbol or "").strip().upper())
        self._edit_type_var = tk.StringVar(value=(trade_type or "BUY").strip().upper())
        self._edit_qty_var = tk.StringVar(value=str(qty).replace(",", "").replace("₹", "").strip())
        self._edit_price_var = tk.StringVar(value=str(price).replace(",", "").replace("₹", "").strip())
        self._edit_fee_var = tk.StringVar(value=str(fee).replace(",", "").replace("₹", "").strip())

        _field("Broker", "🏦", 0, 0, self._edit_broker_var)
        _field("Trade Date", "📅", 0, 1, self._edit_date_var, is_date=True)
        _field("Symbol", "📌", 1, 0, self._edit_symbol_var)
        _field("Quantity", "📊", 1, 1, self._edit_qty_var)

        # Type with simple radio buttons - spans both columns
        label_frame = tk.Frame(form, bg=ModernStyle.BG_SECONDARY)
        label_frame.grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 6), padx=(0, 0))
        tk.Label(
            label_frame, 
            text="💼 Trade Type", 
            bg=ModernStyle.BG_SECONDARY, 
            fg="#1e293b", 
            font=(ModernStyle.FONT_FAMILY, 13, "bold")
        ).pack(side="left")
        
        type_wrap = tk.Frame(form, bg=ModernStyle.BG_SECONDARY)
        type_wrap.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 14), padx=(0, 0))
        
        self._edit_type_buy_rb = tk.Radiobutton(
            type_wrap,
            text="BUY",
            variable=self._edit_type_var,
            value="BUY",
            bg=ModernStyle.BG_SECONDARY,
            fg="#059669",
            font=(ModernStyle.FONT_FAMILY, 13, "bold"),
            selectcolor=ModernStyle.BG_SECONDARY,
            activebackground=ModernStyle.BG_SECONDARY,
            activeforeground="#10b981",
        )
        self._edit_type_buy_rb.pack(side="left", padx=(0, 30))
        
        self._edit_type_sell_rb = tk.Radiobutton(
            type_wrap,
            text="SELL",
            variable=self._edit_type_var,
            value="SELL",
            bg=ModernStyle.BG_SECONDARY,
            fg="#DC2626",
            font=(ModernStyle.FONT_FAMILY, 13, "bold"),
            selectcolor=ModernStyle.BG_SECONDARY,
            activebackground=ModernStyle.BG_SECONDARY,
            activeforeground="#ef4444",
        )
        self._edit_type_sell_rb.pack(side="left")

        _field("Price (₹)", "💰", 3, 0, self._edit_price_var)
        _field("Fees (₹)", "💸", 3, 1, self._edit_fee_var)

        # Status message area with refined styling
        status = tk.Label(
            card, 
            text="", 
            bg=ModernStyle.BG_SECONDARY, 
            fg="#64748b", 
            font=(ModernStyle.FONT_FAMILY, 10, "italic"),
            anchor="w"
        )
        status.pack(anchor="w", padx=20, pady=(8, 16), fill="x")

        # Action buttons with improved layout
        actions = tk.Frame(card, bg=ModernStyle.BG_SECONDARY)
        actions.pack(fill="x", padx=20, pady=(0, 20))

        def _close():
            try:
                win.destroy()
            except Exception:
                pass

        ModernButton(
            actions, 
            text="✓ Update Trade", 
            command=lambda: self._save_trade_edits(broker, trade_id, status, win), 
            bg="#3b82f6", 
            fg="#ffffff", 
            canvas_bg=ModernStyle.BG_SECONDARY, 
            width=160, 
            height=42,
            radius=8,
            font=(ModernStyle.FONT_FAMILY, 12, "bold")
        ).pack(side="right")
        
        ModernButton(
            actions, 
            text="✕ Cancel", 
            command=_close, 
            bg="#475569", 
            fg="#ffffff", 
            canvas_bg=ModernStyle.BG_SECONDARY, 
            width=130, 
            height=42,
            radius=8,
            font=(ModernStyle.FONT_FAMILY, 12, "bold")
        ).pack(side="right", padx=(0, 12))

    def _save_trade_edits(self, broker_old: str, trade_id: str, status_label: tk.Label, dialog: tk.Toplevel) -> None:
        # Validate inputs
        try:
            broker = (self._edit_broker_var.get() or "").strip()
            if not broker:
                raise ValueError("Broker is required")
            date = self._parse_date_or_none(self._edit_date_var.get() or "")
            if not date:
                raise ValueError("Date must be YYYY-MM-DD")
            symbol = (self._edit_symbol_var.get() or "").strip().upper()
            if not symbol:
                raise ValueError("Symbol is required")
            t_type = (self._edit_type_var.get() or "BUY").strip().upper()
            if t_type not in ("BUY", "SELL"):
                raise ValueError("Type must be BUY or SELL")
            qty = self._parse_float(self._edit_qty_var.get())
            price = self._parse_float(self._edit_price_var.get())
            fee = self._parse_float(self._edit_fee_var.get())
            if qty <= 0:
                raise ValueError("Qty must be > 0")
            if price <= 0:
                raise ValueError("Price must be > 0")
        except Exception as e:
            status_label.configure(text=str(e), fg=ModernStyle.ERROR)
            return

        status_label.configure(text="Updating…", fg=ModernStyle.TEXT_TERTIARY)

        def _bg():
            err = None
            try:
                import models.crud as crud
                from TKinter_Tracker.common.engine import rebuild_holdings

                # If broker changed, delete old trade and add new one
                if broker != broker_old:
                    crud.delete_trade(broker_old, trade_id)
                    crud.add_trade(broker, date, symbol, t_type, float(qty), float(price), float(fee), trade_id)
                else:
                    # Just update the trade
                    crud.update_trade(broker, trade_id, date, symbol, t_type, float(qty), float(price), float(fee))
                
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

            def _done():
                if err:
                    status_label.configure(text=f"Update failed: {err}", fg=ModernStyle.ERROR)
                    return
                try:
                    dialog.destroy()
                except Exception:
                    pass
                self._apply_filters()

            self.after(0, _done)

        threading.Thread(target=_bg, daemon=True).start()

    def _delete_selected(self) -> None:
        try:
            items = list(self.trade_table.selection() or [])
        except Exception:
            items = []
        if not items:
            messagebox.showinfo("Trade History", "Select one or more rows to delete (Cmd-click / Shift-click).")
            return

        # Confirm
        if not messagebox.askyesno("Delete Trades", f"Delete {len(items)} selected trade(s)?\n\nThis cannot be undone."):
            return

        def _bg():
            err = None
            try:
                import models.crud as crud
                from TKinter_Tracker.common.engine import rebuild_holdings

                for iid in items:
                    broker, trade_id = self._split_trade_iid(iid)
                    if not broker or not trade_id:
                        continue
                    crud.delete_trade(broker, trade_id)

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

            def _done():
                if err:
                    messagebox.showerror("Delete Trades", f"Delete failed: {err}")
                    return
                self._apply_filters()

            self.after(0, _done)

        threading.Thread(target=_bg, daemon=True).start()

    def _copy_selected(self) -> None:
        try:
            items = list(self.trade_table.selection() or [])
        except Exception:
            items = []
        if not items:
            messagebox.showinfo("Trade History", "No rows selected.")
            return
        self._copy_items(items)

    def _copy_all(self) -> None:
        items = list(self.trade_table.get_children() or [])
        if not items:
            messagebox.showinfo("Trade History", "No data to copy.")
            return
        self._copy_items(items)

    def _copy_items(self, items: list[str]) -> None:
        cols = list(self.trade_table["columns"])
        lines = ["\t".join(cols)]
        for iid in items:
            vals = self.trade_table.item(iid, "values")
            lines.append("\t".join(str(v) for v in vals))
        text = "\n".join(lines)
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Trade History", f"Copied {len(items)} row(s) to clipboard.")
        except Exception as e:
            messagebox.showerror("Trade History", f"Failed to copy: {e}")

    def _show_trade_context_menu(self, event) -> None:
        """Show right-click context menu for trade history table."""
        try:
            iid = self.trade_table.identify_row(event.y)
            if not iid:
                return
            
            # Select the clicked row if not already selected
            if iid not in self.trade_table.selection():
                self.trade_table.selection_set(iid)
            
            # Get trade data for edit
            vals = self.trade_table.item(iid, "values") or ()
            
            # Create context menu
            menu = tk.Menu(self.trade_table, tearoff=False)
            
            # Only enable Edit if we have enough values
            if len(vals) >= 12:
                menu.add_command(label="Edit", command=lambda: self._edit_from_context(iid))
            
            menu.add_command(label="Copy", command=self._copy_selected)
            menu.add_separator()
            menu.add_command(label="Delete", command=self._delete_selected)
            
            # Display menu
            menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"Context menu error: {e}")

    def _edit_from_context(self, iid: str) -> None:
        """Edit a trade from context menu."""
        try:
            broker, trade_id = self._split_trade_iid(iid)
            vals = self.trade_table.item(iid, "values") or ()
            if len(vals) < 12:
                messagebox.showerror("Edit Trade", "Invalid row data.")
                return

            date = str(vals[2])
            symbol = str(vals[4])
            t_type = str(vals[5]).upper()
            qty = str(vals[6])
            price = str(vals[7])
            fee = str(vals[11])

            self._open_edit_trade_dialog(
                broker=broker,
                trade_id=trade_id,
                date=date,
                symbol=symbol,
                trade_type=t_type,
                qty=qty,
                price=price,
                fee=fee,
            )
        except Exception as e:
            messagebox.showerror("Edit Trade", f"Error: {e}")

    def on_show(self):
        self._is_active = True
        if not getattr(self, "_data_loaded", False):
            self.load_data()

    def on_hide(self):
        self._is_active = False

    def _parse_date_or_none(self, s: str) -> str | None:
        val = (s or "").strip()
        if not val:
            return None
        try:
            # Validate format
            datetime.strptime(val, "%Y-%m-%d")
        except Exception:
            raise ValueError("Date must be YYYY-MM-DD")
        return val

    def _update_date_range_info(self) -> None:
        """Update the date range info label to show selected range."""
        try:
            start_str = self.th_start_var.get().strip()
            end_str = self.th_end_var.get().strip()
            
            if start_str and end_str:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                end_dt = datetime.strptime(end_str, "%Y-%m-%d")
                days_diff = (end_dt - start_dt).days
                
                # Format: "Jan 1 - Jan 31 (31 days)"
                date_range = f"{start_dt.strftime('%b %d')} - {end_dt.strftime('%b %d')} ({days_diff + 1} days)"
                self.th_date_range_info.config(text=date_range)
            else:
                self.th_date_range_info.config(text="")
        except Exception:
            self.th_date_range_info.config(text="")

    def _debounced_symbol(self) -> None:
        """Debounced symbol search to avoid excessive filtering."""
        try:
            if self._th_search_timer is not None:
                self.after_cancel(self._th_search_timer)
        except Exception:
            pass
        self._th_search_timer = self.after(180, self._apply_filters)

    def _apply_filters(self) -> None:
        print(f"[APPLY_FILTERS] Called with start={self.th_start_var.get()}, end={self.th_end_var.get()}")
        # Update date range info display
        self._update_date_range_info()
        # Re-run load with current UI filters
        self._data_loaded = False
        self.load_data()

    def _clear_filters(self) -> None:
        try:
            self.th_broker_var.set("All")
            self.th_symbol_var.set("")
            self.th_type_var.set("All")
            today = datetime.now()
            # Start date: exactly one month ago (using timedelta)
            one_month_ago = today - timedelta(days=30)
            start_date = one_month_ago.strftime("%Y-%m-%d")
            self.th_start_var.set(start_date)
            self.th_end_var.set(today.strftime("%Y-%m-%d"))
        except Exception:
            pass
        self._apply_filters()

    def load_data(self):
        print(f"[LOAD_DATA] Called. _data_loaded={getattr(self, '_data_loaded', False)}")
        if getattr(self, "_data_loaded", False):
            print(f"[LOAD_DATA] Already loaded, returning early")
            return
        if self.app_state and hasattr(self.app_state, "data_cache"):
            self._data_loaded = True
            print(f"[LOAD_DATA] Spawning background thread to fetch data")

            def _bg():
                try:
                    from TKinter_Tracker.common.data_cache import TradeHistoryFilters

                    broker = (getattr(self, "th_broker_var", None).get() if hasattr(self, "th_broker_var") else "All")
                    symbol_like = (getattr(self, "th_symbol_var", None).get() if hasattr(self, "th_symbol_var") else "")
                    trade_type = (getattr(self, "th_type_var", None).get() if hasattr(self, "th_type_var") else "All")

                    start_raw = (getattr(self, "th_start_var", None).get() if hasattr(self, "th_start_var") else "")
                    end_raw = (getattr(self, "th_end_var", None).get() if hasattr(self, "th_end_var") else "")
                    start_date = self._parse_date_or_none(start_raw)
                    end_date = self._parse_date_or_none(end_raw)

                    print(f"[BG_THREAD] Fetching data: broker={broker}, symbol={symbol_like}, type={trade_type}, start={start_date}, end={end_date}")
                    filters = TradeHistoryFilters(
                        broker=broker or "All",
                        symbol_like=symbol_like or "",
                        trade_type=trade_type or "All",
                        start_date=start_date,
                        end_date=end_date,
                    )
                    df, summary = self.app_state.data_cache.get_tradehistory_filtered(filters)
                    print(f"[BG_THREAD] Data fetched: {len(df)} rows")
                    self.after(0, lambda: self._update_trades(df, summary))
                except ValueError as ve:
                    print(f"[BG_THREAD] ValueError: {ve}")
                    self.after(0, lambda: messagebox.showerror("Trade History", str(ve)))
                    self._data_loaded = False
                except Exception as e:
                    print(f"[BG_THREAD] Exception:  {e}")
                    import traceback
                    traceback.print_exc()
                    self._data_loaded = False

            # Load broker options each time in case settings changed.
            try:
                import models.crud as crud
                brokers = ["All"] + list(crud.get_all_brokers())
                self.th_broker_cb["values"] = brokers
                if self.th_broker_var.get() not in brokers:
                    self.th_broker_var.set("All")
            except Exception:
                pass

            threading.Thread(target=_bg, daemon=True).start()

    def _open_simple_date_picker(self, date_var: tk.StringVar, title: str = "Select Date") -> None:
        """Open a simple calendar grid date picker for Trade History."""
        top = tk.Toplevel(self)
        top.title(title)
        top.transient(self)
        top.grab_set()
        top.configure(bg=ModernStyle.BG_PRIMARY)
        
        try:
            current_date = datetime.strptime(date_var.get(), "%Y-%m-%d")
        except:
            current_date = datetime.now()
        
        display_year = current_date.year
        display_month = current_date.month
        
        def show_calendar(year, month):
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
            first_day = (first_day + 1) % 7
            
            if month == 12:
                next_month_obj = datetime(year + 1, 1, 1)
            else:
                next_month_obj = datetime(year, month + 1, 1)
            days_in_month = (next_month_obj - datetime(year, month, 1)).days
            
            week_frame = None
            col = 0
            
            if first_day > 0:
                week_frame = tk.Frame(grid_frame, bg=ModernStyle.BG_PRIMARY)
                week_frame.pack(fill="x")
                for _ in range(first_day):
                    tk.Label(week_frame, text="", bg=ModernStyle.BG_PRIMARY, width=6, height=3).pack(side="left")
                col = first_day
            
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
                        date_var.set(selected)
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
        
        calendar_frame = tk.Frame(top, bg=ModernStyle.BG_SECONDARY)
        calendar_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        show_calendar(display_year, display_month)
        top.geometry("280x320")

    def _sync_th_type_buttons(self) -> None:
        """Color the Trade History Type segmented radio buttons."""
        t = (self.th_type_var.get() or "All").upper()
        try:
            if t == "BUY":
                self.th_type_buy_rb.configure(bg=ModernStyle.ACCENT_SECONDARY, fg=ModernStyle.TEXT_ON_ACCENT, activebackground=ModernStyle.ACCENT_SECONDARY, activeforeground=ModernStyle.TEXT_ON_ACCENT)
                self.th_type_sell_rb.configure(bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY, activebackground=ModernStyle.BG_PRIMARY, activeforeground=ModernStyle.TEXT_PRIMARY)
                self.th_type_all_rb.configure(bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY, activebackground=ModernStyle.BG_PRIMARY, activeforeground=ModernStyle.TEXT_PRIMARY)
            elif t == "SELL":
                self.th_type_sell_rb.configure(bg=ModernStyle.ERROR, fg=ModernStyle.TEXT_ON_ACCENT, activebackground=ModernStyle.ERROR, activeforeground=ModernStyle.TEXT_ON_ACCENT)
                self.th_type_buy_rb.configure(bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY, activebackground=ModernStyle.BG_PRIMARY, activeforeground=ModernStyle.TEXT_PRIMARY)
                self.th_type_all_rb.configure(bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY, activebackground=ModernStyle.BG_PRIMARY, activeforeground=ModernStyle.TEXT_PRIMARY)
            else:
                self.th_type_all_rb.configure(bg=ModernStyle.ACCENT_PRIMARY, fg=ModernStyle.TEXT_ON_ACCENT, activebackground=ModernStyle.ACCENT_PRIMARY, activeforeground=ModernStyle.TEXT_ON_ACCENT)
                self.th_type_buy_rb.configure(bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY, activebackground=ModernStyle.BG_PRIMARY, activeforeground=ModernStyle.TEXT_PRIMARY)
                self.th_type_sell_rb.configure(bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY, activebackground=ModernStyle.BG_PRIMARY, activeforeground=ModernStyle.TEXT_PRIMARY)
        except Exception:
            pass

    def _update_trades(self, df, summary: dict):
        print(f"[UPDATE_TRADES] Called with {len(df)} rows")
        # clear
        for item in self.trade_table.get_children():
            self.trade_table.delete(item)

        # summary
        try:
            qty_buy = float(summary.get("qty_buy", 0.0) or 0.0)
            qty_sell = float(summary.get("qty_sell", 0.0) or 0.0)
            fee_buy = float(summary.get("fee_buy", 0.0) or 0.0)
            fee_sell = float(summary.get("fee_sell", 0.0) or 0.0)
            total_pnl = float(summary.get("total_pnl", 0.0) or 0.0)
            trades = int(getattr(df, "shape", [0])[0] or 0) if df is not None else 0
            net_qty = qty_buy - qty_sell
            self.sum_trades.config(text=f"{trades}")
            self.sum_qty.config(text=f"{net_qty:g}")
            self.sum_fees.config(text=f"₹{(fee_buy + fee_sell):,.2f}")
            self.sum_pnl.config(text=f"₹{total_pnl:,.2f}", fg=ModernStyle.SUCCESS if total_pnl >= 0 else ModernStyle.ERROR)
        except Exception:
            pass

        if df is None or getattr(df, "empty", True):
            return

        for idx, row in enumerate(df.itertuples(index=False)):
            row_type = str(getattr(row, "type", "")).upper()
            qty = float(getattr(row, "qty", 0.0) or 0.0)
            price = float(getattr(row, "price", 0.0) or 0.0)
            fee = float(getattr(row, "fee", 0.0) or 0.0)
            run_qty = float(getattr(row, "run_qty", 0.0) or 0.0)
            avg_cost = float(getattr(row, "avg_cost", 0.0) or 0.0)
            r_pnl = float(getattr(row, "running_pnl", 0.0) or 0.0)
            pnl_disp = f"₹{r_pnl:,.2f}" if row_type == "SELL" else "—"

            broker = str(getattr(row, "broker", "") or "").strip()
            trade_id = str(getattr(row, "trade_id", "") or "").strip()
            iid = self._make_trade_iid(broker, trade_id)

            values = (
                "☐",
                str(idx + 1),
                str(getattr(row, "date", "")),
                trade_id,
                str(getattr(row, "symbol", "")),
                row_type,
                f"{qty:g}",
                f"₹{price:,.2f}",
                f"{run_qty:g}",
                f"₹{avg_cost:,.2f}",
                pnl_disp,
                f"₹{fee:,.2f}",
            )
            tag = "even" if (idx % 2 == 0) else "odd"
            try:
                self.trade_table.insert("", "end", iid=iid, values=values, tags=(tag,))
            except Exception:
                # Fallback if iid collides (should be rare)
                self.trade_table.insert("", "end", values=values, tags=(tag,))


