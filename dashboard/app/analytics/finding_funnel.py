"""Pure helpers for the Finding Funnel page's date-range filtering and the
per-area rankings rebuilt from the Detail export. No Streamlit / IO here so
the logic stays unit-testable."""

from datetime import date, timedelta

import pandas as pd

# preset label -> inclusive window length in days (None == whole window).
# Ordered shortest-first so the radio row reads 7 -> 14 -> 30 -> All, and so
# the 2.6-year "All" view is a deliberate choice at the end of the row rather
# than whatever the page happens to open on.
PRESETS = {
    "Last 7 days": 7,
    "Last 14 days": 14,
    "Last 30 days": 30,
    "All": None,
}

# What the page opens on. "All" now spans 2024-01 -> today (~89,800 people over
# ~950 days) because the bogus floor below is gone; this page is read for the
# current picture, so it opens recent and the full history is one click away.
DEFAULT_PRESET = "Last 30 days"


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


def data_date_bounds(det_df: pd.DataFrame, floor: date | None = None):
    """(lo, hi) selectable bounds derived FROM THE DATA: lo = the earliest
    found-date present, hi = the latest.

    `floor` is an optional extra clamp for a caller that genuinely wants one,
    and defaults to None. It used to default to a module-level
    ``DATA_FLOOR = date(2026, 5, 19)`` carrying the comment "the mission's
    finding data begins May 19, 2026" -- the real Tableau export disproves
    that (finding data starts 2024-01-01), and the floor was hiding 77,499 of
    89,850 people, 86% of the dataset. Derive it; never hardcode it again.

    Falls back to (today, today) when there is nothing to measure.
    """
    fallback = floor or date.today()
    if det_df is None or det_df.empty:
        return fallback, fallback
    ev = parse_dates(det_df, "event_date_selected").dropna()
    if ev.empty:
        return fallback, fallback
    lo = ev.min().date()
    if floor is not None:
        lo = max(floor, lo)
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


# (label, Detail date column marking that milestone).
#
# ONE list. The Finding Funnel page imports it instead of keeping its own copy,
# which is how the two drifted apart: the chart showed 6 stages and stopped at
# "Baptism Date Set", while the per-area table directly below it counted 7 and
# included the baptisms. The chart never showed the outcome the whole pipeline
# exists for.
#
# Every later stage is a strict subset of the one above it, so the funnel only
# ever narrows. On the full export:
#   89,850 -> 85,821 -> 55,633 -> 46,073 -> 5,239 -> 2,380 -> 837
FUNNEL_STAGES = [
    ("Found",                  None),
    ("Contact Attempted",      "first_contact_attempt_event_date"),
    ("Successfully Contacted", "first_successful_contact_attempt_event_date"),
    ("Being Taught",           "first_new_person_being_taught_date"),
    ("Attended Church",        "first_sacrament_date"),
    ("Baptism Date Set",       "first_baptism_goal_date_set"),
    ("Baptized",               "confirmation_date"),
]

# Referred is deliberately NOT a funnel stage. It records HOW a person was
# found -- a member or ward referral -- not how far they progressed, and on the
# real export it is SMALLER than the stage beneath it: 19,256 referred against
# 85,821 contact-attempted. Charting it would make the funnel widen halfway
# down, which reads as a broken chart. It keeps its KPI tile and its column on
# the per-area table, where it is a fact about the area rather than a stage.
REFERRED_STAGE = ("Referred", "first_referral_event_date")

# Short headers for the per-area table, derived from FUNNEL_STAGES so a stage
# cannot exist in one place and not the other.
_TABLE_LABELS = {
    "Contact Attempted":      "Attempted",
    "Successfully Contacted": "Contacted",
    "Being Taught":           "Teaching",
    "Attended Church":        "Church",
    "Baptism Date Set":       "Bap Date",
    "Baptized":               "Baptized",
}
_STAGE_COLS = [REFERRED_STAGE] + [
    (_TABLE_LABELS[label], col) for label, col in FUNNEL_STAGES if col is not None
]


def compute_funnel_stage_counts(det_df: pd.DataFrame) -> dict:
    """
    Ordered {stage_label: count} for an already date-filtered Detail export
    (e.g. via filter_by_range). Each stage counts rows (people) that reached
    that milestone -- "Found" is every row; every later stage counts rows
    whose milestone date column is non-blank.

    Keys are the ENGLISH labels from FUNNEL_STAGES. Callers translate for
    display only: the page used to key its own copy of this dict by t(label)
    and then read it back with English literals, so on a Spanish interface
    every lookup missed and the KPI row reported 0 people contacted.
    """
    if det_df is None or det_df.empty:
        return {}
    counts = {}
    for label, col in FUNNEL_STAGES:
        counts[label] = len(det_df) if col is None else int(parse_dates(det_df, col).notna().sum())
    return counts


def trend_series(det_df: pd.DataFrame, max_daily_days: int = 120):
    """(labels, values, granularity) for the findings-over-time chart.

    Buckets by day for a short window and by MONTH once the data spans more
    than `max_daily_days`. Removing the bogus DATA_FLOOR made "All" a 2.6-year
    range, which as a daily bar chart is ~950 bars with unreadable labels.
    `granularity` is "day" or "month" so the caller can say which it drew.
    """
    if det_df is None or det_df.empty:
        return [], [], "day"
    ev = parse_dates(det_df, "event_date_selected").dropna()
    if ev.empty:
        return [], [], "day"
    span = (ev.max().date() - ev.min().date()).days + 1
    if span > max_daily_days:
        per = ev.dt.to_period("M").value_counts().sort_index()
        return [str(p) for p in per.index], [int(v) for v in per.values], "month"
    per = ev.dt.date.value_counts().sort_index()
    return [str(d) for d in per.index], [int(v) for v in per.values], "day"


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
