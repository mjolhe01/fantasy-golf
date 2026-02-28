"""
prizepicks_ev.py

Simple CLI utility to compute expected value (EV) for PrizePicks-style parlays
from a list/table of win probabilities. The script defaults to a set of payout
multipliers for 2-6 picks but lets you override them.

Usage examples:
  - Run and paste 'name,prob' lines (prob as decimal or percent) when prompted
  - Provide a CSV file: python prizepicks_ev.py --file pp_probs.csv
  - Override payouts: python prizepicks_ev.py --mult "{\"2\":1.85,\"3\":2.6}"

Output: top combos per parlay size with probability of hitting, payout multiplier,
net EV per $1 stake, and ROI%.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
from math import prod
from typing import Dict, List, Tuple


DEFAULT_PAYOUTS: Dict[int, float] = {
    2: 1.80,
    3: 2.60,
    4: 4.40,
    5: 7.00,
    6: 12.00,
}


def parse_probs_from_file(path: str) -> List[Tuple[str, float]]:
    rows: List[Tuple[str, float]] = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        for r in reader:
            if not r:
                continue
            if len(r) == 1:
                name = f"pick_{len(rows)+1}"
                prob = r[0]
            else:
                name, prob = r[0], r[1]
            p = parse_prob_value(prob)
            rows.append((name, p))
    return rows


def parse_prob_value(v: str) -> float:
    v = str(v).strip()
    if not v:
        return 0.0
    # allow percent like '45%' or '45'
    if v.endswith("%"):
        return float(v[:-1]) / 100.0
    val = float(v)
    return val if val <= 1.0 else val / 100.0


def prompt_for_probs() -> List[Tuple[str, float]]:
    print("Enter picks, one per line, as: name,prob (prob as decimal or percent). Empty line to finish.")
    rows: List[Tuple[str, float]] = []
    while True:
        try:
            line = input().strip()
        except EOFError:
            break
        if not line:
            break
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 1:
            name = f"pick_{len(rows)+1}"
            prob = parts[0]
        else:
            name, prob = parts[0], parts[1]
        rows.append((name, parse_prob_value(prob)))
    return rows


def compute_ev_for_combo(probs: List[float], payout: float) -> Tuple[float, float]:
    p_win = prod(probs)
    # Return net EV per $1 stake. We assume `payout` is the return multiplier (including stake).
    ev_net = p_win * payout - 1.0
    roi_pct = (p_win * payout - 1.0) * 100.0
    return p_win, ev_net if ev_net is not None else 0.0, roi_pct


def format_pct(x: float) -> str:
    return f"{x*100:.2f}%"


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute PrizePicks EVs from win probabilities")
    ap.add_argument("--file", "-f", help="CSV file with rows 'name,prob' (prob decimal or percent)")
    ap.add_argument(
        "--mult",
        help="JSON string or path to JSON file with payout multipliers, e.g. '{"2":1.8, "3":2.6}'",
    )
    ap.add_argument("--top", type=int, default=10, help="How many top combos to show per parlay size")
    args = ap.parse_args()

    if args.mult:
        try:
            if args.mult.strip().startswith("{"):
                payouts = {int(k): float(v) for k, v in json.loads(args.mult).items()}
            else:
                with open(args.mult) as f:
                    payouts = {int(k): float(v) for k, v in json.load(f).items()}
        except Exception as e:
            print("Failed to parse multipliers, using defaults:", e)
            payouts = DEFAULT_PAYOUTS.copy()
    else:
        payouts = DEFAULT_PAYOUTS.copy()

    if args.file:
        picks = parse_probs_from_file(args.file)
    else:
        picks = prompt_for_probs()

    if not picks:
        print("No picks provided. Exiting.")
        return

    names, probs = zip(*picks)
    n_picks = len(probs)

    print(f"Loaded {n_picks} picks.")

    max_k = min(6, n_picks)
    for k in range(2, max_k + 1):
        payout = payouts.get(k)
        if payout is None:
            print(f"No payout multiplier for {k}-leg parlays; skipping.")
            continue
        combos = []
        for combo in itertools.combinations(range(n_picks), k):
            combo_probs = [probs[i] for i in combo]
            p_win = prod(combo_probs)
            ev_net = p_win * payout - 1.0
            roi_pct = ev_net * 100.0
            combos.append((combo, p_win, ev_net, roi_pct))

        combos.sort(key=lambda x: x[2], reverse=True)
        print(f"\nTop {min(args.top, len(combos))} EV combos for {k}-leg parlays (payout={payout}x):")
        print("ev_net\tROI%\tp_hit\tcombo_names\tcombo_probs")
        for combo, p_win, ev_net, roi_pct in combos[: args.top]:
            combo_names = ",".join(names[i] for i in combo)
            combo_p = ",".join(f"{probs[i]:.3f}" for i in combo)
            print(f"{ev_net:+.4f}\t{roi_pct:+.2f}\t{p_win:.6f}\t{combo_names}\t{combo_p}")


if __name__ == "__main__":
    main()
"""
PrizePicks EV Calculator (2-6 Picks)
======================================
Calculates expected value for PrizePicks lineups across all
pick sizes (2-6), with support for standard, golf/correlated,
and fully custom multiplier inputs.
"""

from math import comb
from typing import List, Dict, Optional
from config import PRIZEPICKS_PAYOUTS_STANDARD, PRIZEPICKS_PAYOUTS_GOLF, BREAKEVEN_RATES


def binomial_prob(n: int, k: int, p: float) -> float:
    """Probability of exactly k successes in n independent trials with prob p each."""
    return comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def prob_exactly_k_correct(probs: List[float], k: int) -> float:
    """DP to compute P(exactly k out of n correct) with varying probabilities."""
    n = len(probs)
    dp = [[0.0] * (n + 1) for _ in range(n + 1)]
    dp[0][0] = 1.0
    for i in range(1, n + 1):
        p = probs[i - 1]
        for j in range(i + 1):
            dp[i][j] = dp[i-1][j] * (1 - p)
            if j > 0:
                dp[i][j] += dp[i-1][j-1] * p
    return dp[n][k]


def get_payout_table(n_picks: int, play_type: str, preset: str = "standard",
                      custom_multipliers: Optional[Dict[int, float]] = None) -> Dict[int, float]:
    """
    Get the payout multiplier table for a given configuration.

    Args:
        n_picks: Number of picks (2-6)
        play_type: 'flex' or 'power'
        preset: 'standard', 'golf', or 'custom'
        custom_multipliers: Dict mapping {correct_picks: multiplier}
                           e.g. {6: 21.0, 5: 1.75, 4: 0.35}

    Returns:
        Dict of {correct_picks: multiplier}
    """
    if preset == "custom" and custom_multipliers:
        return custom_multipliers

    if preset == "golf":
        source = PRIZEPICKS_PAYOUTS_GOLF
    else:
        source = PRIZEPICKS_PAYOUTS_STANDARD

    key = f"{play_type}_play"
    return source.get(key, {}).get(n_picks, {})


def calculate_ev(n_picks: int, pick_probs: List[float], entry_fee: float,
                  play_type: str = "flex", preset: str = "standard",
                  custom_multipliers: Optional[Dict[int, float]] = None) -> dict:
    """
    Calculate EV for any pick size (2-6) with any payout structure.

    Args:
        n_picks: Number of picks (2-6)
        pick_probs: List of win probabilities (length must match n_picks)
        entry_fee: Dollar amount wagered
        play_type: 'flex' or 'power'
        preset: 'standard', 'golf', or 'custom'
        custom_multipliers: For custom preset, dict of {correct: multiplier}

    Returns:
        Comprehensive EV breakdown dict
    """
    assert len(pick_probs) == n_picks, f"Expected {n_picks} probs, got {len(pick_probs)}"

    payouts = get_payout_table(n_picks, play_type, preset, custom_multipliers)
    uniform = len(set(f"{p:.6f}" for p in pick_probs)) == 1

    total_ev = 0
    breakdown = []

    for k in range(n_picks + 1):
        multiplier = payouts.get(k, 0)
        if uniform:
            prob = binomial_prob(n_picks, k, pick_probs[0])
        else:
            prob = prob_exactly_k_correct(pick_probs, k)

        payout = multiplier * entry_fee
        ev_contribution = prob * payout
        total_ev += ev_contribution

        breakdown.append({
            "correct": k,
            "label": f"{k}/{n_picks}",
            "probability": prob,
            "multiplier": multiplier,
            "payout": payout,
            "ev_contribution": ev_contribution,
        })

    net_ev = total_ev - entry_fee
    roi = (net_ev / entry_fee) * 100 if entry_fee > 0 else 0

    return {
        "play_type": play_type,
        "preset": preset,
        "n_picks": n_picks,
        "pick_probabilities": pick_probs,
        "avg_win_prob": sum(pick_probs) / len(pick_probs),
        "entry_fee": entry_fee,
        "gross_ev": total_ev,
        "net_ev": net_ev,
        "roi_pct": roi,
        "breakdown": breakdown,
        "is_positive_ev": net_ev > 0,
        "multipliers_used": payouts,
    }


def compare_flex_vs_power(n_picks: int, pick_probs: List[float], entry_fee: float,
                           preset: str = "standard",
                           custom_flex: Optional[Dict[int, float]] = None,
                           custom_power: Optional[Dict[int, float]] = None) -> dict:
    """Compare Flex Play vs Power Play for the same picks."""
    flex = calculate_ev(n_picks, pick_probs, entry_fee, "flex", preset, custom_flex)
    power = calculate_ev(n_picks, pick_probs, entry_fee, "power", preset, custom_power)

    flex_available = bool(get_payout_table(n_picks, "flex", preset, custom_flex))
    recommendation = "flex" if (flex_available and flex["net_ev"] > power["net_ev"]) else "power"

    if not flex_available:
        flex["note"] = f"Flex not available for {n_picks}-pick"

    return {
        "flex": flex,
        "power": power,
        "recommendation": recommendation,
        "flex_available": flex_available,
        "ev_difference": (flex["net_ev"] - power["net_ev"]) if flex_available else 0,
    }


def find_breakeven_prob(n_picks: int, play_type: str, preset: str = "standard",
                         custom_multipliers: Optional[Dict[int, float]] = None) -> float:
    """Binary search for the per-leg win probability that gives 0 EV."""
    payouts = get_payout_table(n_picks, play_type, preset, custom_multipliers)
    if not payouts:
        return 1.0  # No payouts = impossible to break even

    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        probs = [mid] * n_picks
        result = calculate_ev(n_picks, probs, 100, play_type, preset, custom_multipliers)
        if result["net_ev"] < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def ev_sensitivity_table(n_picks: int = 6, entry_fee: float = 10.0,
                          play_type: str = "flex", preset: str = "standard",
                          custom_multipliers: Optional[Dict[int, float]] = None) -> List[dict]:
    """Generate a table showing EV at different win probabilities."""
    rows = []
    for wp_pct in range(48, 66, 1):
        wp = wp_pct / 100.0
        probs = [wp] * n_picks
        result = calculate_ev(n_picks, probs, entry_fee, play_type, preset, custom_multipliers)
        rows.append({
            "win_prob_pct": wp_pct,
            "net_ev": result["net_ev"],
            "roi_pct": result["roi_pct"],
            "is_positive": result["is_positive_ev"],
        })
    return rows


def format_ev_report(result: dict) -> str:
    """Pretty-print an EV calculation result."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  {result['n_picks']}-Pick {result['play_type'].upper()} "
                 f"({result['preset'].upper()}) EV Report")
    lines.append("=" * 60)
    lines.append(f"  Pick win probs: {[f'{p:.1%}' for p in result['pick_probabilities']]}")
    lines.append(f"  Average prob:   {result['avg_win_prob']:.2%}")
    lines.append(f"  Entry fee:      ${result['entry_fee']:.2f}")
    mults = {k: v for k, v in result['multipliers_used'].items() if v > 0}
    lines.append(f"  Multipliers:    {mults}")
    lines.append("-" * 60)

    for item in result["breakdown"]:
        if item["multiplier"] > 0:
            lines.append(
                f"  {item['label']:>5s}: "
                f"P={item['probability']:.4%}  "
                f"× {item['multiplier']:>6.2f}x  "
                f"Payout=${item['payout']:>8.2f}  "
                f"EV=${item['ev_contribution']:>7.2f}"
            )

    lines.append("-" * 60)
    ev_sign = "+" if result["net_ev"] >= 0 else ""
    emoji = "✅" if result["is_positive_ev"] else "❌"
    lines.append(f"  Net EV:  {ev_sign}${result['net_ev']:.2f}   "
                 f"ROI: {ev_sign}{result['roi_pct']:.1f}%  {emoji}")
    lines.append("=" * 60)
    return "\n".join(lines)


