"""
DataGolf API Client
====================
Full wrapper for the DataGolf REST API.

Endpoints covered:
  General:     player list, schedule, field updates
  Predictions: rankings, pre-tournament, skill ratings, decompositions,
               approach skill, fantasy projections
  Live Model:  in-play predictions, live tournament stats, live hole stats
  Betting:     outrights, matchups, matchups all pairings
  Historical:  raw data, event stats, odds, DFS
"""

import requests
from typing import Optional, List
from config import DATAGOLF_API_KEY, DATAGOLF_BASE_URL


class DataGolfClient:
    """Client for the DataGolf API (feeds.datagolf.com)."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or DATAGOLF_API_KEY
        self.base_url = DATAGOLF_BASE_URL
        if self.api_key == "YOUR_API_KEY_HERE":
            print("⚠️  No DataGolf API key configured!")
            print("   Set DATAGOLF_API_KEY in config.py")
            print("   Get your key at https://datagolf.com/api-access\n")

    def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the DataGolf API."""
        if params is None:
            params = {}
        params["key"] = self.api_key
        params.setdefault("file_format", "json")

        url = f"{self.base_url}/{endpoint}"
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            status = resp.status_code
            if status == 401:
                return {"error": "Authentication failed. Check your API key."}
            elif status == 403:
                return {"error": "Access denied. Subscription may not include API."}
            elif status == 404:
                return {"error": f"Endpoint not found: {endpoint}"}
            else:
                return {"error": f"HTTP {status}: {e}"}
        except requests.exceptions.ConnectionError:
            return {"error": "Connection failed. Check internet connection."}
        except requests.exceptions.Timeout:
            return {"error": "Request timed out (30s)."}
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {e}"}
        except ValueError:
            return {"error": "Invalid JSON response from API."}

    # =========================================================================
    # General Use
    # =========================================================================

    def get_player_list(self) -> dict:
        """All players who've played a major tour since 2018."""
        return self._request("get-player-list")

    def get_schedule(self, tour: str = "pga", season: str = "2026",
                     upcoming_only: str = "yes") -> dict:
        """Tournament schedule. Tours: pga, euro, kft, alt (liv)."""
        return self._request("get-schedule", {
            "tour": tour, "season": season, "upcoming_only": upcoming_only,
        })

    def get_field_updates(self, tour: str = "pga") -> dict:
        """Field list, WDs, tee times, start holes for upcoming event."""
        return self._request("field-updates", {"tour": tour})

    # =========================================================================
    # Model Predictions
    # =========================================================================

    def get_rankings(self) -> dict:
        """Top 500 DG rankings with skill estimates and OWGR rank."""
        return self._request("preds/get-dg-rankings")

    def get_pre_tournament_predictions(self, tour: str = "pga",
                                        add_position: str = "",
                                        odds_format: str = "percent") -> dict:
        """
        Pre-tournament probabilities: win, top5, top10, top20, make_cut.
        add_position: comma-separated extra positions e.g. "1,30,40"
        odds_format: percent, american, decimal, fraction
        """
        params = {"tour": tour, "odds_format": odds_format}
        if add_position:
            params["add_position"] = add_position
        return self._request("preds/pre-tournament", params)

    def get_pre_tournament_archive(self, event_id: str = "",
                                    year: str = "2025",
                                    odds_format: str = "percent") -> dict:
        """Archived pre-tournament predictions for a past event."""
        params = {"year": year, "odds_format": odds_format}
        if event_id:
            params["event_id"] = event_id
        return self._request("preds/pre-tournament-archive", params)

    def get_player_decompositions(self, tour: str = "pga") -> dict:
        """Detailed SG prediction breakdown per player for upcoming event."""
        return self._request("preds/player-decompositions", {"tour": tour})

    def get_skill_ratings(self, display: str = "value") -> dict:
        """
        Skill ratings across all dimensions.
        display: 'value' for SG values, 'rank' for ranks.
        """
        return self._request("preds/skill-ratings", {"display": display})

    def get_approach_skill(self, period: str = "l24") -> dict:
        """
        Detailed approach stats by yardage/lie.
        period: l24 (last 24mo), l12 (last 12mo), ytd
        """
        return self._request("preds/approach-skill", {"period": period})

    def get_fantasy_projections(self, tour: str = "pga",
                                 site: str = "draftkings",
                                 slate: str = "main") -> dict:
        """DFS projections for DraftKings/FanDuel/Yahoo."""
        return self._request("preds/fantasy-projection-defaults", {
            "tour": tour, "site": site, "slate": slate,
        })

    # =========================================================================
    # Live Model (KEY for mid-tournament PrizePicks strategy)
    # =========================================================================

    def get_live_predictions(self, tour: str = "pga",
                              odds_format: str = "percent",
                              dead_heat: str = "no") -> dict:
        """
        LIVE finish probabilities — updates every 5 minutes during rounds.
        Returns win, top5, top10, top20, make_cut probabilities.
        This is the key endpoint for finding stale PrizePicks lines.
        """
        return self._request("preds/in-play", {
            "tour": tour, "odds_format": odds_format, "dead_heat": dead_heat,
        })

    def get_live_tournament_stats(self, stats: str = "",
                                   round_num: str = "event_avg",
                                   display: str = "value") -> dict:
        """
        Live strokes-gained and traditional stats during a tournament.
        stats: comma-separated, e.g. "sg_ott,sg_app,sg_putt,sg_total"
               Available: sg_putt, sg_arg, sg_app, sg_ott, sg_t2g, sg_bs,
                          sg_total, distance, accuracy, gir, prox_fw,
                          prox_rgh, scrambling, great_shots, poor_shots
        round_num: event_cumulative, event_avg, 1, 2, 3, 4
        """
        params = {"round": round_num, "display": display}
        if stats:
            params["stats"] = stats
        else:
            params["stats"] = "sg_ott,sg_app,sg_arg,sg_putt,sg_total"
        return self._request("preds/live-tournament-stats", params)

    def get_live_hole_stats(self, tour: str = "pga") -> dict:
        """Live hole scoring averages and distributions by wave."""
        return self._request("preds/live-hole-stats", {"tour": tour})

    # =========================================================================
    # Betting Tools
    # =========================================================================

    def get_outrights(self, tour: str = "pga", market: str = "win",
                      odds_format: str = "decimal") -> dict:
        """
        Outright odds: DG model vs 11 sportsbooks.
        market: win, top_5, top_10, top_20, mc, make_cut, frl
        """
        return self._request("betting-tools/outrights", {
            "tour": tour, "market": market, "odds_format": odds_format,
        })

    def get_matchups(self, tour: str = "pga",
                     market: str = "tournament_matchups",
                     odds_format: str = "decimal") -> dict:
        """
        Matchup & 3-ball odds: DG model vs 8 sportsbooks.
        market: tournament_matchups, round_matchups, 3_balls
        """
        return self._request("betting-tools/matchups", {
            "tour": tour, "market": market, "odds_format": odds_format,
        })

    def get_matchups_all_pairings(self, tour: str = "pga",
                                   odds_format: str = "decimal") -> dict:
        """DG matchup/3-ball odds for every pairing in next round."""
        return self._request("betting-tools/matchups-all-pairings", {
            "tour": tour, "odds_format": odds_format,
        })

    # =========================================================================
    # Historical Data
    # =========================================================================

    def get_historical_event_list(self, tour: str = "pga") -> dict:
        """List of available historical events with IDs."""
        return self._request("historical-raw-data/event-list", {"tour": tour})

    def get_historical_rounds(self, tour: str = "pga",
                               event_id: str = "all",
                               year: str = "2025") -> dict:
        """Round-level scoring, stats, SG data."""
        return self._request("historical-raw-data/rounds", {
            "tour": tour, "event_id": event_id, "year": year,
        })

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def test_connection(self) -> dict:
        """Quick API health check."""
        result = self.get_schedule(upcoming_only="yes")
        if "error" in result:
            return {"ok": False, "error": result["error"]}

        events = result if isinstance(result, list) else result.get("schedule", [])
        return {
            "ok": True,
            "message": "DataGolf API connected!",
            "upcoming_events": len(events) if isinstance(events, list) else 0,
            "raw": result,
        }

    def get_tournament_field_with_projections(self, tour: str = "pga") -> list:
        """Combine field updates with pre-tournament predictions."""
        field_data = self.get_field_updates(tour)
        pred_data = self.get_pre_tournament_predictions(tour)

        if "error" in field_data or "error" in pred_data:
            return []

        # Build prediction lookup
        pred_lookup = {}
        pred_list = pred_data if isinstance(pred_data, list) else pred_data.get("rankings", [])
        if isinstance(pred_list, list):
            for p in pred_list:
                pred_lookup[p.get("player_name", "")] = p

        # Merge
        field_list = field_data.get("field", []) if isinstance(field_data, dict) else field_data
        enriched = []
        for player in field_list:
            merged = {**player}
            name = player.get("player_name", "")
            if name in pred_lookup:
                merged["projections"] = pred_lookup[name]
            enriched.append(merged)
        return enriched


if __name__ == "__main__":
    client = DataGolfClient()
    status = client.test_connection()
    if status["ok"]:
        print(f"✅ {status['message']}")
        print(f"   Upcoming events: {status['upcoming_events']}")
    else:
        print(f"❌ {status['error']}")
