# ⛳ Fantasy Golf Pick 6 Tool

A Python CLI tool for managing your PrizePicks pick 6 bankroll, calculating expected value, and making data-driven picks using DataGolf projections.

## Features

- **EV Calculator** — Calculate expected value for 6-pick Flex and Power plays with uniform or variable per-leg probabilities
- **Kelly Criterion Sizing** — Optimal entry sizing using fractional Kelly with hard caps
- **Bankroll Tracker** — Persistent tracking of entries, results, P&L, and ROI
- **Stop-Loss Rules** — Session limits, drawdown protection, weekly caps, and absolute floor
- **DataGolf Integration** — Pull live rankings, pre-tournament projections, skill ratings, and field updates

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Get a DataGolf API Key

1. Go to [datagolf.com/subscribe](https://datagolf.com/subscribe) and sign up for the **Scratch Plus** plan (includes API access)
2. Visit [datagolf.com/api-access](https://datagolf.com/api-access) to find your API key
3. Set it as an environment variable:

```bash
# Windows
set DATAGOLF_API_KEY=your_key_here

# Mac/Linux
export DATAGOLF_API_KEY=your_key_here
```

Or edit `config.py` directly and replace `YOUR_API_KEY_HERE`.

### 3. Run

```bash
python main.py
```

## Configuration

All settings are in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `STARTING_BANKROLL` | $100 | Initial bankroll |
| `KELLY_FRACTION` | 0.25 | Quarter Kelly (conservative for high variance) |
| `MAX_BANKROLL_PCT` | 10% | Max % of bankroll per entry |
| `SESSION_STOP_LOSS` | $20 | Stop after losing this much in one session |
| `MAX_DRAWDOWN_PCT` | 30% | Pause if bankroll drops 30% from peak |
| `WEEKLY_LOSS_LIMIT` | $30 | Max weekly loss |
| `MIN_BANKROLL_FLOOR` | $20 | Absolute minimum to keep playing |

## PrizePicks Payout Reference

### 6-Pick Flex Play
| Result | Payout |
|--------|--------|
| 6/6 correct | 25x entry |
| 5/6 correct | 2x entry |
| 4/6 correct | 0.4x entry |

### 6-Pick Power Play
| Result | Payout |
|--------|--------|
| 6/6 correct | 37.5x entry |
| Anything else | $0 |

### Break-Even Win Rates
- **6-pick Flex:** ~54.2% per leg
- **6-pick Power:** ~57.7% per leg

## Workflow for Making Picks

1. **Check bankroll status** (option 1) — make sure you're clear of stop-loss triggers
2. **Pull DataGolf projections** (option 10) — see who's projected well this week
3. **Cross-reference with PrizePicks lines** — find players where your estimated probability exceeds the break-even rate
4. **Run EV calculator** (option 2) — plug in your estimated win probabilities
5. **Get Kelly sizing** (option 3) — determine the right entry amount
6. **Record your entry** (option 4) — track it in the system
7. **Resolve after tournament** (option 5) — log results and update bankroll

## File Structure

```
fantasy_golf/
├── main.py              # CLI interface
├── config.py            # All settings and payout tables
├── datagolf_client.py   # DataGolf API wrapper
├── prizepicks_ev.py     # EV calculator engine
├── bankroll_manager.py  # Kelly sizing, tracking, stop-loss
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Key Math

The tool uses the binomial distribution to calculate the probability of exactly k correct picks out of 6, then multiplies by the PrizePicks payout for each scenario to compute expected value. For variable probabilities (each pick has a different win rate), it uses dynamic programming.

Kelly Criterion sizing is applied with a fractional multiplier (default 25%) because pick-6 pools are extremely high variance. Even with positive EV, full Kelly would lead to massive swings.
