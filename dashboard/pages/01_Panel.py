"""
01_Panel.py
────────────────────────────────────────────────────────────────────────────────
Whole-mission executive snapshot — combines the former Dashboard and Mission
Breakdown pages into one. Mission-level only; for zone/district/area drilldown
use the Breakdowns page.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.auth.auth import require_auth
from app.components.design_system import (
    inject_global_css, render_page_header, render_sidebar,
    render_section_label, render_kpi_row, render_table,
)
from app.config.flavor_loader import flavor, METRIC_LABELS
from app.config.metric_catalog import key_indicator_metrics
from app.i18n import t
from app.i18n.formats import fmt_int, fmt_number, fmt_week_span, fmt_day_month
from app.config.theme import CHART_COLORS
from app.db.queries import (
    get_mission_totals,
    get_zone_totals,
    get_effort_data,
    get_effort_by_area,
    get_weekly_ki_trends,
    get_weekly_ki_totals,
    get_weekly_ki_reporting,
    select_reporting_week,
    exclude_current_week,
    get_daily_summary,
    get_alltime_compliance,
    get_mission_goals,
    get_area_weekly_goals,
    get_ki_goals_for_week,
    get_week_to_date_totals,
    get_week_to_date_areas,
    get_submitting_areas,
    get_scores,
    get_scored_weeks,
    get_daily_log,
    get_weekly_submission_data,
    get_config_value,
)
from app.analytics.zone_comparison import (
    zone_comparison_table, effectiveness_is_rankable, ki_scored_area_count,
    EFFECTIVENESS as ZONE_EFFECTIVENESS,
)
from app.utils.area_helpers import (
    compliance_anchor_date, build_calendar_data,
    latest_due_sunday, weekly_due_weeks,
)
from datetime import date, timedelta

st.set_page_config(
    page_title="CCSM · Dashboard — PMG Compass",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

_mission_name = get_config_value("MISSION_NAME", flavor.display_name)
render_page_header(t("PMG Compass"),
                   t("{mission} — Executive Dashboard", mission=_mission_name))

_EMPTY_MSG = t("No data for this section yet.")

st.caption(
    t("Summary data refreshes daily at noon. Submission compliance is computed "
      "live. Mission-level only — drill into a zone, district or area on the "
      "Breakdowns page.")
)


# ── Load data ─────────────────────────────────────────────────────────────────

mission_df = get_mission_totals()
zone_df    = get_zone_totals()
effort_df  = get_effort_data()
trends_df  = get_weekly_ki_trends(8)
daily_df   = get_daily_summary(7)
ki_df      = get_weekly_ki_totals(8)
app_goals  = get_mission_goals()

all_empty = (
    mission_df.empty
    and zone_df.empty
    and trends_df.empty
    and daily_df.empty
    and ki_df.empty
)
if all_empty:
    st.info(_EMPTY_MSG)
    st.stop()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mission_val(metric_key: str, col: str = "val_7d") -> float:
    if mission_df.empty or "metric_key" not in mission_df.columns:
        return 0.0
    row = mission_df[mission_df["metric_key"] == metric_key]
    if row.empty:
        return 0.0
    return float(row.iloc[0].get(col, 0) or 0)


def _mission_goal(metric_key: str) -> float:
    """Mission-wide weekly goal for a NIGHTLY metric.

    Three sources, most-specific first. DASHBOARD_SUMMARY.goal_weekly and
    GOALS_CONFIG (via app_goals) are both blank across the whole mission today —
    goal_weekly on all 23 MISSION rows, and GOALS_CONFIG is an empty tab — which
    is why no KPI tile has ever shown a bar. They are kept ahead of AGENT_CONFIG
    rather than deleted: populating either is how the mission overrides the
    configured default, and the Goals page edits GOALS_CONFIG inline.

    AGENT_CONFIG's GOAL_* rows are the fallback that actually fires. They are
    PER AREA PER WEEK (get_area_weekly_goals), so a mission-wide bar is that
    number times the active area count -- all 43 active teaching areas, not just
    the ones that reported. A non-submitting area counts as a zero here on
    purpose: this bar answers what the whole mission should have produced.
    """
    if not mission_df.empty and "metric_key" in mission_df.columns:
        row = mission_df[mission_df["metric_key"] == metric_key]
        if not row.empty and float(row.iloc[0].get("goal_weekly", 0) or 0) > 0:
            return float(row.iloc[0]["goal_weekly"])
    configured = float(app_goals.get(metric_key, 0) or 0)
    if configured > 0:
        return configured
    per_area = float(_area_goals.get(metric_key, 0) or 0)
    return per_area * _active_areas if per_area > 0 and _active_areas else 0.0


def _mission_goal_note(metric_key: str) -> str:
    """The arithmetic behind a derived mission goal, for the tile's small print.

    A bar reading "48% of 8.600" is unreadable without it: 8.600 is
    GOAL_contacts_attempted (200) x 43 active areas, and nothing else on the
    page says so. Only returned for the AGENT_CONFIG-derived case -- an entered
    goal is its own explanation.
    """
    if _mission_goal(metric_key) <= 0:
        return ""
    per_area = float(_area_goals.get(metric_key, 0) or 0)
    if per_area <= 0 or not _active_areas:
        return ""
    if float(app_goals.get(metric_key, 0) or 0) > 0:
        return ""
    if not mission_df.empty and "metric_key" in mission_df.columns:
        row = mission_df[mission_df["metric_key"] == metric_key]
        if not row.empty and float(row.iloc[0].get("goal_weekly", 0) or 0) > 0:
            return ""
    return t("{per_area} per area x {n}",
             per_area=fmt_int(per_area), n=fmt_int(_active_areas))


# ── Which week the Key Indicator tiles describe ───────────────────────────────
# The tiles used to read ki_df.iloc[-1] — the newest week present, which from
# Monday morning until the last area submits is the CURRENT, in-progress week.
# Section 4's chart already called exclude_current_week(); the tiles did not, so
# one page showed two different "latest weeks". See select_reporting_week() for
# the full case and the rule it applies.
_ki_row, _ki_week_end, _ki_is_partial = select_reporting_week(ki_df)
_today = date.today()
_this_monday = _today - timedelta(days=_today.weekday())
_this_sunday = _this_monday + timedelta(days=6)

_ki_reporting = get_weekly_ki_reporting()
_active_areas = len(get_submitting_areas())
_area_goals = get_area_weekly_goals()


def _ki_val(metric_key: str) -> float:
    """Mission total for a weekly-form KI metric, for the week the tiles name."""
    if _ki_row is None or metric_key not in _ki_row.index:
        return 0.0
    return float(_ki_row[metric_key] or 0)


# ── Key Indicator goals ───────────────────────────────────────────────────────
# A week's goals are written on the PREVIOUS week's form -- the weekly form asks
# for results "de la semana pasada" and goals "para la semana siguiente" in its
# own section help. get_ki_goals_for_week does that offset; both rows below get
# their goals from it, so neither can drift onto the wrong week.
_cur_goals, _cur_goal_set_by, _cur_goal_src, _cur_goal_areas = \
    get_ki_goals_for_week(_this_sunday)
_past_goals, _past_goal_set_by, _past_goal_src, _past_goal_areas = \
    get_ki_goals_for_week(_ki_week_end)

# ── What the current week can be measured by before its weekly form arrives ────
# The weekly form is submitted once, at the end of the week, so for a week in
# progress there is no ki_*_real to show. Three of the seven Key Indicators are
# also collected nightly and can be totalled Monday-to-today; the other four
# have no nightly equivalent and show their goal with no value rather than a
# zero (see render_kpi_row -- a zero would report a failure, an em dash reports
# an absence).
#
# ki_baptismal_date counts friends who currently HAVE a date -- a standing
# count. Its nightly stand-in, baptismal_calendars, counts calendars handed out
# -- a flow. They are close but not the same question, so the in-progress tile
# is RELABELLED to what it actually measures instead of borrowing the KI's name.
_KI_NIGHTLY_SOURCE = {
    "ki_new_people_real":     "new_people_found",
    "ki_member_lessons_real": "lessons_member_present",
    "ki_baptismal_date_real": "baptismal_calendars",
}
_KI_NIGHTLY_RELABEL = {
    "ki_baptismal_date_real": t("Baptismal Calendars Handed Out"),
}
_wtd_totals = get_week_to_date_totals(_this_monday, _today)
_wtd_areas = get_week_to_date_areas(_this_monday, _today)
_wtd_days = (_today - _this_monday).days + 1


# ═══════════════════════════════════════════════════════════════════════════════
# 1. NIGHTLY ACTIVITY — mission totals, last 7 days
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Nightly Activity — Last 7 Days"))

_nightly_keys = flavor.nightly_highlights
if not _nightly_keys:
    st.info(_EMPTY_MSG)
else:
    render_kpi_row([
        {
            "label": METRIC_LABELS.get(k, k),
            "value": int(_mission_val(k)),
            "goal":  _mission_goal(k),
            "goal_note": _mission_goal_note(k),
        }
        for k in _nightly_keys
    ])

# ═══════════════════════════════════════════════════════════════════════════════
# 2. KEY INDICATORS — the week in progress, then the last complete week
# ═══════════════════════════════════════════════════════════════════════════════
# Was a fixed Pew / Date / Gate / Renew row: Utah Provo's four Key Indicators,
# none of which is a column in CCSM's WEEKLY_KI. _ki_val returns 0.0 for a
# missing column, so this row showed four zeroes under four English labels for
# every week the mission ever reported — a plausible screen, not an error.
#
# CCSM's KIs are the seven `ki_*_real` values the weekly form collects. `_real`
# only: the matching `_meta` keys are a GOAL, and belong beside a value as a
# target, never in a row of achieved results.
#
# The current week leads because it is the week leadership can still act on; the
# completed week sits below it as the confirmed record. That ordering is only
# honest because the in-progress row states its own window and pace — see below.
_ki_metrics = key_indicator_metrics()


# Tile labels for the seven Key Indicators, short enough for a phone-width card.
#
# The catalogue's names are the FORM's question wording, which is right on a
# form and wrong on a tile: "Amigos en la Iglesia (Primera Semana) (Real)" wraps
# to three lines in a 200px card and pushes the number it labels off screen.
#
# Trimmed phrases rather than initialisms (NP / LM / FB), on purpose: a
# president glancing at the page should not have to decode it. "CR" is the one
# exception and only because Conversos Recientes is already said that way in the
# mission. Keys are English and translated like every other string, so the row
# does not silently become Spanish-only.
#
# The "(Real)" suffix goes with them. It exists to tell the Real column apart
# from the Meta column ON THE FORM, where both are asked; a tile has no such
# twin, and on the in-progress row it is wrong as well — those values come from
# the nightly form, not the weekly form's Real column.
_KI_SHORT_LABELS = {
    "ki_new_people_real":        "New People",
    "ki_member_lessons_real":    "Lessons w/ Member",
    "ki_friends_sacrament_real": "Friends at Sacrament",
    "ki_friends_first_week_real": "Friends · First Week",
    "ki_baptismal_date_real":    "On Baptismal Date",
    "ki_baptized_confirmed_real": "Baptized",
    "ki_rc_at_church_real":      "RC at Church",
}


def _ki_label(key: str, fallback: str) -> str:
    """A Key Indicator's tile label: the short form, or the catalogue name with
    the form's "(Real)"/"(Meta)" suffix stripped if no short form exists."""
    short = _KI_SHORT_LABELS.get(key)
    if short:
        return t(short)
    label = METRIC_LABELS.get(key, fallback)
    for suffix in (" (Real)", " (Meta)"):
        if label.endswith(suffix):
            return label[: -len(suffix)]
    return label


