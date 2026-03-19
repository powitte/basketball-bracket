# scoring.py
# ---------------------------------------------------------------------------
# Calculates scores for each bracket participant based on completed game results.
#
# Scoring rules (from config.py):
#   +10 pts  for every correct winner pick
#   +4  pts  upset bonus: winner's seed > loser's seed (lower seed beats higher)
#   +margin//2 pts  win margin bonus (e.g., 80-70 game → +5 pts)
#
# The main entry point is rank_participants(), which takes everyone's picks
# and the ESPN results and returns a sorted leaderboard.
# ---------------------------------------------------------------------------

from config import POINTS_PER_WIN, UPSET_BONUS_PTS, MARGIN_BONUS_DIVISOR
from bracket_data import GAME_BY_ID, TEAM_SEEDS, resolve_teams


def get_team_seed(team_name):
    """Look up a team's seed from the TEAM_SEEDS dict.

    Returns the seed as an integer, or 0 if unknown (shouldn't happen for
    valid bracket team names, but 0 is a safe fallback — it won't trigger
    false upset bonuses).
    """
    return TEAM_SEEDS.get(team_name, 0)


def score_one_pick(picked_winner, actual_winner, actual_loser,
                   winner_score, loser_score):
    """Calculate points earned for one game pick.

    Args:
        picked_winner: the team the participant picked to win
        actual_winner: the team that actually won
        actual_loser:  the team that actually lost
        winner_score:  final score of the winner
        loser_score:   final score of the loser

    Returns a dict with:
        correct     — True/False
        base_pts    — 10 if correct, else 0
        upset_pts   — 4 if correct AND it was an upset, else 0
        margin_pts  — floor(margin / 2) if correct, else 0
        total       — sum of the above three
    """
    if picked_winner != actual_winner:
        # Wrong pick — zero points, no bonuses
        return {"correct": False, "base_pts": 0, "upset_pts": 0, "margin_pts": 0, "total": 0}

    # Correct pick — calculate all three components
    base_pts = POINTS_PER_WIN

    # Upset bonus: winner has a HIGHER seed number than the loser.
    # In NCAA seeding, higher seed number = weaker team, so 12 beating 5 is an upset.
    winner_seed = get_team_seed(actual_winner)
    loser_seed  = get_team_seed(actual_loser)
    upset_pts = UPSET_BONUS_PTS if winner_seed > loser_seed else 0

    # Margin bonus: integer division so scores stay whole numbers.
    # A 10-point win = +5. An 11-point win = +5 (we round down).
    margin = winner_score - loser_score
    margin_pts = margin // MARGIN_BONUS_DIVISOR

    total = base_pts + upset_pts + margin_pts
    return {
        "correct":    True,
        "base_pts":   base_pts,
        "upset_pts":  upset_pts,
        "margin_pts": margin_pts,
        "total":      total,
    }


def build_results_lookup(results):
    """Convert the ESPN results list into a dict keyed by frozenset of team names.

    This makes it fast to look up "did these two teams play, and who won?"
    without looping through all results every time.

    Input:  [{"winner": "Duke", "loser": "Siena", ...}, ...]
    Output: {frozenset({"Duke", "Siena"}): {"winner": "Duke", ...}, ...}
    """
    lookup = {}
    for result in results:
        key = frozenset({result["winner"], result["loser"]})
        lookup[key] = result
    return lookup


def calculate_scores(participant_picks, results):
    """Calculate the total score for one participant.

    Args:
        participant_picks: dict of {game_id: team_name_they_picked}
        results:           list of completed game result dicts from espn_api

    Returns a dict with:
        total        — total points earned
        correct      — number of correct picks
        base_pts     — total base points (10 per correct)
        upset_pts    — total upset bonus points
        margin_pts   — total margin bonus points
        breakdown    — dict of {game_id: score_one_pick result} for scored games
    """
    results_lookup = build_results_lookup(results)

    totals = {"total": 0, "correct": 0, "base_pts": 0, "upset_pts": 0, "margin_pts": 0}
    breakdown = {}

    # Loop through every game the participant picked
    for game_id, picked_team in participant_picks.items():
        if not picked_team:
            continue  # Skip unpicked games (shouldn't happen after submission)

        game = GAME_BY_ID.get(game_id)
        if not game:
            continue  # Unknown game ID — skip

        # Figure out which two teams are in this game based on participant's own picks
        # (for round 2+ games, the teams depend on earlier picks)
        team_a, _, team_b, _ = resolve_teams(game_id, participant_picks)
        if not team_a or not team_b:
            continue  # Can't determine matchup — skip

        # Check if ESPN has a result for this exact matchup
        matchup_key = frozenset({team_a, team_b})
        result = results_lookup.get(matchup_key)
        if not result:
            continue  # Game hasn't been played yet — no points available

        # Score this pick
        score = score_one_pick(
            picked_winner=picked_team,
            actual_winner=result["winner"],
            actual_loser=result["loser"],
            winner_score=result["winner_score"],
            loser_score=result["loser_score"],
        )
        breakdown[game_id] = score

        # Accumulate totals
        totals["total"]      += score["total"]
        totals["base_pts"]   += score["base_pts"]
        totals["upset_pts"]  += score["upset_pts"]
        totals["margin_pts"] += score["margin_pts"]
        if score["correct"]:
            totals["correct"] += 1

    # Count correct picks per round — used for the round-by-round leaderboard columns.
    # round_correct is a dict like {1: 6, 2: 3} meaning 6 correct R64, 3 correct R32, etc.
    round_correct = {}
    for game_id, s in breakdown.items():
        if s["correct"]:
            game = GAME_BY_ID.get(game_id)
            if game:
                r = game["round"]
                round_correct[r] = round_correct.get(r, 0) + 1

    totals["round_correct"] = round_correct
    totals["breakdown"] = breakdown
    return totals


