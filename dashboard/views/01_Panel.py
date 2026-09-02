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
from app.config.metric_catalog import key_indicator_metrics, nightly_metrics
from app.i18n import t
from app.i18n.formats import (
    fmt_int, fmt_number, fmt_percent, fmt_week_span, fmt_day_month,
)
from app.config.theme import CHART_COLORS
from app.db.queries import (
    get_mission_totals,
    get_zone_totals,
    get_daily_effort_log,
    get_nightly_weekly_trends,
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
    get_agent_config,
)
from app.analytics.zone_comparison import (
    zone_comparison_table, mission_summary_row, effectiveness_is_rankable,
    ki_scored_area_count, EFFECTIVENESS as ZONE_EFFECTIVENESS,
)
from app.analytics.period_delta import (
    reporting_dates, window_pair, window_totals, window_areas, days_in_window,
    period_delta, point_delta, MIN_COMPARABLE_DAYS, WINDOW_DAYS,
)
from app.analytics.rate_metrics import rate_rows
from app.analytics import effort_breakdown as eb
from app.analytics import compliance_rankings as cr
from app.components.scope_selector import render_scope_selectors, ANY as scope_ANY
from app.utils.area_helpers import (
    compliance_anchor_date, build_calendar_data,
    latest_due_sunday, weekly_due_weeks,
)
from datetime import date, timedelta
from html import escape as _html_escape

# Page chrome (set_page_config / inject_global_css / render_sidebar) is
# owned by Home.py's st.navigation router since 2026-09-02 — the router and
# this page share one script run, so calling them here would render twice.
user = require_auth()

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
nightly_trends_df = get_nightly_weekly_trends(8)
daily_df   = get_daily_summary(7)
ki_df      = get_weekly_ki_totals(8)
app_goals  = get_mission_goals()

