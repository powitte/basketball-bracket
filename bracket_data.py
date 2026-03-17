# bracket_data.py
# ---------------------------------------------------------------------------
# This file is the single source of truth for the 2026 NCAA Tournament bracket.
# It defines every team, every seed, and every game — including which games feed
# into which later-round games.
#
# Other files import from here. Nothing in this file changes during the tournament;
# the ESPN API (espn_api.py) handles live results separately.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TEAM SEEDS
# ---------------------------------------------------------------------------
# Maps every team slot name → its seed number.
# First Four combined slots (e.g., "PVAM/LEH") use the seed of that bracket position.
# Seeds matter for calculating upset bonuses in scoring.py.
TEAM_SEEDS = {
    # East region
    "Duke": 1, "Siena": 16,
    "Ohio St.": 8, "TCU": 9,
    "St. John's": 5, "N. Iowa": 12,
    "Kansas": 4, "Cal Baptist": 13,
    "Louisville": 6, "South Florida": 11,
    "Michigan St.": 3, "N. Dakota St.": 14,
    "UCLA": 7, "UCF": 10,
    "UConn": 2, "Furman": 15,
    # South region
    "Florida": 1, "PVAM/LEH": 16,   # First Four: Prairie View A&M vs Lehigh
    "Clemson": 8, "Iowa": 9,
    "Vanderbilt": 5, "McNeese": 12,
    "Nebraska": 4, "Troy": 13,
    "N. Carolina": 6, "VCU": 11,
    "Illinois": 3, "Penn": 14,
    "Saint Mary's": 7, "Texas A&M": 10,
    "Houston": 2, "Idaho": 15,
    # West region
    "Arizona": 1, "LIU": 16,
    "Villanova": 8, "Utah St.": 9,
    "Wisconsin": 5, "High Point": 12,
    "Arkansas": 4, "Hawaii": 13,
    "BYU": 6, "TEX/NCST": 11,       # First Four: Texas vs NC State
    "Gonzaga": 3, "Kennesaw St.": 14,
    "Miami": 7, "Missouri": 10,
    "Purdue": 2, "Queens": 15,
    # Midwest region
    "Michigan": 1, "UMBC/HOW": 16,  # First Four: UMBC vs Howard
    "Georgia": 8, "Saint Louis": 9,
    "Texas Tech": 5, "Akron": 12,
    "Alabama": 4, "Hofstra": 13,
    "Tennessee": 6, "M-OH/SMU": 11, # First Four: Miami (OH) vs SMU
    "Virginia": 3, "Wright St.": 14,
    "Kentucky": 7, "Santa Clara": 10,
    "Iowa St.": 2, "Tennessee St.": 15,
}

# ---------------------------------------------------------------------------
# ROUND NAMES
# ---------------------------------------------------------------------------
# Human-readable labels for each round number used in the GAMES list.
ROUND_NAMES = {
    1: "Round of 64",
    2: "Round of 32",
    3: "Sweet 16",
    4: "Elite 8",
    5: "Final Four",
    6: "Championship",
}

# Region display order
REGION_ORDER = ["East", "South", "West", "Midwest"]

# ---------------------------------------------------------------------------
# GAMES LIST
# ---------------------------------------------------------------------------
# Each entry is a dict describing one game. Key fields:
#   id        — unique string ID like 'g1', 'g33', 'g63'
#   region    — which part of the bracket this game belongs to
#   round     — 1 (R64) through 6 (Championship)
#   team_a    — team name for slot A (only set for round 1; later rounds use source_a)
#   seed_a    — seed for slot A (only set for round 1)
#   team_b    — team name for slot B (only set for round 1)
#   seed_b    — seed for slot B (only set for round 1)
#   source_a  — ID of the game whose winner fills slot A (None for round 1)
#   source_b  — ID of the game whose winner fills slot B (None for round 1)
#   next_game — ID of the game this winner advances to (None for Championship)
#
# Game ID numbering:
#   g1–g8:   East R64        g9–g16:  South R64
#   g17–g24: West R64        g25–g32: Midwest R64
#   g33–g36: East R32        g37–g40: South R32
#   g41–g44: West R32        g45–g48: Midwest R32
#   g49–g50: East S16        g51–g52: South S16
#   g53–g54: West S16        g55–g56: Midwest S16
#   g57: East E8             g58: South E8
#   g59: West E8             g60: Midwest E8
#   g61: Final Four (East vs South)
#   g62: Final Four (West vs Midwest)
#   g63: Championship

