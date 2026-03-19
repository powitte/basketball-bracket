# espn_api.py
# ---------------------------------------------------------------------------
# Fetches live and completed game results from ESPN's unofficial scoreboard API.
#
# "Unofficial" means ESPN hasn't formally documented this endpoint, but it's
# publicly accessible and widely used by bracket apps and sports sites.
# We use it because it's free and returns scores + margins we need for scoring.
#
# The main function is get_tournament_results(), which returns a list of
# completed game results that scoring.py uses to calculate points.
# ---------------------------------------------------------------------------

import requests
import time
from datetime import date, timedelta

from config import ESPN_API_URL, ESPN_CACHE_TTL

# ---------------------------------------------------------------------------
# TEAM NAME MAPPING
# ---------------------------------------------------------------------------
# ESPN uses its own team name abbreviations that don't always match ours.
# This dict maps ESPN's "shortDisplayName" → our bracket team name.
# If a name is missing here, the game won't be scored (it'll just be skipped).
# Add entries here if you notice a game isn't being picked up.
ESPN_TO_BRACKET = {
    # --- East ---
    "Duke": "Duke",
    "Siena": "Siena",
    "Ohio St": "Ohio St.",
    "Ohio State": "Ohio St.",
    "TCU": "TCU",
    "St. John's": "St. John's",
    "St. Johns": "St. John's",
    "N. Iowa": "N. Iowa",
    "Northern Iowa": "N. Iowa",
    "Kansas": "Kansas",
    "Cal Baptist": "Cal Baptist",
    "California Baptist": "Cal Baptist",
    "Louisville": "Louisville",
    "S. Florida": "South Florida",
    "South Florida": "South Florida",
    "Michigan St": "Michigan St.",
    "Michigan State": "Michigan St.",
    "N. Dakota St": "N. Dakota St.",
    "North Dakota St": "N. Dakota St.",
    "North Dakota State": "N. Dakota St.",
    "UCLA": "UCLA",
    "UCF": "UCF",
    "Connecticut": "UConn",
    "UConn": "UConn",
    "Furman": "Furman",
    # --- South ---
    "Florida": "Florida",
    "Prairie View": "PVAM/LEH",   # First Four slot
    "Lehigh": "PVAM/LEH",          # First Four slot
    "Clemson": "Clemson",
    "Iowa": "Iowa",
    "Vanderbilt": "Vanderbilt",
    "McNeese": "McNeese",
    "McNeese St": "McNeese",
    "McNeese State": "McNeese",
    "Nebraska": "Nebraska",
    "Troy": "Troy",
    "N. Carolina": "N. Carolina",
    "North Carolina": "N. Carolina",
    "UNC": "N. Carolina",
    "VCU": "VCU",
    "Illinois": "Illinois",
    "Penn": "Penn",
    "Pennsylvania": "Penn",
    "Saint Mary's": "Saint Mary's",
    "St. Mary's": "Saint Mary's",
    "Texas A&M": "Texas A&M",
    "Houston": "Houston",
    "Idaho": "Idaho",
    # --- West ---
    "Arizona": "Arizona",
    "LIU": "LIU",
    "Long Island": "LIU",
    "Villanova": "Villanova",
    "Utah St": "Utah St.",
    "Utah State": "Utah St.",
    "Wisconsin": "Wisconsin",
    "High Point": "High Point",
    "Arkansas": "Arkansas",
    "Hawaii": "Hawaii",
    "BYU": "BYU",
    "Texas": "TEX/NCST",           # First Four slot
    "NC State": "TEX/NCST",        # First Four slot
    "Gonzaga": "Gonzaga",
    "Kennesaw St": "Kennesaw St.",
    "Kennesaw State": "Kennesaw St.",
    "Miami": "Miami",              # Miami (FL) — West region
    "Miami FL": "Miami",
    "Missouri": "Missouri",
    "Purdue": "Purdue",
    "Queens": "Queens",
    # --- Midwest ---
    "Michigan": "Michigan",
    "UMBC": "UMBC/HOW",            # First Four slot
    "Howard": "UMBC/HOW",          # First Four slot
    "Georgia": "Georgia",
    "Saint Louis": "Saint Louis",
    "SLU": "Saint Louis",
    "Texas Tech": "Texas Tech",
    "Akron": "Akron",
    "Alabama": "Alabama",
    "Hofstra": "Hofstra",
    "Tennessee": "Tennessee",
    "Miami OH": "M-OH/SMU",        # First Four slot — Miami (Ohio)
    "Miami (OH)": "M-OH/SMU",
    "Miami (Ohio)": "M-OH/SMU",
    "SMU": "M-OH/SMU",             # First Four slot
    "Virginia": "Virginia",
    "Wright St": "Wright St.",
    "Wright State": "Wright St.",
    "Kentucky": "Kentucky",
    "Santa Clara": "Santa Clara",
    "Iowa St": "Iowa St.",
    "Iowa State": "Iowa St.",
    "Tennessee St": "Tennessee St.",
    "Tennessee State": "Tennessee St.",
}