all_empty = (
    mission_df.empty
    and zone_df.empty
    and nightly_trends_df.empty
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


# Card labels for the four rates, and the shared rate computation. Both used to
# live inside §1b; moved up here during audit item 8 (a verdict banner that
# named the weakest rate above §1) so the banner and §1b would read the same
# figures. Item 8 was later removed at the user's request (didn't like the
# banner) but this hoist stayed — §1b is the only reader now, same as before,
# just defined one section earlier.
#
# The §1b heading already says these are rates, so repeating "Tasa de" on all
# four cards spends the widest line of the card on a word the reader has just
# read. Same trimming rule as _KI_SHORT_LABELS, and the same reason: the
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
# 1. NIGHTLY ACTIVITY — mission totals, last 7 days
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Nightly Activity — Last 7 Days"))

#: The three tiles the page opens with. Fixed here, not read from
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

_nightly_keys = _PANEL_HIGHLIGHT_KEYS
if not _nightly_keys:
    st.info(_EMPTY_MSG)
elif _night_anchor is None:
    st.info(t("No nightly reports yet — DAILY_LOG has no day on which at least "
              "half the mission's areas filed."))
else:
    # The value comes from the same window as the arrow beneath it. It used to
    # be DASHBOARD_SUMMARY's val_7d, whose window is one day wider, which would
    # have put a number and a change describing different spans on one card.
    render_kpi_row([
        {
            "label": METRIC_LABELS.get(k, k),
            "value": int(_cur_totals.get(k, 0)),
            "goal":  _mission_goal(k),
            "goal_note": _mission_goal_note(k),
            "change": period_delta(
                _cur_totals.get(k, 0), _prev_totals.get(k, 0),
                current_basis=_cur_days, prior_basis=_prev_days),
            "delta_label": _VS_PRIOR_WEEK,
        }
        for k in _nightly_keys
    ])

    # The window is stated, and so is the reason there is no comparison yet.
    # A silently missing arrow is the audit's own M7 finding (empty states that
    # never say why) reintroduced one section higher up.
    _win_note = t("{start}–{end} · {n} reporting days",
                  start=fmt_day_month(_cur_start), end=fmt_day_month(_cur_end),
                  n=fmt_int(_cur_days))
    if _prev_days < MIN_COMPARABLE_DAYS:
        st.caption(t(
            "{window}. No comparison yet: the previous 7 days hold {n} days on "
            "which at least half the areas reported, and {need} are needed.",
            window=_win_note, n=fmt_int(_prev_days),
            need=fmt_int(MIN_COMPARABLE_DAYS)))
    elif _prev_days < WINDOW_DAYS:
        st.caption(t(
            "{window}. Compared against {n} reporting days in the previous 7, "
            "scaled per day.", window=_win_note, n=fmt_int(_prev_days)))
    else:
        st.caption(t("{window}, against the 7 days before.", window=_win_note))

# ═══════════════════════════════════════════════════════════════════════════════
# 1b. CONVERSION RATES — how well, against §1's how much (audit H2)
# ═══════════════════════════════════════════════════════════════════════════════
# Numbered 1b rather than 2 on purpose: the audit report and the build queue
# refer to this page's sections by number, and renumbering six of them to insert
# one would silently invalidate every one of those references.
#
# CCSM_Agent1A.gs computes four conversion rates every Monday, each with a target
# in AGENT_CONFIG, a Preach My Gospel page and a scripture — and until now not
# one of them appeared anywhere in the dashboard (audit H2). They are the
# sharpest thing in the dataset: live on 2026-08-21, 4.104 attempts became 673
# lessons and 65 baptismal invitations. The mission teaches well and does not
# invite, and no other section on this page can say so.
#
# The agent keeps the rates in Script Properties for the coaching emails and
# never writes them to a tab, so they are derived here from the same DAILY_LOG
# window §1 uses. That shared window is why this sits directly under §1: the
# tiles above say how much was done, these say how well, and the reader does not
# have to re-learn the timeframe between them.
#
# The audit's plan also called for a link to 07_Embudo_de_Búsqueda.py, on the
# grounds that it already carries "Finding Pipeline" and "Contact Performance"
# and must not be duplicated. That premise did not survive checking: the Embudo
# page runs entirely on uploaded Tableau exports, its TABLEAU_RANKING and
# TABLEAU_DETAIL tabs are empty so the page stops on "No finding data yet", and
# its "contact rate" is attempted ÷ found — a different ratio that happens to
# share a name. There is nothing to duplicate and nowhere to send anyone, so the
# arithmetic is shown here instead, in an expander. Revisit once Tableau syncs.
render_section_label(t("Conversion Rates — Last 7 Days"))

if _night_anchor is None:
    st.info(t("No nightly reports yet — DAILY_LOG has no day on which at least "
              "half the mission's areas filed."))
else:
    # _rate_rows is computed once, in §0 above — the verdict banner names the
    # weakest of these four, so both sections must be reading the same figures.
    # unit/decimals: one decimal, matching the zone table's fmt_number(v, 1).
    # A whole number would print close_rate's 9,7% and 10,4% identically, which
    # on the mission's weakest conversion is exactly where resolution matters.
    #
    # The goal bar's percentage is value ÷ target, so a rate at 39% of its target
    # draws red under the four-tier grading — see render_kpi_row. No value_basis
    # or goal_basis here: a ratio is already size-neutral, so there is no
    # mismatched denominator for the per-area rescue to fix.
    render_kpi_row([
        {
            "label": t(_RATE_SHORT_LABELS.get(r["key"], r["key"])),
            # None, not 0, when the denominator is empty. render_kpi_row treats
            # a non-numeric value as "no reading yet" and shows the target on
            # its own, rather than reporting a 0% the mission never had the
            # chance to avoid.
            "value": r["value"] if r["value"] is not None else "—",
            "goal": r["target"],
            "unit": "%",
            "decimals": 1,
            "change": r["change"],
            "delta_label": _VS_PRIOR_WEEK,
        }
        for r in _rate_rows
    ])

    _rate_win = t("{start}–{end} · {n} reporting days",
                  start=fmt_day_month(_cur_start), end=fmt_day_month(_cur_end),
                  n=fmt_int(_cur_days))
    if _prev_days < MIN_COMPARABLE_DAYS:
        # Same honesty rule as §1: a missing arrow says why it is missing.
        # Unlike §1 there is no scaled middle case — a rate does not grow with
        # the days behind it, so a short prior window cannot be corrected for,
        # only refused. See period_delta.point_delta.
        st.caption(t(
            "{window}. Change is shown in percentage points once the previous 7 "
            "days hold {need} reporting days; they hold {n}.",
            window=_rate_win, n=fmt_int(_prev_days),
            need=fmt_int(MIN_COMPARABLE_DAYS)))
    else:
        st.caption(t("{window}, against the 7 days before, in percentage points.",
                     window=_rate_win))

    # The arithmetic, in full. This is what the Embudo link was meant to be for.
    # Printing both the words and the numbers matters more than it looks: three
    # of the four rates divide by something other than the stage immediately
    # above them — lesson_rate is lessons ÷ ATTEMPTS, not lessons ÷ contacts —
    # and a reader who assumes a single chain will misread every one of them.
    with st.expander(t("How each rate is calculated")):
        render_table(pd.DataFrame([
            {
                t("Rate"): METRIC_LABELS.get(r["key"], r["key"]),
                t("Calculation"): "{} ÷ {}".format(
                    METRIC_LABELS.get(r["metric"].numerator, r["metric"].numerator),
                    METRIC_LABELS.get(r["metric"].denominator, r["metric"].denominator)),
                t("Figures"): "{} ÷ {}".format(fmt_int(r["numerator"]),
                                               fmt_int(r["denominator"])),
                t("Actual"): fmt_percent(r["value"], 1) if r["value"] is not None else "—",
                t("Target"): fmt_percent(r["target"], 0),
            }
            for r in _rate_rows
        ]))
        st.caption(t(
            "Each rate is the ratio of the mission's totals, not the average of "
            "the areas' own rates — averaging lets a few low-volume areas with "
            "favourable ratios carry the mission figure. Targets come from "
            "AGENT_CONFIG and are the same ones CCSM_Agent1A.gs coaches against."))

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
# emphasis=True on both Key Indicator headings: these are the page's primary
# grouping. The seven KIs are what the mission is judged on, and without the
# stronger tier they sat at exactly the same weight as "Daily Effort Breakdown".
render_section_label(
    t("Key Indicators — Current Week ({span})",
      span=fmt_week_span(_this_monday, _this_sunday)),
    emphasis=True,
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

    # Same days of last week, never last week's full total: on a Wednesday that
    # would set four days against seven and print a collapse the mission has not
    # had, then a recovery on Sunday. The basis is reporting AREAS rather than
    # days here -- the two spans are the same length by construction, so what
    # differs between them is who filed.
    _lw_start, _lw_end = _this_monday - timedelta(days=7), _today - timedelta(days=7)
    _lw_totals = window_totals(_daily_log, _lw_start, _lw_end)
    _lw_areas = window_areas(_daily_log, _lw_start, _lw_end)
    _wtd_min_areas = max(1, round(_active_areas * 0.5)) if _active_areas else 1

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
            "change": period_delta(
                _wtd_totals.get(source, 0), _lw_totals.get(source, 0),
                current_basis=_wtd_areas, prior_basis=_lw_areas,
                min_basis=_wtd_min_areas) if measured else None,
            "delta_label": t("vs same days last week"),
        })
    render_kpi_row(_cur_cards)

    st.caption(
        t("Three indicators are counted live from the nightly form; the other "
          "four arrive with the weekly form. Pace: {pct}% of the week elapsed.",
          pct=fmt_int(_pace_pct))
    )

    if _lw_areas < _wtd_min_areas:
        st.caption(t(
            "No comparison with last week: only {n} areas filed a nightly "
            "report over the same days a week ago.", n=fmt_int(_lw_areas)))