def _ki_goal_note(key: str, set_by: dict, areas: int) -> str:
    """Small print under a KI goal bar when not every area set one.

    A blank meta counts as zero — an area that wrote down no goal committed to
    nothing — so a mission goal can rest on a handful of areas and look exactly
    like one every area signed up to. ki_baptized_confirmed is the live case: 6
    of 33 areas set a goal there while all 33 reported results.

    ``areas`` MUST be the number of areas behind the VALUE being shown, not the
    number behind the goal. Comparing the goal's setters against their own week
    is always n of n and can never fire — which on 2026-08-21 left the last
    complete week reading "204, 2040% of goal 10" with nothing to explain it:
    33 areas reported results for the week ending 08-16, but its goals were
    written on the 08-09 form, which exactly one area submitted.
    """
    n = int(set_by.get(key, 0) or 0)
    if not n or not areas or n >= areas:
        return ""
    return t("{n} of {total} areas set a goal", n=fmt_int(n), total=fmt_int(areas))


# ── 2a. The week in progress ───────────────────────────────────────────────────
render_section_label(
    t("Key Indicators — Current Week ({span})",
      span=fmt_week_span(_this_monday, _this_sunday))
)

if not _ki_metrics:
    st.info(_EMPTY_MSG)
else:
    # Monday-to-today, not the rolling val_7d the rest of the page uses: a
    # rolling seven days straddles two reporting weeks and cannot be compared
    # against a Monday–Sunday goal. It does mean an early-week total looks small
    # against a full week's goal, which is what the pace line below is for.
    _pace_pct = round(_wtd_days / 7 * 100)
    st.caption(
        t("Day {n} of 7 · nightly reports through {day} · goals set by "
          "{areas} areas on last week's form.",
          n=fmt_int(_wtd_days),
          day=fmt_day_month(_today),
          areas=fmt_int(_cur_goal_areas))
    )

    _cur_cards = []
    for k, label in _ki_metrics.items():
        source = _KI_NIGHTLY_SOURCE.get(k)
        measured = source is not None and source in _wtd_totals
        # A relabelled tile shows no goal bar. The relabel is not cosmetic —
        # baptismal_calendars counts calendars handed out this week, a flow,
        # while ki_baptismal_date's goal counts friends who hold a date, a
        # standing total. Charting one against the other put a permanent ~20%
        # on screen that measured nothing. A tile that is honest about being a
        # different quantity does not inherit the other quantity's target.
        borrowed = k in _KI_NIGHTLY_RELABEL
        _cur_cards.append({
            "label": _KI_NIGHTLY_RELABEL.get(k, _ki_label(k, label)),
            "value": int(_wtd_totals.get(source, 0)) if measured else "—",
            "goal":  0 if borrowed else _cur_goals.get(k, 0),
            "goal_note": "" if borrowed
                         else _ki_goal_note(k, _cur_goal_set_by, _cur_goal_areas),
            # Nightly totals come from however many areas filed a report this
            # week; the goal from however many wrote one down last week. Those
            # are different sets, so the percentage is computed per area.
            "value_basis": _wtd_areas,
            "goal_basis":  _cur_goal_set_by.get(k, 0),
        })
    render_kpi_row(_cur_cards)

    st.caption(
        t("Three indicators are counted live from the nightly form; the other "
          "four arrive with the weekly form. Pace: {pct}% of the week elapsed.",
          pct=fmt_int(_pace_pct))
    )

