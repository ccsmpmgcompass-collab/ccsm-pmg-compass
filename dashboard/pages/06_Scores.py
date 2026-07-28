"""
06_Scores.py
──────────────────────────────────────────────────────────────
Scores — PMG Compass
Three performance-analysis tools in one page (merged 2026-07-21):
  - Scores        : computed Effort/Skill/KI/Effectiveness scores per area,
                     scoped with the shared Zone/District/Area cascade, plus
                     a score-weight config editor backed by SCORE_CONFIG.
  - Daily Activity : nightly form data explorer (DAILY_LOG), by category.
  - Analyze        : anomaly detection + next-week trend projections.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.auth.auth import require_auth
from app.components.design_system import (
    inject_global_css, render_page_header, render_sidebar,
    render_section_label, render_status_pill, render_kpi_row, render_table,
)
from app.components.scope_selector import ANY as SCOPE_ANY
from app.components.scope_selector import render_scope_selectors
from app.config.flavor_loader import flavor, METRIC_LABELS as _FLAVOR_METRIC_LABELS
from app.config.theme import series_style, CHART_COLORS
from app.db.queries import (
    compute_effort_score_breakdown,
    compute_mission_president_effort_scores,
    detect_anomalies,
    get_all_area_type_indicators,
    get_area_effort_actuals_weekly,
    get_area_effort_expectations_weekly,
    get_areas_df,
    get_config_value,
    get_daily_log,
    get_districts,
    get_effort_data,
    get_submitting_areas,
    get_zones,
    project_next_week,
)
from app.db.sheets_client import overwrite_tab, read_tab

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Scores — PMG Compass",
    page_icon="",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)
dark = True

# Sentinel area code for a single config that applies to every area in the mission.
MISSION_WIDE_CODE = "ALL"
MISSION_WIDE_LABEL = "Whole Mission (all areas)"

# Friendly display names for every metric that feeds the Effectiveness score.
METRIC_LABELS: dict[str, str] = {
    # Finding & teaching
    "new_found":             "New",
    "nm_lessons":            "Non-Member Lessons",
    "member_lessons":        "Mate",
    "rc_lessons":            "Recent-Convert Lessons",
    "la_lessons":            "Less-Active Lessons",
    "nm_meaningful":         "NM Meaningful Conversations",
    "nm_contacted":          "Non-Members Contacted",
    "nm_texts":              "Non-Member Texts Sent",
    "mmm_sent":              "MMM Sent",
    # Love / Share / Invite + referrals
    "lsi_given":             "Love-Share-Invite Given",
    "lsi_followups":         "Love-Share-Invite Follow-Ups",
    "referrals_today":       "Member Referrals",
    "online_referrals":      "Online Referrals",
    # Door / attempt activity
    "nm_doors":              "NM Attempted",
    "la_knocked":            "Less-Active Attempts",
    "fellowshipper_knocked": "Fellowshipper Attempts",
    "aux_knocked":           "Aux / Coordination Attempts",
    "info_knocked":          "Informational Attempts",
    "locos_knocked":         "LOCOS Attempts",
    # Weekly Key Indicators
    "gate":                  "Gate",
    "date_metric":           "Date",
    "pew":                   "Pew",
    "renew":                 "Renew",
    "rc_total":              "RC — Could Have Attended",
}

# ── Constants ─────────────────────────────────────────────────────────────────

SCORE_COLS = [
    "Area_Code",
    "Area_Name",
    "Zone",
    "Missionary_Names",
    "Week_Ending_Date",
    "Effort_Score",
    "Skill_Score",
    "KI_Score",
    "Effectiveness_Score",
    "Computed_At",
]

NUMERIC_SCORE_COLS = ["Effort_Score", "Skill_Score", "KI_Score", "Effectiveness_Score"]

DISPLAY_COL_MAP = {
    "Area_Name":           "Area",
    "Effort_Score":        "Effort",
    "Skill_Score":         "Skill",
    "KI_Score":            "KI",
    "Effectiveness_Score": "Effectiveness",
}

# Score color thresholds
_GREEN  = "#14532d"   # >= 70
_YELLOW = "#713f12"   # 50–69
_RED    = "#7f1d1d"   # < 50

# Effort metric weights shown in config editor (same defaults as AgentScores.gs)
DEFAULT_EFFORT_WEIGHTS: dict[str, float] = {
    "new_found":             20.0,
    "nm_meaningful":         12.0,
    "lsi_followups":         10.0,
    "nm_lessons":            10.0,
    "referrals_today":        8.0,
    "mmm_sent":               7.0,
    "online_referrals":       7.0,
    "lsi_given":              6.0,
    "nm_contacted":           5.0,
    "member_lessons":         4.0,
    "la_lessons":             3.0,
    "rc_lessons":             3.0,
    "nm_texts":               2.0,
    "fellowshipper_knocked":  1.0,
    "la_knocked":             1.0,
    "nm_doors":               1.0,
    "aux_knocked":            0.5,
    "info_knocked":           0.5,
    "locos_knocked":          0.5,
}

DEFAULT_SKILL_WEIGHTS: dict[str, float] = {
    "nm_lessons":     30.0,
    "nm_meaningful":  25.0,
    "member_lessons": 20.0,
    "new_found":      15.0,
    "lsi_followups":  10.0,
}

DEFAULT_KI_WEIGHTS: dict[str, float] = {
    "gate":        40.0,
    "date_metric": 25.0,
    "pew":         20.0,
    "renew":       10.0,
    "rc_total":     5.0,
}

DEFAULT_EFF_WEIGHTS = flavor.scoring_weights


# ── Data loading ──────────────────────────────────────────────────────────────

# Leadership tracking rows in MISSION_ORG / SCORES — matched by Area_Name.
# Mirrors asc_isLeadershipRow_ in AgentScores.gs and _LEADERSHIP_NAME_RE in
# app/db/queries.py (the flags Is_ZL/Is_STL/… are NOT used: a real teaching
# area legitimately carries a flag when its companionship holds the calling).
_LEADERSHIP_NAME_RE = (
    r"^(Mission President|Assistant to President|Zone Leader|"
    r"Sister Training Leader -|District Leader -)"
)


@st.cache_data(ttl=300)
def _load_scores() -> pd.DataFrame:
    """Load SCORES tab and normalise types."""
    df = read_tab("SCORES")
    if df.empty:
        return pd.DataFrame(columns=SCORE_COLS)

    # Normalise column names (case-insensitive strip)
    df.columns = [str(c).strip() for c in df.columns]

    # Ensure all expected columns exist
    for col in SCORE_COLS:
        if col not in df.columns:
            df[col] = ""

    # Coerce numeric score columns
    for col in NUMERIC_SCORE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Normalise date column to string YYYY-MM-DD
    if "Week_Ending_Date" in df.columns:
        df["Week_Ending_Date"] = (
            df["Week_Ending_Date"].astype(str).str.strip().str[:10]
        )

    # Drop leadership tracking rows. They never submit and score 0, so leftover
    # rows (e.g. written before the engine's name-based skip existed) would
    # otherwise appear in the table and drag the mission average down. Keyed off
    # Area_Name / Zone == "ALL" — mirrors asc_isLeadershipRow_ in AgentScores.gs.
    is_leadership = pd.Series(False, index=df.index)
    if "Area_Name" in df.columns:
        is_leadership = df["Area_Name"].astype(str).str.match(
            _LEADERSHIP_NAME_RE, case=False, na=False
        )
    if "Zone" in df.columns:
        is_leadership = is_leadership | (
            df["Zone"].astype(str).str.strip().str.upper() == "ALL"
        )
    df = df[~is_leadership].copy()

    return df


@st.cache_data(ttl=300)
def _load_score_config() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Parse SCORE_CONFIG into two DataFrames:
      sec1 — field weights (Area_Code, Metric_Key, Score_Component, Weight, Active)
      sec2 — effectiveness weights (Area_Code, Effort_Weight, Skill_Weight, KI_Weight)
    """
    raw = read_tab("SCORE_CONFIG")
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    # The tab has two sections separated by a blank row.
    # Section 1 header: Area_Code | Metric_Key | Score_Component | Weight | Active
    # Section 2 header: Area_Code | Effort_Weight | Skill_Weight | KI_Weight

    rows = raw.values.tolist()
    headers0 = [str(c).strip() for c in raw.columns]

    sec1_rows: list[list] = []
    sec2_rows: list[list] = []
    sec1_headers: list[str] = []
    sec2_headers: list[str] = []

    in_section2 = False
    passed_blank = False

    for row in rows:
        row_strs = [str(v).strip() for v in row]
        first = row_strs[0] if row_strs else ""

        # Blank separator row
        if not any(row_strs):
            if not passed_blank:
                passed_blank = True
            continue

        if not passed_blank:
            # Section 1
            if first == "Area_Code" and not sec1_headers:
                sec1_headers = row_strs[:5]
            else:
                sec1_rows.append(row_strs[:5])
        else:
            # Section 2
            if first == "Area_Code" and not sec2_headers:
                sec2_headers = row_strs[:4]
            else:
                sec2_rows.append(row_strs[:4])

    sec1_h = sec1_headers or ["Area_Code", "Metric_Key", "Score_Component", "Weight", "Active"]
    sec2_h = sec2_headers or ["Area_Code", "Effort_Weight", "Skill_Weight", "KI_Weight"]

    sec1 = pd.DataFrame(sec1_rows, columns=sec1_h) if sec1_rows else pd.DataFrame(columns=sec1_h)
    sec2 = pd.DataFrame(sec2_rows, columns=sec2_h) if sec2_rows else pd.DataFrame(columns=sec2_h)

    if not sec1.empty and "Weight" in sec1.columns:
        sec1["Weight"] = pd.to_numeric(sec1["Weight"], errors="coerce").fillna(0.0)

    for col in ["Effort_Weight", "Skill_Weight", "KI_Weight"]:
        if not sec2.empty and col in sec2.columns:
            sec2[col] = pd.to_numeric(sec2[col], errors="coerce").fillna(0.0)

    return sec1, sec2


# ── Score table styling ───────────────────────────────────────────────────────

def _color_score(val: float) -> str:
    """Return CSS background + text color for dark-mode score table cells."""
    if val >= 70:
        return f"background-color: {_GREEN}; color: #86efac"
    if val >= 50:
        return f"background-color: {_YELLOW}; color: #fcd34d"
    return f"background-color: {_RED}; color: #fca5a5"