# Legacy compatibility wrappers
def calculate_ev_uniform(n_picks, win_prob, entry_fee, play_type="flex"):
    return calculate_ev(n_picks, [win_prob] * n_picks, entry_fee, play_type, "standard")

def calculate_ev_variable(pick_probs, entry_fee, play_type="flex"):
    return calculate_ev(len(pick_probs), pick_probs, entry_fee, play_type, "standard")


if __name__ == "__main__":
    print("\n=== Standard Payouts: All Pick Sizes ===\n")
    for n in range(2, 7):
        for ptype in ["power", "flex"]:
            payouts = get_payout_table(n, ptype, "standard")
            if payouts:
                be = find_breakeven_prob(n, ptype, "standard")
                print(f"  {n}-Pick {ptype.upper():>5s}: {payouts}  BE={be:.2%}")

    print("\n=== Golf/Correlated Payouts ===\n")
    for n in range(2, 7):
        for ptype in ["power", "flex"]:
            payouts = get_payout_table(n, ptype, "golf")
            if payouts:
                be = find_breakeven_prob(n, ptype, "golf")
                print(f"  {n}-Pick {ptype.upper():>5s}: {payouts}  BE={be:.2%}")

    print("\n=== Custom 2.7x Power 2-pick ===\n")
    result = calculate_ev(2, [0.56, 0.58], 5.00, "power", "custom", {2: 2.7})
    print(format_ev_report(result))

    print("\n=== 6-Pick Flex: Standard vs Golf ===\n")
    probs = [0.56] * 6
    std = calculate_ev(6, probs, 10.00, "flex", "standard")
    golf = calculate_ev(6, probs, 10.00, "flex", "golf")
    print(f"  Standard: ${std['net_ev']:+.2f} ({std['roi_pct']:+.1f}% ROI)")
    print(f"  Golf:     ${golf['net_ev']:+.2f} ({golf['roi_pct']:+.1f}% ROI)")