# ── 2b. The last complete week ─────────────────────────────────────────────────
_ki_span = (
    fmt_week_span(_ki_week_end - timedelta(days=6), _ki_week_end)
    if _ki_week_end is not None else ""
)
if not _ki_span:
    render_section_label(t("Key Indicators — Last Complete Week"))
elif _ki_is_partial:
    render_section_label(
        t("Key Indicators — Week of {span} (in progress)", span=_ki_span))
else:
    render_section_label(t("Key Indicators — Week of {span}", span=_ki_span))

# The reporting denominator, stated on the page rather than left to be assumed.
# A weekly total is a sum over whoever submitted; printing "31 de 43 áreas
# informaron" is what stops a low week from being read as a bad week.
_ki_reported = _ki_reporting.get(str(_ki_week_end), 0) if _ki_week_end else 0
if _active_areas:
    _ki_pct = round(_ki_reported / _active_areas * 100)
    if _ki_is_partial:
        st.caption(t("{n} of {total} areas have reported so far.",
                     n=fmt_int(_ki_reported), total=fmt_int(_active_areas)))
    else:
        st.caption(t("{n} of {total} areas reported · {pct}%",
                     n=fmt_int(_ki_reported), total=fmt_int(_active_areas),
                     pct=fmt_int(_ki_pct)))