# ── 2b. The last complete week ─────────────────────────────────────────────────
_ki_span = (
    fmt_week_span(_ki_week_end - timedelta(days=6), _ki_week_end)
    if _ki_week_end is not None else ""
)
if not _ki_span:
    render_section_label(t("Key Indicators — Last Complete Week"), emphasis=True)
elif _ki_is_partial:
    render_section_label(
        t("Key Indicators — Week of {span} (in progress)", span=_ki_span),
        emphasis=True)
else:
    render_section_label(t("Key Indicators — Week of {span}", span=_ki_span),
                         emphasis=True)

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

# ── The week before it, for the arrows ────────────────────────────────────────
# A weekly total is a sum over whoever submitted, so two weeks can only be
# compared once both are reduced to a per-area rate — the same rule the goal
# bars follow. Live on 2026-08-21 that is 31 areas (08-16) against 1 (08-09),
# which is why the ≥ half-the-mission gate below matters: without it the row
# would compare the mission to a single companionship and call it a trend.
_prev_week_end = (_ki_week_end - timedelta(days=7)
                  if _ki_week_end is not None else None)
_prev_ki_row = _ki_row_for_week(_prev_week_end)
_prev_ki_reported = (_ki_reporting.get(str(_prev_week_end), 0)
                     if _prev_week_end is not None else 0)
_ki_min_areas = max(1, round(_active_areas * 0.5)) if _active_areas else 1


def _prev_ki_val(metric_key: str) -> float:
    if _prev_ki_row is None or metric_key not in _prev_ki_row.index:
        return 0.0
    return float(_prev_ki_row[metric_key] or 0)


if not _ki_metrics:
    st.info(_EMPTY_MSG)
