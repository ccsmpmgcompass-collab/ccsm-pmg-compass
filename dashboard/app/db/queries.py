"""
queries.py
────────────────────────────────────────────────────────────
All data query functions for COMPASS_CCSM Google Sheets tabs.
No Supabase. No external APIs. Read from Google Sheets only.

Tab schemas
───────────
DASHBOARD_SUMMARY:
    record_type | metric_key | metric_name | zone | area | district
    | val_7d | val_14d | val_28d | val_transfer | goal_weekly
    | date | all_count | most_count | some_count
    | submitted_count | total_areas | meta_key | meta_value

WEEKLY_KI:
    week_end_date | area | zone | district | [metric_key per nightly metric]

DAILY_LOG:
    Date | Area | Zone | District | [metric_key per nightly metric]

LIVE_SNAPSHOT:
    Area | Zone | District | Last_Updated | [metric_key_7d/14d/28d/transfer]

MISSION_ORG:
    Area_ID | Area_Name | Zone | District | Language_Type
    | Companion1_Name | Companion1_Email | Companion2_Name | Companion2_Email
    | Is_DL | Is_ZL | Is_STL | Is_AP | Is_MP | Active

GOALS_CONFIG:
    Area | [metric_key per nightly metric]  (weekly goal per area per metric)

NOTES:
    note_id | created_at | created_by | content | tags
    | zone | district | area | follow_up_date | visible_to | resolved | updated_at
"""

import uuid
import hashlib
import math
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from app.db.sheets_client import (
    read_tab, read_values, append_row, update_row, delete_row, overwrite_tab,
)


# ── Numeric coercion helper ────────────────────────────────────────────────────

