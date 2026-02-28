"""
PrizePicks API Discovery Script
=================================
Finds the golf league_id and pulls all golf projections.
Saves output to pp_output.txt — upload that file to Claude.

Usage: python test_prizepicks.py
"""

import requests
import json

lines = []

def log(msg=""):
    print(msg)
    lines.append(msg)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

try:
    # ─── Step 1: Try to get all leagues ───
    log("=" * 70)
    log("  STEP 1: Finding all PrizePicks leagues")
    log("=" * 70)

    # Try the leagues endpoint first
    for url in ["https://partner-api.prizepicks.com/leagues",
                 "https://api.prizepicks.com/leagues"]:
        log(f"\n  Trying: {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            log(f"  Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and "data" in data:
                    leagues = data["data"]
                    log(f"  Found {len(leagues)} leagues:")
                    log(f"  {'ID':>5s}  {'Name':<30s}  {'Sport':<15s}  Active")
                    log(f"  {'─'*5}  {'─'*30}  {'─'*15}  {'─'*6}")
                    golf_ids = []
                    for lg in leagues:
                        attrs = lg.get("attributes", lg)
                        name = attrs.get("name", "?")
                        sport = attrs.get("sport", "?")
                        lid = lg.get("id", "?")
                        active = attrs.get("active", "?")
                        is_golf = "golf" in name.lower() or "pga" in name.lower()
                        marker = " <<<< GOLF" if is_golf else ""
                        log(f"  {str(lid):>5s}  {name:<30s}  {str(sport):<15s}  {str(active):<6s}{marker}")
                        if is_golf:
                            golf_ids.append(lid)
                    if golf_ids:
                        log(f"\n  🏌️ Golf league IDs found: {golf_ids}")
                    break
                else:
                    log(f"  Unexpected format: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            else:
                log(f"  Response: {r.text[:300]}")
        except Exception as e:
            log(f"  Error: {e}")

    # ─── Step 2: Try common league IDs to find golf ───
    log("\n" + "=" * 70)
    log("  STEP 2: Scanning league IDs for golf projections")
    log("=" * 70)

    golf_league_id = None
    golf_data = None

    # Try a range of IDs - golf is usually in the teens/twenties
    for lid in list(range(1, 50)) + list(range(50, 120, 5)):
        url = f"https://api.prizepicks.com/projections?league_id={lid}&per_page=5"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                projs = data.get("data", [])
                if projs and len(projs) > 0:
                    # Check if any projection mentions golf-related terms
                    included = data.get("included", [])
                    league_names = set()
                    stat_types = set()
                    player_names = []
                    for inc in included:
                        attrs = inc.get("attributes", {})
                        if inc.get("type") == "league":
                            league_names.add(attrs.get("name", ""))
                        if inc.get("type") == "stat_type":
                            stat_types.add(attrs.get("name", ""))
                        if inc.get("type") == "new_player":
                            player_names.append(attrs.get("name", ""))

                    is_golf = any("golf" in n.lower() or "pga" in n.lower() for n in league_names)
                    golf_stats = any(s.lower() in ["birdies", "bogey-free holes", "pars",
                                                     "strokes", "fantasy score", "eagles"]
                                     for s in stat_types)

                    if is_golf or golf_stats:
                        log(f"\n  🏌️ FOUND GOLF! league_id={lid}")
                        log(f"     Leagues: {league_names}")
                        log(f"     Stat types: {stat_types}")
                        log(f"     Players: {player_names[:5]}")
                        golf_league_id = lid
                        break
                    else:
                        # Just log what we found
                        short_leagues = ", ".join(league_names) if league_names else "?"
                        log(f"  ID {lid:>3d}: {short_leagues[:50]}")
            elif r.status_code == 404:
                pass  # Skip silently
            else:
                pass  # Skip errors
        except requests.exceptions.Timeout:
            pass
        except Exception:
            pass

    # ─── Step 3: Pull full golf projections ───
    if golf_league_id:
        log("\n" + "=" * 70)
        log(f"  STEP 3: Pulling ALL golf projections (league_id={golf_league_id})")
        log("=" * 70)

        url = f"https://api.prizepicks.com/projections?league_id={golf_league_id}&per_page=1000"
        r = requests.get(url, headers=HEADERS, timeout=30)
        data = r.json()

        # Save raw JSON for debugging
         with open("pp_golf_props.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        log(f"  Raw JSON saved to pp_golf_raw.json")

        # Parse the JSON:API format
        projections = data.get("data", [])
        included = data.get("included", [])

        # Build lookup tables from "included"
        players = {}
        stat_types = {}
        leagues = {}
        for inc in included:
            iid = inc.get("id")
            itype = inc.get("type")
            attrs = inc.get("attributes", {})
            if itype == "new_player":
                players[iid] = attrs
            elif itype == "stat_type":
                stat_types[iid] = attrs
            elif itype == "league":
                leagues[iid] = attrs

        log(f"\n  Projections: {len(projections)}")
        log(f"  Players: {len(players)}")
        log(f"  Stat types: {list(set(a.get('name','') for a in stat_types.values()))}")
        log(f"  Leagues: {list(set(a.get('name','') for a in leagues.values()))}")

        # Show first projection structure
        if projections:
            log(f"\n  First projection raw:")
            log(f"  {json.dumps(projections[0], indent=2)[:800]}")

        # Parse and display all props
        log(f"\n  {'Player':<28s}  {'Stat Type':<20s}  {'Line':>8s}  {'O/U':<5s}  {'Status':<10s}")
        log(f"  {'─'*28}  {'─'*20}  {'─'*8}  {'─'*5}  {'─'*10}")

        props = []
        for proj in projections:
            attrs = proj.get("attributes", {})
            rels = proj.get("relationships", {})

            # Get player info
            player_rel = rels.get("new_player", {}).get("data", {})
            player_id = player_rel.get("id", "")
            player_info = players.get(player_id, {})
            player_name = player_info.get("name", "Unknown")

            # Get stat type
            stat_rel = rels.get("stat_type", {}).get("data", {})
            stat_id = stat_rel.get("id", "")
            stat_info = stat_types.get(stat_id, {})
            stat_name = stat_info.get("name", "Unknown")

            line_score = attrs.get("line_score", "?")
            status = attrs.get("status", "?")
            odds_type = attrs.get("odds_type", "?")

            props.append({
                "player": player_name,
                "stat": stat_name,
                "line": line_score,
                "status": status,
                "odds_type": odds_type,
                "player_id": player_id,
                "projection_id": proj.get("id", ""),
            })

            log(f"  {player_name:<28s}  {stat_name:<20s}  {str(line_score):>8s}  "
                f"{str(odds_type):<5s}  {str(status):<10s}")

        # Save parsed props
        with open("pp_output.txt", "w", encoding="utf-8") as f:
            json.dump(props, f, indent=2)
        log(f"\n  Parsed props saved to pp_golf_props.json ({len(props)} props)")

    else:
        log("\n  ⚠️  Could not find golf league_id automatically.")
        log("  Try opening PrizePicks in your browser:")
        log("  1. Go to prizepicks.com, click Golf")
        log("  2. Press F12, go to Network tab")
        log("  3. Look for requests to api.prizepicks.com/projections")
        log("  4. Note the league_id parameter in the URL")
        log("  5. Tell Claude that number")

        # Also try the partner API
        log("\n  Trying partner-api with no league filter...")
        try:
            url = "https://partner-api.prizepicks.com/projections?per_page=1000"
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                data = r.json()
                included = data.get("included", [])
                all_leagues = set()
                for inc in included:
                    if inc.get("type") == "league":
                        attrs = inc.get("attributes", {})
                        all_leagues.add(f"{inc.get('id')}: {attrs.get('name', '?')}")
                if all_leagues:
                    log(f"  All active leagues found:")
                    for lg in sorted(all_leagues):
                        log(f"    {lg}")
        except Exception as e:
            log(f"  Error: {e}")

    log("\n" + "=" * 70)
    log("  DONE!")
    log("=" * 70)

except Exception as e:
    log(f"\nFATAL ERROR: {e}")
    import traceback
    log(traceback.format_exc())

with open("pp_output.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"\n>>> Saved to pp_output.txt")
print(f">>> Upload that file to Claude")
input("\nPress Enter to close...")