if not _ki_metrics:
    st.info(_EMPTY_MSG)
else:
    render_kpi_row([
        {
            "label": _ki_label(k, label),
            "value": int(_ki_val(k)),
            "goal":  _past_goals.get(k, 0),
            # Denominator is who reported RESULTS this week, not who set the
            # goals — see _ki_goal_note. Without that, the 1-of-33 case is
            # silent and the bar reads 2040% unexplained.
            "goal_note": _ki_goal_note(k, _past_goal_set_by, _ki_reported),
            "value_basis": _ki_reported,
            "goal_basis":  _past_goal_set_by.get(k, 0),
        }
        for k, label in _ki_metrics.items()
    ])

# ═══════════════════════════════════════════════════════════════════════════════
# 3. ZONES — PER-AREA AVERAGE ACROSS THE FINDING FUNNEL (last 7 days)
# ═══════════════════════════════════════════════════════════════════════════════
# Every figure here is divided by the zone's active area count, never shown raw:
# zones run 8 to 13 areas, so a raw total ranks by size (audit finding C2). The
# arithmetic — and the reason the divisor is ALL active areas rather than the
# ones that reported — lives in app/analytics/zone_comparison.py.

#: The funnel, in the order a contact travels it. Fixed here rather than read
#: from flavor.nightly_highlights: that property is sourced from SCORE_CONFIG's
#: *effort* weights, which exist to weight the effort score, not to choose what
#: a president compares zones on. It yields contacts_attempted, roleplays and
#: member_contacts — two of the three are inputs, not outcomes (audit H1).
_ZONE_FUNNEL_KEYS = [
    "contacts_attempted",
    "contacts_made",
    "friend_lessons",
    "baptismal_invitations",
]

#: Column headers, trimmed to keep eight columns readable on one line. Trimmed
#: phrases in the _KI_SHORT_LABELS style, with one deliberate abbreviation:
#: "Invitaciones" alone is ambiguous against church_invites ("Invitaciones a la
#: Iglesia"), and the unabbreviated "Invitaciones al Bautismo" is wide enough to
#: wrap the column. Naming the wrong thing is the worse failure of the two.
_ZONE_SHORT_LABELS = {
    "contacts_attempted":    "Attempts",
    "contacts_made":         "Contacts",
    "friend_lessons":        "Lessons w/ Friends",
    "baptismal_invitations": "Bapt. Invitations",
}

#: Where the sort falls back to while Effectiveness is still missing its Key
#: Indicator third (see effectiveness_is_rankable). An outcome, complete today,
#: and hard to inflate.
_ZONE_FALLBACK_SORT = "friend_lessons"

#: Per-area average or raw zone total. Stored in session_state as these stable
#: keys rather than as the translated label: a language switch mid-session would
#: leave a Spanish label sitting in a widget whose options had become English.
_ZONE_MODE_PER_AREA = "per_area"
_ZONE_MODE_TOTAL    = "total"


def _zone_mode_label(mode: str) -> str:
    return (t("Per area") if mode == _ZONE_MODE_PER_AREA
            else t("Zone total"))


# The heading names the reading, so it has to be decided BEFORE the radio that
# sets it is drawn — Streamlit renders in source order. Reading session_state
# first is what lets the control sit under its own heading rather than above it.
_zone_mode = st.session_state.get("panel_zone_mode", _ZONE_MODE_PER_AREA)
_zone_per_area = _zone_mode != _ZONE_MODE_TOTAL

render_section_label(t("Zones — Per-Area Average (7 Days)") if _zone_per_area
                     else t("Zones — Zone Totals (7 Days)"))

# Effectiveness comes from SCORES' newest scored week. It is the one column on
# a different clock from the rolling 7 days, and the one column the per-area /
# total switch does not apply to — see zone_comparison_table.
_zone_eff_week = None
_zone_scores = pd.DataFrame()
_zone_scored_weeks = get_scored_weeks()
if _zone_scored_weeks:
    _zone_eff_week = _zone_scored_weeks[0]
    _zone_scores = get_scores(_zone_eff_week)

_zone_num = zone_comparison_table(
    zone_df, get_submitting_areas(), _ZONE_FUNNEL_KEYS, _zone_scores,
    per_area=_zone_per_area)

_zone_cols = [(k, t(_ZONE_SHORT_LABELS[k])) for k in _ZONE_FUNNEL_KEYS]
if ZONE_EFFECTIVENESS in _zone_num.columns:
    _zone_cols.append((ZONE_EFFECTIVENESS, t("Effectiveness")))

