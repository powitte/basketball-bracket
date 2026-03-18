# app.py
# ---------------------------------------------------------------------------
# Main Streamlit application for Trale's 2026 NCAA Bracket Pool.
#
# Streamlit works by running this file top-to-bottom every time a user
# interacts with anything. That's why we use st.session_state to remember
# things between those reruns (like the picks a user has made so far).
#
# Two modes:
#   BEFORE deadline → show the bracket pick submission form
#   AFTER deadline  → show the leaderboard and completed game results
# ---------------------------------------------------------------------------

import random
import streamlit as st
from datetime import datetime
import fitz  # PyMuPDF — converts the bracket PDF to a displayable image

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
    page_title="Trale's 2026 NCAA Bracket Pool",
    page_icon="🏀",
    layout="wide",
)


# ---------------------------------------------------------------------------
# CUSTOM CSS
# ---------------------------------------------------------------------------
# Orange is the primary accent (Trale's pick). Navy is the secondary.
# We inject CSS once at the top so every element in the app can use it.
#
# IMPORTANT: `color-scheme: light` on :root tells the browser to use light-mode
# system colors throughout the page. Without this, Chrome on a Chromebook in
# dark mode can inherit white text — which is invisible on our white backgrounds.
st.markdown("""
<style>
    /* Force light-mode rendering — prevents white-on-white text in Chrome dark mode */
    :root {
        color-scheme: light;
    }

    /* ── Color palette ── */
    :root {
        --orange:      #E8651A;
        --orange-dark: #C04F0E;
        --orange-light:#FFF0E6;
        --navy:        #1B3A6B;
        --navy-light:  #2C5499;
        --gold:        #F5C518;
        --silver:      #A8A9AD;
        --bronze:      #CD7F32;
        --bg:          #F9F6F2;
        --white:       #FFFFFF;
        --border:      #E0D6CC;
        --text-muted:  #7A6F68;
        --text-dark:   #1E1E1E;
    }

    /* ── Page background ── */
    .stApp { background-color: var(--bg); }

    /* ── Main title ── */
    h1 {
        color: var(--navy) !important;
        font-size: 2rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.5px;
    }

    /* ── Section headings ── */
    h2, h3 { color: var(--navy) !important; }

    /* ── Tab strip ── */
    .stTabs [data-baseweb="tab-list"] {
        background-color: var(--navy);
        border-radius: 8px 8px 0 0;
        gap: 2px;
        padding: 4px 4px 0 4px;
    }
    .stTabs [data-baseweb="tab"] {
        color: rgba(255,255,255,0.7) !important;
        font-weight: 600;
        border-radius: 6px 6px 0 0;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--orange) !important;
        color: white !important;
    }

    /* ── Selectbox (bracket slot) styling ── */
    /* The label is hidden — the matchup placeholder serves as the label */
    .stSelectbox > label { display: none; }
    .stSelectbox > div > div {
        border: 2px solid var(--border) !important;
        border-radius: 6px !important;
        background-color: var(--white) !important;
        color: var(--text-dark) !important;   /* explicit dark text — Chrome dark mode fix */
        font-size: 0.85rem !important;
    }
    .stSelectbox > div > div:hover {
        border-color: var(--orange) !important;
    }
    /* Covers the selected-value text inside the selectbox control */
    [data-baseweb="select"] > div {
        color: var(--text-dark) !important;
        background-color: var(--white) !important;
    }
    /* Dropdown list options (the popup that appears when you click) */
    [data-baseweb="popover"] li,
    [data-baseweb="menu"] li {
        color: var(--text-dark) !important;
        background-color: var(--white) !important;
    }

    /* ── Expander (bracket PDF viewer) ── */
    /* Chrome dark mode can render expander summary text as white — force navy */
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span {
        color: var(--navy) !important;
    }

    /* ── Round column header banners ── */
    .round-header {
        background: linear-gradient(135deg, var(--navy), var(--navy-light));
        color: white;
        text-align: center;
        padding: 8px 4px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
        margin-bottom: 10px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    /* ── Scoring rules card ── */
    .scoring-card {
        background: linear-gradient(135deg, var(--navy), var(--navy-light));
        color: white;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 8px 0 16px 0;
    }
    .scoring-card h4 {
        color: var(--orange) !important;
        margin: 0 0 10px 0;
        font-size: 1rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .scoring-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        font-size: 0.9rem;
    }
    .scoring-row:last-child { border-bottom: none; }
    .scoring-pts {
        font-weight: 800;
        color: var(--orange);
        font-size: 1rem;
    }

    /* ── Leaderboard medal rows ── */
    .medal-gold   { background-color: rgba(245,197,24,0.15);  border-left: 4px solid var(--gold); }
    .medal-silver { background-color: rgba(168,169,173,0.15); border-left: 4px solid var(--silver); }
    .medal-bronze { background-color: rgba(205,127,50,0.15);  border-left: 4px solid var(--bronze); }

    /* ── Progress bar color ── */
    .stProgress > div > div > div { background-color: var(--orange) !important; }

    /* ── Primary button ── */
    .stButton > button[kind="primary"] {
        background-color: var(--orange) !important;
        border-color: var(--orange-dark) !important;
        font-weight: 700;
        font-size: 1rem;
        padding: 0.5rem 2rem;
        border-radius: 8px;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--orange-dark) !important;
    }

    /* ── Info / warning / success boxes ── */
    .stAlert { border-radius: 8px; }

    /* ── Countdown banner ── */
    .countdown-banner {
        background: linear-gradient(135deg, var(--orange), var(--orange-dark));
        color: white;
        border-radius: 10px;
        padding: 12px 20px;
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 16px;
        text-align: center;
    }

    /* ── Completed game result rows ── */
    .game-result {
        background: white;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 4px 0;
        border-left: 4px solid var(--orange);
        display: flex;
        align-items: center;
        gap: 12px;
    }

    /* ── Strategy description card (used in Help me pick section) ── */
    .strategy-card {
        background: linear-gradient(135deg, #2C5499, #1B3A6B);
        border-radius: 10px;
        padding: 14px 18px;
        margin: 6px 0 10px 0;
        color: white;
        font-size: 0.9rem;
    }
    .strategy-card b { color: var(--gold); }
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

# method: how the user filled their bracket
#   "custom"  — filled manually (default), or modified an auto-filled bracket
#   "seed"    — auto-filled by seed (chalk)
#   "mascot"  — auto-filled by mascot battle ratings
#   "random"  — auto-filled by pure coin flip
if "method" not in st.session_state:
    st.session_state.method = "custom"

# auto_fill_snapshot: a copy of picks immediately after auto-fill.
# We compare current picks against this snapshot on every rerun;
# any difference means the user manually changed something → method = "custom".
if "auto_fill_snapshot" not in st.session_state:
    st.session_state.auto_fill_snapshot = None

# fill_version increments each time the user applies an auto-fill strategy.
# render_game_picker appends it to every selectbox key, giving each auto-fill
# a fresh widget key so Streamlit has no stale internal state to restore.
# (Stale widget state from prior renders overrides index= — new keys don't.)
if "fill_version" not in st.session_state:
    st.session_state.fill_version = 0


# ---------------------------------------------------------------------------
# MAIN ROUTING
# ---------------------------------------------------------------------------
def main():
    """Entry point — routes to submission form or leaderboard based on deadline."""

    # Header with logo-style title
    col_title, col_logo = st.columns([5, 1])
    with col_title:
        st.title("🏀 Trale's 2026 NCAA Bracket Pool")
    with col_logo:
        st.markdown("<div style='text-align:right; font-size:3rem; padding-top:10px'>🏆</div>",
                    unsafe_allow_html=True)

    now = datetime.now(CT)

    if now < SUBMISSION_DEADLINE:
        show_submission_form(now)
    else:
        show_leaderboard()


# ===========================================================================
# SHARED COMPONENTS
# ===========================================================================

def render_scoring_rules():
    """Display a styled scoring rules card.

    Called on both the submission page (so people know what they're playing for)
    and the leaderboard page (so they can understand the score breakdown).
    """
    st.markdown("""
    <div class="scoring-card">
        <h4>📋 How scoring works</h4>
        <div class="scoring-row">
            <span>✅ Correct winner pick — any round</span>
            <span class="scoring-pts">+10 pts</span>
        </div>
        <div class="scoring-row">
            <span>🔥 Upset bonus — higher seed beats lower seed</span>
            <span class="scoring-pts">+4 pts</span>
        </div>
        <div class="scoring-row">
            <span>📊 Margin bonus — half the final point margin</span>
            <span class="scoring-pts">+½ margin</span>
        </div>
    </div>
    <p style="font-size:0.8rem; color:#7A6F68; margin-top:-8px;">
        Example: You pick a 12-seed to beat a 5-seed by 14 points →
        <strong>+10</strong> (correct) <strong>+4</strong> (upset) <strong>+7</strong> (margin) = <strong>21 pts</strong>
    </p>
    """, unsafe_allow_html=True)


def render_bracket_image():
    """Convert the PDF bracket to a PNG image and display it in an expander.

    PyMuPDF (imported as fitz) renders the PDF page at 2× zoom for crisp display.
    The PDF stays in the repo as the source of truth; this just shows it inline.
    """
    with st.expander("📋 View the full 2026 bracket (click to expand)", expanded=False):
        try:
            # Open the PDF and render the first (only) page to pixels
            doc = fitz.open("2026_bracket.pdf")
            page = doc[0]
            # Matrix(2, 2) = 2× zoom in both dimensions → sharp image at ~144 dpi
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            doc.close()
            st.image(img_bytes, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not render bracket image: {e}")


# ===========================================================================
# AUTO-PICK STRATEGIES
# ===========================================================================
# Three strategies for automatically filling all 63 game picks.
# All three process games in round order (1 → 6) so that each round's results
# are available before the next round tries to resolve its team matchups.
# They build and return a fresh picks dict without touching session state directly.

# ---------------------------------------------------------------------------
# MASCOT POWER RATINGS
# ---------------------------------------------------------------------------
# Scale 1–10. Higher = wins the hypothetical fight.
# Used by the "mascot battle" auto-fill strategy. Ties are randomized.
# Ratings are intentionally a bit opinionated and fun — argue with your bracket.
MASCOT_POWER = {
    # ── East ──
    "Duke":          7,   # Blue Devils — supernatural, but more mischievous than menacing
    "Siena":         5,   # Saints — holy, but not exactly fighters
    "Ohio St.":      2,   # Buckeyes — it is literally a nut
    "TCU":           5,   # Horned Frogs — cool name, still a frog
    "St. John's":    6,   # Red Storm — weather force counts
    "N. Iowa":       8,   # Panthers — big cat
    "Kansas":        5,   # Jayhawks — mythological bird/soldier hybrid
    "Cal Baptist":   6,   # Lancers — mounted knight with a lance
    "Louisville":    4,   # Cardinals — small bird
    "South Florida": 7,   # Bulls — 1,500 lb aggressive animal
    "Michigan St.":  8,   # Spartans — elite ancient warriors
    "N. Dakota St.": 7,   # Bison — massive, powerful
    "UCLA":          8,   # Bruins — bears
    "UCF":           7,   # Knights — armored warrior
    "UConn":         6,   # Huskies — tough working sled dog
    "Furman":        6,   # Paladins — holy knights
    # ── South ──
    "Florida":       9,   # Gators — apex predator
    "PVAM/LEH":      7,   # Panthers/Mountain Hawks — big cat + predatory bird, averaged
    "Clemson":       9,   # Tigers — apex predator
    "Iowa":          5,   # Hawkeyes — sharp-eyed human (literary character, not a bird)
    "Vanderbilt":    5,   # Commodores — naval officer rank
    "McNeese":       5,   # Cowboys — tough, but still a human
    "Nebraska":      3,   # Cornhuskers — farmer
    "Troy":          7,   # Trojans — ancient elite warriors
    "N. Carolina":   4,   # Tar Heels — Civil War infantry nickname (stubbornness, not ferocity)
    "VCU":           7,   # Rams — aggressive horned animal
    "Illinois":      6,   # Illini — tribal warrior
    "Penn":          2,   # Quakers — literally committed to nonviolence
    "Saint Mary's":  5,   # Gaels — Celtic/Irish warriors
    "Texas A&M":     3,   # Aggies — agriculture students
    "Houston":       9,   # Cougars — apex predator (big cat)
    "Idaho":         6,   # Vandals — Germanic warriors who sacked Rome
    # ── West ──
    "Arizona":       8,   # Wildcats — fierce cat
    "LIU":           9,   # Sharks — apex ocean predator
    "Villanova":     8,   # Wildcats — fierce cat
    "Utah St.":      3,   # Aggies — agriculture students
    "Wisconsin":     7,   # Badgers — ferocious relative to their size
    "High Point":    8,   # Panthers — big cat
    "Arkansas":      8,   # Razorbacks — feral wild boar, notoriously aggressive
    "Hawaii":        7,   # Warriors — general warrior class
    "BYU":           9,   # Cougars — apex predator (big cat)
    "TEX/NCST":      8,   # Longhorns/Wolfpack — large horned bovine / wolf pack
    "Gonzaga":       6,   # Bulldogs — tough dog
    "Kennesaw St.":  5,   # Owls — predatory but small
    "Miami":         7,   # Hurricanes — devastating natural force
    "Missouri":      9,   # Tigers — apex predator
    "Purdue":        4,   # Boilermakers — industrial worker
    "Queens":        5,   # Royals — status, not fighters
    # ── Midwest ──
    "Michigan":      10,  # Wolverines — pound for pound the most ferocious animal alive
    "UMBC/HOW":      5,   # Retrievers/Bison — friendly dog + massive animal, averaged to 5
    "Georgia":       6,   # Bulldogs — tough dog
    "Saint Louis":   3,   # Billikens — a small good-luck gnome figurine
    "Texas Tech":    6,   # Red Raiders — cavalry raiders
    "Akron":         4,   # Zips — named after a rubber boot brand (Zipper boots)
    "Alabama":       6,   # Crimson Tide — tidal force
    "Hofstra":       5,   # Pride — it's the concept of a lion pride, not a lion itself
    "Tennessee":     5,   # Volunteers — civilian soldiers
    "M-OH/SMU":      6,   # RedHawks/Mustangs — predatory bird / wild horse, averaged
    "Virginia":      6,   # Cavaliers — royalist cavalry
    "Wright St.":    6,   # Raiders — military raiders
    "Kentucky":      8,   # Wildcats — fierce cat
    "Santa Clara":   6,   # Broncos — wild horse
    "Iowa St.":      7,   # Cyclones — destructive weather
    "Tennessee St.": 9,   # Tigers — apex predator
}


def auto_pick_by_seed():
    """Fill all 63 games by always picking the better (lower) seed.

    Equal seeds and the Championship game (round 6) are randomized.
    The user requested random for "the finals" — because at that point
    any 1-seed can win, and chalk just means everyone ties.

    Processes rounds in order so that each round's picks are ready
    before the next round's resolve_teams() calls need them.

    Returns a complete picks dict {game_id: team_name}.
    """
    picks = {}
    for round_num in range(1, 7):
        for game in GAMES:
            if game["round"] != round_num:
                continue
            team_a, seed_a, team_b, seed_b = resolve_teams(game["id"], picks)
            if not team_a or not team_b:
                continue  # should not happen in a well-formed bracket

            if game["round"] == 6:
                # Championship: randomize regardless of seeds
                picks[game["id"]] = random.choice([team_a, team_b])
            elif seed_a < seed_b:
                picks[game["id"]] = team_a   # team_a is the better seed
            elif seed_b < seed_a:
                picks[game["id"]] = team_b   # team_b is the better seed
            else:
                # Equal seeds (common in later rounds, e.g., two 1-seeds) → coin flip
                picks[game["id"]] = random.choice([team_a, team_b])
    return picks


def auto_pick_by_mascot():
    """Fill all 63 games using the MASCOT_POWER fight ratings above.

    Higher power wins. Ties are randomized.
    Returns a complete picks dict {game_id: team_name}.
    """
    picks = {}
    for round_num in range(1, 7):
        for game in GAMES:
            if game["round"] != round_num:
                continue
            team_a, seed_a, team_b, seed_b = resolve_teams(game["id"], picks)
            if not team_a or not team_b:
                continue

            power_a = MASCOT_POWER.get(team_a, 5)  # default 5 if team somehow not in dict
            power_b = MASCOT_POWER.get(team_b, 5)

            if power_a > power_b:
                picks[game["id"]] = team_a
            elif power_b > power_a:
                picks[game["id"]] = team_b
            else:
                # Equal mascot power → coin flip
                picks[game["id"]] = random.choice([team_a, team_b])
    return picks


def auto_pick_random():
    """Fill all 63 games by random coin flip.

    Returns a complete picks dict {game_id: team_name}.
    """
    picks = {}
    for round_num in range(1, 7):
        for game in GAMES:
            if game["round"] != round_num:
                continue
            team_a, seed_a, team_b, seed_b = resolve_teams(game["id"], picks)
            if not team_a or not team_b:
                continue
            picks[game["id"]] = random.choice([team_a, team_b])
    return picks


def apply_auto_picks(new_picks, method):
    """Write auto-generated picks into session state and record the strategy.

    We increment fill_version so render_game_picker uses a fresh widget key
    for every selectbox. Fresh keys have no prior Streamlit internal state,
    so they always initialize from index= (which we compute from the new picks).

    This is more reliable than trying to overwrite existing widget state:
    Streamlit prefers its own internal widget state over programmatic
    session_state assignments for widgets that rendered in a prior run —
    causing R64 selectboxes to ignore the new pick and revert to the
    matchup placeholder they had on first page load.
    """
    st.session_state.picks = new_picks
    st.session_state.auto_fill_snapshot = dict(new_picks)
    st.session_state.method = method
    st.session_state.fill_version += 1  # triggers fresh widget keys on next render


# ===========================================================================
# MISSING PICKS DIAGNOSTIC
# ===========================================================================

def find_missing_games(picks):
    """Return human-readable descriptions of any games that are still unpicked.

    Only reports games where both teams are already determined — i.e., all
    upstream picks have been made. Games that are locked behind earlier
    unresolved matchups aren't counted here; they'll surface naturally as
    the user fills those earlier rounds.

    Returns a list of strings like ["Final Four tab → Championship"].
    This is intentionally a navigation hint, not just a game ID.
    """
    missing = []
    for game in GAMES:
        team_a, _, team_b, _ = resolve_teams(game["id"], picks)
        if not team_a or not team_b:
            continue  # matchup not determinable yet — skip
        if not picks.get(game["id"]):
            region = game["region"]
            round_name = ROUND_NAMES[game["round"]]
            if game["round"] >= 5:
                # Final Four and Championship are both in the Final Four tab
                missing.append(f"**Final Four tab** → {round_name}")
            else:
                missing.append(f"**{region} tab** → {round_name}")
    return missing


# ===========================================================================
# SUBMISSION FORM
# ===========================================================================

# Human-readable labels and icons for each method key
METHOD_ICONS  = {"custom": "🎨", "seed": "🌱", "mascot": "⚔️", "random": "🎲"}
METHOD_LABELS = {"custom": "Custom", "seed": "By seed", "mascot": "Mascot battle", "random": "Random"}


def show_submission_form(now):
    """Show the bracket pick form before the submission deadline."""

    # --- Detect manual edits after auto-fill ---
    # If picks have diverged from the auto-fill snapshot, mark method as custom.
    # This runs at the top of every rerun so it always reflects the latest state.
    snapshot = st.session_state.auto_fill_snapshot
    if snapshot is not None and st.session_state.picks != snapshot:
        st.session_state.method = "custom"
        st.session_state.auto_fill_snapshot = None

    # --- Countdown banner ---
    time_left = SUBMISSION_DEADLINE - now
    hours, remainder = divmod(int(time_left.total_seconds()), 3600)
    minutes = remainder // 60
    st.markdown(
        f'<div class="countdown-banner">'
        f'⏱ Submissions close in <strong>{hours}h {minutes}m</strong>'
        f' &nbsp;·&nbsp; Deadline: March 19 at 11:00 AM CT'
        f'</div>',
        unsafe_allow_html=True,
    )

    # --- Success state after submitting ---
    if st.session_state.submitted:
        st.success("✅ Your bracket has been submitted! You're all set.")
        return

    # --- Scoring rules + bracket image side by side ---
    col_rules, col_bracket = st.columns([2, 3])
    with col_rules:
        render_scoring_rules()
    with col_bracket:
        render_bracket_image()

    st.markdown("---")

    # ── Step 1: Name ──────────────────────────────────────────────────────────
    st.markdown("### Step 1 — Enter your name")
    name = st.text_input(
        "Your name",
        placeholder="First Last",
        help="Use the same name if you want to update your picks before the deadline.",
        label_visibility="collapsed",
    )

    st.markdown("---")

    # ── Step 1.5: Help me pick (optional) ────────────────────────────────────
    st.markdown("### 🤔 Need help? Pick a strategy *(optional)*")
    st.caption(
        "Select a strategy to auto-fill all 63 picks instantly. "
        "You can change individual picks afterward — it'll be marked Custom."
    )

    # Map display label → internal method key (None = no auto-fill)
    STRATEGY_OPTIONS = {
        "(I'll fill it myself)":                        None,
        "🌱 By seed — chalk, always pick the favorite": "seed",
        "⚔️ Mascot battle — fiercer mascot wins":       "mascot",
        "🎲 Random — pure coin flip, no regrets":        "random",
    }

    chosen_strategy_label = st.selectbox(
        "Pick a strategy",
        options=list(STRATEGY_OPTIONS.keys()),
        key="strategy_dropdown",
        label_visibility="collapsed",
    )
    chosen_strategy = STRATEGY_OPTIONS[chosen_strategy_label]

    if chosen_strategy is not None:
        # Auto-fill and continue rendering in this same script execution.
        #
        # WHY NO st.rerun(): apply_auto_picks increments fill_version, giving
        # every bracket selectbox a fresh widget key. If we call st.rerun(),
        # those fresh keys exist only in session state — Streamlit still has
        # internal widget state from the page load for the OLD keys, and the
        # rerun-based initialization of fresh keys from index= has proven
        # unreliable across Streamlit Cloud versions. By NOT calling st.rerun(),
        # the bracket renders in the same run as the auto-fill. The fresh keys
        # (pick_gX_v<new_version>) are definitively brand-new at render time,
        # so index=current_idx is guaranteed to control the displayed value.
        #
        # Side effect: the strategy dropdown stays on the chosen option for
        # this one render. Deleting the key here means on the next user
        # interaction it resets to "(I'll fill it myself)".
        if chosen_strategy == "seed":
            new_picks = auto_pick_by_seed()
        elif chosen_strategy == "mascot":
            new_picks = auto_pick_by_mascot()
        else:
            new_picks = auto_pick_random()
        apply_auto_picks(new_picks, chosen_strategy)
        del st.session_state["strategy_dropdown"]  # resets on next interaction

    # Show a status badge if a strategy is currently active
    current_method = st.session_state.method
    if current_method != "custom":
        st.success(
            f"{METHOD_ICONS[current_method]} Bracket filled using "
            f"**{METHOD_LABELS[current_method]}**. Change any pick to go Custom."
        )

    st.markdown("---")

    # ── Step 2: Bracket ───────────────────────────────────────────────────────
    total_games = 63
    picks_made = sum(1 for v in st.session_state.picks.values() if v)
    pct = picks_made / total_games
    st.markdown(f"### Step 2 — Fill out your bracket &nbsp; `{picks_made} / {total_games} picks`")
    st.progress(pct)

    # When 5 or fewer picks remain, show exactly which game(s) are missing
    # so the user doesn't have to hunt through every tab to find the last one.
    if 0 < (total_games - picks_made) <= 5:
        missing = find_missing_games(st.session_state.picks)
        if missing:
            st.info("📍 **Still need to pick:** " + " · ".join(missing))

    # --- Bracket tabs ---
    tabs = st.tabs(["🔵 East", "🟠 South", "🔴 West", "🟢 Midwest", "🏆 Final Four"])

    for i, region in enumerate(REGION_ORDER):
        with tabs[i]:
            render_region_tab(region, st.session_state.picks)

    with tabs[4]:
        render_final_four_tab(st.session_state.picks)

    # ── Step 3: Submit ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Step 3 — Submit")

    all_picked = picks_made == total_games
    name_entered = bool(name and name.strip())

    if not name_entered:
        st.warning("⬆ Enter your name in Step 1 before submitting.")
    elif not all_picked:
        st.warning(f"⬆ Complete all 63 picks in Step 2. ({total_games - picks_made} remaining)")
    else:
        # check_already_submitted hits Google Sheets — wrap it so a sheets error
        # doesn't crash the whole page and wipe the user's session state.
        try:
            already_in = check_already_submitted(name.strip())
            if already_in:
                st.info(f"ℹ️ A bracket for **{name.strip()}** already exists — submitting again will replace it.")
        except Exception:
            already_in = False  # assume not submitted; save_picks will surface any real error

        method = st.session_state.method
        st.caption(f"Bracket strategy: {METHOD_ICONS[method]} {METHOD_LABELS[method]}")

        if st.button("🏀 Submit My Bracket", type="primary"):
            try:
                save_picks(name.strip(), st.session_state.picks, method)
                st.session_state.submitted = True
                st.rerun()
            except Exception as e:
                st.error(f"Error saving picks: {e}")


# ===========================================================================
# BRACKET RENDERING
# ===========================================================================

def render_region_tab(region, picks):
    """Render the full bracket for one region as 4 side-by-side columns.

    Columns: Round of 64 | Round of 32 | Sweet 16 | Elite 8
    Games in later rounds are spaced with empty lines to visually align
    them with the two games that feed into them from the left.
    """
    region_games = get_region_games(region)

    r64 = [g for g in region_games if g["round"] == 1]   # 8 games
    r32 = [g for g in region_games if g["round"] == 2]   # 4 games
    s16 = [g for g in region_games if g["round"] == 3]   # 2 games
    e8  = [g for g in region_games if g["round"] == 4]   # 1 game

    col_r64, col_r32, col_s16, col_e8 = st.columns([3, 3, 3, 2])

    with col_r64:
        st.markdown('<div class="round-header">Round of 64</div>', unsafe_allow_html=True)
        for game in r64:
            render_game_picker(game, picks)

    with col_r32:
        st.markdown('<div class="round-header">Round of 32</div>', unsafe_allow_html=True)
        for game in r32:
            st.write("")
            render_game_picker(game, picks)
            st.write("")

    with col_s16:
        st.markdown('<div class="round-header">Sweet 16</div>', unsafe_allow_html=True)
        for game in s16:
            for _ in range(3):
                st.write("")
            render_game_picker(game, picks)
            for _ in range(2):
                st.write("")

    with col_e8:
        st.markdown('<div class="round-header">Elite 8</div>', unsafe_allow_html=True)
        for _ in range(7):
            st.write("")
        for game in e8:
            render_game_picker(game, picks)


def render_final_four_tab(picks):
    """Render the Final Four and Championship picks."""
    st.markdown("### 🏆 Final Four — April 4 · Indianapolis, IN")

    ff_games = [g for g in GAMES if g["round"] == 5]
    col1, spacer, col2 = st.columns([3, 1, 3])
    labels = ["East / South", "West / Midwest"]

    for col, game, label in zip([col1, col2], ff_games, labels):
        with col:
            st.markdown(f"**Semifinal: {label}**")
            render_game_picker(game, picks)

    st.markdown("---")
    st.markdown("#### 🏆 National Championship — April 6")
    champ_games = [g for g in GAMES if g["round"] == 6]
    _, center, _ = st.columns([2, 3, 2])
    with center:
        for game in champ_games:
            render_game_picker(game, picks)


def render_game_picker(game, picks):
    """Render a single game as a selectbox inside a styled bracket slot.

    For Round 1: shows the two seeded teams.
    For later rounds: shows whoever the user picked to win the feeder games.
    If feeder picks haven't been made yet, shows a placeholder.

    Selecting a winner automatically propagates forward — and clearing a pick
    cascades to wipe any downstream picks that depended on it.
    """
    game_id = game["id"]
    team_a, seed_a, team_b, seed_b = resolve_teams(game_id, picks)

    if not team_a or not team_b:
        st.caption("⏳ Pick earlier rounds first")
        return

    label_a = f"({seed_a}) {team_a}" if seed_a else team_a
    label_b = f"({seed_b}) {team_b}" if seed_b else team_b
    # Show the matchup as the placeholder so the user can see who's playing
    # before they make a pick — e.g. "Duke (1) vs Siena (16)"
    matchup_label = f"{team_a} ({seed_a}) vs {team_b} ({seed_b})"
    options = [matchup_label, label_a, label_b]

    current_pick = picks.get(game_id)
    if current_pick == team_a:
        current_idx = 1
    elif current_pick == team_b:
        current_idx = 2
    else:
        current_idx = 0

    # Include fill_version in the key so every auto-fill produces fresh widgets.
    # Fresh keys have no prior Streamlit internal state, so they correctly
    # initialize from index= rather than showing stale cached values.
    fv = st.session_state.get("fill_version", 0)
    chosen_label = st.selectbox(
        label=game_id,
        options=options,
        index=current_idx,
        key=f"pick_{game_id}_v{fv}",
        label_visibility="collapsed",
    )

    if chosen_label == label_a:
        picks[game_id] = team_a
    elif chosen_label == label_b:
        picks[game_id] = team_b
    else:
        picks[game_id] = None
        _clear_downstream(game_id, picks)


def _clear_downstream(game_id, picks):
    """Recursively clear picks for games that depended on this game's winner.

    Example: unpick your East Elite 8 → your Final Four pick also gets cleared.
    """
    game = GAME_BY_ID.get(game_id)
    if not game:
        return
    next_id = game.get("next_game")
    if not next_id:
        return
    picks[next_id] = None
    _clear_downstream(next_id, picks)


# ===========================================================================
# LEADERBOARD
# ===========================================================================

def show_leaderboard():
    """Show the scored leaderboard and completed game results after the deadline."""

    st.markdown("Submissions are closed. Good luck everyone! 🏀")

    # Scoring rules reminder at the top of the leaderboard too
    with st.expander("📋 Scoring rules", expanded=False):
        render_scoring_rules()

    render_bracket_image()

    st.markdown("---")
    st.markdown("### 📊 Standings")

    with st.spinner("Loading scores..."):
        try:
            all_picks = get_all_picks()
        except Exception as e:
            st.error(f"Could not load picks from Google Sheets: {e}")
            return
        try:
            results = get_tournament_results()
        except Exception as e:
            st.warning(f"Could not load ESPN results: {e}")
            results = []

    if not all_picks:
        st.info("No picks submitted yet.")
        return

    ranked = rank_participants(all_picks, results)

    # Build leaderboard as styled HTML table for better visual control.
    # Method icon appears next to the participant's name as a small badge.
    medal_icons = {1: "🥇", 2: "🥈", 3: "🥉"}
    rows_html = ""
    for rank, entry in enumerate(ranked, start=1):
        medal = medal_icons.get(rank, f"#{rank}")
        bg = ""
        if rank == 1:
            bg = "background:rgba(245,197,24,0.12); border-left:4px solid #F5C518;"
        elif rank == 2:
            bg = "background:rgba(168,169,173,0.12); border-left:4px solid #A8A9AD;"
        elif rank == 3:
            bg = "background:rgba(205,127,50,0.12); border-left:4px solid #CD7F32;"
        else:
            bg = "border-left:4px solid #E0D6CC;"

        # Get the method icon; default to custom if not set (old submissions)
        method_key  = entry.get("method", "custom")
        method_icon = METHOD_ICONS.get(method_key, "🎨")
        method_tip  = METHOD_LABELS.get(method_key, "Custom")

        rows_html += f"""
        <tr style="font-size:0.95rem; {bg}">
            <td style="padding:10px 12px; font-weight:700;">{medal}</td>
            <td style="padding:10px 12px; font-weight:600;">
                {entry['name']}
                <span style="font-size:0.75rem; margin-left:4px;"
                      title="{method_tip}">{method_icon}</span>
            </td>
            <td style="padding:10px 12px; font-weight:800; color:#E8651A; font-size:1.1rem;">{entry['score']}</td>
            <td style="padding:10px 12px; color:#555;">{entry['correct']}</td>
            <td style="padding:10px 12px; color:#555;">{entry['base_pts']}</td>
            <td style="padding:10px 12px; color:#555;">{entry['upset_pts']}</td>
            <td style="padding:10px 12px; color:#555;">{entry['margin_pts']}</td>
        </tr>
        """

    st.markdown(f"""
    <table style="width:100%; border-collapse:collapse; background:white;
                  border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <thead>
            <tr style="background:#1B3A6B; color:white; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.5px;">
                <th style="padding:12px;">Rank</th>
                <th style="padding:12px; text-align:left;">Name</th>
                <th style="padding:12px;">Total</th>
                <th style="padding:12px;">Correct</th>
                <th style="padding:12px;">Base</th>
                <th style="padding:12px;">Upset</th>
                <th style="padding:12px;">Margin</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)

    # --- Completed game results ---
    st.markdown("---")
    st.markdown("### 🏀 Completed Games")

    if not results:
        st.info("No completed games yet — check back after March 19.")
        return

    for result in results:
        seed_w = TEAM_SEEDS.get(result["winner"], "?")
        seed_l = TEAM_SEEDS.get(result["loser"], "?")
        upset_tag = ""
        if seed_w > seed_l:
            upset_tag = " 🔥 <em>upset</em>"
        st.markdown(
            f'<div class="game-result">'
            f'<span style="font-weight:700; color:#1B3A6B;">({seed_w}) {result["winner"]}</span>'
            f'<span style="background:#E8651A; color:white; border-radius:4px; padding:2px 8px; font-weight:700;">'
            f'{result["winner_score"]} – {result["loser_score"]}</span>'
            f'<span style="color:#7A6F68;">def. ({seed_l}) {result["loser"]}</span>'
            f'{upset_tag}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__" or True:
    main()
