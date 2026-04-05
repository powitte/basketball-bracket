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

from functools import lru_cache

from config import POINTS_PER_WIN, UPSET_BONUS_PTS, MARGIN_BONUS_DIVISOR
from bracket_data import GAMES, GAME_BY_ID, TEAM_SEEDS


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
    # loser_seed == 0 means the loser is unknown (synthetic bracket entry due to ESPN
    # data gap) — skip the upset check in that case to avoid false bonuses.
    winner_seed = get_team_seed(actual_winner)
    loser_seed  = get_team_seed(actual_loser)
    upset_pts = UPSET_BONUS_PTS if (winner_seed > loser_seed and loser_seed > 0) else 0

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


@lru_cache(maxsize=None)
def _get_possible_teams(game_id):
    """Return the frozenset of all teams that could possibly reach game_id.

    For round 1 games this is just the two scheduled teams. For later rounds
    it's the union of both source games' possible teams — i.e., everyone in
    that bracket subtree. Used by build_actual_bracket's partial-match pass.

    Results are cached because this is called repeatedly for the same game IDs.
    """
    game = GAME_BY_ID.get(game_id)
    if not game:
        return frozenset()
    if game["round"] == 1:
        return frozenset({game["team_a"], game["team_b"]})
    return _get_possible_teams(game["source_a"]) | _get_possible_teams(game["source_b"])


