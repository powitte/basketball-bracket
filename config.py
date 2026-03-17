# config.py
# ---------------------------------------------------------------------------
# Central configuration file for the 2026 NCAA Bracket Pool app.
# All constants live here so you only have to change something in one place.
# Import this file wherever you need these values:
#   from config import SUBMISSION_DEADLINE, POINTS_PER_WIN, ...
# ---------------------------------------------------------------------------

import pytz
from datetime import datetime

# ---------------------------------------------------------------------------
# TIMEZONE SETUP
# ---------------------------------------------------------------------------
# pytz gives us named time zones so we don't have to do manual offset math.
# "America/Chicago" covers both CST (UTC-6) and CDT (UTC-5) automatically.
CT = pytz.timezone("America/Chicago")

# ---------------------------------------------------------------------------
# SUBMISSION DEADLINE
# ---------------------------------------------------------------------------
# Tip-off for the first Round of 64 game is noon ET on March 19, 2026.
# That's 11:00 AM Central Time. We lock the submission form at this moment.
# datetime() creates a "naive" datetime (no timezone info). CT.localize()
# attaches the Central timezone so comparisons work correctly worldwide.
SUBMISSION_DEADLINE = CT.localize(datetime(2026, 3, 19, 11, 0, 0))

# ---------------------------------------------------------------------------
# SCORING CONSTANTS
# ---------------------------------------------------------------------------
# Every correct pick earns a flat 10 points, regardless of round.
POINTS_PER_WIN = 10

# If you correctly pick an upset (the higher seed — weaker team — beats the
# lower seed — stronger team), you earn an extra 4 points.
# Example: a 12-seed beating a 5-seed earns UPSET_BONUS_PTS.
UPSET_BONUS_PTS = 4

# Margin bonus: earn half the final score margin as bonus points.
# Example: winner 80, loser 70 → margin 10 → bonus = 10 // 2 = 5 pts.
# We use integer division (//) so scores stay whole numbers.
MARGIN_BONUS_DIVISOR = 2

# ---------------------------------------------------------------------------
# GOOGLE SHEETS SETTINGS
# ---------------------------------------------------------------------------
# The exact name of the Google Sheet (not the tab — the whole document).
# This must match the sheet name exactly, including capitalization.
SHEET_NAME = "2026_Bracket_Pool_Sheets"

# The tab inside the sheet where bracket picks are stored.
PICKS_TAB = "picks"

# ---------------------------------------------------------------------------
# ESPN API SETTINGS
# ---------------------------------------------------------------------------
# ESPN's unofficial (undocumented) scoreboard endpoint.
# "Unofficial" means ESPN hasn't formally published it, but it's publicly
# accessible and widely used. It may change without notice.
ESPN_API_URL = (
    "http://site.api.espn.com/apis/site/v2/sports/basketball/"
    "mens-college-basketball/scoreboard"
)

# How long (in seconds) to keep ESPN data cached before fetching fresh data.
# 3600 seconds = 1 hour. Games don't finish faster than that, so there's no
# value in checking more often. The app only fetches between 10 AM and 11 PM CT
# (see espn_api.py), so we won't ping ESPN during overnight hours at all.
# This keeps our request volume low and the app responsive.
ESPN_CACHE_TTL = 3600  # seconds (1 hour) — plenty fresh for a casual pool
