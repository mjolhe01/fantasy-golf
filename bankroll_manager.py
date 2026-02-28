"""
Bankroll Manager
=================
Handles entry sizing (Kelly Criterion), bankroll tracking,
drawdown monitoring, and stop-loss enforcement.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional, List
from config import (
    STARTING_BANKROLL, BANKROLL_FILE, KELLY_FRACTION,
    MIN_ENTRY_SIZE, MAX_ENTRY_SIZE, MAX_BANKROLL_PCT,
    SESSION_STOP_LOSS, MAX_DRAWDOWN_PCT, WEEKLY_LOSS_LIMIT,
    MIN_BANKROLL_FLOOR, PRIZEPICKS_PAYOUTS_STANDARD, CURRENCY_SYMBOL
)


class BankrollManager:
    """Manages bankroll tracking, sizing, and risk controls."""

    def __init__(self, bankroll_file: str = None):
        self.bankroll_file = bankroll_file or BANKROLL_FILE
        self.data = self._load_data()

    # =========================================================================
    # Persistence
    # =========================================================================

    def _load_data(self) -> dict:
        """Load bankroll data from file, or initialize fresh."""
        if os.path.exists(self.bankroll_file):
            with open(self.bankroll_file, "r") as f:
                return json.load(f)
        return self._initialize_data()

    def _initialize_data(self) -> dict:
        """Create a fresh bankroll data structure."""
        now = datetime.now().isoformat()
        return {
            "created": now,
            "starting_bankroll": STARTING_BANKROLL,
            "current_bankroll": STARTING_BANKROLL,
            "peak_bankroll": STARTING_BANKROLL,
            "entries": [],
            "sessions": [],
            "current_session": {
                "started": now,
                "entries": [],
                "session_pnl": 0.0,
            },
        }

    def save(self):
        """Persist bankroll data to file."""
        with open(self.bankroll_file, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    # =========================================================================
    # Core Properties
    # =========================================================================

    @property
    def current_bankroll(self) -> float:
        return self.data["current_bankroll"]

    @property
    def peak_bankroll(self) -> float:
        return self.data["peak_bankroll"]

    @property
    def drawdown_pct(self) -> float:
        """Current drawdown from peak as a percentage."""
        if self.peak_bankroll == 0:
            return 0
        return 1 - (self.current_bankroll / self.peak_bankroll)

    @property
    def total_pnl(self) -> float:
        return self.current_bankroll - self.data["starting_bankroll"]

    @property
    def total_entries(self) -> int:
        return len(self.data["entries"])

    @property
    def session_pnl(self) -> float:
        return self.data["current_session"]["session_pnl"]

    # =========================================================================
    # Kelly Criterion Sizing
    # =========================================================================

    def kelly_bet_size(self, win_prob: float, play_type: str = "flex",
                       n_picks: int = 6) -> dict:
        """
        Calculate optimal entry size using Kelly Criterion.

        Args:
            win_prob: Average per-leg win probability
            play_type: 'flex' or 'power'
            n_picks: Number of picks (2-6)

        Returns:
            Dict with recommended size, Kelly %, and bounds info
        """
        # Get the payout table for this pick size and play type
        payout_table = PRIZEPICKS_PAYOUTS_STANDARD.get(f"{play_type}_play", {}).get(n_picks, {})

        # Use the EV calculator for accurate EV
        from prizepicks_ev import calculate_ev
        ev_result = calculate_ev(n_picks, [win_prob] * n_picks, 1.00, play_type, "standard")

        # Top multiplier for Kelly denominator
        top_multiplier = payout_table.get(n_picks, 1)  # integer key = all correct

        net_ev_per_dollar = ev_result["net_ev"]

        if net_ev_per_dollar <= 0:
            kelly_pct = 0.0
        else:
            # Kelly fraction based on edge/odds
            kelly_pct = net_ev_per_dollar / (top_multiplier - 1) if top_multiplier > 1 else 0

        # Apply fractional Kelly
        adjusted_kelly_pct = kelly_pct * KELLY_FRACTION

        # Calculate dollar amount
        raw_size = self.current_bankroll * adjusted_kelly_pct

        # Apply constraints
        constrained_size = max(MIN_ENTRY_SIZE, raw_size)
        constrained_size = min(constrained_size, MAX_ENTRY_SIZE)
        constrained_size = min(constrained_size, self.current_bankroll * MAX_BANKROLL_PCT)

        if self.current_bankroll < MIN_ENTRY_SIZE:
            constrained_size = 0

        return {
            "full_kelly_pct": kelly_pct,
            "fractional_kelly_pct": adjusted_kelly_pct,
            "kelly_fraction_used": KELLY_FRACTION,
            "raw_kelly_size": raw_size,
            "recommended_size": round(constrained_size, 2),
            "current_bankroll": self.current_bankroll,
            "bankroll_pct": (constrained_size / self.current_bankroll * 100)
                            if self.current_bankroll > 0 else 0,
            "net_ev_per_dollar": net_ev_per_dollar,
            "is_positive_ev": net_ev_per_dollar > 0,
            "constraints_applied": {
                "min_entry": MIN_ENTRY_SIZE,
                "max_entry": MAX_ENTRY_SIZE,
                "max_bankroll_pct": MAX_BANKROLL_PCT * 100,
            },
        }

    # =========================================================================
    # Stop-Loss / Risk Controls
    # =========================================================================

    def check_stop_loss(self) -> dict:
        """Check all stop-loss conditions. Returns status and any triggered rules."""
        alerts = []
        can_play = True

        # 1. Absolute floor
        if self.current_bankroll < MIN_BANKROLL_FLOOR:
            alerts.append({
                "rule": "MIN_BANKROLL_FLOOR",
                "message": f"Bankroll (${self.current_bankroll:.2f}) is below "
                           f"minimum floor (${MIN_BANKROLL_FLOOR:.2f})",
                "severity": "STOP",
            })
            can_play = False

        # 2. Max drawdown from peak
        if self.drawdown_pct >= MAX_DRAWDOWN_PCT:
            alerts.append({
                "rule": "MAX_DRAWDOWN",
                "message": f"Drawdown {self.drawdown_pct:.1%} exceeds max "
                           f"{MAX_DRAWDOWN_PCT:.0%} (Peak: ${self.peak_bankroll:.2f}, "
                           f"Current: ${self.current_bankroll:.2f})",
                "severity": "STOP",
            })
            can_play = False

        # 3. Session stop-loss
        if abs(self.session_pnl) >= SESSION_STOP_LOSS and self.session_pnl < 0:
            alerts.append({
                "rule": "SESSION_STOP_LOSS",
                "message": f"Session loss (${abs(self.session_pnl):.2f}) hit "
                           f"session stop-loss (${SESSION_STOP_LOSS:.2f})",
                "severity": "STOP",
            })
            can_play = False

        # 4. Weekly loss limit
        weekly_loss = self._calculate_weekly_pnl()
        if weekly_loss <= -WEEKLY_LOSS_LIMIT:
            alerts.append({
                "rule": "WEEKLY_LOSS_LIMIT",
                "message": f"Weekly loss (${abs(weekly_loss):.2f}) hit "
                           f"weekly limit (${WEEKLY_LOSS_LIMIT:.2f})",
                "severity": "STOP",
            })
            can_play = False

        # Warnings (not full stops)
        if self.drawdown_pct >= MAX_DRAWDOWN_PCT * 0.7:
            alerts.append({
                "rule": "DRAWDOWN_WARNING",
                "message": f"Drawdown approaching limit: {self.drawdown_pct:.1%} "
                           f"(limit: {MAX_DRAWDOWN_PCT:.0%})",
                "severity": "WARNING",
            })

        if abs(self.session_pnl) >= SESSION_STOP_LOSS * 0.7 and self.session_pnl < 0:
            alerts.append({
                "rule": "SESSION_WARNING",
                "message": f"Approaching session stop-loss: "
                           f"${abs(self.session_pnl):.2f} / ${SESSION_STOP_LOSS:.2f}",
                "severity": "WARNING",
            })

        return {
            "can_play": can_play,
            "alerts": alerts,
            "current_bankroll": self.current_bankroll,
            "drawdown_pct": self.drawdown_pct,
            "session_pnl": self.session_pnl,
            "weekly_pnl": weekly_loss,
        }

    def _calculate_weekly_pnl(self) -> float:
        """Calculate P&L over the last 7 days."""
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        weekly_pnl = 0.0
        for entry in self.data["entries"]:
            if entry.get("timestamp", "") >= cutoff:
                weekly_pnl += entry.get("pnl", 0)
        return weekly_pnl

    # =========================================================================
    # Entry Recording
    # =========================================================================

    def record_entry(self, entry_fee: float, picks: list,
                     play_type: str = "flex", notes: str = "") -> dict:
        """Record a new entry (before results are known)."""
        entry = {
            "id": len(self.data["entries"]) + 1,
            "timestamp": datetime.now().isoformat(),
            "entry_fee": entry_fee,
            "play_type": play_type,
            "picks": picks,
            "notes": notes,
            "status": "pending",
            "result": None,
            "payout": 0,
            "pnl": -entry_fee,  # Initially a loss until resolved
        }

        self.data["entries"].append(entry)
        self.data["current_bankroll"] -= entry_fee
        self.data["current_session"]["entries"].append(entry["id"])
        self.data["current_session"]["session_pnl"] -= entry_fee
        self.save()

        return entry

    def resolve_entry(self, entry_id: int, correct_picks: int) -> dict:
        """
        Resolve a pending entry with results.

        Args:
            entry_id: The entry ID to resolve
            correct_picks: Number of picks that hit (0-6)
        """
        entry = None
        for e in self.data["entries"]:
            if e["id"] == entry_id:
                entry = e
                break

        if not entry:
            return {"error": f"Entry {entry_id} not found"}

        play_type = entry["play_type"]
        entry_fee = entry["entry_fee"]
        n_picks = len(entry["picks"])

        # Determine payout using new integer-key format
        payout_table = PRIZEPICKS_PAYOUTS_STANDARD.get(f"{play_type}_play", {}).get(n_picks, {})
        multiplier = payout_table.get(correct_picks, 0)
        payout = multiplier * entry_fee

        # Update entry
        entry["status"] = "resolved"
        entry["result"] = f"{correct_picks}/{n_picks}"
        entry["payout"] = payout
        entry["pnl"] = payout - entry_fee

        # Update bankroll (add back the entry fee already deducted, then add payout)
        self.data["current_bankroll"] += payout + entry_fee  # undo the deduction
        self.data["current_bankroll"] -= entry_fee  # re-deduct properly
        # Simpler: just add the payout
        # Wait, we already deducted entry_fee in record_entry. So just add payout.
        self.data["current_bankroll"] = self.data["current_bankroll"] + entry_fee + payout - entry_fee
        # Cleaner approach:
        # current was already reduced by entry_fee. Add back entry_fee (undo), then set pnl.
        # Actually let's just recalculate:
        self.data["current_bankroll"] += payout  # payout includes the entry fee back if won

        # Wait, PrizePicks payouts INCLUDE your entry fee in the multiplier
        # So 25x on $10 = $250 total returned (not $250 + $10)
        # We already deducted $10. If they win $250, net is +$240.
        # Actually re-reading: "25x your entry fee" means you get $250 back total
        # So pnl = 250 - 10 = +240
        # We already did -10 to bankroll. Now add payout (250).
        # Net effect on bankroll: -10 + 250 = +240. Correct!

        # Actually let me re-examine. In record_entry we do:
        # self.data["current_bankroll"] -= entry_fee
        # So bankroll went down by entry_fee.
        # Now in resolve, payout = multiplier * entry_fee (e.g., 25 * 10 = 250)
        # We want final bankroll = original - entry_fee + payout = original + 240
        # Current bankroll is already (original - entry_fee), so:
        # self.data["current_bankroll"] += payout is correct!
        # That gives: (original - 10) + 250 = original + 240 ✓

        # Update the line above - remove the confusing intermediate and just keep:
        # (The += payout line above is the last one that executes, which is correct)

        # Update peak
        if self.data["current_bankroll"] > self.data["peak_bankroll"]:
            self.data["peak_bankroll"] = self.data["current_bankroll"]

        # Update session P&L
        self.data["current_session"]["session_pnl"] += payout  # add payout to session

        self.save()

        return {
            "entry_id": entry_id,
            "result": f"{correct_picks}/{n_picks}",
            "payout": payout,
            "pnl": payout - entry_fee,
            "new_bankroll": self.data["current_bankroll"],
        }

    def start_new_session(self):
        """Archive current session and start a new one."""
        if self.data["current_session"]["entries"]:
            self.data["sessions"].append(self.data["current_session"])

        self.data["current_session"] = {
            "started": datetime.now().isoformat(),
            "entries": [],
            "session_pnl": 0.0,
        }
        self.save()

    def add_deposit(self, amount: float, notes: str = ""):
        """Add funds to bankroll (reload)."""
        self.data["current_bankroll"] += amount
        if self.data["current_bankroll"] > self.data["peak_bankroll"]:
            self.data["peak_bankroll"] = self.data["current_bankroll"]
        self.data["entries"].append({
            "id": len(self.data["entries"]) + 1,
            "timestamp": datetime.now().isoformat(),
            "type": "deposit",
            "amount": amount,
            "notes": notes,
            "pnl": 0,
        })
        self.save()

    # =========================================================================
    # Reporting
    # =========================================================================

    def get_summary(self) -> str:
        """Generate a bankroll summary report."""
        lines = []
        lines.append("=" * 60)
        lines.append("  💰 BANKROLL SUMMARY")
        lines.append("=" * 60)
        lines.append(f"  Starting bankroll:  ${self.data['starting_bankroll']:.2f}")
        lines.append(f"  Current bankroll:   ${self.current_bankroll:.2f}")
        lines.append(f"  Peak bankroll:      ${self.peak_bankroll:.2f}")

        pnl_sign = "+" if self.total_pnl >= 0 else ""
        lines.append(f"  Total P&L:          {pnl_sign}${self.total_pnl:.2f}")
        lines.append(f"  Drawdown from peak: {self.drawdown_pct:.1%}")
        lines.append(f"  Total entries:      {self.total_entries}")

        # Win/loss record
        resolved = [e for e in self.data["entries"]
                     if e.get("status") == "resolved"]
        if resolved:
            wins = sum(1 for e in resolved if e.get("pnl", 0) > 0)
            losses = sum(1 for e in resolved if e.get("pnl", 0) < 0)
            pushes = sum(1 for e in resolved if e.get("pnl", 0) == 0)
            lines.append(f"  Record:             {wins}W - {losses}L - {pushes}P")

            total_wagered = sum(e.get("entry_fee", 0) for e in resolved)
            total_returned = sum(e.get("payout", 0) for e in resolved)
            if total_wagered > 0:
                roi = ((total_returned - total_wagered) / total_wagered) * 100
                lines.append(f"  ROI:                {roi:+.1f}%")

        lines.append("-" * 60)

        # Session info
        session_sign = "+" if self.session_pnl >= 0 else ""
        lines.append(f"  Session P&L:        {session_sign}${self.session_pnl:.2f}")
        lines.append(f"  Weekly P&L:         ${self._calculate_weekly_pnl():.2f}")

        # Stop-loss status
        stop_check = self.check_stop_loss()
        if stop_check["can_play"]:
            lines.append(f"\n  ✅ All risk controls clear — good to play")
        else:
            lines.append(f"\n  🛑 STOP-LOSS TRIGGERED:")
            for alert in stop_check["alerts"]:
                if alert["severity"] == "STOP":
                    lines.append(f"     ❌ {alert['message']}")

        for alert in stop_check["alerts"]:
            if alert["severity"] == "WARNING":
                lines.append(f"  ⚠️  {alert['message']}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def get_entry_history(self, last_n: int = 10) -> str:
        """Show recent entry history."""
        entries = [e for e in self.data["entries"] if e.get("entry_fee")]
        entries = entries[-last_n:]

        if not entries:
            return "  No entries recorded yet."

        lines = []
        lines.append(f"  {'#':>3s}  {'Date':>10s}  {'Type':>6s}  {'Fee':>6s}  "
                      f"{'Result':>7s}  {'Payout':>8s}  {'P&L':>8s}")
        lines.append(f"  {'─'*3}  {'─'*10}  {'─'*6}  {'─'*6}  "
                      f"{'─'*7}  {'─'*8}  {'─'*8}")

        for e in entries:
            if e.get("type") == "deposit":
                continue
            date = e.get("timestamp", "")[:10]
            ptype = e.get("play_type", "?")[:6]
            fee = f"${e.get('entry_fee', 0):.2f}"
            result = e.get("result", "pending")
            payout = f"${e.get('payout', 0):.2f}"
            pnl = e.get("pnl", 0)
            pnl_str = f"${pnl:+.2f}"
            lines.append(f"  {e['id']:>3d}  {date:>10s}  {ptype:>6s}  "
                          f"{fee:>6s}  {result:>7s}  {payout:>8s}  {pnl_str:>8s}")

        return "\n".join(lines)

    def reset(self, starting_bankroll: float = None):
        """Reset bankroll to starting state."""
        self.data = self._initialize_data()
        if starting_bankroll:
            self.data["starting_bankroll"] = starting_bankroll
            self.data["current_bankroll"] = starting_bankroll
            self.data["peak_bankroll"] = starting_bankroll
        self.save()


# Fix the resolve_entry bankroll calculation
# Let me rewrite it cleanly:
class BankrollManager(BankrollManager):
    def resolve_entry(self, entry_id: int, correct_picks: int) -> dict:
        entry = None
        for e in self.data["entries"]:
            if e["id"] == entry_id:
                entry = e
                break

        if not entry:
            return {"error": f"Entry {entry_id} not found"}

        play_type = entry["play_type"]
        entry_fee = entry["entry_fee"]
        n_picks = len(entry["picks"])

        payouts = PRIZEPICKS_PAYOUTS_STANDARD.get(f"{play_type}_play", {}).get(n_picks, {})
        multiplier = payouts.get(correct_picks, 0)
        payout = multiplier * entry_fee  # Total returned to you

        entry["status"] = "resolved"
        entry["result"] = f"{correct_picks}/{n_picks}"
        entry["payout"] = payout
        entry["pnl"] = payout - entry_fee

        # Bankroll was already reduced by entry_fee in record_entry.
        # Now add back the payout (which includes original stake if you won).
        self.data["current_bankroll"] += payout

        if self.data["current_bankroll"] > self.data["peak_bankroll"]:
            self.data["peak_bankroll"] = self.data["current_bankroll"]

        self.data["current_session"]["session_pnl"] += payout

        self.save()

        return {
            "entry_id": entry_id,
            "result": f"{correct_picks}/{n_picks}",
            "payout": payout,
            "pnl": payout - entry_fee,
            "new_bankroll": self.data["current_bankroll"],
        }


if __name__ == "__main__":
    bm = BankrollManager("test_bankroll.json")
    bm.reset(100.00)
    print(bm.get_summary())

    # Example: calculate kelly sizing
    sizing = bm.kelly_bet_size(win_prob=0.56, play_type="flex", n_picks=6)
    print(f"\n  Kelly sizing for 56% win prob:")
    print(f"  Full Kelly:     {sizing['full_kelly_pct']:.2%}")
    print(f"  Quarter Kelly:  {sizing['fractional_kelly_pct']:.2%}")
    print(f"  Recommended:    ${sizing['recommended_size']:.2f}")
    print(f"  Bankroll %:     {sizing['bankroll_pct']:.1f}%")

    # Clean up test file
    os.remove("test_bankroll.json")
