# app.py
# ---------------------------------------------------------------------------
# Main Streamlit application for the 2026 NCAA Bracket Pool.
#
# Streamlit works by running this file top-to-bottom every time a user
# interacts with anything. That's why we use st.session_state to remember
# things between those reruns (like the picks a user has made so far).
#
# Two modes:
#   BEFORE deadline → show the bracket pick submission form
#   AFTER deadline  → show the leaderboard and completed game results
# ---------------------------------------------------------------------------

import streamlit as st
from datetime import datetime

from config import SUBMISSION_DEADLINE, CT
from bracket_data import (
    GAMES, GAME_BY_ID, TEAM_SEEDS, REGION_ORDER, ROUND_NAMES,
    get_region_games, resolve_teams,
)
from espn_api import get_tournament_results
from scoring import rank_participants
from sheets import save_picks, get_all_picks, check_already_submitted


# ---------------------------------------------------------------------------
# PAGE CONFIG — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="2026 NCAA Bracket Pool",
    page_icon="🏀",
    layout="wide",
)


# ---------------------------------------------------------------------------
# CUSTOM CSS
# ---------------------------------------------------------------------------
# We inject CSS to make the app look more bracket-like. Streamlit's default
# styling is functional but plain — this adds color and structure.
st.markdown("""
<style>
    /* Main accent colors — navy and orange, classic basketball palette */
    :root {
        --navy:  #1a3c6e;
        --orange: #e8651a;
        --light-gray: #f5f5f5;
        --border: #d0d8e4;
    }

    /* App title area */
    h1 { color: var(--navy); }
    h2 { color: var(--navy); }
    h3 { color: var(--navy); font-size: 1rem; }

    /* Style each game's selectbox to look like a bracket slot */
    .stSelectbox > label {
        font-size: 0.75rem;
        color: #555;
    }
    .stSelectbox > div > div {
        border: 1.5px solid var(--border) !important;
        border-radius: 4px !important;
        background-color: white !important;
    }

    /* Picked winner highlight — applied via the "correct pick" indicator */
    .pick-correct { color: #2e7d32; font-weight: bold; }
    .pick-wrong   { color: #c62828; }

    /* Round column headers */
    .round-header {
        background-color: var(--navy);
        color: white;
        text-align: center;
        padding: 6px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85rem;
        margin-bottom: 8px;
    }

    /* Game seed display */
    .seed-badge {
        display: inline-block;
        background: var(--navy);
        color: white;
        border-radius: 3px;
        padding: 0 4px;
        font-size: 0.7rem;
        margin-right: 3px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# ---------------------------------------------------------------------------
# st.session_state persists across reruns within the same browser session.
# We store all bracket picks here so they survive Streamlit's rerun cycle.
if "picks" not in st.session_state:
    st.session_state.picks = {}  # {game_id: team_name}

if "submitted" not in st.session_state:
    st.session_state.submitted = False  # True after a successful submission


# ---------------------------------------------------------------------------
# MAIN ROUTING
# ---------------------------------------------------------------------------
def main():
    """Entry point. Routes to submission form or leaderboard based on deadline."""
    st.title("🏀 2026 NCAA Bracket Pool")

    now = datetime.now(CT)

    if now < SUBMISSION_DEADLINE:
        # Tournament hasn't started — show the pick submission form
        show_submission_form(now)
    else:
        # Tournament is underway — show leaderboard only
        show_leaderboard()


# ===========================================================================
# SUBMISSION FORM
# ===========================================================================

def show_submission_form(now):
    """Show the bracket pick form before the submission deadline."""

    # --- Countdown timer ---
    time_left = SUBMISSION_DEADLINE - now
    hours, remainder = divmod(int(time_left.total_seconds()), 3600)
    minutes = remainder // 60
    st.info(f"⏱ Submissions close in **{hours}h {minutes}m** — March 19 at 11:00 AM CT")

    # --- Show success message if they just submitted ---
    if st.session_state.submitted:
        st.success("✅ Your bracket has been submitted! Refresh to submit a new one or close this tab.")
        if st.button("Submit another bracket"):
            st.session_state.submitted = False
            st.session_state.picks = {}
            st.rerun()
        return

    # --- Name field ---
    st.markdown("### Your Name")
    name = st.text_input(
        "Enter your name",
        placeholder="First Last",
        help="Use the same name each time if you want to update your picks before the deadline.",
        label_visibility="collapsed",
    )

    # --- Progress bar ---
    # Count how many of the 63 games have been picked so far
    total_games = 63
    picks_made = sum(1 for v in st.session_state.picks.values() if v)
    pct = picks_made / total_games
    st.markdown(f"**Bracket progress: {picks_made} / {total_games} picks made**")
    st.progress(pct)

    # --- Bracket tabs ---
    # Each region gets its own tab; Final Four and Championship go in a 5th tab.
    tabs = st.tabs(["East", "South", "West", "Midwest", "🏆 Final Four & Champ"])

    for i, region in enumerate(REGION_ORDER):
        with tabs[i]:
            render_region_tab(region, st.session_state.picks)

    with tabs[4]:
        render_final_four_tab(st.session_state.picks)

    # --- Submit button ---
    st.markdown("---")
    all_picked = picks_made == total_games
    name_entered = bool(name and name.strip())

    if not name_entered:
        st.warning("Enter your name above before submitting.")
    elif not all_picked:
        st.warning(f"Pick all 63 games before submitting. ({total_games - picks_made} remaining)")
    else:
        # Check for duplicate submissions and warn (but don't block)
        already_in = check_already_submitted(name.strip())
        if already_in:
            st.warning(f"⚠️ A bracket for **{name.strip()}** already exists. "
                       "Submitting again will replace it with your latest picks.")

        if st.button("🏀 Submit My Bracket", type="primary"):
            try:
                save_picks(name.strip(), st.session_state.picks)
                st.session_state.submitted = True
                st.rerun()
            except Exception as e:
                st.error(f"Error saving picks: {e}")


def render_region_tab(region, picks):
    """Render the full bracket for one region as 4 side-by-side columns.

    The four columns represent: Round of 64 | Round of 32 | Sweet 16 | Elite 8.
    Games in later rounds are spaced with empty lines to visually align them
    with the two games that feed into them.

    Args:
        region: 'East', 'South', 'West', or 'Midwest'
        picks:  st.session_state.picks dict (mutated in place as user picks)
    """
    st.markdown(f"### {region} Region")

    region_games = get_region_games(region)  # all games rounds 1-4 for this region

    # Split games by round for column rendering
    r64   = [g for g in region_games if g["round"] == 1]  # 8 games
    r32   = [g for g in region_games if g["round"] == 2]  # 4 games
    s16   = [g for g in region_games if g["round"] == 3]  # 2 games
    e8    = [g for g in region_games if g["round"] == 4]  # 1 game

    # Four columns, with R64 wider since it has the most games
    col_r64, col_r32, col_s16, col_e8 = st.columns([3, 3, 3, 2])

    with col_r64:
        st.markdown('<div class="round-header">Round of 64</div>', unsafe_allow_html=True)
        for game in r64:
            render_game_picker(game, picks)

    with col_r32:
        st.markdown('<div class="round-header">Round of 32</div>', unsafe_allow_html=True)
        # Each R32 game aligns between 2 R64 games, so add 1 spacer before each
        for game in r32:
            st.write("")  # spacer for visual alignment
            render_game_picker(game, picks)
            st.write("")  # spacer after

    with col_s16:
        st.markdown('<div class="round-header">Sweet 16</div>', unsafe_allow_html=True)
        # Each S16 game aligns between 2 R32 games; 3 spacers approximates this
        for game in s16:
            st.write("")
            st.write("")
            st.write("")
            render_game_picker(game, picks)
            st.write("")
            st.write("")

    with col_e8:
        st.markdown('<div class="round-header">Elite 8</div>', unsafe_allow_html=True)
        # Single Elite 8 game — push it down to roughly the middle of the column
        for _ in range(7):
            st.write("")
        for game in e8:
            render_game_picker(game, picks)


def render_final_four_tab(picks):
    """Render the Final Four and Championship picks in the 5th tab.

    Shows two Final Four games side by side, then the Championship below.
    """
    st.markdown("### 🏆 Final Four & National Championship")
    st.caption("Indianapolis, IN — April 4 & 6, 2026")

    # Final Four: two games side by side
    ff_games = [g for g in GAMES if g["round"] == 5]
    col1, spacer, col2 = st.columns([3, 1, 3])

    labels = ["East/South semifinal", "West/Midwest semifinal"]
    for col, game, label in zip([col1, col2], ff_games, labels):
        with col:
            st.markdown(f"**{label}**")
            render_game_picker(game, picks)

    # Championship
    st.markdown("---")
    st.markdown("#### 🏆 National Championship — April 6")
    champ_games = [g for g in GAMES if g["round"] == 6]
    _, center, _ = st.columns([2, 3, 2])
    with center:
        for game in champ_games:
            render_game_picker(game, picks)


def render_game_picker(game, picks):
    """Render a single game as a labeled selectbox.

    For Round 1, shows the two known teams with their seeds.
    For later rounds, shows whoever the user picked to win the feeder games.
    If feeder picks are missing, shows a disabled placeholder message.

    The selectbox key (f"pick_{game_id}") is tied to st.session_state,
    which means Streamlit automatically remembers the selection across reruns.

    Args:
        game:  a game dict from bracket_data.GAMES
        picks: the st.session_state.picks dict
    """
    game_id = game["id"]

    # Resolve which two teams are in this game
    team_a, seed_a, team_b, seed_b = resolve_teams(game_id, picks)

    if not team_a or not team_b:
        # Feeder games haven't been picked yet
        st.caption("⏳ Pick earlier rounds first")
        return

    # Build display labels like "(1) Duke" and "(16) Siena"
    label_a = f"({seed_a}) {team_a}" if seed_a else team_a
    label_b = f"({seed_b}) {team_b}" if seed_b else team_b

    # The options list: blank prompt first, then the two teams
    options = ["— pick winner —", label_a, label_b]

    # Figure out which option is currently selected (if any)
    current_pick = picks.get(game_id)
    if current_pick == team_a:
        current_idx = 1
    elif current_pick == team_b:
        current_idx = 2
    else:
        current_idx = 0  # Nothing picked yet (or pick was invalidated)

    # Render the selectbox. The key saves its value to st.session_state automatically.
    chosen_label = st.selectbox(
        label=f"{game_id.upper()}",           # e.g., "G1"
        options=options,
        index=current_idx,
        key=f"pick_{game_id}",
        label_visibility="collapsed",         # hide the label; context is clear from position
    )

    # Map the chosen label back to a plain team name and store it
    if chosen_label == label_a:
        picks[game_id] = team_a
    elif chosen_label == label_b:
        picks[game_id] = team_b
    else:
        # User selected the blank prompt — clear any previous pick
        picks[game_id] = None

        # Cascade: if this pick was cleared, any downstream picks that depended
        # on this game's winner are now invalid. Clear them too.
        _clear_downstream(game_id, picks)


def _clear_downstream(game_id, picks):
    """Recursively clear picks for any games that depend on this game's winner.

    Example: if you unpick your East Elite 8 winner, your Final Four pick
    (East vs South game) should also be cleared since it was based on who
    you thought would win the East.

    Args:
        game_id: the game whose pick was just cleared
        picks:   the picks dict to modify in place
    """
    game = GAME_BY_ID.get(game_id)
    if not game:
        return
    next_id = game.get("next_game")
    if not next_id:
        return  # This was the Championship — nothing downstream

    # Clear the next game's pick and continue down the chain
    picks[next_id] = None
    _clear_downstream(next_id, picks)


# ===========================================================================
# LEADERBOARD
# ===========================================================================

def show_leaderboard():
    """Show the leaderboard and completed game results after the deadline.

    Pulls picks from Google Sheets, fetches ESPN results, scores everything,
    and displays a ranked table.
    """
    st.markdown("### 📊 Standings")
    st.caption(f"Scores update every hour. Last source: ESPN scoreboard API.")

    # --- Load data ---
    with st.spinner("Loading picks and scores..."):
        try:
            all_picks = get_all_picks()
        except Exception as e:
            st.error(f"Could not load picks from Google Sheets: {e}")
            return

        try:
            results = get_tournament_results()
        except Exception as e:
            st.warning(f"Could not load ESPN results: {e}. Showing picks only.")
            results = []

    if not all_picks:
        st.info("No picks have been submitted yet.")
        return

    # --- Score everyone ---
    ranked = rank_participants(all_picks, results)

    # --- Leaderboard table ---
    # Build a list of dicts for st.dataframe to display as a clean table
    table_rows = []
    for rank, entry in enumerate(ranked, start=1):
        table_rows.append({
            "Rank":         rank,
            "Name":         entry["name"],
            "Total Pts":    entry["score"],
            "Correct Picks": entry["correct"],
            "Base Pts":     entry["base_pts"],
            "Upset Bonus":  entry["upset_pts"],
            "Margin Bonus": entry["margin_pts"],
        })

    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
    )

    # --- Completed games results ---
    st.markdown("---")
    st.markdown("### 🏀 Completed Games")

    if not results:
        st.info("No completed games yet. Check back after March 19.")
        return

    # Show results grouped by showing winner vs loser with score
    for result in results:
        col1, col2, col3 = st.columns([3, 1, 3])
        with col1:
            seed_w = TEAM_SEEDS.get(result["winner"], "?")
            st.markdown(f"✅ **({seed_w}) {result['winner']}**")
        with col2:
            st.markdown(f"**{result['winner_score']} – {result['loser_score']}**")
        with col3:
            seed_l = TEAM_SEEDS.get(result["loser"], "?")
            st.markdown(f"({seed_l}) {result['loser']}")


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__" or True:
    # Streamlit runs this file as a script, so calling main() here boots the app.
    main()
