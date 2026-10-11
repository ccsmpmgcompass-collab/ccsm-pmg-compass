"""Build the weekly KI ranking PDFs by hand: the mission document and one per zone.

The documents themselves live in dashboard/app/reports/ki_ranking.py, which the
Monday job (app.ingestion.ki_pdf_runner, PLAN-2026-10-10-ki-autosend.md) uses
to attach them to the weekly letter. This is for a rebuild on demand.

    cd tools
    ../dashboard/venv/Scripts/python.exe build_ki_ranking.py --out-dir ../Indicadores_2026-10-04
        [--cached] [--week-end 2026-10-04] [--cutoff "2026-10-05 21:30"]

The first run fetches the live sheet into tools/dump.json; --cached reuses it.
--week-end is the Sunday ending the latest week (default: the last Sunday).
--cutoff leaves out forms stamped after that mission-time moment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(os.path.dirname(HERE), "dashboard")
sys.path.insert(0, DASH)
sys.stdout.reconfigure(encoding="utf-8")

from app.reports import ki_ranking as KR  # noqa: E402

TABS = ["WEEKLY_KI", "MISSION_ORG", "WEEKLY_FORM_RAW", "QUESTIONS_CONFIG"]


def fetch():
    import tomllib
    import gspread
    from google.oauth2.service_account import Credentials
    s = tomllib.load(open(os.path.join(DASH, ".streamlit", "secrets.toml"), "rb"))
    cd = dict(s["gcp_service_account"])
    cd["private_key"] = cd["private_key"].replace("\\n", "\n")
    gc = gspread.authorize(Credentials.from_service_account_info(cd, scopes=[
        "https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))
    sh = gc.open(s["COMPASS_SHEET_NAME"])
    out = {t: sh.worksheet(t).get_all_values() for t in TABS}
    out["_fetched"] = datetime.now().isoformat(timespec="minutes")
    json.dump(out, open(os.path.join(HERE, "dump.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cached", action="store_true")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--week-end", default=None, help="Sunday ending the latest week (YYYY-MM-DD)")
    ap.add_argument("--cutoff", default=None, help="leave out forms after this (YYYY-MM-DD HH:MM)")
    a = ap.parse_args()
    raw = (json.load(open(os.path.join(HERE, "dump.json"), encoding="utf-8"))
           if a.cached else fetch())
    if a.week_end:
        w2 = date.fromisoformat(a.week_end)
    else:
        today = date.today()
        w2 = today - timedelta(days=today.weekday() + 1)   # the last Sunday before today
    cutoff = datetime.fromisoformat(a.cutoff) if a.cutoff else None
    stamp = a.cutoff or raw["_fetched"].replace("T", " ")

    if "WEEKLY_KI" in raw:
        n_live, diff, extra = KR.check_against_weekly_ki(raw, KR.ki_from_raw(raw))
        print(f"check: {n_live} WEEKLY_KI rows, {len(diff)} differ from the rebuild: {diff}")
        print(f"       not yet in WEEKLY_KI: {len(extra)} rows")

    os.makedirs(a.out_dir, exist_ok=True)
    for d in KR.build_documents(raw, w2, cutoff, stamp):
        path = os.path.join(a.out_dir, d["file_name"])
        with open(path, "wb") as f:
            f.write(d["pdf"])
        print(f"PDF: {path}  pages: {d['pages']}")
    print("forms read at", stamp)


if __name__ == "__main__":
    main()