# ---------------------------------------------------------------------------
# CACHE
# ---------------------------------------------------------------------------
# We store results in memory so we don't hammer ESPN's API on every page load.
# _cache["data"] holds the results list; _cache["fetched_at"] is the Unix
# timestamp of when we last fetched. If it's been less than ESPN_CACHE_TTL
# seconds, we return the cached data instead of making a new request.
_cache = {
    "data": [],
    "fetched_at": 0,   # 0 means "never fetched"
}


def _tournament_dates():
    """Generate all dates from the First Four through the Championship.

    Returns a list of date strings in YYYYMMDD format, which is what the
    ESPN API expects in its ?dates= query parameter.
    """
    start = date(2026, 3, 17)   # First Four tip-off
    end   = date(2026, 4, 6)    # National Championship
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return dates


def _map_team(espn_name):
    """Convert an ESPN team name to our bracket team name.

    Tries exact match first, then strips trailing periods/spaces and tries again.
    Returns None if no match found — that game will be skipped in scoring.
    """
    if espn_name in ESPN_TO_BRACKET:
        return ESPN_TO_BRACKET[espn_name]
    # Try stripping trailing whitespace or punctuation variations
    cleaned = espn_name.strip().rstrip(".")
    return ESPN_TO_BRACKET.get(cleaned)


def _fetch_results():
    """Query ESPN for all tournament games and return completed game results.

    Loops over all tournament dates and queries the ESPN scoreboard API for each.
    For each completed game, extracts team names and final scores.
    Returns a list of dicts, one per completed game.
    """
    results = []

    for date_str in _tournament_dates():
        try:
            # Build the URL with query parameters:
            # groups=50 → NCAA Men's Basketball Tournament
            # limit=100 → return up to 100 games per date (way more than needed)
            url = f"{ESPN_API_URL}?dates={date_str}&groups=50&limit=100"
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # raises an error for HTTP 4xx/5xx
            data = response.json()
        except Exception as e:
            # Don't crash the whole app if one date fails — just skip it
            print(f"ESPN API error for date {date_str}: {e}")
            continue

        # ESPN wraps all games in an "events" list
        for event in data.get("events", []):
            # Each event has one "competition" (the actual game)
            competitions = event.get("competitions", [])
            if not competitions:
                continue
            competition = competitions[0]

            # Skip games that aren't finished yet
            status = competition.get("status", {})
            if not status.get("type", {}).get("completed", False):
                continue

            # Extract the two teams (competitors)
            competitors = competition.get("competitors", [])
            if len(competitors) != 2:
                continue

            # Parse team name and score for each competitor
            parsed = []
            for comp in competitors:
                espn_name = comp.get("team", {}).get("shortDisplayName", "")
                bracket_name = _map_team(espn_name)
                try:
                    score = int(comp.get("score", 0))
                except (ValueError, TypeError):
                    score = 0
                # Keep the original ESPN name so First Four display shows actual teams
                parsed.append({"name": bracket_name, "espn_name": espn_name, "score": score})

            # Both teams must be recognized; skip if either is unknown
            if not parsed[0]["name"] or not parsed[1]["name"]:
                continue

            # Determine winner and loser by score
            if parsed[0]["score"] >= parsed[1]["score"]:
                winner, loser = parsed[0], parsed[1]
            else:
                winner, loser = parsed[1], parsed[0]

            margin = winner["score"] - loser["score"]
            results.append({
                "winner":         winner["name"],
                "loser":          loser["name"],
                "winner_score":   winner["score"],
                "loser_score":    loser["score"],
                "margin":         margin,
                # Original ESPN names — used for display so First Four games
                # show "Texas def. NC State" instead of "TEX/NCST def. TEX/NCST"
                "display_winner": winner["espn_name"],
                "display_loser":  loser["espn_name"],
            })

    return results


def get_tournament_results():
    """Return a list of completed tournament game results (with caching).

    Each result is a dict:
        winner       — bracket team name of the winning team
        loser        — bracket team name of the losing team
        winner_score — final score of the winner
        loser_score  — final score of the loser
        margin       — point difference (winner_score - loser_score)

    Results are cached for ESPN_CACHE_TTL seconds to avoid excessive API calls.
    """
    now = time.time()

    # Check if cache is still fresh
    if _cache["fetched_at"] and (now - _cache["fetched_at"]) < ESPN_CACHE_TTL:
        return _cache["data"]

    # Cache is stale or empty — fetch fresh data
    fresh = _fetch_results()
    _cache["data"] = fresh
    _cache["fetched_at"] = now
    return fresh
