"""The weekly job that sets every sector's nightly goals.

PLAN-2026-10-02-goals.md, step G7. Runs every Monday morning in GitHub Actions
(`.github/workflows/area-goals.yml`), after Agent3's 6 AM DAILY_LOG refresh and
long before Agent1A's 9:15 PM email:

  1. reads DAILY_LOG, MISSION_ORG, QUESTIONS_CONFIG, AGENT_CONFIG, APP_SETTINGS,
     last week's AREA_WEEKLY_GOALS rows, NIGHTLY_GOAL_OVERRIDES and
     AREA_LINEAGE (a new sector's inherited history — PLAN-2026-10-05 R7);
  2. computes each active sector's goal per nightly metric for the week starting
     this Monday — `app.analytics.area_goals.compute`, the one copy of the rule;
  3. writes that week's rows into AREA_WEEKLY_GOALS (a re-run replaces them, so
     the job is safe to repeat) and rewrites GOALS_CONFIG with the same numbers
     — the tab Agent1A's email, Agent5B's Friday email and the scores already
     read.

No Streamlit: credentials come from `gcp_creds`, exactly as the Tableau runner's
do. **The repository is public**, so nothing this prints names a sector or a
figure — counts only.

    python -m app.ingestion.area_goals_runner [--dry-run] [--week-start YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

import pandas as pd

from app.analytics import area_goals as AG

HISTORY_TAB = "AREA_WEEKLY_GOALS"
OVERRIDES_TAB = "NIGHTLY_GOAL_OVERRIDES"
GOALS_TAB = "GOALS_CONFIG"
HISTORY_FIXED = ["Week_Start", "Area", "Overridden"]

#: The same pattern `queries.get_submitting_areas` uses: tracking rows for
#: leaders are not sectors and file no nightly form.
LEADERSHIP_NAME_RE = re.compile(
    r"^(Mission President|Assistant to President|Zone Leader|"
    r"Sister Training Leader -|District Leader -)", re.IGNORECASE)

_SCOPES = ["https://spreadsheets.google.com/feeds",
           "https://www.googleapis.com/auth/drive"]


def _status(msg: str) -> None:
    print(json.dumps({"type": "status", "msg": msg}), flush=True)


# ── Pure: reading the grids ───────────────────────────────────────────────────

def _records(grid: list) -> list[dict]:
    if not grid:
        return []
    header = [str(h).strip() for h in grid[0]]
    return [dict(zip(header, [str(c).strip() for c in row])) for row in grid[1:]]


def roster(grid: list) -> dict:
    """{area: zone} for every active, non-leadership MISSION_ORG row."""
    out = {}
    for r in _records(grid):
        name = r.get("Area_Name", "")
        if not name or r.get("Active", "").upper() != "TRUE":
            continue
        if LEADERSHIP_NAME_RE.match(name):
            continue
        out[name] = r.get("Zone", "")
    return out


def nightly_keys(grid: list) -> list[str]:
    """Active NIGHTLY NUMBER metrics, in sheet order — Agent1A's own rule
    (a1a_loadCountMetrics), so the email and this job agree on the list."""
    keys = []
    for r in _records(grid):
        if r.get("Active", "").upper() != "TRUE":
            continue
        if r.get("Data_Type", "").upper() != "NUMBER":
            continue
        if r.get("Form_Type", "").upper() not in ("NIGHTLY", ""):
            continue
        if r.get("Metric_Key"):
            keys.append(r["Metric_Key"])
    return keys


def config(grid: list) -> dict:
    out = {}
    for r in _records(grid):
        k = r.get("Key") or r.get("Config_Key") or ""
        if k:
            out[k] = r.get("Value", r.get("Config_Value", ""))
    return out


def configured_goals(cfg: dict) -> dict:
    out = {}
    for k, v in cfg.items():
        if k.startswith("GOAL_") and not k.startswith("GOAL_ANNUAL"):
            try:
                n = float(v)
            except (TypeError, ValueError):
                continue
            if n > 0:
                out[k[5:]] = n
    return out


def stretch(settings_grid: list) -> float:
    """1 + rec_stretch_pct/100 from APP_SETTINGS; 10% when unset, which is what
    `queries.get_rec_stretch_pct` defaults to."""
    for r in _records(settings_grid):
        if r.get("key") == "rec_stretch_pct":
            try:
                return 1 + float(r.get("value", "10")) / 100.0
            except ValueError:
                break
    return 1.10


def _num(v) -> float | None:
    try:
        n = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def history_week(grid: list, week_start: date) -> tuple[dict, dict]:
    """``({area: {key: goal}}, {area: set(overridden keys)})`` for one week."""
    goals, overridden = {}, {}
    want = week_start.isoformat()
    for r in _records(grid):
        if r.get("Week_Start") != want or not r.get("Area"):
            continue
        a = r["Area"]
        goals[a] = {k: n for k, v in r.items()
                    if k not in HISTORY_FIXED and (n := _num(v)) is not None}
        overridden[a] = {k for k in r.get("Overridden", "").split(",") if k}
    return goals, overridden


def overrides(grid: list) -> dict:
    """{area: {key: goal}} — a blank cell is no override."""
    out = {}
    for r in _records(grid):
        a = r.get("Area")
        if not a:
            continue
        vals = {k: int(n) for k, v in r.items()
                if k != "Area" and (n := _num(v)) is not None}
        if vals:
            out[a] = vals
    return out


def lineage(grid: list) -> dict:
    """``{new_area: [(old_area, transfer_date), ...]}`` from AREA_LINEAGE.

    The date is the transfer the new area began on: a predecessor's nights
    BEFORE it are the new area's inherited history (PLAN-2026-10-05 D3). A row
    without a readable date is skipped rather than guessed at.
    """
    out: dict = {}
    for r in _records(grid):
        new = r.get("New_Area", "")
        try:
            cutoff = date.fromisoformat(r.get("Transfer_Date", "")[:10])
        except ValueError:
            continue
        for old in (p.strip() for p in r.get("Old_Areas", "").split(";")):
            if new and old and old != new:
                out.setdefault(new, []).append((old, cutoff))
    return out


def daily_frame(grid: list) -> pd.DataFrame:
    recs = _records(grid)
    return pd.DataFrame(recs) if recs else pd.DataFrame()


# ── Pure: building the grids ──────────────────────────────────────────────────

def history_rows(week_start: date, goals: dict, keys: list) -> list[list]:
    rows = []
    for area in sorted(goals):
        g = goals[area]
        led = sorted(k for k in keys if k in g and g[k].source == AG.LEADERSHIP)
        rows.append([week_start.isoformat(), area, ",".join(led)]
                    + [("" if g.get(k) is None or g[k].goal is None else g[k].goal)
                       for k in keys])
    return rows


def merged_history(grid: list, week_start: date, new_rows: list, keys: list) -> list[list]:
    """The whole AREA_WEEKLY_GOALS tab with this week's rows replaced.

    Older weeks are carried across under the new header, column by column, so a
    metric added to the form later gets a blank for the weeks before it existed
    rather than shifting every other column.
    """
    header = HISTORY_FIXED + list(keys)
    keep = [r for r in _records(grid) if r.get("Week_Start")
            and r.get("Week_Start") != week_start.isoformat()]
    body = [[r.get(h, "") for h in header] for r in keep]
    body.sort(key=lambda r: (r[0], r[1]))
    return [header] + body + new_rows


def goals_config_grid(goals: dict, keys: list) -> list[list]:
    """GOALS_CONFIG as the agents read it: Area + one column per metric."""
    body = [[area] + [("" if goals[area].get(k) is None or goals[area][k].goal is None
                       else goals[area][k].goal) for k in keys]
            for area in sorted(goals)]
    return [["Area"] + list(keys)] + body


def summary(goals: dict) -> dict:
    """Counts by source — the only thing the job prints."""
    out: dict = {}
    for per_key in goals.values():
        for g in per_key.values():
            out[g.source] = out.get(g.source, 0) + 1
    return out


# ── Sheets ────────────────────────────────────────────────────────────────────

def _open_sheet():
    import gspread
    from google.oauth2.service_account import Credentials

    from app.integrations.gcp_creds import get_service_account_dict
    creds = Credentials.from_service_account_info(get_service_account_dict(),
                                                  scopes=_SCOPES)
    client = gspread.authorize(creds)
    return client.open(os.environ.get("COMPASS_SHEET_NAME", "COMPASS_CCSM"))


def _grid(sh, tab: str) -> list:
    import gspread
    try:
        return sh.worksheet(tab).get_all_values()
    except gspread.exceptions.WorksheetNotFound:
        return []


def _overwrite(sh, tab: str, rows: list) -> None:
    """Write ``rows`` from A1 and clear anything below/right of them."""
    import gspread
    n_cols = max(len(r) for r in rows)
    try:
        ws = sh.worksheet(tab)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=max(len(rows) + 50, 100),
                              cols=max(n_cols, 10))
    if ws.row_count < len(rows) or ws.col_count < n_cols:
        ws.resize(rows=max(ws.row_count, len(rows) + 50),
                  cols=max(ws.col_count, n_cols))
    padded = [list(r) + [""] * (n_cols - len(r)) for r in rows]
    ws.update(values=padded, range_name="A1", value_input_option="RAW")
    # Clear what an older, longer or wider version left behind.
    if ws.row_count > len(rows):
        ws.batch_clear([f"A{len(rows) + 1}:ZZ{ws.row_count}"])
    from app.db.tabular_io import col_letter
    if ws.col_count > n_cols:
        ws.batch_clear([f"{col_letter(n_cols + 1)}1:ZZ{len(rows)}"])


def _this_monday(tz_name: str) -> date:
    try:
        import zoneinfo
        today = datetime.now(zoneinfo.ZoneInfo(tz_name)).date()
    except Exception:
        today = date.today()
    return AG.week_monday(today)


def main() -> None:
    ap = argparse.ArgumentParser(description="Set every sector's nightly goals for the week.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute and print counts; write nothing.")
    ap.add_argument("--week-start", help="The Monday to compute for (default: this week's).")
    args = ap.parse_args()

    _status("Reading the sheet")
    sh = _open_sheet()
    cfg = config(_grid(sh, "AGENT_CONFIG"))
    week_start = (date.fromisoformat(args.week_start) if args.week_start
                  else _this_monday(cfg.get("MISSION_TIMEZONE") or "America/Santiago"))
    if week_start.weekday() != 0:
        print(f"ERROR: {week_start} is not a Monday", file=sys.stderr)
        sys.exit(2)

    areas = roster(_grid(sh, "MISSION_ORG"))
    keys = nightly_keys(_grid(sh, "QUESTIONS_CONFIG"))
    daily = daily_frame(_grid(sh, "DAILY_LOG"))
    history = _grid(sh, HISTORY_TAB)
    prev, prev_over = history_week(history, week_start - timedelta(days=7))
    standing = overrides(_grid(sh, OVERRIDES_TAB))
    if not areas or not keys:
        print("ERROR: no active sectors or no nightly metrics found", file=sys.stderr)
        sys.exit(1)

    goals = AG.compute(daily, areas, keys, week_start=week_start,
                       stretch=stretch(_grid(sh, "APP_SETTINGS")),
                       previous=prev, previous_overridden=prev_over,
                       overrides=standing, configured=configured_goals(cfg),
                       lineage=lineage(_grid(sh, "AREA_LINEAGE")))
    counts = summary(goals)
    _status(f"Week {week_start}: {len(goals)} sectors x {len(keys)} metrics; "
            + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if args.dry_run:
        _status("Dry run - nothing written")
        return

    _status("Writing AREA_WEEKLY_GOALS")
    _overwrite(sh, HISTORY_TAB,
               merged_history(history, week_start,
                              history_rows(week_start, goals, keys), keys))
    _status("Writing GOALS_CONFIG")
    _overwrite(sh, GOALS_TAB, goals_config_grid(goals, keys))
    _status(f"Done: goals set for {len(goals)} sectors, week of {week_start}")


if __name__ == "__main__":
    main()
