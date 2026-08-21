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
from app.i18n.formats import (
    fmt_int, fmt_number, fmt_percent, fmt_week_span, fmt_day_month,
)
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
    get_agent_config,
)
from app.analytics.zone_comparison import (
    zone_comparison_table, mission_summary_row, effectiveness_is_rankable,
    ki_scored_area_count, EFFECTIVENESS as ZONE_EFFECTIVENESS,
)
from app.analytics.period_delta import (
    reporting_dates, window_pair, window_totals, window_areas, days_in_window,
    period_delta, MIN_COMPARABLE_DAYS, WINDOW_DAYS,
)
from app.analytics.rate_metrics import rate_rows
from app.analytics import compliance_rankings as cr
from app.components.scope_selector import render_scope_selectors, ANY as scope_ANY
from app.utils.area_helpers import (
    compliance_anchor_date, build_calendar_data,
    latest_due_sunday, weekly_due_weeks,
)
from datetime import date, timedelta
from html import escape as _html_escape

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

# The scope switch reads as two real tabs rather than the small pills
# st.segmented_control draws by default -- same treatment, and the same reason,
# as the section switcher on the Maintenance page.
st.markdown(
    """
    <style>
    div[class*="st-key-panel_rank_scope"] button {
        font-size: 0.95rem !important;
        padding: 0.55rem 1.1rem !important;
        border-radius: 10px !important;
    }
    div[class*="st-key-panel_rank_scope"] button p {
        font-size: 0.95rem !important; font-weight: 600 !important;
    }
    div[class*="st-key-panel_rank_scope"] { margin-bottom: 0.75rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Options are stable ids with a format_func, never the translated label: a
# mid-session language switch would otherwise strand a Spanish string in an
# English options list. Same pattern as the zone table's per-area/totals switch.
_SCOPE_AREA, _SCOPE_ZONE = "area", "zone"
_scope_labels = {
    _SCOPE_AREA: t("Area Rankings"),
    _SCOPE_ZONE: t("Zone Rankings"),
}
if hasattr(st, "segmented_control"):
    _rank_scope = st.segmented_control(
        t("Rankings scope"), [_SCOPE_AREA, _SCOPE_ZONE],
        format_func=lambda k: _scope_labels[k],
        key="panel_rank_scope", default=_SCOPE_AREA,
        label_visibility="collapsed",
    )
else:  # Streamlit < 1.40
    _rank_scope = st.radio(
        t("Rankings scope"), [_SCOPE_AREA, _SCOPE_ZONE],
        format_func=lambda k: _scope_labels[k],
        horizontal=True, key="panel_rank_scope", label_visibility="collapsed",
    )
_rank_scope = _rank_scope or _SCOPE_AREA

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
    shown = f"{pct}%" if pct is not None else "—"
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
    st.markdown("".join(
        _rank_row_html(
            i,
            getattr(r, "area", None) or getattr(r, "zone", ""),
            _rank_detail(r),
            r.pct(_rk_type),
            cr.status_of(r.pct(_rk_type)),
        )
        for i, r in enumerate(_display_rows, start=1)
    ), unsafe_allow_html=True)

    # The window actually graded, not the window asked for. On "This Month So
    # Far" those differ by nine days right now, and the row counts would look
    # arbitrary without it.
    _rk_span = t("{start}–{end}", start=fmt_day_month(_rk_lo),
                 end=fmt_day_month(_rk_hi))
    if _rank_scope == _SCOPE_AREA:
        st.caption(t("{n} area(s) shown · {span}",
                     n=fmt_int(len(_display_rows)), span=_rk_span))
    else:
        st.caption(t("{n} zone(s) shown · {span}",
                     n=fmt_int(len(_display_rows)), span=_rk_span))
