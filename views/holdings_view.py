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
from ui_widgets import ModernButton
from ui_utils import center_window


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
        header.pack(fill=tk.X, padx=20, pady=5)
        
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
        broker_pill = tk.Frame(filter_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground="#DBEAFE", highlightthickness=1)
        broker_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(broker_pill, text="🏦 Broker:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 14, "bold")).pack(side=tk.LEFT, padx=3, pady=3)
        self.broker_var = tk.StringVar(value="All")
        self.broker_combo = ttk.Combobox(broker_pill, textvariable=self.broker_var, values=["All"], state="readonly", width=16, font=(ModernStyle.FONT_FAMILY, 13))
        self.broker_combo.pack(side=tk.LEFT, padx=3, pady=3)
        self.broker_combo.bind("<<ComboboxSelected>>", lambda e: self.on_filter_change())
        
        # Symbol search with background pill
        symbol_pill = tk.Frame(filter_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground="#E9D5FF", highlightthickness=1)
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
        signal_pill = tk.Frame(filter_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground="#DCFCE7", highlightthickness=1)
        signal_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        tk.Label(signal_pill, text="📊 Signal:", bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_PRIMARY, font=(ModernStyle.FONT_FAMILY, 14, "bold")).pack(side=tk.LEFT, padx=3, pady=3)
        self.signal_var = tk.StringVar(value="All")
        signal_combo = ttk.Combobox(signal_pill, textvariable=self.signal_var, values=["All", "ACCUMULATE", "REDUCE", "N/A"], state="readonly", width=14, font=(ModernStyle.FONT_FAMILY, 14))
        signal_combo.pack(side=tk.LEFT, padx=3, pady=3)
        signal_combo.bind("<<ComboboxSelected>>", lambda e: self.on_filter_change())

        # Exclude zero qty with background pill
        exclude_pill = tk.Frame(filter_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground="#FEE2E2", highlightthickness=1)
        exclude_pill.pack(side=tk.LEFT, padx=3, pady=3, ipady=2, ipadx=4)
        self.exclude_zero_qty_var = tk.BooleanVar(value=False)
        exclude_chk = tk.Checkbutton(
            exclude_pill,
            text="🧪 Filter 0 Qty",
            variable=self.exclude_zero_qty_var,
            bg=ModernStyle.BG_SECONDARY,
            fg=ModernStyle.TEXT_PRIMARY,
            activebackground=ModernStyle.BG_SECONDARY,
            activeforeground=ModernStyle.TEXT_PRIMARY,
            selectcolor=ModernStyle.BG_SECONDARY,
            font=(ModernStyle.FONT_FAMILY, 14,"bold"),
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
            ("Holdings", "count", ModernStyle.ACCENT_PRIMARY, "#DBEAFE"),        # Blue
            ("Invested", "invested", ModernStyle.ACCENT_SECONDARY, "#DCFCE7"),  # Green
            ("Current", "current", "#0891B2", "#CFFAFE"),                        # Cyan
            ("P&L", "pnl", ModernStyle.ACCENT_TERTIARY, "#FEF3C7"),              # Amber
            ("Total Fees", "fees", ModernStyle.ERROR, "#FEE2E2"),                # Red
        ]
        
        for label, key, color, pill_bg in stat_configs:
            stat_pill = tk.Frame(stats_frame, bg=ModernStyle.BG_SECONDARY, highlightbackground=pill_bg, highlightthickness=2)
            stat_pill.pack(side=tk.LEFT, padx=3, pady=3, expand=True, fill=tk.X, ipady=3, ipadx=4)
            
            tk.Label(stat_pill, text=label, bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_SECONDARY, font=(ModernStyle.FONT_FAMILY, 12, "bold")).pack()
            
            val_label = tk.Label(stat_pill, text="—", bg=ModernStyle.BG_SECONDARY, fg=color, font=(ModernStyle.FONT_FAMILY, 16, "bold"))
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
        widths = [40, 90, 170, 70, 95, 95, 85, 110, 75, 70, 70, 105, 85, 90]
        for col, width in zip(columns, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width)

        # Alternating rows - clean zebra stripe, no per-row color overrides
        try:
            style = ttk.Style()
            style.configure("Holdings.Treeview", font=(ModernStyle.FONT_FAMILY, 12), rowheight=30)
            # Header: dark slate — clearly distinct from the blue row-selection colour
            style.configure(
                "Holdings.Treeview.Heading",
                font=(ModernStyle.FONT_FAMILY, 13, "bold"),
                background="#1E293B",
                foreground="#FFFFFF",
                relief="flat",
            )
            style.map(
                "Holdings.Treeview.Heading",
                background=[("active", "#334155")],
                foreground=[("active", "#FFFFFF")],
            )
            self.tree.configure(style="Holdings.Treeview")

            # Only background zebra stripes — no foreground color tags on rows
            self.tree.tag_configure("odd",  background="#FFFFFF")  # pure white
            self.tree.tag_configure("even", background="#F8FAFC")  # ultra faint slate
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
            lines.append("\t".join(str(v) for v in vals))
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
            menu.add_command(label="Copy", command=self._copy_selected)
            menu.add_separator()
            menu.add_command(label="Delete", command=self._delete_selected_holding)
            
            # Display menu
            menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"Context menu error: {e}")

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
            
            # Create edit dialog
            win = tk.Toplevel(self)
            win.title(f"Edit Holding - {symbol}")
            win.configure(bg="#0F172A")
            win.resizable(False, False)
            win.geometry("500x520")
            try:
                win.transient(self.winfo_toplevel())
                win.grab_set()
            except Exception:
                pass
            
            try:
                center_window(win, parent=self.winfo_toplevel())
            except Exception:
                pass
            
            # ── Premium header with accent gradient bar ──
            header = tk.Frame(win, bg="#0F172A")
            header.pack(fill="x")

            # Thin accent gradient bar at very top
            tk.Frame(header, bg=ModernStyle.ACCENT_PRIMARY, height=3).pack(fill="x")

            inner_hdr = tk.Frame(header, bg="#0F172A")
            inner_hdr.pack(fill="x", padx=28, pady=(18, 16))

            # Left block: icon + title
            tk.Label(
                inner_hdr, text="✏️", bg="#0F172A", fg="#F8FAFC",
                font=(ModernStyle.FONT_FAMILY, 26)
            ).pack(side="left", padx=(0, 12))

            title_col = tk.Frame(inner_hdr, bg="#0F172A")
            title_col.pack(side="left", fill="y")
            tk.Label(
                title_col, text="Edit Holding",
                bg="#0F172A", fg="#F8FAFC",
                font=(ModernStyle.FONT_FAMILY, 20, "bold")
            ).pack(anchor="w")

            # Symbol + Broker as chip badges
            chips_row = tk.Frame(title_col, bg="#0F172A")
            chips_row.pack(anchor="w", pady=(4, 0))
            for chip_text, chip_bg in [(f"📈 {symbol}", "#1E3A8A"), (f"🏦 {broker}", "#1E293B")]:
                chip = tk.Frame(chips_row, bg=chip_bg)
                chip.pack(side="left", padx=(0, 6))
                tk.Label(
                    chip, text=chip_text, bg=chip_bg, fg="#94A3B8",
                    font=(ModernStyle.FONT_FAMILY, 10, "bold"),
                    padx=8, pady=2
                ).pack()
            
            # ── scrolling content card ──
            card = tk.Frame(win, bg="#F8FAFC", highlightbackground="#E2E8F0", highlightthickness=1)
            card.pack(fill="both", expand=True, padx=20, pady=(0, 20))

            # Accent separator under header
            tk.Frame(card, bg=ModernStyle.ACCENT_PRIMARY, height=2).pack(fill="x")
            
            form = tk.Frame(card, bg="#F8FAFC")
            form.pack(fill="x", padx=24, pady=(20, 8))
            form.grid_columnconfigure(0, weight=1)
            
            def _field(label: str, emoji: str, row: int, var: tk.StringVar, hint: str = ""):
                # Label row
                lrow = tk.Frame(form, bg="#F8FAFC")
                lrow.grid(row=row, column=0, sticky="w", pady=(0, 4))
                tk.Label(
                    lrow, text=emoji,
                    bg="#F8FAFC", fg=ModernStyle.ACCENT_PRIMARY,
                    font=(ModernStyle.FONT_FAMILY, 14)
                ).pack(side="left", padx=(0, 6))
                tk.Label(
                    lrow, text=label,
                    bg="#F8FAFC", fg="#0F172A",
                    font=(ModernStyle.FONT_FAMILY, 12, "bold")
                ).pack(side="left")
                if hint:
                    tk.Label(
                        lrow, text=hint,
                        bg="#F8FAFC", fg="#94A3B8",
                        font=(ModernStyle.FONT_FAMILY, 10)
                    ).pack(side="left", padx=(6, 0))

                # Entry wrap with focus ring effect
                ent_wrap = tk.Frame(form, bg="#CBD5E1", padx=1, pady=1)
                ent_wrap.grid(row=row + 1, column=0, sticky="ew", pady=(0, 18))
                
                ent = tk.Entry(
                    ent_wrap,
                    textvariable=var,
                    bg="#FFFFFF",
                    fg="#0F172A",
                    font=(ModernStyle.FONT_FAMILY, 14),
                    relief=tk.FLAT,
                    insertbackground=ModernStyle.ACCENT_PRIMARY,
                    highlightthickness=0
                )
                
                def _on_focus_in(e, wrap=ent_wrap, inner=ent):
                    wrap.configure(bg=ModernStyle.ACCENT_PRIMARY)
                    inner.configure(bg="#FFFFFF")
                def _on_focus_out(e, wrap=ent_wrap, inner=ent):
                    wrap.configure(bg="#CBD5E1")
                    inner.configure(bg="#FFFFFF")
                
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
            
            # Status bar
            status = tk.Label(
                card, text="", bg="#F8FAFC", fg="#64748B",
                font=(ModernStyle.FONT_FAMILY, 10, "italic"), anchor="w"
            )
            status.pack(anchor="w", padx=24, pady=(0, 8), fill="x")
            
            # Divider before buttons
            tk.Frame(card, bg="#E2E8F0", height=1).pack(fill="x", padx=20, pady=(0, 12))

            # Action buttons
            actions = tk.Frame(card, bg="#F8FAFC")
            actions.pack(fill="x", padx=24, pady=(0, 20))
            
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
                    
                    status.configure(text="⏳ Saving…", fg=ModernStyle.TEXT_TERTIARY)
                    
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
                        except Exception as e:
                            err = str(e)
                        
                        def _done():
                            if err:
                                status.configure(text=f"❌ Save failed: {err}", fg=ModernStyle.ERROR)
                                return
                            try:
                                win.destroy()
                            except Exception:
                                pass
                            self.load_data()
                        
                        self.after(0, _done)
                    
                    threading.Thread(target=_bg, daemon=True).start()
                except Exception as e:
                    status.configure(text=str(e), fg=ModernStyle.ERROR)
            
            ModernButton(actions, text="✕  Cancel", command=_close, bg=ModernStyle.SALMON, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg="#F8FAFC", width=130, height=38).pack(side="right")
            ModernButton(actions, text="✔  Update", command=_save, bg=ModernStyle.ACCENT_PRIMARY, fg=ModernStyle.TEXT_ON_ACCENT, canvas_bg="#F8FAFC", width=130, height=38).pack(side="right", padx=(0, 10))
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

        top = tk.Toplevel(self)
        top.title(f"Trade Drilldown - {symbol}")
        top.configure(bg=ModernStyle.BG_PRIMARY)
        top.geometry("980x560")

        try:
            top.transient(self.winfo_toplevel())
        except Exception:
            pass
        try:
            center_window(top, parent=self.winfo_toplevel())
        except Exception:
            pass

        hdr = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        hdr.pack(fill="x", padx=16, pady=14)
        title_row = tk.Frame(hdr, bg=ModernStyle.BG_PRIMARY)
        title_row.pack(fill="x")
        title = f"{symbol}" + (f"  •  {stock_name}" if stock_name else "")
        tk.Label(title_row, text=title, fg=ModernStyle.TEXT_PRIMARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_TITLE).pack(side="left", anchor="w")
        sub = broker if broker else "All brokers"
        tk.Label(hdr, text=f"Trades for: {sub}", fg=ModernStyle.TEXT_SECONDARY, bg=ModernStyle.BG_PRIMARY, font=ModernStyle.FONT_BODY).pack(anchor="w")

        # Summary line from current holding
        try:
            qty = float(meta.get("qty", 0.0) or 0.0)
            avg = float(meta.get("avg_price", 0.0) or 0.0)
            mkt = float(meta.get("market_price", 0.0) or 0.0)
            pnl = float(meta.get("running_pnl", 0.0) or 0.0)
            fees = float(meta.get("total_fees", 0.0) or 0.0)
            tk.Label(
                hdr,
                text=f"Qty {qty:g}  •  Avg ₹{avg:,.2f}  •  Mkt ₹{mkt:,.2f}  •  P&L ₹{pnl:,.2f}  •  Fees ₹{fees:,.2f}",
                fg=ModernStyle.TEXT_TERTIARY,
                bg=ModernStyle.BG_PRIMARY,
                font=ModernStyle.FONT_SMALL,
            ).pack(anchor="w", pady=(4, 0))
        except Exception:
            pass

        body = tk.Frame(top, bg=ModernStyle.BG_PRIMARY)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Table actions
        act = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        act.pack(fill="x", pady=(0, 8))
        ModernButton(
            act,
            text="Copy Trades",
            command=lambda: self._copy_treeview(trade_tv),
            bg=ModernStyle.ACCENT_PRIMARY,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=130,
            height=36,
        ).pack(side="left")

        ModernButton(
            act,
            text="Close",
            command=lambda: top.destroy(),
            bg=ModernStyle.SALMON,
            fg=ModernStyle.TEXT_ON_ACCENT,
            canvas_bg=ModernStyle.BG_PRIMARY,
            width=92,
            height=36,
        ).pack(side="right")

        table = tk.Frame(body, bg=ModernStyle.BG_PRIMARY)
        table.pack(fill="both", expand=True)

        cols = ("Date", "Trade ID", "Type", "Qty", "Price ₹", "Fees ₹", "Run Qty", "AvgCost ₹", "Running PnL ₹", "Broker")
        trade_tv = ttk.Treeview(table, columns=cols, show="headings", height=16)
        widths = [100, 90, 60, 70, 90, 80, 80, 95, 120, 120]
        for c, w in zip(cols, widths):
            trade_tv.heading(c, text=c)
            trade_tv.column(c, width=w, anchor="w")

        vsb = ttk.Scrollbar(table, orient="vertical", command=trade_tv.yview)
        hsb = ttk.Scrollbar(table, orient="horizontal", command=trade_tv.xview)
        trade_tv.configure(yscroll=vsb.set, xscroll=hsb.set)
        trade_tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)

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

    def _copy_treeview(self, tv: ttk.Treeview) -> None:
        try:
            cols = list(tv["columns"])
            lines = ["\t".join(cols)]
            for iid in tv.get_children():
                vals = tv.item(iid, "values")
                lines.append("\t".join(str(v) for v in vals))
            text = "\n".join(lines)
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Drilldown", "Copied trades to clipboard.")
        except Exception as e:
            messagebox.showerror("Drilldown", f"Failed to copy: {e}")

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
        self.load_data()

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
