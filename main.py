"""
Fantasy Golf Pick 6 Tool
=========================
Main CLI application for PrizePicks pick 6 bankroll management,
EV calculation, and DataGolf-powered pick analysis.

Usage: python main.py
"""

import sys
import os
from datetime import datetime

from config import (
    DATAGOLF_API_KEY, STARTING_BANKROLL, KELLY_FRACTION,
    BREAKEVEN_RATES, PRIZEPICKS_PAYOUTS
)
from datagolf_client import DataGolfClient
from prizepicks_ev import (
    calculate_ev_uniform, calculate_ev_variable, compare_flex_vs_power,
    ev_sensitivity_table, format_ev_report, find_breakeven_prob
)
from bankroll_manager import BankrollManager


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         ⛳  FANTASY GOLF PICK 6 TOOL  ⛳               ║")
    print("║         PrizePicks Bankroll & EV Manager                ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()


def print_menu():
    print("  ┌─────────────────────────────────────────┐")
    print("  │  MAIN MENU                              │")
    print("  ├─────────────────────────────────────────┤")
    print("  │  1. 📊 Bankroll Summary                 │")
    print("  │  2. 🧮 EV Calculator                    │")
    print("  │  3. 📏 Kelly Criterion Sizing            │")
    print("  │  4. 📝 Record an Entry                  │")
    print("  │  5. ✅ Resolve Entry (enter results)     │")
    print("  │  6. 📈 EV Sensitivity Table             │")
    print("  │  7. ⛳ DataGolf: Tournament Preview      │")
    print("  │  8. 🏆 DataGolf: Player Rankings        │")
    print("  │  9. 🎯 DataGolf: Skill Ratings          │")
    print("  │ 10. 🔍 DataGolf: Pre-Tournament Picks   │")
    print("  │ 11. 📜 Entry History                    │")
    print("  │ 12. 🛑 Check Stop-Loss Status           │")
    print("  │ 13. 💵 Add Deposit                      │")
    print("  │ 14. 🔄 New Session                      │")
    print("  │ 15. ⚙️  Settings Info                    │")
    print("  │  0. 🚪 Exit                             │")
    print("  └─────────────────────────────────────────┘")
    print()


# =============================================================================
# Menu Handlers
# =============================================================================

def handle_bankroll_summary(bm: BankrollManager):
    print(bm.get_summary())


def handle_ev_calculator(bm: BankrollManager):
    print("\n  === EV CALCULATOR ===")
    print("  Calculate expected value for a pick 6 lineup.\n")

    mode = input("  Uniform probability for all picks? (y/n): ").strip().lower()

    if mode == "y":
        try:
            wp = float(input("  Estimated win probability per pick (e.g., 0.56 or 56): "))
            if wp > 1:
                wp = wp / 100.0
            entry = float(input(f"  Entry fee (current bankroll: ${bm.current_bankroll:.2f}): $"))
        except ValueError:
            print("  ❌ Invalid input.")
            return

        comparison = compare_flex_vs_power([wp] * 6, entry)
        print(format_ev_report(comparison["flex"]))
        print(format_ev_report(comparison["power"]))
        print(f"\n  💡 Recommendation: {comparison['recommendation'].upper()} PLAY")
        print(f"     EV advantage: ${comparison['ev_difference']:+.2f}")

    else:
        print("  Enter win probability for each of your 6 picks:")
        probs = []
        for i in range(6):
            try:
                p = float(input(f"    Pick {i+1} win prob (e.g., 0.57 or 57): "))
                if p > 1:
                    p = p / 100.0
                probs.append(p)
            except ValueError:
                print("  ❌ Invalid input.")
                return

        try:
            entry = float(input(f"  Entry fee (current bankroll: ${bm.current_bankroll:.2f}): $"))
        except ValueError:
            print("  ❌ Invalid input.")
            return

        comparison = compare_flex_vs_power(probs, entry)
        print(format_ev_report(comparison["flex"]))
        print(format_ev_report(comparison["power"]))
        print(f"\n  💡 Recommendation: {comparison['recommendation'].upper()} PLAY")
        print(f"     EV advantage: ${comparison['ev_difference']:+.2f}")


def handle_kelly_sizing(bm: BankrollManager):
    print("\n  === KELLY CRITERION ENTRY SIZING ===\n")

    try:
        wp = float(input("  Estimated avg win probability per pick (e.g., 0.56 or 56): "))
        if wp > 1:
            wp = wp / 100.0
    except ValueError:
        print("  ❌ Invalid input.")
        return

    play_type = input("  Play type (flex/power) [flex]: ").strip().lower() or "flex"
    if play_type not in ("flex", "power"):
        play_type = "flex"

    sizing = bm.kelly_bet_size(wp, play_type, 6)

    print(f"\n  {'='*50}")
    print(f"  Kelly Criterion Entry Sizing")
    print(f"  {'='*50}")
    print(f"  Current bankroll:    ${sizing['current_bankroll']:.2f}")
    print(f"  Win prob per leg:    {wp:.1%}")
    print(f"  Play type:           {play_type}")
    print(f"  Net EV per $1:       ${sizing['net_ev_per_dollar']:+.4f}")
    print(f"  {'─'*50}")
    print(f"  Full Kelly:          {sizing['full_kelly_pct']:.2%} "
          f"(${sizing['current_bankroll'] * sizing['full_kelly_pct']:.2f})")
    print(f"  {KELLY_FRACTION:.0%} Kelly (used):    {sizing['fractional_kelly_pct']:.2%} "
          f"(${sizing['raw_kelly_size']:.2f})")
    print(f"  {'─'*50}")
    print(f"  ✅ RECOMMENDED SIZE:  ${sizing['recommended_size']:.2f} "
          f"({sizing['bankroll_pct']:.1f}% of bankroll)")
    print(f"  {'='*50}")

    if not sizing["is_positive_ev"]:
        print(f"\n  ⚠️  This is NEGATIVE EV. Kelly says don't bet.")
        be = BREAKEVEN_RATES.get(f"6_pick_{play_type}", 0)
        print(f"     Need >{be:.1%} per leg to break even on {play_type}.")


def handle_record_entry(bm: BankrollManager):
    print("\n  === RECORD NEW ENTRY ===\n")

    # Check stop-loss first
    stop_check = bm.check_stop_loss()
    if not stop_check["can_play"]:
        print("  🛑 STOP-LOSS TRIGGERED — Cannot record new entries.")
        for alert in stop_check["alerts"]:
            if alert["severity"] == "STOP":
                print(f"     ❌ {alert['message']}")
        print("     Start a new session or add a deposit to continue.")
        return

    for alert in stop_check["alerts"]:
        if alert["severity"] == "WARNING":
            print(f"  ⚠️  {alert['message']}")

    try:
        entry_fee = float(input(f"  Entry fee (bankroll: ${bm.current_bankroll:.2f}): $"))
        if entry_fee > bm.current_bankroll:
            print("  ❌ Entry fee exceeds bankroll.")
            return
    except ValueError:
        print("  ❌ Invalid input.")
        return

    play_type = input("  Play type (flex/power) [flex]: ").strip().lower() or "flex"

    print("  Enter your 6 picks (player names or descriptions):")
    picks = []
    for i in range(6):
        pick = input(f"    Pick {i+1}: ").strip()
        if not pick:
            pick = f"Pick {i+1}"
        picks.append(pick)

    notes = input("  Notes (optional): ").strip()

    entry = bm.record_entry(entry_fee, picks, play_type, notes)
    print(f"\n  ✅ Entry #{entry['id']} recorded!")
    print(f"     Fee: ${entry_fee:.2f} | Type: {play_type} | Picks: {len(picks)}")
    print(f"     Remaining bankroll: ${bm.current_bankroll:.2f}")


def handle_resolve_entry(bm: BankrollManager):
    print("\n  === RESOLVE ENTRY ===\n")

    # Show pending entries
    pending = [e for e in bm.data["entries"]
               if e.get("status") == "pending"]
    if not pending:
        print("  No pending entries to resolve.")
        return

    print("  Pending entries:")
    for e in pending:
        print(f"    #{e['id']}: ${e['entry_fee']:.2f} {e['play_type']} — "
              f"{', '.join(e['picks'][:3])}...")

    try:
        entry_id = int(input("\n  Entry # to resolve: "))
        correct = int(input("  How many picks correct (0-6): "))
        if correct < 0 or correct > 6:
            print("  ❌ Must be 0-6.")
            return
    except ValueError:
        print("  ❌ Invalid input.")
        return

    result = bm.resolve_entry(entry_id, correct)
    if "error" in result:
        print(f"  ❌ {result['error']}")
        return

    pnl_sign = "+" if result["pnl"] >= 0 else ""
    emoji = "🎉" if result["pnl"] > 0 else "😤" if result["pnl"] < 0 else "😐"
    print(f"\n  {emoji} Entry #{result['entry_id']} resolved: {result['result']}")
    print(f"     Payout: ${result['payout']:.2f}")
    print(f"     P&L: {pnl_sign}${result['pnl']:.2f}")
    print(f"     New bankroll: ${result['new_bankroll']:.2f}")


def handle_sensitivity_table(bm: BankrollManager):
    print("\n  === EV SENSITIVITY TABLE ===")
    print("  Shows EV at different win probabilities for a $10 entry.\n")

    for play_type in ["flex", "power"]:
        be = find_breakeven_prob(6, play_type)
        print(f"  6-Pick {play_type.upper()} Play (break-even: {be:.2%})")
        print(f"  {'Win%':>6s}  {'Net EV':>9s}  {'ROI':>8s}  {'Status':>8s}")
        print(f"  {'─'*6}  {'─'*9}  {'─'*8}  {'─'*8}")

        table = ev_sensitivity_table(6, 10.0, play_type)
        for row in table:
            status = "  +EV ✅" if row["is_positive"] else "  -EV ❌"
            print(f"  {row['win_prob_pct']:>5d}%  ${row['net_ev']:>+8.2f}  "
                  f"{row['roi_pct']:>+7.1f}%{status}")
        print()


def handle_tournament_preview(dg: DataGolfClient):
    print("\n  === TOURNAMENT PREVIEW ===\n")

    print("  Fetching upcoming tournament info...")
    field = dg.get_field_updates()

    if not field:
        print("  ❌ Could not fetch field data. Check your API key.")
        return

    # Display tournament info
    event_name = field.get("event_name", "Unknown Event")
    course = field.get("course", "Unknown Course")
    print(f"  🏌️ {event_name}")
    print(f"  📍 {course}")
    print(f"  {'─'*50}")

    # Show field
    field_list = field.get("field", [])
    if field_list:
        print(f"  Field size: {len(field_list)} players")
        print(f"\n  Top players in field:")
        # Sort by DG ranking if available
        for i, player in enumerate(field_list[:30]):
            name = player.get("player_name", "Unknown")
            dg_id = player.get("dg_id", "")
            r1_tee = player.get("r1_teetime", "")
            print(f"    {i+1:>3d}. {name:<30s} Tee: {r1_tee}")
    else:
        print("  No field data available yet.")


def handle_player_rankings(dg: DataGolfClient):
    print("\n  === DATAGOLF PLAYER RANKINGS ===\n")

    print("  Fetching rankings...")
    rankings = dg.get_rankings()

    if not rankings:
        print("  ❌ Could not fetch rankings.")
        return

    rank_list = rankings if isinstance(rankings, list) else rankings.get("rankings", [])

    print(f"  {'Rank':>5s}  {'Player':<30s}  {'DG Rank':>8s}  {'Skill':>8s}")
    print(f"  {'─'*5}  {'─'*30}  {'─'*8}  {'─'*8}")

    for i, p in enumerate(rank_list[:50]):
        name = p.get("player_name", "Unknown")
        dg_rank = p.get("datagolf_rank", i+1)
        skill = p.get("dg_skill_estimate", "N/A")
        if isinstance(skill, (int, float)):
            skill = f"{skill:.2f}"
        print(f"  {dg_rank:>5}  {name:<30s}  {str(dg_rank):>8s}  {str(skill):>8s}")


def handle_skill_ratings(dg: DataGolfClient):
    print("\n  === DATAGOLF SKILL RATINGS ===\n")

    print("  Fetching skill ratings...")
    skills = dg.get_skill_ratings()

    if not skills:
        print("  ❌ Could not fetch skill ratings.")
        return

    skill_list = skills if isinstance(skills, list) else skills.get("rankings", [])

    print(f"  {'Player':<25s}  {'OTT':>6s}  {'APP':>6s}  {'ARG':>6s}  "
          f"{'Putt':>6s}  {'Total':>6s}")
    print(f"  {'─'*25}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*6}")

    for p in skill_list[:40]:
        name = p.get("player_name", "Unknown")[:25]
        ott = p.get("off_the_tee", "N/A")
        app = p.get("approach", "N/A")
        arg = p.get("around_the_green", "N/A")
        putt = p.get("putting", "N/A")
        total = p.get("sg_total", "N/A")

        def fmt(v):
            return f"{v:>6.2f}" if isinstance(v, (int, float)) else f"{str(v):>6s}"

        print(f"  {name:<25s}  {fmt(ott)}  {fmt(app)}  {fmt(arg)}  "
              f"{fmt(putt)}  {fmt(total)}")


def handle_pretournament_picks(dg: DataGolfClient, bm: BankrollManager):
    print("\n  === PRE-TOURNAMENT PICK ANALYSIS ===\n")

    print("  Fetching pre-tournament predictions...")
    preds = dg.get_pre_tournament_predictions()

    if not preds:
        print("  ❌ Could not fetch predictions. Check your API key.")
        return

    pred_list = preds if isinstance(preds, list) else preds.get("rankings", [])

    print(f"  {'#':>3s}  {'Player':<28s}  {'Win%':>6s}  {'T5%':>6s}  "
          f"{'T10%':>6s}  {'T20%':>6s}  {'MC%':>6s}")
    print(f"  {'─'*3}  {'─'*28}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*6}")

    for i, p in enumerate(pred_list[:50]):
        name = p.get("player_name", "Unknown")[:28]
        win = p.get("win_prob", 0)
        t5 = p.get("top_5", 0) or p.get("top_5_prob", 0)
        t10 = p.get("top_10", 0) or p.get("top_10_prob", 0)
        t20 = p.get("top_20", 0) or p.get("top_20_prob", 0)
        mc = p.get("make_cut", 0) or p.get("make_cut_prob", 0)

        def fmt_pct(v):
            if isinstance(v, (int, float)):
                return f"{v*100:>5.1f}%" if v < 1 else f"{v:>5.1f}%"
            return f"{'N/A':>6s}"

        print(f"  {i+1:>3d}  {name:<28s}  {fmt_pct(win)}  {fmt_pct(t5)}  "
              f"{fmt_pct(t10)}  {fmt_pct(t20)}  {fmt_pct(mc)}")

    print(f"\n  💡 TIP: Use these probabilities to estimate your pick win rates,")
    print(f"     then run the EV Calculator (option 2) or Kelly Sizing (option 3).")


def handle_entry_history(bm: BankrollManager):
    print("\n  === ENTRY HISTORY (Last 15) ===\n")
    print(bm.get_entry_history(15))


def handle_stop_loss_check(bm: BankrollManager):
    print("\n  === STOP-LOSS STATUS ===\n")
    status = bm.check_stop_loss()

    if status["can_play"]:
        print("  ✅ All clear — you can play!")
    else:
        print("  🛑 STOP-LOSS TRIGGERED — Do not enter new plays!")

    print(f"\n  Current bankroll:    ${status['current_bankroll']:.2f}")
    print(f"  Drawdown from peak:  {status['drawdown_pct']:.1%}")
    print(f"  Session P&L:         ${status['session_pnl']:.2f}")
    print(f"  Weekly P&L:          ${status['weekly_pnl']:.2f}")

    if status["alerts"]:
        print("\n  Alerts:")
        for alert in status["alerts"]:
            emoji = "❌" if alert["severity"] == "STOP" else "⚠️"
            print(f"    {emoji} [{alert['rule']}] {alert['message']}")
    else:
        print("\n  No alerts. 👍")


def handle_deposit(bm: BankrollManager):
    print("\n  === ADD DEPOSIT ===\n")
    try:
        amount = float(input("  Deposit amount: $"))
        if amount <= 0:
            print("  ❌ Must be positive.")
            return
    except ValueError:
        print("  ❌ Invalid input.")
        return

    notes = input("  Notes (optional): ").strip()
    bm.add_deposit(amount, notes)
    print(f"\n  ✅ Deposited ${amount:.2f}")
    print(f"     New bankroll: ${bm.current_bankroll:.2f}")


def handle_new_session(bm: BankrollManager):
    print("\n  Starting new session...")
    bm.start_new_session()
    print("  ✅ New session started. Previous session archived.")


def handle_settings_info():
    print("\n  === CURRENT SETTINGS ===\n")
    print(f"  Starting bankroll:     ${STARTING_BANKROLL:.2f}")
    print(f"  Kelly fraction:        {KELLY_FRACTION:.0%}")
    print(f"  Session stop-loss:     ${20:.2f}")
    print(f"  Max drawdown:          {0.30:.0%}")
    print(f"  Weekly loss limit:     ${30:.2f}")
    print(f"  Min bankroll floor:    ${20:.2f}")
    print(f"  DataGolf API key:      {'Configured ✅' if DATAGOLF_API_KEY != 'YOUR_API_KEY_HERE' else 'Not set ❌'}")
    print(f"\n  PrizePicks 6-Pick Payouts:")
    print(f"    Flex:  6/6 = 25x  |  5/6 = 2x  |  4/6 = 0.4x")
    print(f"    Power: 6/6 = 37.5x (all or nothing)")
    print(f"\n  Break-even per-leg win rates:")
    for k, v in BREAKEVEN_RATES.items():
        print(f"    {k}: {v:.2%}")
    print(f"\n  Edit config.py to change these settings.")


# =============================================================================
# Main Loop
# =============================================================================

def main():
    bm = BankrollManager()
    dg = DataGolfClient()

    clear_screen()
    print_header()

    # Quick stop-loss check on startup
    status = bm.check_stop_loss()
    if not status["can_play"]:
        print("  🛑 WARNING: Stop-loss conditions are active!")
        for alert in status["alerts"]:
            if alert["severity"] == "STOP":
                print(f"     ❌ {alert['message']}")
        print()

    while True:
        print_menu()
        choice = input("  Enter choice: ").strip()

        try:
            if choice == "0":
                print("\n  👋 Good luck out there! ⛳\n")
                break
            elif choice == "1":
                handle_bankroll_summary(bm)
            elif choice == "2":
                handle_ev_calculator(bm)
            elif choice == "3":
                handle_kelly_sizing(bm)
            elif choice == "4":
                handle_record_entry(bm)
            elif choice == "5":
                handle_resolve_entry(bm)
            elif choice == "6":
                handle_sensitivity_table(bm)
            elif choice == "7":
                handle_tournament_preview(dg)
            elif choice == "8":
                handle_player_rankings(dg)
            elif choice == "9":
                handle_skill_ratings(dg)
            elif choice == "10":
                handle_pretournament_picks(dg, bm)
            elif choice == "11":
                handle_entry_history(bm)
            elif choice == "12":
                handle_stop_loss_check(bm)
            elif choice == "13":
                handle_deposit(bm)
            elif choice == "14":
                handle_new_session(bm)
            elif choice == "15":
                handle_settings_info()
            else:
                print("  ❌ Invalid choice. Try again.")
        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!\n")
            break
        except Exception as e:
            print(f"\n  ❌ Error: {e}")

        input("\n  Press Enter to continue...")


if __name__ == "__main__":
    main()