else:
    render_kpi_row([
        {
            "label": _ki_label(k, label),
            "value": int(_ki_val(k)),
            "goal":  _past_goals.get(k, 0),
            "change": period_delta(
                _ki_val(k), _prev_ki_val(k),
                current_basis=_ki_reported, prior_basis=_prev_ki_reported,
                min_basis=_ki_min_areas),
            "delta_label": t("vs prior week"),
            # Denominator is who reported RESULTS this week, not who set the
            # goals — see _ki_goal_note. Without that, the 1-of-33 case is
            # silent and the bar reads 2040% unexplained.
            "goal_note": _ki_goal_note(k, _past_goal_set_by, _ki_reported),
            "value_basis": _ki_reported,
            "goal_basis":  _past_goal_set_by.get(k, 0),
        }
        for k, label in _ki_metrics.items()
    ])

    if _prev_ki_reported < _ki_min_areas:
        _prev_span = (fmt_week_span(_prev_week_end - timedelta(days=6),
                                    _prev_week_end)
                      if _prev_week_end is not None else "")
        st.caption(t(
            "No comparison with the previous week: {n} of {total} areas "
            "submitted the weekly form for {span}, and at least {need} are "
            "needed for a mission-level comparison.",
            n=fmt_int(_prev_ki_reported), total=fmt_int(_active_areas),
            span=_prev_span, need=fmt_int(_ki_min_areas)))
    elif _prev_ki_reported != _ki_reported:
        st.caption(t(
            "Compared against the previous week per area — {prev} areas "
            "reported then, {now} now.",
            prev=fmt_int(_prev_ki_reported), now=fmt_int(_ki_reported)))

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

    # ── The mission, as a final row ───────────────────────────────────────────
    # Recomputed from the raw totals, never summed or averaged from the rows
    # above it: averaging four zone averages weights an 8-area zone the same as
    # a 13-area one, so it would not equal the mission's own per-area figure.
    # It carries no rank — it is the thing the ranked rows are parts of.
    _mission_row = mission_summary_row(
        zone_df, get_submitting_areas(), _ZONE_FUNNEL_KEYS, _zone_scores,
        per_area=_zone_per_area)
    _mission_cells = {
        t("Rank"):  "",
        t("Zone"):  t("Mission"),
        t("Areas"): fmt_int(_mission_row["areas"]),
    }
    for _k, _lbl in _zone_cols:
        _places = 1 if (_zone_per_area or _k == ZONE_EFFECTIVENESS) else 0
        _mission_cells[_lbl] = fmt_number(_mission_row.get(_k), _places)
    _zone_tbl = pd.concat(
        [_zone_tbl, pd.DataFrame([_mission_cells])], ignore_index=True)

    # Styled rather than rendered plain so the summary reads as a total and not
    # as a fifth zone. render_table hides a Styler's index, so the row is
    # addressed by position.
    _last = len(_zone_tbl) - 1
    _styled = _zone_tbl.style.apply(
        lambda row: (["font-weight:700;border-top:2px solid rgba(255,255,255,0.22);"]
                     * len(row)) if row.name == _last else [""] * len(row),
        axis=1)
    render_table(_styled)

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
# B2 (AUDIT-IA-2026-08-22.md): this section used to plot flavor.nightly_highlights
# (e.g. contacts_attempted) against get_weekly_ki_trends(), which only ever
# returns the seven ki_* columns from the WEEKLY form — those nightly keys can
# never be present there, so the left chart silently drew zero traces. Nightly
# metrics have to come from get_nightly_weekly_trends() (bucketed off
# DAILY_LOG), same fix already applied to the Effort score's per-area source.
# The two charts are also independent questions with independent sources, so
# a missing one no longer blanks out the other — each has its own guard.
render_section_label(t("8-Week Trend — Mission Totals"))

nightly_chart = exclude_current_week(nightly_trends_df)
ki_chart      = exclude_current_week(ki_df)
_has_nightly_trend = not nightly_chart.empty and "week_end_date" in nightly_chart.columns
_has_ki_trend      = not ki_chart.empty and "week_end_date" in ki_chart.columns

if not _has_nightly_trend and not _has_ki_trend:
    st.info(_EMPTY_MSG)
