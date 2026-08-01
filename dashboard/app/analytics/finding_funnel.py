"""Pure helpers for the Finding Funnel page's date-range filtering and the
per-area rankings rebuilt from the Detail export. No Streamlit / IO here so
the logic stays unit-testable."""

from datetime import date, timedelta

import pandas as pd

# Data floor: the mission's finding data begins May 19, 2026.
DATA_FLOOR = date(2026, 5, 19)

# preset label -> inclusive window length in days (None == whole window)
PRESETS = {"All": None, "Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30}


def resolve_col(df: pd.DataFrame, *needles: str):
    """Exact (case-insensitive) match wins; else the SHORTEST column whose
    lowercased name contains all needles, skipping Tableau's giant
    '...(combined)' mashup column."""
    lowered = {str(c).lower(): c for c in df.columns}
    for n in needles:
        if n in lowered:
            return lowered[n]
    matches = [c for c in df.columns
               if all(n in str(c).lower() for n in needles)
               and "(combined)" not in str(c).lower()]
    return min(matches, key=lambda c: len(str(c))) if matches else None


def parse_dates(df: pd.DataFrame, name: str) -> pd.Series:
    """Parse a Detail date column to datetime (NaT where blank/absent)."""
    c = resolve_col(df, name)
    if c is None:
        return pd.Series([pd.NaT] * len(df), index=df.index)
    return pd.to_datetime(df[c], errors="coerce", format="mixed")


def data_date_bounds(det_df: pd.DataFrame, floor: date = DATA_FLOOR):
    """(lo, hi) selectable bounds: lo = max(floor, earliest found-date),
    hi = latest found-date present. Falls back to (floor, floor) when empty."""
    if det_df is None or det_df.empty:
        return floor, floor
    ev = parse_dates(det_df, "event_date_selected").dropna()
    if ev.empty:
        return floor, floor
    lo = max(floor, ev.min().date())
    hi = ev.max().date()
    return (lo, hi) if hi >= lo else (lo, lo)


def preset_range(preset: str, lo: date, hi: date):
    """Resolve a preset label to a concrete (start, end) window anchored on hi
    (the data's latest found-date). 'All'/unknown -> (lo, hi). Start clamps to lo."""
    n = PRESETS.get(preset)
    if n is None:
        return lo, hi
    start = hi - timedelta(days=n - 1)
    return (max(start, lo), hi)


def filter_by_range(det_df: pd.DataFrame, start, end) -> pd.DataFrame:
    """Keep Detail rows whose event_date_selected falls in [start, end]
    (inclusive). start/end are datetime.date or None. When BOTH are None
    ('All'), the frame is returned unchanged so blank-date rows are retained."""
    if det_df is None or det_df.empty or (start is None and end is None):
        return det_df
    ev = parse_dates(det_df, "event_date_selected")
    mask = ev.notna()
    d = ev.dt.date
    if start is not None:
        mask &= d >= start
    if end is not None:
        mask &= d <= end
    return det_df[mask]


# (label, Detail date column marking that milestone) — matches the Finding
# Funnel page's own FUNNEL list (pages/07_Embudo_de_Búsqueda.py) so the mission
# slideshow's numbers always agree with what's on that page.
FUNNEL_STAGES = [
    ("Found",                  None),
    ("Contact Attempted",      "first_contact_attempt_event_date"),
    ("Successfully Contacted", "first_successful_contact_attempt_event_date"),
    ("Being Taught",           "first_new_person_being_taught_date"),
    ("Attended Church",        "first_sacrament_date"),
    ("Baptism Date Set",       "first_baptism_goal_date_set"),
]


def compute_funnel_stage_counts(det_df: pd.DataFrame) -> dict:
    """
    Ordered {stage_label: count} for an already date-filtered Detail export
    (e.g. via filter_by_range). Each stage counts rows (people) that reached
    that milestone — "Found" is every row; every later stage counts rows
    whose milestone date column is non-blank.
    """
    if det_df is None or det_df.empty:
        return {}
    counts = {}
    for label, col in FUNNEL_STAGES:
        counts[label] = len(det_df) if col is None else int(parse_dates(det_df, col).notna().sum())
    return counts


# (label, Detail date column marking that milestone) — a person counts toward a
# stage when that date column is present (non-blank).
_STAGE_COLS = [
    ("Referred",  "first_referral_event_date"),
    ("Attempted", "first_contact_attempt_event_date"),
    ("Contacted", "first_successful_contact_attempt_event_date"),
    ("Teaching",  "first_new_person_being_taught_date"),
    ("Church",    "first_sacrament_date"),
    ("Bap Date",  "first_baptism_goal_date_set"),
    ("Baptized",  "confirmation_date"),
]


def build_area_rankings(det_df: pd.DataFrame) -> pd.DataFrame:
    """Per-area finding table rebuilt from Detail so it honors the active date
    filter. One row per latest_teaching_area_name; every metric is a count of
    people in that area whose milestone date is present. Contact %/Contacted %
    are those counts over Found. Areas with zero Found dropped; sorted Found desc."""
    if det_df is None or det_df.empty:
        return pd.DataFrame()
    area_col = resolve_col(det_df, "latest_teaching_area_name") or \
        resolve_col(det_df, "teaching_area")
    if area_col is None:
        return pd.DataFrame()

    frame = {"Area": det_df[area_col].astype(str).str.strip()
             .replace({"": "Unknown", "nan": "Unknown"})}
    for label, col in _STAGE_COLS:
        frame[label] = parse_dates(det_df, col).notna().astype(int).values
    df = pd.DataFrame(frame)

    agg = {"Found": ("Area", "size")}
    agg.update({label: (label, "sum") for label, _ in _STAGE_COLS})
    g = df.groupby("Area", as_index=False).agg(**agg)

    g["Contact %"] = (g["Attempted"] / g["Found"] * 100).where(g["Found"] > 0, 0.0)
    g["Contacted %"] = (g["Contacted"] / g["Found"] * 100).where(g["Found"] > 0, 0.0)

    out = g[["Area", "Found", "Referred", "Contact %", "Contacted %",
             "Teaching", "Church", "Bap Date", "Baptized"]]
    out = out[out["Found"] > 0].sort_values("Found", ascending=False)
    return out.reset_index(drop=True)
