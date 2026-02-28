"""
DataGolf API Test Script
=========================
Run this to see exactly what the API returns.
Copy/paste the output back to Claude so we can fix the parsing.

Usage: python test_datagolf.py
"""

import requests
import json

API_KEY = "021f429c8c7164c88ce968d5fb71"
BASE = "https://feeds.datagolf.com"

def call(endpoint, params=None):
    if params is None:
        params = {}
    params["key"] = API_KEY
    params["file_format"] = "json"
    url = f"{BASE}/{endpoint}"
    print(f"\n{'='*70}")
    print(f"  CALLING: {endpoint}")
    print(f"  URL: {url}")
    print(f"{'='*70}")
    try:
        r = requests.get(url, params=params, timeout=30)
        print(f"  Status: {r.status_code}")
        if r.status_code != 200:
            print(f"  Error: {r.text[:500]}")
            return None
        data = r.json()
        # Show the structure
        if isinstance(data, list):
            print(f"  Type: list, length={len(data)}")
            if len(data) > 0:
                print(f"  First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'not a dict'}")
                print(f"  First item: {json.dumps(data[0], indent=2)[:800]}")
        elif isinstance(data, dict):
            print(f"  Type: dict, keys={list(data.keys())}")
            for k, v in data.items():
                if isinstance(v, list):
                    print(f"    '{k}': list[{len(v)}]", end="")
                    if len(v) > 0 and isinstance(v[0], dict):
                        print(f"  keys={list(v[0].keys())}")
                        print(f"    First item: {json.dumps(v[0], indent=2)[:600]}")
                    else:
                        print()
                elif isinstance(v, dict):
                    print(f"    '{k}': dict keys={list(v.keys())[:10]}")
                else:
                    print(f"    '{k}': {v}")
        return data
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        return None


print("\n" + "★" * 70)
print("  DATAGOLF API TEST")
print("★" * 70)

# ─── Test 1: Basic connection ───
data = call("get-schedule", {"tour": "pga", "season": "2026", "upcoming_only": "yes"})

# ─── Test 2: Skill Ratings (has GIR-like data) ───
data = call("preds/skill-ratings", {"display": "value"})

if data:
    # Try to find and sort by GIR or approach-related fields
    players = data if isinstance(data, list) else data.get("rankings", [])
    if players and isinstance(players, list) and len(players) > 0:
        print(f"\n  ALL KEYS in first player: {sorted(players[0].keys())}")
        
        # Look for GIR-related keys
        gir_keys = [k for k in players[0].keys() if 'gir' in k.lower() or 'green' in k.lower()]
        app_keys = [k for k in players[0].keys() if 'app' in k.lower() or 'approach' in k.lower()]
        print(f"  GIR-related keys: {gir_keys}")
        print(f"  Approach-related keys: {app_keys}")

# ─── Test 3: Approach Skill (detailed GIR stats) ───
data = call("preds/approach-skill", {"period": "l24"})

if data:
    players = data if isinstance(data, list) else data.get("rankings", [])
    if players and isinstance(players, list) and len(players) > 0:
        print(f"\n  ALL KEYS in first player: {sorted(players[0].keys())}")
        gir_keys = [k for k in players[0].keys() if 'gir' in k.lower() or 'green' in k.lower()]
        print(f"  GIR-related keys: {gir_keys}")

# ─── Test 4: Live Tournament Stats (has GIR during events) ───
data = call("preds/live-tournament-stats", {
    "stats": "sg_ott,sg_app,sg_arg,sg_putt,sg_total,gir,accuracy,distance",
    "round": "event_avg",
    "display": "value",
})

if data:
    players = data if isinstance(data, list) else []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list) and len(v) > 0:
                players = v
                break
    if players and isinstance(players, list) and len(players) > 0:
        print(f"\n  ALL KEYS in first player: {sorted(players[0].keys())}")
        gir_keys = [k for k in players[0].keys() if 'gir' in k.lower() or 'green' in k.lower()]
        print(f"  GIR-related keys: {gir_keys}")
        
        # Try sorting by GIR
        for gk in gir_keys:
            sorted_players = sorted(players, key=lambda p: p.get(gk, 0) or 0, reverse=True)
            print(f"\n  TOP 20 SORTED BY '{gk}':")
            print(f"  {'#':>3s}  {'Player':<30s}  {gk:>10s}")
            print(f"  {'─'*3}  {'─'*30}  {'─'*10}")
            for i, p in enumerate(sorted_players[:20]):
                val = p.get(gk, 'N/A')
                name = p.get('player_name', '?')
                if isinstance(val, (int, float)):
                    print(f"  {i+1:>3d}  {name:<30s}  {val:>10.2f}")
                else:
                    print(f"  {i+1:>3d}  {name:<30s}  {str(val):>10s}")

# ─── Test 5: Pre-tournament predictions ───
data = call("preds/pre-tournament", {"tour": "pga", "odds_format": "percent"})

# ─── Test 6: Field updates ───
data = call("field-updates", {"tour": "pga"})

# ─── Test 7: Rankings ───  
data = call("preds/get-dg-rankings")

print("\n" + "★" * 70)
print("  DONE! Copy everything above and paste it back to Claude.")
print("★" * 70)