_TIER_DOT_COLORS = {"green": "#16a34a", "amber": "#ca8a04", "red": "#dc2626"}


def _tier_circle(val: Any) -> str:
    """A flat colored dot for the table's leading Rating column — same
    thresholds as _color_score, but a glance-able marker instead of reading
    Effectiveness's own colored cell. A plain CSS circle, not an emoji: the 🟢🟡🔴
    glyphs render with a glossy 3D highlight on most platforms, which read as
    "shiny" against the flat, matte colors everywhere else on this page (the bar
    chart's fills, the legend pills) — Carson asked for it to match. render_table
    renders the Styler's HTML unescaped, so this <span> draws as a real element."""
    try:
        fval = float(val)
    except (TypeError, ValueError):
        return "—"
    color = (
        _TIER_DOT_COLORS["green"] if fval >= 70
        else _TIER_DOT_COLORS["amber"] if fval >= 50
        else _TIER_DOT_COLORS["red"]
    )
    return (
        f'<span style="display:inline-block;width:12px;height:12px;'
        f'border-radius:50%;background:{color};"></span>'
    )


def _style_score_df(df: pd.DataFrame) -> pd.DataFrame.style:
    """Apply color styling to score columns."""
    cols_to_style = [c for c in NUMERIC_SCORE_COLS if c in df.columns]
    styler = df.style
    for col in cols_to_style:
        styler = styler.map(_color_score, subset=[col])  # type: ignore[arg-type]
    return styler


# ── Filtering helpers ─────────────────────────────────────────────────────────

def _scope_area_names(
    areas_all: pd.DataFrame,
    level: str | None,
    zone: str,
    district: str,
    area: str,
) -> set | None:
    """Area names to keep for the selected scope, resolved against MISSION_ORG's
    roster (SCORES has no District column, and the roster is the authority for
    who's in a zone/district anyway — same reason Breakdowns scopes by roster).

    Returns None for the mission-wide view (no filter). A zone/district with no
    roster match returns an empty set, so the table honestly shows nothing
    rather than silently falling back to every area.
    """
    if level is None:
        return None
    if level == "area":
        return {str(area).strip()}
    col = "Zone" if level == "zone" else "District"
    val = zone if level == "zone" else district
    if areas_all.empty or col not in areas_all.columns or "Area_Name" not in areas_all.columns:
        return set()
    sel = areas_all[areas_all[col].astype(str).str.strip() == str(val).strip()]
    return set(sel["Area_Name"].astype(str).str.strip())


def _filter_by_scope(df: pd.DataFrame, area_names: set | None) -> pd.DataFrame:
    """Keep only rows whose area is in `area_names` (None = mission-wide)."""
    if df.empty or area_names is None or "Area_Name" not in df.columns:
        return df
    return df[df["Area_Name"].astype(str).str.strip().isin(area_names)].copy()


def _filter_by_time(df: pd.DataFrame, time_range: str) -> pd.DataFrame:
    if df.empty or "Week_Ending_Date" not in df.columns:
        return df

    today_str = date.today().strftime("%Y-%m-%d")

    if time_range == "Last 7 Days":
        cutoff = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        df = df[df["Week_Ending_Date"] >= cutoff].copy()
    elif time_range == "Transfer to Date":
        # A transfer is 6 weeks; use the most recent Mon that started a 6-week block.
        # Approximation: last 42 days from today.
        cutoff = (date.today() - timedelta(days=42)).strftime("%Y-%m-%d")
        df = df[df["Week_Ending_Date"] >= cutoff].copy()
    # "All Time" — no filter

    return df


