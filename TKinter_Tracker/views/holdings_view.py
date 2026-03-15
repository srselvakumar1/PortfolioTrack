"""
Holdings View - Tkinter Implementation
Modern, premium aesthetic with real-time data display
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import pandas as pd
from typing import Optional
from common.data_cache import DataCache, HoldingsFilters, TradeHistoryFilters
from common.database import db_session
import common.models.crud as crud

from ui_theme import ModernStyle
from ui_widgets import ModernButton, PremiumModal
from ui_utils import center_window, add_treeview_copy_menu, treeview_sort_column


class ModernEntry(tk.Entry):
    """Custom entry with modern styling."""
    
    def __init__(self, parent, placeholder="", **kwargs):
        super().__init__(parent, **kwargs)
        self.placeholder = placeholder
        self.default_color = ModernStyle.TEXT_TERTIARY
        self.normal_color = ModernStyle.TEXT_PRIMARY
        
        if placeholder:
            self.insert(0, placeholder)
            self.config(fg=self.default_color)
        
        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<FocusOut>', self._on_focus_out)
    
    def _on_focus_in(self, event=None):
        if self.get() == self.placeholder:
            self.delete(0, tk.END)
            self.config(fg=self.normal_color)
    
    def _on_focus_out(self, event=None):
        if not self.get():
            self.insert(0, self.placeholder)
            self.config(fg=self.default_color)
    
    def get_value(self):
        """Get entry value, ignoring placeholder."""
        val = self.get()
        return "" if val == self.placeholder else val


class HoldingsView(tk.Frame):
    """Holdings view - Display and manage holdings with filters."""
    
    def __init__(self, parent, app_state=None, **kwargs):
        super().__init__(parent, bg=ModernStyle.BG_PRIMARY, **kwargs)
        self.app_state = app_state
        self._is_active = False
        self._data_loaded = False
        self._search_timer = None
        self.current_df: Optional[pd.DataFrame] = None
        self._row_meta: dict[str, dict] = {}
        
        # Initialize data cache
        self.data_cache = DataCache()
        try:
            self.data_cache.refresh_from_db()
        except Exception as e:
            print(f"Error loading data cache: {e}")
        
        self.build()
    
    def build(self):
        self._build_header()
        self._build_filter_panel()
        self._build_stats_card()
        self._build_table()
        self.load_data()
    
    def _build_header(self):
        header = tk.Frame(self, bg=ModernStyle.BG_PRIMARY)
        header.pack(fill=tk.X, padx=20, pady=4)
        
        title = tk.Label(
            header,
            text="💹 Holdings",
            font=(ModernStyle.FONT_FAMILY, 24, "bold"),
            bg=ModernStyle.BG_PRIMARY,
            fg=ModernStyle.TEXT_PRIMARY
        )
        title.pack(anchor=tk.W)
        
        subtitle = tk.Label(
            header,
            text="Manage and monitor your stock portfolio",
            font=ModernStyle.FONT_BODY,
            bg=ModernStyle.BG_PRIMARY,
            fg=ModernStyle.TEXT_SECONDARY
        )
        subtitle.pack(anchor=tk.W)
        
        # Accent divider
        tk.Frame(self, bg=ModernStyle.BRAND_GOLD, height=1).pack(fill="x", padx=20, pady=(10, 5))
    
    def _build_filter_panel(self):
        """Build filters: broker, symbol, signal with colored pill styling."""
        filter_frame = tk.Frame(
            self,
            bg=ModernStyle.BG_PRIMARY,
            highlightbackground=ModernStyle.BORDER_COLOR,
            highlightthickness=0,
        )
        filter_frame.pack(fill=tk.X, padx=20, pady=4)
        
        # Broker filter with background pill
        broker_pill = tk.Frame(filter_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.ACCENT_PRIMARY_PALE, highlightthickness=1)
        broker_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(broker_pill, text="🏦 Broker:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 14, "bold")).pack(side=tk.LEFT, padx=3, pady=3)
        self.broker_var = tk.StringVar(value="All")
        self.broker_combo = ttk.Combobox(broker_pill, textvariable=self.broker_var, values=["All"], state="readonly", width=16, font=(ModernStyle.FONT_FAMILY, 13))
        self.broker_combo.pack(side=tk.LEFT, padx=3, pady=3)
        self.broker_combo.bind("<<ComboboxSelected>>", lambda e: self.on_filter_change())
        
        # Symbol search with background pill
        symbol_pill = tk.Frame(filter_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.ACCENT_PURPLE_PALE, highlightthickness=1)
        symbol_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(symbol_pill, text="🔍 Symbol:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 14, "bold")).pack(side=tk.LEFT, padx=3, pady=3)
        self.symbol_var = tk.StringVar()
        symbol_entry = ModernEntry(
            symbol_pill,
            placeholder="Search...",
            width=22,
            bg=ModernStyle.ENTRY_BG,
            fg=ModernStyle.TEXT_PRIMARY,
            insertbackground=ModernStyle.ACCENT_PRIMARY,
            highlightthickness=1,
            highlightbackground=ModernStyle.BORDER_COLOR,
            highlightcolor=ModernStyle.ACCENT_PRIMARY,
            relief=tk.FLAT,
            bd=0,
            font=(ModernStyle.FONT_FAMILY, 13),
        )
        symbol_entry.pack(side=tk.LEFT, padx=3, pady=3)
        symbol_entry.bind("<KeyRelease>", self._on_symbol_search)
        self.symbol_entry = symbol_entry
        
        # Signal filter with background pill
        signal_pill = tk.Frame(filter_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.ACCENT_SECONDARY_PALE, highlightthickness=1)
        signal_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(signal_pill, text="📊 Signal:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 14, "bold")).pack(side=tk.LEFT, padx=3, pady=3)
        self.signal_var = tk.StringVar(value="All")
        signal_combo = ttk.Combobox(signal_pill, textvariable=self.signal_var, values=["All", "ACCUMULATE", "REDUCE", "N/A"], state="readonly", width=14, font=(ModernStyle.FONT_FAMILY, 14))
        signal_combo.pack(side=tk.LEFT, padx=3, pady=3)
        signal_combo.bind("<<ComboboxSelected>>", lambda e: self.on_filter_change())

        # Exclude zero qty with background pill
        exclude_pill = tk.Frame(filter_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground=ModernStyle.ERROR_PALE, highlightthickness=1)
        exclude_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        self.exclude_zero_qty_var = tk.BooleanVar(value=True)
        exclude_chk = tk.Checkbutton(
            exclude_pill,
            text=" 🛡️ Filter 0 Qty",
            variable=self.exclude_zero_qty_var,
            bg=ModernStyle.BG_SECONDARY,
            fg=ModernStyle.TEXT_PRIMARY,
            activebackground=ModernStyle.BG_SECONDARY,
            activeforeground=ModernStyle.TEXT_PRIMARY,
            selectcolor=ModernStyle.BG_SECONDARY,
            font=(ModernStyle.FONT_FAMILY, 14,"bold"),
            relief="flat",          # Makes it flat
            command=self.on_filter_change,
        )
        exclude_chk.pack(side=tk.LEFT, padx=3, pady=3)
        
        # Spacer
        tk.Frame(filter_frame, bg=ModernStyle.BG_PRIMARY).pack(side=tk.LEFT, expand=True)
        
        # Buttons in a row
        apply_btn = ModernButton(
            filter_frame,
            text="Search",
            command=self.on_filter_change,
            bg=ModernStyle.ACCENT_PRIMARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=100,
            height=32,
        )
        apply_btn.pack(side=tk.LEFT, padx=2, pady=3)

        refresh_btn = ModernButton(
            filter_frame,
            text="Refresh",
            command=self.refresh,
            bg=ModernStyle.ACCENT_TERTIARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=100,
            height=32,
        )
        refresh_btn.pack(side=tk.LEFT, padx=2, pady=3)
        
        # Load brokers
        threading.Thread(target=self._load_brokers, daemon=True).start()
    
    def _build_stats_card(self):
        stats_frame = tk.Frame(
            self,
            bg=ModernStyle.BG_PRIMARY,
            highlightbackground=ModernStyle.BORDER_COLOR,
            highlightthickness=0,
        )
        stats_frame.pack(fill=tk.X, padx=20, pady=2)
        
        self.stats_labels = {}
        
        # Define colored pills for each stat
        stat_configs = [
            ("Holdings", "count", ModernStyle.ACCENT_PRIMARY, ModernStyle.ACCENT_PRIMARY_PALE),
            ("Invested", "invested", ModernStyle.ACCENT_SECONDARY, ModernStyle.ACCENT_SECONDARY_PALE),
            ("Current", "current", ModernStyle.INFO, ModernStyle.INFO_PALE),
            ("P&L", "pnl", ModernStyle.ACCENT_TERTIARY, ModernStyle.ACCENT_TERTIARY_PALE),
            ("Total Fees", "fees", ModernStyle.ERROR, ModernStyle.ERROR_PALE),
        ]
        
        for label, key, color, pill_bg in stat_configs:
            stat_pill = tk.Frame(stats_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground=pill_bg, highlightthickness=2)
            stat_pill.pack(side=tk.LEFT, padx=3, pady=3, expand=True, fill=tk.X, ipady=3, ipadx=4)
            
            tk.Label(stat_pill, text=label, bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_SECONDARY, font=ModernStyle.FONT_KPI_LABEL).pack()
            
            val_label = tk.Label(stat_pill, text="—", bg=ModernStyle.BG_SECONDARY, fg=color, font=ModernStyle.FONT_KPI_VALUE)
            val_label.pack(pady=(2, 0))
            
            self.stats_labels[key] = val_label

        # Right-side actions (requested: at right end of Summary section)
        tk.Frame(stats_frame, bg=ModernStyle.BG_PRIMARY).pack(side=tk.LEFT, expand=True, fill=tk.X)
        actions = tk.Frame(stats_frame, bg=ModernStyle.BG_PRIMARY)
        actions.pack(side=tk.RIGHT, padx=4, pady=3)

        ModernButton(
            actions,
            text="Delete",
            command=self._delete_selected_holding,
            bg=ModernStyle.ERROR,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=100,
            height=32,
        ).pack(side=tk.LEFT)
    
    def _build_table(self):
        """Build holdings table."""
        table_frame = tk.Frame(self, bg=ModernStyle.BG_PRIMARY)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=4)

        # Inner frame for the table grid (tree + scrollbars)
        inner = tk.Frame(table_frame, bg=ModernStyle.BG_PRIMARY)
        inner.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview (match Flet column set)
        columns = (
            "#",
            "Symbol",
            "Name",
            "Qty",
            "Avg Prc ₹",
            "Mkt Prc ₹",
            "Daily Chg",
            "Flash PnL ₹",
            "Weight%",
            "XIRR%",
            "CAGR%",
            "Real PnL ₹",
            "Fees ₹",
            "IV Signal",
        )
        self.tree = ttk.Treeview(inner, columns=columns, height=20, show="headings")
        
        # Define headings and column widths
        widths = [40, 100, 160, 60, 90, 90, 90, 100, 70, 70, 70, 100, 80, 80]
        sortable_cols = ("Symbol", "Fees ₹", "Real PnL ₹", "XIRR%", "CAGR%", "IV Signal")
        for col, w in zip(columns, widths):
            if col in sortable_cols:
                self.tree.heading(col, text=f"{col} ↕", command=lambda c=col: treeview_sort_column(self.tree, c, False))
            else:
                self.tree.heading(col, text=col)
            self.tree.column(col, width=w)

        # Alternating rows - clean zebra stripe, no per-row color overrides
        try:
            style = ttk.Style()
            style.configure("Holdings.Treeview", font=(ModernStyle.FONT_FAMILY, 12), rowheight=30)
            # Header: dark slate — clearly distinct from the blue row-selection colour
            style.configure(
                "Holdings.Treeview.Heading",
                font=(ModernStyle.FONT_FAMILY, 13, "bold"),
                background=ModernStyle.SLATE_800,
                foreground=ModernStyle.TEXT_ON_ACCENT,
                relief="flat",
            )
            style.map(
                "Holdings.Treeview.Heading",
                background=[("active", ModernStyle.SLATE_700)],
                foreground=[("active", ModernStyle.TEXT_ON_ACCENT)],
            )
            self.tree.configure(style="Holdings.Treeview")
            
            # Add right-click copy menu
            add_treeview_copy_menu(self.tree)

            # Only background zebra stripes — no foreground color tags on rows
            self.tree.tag_configure("odd",  background=ModernStyle.BG_SECONDARY)
            self.tree.tag_configure("even", background=ModernStyle.SLATE_50)
        except Exception:
            pass
        
        # Scrollbars
        vsb = ttk.Scrollbar(inner, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(inner, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        
        # Grid
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        # Open drilldown on double-click
        try:
            self.tree.bind("<Double-1>", lambda _e=None: self._open_drilldown_selected())
        except Exception:
            pass
        
        # Right-click context menu (Button-2 for macOS 3-button mouse, Button-3 for others)
        try:
            self.tree.bind("<Button-2>", self._show_holdings_context_menu)
            self.tree.bind("<Button-3>", self._show_holdings_context_menu)
        except Exception:
            pass

    def _copy_selected(self) -> None:
        try:
            items = list(self.tree.selection() or [])
        except Exception:
            items = []
        if not items:
            messagebox.showinfo("Holdings", "No rows selected.")
            return
        self._copy_items(items)

    def _copy_all(self) -> None:
        items = list(self.tree.get_children() or [])
        if not items:
            messagebox.showinfo("Holdings", "No data to copy.")
            return
        self._copy_items(items)

    def _copy_items(self, items: list[str]) -> None:
        cols = list(self.tree["columns"])
        lines = ["\t".join(cols)]
        for iid in items:
            vals = self.tree.item(iid, "values")
            lines.append("\t".join(str(v).replace("₹", "").replace(",", "").replace("%", "").strip() for v in vals))
        text = "\n".join(lines)
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Holdings", f"Copied {len(items)} row(s) to clipboard.")
        except Exception as e:
            messagebox.showerror("Holdings", f"Failed to copy: {e}")

    def _show_holdings_context_menu(self, event) -> None:
        """Show right-click context menu for holdings table."""
        try:
            iid = self.tree.identify_row(event.y)
            if not iid:
                return
            
            # Select the clicked row if not already selected
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            
            # Create context menu
            menu = tk.Menu(self.tree, tearoff=False)
            menu.add_command(label="Edit", command=lambda: self._edit_holding_properties(iid))
            menu.add_command(label="View Trades", command=self._open_drilldown_selected)
            menu.add_command(label="➕ Add Trade", command=lambda: self._open_add_trade_from_holding(iid))
            menu.add_separator()
            menu.add_command(label="Copy Selected", command=self._copy_selected)
            menu.add_command(label="Copy All (Visible)", command=self._copy_all)
            menu.add_separator()
            menu.add_command(label="Delete", command=self._delete_selected_holding)
            
            # Display menu
            menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"Context menu error: {e}")

    def _open_add_trade_from_holding(self, iid: str) -> None:
        """Open a quick Add Trade popup pre-filled with the holding's symbol and broker."""
        import threading
        from ui_utils import center_window

        meta = self._row_meta.get(iid, {})
        try:
            values = self.tree.item(iid, "values") or ()
            symbol = str(meta.get("symbol") or (values[1] if len(values) > 1 else "")).strip()
        except Exception:
            symbol = ""
        broker = str(meta.get("broker") or "").strip()
        stock_name = str(meta.get("stock_name") or "").strip()

        win = tk.Toplevel(self)
        win.title("➕ Add Trade")
        win.configure(bg=ModernStyle.BG_PRIMARY)
        win.resizable(False, False)
        win.geometry("600x480")
        try:
            win.transient(self.winfo_toplevel())
            win.grab_set()
        except Exception:
            pass
        try:
            center_window(win, parent=self.winfo_toplevel())
        except Exception:
            pass

        # ── Header ──────────────────────────────────────────────────────────────
        tk.Frame(win, bg=ModernStyle.SUCCESS, height=4).pack(fill="x")

        header = tk.Frame(win, bg=ModernStyle.BG_PRIMARY)
        header.pack(fill="x", padx=28, pady=(16, 0))

        tk.Label(
            header, text=symbol,
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.ACCENT_PRIMARY,
            font=(ModernStyle.FONT_FAMILY, 28, "bold"),
        ).pack(anchor="w")

        self._add_h_stock_name_lbl = tk.Label(
            header, text=stock_name if stock_name else "",
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_SECONDARY,
            font=(ModernStyle.FONT_FAMILY, 12),
        )
        self._add_h_stock_name_lbl.pack(anchor="w", pady=(0, 8))

        tk.Label(
            header, text="➕  Quick Add Trade",
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_SECONDARY,
            font=(ModernStyle.FONT_FAMILY, 11),
        ).pack(anchor="w", pady=(0, 10))

        tk.Frame(win, bg=ModernStyle.BORDER_COLOR, height=1).pack(fill="x", padx=20)

        # ── Form ────────────────────────────────────────────────────────────────
        card = tk.Frame(win, bg=ModernStyle.BG_PRIMARY)
        card.pack(fill="both", expand=True, padx=24, pady=12)

        form = tk.Frame(card, bg=ModernStyle.BG_PRIMARY)
        form.pack(fill="x")
        for i in range(2):
            form.grid_columnconfigure(i, weight=1)

        BG = ModernStyle.BG_PRIMARY
        BORDER = "#E2E8F0"
        FG = "#0F172A"

        def _label(text, r, c):
            tk.Label(form, text=text, bg=BG, fg=ModernStyle.TEXT_SECONDARY,
                     font=(ModernStyle.FONT_FAMILY, 11, "bold")).grid(
                row=r * 2, column=c, sticky="w",
                pady=(8 if r > 0 else 0, 4), padx=(0, 12 if c == 0 else 0))

        def _entry(r, c, var, *, is_date=False):
            from views.base_view import _create_date_input
            wrap = tk.Frame(form, bg=BORDER, padx=1, pady=1)
            wrap.grid(row=r * 2 + 1, column=c, sticky="ew",
                      pady=(0, 4), padx=(0, 12 if c == 0 else 0))
            if is_date:
                ent = _create_date_input(wrap, var)
                ent.pack(fill="both", expand=True)
            else:
                ent = tk.Entry(wrap, textvariable=var, bg="#F8FAFC", fg=FG,
                               font=(ModernStyle.FONT_FAMILY, 13), relief=tk.FLAT,
                               insertbackground=ModernStyle.SUCCESS, highlightthickness=0)
                def _fi(e, w=wrap, i=ent): w.configure(bg=ModernStyle.SUCCESS); i.configure(bg="#FFFFFF")
                def _fo(e, w=wrap, i=ent): w.configure(bg=BORDER); i.configure(bg="#F8FAFC")
                ent.bind("<FocusIn>", _fi)
                ent.bind("<FocusOut>", _fo)
                ent.pack(fill="both", expand=True, ipady=6, padx=8)
            return ent

        from datetime import datetime as _DT
        _add_broker_var  = tk.StringVar(value=broker)
        _add_date_var    = tk.StringVar(value=_DT.now().strftime("%Y-%m-%d"))
        _add_symbol_var  = tk.StringVar(value=symbol)
        _add_type_var    = tk.StringVar(value="BUY")
        _add_qty_var     = tk.StringVar(value="")
        _add_price_var   = tk.StringVar(value="")
        _add_fee_var     = tk.StringVar(value="0.0")

        # Broker dropdown
        _label("👑  Broker", 0, 0)
        broker_wrap = tk.Frame(form, bg=BORDER, padx=1, pady=1)
        broker_wrap.grid(row=1, column=0, sticky="ew", pady=(0, 4), padx=(0, 12))
        try:
            import common.models.crud as _crud
            known_brokers = sorted(set(_crud.get_all_brokers()))
        except Exception:
            known_brokers = []
        if broker and broker not in known_brokers:
            known_brokers.insert(0, broker)
        ttk.Combobox(broker_wrap, textvariable=_add_broker_var,
                     values=known_brokers, font=(ModernStyle.FONT_FAMILY, 13),
                     state="normal").pack(fill="both", expand=True, ipady=4, padx=4)

        _label("📅  Date", 0, 1)
        _entry(0, 1, _add_date_var, is_date=True)

        _label("📊  Quantity", 1, 0)
        _entry(1, 0, _add_qty_var)
        _label("💰  Price (₹)", 1, 1)
        _entry(1, 1, _add_price_var)

        _label("💸  Fees (₹)", 2, 0)
        _entry(2, 0, _add_fee_var)

        # Trade type radio
        type_lbl_row = tk.Frame(form, bg=BG)
        type_lbl_row.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 4))
        tk.Label(type_lbl_row, text="🌲  Trade Type", bg=BG, fg=ModernStyle.TEXT_SECONDARY,
                 font=(ModernStyle.FONT_FAMILY, 11, "bold")).pack(side="left")
        type_row = tk.Frame(form, bg=BG)
        type_row.grid(row=6, column=0, columnspan=2, sticky="w")
        for val, color in [("BUY", "#059669"), ("SELL", "#DC2626")]:
            tk.Radiobutton(type_row, text=val, variable=_add_type_var, value=val,
                           bg=BG, fg=color, font=(ModernStyle.FONT_FAMILY, 13, "bold"),
                           selectcolor=BG, activebackground=BG).pack(side="left", padx=(0, 24))

        # ── Actions ─────────────────────────────────────────────────────────────
        tk.Frame(win, bg=ModernStyle.BORDER_COLOR, height=1).pack(fill="x", padx=24, pady=(4, 0))

        status_lbl = tk.Label(win, text="", bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_SECONDARY,
                              font=(ModernStyle.FONT_FAMILY, 10, "italic"), anchor="w")
        status_lbl.pack(anchor="w", padx=28, pady=(6, 4), fill="x")

        act = tk.Frame(win, bg=ModernStyle.BG_PRIMARY)
        act.pack(fill="x", padx=24, pady=(0, 16))

        def _save():
            try:
                b = _add_broker_var.get().strip()
                if not b: raise ValueError("Broker is required")
                from ui_utils import center_window as _cw
                from datetime import date as _date
                d_str = _add_date_var.get().strip()
                import datetime as _dt
                _dt.datetime.strptime(d_str, "%Y-%m-%d")  # validates format
                sym = _add_symbol_var.get().strip().upper()
                if not sym: raise ValueError("Symbol is required")
                t = _add_type_var.get().strip().upper()
                qty = float(_add_qty_var.get().replace(",", "") or 0)
                price = float(_add_price_var.get().replace(",", "").replace("₹", "") or 0)
                fee = float(_add_fee_var.get().replace(",", "").replace("₹", "") or 0)
                if qty <= 0: raise ValueError("Qty must be > 0")
                if price <= 0: raise ValueError("Price must be > 0")
            except Exception as ex:
                status_lbl.configure(text=str(ex), fg=ModernStyle.ERROR)
                return

            status_lbl.configure(text="Saving…", fg=ModernStyle.TEXT_SECONDARY)

            def _bg():
                err = None
                try:
                    import common.models.crud as _crud2
                    import uuid
                    trade_id = str(uuid.uuid4())[:8]
                    _crud2.add_trade(b, d_str, sym, t, qty, price, fee, trade_id)
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
                except Exception as ex2:
                    err = str(ex2)

                def _done():
                    if err:
                        status_lbl.configure(text=f"Error: {err}", fg=ModernStyle.ERROR)
                        return
                    try: win.destroy()
                    except Exception: pass
                    try: self.load_data()
                    except Exception: pass

                self.after(0, _done)

            threading.Thread(target=_bg, daemon=True).start()

        from ui_widgets import ModernButton as _MB
        _MB(act, text="✓ Add Trade", command=_save,
            bg=ModernStyle.SUCCESS, fg="#ffffff", canvas_bg=BG,
            width=150, height=40, radius=8, font=(ModernStyle.FONT_FAMILY, 12, "bold")
        ).pack(side="right")
        _MB(act, text="✕ Cancel", command=win.destroy,
            bg=ModernStyle.TEXT_TERTIARY, fg="#ffffff", canvas_bg=BG,
            width=110, height=40, radius=8, font=(ModernStyle.FONT_FAMILY, 12, "bold")
        ).pack(side="right", padx=(0, 10))

    def _edit_holding_properties(self, iid: str) -> None:
        """Edit holding properties: stock name, avg cost, and total fees."""
        try:
            meta = self._row_meta.get(iid, {})
            values = self.tree.item(iid, "values") or ()
            
            symbol = str(meta.get("symbol") or (values[1] if len(values) > 1 else "")).strip()
            broker = str(meta.get("broker") or "").strip()
            stock_name = str(values[2] if len(values) > 2 else "—").replace("—", "").strip()
            avg_cost = str(values[4] if len(values) > 4 else "0").replace("₹", "").replace(",", "").strip()
            total_fees = str(meta.get("total_fees") or "0").replace("₹", "").replace(",", "").strip()
            
            if not symbol or not broker:
                messagebox.showerror("Edit Holding", "Could not determine symbol/broker for selected row.")
                return
            
            # Create edit dialog using PremiumModal base class
            win = PremiumModal(self, title="Edit Holding", geometry="500x450", icon="✏️")
            
            # Add chips for context
            win.add_chip("📈", symbol, bg_color=ModernStyle.ACCENT_PRIMARY, fg_color=ModernStyle.SLATE_300)
            win.add_chip("🏦", broker, bg_color=ModernStyle.SLATE_800, fg_color=ModernStyle.SLATE_300)
            
            # Add top right close button manually to the top header
            tk.Button(
                win.inner_hdr, 
                text="✕", 
                command=win.destroy, 
                bg=ModernStyle.BG_PRIMARY, 
                fg=ModernStyle.ERROR, 
                font=(ModernStyle.FONT_FAMILY, 20, "bold"),
                bd=0,
                activebackground=ModernStyle.BG_PRIMARY,
                activeforeground=ModernStyle.SALMON,
                cursor="hand2"
            ).pack(side="right", anchor="ne", padx=(0, 10))
            
            form = win.content_frame
            form.grid_columnconfigure(0, weight=1)
            
            def _field(label: str, emoji: str, row: int, var: tk.StringVar, hint: str = ""):
                # Label row
                lrow = tk.Frame(form, bg=ModernStyle.SLATE_50)
                lrow.grid(row=row, column=0, sticky="w", pady=(0, 4))
                tk.Label(
                    lrow, text=emoji,
                    bg=ModernStyle.SLATE_50, fg=ModernStyle.ACCENT_PRIMARY,
                    font=(ModernStyle.FONT_FAMILY, 14)
                ).pack(side="left", padx=(0, 6))
                tk.Label(
                    lrow, text=label,
                    bg=ModernStyle.SLATE_50, fg=ModernStyle.SLATE_900,
                    font=(ModernStyle.FONT_FAMILY, 12, "bold")
                ).pack(side="left")
                if hint:
                    tk.Label(
                        lrow, text=hint,
                        bg=ModernStyle.SLATE_50, fg=ModernStyle.SLATE_400,
                        font=(ModernStyle.FONT_FAMILY, 10)
                    ).pack(side="left", padx=(6, 0))

                # Entry wrap with focus ring effect
                ent_wrap = tk.Frame(form, bg=ModernStyle.SLATE_300, padx=1, pady=1)
                ent_wrap.grid(row=row + 1, column=0, sticky="ew", pady=(0, 18))
                
                ent = tk.Entry(
                    ent_wrap,
                    textvariable=var,
                    bg=ModernStyle.BG_SECONDARY,
                    fg=ModernStyle.SLATE_900,
                    font=(ModernStyle.FONT_FAMILY, 14),
                    relief=tk.FLAT,
                    insertbackground=ModernStyle.ACCENT_PRIMARY,
                    highlightthickness=0
                )
                
                def _on_focus_in(e, wrap=ent_wrap, inner=ent):
                    wrap.configure(bg=ModernStyle.ACCENT_PRIMARY)
                    inner.configure(bg=ModernStyle.BG_SECONDARY)
                def _on_focus_out(e, wrap=ent_wrap, inner=ent):
                    wrap.configure(bg=ModernStyle.SLATE_300)
                    inner.configure(bg=ModernStyle.BG_SECONDARY)
                
                ent.bind("<FocusIn>", _on_focus_in)
                ent.bind("<FocusOut>", _on_focus_out)
                ent.pack(fill="both", expand=True, ipady=8, padx=12)
                return ent
            
            stock_name_var = tk.StringVar(value=stock_name)
            avg_cost_var = tk.StringVar(value=avg_cost)
            total_fees_var = tk.StringVar(value=total_fees)
            
            _field("Stock Name", "💠", 0, stock_name_var, "(optional)")
            _field("Avg Cost", "💎", 2, avg_cost_var, "(₹)")
            _field("Total Fees", "💙", 4, total_fees_var, "(₹)")
            
            # We use PremiumModal's actions_frame
            actions = win.actions_frame
            
            def _close():
                try:
                    win.destroy()
                except Exception:
                    pass
            
            def _save():
                try:
                    new_stock_name = (stock_name_var.get() or "").strip()
                    new_avg_cost = float(avg_cost_var.get() or "0")
                    new_total_fees = float(total_fees_var.get() or "0")
                    
                    if new_avg_cost < 0:
                        raise ValueError("Avg Cost cannot be negative")
                    if new_total_fees < 0:
                        raise ValueError("Total Fees cannot be negative")
                    
                    win.set_status("⏳ Saving…")
                    
                    def _bg():
                        err = None
                        try:
                            import common.models.crud as crud
                            from common.engine import rebuild_holdings
                            
                            crud.update_holding_properties(broker, symbol, new_stock_name, new_avg_cost, new_total_fees)
                            try:
                                rebuild_holdings()
                            except Exception:
                                pass
                            try:
                                self.data_cache.refresh_from_db()
                            except Exception:
                                pass
                            try:
                                if self.app_state is not None and hasattr(self.app_state, "data_cache"):
                                    self.app_state.data_cache.refresh_from_db()
                            except Exception:
                                pass
                        except Exception as e:
                            err = str(e)
                        
                        def _done():
                            if err:
                                win.set_status(f"❌ Save failed: {err}", is_error=True)
                                return
                            try:
                                win.destroy()
                            except Exception:
                                pass
                            self.load_data()
                        
                        self.after(0, _done)
                    
                    threading.Thread(target=_bg, daemon=True).start()
                except Exception as e:
                    win.set_status(str(e), is_error=True)
            
            ModernButton(actions, text="✕  Cancel", command=_close, bg=ModernStyle.SALMON, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg=ModernStyle.SLATE_50, width=130, height=38).pack(side="right")
            ModernButton(actions, text="✔  Update", command=_save, bg=ModernStyle.ACCENT_PRIMARY, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg=ModernStyle.SLATE_50, width=130, height=38).pack(side="right", padx=(0, 10))
        except Exception as e:
            messagebox.showerror("Edit Holding", f"Error: {e}")

    def _open_drilldown_selected(self) -> None:
        try:
            sel = list(self.tree.selection() or [])
        except Exception:
            sel = []
        if not sel:
            messagebox.showinfo("Drilldown", "Select a holding row first.")
            return

        iid = sel[0]
        meta = self._row_meta.get(iid, {})
        # Fallback: read symbol from displayed table
        try:
            values = self.tree.item(iid, "values")
            symbol = str(values[1]) if len(values) > 1 else ""
        except Exception:
            symbol = ""

        symbol = (meta.get("symbol") or symbol or "").strip()
        if not symbol or symbol == "—":
            messagebox.showerror("Drilldown", "Could not determine symbol for selected row.")
            return

        broker = (meta.get("broker") or "").strip()
        stock_name_val = meta.get("stock_name")
        stock_name = stock_name_val.strip() if isinstance(stock_name_val, str) else ""

        top = PremiumModal(self, title="Trade Drilldown", geometry="980x640", icon="📊")

        if stock_name:
            top.title_lbl.config(text=f"{stock_name}", fg=ModernStyle.BRAND_GOLD, font=(ModernStyle.FONT_FAMILY, 24, "bold"))
        else:
            top.title_lbl.config(text=f"{symbol} Drilldown")

        # Add context chips
        top.add_chip("📈", symbol, bg_color=ModernStyle.ACCENT_PRIMARY, fg_color=ModernStyle.SLATE_300)
        top.add_chip("🏦", broker if broker else "All brokers", bg_color=ModernStyle.SLATE_800, fg_color=ModernStyle.SLATE_300)

        # Summary line displayed inline as chips
        try:
            qty = float(meta.get("qty", 0.0) or 0.0)
            avg = float(meta.get("avg_price", 0.0) or 0.0)
            mkt = float(meta.get("market_price", 0.0) or 0.0)
            pnl = float(meta.get("running_pnl", 0.0) or 0.0)
            fees = float(meta.get("total_fees", 0.0) or 0.0)
            
            pnl_color = ModernStyle.SUCCESS if pnl >= 0 else ModernStyle.ERROR
            
            # Format nicely. Added alongside chips to stay inline top
            top.add_chip("📊", f"Qty: {qty:g}", bg_color=ModernStyle.BG_PRIMARY, fg_color=ModernStyle.TEXT_PRIMARY)
            top.add_chip("💵", f"Avg: ₹{avg:,.2f}", bg_color=ModernStyle.BG_PRIMARY, fg_color=ModernStyle.TEXT_PRIMARY)
            top.add_chip("💰", f"Mkt: ₹{mkt:,.2f}", bg_color=ModernStyle.BG_PRIMARY, fg_color=ModernStyle.TEXT_PRIMARY)
            top.add_chip("📉", f"Fees: ₹{fees:,.2f}", bg_color=ModernStyle.BG_PRIMARY, fg_color=ModernStyle.WARNING)
            top.add_chip("🏆", f"P&L: ₹{pnl:,.2f}", bg_color=ModernStyle.BG_PRIMARY, fg_color=pnl_color)
        except Exception:
            pass

        # Add top right close button manually to the top header
        tk.Button(
            top.inner_hdr, 
            text="✕", 
            command=top.destroy, 
            bg=ModernStyle.BG_PRIMARY, 
            fg=ModernStyle.ERROR, 
            font=(ModernStyle.FONT_FAMILY, 20, "bold"),
            bd=0,
            activebackground=ModernStyle.BG_PRIMARY,
            activeforeground=ModernStyle.SALMON,
            cursor="hand2"
        ).pack(side="right", anchor="ne", padx=(0, 10))

        body = top.content_frame

        act = top.actions_frame

        # Remove horizontal scrollbar by completely overriding the old layout 
        # and re-packing the Treeview directly in the window's constraints.
        
        # Cleanup previously generated bottom close button from other UI changes if it still existed
        for widget in act.winfo_children():
            widget.destroy()
        
        # Hide the bottom actions frame since we don't need it now
        act.pack_forget()

        table = tk.Frame(body, bg=ModernStyle.BG_SECONDARY)
        table.pack(fill="both", expand=True)
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)

        cols = ("#", "Date", "Trade ID", "Type", "Qty", "Price ₹", "Fees ₹", "Run Qty", "AvgCost ₹", "Running PnL ₹", "Broker")
        trade_tv = ttk.Treeview(table, columns=cols, show="headings", height=16)
        widths = [40, 90, 90, 60, 70, 90, 80, 80, 95, 100, 100]
        for c, w in zip(cols, widths):
            trade_tv.heading(c, text=c)
            trade_tv.column(c, width=w, anchor="w", stretch=True)

        vsb = ttk.Scrollbar(table, orient="vertical", command=trade_tv.yview)
        trade_tv.configure(yscrollcommand=vsb.set)

        trade_tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        
        # Add right click copy menu to the popup table
        add_treeview_copy_menu(trade_tv)

        # Load trades from cache (in background)
        def _load():
            try:
                # Prefer app_state cache if present to stay consistent with other views
                cache = None
                if self.app_state is not None and hasattr(self.app_state, "data_cache"):
                    cache = self.app_state.data_cache
                else:
                    cache = self.data_cache

                f = TradeHistoryFilters(
                    broker=(broker if broker else "All"),
                    symbol_like=symbol,
                    trade_type="All",
                    start_date=None,
                    end_date=None,
                )
                df, _sum = cache.get_tradehistory_filtered(f)
            except Exception:
                df = pd.DataFrame()

            def _apply():
                for it in trade_tv.get_children():
                    trade_tv.delete(it)
                if df is None or df.empty:
                    return
                for i, r in enumerate(df.itertuples(index=False)):
                    rtype = str(getattr(r, "type", "")).upper()
                    qty = float(getattr(r, "qty", 0.0) or 0.0)
                    price = float(getattr(r, "price", 0.0) or 0.0)
                    fee = float(getattr(r, "fee", 0.0) or 0.0)
                    run_qty = float(getattr(r, "run_qty", 0.0) or 0.0)
                    avg_cost = float(getattr(r, "avg_cost", 0.0) or 0.0)
                    rpnl = float(getattr(r, "running_pnl", 0.0) or 0.0)
                    # Show Running PnL only for SELL trades
                    rpnl_disp = f"₹{rpnl:,.2f}" if rtype in {"SELL", "S"} else "—"
                    vals = (
                        str(i + 1),
                        str(getattr(r, "date", "")),
                        str(getattr(r, "trade_id", "")),
                        rtype,
                        f"{qty:g}",
                        f"₹{price:,.2f}",
                        f"₹{fee:,.2f}",
                        f"{run_qty:g}",
                        f"₹{avg_cost:,.2f}",
                        rpnl_disp,
                        str(getattr(r, "broker", "")),
                    )
                    trade_tv.insert("", "end", values=vals)

            self.after(0, _apply)

        threading.Thread(target=_load, daemon=True).start()

    def _delete_selected_holding(self) -> None:
        try:
            sel = list(self.tree.selection() or [])
        except Exception:
            sel = []
        if not sel:
            messagebox.showinfo("Delete Holding", "Select a holding row first.")
            return

        iid = sel[0]
        meta = self._row_meta.get(iid, {})
        symbol = str(meta.get("symbol") or "").strip()
        broker = str(meta.get("broker") or "").strip()

        if not symbol:
            try:
                values = self.tree.item(iid, "values")
                symbol = str(values[1]) if len(values) > 1 else ""
            except Exception:
                symbol = ""

        if not symbol:
            messagebox.showerror("Delete Holding", "Could not determine selected symbol.")
            return
        if not broker:
            messagebox.showerror("Delete Holding", "Could not determine broker for selected holding.")
            return

        if not messagebox.askyesno(
            "Delete Holding",
            f"Delete holding {symbol} ({broker}) and ALL its underlying trades?\n\nThis cannot be undone.",
        ):
            return

        def _bg():
            try:
                crud.delete_holding_and_trades(broker, symbol)
            except Exception as e:
                err = str(e)
                self.after(0, lambda e=err: messagebox.showerror("Delete Holding", f"Failed to delete: {e}"))
                return

            try:
                from common.engine import rebuild_holdings
                rebuild_holdings()
            except Exception:
                pass

            try:
                self.data_cache.refresh_from_db()
            except Exception:
                pass
            try:
                if self.app_state is not None and hasattr(self.app_state, "data_cache"):
                    self.app_state.data_cache.refresh_from_db()
            except Exception:
                pass

            self.after(0, self.refresh)

        threading.Thread(target=_bg, daemon=True).start()
    
    def _load_brokers(self):
        """Load broker list in background."""
        try:
            brokers = ["All"]
            with db_session() as conn:
                result = conn.execute("SELECT DISTINCT broker FROM holdings WHERE broker IS NOT NULL ORDER BY broker")
                brokers.extend([row[0] for row in result.fetchall()])
            
            # Update combo box
            if hasattr(self, 'broker_combo'):
                self.after(0, lambda: self.broker_combo.configure(values=brokers))
        except Exception as e:
            print(f"Error loading brokers: {e}")
    
    def _on_symbol_search(self, event=None):
        """Handle symbol search with debouncing."""
        if self._search_timer:
            self.after_cancel(self._search_timer)
        
        # Debounce: wait 200ms before searching
        self._search_timer = self.after(200, self.on_filter_change)
    
    def on_filter_change(self):
        """Handle filter changes."""
        threading.Thread(target=self.load_data, daemon=True).start()
    
    def load_data(self):
        """Load and display holdings data."""
        try:
            # Always refresh the cache from DB so we pick up any changes from
            # rebuild_holdings() that ran in a background thread (e.g. after bulk import).
            try:
                cache = None
                if self.app_state is not None and hasattr(self.app_state, "data_cache"):
                    cache = self.app_state.data_cache
                else:
                    cache = self.data_cache
                cache.refresh_from_db()
                # Keep both caches in sync
                self.data_cache = cache
            except Exception:
                pass

            # Get filter values
            broker = self.broker_var.get() if hasattr(self, 'broker_var') else "All"
            symbol = self.symbol_entry.get_value() if hasattr(self, 'symbol_entry') else ""
            signal = self.signal_var.get() if hasattr(self, 'signal_var') else "All"
            exclude_zero = bool(self.exclude_zero_qty_var.get()) if hasattr(self, 'exclude_zero_qty_var') else False
            
            # Query cache
            filters = HoldingsFilters(
                broker=broker or "All",
                symbol_like=symbol.upper(),
                iv_signal=signal or "All",
                exclude_zero_qty=exclude_zero
            )
            
            df, summary = self.data_cache.get_holdings_filtered(filters)
            self.current_df = df
            
            # Update UI in main thread
            self.after(0, lambda: self._update_display(df, summary))
        
        except Exception as e:
            print(f"Error loading data: {e}")
    
    def _update_display(self, df: pd.DataFrame, summary: dict):
        """Update table and stats display."""
        self._row_meta = {}
        # Clear table
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Update stats
        self.stats_labels["count"].config(text=f"{len(df)}")
        self.stats_labels["invested"].config(text=f"₹ {float(summary.get('invested', 0)):,.0f}")
        self.stats_labels["current"].config(text=f"₹ {float(summary.get('current', 0)):,.0f}")
        
        pnl = float(summary.get('pnl', 0))
        pnl_color = ModernStyle.SUCCESS if pnl >= 0 else ModernStyle.ERROR
        self.stats_labels["pnl"].config(text=f"₹ {pnl:,.0f}", fg=pnl_color)
        
        try:
            total_fees = float(df.get("total_fees", pd.Series(dtype=float)).sum()) if not df.empty else 0.0
            self.stats_labels["fees"].config(text=f"₹ {total_fees:,.0f}")
        except Exception:
            self.stats_labels["fees"].config(text="₹ 0")
        
        # Precompute total current value for Weight%
        try:
            total_val = float(df.get("current_value", pd.Series(dtype=float)).sum()) if not df.empty else 0.0
        except Exception:
            total_val = 0.0

        # Populate table (match Flet computations)
        for idx, row in enumerate(df.itertuples(index=False)):
            qty = float(getattr(row, 'qty', 0) or 0)
            avg_price = float(getattr(row, 'avg_price', 0) or 0)
            mkt_price = float(getattr(row, 'market_price', 0) or 0)
            prev_close = float(getattr(row, 'previous_close', 0) or 0)
            running_pnl = float(getattr(row, 'running_pnl', 0) or 0)
            total_fees = float(getattr(row, 'total_fees', 0) or 0)
            xirr = float(getattr(row, 'xirr', 0) or 0)
            cagr = float(getattr(row, 'cagr', 0) or 0)
            current_value = float(getattr(row, 'current_value', 0) or 0)
            signal = getattr(row, 'action_signal', None) or getattr(row, 'iv_signal', None) or "N/A"

            # Daily change % — arrow prefix for sign clarity (no row color tag)
            if prev_close > 0 and mkt_price > 0:
                daily_pct = ((mkt_price - prev_close) / prev_close) * 100.0
                arrow = "🌲" if daily_pct >= 0 else "🔻"
                daily_disp = f"{arrow} {daily_pct:+.2f}%"
            else:
                daily_disp = "—"

            # Flash PnL — arrow prefix for sign clarity
            if mkt_price > 0:
                flash_pnl = (mkt_price - avg_price) * qty
                arrow = "🌲" if flash_pnl >= 0 else "🔻"
                flash_disp = f"{arrow} ₹{flash_pnl:,.0f}"
            else:
                flash_disp = "—"

            # Real PnL — arrow prefix
            rpnl_arrow = "🌲" if running_pnl >= 0 else "🔻"
            rpnl_disp = f"{rpnl_arrow} ₹{running_pnl:,.0f}"

            # Weight% (Flet: current_value / total_value)
            if total_val > 0:
                weight_pct = (current_value / total_val) * 100.0
                weight_disp = f"{weight_pct:.1f}%"
            else:
                weight_disp = "0.0%"

            xirr_disp = "—" if float(xirr) == -100 else (f"{xirr:.2f}%" if qty > 0 else "—")
            cagr_disp = f"{cagr:.2f}%" if qty > 0 else "—"

            # stock_name can be NaN (float) from pandas; normalize before slicing.
            stock_name = getattr(row, 'stock_name', '—')
            try:
                if stock_name is None or (isinstance(stock_name, float) and pd.isna(stock_name)):
                    stock_name = '—'
            except Exception:
                pass
            try:
                stock_name = str(stock_name)
            except Exception:
                stock_name = '—'
            stock_name = (stock_name or '—').strip() or '—'

            # Signal display — rich emoji badge per signal type
            sig_norm = str(signal).strip().upper()
            if sig_norm in {"ACCUMULATE", "BUY", "ADD"}:
                signal_disp = f"🌲 ACCUMULATE"
            elif sig_norm in {"REDUCE", "SELL", "TRIM"}:
                signal_disp = f"♦️ REDUCE"
            elif sig_norm in {"HOLD", "WAIT"}:
                signal_disp = f"🔸 HOLD"
            elif sig_norm in {"N/A", "NA", ""}:
                signal_disp = "🔘 N/A"
            else:
                signal_disp = f"🔹 {signal}"

            values = (
                str(idx + 1),
                getattr(row, 'symbol', '—'),
                stock_name[:28],
                f"{qty:,.0f}",
                f"₹{avg_price:,.2f}",
                f"₹{mkt_price:,.2f}" if mkt_price > 0 else "—",
                daily_disp,
                flash_disp,
                weight_disp,
                xirr_disp,
                cagr_disp,
                rpnl_disp,
                f"₹{total_fees:,.2f}",
                signal_disp,
            )

            # Only zebra stripe — no foreground color tags on rows
            stripe_tag = "even" if (idx % 2 == 0) else "odd"
            iid = self.tree.insert("", "end", values=values, tags=(stripe_tag,))
            try:
                self._row_meta[str(iid)] = {
                    "broker": getattr(row, "broker", ""),
                    "symbol": getattr(row, "symbol", ""),
                    "stock_name": getattr(row, "stock_name", ""),
                    "qty": qty,
                    "avg_price": avg_price,
                    "market_price": mkt_price,
                    "running_pnl": running_pnl,
                    "total_fees": total_fees,
                }
            except Exception:
                pass
    
    def refresh(self):
        self._data_loaded = False
        def _force_rebuild():
            try:
                from common.engine import rebuild_holdings, fetch_and_update_market_data
                from common.database import db_session
                try:
                    with db_session() as conn:
                        c = conn.cursor()
                        c.execute("SELECT DISTINCT symbol FROM trades")
                        symbols = [r[0] for r in c.fetchall() if r[0]]
                    if symbols:
                        fetch_and_update_market_data(symbols)
                except Exception as e:
                    print(f"Market fetch failed: {e}")

                rebuild_holdings()
            except Exception as e:
                print(f"Force rebuild failed: {e}")
            self.load_data()
        threading.Thread(target=_force_rebuild, daemon=True).start()

    def _clear_filters(self):
        try:
            self.broker_var.set("All")
        except Exception:
            pass
        try:
            self.signal_var.set("All")
        except Exception:
            pass
        try:
            if hasattr(self, "symbol_entry"):
                self.symbol_entry.delete(0, tk.END)
        except Exception:
            pass
        try:
            if hasattr(self, "exclude_zero_qty_var"):
                self.exclude_zero_qty_var.set(False)
        except Exception:
            pass
        self.on_filter_change()
    
    def on_show(self):
        """Called when view becomes visible."""
        self._is_active = True
        if not self._data_loaded:
            self.load_data()
    
    def on_hide(self):
        """Called when view becomes hidden."""
        self._is_active = False