def build_actual_bracket(results):
    """Walk the bracket game tree using real ESPN results to determine who actually
    played (and who won) in each game slot (g1–g63).

    ESPN occasionally omits individual game results (observed: 4 R64 games and
    1 S16 game missing from the 2026 data). A single gap breaks the entire
    forward chain for that sub-bracket. This function uses a multi-pass strategy
    to recover as much of the chain as possible:

    Pass 1 — standard forward chain (current approach, fast path)
    Pass 2 — infer missing R64 winners: a team that appears in ANY later ESPN
             result must have won its R64 game (the loser is eliminated and won't
             appear again). Creates a synthetic entry with scores=0.
    Pass 3 — forward chain again; resolves R32/S16/E8 games downstream of the
             newly inferred R64 winners. Loops until convergence.
    Pass 4 — partial matching: for a game with ONE known source team, scan
             unassigned ESPN results for that team where the opponent is in the
             valid bracket subtree for the unknown source. Covers cases like
             "g49 unknown but g50=UConn and 'UConn def. Duke' is in ESPN" —
             assigns the result to the parent game and synthesizes the unknown
             source's entry (winner only, scores=0).
    Pass 5 — final forward chain to resolve anything unlocked by pass 4.

    Returns a dict: {game_id: result_dict} where result_dict has winner, loser,
    winner_score, loser_score (same shape as ESPN result entries). Synthetic
    entries have winner_score=loser_score=0 and loser="unknown" where the
    actual opponent couldn't be determined from available data.
    """
    results_by_pair = build_results_lookup(results)

    # All teams that appear in any non-First-Four ESPN result.
    # If a team shows up here, they survived at least to R32 (the R64 loser
    # would only appear in the R64 result, which is what we're trying to infer).
    teams_in_results = {
        team
        for r in results
        if r["winner"] != r["loser"]          # skip First Four self-matches
        for team in (r["winner"], r["loser"])
    }

    # Index ESPN results by team name for fast lookup in pass 4.
    team_to_results = {}
    for r in results:
        if r["winner"] == r["loser"]:
            continue
        for team in (r["winner"], r["loser"]):
            team_to_results.setdefault(team, []).append(r)

    actual   = {}   # game_id → result dict (real or synthetic)
    assigned = set()  # frozensets of real ESPN result pairs already assigned to a slot

    # ------------------------------------------------------------------
    def _forward_pass():
        """One sweep through the game list, resolving what we can via the
        chain. Returns True if at least one new game was resolved."""
        changed = False
        for game in GAMES:
            gid = game["id"]
            if gid in actual:
                continue
            if game["round"] == 1:
                team_a, team_b = game["team_a"], game["team_b"]
            else:
                src_a = actual.get(game["source_a"])
                src_b = actual.get(game["source_b"])
                if not src_a or not src_b:
                    continue
                team_a, team_b = src_a["winner"], src_b["winner"]

            key = frozenset({team_a, team_b})
            result = results_by_pair.get(key)
            if result and key not in assigned:
                actual[gid] = result
                assigned.add(key)
                changed = True
        return changed

    def _synthetic(winner, loser):
        """Build a placeholder result dict for a game ESPN didn't return.
        Scores are 0, so no margin bonus is awarded — unavoidable data gap.
        """
        return {"winner": winner, "loser": loser,
                "winner_score": 0, "loser_score": 0, "margin": 0,
                "display_winner": winner, "display_loser": loser}

    # ------------------------------------------------------------------
    # Pass 1: Forward chain
    _forward_pass()

    # ------------------------------------------------------------------
    # Pass 2: Infer missing R64 winners.
    # The loser of an R64 game is eliminated and won't appear in any R32+
    # result. So if team_a shows up in ESPN results and team_b doesn't,
    # team_a must have won the R64 game even if that result is absent.
    for game in GAMES:
        if game["round"] != 1 or game["id"] in actual:
            continue
        team_a, team_b = game["team_a"], game["team_b"]
        a_seen = team_a in teams_in_results
        b_seen = team_b in teams_in_results
        if a_seen == b_seen:    # both or neither — ambiguous, skip
            continue
        winner = team_a if a_seen else team_b
        loser  = team_b if a_seen else team_a
        actual[game["id"]] = _synthetic(winner, loser)

    # ------------------------------------------------------------------
    # Pass 3: Forward chain again, looping until nothing new resolves.
    changed = True
    while changed:
        changed = _forward_pass()

    # ------------------------------------------------------------------
    # Pass 4: Partial matching — one source resolved, one still missing.
    #
    # Example: g57 (East E8) has source_b=g50 resolved (UConn won) but
    # source_a=g49 unresolved (its source g34 is unknowable because g3/g4
    # have no ESPN data at all). However, "UConn def. Duke" IS in ESPN.
    # Duke is in g49's possible-team set, so we can assign that result to
    # g57 and create a synthetic g49 entry (winner=Duke, loser=unknown).
    for game in GAMES:
        gid = game["id"]
        if gid in actual or game["round"] == 1:
            continue
        src_a = actual.get(game["source_a"])
        src_b = actual.get(game["source_b"])
        if src_a and src_b:
            continue    # both known — forward pass should have caught this
        if not src_a and not src_b:
            continue    # neither known — can't proceed

        known_team   = src_a["winner"] if src_a else src_b["winner"]
        unknown_src  = game["source_b"] if src_a else game["source_a"]
        possible     = _get_possible_teams(unknown_src)

        for res in team_to_results.get(known_team, []):
            rkey = frozenset({res["winner"], res["loser"]})
            if rkey in assigned:
                continue
            other = res["loser"] if res["winner"] == known_team else res["winner"]
            if other not in possible:
                continue    # other team isn't from the right bracket subtree

            # Valid match — assign this ESPN result to gid
            actual[gid] = res
            assigned.add(rkey)

            # Synthesize a minimal entry for the unknown source so the chain
            # can continue (winner is all we need; loser and scores are unknown)
            if unknown_src not in actual:
                actual[unknown_src] = _synthetic(other, "unknown")
            break

    # ------------------------------------------------------------------
    # Pass 5: Final forward chain to resolve anything unlocked by pass 4
    changed = True
    while changed:
        changed = _forward_pass()

    return actual


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
    # Build a game_id → actual result mapping by walking the real bracket tree.
    # This is the correct way to score rounds 2+: a participant earns points for
    # picking the right winner of each game SLOT, regardless of whether they also
    # correctly predicted both teams in that matchup.
    actual_bracket = build_actual_bracket(results)

    totals = {"total": 0, "correct": 0, "base_pts": 0, "upset_pts": 0, "margin_pts": 0}
    breakdown = {}

    for game_id, picked_team in participant_picks.items():
        if not picked_team:
            continue

        game = GAME_BY_ID.get(game_id)
        if not game:
            continue

        result = actual_bracket.get(game_id)
        if not result:
            continue    # game not yet played (or unresolvable data gap)

        score = score_one_pick(
            picked_winner=picked_team,
            actual_winner=result["winner"],
            actual_loser=result["loser"],
            winner_score=result["winner_score"],
            loser_score=result["loser_score"],
        )
        breakdown[game_id] = score

        totals["total"]      += score["total"]
        totals["base_pts"]   += score["base_pts"]
        totals["upset_pts"]  += score["upset_pts"]
        totals["margin_pts"] += score["margin_pts"]
        if score["correct"]:
            totals["correct"] += 1

    # Count correct picks per round for the round-by-round leaderboard columns
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

    Used as a fallback inside compute_win_probabilities for early rounds
    (too many games to enumerate) and stored on ranked entries for display.

    Methodology:
      - Each team has a 50% chance of winning each future game.
      - Each correct pick earns an average of 16 points (base + bonuses).
      - If a participant's picked team has been eliminated, that pick is worth 0.
      - If a game has already been decided, it's in the current score already.

    Returns total expected additional points as a float.
    """
    wins_by_team = {}
    eliminated   = set()
    for result in results:
        if result["winner"] == result["loser"]:
            continue    # First Four — skip
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
            continue    # team is out

        wins = wins_by_team.get(picked_team, 0)
        if wins >= round_num:
            continue    # already decided, in current score

        games_needed = round_num - wins
        expected += 16.0 * (0.5 ** games_needed)

    return expected


def compute_win_probabilities(ranked, results):
    """Calculate the probability each participant wins the pool.

    Uses recursive scenario enumeration: for each undecided game whose matchup
    is already determined, branch on both outcomes and propagate forward. This
    naturally handles cascading games (e.g., Championship teams depend on who
    wins the Final Four) and gives 0% to anyone who cannot possibly catch the
    leader.

    Only games whose BOTH participants have appeared in ESPN results are
    enumerated. This filters out historical data gaps (R64 games ESPN never
    returned) so they aren't mistakenly treated as future games.

    Falls back to a score-proportional estimate when more than 15 undecided
    games remain simultaneously determinable, which only occurs in the very
    early rounds (during or just after R64).

    Args:
        ranked:  list of participant dicts from rank_participants()
        results: list of completed game result dicts from espn_api
    """
    actual = build_actual_bracket(results)

    # Teams that have an actual ESPN result — used to filter out data-gap games
    # (teams with zero ESPN appearances can't be distinguished from future entrants).
    teams_active = {
        team
        for r in results
        if r["winner"] != r["loser"]
        for team in (r["winner"], r["loser"])
    }

    # All games not yet in actual — candidates for future enumeration
    all_undecided = [g for g in GAMES if g["id"] not in actual]

    # Count how many undecided games are currently determinable with active teams.
    # If this exceeds 15 (→ >32K scenarios) we fall back to the proportional method.
    def _count_now_determinable(cur_actual):
        count = 0
        for game in all_undecided:
            if game["id"] in cur_actual:
                continue
            if game["round"] == 1:
                ta, tb = game["team_a"], game["team_b"]
            else:
                sa = cur_actual.get(game["source_a"])
                sb = cur_actual.get(game["source_b"])
                if not sa or not sb:
                    continue
                ta, tb = sa["winner"], sb["winner"]
            if ta in teams_active and tb in teams_active:
                count += 1
        return count

    if _count_now_determinable(actual) > 15:
        # Fallback: score-proportional with +1 floor (appropriate for early rounds
        # when there are still many games and anyone can theoretically win)
        weights = [max(e["score"] + e.get("expected_score", 0.0), 0.0) + 1 for e in ranked]
        total_w = sum(weights)
        raw     = [w / total_w * 100 for w in weights]
        rounded = [round(p, 1) for p in raw]
        diff    = round(100.0 - sum(rounded), 1)
        if rounded:
            rounded[0] = round(rounded[0] + diff, 1)
        return rounded

    base_scores   = [e["score"] for e in ranked]
    scenario_wins = [0.0] * len(ranked)
    total_scenarios = [0]

    def _recurse(cur_actual, incr):
        """Recursively enumerate undecided game outcomes.

        cur_actual:    actual_bracket extended with this branch's decided games
        incr:          list of incremental points each participant has earned
                       from games decided in this branch so far
        """
        # Find the first undecided game whose matchup is now determinable
        # and whose teams have actually appeared in ESPN (not data-gap games)
        for game in all_undecided:
            gid = game["id"]
            if gid in cur_actual:
                continue
            if game["round"] == 1:
                ta, tb = game["team_a"], game["team_b"]
            else:
                sa = cur_actual.get(game["source_a"])
                sb = cur_actual.get(game["source_b"])
                if not sa or not sb:
                    continue
                ta, tb = sa["winner"], sb["winner"]

            # Only enumerate games with teams that are confirmed active in ESPN.
            # This excludes R64 games whose results ESPN never returned, which are
            # already decided but have no data — they should not be re-enumerated.
            if ta not in teams_active or tb not in teams_active:
                continue

            # Enumerate both outcomes for this game
            for winner, loser in [(ta, tb), (tb, ta)]:
                w_seed = TEAM_SEEDS.get(winner, 0)
                l_seed = TEAM_SEEDS.get(loser, 0)
                # Award base + upset bonus (deterministic from seeds) +
                # expected margin bonus (~10-pt average game → +5 pts)
                pts = POINTS_PER_WIN + (UPSET_BONUS_PTS if w_seed > l_seed else 0) + 5

                new_incr = list(incr)
                for i, entry in enumerate(ranked):
                    if entry["picks"].get(gid) == winner:
                        new_incr[i] += pts

                # Extend the bracket so downstream games (e.g., Championship
                # after the FF) can be determined in the next recursion level
                new_actual = {**cur_actual,
                              gid: {"winner": winner, "loser": loser,
                                    "winner_score": 0, "loser_score": 0}}
                _recurse(new_actual, new_incr)

            return  # processed the first determinable game; let recursion handle the rest

        # Leaf: no more determinable active-team games → record this scenario's outcome
        final = [base_scores[i] + incr[i] for i in range(len(ranked))]
        best  = max(final)
        winners_idx = [i for i, s in enumerate(final) if s == best]
        share = 1.0 / len(winners_idx)
        for i in winners_idx:
            scenario_wins[i] += share
        total_scenarios[0] += 1

    _recurse(actual, [0.0] * len(ranked))

    tot = total_scenarios[0] or 1
    raw     = [scenario_wins[i] / tot * 100 for i in range(len(ranked))]
    rounded = [round(p, 1) for p in raw]
    diff    = round(100.0 - sum(rounded), 1)
    if rounded:
        rounded[0] = round(rounded[0] + diff, 1)
    return rounded


def rank_participants(all_picks_list, results):
    """Score all participants and return a sorted leaderboard.

    Args:
        all_picks_list: list of dicts from sheets.get_all_picks(), each with
                        keys 'name', 'timestamp', 'picks'
        results:        list of completed game result dicts from espn_api

    Returns a list of dicts sorted by score descending (ties broken by name).
    """
    ranked = []
    for entry in all_picks_list:
        scores   = calculate_scores(entry["picks"], results)
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
            "method":         entry.get("method", "custom"),
        })

    ranked.sort(key=lambda x: (-x["score"], x["name"]))
    return ranked