GAMES = [
    # -----------------------------------------------------------------------
    # EAST — Round of 64 (g1–g8)
    # -----------------------------------------------------------------------
    {"id": "g1",  "region": "East", "round": 1, "team_a": "Duke",         "seed_a": 1,  "team_b": "Siena",        "seed_b": 16, "source_a": None,  "source_b": None,  "next_game": "g33"},
    {"id": "g2",  "region": "East", "round": 1, "team_a": "Ohio St.",      "seed_a": 8,  "team_b": "TCU",          "seed_b": 9,  "source_a": None,  "source_b": None,  "next_game": "g33"},
    {"id": "g3",  "region": "East", "round": 1, "team_a": "St. John's",    "seed_a": 5,  "team_b": "N. Iowa",      "seed_b": 12, "source_a": None,  "source_b": None,  "next_game": "g34"},
    {"id": "g4",  "region": "East", "round": 1, "team_a": "Kansas",        "seed_a": 4,  "team_b": "Cal Baptist",  "seed_b": 13, "source_a": None,  "source_b": None,  "next_game": "g34"},
    {"id": "g5",  "region": "East", "round": 1, "team_a": "Louisville",    "seed_a": 6,  "team_b": "South Florida","seed_b": 11, "source_a": None,  "source_b": None,  "next_game": "g35"},
    {"id": "g6",  "region": "East", "round": 1, "team_a": "Michigan St.",  "seed_a": 3,  "team_b": "N. Dakota St.","seed_b": 14, "source_a": None,  "source_b": None,  "next_game": "g35"},
    {"id": "g7",  "region": "East", "round": 1, "team_a": "UCLA",          "seed_a": 7,  "team_b": "UCF",          "seed_b": 10, "source_a": None,  "source_b": None,  "next_game": "g36"},
    {"id": "g8",  "region": "East", "round": 1, "team_a": "UConn",         "seed_a": 2,  "team_b": "Furman",       "seed_b": 15, "source_a": None,  "source_b": None,  "next_game": "g36"},
    # -----------------------------------------------------------------------
    # SOUTH — Round of 64 (g9–g16)
    # -----------------------------------------------------------------------
    {"id": "g9",  "region": "South", "round": 1, "team_a": "Florida",      "seed_a": 1,  "team_b": "PVAM/LEH",    "seed_b": 16, "source_a": None,  "source_b": None,  "next_game": "g37"},
    {"id": "g10", "region": "South", "round": 1, "team_a": "Clemson",      "seed_a": 8,  "team_b": "Iowa",        "seed_b": 9,  "source_a": None,  "source_b": None,  "next_game": "g37"},
    {"id": "g11", "region": "South", "round": 1, "team_a": "Vanderbilt",   "seed_a": 5,  "team_b": "McNeese",     "seed_b": 12, "source_a": None,  "source_b": None,  "next_game": "g38"},
    {"id": "g12", "region": "South", "round": 1, "team_a": "Nebraska",     "seed_a": 4,  "team_b": "Troy",        "seed_b": 13, "source_a": None,  "source_b": None,  "next_game": "g38"},
    {"id": "g13", "region": "South", "round": 1, "team_a": "N. Carolina",  "seed_a": 6,  "team_b": "VCU",         "seed_b": 11, "source_a": None,  "source_b": None,  "next_game": "g39"},
    {"id": "g14", "region": "South", "round": 1, "team_a": "Illinois",     "seed_a": 3,  "team_b": "Penn",        "seed_b": 14, "source_a": None,  "source_b": None,  "next_game": "g39"},
    {"id": "g15", "region": "South", "round": 1, "team_a": "Saint Mary's", "seed_a": 7,  "team_b": "Texas A&M",   "seed_b": 10, "source_a": None,  "source_b": None,  "next_game": "g40"},
    {"id": "g16", "region": "South", "round": 1, "team_a": "Houston",      "seed_a": 2,  "team_b": "Idaho",       "seed_b": 15, "source_a": None,  "source_b": None,  "next_game": "g40"},
    # -----------------------------------------------------------------------
    # WEST — Round of 64 (g17–g24)
    # -----------------------------------------------------------------------
    {"id": "g17", "region": "West", "round": 1, "team_a": "Arizona",       "seed_a": 1,  "team_b": "LIU",          "seed_b": 16, "source_a": None,  "source_b": None,  "next_game": "g41"},
    {"id": "g18", "region": "West", "round": 1, "team_a": "Villanova",     "seed_a": 8,  "team_b": "Utah St.",     "seed_b": 9,  "source_a": None,  "source_b": None,  "next_game": "g41"},
    {"id": "g19", "region": "West", "round": 1, "team_a": "Wisconsin",     "seed_a": 5,  "team_b": "High Point",   "seed_b": 12, "source_a": None,  "source_b": None,  "next_game": "g42"},
    {"id": "g20", "region": "West", "round": 1, "team_a": "Arkansas",      "seed_a": 4,  "team_b": "Hawaii",       "seed_b": 13, "source_a": None,  "source_b": None,  "next_game": "g42"},
    {"id": "g21", "region": "West", "round": 1, "team_a": "BYU",           "seed_a": 6,  "team_b": "TEX/NCST",    "seed_b": 11, "source_a": None,  "source_b": None,  "next_game": "g43"},
    {"id": "g22", "region": "West", "round": 1, "team_a": "Gonzaga",       "seed_a": 3,  "team_b": "Kennesaw St.", "seed_b": 14, "source_a": None,  "source_b": None,  "next_game": "g43"},
    {"id": "g23", "region": "West", "round": 1, "team_a": "Miami",         "seed_a": 7,  "team_b": "Missouri",     "seed_b": 10, "source_a": None,  "source_b": None,  "next_game": "g44"},
    {"id": "g24", "region": "West", "round": 1, "team_a": "Purdue",        "seed_a": 2,  "team_b": "Queens",       "seed_b": 15, "source_a": None,  "source_b": None,  "next_game": "g44"},
    # -----------------------------------------------------------------------
    # MIDWEST — Round of 64 (g25–g32)
    # -----------------------------------------------------------------------
    {"id": "g25", "region": "Midwest", "round": 1, "team_a": "Michigan",   "seed_a": 1,  "team_b": "UMBC/HOW",    "seed_b": 16, "source_a": None,  "source_b": None,  "next_game": "g45"},
    {"id": "g26", "region": "Midwest", "round": 1, "team_a": "Georgia",    "seed_a": 8,  "team_b": "Saint Louis", "seed_b": 9,  "source_a": None,  "source_b": None,  "next_game": "g45"},
    {"id": "g27", "region": "Midwest", "round": 1, "team_a": "Texas Tech", "seed_a": 5,  "team_b": "Akron",       "seed_b": 12, "source_a": None,  "source_b": None,  "next_game": "g46"},
    {"id": "g28", "region": "Midwest", "round": 1, "team_a": "Alabama",    "seed_a": 4,  "team_b": "Hofstra",     "seed_b": 13, "source_a": None,  "source_b": None,  "next_game": "g46"},
    {"id": "g29", "region": "Midwest", "round": 1, "team_a": "Tennessee",  "seed_a": 6,  "team_b": "M-OH/SMU",   "seed_b": 11, "source_a": None,  "source_b": None,  "next_game": "g47"},
    {"id": "g30", "region": "Midwest", "round": 1, "team_a": "Virginia",   "seed_a": 3,  "team_b": "Wright St.",  "seed_b": 14, "source_a": None,  "source_b": None,  "next_game": "g47"},
    {"id": "g31", "region": "Midwest", "round": 1, "team_a": "Kentucky",   "seed_a": 7,  "team_b": "Santa Clara", "seed_b": 10, "source_a": None,  "source_b": None,  "next_game": "g48"},
    {"id": "g32", "region": "Midwest", "round": 1, "team_a": "Iowa St.",   "seed_a": 2,  "team_b": "Tennessee St.","seed_b": 15, "source_a": None,  "source_b": None,  "next_game": "g48"},
    # -----------------------------------------------------------------------
    # EAST — Round of 32 (g33–g36)
    # source_a = winner of top game, source_b = winner of bottom game
    # -----------------------------------------------------------------------
    {"id": "g33", "region": "East", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g1",  "source_b": "g2",  "next_game": "g49"},
    {"id": "g34", "region": "East", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g3",  "source_b": "g4",  "next_game": "g49"},
    {"id": "g35", "region": "East", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g5",  "source_b": "g6",  "next_game": "g50"},
    {"id": "g36", "region": "East", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g7",  "source_b": "g8",  "next_game": "g50"},
    # -----------------------------------------------------------------------
    # SOUTH — Round of 32 (g37–g40)
    # -----------------------------------------------------------------------
    {"id": "g37", "region": "South", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g9",  "source_b": "g10", "next_game": "g51"},
    {"id": "g38", "region": "South", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g11", "source_b": "g12", "next_game": "g51"},
    {"id": "g39", "region": "South", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g13", "source_b": "g14", "next_game": "g52"},
    {"id": "g40", "region": "South", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g15", "source_b": "g16", "next_game": "g52"},
    # -----------------------------------------------------------------------
    # WEST — Round of 32 (g41–g44)
    # -----------------------------------------------------------------------
    {"id": "g41", "region": "West", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g17", "source_b": "g18", "next_game": "g53"},
    {"id": "g42", "region": "West", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g19", "source_b": "g20", "next_game": "g53"},
    {"id": "g43", "region": "West", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g21", "source_b": "g22", "next_game": "g54"},
    {"id": "g44", "region": "West", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g23", "source_b": "g24", "next_game": "g54"},
    # -----------------------------------------------------------------------
    # MIDWEST — Round of 32 (g45–g48)
    # -----------------------------------------------------------------------
    {"id": "g45", "region": "Midwest", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g25", "source_b": "g26", "next_game": "g55"},
    {"id": "g46", "region": "Midwest", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g27", "source_b": "g28", "next_game": "g55"},
    {"id": "g47", "region": "Midwest", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g29", "source_b": "g30", "next_game": "g56"},
    {"id": "g48", "region": "Midwest", "round": 2, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g31", "source_b": "g32", "next_game": "g56"},
    # -----------------------------------------------------------------------
    # SWEET 16 (g49–g56)
    # -----------------------------------------------------------------------
    {"id": "g49", "region": "East",    "round": 3, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g33", "source_b": "g34", "next_game": "g57"},
    {"id": "g50", "region": "East",    "round": 3, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g35", "source_b": "g36", "next_game": "g57"},
    {"id": "g51", "region": "South",   "round": 3, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g37", "source_b": "g38", "next_game": "g58"},
    {"id": "g52", "region": "South",   "round": 3, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g39", "source_b": "g40", "next_game": "g58"},
    {"id": "g53", "region": "West",    "round": 3, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g41", "source_b": "g42", "next_game": "g59"},
    {"id": "g54", "region": "West",    "round": 3, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g43", "source_b": "g44", "next_game": "g59"},
    {"id": "g55", "region": "Midwest", "round": 3, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g45", "source_b": "g46", "next_game": "g60"},
    {"id": "g56", "region": "Midwest", "round": 3, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g47", "source_b": "g48", "next_game": "g60"},
    # -----------------------------------------------------------------------
    # ELITE 8 (g57–g60)
    # -----------------------------------------------------------------------
    {"id": "g57", "region": "East",    "round": 4, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g49", "source_b": "g50", "next_game": "g61"},
    {"id": "g58", "region": "South",   "round": 4, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g51", "source_b": "g52", "next_game": "g61"},
    {"id": "g59", "region": "West",    "round": 4, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g53", "source_b": "g54", "next_game": "g62"},
    {"id": "g60", "region": "Midwest", "round": 4, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g55", "source_b": "g56", "next_game": "g62"},
    # -----------------------------------------------------------------------
    # FINAL FOUR (g61–g62)
    # East winner vs South winner; West winner vs Midwest winner
    # -----------------------------------------------------------------------
    {"id": "g61", "region": "Final Four", "round": 5, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g57", "source_b": "g58", "next_game": "g63"},
    {"id": "g62", "region": "Final Four", "round": 5, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g59", "source_b": "g60", "next_game": "g63"},
    # -----------------------------------------------------------------------
    # CHAMPIONSHIP (g63)
    # -----------------------------------------------------------------------
    {"id": "g63", "region": "Championship", "round": 6, "team_a": None, "seed_a": None, "team_b": None, "seed_b": None, "source_a": "g61", "source_b": "g62", "next_game": None},
]

# ---------------------------------------------------------------------------
# LOOKUP DICT
# ---------------------------------------------------------------------------
# Build a dict keyed by game ID for fast lookup anywhere in the app.
# Instead of searching through the list every time, just do GAME_BY_ID['g33'].
GAME_BY_ID = {game["id"]: game for game in GAMES}


def get_region_games(region):
    """Return all games for a given region (rounds 1–4), in game-ID order.

    Used by app.py to render each region's tab. Only returns games up through
    Elite 8 — Final Four and Championship are handled separately.
    """
    return [g for g in GAMES if g["region"] == region and g["round"] <= 4]


def resolve_teams(game_id, picks):
    """Given a game ID and the current pick dict, return (team_a, seed_a, team_b, seed_b).

    For round 1 games, the teams are known from the bracket.
    For later rounds, the teams are whoever the user picked to win the source games.
    Returns (None, None, None, None) if source picks are missing.

    picks: dict of {game_id: team_name}
    """
    game = GAME_BY_ID[game_id]
    if game["round"] == 1:
        # Round 1 teams are fixed — just read from the game definition
        return game["team_a"], game["seed_a"], game["team_b"], game["seed_b"]
    else:
        # Later rounds: find what the user picked for each source game
        team_a = picks.get(game["source_a"])
        team_b = picks.get(game["source_b"])
        if not team_a or not team_b:
            return None, None, None, None
        seed_a = TEAM_SEEDS.get(team_a)
        seed_b = TEAM_SEEDS.get(team_b)
        return team_a, seed_a, team_b, seed_b
