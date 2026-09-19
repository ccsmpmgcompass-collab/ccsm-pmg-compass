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
from app.components.charts import chart, ranked_list, spark_multiples
from app.components.ki_drilldown import (
    ki_href, render_ki_drilldown, TAB_CYCLE, TAB_WEEK,
)
from app.components.design_system import (
    CALENDAR_FUTURE, CALENDAR_PRETRACKING,
    compliance_legend_bands, compliance_tint,
    render_page_header,
    render_section_label, render_kpi_row, render_table,
)
from app.config.flavor_loader import flavor, METRIC_LABELS
from app.config.metric_catalog import (
    key_indicator_metrics, ki_short_label, nightly_metrics,
)
from app.i18n import t
from app.i18n.formats import (
    fmt_int, fmt_number, fmt_percent, fmt_week_span, fmt_day_month,
    fmt_month_abbr,
)
from app.components.charts import GOAL_LINE, MAGNITUDE
from app.config.theme import DIM, INK, MUTED, SERIES_COLORS, STATUS
from app.db.queries import (
    get_mission_baptisms_by_month,
    get_mission_totals,
    get_zone_totals,
    get_daily_effort_log,
    get_nightly_weekly_trends,
    get_weekly_ki_totals,
    get_weekly_ki_reporting,
    get_weekly_form_data,
    select_reporting_week,
    exclude_current_week,
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
    get_agent_config,
)
from app.analytics.zone_comparison import (
    zone_comparison_table, mission_summary_row, effectiveness_is_rankable,
    ki_scored_area_count, zone_ki_table, zone_ki_mission_row,
    EFFECTIVENESS as ZONE_EFFECTIVENESS,
)
from app.analytics.period_delta import (
    reporting_dates, window_pair, window_totals, window_areas, days_in_window,
    period_delta, point_delta, MIN_COMPARABLE_DAYS, WINDOW_DAYS,
)
from app.analytics.rate_metrics import rate_rows
from app.utils.transfer_helpers import (
    transfer_cycles, transfer_period_bounds, transfer_window,
)
from app.analytics import transfer_year as ty
from app.analytics import ki_history as kh
from app.db.goals_queries import areas_with_goals, group_goal_totals
from app.analytics import annual_baptisms as ab
from app.analytics import effort_breakdown as eb
from app.analytics import compliance_rankings as cr
from app.utils.area_helpers import (
    compliance_anchor_date, build_calendar_data, mission_today,
    latest_due_sunday, weekly_due_weeks,
)
from datetime import date, timedelta
from html import escape as _html_escape
from urllib.parse import urlencode

# Page chrome (set_page_config / inject_global_css / render_sidebar) is
# owned by Home.py's st.navigation router since 2026-09-02 — the router and
# this page share one script run, so calling them here would render twice.
user = require_auth()

_mission_name = get_config_value("MISSION_NAME", flavor.display_name)
render_page_header(t("PMG Compass"),
                   t("{mission} — Executive Dashboard", mission=_mission_name))

_EMPTY_MSG = t("No data for this section yet.")

# The page opened with a three-sentence caption: when the summary refreshes,
# that compliance is live, and that this page is mission-level only. The last
# is no longer true in the way it was written — every Key Indicator card opens
# its own drill-down — and the other two describe particular sections rather
# than the page, so they are those sections' ⓘ and right-hand lines now
# (audit X4, data-pages plan C2).


# ── Load data ─────────────────────────────────────────────────────────────────

mission_df = get_mission_totals()
zone_df    = get_zone_totals()
nightly_trends_df = get_nightly_weekly_trends(8)
ki_df      = get_weekly_ki_totals(8)
app_goals  = get_mission_goals()

