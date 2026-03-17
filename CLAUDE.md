# NCAA Bracket Pool — Project Orientation

## What This Is
A free web app for a small friend group (~20 people) to submit bracket picks,
track live results, and see a scored leaderboard. Built as a father-son learning
project. Code should be heavily commented for explainability.

## Stack
| Layer | Tool | Why |
|---|---|---|
| Web app | Streamlit (Python) | Pure Python, easy to explain, fast to build |
| Database | Google Sheets (via gspread) | No setup friction, data visible/editable |
| Live scores | ESPN unofficial API | Free, returns scores + margins |
| Hosting | Streamlit Community Cloud | Free, deploys from GitHub |

## Key Dates
- **Bracket finalized:** March 16, 2026
- **Submission deadline:** March 19, 2026 at 11:00 AM CT / noon ET (first Round of 64 tip-off)
- **First Four:** March 17–18, 2026
- **Round of 64:** March 19–20, 2026
- **Championship:** April 6, 2026

## Scoring Rules
- **10 pts** for every correct winner in any round
- **+4 pts** upset bonus: correct pick where winner seed > loser seed
- **+half the margin** bonus: if final score is 80–70, winner earns +5 bonus pts
  (margin bonus only applies to completed games with final scores)

## App Behavior
- **Before deadline:** Show bracket pick submission form + countdown timer
- **After deadline:** Lock submissions; show leaderboard + bracket results only
- Deadline is controlled by `SUBMISSION_DEADLINE` in `config.py`

## File Structure
```
basketball bracket/
├── CLAUDE.md               ← this file
├── 2026_bracket.pdf        ← source bracket image
├── app.py                  ← Streamlit entry point; routing between modes
├── bracket_data.py         ← static bracket: all 68 teams, seeds, regions, game tree
├── espn_api.py             ← fetches live/final scores from ESPN unofficial API
├── scoring.py              ← calculates scores for each participant
├── sheets.py               ← reads/writes picks to Google Sheets via gspread
├── config.py               ← constants: deadline, scoring weights, sheet name
├── requirements.txt        ← pip dependencies
├── .streamlit/
│   └── secrets.toml        ← Google service account credentials (local, gitignored)
└── .gitignore
```

See `bracket_data.py` for the full team/seed/game structure (source of truth).

## Bracket Structure (68 teams, 4 regions)
**First Four (March 17–18):**
Participants do NOT pick First Four games separately. Instead, the combined slot
name appears as a single selectable team in the Round of 64 bracket. If a user
picks "TEX/NCST" and that slot's winner advances, the pick is scored normally.
- West 11 slot: "TEX/NCST" (Texas vs NC State)
- Midwest 11 slot: "M-OH/SMU" (Miami OH vs SMU)
- Midwest 16 slot: "UMBC/HOW" (UMBC vs Howard)
- South 16 slot: "PVAM/LEH" (Prairie View vs Lehigh)

**East:** Duke(1), Siena(16), Ohio St.(8), TCU(9), St. John's(5), N. Iowa(12),
Kansas(4), Cal Baptist(13), Louisville(6), South Florida(11), Michigan St.(3),
N. Dakota St.(14), UCLA(7), UCF(10), UConn(2), Furman(15)

**South:** Florida(1), PVAM/LEH(16), Clemson(8), Iowa(9), Vanderbilt(5),
McNeese(12), Nebraska(4), Troy(13), N. Carolina(6), VCU(11), Illinois(3),
Penn(14), Saint Mary's(7), Texas A&M(10), Houston(2), Idaho(15)

**West:** Arizona(1), LIU(16), Villanova(8), Utah St.(9), Wisconsin(5),
High Point(12), Arkansas(4), Hawaii(13), BYU(6), TEX/NCST(11), Gonzaga(3),
Kennesaw St.(14), Miami(7), Missouri(10), Purdue(2), Queens(15)

**Midwest:** Michigan(1), UMBC/HOW(16), Georgia(8), Saint Louis(9),
Texas Tech(5), Akron(12), Alabama(4), Hofstra(13), Tennessee(6), M-OH/SMU(11),
Virginia(3), Wright St.(14), Kentucky(7), Santa Clara(10), Iowa St.(2),
Tennessee St.(15)

## ESPN API
Base URL: `http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard`
- Returns live + final scores for all games
- Use team name matching to map ESPN results → bracket slots
- Cache responses (60-second TTL) to avoid hammering the API
- See `espn_api.py` for implementation

## Google Sheets Schema
Two tabs in one Google Sheet:
1. **picks** — columns: `timestamp, name, [63 game pick columns]`
2. **results** — managed automatically from ESPN API cache (optional manual override)

Credentials stored in `.streamlit/secrets.toml` (never committed to git).

## Setup References
- Google service account setup: see README or ask Claude
- Streamlit Community Cloud deploy: connect GitHub repo at share.streamlit.io
- gspread auth docs: gspread.readthedocs.io