def _num(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Coerce listed columns to numeric, filling blanks with 0."""
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# AGENT_CONFIG
# ══════════════════════════════════════════════════════════════════════════════

def get_agent_config() -> dict:
    """Read AGENT_CONFIG tab as {Config_Key: Value} dict. Cached 5 min."""
    df = read_tab("AGENT_CONFIG")
    if df.empty:
        return {}
    key_col = next((c for c in df.columns if c.strip().lower() in ("config_key", "key")), None)
    val_col = next((c for c in df.columns if c.strip().lower() in ("value", "config_value")), None)
    if not key_col or not val_col:
        return {}
    return dict(zip(df[key_col].astype(str).str.strip(), df[val_col].astype(str).str.strip()))


def get_config_value(key: str, default: str = "") -> str:
    """Convenience: get one AGENT_CONFIG value by key."""
    return get_agent_config().get(key, default)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD_SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def get_meta() -> dict:
    """Return META key-value pairs as a plain dict."""
    df = read_tab("DASHBOARD_SUMMARY", header_marker="record_type")
    if df.empty or "record_type" not in df.columns:
        return {}
    meta = df[df["record_type"] == "META"][["meta_key", "meta_value"]]
    return dict(zip(meta["meta_key"], meta["meta_value"]))


def get_mission_totals() -> pd.DataFrame:
    """MISSION rows: one row per metric with val_7d/14d/28d/transfer + goal_weekly."""
    df = read_tab("DASHBOARD_SUMMARY", header_marker="record_type")
    if df.empty or "record_type" not in df.columns:
        return pd.DataFrame()
    rows = df[df["record_type"] == "MISSION"].copy()
    return _num(rows, ["val_7d", "val_14d", "val_28d", "val_transfer", "goal_weekly"])


def get_zone_totals() -> pd.DataFrame:
    """ZONE rows: one row per zone per metric."""
    df = read_tab("DASHBOARD_SUMMARY", header_marker="record_type")
    if df.empty or "record_type" not in df.columns:
        return pd.DataFrame()
    rows = df[df["record_type"] == "ZONE"].copy()
    return _num(rows, ["val_7d", "val_14d", "val_28d", "val_transfer"])


def get_compliance() -> pd.DataFrame:
    """COMPLIANCE rows: one row per area with submitted_count and last date."""
    df = read_tab("DASHBOARD_SUMMARY", header_marker="record_type")
    if df.empty or "record_type" not in df.columns:
        return pd.DataFrame()
    rows = df[df["record_type"] == "COMPLIANCE"].copy()
    return _num(rows, ["submitted_count", "total_areas"])


def get_alltime_compliance(start_date: str = None) -> pd.DataFrame:
    """
    Per-area submission compliance from SYSTEM_START_DATE (AGENT_CONFIG, fallback
    2026-06-08) through the most recent completed nightly cutoff (9:30 PM MT).
    Computed live from DAILY_LOG, so partial weeks always count.

    A blank Area_ID in MISSION_ORG marks an area created or renamed at the most
    recent transfer (mission_org_merge_preview.py's convention — new/merged
    areas are appended with no ID). Such areas didn't exist under their current
    name before TRANSFER_START_DATE, so their window floors there instead of
    SYSTEM_START_DATE — mirrors AgentTransfer.gs/Agent3.gs's existing
    max(SYSTEM_START_DATE, TRANSFER_START_DATE) floor, applied per-area since
    this metric (unlike Agent3's short lookback) spans the whole mission history.

    The blank-Area_ID flag is only a hint, not ground truth: live data (2026-07-28)
    showed 8 of 12 blank-Area_ID areas already had DAILY_LOG rows under their exact
    current name well before TRANSFER_START_DATE (never got an ID backfilled, but
    were not actually new) — flooring days_possible at TRANSFER_START_DATE while
    days_submitted still counted those earlier days pushed pct as high as 179%.
    DAILY_LOG is the source of truth here: an area only gets the later floor if it
    truly has no submissions before it.
    Returns: area, zone, district, days_submitted, days_possible, pct, last_date.
    """
    from app.utils.area_helpers import compliance_anchor_date

    if not start_date:
        start_date = get_config_value("SYSTEM_START_DATE", "2026-06-08")[:10]
    transfer_start = get_config_value("TRANSFER_START_DATE", start_date)[:10]
    new_area_start = max(start_date, transfer_start)

    anchor = compliance_anchor_date()
    anchor_str = anchor.strftime("%Y-%m-%d")

    def _days_possible(floor_date: str) -> int:
        return max(0, (anchor - datetime.strptime(floor_date, "%Y-%m-%d").date()).days + 1)

    days_possible_existing = _days_possible(start_date)
    days_possible_new = _days_possible(new_area_start)

    areas = get_submitting_areas()
    if areas.empty:
        return pd.DataFrame()

    log = get_daily_log(400)
    if not log.empty:
        log = log[(log["Date"] >= start_date) & (log["Date"] <= anchor_str)]

    rows = []
    for _, a in areas.iterrows():
        name = str(a.get("Area_Name", a.get("Area", ""))).strip()
        is_new_area = str(a.get("Area_ID", "")).strip() == ""
        sub = log[log["Area"] == name] if not log.empty else pd.DataFrame()
        if is_new_area and not sub.empty and sub["Date"].min() < new_area_start:
            # Log has rows before the floor we'd otherwise use — this area was
            # actually submitting under this name pre-transfer, so the blank
            # Area_ID doesn't mean "new." Use the normal SYSTEM_START_DATE floor
            # so days_possible isn't smaller than the window days_submitted counts.
            is_new_area = False
        days_possible = days_possible_new if is_new_area else days_possible_existing
        n = sub["Date"].nunique() if not sub.empty else 0
        rows.append({
            "area":           name,
            "zone":           a.get("Zone", ""),
            "district":       a.get("District", ""),
            "days_submitted": n,
            "days_possible":  days_possible,
            "pct":            round(n / days_possible * 100) if days_possible else 0,
            "last_date":      sub["Date"].max() if not sub.empty else "",
        })
    return pd.DataFrame(rows)


def get_weekly_compliance_trend() -> pd.DataFrame:
    """
    Mission-wide weekly reporting compliance since SYSTEM_START_DATE: for
    each Mon-Sun week, % of currently active submitting areas that logged
    at least one DAILY_LOG entry that week. Returns one row per week_start
    (the Monday), columns week_start, pct. Empty if there are no active
    submitting areas or no log rows since launch.
    """
    start_date = get_config_value("SYSTEM_START_DATE", "2026-06-08")[:10]
    log = get_daily_log(400)
    areas = get_submitting_areas()
    n_areas = len(areas)
    if log.empty or "Date" not in log.columns or n_areas == 0:
        return pd.DataFrame(columns=["week_start", "pct"])

    log = log[log["Date"] >= start_date].copy()
    if log.empty:
        return pd.DataFrame(columns=["week_start", "pct"])

    log["_dt"] = pd.to_datetime(log["Date"], errors="coerce")
    log = log.dropna(subset=["_dt"])
    log["week_start"] = (
        log["_dt"] - pd.to_timedelta(log["_dt"].dt.weekday, unit="D")
    ).dt.strftime("%Y-%m-%d")

    rows = []
    for week_start, g in log.groupby("week_start"):
        reporting_areas = g["Area"].astype(str).str.strip().nunique()
        rows.append({"week_start": week_start, "pct": round(reporting_areas / n_areas * 100)})
    return pd.DataFrame(rows).sort_values("week_start").reset_index(drop=True)


def get_coaching_reach_since_launch() -> dict:
    """
    Estimated volume of personalized coaching emails sent since launch.
    PMG Compass has no per-send log (FEEDBACK_HISTORY only tracks each
    area's MOST RECENT send, not a history), so this estimates reach as
    (number of Monday coaching cycles since SYSTEM_START_DATE) x (number of
    currently active submitting areas) — SCORES' distinct Week_Ending_Date
    values proxy "a coaching cycle happened" (AgentScores runs Sunday
    night, feeding Monday's Agent1C send).
    Returns {"weeks": int, "areas": int, "estimated_emails": int}.
    """
    start_date = get_config_value("SYSTEM_START_DATE", "2026-06-08")[:10]
    scores = read_tab("SCORES")
    weeks = 0
    if not scores.empty and "Week_Ending_Date" in scores.columns:
        wk = scores["Week_Ending_Date"].astype(str).str.strip().str[:10]
        weeks = int(wk[wk >= start_date].nunique())
    areas = len(get_submitting_areas())
    return {"weeks": weeks, "areas": areas, "estimated_emails": weeks * areas}


def get_effort_data() -> pd.DataFrame:
    """EFFORT rows: daily effort counts (all/most/some) for last 7 days."""
    df = read_tab("DASHBOARD_SUMMARY", header_marker="record_type")
    if df.empty or "record_type" not in df.columns:
        return pd.DataFrame()
    rows = df[df["record_type"] == "EFFORT"].copy()
    return _num(rows, ["all_count", "most_count", "some_count", "total_areas"])


# ══════════════════════════════════════════════════════════════════════════════
# WEEKLY_KI
# ══════════════════════════════════════════════════════════════════════════════

_WKI_BASE_COLS = ["week_end_date", "area", "zone", "district"]

@st.cache_data(ttl=300)
def get_weekly_ki() -> pd.DataFrame:
    """All WEEKLY_KI rows. week_end_date column normalised to string YYYY-MM-DD."""
    df = read_tab("WEEKLY_KI", header_marker="week_end_date")
    if df.empty or "week_end_date" not in df.columns:
        return pd.DataFrame(columns=_WKI_BASE_COLS)
    df["week_end_date"] = df["week_end_date"].astype(str).str.strip().str[:10]
    metric_cols = [c for c in df.columns if c not in _WKI_BASE_COLS]
    return _num(df, metric_cols)


def get_weekly_ki_trends(n_weeks: int = 52) -> pd.DataFrame:
    """
    Mission-wide weekly totals for the last n_weeks weeks.
    Returns one row per week_end_date with summed metric columns.
    Sorted oldest to newest.
    """
    df = get_weekly_ki()
    if df.empty or "week_end_date" not in df.columns:
        return pd.DataFrame()
    metric_cols = [c for c in df.columns if c not in ("week_end_date", "area", "zone", "district")]
    if not metric_cols:
        return pd.DataFrame()
    grouped = df.groupby("week_end_date")[metric_cols].sum().reset_index()
    grouped = grouped.sort_values("week_end_date").tail(n_weeks)
    return grouped


def exclude_current_week(df: pd.DataFrame, date_col: str = "week_end_date") -> pd.DataFrame:
    """
    Drop rows whose week falls in the current, still-in-progress Mon–Sun
    reporting week, so weekly TREND lines don't dip on a week that isn't
    finished yet (the "pyramid" artifact). A week is kept only if its end date
    is before this week's Monday. Falls back to the original frame if filtering
    would leave it empty (e.g. only the current week has data).

    Use this for trend charts only — never for "this week / last 7 days"
    snapshots, which legitimately show the current week.
    """
    if df is None or df.empty or date_col not in df.columns:
        return df
    today = datetime.today().date()
    monday = today - timedelta(days=today.weekday())
    wk = pd.to_datetime(df[date_col], errors="coerce").dt.date
    kept = df[wk.notna() & (wk < monday)]
    return kept if not kept.empty else df


def get_weekly_ki_by_zone() -> pd.DataFrame:
    """Weekly totals grouped by zone + week_end_date."""
    df = get_weekly_ki()
    if df.empty or "week_end_date" not in df.columns:
        return pd.DataFrame()
    metric_cols = [c for c in df.columns if c not in ("week_end_date", "area", "zone", "district")]
    if not metric_cols:
        return pd.DataFrame()
    return df.groupby(["week_end_date", "zone"])[metric_cols].sum().reset_index()


def get_zone_weekly_actuals() -> pd.DataFrame:
    """
    One row per zone for the most recent shared week: nightly-derived metrics
    (get_weekly_ki_by_zone()'s latest week_end_date) combined with the
    weekly-form Key Indicators (summed per zone from get_weekly_form_data()'s
    latest week — whatever QUESTIONS_CONFIG says that form asks). The two sources' latest
    weeks aren't guaranteed to be the same calendar week (nightly rolls up
    continuously; the weekly form is Sunday-gated), so each is taken
    independently at its own latest COMPLETE week before merging (the
    nightly side excludes the current in-progress week — see
    exclude_current_week — so a partial week is never compared against a
    full week's goal). Used to rank individual metrics against goals for
    the leadership report's "focus" sections — see
    app.analytics.leadership_insights.compute_zone_metric_focus.
    """
    nightly = exclude_current_week(get_weekly_ki_by_zone())
    nightly_latest = pd.DataFrame()
    if not nightly.empty:
        latest_week = nightly["week_end_date"].max()
        nightly_latest = nightly[nightly["week_end_date"] == latest_week].drop(columns=["week_end_date"])

    weekly_form = get_weekly_form_data()
    wf_latest = pd.DataFrame()
    if not weekly_form.empty:
        latest_wf_week = weekly_form["week_end_date"].max()
        wf_cur = weekly_form[weekly_form["week_end_date"] == latest_wf_week]
        # Sum whichever metric columns the weekly form actually produced, not a
        # hardcoded list. The old ["pew","date_metric","gate","renew","rc_total"]
        # named Provo's KIs — none present in CCSM's frame — so this raised a
        # KeyError the moment the parser above started returning real rows.
        _wf_metrics = [c for c in wf_cur.columns
                       if c not in ("week_end_date", "area", "zone")]
        wf_latest = wf_cur.groupby("zone")[_wf_metrics].sum().reset_index()

    if nightly_latest.empty and wf_latest.empty:
        return pd.DataFrame()
    if nightly_latest.empty:
        return wf_latest
    if wf_latest.empty:
        return nightly_latest
    return pd.merge(nightly_latest, wf_latest, on="zone", how="outer").fillna(0.0)


def get_mission_weekly_actuals() -> dict:
    """Mission-wide equivalent of get_zone_weekly_actuals(): latest COMPLETE
    week of get_weekly_ki_trends() (nightly, excluding the current
    in-progress week) combined with latest week of get_weekly_ki_totals()
    (weekly-form KI) into one flat {metric: value} dict."""
    nightly = exclude_current_week(get_weekly_ki_trends(n_weeks=3))
    mission: dict = {}
    if not nightly.empty:
        row = nightly.sort_values("week_end_date").iloc[-1]
        mission.update({c: float(row[c]) for c in nightly.columns if c != "week_end_date"})

    weekly_form = get_weekly_ki_totals(n_weeks=1)
    if not weekly_form.empty:
        row = weekly_form.sort_values("week_end_date").iloc[-1]
        mission.update({c: float(row[c]) for c in weekly_form.columns if c != "week_end_date"})

    return mission


def get_latest_weekly_ki() -> pd.DataFrame:
    """Most recent week_end_date rows (all areas)."""
    df = get_weekly_ki()
    if df.empty or "week_end_date" not in df.columns:
        return pd.DataFrame()
    latest = df["week_end_date"].max()
    return df[df["week_end_date"] == latest].copy()


# ══════════════════════════════════════════════════════════════════════════════
# WEEKLY_FORM_RAW — weekly KI form (pew / date / gate / renew / rc_total)
# ══════════════════════════════════════════════════════════════════════════════

# ── Weekly form structure ─────────────────────────────────────────────────────
# The weekly Google Form has one SECTION PER ZONE, so its response sheet repeats
# the whole question block ten times: 182 columns, with "¿En qué área sirve?" at
# ten different positions. A missionary fills only their own zone's section and
# every other section's columns are blank on that row.
#
# These two constants mirror A3_FORM_AREA_COL / A3_FORM_ZONE_COL in
# CCSM_Agent3.gs. They are structural questions, so unlike the metric columns
# they have no QUESTIONS_CONFIG row to read them from.
# tests/test_weekly_form_parser.py asserts both still match the live header.
#
# This parser previously looked for "What is your Area?", "What is your Zone?",
# "What week" and (Pew)/(Date)/(Gate)/(Renew)/(Total) — Utah Provo's English
# form, inherited with the fork. Against CCSM's Spanish header EVERY ONE of
# those patterns matches ZERO columns, so section detection found nothing,
# get_weekly_form_data() returned an empty frame on every call, and the whole
# Key Indicator pipeline — dashboard KI cards, KI trends, zone KI comparisons,
# projections, Goals actuals — was blank by construction rather than for want
# of data.
_FORM_AREA_COL = "¿En qué área sirve?"
_FORM_ZONE_COL = "¿En qué zona sirve?"

# Fallback only; the real header is read from QUESTIONS_CONFIG's WEEKLY
# report_date row, so a reworded form question follows automatically.
_FORM_WEEK_DATE_COL = "¿Qué fecha está ingresando?"


def _weekly_form_layout(cols: list) -> dict:
    """Locate the repeated per-zone sections in a *_FORM_RAW header.

    read_tab() renames duplicate headers to `name`, `name_1`, `name_2`… so that
    the DataFrame builds, which is why every match here is a `startswith` on the
    base question text rather than an equality test.

    Returns {"sections": [(start, end), …], "zone_col": name|None,
             "ts_col": name|None} with `end` exclusive.
    """
    starts = [i for i, c in enumerate(cols) if str(c).startswith(_FORM_AREA_COL)]
    sections = [
        (s, starts[i + 1] if i + 1 < len(starts) else len(cols))
        for i, s in enumerate(starts)
    ]
    return {
        "sections": sections,
        "zone_col": next((c for c in cols if str(c).startswith(_FORM_ZONE_COL)), None),
        # Google names column 1 in the FORM's locale; the live sheet says
        # "Timestamp" but a re-created form could say "Marca temporal".
        "ts_col": next(
            (c for c in cols
             if str(c).startswith("Timestamp") or str(c).startswith("Marca temporal")),
            None,
        ),
    }


def _weekly_metric_columns() -> list[tuple[str, str]]:
    """[(Form_Column_Header, metric_key), …] for every active WEEKLY metric,
    straight from QUESTIONS_CONFIG — so a question added to the weekly form is
    picked up without a code change, and a reworded one keeps working.

    Excludes report_date: that column IS the week the row is about, handled
    separately below, not a value to sum.
    """
    df = read_tab("QUESTIONS_CONFIG")
    if df.empty or "Metric_Key" not in df.columns:
        return []
    out: list[tuple[str, str]] = []
    for _, r in df.iterrows():
        key = str(r.get("Metric_Key", "")).strip()
        header = str(r.get("Form_Column_Header", "")).strip()
        form = str(r.get("Form_Type", "")).strip().upper()
        active = str(r.get("Active", "TRUE")).strip().upper()
        if not key or not header or form != "WEEKLY":
            continue
        if key == "report_date" or active not in ("TRUE", "YES", "1", ""):
            continue
        out.append((header, key))
    return out


def _weekly_date_column() -> str:
    df = read_tab("QUESTIONS_CONFIG")
    if not df.empty and {"Metric_Key", "Form_Type", "Form_Column_Header"} <= set(df.columns):
        rows = df[(df["Metric_Key"].astype(str).str.strip() == "report_date")
                  & (df["Form_Type"].astype(str).str.strip().str.upper() == "WEEKLY")]
        if not rows.empty:
            header = str(rows.iloc[0]["Form_Column_Header"]).strip()
            if header:
                return header
    return _FORM_WEEK_DATE_COL


def _norm_week_date(raw: str) -> str:
    """Normalise '6/14/2026' or '2026-06-14' style strings to YYYY-MM-DD."""
    raw = str(raw).strip()[:19]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw.split(" ")[0], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


@st.cache_data(ttl=300)
def get_weekly_form_data() -> pd.DataFrame:
    """
    Parse WEEKLY_FORM_RAW (one form section per zone) into tidy rows:
    week_end_date | area | zone | <one column per active WEEKLY metric>.

    The metric columns are whatever QUESTIONS_CONFIG says the weekly form asks —
    for CCSM the seven Key Indicators as `_real` (achieved) and `_meta` (that
    companionship's goal for the week) pairs, plus leader_call and
    correlation_meeting. Callers must not sum a `_real` and a `_meta` together:
    one is an outcome and the other a target.

    This is the only aggregation of the weekly metrics available to the app —
    WEEKLY_KI carries nightly-form rollups.
    """
    df = read_tab("WEEKLY_FORM_RAW")
    if df.empty:
        return pd.DataFrame()

    cols = list(df.columns)
    layout = _weekly_form_layout(cols)
    if not layout["sections"]:
        return pd.DataFrame()

    metric_cols = _weekly_metric_columns()
    if not metric_cols:
        return pd.DataFrame()
    date_header = _weekly_date_column()
    zone_col, ts_col = layout["zone_col"], layout["ts_col"]

    out = []
    for _, row in df.iterrows():
        zone = str(row[zone_col]).strip() if zone_col else ""
        for start, end in layout["sections"]:
            area = str(row.iloc[start]).strip()
            if not area:
                continue

            rec = {"area": area, "zone": zone}
            for header, key in metric_cols:
                val = 0.0
                for j in range(start, end):
                    # startswith, not equality: read_tab suffixes duplicate
                    # headers (_1, _2, …) and every question repeats per zone.
                    if str(cols[j]).startswith(header):
                        v = pd.to_numeric(row.iloc[j], errors="coerce")
                        val = 0.0 if pd.isna(v) else float(v)
                        break
                rec[key] = val

            week = ""
            for j in range(start, end):
                if str(cols[j]).startswith(date_header):
                    raw_week = _norm_week_date(row.iloc[j])
                    if raw_week:
                        # Snap to the Sunday that ends the week (previous or same).
                        # Missionaries sometimes enter Monday by mistake (e.g. 6/15
                        # instead of 6/14).  (weekday()+1)%7 is 0 for Sunday, 1 for
                        # Monday, … so subtracting it always lands on the prior Sunday.
                        _wd = datetime.strptime(raw_week, "%Y-%m-%d")
                        week = (_wd - timedelta(days=(_wd.weekday() + 1) % 7)).strftime("%Y-%m-%d")
                    break
            if not week and ts_col:
                ts = _norm_week_date(row[ts_col])
                if ts:
                    d = datetime.strptime(ts, "%Y-%m-%d")
                    week = (d + timedelta(days=6 - d.weekday())).strftime("%Y-%m-%d")
            rec["week_end_date"] = week
            out.append(rec)

    if not out:
        return pd.DataFrame()
    tidy = pd.DataFrame(out)
    # One row per area per week — keep the latest submission if duplicated
    tidy = tidy.drop_duplicates(subset=["week_end_date", "area"], keep="last")
    return tidy[["week_end_date", "area", "zone"] + [k for _, k in metric_cols]]


@st.cache_data(ttl=300)
def get_weekly_submission_data() -> pd.DataFrame:
    """
    Which reporting weeks each area SUBMITTED the weekly form for — keyed by the
    day it was submitted (the Sunday), not the timestamp time or the in-form date.

    The weekly report covers Mon–Sun and is due Sunday. A submission belongs to
    the week ending on the most recent Sunday on/before its submission date (a
    Sunday submission → that Sunday; a late Mon/Tue submission → the prior Sunday).
    This mirrors ar_checkWeeklyCompliance() in docs/AgentReminder.gs.

    Returns tidy rows: week_end_date | area | zone, deduped per (area, week).
    Unlike get_weekly_form_data() this carries no KI metrics — it answers only
    "did the form arrive", for submission-compliance display.
    """
    df = read_tab("WEEKLY_FORM_RAW")
    if df.empty:
        return pd.DataFrame()

    cols = list(df.columns)
    layout = _weekly_form_layout(cols)
    if not layout["sections"]:
        return pd.DataFrame()
    zone_col, ts_col = layout["zone_col"], layout["ts_col"]
    if ts_col is None:
        return pd.DataFrame()

    out = []
    for _, row in df.iterrows():
        sub = _norm_week_date(row[ts_col])           # submission DATE (time dropped)
        if not sub:
            continue
        d = datetime.strptime(sub, "%Y-%m-%d")
        sunday = (d - timedelta(days=(d.weekday() + 1) % 7)).strftime("%Y-%m-%d")
        zone = str(row[zone_col]).strip() if zone_col else ""
        for start, _end in layout["sections"]:
            area = str(row.iloc[start]).strip()
            if not area:
                continue
            out.append({"week_end_date": sunday, "area": area, "zone": zone})

    if not out:
        return pd.DataFrame()
    tidy = pd.DataFrame(out).drop_duplicates(subset=["week_end_date", "area"], keep="last")
    return tidy[["week_end_date", "area", "zone"]]


def get_weekly_ki_totals(n_weeks: int = 52) -> pd.DataFrame:
    """Mission-wide weekly-form totals per week — every metric that form asks.

    Columns are taken from the parsed frame rather than a hardcoded list; the
    old ["pew","date_metric","gate","renew","rc_total"] was Provo's and would
    KeyError against CCSM's columns.
    """
    df = get_weekly_form_data()
    if df.empty:
        return pd.DataFrame()
    keys = [c for c in df.columns if c not in ("week_end_date", "area", "zone")]
    if not keys:
        return pd.DataFrame()
    grouped = df.groupby("week_end_date")[keys].sum().reset_index()
    return grouped.sort_values("week_end_date").tail(n_weeks)


def get_nightly_weekly_trends(n_weeks: int = 52) -> pd.DataFrame:
    """Mission-wide weekly totals for the NIGHTLY metrics, from DAILY_LOG.

    CCSM's WEEKLY_KI is structurally different from Utah Provo's. Provo derives
    WEEKLY_KI from DAILY_LOG, so it holds nightly rollups and a nightly metric
    can be trended straight off it. CCSM's CCSM_Agent5A.gs replaced that
    wholesale (see its header, "STRUCTURAL CHANGE vs Provo"): WEEKLY_KI is a
    parse of the weekly form's Real/Meta columns, so it holds ONLY the seven
    ki_* pairs and contains no nightly metric at all.

    Nightly metrics therefore have to be bucketed from DAILY_LOG here. Without
    this, every nightly metric routed to get_weekly_ki_trends() and found no
    such column — a projection or trend of nothing.

    Weeks end Sunday, matching the Mon–Sun reporting week used everywhere else
    (see exclude_current_week and CCSM_Agent1A's own week calculation).
    """
    df = get_daily_log(days=n_weeks * 7 + 14)
    if df.empty or "Date" not in df.columns:
        return pd.DataFrame()

    d = pd.to_datetime(df["Date"], errors="coerce")
    keep = d.notna()
    if not keep.any():
        return pd.DataFrame()
    df = df[keep].copy()
    d = d[keep]
    # Snap each day to the Sunday that ENDS its Mon–Sun week: Monday=0 … so
    # (6 - weekday) days forward always lands on that week's Sunday.
    df["week_end_date"] = (
        d + pd.to_timedelta(6 - d.dt.weekday, unit="D")
    ).dt.strftime("%Y-%m-%d")

    meta = {"Date", "Area", "Zone", "District", "week_end_date"}
    metric_cols = [c for c in df.columns if c not in meta]
    if not metric_cols:
        return pd.DataFrame()
    numeric = _num(df, metric_cols)
    grouped = numeric.groupby("week_end_date")[metric_cols].sum(numeric_only=True).reset_index()
    return grouped.sort_values("week_end_date").tail(n_weeks)


def get_nightly_weekly_trends_by_area(n_weeks: int = 52) -> pd.DataFrame:
    """Per-AREA weekly totals for the nightly metrics, from DAILY_LOG.

    The per-area counterpart to get_nightly_weekly_trends(); returns
    area | week_end_date | <one column per nightly metric>. Used by the Effort
    score, whose metrics are all nightly and therefore have no per-area weekly
    source in CCSM's WEEKLY_KI.
    """
    df = get_daily_log(days=n_weeks * 7 + 14)
    if df.empty or "Date" not in df.columns or "Area" not in df.columns:
        return pd.DataFrame()

    d = pd.to_datetime(df["Date"], errors="coerce")
    keep = d.notna()
    if not keep.any():
        return pd.DataFrame()
    df = df[keep].copy()
    d = d[keep]
    df["week_end_date"] = (
        d + pd.to_timedelta(6 - d.dt.weekday, unit="D")
    ).dt.strftime("%Y-%m-%d")
    df["area"] = df["Area"].astype(str).str.strip()

    meta = {"Date", "Area", "Zone", "District", "week_end_date", "area"}
    metric_cols = [c for c in df.columns if c not in meta]
    if not metric_cols:
        return pd.DataFrame()
    numeric = _num(df, metric_cols)
    return (numeric.groupby(["area", "week_end_date"])[metric_cols]
            .sum(numeric_only=True).reset_index())


# ══════════════════════════════════════════════════════════════════════════════
# DAILY_LOG
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_daily_log(days: int = 365) -> pd.DataFrame:
    """
    DAILY_LOG rows for the last `days` calendar days.
    Date column normalised to string YYYY-MM-DD.

    Cached: pure derivation of DAILY_LOG, which only Apps Script writes — the
    app's own writes (which clear only the sheets-layer caches) never touch it,
    so this can never serve staler data than read_tab itself. Same reasoning on
    the other cached derivations below; don't add caches like this to
    derivations of tabs the APP writes (NOTES, TABLEAU_*, MISSION_ORG) without
    also clearing them from the write path.
    """
    df = read_tab("DAILY_LOG", header_marker="Date")
    if df.empty:
        return df
    rename = {}
    for orig in df.columns:
        low = orig.strip().lower()
        if low == "log_date" or low == "date":
            rename[orig] = "Date"
        elif low == "area_name" or low == "area":
            rename[orig] = "Area"
        elif low == "zone":
            rename[orig] = "Zone"
        elif low == "district":
            rename[orig] = "District"
        elif low.endswith("_knocked"):
            # DAILY_LOG header predates the QUESTIONS_CONFIG "Attempt" rename;
            # data is positionally correct, only the label is stale.
            rename[orig] = orig.strip()[: -len("_knocked")] + "_Attempt"
    if rename:
        df = df.rename(columns=rename)
    if "Date" not in df.columns:
        return pd.DataFrame()
    df["Date"] = df["Date"].astype(str).str.strip().str[:10]
    cutoff = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    df = df[df["Date"] >= cutoff].copy()
    metric_cols = [c for c in df.columns if c not in ("Date", "Area", "Zone", "District")]
    return _num(df, metric_cols)


def get_daily_summary(days: int = 30) -> pd.DataFrame:
    """Mission-wide daily totals — one row per date."""
    df = get_daily_log(days)
    if df.empty:
        return df
    metric_cols = [c for c in df.columns if c not in ("Date", "Area", "Zone", "District")]
    return df.groupby("Date")[metric_cols].sum().reset_index().sort_values("Date")


# ══════════════════════════════════════════════════════════════════════════════
# NIGHTLY_FORM_RAW — submission timeliness (on-time vs late)
# ══════════════════════════════════════════════════════════════════════════════

def _norm_date_flex(raw) -> str:
    """Parse a date or datetime string to YYYY-MM-DD. Drops any time portion.
    Returns '' if unparseable. Handles 6/17/2026, 6/17/2026 11:28:46, 2026-06-17."""
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return ""
    s = s.split(" ")[0].split("T")[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


@st.cache_data(ttl=300)
def get_nightly_submission_timing() -> pd.DataFrame:
    """
    Parse NIGHTLY_FORM_RAW to determine, per area per reported day, whether the
    nightly form was submitted ON TIME (the form's Timestamp date == the
    "What date are you inputting?" date) or LATE (different dates).

    The nightly form is multi-section: one submission row carries up to 7
    area/date entries that all share the row's Timestamp. Each section's area and
    date columns are paired in document order.

    Returns one row per (area, report_date):
        area | report_date (YYYY-MM-DD) | submit_date (YYYY-MM-DD) | on_time (bool)
    on_time is True if ANY submission for that area+date landed on the same day.
    Returns an empty frame (never raises) if the tab is unavailable.
    """
    empty = pd.DataFrame(columns=["area", "report_date", "submit_date", "on_time"])
    try:
        df = read_tab("NIGHTLY_FORM_RAW")
    except Exception:
        return empty
    cols = list(df.columns)
    if df.empty or not cols:
        return empty

    ts_col = next((c for c in cols if str(c).strip().lower().startswith("timestamp")), cols[0])
    area_idx = [i for i, c in enumerate(cols) if str(c).strip().lower().startswith("what is your area?")]
    date_idx = [i for i, c in enumerate(cols) if str(c).strip().lower().startswith("what date are you inputting?")]
    pairs = list(zip(area_idx, date_idx))  # section-aligned by document order
    if not pairs:
        return empty

    out = []
    for _, row in df.iterrows():
        submit_date = _norm_date_flex(row.get(ts_col, ""))
        if not submit_date:
            continue
        for ai, di in pairs:
            area = str(row.iloc[ai]).strip()
            if not area or area.lower() == "nan":
                continue
            report_date = _norm_date_flex(row.iloc[di])
            if not report_date:
                continue
            out.append({
                "area": area,
                "report_date": report_date,
                "submit_date": submit_date,
                "on_time": report_date == submit_date,
            })

    if not out:
        return empty
    tidy = pd.DataFrame(out)
    # Collapse duplicate submissions: on time if it was ever submitted on time;
    # keep the earliest submission date for reference.
    return tidy.groupby(["area", "report_date"], as_index=False).agg(
        submit_date=("submit_date", "min"),
        on_time=("on_time", "max"),
    )


# Effort question header in NIGHTLY_FORM_RAW (matches Agent5A / Agent1A).
_EFFORT_COL_PREFIX = "all, most or some effort"

def get_effort_by_area(days: int = 7) -> pd.DataFrame:
    """
    Per-area effort tally from NIGHTLY_FORM_RAW over the last `days` reported days.
    The nightly form is multi-section: each section pairs an area, a report date,
    and an effort answer (All / Most / Some) in document order.

    Returns one row per area, sorted by effort score then activity:
        Area | All | Most | Some | Total | Effort Score
    Effort Score = (All*3 + Most*2 + Some*1) / Total  (same weighting as Agent1A).
    One effort value is counted per area per report_date (re-submissions deduped,
    keeping the latest). Returns an empty frame (never raises) if unavailable.
    """
    out_cols = ["Area", "All", "Most", "Some", "Total", "Effort Score"]
    empty = pd.DataFrame(columns=out_cols)
    try:
        df = read_tab("NIGHTLY_FORM_RAW")
    except Exception:
        return empty
    cols = list(df.columns)
    if df.empty or not cols:
        return empty

    def _starts(prefix):
        return [i for i, c in enumerate(cols) if str(c).strip().lower().startswith(prefix)]

    area_idx   = _starts("what is your area?")
    date_idx   = _starts("what date are you inputting?")
    effort_idx = _starts(_EFFORT_COL_PREFIX)
    trips = list(zip(area_idx, date_idx, effort_idx))  # section-aligned by order
    if not trips:
        return empty

    cutoff = (datetime.now().date() - timedelta(days=days - 1))  # inclusive window

    rows = []
    for _, row in df.iterrows():
        for ai, di, ei in trips:
            area = str(row.iloc[ai]).strip()
            if not area or area.lower() == "nan":
                continue
            report_date = _norm_date_flex(row.iloc[di])
            if not report_date:
                continue
            try:
                if datetime.strptime(report_date, "%Y-%m-%d").date() < cutoff:
                    continue
            except ValueError:
                continue
            ev = str(row.iloc[ei]).strip().lower()
            level = {"all": "All", "most": "Most", "some": "Some"}.get(ev)
            if level is None:
                continue
            rows.append({"area": area, "report_date": report_date, "level": level})

    if not rows:
        return empty
    tidy = pd.DataFrame(rows).drop_duplicates(
        subset=["area", "report_date"], keep="last")
    pivot = (tidy.groupby("area")["level"].value_counts()
             .unstack(fill_value=0).reset_index())
    for lvl in ("All", "Most", "Some"):
        if lvl not in pivot.columns:
            pivot[lvl] = 0
    pivot["Total"] = pivot["All"] + pivot["Most"] + pivot["Some"]
    pivot["Effort Score"] = (
        (pivot["All"] * 3 + pivot["Most"] * 2 + pivot["Some"]) / pivot["Total"]
    ).round(2)
    pivot = pivot.rename(columns={"area": "Area"})
    return (pivot[out_cols]
            .sort_values(["Effort Score", "Total"], ascending=[False, False])
            .reset_index(drop=True))


# ══════════════════════════════════════════════════════════════════════════════
# LIVE_SNAPSHOT
# ══════════════════════════════════════════════════════════════════════════════

def get_live_snapshot() -> pd.DataFrame:
    """Full LIVE_SNAPSHOT with all rolling window columns."""
    df = read_tab("LIVE_SNAPSHOT", header_marker="District")
    if df.empty:
        return df
    numeric_cols = [c for c in df.columns if c not in ("Area", "Zone", "District", "Last_Updated")]
    return _num(df, numeric_cols)


# ══════════════════════════════════════════════════════════════════════════════
# SCORES
# ══════════════════════════════════════════════════════════════════════════════

#: Leadership tracking rows in SCORES, matched by Area_Name. Mirrors
#: asc_isLeadershipRow_ in CCSM_AgentScores.gs. They never submit and score 0,
#: so leaving them in drags every mission average down.
_SCORES_LEADERSHIP_RE = (
    r"^(Mission President|Assistant to President|Zone Leader|"
    r"Sister Training Leader -|District Leader -)"
)


@st.cache_data(ttl=300)
def get_scores(week_ending: str = None) -> pd.DataFrame:
    """The SCORES tab: one row per area per scored week.

    A shared reader so the Puntajes page and the Informes page cannot disagree
    about which rows count — leadership rows are dropped here, once.

    `week_ending` filters to a single week; None returns every week.
    """
    df = read_tab("SCORES")
    if df.empty:
        return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]
    for col in ("Effort_Score", "Skill_Score", "KI_Score", "Effectiveness_Score"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "Week_Ending_Date" in df.columns:
        df["Week_Ending_Date"] = (
            df["Week_Ending_Date"].astype(str).str.strip().str[:10]
        )

    drop = pd.Series(False, index=df.index)
    if "Area_Name" in df.columns:
        drop = df["Area_Name"].astype(str).str.match(
            _SCORES_LEADERSHIP_RE, case=False, na=False)
    if "Zone" in df.columns:
        drop = drop | (df["Zone"].astype(str).str.strip().str.upper() == "ALL")
    df = df[~drop].copy()

    if week_ending:
        df = df[df["Week_Ending_Date"] == str(week_ending)[:10]].copy()
    return df


@st.cache_data(ttl=300)
def get_scored_weeks() -> list:
    """Every Week_Ending_Date present in SCORES, newest first."""
    df = get_scores()
    if df.empty or "Week_Ending_Date" not in df.columns:
        return []
    return sorted(
        {w for w in df["Week_Ending_Date"].astype(str) if w and w != "nan"},
        reverse=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# MISSION_ORG
# ══════════════════════════════════════════════════════════════════════════════

def get_areas_df(active_only: bool = True) -> pd.DataFrame:
    """
    All areas from MISSION_ORG.
    active_only=True filters to Active == TRUE rows.
    Leadership rows included — callers filter as needed.

    NOT cached, deliberately: read_tab() underneath already carries the
    ttl=300 cache (and is what every test in tests/test_db mocks directly
    via patch("app.db.queries.read_tab", ...) to swap in per-test fixtures)
    — caching this function TOO would key purely on active_only (no way to
    see that read_tab was mocked differently), so whichever test ran first
    in the pytest process would silently poison every later test that also
    calls get_areas_df(). Confirmed live (2026-07-21): wrapping this in
    @st.cache_data broke test_zones_leadership_filter.py /
    test_all_leader_assignments.py / test_alltime_compliance.py the moment
    they ran after another test in the same process. The real Mission Goals
    slowness fix is _resolve_area_category's per-area cache below, not this.
    """
    df = read_tab("MISSION_ORG")
    if df.empty:
        return df
    if active_only and "Active" in df.columns:
        df = df[df["Active"].astype(str).str.upper() == "TRUE"].copy()
    return df


_LEADERSHIP_NAME_RE = r"^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)"


def get_submitting_areas() -> pd.DataFrame:
    """Active MISSION_ORG rows that submit the nightly form (no leadership rows).

    Leadership rows are identified by Area_Name pattern, not by the Is_ZL/Is_STL/
    Is_DL/Is_AP/Is_MP flags — those flags are also legitimately TRUE on a real
    teaching-area row whenever that area's companion currently holds a calling
    (mirrors AgentTransfer.gs's at_isLeadershipRow_).

    NOT cached — see get_areas_df's docstring, same test-poisoning reason.
    """
    df = get_areas_df()
    if df.empty:
        return df
    mask_leadership = df.get("Area_Name", pd.Series(dtype=str)).astype(str).str.match(
        _LEADERSHIP_NAME_RE, case=False
    )
    return df[~mask_leadership].copy()


def get_zones() -> list:
    """Sorted list of unique zone names from real teaching areas (excluding ALL).

    Leadership tracking rows are excluded: their Zone can name a zone that no
    longer has any teaching areas (e.g. after Provo North + Provo West merged
    into "Provo North & West (PN/W)", the "Zone Leader - Provo North/West"
    rows still carry the old zone names). Counting those would surface phantom,
    empty zones in the dashboard's filters. Mirrors get_submitting_areas().
    """
    df = get_submitting_areas()
    if df.empty or "Zone" not in df.columns:
        return []
    zones = df["Zone"].dropna().unique().tolist()
    return sorted(z for z in zones if str(z).upper() != "ALL")


def get_districts(zone: str = None) -> list:
    """Sorted list of districts from real teaching areas, optionally by zone.

    Excludes leadership tracking rows (same phantom-value reasoning as
    get_zones()) — their District can be a leadership-only label like
    "Edgemont District" or "ALL" that isn't a real teaching district.
    """
    df = get_submitting_areas()
    if df.empty or "District" not in df.columns:
        return []
    if zone:
        df = df[df["Zone"] == zone]
    return sorted(df["District"].dropna().unique().tolist())


def get_allowed_emails() -> set:
    """All valid companion email addresses from MISSION_ORG only (allowed to view dashboard)."""
    df = get_areas_df()
    emails = set()
    for col in ("Companion1_Email", "Companion2_Email"):
        if col in df.columns:
            for e in df[col].dropna():
                e = str(e).strip().lower()
                if e and "@" in e and "notreadyyet" not in e and "tbd@" not in e:
                    emails.add(e)
    return emails


def get_user_role(email: str) -> str:
    """
    Derive role from MISSION_ORG flags.
    Returns: 'president' | 'assistant' | 'leader' | 'missionary' | 'unknown'
    """
    if not email:
        return "unknown"
    email_lower = email.lower().strip()
    df = get_areas_df()
    if df.empty:
        return "unknown"

    for _, row in df.iterrows():
        emails = {
            str(row.get("Companion1_Email", "")).lower().strip(),
            str(row.get("Companion2_Email", "")).lower().strip(),
        }
        if email_lower not in emails:
            continue
        if str(row.get("Is_MP", "")).upper() == "TRUE":
            return "president"
        if str(row.get("Is_AP", "")).upper() == "TRUE":
            return "assistant"
        if any(str(row.get(f, "")).upper() == "TRUE" for f in ("Is_ZL", "Is_STL", "Is_DL")):
            return "leader"
        return "missionary"

    return "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# GOALS_CONFIG
# ══════════════════════════════════════════════════════════════════════════════

def get_goals_df() -> pd.DataFrame:
    """
    GOALS_CONFIG: Area | [metric_key...] — weekly goals per area per metric.
    Numeric columns coerced; missing values become 0.
    """
    df = read_tab("GOALS_CONFIG", header_marker="Area")
    if df.empty:
        return df
    metric_cols = [c for c in df.columns if c != "Area"]
    return _num(df, metric_cols)


def get_mission_goals() -> dict:
    """Sum all per-area goals to get mission-wide weekly goal per metric."""
    df = get_goals_df()
    if df.empty:
        return {}
    metric_cols = [c for c in df.columns if c != "Area"]
    return df[metric_cols].sum().to_dict()


def get_area_goals(area: str) -> dict:
    """Return {metric_key: goal_value} for a specific area. 0 if not found."""
    df = get_goals_df()
    if df.empty or "Area" not in df.columns:
        return {}
    row = df[df["Area"] == area]
    if row.empty:
        return {}
    return row.iloc[0].drop("Area").to_dict()


def get_question_metrics(form_type: str = None) -> list:
    """
    Metric definitions from QUESTIONS_CONFIG.
    Returns [(metric_key, display_name, form_type), ...] in sheet order.
    form_type: optional filter 'NIGHTLY' or 'WEEKLY'.
    """
    df = read_tab("QUESTIONS_CONFIG")
    if df.empty or "Metric_Key" not in df.columns:
        return []
    out = []
    for _, r in df.iterrows():
        key  = str(r.get("Metric_Key", "")).strip()
        name = str(r.get("Metric_Display_Name", "")).strip() or key
        ftype = str(r.get("Form_Type", "")).strip().upper()
        if not key:
            continue
        if form_type and ftype != form_type.upper():
            continue
        out.append((key, name, ftype))
    return out


def save_area_goals(area: str, goals: dict) -> None:
    """
    Write one area's weekly goals to GOALS_CONFIG (schema: Area | metric keys).
    Rewrites the tab cleanly, preserving every other area's row. This is also
    what migrates the tab off the legacy header the agents can't read.
    """
    from app.db.sheets_client import overwrite_tab

    keys = [k for k, _, _ in get_question_metrics()]
    existing = get_goals_df()  # header-marker read: empty if legacy/blank tab

    rows_by_area = {}
    if not existing.empty and "Area" in existing.columns:
        for _, r in existing.iterrows():
            a = str(r.get("Area", "")).strip()
            if a:
                rows_by_area[a] = {k: r.get(k, 0) for k in keys}

    rows_by_area[area] = {k: goals.get(k, 0) for k in keys}

    header = ["Area"] + keys
    body = [
        [a] + [int(float(vals.get(k, 0) or 0)) for k in keys]
        for a, vals in sorted(rows_by_area.items())
    ]
    overwrite_tab("GOALS_CONFIG", [header] + body)


def save_all_area_goals(goals_by_area: dict) -> None:
    """
    Bulk counterpart to save_area_goals: write EVERY area in `goals_by_area`
    ({area: {metric_key: goal}}) into GOALS_CONFIG in one overwrite_tab call —
    one Sheets API write total, not one per area. Rows for areas not in
    `goals_by_area` are preserved as-is.
    """
    from app.db.sheets_client import overwrite_tab

    keys = [k for k, _, _ in get_question_metrics()]
    existing = get_goals_df()

    rows_by_area = {}
    if not existing.empty and "Area" in existing.columns:
        for _, r in existing.iterrows():
            a = str(r.get("Area", "")).strip()
            if a:
                rows_by_area[a] = {k: r.get(k, 0) for k in keys}

    for area, goals in goals_by_area.items():
        rows_by_area[str(area).strip()] = {k: goals.get(k, 0) for k in keys}

    header = ["Area"] + keys
    body = [
        [a] + [int(float(vals.get(k, 0) or 0)) for k in keys]
        for a, vals in sorted(rows_by_area.items())
    ]
    overwrite_tab("GOALS_CONFIG", [header] + body)


def delete_area_goals(area: str) -> None:
    """Remove one area's custom goals row from GOALS_CONFIG."""
    from app.db.sheets_client import overwrite_tab

    keys = [k for k, _, _ in get_question_metrics()]
    existing = get_goals_df()
    if existing.empty or "Area" not in existing.columns:
        return
    header = ["Area"] + keys
    body = [
        [str(r["Area"]).strip()] + [int(float(r.get(k, 0) or 0)) for k in keys]
        for _, r in existing.iterrows()
        if str(r["Area"]).strip() and str(r["Area"]).strip() != area
    ]
    overwrite_tab("GOALS_CONFIG", [header] + body)


def get_zone_goals(zone: str) -> dict:
    """
    Zone-level weekly goals: sum of per-area goals across the zone's
    submitting areas. Returns {metric_key: goal_value}.
    """
    goals = get_goals_df()
    if goals.empty or "Area" not in goals.columns:
        return {}
    areas = get_submitting_areas()
    if areas.empty or "Zone" not in areas.columns:
        return {}
    zone_areas = set(
        areas[areas["Zone"] == zone]["Area_Name"].astype(str).str.strip()
    )
    sub = goals[goals["Area"].astype(str).str.strip().isin(zone_areas)]
    if sub.empty:
        return {}
    metric_cols = [c for c in sub.columns if c != "Area"]
    return sub[metric_cols].sum().to_dict()


def get_district_goals(district: str) -> dict:
    """
    District-level weekly goals: sum of per-area goals across the district's
    submitting areas. Returns {metric_key: goal_value}. Same pattern as
    get_zone_goals, one level down.
    """
    goals = get_goals_df()
    if goals.empty or "Area" not in goals.columns:
        return {}
    areas = get_submitting_areas()
    if areas.empty or "District" not in areas.columns:
        return {}
    district_areas = set(
        areas[areas["District"] == district]["Area_Name"].astype(str).str.strip()
    )
    sub = goals[goals["Area"].astype(str).str.strip().isin(district_areas)]
    if sub.empty:
        return {}
    metric_cols = [c for c in sub.columns if c != "Area"]
    return sub[metric_cols].sum().to_dict()


# ══════════════════════════════════════════════════════════════════════════════
# GOAL_RECALIBRATION (written by Agent2.gs, once per ~6-week transfer)
# ══════════════════════════════════════════════════════════════════════════════

def get_goal_recalibration() -> pd.DataFrame:
    """
    Per-area per-metric trend analysis + suggested next-transfer goal, written
    by Agent2.gs once per ~6-week transfer. Row 1 of the tab is a stale legacy
    header duplicated as a data row in row 2 (a2_writeGoalRecalibration quirk)
    — read_tab's header_marker scan finds the real header and drops the repeat.
    """
    df = read_tab("GOAL_RECALIBRATION", header_marker="Metric_Key")
    if df.empty or "Metric_Key" not in df.columns:
        return pd.DataFrame()

    rename = {}
    for c in df.columns:
        if c.startswith("Avg_Week_T1"):
            rename[c] = "avg_week_t1"
        elif c.startswith("Avg_Week_T2"):
            rename[c] = "avg_week_t2"
        elif c.startswith("Avg_Week_T3"):
            rename[c] = "avg_week_t3"
    df = df.rename(columns=rename)

    return _num(df, ["Current_Goal", "avg_week_t1", "avg_week_t2", "avg_week_t3", "Suggested_Goal"])


def apply_goal_recalibration_suggestion(area: str, metric_key: str, suggested_goal: float) -> None:
    """Write one GOAL_RECALIBRATION suggestion into GOALS_CONFIG for one area+metric."""
    current = get_area_goals(area)
    current[metric_key] = suggested_goal
    save_area_goals(area, current)


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDED GOALS (based on actual performance — area's own, or mission-wide)
# ══════════════════════════════════════════════════════════════════════════════

# ── Recent-convert totals: REMOVED ────────────────────────────────────────────
# get_latest_rc_total / get_area_rc_attendance_potential /
# get_mission_rc_attendance_potential lived here. All three read a `rc_total`
# column — Utah Provo's running headcount of the recent converts an area is
# working with — that CCSM's weekly form does not ask, so each could only ever
# return 0. Their only callers were the Goals page's Renew fraction
# denominators, removed in 3a8bfa7 because "3 / 0" is worse than no fraction.
#
# If CCSM ever adds a recent-convert headcount question, rebuild this from the
# QUESTIONS_CONFIG metric key rather than reinstating the hardcoded "rc_total".


# ── Per-language weekly expectations ────────────────────────────────────────
#
# Flat weekly per-area expectations, set by the area's MISSION_ORG
# Language_Type. NOT based on submitted data — a pure "this is the bar"
# table. nm_lessons/new_found/mmm_sent here are the SAME numbers
# AREA_TYPE_EXPECTATIONS carries (see below) — as of 2026-07-18 (Carson) this
# whole table is user-editable from the Goals page's "Area Expectation
# Settings" tab, so get_area_weekly_expectation/get_mission_weekly_expectation
# _total both resolve through get_area_type_expectations() rather than a
# hardcoded dict; _AREA_TYPE_EXPECTATIONS_DEFAULTS below is what a fresh
# install (or an emptied sheet tab) falls back to:
#   English            15 NM lessons / 2 new found / 70 MMMs
#   Spanish            double English on both, but only 10 MMMs
#   Bilingual          halfway between English and Spanish (23 / 3 / 40)
#   Haitian/Creole/French, ASL, Chinese — English rates except MMMs drop to
#     10, but as THREE SEPARATE groups, not one shared bucket (Carson,
#     2026-07-18: "the Haitian area needs to be held to a different
#     expectation... without changing the ASL or the other one") — they
#     started identical (15/2/10/1/1 each) but are independently editable
#     from here on, each its own section on the Area Expectation Settings
#     tab. (Haitian/Creole/French is also matched by AREA NAME, not just by
#     Language_Type — see _language_group.)
# Anything unrecognized (blank Language_Type, any other language) falls
# back to English — including English-speaking "Asian" YSA areas, which are
# held to the full English 70-MMM standard (Carson, 2026-07-18).


#: The expectation group every area belongs to when the roster defines no
#: language split. CCSM is a single-language mission and its MISSION_ORG has no
#: Language_Type column at all.
DEFAULT_AREA_TYPE_GROUP = "all"


def _language_group(language_type, area_name="") -> str:
    """Map a raw MISSION_ORG Language_Type string onto an expectation group.

    Utah Provo splits its roster six ways (English, Spanish, Bilingual,
    Haitian/Creole/French, ASL, Chinese) because it serves all of them, and the
    inherited version of this function hardcoded that split plus area-NAME
    matching on "Haitian"/"Creole"/"French".

    CCSM serves one language and its MISSION_ORG has no Language_Type column,
    so every lookup returned blank and every area fell through to Provo's
    "english" bucket — which is not merely the wrong label, it is the strictest
    of Provo's six expectation sets (70 MMMs/week), applied to 98 Chilean areas
    for metrics they do not collect.

    A roster that DOES carry a language is still honoured, so this stays correct
    if CCSM ever adds one (a Mapuche- or English-speaking area, say). Matching
    is substring-based because the column is hand-typed.
    """
    lang = str(language_type or "").strip().lower()
    if not lang:
        return DEFAULT_AREA_TYPE_GROUP
    if "bilingual" in lang or ("spanish" in lang and "english" in lang):
        return "bilingual"
    if "spanish" in lang or "español" in lang or "espanol" in lang:
        return "spanish"
    if "english" in lang or "inglés" in lang or "ingles" in lang:
        return "english"
    return DEFAULT_AREA_TYPE_GROUP


@st.cache_data(ttl=300)
def get_area_language_group(area: str) -> str:
    """One area's expectation group, from its MISSION_ORG Language_Type.

    Returns DEFAULT_AREA_TYPE_GROUP when the roster carries no language column,
    which is CCSM's case — see _language_group.
    """
    areas = get_submitting_areas()
    if (
        not areas.empty
        and "Language_Type" in areas.columns
        and "Area_Name" in areas.columns
    ):
        names = areas["Area_Name"].astype(str).str.strip().str.lower()
        match = areas[names == str(area).strip().lower()]
        if not match.empty:
            return _language_group(match.iloc[0].get("Language_Type", ""), area)
    return DEFAULT_AREA_TYPE_GROUP


def get_area_weekly_expectation(area: str, metric: str) -> int:
    """
    One area's flat WEEKLY expectation for `metric` ("nm_lessons",
    "new_found", or "mmm_sent"), from resolve_area_expectations() (custom
    categories first, then the area's built-in language group). Used as the
    fixed "/ N" fraction denominator on Area Goal Customization and the
    Breakdowns trend chart's expectation lines. If the indicator's stored
    cadence is MONTHLY (Carson, 2026-07-18: cadence is now per-indicator,
    editable), converted to a weekly-equivalent via the mission-wide average
    weeks/month (_AVG_WEEKS_PER_MONTH) — a rough conversion, not tied to any
    specific calendar month, since this function takes no date. Rounded —
    the sheet is meant to carry whole-number counts, but a hand-edited
    fraction shouldn't crash this.
    """
    entry = resolve_area_expectations(area).get(metric)
    if not entry:
        return 0
    value = entry["value"]
    if entry["cadence"] == "monthly":
        value = value / _AVG_WEEKS_PER_MONTH
    return int(round(value))


@st.cache_data(ttl=300)
def get_mission_weekly_expectation_total(metric: str) -> int:
    """
    Hypothetical mission-wide WEEKLY total for `metric`: every submitting
    area hitting its own resolve_area_expectations() figure (custom
    categories included, monthly indicators converted to a weekly-
    equivalent), summed. Used as the fixed denominator on Mission Goals'
    fractions — the caller scales this weekly figure up to a monthly one
    (see _weeks_in_month in pages/02_Metas.py, dynamic per calendar month).
    """
    areas = get_submitting_areas()
    if areas.empty or "Area_Name" not in areas.columns:
        return 0
    names = areas["Area_Name"].dropna().astype(str)
    total = 0.0
    for nm in names:
        entry = resolve_area_expectations(nm).get(metric)
        if not entry:
            continue
        v = entry["value"]
        total += v / _AVG_WEEKS_PER_MONTH if entry["cadence"] == "monthly" else v
    return int(round(total))


@st.cache_data(ttl=300)
def get_mission_monthly_expectation_total(metric: str, month_start: str) -> int:
    """
    Hypothetical mission-wide MONTHLY total for `metric` over the calendar
    month starting at `month_start` (ISO date): every submitting area at
    its own resolve_area_expectations() figure. A monthly-cadence
    indicator counts as-is; a weekly-cadence one scales by that month's
    EXACT weeks (days/7) — except pew and renew, both Sunday-only church-
    attendance events, which scale by the month's actual Sunday count (4
    or 5), matching the Goals page's REC convention. Exact per-area floats
    summed THEN
    ceil'd — not routed through get_mission_weekly_expectation_total,
    whose int-rounded weekly figure re-scaled by an average month would
    drift ~15% for monthly-cadence indicators like Gate. 0 when no area
    has an expectation — the Mission Goals fraction only draws for a
    positive total (same "no expectation, no reference" rule as the
    Breakdowns lines).
    """
    try:
        start = date.fromisoformat(month_start)
    except (ValueError, TypeError):
        return 0
    nxt = (date(start.year + 1, 1, 1) if start.month == 12
           else date(start.year, start.month + 1, 1))
    days = (nxt - start).days
    weeks = days / 7
    sundays = sum(1 for i in range(days)
                  if (start + timedelta(days=i)).weekday() == 6)
    areas = get_submitting_areas()
    if areas.empty or "Area_Name" not in areas.columns:
        return 0
    total = 0.0
    for nm in areas["Area_Name"].dropna().astype(str):
        entry = resolve_area_expectations(nm).get(metric)
        if not entry:
            continue
        try:
            v = float(entry.get("value") or 0)
        except (ValueError, TypeError):
            continue
        if v <= 0:
            continue
        if entry["cadence"] == "monthly":
            total += v
        else:
            # A weekly expectation scales to a month differently depending on
            # where the number comes from. A NIGHTLY metric accumulates every
            # day, so a month holds days/7 = 4.4286 weeks of it. A WEEKLY-FORM
            # metric is reported once per week, so a month holds however many
            # of those reports actually occur — 4 or 5, never 4.4286.
            #
            # Carson, 2026-07-21: Pew ("People at Sacrament Meeting") is a
            # once-a-week church-attendance event exactly like Renew, but was
            # only scaled by the generic weeks-in-month figure — a 31-day
            # month's 4.4286 "weeks" vs the real 4 Sundays inflated 60 areas x
            # 1/wk to 266 instead of the correct 240.
            #
            # That was fixed by naming Provo's two once-a-week keys. Naming
            # keys does not travel: CCSM's weekly form carries all SEVEN of its
            # Key Indicators, so every one of them was being inflated by ~11%
            # here, and a mission whose form changes would silently regain the
            # bug. The rule is the metric's FORM, which the catalogue knows.
            once_weekly = metric in _weekly_form_metric_keys()
            total += v * (sundays if once_weekly else weeks)
    return int(math.ceil(total)) if total > 0 else 0


# ── Area-type expectations (Goals fractions + Breakdowns lines + Effort) ───
#
# Backs get_area_weekly_expectation/get_mission_weekly_expectation_total
# above (nm_lessons/new_found/mmm_sent) AND the Effort score on
# pages/06_Puntajes.py (nm_lessons/new_found/mmm_sent/pew/gate) — ONE table
# for both, editable from the Goals page's "Area Expectation Settings" tab
# (Carson, 2026-07-18) via save_area_type_expectations() below.
#
# Long/normalized format (Carson, 2026-07-18: "have it be able to be
# changed — what the indicator is and whether it's weekly or monthly ...
# also add other expectations if wanted"): each CATEGORY (the 4 built-in
# language groups, or a custom one) is a variable-length list of
# INDICATORS, each independently naming a metric, a weekly/monthly cadence,
# and a value — not a fixed 5-column row per category. Lives in its own
# sheet tab (AREA_TYPE_EXPECTATIONS, one row per indicator) instead of a
# hardcoded dict; _AREA_TYPE_INDICATOR_DEFAULTS below is only the fallback
# for when that tab is empty or a category is missing from it. Same four
# built-in groups, same _language_group() matching. See
# docs/superpowers/specs/2026-07-17-effort-score-rework-design.md (the
# original, fixed-5-metric version of this table).
AREA_TYPE_EXPECTATIONS_TAB = "AREA_TYPE_EXPECTATIONS"

# Mission-wide average weeks/month (30.4368-day average month / 7) — used
# ONLY by callers that need a weekly-equivalent for a MONTHLY indicator but
# have no specific calendar month to prorate against (get_area_weekly_
# expectation, get_mission_weekly_expectation_total). Where an exact date
# IS available (get_area_effort_expectations_weekly), _mp_weeks_in_month
# prorates against that date's REAL month length instead — more precise,
# used in preference to this constant whenever possible.
_AVG_WEEKS_PER_MONTH = 30.4368 / 7

def _area_type_indicator_defaults() -> dict[str, list[tuple[str, str, float]]]:
    """group key -> [(metric, cadence, value), …], the fallback used when
    AREA_TYPE_EXPECTATIONS is empty or a category is missing from it.

    Built from AGENT_CONFIG's GOAL_* keys — the weekly per-area targets the
    mission itself set, and the same numbers CCSM_Agent1A.gs coaches against —
    rather than a written-down table. There is one group because CCSM is a
    single-language mission (see _language_group).

    This replaced six hardcoded Utah Provo groups over Provo metrics
    (nm_lessons 15/30/23, new_found, mmm_sent 70/10/40, pew, gate). Since
    CCSM's roster has no Language_Type column, every one of its 98 areas landed
    in the strictest of those six and was measured against metrics it does not
    collect — so every expectation on the Goals page read as unmet, forever.

    A GOAL_* value of 0 is skipped: an expectation of zero is not a bar, and
    _scale_effort_metric() treats it as "nothing expected, full marks", which
    would quietly award a perfect score for a metric nobody set a target on.
    """
    config = get_agent_config()
    rows: list[tuple[str, str, float]] = []
    for key, raw in config.items():
        if not str(key).startswith("GOAL_"):
            continue
        metric = str(key)[len("GOAL_"):].strip()
        if not metric:
            continue
        try:
            value = float(str(raw).strip())
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        # Every GOAL_* in AGENT_CONFIG is a WEEKLY per-area target (see
        # CCSM_AGENT_CONFIG_ROWS in CcsmData.gs). Provo's table mixed in a
        # monthly cadence for `gate`; CCSM has no monthly goal key.
        rows.append((metric, "weekly", value))

    rows.sort(key=lambda r: r[0])
    return {DEFAULT_AREA_TYPE_GROUP: rows}

# group key -> the label AREA_TYPE_EXPECTATIONS' Area_Type column carries.
#
# One built-in group, because CCSM is a single-language mission whose roster
# carries no Language_Type column (see _language_group). Provo's six —
# English / Spanish / Bilingual / Haitian-Creole-French / ASL / Chinese — named
# languages CCSM does not serve, and offered the mission six editable
# expectation sets where five could never apply to any area.
#
# The label is the Spanish the rest of this app uses, since it appears on the
# Goals page's Area Expectation Settings tab. Adding a group later (a Mapuche-
# or English-speaking area, say) means adding a key here and a matching branch
# in _language_group.
_AREA_TYPE_LABELS: dict[str, str] = {
    DEFAULT_AREA_TYPE_GROUP: "Todas las Áreas",
}

_AREA_TYPE_EXPECTATIONS_HEADER = ["Area_Type", "Metric", "Cadence", "Value"]


def is_builtin_area_type_label(label: str) -> bool:
    """True for a built-in group label (see _AREA_TYPE_LABELS). Anything else
    is a CUSTOM category a user added from Goals > Area Expectation Settings >
    "Add a custom expectation" — those stay fully supported, and are how a
    mission expresses a distinction this table does not model."""
    return label in _AREA_TYPE_LABELS.values()


@st.cache_data(ttl=300)
def get_all_area_type_indicators() -> list[dict]:
    """
    Every INDICATOR row currently in AREA_TYPE_EXPECTATIONS, in sheet
    order — the 4 built-in categories' default indicators PLUS any custom
    categories/indicators a user has added. Each:
    {"category":, "metric":, "cadence": "weekly"|"monthly", "value": float}.
    A row with an unrecognized/blank Cadence defaults to "weekly" rather
    than being dropped (a hand-edited sheet cell shouldn't silently vanish
    an indicator).

    Falls back to the 4 built-ins' default indicators when the tab is empty
    or unreachable.
    """
    df = read_tab(AREA_TYPE_EXPECTATIONS_TAB)
    # Require the FULL long-format header, not just "Area_Type" — that one
    # column name survived from the old 6-column-per-category schema too, so
    # checking it alone let a sheet still in that old shape slip past this
    # guard "non-empty," then silently lose every row a few lines down (each
    # row's Metric/Cadence/Value lookups all come back blank on an old-shape
    # sheet, and a blank Metric gets dropped) — the whole tab quietly
    # resolved to ZERO indicators instead of falling back to defaults. Bug
    # that shipped in 1ff536e, caught 2026-07-18 when Carson reported the
    # Area Expectation Settings page rendering almost nothing.
    if df.empty or not {"Area_Type", "Metric", "Cadence", "Value"} <= set(df.columns):
        return [
            {"category": _AREA_TYPE_LABELS[g], "metric": m, "cadence": c, "value": v}
            for g, indicators in _area_type_indicator_defaults().items()
            for m, c, v in indicators
        ]
    rows = []
    for _, row in df.iterrows():
        category = str(row.get("Area_Type", "")).strip()
        metric = str(row.get("Metric", "")).strip()
        if not category or not metric:
            continue
        cadence = str(row.get("Cadence", "")).strip().lower()
        if cadence not in ("weekly", "monthly"):
            cadence = "weekly"
        try:
            value = float(row.get("Value", 0) or 0)
        except (ValueError, TypeError):
            continue
        rows.append({"category": category, "metric": metric, "cadence": cadence, "value": value})
    return rows


def get_area_type_category_labels() -> list[str]:
    """Every category label currently present, built-ins first (in their
    fixed order) then custom ones in the order they first appear in the
    sheet — the order the Goals page renders sections in."""
    present: list[str] = []
    seen: set[str] = set()
    for ind in get_all_area_type_indicators():
        if ind["category"] not in seen:
            seen.add(ind["category"])
            present.append(ind["category"])
    ordered = [lbl for lbl in _AREA_TYPE_LABELS.values() if lbl in present]
    ordered += [lbl for lbl in present if lbl not in _AREA_TYPE_LABELS.values()]
    return ordered


@st.cache_data(ttl=300)
def _resolve_area_category(area: str) -> tuple[str, list[dict]]:
    """
    The category `area` resolves to — (label, its indicator rows). Match
    priority (Carson, 2026-07-18: categories are the backbone, "set one for
    a specific area if I need to" layers on top):
      1. EXACT-AREA OVERRIDE — a custom category whose label equals the
         area's own name (case-insensitive). Always wins, so "Provo" the
         override never leaks onto "Provo North" and vice versa.
      2. SUBSTRING custom category — the label matched case-insensitively
         as a substring against the area's MISSION_ORG Language_Type OR the
         area's own name (the same convention _language_group() already
         uses for Haitian/Creole/French-by-name, so typing "Japanese"
         catches areas with that Language_Type). First match in sheet
         order wins, using ALL of its indicators.
      3. The area's built-in language group (get_area_language_group).

    Cached BY AREA (Carson, 2026-07-21: Mission Goals was "super slow, not
    loading"): get_mission_monthly_expectation_total/get_mission_weekly_
    expectation_total call resolve_area_expectations() once per area PER
    METRIC, redoing this exact same roster-lookup-and-category-match for
    every area on every metric even though its result doesn't depend on
    metric at all. Profiled at ~8.5s for 200 areas x 25 metrics uncached
    (mostly repeated get_submitting_areas() calls + Streamlit's own cache-
    hit deep-copy overhead, called 5000 times instead of 200) — caching
    this one function turns every metric after the first into a per-area
    cache hit instead of a full re-resolution. Cleared wherever MISSION_ORG
    (roster/Language_Type) or AREA_TYPE_EXPECTATIONS (indicators) is
    written — see transfer_apply_service.apply() and
    save_area_type_expectations() below.
    """
    areas = get_submitting_areas()
    lang = ""
    roster_l: set[str] = set()
    if not areas.empty and "Area_Name" in areas.columns:
        names = areas["Area_Name"].astype(str).str.strip().str.lower()
        roster_l = set(names)
        if "Language_Type" in areas.columns:
            match = areas[names == str(area).strip().lower()]
            if not match.empty:
                lang = str(match.iloc[0].get("Language_Type", "") or "")

    by_category: dict[str, list[dict]] = {}
    for ind in get_all_area_type_indicators():
        by_category.setdefault(ind["category"], []).append(ind)

    lang_l = lang.lower()
    area_l = str(area or "").lower()
    area_norm = area_l.strip()
    for label, indicators in by_category.items():
        if is_builtin_area_type_label(label):
            continue
        if label.strip().lower() == area_norm:
            return label, indicators
    for label, indicators in by_category.items():
        if is_builtin_area_type_label(label):
            continue
        kw = label.strip().lower()
        # A label that IS a roster area's name is an exact-area override —
        # exact-only, never a substring keyword, or "Provo" the override
        # would leak onto "Provo North" through this pass.
        if kw in roster_l:
            continue
        if kw and (kw in lang_l or kw in area_l):
            return label, indicators

    group = get_area_language_group(area)
    # .get, not [ ]: a roster that names a language with no built-in group
    # (see _language_group) must fall back to the default group rather than
    # raising KeyError from a data value.
    builtin_label = _AREA_TYPE_LABELS.get(
        group, _AREA_TYPE_LABELS[DEFAULT_AREA_TYPE_GROUP])
    # No "or [defaults]" fallback here: get_all_area_type_indicators() already
    # bootstraps every built-in group's defaults together the one time the
    # whole tab is empty, so by this point a missing built-in label means the
    # Area Expectation Settings editor deliberately removed every one of that
    # category's rows — that must mean zero expectations for it, not a silent
    # reversion to the hardcoded defaults (bug found 2026-07-21: removing all
    # of a category's rows kept showing the mission fraction as if nothing had
    # been removed).
    indicators = by_category.get(builtin_label, [])
    return builtin_label, indicators


def resolve_area_expectations(area: str) -> dict[str, dict]:
    """
    One area's expectations, keyed by metric: {"cadence": "weekly"|
    "monthly", "value": float}. Resolution order (exact-area override,
    then substring custom category, then built-in language group) is
    _resolve_area_category's — see there.
    """
    _, indicators = _resolve_area_category(area)
    return {i["metric"]: {"cadence": i["cadence"], "value": i["value"]} for i in indicators}


def resolve_area_category_label(area: str) -> str:
    """The display label of the category `area` resolves to — a custom
    category's own label, or the built-in group's ("English", "Spanish",
    ...). Names the Breakdowns trend chart's expectation lines, so a graph
    mixing categories labels each line with the category that produced it
    (custom categories included, which get_area_language_group can't do)."""
    return _resolve_area_category(area)[0]


def get_area_expectation_entry(area: str, metric: str) -> dict | None:
    """
    One area's expectation for `metric` as {"cadence", "value", "weekly"},
    or None when the area's category defines no (or a zero) expectation for
    it. "weekly" is the FLOAT weekly pace — a monthly indicator converted
    via _AVG_WEEKS_PER_MONTH without rounding, because e.g. Gate's 1/month
    is ≈0.23/week and get_area_weekly_expectation's int rounding would
    collapse that to 0 (no line at all). Backs the Breakdowns trend chart's
    expectation lines, which draw for ANY metric with an expectation
    defined here (Carson, 2026-07-18) — not a fixed metric list.
    """
    entry = resolve_area_expectations(area).get(metric)
    if not entry:
        return None
    try:
        value = float(entry.get("value") or 0)
    except (ValueError, TypeError):
        return None
    if value <= 0:
        return None
    weekly = value / _AVG_WEEKS_PER_MONTH if entry["cadence"] == "monthly" else value
    return {"cadence": entry["cadence"], "value": value, "weekly": weekly}


def get_group_weekly_expectation_totals(area_names) -> dict[str, float]:
    """
    Sum of every area's get_area_expectation_entry(...)["weekly"] across
    `area_names`, per metric — {metric_key: weekly_total}, only metrics with
    a positive expectation somewhere in the group. Same "ANY metric with an
    expectation gets one" rule as the trend lines/get_area_expectation_entry
    — not a fixed metric list. Works for all three Breakdowns levels off the
    same `group_areas` set they already build (Zone/District: every area
    inside summed together; Area: the set-of-one).

    Deliberately NOT cached itself: the per-area resolution underneath
    (_resolve_area_category, cached ttl=300) is already cleared by
    save_area_type_expectations() on every edit, so recomputing the sum
    fresh here on each call means an edited/created/deleted expectation
    shows up on the very next rerun — no second cache to remember to
    invalidate.
    """
    totals: dict[str, float] = {}
    for area in area_names:
        for metric, entry in resolve_area_expectations(area).items():
            try:
                value = float(entry.get("value") or 0)
            except (ValueError, TypeError):
                continue
            if value <= 0:
                continue
            weekly = value / _AVG_WEEKS_PER_MONTH if entry.get("cadence") == "monthly" else value
            totals[metric] = totals.get(metric, 0.0) + weekly
    return totals


def save_area_type_expectations(indicators: list[dict]) -> str | None:
    """
    Persist ALL AREA_TYPE_EXPECTATIONS indicator rows — the 4 built-in
    categories' indicators PLUS any custom categories/indicators — back to
    the sheet in one batched overwrite_tab() call, the same clear-and-
    rewrite-cleanly convention SCORE_CONFIG uses (see _rewrite_score_config
    in pages/06_Puntajes.py), appropriate here too since this is a small,
    whole-table config tab, not append-only data.

    `indicators` is an ORDERED list of {"category":, "metric":, "cadence":,
    "value":} — same shape get_all_area_type_indicators() returns, so the
    Goals page can pass its edited (and possibly added-to/removed-from)
    copy straight back in. A row with a blank category or metric is
    dropped. The caller is responsible for keeping the 4 built-in
    categories' indicators present — this function just writes whatever
    it's given.

    Returns an error message string on failure, None on success. Clears
    get_all_area_type_indicators()'s cache so the Goals fractions,
    Breakdowns expectation lines, and the Scores page's Effort score all
    pick up the new numbers (built-in AND custom) on their next read — no
    other tab is touched.
    """
    body = [
        [i["category"], i["metric"], i.get("cadence", "weekly") or "weekly", i.get("value", 0)]
        for i in indicators
        if str(i.get("category", "")).strip() and str(i.get("metric", "")).strip()
    ]
    try:
        overwrite_tab(AREA_TYPE_EXPECTATIONS_TAB, [_AREA_TYPE_EXPECTATIONS_HEADER] + body)
    except Exception as e:
        return str(e)
    get_all_area_type_indicators.clear()
    # _resolve_area_category is cached PER AREA (2026-07-21 perf fix) on top
    # of get_all_area_type_indicators — clearing that alone isn't enough,
    # every area's already-resolved category+indicators would keep serving
    # the pre-save rows straight from its own cache.
    _resolve_area_category.clear()
    # Mission Goals' fraction denominators sum expectations across every
    # area inside their own 5-minute cache — without this clear a save
    # visibly moved the Area Goals fractions but left Mission Goals stale
    # for up to 5 minutes. (get_area_language_group needs no clear: it
    # reads the MISSION_ORG roster, not this tab. The Scores page's cached
    # Effort scores re-key themselves off these rows via _exp_fingerprint
    # in pages/06_Puntajes.py rather than needing a clear from here.)
    get_mission_weekly_expectation_total.clear()
    get_mission_monthly_expectation_total.clear()
    return None


@st.cache_data(ttl=300)
def get_score_component_weights(component: str, area_code: str = "ALL") -> dict[str, float]:
    """{metric_key: weight} for one SCORE_CONFIG component ('effort', 'skill',
    'ki'), for `area_code` falling back to the mission-wide 'ALL' rows.

    SCORE_CONFIG is the tab CCSM_AgentScores.gs reads to compute the scores it
    writes to SCORES, so reading it here is what keeps the dashboard's
    explanation of a score and the agent's calculation of it in agreement. A
    per-area row overrides the 'ALL' row for the same metric — the same
    precedence applySection1() uses in that agent.

    Section 1 of the tab is Area_Code | Metric_Key | Score_Component | Weight |
    Active, and a blank row separates it from section 2. Rows past that
    separator have a different meaning, so parsing stops there.
    """
    raw = read_tab("SCORE_CONFIG")
    if raw.empty:
        return {}

    want = str(component).strip().lower()
    rows = [[str(v).strip() for v in r] for r in raw.values.tolist()]

    weights: dict[str, float] = {}
    overrides: dict[str, float] = {}
    for row in rows:
        if not any(row):
            break                       # blank separator -> section 2 begins
        if len(row) < 5 or row[0] == "Area_Code":
            continue
        code, key, comp, weight, active = row[0], row[1], row[2], row[3], row[4]
        if comp.strip().lower() != want or not key:
            continue
        if active.strip().upper() == "FALSE":
            continue
        try:
            w = float(weight)
        except (TypeError, ValueError):
            continue
        if code.strip().upper() == "ALL":
            weights[key] = w
        elif code.strip().casefold() == str(area_code).strip().casefold():
            overrides[key] = w

    weights.update(overrides)
    return weights


#: An even split across the three components. Used only when SCORE_CONFIG has
#: no section-2 row at all — with nothing configured, the only defensible
#: statement is that Effort, Skill and KI count the same. Deliberately NOT any
#: particular mission's numbers: the previous default was Utah Provo's
#: 0.30/0.40/0.30, which silently reweighted every Effectiveness score this app
#: recomputed for CCSM (whose real row is 0.33/0.33/0.34).
_EVEN_COMPOSITION: dict[str, float] = {"effort": 1 / 3, "skill": 1 / 3, "ki": 1 / 3}


@st.cache_data(ttl=300)
def get_effectiveness_composition_weights(area_code: str = "ALL") -> dict[str, float]:
    """{effort, skill, ki} — how the three components combine into
    Effectiveness, from SCORE_CONFIG's SECOND section.

    That section sits below a blank separator row and is headed
    Area_Code | Effort_Weight | Skill_Weight | KI_Weight. It is the same row
    CCSM_AgentScores.gs reads, so honouring it is what keeps a recomputed
    Effectiveness score equal to the one the agent wrote to SCORES.

    A per-area row wins over the mission-wide 'ALL' row. Falls back to an even
    split when the section is missing or unparseable — never to a mission's
    hardcoded numbers.
    """
    raw = read_tab("SCORE_CONFIG")
    if raw.empty:
        return dict(_EVEN_COMPOSITION)

    rows = [[str(v).strip() for v in r] for r in raw.values.tolist()]

    # Skip section 1 entirely: stop at the first blank separator row.
    section2: list[list[str]] = []
    seen_blank = False
    for row in rows:
        if not any(row):
            seen_blank = True
            continue
        if seen_blank:
            section2.append(row)

    found: dict[str, dict[str, float]] = {}
    for row in section2:
        if len(row) < 4 or row[0] == "Area_Code":
            continue
        try:
            trio = {
                "effort": float(row[1]),
                "skill":  float(row[2]),
                "ki":     float(row[3]),
            }
        except (TypeError, ValueError):
            continue
        # A row of all zeroes cannot combine anything — treat it as absent
        # rather than dividing by zero downstream.
        if sum(trio.values()) <= 0:
            continue
        found[row[0].strip().casefold()] = trio

    for code in (str(area_code).strip().casefold(), "all"):
        if code in found:
            return found[code]
    return dict(_EVEN_COMPOSITION)


def _effort_metric_weights(area_code: str = "ALL") -> dict[str, float]:
    """Weights behind the Effort score.

    Was a hardcoded {nm_lessons: 30, new_found: 25, mmm_sent: 20, pew: 15,
    gate: 10} — Utah Provo's metrics, none of which CCSM collects. Every actual
    therefore resolved to None/NaN and this whole score computed as NaN for all
    98 areas: the Scores page's Effort breakdown rendered nothing at all, which
    reads as "no data yet" rather than as a broken calculation.

    CCSM's Effort component is defined in SCORE_CONFIG (contacts_attempted,
    roleplays, member_contacts, effort) and is what CCSM_AgentScores.gs actually
    uses. Reading the same source means the breakdown EXPLAINS the score the
    agent produced instead of computing a rival one.
    """
    return get_score_component_weights("effort", area_code)


def _scale_effort_metric(actual: float, expectation: float) -> float:
    """
    0-100 per-metric Effort score. Symmetric linear scale anchored so that
    exactly meeting expectation (100%) scores 75; the same slope runs both
    directions, capped to [0, 100] (100 is reached at 133.3% of
    expectation). An expectation of 0 always scores 100 — nothing was
    expected, so there's nothing to fall short of.
    """
    if expectation <= 0:
        return 100.0
    pct = actual / expectation * 100.0
    return max(0.0, min(100.0, pct * 0.75))


def compute_effort_score(
    actuals: dict[str, float | None], expectations: dict[str, float]
) -> float | None:
    """
    Weighted-average Effort score (0-100) over the metrics SCORE_CONFIG assigns
    to the 'effort' component — the same set and weights CCSM_AgentScores.gs
    uses, so this explains the agent's score rather than computing a rival one.

    actuals: metric_key -> actual value, or None if that metric's data source
    had no submission this week — that metric is excluded and the remaining
    weights renormalized.

    A metric with no weight in SCORE_CONFIG is skipped rather than raising: the
    tab is editable from the Scores page, so a metric can legitimately be
    dropped from scoring between one read and the next.

    Returns None when nothing is left to score, which callers must render as
    "no score" — never as zero. Zero is a real score meaning the area did
    nothing; None means we could not tell.
    """
    weights = _effort_metric_weights()
    present = {k: v for k, v in actuals.items()
               if v is not None and weights.get(k, 0) > 0}
    if not present:
        return None
    total_weight = sum(weights[k] for k in present)
    if total_weight <= 0:
        return None
    weighted_sum = sum(
        _scale_effort_metric(present[k], expectations.get(k, 0.0)) * weights[k]
        for k in present
    )
    return weighted_sum / total_weight


def compute_effort_score_breakdown(
    actuals: dict[str, float | None], expectations: dict[str, float]
) -> list[dict[str, float | str]]:
    """
    Per-metric breakdown behind compute_effort_score: one row per present
    metric (same None-exclusion rule) with its actual, expectation, weight,
    and weighted contribution toward the final score (these contributions
    sum to compute_effort_score's weighted_sum, before the total_weight
    normalization). Powers the Scores page's per-area Effort pie chart —
    "which of the things they're doing is actually moving the score."

    Weights come from SCORE_CONFIG, so this stays in step with
    compute_effort_score and with the agent that wrote the score.
    """
    weights = _effort_metric_weights()
    present = {k: v for k, v in actuals.items()
               if v is not None and weights.get(k, 0) > 0}
    rows = []
    for k, v in present.items():
        weight = weights[k]
        expectation = expectations.get(k, 0.0)
        scaled = _scale_effort_metric(v, expectation)
        rows.append({
            "metric":       k,
            "actual":       v,
            "expectation":  expectation,
            "weight":       weight,
            "scaled_score": scaled,
            "contribution": scaled * weight,
        })
    return rows


def get_area_effort_actuals_weekly(area: str, week_end_date: str) -> dict[str, float | None] | None:
    """
    Raw actuals for the metrics SCORE_CONFIG assigns to the Effort component,
    for one area + week. Single-row counterpart to
    compute_mission_president_effort_scores' batch merge; powers the Scores
    page's per-area Effort contribution chart.

    Effort metrics are NIGHTLY (contacts_attempted, roleplays, member_contacts,
    effort), so they are summed out of DAILY_LOG for that Mon-Sun week. They are
    deliberately NOT read from WEEKLY_KI: CCSM's WEEKLY_KI holds only the weekly
    form's ki_* pairs (see get_nightly_weekly_trends), so the previous version —
    which looked for nm_lessons/new_found/mmm_sent there and returned None when
    nm_lessons was absent — returned None for every area, every week.

    `effort` is a CHOICE metric (Todo / La mayor parte / Algo) rather than a
    count. It is scored by the agent through ccsmEffortScore() and has no
    numeric column to sum here, so it is reported as None (excluded, weights
    renormalized) instead of being coerced to a meaningless 0.

    Returns None when the area has no submissions at all that week — nothing to
    score, which the caller must render as "no score" rather than zero.
    """
    area = str(area).strip()
    week_end_date = str(week_end_date).strip()[:10]

    weights = _effort_metric_weights()
    if not weights:
        return None

    daily = get_daily_log(days=3650)
    if daily.empty or "Date" not in daily.columns or "Area" not in daily.columns:
        return None

    d = pd.to_datetime(daily["Date"], errors="coerce")
    week = (d + pd.to_timedelta(6 - d.dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")
    rows = daily[(daily["Area"].astype(str).str.strip() == area)
                 & (week == week_end_date)]
    if rows.empty:
        return None

    from app.config.metric_catalog import non_numeric_metrics
    non_numeric = non_numeric_metrics()

    actuals: dict[str, float | None] = {}
    for key in weights:
        # Consult QUESTIONS_CONFIG's Data_Type rather than inspecting values:
        # get_daily_log() runs every metric column through _num(), which
        # coerces "Todo" to NaN and then fills it with 0, so a CHOICE metric is
        # indistinguishable from a real zero by the time it reaches here.
        if key in non_numeric or key not in rows.columns:
            actuals[key] = None
            continue
        vals = pd.to_numeric(rows[key], errors="coerce")
        actuals[key] = float(vals.fillna(0).sum())

    if all(v is None for v in actuals.values()):
        return None
    return actuals


def _mp_weeks_in_month(day: date) -> float:
    """
    Number of 7-day weeks in the calendar month containing `day`, e.g.
    31/7 ≈ 4.43 for a 31-day month, 4.0 for a 28-day February. Same
    monthly-to-weekly conversion pages/02_Metas.py uses for its Goal
    fractions (_weeks_in_month there).
    """
    month_start = day.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (next_month - month_start).days / 7


def get_area_effort_expectations_weekly(area: str, week_end_date: str) -> dict[str, float]:
    """
    This area's weekly Effort expectations for the 5 Effort metrics
    (nm_lessons, new_found, mmm_sent, pew, gate), from
    resolve_area_expectations() (custom categories first, then the area's
    built-in language group). Any indicator whose stored cadence is MONTHLY
    (gate, by default — but now editable per-indicator, Carson 2026-07-18)
    is prorated using the EXACT number of weeks in week_end_date's calendar
    month (more precise than get_area_weekly_expectation's average-month
    fallback, since a real date is available here). A metric this area's
    category doesn't define at all defaults to 0 rather than crashing —
    custom categories aren't required to define all 5 Effort metrics.
    """
    exp = resolve_area_expectations(area)
    day = datetime.strptime(str(week_end_date)[:10], "%Y-%m-%d").date()
    weeks = _mp_weeks_in_month(day)
    result = {}
    # Keys come from SCORE_CONFIG's effort component, not a fixed tuple of
    # Provo's five. A metric with no expectation defined defaults to 0, which
    # _scale_effort_metric treats as "nothing was expected, so nothing was
    # fallen short of" — a full score rather than a divide-by-zero.
    for key in _effort_metric_weights():
        entry = exp.get(key)
        if not entry:
            result[key] = 0.0
            continue
        v = entry["value"]
        result[key] = (v / weeks if weeks else v) if entry["cadence"] == "monthly" else v
    return result


def compute_mission_president_effort_scores(scores_df: pd.DataFrame) -> pd.Series:
    """
    New Effort_Score for every row of `scores_df` (needs Area_Name and
    Week_Ending_Date columns), per the mission president's fixed weekly
    expectations (docs/superpowers/specs/2026-07-17-effort-score-rework-
    design.md). Returns a float Series aligned to scores_df's index; a row
    whose actuals can't be resolved (e.g. no matching WEEKLY_KI week for
    that area) is NaN — callers should fall back to the row's original
    Effort_Score for those.
    """
    if scores_df.empty:
        return pd.Series(dtype=float)

    weights = _effort_metric_weights()
    if not weights:
        return pd.Series([float("nan")] * len(scores_df), index=scores_df.index, dtype=float)

    base = scores_df[["Area_Name", "Week_Ending_Date"]].copy()
    base["Area_Name"] = base["Area_Name"].astype(str).str.strip()
    base["Week_Ending_Date"] = base["Week_Ending_Date"].astype(str).str.strip().str[:10]

    # Effort metrics are NIGHTLY, so they roll up from DAILY_LOG by week. The
    # previous version merged nm_lessons/new_found/mmm_sent from WEEKLY_KI and
    # pew/gate from the weekly form — Provo's five. CCSM's WEEKLY_KI holds only
    # the weekly form's ki_* pairs, so the merge contributed nothing, the
    # `if pd.isna(r["nm_lessons"])` guard fired on every row, and this returned
    # NaN for all 98 areas: the Effort column and its breakdown showed nothing,
    # which reads as "no data yet" rather than as a broken calculation.
    weekly = get_nightly_weekly_trends_by_area(n_weeks=520)
    metric_keys = list(weights)
    if not weekly.empty:
        weekly = weekly.rename(
            columns={"area": "Area_Name", "week_end_date": "Week_Ending_Date"})
        weekly["Area_Name"] = weekly["Area_Name"].astype(str).str.strip()
        keep = ["Area_Name", "Week_Ending_Date"] + [
            k for k in metric_keys if k in weekly.columns]
        base = base.merge(weekly[keep], on=["Area_Name", "Week_Ending_Date"], how="left")
    for col in metric_keys:
        if col not in base.columns:
            base[col] = float("nan")

    base.index = scores_df.index
    scores = []
    for _idx, r in base.iterrows():
        actuals = {
            k: (float(r[k]) if pd.notna(r[k]) else None) for k in metric_keys
        }
        if all(v is None for v in actuals.values()):
            scores.append(float("nan"))       # no submissions that week
            continue
        expectations = get_area_effort_expectations_weekly(
            r["Area_Name"], r["Week_Ending_Date"])
        score = compute_effort_score(actuals, expectations)
        scores.append(score if score is not None else float("nan"))

    return pd.Series(scores, index=scores_df.index, dtype=float)


_REC_STRETCH_SETTING_KEY = "rec_stretch_pct"
_REC_STRETCH_DEFAULT_PCT = 10


def get_rec_stretch_pct() -> int:
    """The REC-badge "nudge" percentage (Goal Settings page, Recommended Goal
    Nudge control) — how far above an area's/mission's own average history
    every REC badge on Area Goals + Mission Goals recommends, in whole
    percentage points (0, 10, 20, ... — steps of 10, no other value should be
    written). Backed by APP_SETTINGS via get_app_setting(); defaults to 10
    (the original hardcoded behavior) if unset or unparseable. NOT read by
    any docs/*.gs agent — purely a Streamlit-side REC-pill calculation."""
    from app.db.goals_queries import get_app_setting
    raw = get_app_setting(_REC_STRETCH_SETTING_KEY, str(_REC_STRETCH_DEFAULT_PCT))
    try:
        return int(float(raw))
    except (ValueError, TypeError):
        return _REC_STRETCH_DEFAULT_PCT


def _rec_stretch_factor() -> float:
    """1 + nudge% as a multiplier, e.g. 10% -> 1.10, 0% -> 1.00."""
    return 1.0 + get_rec_stretch_pct() / 100.0


def _stretch_recommendation(df: pd.DataFrame, keys: list, area: str | None) -> dict:
    """
    Shared REC-badge math for both get_recommended_goals(area) and
    get_mission_recommended_goals(): a light STRETCH goal sitting just above
    the long-run average, so it pushes missionaries to be slightly better.
    Averages EVERY completed week available (full history — all transfers,
    not just a recent window) and recommends ceil(mean * stretch_factor),
    where stretch_factor is 1 + the Goal Settings "nudge" percentage / 100
    (see _rec_stretch_factor() — defaults to 1.10, i.e. 10%, until changed).
    The in-progress current week is always excluded so a partial week
    doesn't drag the average down. Every returned value is floored at 1.

    area=<name>: filters to that area's own rows first (per-area basis, used
    by get_recommended_goals).
    area=None: sums EVERY area's rows together per week FIRST (mission-wide
    weekly totals), then averages those — i.e. the mission's own aggregate
    performance across all areas, not a sum of each area's individual REC
    (which would double up each area's independent rounding). Used by
    get_mission_recommended_goals().
    """
    out = {}
    if df.empty or "area" not in df.columns:
        return out
    if area is not None:
        # Whitespace-tolerant area match — WEEKLY_KI/WEEKLY_FORM_RAW area names
        # can carry stray spaces vs. the MISSION_ORG Area_Name used in the picker.
        sub = df[df["area"].astype(str).str.strip() == str(area).strip()].copy()
    else:
        sub = df.copy()
    if sub.empty:
        return out
    if "week_end_date" in sub.columns:
        sub = exclude_current_week(sub)
        if area is None:
            numeric_cols = [k for k in keys if k in sub.columns]
            if not numeric_cols:
                return out
            sub = sub.groupby("week_end_date")[numeric_cols].sum(min_count=1).reset_index()
        sub = sub.sort_values("week_end_date")
    stretch = _rec_stretch_factor()
    for key in keys:
        if key in sub.columns:
            vals = pd.to_numeric(sub[key], errors="coerce").dropna()
            if not vals.empty:
                out[key] = max(1, math.ceil(vals.mean() * stretch))
    return out


def _goalable_weekly_keys(metric_defs: list) -> list:
    """Weekly-form metrics a goal can sensibly be recommended for.

    Was `f == "WEEKLY" and k != "rc_total"` in three places — rc_total is
    Provo's running recent-convert headcount, a number no goal applies to.
    CCSM has no such key, so all three exclusions excluded nothing, and the two
    kinds of weekly key CCSM DOES have that no goal applies to were let
    straight through:

      * `_meta` keys are the companionship's own weekly goal, captured on the
        form beside each `_real` achievement. Recommending a goal for one means
        recommending a goal for a goal, and the recommendation is computed from
        the history of that field — i.e. from what areas have previously aimed
        at, not from what they achieved.
      * CHOICE metrics carry no summable number to average.
    """
    from app.config.metric_catalog import metric_data_type

    return [
        k for k, _, f in metric_defs
        if f == "WEEKLY" and not k.endswith("_meta")
        and metric_data_type(k) != "CHOICE"
    ]


@st.cache_data(ttl=300)
def get_recommended_goals(area: str) -> dict:
    """
    Recommended goal per metric for `area`, based on the AREA'S OWN performance —
    not a language peer group. See _stretch_recommendation() for the formula.

    - NIGHTLY (daily) metrics — source WEEKLY_KI.
    - WEEKLY / transfer metrics — source WEEKLY_FORM_RAW. The stored goal stays
      weekly; the Goals page projects it over the 6-week transfer for display.

    Weekly keys that no goal applies to are excluded — see
    _goalable_weekly_keys().

    Using full history rather than a recent window trades away the recent-weeks
    seasonality self-correction (e.g. a BYU/YSA summer dip no longer pulls the rec
    down on its own), by deliberate choice.

    Every NIGHTLY metric always gets a recommendation of at least 1, even with no
    data. WEEKLY / transfer metrics only get one when the area has data for them.
    Every returned value is floored at 1.
    """
    metric_defs = get_question_metrics()
    nightly_keys = [k for k, _, f in metric_defs if f == "NIGHTLY"]
    weekly_keys = _goalable_weekly_keys(metric_defs)

    recommended = {}
    recommended.update(_stretch_recommendation(get_weekly_ki(), nightly_keys, area))
    recommended.update(_stretch_recommendation(get_weekly_form_data(), weekly_keys, area))

    # Every nightly (daily) metric always shows at least 1.
    for key in nightly_keys:
        recommended[key] = max(1, recommended.get(key, 0))

    return recommended


def _stretch_recommendation_monthly(df: pd.DataFrame, keys: list, area: str) -> dict:
    """
    Monthly counterpart to _stretch_recommendation(): buckets every weekly
    row into the CALENDAR MONTH its week_end_date falls in, sums each
    metric within that month to get an actual monthly total, then
    recommends ceil(mean-of-completed-months * stretch_factor) — the same
    Goal Settings "nudge" stretch (see _rec_stretch_factor(), defaults to
    1.10/10%), but averaged over the area's own real monthly totals instead
    of a weekly average scaled up by a fixed weeks-per-month factor. The
    current, still-in-progress calendar month is always excluded so a
    partial month doesn't drag the average down. Every returned value is
    floored at 1.
    """
    out = {}
    if df.empty or "area" not in df.columns or "week_end_date" not in df.columns:
        return out
    sub = df[df["area"].astype(str).str.strip() == str(area).strip()].copy()
    if sub.empty:
        return out
    week_dates = pd.to_datetime(sub["week_end_date"], errors="coerce")
    sub = sub[week_dates.notna()].copy()
    week_dates = week_dates[week_dates.notna()]
    if sub.empty:
        return out
    sub["_month"] = week_dates.dt.strftime("%Y-%m")
    current_month = datetime.today().strftime("%Y-%m")
    sub = sub[sub["_month"] != current_month]
    if sub.empty:
        return out
    numeric_cols = [k for k in keys if k in sub.columns]
    if not numeric_cols:
        return out
    monthly = sub.groupby("_month")[numeric_cols].sum(min_count=1).reset_index()
    stretch = _rec_stretch_factor()
    for key in keys:
        if key in monthly.columns:
            vals = pd.to_numeric(monthly[key], errors="coerce").dropna()
            if not vals.empty:
                out[key] = max(1, math.ceil(vals.mean() * stretch))
    return out


@st.cache_data(ttl=300)
def get_recommended_monthly_goals(area: str) -> dict:
    """
    Recommended MONTHLY goal per metric for `area` — the Monthly Goals
    counterpart to get_recommended_goals(). Same ~10% stretch, but computed
    from the area's own real CALENDAR-MONTH totals (every completed month's
    weekly rows summed together, then averaged across full history) instead
    of a single weekly average projected up by a fixed weeks-per-month
    factor. See _stretch_recommendation_monthly() for the formula.

    EVERY metric — NIGHTLY or WEEKLY/transfer (Gate, Date, Pew, Renew
    included) — always gets a recommendation of at least 1, even with zero
    recorded history for that area (e.g. a newly-assigned area), so a REC
    badge is guaranteed to show on every Monthly Goals box for every area.

    An area whose ENTIRE history so far falls inside the current,
    in-progress calendar month (e.g. a newly-assigned area, or simply early
    in the month before any prior month's data exists) has no completed
    month to average — _stretch_recommendation_monthly() returns nothing
    for it, which would otherwise make its REC badge vanish. Falls back to
    the plain WEEKLY stretch average (_stretch_recommendation, full weekly
    history) scaled up by this month's real length for exactly those keys,
    so a badge is always shown once the area has ANY history at all.
    """
    metric_defs = get_question_metrics()
    nightly_keys = [k for k, _, f in metric_defs if f == "NIGHTLY"]
    weekly_keys = _goalable_weekly_keys(metric_defs)

    recommended = {}
    recommended.update(_stretch_recommendation_monthly(get_weekly_ki(), nightly_keys, area))
    recommended.update(_stretch_recommendation_monthly(get_weekly_form_data(), weekly_keys, area))

    missing = [k for k in nightly_keys + weekly_keys if k not in recommended]
    if missing:
        weekly_fallback = {}
        weekly_fallback.update(_stretch_recommendation(get_weekly_ki(), missing, area))
        weekly_fallback.update(_stretch_recommendation(get_weekly_form_data(), missing, area))
        if weekly_fallback:
            month_start = date.today().replace(day=1)
            next_month = date(
                month_start.year + (month_start.month == 12),
                month_start.month % 12 + 1,
                1,
            )
            weeks_in_month = (next_month - month_start).days / 7
            for key, val in weekly_fallback.items():
                recommended[key] = max(1, math.ceil(val * weeks_in_month))

    for key in nightly_keys + weekly_keys:
        recommended[key] = max(1, recommended.get(key, 0))

    return recommended


@st.cache_data(ttl=300)
def get_mission_recommended_goals() -> dict:
    """
    Recommended goal per metric, mission-wide: same +10% stretch formula as
    get_recommended_goals(), but based on the WHOLE MISSION'S own performance
    (every area's weeks summed together first, then averaged over full
    history) rather than any single area. Keyed by the same raw metric keys
    as get_recommended_goals (e.g. "gate", "renew", "nm_lessons") — the Goals
    page's Mission Goals tab translates its GOAL_LABELS keys (e.g. "baptisms")
    to these via GOAL_TO_ACTUAL before looking up a REC value.
    """
    metric_defs = get_question_metrics()
    nightly_keys = [k for k, _, f in metric_defs if f == "NIGHTLY"]
    weekly_keys = _goalable_weekly_keys(metric_defs)

    recommended = {}
    recommended.update(_stretch_recommendation(get_weekly_ki(), nightly_keys, None))
    recommended.update(_stretch_recommendation(get_weekly_form_data(), weekly_keys, None))

    for key in nightly_keys:
        recommended[key] = max(1, recommended.get(key, 0))

    return recommended


# ══════════════════════════════════════════════════════════════════════════════
# NOTES (read/write to NOTES tab in COMPASS_CCSM)
# ══════════════════════════════════════════════════════════════════════════════

_NOTES_HEADER = [
    "note_id", "created_at", "created_by", "content", "tags",
    "zone", "district", "area", "follow_up_date",
    "visible_to", "resolved", "updated_at",
]


def _ensure_notes_header() -> None:
    """Write the header row if NOTES tab is empty."""
    df = read_tab("NOTES")
    if df.empty:
        from app.db.sheets_client import _get_spreadsheet
        ws = _get_spreadsheet().worksheet("NOTES")
        if ws.row_count == 0 or not ws.row_values(1):
            ws.append_row(_NOTES_HEADER)


def get_notes(user_email: str = None, show_resolved: bool = False) -> pd.DataFrame:
    """
    Return notes visible to user_email.
    visible_to is a comma-separated list of emails, or 'all'.
    """
    df = read_tab("NOTES")
    if df.empty:
        return pd.DataFrame(columns=_NOTES_HEADER)

    if not show_resolved and "resolved" in df.columns:
        df = df[df["resolved"].astype(str).str.upper() != "TRUE"].copy()

    if user_email:
        email_lower = user_email.lower().strip()

        def _visible(row):
            vt = str(row.get("visible_to", "all")).lower().strip()
            return vt == "all" or email_lower in [e.strip() for e in vt.split(",")]

        df = df[df.apply(_visible, axis=1)].copy()

    return df


def get_due_follow_ups(user_email: str = None) -> pd.DataFrame:
    """Notes with a follow_up_date <= today that are not yet resolved."""
    df = get_notes(user_email=user_email, show_resolved=False)
    if df.empty or "follow_up_date" not in df.columns:
        return pd.DataFrame(columns=_NOTES_HEADER)
    today = datetime.today().strftime("%Y-%m-%d")
    df["follow_up_date"] = df["follow_up_date"].astype(str)
    return df[(df["follow_up_date"] != "") & (df["follow_up_date"] <= today)].copy()


def create_note(
    created_by: str,
    content: str,
    tags: str = "",
    zone: str = "",
    district: str = "",
    area: str = "",
    follow_up_date: str = "",
    visible_to: str = "all",
) -> None:
    _ensure_notes_header()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    row = [
        str(uuid.uuid4()),
        now,
        created_by,
        content,
        tags,
        zone,
        district,
        area,
        follow_up_date,
        visible_to,
        "FALSE",
        now,
    ]
    append_row("NOTES", row)


def update_note(note_id: str, **kwargs) -> None:
    """Update fields on an existing note by note_id."""
    df = read_tab("NOTES")
    if df.empty or "note_id" not in df.columns:
        return
    idx = df.index[df["note_id"] == note_id].tolist()
    if not idx:
        return
    row_s = df.loc[idx[0]].copy()
    for k, v in kwargs.items():
        if k in row_s.index:
            row_s[k] = v
    row_s["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    update_row("NOTES", idx[0] + 2, row_s.reindex(_NOTES_HEADER).tolist())


def resolve_note(note_id: str, resolved: bool = True) -> None:
    update_note(note_id, resolved="TRUE" if resolved else "FALSE")


def delete_note(note_id: str) -> None:
    df = read_tab("NOTES")
    if df.empty or "note_id" not in df.columns:
        return
    idx = df.index[df["note_id"] == note_id].tolist()
    if not idx:
        return
    delete_row("NOTES", idx[0] + 2)


# ══════════════════════════════════════════════════════════════════════════════
# SUGGESTIONS / QUESTIONS triage
#
# The "SUGGESTIONS" tab is the Google Form's linked RESPONSE sheet and must be
# treated as READ-ONLY. It is polluted by two non-form sources:
#   1. Other forms (nightly/weekly) whose submissions AgentQA's onFormSubmit
#      trigger historically appended here — these carry a ZONE NAME in col 1.
#   2. AgentQA's own duplicate copy of each real Q/S submission (a second row
#      with the same name/email/message as the native form row).
# So we only treat a row as REAL when col 1 contains 'suggestion' or 'question'
# (the form's selector), and we DEDUPE by submission content (email + message)
# to collapse the native row and AgentQA's duplicate. Columns are read BY
# POSITION (header labels are unreliable):
#   0 Timestamp | 1 selector | 2-4 Suggestion section | 5-7 Question section
#
# Triage state lives in a SEPARATE tab, SUGGESTIONS_REVIEW, keyed by a stable
# content hash of the submission. We NEVER write to the form response sheet. The
# review row snapshots the submission so the email bridge is self-contained.
# ══════════════════════════════════════════════════════════════════════════════

_REVIEW_TAB = "SUGGESTIONS_REVIEW"
_REVIEW_HEADER = [
    "Key", "Kind", "Name", "Email", "Message",
    "Status", "ReviewedBy", "ReviewedAt", "ReviewerNote", "EmailedToCompass",
]
_SUGGESTIONS_COLS = [
    "Key", "Timestamp", "Kind", "Name", "Email", "Message",
    "Status", "ReviewedBy", "ReviewedAt", "ReviewerNote",
]


def _parse_form_suggestions() -> list:
    """
    Read the form response sheet by position and return one dict per real,
    DEDUPED Q/S submission. A row is real only when col 1 contains 'suggestion'
    or 'question' (excludes nightly-form zone rows). Native form rows and
    AgentQA's duplicate copies of the same submission collapse to one entry via
    a content hash of email+message. Keys: Key, Timestamp, Kind
    ('Suggestion'/'Question'), Name, Email, Message.
    """
    rows = read_values("SUGGESTIONS")
    seen = set()
    out = []
    for r in rows[1:]:  # skip header row
        def cell(i):
            return str(r[i]).strip() if i < len(r) and r[i] is not None else ""
        selector = cell(1).lower()
        is_q = "question" in selector
        is_s = "suggestion" in selector
        if not (is_q or is_s):
            continue  # not a real Q/S submission (e.g. nightly-form zone row)
        kind = "Question" if is_q else "Suggestion"
        # Data sits in the suggestion section (2-4) or the question section (5-7).
        name    = cell(2) or cell(5)
        email   = cell(3) or cell(6)
        message = cell(4) or cell(7)
        if not (name or email or message):
            continue
        basis = (email.lower() or name.lower()) + "|" + message.lower()
        key = hashlib.md5(basis.encode("utf-8")).hexdigest()[:16]
        if key in seen:
            continue  # collapse native row + AgentQA duplicate
        seen.add(key)
        out.append({
            "Key": key, "Timestamp": cell(0), "Kind": kind,
            "Name": name, "Email": email, "Message": message,
        })
    return out


def _read_review() -> dict:
    """Return {Key: {Status, ReviewedBy, ReviewedAt, ReviewerNote,
    EmailedToCompass}} from the SUGGESTIONS_REVIEW tab."""
    df = read_tab(_REVIEW_TAB)
    reviews = {}
    if not df.empty and "Key" in df.columns:
        for _, row in df.iterrows():
            k = str(row.get("Key", "")).strip()
            if not k:
                continue
            reviews[k] = {
                "Status": (str(row.get("Status", "") or "").strip() or "Pending"),
                "ReviewedBy": str(row.get("ReviewedBy", "") or "").strip(),
                "ReviewedAt": str(row.get("ReviewedAt", "") or "").strip(),
                "ReviewerNote": str(row.get("ReviewerNote", "") or "").strip(),
                "EmailedToCompass": str(row.get("EmailedToCompass", "") or "").strip(),
            }
    return reviews


def get_suggestions(
    status: str = None,
    type_filter: str = None,
    search: str = None,
) -> pd.DataFrame:
    """
    Unified triage list: every real form submission joined with its review
    state (default 'Pending'). Filters: status ('Pending'/'Accepted'/'Rejected'/
    'All'), type_filter ('Suggestion'/'Question'/'All'), and a case-insensitive
    search over Name + Message.
    """
    subs = _parse_form_suggestions()
    if not subs:
        return pd.DataFrame(columns=_SUGGESTIONS_COLS)
    reviews = _read_review()
    records = []
    for s in subs:
        rv = reviews.get(s["Key"], {})
        records.append({
            **s,
            "Status": rv.get("Status", "Pending"),
            "ReviewedBy": rv.get("ReviewedBy", ""),
            "ReviewedAt": rv.get("ReviewedAt", ""),
            "ReviewerNote": rv.get("ReviewerNote", ""),
        })
    df = pd.DataFrame(records, columns=_SUGGESTIONS_COLS)
    df["Status"] = df["Status"].replace("Implemented", "Done")

    if status and status != "All":
        df = df[df["Status"] == status]
    if type_filter and type_filter != "All":
        df = df[df["Kind"].astype(str).str.lower() == type_filter.lower()]
    if search:
        s = search.lower()
        df = df[df.apply(
            lambda r: s in str(r["Message"]).lower() or s in str(r["Name"]).lower(),
            axis=1,
        )]
    return df


def set_suggestion_status(
    key: str,
    status: str,
    reviewer: str,
    note: str = "",
    kind: str = "",
    name: str = "",
    email: str = "",
    message: str = "",
) -> None:
    """
    Upsert a submission's triage state in SUGGESTIONS_REVIEW, keyed by `key`
    (the submission Timestamp). NEVER writes to the form response sheet. The
    snapshot fields (kind/name/email/message) make the review row self-contained
    for the email bridge. EmailedToCompass is preserved (owned by the bridge).
    """
    key = str(key).strip()
    if not key:
        return
    df = read_tab(_REVIEW_TAB)
    rows_by_key = {}
    if not df.empty and "Key" in df.columns:
        for _, row in df.iterrows():
            k = str(row.get("Key", "")).strip()
            if k:
                rows_by_key[k] = {c: str(row.get(c, "") or "") for c in _REVIEW_HEADER}

    existing = rows_by_key.get(key, {})
    rows_by_key[key] = {
        "Key": key,
        "Kind": kind or existing.get("Kind", ""),
        "Name": name or existing.get("Name", ""),
        "Email": email or existing.get("Email", ""),
        "Message": message or existing.get("Message", ""),
        "Status": status,
        "ReviewedBy": reviewer,
        "ReviewedAt": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        "ReviewerNote": note,
        "EmailedToCompass": existing.get("EmailedToCompass", ""),
    }
    body = [[rows_by_key[k].get(c, "") for c in _REVIEW_HEADER] for k in rows_by_key]
    overwrite_tab(_REVIEW_TAB, [_REVIEW_HEADER] + body)


# get_miracles() was here. It read a tab called "Miracles" — a Google Form
# response sheet Utah Provo has and COMPASS_CCSM does not. CCSM never adopted
# the miracle form (docs/superpowers/specs/2026-07-11-ccsm-sheet-and-agents-
# design.md cuts the miracle-form utilities; the dashboard design doc cuts the
# Miracles tab for the same reason), so the only page that called this was
# deleted before launch and tests/test_isolation.py::test_miracles_removed
# keeps it deleted.
#
# Removed rather than left in place: read_tab() returns an empty DataFrame for
# a tab that does not exist, so this function was a working-looking accessor
# that could only ever return nothing — precisely the shape of dead Provo
# plumbing this app has been cleared of. If CCSM ever adds a miracles form,
# add the reader back against the tab that then exists.


@st.cache_data(ttl=300)
def get_blitz_dates(area: str = None):
    """
    Returns blitz dates from DAILY_LOG Is_Blitz column.

    With area=None: returns {area_name: set[YYYY-MM-DD]} for all areas.
    With area="Provo 1": returns set[YYYY-MM-DD] for that area (empty set if none).
    """
    df = read_tab("DAILY_LOG")
    empty = {} if area is None else set()
    if df.empty or "Is_Blitz" not in df.columns or "Area" not in df.columns or "Date" not in df.columns:
        return empty

    blitz_df = df[df["Is_Blitz"].astype(str).str.strip().str.upper() == "TRUE"]

    if area is not None:
        area_df = blitz_df[blitz_df["Area"].astype(str).str.strip() == area.strip()]
        return {d for d in area_df["Date"].astype(str).str.strip().tolist() if d and d.lower() != "nan"}

    result = {}
    for _, row in blitz_df.iterrows():
        a = str(row["Area"]).strip()
        d = str(row["Date"]).strip()
        if a and d and d.lower() != "nan":
            result.setdefault(a, set()).add(d)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# TABLEAU PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════

def get_tableau_detail() -> tuple:
    """
    Load persisted Finding Detail CSV from COMPASS_CCSM.
    Returns (df, uploaded_by, uploaded_at) or (empty_df, '', '').
    Row 1 is metadata, row 2 is the real header.
    """
    df = read_tab("TABLEAU_DETAIL")
    if df.empty or len(df) < 2:
        return pd.DataFrame(), "", ""
    meta_row = df.iloc[0]
    by_val = str(meta_row.iloc[0]) if len(meta_row) > 0 else ""
    at_val = str(meta_row.iloc[1]) if len(meta_row) > 1 else ""
    uploaded_by = by_val.replace("_uploaded_by:", "") if "_uploaded_by:" in by_val else ""
    uploaded_at = at_val.replace("_uploaded_at:", "") if "_uploaded_at:" in at_val else ""
    real_df = df.iloc[1:].copy()
    real_df.columns = df.columns
    real_df = real_df.reset_index(drop=True)
    return real_df, uploaded_by, uploaded_at


def get_tableau_ranking() -> tuple:
    """
    Load persisted Finding Ranking CSV from COMPASS_CCSM.
    Returns (df, uploaded_by, uploaded_at) or (empty_df, '', '').
    """
    df = read_tab("TABLEAU_RANKING")
    if df.empty or len(df) < 2:
        return pd.DataFrame(), "", ""
    meta_row = df.iloc[0]
    by_val = str(meta_row.iloc[0]) if len(meta_row) > 0 else ""
    at_val = str(meta_row.iloc[1]) if len(meta_row) > 1 else ""
    uploaded_by = by_val.replace("_uploaded_by:", "") if "_uploaded_by:" in by_val else ""
    uploaded_at = at_val.replace("_uploaded_at:", "") if "_uploaded_at:" in at_val else ""
    real_df = df.iloc[1:].copy()
    real_df.columns = df.columns
    real_df = real_df.reset_index(drop=True)
    return real_df, uploaded_by, uploaded_at


def get_baptisms_actual(month_start: str) -> int | None:
    """
    Mission-wide baptisms actually performed in the given month, from
    TABLEAU_BAPTISMS (referral_system/baptisms_capture.py, run daily). This is
    the real "Total People Baptized" KPI read off the Mission Finding Summary
    Tableau view — NOT the weekly-form "gate" field, which under-counts badly
    (verified: ~18-20 vs an official 41 for one month) since missionaries often
    don't fill it in reliably.

    month_start: 'YYYY-MM-DD' (first of the month, as used elsewhere in
    goals_queries.py). Returns None if no capture has run for that month yet
    (e.g. before this feature existed, or the scheduled job hasn't caught up) —
    callers should fall back to the gate proxy in that case.
    """
    df = read_tab("TABLEAU_BAPTISMS")
    if df.empty or "month" not in df.columns:
        return None
    month_key = str(month_start)[:7]  # 'YYYY-MM'
    match = df[(df["zone"] == "MISSION") & (df["month"].astype(str) == month_key)]
    if match.empty:
        return None
    try:
        return int(float(match.iloc[-1]["baptisms"]))
    except (ValueError, TypeError):
        return None


def get_baptisms_since_launch(start_date: str) -> int:
    """
    Total real mission-wide baptisms (get_baptisms_actual, the Tableau-sourced
    count) summed over every calendar month from start_date through the
    current month. A month with no capture yet (e.g. the in-progress current
    month before today's sync) contributes 0, never crashes.
    """
    start = date.fromisoformat(str(start_date)[:10])
    today = date.today()
    total = 0
    y, m = start.year, start.month
    while (y, m) <= (today.year, today.month):
        val = get_baptisms_actual(f"{y:04d}-{m:02d}-01")
        if val:
            total += val
        m += 1
        if m > 12:
            m = 1
            y += 1
    return total


def get_tableau_daterange() -> tuple:
    """Return the (start, end) ISO date strings the Tableau export was run for,
    read from the '_range:START|END' marker the scraper stamps into the metadata
    row. Returns ('', '') if not present (e.g. an older manual upload)."""
    for tab in ("TABLEAU_DETAIL", "TABLEAU_RANKING"):
        df = read_tab(tab)
        if df.empty:
            continue
        meta_row = df.iloc[0]
        for cell in meta_row.astype(str):
            if cell.startswith("_range:"):
                payload = cell.replace("_range:", "", 1)
                if "|" in payload:
                    start, end = payload.split("|", 1)
                    start, end = start.strip(), end.strip()
                    if start and end and start.lower() != "none":
                        return start, end
    return "", ""


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def detect_anomalies(metric_key: str, threshold: float = 0.70) -> pd.DataFrame:
    """
    Flag areas where the latest week < threshold × 4-week baseline.
    Returns DataFrame: area, zone, district, this_week, avg_4wk, pct_change, severity.
    """
    df = get_weekly_ki()
    if df.empty or metric_key not in df.columns:
        return pd.DataFrame()

    recent = df.sort_values("week_end_date").groupby("area").tail(5)
    results = []
    for area, grp in recent.groupby("area"):
        grp = grp.sort_values("week_end_date")
        if len(grp) < 2:
            continue
        latest = float(grp.iloc[-1][metric_key])
        baseline = float(grp.iloc[:-1][metric_key].mean())
        if baseline == 0:
            continue
        pct = latest / baseline
        if pct < threshold:
            row = grp.iloc[-1]
            results.append({
                "area":       area,
                "zone":       row.get("zone", ""),
                "district":   row.get("district", ""),
                "this_week":  latest,
                "avg_4wk":    round(baseline, 1),
                "pct_change": round((pct - 1) * 100, 1),
                "severity":   "High" if pct < 0.5 else "Medium",
            })
    return pd.DataFrame(results)


# Weekly-form metrics live in WEEKLY_FORM_RAW (get_weekly_ki_totals), not in
# the nightly-form rollups (get_weekly_ki_trends). Route projections accordingly.
#
# Read from QUESTIONS_CONFIG rather than hardcoded: the old
# {"pew","date_metric","gate","renew","rc_total"} was Provo's set, so for CCSM
# every weekly metric fell through to the NIGHTLY branch and projected off a
# series that has no such column — yielding a confident-looking projection of
# nothing. Routing a projection to the wrong source is worse than refusing one.
def _weekly_form_metric_keys() -> set:
    from app.config.metric_catalog import weekly_metric_keys
    return set(weekly_metric_keys())


def project_next_week(metric_key: str, n_weeks: int = 12) -> dict:
    """
    Trustworthy next-week projection of a mission-wide total, with confidence.

    Works for both nightly-form metrics (WEEKLY_KI) and weekly-form metrics
    (pew/date_metric/gate/renew/rc_total from WEEKLY_FORM_RAW). This function is
    only the data plumbing — it fetches the weekly series, drops the current
    still-in-progress week (so a half-finished week can't fake a downward trend),
    trims to the most recent `n_weeks` COMPLETE weeks, and hands the math to
    app.analytics.trends.compute_projection.

    Returns compute_projection's dict:
      status ("ok" | "insufficient"), projected, week_end_date, lower, upper,
      confidence ("high" | "low"), slope_per_week, r_squared, actuals, weeks.
    Returns {} only when the series is entirely unavailable.
    """
    from app.analytics.trends import compute_projection

    if metric_key in _weekly_form_metric_keys():
        trends = get_weekly_ki_totals(n_weeks * 2)
    else:
        # Nightly metrics bucket from DAILY_LOG, NOT from WEEKLY_KI: CCSM's
        # WEEKLY_KI holds only the weekly form's ki_* pairs (see
        # get_nightly_weekly_trends), so the old route found no such column and
        # produced a confident-looking projection of nothing. WEEKLY_KI is still
        # tried first for anything that genuinely lives there.
        trends = get_weekly_ki_trends(n_weeks * 2)
        if trends.empty or metric_key not in trends.columns:
            trends = get_nightly_weekly_trends(n_weeks * 2)
    if trends.empty or metric_key not in trends.columns:
        return {}

    # Never fit against the current, still-in-progress reporting week.
    trends = exclude_current_week(trends)
    trends = trends.sort_values("week_end_date").tail(n_weeks)

    return compute_projection(
        trends[metric_key].tolist(),
        trends["week_end_date"].tolist(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# LEADER WEEKLY EMAIL — ported from worktree-leader-weekly-email-v2
# ══════════════════════════════════════════════════════════════════════════════

_SCORE_COLS = ["Effort_Score", "Skill_Score", "KI_Score", "Effectiveness_Score"]


def get_scores_by_area() -> pd.DataFrame:
    """
    Latest week's Effort/Skill/KI/Effectiveness score per real teaching
    area, for the Zone/District Leader weekly email's Scores-by-area
    section. Excludes leadership tracking rows (Area_Name match, or
    Zone == "ALL") since they never submit and score 0.
    """
    cols = ["area"] + _SCORE_COLS + ["Week_Ending_Date"]
    df = read_tab("SCORES")
    if df.empty or "Week_Ending_Date" not in df.columns:
        return pd.DataFrame(columns=cols)

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in _SCORE_COLS:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["Week_Ending_Date"] = df["Week_Ending_Date"].astype(str).str.strip().str[:10]

    mask_leadership = pd.Series(False, index=df.index)
    if "Area_Name" in df.columns:
        mask_leadership = df["Area_Name"].astype(str).str.match(
            _LEADERSHIP_NAME_RE, case=False, na=False
        )
    if "Zone" in df.columns:
        mask_leadership = mask_leadership | (
            df["Zone"].astype(str).str.strip().str.upper() == "ALL"
        )
    df = df[~mask_leadership]

    if df.empty or "Area_Name" not in df.columns:
        return pd.DataFrame(columns=cols)

    latest_week = df["Week_Ending_Date"].max()
    latest = df[df["Week_Ending_Date"] == latest_week].copy()
    latest = latest.rename(columns={"Area_Name": "area"})
    # Guard against duplicate area rows for the same week (e.g. a re-run of
    # AgentScores appending instead of overwriting) — keep the last one so a
    # single dupe doesn't crash the whole zone/district's leader report.
    latest = latest.drop_duplicates(subset="area", keep="last")
    return latest[cols].reset_index(drop=True)


def get_score_history() -> pd.DataFrame:
    """
    Every SCORES row across all weeks (not just the latest, unlike
    get_scores_by_area()), for since-launch score trend charts. Excludes
    leadership tracking rows the same way get_scores_by_area() does.
    Returns: area, zone, Week_Ending_Date, Effort_Score, Skill_Score,
    KI_Score, Effectiveness_Score.
    """
    cols = ["area", "zone", "Week_Ending_Date"] + _SCORE_COLS
    df = read_tab("SCORES")
    if df.empty or "Week_Ending_Date" not in df.columns:
        return pd.DataFrame(columns=cols)

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in _SCORE_COLS:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["Week_Ending_Date"] = df["Week_Ending_Date"].astype(str).str.strip().str[:10]

    mask_leadership = pd.Series(False, index=df.index)
    if "Area_Name" in df.columns:
        mask_leadership = df["Area_Name"].astype(str).str.match(
            _LEADERSHIP_NAME_RE, case=False, na=False
        )
    if "Zone" in df.columns:
        mask_leadership = mask_leadership | (
            df["Zone"].astype(str).str.strip().str.upper() == "ALL"
        )
    df = df[~mask_leadership]

    if df.empty or "Area_Name" not in df.columns:
        return pd.DataFrame(columns=cols)

    df = df.rename(columns={"Area_Name": "area", "Zone": "zone"})
    df = df.drop_duplicates(subset=["area", "Week_Ending_Date"], keep="last")
    return df[cols].reset_index(drop=True)


def get_score_trend_since_launch() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Mission-wide and per-zone average score trend since SYSTEM_START_DATE.
    Returns (mission_trend, zone_trend):
      mission_trend: one row per Week_Ending_Date, mean of each _SCORE_COLS
                     across all areas that week.
      zone_trend: one row per (zone, Week_Ending_Date), mean of each
                  _SCORE_COLS within that zone that week. Restricted to
                  zones in get_zones() (currently active teaching areas) —
                  a zone/district merge or rename (e.g. "Provo West"
                  merging into "Provo North & West (PN/W)") leaves old
                  SCORES rows carrying the retired zone label, and
                  surfacing that stale name in a leadership report would
                  read as a phantom zone with no current leader. Same
                  "don't trust the historical label" gotcha
                  _scope_by_area_membership() in leader_report.py already
                  guards against, applied at the zone-list level here
                  since this trend spans the mission's whole history
                  rather than one zone/district's current roster.
    Both sorted oldest to newest; weeks before SYSTEM_START_DATE excluded
    (fallback "2026-06-08").
    """
    df = get_score_history()
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    start_date = get_config_value("SYSTEM_START_DATE", "2026-06-08")[:10]
    df = df[df["Week_Ending_Date"] >= start_date]
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    mission_trend = (
        df.groupby("Week_Ending_Date")[_SCORE_COLS].mean()
        .reset_index().sort_values("Week_Ending_Date").reset_index(drop=True)
    )
    zone_trend = (
        df.groupby(["zone", "Week_Ending_Date"])[_SCORE_COLS].mean()
        .reset_index().sort_values(["zone", "Week_Ending_Date"]).reset_index(drop=True)
    )
    current_zones = set(get_zones())
    zone_trend = zone_trend[zone_trend["zone"].isin(current_zones)].reset_index(drop=True)
    return mission_trend, zone_trend


def _classify_leadership_row(area_name: str, zone: str, district: str) -> dict | None:
    """
    Classify a MISSION_ORG row as a Zone or District leadership assignment
    from its Area_Name, or None if it isn't a leadership tracking row.
    Shared by get_all_leader_assignments() so the "what counts as a
    ZL/STL/DL row" rule lives in exactly one place.
    """
    name = str(area_name or "").strip().lower()
    if name.startswith("district leader -"):
        d = str(district or "").strip()
        return {"kind": "District", "value": d} if d else None
    if name.startswith("zone leader") or name.startswith("sister training leader -"):
        z = str(zone or "").strip()
        return {"kind": "Zone", "value": z} if z else None
    return None


_ROLE_FLAGS = (
    # (role, MISSION_ORG flag column, report kind, column the scope is read from)
    ("ZL", "Is_ZL", "Zone", "Zone"),
    ("STL", "Is_STL", "Zone", "Zone"),
    ("DL", "Is_DL", "District", "District"),
)

# A ZL and an STL both receive the same Zone report, so both map to kind "Zone".
_ROLE_KIND = {role: kind for role, _flag, kind, _scope in _ROLE_FLAGS}


def _tracking_row_role(area_name: str) -> str | None:
    """Which calling a "Zone Leader - X" / "District Leader - X" /
    "Sister Training Leader - X" tracking row represents, or None."""
    name = str(area_name or "").strip().lower()
    if name.startswith("district leader -"):
        return "DL"
    if name.startswith("sister training leader -"):
        return "STL"
    if name.startswith("zone leader"):
        return "ZL"
    return None


def _flagged_leaders() -> dict[tuple[str, str], list[dict]]:
    """
    Map (role, scope) -> [{email, name, area}, ...] for every missionary whose
    own active teaching-area row carries the matching Is_ZL/Is_STL/Is_DL flag.
    Both companions on a flagged row are included — a companionship is two
    people and both hold the calling.

    Keyed by role (not report kind) so a vacant Sister Training Leader calling
    isn't masked by the Zone Leader who shares its zone scope.
    """
    df = get_areas_df()
    out: dict[tuple[str, str], list[dict]] = {}
    if df.empty:
        return out
    for _, row in df.iterrows():
        # Skip the "Zone Leader - X" / "District Leader - X" tracking rows: the
        # flags are legitimately TRUE there too, but their scope is the routing
        # label, not a real area assignment.
        if _classify_leadership_row(
                row.get("Area_Name", ""), row.get("Zone", ""), row.get("District", "")):
            continue
        for role, flag, _kind, scope_col in _ROLE_FLAGS:
            if str(row.get(flag, "")).strip().upper() != "TRUE":
                continue
            scope = str(row.get(scope_col, "")).strip()
            if not scope:
                continue
            for ncol, ecol in (("Companion1_Name", "Companion1_Email"),
                               ("Companion2_Name", "Companion2_Email")):
                email = str(row.get(ecol, "")).strip().lower()
                if email and "@" in email:
                    out.setdefault((role, scope), []).append({
                        "email": email,
                        "name": str(row.get(ncol, "")).strip(),
                        "area": str(row.get("Area_Name", "")).strip(),
                    })
    return out


def _coverage_map() -> dict[tuple[str, str], str]:
    """
    (role, scope) -> the scope that covers it, read from the optional
    `Covered_By` column on leadership tracking rows.

    A leader's scope comes from their own area's Zone/District, so a missionary
    can hold exactly one scope per role. `Covered_By` is how one leader covers a
    second scope's vacant calling — e.g. the Provo East STL is also the STL for
    Provo North & West, so that row carries `Covered_By = "Provo East"`.

    It stores a SCOPE NAME, never an email: recipients are still resolved
    through the Is_* flags, so coverage self-heals across transfers exactly the
    way normal routing does. Putting an address here instead would reintroduce
    the stale-tracking-row bug that mis-routed 11 reports on 2026-07-27.

    Absent column, blank value, and self-reference all mean "no coverage", so
    the code is a no-op until the column exists in MISSION_ORG.
    """
    df = get_areas_df()
    out: dict[tuple[str, str], str] = {}
    if df.empty or "Covered_By" not in df.columns:
        return out
    for _, row in df.iterrows():
        result = _classify_leadership_row(
            row.get("Area_Name", ""), row.get("Zone", ""), row.get("District", ""))
        if not result:
            continue
        role = _tracking_row_role(row.get("Area_Name", ""))
        if not role:
            continue
        covering = str(row.get("Covered_By", "") or "").strip()
        scope = str(result["value"]).strip()
        if not covering or covering == scope:
            continue
        out[(role, scope)] = covering
    return out


def get_all_leader_assignments() -> list[dict]:
    """
    Every Zone Leader / Sister Training Leader / District Leader recipient,
    with their resolved scope. Used by send_leader_weekly_reports.py.

    Recipients are resolved from the Is_ZL/Is_STL/Is_DL flags on real
    teaching-area rows — NOT from the "Zone Leader - X" / "District Leader - X"
    tracking rows' own Companion1_Email. Those tracking rows are not updated by
    the transfer flow, so their email goes stale every time a calling moves.
    On 2026-07-27 that mis-routed 11 of 31 leader reports the first night they
    went to real inboxes (a Zone Leader received a District Leader breakdown,
    and two district pairs were crossed). The per-area role flags ARE
    maintained by the transfer flow, so deriving from them self-heals.

    Verified equivalent to the hand-corrected tracking rows on 2026-07-27
    (24 of 24 identical) before this became the source of truth. Scopes where
    nobody is flagged yield no recipient rather than a stale wrong one — see
    get_leader_assignment_warnings() to surface those.
    """
    flagged = _flagged_leaders()
    seen = set()
    out = []

    def _add(email: str, kind: str, scope: str) -> None:
        key = (email, kind, scope)
        if key in seen:
            return
        seen.add(key)
        out.append({"email": email, "kind": kind, "value": scope})

    for (role, scope), people in flagged.items():
        for p in people:
            _add(p["email"], _ROLE_KIND[role], scope)

    # Covered_By: a scope with nobody flagged can name another scope whose
    # role-holders receive its report too. Skipped the moment the scope has its
    # own flagged leader, so the arrangement can't outlive its truth.
    for (role, scope), covering in _coverage_map().items():
        if flagged.get((role, scope)):
            continue
        for p in flagged.get((role, covering), []):
            _add(p["email"], _ROLE_KIND[role], scope)

    return out


def get_leader_assignment_warnings() -> list[str]:
    """
    Human-readable warnings about leadership routing, for the weekly batch
    summary email. Surfaces the two failure modes that would otherwise be
    silent: a tracking row whose scope has nobody flagged (that report goes to
    NOBODY), and a tracking row whose stored email disagrees with the flags
    (harmless for routing now, but a sign MISSION_ORG needs tidying).
    """
    df = get_areas_df()
    if df.empty:
        return []
    flagged = _flagged_leaders()
    coverage = _coverage_map()
    warnings = []
    for _, row in df.iterrows():
        result = _classify_leadership_row(
            row.get("Area_Name", ""), row.get("Zone", ""), row.get("District", ""))
        if not result:
            continue
        name = str(row.get("Area_Name", "")).strip()
        role = _tracking_row_role(name)
        people = flagged.get((role, result["value"]), [])
        if not people:
            covering = coverage.get((role, result["value"]))
            cover_people = flagged.get((role, covering), []) if covering else []
            if cover_people:
                who = ", ".join(f"{p['name']} <{p['email']}>" for p in cover_people)
                warnings.append(
                    f"COVERED BY: '{name}' has nobody flagged Is_{role} in "
                    f"{result['kind']} '{result['value']}', so the {role} for "
                    f"'{covering}' ({who}) receives it as well.")
                continue
            extra = ""
            if covering:
                extra = (f" Its Covered_By names '{covering}', but nobody is "
                         f"flagged Is_{role} there either.")
            warnings.append(
                f"VACANT: '{name}' expects a {role} over {result['kind']} "
                f"'{result['value']}', but nobody there is flagged Is_{role} — "
                f"that calling looks unfilled in MISSION_ORG.{extra}")
            continue
        stored = str(row.get("Companion1_Email", "")).strip().lower()
        if stored and "@" in stored and stored not in {p["email"] for p in people}:
            who = ", ".join(f"{p['name']} <{p['email']}>" for p in people)
            warnings.append(
                f"STALE ROW: '{name}' still stores {stored}, but the flagged "
                f"{role} for '{result['value']}' is {who}. Routing used the "
                f"flags (correct); update the row when convenient.")
    return warnings


# ── Area lineage (merge/split/rename/retire) ────────────────────────────────
# Reads AREA_LINEAGE, written by docs/LineageReview.gs's applyLineage(). See
# docs/superpowers/specs/2026-07-07-area-lifecycle-design.md and
# docs/superpowers/specs/2026-07-19-area-lineage-completion-design.md.

def get_area_lineage() -> pd.DataFrame:
    """All AREA_LINEAGE rows. Empty DataFrame if the tab doesn't exist yet
    (read_tab handles the missing-worksheet case) or has no rows."""
    return read_tab("AREA_LINEAGE")


def get_lineage_for_successor(area: str) -> dict | None:
    """Most recent AREA_LINEAGE row where `area` is the New_Area (successor).
    None if `area` has never been a lineage successor."""
    df = get_area_lineage()
    if df.empty or "New_Area" not in df.columns:
        return None
    matches = df[df["New_Area"].astype(str).str.strip() == area.strip()]
    if matches.empty:
        return None
    return matches.iloc[-1].to_dict()


def get_lineage_for_retired_parent(area: str) -> dict | None:
    """Most recent AREA_LINEAGE row where `area` appears in the semicolon-
    separated Old_Areas (i.e. `area` was combined/renamed away). None if
    `area` was never a lineage parent."""
    df = get_area_lineage()
    if df.empty or "Old_Areas" not in df.columns:
        return None
    for _, row in df.iloc[::-1].iterrows():
        parents = [p.strip() for p in str(row.get("Old_Areas", "")).split(";") if p.strip()]
        if area.strip() in parents:
            return row.to_dict()
    return None


def get_retired_lineage_areas() -> set:
    """Every area name that appears as a parent (Old_Areas) in AREA_LINEAGE —
    the set of retired areas eligible for the Breakdowns picker + marker."""
    df = get_area_lineage()
    if df.empty or "Old_Areas" not in df.columns:
        return set()
    out = set()
    for val in df["Old_Areas"]:
        out.update(p.strip() for p in str(val).split(";") if p.strip())
    return out


def get_lineage_visible_areas() -> pd.DataFrame:
    """Areas selectable in the Breakdowns picker: every active submitting area,
    plus retired areas that have an AREA_LINEAGE record (so their redirect
    marker is reachable). Retired areas with no lineage record stay hidden,
    matching today's behavior."""
    active = get_submitting_areas()
    retired_names = get_retired_lineage_areas()
    if not retired_names:
        return active
    all_areas = get_areas_df(active_only=False)
    if all_areas.empty or "Area_Name" not in all_areas.columns:
        return active
    retired = all_areas[
        all_areas["Area_Name"].astype(str).str.strip().isin(retired_names)
        & (all_areas.get("Active", pd.Series(dtype=str)).astype(str).str.upper() != "TRUE")
    ]
    if retired.empty:
        return active
    return pd.concat([active, retired], ignore_index=True)


def get_recent_transfer_dates(n: int = 2) -> list:
    """Start_Date of the n most recent 'Actual' TRANSFER_SCHEDULE rows, most
    recent (highest Transfer_Number) first. Empty if the tab is missing/empty
    or has no Actual rows."""
    df = read_tab("TRANSFER_SCHEDULE")
    if df.empty or "Status" not in df.columns:
        return []
    actual = df[df["Status"].astype(str).str.strip() == "Actual"].copy()
    if actual.empty:
        return []
    actual["_num"] = pd.to_numeric(actual["Transfer_Number"], errors="coerce")
    actual = actual.dropna(subset=["_num"]).sort_values("_num", ascending=False)
    return actual["Start_Date"].astype(str).head(n).tolist()


def is_within_last_transfers(transfer_date: str, n: int = 2) -> bool:
    """True if `transfer_date` matches one of the n most recent 'Actual'
    TRANSFER_SCHEDULE Start_Dates — drives the badge's display window."""
    return str(transfer_date).strip() in get_recent_transfer_dates(n)