_zone_eff_ready = (
    ZONE_EFFECTIVENESS in _zone_num.columns
    and effectiveness_is_rankable(_zone_scores, _active_areas)
)
_zone_default_key = (ZONE_EFFECTIVENESS if _zone_eff_ready
                     else _ZONE_FALLBACK_SORT)

if _zone_num.empty:
    st.info(t("No zone totals yet — MISSION_ORG lists no active areas, or the "
              "nightly agent has not written DASHBOARD_SUMMARY."))
else:
    _zone_keys = [k for k, _ in _zone_cols]
    _zone_lbl  = dict(_zone_cols)
    _zone_idx  = (_zone_keys.index(_zone_default_key)
                  if _zone_default_key in _zone_keys else 0)

    # Both controls key on stable identifiers with a format_func, never on the
    # translated label — a mid-session language switch would otherwise leave a
    # stored Spanish string in a widget whose options had turned English.
    _sort_col, _mode_col, _ = st.columns([1, 1, 1])
    with _sort_col:
        _zone_sort_key = st.selectbox(
            t("Sort by"), _zone_keys, index=_zone_idx,
            format_func=lambda k: _zone_lbl[k], key="panel_zone_sort")
    with _mode_col:
        st.radio(
            t("Show"), [_ZONE_MODE_PER_AREA, _ZONE_MODE_TOTAL],
            format_func=_zone_mode_label, horizontal=True,
            key="panel_zone_mode")

    _zone_num = (_zone_num.sort_values(_zone_sort_key, ascending=False)
                          .reset_index(drop=True))

    # The Areas column is shown in BOTH modes: per area it is the divisor, so
    # the arithmetic is checkable without leaving the page; on totals it is the
    # reason one zone outranks another, which is the whole of finding C2.
    _zone_tbl = pd.DataFrame({
        t("Rank"):  [str(i) for i in range(1, len(_zone_num) + 1)],
        t("Zone"):  _zone_num["zone"],
        t("Areas"): _zone_num["areas"].map(fmt_int),
    })
    for _k, _lbl in _zone_cols:
        # Counts follow the switch; Effectiveness is a 0-100 score and keeps its
        # decimal in both modes.
        _places = 1 if (_zone_per_area or _k == ZONE_EFFECTIVENESS) else 0
        _zone_tbl[_lbl] = _zone_num[_k].map(
            lambda v, p=_places: fmt_number(v, p))
    render_table(_zone_tbl)

    if not _zone_per_area:
        st.caption(t("Zone totals rank by zone size — these zones run "
                     "{low} to {high} areas."
                     " Effectiveness stays a per-area average.",
                     low=fmt_int(_zone_num["areas"].min()),
                     high=fmt_int(_zone_num["areas"].max())))

    if _zone_eff_week and not _zone_eff_ready:
        st.caption(t(
            "Effectiveness does not lead the ranking yet: its Key Indicator "
            "component is still 0 for most areas ({n} of {total} scored), "
            "because a week's KI goals are set on the previous week's form.",
            n=fmt_int(ki_scored_area_count(_zone_scores)),
            total=fmt_int(_active_areas)))

# ═══════════════════════════════════════════════════════════════════════════════
# 4. EIGHT-WEEK TRENDS (mission totals)
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("8-Week Trend — Mission Totals"))

trends_chart = exclude_current_week(trends_df)
ki_chart     = exclude_current_week(ki_df)
if trends_chart.empty or "week_end_date" not in trends_chart.columns:
    st.info(_EMPTY_MSG)
else:
    weeks = trends_chart["week_end_date"].astype(str)

    col_a, col_b = st.columns(2)

    with col_a:
        fig1 = go.Figure()
        for i, key in enumerate(flavor.nightly_highlights):
            if key in trends_chart.columns:
                fig1.add_trace(go.Scatter(
                    x=weeks, y=trends_chart[key], mode="lines+markers",
                    name=METRIC_LABELS.get(key, key),
                    line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2),
                    marker=dict(size=6),
                ))
        fig1.update_layout(
            title=t("Nightly Activity"),
            xaxis_title=t("Week Ending"), yaxis_title=t("Count"),
            xaxis_type="category", hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=50, b=40, l=40, r=20),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        fig2 = go.Figure()
        ki_weeks = ki_chart["week_end_date"].astype(str) if not ki_chart.empty else weeks
        for i, key in enumerate(key_indicator_metrics()):
            if not ki_chart.empty and key in ki_chart.columns:
                fig2.add_trace(go.Scatter(
                    x=ki_weeks, y=ki_chart[key], mode="lines+markers",
                    name=METRIC_LABELS.get(key, key),
                    line=dict(color=CHART_COLORS[(i + 2) % len(CHART_COLORS)], width=2),
                    marker=dict(size=6),
                ))
        fig2.update_layout(
            title=t("Key Indicators"),
            xaxis_title=t("Week Ending"), yaxis_title=t("Count"),
            xaxis_type="category", hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=50, b=40, l=40, r=20),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 5. DAILY TREND — headline nightly metric, last 7 days
