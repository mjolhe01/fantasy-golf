"""
Fantasy Golf Pick 6 Tool - Configuration
==========================================
Update these settings before first use.
"""

import os
import json

# =============================================================================
# DataGolf API
# =============================================================================
# Sign up at https://datagolf.com/subscribe (Scratch Plus plan for API access)
# Find your key at https://datagolf.com/api-access
DATAGOLF_API_KEY = os.environ.get("DATAGOLF_API_KEY", "021f429c8c7164c88ce968d5fb71")
DATAGOLF_BASE_URL = "https://feeds.datagolf.com"

# =============================================================================
# Bankroll Settings
# =============================================================================
STARTING_BANKROLL = 100.00  # Initial bankroll in dollars
BANKROLL_FILE = "bankroll_history.json"  # File to persist bankroll data

# =============================================================================
# Entry Sizing (Kelly Criterion)
# =============================================================================
# Fractional Kelly multiplier (0.25 = quarter Kelly, recommended for high variance)
# Full Kelly is mathematically optimal but extremely aggressive for pick 6
KELLY_FRACTION = 0.25

# Hard caps on entry sizing
MIN_ENTRY_SIZE = 1.00   # PrizePicks minimum
MAX_ENTRY_SIZE = 25.00  # Cap per entry as % of bankroll (will also be bounded)
MAX_BANKROLL_PCT = 0.10  # Never risk more than 10% of bankroll on one entry

# =============================================================================
# Stop-Loss / Drawdown Rules
# =============================================================================
# Session stop-loss: stop playing after losing this much in one session
SESSION_STOP_LOSS = 20.00  # Dollars

# Drawdown stop-loss: pause if bankroll drops below this % of peak
MAX_DRAWDOWN_PCT = 0.30  # 30% drawdown from peak = stop and reassess

# Weekly loss limit
WEEKLY_LOSS_LIMIT = 30.00  # Max dollars to lose in a 7-day rolling window

# Minimum bankroll to continue playing (absolute floor)
MIN_BANKROLL_FLOOR = 20.00  # Below this, stop and reload or quit

# =============================================================================
# PrizePicks Payout Structures (2-6 picks)
# =============================================================================
# STANDARD payouts (non-correlated, cross-sport or single picks per game)
# CORRELATED payouts are reduced — PrizePicks adjusts these dynamically
# based on same-game, same-sport (especially golf), and other factors.
#
# The app lets you enter CUSTOM multipliers to match what PP actually shows you.
# =============================================================================

PRIZEPICKS_PAYOUTS_STANDARD = {
    "power_play": {
        2: {2: 3.0},
        3: {3: 5.0},
        4: {4: 10.0},
        5: {5: 20.0},
        6: {6: 37.5},
    },
    "flex_play": {
        2: {},  # No flex for 2-pick
        3: {3: 2.25, 2: 1.25},
        4: {4: 5.0, 3: 1.5},
        5: {5: 10.0, 4: 2.0, 3: 0.4},
        6: {6: 25.0, 5: 2.0, 4: 0.4},
    },
}

# Example golf / correlated payouts (common reductions seen on PrizePicks)
# These are approximate — actual values depend on the specific lineup.
# Users should always enter the real multiplier PP shows them.
PRIZEPICKS_PAYOUTS_GOLF = {
    "power_play": {
        2: {2: 2.7},
        3: {3: 4.5},
        4: {4: 8.5},
        5: {5: 17.0},
        6: {6: 32.0},
    },
    "flex_play": {
        2: {},
        3: {3: 2.0, 2: 1.1},
        4: {4: 4.25, 3: 1.35},
        5: {5: 8.5, 4: 1.75, 3: 0.35},
        6: {6: 21.0, 5: 1.75, 4: 0.35},
    },
}

# Legacy compatibility alias (6-pick only)
PRIZEPICKS_PAYOUTS = {
    "power_play": {"6_of_6": 37.5, "5_of_6": 0, "4_of_6": 0},
    "flex_play": {"6_of_6": 25.0, "5_of_6": 2.0, "4_of_6": 0.4, "3_of_6": 0},
}

# Break-even per-leg win probabilities (standard payouts)
BREAKEVEN_RATES = {
    "2_pick_power": 0.5774,
    "3_pick_power": 0.5848,
    "3_pick_flex": 0.5606,
    "4_pick_power": 0.5623,
    "4_pick_flex": 0.5495,
    "5_pick_power": 0.5493,
    "5_pick_flex": 0.5425,
    "6_pick_power": 0.5466,
    "6_pick_flex": 0.5421,
}

# =============================================================================
# Display Settings
# =============================================================================
CURRENCY_SYMBOL = "$"
DECIMAL_PLACES = 2


def load_config_overrides(filepath="config_overrides.json"):
    """Load any local config overrides from a JSON file."""
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            overrides = json.load(f)
            return overrides
    return {}