def compute_expected_score(picks, results):
    """Estimate remaining expected points for one participant.

    Methodology (per user spec):
      - Each team has a 50% chance of winning each future game.
      - Each correct pick earns an average of 16 points (base + bonuses).
      - If a participant's picked team has been eliminated, that pick is worth 0.
      - If a game has already been decided, it's already reflected in current score
        and is excluded here.

    Algorithm:
      For each future pick (game not yet decided):
        games_needed = round_number_of_pick - rounds_the_team_has_already_won
        expected_pts = 16 * (0.5 ** games_needed)

    Returns total expected additional points as a float.
    """
    # Build team status from ESPN results:
    #   wins_by_team: how many bracket rounds each team has won (0 = not yet played)
    #   eliminated:   teams that lost a game (can't earn future points)
    #
    # First Four games have result["winner"] == result["loser"] (both map to the
    # same combined slot name like "TEX/NCST") — we skip those because participants
    # don't pick First Four games, and the First Four win isn't a scored bracket round.
    wins_by_team = {}
    eliminated = set()
    for result in results:
        if result["winner"] == result["loser"]:
            continue  # First Four game — skip
        wins_by_team[result["winner"]] = wins_by_team.get(result["winner"], 0) + 1
        eliminated.add(result["loser"])

    expected = 0.0
    for game_id, picked_team in picks.items():
        if not picked_team:
            continue
        game = GAME_BY_ID.get(game_id)
        if not game:
            continue
        round_num = game["round"]

        if picked_team in eliminated:
            continue  # Team is out — zero expected points

        wins = wins_by_team.get(picked_team, 0)

        if wins >= round_num:
            # Team already won this round — game is decided, in current score already
            continue

        # Team is still alive and this game hasn't been played yet.
        # They need (round_num - wins) more wins to fulfill this pick.
        games_needed = round_num - wins
        expected += 16.0 * (0.5 ** games_needed)

    return expected


def compute_win_probabilities(ranked):
    """Convert current + expected scores into win probabilities summing to 100%.

    Weight = current_score + expected_score + 1
    The +1 baseline keeps all probabilities non-zero (before any games,
    everyone has equal expected scores so the result is 1/n for each).

    Returns a list of floats (percentages, 1 decimal place) in ranked order.
    The list is adjusted so the values sum to exactly 100.0.
    """
    weights = [max(e["score"] + e.get("expected_score", 0.0), 0.0) + 1 for e in ranked]
    total = sum(weights)
    raw = [w / total * 100 for w in weights]
    rounded = [round(p, 1) for p in raw]
    # Fix floating-point rounding so the total is exactly 100.0
    diff = round(100.0 - sum(rounded), 1)
    if rounded:
        rounded[0] = round(rounded[0] + diff, 1)
    return rounded


def rank_participants(all_picks_list, results):
    """Score all participants and return a sorted leaderboard.

    Args:
        all_picks_list: list of dicts from sheets.get_all_picks(), each with
                        keys 'name', 'timestamp', 'picks'
        results:        list of completed game result dicts from espn_api

    Returns a list of dicts sorted by score descending (ties broken by name):
        name        — participant's name
        score       — total points
        correct     — number of correct picks
        base_pts    — base points subtotal
        upset_pts   — upset bonus subtotal
        margin_pts  — margin bonus subtotal
        picks       — the raw picks dict (for displaying their bracket)
    """
    ranked = []
    for entry in all_picks_list:
        scores = calculate_scores(entry["picks"], results)
        expected = compute_expected_score(entry["picks"], results)
        ranked.append({
            "name":           entry["name"],
            "score":          scores["total"],
            "correct":        scores["correct"],
            "base_pts":       scores["base_pts"],
            "upset_pts":      scores["upset_pts"],
            "margin_pts":     scores["margin_pts"],
            "round_correct":  scores["round_correct"],
            "expected_score": expected,
            "picks":          entry["picks"],
            "breakdown":      scores["breakdown"],
            # Pass through the bracket strategy so the leaderboard can display it
            "method":         entry.get("method", "custom"),
        })

    # Sort: highest score first; alphabetical name as tiebreaker
    ranked.sort(key=lambda x: (-x["score"], x["name"]))
    return ranked
