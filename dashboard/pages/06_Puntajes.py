"""
06_Puntajes.py
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
from app.config.metric_catalog import (
    key_indicator_metrics as _key_indicator_metrics,
    metric_data_type as _metric_data_type,
    nightly_metrics as _nightly_metrics,
    non_numeric_metrics as _non_numeric_metrics,
    weekly_metrics as _weekly_metrics,
)
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
    get_score_component_weights,
    get_submitting_areas,
    get_zones,
    project_next_week,
)
from app.db.sheets_client import overwrite_tab, read_tab
from app.i18n import t

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CCSM · Scores — PMG Compass",
    page_icon="",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)
dark = True

# Sentinel area code for a single config that applies to every area in the mission.
MISSION_WIDE_CODE = "ALL"
# Display label only - every comparison uses this same constant, and the value
# persisted to the sheet is MISSION_WIDE_CODE, so translating it is safe.
MISSION_WIDE_LABEL = t("Whole Mission (all areas)")

# Friendly display names for every metric that feeds the Effectiveness score.
#
# Was a hardcoded dict of Utah Provo's vocabulary — new_found, nm_lessons,
# lsi_given ("Love-Share-Invite Given"), locos_knocked, pew, gate, renew,
# rc_total — inherited with the fork. CCSM runs no Love/Share/Invite at all, so
# none of those keys exist in its data; the labels rendered onto this page
# anyway, because a label dict does not need matching data to be displayed.
#
# Now the generated catalogue. `_FLAVOR_METRIC_LABELS` is itself the live
# QUESTIONS_CONFIG view (see app/config/flavor_loader._LiveMetricLabels), so
# this is an alias rather than a fifth copy.
METRIC_LABELS = _FLAVOR_METRIC_LABELS

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

# Baseline weights shown in the config editor, and the metric universe it
# offers. Both come from SCORE_CONFIG — the tab CCSM_AgentScores.gs itself
# reads — so the editor shows the mission its own configuration.
#
# These were three hardcoded dicts of Utah Provo's metrics (new_found,
# nm_lessons, lsi_given, locos_knocked / gate, date_metric, pew, renew,
# rc_total). Nothing warned, because the editor's job is to DISPLAY a weight
# per metric and it did that perfectly for metrics CCSM has never collected.
#
# That was not merely cosmetic. The editor's Save does a full clear-and-rewrite
# of SCORE_CONFIG over exactly this universe (_rewrite_score_config below), so
# one Save from the Score Weight Editor would have replaced CCSM's real
# configuration — contacts_attempted / roleplays / member_contacts / effort,
# the four rates, and the seven ki_*_real — with Provo's keys, and the next
# scoring run would have scored all 98 areas against metrics that do not exist.
#
# Functions, not dicts: a module-level dict is built at import time, when there
# is no Streamlit session and no sheet to read.

def _default_component_weights(component: str) -> dict[str, float]:
    """Mission-wide ('ALL') SCORE_CONFIG weights for one score component."""
    return get_score_component_weights(component, MISSION_WIDE_CODE)


def _component_universe(component: str) -> list[str]:
    """Every metric the editor may assign a weight to for `component`.

    Effort and Skill both draw on the nightly form; KI is the weekly form's
    Key Indicators. The universe is the catalogue plus anything SCORE_CONFIG
    already weights — so a metric the agents score but the catalogue has since
    dropped stays visible and editable instead of silently vanishing from the
    editor while still counting toward the score.

    Rates (contact_rate, mc_rate, lesson_rate, close_rate) are computed, not
    asked, so they are not in QUESTIONS_CONFIG — they arrive via the
    SCORE_CONFIG half of this union, which is exactly where CCSM weights them
    for Skill.
    """
    if component == "ki":
        catalog = list(_key_indicator_metrics())
    else:
        catalog = list(_nightly_metrics())
    configured = list(_default_component_weights(component))
    return catalog + [k for k in configured if k not in catalog]


def _default_eff_weights() -> dict[str, float]:
    """Effectiveness composition {effort, skill, ki} from SCORE_CONFIG."""
    return flavor.scoring_weights


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
    defaults = _default_component_weights(component)

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
    fallback = _default_eff_weights()
    if sec2.empty or "Area_Code" not in sec2.columns:
        return dict(fallback)

    mask = sec2["Area_Code"].str.strip().str.lower() == area_code.lower()
    rows = sec2[mask]
    if rows.empty:
        return dict(fallback)

    r = rows.iloc[0]
    return {
        "effort": float(r.get("Effort_Weight", fallback["effort"]) or fallback["effort"]),
        "skill":  float(r.get("Skill_Weight",  fallback["skill"])  or fallback["skill"]),
        "ki":     float(r.get("KI_Weight",     fallback["ki"])     or fallback["ki"]),
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
def _ANALYZE_METRIC_LABELS() -> dict:
    """Nightly metrics for Analyze's anomaly section — the only ones with
    area-level daily history to flag an anomaly against.

    Was another hardcoded Provo catalogue. A function now, because the
    catalogue is read from the sheet and there is no session at import time.
    """
    return dict(_nightly_metrics())


def _ANALYZE_PROJECTION_METRIC_LABELS() -> dict:
    """Everything the projection dropdown covers: the nightly metrics above
    PLUS the weekly-form Key Indicators, which project from WEEKLY_FORM_RAW.

    Weekly ones are suffixed so it is clear which form drives them — a
    projection off a once-a-week series behaves very differently from one off
    daily data, and the reader should not have to know the metric to know that.
    """
    labels = dict(_nightly_metrics())
    for key, name in _weekly_metrics().items():
        labels[key] = t('{metric} — Weekly Form', metric=name)
    return labels

# ── Daily Activity's metric universe + cached loaders ──────────────────────────
_DA_METRIC_LABELS = _FLAVOR_METRIC_LABELS  # live QUESTIONS_CONFIG label lookup


def _daily_activity_metrics() -> dict[str, str]:
    """{key: label} for every nightly metric this mission can chart and total.

    Replaces five hardcoded column groups — Teaching, Finding, Contacting,
    Member Work, Support Attempts — holding Utah Provo's keys (nm_lessons,
    lsi_given, nm_doors, locos_Attempt …). Every section below filters those
    lists with `[c for c in cols if c in df.columns]`, so against CCSM's
    DAILY_LOG every group matched nothing: the whole Daily Activity tab
    rendered "No data for this category" five times over, which reads as a
    quiet mission rather than as a page wired to another mission's schema.

    CCSM's QUESTIONS_CONFIG has no category column, so there is no honest way
    to reproduce those groupings — and inventing new ones would be the same
    mistake with different words. Every nightly metric is offered instead, in
    the sheet's own Display_Order, per [[feedback-show-all-metrics]].

    Non-numeric metrics are excluded: `effort` is CHOICE and `exchanges` is
    YESNO, and summing either produces a number with no meaning. `effort` has
    its own section further down, which reads the agent-computed counts.
    """
    skip = _non_numeric_metrics()
    return {k: v for k, v in _nightly_metrics().items() if k not in skip}

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
    render_page_header(t("Area Scores"), t('{mission_name} — weekly computed performance scores per area', mission_name=get_config_value('MISSION_NAME', flavor.display_name)), icon="")


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
            render_page_header(t("Mission Scores"), t('{mission_name} — weekly computed performance scores per area', mission_name=get_config_value('MISSION_NAME', flavor.display_name)), icon="")
        st.info(
            t("No scores have been computed yet. Scores are calculated automatically "
            "each Sunday at 11 PM Mountain Time. Run computeAllAreaScores() in "
            "Apps Script to compute scores immediately.")
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
        t("Mission Score"), key="sc_mission_reset",
        help=t("Clear Zone/District/Area/missionary and show the mission-wide view"),
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
        render_page_header(_page_title, t('{mission_name} — weekly computed performance scores per area', mission_name=get_config_value('MISSION_NAME', flavor.display_name)), icon="")

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

            render_section_label(t('Mission Score — Average Across All Areas ({ms_range})', ms_range=_ms_range))
            render_kpi_row([
                {"label": "Mission Effectiveness", "value": _ms_avg("Effectiveness_Score")},
                {"label": "Effort",               "value": _ms_avg("Effort_Score")},
                {"label": "Skill",                "value": _ms_avg("Skill_Score")},
                {"label": "KI",                   "value": _ms_avg("KI_Score")},
            ])
        else:
            render_section_label(t('Mission Score — Average Across All Areas ({ms_range})', ms_range=_ms_range))
            st.info(f"No scores fall inside {_ms_range}." + _stale_range_hint(_ms_range))

    _tcol, _, _ = st.columns(3)
    with _tcol:
        time_range = st.selectbox(
            t("Time Range"),
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
    render_section_label(t("Score Tier Key"))
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
        render_section_label(t('Effort Score Breakdown — {sel_area}', sel_area=sel_area))

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
        # metric, never its share of that week's pie, so a metric keeps the same
        # hue whether it's the biggest slice or the smallest.
        #
        # Was Provo's ["nm_lessons", "new_found", "mmm_sent", "pew", "gate"].
        # _pie_metrics filters that order down to metrics present in the
        # breakdown, so against CCSM's Effort component (contacts_attempted,
        # roleplays, member_contacts, effort) NOTHING matched and the pie
        # rendered empty — indistinguishable from an area with no Effort data.
        #
        # Sourced from SCORE_CONFIG's effort rows so the slices are exactly the
        # metrics the score is made of, heaviest first — the order stays stable
        # across areas and weeks because the weights do.
        _effort_weights = _default_component_weights("effort")
        _pie_metric_order = sorted(
            _effort_weights, key=lambda m: (-_effort_weights[m], m)
        )

        _breakdown = _avg_effort_breakdown(sel_area, _pie_weeks)

        if not _breakdown:
            st.info(t("No Effort data available for this area in the selected Time Range."))
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
            # The weight list is BUILT from SCORE_CONFIG, not spelled out. It
            # used to read "weighted nm_lessons 30% · new_found 25% · mmm_sent
            # 20% · pew 15% · gate 10%" — Provo's metrics and Provo's weights,
            # printed as a factual description of a CCSM area's score.
            _wsum = sum(_effort_weights.values())
            _weight_txt = " · ".join(
                f"{METRIC_LABELS.get(m, m)} {_effort_weights[m] / _wsum:.0%}"
                for m in _pie_metric_order
            ) if _wsum > 0 else ""
            st.caption(
                t("Each slice is that metric's average share of this area's weekly Effort score across {count} week(s) in {time_range} (actual vs. expectation, weighted {weights}) — not raw activity volume.",
                  count=len(_pie_weeks), time_range=time_range, weights=_weight_txt)
            )
    else:
        render_section_label(t("Effectiveness Score by Area"))

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

    render_section_label(t("Score Summary"))

    st.caption(
        t("{scope_label}  |  {time_range}  |  {count} area(s) shown  |  Scores averaged across each area's weeks in this range", scope_label=scope_label, time_range=time_range, count=len(display_df))
    )

    st.caption(
        t("Effort uses its own tiers — meeting the mission president's weekly "
        "expectations exactly scores 75, so its bar is green above 75, "
        "yellow 50–75, red below 50 (Skill/KI/Effectiveness keep 70/50).")
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
        t("Scores are automatically recomputed each Sunday at 11 PM Mountain Time by the "
        "AgentScores Apps Script engine. To trigger an immediate recalculation, open the "
        "Google Apps Script editor for COMPASS_CCSM and run computeAllAreaScores().")
    )

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════════
    # SCORE WEIGHT EDITOR
    # ═══════════════════════════════════════════════════════════════════════════════

    # Full metric universe per component, from QUESTIONS_CONFIG + SCORE_CONFIG.
    # Effort and Skill both draw from the nightly (daily) form, so either
    # component can weight any of those metrics. KI draws from the weekly form.
    # A weight of 0 means the metric simply doesn't count.
    # Effort and Skill are asked separately rather than sharing one nightly
    # list: CCSM scores Skill on the four DERIVED rates (contact_rate, mc_rate,
    # lesson_rate, close_rate), which are computed by CCSM_Agent1A.gs and so
    # have no QUESTIONS_CONFIG row. They reach the editor only through the
    # SCORE_CONFIG half of _component_universe's union, and only when asked for
    # by their own component.
    EFFORT_UNIVERSE = _component_universe("effort")
    SKILL_UNIVERSE  = _component_universe("skill")
    KI_UNIVERSE     = _component_universe("ki")
    DEFAULT_EFFORT_WEIGHTS = _default_component_weights("effort")
    DEFAULT_SKILL_WEIGHTS  = _default_component_weights("skill")
    DEFAULT_KI_WEIGHTS     = _default_component_weights("ki")

    # An empty catalogue must not become an empty SCORE_CONFIG. Save below
    # clear-and-rewrites the tab over exactly this universe, so rendering the
    # editor with nothing in it offers a Save that wipes the mission's scoring
    # configuration — and reports success.
    if not EFFORT_UNIVERSE and not SKILL_UNIVERSE and not KI_UNIVERSE:
        st.warning(
            t("No metrics are configured for this mission, so there is nothing to "
              "weight. Check the QUESTIONS_CONFIG and SCORE_CONFIG tabs of "
              "COMPASS_CCSM before editing score weights.")
        )
        return


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
                    t('{metric_labels}  ·  rec {rec:g}', metric_labels=METRIC_LABELS.get(k, k), rec=rec),
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


    with st.expander(t("Edit Score Weights"), expanded=False):
        st.markdown(
            t("**How the Effectiveness score is built.** Each area's Effectiveness score is a "
            "blend of three components — **Effort**, **Skill**, and **Key Indicators (KI)**. "
            "Set how much each component counts in *Component Mix* below, then fine-tune every "
            "individual metric (lessons, contacts, referrals, door attempts, weekly KIs, etc.) "
            "inside each component tab.")
        )

        # ── Scope selector: whole mission or a single area ────────────────────────
        cfg_area_options = [MISSION_WIDE_LABEL] + (area_names if area_names else sorted(
            scores_df["Area_Name"].dropna().astype(str).unique().tolist()
        ))

        cfg_area = st.selectbox(
            t("Apply weights to"),
            options=cfg_area_options,
            key="cfg_area",
            help=t("Choose 'Whole Mission' to set one baseline for every area, or pick a single "
                 "area to override it. Area-specific weights win over the mission baseline."),
        )

        is_mission_wide = (cfg_area == MISSION_WIDE_LABEL)

        if is_mission_wide:
            cfg_area_code = MISSION_WIDE_CODE
            st.info(
                t("Editing the **mission-wide baseline**. These weights apply to every area "
                "unless that area has its own override."),
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
            st.markdown(t('**Area Code:** `{cfg_area_code}`', cfg_area_code=cfg_area_code))

        # ── Component mix (effectiveness sub-weights) ─────────────────────────────
        st.markdown(t("##### Component Mix"))
        st.caption(
            t("How much each component counts toward Effectiveness. Must sum to 1.0 "
            "(e.g. Effort 0.30 + Skill 0.30 + KI 0.40).")
        )

        current_eff = _get_area_eff_weights(sec2, cfg_area_code)

        eff_col1, eff_col2, eff_col3 = st.columns(3)
        with eff_col1:
            eff_effort = st.number_input(
                t("Effort Weight"),
                min_value=0.0, max_value=1.0, step=0.05,
                value=float(current_eff["effort"]),
                format="%.2f",
                key="eff_effort",
            )
        with eff_col2:
            eff_skill = st.number_input(
                t("Skill Weight"),
                min_value=0.0, max_value=1.0, step=0.05,
                value=float(current_eff["skill"]),
                format="%.2f",
                key="eff_skill",
            )
        with eff_col3:
            eff_ki = st.number_input(
                t("KI Weight"),
                min_value=0.0, max_value=1.0, step=0.05,
                value=float(current_eff["ki"]),
                format="%.2f",
                key="eff_ki",
            )

        eff_sum = round(eff_effort + eff_skill + eff_ki, 4)
        if abs(eff_sum - 1.0) > 0.001:
            st.warning(t('Component mix must sum to 1.0 (currently {eff_sum:.4f}).', eff_sum=eff_sum))
            eff_valid = False
        else:
            st.success(t('Component mix sums to {eff_sum:.2f}', eff_sum=eff_sum))
            eff_valid = True

        # ── Per-metric weights ────────────────────────────────────────────────────
        st.markdown(t("##### Metric Weights"))
        st.caption(
            t("Every metric from the nightly and weekly forms, with the weight it carries. "
            "Each box label shows the recommended baseline (rec). A weight of 0 means the "
            "metric doesn't count. The engine normalises by component total, so relative "
            "proportions are what matter.")
        )

        tab_effort, tab_skill, tab_ki = st.tabs(
            [t("Effort Metrics"), t("Skill Metrics"), t("Key Indicator Metrics")]
        )

        with tab_effort:
            st.caption(
                t("Legacy / unused — the Effort score is now computed from the "
                "mission president's fixed weekly expectations per area type, "
                "not these per-metric weights. Kept for reference only.")
            )
            edited_effort = _render_weight_inputs(
                "effort",
                _component_weights(cfg_area_code, "effort", EFFORT_UNIVERSE, DEFAULT_EFFORT_WEIGHTS),
                DEFAULT_EFFORT_WEIGHTS, cfg_area_code,
            )

        with tab_skill:
            st.caption(t("Nightly-form quality signals — how effectively the area is working. "
                       "Metrics left at 0 don't count toward Skill."))
            edited_skill = _render_weight_inputs(
                "skill",
                _component_weights(cfg_area_code, "skill", SKILL_UNIVERSE, DEFAULT_SKILL_WEIGHTS),
                DEFAULT_SKILL_WEIGHTS, cfg_area_code,
            )

        with tab_ki:
            st.caption(t("Weekly-form Key Indicators. Metrics left at 0 don't count toward KI."))
            edited_ki = _render_weight_inputs(
                "ki",
                _component_weights(cfg_area_code, "ki", KI_UNIVERSE, DEFAULT_KI_WEIGHTS),
                DEFAULT_KI_WEIGHTS, cfg_area_code,
            )

        # ── Save button ───────────────────────────────────────────────────────────
        st.markdown(t("---"))

        if st.button(
            t("Save Config"),
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
                    t('Saved {saved} weight rows for {scope_txt}. The new weights take effect on the next scoring run (Sunday 11 PM MT, or run computeAllAreaScores() now).', saved=saved, scope_txt=scope_txt)
                )
            except Exception as save_err:
                st.error(t('Failed to save config: {save_err}', save_err=save_err))


def _render_daily_tab():
    # ── Top control: number of days displayed ──────────────────────────────────────
    ctrl_col, _spacer = st.columns([1, 3])
    with ctrl_col:
        days = st.number_input(
            t("Days displayed"),
            min_value=1, max_value=120, value=14, step=1,
            key="da_days",
            help=t("How many days of nightly-form data to show on this page."),
        )
    window_label = f"last {int(days)} days"

    df = _load_daily(int(days))

    if df.empty:
        st.info(t("No daily activity data yet. Re-run the data refresh to populate this page."))
        return

    # Zone/District filter
    all_zones = _load_zones()
    zone_options = ["All"] + all_zones
    _da_f1, _da_f2 = st.columns(2)
    with _da_f1:
        selected_zone = st.selectbox(t("Zone"), zone_options, key="da_zone")

    if selected_zone != "All":
        df = df[df["Zone"] == selected_zone].copy() if "Zone" in df.columns else df

        district_options = ["All"] + _load_districts(selected_zone)
        with _da_f2:
            selected_district = st.selectbox(t("District"), district_options, key="da_district")
        if selected_district != "All":
            df = df[df["District"] == selected_district].copy() if "District" in df.columns else df

    if df.empty:
        st.info(t("No data for the selected filters."))
        return

    # ── Present metric columns ─────────────────────────────────────────────────────
    _da_metrics = _daily_activity_metrics()
    present = [c for c in _da_metrics if c in df.columns]

    if not present:
        st.info(t(
            "None of this mission's nightly metrics appear in DAILY_LOG. Check the "
            "QUESTIONS_CONFIG tab of COMPASS_CCSM, then re-run the nightly refresh."
        ))
        return

    def _col_sum(col: str) -> int:
        return int(df[col].sum()) if col in df.columns else 0

    # ═══════════════════════════════════════════════════════════════════════════════
    # MISSION TOTALS
    # ═══════════════════════════════════════════════════════════════════════════════
    # Every nightly metric, in QUESTIONS_CONFIG's own Display_Order. This was a
    # fixed five — NM Lessons, New People Found, NM Contacted, LSI Given, NM
    # Attempted — hardcoded to Provo columns, so all five read 0 for CCSM.
    render_section_label(t('Mission Totals — {window_label}', window_label=window_label))

    _TILES_PER_ROW = 5
    for _start in range(0, len(present), _TILES_PER_ROW):
        _row_keys = present[_start:_start + _TILES_PER_ROW]
        _tiles = st.columns(_TILES_PER_ROW)
        for _i, _key in enumerate(_row_keys):
            _tiles[_i].metric(_da_metrics[_key], _col_sum(_key))

    # ═══════════════════════════════════════════════════════════════════════════════
    # DAILY TREND
    # ═══════════════════════════════════════════════════════════════════════════════
    render_section_label(t("Daily Trend"))

    # Default selection is the mission's own Effort metrics — SCORE_CONFIG is
    # the one place CCSM states which nightly numbers it cares about, so the
    # chart opens on those rather than on whichever metrics happen to sort
    # first. Falls back to the first few only when SCORE_CONFIG is unreadable.
    _effort_keys = [k for k in _default_component_weights("effort") if k in present]
    _default_trend = _effort_keys or present[:3]

    _trend_keys = st.multiselect(
        t("Metrics to chart"),
        options=present,
        default=_default_trend,
        format_func=lambda k: _da_metrics.get(k, k),
        key="da_trend_metrics",
    )

    if not _trend_keys:
        st.info(t("Pick at least one metric to chart."))
    elif "Date" not in df.columns:
        st.info(t("DAILY_LOG has no Date column, so there is no trend to draw."))
    else:
        _trend = (
            df.groupby("Date")[_trend_keys]
            .sum()
            .reset_index()
            .sort_values("Date")
        )
        _fig_trend = go.Figure()
        for _i, _key in enumerate(_trend_keys):
            _fig_trend.add_trace(go.Bar(
                x=_trend["Date"],
                y=_trend[_key],
                name=_da_metrics.get(_key, _key),
                marker_color=CHART_COLORS[_i % len(CHART_COLORS)],
            ))
        _fig_trend.update_layout(
            title=t('Nightly reporting — {window_label}', window_label=window_label),
            xaxis_title=t("Date"),
            xaxis_type="category",
            yaxis_title=t("Count"),
            barmode="group",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=60, b=50, l=50, r=20),
        )
        st.plotly_chart(_fig_trend, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════════
    # BY AREA
    # ═══════════════════════════════════════════════════════════════════════════════
    render_section_label(t("By Area"))

    _area_metric = st.selectbox(
        t("Metric"),
        options=present,
        index=present.index(_default_trend[0]) if _default_trend else 0,
        format_func=lambda k: _da_metrics.get(k, k),
        key="da_area_metric",
    )

    if "Area" not in df.columns:
        st.info(t("DAILY_LOG has no Area column, so it cannot be broken down by area."))
    else:
        _label = _da_metrics.get(_area_metric, _area_metric)
        _area_tbl = (
            df.groupby("Area")[_area_metric]
            .sum()
            .reset_index()
            .rename(columns={_area_metric: _label})
            .sort_values(_label, ascending=False)
        )
        if _area_tbl.empty:
            st.info(t("No data for the selected filters."))
        else:
            render_table(_area_tbl)

    # ═══════════════════════════════════════════════════════════════════════════════
    # EFFORT REPORTING
    # ═══════════════════════════════════════════════════════════════════════════════
    # `effort` is a CHOICE question (Todo / La mayor parte / Algo), so it is
    # excluded from the totals and charts above — summing it would produce a
    # number with no meaning. The agents bucket it into counts instead, which is
    # what this section reads.
    render_section_label(t("Effort Reporting"))

    effort_df = _load_effort()
    _effort_cols = (
        [c for c in ("all_count", "most_count", "some_count") if c in effort_df.columns]
        if not effort_df.empty else []
    )
    if not _effort_cols:
        st.info(t("No effort responses recorded for this window yet."))
    else:
        _effort_labels = {
            "all_count":  t("Full Effort"),
            "most_count": t("Most Effort"),
            "some_count": t("Some Effort"),
        }
        totals = effort_df[_effort_cols].sum()
        ecols = st.columns(len(_effort_cols))
        for i, col in enumerate(_effort_cols):
            ecols[i].metric(_effort_labels.get(col, col), int(totals[col]))

        if "date" in effort_df.columns:
            fig_effort = go.Figure()
            for i, col in enumerate(_effort_cols):
                fig_effort.add_trace(go.Bar(
                    x=effort_df["date"],
                    y=effort_df[col],
                    name=_effort_labels.get(col, col),
                    marker_color=CHART_COLORS[i % len(CHART_COLORS)],
                ))
            fig_effort.update_layout(
                title=t("Effort reported per day"),
                xaxis_title=t("Date"),
                yaxis_title=t("Count"),
                barmode="stack",
                hovermode="x unified",
                margin=dict(t=50, b=50, l=50, r=20),
            )
            st.plotly_chart(fig_effort, use_container_width=True)

    render_section_label(t("Raw Data"))

    # ═══════════════════════════════════════════════════════════════════════════════
    # RAW DATA EXPANDER
    # ═══════════════════════════════════════════════════════════════════════════════
    with st.expander(t("Raw Daily Records"), expanded=False):
        base_cols = [c for c in ("Date", "Zone", "District", "Area") if c in df.columns]
        display_cols = base_cols + present
        rename_map = {m: _DA_METRIC_LABELS.get(m, m) for m in present}
        sort_col = "Date" if "Date" in df.columns else df.columns[0]
        render_table(
            df[display_cols].sort_values(sort_col, ascending=False).rename(columns=rename_map)
        )


def _render_analyze_tab():
    # The catalogue comes from QUESTIONS_CONFIG, so it CAN be empty — an
    # unreadable tab, a quota blip, a mission mid-setup. st.selectbox over an
    # empty options list returns None, and the old hardcoded dict could never
    # be empty, so every lookup below assumed a real key and this whole page
    # died with `KeyError: None` before rendering anything.
    _an_labels = _ANALYZE_METRIC_LABELS()
    if not _an_labels:
        st.info(t("No metrics are configured yet — check QUESTIONS_CONFIG on the Maintenance page."))
        return

    _an_c1, _an_c2 = st.columns(2)
    with _an_c1:
        metric_key = st.selectbox(
            t("Metric"),
            options=list(_an_labels.keys()),
            format_func=lambda k: _an_labels.get(k, k),
            key="analyze_metric",
        )
    with _an_c2:
        threshold_pct = st.slider(
            t("Anomaly Threshold (%)"),
            min_value=50,
            max_value=95,
            value=70,
            step=5,
            help=t("Flag areas where this week's value is below this % of their 4-week average."),
            key="analyze_threshold",
        )

    threshold = threshold_pct / 100.0

    metric_label = _an_labels.get(metric_key, metric_key)

    # ══════════════════════════════════════════════════════════════════════════════
    # SECTION 1: Areas of Concern
    # ══════════════════════════════════════════════════════════════════════════════

    render_section_label(t('Areas of Concern — {metric_label}', metric_label=metric_label))
    st.caption(
        t('Areas where this week is below {threshold_pct}% of their 4-week average.', threshold_pct=threshold_pct)
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
        st.success(t('No anomalies detected this week for **{metric_label}**.', metric_label=metric_label))
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
            st.caption(t('Showing the {n} biggest drops of {total_flagged} areas flagged.', n=n, total_flagged=_total_flagged))
        else:
            st.caption(t('{n} area{value} flagged.', n=n, value='s' if n != 1 else ''))

    render_section_label(t("Trend Projection"))

    # Same empty-catalogue guard as the metric picker above — see its comment.
    _proj_labels = _ANALYZE_PROJECTION_METRIC_LABELS()
    if not _proj_labels:
        st.info(t("No metrics are configured yet — check QUESTIONS_CONFIG on the Maintenance page."))
        return

    proj_metric_key = st.selectbox(
        t("Metric to project"),
        options=list(_proj_labels.keys()),
        format_func=lambda k: _proj_labels.get(k, k),
        key="analyze_proj_metric",
        help=t("Pick any nightly-form or weekly-form metric to see its projection."),
    )
    proj_label = _proj_labels.get(proj_metric_key, proj_metric_key)

    st.caption(
        t("Mission-wide totals from completed weeks (current in-progress week excluded), "
        "with next week projected by linear regression and an 80% confidence range.")
    )

    projection = project_next_week(metric_key=proj_metric_key)

    status = projection.get("status") if projection else None

    if not projection or not projection.get("weeks"):
        st.info(t("No history available yet for this metric."))
    elif status == "insufficient":
        have = len(projection.get("weeks", []))
        st.info(
            t('Not enough history yet for a trustworthy projection — need at least 4 completed weeks, have {have}.', have=have)
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
                    label=t('Projected {proj_label} — Week ending {proj_date}', proj_label=proj_label, proj_date=proj_date),
                    value=int(round(proj_val)),
                    delta=delta_val,
                    delta_color="normal",
                )
            with col_conf:
                if lower is not None and upper is not None:
                    st.caption(t('**Likely range:** {lower:g} – {upper:g}', lower=lower, upper=upper))
                if high_conf:
                    st.success(t("High confidence — the trend is statistically significant."))
                else:
                    st.warning(
                        t("Low confidence — the recent weeks aren't a statistically "
                        "significant trend. Treat this as a rough estimate, not a forecast.")
                    )


tab_scores, tab_daily, tab_analyze = st.tabs([t("Scores"), t("Daily Activity"), t("Analyze")])
with tab_scores:
    _render_scores_tab()
with tab_daily:
    _render_daily_tab()
with tab_analyze:
    _render_analyze_tab()
