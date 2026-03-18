# sheets.py
# ---------------------------------------------------------------------------
# Handles all reading and writing to Google Sheets via the gspread library.
#
# Google Sheets acts as our database — it's free, visible/editable by admins,
# and requires no server setup. The "picks" tab stores one row per submission.
#
# Authentication uses a Google service account whose credentials are stored
# in .streamlit/secrets.toml (local) or Streamlit Cloud's Secrets UI (prod).
# That file is gitignored and claudeignored — credentials never touch code.
# ---------------------------------------------------------------------------

import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
from datetime import datetime, timezone

from config import SHEET_NAME, PICKS_TAB

# The scopes tell Google which APIs we need access to.
# "spreadsheets" = read/write sheets. "drive" = needed to open sheets by name.
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Column order for picks in the sheet: g1 through g63
# We sort numerically (g2 before g10) so the sheet columns are in bracket order.
GAME_COLUMNS = [f"g{i}" for i in range(1, 64)]


def get_client():
    """Create and return an authenticated gspread client.

    Reads credentials from st.secrets["gcp_service_account"], which comes from
    .streamlit/secrets.toml locally or Streamlit Cloud's Secrets UI in production.
    Returns a gspread client object that can open spreadsheets.
    """
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def get_worksheet(tab_name):
    """Open the Google Sheet and return the specified worksheet (tab).

    Args:
        tab_name: the tab name inside the sheet (e.g., "picks")
    Returns a gspread Worksheet object.
    """
    client = get_client()
    sheet = client.open(SHEET_NAME)
    return sheet.worksheet(tab_name)


def _ensure_headers(worksheet):
    """Ensure row 1 of the picks sheet contains the correct full header row.

    Format: timestamp | name | g1 | g2 | ... | g63 | method  (65 columns)

    Overwrites row 1 whenever it doesn't match exactly — handles empty sheets,
    partial headers from failed prior runs, and missing columns from migration.
    Data rows (row 2+) are never touched.
    """
    headers = ["timestamp", "name"] + GAME_COLUMNS + ["method"]
    existing = worksheet.get_all_values()
    if not existing or existing[0] != headers:
        # Write the full header row to A1, overwriting whatever is there.
        # values= takes a list of rows; we pass one row.
        worksheet.update(values=[headers], range_name="A1")


def save_picks(name, picks_dict, method="custom"):
    """Save a participant's bracket picks as a new row in the picks sheet.

    Always appends a new row — the most recent submission per name counts.
    This lets people update their picks before the deadline without losing history.

    Args:
        name:       participant's name (string)
        picks_dict: dict of {game_id: picked_team_name} — all 63 games
        method:     how the bracket was filled ("custom", "seed", "mascot", "random")
    """
    ws = get_worksheet(PICKS_TAB)
    _ensure_headers(ws)

    # Build the row in the correct column order, with method appended at the end
    timestamp = datetime.now(timezone.utc).isoformat()
    row = [timestamp, name]
    for game_id in GAME_COLUMNS:
        row.append(picks_dict.get(game_id, ""))  # blank if not picked (shouldn't happen)
    row.append(method)

    ws.append_row(row, value_input_option="RAW")


def get_all_picks():
    """Read all submissions from the picks sheet and return one entry per person.

    If someone submitted multiple times (they updated their picks before the
    deadline), we keep only their most recent submission based on timestamp.

    Returns a list of dicts:
        name      — participant name
        timestamp — ISO timestamp of their submission
        picks     — dict of {game_id: picked_team_name}
    """
    ws = get_worksheet(PICKS_TAB)
    rows = ws.get_all_records()  # returns list of dicts keyed by header row

    if not rows:
        return []

    # Group by name, keeping the latest submission for each person.
    # We track latest by comparing timestamp strings — ISO format sorts correctly.
    latest_by_name = {}
    for row in rows:
        name = row.get("name", "").strip()
        if not name:
            continue
        ts = row.get("timestamp", "")
        existing = latest_by_name.get(name)
        if not existing or ts > existing["timestamp"]:
            latest_by_name[name] = {"timestamp": ts, "row": row}

    # Convert to the format the rest of the app expects
    result = []
    for name, entry in latest_by_name.items():
        row = entry["row"]
        picks = {game_id: row.get(game_id, "") for game_id in GAME_COLUMNS}
        # Remove empty picks (defensive — shouldn't happen after a valid submission)
        picks = {k: v for k, v in picks.items() if v}
        result.append({
            "name":      name,
            "timestamp": entry["timestamp"],
            "picks":     picks,
            # Default to "custom" for old submissions that predate this column
            "method":    entry["row"].get("method", "custom") or "custom",
        })

    return result


def check_already_submitted(name):
    """Check whether a given name has already submitted a bracket.

    Used to show a warning on the submission form if the name matches
    an existing entry. Case-insensitive comparison.

    Returns True if a submission exists for this name, False otherwise.
    """
    ws = get_worksheet(PICKS_TAB)
    rows = ws.get_all_records()
    submitted_names = {r.get("name", "").strip().lower() for r in rows}
    return name.strip().lower() in submitted_names