# ═══════════════════════════════════════════════════════════════════════════════
# Was hardcoded to nm_lessons ("Non-Member Lessons per Day"). CCSM's nightly
# form has no such question, so the guard below always fell to _EMPTY_MSG and
# this section has never drawn anything.
_daily_key = next(
    (k for k in flavor.nightly_highlights if k in daily_df.columns),
    "",
) if not daily_df.empty else ""
_daily_label = METRIC_LABELS.get(_daily_key, _daily_key)

render_section_label(
    t("Daily {metric} — Last 7 Days", metric=_daily_label) if _daily_key
    else t("Daily Trend — Last 7 Days")
)

if not _daily_key:
    st.info(_EMPTY_MSG)
else:
    date_col = "Date" if "Date" in daily_df.columns else daily_df.columns[0]
    fig_daily = px.bar(
        daily_df,
        x=date_col,
        y=_daily_key,
        labels={date_col: t("Date"), _daily_key: _daily_label},
        title=t("{metric} per day (mission total)", metric=_daily_label),
        color_discrete_sequence=["#6366f1"],
    )
    fig_daily.update_layout(
        xaxis_title=t("Date"),
        xaxis_type="category",
        yaxis_title=_daily_label,
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig_daily, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 6. DAILY EFFORT BREAKDOWN — last 7 days
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Daily Effort Breakdown — Last 7 Days"))

if effort_df.empty:
    st.info(_EMPTY_MSG)
else:
    all_count  = int(effort_df["all_count"].sum())
    most_count = int(effort_df["most_count"].sum())
    some_count = int(effort_df["some_count"].sum())

    effort_data = pd.DataFrame({
        "Effort Level": ["All", "Most", "Some"],
        "Count":        [all_count, most_count, some_count],
    })

    fig_effort = px.bar(
        effort_data,
        x="Effort Level",
        y="Count",
        color="Effort Level",
        color_discrete_map={
            "All":  "#22c55e",
            "Most": "#f59e0b",
            "Some": "#ef4444",
        },
        title="Area Effort Levels Across Last 7 Days",
    )
    fig_effort.update_layout(
        showlegend=False,
        margin=dict(t=40, b=20),
        yaxis_title="Day-Area Count",
    )
    st.plotly_chart(fig_effort, use_container_width=True)

    e1, e2, e3 = st.columns(3)
    e1.metric(t("All Effort"),  all_count,  help=t("Areas reporting full effort"))
    e2.metric(t("Most Effort"), most_count, help=t("Areas reporting most effort"))
    e3.metric(t("Some Effort"), some_count, help=t("Areas reporting some effort"))

    area_effort = get_effort_by_area(days=7)
    with st.expander(t("Effort by area — who reported what (last 7 days)")):
        if area_effort.empty:
            st.caption(t("No per-area effort responses in the last 7 days."))
        else:
            st.caption(
                t("{n} areas · sorted by effort score "
                  "(All=3, Most=2, Some=1, averaged per submission). "
                  "Counts are submissions per area over the last 7 days.",
                  n=len(area_effort))
            )
            render_table(area_effort)

# ═══════════════════════════════════════════════════════════════════════════════
# 7. SUBMISSION COMPLIANCE — all-time summary, calendars, per-area detail
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Submission Compliance"))

comp_df = get_alltime_compliance()

if comp_df.empty:
    mission_pct, days_tracked, areas_current, total_forms = "—", "—", "—", "—"
else:
    total_sub      = int(comp_df["days_submitted"].sum())
    total_possible = int(comp_df["days_possible"].sum())
    mission_pct    = round(total_sub / total_possible * 100) if total_possible else 0
    days_tracked   = int(comp_df["days_possible"].max())
    areas_current  = int((comp_df["pct"] >= 100).sum())
    total_forms    = total_sub

render_kpi_row([
    {"label": "Total Forms Submitted", "value": str(total_forms)},
    {"label": "Compliance All-Time", "value": f"{mission_pct}%" if mission_pct != "—" else "—"},
    {"label": "Days Tracked",        "value": str(days_tracked)},
    {"label": "Areas at 100%",       "value": str(areas_current)},
])

# ── Nightly submission compliance — daily % calendar heatmap ──────────────────
render_section_label(t("Nightly Submission Compliance — Daily %"))

_subm_areas  = get_submitting_areas()
_daily_all   = get_daily_log(days=45)
_total_areas = (
    _subm_areas["Area_Name"].astype(str).str.strip().nunique()
    if not _subm_areas.empty and "Area_Name" in _subm_areas.columns else 0
)

if _total_areas == 0 or _daily_all.empty or "Date" not in _daily_all.columns:
    st.info(t("No nightly compliance data yet."))
else:
    _submitting_set = set(_subm_areas["Area_Name"].dropna().astype(str).str.strip())
    _dl = _daily_all.copy()
    _dl["Area"] = _dl["Area"].astype(str).str.strip()
    _dl = _dl[_dl["Area"].isin(_submitting_set)]
    _per_day_counts = _dl.groupby("Date")["Area"].nunique().to_dict()

    _mb_sys_start = get_config_value("SYSTEM_START_DATE", "")
    _mb_anchor    = compliance_anchor_date()
    _mb_win_end   = _mb_anchor.isoformat()
    _mb_thirty    = (_mb_anchor - timedelta(days=29)).isoformat()
    _mb_win_start = max(_mb_sys_start, _mb_thirty) if _mb_sys_start else _mb_thirty

    _mb_cal = build_calendar_data(set(), _mb_win_end, n_weeks=5, anchor_date=_mb_anchor)

    def _mb_pct_color(p: int):
        if p >= 85:
            return "rgba(34,197,94,0.25)", "#22c55e"
        if p >= 70:
            return "rgba(245,158,11,0.22)", "#f59e0b"
        return "rgba(239,68,68,0.20)", "#ef4444"

    _mb_day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _mb_hdr = "".join(
        f'<th style="text-align:center;padding:4px 8px;color:#9ca3af;font-size:0.72rem;font-weight:600;">{d}</th>'
        for d in _mb_day_labels
    )

    _counted_pcts = []
    _mb_body = ""
    for week in _mb_cal:
        cells = ""
        for cell in week:
            d = cell["date"]
            day_num = d[8:]
            if cell["future"]:
                bg, fg, pct_txt, title = "rgba(255,255,255,0.02)", "#374151", "", f"{d} — upcoming"
            elif d < _mb_win_start:
                bg, fg, pct_txt, title = "rgba(255,255,255,0.03)", "#4b5563", "", f"{d} — before tracking started"
            else:
                n = _per_day_counts.get(d, 0)
                pct = round(n / _total_areas * 100) if _total_areas else 0
                _counted_pcts.append(pct)
                bg, fg = _mb_pct_color(pct)
                pct_txt = f"{pct}%"
                title = f"{d} — {n}/{_total_areas} areas submitted ({pct}%)"
            pct_html = (
                f'<div style="font-size:0.8rem;font-weight:700;color:{fg};">{pct_txt}</div>'
                if pct_txt else '<div style="font-size:0.8rem;">&nbsp;</div>'
            )
            cells += (
                f'<td title="{title}" style="text-align:center;padding:5px 4px;background:{bg};'
                f'border-radius:4px;vertical-align:middle;">'
                f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{day_num}</div>'
                f'{pct_html}</td>'
            )
        _mb_body += f"<tr>{cells}</tr>"

    def _mb_legend_item(color, label):
        return (
            f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
            f'border-radius:2px;margin-right:4px;"></span>{label}&nbsp;&nbsp;&nbsp;'
        )

    st.markdown(
        f'<table style="width:100%;border-collapse:separate;border-spacing:3px;margin-bottom:0.5rem;">'
        f'<thead><tr>{_mb_hdr}</tr></thead><tbody>{_mb_body}</tbody></table>'
        f'<div style="font-size:0.72rem;color:#9ca3af;margin-bottom:0.5rem;">'
        + _mb_legend_item("rgba(34,197,94,0.25)", "&ge;85%")
        + _mb_legend_item("rgba(245,158,11,0.22)", "70–84%")
        + _mb_legend_item("rgba(239,68,68,0.20)", "&lt;70%")
        + _mb_legend_item("rgba(255,255,255,0.03)", "Upcoming / pre-tracking")
        + "</div>",
        unsafe_allow_html=True,
    )

    if _counted_pcts:
        _avg = round(sum(_counted_pcts) / len(_counted_pcts))
        st.markdown(
            f'<p style="color:#9ca3af;font-size:0.82rem;">Each box is the share of the mission\'s '
            f'<strong style="color:#f4f4f8;">{_total_areas}</strong> submitting areas that turned in '
            f'the nightly form that day. Window average: '
            f'<strong style="color:#f4f4f8;">{_avg}%</strong>.</p>',
            unsafe_allow_html=True,
        )

# ── Weekly report submission — % of areas submitting the weekly form, by week ─
render_section_label(t("Weekly Report Submission — By Week"))

_nightly_avg = (
    sum(_counted_pcts) / len(_counted_pcts)
    if "_counted_pcts" in locals() and _counted_pcts else None
)

_wk_all       = get_weekly_submission_data()
_wk_sys_start = get_config_value("SYSTEM_START_DATE", "")
_wk_anchor    = latest_due_sunday()
_wk_due_weeks = weekly_due_weeks(_wk_sys_start, anchor_sunday=_wk_anchor, n_weeks=8)

def _wk_leg(color, label):
    return (
        f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
        f'border-radius:2px;margin-right:4px;"></span>{label}&nbsp;&nbsp;&nbsp;'
    )

_weekly_avg = None
if _total_areas == 0 or not _wk_due_weeks:
    st.info(t("No weekly submission data yet."))
else:
    _wk_submitting = (
        set(_subm_areas["Area_Name"].dropna().astype(str).str.strip())
        if not _subm_areas.empty and "Area_Name" in _subm_areas.columns else set()
    )
    if not _wk_all.empty and "area" in _wk_all.columns:
        _wk = _wk_all.copy()
        _wk["area"] = _wk["area"].astype(str).str.strip()
        if _wk_submitting:
            _wk = _wk[_wk["area"].isin(_wk_submitting)]
        _per_week_counts = _wk.groupby("week_end_date")["area"].nunique().to_dict()
    else:
        _per_week_counts = {}

    def _wk_pct_color(p):
        if p >= 85:
            return "rgba(34,197,94,0.25)", "#22c55e"
        if p >= 70:
            return "rgba(245,158,11,0.22)", "#f59e0b"
        return "rgba(239,68,68,0.20)", "#ef4444"

    _wk_pcts, _wk_cells = [], ""
    for w in _wk_due_weeks:
        _wd = date.fromisoformat(w)
        n   = _per_week_counts.get(w, 0)
        pct = round(n / _total_areas * 100) if _total_areas else 0
        _wk_pcts.append(pct)
        bg, fg = _wk_pct_color(pct)
        _wk_cells += (
            f'<td title="Week ending {w} — {n}/{_total_areas} areas submitted ({pct}%)" '
            f'style="text-align:center;padding:6px 8px;background:{bg};border-radius:4px;'
            f'vertical-align:middle;min-width:52px;">'
            f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1.2;">{_wd.month}/{_wd.day}</div>'
            f'<div style="font-size:0.8rem;font-weight:700;color:{fg};">{pct}%</div></td>'
        )
    st.markdown(
        '<table style="border-collapse:separate;border-spacing:3px;margin-bottom:0.5rem;">'
        f'<tbody><tr>{_wk_cells}</tr></tbody></table>'
        '<div style="font-size:0.72rem;color:#9ca3af;margin-bottom:0.5rem;">'
        + _wk_leg("rgba(34,197,94,0.25)", "&ge;85%")
        + _wk_leg("rgba(245,158,11,0.22)", "70–84%")
        + _wk_leg("rgba(239,68,68,0.20)", "&lt;70%")
        + '</div>',
        unsafe_allow_html=True,
    )

    _weekly_avg = sum(_wk_pcts) / len(_wk_pcts) if _wk_pcts else None
    if _weekly_avg is not None:
        st.markdown(
            f'<p style="color:#9ca3af;font-size:0.82rem;">Each box is the share of the mission\'s '
            f'<strong style="color:#f4f4f8;">{_total_areas}</strong> areas that submitted the weekly '
            f'form for that Mon–Sun week (credited by the day it arrived). Window average: '
            f'<strong style="color:#f4f4f8;">{round(_weekly_avg)}%</strong>.</p>',
            unsafe_allow_html=True,
        )

if _nightly_avg is not None and _weekly_avg is not None:
    _combined = round((_nightly_avg + _weekly_avg) / 2)
    _cc = "#22c55e" if _combined >= 85 else ("#f59e0b" if _combined >= 70 else "#ef4444")
    st.markdown(
        f'<div style="margin-top:0.5rem;padding:10px 14px;border-radius:6px;'
        f'background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);">'
        f'<span style="color:#9ca3af;font-size:0.82rem;">Combined submission compliance '
        f'(nightly + weekly, averaged): </span>'
        f'<strong style="color:{_cc};font-size:1.05rem;">{_combined}%</strong>'
        f'<span style="color:#6b7280;font-size:0.75rem;"> &nbsp;— nightly {round(_nightly_avg)}%, '
        f'weekly {round(_weekly_avg)}%</span></div>',
        unsafe_allow_html=True,
    )

# ── Per-area submission detail (folded in from the old Submissions page) ───────
with st.expander(t("Area Submission Detail — all-time compliance per area")):
    if comp_df.empty:
        st.info(t("No per-area submission data available yet."))
    else:
        detail = comp_df.copy()

        def _sub_status(pct: float) -> str:
            if pct >= 90:
                return "On Track"
            if pct >= 50:
                return "Partial"
            return "Behind"

        detail["Status"] = detail["pct"].apply(_sub_status)

        f1, f2 = st.columns([2, 2])
        # Sentinel is translated for display but compared against the same
        # t() call below, never against a bare English literal.
        _all_zones = t("All Zones")
        zone_opts = [_all_zones] + sorted(detail["zone"].dropna().astype(str).unique().tolist())
        with f1:
            zsel = st.selectbox(t("Zone"), zone_opts, key="dash_sub_zone")
        with f2:
            # Translated label -> English value. Only the label is shown; every
            # comparison below still runs on the English value, so filtering
            # behaves identically in either language.
            _show_opts = {
                t("All"): "All",
                t("Behind only"): "Behind only",
                t("On Track only"): "On Track only",
            }
            ssel = _show_opts[st.radio(
                t("Show"), list(_show_opts),
                horizontal=True, key="dash_sub_show",
            )]

        view = detail
        if zsel != _all_zones:
            view = view[view["zone"] == zsel]
        if ssel == "Behind only":
            view = view[view["Status"] == "Behind"]
        elif ssel == "On Track only":
            view = view[view["Status"] == "On Track"]

        view = view.sort_values(["pct", "area"], ascending=[True, True])

        # Headers are translated only at the point of display, after every
        # filter and sort above has run on the English column names.
        _cols = {
            "area": t("Area"), "zone": t("Zone"), "district": t("District"),
            "days_submitted": t("Days Submitted"),
            "days_possible": t("Days Possible"),
            "pct": t("Compliance %"), "last_date": t("Last Submitted"),
            "Status": t("Status"),
        }
        disp = view.rename(columns=_cols)[list(_cols.values())]
        # detail["Status"] stays English so the filters above keep working;
        # translate the cell values for display only.
        disp[t("Status")] = disp[t("Status")].map(lambda s: t(s))

        st.caption(t("{n} area(s) shown — worst first", n=len(disp)))
        if disp.empty:
            st.info(t("No areas match the current filter."))
        else:
            render_table(disp)
