"""Dump the COMPASS_CCSM tabs the coaching chain reads, as raw cell grids.

Feeds tools/email_preview/render.js, which runs the REAL Agent1A -> 1B -> 1C
code offline and writes the exact HTML those agents would email.

Raw grids, not DataFrames: a1a_getSheetData() returns
sheet.getDataRange().getValues() — a list of rows including the header — and
the agents index it positionally. Reshaping it here would change what the code
under test sees.

⚠️ The output holds missionary names and email addresses. It is written to
tools/email_preview/.data/ which is gitignored. Never commit it.

Usage (from dashboard/, so the venv and st.secrets resolve):
    venv/Scripts/python.exe ../tools/email_preview/dump_tabs.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / ".data"

# Every tab the chain touches. DAILY_LOG/NIGHTLY_FORM_RAW/QUESTIONS_CONFIG/
# GOALS_CONFIG/MISSION_ORG/FEEDBACK_HISTORY/WEEKLY_KI come from
# a1a_getSheetData; the rest are read by CCSM_Helpers (getConfig,
# getMessageBank) on the way through.
TABS = [
    "MISSION_ORG",
    "DAILY_LOG",
    "NIGHTLY_FORM_RAW",
    "QUESTIONS_CONFIG",
    "GOALS_CONFIG",
    "FEEDBACK_HISTORY",
    "WEEKLY_KI",
    "MESSAGE_BANK",
    "AGENT_CONFIG",
    "WEEKLY_BREAKDOWNS",
    "SCORES",
    "LIVE_SNAPSHOT",
]


def main() -> int:
    sys.path.insert(0, str(HERE.parent.parent / "dashboard"))
    from app.db.sheets_client import _get_spreadsheet

    ss = _get_spreadsheet()
    have = {w.title: w for w in ss.worksheets()}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grids = {}
    for tab in TABS:
        ws = have.get(tab)
        if ws is None:
            print(f"  {tab:22} MISSING — skipped")
            grids[tab] = []
            continue
        rows = ws.get_all_values()
        grids[tab] = rows
        cols = len(rows[0]) if rows else 0
        print(f"  {tab:22} {len(rows):>6} rows x {cols:>3} cols")

    out = OUT_DIR / "tabs.json"
    out.write_text(json.dumps(grids), encoding="utf-8")
    print(f"\nwrote {out}  ({out.stat().st_size / 1e6:.2f} MB)")
    # ASCII only: the Windows console runs cp1252, where a warning emoji or an
    # em dash raises UnicodeEncodeError and buries the successful dump above it.
    print("WARNING: contains real names and emails - gitignored, do not commit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
