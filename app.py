"""
Fantasy Golf Pick 6 Tool — Windows GUI
========================================
Desktop app for PrizePicks bankroll management, EV calculation
(2-6 picks with standard/golf/custom multipliers), and DataGolf analysis.

Usage: python app.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
import sys
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DATAGOLF_API_KEY, STARTING_BANKROLL, KELLY_FRACTION,
    BREAKEVEN_RATES, PRIZEPICKS_PAYOUTS_STANDARD, PRIZEPICKS_PAYOUTS_GOLF,
    SESSION_STOP_LOSS, MAX_DRAWDOWN_PCT, WEEKLY_LOSS_LIMIT, MIN_BANKROLL_FLOOR
)
from datagolf_client import DataGolfClient
from prizepicks_ev import (
    calculate_ev, get_payout_table,
    find_breakeven_prob, ev_sensitivity_table,
)
from bankroll_manager import BankrollManager


# =============================================================================
# Color Scheme
# =============================================================================
C = {
    "bg": "#1a1f2e", "card": "#232a3b", "input": "#2d3548",
    "header": "#0f1320", "green": "#00d26a", "red": "#ff4757",
    "gold": "#ffc312", "blue": "#4da6ff", "text": "#e8eaf0",
    "text2": "#8892a6", "muted": "#5a6478", "border": "#2d3548",
    "warn": "#ffa502",
}


class FantasyGolfApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("⛳ Fantasy Golf Pick 6 Tool")
        self.geometry("1150x780")
        self.minsize(950, 650)
        self.configure(bg=C["bg"])

        self.bm = BankrollManager()
        self.dg = DataGolfClient()
        self._setup_styles()
        self._build_ui()
        self._refresh_bankroll_display()

    # =========================================================================
    # Styles
    # =========================================================================
    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TNotebook", background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=C["card"], foreground=C["text2"],
                     padding=[16, 8], font=("Segoe UI", 10))
        s.map("TNotebook.Tab", background=[("selected", C["bg"])],
               foreground=[("selected", C["green"])])
        s.configure("Dark.Treeview", background=C["card"], foreground=C["text"],
                     fieldbackground=C["card"], font=("Consolas", 9), rowheight=26)
        s.configure("Dark.Treeview.Heading", background=C["input"],
                     foreground=C["text2"], font=("Segoe UI", 9, "bold"))
        s.map("Dark.Treeview", background=[("selected", C["input"])],
               foreground=[("selected", C["blue"])])

    def _btn(self, parent, text, command, accent=True, **kw):
        """Create a styled button."""
        bg = C["green"] if accent else C["input"]
        fg = "#000000" if accent else C["text"]
        hover = "#00b85c" if accent else C["border"]
        btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=hover, activeforeground=fg,
                         font=("Segoe UI", 9 if not accent else 10,
                               "bold" if accent else "normal"),
                         relief="flat", cursor="hand2", padx=14, pady=6, **kw)
        return btn

    def _entry(self, parent, width=12, default=""):
        """Create a styled entry."""
        e = tk.Entry(parent, bg=C["input"], fg=C["text"],
                      insertbackground=C["text"], font=("Consolas", 11),
                      width=width, relief="flat", bd=4)
        if default:
            e.insert(0, default)
        return e

    def _label(self, parent, text, size=9, color=None, bold=False, bg=None):
        """Create a styled label."""
        return tk.Label(parent, text=text, bg=bg or C["card"],
                         fg=color or C["text2"],
                         font=("Segoe UI", size, "bold" if bold else "normal"))

    # =========================================================================
    # UI
    # =========================================================================
    def _build_ui(self):
        # Banner
        banner = tk.Frame(self, bg=C["header"], height=50)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text="⛳  FANTASY GOLF PICK 6 TOOL", bg=C["header"],
                 fg=C["green"], font=("Segoe UI", 13, "bold")).pack(side="left", padx=20, pady=10)
        self.bankroll_lbl = tk.Label(banner, text="", bg=C["header"], fg=C["gold"],
                                      font=("Consolas", 12, "bold"))
        self.bankroll_lbl.pack(side="right", padx=20, pady=10)
        self.sl_indicator = tk.Label(banner, text="", bg=C["header"], font=("Segoe UI", 10))
        self.sl_indicator.pack(side="right", padx=10, pady=10)

        # Tabs
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self._build_dashboard()
        self._build_ev_tab()
        self._build_kelly_tab()
        self._build_entries_tab()
        self._build_datagolf_tab()
        self._build_settings_tab()

    # -------------------------------------------------------------------------
    # Tab 1: Dashboard
    # -------------------------------------------------------------------------
    def _build_dashboard(self):
        tab = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(tab, text="  📊 Dashboard  ")

        cards = tk.Frame(tab, bg=C["bg"])
        cards.pack(fill="x", padx=10, pady=10)
        self.card_br = self._stat_card(cards, "CURRENT BANKROLL", "$100.00", 0)
        self.card_pnl = self._stat_card(cards, "TOTAL P&L", "$0.00", 1)
        self.card_peak = self._stat_card(cards, "PEAK BANKROLL", "$100.00", 2)
        self.card_dd = self._stat_card(cards, "DRAWDOWN", "0.0%", 3)
        for i in range(4):
            cards.columnconfigure(i, weight=1)

        sl = tk.Frame(tab, bg=C["card"])
        sl.pack(fill="x", padx=10, pady=(0, 10))
        self.sl_text = tk.Label(sl, text="  ✅ All risk controls clear", bg=C["card"],
                                 fg=C["green"], font=("Segoe UI", 10), anchor="w", padx=15, pady=10)
        self.sl_text.pack(fill="x")

        self._label(tab, "RECENT ENTRIES", 9, C["text2"], True, C["bg"]).pack(
            fill="x", padx=12, pady=(5, 2))
        tf = tk.Frame(tab, bg=C["card"])
        tf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("id", "date", "type", "fee", "result", "payout", "pnl")
        self.etree = ttk.Treeview(tf, columns=cols, show="headings", style="Dark.Treeview", height=8)
        for c, h, w in [("id","#",40),("date","Date",100),("type","Type",60),
                         ("fee","Fee",80),("result","Result",70),("payout","Payout",80),("pnl","P&L",80)]:
            self.etree.heading(c, text=h)
            self.etree.column(c, width=w, anchor="center")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.etree.yview)
        self.etree.configure(yscrollcommand=sb.set)
        self.etree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        bf = tk.Frame(tab, bg=C["bg"])
        bf.pack(fill="x", padx=10, pady=(0, 5))
        self._btn(bf, "🔄 Refresh", self._refresh_bankroll_display, False).pack(side="right")

    def _stat_card(self, parent, title, value, col):
        f = tk.Frame(parent, bg=C["card"], padx=20, pady=15)
        f.grid(row=0, column=col, sticky="nsew", padx=5)
        tk.Label(f, text=title, bg=C["card"], fg=C["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        lbl = tk.Label(f, text=value, bg=C["card"], fg=C["green"],
                        font=("Consolas", 20, "bold"))
        lbl.pack(anchor="w", pady=(4, 0))
        return lbl

    # -------------------------------------------------------------------------
    # Tab 2: EV Calculator (2-6 picks, presets, custom multipliers)
    # -------------------------------------------------------------------------
    def _build_ev_tab(self):
        tab = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(tab, text="  🧮 EV Calculator  ")

        # LEFT: inputs
        left = tk.Frame(tab, bg=C["card"], padx=18, pady=12)
        left.pack(side="left", fill="y", padx=(10, 5), pady=10)

        self._label(left, "EV CALCULATOR", 12, C["text"], True).pack(anchor="w", pady=(0, 10))

        row = tk.Frame(left, bg=C["card"])
        row.pack(fill="x", pady=4)
        self._label(row, "Win Prob/Leg (%):").pack(side="left")
        self.ev_uni_prob = self._entry(row, 8, "56")
        self.ev_uni_prob.pack(side="left", padx=10)

        row2 = tk.Frame(left, bg=C["card"])
        row2.pack(fill="x", pady=4)
        self._label(row2, "Entry Fee ($):").pack(side="left")
        self.ev_fee = self._entry(row2, 8, "5")
        self.ev_fee.pack(side="left", padx=10)

        self._btn(left, "⚡ Calculate EV Table", self._calculate_ev).pack(fill="x", pady=(12, 4))
        self._btn(left, "📊 Sensitivity Table", self._show_sensitivity, False).pack(fill="x", pady=4)

        self.be_label = tk.Label(left, text="Break-even rates:\n  (after calculating)",
                                  bg=C["input"], fg=C["text2"],
                                  font=("Consolas", 8), justify="left", padx=8, pady=6, anchor="w")
        self.be_label.pack(fill="x", pady=(12, 0))

        legend = tk.Frame(left, bg=C["card"])
        legend.pack(fill="x", pady=(10, 0))
        tk.Label(legend, text="■ +EV", bg=C["card"], fg=C["green"],
                 font=("Segoe UI", 8)).pack(side="left", padx=(0, 10))
        tk.Label(legend, text="■ -EV", bg=C["card"], fg=C["red"],
                 font=("Segoe UI", 8)).pack(side="left")

        # RIGHT: table + detail area
        right = tk.Frame(tab, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True, padx=(5, 10), pady=10)

        cols = ("picks", "type", "std_ev", "std_roi", "golf_ev", "golf_roi", "std_be", "golf_be")
        self.ev_tree = ttk.Treeview(right, columns=cols, show="headings", style="Dark.Treeview")
        for col, heading, width in [
            ("picks", "Picks", 75), ("type", "Type", 65),
            ("std_ev", "Std Net EV", 110), ("std_roi", "Std ROI%", 95),
            ("golf_ev", "Golf Net EV", 110), ("golf_roi", "Golf ROI%", 95),
            ("std_be", "Std BE%", 90), ("golf_be", "Golf BE%", 90),
        ]:
            self.ev_tree.heading(col, text=heading)
            self.ev_tree.column(col, width=width, anchor="center")

        sb = ttk.Scrollbar(right, orient="vertical", command=self.ev_tree.yview)
        self.ev_tree.configure(yscrollcommand=sb.set)
        self.ev_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.ev_tree.tag_configure("pos", foreground=C["green"])
        self.ev_tree.tag_configure("neg", foreground=C["red"])
        self.ev_tree.tag_configure("mixed", foreground=C["warn"])

        self.ev_out = scrolledtext.ScrolledText(
            right, bg=C["card"], fg=C["text"], font=("Consolas", 9), relief="flat",
            wrap="word", padx=12, pady=10, height=7)
        self.ev_out.pack(fill="x", pady=(5, 0))
        self.ev_out.insert("1.0",
            "  Enter a win prob % and click Calculate EV Table.\n"
            "  Std = Standard (non-correlated) payouts\n"
            "  Golf = Golf/correlated (reduced) payouts\n"
            "  BE% = break-even win rate per leg needed")
        self.ev_out.configure(state="disabled")

    def _calculate_ev(self):
        try:
            wp = float(self.ev_uni_prob.get())
            if wp > 1:
                wp /= 100.0
            fee = float(self.ev_fee.get())
        except ValueError:
            messagebox.showerror("Error", "Enter a valid probability and fee.")
            return

        self.ev_tree.delete(*self.ev_tree.get_children())
        be_lines = [f"Break-even rates ({wp:.1%}/leg):"]

        for n in range(2, 7):
            for ptype in ["power", "flex"]:
                std_payouts = get_payout_table(n, ptype, "standard")
                golf_payouts = get_payout_table(n, ptype, "golf")
                if not std_payouts and not golf_payouts:
                    continue

                probs = [wp] * n

                if std_payouts:
                    std = calculate_ev(n, probs, fee, ptype, "standard")
                    std_ev_str = f"${std['net_ev']:+.2f}"
                    std_roi_str = f"{std['roi_pct']:+.1f}%"
                    std_pos = std["is_positive_ev"]
                    std_be = find_breakeven_prob(n, ptype, "standard")
                    std_be_str = f"{std_be:.2%}"
                    be_lines.append(f"  {n}P {ptype[0].upper()} Std: {std_be:.2%}")
                else:
                    std_ev_str = std_roi_str = std_be_str = "N/A"
                    std_pos = None

                if golf_payouts:
                    golf = calculate_ev(n, probs, fee, ptype, "golf")
                    golf_ev_str = f"${golf['net_ev']:+.2f}"
                    golf_roi_str = f"{golf['roi_pct']:+.1f}%"
                    golf_pos = golf["is_positive_ev"]
                    golf_be = find_breakeven_prob(n, ptype, "golf")
                    golf_be_str = f"{golf_be:.2%}"
                else:
                    golf_ev_str = golf_roi_str = golf_be_str = "N/A"
                    golf_pos = None

                if std_pos is True and (golf_pos is True or golf_pos is None):
                    tag = "pos"
                elif std_pos is False and (golf_pos is False or golf_pos is None):
                    tag = "neg"
                elif std_pos is None:
                    tag = "pos" if golf_pos else "neg"
                else:
                    tag = "mixed"

                self.ev_tree.insert("", "end", tags=(tag,), values=(
                    f"{n}-Pick", ptype.upper(),
                    std_ev_str, std_roi_str,
                    golf_ev_str, golf_roi_str,
                    std_be_str, golf_be_str,
                ))

        self.be_label.config(text="\n".join(be_lines))

    def _show_sensitivity(self):
        try:
            wp = float(self.ev_uni_prob.get())
            if wp > 1:
                wp /= 100.0
            fee = float(self.ev_fee.get())
        except ValueError:
            return

        lines = []
        for preset in ["standard", "golf"]:
            for ptype in ["power", "flex"]:
                payouts = get_payout_table(6, ptype, preset)
                if not payouts:
                    continue
                be = find_breakeven_prob(6, ptype, preset)
                lines.append(f"  6-Pick {ptype.upper()} ({preset}) — Break-even: {be:.2%}")
                lines.append(f"  {'Win%':>6s}  {'Net EV':>9s}  {'ROI':>8s}")
                lines.append(f"  {'─'*6}  {'─'*9}  {'─'*8}")
                for row in ev_sensitivity_table(6, fee, ptype, preset):
                    arrow = "◀" if abs(row["win_prob_pct"] / 100 - wp) < 0.006 else " "
                    status = "+EV ✅" if row["is_positive"] else "-EV ❌"
                    lines.append(f"  {row['win_prob_pct']:>5d}% {arrow} ${row['net_ev']:>+8.2f}"
                                 f"  {row['roi_pct']:>+7.1f}%  {status}")
                lines.append("")

        self.ev_out.configure(state="normal")
        self.ev_out.delete("1.0", "end")
        self.ev_out.insert("1.0", "\n".join(lines))
        self.ev_out.configure(state="disabled")

    # -------------------------------------------------------------------------
    # Tab 3: Kelly Sizing
    # -------------------------------------------------------------------------
    def _build_kelly_tab(self):
        tab = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(tab, text="  📏 Kelly Sizing  ")

        inp = tk.Frame(tab, bg=C["card"], padx=25, pady=20)
        inp.pack(fill="x", padx=10, pady=10)

        self._label(inp, "KELLY CRITERION ENTRY SIZING", 12, C["text"], True).grid(
            row=0, column=0, columnspan=6, sticky="w", pady=(0, 15))

        self._label(inp, "Win Prob/Leg (%):").grid(row=1, column=0, sticky="w", pady=5)
        self.k_prob = self._entry(inp, 8, "56")
        self.k_prob.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        self._label(inp, "# Picks:").grid(row=1, column=2, sticky="w", padx=(15, 0))
        self.k_npicks = ttk.Combobox(inp, values=["2","3","4","5","6"], state="readonly",
                                      width=4, font=("Segoe UI", 10))
        self.k_npicks.set("6")
        self.k_npicks.grid(row=1, column=3, sticky="w", padx=10)

        self._label(inp, "Type:").grid(row=1, column=4, sticky="w", padx=(15, 0))
        self.k_type = ttk.Combobox(inp, values=["flex", "power"], state="readonly",
                                    width=7, font=("Segoe UI", 10))
        self.k_type.set("flex")
        self.k_type.grid(row=1, column=5, sticky="w", padx=10)

        self._btn(inp, "⚡ Calculate Size", self._calc_kelly).grid(
            row=2, column=0, columnspan=6, sticky="w", pady=(15, 0))

        self.k_out = scrolledtext.ScrolledText(tab, bg=C["card"], fg=C["text"],
                                                font=("Consolas", 11), relief="flat",
                                                wrap="word", padx=20, pady=15)
        self.k_out.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.k_out.insert("1.0", f"  Enter a win probability and click Calculate.\n\n"
                           f"  Uses {KELLY_FRACTION:.0%} Kelly for high-variance pick pools.\n"
                           f"  Current bankroll: ${self.bm.current_bankroll:.2f}")
        self.k_out.configure(state="disabled")

    def _calc_kelly(self):
        try:
            wp = float(self.k_prob.get())
            if wp > 1: wp /= 100.0
            n = int(self.k_npicks.get())
        except ValueError:
            messagebox.showerror("Error", "Enter valid inputs.")
            return

        pt = self.k_type.get()
        sizing = self.bm.kelly_bet_size(wp, pt, n)

        lines = []
        lines.append("═" * 50)
        lines.append("  KELLY CRITERION ENTRY SIZING")
        lines.append("═" * 50)
        lines.append(f"  Bankroll:         ${sizing['current_bankroll']:.2f}")
        lines.append(f"  Win prob/leg:     {wp:.1%}")
        lines.append(f"  Play:             {n}-pick {pt}")
        lines.append(f"  EV per $1:        ${sizing['net_ev_per_dollar']:+.4f}")
        lines.append("─" * 50)
        lines.append(f"  Full Kelly:       {sizing['full_kelly_pct']:.2%} "
                     f"(${sizing['current_bankroll'] * sizing['full_kelly_pct']:.2f})")
        lines.append(f"  {KELLY_FRACTION:.0%} Kelly:       "
                     f"{sizing['fractional_kelly_pct']:.2%} "
                     f"(${sizing['raw_kelly_size']:.2f})")
        lines.append("─" * 50)
        if sizing["is_positive_ev"]:
            lines.append(f"  ✅ RECOMMENDED:   ${sizing['recommended_size']:.2f} "
                         f"({sizing['bankroll_pct']:.1f}% of bankroll)")
        else:
            lines.append(f"  ⚠️  NEGATIVE EV — Kelly says don't bet.")
        lines.append("═" * 50)

        self.k_out.configure(state="normal")
        self.k_out.delete("1.0", "end")
        self.k_out.insert("1.0", "\n".join(lines))
        self.k_out.configure(state="disabled")

    # -------------------------------------------------------------------------
    # Tab 4: Entries
    # -------------------------------------------------------------------------
    def _build_entries_tab(self):
        tab = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(tab, text="  📝 Entries  ")

        # Record
        rf = tk.LabelFrame(tab, text=" Record New Entry ", bg=C["card"], fg=C["green"],
                            font=("Segoe UI", 10, "bold"), padx=15, pady=10)
        rf.pack(fill="x", padx=10, pady=10)

        r1 = tk.Frame(rf, bg=C["card"])
        r1.pack(fill="x", pady=3)
        self._label(r1, "Fee ($):").pack(side="left")
        self.ent_fee = self._entry(r1, 8, "5")
        self.ent_fee.pack(side="left", padx=10)
        self._label(r1, "Type:").pack(side="left", padx=(15, 0))
        self.ent_type = ttk.Combobox(r1, values=["flex","power"], state="readonly",
                                      width=7, font=("Segoe UI", 9))
        self.ent_type.set("flex")
        self.ent_type.pack(side="left", padx=10)

        r2 = tk.Frame(rf, bg=C["card"])
        r2.pack(fill="x", pady=5)
        self._label(r2, "Picks (comma-separated):").pack(anchor="w")
        self.ent_picks = tk.Entry(r2, bg=C["input"], fg=C["text"],
                                   insertbackground=C["text"], font=("Consolas", 10),
                                   relief="flat", bd=4)
        self.ent_picks.pack(fill="x", pady=3)

        r3 = tk.Frame(rf, bg=C["card"])
        r3.pack(fill="x", pady=3)
        self._label(r3, "Notes:").pack(side="left")
        self.ent_notes = self._entry(r3, 30, "")
        self.ent_notes.pack(side="left", padx=10, fill="x", expand=True)
        self._btn(r3, "💾 Record Entry", self._record_entry).pack(side="right")

        # Resolve
        resf = tk.LabelFrame(tab, text=" Resolve Entry ", bg=C["card"], fg=C["gold"],
                               font=("Segoe UI", 10, "bold"), padx=15, pady=10)
        resf.pack(fill="x", padx=10, pady=(0, 10))
        rr = tk.Frame(resf, bg=C["card"])
        rr.pack(fill="x", pady=3)
        self._label(rr, "Entry #:").pack(side="left")
        self.res_id = self._entry(rr, 6)
        self.res_id.pack(side="left", padx=10)
        self._label(rr, "Correct (0-6):").pack(side="left", padx=(15, 0))
        self.res_correct = self._entry(rr, 4)
        self.res_correct.pack(side="left", padx=10)
        self._btn(rr, "✅ Resolve", self._resolve_entry).pack(side="right")

        self.res_status = tk.Label(resf, text="", bg=C["card"], fg=C["text2"],
                                    font=("Consolas", 9), anchor="w")
        self.res_status.pack(fill="x", pady=(5, 0))

        af = tk.Frame(tab, bg=C["bg"])
        af.pack(fill="x", padx=10, pady=(0, 5))
        self._btn(af, "💵 Add Deposit", self._add_deposit, False).pack(side="left", padx=(0, 5))
        self._btn(af, "🔄 New Session", self._new_session, False).pack(side="left", padx=5)
        self._btn(af, "🗑️ Reset Bankroll", self._reset_bankroll, False).pack(side="right")

    # -------------------------------------------------------------------------
    # Tab 5: DataGolf
    # -------------------------------------------------------------------------
    def _build_datagolf_tab(self):
        tab = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(tab, text="  ⛳ DataGolf  ")

        # Storage for sortable data
        self._dg_cached_data = []
        self._dg_cached_action = None
        self._dg_cached_header = ""

        # Row 1: Pre-tournament
        bf1 = tk.Frame(tab, bg=C["bg"])
        bf1.pack(fill="x", padx=10, pady=(10, 2))
        self._label(bf1, "PRE-TOURN:", 8, C["text2"], True, C["bg"]).pack(side="left", padx=(0, 5))
        for txt, act in [("🏆 Rankings","rankings"),("🎯 Predictions","predictions"),
                          ("🏌️ Field","field"),("📊 Skills","skills")]:
            self._btn(bf1, txt, lambda a=act: self._dg_threaded(a), False).pack(side="left", padx=2)

        # Row 2: Live model
        bf2 = tk.Frame(tab, bg=C["bg"])
        bf2.pack(fill="x", padx=10, pady=2)
        self._label(bf2, "LIVE:", 8, C["gold"], True, C["bg"]).pack(side="left", padx=(0, 5))
        for txt, act in [("🔴 Live Predictions","live_preds"),
                          ("📈 Live Stats","live_stats")]:
            self._btn(bf2, txt, lambda a=act: self._dg_threaded(a)).pack(side="left", padx=2)
        self._btn(bf2, "🔌 Test API", lambda: self._dg_threaded("test"), False).pack(side="right")

        # Row 3: Sort controls
        bf3 = tk.Frame(tab, bg=C["bg"])
        bf3.pack(fill="x", padx=10, pady=2)
        self._label(bf3, "Sort by:", 8, C["text2"], True, C["bg"]).pack(side="left", padx=(0, 5))
        self.dg_sort_var = tk.StringVar(value="(fetch data first)")
        self.dg_sort_combo = ttk.Combobox(bf3, textvariable=self.dg_sort_var, width=25,
                                            state="readonly")
        self.dg_sort_combo.pack(side="left", padx=2)
        self.dg_sort_combo.bind("<<ComboboxSelected>>", self._dg_sort_changed)
        self.dg_sort_desc = tk.BooleanVar(value=True)
        tk.Checkbutton(bf3, text="Descending", variable=self.dg_sort_desc,
                       bg=C["bg"], fg=C["text"], selectcolor=C["card"],
                       activebackground=C["bg"], activeforeground=C["text"],
                       command=self._dg_sort_apply).pack(side="left", padx=5)

        # Output area
        self.dg_out = scrolledtext.ScrolledText(tab, bg=C["card"], fg=C["text"],
                                                  font=("Consolas", 9), relief="flat",
                                                  wrap="none", padx=15, pady=15)
        self.dg_out.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        api_ok = "✅ Configured" if DATAGOLF_API_KEY != "YOUR_API_KEY_HERE" else "❌ Not Set"
        self.dg_out.insert("1.0",
            f"  DataGolf API: {api_ok}\n\n"
            f"  Click any button above to fetch data.\n"
            f"  Use the Sort dropdown to re-sort results by any column.\n\n"
            f"  💡 TIP: During rounds, use 'Live Stats' to pull GIR,\n"
            f"  SG stats, etc. and sort to find your best picks.")
        self.dg_out.configure(state="disabled")

    # -------------------------------------------------------------------------
    # Tab 6: Settings
    # -------------------------------------------------------------------------
    def _build_settings_tab(self):
        tab = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(tab, text="  ⚙️ Settings  ")
        f = tk.Frame(tab, bg=C["card"], padx=25, pady=20)
        f.pack(fill="both", expand=True, padx=10, pady=10)
        self._label(f, "CURRENT SETTINGS", 12, C["text"], True).pack(anchor="w", pady=(0, 15))

        text = (
            f"Starting Bankroll:    ${STARTING_BANKROLL:.2f}\n"
            f"Kelly Fraction:       {KELLY_FRACTION:.0%}\n"
            f"Max Entry %:          10% of bankroll\n"
            f"Session Stop-Loss:    ${SESSION_STOP_LOSS:.2f}\n"
            f"Max Drawdown:         {MAX_DRAWDOWN_PCT:.0%}\n"
            f"Weekly Loss Limit:    ${WEEKLY_LOSS_LIMIT:.2f}\n"
            f"Min Bankroll Floor:   ${MIN_BANKROLL_FLOOR:.2f}\n\n"
            f"DataGolf API:         {'✅' if DATAGOLF_API_KEY != 'YOUR_API_KEY_HERE' else '❌'}\n\n"
            f"STANDARD PAYOUTS (non-correlated):\n"
            f"  2-Power: 3.0x    | 3-Power: 5.0x   | 3-Flex: 2.25x/1.25x\n"
            f"  4-Power: 10.0x   | 4-Flex: 5.0x/1.5x\n"
            f"  5-Power: 20.0x   | 5-Flex: 10x/2x/0.4x\n"
            f"  6-Power: 37.5x   | 6-Flex: 25x/2x/0.4x\n\n"
            f"GOLF / CORRELATED (approximate, always check PP):\n"
            f"  2-Power: 2.7x    | 3-Power: 4.5x   | 3-Flex: 2.0x/1.1x\n"
            f"  4-Power: 8.5x    | 4-Flex: 4.25x/1.35x\n"
            f"  5-Power: 17.0x   | 5-Flex: 8.5x/1.75x/0.35x\n"
            f"  6-Power: 32.0x   | 6-Flex: 21x/1.75x/0.35x\n\n"
            f"Edit config.py to change settings.\n"
            f"Use 'custom' preset in EV Calculator to enter exact PP multipliers."
        )
        tk.Label(f, text=text, bg=C["card"], fg=C["text2"], font=("Consolas", 9),
                 justify="left", anchor="nw").pack(fill="both", expand=True)

    # =========================================================================
    # Action Handlers
    # =========================================================================
    def _refresh_bankroll_display(self):
        bm = self.bm
        bm.data = bm._load_data()
        self.bankroll_lbl.config(text=f"Bankroll: ${bm.current_bankroll:.2f}")
        self.card_br.config(text=f"${bm.current_bankroll:.2f}")
        pnl = bm.total_pnl
        self.card_pnl.config(text=f"${pnl:+.2f}",
                              fg=C["green"] if pnl >= 0 else C["red"])
        self.card_peak.config(text=f"${bm.peak_bankroll:.2f}")
        dd = bm.drawdown_pct
        self.card_dd.config(text=f"{dd:.1%}",
                             fg=C["green"] if dd < 0.15 else (C["warn"] if dd < 0.25 else C["red"]))

        status = bm.check_stop_loss()
        if status["can_play"]:
            self.sl_text.config(text="  ✅ All risk controls clear — good to play", fg=C["green"])
            self.sl_indicator.config(text="● CLEAR", fg=C["green"])
        else:
            msgs = [a["message"] for a in status["alerts"] if a["severity"] == "STOP"]
            self.sl_text.config(text="  🛑 STOP: " + " | ".join(msgs), fg=C["red"])
            self.sl_indicator.config(text="● STOP", fg=C["red"])

        self.etree.delete(*self.etree.get_children())
        for e in [x for x in bm.data["entries"] if x.get("entry_fee") and x.get("type") != "deposit"][-15:]:
            self.etree.insert("", "end", values=(
                e.get("id",""), e.get("timestamp","")[:10], e.get("play_type",""),
                f"${e.get('entry_fee',0):.2f}", e.get("result","pending"),
                f"${e.get('payout',0):.2f}", f"${e.get('pnl',0):+.2f}"))

        pending = [e for e in bm.data["entries"] if e.get("status") == "pending"]
        self.res_status.config(text="Pending: " + ", ".join(
            [f"#{e['id']} (${e['entry_fee']:.2f})" for e in pending]) if pending else "No pending entries.")

    def _record_entry(self):
        if not self.bm.check_stop_loss()["can_play"]:
            messagebox.showwarning("Stop-Loss", "Stop-loss active. Cannot enter.")
            return
        try:
            fee = float(self.ent_fee.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid fee.")
            return
        if fee > self.bm.current_bankroll:
            messagebox.showerror("Error", "Fee exceeds bankroll.")
            return
        picks = [p.strip() for p in self.ent_picks.get().split(",") if p.strip()]
        if not picks:
            messagebox.showerror("Error", "Enter picks.")
            return
        entry = self.bm.record_entry(fee, picks, self.ent_type.get(), self.ent_notes.get())
        messagebox.showinfo("Recorded", f"Entry #{entry['id']} — ${fee:.2f}\n"
                             f"Bankroll: ${self.bm.current_bankroll:.2f}")
        self._refresh_bankroll_display()
        self.ent_picks.delete(0, "end")
        self.ent_notes.delete(0, "end")

    def _resolve_entry(self):
        try:
            eid = int(self.res_id.get())
            correct = int(self.res_correct.get())
        except ValueError:
            messagebox.showerror("Error", "Enter valid entry # and correct count.")
            return
        result = self.bm.resolve_entry(eid, correct)
        if "error" in result:
            messagebox.showerror("Error", result["error"])
            return
        e = "🎉" if result["pnl"] > 0 else "😤" if result["pnl"] < 0 else "😐"
        messagebox.showinfo("Resolved", f"{e} #{result['entry_id']}: {result['result']}\n"
                             f"Payout: ${result['payout']:.2f}\n"
                             f"P&L: ${result['pnl']:+.2f}\n"
                             f"Bankroll: ${result['new_bankroll']:.2f}")
        self._refresh_bankroll_display()
        self.res_id.delete(0, "end")
        self.res_correct.delete(0, "end")

    def _add_deposit(self):
        d = tk.Toplevel(self)
        d.title("Add Deposit")
        d.geometry("300x120")
        d.configure(bg=C["card"])
        d.transient(self)
        d.grab_set()
        tk.Label(d, text="Amount ($):", bg=C["card"], fg=C["text"],
                 font=("Segoe UI", 10)).pack(pady=(15, 5))
        ae = self._entry(d, 12)
        ae.pack()
        ae.focus()
        def do():
            try:
                a = float(ae.get())
                if a > 0:
                    self.bm.add_deposit(a)
                    self._refresh_bankroll_display()
                    d.destroy()
            except ValueError: pass
        self._btn(d, "Deposit", do).pack(pady=10)

    def _new_session(self):
        if messagebox.askyesno("New Session", "Archive current session?"):
            self.bm.start_new_session()
            self._refresh_bankroll_display()

    def _reset_bankroll(self):
        if messagebox.askyesno("Reset", "Reset bankroll? Cannot be undone."):
            self.bm.reset(STARTING_BANKROLL)
            self._refresh_bankroll_display()

    # =========================================================================
    # DataGolf (threaded)
    # =========================================================================
    def _dg_threaded(self, action):
        self._dg_text("  ⏳ Fetching...")
        threading.Thread(target=self._dg_fetch, args=(action,), daemon=True).start()

    def _dg_sort_changed(self, event=None):
        self._dg_sort_apply()

    def _dg_sort_apply(self):
        """Re-sort cached data by the selected column and re-render."""
        if not self._dg_cached_data:
            return
        sort_key = self.dg_sort_var.get()
        if not sort_key or sort_key == "(fetch data first)":
            return
        desc = self.dg_sort_desc.get()
        data = self._dg_cached_data
        action = self._dg_cached_action

        # Sort — put None/missing values last
        def sort_val(p):
            v = p.get(sort_key)
            if v is None or v == "":
                return float('-inf') if desc else float('inf')
            if isinstance(v, (int, float)):
                return v
            try:
                return float(v)
            except (ValueError, TypeError):
                return float('-inf') if desc else float('inf')

        sorted_data = sorted(data, key=sort_val, reverse=desc)
        text = self._dg_format_table(sorted_data, action, f"  Sorted by: {sort_key} ({'desc' if desc else 'asc'})")
        self._dg_text(self._dg_cached_header + "\n" + text)

    def _dg_format_table(self, players, action, subtitle=""):
        """Format a player list into a text table based on action type."""
        if not players:
            return "  No data."
        lines = []
        if subtitle:
            lines.append(subtitle)
            lines.append("")

        if action == "rankings":
            lines.append(f"  {'Rank':>5s}  {'Player':<30s}  {'Skill':>8s}  {'OWGR':>6s}  {'Tour':<5s}")
            lines.append("  " + "─" * 60)
            for p in players:
                skill = p.get('dg_skill_estimate')
                skill_str = f"{skill:>8.2f}" if isinstance(skill, (int, float)) else f"{'---':>8s}"
                owgr = p.get('owgr_rank')
                owgr_str = f"{owgr:>6}" if owgr is not None else f"{'---':>6s}"
                lines.append(f"  {p.get('datagolf_rank',''):>5}  {p.get('player_name','?'):<30s}  "
                             f"{skill_str}  {owgr_str}  {str(p.get('primary_tour','')):<5s}")

        elif action == "predictions":
            lines.append(f"  {'#':>3s}  {'Player':<28s}  {'Win%':>7s}  {'T5%':>7s}  "
                         f"{'T10%':>7s}  {'T20%':>7s}  {'MC%':>7s}")
            lines.append("  " + "─" * 75)
            for i, p in enumerate(players):
                def pct(k):
                    val = p.get(k)
                    if isinstance(val, (int, float)):
                        return f"{val*100:>6.2f}%"
                    return f"{'---':>7s}"
                lines.append(f"  {i+1:>3d}  {p.get('player_name','?')[:28]:<28s}  "
                             f"{pct('win')}  {pct('top_5')}  {pct('top_10')}  "
                             f"{pct('top_20')}  {pct('make_cut')}")

        elif action == "skills":
            lines.append(f"  {'Player':<25s}  {'SG:OTT':>7s}  {'SG:APP':>7s}  {'SG:ARG':>7s}  "
                         f"{'SG:Putt':>7s}  {'SG:Tot':>7s}  {'DrDist':>7s}  {'DrAcc':>7s}")
            lines.append("  " + "─" * 80)
            for p in players:
                def v(k):
                    val = p.get(k)
                    return f"{val:>7.3f}" if isinstance(val, (int, float)) else f"{'---':>7s}"
                lines.append(f"  {p.get('player_name','?')[:25]:<25s}  "
                             f"{v('sg_ott')}  {v('sg_app')}  {v('sg_arg')}  "
                             f"{v('sg_putt')}  {v('sg_total')}  {v('driving_dist')}  {v('driving_acc')}")

        elif action == "live_stats":
            lines.append(f"  {'Pos':>4s}  {'Player':<28s}  {'Total':>6s}  {'Rd':>4s}  {'Thru':>4s}  "
                         f"{'GIR':>6s}  {'SG:APP':>7s}  {'SG:Tot':>7s}")
            lines.append("  " + "─" * 82)
            for p in players:
                gir_val = p.get('gir')
                gir_str = f"{gir_val*100:>5.1f}%" if isinstance(gir_val, (int, float)) else f"{'---':>6s}"
                def v(k):
                    val = p.get(k)
                    return f"{val:>7.2f}" if isinstance(val, (int, float)) else f"{'---':>7s}"
                total = p.get('total')
                total_str = f"{total:>+4d}" if isinstance(total, (int, float)) else f"{'---':>6s}"
                rd = p.get('round')
                rd_str = f"{rd:>4}" if rd is not None else f"{'---':>4s}"
                thru = p.get('thru')
                thru_str = f"{thru:>4}" if thru is not None else f"{'---':>4s}"
                pos = str(p.get('position') or '')[:4]
                lines.append(f"  {pos:>4s}  {p.get('player_name','?')[:28]:<28s}  "
                             f"{total_str:>6s}  {rd_str}  {thru_str}  "
                             f"{gir_str}  {v('sg_app')}  {v('sg_total')}")

        elif action == "live_preds":
            lines.append(f"  {'Pos':>4s}  {'Player':<28s}  {'Win%':>7s}  {'T5%':>7s}  "
                         f"{'T10%':>7s}  {'T20%':>7s}  {'MC%':>7s}")
            lines.append("  " + "─" * 78)
            for p in players:
                def f(k):
                    val = p.get(k)
                    if isinstance(val, (int, float)):
                        pct = val * 100 if val < 1 else val
                        return f"{pct:>6.2f}%"
                    return f"{'---':>7s}"
                pos = str(p.get('position') or p.get('current_pos') or '')[:4]
                lines.append(f"  {pos:>4s}  "
                             f"{p.get('player_name','?')[:28]:<28s}  "
                             f"{f('win_prob')}  {f('top_5')}  {f('top_10')}  "
                             f"{f('top_20')}  {f('make_cut')}")

        elif action == "field":
            lines.append(f"  {'#':>3s}  {'Player':<30s}  {'R1 Tee Time':<15s}")
            lines.append("  " + "─" * 55)
            for i, p in enumerate(players):
                lines.append(f"  {i+1:>3d}  {p.get('player_name','?'):<30s}  "
                             f"{p.get('r1_teetime',''):>15s}")

        else:
            # Generic fallback — show all numeric columns
            if players:
                keys = [k for k in players[0].keys() if k != 'player_name']
                header = f"  {'Player':<25s}"
                for k in keys[:8]:
                    header += f"  {k[:10]:>10s}"
                lines.append(header)
                lines.append("  " + "─" * (27 + 12 * min(len(keys), 8)))
                for p in players:
                    row = f"  {p.get('player_name','?')[:25]:<25s}"
                    for k in keys[:8]:
                        val = p.get(k)
                        if isinstance(val, float):
                            row += f"  {val:>10.3f}"
                        else:
                            row += f"  {str(val)[:10]:>10s}"
                    lines.append(row)

        return "\n".join(lines)

    def _dg_update_sort_options(self, players, action):
        """Populate sort dropdown with column names from the data."""
        if not players or not isinstance(players, list) or len(players) == 0:
            return
        # Get numeric keys that make sense to sort by
        keys = []
        sample = players[0]
        for k, v in sample.items():
            if k in ('dg_id', 'am', 'course', 'country'):
                continue
            if isinstance(v, (int, float)) or k == 'player_name':
                keys.append(k)
        # Put the most useful ones first
        priority = ['gir', 'sg_total', 'sg_app', 'sg_ott', 'sg_arg', 'sg_putt',
                     'total', 'position', 'win', 'top_5', 'top_10', 'top_20', 'make_cut',
                     'dg_skill_estimate', 'owgr_rank', 'datagolf_rank',
                     'driving_dist', 'driving_acc', 'player_name']
        sorted_keys = [k for k in priority if k in keys]
        sorted_keys += [k for k in keys if k not in sorted_keys]
        self.dg_sort_combo["values"] = sorted_keys
        # Auto-select first key
        if sorted_keys:
            self.dg_sort_var.set(sorted_keys[0])

    def _dg_fetch(self, action):
        try:
            if action == "test":
                r = self.dg.test_connection()
                if r["ok"]:
                    raw = r.get("raw", {})
                    events = raw.get("schedule", []) if isinstance(raw, dict) else raw
                    lines = [f"  ✅ {r['message']}", f"  Upcoming events: {len(events)}", ""]
                    for ev in (events if isinstance(events, list) else [])[:8]:
                        lines.append(f"  {ev.get('event_name','N/A')}")
                        lines.append(f"    📍 {ev.get('course','N/A')} — {ev.get('location','')}")
                        lines.append(f"    📅 {ev.get('start_date','')}  Status: {ev.get('status','')}")
                        lines.append("")
                    self.after(0, self._dg_text, "\n".join(lines))
                else:
                    self.after(0, self._dg_text, f"  ❌ {r['error']}")
                return

            elif action == "rankings":
                d = self.dg.get_rankings()
                if isinstance(d, dict) and "error" in d:
                    self.after(0, self._dg_text, f"  ❌ {d['error']}")
                    return
                players = d.get("rankings", [])
                header = f"  🏆 DataGolf Rankings  |  Updated: {d.get('last_updated','?')}"

            elif action == "predictions":
                d = self.dg.get_pre_tournament_predictions()
                if isinstance(d, dict) and "error" in d:
                    self.after(0, self._dg_text, f"  ❌ {d['error']}")
                    return
                # Use baseline_history_fit (includes course fit) if available
                players = d.get("baseline_history_fit", d.get("baseline", []))
                header = (f"  🎯 {d.get('event_name','?')}  |  Model: baseline + course fit\n"
                          f"  Updated: {d.get('last_updated','?')}")

            elif action == "field":
                d = self.dg.get_field_updates()
                if isinstance(d, dict) and "error" in d:
                    self.after(0, self._dg_text, f"  ❌ {d['error']}")
                    return
                players = d.get("field", [])
                header = (f"  🏌️ {d.get('event_name','?')}\n"
                          f"  📍 {d.get('course','?')}  |  Field: {len(players)} players")

            elif action == "skills":
                d = self.dg.get_skill_ratings()
                if isinstance(d, dict) and "error" in d:
                    self.after(0, self._dg_text, f"  ❌ {d['error']}")
                    return
                players = d.get("players", [])
                header = f"  📊 Skill Ratings  |  Updated: {d.get('last_updated','?')}"

            elif action == "live_stats":
                d = self.dg.get_live_tournament_stats(
                    stats="sg_ott,sg_app,sg_arg,sg_putt,sg_total,gir,accuracy,distance",
                    round_num="event_avg"
                )
                if isinstance(d, dict) and "error" in d:
                    self.after(0, self._dg_text, f"  ❌ {d['error']}\n\n"
                               "  Live stats only available during tournaments.")
                    return
                players = d.get("live_stats", [])
                header = (f"  📈 LIVE: {d.get('event_name','?')}  |  {d.get('course_name','')}\n"
                          f"  Updated: {d.get('last_updated','?')}  |  {len(players)} players")

            elif action == "live_preds":
                d = self.dg.get_live_predictions()
                if isinstance(d, dict) and "error" in d:
                    self.after(0, self._dg_text, f"  ❌ {d['error']}\n\n"
                               "  Live predictions only available during rounds.")
                    return
                # Find the player list in the response
                players = []
                if isinstance(d, list):
                    players = d
                elif isinstance(d, dict):
                    for key in ['data', 'rankings', 'live_stats', 'in_play']:
                        if isinstance(d.get(key), list):
                            players = d[key]
                            break
                    if not players:
                        # Try first list value
                        for v in d.values():
                            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                                players = v
                                break
                header = (f"  🔴 LIVE Predictions  |  Updated: {d.get('last_updated','?')}\n"
                          f"  {d.get('event_name','')}")

            else:
                self.after(0, self._dg_text, f"  Unknown action: {action}")
                return

            if not players:
                self.after(0, self._dg_text, f"  ⚠️  No data returned for '{action}'.\n"
                           "  This may be between events or outside tournament hours.")
                return

            # Cache for sorting
            self._dg_cached_data = players
            self._dg_cached_action = action
            self._dg_cached_header = header

            # Update sort dropdown
            self.after(0, self._dg_update_sort_options, players, action)

            # Format and display
            table = self._dg_format_table(players, action)
            self.after(0, self._dg_text, header + "\n\n" + table)

        except Exception as e:
            import traceback
            self.after(0, self._dg_text, f"  ❌ Error: {e}\n\n{traceback.format_exc()}")

    def _dg_text(self, text):
        self.dg_out.configure(state="normal")
        self.dg_out.delete("1.0", "end")
        self.dg_out.insert("1.0", text)
        self.dg_out.configure(state="disabled")


if __name__ == "__main__":
    app = FantasyGolfApp()
    app.mainloop()