def _most_recent_per_area(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the most recent week per area."""
    if df.empty or "Area_Code" not in df.columns or "Week_Ending_Date" not in df.columns:
        return df
    idx = df.groupby("Area_Code")["Week_Ending_Date"].idxmax()
    return df.loc[idx].copy()


def _avg_effort_breakdown(area: str, weeks: list[str]) -> list[dict] | None:
    """
    Per-metric Effort breakdown for `area`, averaged across every week in
    `weeks` — the SAME time+scope-filtered weeks _avg_over_window averages
    Effort_Score across for the table/KPI cards. Powers the Scores page's
    per-area pie chart: without this, the pie stayed pinned to only the
    single latest week no matter what Time Range was picked, so it could
    disagree with the Effort number shown right next to it. Averages each
    metric's 0-100 `scaled_score` across the weeks it was present in (not
    the raw actual/expectation first, then scored) so a week where a metric
    hit the clamp at 0 or 100 doesn't get un-clamped by averaging inputs
    before scoring — mirrors how the displayed score is the mean of per-week
    Effort_Scores, not the score of mean inputs. A metric absent from every
    week (e.g. pew when no weekly form was ever submitted) stays excluded,
    same exclusion rule as a single week.
    """
    scaled_sum: dict[str, float] = {}
    actual_sum: dict[str, float] = {}
    exp_sum: dict[str, float] = {}
    counts: dict[str, int] = {}
    weights: dict[str, float] = {}
    for wk in weeks:
        actuals = get_area_effort_actuals_weekly(area, wk)
        if actuals is None:
            continue
        expectations = get_area_effort_expectations_weekly(area, wk)
        for row in compute_effort_score_breakdown(actuals, expectations):
            k = row["metric"]
            scaled_sum[k] = scaled_sum.get(k, 0.0) + row["scaled_score"]
            actual_sum[k] = actual_sum.get(k, 0.0) + row["actual"]
            exp_sum[k]    = exp_sum.get(k, 0.0) + row["expectation"]
            counts[k]     = counts.get(k, 0) + 1
            weights[k]    = row["weight"]

    if not counts:
        return None

    result = []
    for k, n in counts.items():
        avg_scaled = scaled_sum[k] / n
        result.append({
            "metric":       k,
            "actual":       actual_sum[k] / n,
            "expectation":  exp_sum[k] / n,
            "weight":       weights[k],
            "scaled_score": avg_scaled,
            "contribution": avg_scaled * weights[k],
        })
    return result


def _render_leader_line_pie(pie_df: pd.DataFrame, color_map: dict[str, str], title: str):
    """
    A donut chart where EVERY slice gets its own "elbow" callout — a short
    gap off the ring, a diagonal out to an elbow, then a horizontal segment
    that doubles as an underline beneath its label — in a fixed canvas so
    the hand-computed geometry below lines up exactly with the rendered
    slices. Matches the callout style common to modern dashboards (Power BI/
    Highcharts pie label connectors), not a bare radial line.

    Plotly's native `textposition="outside"` only draws a connector line for
    labels it had to nudge to avoid overlapping a neighbor — a big slice's
    label sits flush against the ring with NO line, while a tiny slice next
    to it gets one (Carson, 2026-07-18: "there is not a line on all of
    them"). A first hand-rolled version fixed that but drew the line flush
    against the ring with barely any offset, which read as a rendering
    glitch rather than a deliberate callout (Carson: "this looks like
    garbage... have it go off to the side and underline whatever section
    it's about") — this is the redo: a visible gap, a diagonal, and a real
    underline, colored to match its own slice instead of a flat gray so the
    line reads as clearly "belonging" to that wedge.

    Geometry requires knowing the pie's actual on-screen radius in BOTH x
    and y paper-fraction units (they differ whenever the canvas isn't
    square), which in turn requires a FIXED figure width/height — this is
    why the caller must NOT use `use_container_width=True` for this figure.
    Slice order/angles are calibrated empirically (see the "PIE OUTSIDE-
    LABEL RENDER OK" scratch harness from this session): `sort=False,
    direction="clockwise", rotation=0` renders slice i at cumulative angle
    2*pi*(sum of fractions before i + half of i's own fraction), measured
    clockwise from 12 o'clock — i.e. `theta`, `sin_t = dx`, `cos_t = dy` below
    (paper y grows UP, so +cos is "toward 12 o'clock").

    A slice with 0 contribution has zero angular width — no wedge is drawn
    for it at all — so it's dropped before any of this runs; a leader line
    pointing at a knife-edge with nothing behind it is exactly the kind of
    orphaned label that read as broken in the first place.
    """
    pie_df = pie_df[pie_df["Contribution"] > 0].reset_index(drop=True)

    # W is wider than a "square" pie needs — the longest labels ("At
    # Sacrament Meeting (Pew)", "Baptized & Confirmed (Gate)") need real
    # canvas room to grow into on the side they're anchored from, or they
    # clip against the figure edge. Verified against those exact two labels.
    W, H = 1000, 560
    domain = dict(x=[0.30, 0.70], y=[0.10, 0.92])

    fig = px.pie(
        pie_df,
        names="Metric",
        values="Contribution",
        color="Metric",
        color_discrete_map=color_map,
        hole=0.35,
        title=title,
        hover_data=["Actual", "Expectation"],
    )
    fig.update_traces(
        textinfo="none",
        sort=False,
        direction="clockwise",
        rotation=0,
        domain=domain,
        showlegend=False,  # every slice now carries its own label — a legend would just repeat it
    )
    fig.update_layout(
        width=W, height=H,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=70, b=10),
    )

    dom_w_px = (domain["x"][1] - domain["x"][0]) * W
    dom_h_px = (domain["y"][1] - domain["y"][0]) * H
    radius_px = min(dom_w_px, dom_h_px) / 2
    rx, ry = radius_px / W, radius_px / H
    cx, cy = sum(domain["x"]) / 2, sum(domain["y"]) / 2

    r_gap = 1.06                  # visible breathing room between the ring and where the line starts
    r_bend = 1.24                 # diagonal segment's elbow, before the horizontal underline
    h_len_px = 78                 # underline length in pixels
    underline_y_gap = 0.018       # label sits just above its underline, this far up (paper y-fraction)
    min_y_gap = 0.09              # min vertical spacing between two same-side labels' underlines

    total = pie_df["Contribution"].sum()
    slices: list[dict] = []
    cum = 0.0
    for _, row in pie_df.iterrows():
        frac = row["Contribution"] / total
        theta = 2 * math.pi * (cum + frac / 2)
        cum += frac
        sin_t, cos_t = math.sin(theta), math.cos(theta)
        side = 1 if sin_t >= 0 else -1
        slices.append(dict(
            row=row, frac=frac, side=side,
            gap=(cx + rx * r_gap * sin_t, cy + ry * r_gap * cos_t),
            bend=(cx + rx * r_bend * sin_t, cy + ry * r_bend * cos_t),
            color=color_map[row["Metric"]],
        ))

    # Declutter same-side labels by stacking them vertically (top slice's
    # natural y wins, each one below it gets pushed down at least min_y_gap)
    # rather than pushing them further out radially — for two slices at
    # nearly the same angle (e.g. Pew+Gate both small, next to each other),
    # radial pushback mostly moves them further UP, not apart, driving them
    # straight into the title instead of separating them.
    for side in (1, -1):
        same_side = [s for s in slices if s["side"] == side]
        same_side.sort(key=lambda s: -s["bend"][1])  # topmost (largest y) first
        last_y = None
        for s in same_side:
            y = s["bend"][1]
            if last_y is not None and (last_y - y) < min_y_gap:
                y = last_y - min_y_gap
            last_y = y
            s["label_y"] = y

    for s in slices:
        row, side, color = s["row"], s["side"], s["color"]
        gap_x, gap_y = s["gap"]
        bend_x, bend_y = s["bend"]
        label_y = s["label_y"]
        end_x = bend_x + side * (h_len_px / W)

        path = f"M {gap_x},{gap_y} L {bend_x},{bend_y}"
        if abs(label_y - bend_y) > 1e-6:
            path += f" L {bend_x},{label_y}"  # vertical jog when decluttering moved this label
        path += f" L {end_x},{label_y}"

        fig.add_shape(
            type="path", xref="paper", yref="paper", path=path,
            line=dict(color=color, width=1.5),
        )
        # Small dot anchors the callout to its slice — a common connector
        # affordance (Power BI/Highcharts) that also makes the gap-before-
        # the-line read as deliberate rather than a broken/missing segment.
        fig.add_shape(
            type="circle", xref="paper", yref="paper",
            x0=gap_x - 0.004, x1=gap_x + 0.004,
            y0=gap_y - 0.004 * (W / H), y1=gap_y + 0.004 * (W / H),
            fillcolor=color, line=dict(width=0),
        )

        xanchor = "left" if side > 0 else "right"
        pct = s["frac"] * 100
        fig.add_annotation(
            x=end_x, y=label_y + underline_y_gap, xref="paper", yref="paper",
            text=f"{row['Metric']}<br>{pct:.3g}%",
            showarrow=False, xanchor=xanchor, yanchor="bottom",
            font=dict(color="#9ca3af", family="system-ui, -apple-system", size=12),
            align=xanchor,
        )

    return fig


def _avg_over_window(df: pd.DataFrame) -> pd.DataFrame:
    """One row per area with its scores AVERAGED across every week in `df`
    (which has already been cut down to the selected time range). This is what
    makes the Time Range picker actually move the numbers: the old
    most-recent-week-only collapse showed the same latest week no matter which
    range was picked, since the latest week sits inside all three windows.
    Identity columns (Zone, Missionary_Names, Week_Ending_Date) come from the
    most recent week; `Weeks` says how many weekly rows went into the average.
    """
    if df.empty or "Area_Code" not in df.columns or "Week_Ending_Date" not in df.columns:
        return df
    score_cols = [c for c in NUMERIC_SCORE_COLS if c in df.columns]
    latest = _most_recent_per_area(df).set_index("Area_Code")
    latest[score_cols] = df.groupby("Area_Code")[score_cols].mean()
    latest["Weeks"] = df.groupby("Area_Code")["Week_Ending_Date"].nunique()
    return latest.reset_index()


# ── Config editor helpers ─────────────────────────────────────────────────────

def _get_area_field_weights(
    sec1: pd.DataFrame, area_code: str, component: str
) -> dict[str, float]:
    """Extract field weights for a given area + component from SCORE_CONFIG sec1."""
    defaults = {
        "effort": DEFAULT_EFFORT_WEIGHTS,
        "skill":  DEFAULT_SKILL_WEIGHTS,
        "ki":     DEFAULT_KI_WEIGHTS,
    }.get(component, {})

    if sec1.empty or "Area_Code" not in sec1.columns:
        return dict(defaults)

    mask = (
        (sec1["Area_Code"].str.strip().str.lower() == area_code.lower()) &
        (sec1["Score_Component"].str.strip().str.lower() == component)
    )
    rows = sec1[mask]

    result = dict(defaults)
    for _, r in rows.iterrows():
        active = str(r.get("Active", "TRUE")).strip().upper()
        if active == "FALSE":
            continue
        metric = str(r.get("Metric_Key", "")).strip()
        w = float(r.get("Weight", 0) or 0)
        if metric:
            result[metric] = w

    return result


def _get_area_eff_weights(sec2: pd.DataFrame, area_code: str) -> dict[str, float]:
    """Extract effectiveness sub-weights for a given area from SCORE_CONFIG sec2."""
    if sec2.empty or "Area_Code" not in sec2.columns:
        return dict(DEFAULT_EFF_WEIGHTS)

    mask = sec2["Area_Code"].str.strip().str.lower() == area_code.lower()
    rows = sec2[mask]
    if rows.empty:
        return dict(DEFAULT_EFF_WEIGHTS)

    r = rows.iloc[0]
    return {
        "effort": float(r.get("Effort_Weight", DEFAULT_EFF_WEIGHTS["effort"]) or DEFAULT_EFF_WEIGHTS["effort"]),
        "skill":  float(r.get("Skill_Weight",  DEFAULT_EFF_WEIGHTS["skill"])  or DEFAULT_EFF_WEIGHTS["skill"]),
        "ki":     float(r.get("KI_Weight",     DEFAULT_EFF_WEIGHTS["ki"])     or DEFAULT_EFF_WEIGHTS["ki"]),
    }


def _color_effort_score(val: float) -> str:
    """Effort-only color tiers: green >75, yellow 50-75, red <50 — a
    different boundary than _color_score's 70/50 (used by Skill/KI/
    Effectiveness), per the mission-president Effort rework: exactly meeting
    expectation scores 75, so 75 itself needs to read as the top of yellow,
    not green."""
    if val > 75:
        return f"background-color: {_GREEN}; color: #86efac"
    if val >= 50:
        return f"background-color: {_YELLOW}; color: #fcd34d"
    return f"background-color: {_RED}; color: #fca5a5"


def _apply_mp_effort_and_effectiveness(df: pd.DataFrame, sec2: pd.DataFrame) -> pd.DataFrame:
    """
    Override Effort_Score with the mission-president fixed-expectations
    score (docs/superpowers/specs/2026-07-17-effort-score-rework-design.md),
    and recompute Effectiveness_Score from it. Skill_Score/KI_Score stay
    exactly as AgentScores.gs wrote them. Rows whose new Effort score can't
    be computed (NaN from compute_mission_president_effort_scores) keep
    their original sheet values for both columns untouched.
    """
    if df.empty:
        return df
    new_effort = compute_mission_president_effort_scores(df)
    out = df.copy()
    has_new = new_effort.notna()
    out.loc[has_new, "Effort_Score"] = new_effort[has_new]

    for idx in out.index[has_new]:
        area_code = str(out.at[idx, "Area_Code"])
        w = _get_area_eff_weights(sec2, area_code)
        total_w = w["effort"] + w["skill"] + w["ki"]
        if total_w <= 0:
            continue
        out.at[idx, "Effectiveness_Score"] = (
            out.at[idx, "Effort_Score"] * w["effort"]
            + out.at[idx, "Skill_Score"] * w["skill"]
            + out.at[idx, "KI_Score"] * w["ki"]
        ) / total_w
    return out


def _exp_fingerprint() -> tuple:
    """Every AREA_TYPE_EXPECTATIONS indicator row as a hashable tuple —
    passed into _load_scores_mp_effort purely as a cache key, so saving the
    Goals page's Area Expectation Settings changes the key and the Effort/
    Effectiveness scores recompute on the very next load instead of serving
    the pre-save numbers for up to 5 minutes (Carson, 2026-07-18: edits
    must reach the Effort score immediately)."""
    return tuple(
        (r["category"], r["metric"], r["cadence"], r["value"])
        for r in get_all_area_type_indicators()
    )


@st.cache_data(ttl=300)
def _load_scores_mp_effort(exp_fingerprint: tuple = ()) -> pd.DataFrame:
    """SCORES with Effort_Score/Effectiveness_Score overridden per the
    mission-president Effort rework — the single load point every section of
    this page should use instead of _load_scores() directly. Call it with
    _exp_fingerprint() so a saved expectation edit invalidates the cache."""
    df = _load_scores()
    if df.empty:
        return df
    _, sec2 = _load_score_config()
    return _apply_mp_effort_and_effectiveness(df, sec2)

# ── Analyze's metric label dicts (renamed to avoid colliding with Scores' own
# METRIC_LABELS above) ──────────────────────────────────────────────────────
_ANALYZE_METRIC_LABELS = {
    "nm_lessons":          "NM Lessons",
    "member_lessons":      "Lessons With a Member Participating (MATE)",
    "rc_lessons":          "RC Lessons",
    "la_lessons":          "LA Lessons",
    "lsi_given":           "LSI Given",
    "lsi_followups":       "LSI Follow-ups",
    "new_found":           "New People Being Taught (NEW)",
    "online_referrals":    "Online Referrals",
    "nm_doors":            "NM Attempted",
    "nm_contacted":        "NM Contacted",
    "nm_meaningful":       "NM Meaningful",
    "mmm_sent":            "MMM Sent",
    "la_Attempt":          "LA Attempted",
    "fellowshipper_Attempt": "Fellowshipper Attempted",
    "aux_Attempt":         "Aux Attempted",
    "info_Attempt":        "Info Attempted",
    "locos_Attempt":       "LOCOS Attempted",
    "referrals_today":     "Referrals Today",
    "nm_texts":            "NM Texts",
}

# Projection dropdown covers every metric — the nightly-form metrics above PLUS
# the weekly-form KI metrics (pew/date/gate/renew/rc_total), which project from
# WEEKLY_FORM_RAW. Weekly-form ones are suffixed so it's clear which form drives
# them. (The anomaly section still uses _ANALYZE_METRIC_LABELS only — weekly-form metrics
# have no area-level history to flag anomalies against.)
_ANALYZE_PROJECTION_METRIC_LABELS = {
    **_ANALYZE_METRIC_LABELS,
    "pew":         "People at Sacrament Meeting (PEW) — Weekly Form",
    "date_metric": "Baptismal Date (DATE) — Weekly Form",
    "gate":        "Baptized & Confirmed (GATE) — Weekly Form",
    "renew":       "New Members at Sacrament Meeting (RENEW) — Weekly Form",
    "rc_total":    "RC Total (Weekly Form)",
}

# ── Daily Activity's metric groups + cached loaders ────────────────────────────
# ── Metric groups derived from active flavor ───────────────────────────────────
_DA_METRIC_LABELS = _FLAVOR_METRIC_LABELS  # global lookup for all 19 metrics

_groups = flavor.metric_groups
_LESSON_COLS  = _groups.get("Teaching",         ["nm_lessons", "member_lessons", "rc_lessons", "la_lessons"])
_FINDING_COLS = _groups.get("Finding",          ["new_found", "online_referrals", "referrals_today"])
_CONTACT_COLS = _groups.get("Contacting",       ["nm_doors", "nm_contacted", "nm_meaningful"])
_LSI_COLS     = _groups.get("Member Work",      ["lsi_given", "lsi_followups"])
_DOOR_COLS    = _groups.get("Support Attempts", ["la_Attempt", "fellowshipper_Attempt", "aux_Attempt", "info_Attempt", "locos_Attempt"])
_EFFORT_COLS  = []  # populated from get_effort_data if present

# ── Cached loaders ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _load_daily(days: int) -> pd.DataFrame:
    return get_daily_log(days)


@st.cache_data(ttl=300)
def _load_zones() -> list:
    return get_zones()


@st.cache_data(ttl=300)
def _load_districts(zone: str) -> list:
    return get_districts(zone)


@st.cache_data(ttl=300)
def _load_effort() -> pd.DataFrame:
    try:
        return get_effort_data()
    except Exception:
        return pd.DataFrame()


# Filled in once the Scores tab knows its own scope (title mirrors Zone/
# District/Area/Mission — Carson, 2026-07-24). A plain call here would show a
# static title before that scope is known; st.empty() reserves the slot at
# the top of the page while the real title renders further down, inside
# _render_scores_tab(), after render_scope_selectors() returns `_level`.
_header_slot = st.empty()
with _header_slot.container():
    render_page_header("Area Scores", f"{get_config_value('MISSION_NAME', flavor.display_name)} — weekly computed performance scores per area", icon="")


def _render_scores_tab():
    # ── Load data ─────────────────────────────────────────────────────────────────

    scores_df = _load_scores_mp_effort(_exp_fingerprint())
    sec1, sec2 = _load_score_config()

    try:
        areas_df    = get_areas_df(active_only=True)
        zones_list  = get_zones()
        area_names  = sorted(
            areas_df["Area_Name"].dropna().astype(str).unique().tolist()
        ) if not areas_df.empty and "Area_Name" in areas_df.columns else []
    except Exception as _e:
        areas_df   = pd.DataFrame()
        zones_list = []
        area_names = []

    # ── Empty state ───────────────────────────────────────────────────────────────

    if scores_df.empty:
        # No scope is known yet (the selectors never render below), so the
        # title falls back to the mission-wide label.
        with _header_slot.container():
            render_page_header("Mission Scores", f"{get_config_value('MISSION_NAME', flavor.display_name)} — weekly computed performance scores per area", icon="")
        st.info(
            "No scores have been computed yet. Scores are calculated automatically "
            "each Sunday at 11 PM Mountain Time. Run computeAllAreaScores() in "
            "Apps Script to compute scores immediately."
        )
        return

    # The most recent week ANY area has a computed score for, regardless of the
    # Time Range filter below — powers the "why is this empty" messages further
    # down (Carson, 2026-07-24: "Last 7 Days" going completely blank with no
    # explanation when the weekly AgentScores run is late/skipped and every
    # score is older than 7 days).
    _latest_computed_week = (
        scores_df["Week_Ending_Date"].astype(str).str[:10].max()
        if "Week_Ending_Date" in scores_df.columns and not scores_df.empty else ""
    )

    def _stale_range_hint(time_range: str) -> str:
        if not _latest_computed_week:
            return ""
        return (
            f" The most recently computed week is {_latest_computed_week} — "
            f"outside {time_range}. Try Transfer to Date or All Time, or confirm "
            "AgentScores ran on schedule (Sundays, 11 PM Mountain Time)."
        )

    # ═══════════════════════════════════════════════════════════════════════════════
    # SCOPE + TIME FILTERS
    # ═══════════════════════════════════════════════════════════════════════════════

    # One-click way back to the mission-wide view (Carson, 2026-07-24) — clears
    # all three cascading selectors at once, instead of resetting each one
    # individually. Sits above the dropdowns it clears.
    if st.button(
        "Mission Score", key="sc_mission_reset",
        help="Clear Zone/District/Area/missionary and show the mission-wide view",
    ):
        st.session_state["sc_zone_val"] = SCOPE_ANY
        st.session_state["sc_district_val"] = SCOPE_ANY
        st.session_state["sc_area_val"] = SCOPE_ANY

    # Same cascading Zone → District → Area → Find-by-missionary selectors as the
    # Breakdowns page (app/components/scope_selector.py), deepest selection wins.
    # Nothing selected = the whole mission. `prefix="sc"` keeps this page's picks
    # separate from Breakdowns'.
    _scope_areas_all = get_submitting_areas()
    sel_zone, sel_district, sel_area, _level = render_scope_selectors(
        _scope_areas_all, prefix="sc", zones=zones_list or None,
    )

    # Backfill the title reserved at the top of the page, now that the scope is
    # known — Zone/District/Area Scores while drilled in, Mission Scores while
    # nothing is picked (which is also where the Mission Score button above
    # lands you).
    _page_title = (
        "Area Scores" if _level == "area"
        else "District Scores" if _level == "district"
        else "Zone Scores" if _level == "zone"
        else "Mission Scores"
    )
    with _header_slot.container():
        render_page_header(_page_title, f"{get_config_value('MISSION_NAME', flavor.display_name)} — weekly computed performance scores per area", icon="")

    # ═══════════════════════════════════════════════════════════════════════════════
    # MISSION SCORE — mission-wide composite, most recent week per area. Shows
    # ONLY while nothing is selected (Carson, 2026-07-24): once a Zone/District/
    # Area is picked, the chart and table below already switch to that scope's
    # own numbers, so this would just be redundant clutter at that point.
    # ═══════════════════════════════════════════════════════════════════════════════

    if _level is None:
        # The Time Range widget renders further down the page, but its picked
        # value survives in session_state across reruns, so these cards can
        # follow it from up here. First load (no pick yet) uses the widget's
        # own default.
        _ms_range = st.session_state.get("time_range", "Last 7 Days")
        _ms_latest = _avg_over_window(_filter_by_time(_load_scores_mp_effort(_exp_fingerprint()), _ms_range))
        if not _ms_latest.empty:
            def _ms_avg(col: str) -> str:
                if col not in _ms_latest.columns:
                    return "—"
                return f"{pd.to_numeric(_ms_latest[col], errors='coerce').fillna(0).mean():.1f}"

            render_section_label(f"Mission Score — Average Across All Areas ({_ms_range})")
            render_kpi_row([
                {"label": "Mission Effectiveness", "value": _ms_avg("Effectiveness_Score")},
                {"label": "Effort",               "value": _ms_avg("Effort_Score")},
                {"label": "Skill",                "value": _ms_avg("Skill_Score")},
                {"label": "KI",                   "value": _ms_avg("KI_Score")},
            ])
        else:
            render_section_label(f"Mission Score — Average Across All Areas ({_ms_range})")
            st.info(f"No scores fall inside {_ms_range}." + _stale_range_hint(_ms_range))

    _tcol, _, _ = st.columns(3)
    with _tcol:
        time_range = st.selectbox(
            "Time Range",
            options=["Last 7 Days", "Transfer to Date", "All Time"],
            key="time_range",
        )

    st.divider()

    # ── Apply filters ─────────────────────────────────────────────────────────────

    _scope_names = _scope_area_names(_scope_areas_all, _level, sel_zone, sel_district, sel_area)
    filtered_df = _filter_by_time(scores_df, time_range)
    filtered_df = _filter_by_scope(filtered_df, _scope_names)
    # Average across the window's weeks — NOT most-recent-week-only, which made
    # every Time Range option display identical numbers (the latest week is inside
    # all three windows).
    display_df  = _avg_over_window(filtered_df)

    # ── Sort by Effectiveness descending ──────────────────────────────────────────

    if not display_df.empty and "Effectiveness_Score" in display_df.columns:
        display_df = display_df.sort_values("Effectiveness_Score", ascending=False)

    # Computed once, ahead of both sections below: the chart title needs it first
    # now that the chart renders above the table.
    if _level == "area":
        scope_label = f"Area: {sel_area}"
    elif _level == "district":
        scope_label = f"District: {sel_district}"
    elif _level == "zone":
        scope_label = f"Zone: {sel_zone}"
    else:
        scope_label = "Mission-Wide"

    # Moved to sit right above the graph (Carson, 2026-07-17) — was up by the
    # Mission Score cards at the top of the page, far from the chart it explains.
    # Green cutoff is 75 here (Carson, 2026-07-18) — the Effectiveness bar chart's
    # OWN threshold, chosen independent of _color_score's 70/50 (still used by the
    # Skill/KI columns and the Score Summary table below).
    render_section_label("Score Tier Key")
    render_status_pill("≥ 75  Strong", "green")
    render_status_pill("50–74  Developing", "amber")
    render_status_pill("< 50  Needs Attention", "red")

    # ═══════════════════════════════════════════════════════════════════════════════
    # CHART — Effectiveness by Area, or (single-area drill-in) Effort Score
    # Breakdown — a pie of what's actually contributing to THIS area's Effort
    # score, since a one-bar "Effectiveness by Area" chart carries no signal once
    # scope narrows to a single area (Carson, 2026-07-18).
    # ═══════════════════════════════════════════════════════════════════════════════

    if _level == "area":
        render_section_label(f"Effort Score Breakdown — {sel_area}")

        # Same weeks _avg_over_window averaged Effort_Score across for this area
        # (filtered_df is time+scope filtered, one row per week, ahead of that
        # collapse) — so changing Time Range, or new data landing for the
        # in-range weeks, moves the pie exactly the way it moves the Effort
        # number next to it, instead of the pie staying pinned to one fixed week.
        _pie_weeks: list[str] = []
        if not filtered_df.empty and "Week_Ending_Date" in filtered_df.columns:
            _pie_weeks = sorted(
                filtered_df["Week_Ending_Date"].astype(str).str[:10].unique().tolist()
            )

        # Fixed metric order + color, same every area/week — color follows the
        # metric, never its share of that week's pie, so nm_lessons is always the
        # same hue whether it's the biggest slice or the smallest.
        _pie_metric_order = ["nm_lessons", "new_found", "mmm_sent", "pew", "gate"]

        _breakdown = _avg_effort_breakdown(sel_area, _pie_weeks)

        if not _breakdown:
            st.info("No Effort data available for this area in the selected Time Range.")
        else:
            _by_metric = {row["metric"]: row for row in _breakdown}
            _pie_metrics = [m for m in _pie_metric_order if m in _by_metric]
            _color_map = {
                METRIC_LABELS.get(m, m): series_style(i)[0]
                for i, m in enumerate(_pie_metric_order)
            }

            pie_df = pd.DataFrame({
                "Metric":       [METRIC_LABELS.get(m, m) for m in _pie_metrics],
                "Contribution": [_by_metric[m]["contribution"] for m in _pie_metrics],
                "Actual":       [round(_by_metric[m]["actual"], 1) for m in _pie_metrics],
                "Expectation":  [round(_by_metric[m]["expectation"], 1) for m in _pie_metrics],
            })

            fig = _render_leader_line_pie(
                pie_df, _color_map, f"Effort Score Breakdown — {sel_area} ({time_range})"
            )

            # NOT use_container_width — the leader-line geometry in
            # _render_leader_line_pie is computed against its own fixed
            # width/height, so letting Streamlit stretch the figure to the
            # container would throw every line off-slice.
            st.plotly_chart(fig, use_container_width=False)
            st.caption(
                f"Each slice is that metric's average share of this area's weekly "
                f"Effort score across {len(_pie_weeks)} week(s) in {time_range} "
                "(actual vs. expectation, weighted nm_lessons 30% · new_found 25% "
                "· mmm_sent 20% · pew 15% · gate 10%) — not raw activity volume."
            )
    else:
        render_section_label("Effectiveness Score by Area")

        if display_df.empty:
            st.info("No data to chart." + _stale_range_hint(time_range))
        else:
            chart_df = display_df[
                ["Area_Name", "Zone", "Effectiveness_Score"]
            ].copy().sort_values("Effectiveness_Score", ascending=False)

            # Color bars by threshold — 75 (not _color_score's 70) is this chart's own
            # green cutoff (Carson, 2026-07-18), matching the Score Tier Key above it.
            chart_df["_color"] = chart_df["Effectiveness_Score"].apply(
                lambda v: "75+" if v >= 75 else ("50-74" if v >= 50 else "Below 50")
            )

            color_map = {"75+": "#16a34a", "50-74": "#ca8a04", "Below 50": "#dc2626"}

            fig = px.bar(
                chart_df,
                x="Area_Name",
                y="Effectiveness_Score",
                color="_color",
                color_discrete_map=color_map,
                labels={
                    "Area_Name":           "Area",
                    "Effectiveness_Score": "Effectiveness Score",
                    "_color":              "Score Range",
                },
                title=f"Effectiveness Score — {scope_label} ({time_range})",
                hover_data={"Zone": True, "_color": False},
            )

            fig.update_layout(
                xaxis_tickangle=-45,
                yaxis_range=[0, 105],
                legend_title_text="Score Range",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )

            fig.add_hline(y=75, line_dash="dot", line_color="#16a34a", annotation_text="75 (Good)")
            fig.add_hline(y=50, line_dash="dot", line_color="#ca8a04", annotation_text="50 (Needs Work)")

            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════════
    # SCORE TABLE
    # ═══════════════════════════════════════════════════════════════════════════════

    render_section_label("Score Summary")

    st.caption(
        f"{scope_label}  |  {time_range}  |  "
        f"{len(display_df)} area(s) shown  |  Scores averaged across each area's weeks in this range"
    )

    st.caption(
        "Effort uses its own tiers — meeting the mission president's weekly "
        "expectations exactly scores 75, so its bar is green above 75, "
        "yellow 50–75, red below 50 (Skill/KI/Effectiveness keep 70/50)."
    )

    if display_df.empty:
        st.info("No scores match the current filters." + _stale_range_hint(time_range))
    else:
        # Build display subset with friendly column names
        table_cols_raw  = ["Area_Name", "Zone", "Missionary_Names", "Week_Ending_Date", "Weeks"] + NUMERIC_SCORE_COLS
        table_cols      = [c for c in table_cols_raw if c in display_df.columns]
        table_df        = display_df[table_cols].copy()

        # Rename to friendly labels
        rename_map = {
            "Area_Name":           "Area",
            "Zone":                "Zone",
            "Missionary_Names":    "Missionaries",
            # Scores are averaged over the range; this column shows the newest week
            # that went into the average, and Weeks says how many did.
            "Week_Ending_Date":    "Latest Week",
            "Weeks":               "Weeks",
            "Effort_Score":        "Effort",
            "Skill_Score":         "Skill",
            "KI_Score":            "KI",
            "Effectiveness_Score": "Effectiveness",
        }
        table_df = table_df.rename(columns={k: v for k, v in rename_map.items() if k in table_df.columns})

        # Leading Rating column — one colored circle per area, at a glance, keyed off
        # the same Effectiveness thresholds as the Score Tier Key above the chart.
        # display_df and table_df share an index (table_df is display_df[cols].copy()),
        # so this lines up row-for-row without a join.
        if "Effectiveness_Score" in display_df.columns:
            table_df.insert(0, "Rating", display_df["Effectiveness_Score"].apply(_tier_circle))
        else:
            table_df.insert(0, "Rating", "—")

        # Score columns after rename
        score_display_cols = [v for k, v in rename_map.items() if k in NUMERIC_SCORE_COLS and v in table_df.columns]

        def _make_style_cell(color_fn):
            def _style_cell(val: Any) -> str:
                try:
                    fval = float(val)
                except (TypeError, ValueError):
                    return ""
                return color_fn(fval)
            return _style_cell

        # Base style every cell explicitly so non-score columns (Area, Zone, etc.)
        # don't render dark-on-dark; score columns then override with tier colors.
        # Effort uses its own 75/50 tiers (mission-president rework); Skill/KI/
        # Effectiveness keep the original 70/50 tiers via _color_score.
        styler = table_df.style.set_properties(
            **{"background-color": "#1E2D3D", "color": "#FFFFFF"}
        )
        for col in score_display_cols:
            color_fn = _color_effort_score if col == "Effort" else _color_score
            styler = styler.map(_make_style_cell(color_fn), subset=[col])  # type: ignore[arg-type]

        # Format score columns to 1 decimal
        format_dict = {col: "{:.1f}" for col in score_display_cols}
        styler = styler.format(format_dict, na_rep="—")

        render_table(styler)

        # ── Color legend ──────────────────────────────────────────────────────────
        legend_cols = st.columns(3)
        with legend_cols[0]:
            st.markdown(
                f'<span style="background:{_GREEN};color:#86efac;padding:2px 8px;border-radius:4px;">'
                "Strong — 70+</span>",
                unsafe_allow_html=True,
            )
        with legend_cols[1]:
            st.markdown(
                f'<span style="background:{_YELLOW};color:#fcd34d;padding:2px 8px;border-radius:4px;">'
                "Developing — 50–69</span>",
                unsafe_allow_html=True,
            )
        with legend_cols[2]:
            st.markdown(
                f'<span style="background:{_RED};color:#fca5a5;padding:2px 8px;border-radius:4px;">'
                "Needs Attention — below 50</span>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════════
    # RECALCULATE INFO
    # ═══════════════════════════════════════════════════════════════════════════════

    st.info(
        "Scores are automatically recomputed each Sunday at 11 PM Mountain Time by the "
        "AgentScores Apps Script engine. To trigger an immediate recalculation, open the "
        "Google Apps Script editor for COMPASS_CCSM and run computeAllAreaScores()."
    )

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════════
    # SCORE WEIGHT EDITOR
    # ═══════════════════════════════════════════════════════════════════════════════

    # Full metric universe per component. Effort and Skill both draw from the nightly
    # (daily) form, so either component can weight any of those metrics. KI draws from
    # the weekly form. A weight of 0 means the metric simply doesn't count.
    DAILY_UNIVERSE = list(DEFAULT_EFFORT_WEIGHTS.keys())   # all 19 nightly-form metrics
    KI_UNIVERSE    = list(DEFAULT_KI_WEIGHTS.keys())        # all weekly KI metrics


    def _component_weights(area_code: str, component: str,
                           universe: list[str], default_map: dict[str, float]) -> dict[str, float]:
        """Current weight for every metric in `universe`, pulling saved config first
        then the component default (0 if neither)."""
        saved = _get_area_field_weights(sec1, area_code, component)
        return {k: float(saved.get(k, default_map.get(k, 0.0))) for k in universe}


    def _render_weight_inputs(component: str, weights: dict[str, float],
                              default_map: dict[str, float], area_code: str,
                              ncols: int = 2) -> dict[str, float]:
        """
        Render one labeled number_input per metric and return {metric_key: weight}.

        Replaces st.data_editor, whose canvas cells rendered dark-on-dark (looked
        empty) and white-on-white while typing in this dark-glass themed app.
        number_input uses the app's standard dark input style with white text, so
        every metric and every keystroke is visible. The area_code is folded into
        each widget key so switching area/scope reloads the correct values.
        """
        result: dict[str, float] = {}
        keys = list(weights.keys())
        cols = st.columns(ncols)
        for i, k in enumerate(keys):
            rec = default_map.get(k, weights[k])
            with cols[i % ncols]:
                result[k] = st.number_input(
                    f"{METRIC_LABELS.get(k, k)}  ·  rec {rec:g}",
                    min_value=0.0, max_value=100.0, step=0.5,
                    value=float(weights[k]),
                    format="%.1f",
                    key=f"w_{component}_{k}_{area_code}",
                )
        return result


    def _rewrite_score_config(area_code: str,
                              edited_by_component: list[tuple[str, dict[str, float]]],
                              eff_w: tuple[float, float, float],
                              cur_sec1: pd.DataFrame,
                              cur_sec2: pd.DataFrame) -> int:
        """
        Rebuild SCORE_CONFIG cleanly: preserve every OTHER area's rows, replace this
        area's rows with the edited values, and write both sections back in one batch
        (header1 / field-weight rows / blank separator / header2 / sub-weight rows).

        Replaces the old append-based save, which appended field-weight rows below the
        section separator where the engine misread them as effectiveness sub-weights.
        """
        sec1_h = ["Area_Code", "Metric_Key", "Score_Component", "Weight", "Active"]
        sec2_h = ["Area_Code", "Effort_Weight", "Skill_Weight", "KI_Weight", ""]
        code_l = str(area_code).strip().lower()

        def _pad(row: list) -> list:
            return (row + [""] * 5)[:5]

        # Section 1 — keep other areas, drop this area, then add edited rows.
        sec1_rows: list[list] = []
        if not cur_sec1.empty:
            for _, r in cur_sec1.iterrows():
                if str(r.get("Area_Code", "")).strip().lower() == code_l:
                    continue
                sec1_rows.append([
                    str(r.get("Area_Code", "")).strip(),
                    str(r.get("Metric_Key", "")).strip(),
                    str(r.get("Score_Component", "")).strip(),
                    float(pd.to_numeric(r.get("Weight", 0), errors="coerce") or 0),
                    str(r.get("Active", "TRUE")).strip() or "TRUE",
                ])
        for component, weights in edited_by_component:
            for key, weight in weights.items():
                if not key:
                    continue
                sec1_rows.append([area_code, key, component, float(weight or 0), "TRUE"])

        # Section 2 — keep other areas, drop this area, then add edited sub-weights.
        sec2_rows: list[list] = []
        if not cur_sec2.empty:
            for _, r in cur_sec2.iterrows():
                if str(r.get("Area_Code", "")).strip().lower() == code_l:
                    continue
                sec2_rows.append([
                    str(r.get("Area_Code", "")).strip(),
                    float(pd.to_numeric(r.get("Effort_Weight", 0), errors="coerce") or 0),
                    float(pd.to_numeric(r.get("Skill_Weight", 0), errors="coerce") or 0),
                    float(pd.to_numeric(r.get("KI_Weight", 0), errors="coerce") or 0),
                    "",
                ])
        sec2_rows.append([area_code, round(eff_w[0], 4), round(eff_w[1], 4), round(eff_w[2], 4), ""])

        grid = [sec1_h]
        grid += [_pad(r) for r in sec1_rows]
        grid += [["", "", "", "", ""]]
        grid += [sec2_h]
        grid += [_pad(r) for r in sec2_rows]

        overwrite_tab("SCORE_CONFIG", grid)
        return len(sec1_rows) + 1


    with st.expander("Edit Score Weights", expanded=False):
        st.markdown(
            "**How the Effectiveness score is built.** Each area's Effectiveness score is a "
            "blend of three components — **Effort**, **Skill**, and **Key Indicators (KI)**. "
            "Set how much each component counts in *Component Mix* below, then fine-tune every "
            "individual metric (lessons, contacts, referrals, door attempts, weekly KIs, etc.) "
            "inside each component tab."
        )

        # ── Scope selector: whole mission or a single area ────────────────────────
        cfg_area_options = [MISSION_WIDE_LABEL] + (area_names if area_names else sorted(
            scores_df["Area_Name"].dropna().astype(str).unique().tolist()
        ))

        cfg_area = st.selectbox(
            "Apply weights to",
            options=cfg_area_options,
            key="cfg_area",
            help="Choose 'Whole Mission' to set one baseline for every area, or pick a single "
                 "area to override it. Area-specific weights win over the mission baseline.",
        )

        is_mission_wide = (cfg_area == MISSION_WIDE_LABEL)

        if is_mission_wide:
            cfg_area_code = MISSION_WIDE_CODE
            st.info(
                "Editing the **mission-wide baseline**. These weights apply to every area "
                "unless that area has its own override.",
                icon=None,
            )
        else:
            # Resolve area code from MISSION_ORG
            cfg_area_code = cfg_area
            if not areas_df.empty and "Area_Name" in areas_df.columns:
                match = areas_df[areas_df["Area_Name"] == cfg_area]
                if not match.empty:
                    code_col = "Area_ID" if "Area_ID" in match.columns else "Area_Name"
                    cfg_area_code = str(match.iloc[0][code_col]).strip()
            st.markdown(f"**Area Code:** `{cfg_area_code}`")

        # ── Component mix (effectiveness sub-weights) ─────────────────────────────
        st.markdown("##### Component Mix")
        st.caption(
            "How much each component counts toward Effectiveness. Must sum to 1.0 "
            "(e.g. Effort 0.30 + Skill 0.30 + KI 0.40)."
        )

        current_eff = _get_area_eff_weights(sec2, cfg_area_code)

        eff_col1, eff_col2, eff_col3 = st.columns(3)
        with eff_col1:
            eff_effort = st.number_input(
                "Effort Weight",
                min_value=0.0, max_value=1.0, step=0.05,
                value=float(current_eff["effort"]),
                format="%.2f",
                key="eff_effort",
            )
        with eff_col2:
            eff_skill = st.number_input(
                "Skill Weight",
                min_value=0.0, max_value=1.0, step=0.05,
                value=float(current_eff["skill"]),
                format="%.2f",
                key="eff_skill",
            )
        with eff_col3:
            eff_ki = st.number_input(
                "KI Weight",
                min_value=0.0, max_value=1.0, step=0.05,
                value=float(current_eff["ki"]),
                format="%.2f",
                key="eff_ki",
            )

        eff_sum = round(eff_effort + eff_skill + eff_ki, 4)
        if abs(eff_sum - 1.0) > 0.001:
            st.warning(f"Component mix must sum to 1.0 (currently {eff_sum:.4f}).")
            eff_valid = False
        else:
            st.success(f"Component mix sums to {eff_sum:.2f}")
            eff_valid = True

        # ── Per-metric weights ────────────────────────────────────────────────────
        st.markdown("##### Metric Weights")
        st.caption(
            "Every metric from the nightly and weekly forms, with the weight it carries. "
            "Each box label shows the recommended baseline (rec). A weight of 0 means the "
            "metric doesn't count. The engine normalises by component total, so relative "
            "proportions are what matter."
        )

        tab_effort, tab_skill, tab_ki = st.tabs(
            ["Effort Metrics", "Skill Metrics", "Key Indicator Metrics"]
        )

        with tab_effort:
            st.caption(
                "Legacy / unused — the Effort score is now computed from the "
                "mission president's fixed weekly expectations per area type, "
                "not these per-metric weights. Kept for reference only."
            )
            edited_effort = _render_weight_inputs(
                "effort",
                _component_weights(cfg_area_code, "effort", DAILY_UNIVERSE, DEFAULT_EFFORT_WEIGHTS),
                DEFAULT_EFFORT_WEIGHTS, cfg_area_code,
            )

        with tab_skill:
            st.caption("Nightly-form quality signals — how effectively the area is working. "
                       "Metrics left at 0 don't count toward Skill.")
            edited_skill = _render_weight_inputs(
                "skill",
                _component_weights(cfg_area_code, "skill", DAILY_UNIVERSE, DEFAULT_SKILL_WEIGHTS),
                DEFAULT_SKILL_WEIGHTS, cfg_area_code,
            )

        with tab_ki:
            st.caption("Weekly-form Key Indicators — Pew, Date, Gate, Renew, RC.")
            edited_ki = _render_weight_inputs(
                "ki",
                _component_weights(cfg_area_code, "ki", KI_UNIVERSE, DEFAULT_KI_WEIGHTS),
                DEFAULT_KI_WEIGHTS, cfg_area_code,
            )

        # ── Save button ───────────────────────────────────────────────────────────
        st.markdown("---")

        if st.button(
            "Save Config",
            type="primary",
            disabled=not eff_valid,
            key="save_score_config",
        ):
            try:
                saved = _rewrite_score_config(
                    cfg_area_code,
                    [("effort", edited_effort), ("skill", edited_skill), ("ki", edited_ki)],
                    (eff_effort, eff_skill, eff_ki),
                    sec1, sec2,
                )
                _load_score_config.clear()

                scope_txt = (
                    "the **whole mission**" if is_mission_wide
                    else f"**{cfg_area}** (`{cfg_area_code}`)"
                )
                st.success(
                    f"Saved {saved} weight rows for {scope_txt}. "
                    "The new weights take effect on the next scoring run "
                    "(Sunday 11 PM MT, or run computeAllAreaScores() now)."
                )
            except Exception as save_err:
                st.error(f"Failed to save config: {save_err}")


def _render_daily_tab():
    # ── Top control: number of days displayed ──────────────────────────────────────
    ctrl_col, _spacer = st.columns([1, 3])
    with ctrl_col:
        days = st.number_input(
            "Days displayed",
            min_value=1, max_value=120, value=14, step=1,
            key="da_days",
            help="How many days of nightly-form data to show on this page.",
        )
    window_label = f"last {int(days)} days"

    df = _load_daily(int(days))

    if df.empty:
        st.info("No daily activity data yet. Re-run the data refresh to populate this page.")
        return

    # Zone/District filter
    all_zones = _load_zones()
    zone_options = ["All"] + all_zones
    _da_f1, _da_f2 = st.columns(2)
    with _da_f1:
        selected_zone = st.selectbox("Zone", zone_options, key="da_zone")

    if selected_zone != "All":
        df = df[df["Zone"] == selected_zone].copy() if "Zone" in df.columns else df

        district_options = ["All"] + _load_districts(selected_zone)
        with _da_f2:
            selected_district = st.selectbox("District", district_options, key="da_district")
        if selected_district != "All":
            df = df[df["District"] == selected_district].copy() if "District" in df.columns else df

    if df.empty:
        st.info("No data for the selected filters.")
        return

    # ── Present metric columns ─────────────────────────────────────────────────────
    _ALL_METRIC_GROUPS = _LESSON_COLS + _FINDING_COLS + _CONTACT_COLS + _LSI_COLS + _DOOR_COLS
    present = [c for c in _ALL_METRIC_GROUPS if c in df.columns]

    def _col_sum(col: str) -> int:
        return int(df[col].sum()) if col in df.columns else 0

    # ═══════════════════════════════════════════════════════════════════════════════
    # MISSION TOTALS ROW
    # ═══════════════════════════════════════════════════════════════════════════════
    render_section_label(f"Mission Totals — {window_label}")

    nm_total      = _col_sum("nm_lessons")
    found_total   = sum(_col_sum(c) for c in _FINDING_COLS)
    contact_total = _col_sum("nm_contacted")
    lsi_total     = _col_sum("lsi_given")
    doors_total   = _col_sum("nm_doors")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("NM Lessons",       nm_total)
    m2.metric("New People Found", found_total)
    m3.metric("NM Contacted",     contact_total)
    m4.metric("LSI Given",        lsi_total)
    m5.metric("NM Attempted",     doors_total)

    render_section_label("Activity by Category")

    # ═══════════════════════════════════════════════════════════════════════════════
    # TABS
    # ═══════════════════════════════════════════════════════════════════════════════
    tab_lessons, tab_finding, tab_contacts, tab_lsi, tab_effort = st.tabs([
        "Lessons", "Finding", "Contacts", "LSI & Attempts", "Effort"
    ])


    def _daily_bar(df_in: pd.DataFrame, col: str, title: str) -> go.Figure:
        """Return a simple daily bar chart for a single metric column."""
        if "Date" not in df_in.columns or col not in df_in.columns:
            return go.Figure()
        daily = (
            df_in.groupby("Date")[col]
            .sum()
            .reset_index()
            .sort_values("Date")
        )
        fig = go.Figure(go.Bar(
            x=daily["Date"],
            y=daily[col],
            marker_color=CHART_COLORS[0],
            name=_DA_METRIC_LABELS.get(col, col),
        ))
        fig.update_layout(
            title=title,
            xaxis_title="Date",
            xaxis_type="category",
            yaxis_title=_DA_METRIC_LABELS.get(col, col),
            hovermode="x unified",
            margin=dict(t=50, b=50, l=50, r=20),
        )
        return fig


    def _area_breakdown(df_in: pd.DataFrame, col: str) -> pd.DataFrame:
        """Summarise a metric by area, sorted descending."""
        if "Area" not in df_in.columns or col not in df_in.columns:
            return pd.DataFrame()
        return (
            df_in.groupby("Area")[col]
            .sum()
            .reset_index()
            .rename(columns={"Area": "Area", col: _DA_METRIC_LABELS.get(col, col)})
            .sort_values(_DA_METRIC_LABELS.get(col, col), ascending=False)
        )


    def _summary_metrics(df_in: pd.DataFrame, cols: list) -> None:
        """Render a row of st.metric for each present column."""
        present_cols = [c for c in cols if c in df_in.columns]
        if not present_cols:
            st.info("No data for this category.")
            return
        metric_cols = st.columns(len(present_cols))
        for i, col in enumerate(present_cols):
            metric_cols[i].metric(_DA_METRIC_LABELS.get(col, col), int(df_in[col].sum()))


    # ── Lessons tab ────────────────────────────────────────────────────────────────
    with tab_lessons:
        render_section_label("Lessons Summary")
        _summary_metrics(df, _LESSON_COLS)

        primary = "nm_lessons"
        if primary in df.columns:
            st.plotly_chart(
                _daily_bar(df, primary, f"NM Lessons per Day — {window_label}"),
                use_container_width=True,
            )

            # Multi-line all lesson types
            lesson_present = [c for c in _LESSON_COLS if c in df.columns]
            if lesson_present and "Date" in df.columns:
                lesson_daily = (
                    df.groupby("Date")[lesson_present]
                    .sum()
                    .reset_index()
                    .sort_values("Date")
                )
                fig_multi = go.Figure()
                for i, col in enumerate(lesson_present):
                    fig_multi.add_trace(go.Scatter(
                        x=lesson_daily["Date"],
                        y=lesson_daily[col],
                        mode="lines+markers",
                        name=_DA_METRIC_LABELS.get(col, col),
                        line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2),
                        marker=dict(size=5),
                    ))
                fig_multi.update_layout(
                    title=f"All Lesson Types — Daily — {window_label}",
                    xaxis_title="Date",
                    yaxis_title="Count",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(t=60, b=50, l=50, r=20),
                )
                st.plotly_chart(fig_multi, use_container_width=True)

        area_tbl = _area_breakdown(df, primary)
        if not area_tbl.empty:
            st.caption("By-area totals")
            render_table(area_tbl)


    # ── Finding tab ────────────────────────────────────────────────────────────────
    with tab_finding:
        render_section_label("Finding Summary")
        _summary_metrics(df, _FINDING_COLS)

        primary = "new_found"
        finding_present = [c for c in _FINDING_COLS if c in df.columns]
        if finding_present and "Date" in df.columns:
            find_daily = (
                df.groupby("Date")[finding_present]
                .sum()
                .reset_index()
                .sort_values("Date")
            )
            fig_find = go.Figure()
            for i, col in enumerate(finding_present):
                fig_find.add_trace(go.Bar(
                    x=find_daily["Date"],
                    y=find_daily[col],
                    name=_DA_METRIC_LABELS.get(col, col),
                    marker_color=CHART_COLORS[i % len(CHART_COLORS)],
                ))
            fig_find.update_layout(
                title=f"Finding Metrics — Daily — {window_label}",
                xaxis_title="Date",
                yaxis_title="Count",
                barmode="stack",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=50, l=50, r=20),
            )
            st.plotly_chart(fig_find, use_container_width=True)

        if primary in df.columns:
            area_tbl = _area_breakdown(df, primary)
            if not area_tbl.empty:
                st.caption("New People Found — by area")
                render_table(area_tbl)


    # ── Contacts tab ───────────────────────────────────────────────────────────────
    with tab_contacts:
        render_section_label("Contacts Summary")
        _summary_metrics(df, _CONTACT_COLS)

        contact_present = [c for c in _CONTACT_COLS if c in df.columns]
        if contact_present and "Date" in df.columns:
            cont_daily = (
                df.groupby("Date")[contact_present]
                .sum()
                .reset_index()
                .sort_values("Date")
            )
            fig_cont = go.Figure()
            for i, col in enumerate(contact_present):
                fig_cont.add_trace(go.Bar(
                    x=cont_daily["Date"],
                    y=cont_daily[col],
                    name=_DA_METRIC_LABELS.get(col, col),
                    marker_color=CHART_COLORS[i % len(CHART_COLORS)],
                ))
            fig_cont.update_layout(
                title=f"Contact Metrics — Daily — {window_label}",
                xaxis_title="Date",
                yaxis_title="Count",
                barmode="group",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=50, l=50, r=20),
            )
            st.plotly_chart(fig_cont, use_container_width=True)

        primary = "nm_contacted"
        if primary in df.columns:
            area_tbl = _area_breakdown(df, primary)
            if not area_tbl.empty:
                st.caption("NM Contacted — by area")
                render_table(area_tbl)


    # ── LSI & Doors tab ────────────────────────────────────────────────────────────
    with tab_lsi:
        render_section_label("LSI Given & Follow-Ups")
        _summary_metrics(df, _LSI_COLS)

        lsi_present = [c for c in _LSI_COLS if c in df.columns]
        if lsi_present and "Date" in df.columns:
            lsi_daily = (
                df.groupby("Date")[lsi_present]
                .sum()
                .reset_index()
                .sort_values("Date")
            )
            fig_lsi = go.Figure()
            for i, col in enumerate(lsi_present):
                fig_lsi.add_trace(go.Bar(
                    x=lsi_daily["Date"],
                    y=lsi_daily[col],
                    name=_DA_METRIC_LABELS.get(col, col),
                    marker_color=CHART_COLORS[i % len(CHART_COLORS)],
                ))
            fig_lsi.update_layout(
                title=f"LSI — Daily — {window_label}",
                xaxis_title="Date",
                yaxis_title="Count",
                barmode="group",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=50, l=50, r=20),
            )
            st.plotly_chart(fig_lsi, use_container_width=True)

        render_section_label("Attempts by Type")
        _summary_metrics(df, _DOOR_COLS)

        door_present = [c for c in _DOOR_COLS if c in df.columns]
        if door_present and "Date" in df.columns:
            door_daily = (
                df.groupby("Date")[door_present]
                .sum()
                .reset_index()
                .sort_values("Date")
            )
            fig_door = go.Figure()
            for i, col in enumerate(door_present):
                fig_door.add_trace(go.Bar(
                    x=door_daily["Date"],
                    y=door_daily[col],
                    name=_DA_METRIC_LABELS.get(col, col),
                    marker_color=CHART_COLORS[i % len(CHART_COLORS)],
                ))
            fig_door.update_layout(
                title=f"Attempts by Type — Daily — {window_label}",
                xaxis_title="Date",
                yaxis_title="Count",
                barmode="stack",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=50, l=50, r=20),
            )
            st.plotly_chart(fig_door, use_container_width=True)

        # By-area breakdown for LSI Given
        if "lsi_given" in df.columns:
            area_tbl = _area_breakdown(df, "lsi_given")
            if not area_tbl.empty:
                st.caption("LSI Given — by area")
                render_table(area_tbl)


    # ── Effort tab ─────────────────────────────────────────────────────────────────
    with tab_effort:
        render_section_label("Effort Reporting")

        effort_df = _load_effort()
        if effort_df.empty:
            st.info("Effort tracking coming soon.")
        else:
            effort_present = [c for c in ["all_count", "most_count", "some_count"] if c in effort_df.columns]
            if effort_present:
                totals = effort_df[effort_present].sum()
                ecols = st.columns(len(effort_present))
                label_map = {"all_count": "Full Effort", "most_count": "Most Effort", "some_count": "Some Effort"}
                for i, col in enumerate(effort_present):
                    ecols[i].metric(label_map.get(col, col), int(totals[col]))

                if "date" in effort_df.columns:
                    fig_effort = go.Figure()
                    for i, col in enumerate(effort_present):
                        fig_effort.add_trace(go.Bar(
                            x=effort_df["date"],
                            y=effort_df[col],
                            name=label_map.get(col, col),
                            marker_color=CHART_COLORS[i % len(CHART_COLORS)],
                        ))
                    fig_effort.update_layout(
                        title="Effort Reported — Daily",
                        xaxis_title="Date",
                        yaxis_title="Count",
                        barmode="stack",
                        hovermode="x unified",
                        margin=dict(t=50, b=50, l=50, r=20),
                    )
                    st.plotly_chart(fig_effort, use_container_width=True)
            else:
                st.info("Effort tracking coming soon.")

    render_section_label("Raw Data")

    # ═══════════════════════════════════════════════════════════════════════════════
    # RAW DATA EXPANDER
    # ═══════════════════════════════════════════════════════════════════════════════
    with st.expander("Raw Daily Records", expanded=False):
        base_cols = [c for c in ("Date", "Zone", "District", "Area") if c in df.columns]
        display_cols = base_cols + present
        rename_map = {m: _DA_METRIC_LABELS.get(m, m) for m in present}
        sort_col = "Date" if "Date" in df.columns else df.columns[0]
        render_table(
            df[display_cols].sort_values(sort_col, ascending=False).rename(columns=rename_map)
        )


def _render_analyze_tab():
    _an_c1, _an_c2 = st.columns(2)
    with _an_c1:
        metric_key = st.selectbox(
            "Metric",
            options=list(_ANALYZE_METRIC_LABELS.keys()),
            format_func=lambda k: _ANALYZE_METRIC_LABELS[k],
            key="analyze_metric",
        )
    with _an_c2:
        threshold_pct = st.slider(
            "Anomaly Threshold (%)",
            min_value=50,
            max_value=95,
            value=70,
            step=5,
            help="Flag areas where this week's value is below this % of their 4-week average.",
            key="analyze_threshold",
        )

    threshold = threshold_pct / 100.0

    metric_label = _ANALYZE_METRIC_LABELS[metric_key]

    # ══════════════════════════════════════════════════════════════════════════════
    # SECTION 1: Areas of Concern
    # ══════════════════════════════════════════════════════════════════════════════

    render_section_label(f"Areas of Concern — {metric_label}")
    st.caption(
        f"Areas where this week is below {threshold_pct}% of their 4-week average."
    )

    anomalies_df = detect_anomalies(metric_key=metric_key, threshold=threshold)

    # Focus the list on the anomalies worth acting on. detect_anomalies flags every
    # area below the threshold, which for high-volume metrics (NM Contacted) is 60+
    # rows, while a tiny area going 0.3 -> 0 is technically "-100%" but meaningless.
    # So: drop tiny-baseline noise, then rank by the biggest ACTUAL drop (units lost
    # vs their own 4-wk average) and soft-cap the list. This reliably lands at a
    # useful ~5-10 across every metric. (Breakdowns' area pills are unaffected — this
    # only shapes the Analyze display.)
    _MIN_BASELINE = 2.0   # ignore areas averaging < 2/week of this metric
    _MAX_SHOWN    = 10

    _total_flagged = 0
    if isinstance(anomalies_df, pd.DataFrame) and not anomalies_df.empty:
        anomalies_df = anomalies_df[anomalies_df["avg_4wk"] >= _MIN_BASELINE].copy()
        anomalies_df["_drop"] = anomalies_df["avg_4wk"] - anomalies_df["this_week"]
        anomalies_df = anomalies_df.sort_values("_drop", ascending=False)
        _total_flagged = len(anomalies_df)
        anomalies_df = anomalies_df.head(_MAX_SHOWN).drop(columns=["_drop"])

    if anomalies_df is None or (isinstance(anomalies_df, pd.DataFrame) and anomalies_df.empty):
        st.success(f"No anomalies detected this week for **{metric_label}**.")
    else:
        # Build display table
        display_cols = {
            "zone":       "Zone",
            "district":   "District",
            "area":       "Area",
            "this_week":  "This Week",
            "avg_4wk":    "4-Wk Avg",
            "pct_change": "% Change",
            "severity":   "Severity",
        }
        available = [c for c in display_cols if c in anomalies_df.columns]
        display = anomalies_df[available].copy()
        display = display.rename(columns={c: display_cols[c] for c in available})

        if "This Week" in display.columns:
            display["This Week"] = display["This Week"].apply(
                lambda v: int(v) if pd.notna(v) else 0
            )
        if "4-Wk Avg" in display.columns:
            display["4-Wk Avg"] = display["4-Wk Avg"].round(1)
        if "% Change" in display.columns:
            display["% Change"] = display["% Change"].apply(
                lambda v: f"{v:+.1f}%" if pd.notna(v) else "—"
            )

        # Color severity column
        def _severity_color(val):
            if val == "High":
                return "background-color: #b91c1c; color: white;"
            if val == "Medium":
                return "background-color: #d97706; color: white;"
            return ""

        if "Severity" in display.columns:
            styled = display.style.map(_severity_color, subset=["Severity"])
            render_table(styled)
        else:
            render_table(display)

        n = len(anomalies_df)
        if _total_flagged > n:
            st.caption(f"Showing the {n} biggest drops of {_total_flagged} areas flagged.")
        else:
            st.caption(f"{n} area{'s' if n != 1 else ''} flagged.")

    render_section_label("Trend Projection")

    proj_metric_key = st.selectbox(
        "Metric to project",
        options=list(_ANALYZE_PROJECTION_METRIC_LABELS.keys()),
        format_func=lambda k: _ANALYZE_PROJECTION_METRIC_LABELS[k],
        key="analyze_proj_metric",
        help="Pick any nightly-form or weekly-form metric to see its projection.",
    )
    proj_label = _ANALYZE_PROJECTION_METRIC_LABELS[proj_metric_key]

    st.caption(
        "Mission-wide totals from completed weeks (current in-progress week excluded), "
        "with next week projected by linear regression and an 80% confidence range."
    )

    projection = project_next_week(metric_key=proj_metric_key)

    status = projection.get("status") if projection else None

    if not projection or not projection.get("weeks"):
        st.info("No history available yet for this metric.")
    elif status == "insufficient":
        have = len(projection.get("weeks", []))
        st.info(
            f"Not enough history yet for a trustworthy projection — "
            f"need at least 4 completed weeks, have {have}."
        )
    else:
        weeks = projection["weeks"]
        actuals = projection["actuals"]
        proj_val = projection.get("projected")
        proj_date = projection.get("week_end_date", "")
        lower = projection.get("lower")
        upper = projection.get("upper")
        confidence = projection.get("confidence", "low")
        high_conf = confidence == "high"

        # High confidence reads green; low confidence reads amber to signal "rough".
        proj_color = "#22c55e" if high_conf else "#f59e0b"

        # ── Plotly chart ──────────────────────────────────────────────────────────
        bg_color = "#0e1117" if dark else "#ffffff"
        font_color = "#fafafa" if dark else "#262730"
        grid_color = "#333333" if dark else "#e5e7eb"

        fig = go.Figure()

        # Confidence band — a shaded cone fanning from the last actual out to the
        # [lower, upper] range at the projected week. Width = how much to trust it.
        if lower is not None and upper is not None and proj_date:
            band_fill = "rgba(34,197,94,0.15)" if high_conf else "rgba(245,158,11,0.15)"
            fig.add_trace(
                go.Scatter(
                    x=[weeks[-1], proj_date, proj_date, weeks[-1]],
                    y=[actuals[-1], upper, lower, actuals[-1]],
                    fill="toself",
                    fillcolor=band_fill,
                    line=dict(width=0),
                    hoverinfo="skip",
                    name="80% range",
                    showlegend=True,
                )
            )

        # Actuals line
        fig.add_trace(
            go.Scatter(
                x=weeks,
                y=actuals,
                mode="lines+markers",
                name="Actuals",
                line=dict(color="#3b82f6", width=2),
                marker=dict(size=7),
            )
        )

        # Projected point — dashed connector from last actual
        if proj_val is not None and proj_date:
            fig.add_trace(
                go.Scatter(
                    x=[weeks[-1], proj_date],
                    y=[actuals[-1], proj_val],
                    mode="lines",
                    name="Projection",
                    line=dict(color=proj_color, width=2, dash="dash"),
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[proj_date],
                    y=[proj_val],
                    mode="markers+text",
                    name="Projected",
                    marker=dict(
                        size=12,
                        color=proj_color,
                        symbol="diamond",
                        line=dict(width=2, color="#f4f4f8"),
                    ),
                    text=[f"{proj_val:.0f}"],
                    textposition="top center",
                    textfont=dict(color=font_color),
                )
            )

        fig.update_layout(
            title=f"{proj_label} — {len(weeks)} Completed Weeks + Projection",
            xaxis_title="Week Ending",
            yaxis_title=proj_label,
            plot_bgcolor=bg_color,
            paper_bgcolor=bg_color,
            font=dict(color=font_color),
            xaxis=dict(gridcolor=grid_color, tickangle=-30),
            yaxis=dict(gridcolor=grid_color, rangemode="tozero"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=50, b=20),
        )

        st.plotly_chart(fig, use_container_width=True)

        # ── Metric card + confidence badge ────────────────────────────────────────
        if proj_val is not None:
            delta_val = round(proj_val - actuals[-1], 1) if actuals else None
            col_metric, col_conf = st.columns([1, 1])
            with col_metric:
                st.metric(
                    label=f"Projected {proj_label} — Week ending {proj_date}",
                    value=int(round(proj_val)),
                    delta=delta_val,
                    delta_color="normal",
                )
            with col_conf:
                if lower is not None and upper is not None:
                    st.caption(f"**Likely range:** {lower:g} – {upper:g}")
                if high_conf:
                    st.success("High confidence — the trend is statistically significant.")
                else:
                    st.warning(
                        "Low confidence — the recent weeks aren't a statistically "
                        "significant trend. Treat this as a rough estimate, not a forecast."
                    )


tab_scores, tab_daily, tab_analyze = st.tabs(["Scores", "Daily Activity", "Analyze"])
with tab_scores:
    _render_scores_tab()
with tab_daily:
    _render_daily_tab()
with tab_analyze:
    _render_analyze_tab()