all_empty = (
    mission_df.empty
    and zone_df.empty
    and nightly_trends_df.empty
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
# The mission's own date, not the server's: this app runs on Streamlit Cloud in
# UTC, which rolls over to tomorrow in the evening mission-local — exactly when
# the nightly reports are being filed. The drill-down under the scoreboard
# already uses mission_today(), and the two must agree on what week it is.
_today = mission_today()
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


def _ki_row_for_week(week_end):
    """The weekly-totals row for a given week end, or None if that week is
    absent. Looked up BY DATE rather than by taking the row before the chosen
    one: weeks with no submissions at all have no row, so "the previous row" and
    "the previous week" are not the same thing — the same trap
    get_ki_goals_for_week already avoids for goals."""
    if ki_df.empty or week_end is None or "week_end_date" not in ki_df.columns:
        return None
    ends = pd.to_datetime(ki_df["week_end_date"], errors="coerce").dt.date
    match = ki_df[ends == week_end]
    return match.iloc[0] if not match.empty else None


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
# progress there is no ki_*_real to show. Two of the seven Key Indicators are
# asked nightly in the same words and can be totalled Monday-to-today; the rest
# show their goal with no value rather than a zero (see render_kpi_row -- a zero
# would report a failure, an em dash reports an absence).
_KI_NIGHTLY_SOURCE = {
    "ki_new_people_real":     "new_people_found",
    "ki_member_lessons_real": "lessons_member_present",
}

#: A nightly metric that is CLOSE to a Key Indicator but is not it, shown as the
#: card's small print rather than as its value. ki_baptismal_date counts friends
#: who currently HOLD a date — a standing count; baptismal_calendars counts
#: calendars handed out — a flow. Borrowing the flow as the indicator's
#: mid-week value meant relabelling the tile, and with one scoreboard row that
#: would put a name which is not a Key Indicator among six that are (decision
#: 11: these seven labels are constant app-wide). The figure is worth seeing and
#: is kept; the claim that it IS the indicator is not.
_KI_NIGHTLY_NOTE = {
    "ki_baptismal_date_real": "baptismal_calendars",
}

_wtd_totals = get_week_to_date_totals(_this_monday, _today)
_wtd_areas = get_week_to_date_areas(_this_monday, _today)
_wtd_days = (_today - _this_monday).days + 1


# ── The two windows every "vs. before" on this page is measured across ─────────
# One DAILY_LOG read, shared by §1 (rolling 7 days) and §2a (the week so far).
# 30 days is enough for both and for the prior side of each.
#
# The windows are computed here rather than taken from DASHBOARD_SUMMARY's
# val_7d / val_14d. Those exist and the audit called using them the cheapest fix
# on the board (H3) -- but CCSM_Agent3.gs cuts at `date >= today - 7`, which is
# EIGHT calendar dates, while the prior window implied by val_14d - val_7d is
# seven. See app/analytics/period_delta.py for what that does to the arrows, and
# for why a date only counts once half the mission has filed on it.
_daily_log = get_daily_log(30)
_report_dates = reporting_dates(_daily_log, _active_areas)
_night_anchor = _report_dates[-1] if _report_dates else None

if _night_anchor is not None:
    _cur_start, _cur_end, _prev_start, _prev_end = window_pair(_night_anchor)
    _cur_days = days_in_window(_report_dates, _cur_start, _cur_end)
    _prev_days = days_in_window(_report_dates, _prev_start, _prev_end)
    _cur_totals = window_totals(_daily_log, _cur_start, _cur_end)
    _prev_totals = window_totals(_daily_log, _prev_start, _prev_end)
else:
    _cur_start = _cur_end = _prev_start = _prev_end = None
    _cur_days = _prev_days = 0
    _cur_totals = _prev_totals = {}

#: Label under every arrow on this page's rolling-7-day tiles.
_VS_PRIOR_WEEK = t("vs prior 7 days")

#: The rolling nightly window every figure on this page that is NOT from
#: the weekly form describes — the zone funnel, nightly activity and the
#: conversion rates — and, when the prior side is too thin to compare
#: against, why those sections carry no arrows. Both were captions under
#: the rows until step C2 (audit X4); the window is a heading's right-hand
#: line now and the refusal is a chip on the card. Defined here, above
#: every section that reads it, because zones (§3) comes before nightly
#: activity (§4a) since step C1, and — when
#: the prior side is too thin to compare against — why there are no arrows.
#: Both were captions under the rows until step C2 (audit X4).
_night_window = (
    t("{start}–{end} · {n} reporting days",
      start=fmt_day_month(_cur_start), end=fmt_day_month(_cur_end),
      n=fmt_int(_cur_days))
    if _night_anchor is not None else ""
)
_night_no_change = ""
_night_scaled = ""
if _night_anchor is not None:
    if _prev_days < MIN_COMPARABLE_DAYS:
        _night_no_change = t(
            "No comparison yet: the previous 7 days hold {n} days on which at "
            "least half the areas reported, and {need} are needed.",
            n=fmt_int(_prev_days), need=fmt_int(MIN_COMPARABLE_DAYS))
    elif _prev_days < WINDOW_DAYS:
        _night_scaled = t(
            "Compared against {n} reporting days in the previous 7, scaled per "
            "day.", n=fmt_int(_prev_days))

#: The same refusal for the four conversion rates, which have no scaled middle
#: case: a rate does not grow with the days behind it, so a short prior window
#: cannot be corrected for, only refused. See period_delta.point_delta.
_rate_no_change = (
    t("Change is shown in percentage points once the previous 7 days hold "
      "{need} reporting days; they hold {n}.",
      n=fmt_int(_prev_days), need=fmt_int(MIN_COMPARABLE_DAYS))
    if _night_anchor is not None and _prev_days < MIN_COMPARABLE_DAYS else ""
)


# Card labels for the four rates, and the shared rate computation. Both used to
# live inside §1b; moved up here during audit item 8 (a verdict banner that
# named the weakest rate above §1) so the banner and §1b would read the same
# figures. Item 8 was later removed at the user's request (didn't like the
# banner) but this hoist stayed — §1b is the only reader now, same as before,
# just defined one section earlier.
#
# The §1b heading already says these are rates, so repeating "Tasa de" on all
# four cards spends the widest line of the card on a word the reader has just
# read. Same trimming rule as metric_catalog.KI_SHORT_LABELS, and the same reason: the
# catalogue's names are built to be unambiguous in a metric picker, not to fit
# a 200px card.
#
# "Significativas" is not an invention — it is how CCSM_Agent1C.gs already says
# it in the coaching email (A1C_METRIC_LABELS: 'Tasa de Significativas'; the
# leadership KPI tile: 'Signif.'), so email and dashboard agree.
_RATE_SHORT_LABELS = {
    "contact_rate": "Contact",
    "mc_rate":      "Meaningful Conversations",
    "lesson_rate":  "Lessons",
    "close_rate":   "Baptismal Invitation",
}

_rate_rows = rate_rows(_cur_totals, _prev_totals, get_agent_config(),
                       current_days=_cur_days, prior_days=_prev_days)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. KEY INDICATORS — the scoreboard the page opens on
# ═══════════════════════════════════════════════════════════════════════════════
# PLAN-2026-09-18-data-pages.md §4, step C1. Three findings close here:
#
#   P1  the page opened on three nightly outputs and four conversion rates. The
#       seven Key Indicators the mission is actually judged on started at
#       section ③, and baptisms against the annual goal at ⑥, six screens down.
#   P2  fourteen cards for seven metrics: "Semana en curso" and "Semana del 7 al
#       13" were two full rows of the same seven, four of the first row reading
#       "—". One row now, and the period is a toggle above it.
#   X4  those two rows carried five explanatory captions between them. They are
#       the section's ⓘ and its right-hand line instead.
#
# Decision 6 is applied here and it REVERSES what the bar has meant on this
# page. The goal bar is now the COMPANIONSHIPS' own meta — the ki_*_meta each
# area wrote on the previous week's form — because that is the number the
# Church's own app shows the Assistants, and the two must agree. The leadership
# transfer goal from Metas is a labelled MARK on the same bar: the violet tick,
# the same quantity the drill-down draws as a dotted violet line. Until this
# step the card drew the leadership goal while the drill-down directly beneath
# it drew the meta, and the two disagreed by design (PLAN STATUS, B3 note b).
_ki_metrics = key_indicator_metrics()

#: The scope every figure in this section is summed over: every submitting area.
#: The drill-down at the foot of the section is handed the same set, so a card
#: and the panel it opens can never describe two different rosters.
_ki_scope_roster = get_submitting_areas()
_ki_scope_areas = (
    set(_ki_scope_roster["Area_Name"].astype(str).str.strip())
    if "Area_Name" in _ki_scope_roster.columns else set()
)

#: The three readings of the same seven metrics. Stored as stable ids rather
#: than as their translated labels: a language switch mid-session would leave a
#: Spanish string in a widget whose options had turned English — the same rule
#: the zone mode switch and the drill-down's tabs already follow.
_KI_PERIOD_WEEK  = "week"
_KI_PERIOD_LAST  = "last"
_KI_PERIOD_CYCLE = "cycle"
_KI_PERIODS = [_KI_PERIOD_WEEK, _KI_PERIOD_LAST, _KI_PERIOD_CYCLE]


def _ki_period_label(period: str) -> str:
    return {
        _KI_PERIOD_WEEK:  t("This week"),
        _KI_PERIOD_LAST:  t("Last week"),
        _KI_PERIOD_CYCLE: t("This cambio"),
    }.get(period, period)


# The week in progress leads, because it is the week leadership can still act
# on — the ordering the page has always had, now a default rather than a second
# row. It is only honest because the row states its own window and pace, and
# because a metric the weekly form has not delivered yet shows "—" and says
# when it arrives rather than a zero.
_ki_period = st.session_state.get("panel_ki_period_val", _KI_PERIOD_WEEK)
if _ki_period not in _KI_PERIODS:
    _ki_period = _KI_PERIOD_WEEK


def _cycle_label(cycle: dict | None) -> str:
    if not cycle:
        return ""
    return str(cycle.get("number") or "").strip() or fmt_day_month(cycle["start"])


def _leadership_week_goal(week_end) -> tuple[dict, int, str]:
    """The mission's leadership goal for the week ending `week_end`.

    Returns ``({metric: weekly figure}, areas_that_set_one, cycle_label)``. The
    stored goal is a TRANSFER TOTAL, so a week's share of it is that total
    divided by the cycle's real weeks — the same conversion the Desgloses cards
    and the drill-down's violet mark make, so one goal cannot mean two things in
    three places (PLAN §7.5).

    Empty until leadership actually enters goals, in which case the card simply
    carries no mark and the companionships' meta stands alone.
    """
    if week_end is None:
        return {}, 0, ""
    for cycle in transfer_cycles():
        if not (cycle["start"] <= week_end <= cycle["end"]):
            continue
        weeks = max(1.0, ty.weeks_in_cycle(cycle["start"], cycle["end"]))
        totals = group_goal_totals(cycle["start"])
        if not any(totals.values()):
            return {}, 0, ""
        return ({k: v / weeks for k, v in totals.items() if v},
                areas_with_goals(cycle["start"]), _cycle_label(cycle))
    return {}, 0, ""


# The leadership goal for whichever cambio each of the two weeks falls in, as a
# weekly figure. Empty until someone enters one on the Metas page.
_cur_lead_goals, _cur_lead_areas, _cur_lead_label = _leadership_week_goal(_this_sunday)
_past_lead_goals, _past_lead_areas, _past_lead_label = _leadership_week_goal(_ki_week_end)


def _ki_goal_note(key: str, set_by: dict, areas: int) -> str:
    """Small print behind a goal bar when not every area wrote a meta.

    A blank meta counts as zero — an area that wrote down no goal committed to
    nothing — so a mission meta can rest on a handful of areas and look exactly
    like one every area signed up to. ki_baptized_confirmed is the live case: 6
    of 33 areas set a goal there while all 33 reported results.

    ``areas`` MUST be the number of areas behind the VALUE being shown, not the
    number behind the meta. Comparing the meta's setters against their own week
    is always n of n and can never fire — which on 2026-08-21 left the last
    complete week reading "204, 2040% of goal 10" with nothing to explain it.
    """
    n = int(set_by.get(key, 0) or 0)
    if not n or not areas or n >= areas:
        return ""
    return t("{n} of {total} areas set a goal", n=fmt_int(n), total=fmt_int(areas))


# ── The sparkline: the last six complete weeks, mission-wide ──────────────────
# A weekly total is a sum over whoever submitted, so a week 2 areas reported and
# a week 39 did are not two points on one line — drawn together they make a
# launch out of a reporting gap. Only weeks at least half the mission reported
# reach the sparkline, the same gate every comparison on this page passes.
_KI_SPARK_WEEKS = 6
_ki_min_areas = max(1, round(_active_areas * 0.5)) if _active_areas else 1
_ki_spark_df = exclude_current_week(ki_df)
if not _ki_spark_df.empty and "week_end_date" in _ki_spark_df.columns:
    _ki_spark_df = _ki_spark_df[
        _ki_spark_df["week_end_date"].astype(str).map(
            lambda w: _ki_reporting.get(str(w)[:10], 0) >= _ki_min_areas)
    ].tail(_KI_SPARK_WEEKS)


def _ki_spark(metric: str) -> list | None:
    """The metric's last six complete weeks, or None for too little history."""
    if _ki_spark_df.empty or metric not in _ki_spark_df.columns:
        return None
    values = pd.to_numeric(_ki_spark_df[metric], errors="coerce").dropna().tolist()
    return values if len(values) >= 2 else None


# ── The week now in progress ──────────────────────────────────────────────────
# Monday-to-today from the NIGHTLY form, never the rolling 7 days the sections
# below use: a rolling week straddles two reporting weeks and cannot be set
# against a Monday–Sunday meta. Two of the seven are collected nightly and can
# be counted live; the rest arrive with the weekly form on Sunday.
#
# ki_baptismal_date used to borrow baptismal_calendars as its mid-week VALUE,
# under a relabelled tile. With one scoreboard row that relabel would put a
# name that is not a Key Indicator among six that are, against decision 11's
# rule that these seven labels are constant app-wide — and the two quantities
# are genuinely different (calendars handed out is a flow; friends holding a
# date is a standing count). The calendars figure survives as the card's note,
# which claims nothing about the indicator itself.
_lw_start, _lw_end = _this_monday - timedelta(days=7), _today - timedelta(days=7)
_lw_totals = window_totals(_daily_log, _lw_start, _lw_end)
_lw_areas = window_areas(_daily_log, _lw_start, _lw_end)
_wtd_min_areas = max(1, round(_active_areas * 0.5)) if _active_areas else 1


def _ki_week_card(metric: str) -> dict:
    source = _KI_NIGHTLY_SOURCE.get(metric)
    measured = source is not None and source in _wtd_totals
    goal = float(_cur_goals.get(metric, 0) or 0)
    notes = []
    if not measured:
        notes.append(t("arrives Sunday"))
    stand_in = _KI_NIGHTLY_NOTE.get(metric)
    if stand_in is not None and stand_in in _wtd_totals:
        notes.append(t("{n} baptismal calendars handed out",
                       n=fmt_int(_wtd_totals.get(stand_in, 0))))
    return {
        "label": ki_short_label(metric),
        "href": ki_href(metric),
        "value": int(_wtd_totals.get(source, 0)) if measured else "—",
        "spark": _ki_spark(metric),
        # The bar is the companionships' meta; the leadership goal is the mark.
        "goal": goal,
        "mark": _cur_lead_goals.get(metric),
        "mark_label": t("Leadership goal, per week"),
        # An in-progress week is graded on where it should be TODAY, not on the
        # whole week's meta — five days in, a companionship exactly on pace has
        # produced five sevenths of it.
        "pace": goal * _wtd_days / 7 if goal > 0 and measured else None,
        "day": _wtd_days, "days": 7,
        "goal_note": _ki_goal_note(metric, _cur_goal_set_by, _cur_goal_areas),
        # Nightly totals come from however many areas filed this week; the meta
        # from however many wrote one down last week. Different sets, so the
        # percentage is computed per area.
        "value_basis": _wtd_areas,
        "goal_basis": _cur_goal_set_by.get(metric, 0),
        "change": period_delta(
            _wtd_totals.get(source, 0), _lw_totals.get(source, 0),
            current_basis=_wtd_areas, prior_basis=_lw_areas,
            min_basis=_wtd_min_areas) if measured else None,
        "delta_label": t("vs same days last week"),
        "note": " · ".join(notes),
    }


# ── The last complete week ────────────────────────────────────────────────────
# A weekly total is a sum over whoever submitted, so two weeks can only be
# compared once both are reduced to a per-area rate. Live on 2026-08-21 that was
# 31 areas against 1, which is why the half-the-mission gate below matters.
_prev_week_end = (_ki_week_end - timedelta(days=7)
                  if _ki_week_end is not None else None)
_prev_ki_row = _ki_row_for_week(_prev_week_end)
_prev_ki_reported = (_ki_reporting.get(str(_prev_week_end), 0)
                     if _prev_week_end is not None else 0)
_ki_reported = _ki_reporting.get(str(_ki_week_end), 0) if _ki_week_end else 0


def _prev_ki_val(metric_key: str) -> float:
    if _prev_ki_row is None or metric_key not in _prev_ki_row.index:
        return 0.0
    return float(_prev_ki_row[metric_key] or 0)


def _ki_last_card(metric: str) -> dict:
    return {
        "label": ki_short_label(metric),
        "href": ki_href(metric),
        "value": int(_ki_val(metric)),
        "spark": _ki_spark(metric),
        "goal": float(_past_goals.get(metric, 0) or 0),
        "mark": _past_lead_goals.get(metric),
        "mark_label": t("Leadership goal, per week"),
        "goal_note": _ki_goal_note(metric, _past_goal_set_by, _ki_reported),
        "value_basis": _ki_reported,
        "goal_basis": _past_goal_set_by.get(metric, 0),
        "change": period_delta(
            _ki_val(metric), _prev_ki_val(metric),
            current_basis=_ki_reported, prior_basis=_prev_ki_reported,
            min_basis=_ki_min_areas),
        "delta_label": t("vs prior week"),
    }


# ── The cambio so far ─────────────────────────────────────────────────────────
# PLAN §1.1, the cambio grain: companionship metas only exist for the weeks
# already planned, so the bar compares what has been ACHIEVED so far against the
# metas SET so far, and the full-cycle leadership goal is the mark. The arrows
# compare the same weeks of the previous cambio — the twin the whole app uses,
# and the reason an in-progress cycle never reads as a collapse.
_ki_cycle = transfer_window(0, _today)
_ki_prev_cycle = transfer_window(1, _today)
_ki_cycle_points: dict = {}
_ki_cycle_twin_points: dict = {}
_ki_cycle_totals: dict = {}
#: Area-weeks behind each side of the cambio comparison — how many areas filed
#: a weekly form, summed over the weeks that have elapsed. The count is the same
#: for all seven metrics (it counts rows, not values), so it is taken once.
_ki_cycle_basis = _ki_twin_basis = 0
_ki_cycle_elapsed = 0

if _ki_period == _KI_PERIOD_CYCLE and _ki_cycle is not None and _ki_metrics:
    # One read of the weekly form for all seven metrics, rather than seven.
    _ki_weekly_df = get_weekly_form_data()
    _ki_cycle_totals = group_goal_totals(_ki_cycle["start"], set(_ki_scope_areas))
    for _k in _ki_metrics:
        _ki_cycle_points[_k] = kh.weekly_series(
            _ki_scope_areas, _k, _ki_cycle, weekly=_ki_weekly_df, today=_today)
        # The twin's own weekly points rather than twin_weekly()'s bare values:
        # the comparison needs to know how many areas stand behind each side,
        # not only what they added up to.
        _ki_cycle_twin_points[_k] = (
            kh.weekly_series(_ki_scope_areas, _k, _ki_prev_cycle,
                             weekly=_ki_weekly_df, today=_today)
            if _ki_prev_cycle else [])
    _ref = next(iter(_ki_cycle_points.values()), [])
    _ki_cycle_elapsed = len([p for p in _ref if not p.is_future])
    _ki_cycle_basis = sum(p.reporting for p in _ref if not p.is_future)
    _ki_twin_basis = sum(
        p.reporting
        for p in next(iter(_ki_cycle_twin_points.values()), [])[:_ki_cycle_elapsed])


def _ki_cycle_card(metric: str) -> dict:
    points = _ki_cycle_points.get(metric) or []
    elapsed = [p for p in points if not p.is_future]
    covered = [p for p in elapsed if p.reporting]
    metas = [p.meta for p in elapsed if p.meta is not None]
    actual = sum(p.actual or 0.0 for p in covered) if covered else None

    # The twin, truncated to the weeks that have elapsed here, compared on the
    # AREA-WEEKS behind each side rather than on the weeks alone. The previous
    # cambio is only a PARTIAL twin on this mission — 2026-5 holds data from
    # 9 Aug, and its first week carries two areas — so week counts alone would
    # set 225 areas-worth against 16 and print a fourteen-fold rise. Reduced to
    # a per-area rate the mismatch cancels, and the half-the-mission gate
    # refuses the comparison outright while the twin is that thin, exactly as
    # the weekly reading does.
    twin = _ki_cycle_twin_points.get(metric) or []
    twin_total = sum(p.actual or 0.0 for p in twin[:len(elapsed)] if p.reporting)
    change = None
    if covered and _ki_twin_basis:
        change = period_delta(actual, twin_total,
                              current_basis=_ki_cycle_basis,
                              prior_basis=_ki_twin_basis,
                              min_basis=_ki_min_areas)
    return {
        "label": ki_short_label(metric),
        "href": ki_href(metric),
        "value": int(actual) if actual is not None else "—",
        "spark": _ki_spark(metric),
        "goal": sum(metas) if metas else 0,
        "mark": kh.leadership_total(_ki_scope_areas, _ki_cycle, metric,
                                    totals=_ki_cycle_totals),
        "mark_label": t("Cambio goal"),
        # Both sides are weekly sums, so the basis is the WEEKS behind each:
        # two weeks of results against three weeks of metas is a real mismatch
        # and the per-week rates cancel it.
        "value_basis": len(covered),
        "goal_basis": len([p for p in elapsed if p.meta is not None]),
        "change": change,
        "delta_label": t("vs the same weeks of the previous cambio"),
        "note": "" if covered else t("arrives Sunday"),
    }


# ── When this page refuses to compare, and why ────────────────────────────────
# Every reading has one way of being uncomparable, and it is always the same
# shape: the prior side rests on too few reporting areas to stand for the
# mission. The sentence is built once, here, because it has to reach three
# places — the ⓘ, for the reader on a phone with nothing to hover; the chip on
# each card, which says only that there is no comparison; and that chip's
# tooltip. It used to be a paragraph under the row (audit X4).
_ki_no_change_reason = ""
if _ki_period == _KI_PERIOD_WEEK and _lw_areas < _wtd_min_areas:
    _ki_no_change_reason = t(
        "No comparison with last week: only {n} areas filed a nightly report "
        "over the same days a week ago.", n=fmt_int(_lw_areas))
elif _ki_period == _KI_PERIOD_LAST and _prev_ki_reported < _ki_min_areas:
    _prev_span = (fmt_week_span(_prev_week_end - timedelta(days=6), _prev_week_end)
                  if _prev_week_end is not None else "")
    _ki_no_change_reason = t(
        "No comparison with the previous week: {n} of {total} areas submitted "
        "the weekly form for {span}, and at least {need} are needed for a "
        "mission-level comparison.",
        n=fmt_int(_prev_ki_reported), total=fmt_int(_active_areas),
        span=_prev_span, need=fmt_int(_ki_min_areas))
elif _ki_period == _KI_PERIOD_CYCLE and _ki_prev_cycle is None:
    _ki_no_change_reason = t(
        "No comparison yet: the schedule holds no cambio before this one.")
elif _ki_period == _KI_PERIOD_CYCLE and _ki_twin_basis < _ki_min_areas:
    _ki_no_change_reason = t(
        "No comparison with cambio {prev}: its matching {n} weeks hold "
        "{reports} between them, and at least {need} are needed.",
        prev=_cycle_label(_ki_prev_cycle), n=fmt_int(_ki_cycle_elapsed),
        reports=(t("1 weekly report") if _ki_twin_basis == 1
                 else t("{n} weekly reports", n=fmt_int(_ki_twin_basis))),
        need=fmt_int(_ki_min_areas))


# ── The heading, its right-hand line, and the toggle ──────────────────────────
# The right-hand line is where the window and the coverage live now: which
# cambio, how far into it, and how much of the mission is behind the numbers.
# Those were three captions under two headings (audit X4).
_ki_right_parts = []
if _ki_period == _KI_PERIOD_LAST:
    _ki_span = (fmt_week_span(_ki_week_end - timedelta(days=6), _ki_week_end)
                if _ki_week_end is not None else "")
    if _ki_span:
        _ki_right_parts.append(
            t("week of {span} (in progress)", span=_ki_span) if _ki_is_partial
            else t("week of {span}", span=_ki_span))
    if _active_areas:
        _ki_right_parts.append(t("{n} of {total} areas reported",
                                 n=fmt_int(_ki_reported),
                                 total=fmt_int(_active_areas)))
else:
    if _ki_cycle is not None:
        _ki_right_parts.append(t("cambio {cycle}", cycle=_cycle_label(_ki_cycle)))
        _n, _m = kh.cycle_position(_ki_cycle, _today)
        _ki_right_parts.append(t("week {n} of {m}", n=fmt_int(_n), m=fmt_int(_m)))
    if _ki_period == _KI_PERIOD_CYCLE:
        _cyc_pts = next(iter(_ki_cycle_points.values()), [])
        _cyc_elapsed = [p for p in _cyc_pts if not p.is_future]
        _ki_right_parts.append(
            t("{n} of {m} weeks reported",
              n=fmt_int(sum(1 for p in _cyc_elapsed if p.reporting)),
              m=fmt_int(len(_cyc_elapsed))))
    elif _active_areas:
        _ki_right_parts.append(
            t("{n} of {total} areas filed this week",
              n=fmt_int(_wtd_areas), total=fmt_int(_active_areas)))

#: The section's own explanation, behind the ⓘ. Everything the two Key
#: Indicator rows used to carry as five captions under them (audit X4).
_ki_info = t(
    "The seven indicators the mission is judged on, for every area that "
    "submits. The bar is the goal the companionships set themselves on the "
    "weekly form — the same number the Church's app shows them — and the "
    "violet mark is the goal leadership set for the cambio on the Metas "
    "page. During the week in progress two indicators are counted live from "
    "the nightly form and the rest arrive with the weekly form on Sunday; "
    "the white tick is where the week's goal says today should be. Totals "
    "are compared per area, because a week's total is a sum over whoever "
    "reported. Tap any card for that indicator's history.")
if _ki_no_change_reason:
    _ki_info += " " + _ki_no_change_reason

render_section_label(
    t("Key Indicators"), emphasis=True,
    right=" · ".join(p for p in _ki_right_parts if p),
    info=_ki_info,
)

_ki_picked = st.pills(
    t("Period"), _KI_PERIODS, format_func=_ki_period_label,
    default=_ki_period, label_visibility="collapsed",
    # The key carries the active period, so a run in which the pill is
    # deselected does not leave a stale widget value behind the heading.
    key=f"panel_ki_period_{_ki_period}",
)
if _ki_picked is not None and _ki_picked != _ki_period:
    st.session_state["panel_ki_period_val"] = _ki_picked
    st.rerun()

if not _ki_metrics:
    st.info(_EMPTY_MSG)
elif _ki_period == _KI_PERIOD_CYCLE and _ki_cycle is None:
    st.info(t("No transfer schedule yet — TRANSFER_SCHEDULE is empty, so there "
              "is no cambio to show by week."))
else:
    if _ki_period == _KI_PERIOD_CYCLE:
        _ki_builder = _ki_cycle_card
    elif _ki_period == _KI_PERIOD_LAST:
        _ki_builder = _ki_last_card
    else:
        _ki_builder = _ki_week_card

    _ki_cards = []
    for _k in _ki_metrics:
        _card = _ki_builder(_k)
        # A refused comparison is the card's own chip now, not a paragraph
        # under the row: "sin comparación", with the reason on hover and in
        # the ⓘ above. Only where there IS a number to have compared — a card
        # still waiting for Sunday has nothing to say about last week.
        if (_ki_no_change_reason and _card.get("change") is None
                and isinstance(_card.get("value"), (int, float))):
            _card["change_note"] = t("no comparison")
            _card["change_note_title"] = _ki_no_change_reason
        _ki_cards.append(_card)
    render_kpi_row(_ki_cards)

# ── The drill-down — a tapped Key Indicator, by week / cambio / area ──────────
# Opened by ?ki=<metric>, which every card above links to; the pills strip is
# the visible affordance. The panel owns the metric, this page owns the scope
# (PLAN-2026-09-18-data-pages.md §3). Its first tab follows the period the
# scoreboard is showing.
if _ki_metrics:
    render_ki_drilldown(
        "Mission", _mission_name, _ki_scope_areas, key="panel_ki",
        default_tab=(TAB_CYCLE if _ki_period == _KI_PERIOD_CYCLE else TAB_WEEK))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. THE YEAR AGAINST THE BAPTISMAL GOAL
# ═══════════════════════════════════════════════════════════════════════════════
# Was section ⑥ of thirteen, six screens down (audit P1). Every other number on
# this page describes a week; this is the year the mission is actually judged
# on, so it sits directly under the Key Indicators.
#
# The three figures that used to be a caption UNDER the chart are a card row
# ABOVE it (step C1.2): where the year stands, how that compares with the goal's
# pace, and where it lands if the months so far are representative. A reader who
# stops at the first line has the answer; the chart is the evidence.
#
# The goal lives in AGENT_CONFIG (GOAL_ANNUAL_baptisms) rather than in this file
# so next year's number is a sheet edit, not a deploy — with no row, the chart
# still draws the year and simply has no line to aim at.
_ab_monthly = get_mission_baptisms_by_month()
if _ab_monthly:
    _ab_year = _today.year
    try:
        _ab_goal = float((get_config_value("GOAL_ANNUAL_baptisms", "") or "").strip())
    except (TypeError, ValueError):
        _ab_goal = 0.0

    _ab_series = ab.cumulative(_ab_monthly, _ab_year)
    _ab_n = ab.months_covered(_ab_series)

    if _ab_n:
        _ab_pace = ab.goal_pace(_ab_goal)
        _ab_landing = ab.landing_estimate(_ab_series, _ab_goal)
        _ab_gap = ab.pace_gap(_ab_series, _ab_goal)
        _ab_x = [fmt_month_abbr(m) for m in range(1, ab.MONTHS_IN_YEAR + 1)]
        # The line stops where the capture stops. Said in the heading, because a
        # cumulative line that simply ends is easy to read as a mission that
        # stopped rather than an export that has not run.
        _ab_last = fmt_month_abbr(_ab_n)

        render_section_label(
            t("{year} Baptisms", year=_ab_year), emphasis=True,
            right=t("certified through {month}", month=_ab_last),
            info=t(
                "Certified monthly totals from the Tableau export, counted "
                "cumulatively against the mission's annual goal. The dashed "
                "amber line is a twelfth of the goal a month — flat on purpose, "
                "because this mission's own months swing between 17 and 50 with "
                "no stable pattern to shape a curve to. The two grey lines "
                "behind are the previous two years. The weekly form's own "
                "baptism field is not used here: it undercounts by roughly "
                "half."),
        )

        # ── Where the year stands, in three figures ──────────────────────────
        _ab_cards = [{
            "label": t("Baptisms through {month}", month=_ab_last),
            "value": int(_ab_series[_ab_n - 1]),
            "goal": _ab_goal if _ab_goal > 0 else None,
            # Graded on the pace, not on the whole year: in July a mission
            # exactly on pace has 58% of an annual goal, and grading that
            # against 100% would paint a mission on track in red.
            "pace": _ab_pace[_ab_n - 1] if _ab_pace else None,
        }]
        if _ab_gap is not None:
            _ab_cards.append({
                "label": t("vs goal pace"),
                "value": "{}{}".format("+" if _ab_gap >= 0 else "−",
                                       fmt_int(abs(round(_ab_gap)))),
                "note": (t("ahead of the goal's pace") if _ab_gap >= 0
                         else t("behind the goal's pace")),
            })
        if _ab_landing:
            _ab_cards.append({
                "label": t("Projection"),
                # A tilde, because this is the only figure on the page that
                # describes something that has not happened yet.
                "value": "~" + fmt_int(round(_ab_landing["value"])),
                "note": t("if the {n} months so far are representative",
                          n=fmt_int(_ab_landing["months"])),
            })
        render_kpi_row(_ab_cards)

        fig_ab = go.Figure()
        # Prior years first, so they sit behind. Two of them, because one is an
        # anecdote: 2024 and 2025 finished 385 and 403, close enough that the
        # pair reads as the mission's normal range rather than as a target.
        for _off, _dim in ((2, "rgba(203,203,210,0.22)"), (1, "rgba(203,203,210,0.40)")):
            _prev = ab.cumulative(_ab_monthly, _ab_year - _off)
            if ab.months_covered(_prev) < 1:
                continue
            fig_ab.add_trace(go.Scatter(
                x=_ab_x, y=_prev, mode="lines",
                name=str(_ab_year - _off),
                line=dict(color=_dim, width=1.5),
                hovertemplate="%{y:.0f}<extra>" + str(_ab_year - _off) + "</extra>",
            ))
        if _ab_pace:
            fig_ab.add_trace(go.Scatter(
                x=_ab_x, y=_ab_pace, mode="lines",
                name=t("Goal pace ({goal})", goal=fmt_int(_ab_goal)),
                line=dict(color=GOAL_LINE, width=2, dash="dash"),
                hovertemplate="%{y:.0f}<extra>" + t("goal pace") + "</extra>",
            ))
        # The current year last, so it draws on top of everything it is being
        # compared against.
        fig_ab.add_trace(go.Scatter(
            x=_ab_x[:_ab_n], y=_ab_series[:_ab_n],
            mode="lines+markers",
            name=str(_ab_year),
            line=dict(color=MAGNITUDE, width=3),
            marker=dict(size=7),
            hovertemplate="%{y:.0f}<extra>" + str(_ab_year) + "</extra>",
            cliponaxis=False,
        ))
        fig_ab.update_layout(
            xaxis=dict(type="category"),
            yaxis=dict(title=t("Baptisms, cumulative"), rangemode="tozero"),
            hovermode="x unified",
        )
        chart(fig_ab, height=340)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ZONES — the seven Key Indicators, per area
# ═══════════════════════════════════════════════════════════════════════════════
# Data-pages plan §4 step C3, decision 7. This was a nine-column HTML table of
# the nightly funnel: rank, zone, areas, four counts and Effectiveness as plain
# text, with no visual encoding and 766px of sideways scroll on a phone (audit
# P5). Two things changed.
#
# WHAT is compared: the seven Key Indicators, not the finding funnel. The
# mission is judged on the seven, every other section of this page is about the
# seven, and a zone comparison on a different set of metrics asks the reader to
# hold two vocabularies at once. The funnel is still here, one tap away, because
# it answers the other half of the question — how much finding work went in.
#
# HOW it is drawn: charts.ranked_list with columns. Rank, dot, zone, coverage
# and the sort column's bar on the left; the seven small numbers on the right,
# the best and worst in each column tinted. On a phone the two halves stack and
# every number names itself, so nothing scrolls sideways.
#
# Every figure is still divided by the zone's active area count, never shown
# raw: zones run 8 to 13 areas, so a raw total ranks by size (audit C2). The
# arithmetic lives in app/analytics/zone_comparison.py.

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

#: Column headers, trimmed to keep the strip readable. Trimmed phrases in the
#: KI_SHORT_LABELS style, with one deliberate abbreviation: "Invitaciones" alone
#: is ambiguous against church_invites ("Invitaciones a la Iglesia"), and the
#: unabbreviated "Invitaciones al Bautismo" is wide enough to wrap the column.
#: Naming the wrong thing is the worse failure of the two.
_ZONE_SHORT_LABELS = {
    "contacts_attempted":    "Attempts",
    "contacts_made":         "Contacts",
    "friend_lessons":        "Lessons w/ Friends",
    "baptismal_invitations": "Bapt. Invitations",
}

#: The seven Key Indicators trimmed AGAIN for a seven-column strip, where each
#: column has about 80px. The card labels stay what decision 11 fixed them as —
#: these are column headers, the same exception _ZONE_SHORT_LABELS above has
#: always been, and every cell carries the full name on hover.
_ZONE_KI_LABELS = {
    "ki_new_people_real":         "New",
    "ki_member_lessons_real":     "Lessons",
    "ki_friends_sacrament_real":  "Sacrament",
    "ki_friends_first_week_real": "1st week",
    "ki_baptismal_date_real":     "With date",
    "ki_baptized_confirmed_real": "Baptized",
    "ki_rc_at_church_real":       "RC",
}

#: Where the sort falls back to while Effectiveness is still missing its Key
#: Indicator third (see effectiveness_is_rankable). An outcome, complete today,
#: and hard to inflate.
_ZONE_FALLBACK_SORT = "friend_lessons"

#: Which comparison is on screen, and whether it reads per area or as a total.
#: Stored under their own *_val keys rather than as widget keys: these were an
#: st.radio until this step, and Streamlit keeps a retired widget's state under
#: its key (see render_section_tabs' note on the same collision).
_ZONE_VIEW_KI, _ZONE_VIEW_FUNNEL = "ki", "funnel"
_ZONE_MODE_PER_AREA, _ZONE_MODE_TOTAL = "per_area", "total"

_zone_view = st.session_state.get("panel_zone_view_val", _ZONE_VIEW_KI)
if _zone_view not in (_ZONE_VIEW_KI, _ZONE_VIEW_FUNNEL):
    _zone_view = _ZONE_VIEW_KI
_zone_mode = st.session_state.get("panel_zone_mode_val", _ZONE_MODE_PER_AREA)
if _zone_mode not in (_ZONE_MODE_PER_AREA, _ZONE_MODE_TOTAL):
    _zone_mode = _ZONE_MODE_PER_AREA
_zone_per_area = _zone_mode == _ZONE_MODE_PER_AREA


def _zone_view_label(view: str) -> str:
    return (t("Key Indicators") if view == _ZONE_VIEW_KI
            else t("Nightly funnel"))


def _zone_mode_label(mode: str) -> str:
    return (t("Per area") if mode == _ZONE_MODE_PER_AREA
            else t("Zone total"))


# Effectiveness comes from SCORES' newest scored week. On the funnel view it is
# the one column on a different clock from the rolling 7 days, and the one the
# per-area / total switch does not apply to — see zone_comparison_table.
_zone_eff_week = None
_zone_scores = pd.DataFrame()
_zone_scored_weeks = get_scored_weeks()
if _zone_scored_weeks:
    _zone_eff_week = _zone_scored_weeks[0]
    _zone_scores = get_scores(_zone_eff_week)

if _zone_view == _ZONE_VIEW_KI:
    _zone_keys = list(_ki_metrics)
    _zone_cols = [(k, t(_ZONE_KI_LABELS.get(k, k)), ki_short_label(k))
                  for k in _zone_keys]
    _zone_num = zone_ki_table(get_weekly_form_data(), _ki_scope_roster,
                              _zone_keys, _ki_week_end, per_area=_zone_per_area)
    _zone_mission = zone_ki_mission_row(get_weekly_form_data(), _ki_scope_roster,
                                        _zone_keys, _ki_week_end,
                                        per_area=_zone_per_area)
    _zone_default_key = ("ki_new_people_real" if "ki_new_people_real" in _zone_keys
                         else (_zone_keys[0] if _zone_keys else ""))
    _zone_window = (
        t("week of {span}", span=fmt_week_span(_ki_week_end - timedelta(days=6),
                                               _ki_week_end))
        if _ki_week_end is not None else ""
    )
else:
    _zone_num = zone_comparison_table(
        zone_df, _ki_scope_roster, _ZONE_FUNNEL_KEYS, _zone_scores,
        per_area=_zone_per_area)
    _zone_mission = mission_summary_row(
        zone_df, _ki_scope_roster, _ZONE_FUNNEL_KEYS, _zone_scores,
        per_area=_zone_per_area)
    _zone_cols = [(k, t(_ZONE_SHORT_LABELS[k]), t(_ZONE_SHORT_LABELS[k]))
                  for k in _ZONE_FUNNEL_KEYS]
    if ZONE_EFFECTIVENESS in _zone_num.columns:
        _zone_cols.append((ZONE_EFFECTIVENESS, t("Effectiveness"),
                           t("Effectiveness")))
    _zone_keys = [k for k, _short, _full in _zone_cols]
    _zone_eff_ready = (
        ZONE_EFFECTIVENESS in _zone_num.columns
        and effectiveness_is_rankable(_zone_scores, _active_areas)
    )
    _zone_default_key = (ZONE_EFFECTIVENESS if _zone_eff_ready
                         else _ZONE_FALLBACK_SORT)
    _zone_window = _night_window

# ── The heading ───────────────────────────────────────────────────────────────
_zone_info = [t(
    "Every figure here is divided by the zone's active area count, including "
    "the areas that did not report — these zones run from 8 to 13 areas, so a "
    "raw total ranks them by size rather than by work. The best and worst in "
    "each column are tinted. Tap a zone to open it on Desgloses.")]
if _zone_view == _ZONE_VIEW_KI:
    _zone_info.append(t(
        "The seven indicators come from the weekly form, so this is the last "
        "complete week rather than a rolling seven days, and a zone's coverage "
        "is printed beside its name: at 6 of 13 areas a zone is having a quiet "
        "week to report, not necessarily a bad one."))
else:
    _zone_info.append(t(
        "The nightly funnel is a rolling seven days from the nightly form, so "
        "it is on a different clock from the Key Indicators."))
    if _zone_eff_week and not _zone_eff_ready:
        _zone_info.append(t(
            "Effectiveness does not lead the ranking yet: its Key Indicator "
            "component is still 0 for most areas ({n} of {total} scored), "
            "because a week's KI goals are set on the previous week's form.",
            n=fmt_int(ki_scored_area_count(_zone_scores)),
            total=fmt_int(_active_areas)))
if not _zone_per_area and not _zone_num.empty:
    _zone_info.append(t(
        "Zone totals rank by zone size — these zones run {low} to {high} areas."
        " Effectiveness stays a per-area average.",
        low=fmt_int(_zone_num["areas"].min()),
        high=fmt_int(_zone_num["areas"].max())))

render_section_label(
    t("Zones — Per Area") if _zone_per_area else t("Zones — Zone Totals"),
    emphasis=True,
    right=_zone_window,
    info=" ".join(_zone_info),
)

# ── The controls: what to compare, how to read it, what to rank on ────────────
_zc1, _zc2 = st.columns([2, 1])
with _zc1:
    _zone_picked_view = st.pills(
        t("Compare"), [_ZONE_VIEW_KI, _ZONE_VIEW_FUNNEL],
        format_func=_zone_view_label, default=_zone_view,
        label_visibility="collapsed", key=f"panel_zone_view_{_zone_view}")
    if _zone_picked_view is not None and _zone_picked_view != _zone_view:
        st.session_state["panel_zone_view_val"] = _zone_picked_view
        st.rerun()
    _zone_picked_mode = st.pills(
        t("Show"), [_ZONE_MODE_PER_AREA, _ZONE_MODE_TOTAL],
        format_func=_zone_mode_label, default=_zone_mode,
        label_visibility="collapsed", key=f"panel_zone_mode_{_zone_mode}")
    if _zone_picked_mode is not None and _zone_picked_mode != _zone_mode:
        st.session_state["panel_zone_mode_val"] = _zone_picked_mode
        st.rerun()

_zone_labels = {k: short for k, short, _full in _zone_cols}
with _zc2:
    _zone_sort_key = st.selectbox(
        t("Sort by"), _zone_keys,
        index=(_zone_keys.index(_zone_default_key)
               if _zone_default_key in _zone_keys else 0),
        format_func=lambda k: _zone_labels.get(k, k),
        key=f"panel_zone_sort_{_zone_view}") if _zone_keys else ""

if _zone_num.empty or not _zone_keys:
    st.info(t("No zone totals yet — MISSION_ORG lists no active areas, or "
              "nobody has reported for this window."))
else:
    _zone_num = (_zone_num.sort_values(_zone_sort_key, ascending=False,
                                       na_position="last")
                          .reset_index(drop=True))

    def _zone_places(key: str) -> int:
        """Counts follow the per-area switch; Effectiveness is a 0-100 score
        and keeps its decimal in both readings."""
        return 1 if (_zone_per_area or key == ZONE_EFFECTIVENESS) else 0

    # Best and worst in each column, tinted. Only where there is something to
    # tell apart: with fewer than three zones, or a column where every zone
    # sits on the same number, "best" and "worst" name nothing.
    _zone_best: dict = {}
    _zone_worst: dict = {}
    if len(_zone_num) >= 3:
        for _k in _zone_keys:
            _vals = pd.to_numeric(_zone_num[_k], errors="coerce").dropna()
            if len(_vals) >= 3 and _vals.max() > _vals.min():
                _zone_best[_k] = float(_vals.max())
                _zone_worst[_k] = float(_vals.min())

    def _zone_cells(row) -> tuple:
        cells, status = [], []
        for _k in _zone_keys:
            _v = row.get(_k)
            cells.append(fmt_number(_v, _zone_places(_k)))
            if pd.isna(_v):
                status.append(None)
            elif _k in _zone_best and float(_v) == _zone_best[_k]:
                status.append("good")
            elif _k in _zone_worst and float(_v) == _zone_worst[_k]:
                status.append("bad")
            else:
                status.append(None)
        return cells, status

    def _zone_sub(row) -> str:
        """How much of the zone is behind the numbers. On the weekly view that
        is who submitted the form; on the nightly one the area count is the
        divisor, and printing it is what makes the arithmetic checkable."""
        areas = fmt_int(row.get("areas"))
        if _zone_view == _ZONE_VIEW_KI and "reporting" in row:
            return t("{n} of {total} areas reported",
                     n=fmt_int(row.get("reporting")), total=areas)
        return t("{n} areas", n=areas)

    _zone_rows = []
    for _i, _row in _zone_num.iterrows():
        _cells, _status = _zone_cells(_row)
        _zone_rows.append({
            "rank": _i + 1,
            "name": _row["zone"],
            "sub": _zone_sub(_row),
            # No headline number: the sort column is one of the seven and
            # printing it twice on a row reads as a mistake. The bar under the
            # zone's name carries the ranking.
            "bar": (0 if pd.isna(_row.get(_zone_sort_key))
                    else float(_row.get(_zone_sort_key))),
            "cells": _cells,
            "cell_status": _status,
            "href": "/Desgloses?" + urlencode({"bd_zone": str(_row["zone"])}),
        })

    # The mission as a final row: recomputed from the raw totals, never averaged
    # from the rows above it — averaging four zone averages weights an 8-area
    # zone the same as a 13-area one. It carries no rank and no tint; it is the
    # thing the ranked rows are parts of, not a fifth zone.
    _m_cells, _ = _zone_cells(_zone_mission)
    _zone_rows.append({
        "rank": "",
        "name": t("Mission"),
        "sub": _zone_sub(_zone_mission),
        "bar": (0 if pd.isna(_zone_mission.get(_zone_sort_key))
                else float(_zone_mission.get(_zone_sort_key))),
        "cells": _m_cells,
        "cell_status": None,
    })

    st.markdown(
        ranked_list(
            _zone_rows,
            columns=[(short, full) for _k, short, full in _zone_cols],
        ),
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DAILY ACTIVITY — how much, how well, and which way it is going
# ═══════════════════════════════════════════════════════════════════════════════
# Data-pages plan §4 step C4. Four sections became one: nightly highlights (4a),
# conversion rates (4b), the eight-week trend (4c) and the per-day bar chart
# (4d). They described one subject — the nightly form — across four headings,
# three windows and two chart idioms.
#
# What the merge fixes:
#
#   P4  the eight-week trend was two spaghetti charts. Seven Key Indicators on
#       one axis, where "Nuevas personas" is 225 and "Bautizados" is 1, put five
#       lines flat on zero; all of them were drawn from one blue ramp, so they
#       were indistinguishable anyway, and the legends were taller than the
#       plots. Small multiples give every metric its own axis and its own
#       height, and print the last value.
#   P6  "Lecciones con amigos por día" was one metric, seven bars and a
#       dropdown, answering a question nothing else asked. Deleted; the same
#       metric is one of the eight small multiples below, over eight weeks
#       rather than seven days.
#   P6  the rate arithmetic expander repeated on a second screen what the cards
#       already showed. The formulas — which matter, because three of the four
#       rates divide by something other than the stage above them — are in the
#       section's ⓘ, and each rate card carries its own two figures.
#
# The window is the one every figure here shares, computed once at the top of
# the page: the seven days ending on the last date at least half the mission
# filed for.

#: The three tiles the section opens with. Fixed here, not read from
#: flavor.nightly_highlights: that property derives from SCORE_CONFIG's *effort*
#: weights, which exist to weight the effort score, not to choose what a
#: president sees first. It yielded contacts_attempted, roleplays and
#: member_contacts — two of the three are inputs rather than outcomes, and
#: contacts_attempted then appeared three times on one page (audit H1).
#:
#: These three are the end of the finding funnel: what was actually placed,
#: invited and offered. Order is the mission's own, chosen by the user.
_PANEL_HIGHLIGHT_KEYS = [
    "bom_shared",
    "church_invites",
    "baptismal_invitations",
]

#: The eight nightly metrics that earn a chart (decision 9, PLAN §1.2). The
#: nightly form asks twenty; the other twelve are on Desgloses, which is where
#: a reader goes to look at one area's work rather than the mission's shape.
_PANEL_TREND_KEYS = [
    "contacts_attempted",
    "contacts_made",
    "friend_lessons",
    "lessons_member_present",
    "church_invites",
    "baptismal_invitations",
    # PLAN §1.2 lists this one as `referrals_received`, which no CCSM form asks.
    # The nightly form's key is `member_referrals_received` (checked against
    # nightly_metrics() on 2026-09-18); the plan's key drew nothing at all, and
    # silently, since a metric the frame has no column for is skipped.
    "member_referrals_received",
    "baptismal_calendars",
]

_TREND_WEEKS = 8
nightly_chart = exclude_current_week(nightly_trends_df)
ki_chart      = exclude_current_week(ki_df)
_has_nightly_trend = not nightly_chart.empty and "week_end_date" in nightly_chart.columns
_has_ki_trend      = not ki_chart.empty and "week_end_date" in ki_chart.columns
_weeks_plotted = max(
    len(nightly_chart) if _has_nightly_trend else 0,
    len(ki_chart) if _has_ki_trend else 0,
)

# The four rates' formulas, in words. Three of the four divide by something
# other than the stage immediately above them — lesson_rate is lessons ÷
# ATTEMPTS, not lessons ÷ contacts — and a reader who assumes a single chain
# misreads every one of them. This was a table behind an expander (audit P6);
# the words are what carried the meaning, and each card now shows its own two
# figures.
_rate_formulas = " · ".join(
    "{} = {} ÷ {}".format(
        t(_RATE_SHORT_LABELS.get(r["key"], r["key"])),
        METRIC_LABELS.get(r["metric"].numerator, r["metric"].numerator),
        METRIC_LABELS.get(r["metric"].denominator, r["metric"].denominator))
    for r in _rate_rows
) if _rate_rows else ""

render_section_label(
    t("Daily Activity"), emphasis=True,
    right=_night_window,
    info=" ".join(x for x in [
        t("What the mission placed, invited and offered over the window, then "
          "how well it converted. A day counts as a reporting day once at least "
          "half the areas have filed, so a quiet Sunday cannot pass for a "
          "collapse. Each rate is the ratio of the mission's totals, not the "
          "average of the areas' own rates — averaging lets a few low-volume "
          "areas with favourable ratios carry the mission figure — and moves in "
          "percentage points, because a percent change of a percentage turns "
          "two more invitations per hundred lessons into \"+31%\". Targets come "
          "from AGENT_CONFIG and are the ones CCSM_Agent1A.gs coaches against."),
        _rate_formulas, _night_scaled, _night_no_change,
        _rate_no_change] if x),
)


def _night_card(card: dict) -> dict:
    """A nightly card with the section's refusal on it, where it has a value
    but no arrow. The reason is in the ⓘ above for the reader who cannot
    hover, and on the chip for the one who can (step C2)."""
    if _night_no_change and card.get("change") is None:
        card["change_note"] = t("no comparison")
        card["change_note_title"] = _night_no_change
    return card


if not _night_anchor:
    st.info(t("No nightly reports yet — DAILY_LOG has no day on which at least "
              "half the mission's areas filed."))
else:
    # One grid, seven cards: how much, then how well. They were two rows under
    # two headings, and the reader had to re-learn the window between them —
    # which was the same window both times.
    _activity_cards = []
    for _k in _PANEL_HIGHLIGHT_KEYS:
        _activity_cards.append(_night_card({
            "label": METRIC_LABELS.get(_k, _k),
            "value": int(_cur_totals.get(_k, 0)),
            "goal":  _mission_goal(_k),
            "goal_note": _mission_goal_note(_k),
            "change": period_delta(
                _cur_totals.get(_k, 0), _prev_totals.get(_k, 0),
                current_basis=_cur_days, prior_basis=_prev_days),
            "delta_label": _VS_PRIOR_WEEK,
        }))
    for _r in _rate_rows:
        _activity_cards.append({
            "label": t(_RATE_SHORT_LABELS.get(_r["key"], _r["key"])),
            # None, not 0, when the denominator is empty. render_kpi_row treats
            # a non-numeric value as "no reading yet" and shows the target on
            # its own, rather than reporting a 0% the mission never had the
            # chance to avoid.
            "value": _r["value"] if _r["value"] is not None else "—",
            "goal": _r["target"],
            "unit": "%",
            "decimals": 1,
            # The two figures the ratio came from. This is what the arithmetic
            # expander was for, on the card that needs it.
            "note": t("{num} of {den}", num=fmt_int(_r["numerator"]),
                      den=fmt_int(_r["denominator"])),
            "change": _r["change"],
            "delta_label": _VS_PRIOR_WEEK,
            **({"change_note": t("no comparison"),
                "change_note_title": _rate_no_change}
               if _rate_no_change and _r["change"] is None else {}),
        })
    render_kpi_row(_activity_cards)

# ── Week by week, one small chart per metric ──────────────────────────────────
# Replaces both spaghetti charts (audit P4). One hue, one metric per panel, its
# own y-axis, the last value printed — see charts.small_multiples.
if not _has_nightly_trend and not _has_ki_trend:
    st.info(_EMPTY_MSG)
else:
    _trend_right = (t("{n} of {total} complete weeks so far",
                      n=fmt_int(_weeks_plotted), total=fmt_int(_TREND_WEEKS))
                    if 0 < _weeks_plotted < _TREND_WEEKS else "")

    # Drawn with spark_multiples rather than the Plotly small_multiples: a
    # subplot grid's column count is fixed when the figure is built, and four
    # columns at 375px gives each panel 80px, where the titles overlap each
    # other and the values land in the next panel (measured live, 2026-09-18).
    # This grid wraps — four across on a laptop, two on a phone.
    if _has_nightly_trend:
        _n_series = {
            METRIC_LABELS.get(k, k): nightly_chart[k].tolist()
            for k in _PANEL_TREND_KEYS if k in nightly_chart.columns
        }
        if _n_series:
            render_section_label(t("Nightly work, week by week"),
                                 right=_trend_right)
            st.markdown(spark_multiples(_n_series), unsafe_allow_html=True)

    if _has_ki_trend:
        _k_series = {
            ki_short_label(k): ki_chart[k].tolist()
            for k in _ki_metrics if k in ki_chart.columns
        }
        if _k_series:
            render_section_label(t("Key Indicators, week by week"),
                                 right=_trend_right)
            st.markdown(spark_multiples(_k_series), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# THE EFFORT WINDOW — the nights whose deadline has passed
# ═══════════════════════════════════════════════════════════════════════════════
# Two sections said "last 7 days" and meant different things: one read
# get_daily_summary(7), whose cutoff is `today - 7` and therefore spans eight
# dates from the moment tonight's first report lands, and the effort section
# read DASHBOARD_SUMMARY's EFFORT rows, which CCSM_Agent5A.gs cuts the same way.
# The window is computed once, here, on the anchor compliance is already graded
# against: the last night whose 9:30 PM deadline has passed. An area with hours
# left to file has not missed anything yet.
#
# The first of those two sections is gone (step C4 folded the per-day bar chart
# into the small multiples above), so this now serves the effort section and the
# compliance rankings below it.
_due_anchor = compliance_anchor_date()
_night_start, _night_end = eb.window_bounds(_due_anchor)
_night_span = t("{start}–{end}", start=fmt_day_month(_night_start),
                 end=fmt_day_month(_night_end))
_night_days = [_night_start + timedelta(days=i)
               for i in range((_night_end - _night_start).days + 1)]


# ═══════════════════════════════════════════════════════════════════════════════
# 5. INFORMES — reporting hygiene, one tab down
# ═══════════════════════════════════════════════════════════════════════════════
# Data-pages plan §4 step C5, and audit rule 7: compliance and effort are how
# well the mission REPORTS, not how the mission is doing. They were five of the
# thirteen sections and about 45% of the scroll, above the fold on a page whose
# first question is "where are we".
#
# They are one section with two readings now. Only the chosen reading's body
# runs, so the tab that is closed costs no sheet read — DAILY_LOG at 400 days
# and the effort log at 60 are the two most expensive reads on this page.
_INF_COMPLIANCE, _INF_EFFORT = "compliance", "effort"
_inf_view = st.session_state.get("panel_informes_val", _INF_COMPLIANCE)
if _inf_view not in (_INF_COMPLIANCE, _INF_EFFORT):
    _inf_view = _INF_COMPLIANCE

render_section_label(
    t("Reports"), emphasis=True,
    info=t("Whether the forms arrived, and what the companionships said about "
           "their own effort while filing them. Compliance is computed live "
           "rather than from the nightly summary. An area owes one nightly "
           "form a day from the day it started reporting, and one weekly form "
           "each Sunday; a night whose 9:30 PM deadline has not passed is not "
           "counted as missed."),
)

_inf_picked = st.pills(
    t("Report"), [_INF_COMPLIANCE, _INF_EFFORT],
    format_func=lambda k: (t("Compliance") if k == _INF_COMPLIANCE
                           else t("Effort")),
    default=_inf_view, label_visibility="collapsed",
    key=f"panel_informes_{_inf_view}",
)
if _inf_picked is not None and _inf_picked != _inf_view:
    st.session_state["panel_informes_val"] = _inf_picked
    st.rerun()

if _inf_view == _INF_EFFORT:
    # ── Effort level — last 7 days, over every active area ────────────────────
    # M3. This section used to sum DASHBOARD_SUMMARY's EFFORT rows and report "146
    # Todo · 83 La mayor parte · 13 Algo" — 242 answers presented as the mission,
    # when 43 areas over 7 days had 301 chances to answer and 59 of them went
    # unfiled. Every share on screen was silently a share of the submitters.
    #
    # The arithmetic now lives in app/analytics/effort_breakdown.py, which builds
    # the denominator from the active areas and places the answers into it. Two
    # consequences worth keeping: the cards are percentages of all possible
    # area-days, and the effort SCORE is computed over the areas that answered and
    # only them (a missing form is a compliance failure — section 7 grades it by
    # name — not evidence that a companionship worked badly).

    #: How far the effort score must move before the card calls it a change. The
    #: rates' 2,0 is percentage POINTS on a 0-100 scale; this score lives on 1-3,
    #: where 0,10 is about one area in ten moving up a whole answer. Provisional in
    #: the same way period_delta.NEUTRAL_BAND_POINTS is — revisit once there are
    #: 6-8 weeks of history to see the real week-to-week wobble.
    _EFFORT_NEUTRAL_POINTS = 0.10

    _eff_areas = get_submitting_areas()
    _eff_log = get_daily_effort_log(60)
    _eff_sys_start = get_config_value("SYSTEM_START_DATE", "2026-06-08")[:10]
    _eff_transfer_start = get_config_value("TRANSFER_START_DATE", _eff_sys_start)[:10]
    _eff_floor = date.fromisoformat(_eff_sys_start)
    _eff_transfer = date.fromisoformat(_eff_transfer_start)

    _eff_cur = eb.build_window(
        _eff_log, _eff_areas, start=_night_start, end=_night_end,
        system_start=_eff_floor, transfer_start=_eff_transfer,
    )

    # Drawn after the window is built, so the denominator can be stated in the
    # heading rather than in a caption under the cards (step C2). It is the whole
    # point of this section: the shares are of every answer that COULD have been
    # filed, not of the ones that were.
    render_section_label(
        t("Effort Level — Last 7 Days"),
        right=_night_span,
        info=t("{areas} active areas × {days} days = {possible} possible answers. "
               "{missing} were never filed ({pct}). The three shares are of all of "
               "them, so a missing form counts against the mission; the Effort "
               "Score is averaged over the area-days that DID answer, because an "
               "unfiled form is a compliance failure rather than evidence that a "
               "companionship worked badly.",
               areas=fmt_int(_eff_cur.area_count),
               days=fmt_int(len(_eff_cur.days)),
               possible=fmt_int(_eff_cur.possible),
               missing=fmt_int(_eff_cur.missing),
               pct=fmt_percent(_eff_cur.missing_share)) if _eff_cur.possible > 0 else None,
    )

    if _eff_cur.possible <= 0:
        st.info(t("No effort answers have been logged yet. The nightly form asks "
                  "for one every night, so this fills in as areas report."))
    else:
        # The prior window, for the score's arrow only. Same pair section 1 uses, so
        # "prior 7 days" means one thing on this page.
        _, _, _eff_prior_start, _eff_prior_end = window_pair(_due_anchor)
        _eff_prior = eb.build_window(
            _eff_log, _eff_areas, start=_eff_prior_start, end=_eff_prior_end,
            system_start=_eff_floor, transfer_start=_eff_transfer,
        )
        _eff_report_dates = reporting_dates(_eff_log, len(_eff_areas))
        _eff_change = point_delta(
            _eff_cur.score, _eff_prior.score,
            current_basis=days_in_window(_eff_report_dates, _night_start, _night_end),
            prior_basis=days_in_window(_eff_report_dates, _eff_prior_start, _eff_prior_end),
            neutral_band=_EFFORT_NEUTRAL_POINTS,
        )

        _eff_labels = {
            eb.ALL:  t("Effort · All"),
            eb.MOST: t("Effort · Most"),
            eb.SOME: t("Effort · Some"),
        }

        def _eff_card(level: str) -> dict:
            """One answer as a share of every area-day that could have carried it."""
            return {
                "label": _eff_labels[level],
                "value": _eff_cur.share(level),
                "unit": "%", "decimals": 1,
                "note": t("{n} of {total} area-days",
                          n=fmt_int(_eff_cur.counts.get(level, 0)),
                          total=fmt_int(_eff_cur.possible)),
            }

        _eff_target = eb.score_target(get_agent_config())
        render_kpi_row([
            _eff_card(eb.ALL),
            _eff_card(eb.MOST),
            _eff_card(eb.SOME),
            {
                "label": t("Effort Score"),
                "value": _eff_cur.score,
                "decimals": 2,
                "goal": _eff_target,
                "change": _eff_change,
                "points_unit": "",
                "delta_label": t("vs prior 7 days"),
                "note": t("Among the {n} area-days that answered",
                          n=fmt_int(_eff_cur.answered)),
            },
        ])


        # ── Per day, as a share of that day's areas ───────────────────────────────
        # The old chart was three bars holding the same three numbers as the tiles
        # beside it (M2). Per day it earns its place: it is the only thing on the
        # page that shows whether a Sunday collapses or a transfer week sags, and
        # the unfiled share is drawn rather than described.
        _eff_day_labels = [fmt_day_month(d.day) for d in _eff_cur.days]
        _eff_segments = [
            (eb.ALL,  _eff_labels[eb.ALL],  STATUS["good"]),
            (eb.MOST, _eff_labels[eb.MOST], STATUS["warn"]),
            (eb.SOME, _eff_labels[eb.SOME], STATUS["bad"]),
        ]

        render_section_label(t("Effort answers per day, share of all active areas"),
                             numbered=False)
        fig_effort = go.Figure()
        for level, label, color in _eff_segments:
            fig_effort.add_trace(go.Bar(
                x=_eff_day_labels,
                y=[d.share(level) or 0 for d in _eff_cur.days],
                name=label,
                marker_color=color,
                customdata=[[d.counts.get(level, 0), d.possible] for d in _eff_cur.days],
                hovertemplate="%{fullData.name}: %{customdata[0]}/%{customdata[1]} "
                              "(%{y:.0f}%)<extra></extra>",
            ))
        fig_effort.add_trace(go.Bar(
            x=_eff_day_labels,
            y=[d.missing_share or 0 for d in _eff_cur.days],
            name=t("Not reported"),
            marker_color=DIM,
            customdata=[[d.missing, d.possible] for d in _eff_cur.days],
            hovertemplate="%{fullData.name}: %{customdata[0]}/%{customdata[1]} "
                          "(%{y:.0f}%)<extra></extra>",
        ))
        fig_effort.update_layout(
            barmode="stack",
            xaxis_title=t("Date"),
            xaxis_type="category",
            yaxis_title=t("Share of active areas"),
            yaxis=dict(range=[0, 100], ticksuffix="%"),
        )
        chart(fig_effort, height=300)

        # ── Per area ──────────────────────────────────────────────────────────────
        with st.expander(t("Effort by area — who answered what ({span})", span=_night_span)):
            # Ranked, not merely sorted: an area with two answers and a perfect
            # score does not lead the mission. eb.MIN_RANKABLE_ANSWERS sinks those
            # rows to the bottom with their numbers intact.
            _eff_rows = eb.rank_areas(_eff_cur.areas)
            _eff_table = pd.DataFrame([{
                t("Area"):     a.area,
                t("Zone"):     a.zone,
                _eff_labels[eb.ALL]:  a.counts.get(eb.ALL, 0),
                _eff_labels[eb.MOST]: a.counts.get(eb.MOST, 0),
                _eff_labels[eb.SOME]: a.counts.get(eb.SOME, 0),
                t("Answered"): f"{fmt_int(a.answered)}/{fmt_int(a.possible)}",
                t("Not reported"): a.missing,
                t("Effort Score"): fmt_number(a.score, 2) if a.score is not None else "—",
            } for a in _eff_rows])
            st.caption(
                t("{n} active areas · Todo=3, La mayor parte=2, Algo=1, averaged "
                  "over the nights the area answered. An area that filed nothing "
                  "has no score, not a zero.", n=fmt_int(len(_eff_rows)))
            )
            render_table(_eff_table)

else:
    # ── Submission compliance — the headline, the rankings, the
    #    calendars ─────────────────────────────────────────────────
    comp_df = get_alltime_compliance()

    if comp_df.empty:
        mission_pct = days_tracked = areas_current = total_forms = None
        total_possible = None
    else:
        total_sub      = int(comp_df["days_submitted"].sum())
        total_possible = int(comp_df["days_possible"].sum())
        mission_pct    = round(total_sub / total_possible * 100) if total_possible else 0
        days_tracked   = int(comp_df["days_possible"].max())
        areas_current  = int((comp_df["pct"] >= 100).sum())
        total_forms    = total_sub

    # ONE headline number, not four competing ones.
    #
    # This section used to open with a row of four tiles — Total Forms Submitted,
    # Compliance All-Time, Days Tracked, Areas at 100% — three of which are inputs
    # to the fourth. A reader had to work out which one was the answer
    # (AUDIT-IA-2026-08-22.md: "four competing percentages"). All-time compliance
    # is the answer; the arithmetic behind it moves into the expander, the same
    # pattern §1b already uses for its rates.
    render_kpi_row([{
        "label": t("All-Time Compliance"),
        "value": f"{fmt_int(mission_pct)}%" if mission_pct is not None else "—",
        "note": (t("{submitted} of {possible} area-days since tracking began",
                   submitted=fmt_int(total_forms), possible=fmt_int(total_possible))
                 if total_possible else ""),
    }])

    with st.expander(t("How compliance is calculated")):
        st.markdown(t(
            "Every submitting area owes one nightly form per day from the day this "
            "mission started tracking. All-time compliance is the mission's total "
            "forms divided by its total owed — a ratio of totals, not the average "
            "of each area's own percentage, so a large area counts for more than a "
            "small one."
        ))
        render_kpi_row([
            {"label": t("Total Forms Submitted"),
             "value": fmt_int(total_forms) if total_forms is not None else "—"},
            {"label": t("Days Tracked"),
             "value": fmt_int(days_tracked) if days_tracked is not None else "—"},
            {"label": t("Areas at 100%"),
             "value": fmt_int(areas_current) if areas_current is not None else "—"},
        ])


    # ── Compliance rankings (replaced the all-time per-area expander) ─────────────
    # Was an expander holding a plain table of every area's all-time compliance,
    # sorted worst-first with a "Behind only" filter. It answered one question over
    # one window and hid the answer behind a click.
    #
    # This is a ranked leaderboard over any of five periods, for areas or zones,
    # graded on the nightly form, the weekly form, or both. Built to a reference
    # design from a sibling mission's dashboard; the arithmetic that reference
    # implies -- and it is not the obvious arithmetic -- lives in
    # app/analytics/compliance_rankings.py with the numbers from those screenshots
    # pinned as tests. Two rules in particular are easy to "simplify" wrongly:
    # an area averages its two rounded percentages instead of pooling its counts,
    # and a zone averages its areas instead of pooling theirs.
    #
    # Naming every area, including the worst, is a deliberate exception to this
    # page's positive-only rule for per-area callouts (the rule exists because the
    # missionaries named can read the page). The user's reasoning: compliance is
    # "did you turn the form in", a behaviour an area controls outright, not a
    # judgement of how well they teach. The rule still stands for performance.

    # The controls: nine widgets became four (step C5, audit P7). Two tab buttons,
    # four scope selectors and three dropdowns stood between the heading and the
    # list, which is the good part. What went:
    #
    #   * the zone/district/area/missionary filter. The zone view already answers
    #     "how does my zone compare", the fold below already answers "this list is
    #     too long", and a ranking filtered to one district was a leaderboard of
    #     three rows. Desgloses is where one area's compliance is read.
    #   * render_section_tabs, whose two full-width buttons are a page-level
    #     idiom; inside a tab it read as a second level of navigation.
    _SCOPE_AREA, _SCOPE_ZONE = "area", "zone"
    _rank_scope = st.session_state.get("panel_rank_scope_val", _SCOPE_AREA)
    if _rank_scope not in (_SCOPE_AREA, _SCOPE_ZONE):
        _rank_scope = _SCOPE_AREA

    _ct_labels = {
        cr.OVERALL: t("Overall (Daily + Weekly)"),
        cr.NIGHTLY: t("Daily only"),
        cr.WEEKLY:  t("Weekly only"),
    }
    _view_labels = {
        "best":  t("Best → Worst"),
        "worst": t("Worst → Best"),
        "name":  t("By name (A–Z)"),
    }
    # A transfer label the schedule cannot supply is dropped from the menu rather
    # than offered and left to resolve to nothing. Same rule as the Desgloses picker.
    _rk_transfers = transfer_period_bounds()
    _rk_periods = [p for p in cr.PERIODS
                   if p not in ("This Transfer So Far", "Last Transfer")
                   or p in _rk_transfers]
    _rk_default = ("This Transfer So Far" if "This Transfer So Far" in _rk_periods
                   else "This Month So Far")
    _period_labels = {p: t(p) for p in cr.PERIODS}

    _rc0, _rc1, _rc2, _rc3 = st.columns([1.1, 1, 1, 1])
    with _rc0:
        _rank_picked = st.pills(
            t("Rank"), [_SCOPE_AREA, _SCOPE_ZONE],
            format_func=lambda k: (t("Areas") if k == _SCOPE_AREA else t("Zones")),
            default=_rank_scope, label_visibility="collapsed",
            key=f"panel_rank_scope_{_rank_scope}")
        if _rank_picked is not None and _rank_picked != _rank_scope:
            st.session_state["panel_rank_scope_val"] = _rank_picked
            st.rerun()
    with _rc1:
        _rk_type = st.selectbox(
            t("Compliance Type"), list(_ct_labels),
            format_func=lambda k: _ct_labels[k], key="panel_rank_type")
    with _rc2:
        _rk_period = st.selectbox(
            t("Period"), _rk_periods, format_func=lambda k: _period_labels[k],
            index=_rk_periods.index(_rk_default), key="panel_rank_period")
    with _rc3:
        _rk_view = st.selectbox(
            t("View"), list(_view_labels),
            format_func=lambda k: _view_labels[k], key="panel_rank_view")

    # ── The window, and the floors that keep it honest ────────────────────────────
    # start/end come from the period; the floor is when this mission began logging
    # and the anchor is the last night whose deadline has passed. Without the floor,
    # "This Month So Far" charges every area for the nine days of August before
    # tracking existed; without the anchor, tonight's not-yet-due form reads as a
    # miss from the moment the page loads.
    _rk_sys_start = get_config_value("SYSTEM_START_DATE", "2026-06-08")[:10]
    _rk_transfer_start = get_config_value("TRANSFER_START_DATE", _rk_sys_start)[:10]
    _rk_start, _rk_end = cr.period_bounds(_rk_period, date.today(),
                                          transfers=_rk_transfers)
    _rk_floor = date.fromisoformat(_rk_sys_start)
    _rk_anchor = compliance_anchor_date()
    _rk_lo, _rk_hi = cr.clip_window(_rk_start, _rk_end, _rk_floor, _rk_anchor)

    _rank_rows = cr.build_area_windows(
        get_submitting_areas(), get_daily_log(400), get_weekly_submission_data(),
        start=_rk_start, end=_rk_end,
        system_start=_rk_floor,
        transfer_start=date.fromisoformat(_rk_transfer_start),
        anchor=_rk_anchor,
    )

    # Filters apply to areas before any rollup, so a zone ranking always describes
    # the whole zone.
    if _rank_scope == _SCOPE_AREA:
        _display_rows = _rank_rows
    else:
        _display_rows = cr.build_zone_windows(_rank_rows, _rk_type)

    _display_rows = cr.rank(_display_rows, _rk_type,
                            worst_first=(_rk_view == "worst"),
                            by_name=(_rk_view == "name"))

    #: Row colours come from charts.ranked_list, keyed on the status
    #: compliance_rankings.status_of returns. The bands are its GREEN_MIN /
    #: AMBER_MIN, the same >=85 / 70-84 / <70 the two calendars above legend --
    #: one number must not be green on a calendar and amber in the ranking
    #: beneath it.


    def _rank_detail(row) -> str:
        """"16/20 días · 3/3 semanas" — both halves, because the two together are
        what the Overall figure averages.

        The weekly half is dropped when no weekly report has come due in the window
        (a Mon–Wed "This Week" contains no Sunday). Printing "0/0 semanas" there
        reads as a failure at a glance, and it is the one case where the Overall
        figure is the nightly figure alone — see AreaWindow.overall_pct."""
        days = t("{ds}/{dp} days", ds=fmt_int(row.days_submitted),
                 dp=fmt_int(row.days_possible))
        if not row.weeks_possible:
            return days
        return t("{days} · {ws}/{wp} weeks", days=days,
                 ws=fmt_int(row.weeks_submitted), wp=fmt_int(row.weeks_possible))


    if _rk_lo is None:
        # The period is entirely before this mission started logging. Saying so
        # beats a screen of areas at 0%, which reads as mass failure rather than as
        # an absence of data (audit M7: an empty state must say why).
        st.info(t(
            "No data for this period — compliance tracking began on {start}.",
            start=fmt_day_month(_rk_floor)))
    elif not _display_rows:
        st.info(t("No areas match the current filter."))
    else:
        def _rank_rows_html(rows) -> str:
            """`rows` is (rank, row) pairs — the rank is passed rather than
            enumerated, so a folded view still prints each area's TRUE position."""
            return ranked_list([
                {
                    "rank": i,
                    "name": getattr(r, "area", None) or getattr(r, "zone", ""),
                    "sub": _rank_detail(r),
                    "value": r.pct(_rk_type),
                    "status": cr.status_of(r.pct(_rk_type)),
                }
                for i, r in rows
            ], value_fmt=lambda v: f"{fmt_int(v)}%", bar_max=100)

        _ranked = list(enumerate(_display_rows, start=1))

        # ── Top 5 + bottom 5, with the full list one click away ──────────────────
        #
        # This block was every area, unpaginated: 3.8 screens, 38% of the Panel, in
        # a section already carrying 60% of the page between compliance and effort
        # (AUDIT-IA-2026-08-22.md's headline measurement). What a president acts on
        # is the two ends — who to praise and who to call — so those are what the
        # page shows; the middle is still one click away with every filter intact,
        # which is why this is a fold and not a cut.
        #
        # Two cases deliberately do NOT fold:
        #   * "By name (A–Z)", where first and last are alphabetical accidents and
        #     "top 5" would be a lie about performance;
        #   * a list short enough that folding would hide fewer rows than the fold
        #     itself costs — a zone ranking is ten rows, and every filtered area
        #     view is shorter still.
        _FOLD_HEAD = _FOLD_TAIL = 5
        _fold = (_rk_view != "name"
                 and len(_ranked) > _FOLD_HEAD + _FOLD_TAIL + 2)

        if not _fold:
            st.markdown(_rank_rows_html(_ranked), unsafe_allow_html=True)
        else:
            _hidden = len(_ranked) - _FOLD_HEAD - _FOLD_TAIL
            st.markdown(_rank_rows_html(_ranked[:_FOLD_HEAD]), unsafe_allow_html=True)
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:0.75rem;'
                f'margin:0.55rem 0 0.9rem 0;color:{DIM};font-size:0.75rem;">'
                f'<div style="flex:1;height:1px;background:rgba(255,255,255,0.07);"></div>'
                f'{_html_escape(t("{n} more", n=fmt_int(_hidden)))}'
                f'<div style="flex:1;height:1px;background:rgba(255,255,255,0.07);"></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_rank_rows_html(_ranked[-_FOLD_TAIL:]), unsafe_allow_html=True)

            _all_label = (t("See all {n} areas", n=fmt_int(len(_ranked)))
                          if _rank_scope == _SCOPE_AREA
                          else t("See all {n} zones", n=fmt_int(len(_ranked))))
            with st.expander(_all_label):
                st.markdown(_rank_rows_html(_ranked), unsafe_allow_html=True)

        # The window actually graded, not the window asked for. On "This Month So
        # Far" those differ by nine days right now, and the row counts would look
        # arbitrary without it.
        _rk_span = t("{start}–{end}", start=fmt_day_month(_rk_lo),
                     end=fmt_day_month(_rk_hi))
        if _fold:
            # Say what is on screen, not what was computed — "43 areas shown" over
            # a list of ten is exactly the kind of quiet mismatch this audit was
            # called to find.
            st.caption(
                t("Best {head} and last {tail} of {n} areas · {span}",
                  head=fmt_int(_FOLD_HEAD), tail=fmt_int(_FOLD_TAIL),
                  n=fmt_int(len(_ranked)), span=_rk_span)
                if _rk_view != "worst" else
                t("Last {head} and best {tail} of {n} areas · {span}",
                  head=fmt_int(_FOLD_HEAD), tail=fmt_int(_FOLD_TAIL),
                  n=fmt_int(len(_ranked)), span=_rk_span)
            )
        elif _rank_scope == _SCOPE_AREA:
            st.caption(t("{n} area(s) shown · {span}",
                         n=fmt_int(len(_display_rows)), span=_rk_span))
        else:
            st.caption(t("{n} zone(s) shown · {span}",
                         n=fmt_int(len(_display_rows)), span=_rk_span))


    # ── The two calendars, behind one click ──────────────────────────────────────
    # They are the most scrolled part of the page and answer a question a reader
    # asks occasionally, not one they open the Panel for. The "combined submission
    # compliance" box that used to sit under them — an average of two averages —
    # is deleted: the headline above is the mission's compliance, and a second,
    # differently-computed figure beside it was a second answer to one question.
    with st.expander(t("Calendars")):
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

            # Through t() rather than strftime: strftime follows the SERVER's locale,
            # which on Streamlit Cloud is English regardless of the mission's language.
            _mb_day_labels = [t("Mon"), t("Tue"), t("Wed"), t("Thu"),
                              t("Fri"), t("Sat"), t("Sun")]
            _mb_hdr = "".join(
                f'<th style="text-align:center;padding:4px 8px;color:{MUTED};font-size:0.72rem;font-weight:600;">{d}</th>'
                for d in _mb_day_labels
            )

            _counted_pcts = []
            _mb_body = ""
            # Whether either greyed state actually occurs in this window. The legend
            # used to name both unconditionally, which meant the calendar explained a
            # "pre-tracking" colour that was nowhere on it — the window has been past
            # SYSTEM_START_DATE for months. A legend entry for a colour that isn't
            # drawn is noise at best and a wrong reading at worst.
            _mb_has_future = _mb_has_pretracking = False
            for week in _mb_cal:
                cells = ""
                for cell in week:
                    d = cell["date"]
                    day_num = d[8:]
                    if cell["future"]:
                        _mb_has_future = True
                        bg, fg, pct_txt = (*CALENDAR_FUTURE, "")
                        title = t("{date} — upcoming", date=d)
                    elif d < _mb_win_start:
                        _mb_has_pretracking = True
                        bg, fg, pct_txt = (*CALENDAR_PRETRACKING, "")
                        title = t("{date} — before tracking started", date=d)
                    else:
                        n = _per_day_counts.get(d, 0)
                        pct = round(n / _total_areas * 100) if _total_areas else 0
                        _counted_pcts.append(pct)
                        bg, fg = compliance_tint(pct)
                        pct_txt = f"{fmt_int(pct)}%"
                        title = t("{date} — {n}/{total} areas submitted ({pct}%)",
                                  date=d, n=fmt_int(n), total=fmt_int(_total_areas),
                                  pct=fmt_int(pct))
                    pct_html = (
                        f'<div style="font-size:0.8rem;font-weight:700;color:{fg};">{pct_txt}</div>'
                        if pct_txt else '<div style="font-size:0.8rem;">&nbsp;</div>'
                    )
                    cells += (
                        f'<td title="{title}" style="text-align:center;padding:5px 4px;background:{bg};'
                        f'border-radius:4px;vertical-align:middle;">'
                        f'<div style="font-size:0.6rem;color:{MUTED};line-height:1;">{day_num}</div>'
                        f'{pct_html}</td>'
                    )
                _mb_body += f"<tr>{cells}</tr>"

            def _mb_legend_item(color, label):
                return (
                    f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
                    f'border-radius:2px;margin-right:4px;"></span>{label}&nbsp;&nbsp;&nbsp;'
                )

            _mb_legend = "".join(_mb_legend_item(c, lbl)
                                 for c, lbl in compliance_legend_bands())
            if _mb_has_future:
                _mb_legend += _mb_legend_item(CALENDAR_FUTURE[0], t("Upcoming"))
            if _mb_has_pretracking:
                _mb_legend += _mb_legend_item(CALENDAR_PRETRACKING[0],
                                              t("Before tracking started"))

            st.markdown(
                f'<table style="width:100%;border-collapse:separate;border-spacing:3px;margin-bottom:0.5rem;">'
                f'<thead><tr>{_mb_hdr}</tr></thead><tbody>{_mb_body}</tbody></table>'
                f'<div style="font-size:0.72rem;color:{MUTED};margin-bottom:0.5rem;">'
                + _mb_legend
                + "</div>",
                unsafe_allow_html=True,
            )

            if _counted_pcts:
                _avg = round(sum(_counted_pcts) / len(_counted_pcts))
                st.markdown(
                    f'<p style="color:{MUTED};font-size:0.82rem;">'
                    + t("Each box is the share of the mission's {total} submitting "
                        "areas that turned in the nightly form that day. Window "
                        "average: {avg}%.",
                        total=f'<strong style="color:{INK};">{fmt_int(_total_areas)}</strong>',
                        avg=f'<strong style="color:{INK};">{fmt_int(_avg)}</strong>')
                    + '</p>',
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

            _wk_pcts, _wk_cells = [], ""
            for w in _wk_due_weeks:
                _wd = date.fromisoformat(w)
                n   = _per_week_counts.get(w, 0)
                pct = round(n / _total_areas * 100) if _total_areas else 0
                _wk_pcts.append(pct)
                bg, fg = compliance_tint(pct)
                _wk_title = t("Week ending {date} — {n}/{total} areas submitted ({pct}%)",
                              date=w, n=fmt_int(n), total=fmt_int(_total_areas),
                              pct=fmt_int(pct))
                _wk_cells += (
                    f'<td title="{_wk_title}" '
                    f'style="text-align:center;padding:6px 8px;background:{bg};border-radius:4px;'
                    f'vertical-align:middle;min-width:52px;">'
                    f'<div style="font-size:0.6rem;color:{MUTED};line-height:1.2;">{_wd.month}/{_wd.day}</div>'
                    f'<div style="font-size:0.8rem;font-weight:700;color:{fg};">{fmt_int(pct)}%</div></td>'
                )
            st.markdown(
                '<table style="border-collapse:separate;border-spacing:3px;margin-bottom:0.5rem;">'
                f'<tbody><tr>{_wk_cells}</tr></tbody></table>'
                f'<div style="font-size:0.72rem;color:{MUTED};margin-bottom:0.5rem;">'
                + "".join(_wk_leg(c, lbl) for c, lbl in compliance_legend_bands())
                + '</div>',
                unsafe_allow_html=True,
            )

            _weekly_avg = sum(_wk_pcts) / len(_wk_pcts) if _wk_pcts else None
            if _weekly_avg is not None:
                st.markdown(
                    f'<p style="color:{MUTED};font-size:0.82rem;">'
                    + t("Each box is the share of the mission's {total} areas that "
                        "submitted the weekly form for that Mon–Sun week (credited by "
                        "the day it arrived). Window average: {avg}%.",
                        total=f'<strong style="color:{INK};">{fmt_int(_total_areas)}</strong>',
                        avg=f'<strong style="color:{INK};">{fmt_int(round(_weekly_avg))}</strong>')
                    + '</p>',
                    unsafe_allow_html=True,
                )