else:
    col_a, col_b = st.columns(2)

    with col_a:
        if _has_nightly_trend:
            weeks = nightly_chart["week_end_date"].astype(str)
            fig1 = go.Figure()
            for i, key in enumerate(flavor.nightly_highlights):
                if key in nightly_chart.columns:
                    fig1.add_trace(go.Scatter(
                        x=weeks, y=nightly_chart[key], mode="lines+markers",
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
        else:
            st.info(_EMPTY_MSG)

    with col_b:
        if _has_ki_trend:
            ki_weeks = ki_chart["week_end_date"].astype(str)
            fig2 = go.Figure()
            for i, key in enumerate(key_indicator_metrics()):
                if key in ki_chart.columns:
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
        else:
            st.info(_EMPTY_MSG)

# ═══════════════════════════════════════════════════════════════════════════════
# THE NIGHTLY WINDOW — shared by sections 5 and 6
# ═══════════════════════════════════════════════════════════════════════════════
# Both sections said "last 7 days" and meant different things. Section 5 read
# get_daily_summary(7), whose cutoff is `today - 7` and therefore spans eight
# dates from the moment tonight's first report lands; section 6 read
# DASHBOARD_SUMMARY's EFFORT rows, which CCSM_Agent5A.gs cuts the same way. The
# window is computed once, here, on the anchor section 7 already grades
# compliance against: the last night whose 9:30 PM deadline has passed. An area
# with hours left to file has not missed anything yet.
_night_anchor = compliance_anchor_date()
_night_start, _night_end = eb.window_bounds(_night_anchor)
_night_span = t("{start}–{end}", start=fmt_day_month(_night_start),
                 end=fmt_day_month(_night_end))
_night_days = [_night_start + timedelta(days=i)
               for i in range((_night_end - _night_start).days + 1)]

# ═══════════════════════════════════════════════════════════════════════════════
# 5. DAILY TREND — one nightly metric, last 7 days
# ═══════════════════════════════════════════════════════════════════════════════
# Was hardcoded to nm_lessons ("Non-Member Lessons per Day"), which CCSM's
# nightly form does not ask, so this section drew nothing for months; it was
# then repointed at flavor.nightly_highlights[0] — contacts_attempted, the
# number section 1b already divides by and section 3 already carries as a
# column. That was M6: one figure, three appearances. The metric is the
# reader's choice now, defaulting to one nothing else on the page shows.
_daily_metric_options = [
    k for k in nightly_metrics()
    if k != "effort" and not daily_df.empty and k in daily_df.columns
]
_daily_default = ("friend_lessons" if "friend_lessons" in _daily_metric_options
                  else (_daily_metric_options[0] if _daily_metric_options else ""))

# Read before the widget is drawn, so the heading can name the chosen metric and
# still sit above its own control (Streamlit renders in source order). Same
# pattern as section 3's Mostrar switch.
_daily_key = st.session_state.get("panel_daily_metric", _daily_default)
if _daily_key not in _daily_metric_options:
    _daily_key = _daily_default
_daily_label = METRIC_LABELS.get(_daily_key, _daily_key)

render_section_label(
    t("Daily {metric} — Last 7 Days", metric=_daily_label) if _daily_key
    else t("Daily Trend — Last 7 Days")
)

if not _daily_metric_options:
    st.info(t("No nightly activity has been logged yet, so there is nothing to "
              "chart by day."))
else:
    st.selectbox(
        t("Metric"), _daily_metric_options,
        format_func=lambda k: METRIC_LABELS.get(k, k),
        index=_daily_metric_options.index(_daily_key),
        key="panel_daily_metric",
    )

    # Reindexed onto the window's seven dates: a day nobody reported is a gap in
    # the mission's activity, and dropping the row would redraw the week as if
    # that day had never been scheduled.
    _daily_window = pd.DataFrame({"Date": [d.isoformat() for d in _night_days]})
    _daily_window = _daily_window.merge(
        daily_df[["Date", _daily_key]], on="Date", how="left"
    ).fillna({_daily_key: 0})
    _daily_window["Label"] = [fmt_day_month(d) for d in _night_days]

    fig_daily = px.bar(
        _daily_window,
        x="Label",
        y=_daily_key,
        labels={"Label": t("Date"), _daily_key: _daily_label},
        title=t("{metric} per day (mission total)", metric=_daily_label),
        color_discrete_sequence=["#6366f1"],
    )
    fig_daily.update_layout(
        xaxis_title=t("Date"),
        xaxis_type="category",
        yaxis_title=_daily_label,
        margin=dict(t=40, b=20),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_daily, use_container_width=True)
    st.caption(t("{span} · mission total per day.", span=_night_span))

# ═══════════════════════════════════════════════════════════════════════════════
# 6. EFFORT LEVEL — last 7 days, over every active area
# ═══════════════════════════════════════════════════════════════════════════════
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
render_section_label(t("Effort Level — Last 7 Days"))

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

if _eff_cur.possible <= 0:
    st.info(t("No effort answers have been logged yet. The nightly form asks "
              "for one every night, so this fills in as areas report."))
else:
    # The prior window, for the score's arrow only. Same pair section 1 uses, so
    # "prior 7 days" means one thing on this page.
    _, _, _eff_prior_start, _eff_prior_end = window_pair(_night_anchor)
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

    st.caption(
        t("{areas} active areas × {days} days = {possible} possible answers. "
          "{missing} were never filed ({pct}). {span}.",
          areas=fmt_int(_eff_cur.area_count),
          days=fmt_int(len(_eff_cur.days)),
          possible=fmt_int(_eff_cur.possible),
          missing=fmt_int(_eff_cur.missing),
          pct=fmt_percent(_eff_cur.missing_share),
          span=_night_span)
    )

    # ── Per day, as a share of that day's areas ───────────────────────────────
    # The old chart was three bars holding the same three numbers as the tiles
    # beside it (M2). Per day it earns its place: it is the only thing on the
    # page that shows whether a Sunday collapses or a transfer week sags, and
    # the unfiled share is drawn rather than described.
    _eff_day_labels = [fmt_day_month(d.day) for d in _eff_cur.days]
    _eff_segments = [
        (eb.ALL,  _eff_labels[eb.ALL],  "#22c55e"),
        (eb.MOST, _eff_labels[eb.MOST], "#f59e0b"),
        (eb.SOME, _eff_labels[eb.SOME], "#ef4444"),
    ]

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
        marker_color="#4b5563",
        customdata=[[d.missing, d.possible] for d in _eff_cur.days],
        hovertemplate="%{fullData.name}: %{customdata[0]}/%{customdata[1]} "
                      "(%{y:.0f}%)<extra></extra>",
    ))
    fig_effort.update_layout(
        barmode="stack",
        title=t("Effort answers per day, share of all active areas"),
        xaxis_title=t("Date"),
        xaxis_type="category",
        yaxis_title=t("Share of active areas"),
        yaxis=dict(range=[0, 100], ticksuffix="%"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=20),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_effort, use_container_width=True)

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


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SUBMISSION COMPLIANCE — all-time summary, calendars, per-area detail
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Submission Compliance"))

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

    # Through t() rather than strftime: strftime follows the SERVER's locale,
    # which on Streamlit Cloud is English regardless of the mission's language.
    _mb_day_labels = [t("Mon"), t("Tue"), t("Wed"), t("Thu"),
                      t("Fri"), t("Sat"), t("Sun")]
    _mb_hdr = "".join(
        f'<th style="text-align:center;padding:4px 8px;color:#9ca3af;font-size:0.72rem;font-weight:600;">{d}</th>'
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
                bg, fg, pct_txt = "rgba(255,255,255,0.02)", "#374151", ""
                title = t("{date} — upcoming", date=d)
            elif d < _mb_win_start:
                _mb_has_pretracking = True
                bg, fg, pct_txt = "rgba(255,255,255,0.03)", "#4b5563", ""
                title = t("{date} — before tracking started", date=d)
            else:
                n = _per_day_counts.get(d, 0)
                pct = round(n / _total_areas * 100) if _total_areas else 0
                _counted_pcts.append(pct)
                bg, fg = _mb_pct_color(pct)
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
                f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{day_num}</div>'
                f'{pct_html}</td>'
            )
        _mb_body += f"<tr>{cells}</tr>"

    def _mb_legend_item(color, label):
        return (
            f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
            f'border-radius:2px;margin-right:4px;"></span>{label}&nbsp;&nbsp;&nbsp;'
        )

    _mb_legend = (
        _mb_legend_item("rgba(34,197,94,0.25)", "&ge;85%")
        + _mb_legend_item("rgba(245,158,11,0.22)", "70–84%")
        + _mb_legend_item("rgba(239,68,68,0.20)", "&lt;70%")
    )
    if _mb_has_future:
        _mb_legend += _mb_legend_item("rgba(255,255,255,0.02)", t("Upcoming"))
    if _mb_has_pretracking:
        _mb_legend += _mb_legend_item("rgba(255,255,255,0.03)",
                                      t("Before tracking started"))

    st.markdown(
        f'<table style="width:100%;border-collapse:separate;border-spacing:3px;margin-bottom:0.5rem;">'
        f'<thead><tr>{_mb_hdr}</tr></thead><tbody>{_mb_body}</tbody></table>'
        f'<div style="font-size:0.72rem;color:#9ca3af;margin-bottom:0.5rem;">'
        + _mb_legend
        + "</div>",
        unsafe_allow_html=True,
    )

    if _counted_pcts:
        _avg = round(sum(_counted_pcts) / len(_counted_pcts))
        st.markdown(
            '<p style="color:#9ca3af;font-size:0.82rem;">'
            + t("Each box is the share of the mission's {total} submitting "
                "areas that turned in the nightly form that day. Window "
                "average: {avg}%.",
                total=f'<strong style="color:#f4f4f8;">{fmt_int(_total_areas)}</strong>',
                avg=f'<strong style="color:#f4f4f8;">{fmt_int(_avg)}</strong>')
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
        _wk_title = t("Week ending {date} — {n}/{total} areas submitted ({pct}%)",
                      date=w, n=fmt_int(n), total=fmt_int(_total_areas),
                      pct=fmt_int(pct))
        _wk_cells += (
            f'<td title="{_wk_title}" '
            f'style="text-align:center;padding:6px 8px;background:{bg};border-radius:4px;'
            f'vertical-align:middle;min-width:52px;">'
            f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1.2;">{_wd.month}/{_wd.day}</div>'
            f'<div style="font-size:0.8rem;font-weight:700;color:{fg};">{fmt_int(pct)}%</div></td>'
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
            '<p style="color:#9ca3af;font-size:0.82rem;">'
            + t("Each box is the share of the mission's {total} areas that "
                "submitted the weekly form for that Mon–Sun week (credited by "
                "the day it arrived). Window average: {avg}%.",
                total=f'<strong style="color:#f4f4f8;">{fmt_int(_total_areas)}</strong>',
                avg=f'<strong style="color:#f4f4f8;">{fmt_int(round(_weekly_avg))}</strong>')
            + '</p>',
            unsafe_allow_html=True,
        )

if _nightly_avg is not None and _weekly_avg is not None:
    _combined = round((_nightly_avg + _weekly_avg) / 2)
    _cc = "#22c55e" if _combined >= 85 else ("#f59e0b" if _combined >= 70 else "#ef4444")
    st.markdown(
        f'<div style="margin-top:0.5rem;padding:10px 14px;border-radius:6px;'
        f'background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);">'
        f'<span style="color:#9ca3af;font-size:0.82rem;">'
        f'{t("Combined submission compliance (nightly + weekly, averaged):")} </span>'
        f'<strong style="color:{_cc};font-size:1.05rem;">{fmt_int(_combined)}%</strong>'
        f'<span style="color:#6b7280;font-size:0.75rem;"> &nbsp;'
        f'{t("— nightly {nightly}%, weekly {weekly}%", nightly=fmt_int(round(_nightly_avg)), weekly=fmt_int(round(_weekly_avg)))}'
        f'</span></div>',
        unsafe_allow_html=True,
    )

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
render_section_label(t("Compliance Rankings"))

# The scope switch is two half-width buttons, as in the reference design.
#
# It was st.segmented_control, which cannot be made to do this. That widget
# renders its buttons inside a flex row carrying `max-width: fit-content`, and
# even with the row forced to 100% the buttons refuse to take the free space --
# measured live: a 780px row with two flex-grow:1 children that stayed 167px
# each. Rather than keep overriding emotion-generated internals that a Streamlit
# upgrade would quietly change underneath us, this uses two real buttons in two
# columns, which fill their halves by construction.
#
# The active half is type="primary", whose indigo fill is already the app's
# accent -- the same distinction the reference draws between the selected and
# unselected tab, achieved with no colour CSS of our own.
_SCOPE_AREA, _SCOPE_ZONE = "area", "zone"
_scope_labels = {
    _SCOPE_AREA: t("Area Rankings"),
    _SCOPE_ZONE: t("Zone Rankings"),
}

# A plain session value, not a widget key: the two buttons write it, and nothing
# else owns it. (The old segmented_control held its state under the same name as
# a WIDGET key, so this deliberately uses a different one -- reusing it would
# collide with whatever Streamlit still has cached for the retired widget.)
if "panel_rank_scope_val" not in st.session_state:
    st.session_state["panel_rank_scope_val"] = _SCOPE_AREA

# type="primary" alone is not enough: the design system sets `background` on
# `.stButton > button` with !important, which flattens Streamlit's own primary
# styling, so both halves render identically and nothing looks selected. The
# selected state is therefore drawn here, keyed on the active button's
# st-key- class -- which the page knows before it draws either button.
_rank_scope = st.session_state["panel_rank_scope_val"]

st.markdown(
    """
    <style>
    div[class*="st-key-panel_rank_tab_"] button {
        min-height: 3.4rem !important;
        border-radius: 10px !important;
    }
    div[class*="st-key-panel_rank_tab_"] button p {
        font-size: 1.05rem !important; font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
# The app's own accent gradient, at the strength the section-label accent bars
# use -- selected reads as "this one", not as a call to action.
st.markdown(
    f"""
    <style>
    div[class*="st-key-panel_rank_tab_{_rank_scope}"] button {{
        background: linear-gradient(135deg, rgba(99,102,241,0.28),
                                    rgba(139,92,246,0.28)) !important;
        border: 1px solid rgba(99,102,241,0.70) !important;
        box-shadow: 0 0 14px rgba(99,102,241,0.28) !important;
    }}
    div[class*="st-key-panel_rank_tab_{_rank_scope}"] button p {{
        color: #ffffff !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

_sc_left, _sc_right = st.columns(2)
for _col, _scope_key in ((_sc_left, _SCOPE_AREA), (_sc_right, _SCOPE_ZONE)):
    with _col:
        if st.button(
            _scope_labels[_scope_key],
            key=f"panel_rank_tab_{_scope_key}",
            use_container_width=True,
            type=("primary"
                  if st.session_state["panel_rank_scope_val"] == _scope_key
                  else "secondary"),
        ):
            st.session_state["panel_rank_scope_val"] = _scope_key
            # Rerun rather than falling through: `type=` for both buttons was
            # evaluated from the OLD value earlier in this same run, so without
            # this the list below would switch while the highlight stayed on the
            # other button until the next interaction.
            st.rerun()

st.write("")

# Zone / District / Area / missionary, for the area view only -- a zone ranking
# filtered to one zone is a single row. This is the same component the
# Breakdowns page uses, under its own prefix so the two pages' selections stay
# independent.
_rk_zone = _rk_district = _rk_area = scope_ANY
if _rank_scope == _SCOPE_AREA:
    _rk_zone, _rk_district, _rk_area, _ = render_scope_selectors(
        get_submitting_areas(), prefix="panel_rank")

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
_period_labels = {p: t(p) for p in cr.PERIODS}

_rc1, _rc2, _rc3 = st.columns(3)
with _rc1:
    _rk_type = st.selectbox(
        t("Compliance Type"), list(_ct_labels),
        format_func=lambda k: _ct_labels[k], key="panel_rank_type")
with _rc2:
    _rk_period = st.selectbox(
        t("Period"), list(cr.PERIODS), format_func=lambda k: _period_labels[k],
        index=list(cr.PERIODS).index("This Month So Far"), key="panel_rank_period")
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
_rk_start, _rk_end = cr.period_bounds(_rk_period, date.today())
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
    if _rk_zone != scope_ANY:
        _rank_rows = [r for r in _rank_rows if r.zone == _rk_zone]
    if _rk_district != scope_ANY:
        _rank_rows = [r for r in _rank_rows if r.district == _rk_district]
    if _rk_area != scope_ANY:
        _rank_rows = [r for r in _rank_rows if r.area == _rk_area]
    _display_rows = _rank_rows
else:
    _display_rows = cr.build_zone_windows(_rank_rows, _rk_type)

_display_rows = cr.rank(_display_rows, _rk_type,
                        worst_first=(_rk_view == "worst"),
                        by_name=(_rk_view == "name"))

#: Row colours. The bands are compliance_rankings.GREEN_MIN / AMBER_MIN, which
#: are the same >=85 / 70-84 / <70 the two calendars above legend -- one number
#: must not be green on a calendar and amber in the ranking beneath it.
_RANK_COLORS = {
    "green": ("rgba(34,197,94,0.10)",  "#22c55e", "#4ade80"),
    "amber": ("rgba(245,158,11,0.10)", "#f59e0b", "#fbbf24"),
    "red":   ("rgba(239,68,68,0.10)",  "#ef4444", "#f87171"),
    "none":  ("rgba(255,255,255,0.03)", "#4b5563", "#9ca3af"),
}


def _rank_row_html(i: int, name: str, detail: str, pct, status: str) -> str:
    bg, dot, fg = _RANK_COLORS[status]
    shown = f"{fmt_int(pct)}%" if pct is not None else "—"
    return (
        f'<div style="display:flex;align-items:center;gap:0.85rem;'
        f'background:{bg};border-radius:8px;padding:0.7rem 1rem;'
        f'margin-bottom:0.35rem;">'
        f'<span style="width:1.6rem;flex:none;text-align:right;color:#6b7280;'
        f'font-size:0.8rem;">{i}</span>'
        f'<span style="width:0.6rem;height:0.6rem;flex:none;border-radius:50%;'
        f'background:{dot};"></span>'
        f'<span style="flex:1 1 40%;color:#f4f4f8;font-weight:600;'
        f'font-size:0.95rem;">{_html_escape(name)}</span>'
        f'<span style="flex:1 1 30%;color:#9ca3af;font-size:0.82rem;">'
        f'{_html_escape(detail)}</span>'
        f'<span style="flex:none;color:{fg};font-weight:700;font-size:0.95rem;'
        f'text-align:right;min-width:3.2rem;">{shown}</span>'
        f'</div>'
    )


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
        return "".join(
            _rank_row_html(
                i,
                getattr(r, "area", None) or getattr(r, "zone", ""),
                _rank_detail(r),
                r.pct(_rk_type),
                cr.status_of(r.pct(_rk_type)),
            )
            for i, r in rows
        )

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
            f'margin:0.55rem 0 0.9rem 0;color:#4b5563;font-size:0.75rem;">'
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
