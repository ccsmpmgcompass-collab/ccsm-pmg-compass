"""
breakdowns_engine.py
────────────────────────────────────────────────────────────────────────────────
Rendering engine for views/04_Desgloses.py: the metric catalogue, cached data
loaders, chart helpers, and the shared group-breakdown / teaching-pipeline /
compliance-calendar renderers. Extracted from the page 2026-07-18 so the page
file is just scope-selector dispatch + notes.

Importing this module is side-effect-free beyond defining @st.cache_data'd
functions — no page config, no auth, no CSS injection happen here.
"""

import calendar
import html
import math
import uuid
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from app.analytics import trends
from app.analytics.period_delta import (
    MIN_COMPARABLE_DAYS,
    NEUTRAL_BAND_PCT,
    REPORTING_MIN_SHARE,
    SMALL_COUNT_MAX,
    days_in_window,
    period_delta,
    reporting_dates,
)
from app.components.charts import (
    apply_layout, chart, change_text, ranked_list, stage_bars,
)
from app.components.design_system import (
    goal_bar_state, goal_bar_status, projection_caption, render_kpi_row,
    render_section_label,
)
from app.components.ki_drilldown import (
    ki_href, render_ki_drilldown, selected_ki,
)
from app.config.theme import series_style, STATUS
from app.i18n.formats import fmt_day_month, fmt_int, fmt_number
from app.db.queries import (
    get_area_expectation_entry,
    get_area_weekly_goals,
    get_area_type_category_labels,
    get_blitz_dates,
    get_config_value,
    get_daily_log,
    get_group_weekly_expectation_totals,
    get_lineage_for_retired_parent,
    get_lineage_for_successor,
    get_nightly_submission_timing,
    get_weekly_form_data,
    get_weekly_ki,
    get_weekly_submission_data,
    get_zones,
    is_within_last_transfers,
    resolve_area_category_label,
)
from app.utils.transfer_helpers import (
    transfer_cycles, transfer_period_bounds, transfer_window,
)
from app.analytics import transfer_year
from app.db.goals_queries import areas_with_goals, group_goal_totals
from app.utils.area_helpers import (
    build_calendar_data,
    compliance_anchor_date,
    format_metric_label,
    latest_due_sunday,
    mission_today,
    weekly_due_weeks,
)
from app.i18n import t


# ══════════════════════════════════════════════════════════════════════════════
# METRIC CATALOGUE (group views)
# ══════════════════════════════════════════════════════════════════════════════
# The catalogue is GENERATED from the live QUESTIONS_CONFIG tab — see
# app/config/metric_catalog.py. This module used to carry its own copy of Utah
# Provo's vocabulary (gate, pew, renew, date_metric, nm_doors, lsi_given,
# locos_Attempt, mmm_sent …), none of which is a question on a CCSM form, and
# the same list existed in app/config/metrics.py and app/utils/area_helpers.py
# as well.
#
# These are FUNCTIONS, not module-level dicts, deliberately: a dict would be
# built at import time, when there is no session and no sheet to read.

from app.config.metric_catalog import (
    goal_metric_key,
    is_rate_metric,
    key_indicator_metrics,
    ki_short_label,
    metric_options,
    non_numeric_metrics,
    weekly_metric_keys,
)


def _weekly_metrics() -> frozenset[str]:
    """Metrics that live only in the weekly form — one row per area per WEEK,
    no daily grain to toggle to, so they are always bucketed by week.

    CCSM has no third source here. Provo additionally had WEEKLY_KI-computed
    metrics (mmm_sent) merged in as `_WEEKLY_KI_METRICS`; CCSM's WEEKLY_KI holds
    the same `ki_*` keys the form already supplies, so the weekly-form set is
    the whole of it.
    """
    return weekly_metric_keys()

# Shared style for every expectation reference (trend hlines, bar hlines, and
# the area bar's dash markers) — one look everywhere Carson sees "the bar".
_EXP_LINE_STYLE = dict(color="rgba(203,203,210,0.55)", width=1.5, dash="dot")
# NEVER pass this dict to add_hline directly — always dict(_EXP_ANNOTATION).
# add_hline MUTATES the annotation dict it's given (writes x/y/anchors/text
# into it), so sharing one instance pinned every expectation label on every
# chart to wherever the process's FIRST-drawn line happened to sit — the
# "label floating where the old line used to be" glitch on Area/x-axis
# switches (Carson, 2026-07-19).
_EXP_ANNOTATION = dict(
    font=dict(color="rgba(210,210,216,0.95)", size=11),
    bgcolor="rgba(8,8,14,0.55)",
)


def _expectation_paces(group_areas, metric) -> dict[float, tuple[dict, set[str]]]:
    """Distinct expectation paces among `group_areas` for `metric`, from the
    editable AREA_TYPE_EXPECTATIONS table (Goals > Area Expectation
    Settings): {weekly_pace: (entry, category_labels)}. Grouped by PACE, not
    category, so two categories sharing a number draw ONE reference line —
    each pace keeps every category label that produced it. An area whose
    category defines no (or a zero) expectation contributes nothing."""
    paces: dict[float, tuple[dict, set[str]]] = {}
    for a in group_areas:
        e = get_area_expectation_entry(a, metric)
        if not e:
            continue
        p = round(e["weekly"], 4)
        if p in paces:
            paces[p][1].add(resolve_area_category_label(a))
        else:
            paces[p] = (e, {resolve_area_category_label(a)})
    return paces


def _expectation_prefix(cats: set[str], multi: bool) -> str:
    """Label prefix for one expectation reference: bare "Expectation" when
    the chart shows a single distinct pace, otherwise the producing
    category/ies joined in settings-tab order ("Spanish/Bilingual
    Expectation")."""
    if not multi:
        return t("Expectation")
    rank = {lbl: i for i, lbl in enumerate(get_area_type_category_labels())}
    return t("{categories} Expectation",
             categories="/".join(sorted(cats, key=lambda l: rank.get(l, len(rank)))))


def _expectation_rate(entry: dict) -> str:
    """The stored figure as typed in the settings tab: "30/wk" or "2/mo"."""
    unit = "mo" if entry["cadence"] == "monthly" else "wk"
    return f"{entry['value']:g}/{unit}"


# Rate/score metrics are averaged across areas, never summed — see
# is_rate_metric() in app/config/metric_catalog.py, which mirrors
# CCSM_Agent1A.gs's A1A_RATE_METRICS and is held to it by a test.

_ANY = "— any —"

# ── KPI card periods ──────────────────────────────────────────────────────────
# Windows for the group's key-indicator cards. Values come from DAILY_LOG (one
# row per area per day), which is the only source that can answer an arbitrary
# range — LIVE_SNAPSHOT only stores fixed 7d/14d/28d/transfer rollups.
_KPI_PERIODS = [
    # The transfer leads, because the transfer is the unit the mission actually
    # plans and is judged in — a week is a reporting rhythm and a month is an
    # accident of the calendar. Filled in on 2026-09-03, once TRANSFER_SCHEDULE
    # held the mission's real cycles; before that these two labels would have
    # rested on a six-week guess from TRANSFER_START_DATE.
    "This Transfer So Far",
    "Last Transfer",
    "This Week",
    "Last Week",
    "This Month So Far",
    "Last Month",
    "All Time",
    "Custom",
]

# DAILY_LOG history to pull for the cards. The `days` arg to get_daily_log is a
# client-side filter — read_tab reads (and caches) the whole tab either way — so
# a wide window costs no extra Sheets read. See sheets_client._read_tab_cached.
_KPI_HISTORY_DAYS = 3650


def _kpi_period_bounds(
    label: str, today: date, transfers: dict | None = None
) -> tuple[date | None, date | None, int | None]:
    """(start, end, days_in_full_period) for a KPI period label — both ends
    inclusive. Returns (None, None, None) for "All Time": no bounds, and no
    goal, since a goal over unbounded history is meaningless.

    The mission week runs Monday–Sunday (Agent5A.gs rolls back to Monday, and
    the weekly report covers Mon–Sun), so weeks anchor on Monday, not Sunday.

    days_in_full_period is the FULL length of the period, not the elapsed part,
    so an in-progress period's card reads as "progress toward this week's /
    this month's goal" rather than silently lowering the bar.
    """
    # The two transfer windows are resolved from TRANSFER_SCHEDULE by the
    # caller and handed in, rather than read here: this function is pure and is
    # held to `compliance_rankings.period_bounds` by a drift test, and a sheet
    # read inside it would make both of those false.
    if label in ("This Transfer So Far", "Last Transfer"):
        bounds = (transfers or {}).get(label)
        if not bounds:
            return None, None, None
        start, end = bounds
        if label == "Last Transfer":
            # A completed cycle: its full length IS its length.
            return start, end, (end - start).days + 1
        # In progress. days_in_full_period is the WHOLE cycle, so the goal is
        # the transfer's goal rather than a fortnight's worth of it — the same
        # rule "This Month So Far" follows.
        full = (transfers or {}).get("_this_transfer_full")
        return start, end, ((full - start).days + 1 if full else None)

    if label == "This Week":
        return today - timedelta(days=today.weekday()), today, 7
    if label == "Last Week":
        this_monday = today - timedelta(days=today.weekday())
        return this_monday - timedelta(days=7), this_monday - timedelta(days=1), 7
    if label == "This Month So Far":
        return (
            today.replace(day=1),
            today,
            calendar.monthrange(today.year, today.month)[1],
        )
    if label == "Last Month":
        last_day = today.replace(day=1) - timedelta(days=1)
        return (
            last_day.replace(day=1),
            last_day,
            calendar.monthrange(last_day.year, last_day.month)[1],
        )
    # "Custom" resolves from two date widgets, not from `today`; the caller
    # overrides all three values. It is listed here so the fall-through below
    # cannot silently hand it All Time's unbounded window.
    return None, None, None  # All Time, and Custom before its widgets are read


def _kpi_prior_bounds(
    label: str, cur_start: date | None, cur_end: date | None, today: date,
    floor: date | None = None, transfers: dict | None = None,
) -> tuple[date, date] | None:
    """The TWIN of a KPI period: the same-shaped window immediately before it,
    both ends inclusive — or None when the period has no honest twin.

    "Same-shaped", not "same-named", and the difference matters on an
    in-progress period. Three days into September, the twin of "This Month So
    Far" is 1–3 August, not the whole of August: a ghost bar drawn from 31 days
    of history standing beside a 3-day bar is not a comparison, it's a
    guaranteed collapse. The same reading applies to "This Week" — four days
    into the week, the twin is the first four days of last week.

    (`period_delta` normalizes the prior side onto the current side's basis, so
    the ARROW would survive a mismatched twin either way. The charts in Steps
    C2/C3 draw the twin's raw per-bucket totals, and those would not.)

    A completed period's twin is simply the whole period before it. "All Time"
    has no twin at all — there is no earlier history to hold it against — and
    says so by returning None rather than inventing one.

    A twin that would start before the mission's own records is still returned;
    the caller sees an empty slice and reports "no comparison yet", which is the
    truth. Clamping it here would silently shorten the window instead.
    """
    if label == "All Time" or cur_start is None or cur_end is None:
        return None

    if label == "This Week":
        # Same elapsed days of last week: last Monday .. last Monday + offset.
        prior_monday = cur_start - timedelta(days=7)
        return prior_monday, prior_monday + (cur_end - cur_start)

    if label == "Last Week":
        return cur_start - timedelta(days=7), cur_end - timedelta(days=7)

    if label == "This Month So Far":
        # Same elapsed days of last month. A month shorter than the elapsed
        # window (31 March -> February) clamps at its own last day rather than
        # spilling into March, which would double-count days already in `cur`.
        last_day_prev = cur_start - timedelta(days=1)
        p_start = last_day_prev.replace(day=1)
        elapsed = (cur_end - cur_start).days
        return p_start, min(p_start + timedelta(days=elapsed), last_day_prev)

    if label == "Last Month":
        last_day_prev = cur_start - timedelta(days=1)
        return last_day_prev.replace(day=1), last_day_prev

    if label == "This Transfer So Far":
        # The same elapsed days of the previous cycle. Six weeks against
        # eighteen days would report a collapse on every card.
        prev = (transfers or {}).get("Last Transfer")
        if not prev:
            return None
        p_start, p_end = prev
        twin_end = p_start + (cur_end - cur_start)
        return (p_start, min(twin_end, p_end)) if twin_end >= p_start else None

    if label == "Last Transfer":
        # Would need the cycle before the previous one. TRANSFER_SCHEDULE
        # reaches back to 2026-06-15 and no further, so there is none — and an
        # absent twin is reported as absent rather than guessed at by
        # subtracting six weeks from a date the schedule never recorded.
        prev2 = (transfers or {}).get("_transfer_before_last")
        if not prev2:
            return None
        return prev2

    if label == "Custom":
        # An arbitrary range's twin is the equal-length window ending the day
        # before it starts. `floor` is where the mission's records begin: a twin
        # reaching back past it would be measured against days that do not
        # exist, and a partial twin would be worse than none — it would look
        # like a real comparison. So there simply is no twin, and the caller
        # says so, the same as All Time.
        length = (cur_end - cur_start).days + 1
        pr_end = cur_start - timedelta(days=1)
        pr_start = pr_end - timedelta(days=length - 1)
        if floor is not None and pr_start < floor:
            return None
        return pr_start, pr_end

    # An unknown label (a period added to _KPI_PERIODS without a twin rule)
    # gets no twin rather than a wrong one.
    return None


def _records_floor(hist: pd.DataFrame) -> date:
    """The earliest date this page may be asked about.

    AGENT_CONFIG's SYSTEM_START_DATE is the mission's own answer and is
    authoritative — but it is a hand-entered figure and is currently 2026-08-10,
    one day AFTER DAILY_LOG's first row. Taking the earlier of the two means a
    date picker can never exclude a day the mission actually has data for, which
    is the only way this floor can be wrong in a direction anyone would notice.
    """
    floor = date(2026, 6, 8)   # the default used elsewhere in app/db/queries.py
    try:
        configured = str(get_config_value("SYSTEM_START_DATE", "") or "").strip()[:10]
        if configured:
            floor = date.fromisoformat(configured)
    except (ValueError, TypeError):
        pass
    if hist is not None and not hist.empty and "Date" in hist.columns:
        try:
            earliest = date.fromisoformat(str(hist["Date"].min())[:10])
            floor = min(floor, earliest)
        except (ValueError, TypeError):
            pass
    return floor


def _completed_weekly_series(hist: pd.DataFrame, key: str, before: date):
    """(values, week_end_dates) for this group's COMPLETED Mon-Sun weeks in
    `key`, oldest first, every week ending strictly before `before`.

    Completed at BOTH ends, and the leading end is the one that actually bit.

    A week that is three days old is a small number, not a low week, and
    feeding it to a straight-line fit as though it were finished would drag
    every projection down each Monday and let it recover by Sunday — a sawtooth
    in the forecast that describes the calendar, not the mission.

    The same is true of the first week, and there it was not hypothetical.
    DAILY_LOG begins on Sunday 2026-08-09, so the week ending that day held one
    area-day and a total of 7 where a real week holds ~240 and ~180. The series
    read 7 → 197 → 127 → 159, the fit saw a mission exploding out of nothing,
    and roleplays — 22 in three days — projected to land at 867 (seen live
    2026-09-03; a straight pace says ~220). A week is only counted when its
    whole Monday-to-Sunday span lies inside the records.
    """
    if hist is None or hist.empty or key not in hist.columns:
        return [], []
    if "Date" not in hist.columns:
        return [], []
    frame = hist[["Date", key]].copy()
    frame["__d"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.dropna(subset=["__d"])
    if frame.empty:
        return [], []
    # Sunday-ending weeks, matching the mission week the rest of the app uses
    # (Agent5A.gs rolls back to Monday; the weekly report covers Mon-Sun).
    frame["__wk"] = (frame["__d"] + pd.to_timedelta(
        6 - frame["__d"].dt.weekday, unit="D")).dt.date
    frame[key] = pd.to_numeric(frame[key], errors="coerce").fillna(0)
    first = frame["__d"].min().date()
    weekly = frame.groupby("__wk")[key].sum().sort_index()
    weekly = weekly[[
        w < before and (w - timedelta(days=6)) >= first for w in weekly.index]]
    return [float(v) for v in weekly.values], [w.isoformat() for w in weekly.index]


def _landing_estimate(value, elapsed_days, full_days, weekly_values, week_dates):
    """Where this period is heading, and how much to believe it.

    Returns ``{"value": float, "confidence": "high"|"low"}`` or None when there
    is nothing honest to say.

    Two methods, and which one runs depends on how much history exists:

      * **Fewer than four completed weeks** — straight pace extrapolation. It
        assumes the rest of the period looks like the part already run, which
        is a weak assumption and is labelled as one ("early estimate").
      * **Four or more** — the remaining days are projected from the fitted
        weekly trend instead, so a mission that is climbing is not credited
        with only its current average. compute_projection() reports whether
        that slope is distinguishable from flat, and that is the confidence.

    Either way the estimate is ``what has already happened`` plus ``what the
    remaining days are expected to add`` — never a pure forecast. The days
    already banked are facts and are not re-predicted.
    """
    try:
        value = float(value)
        elapsed_days = int(elapsed_days)
        full_days = int(full_days)
    except (TypeError, ValueError):
        return None
    if elapsed_days <= 0 or full_days <= 0 or elapsed_days > full_days:
        return None
    remaining = full_days - elapsed_days
    if remaining <= 0:
        return None   # the period is over; there is nothing left to project

    if len(weekly_values) >= trends.MIN_WEEKS:
        proj = trends.compute_projection(weekly_values, week_dates)
        if proj.get("status") == "ok":
            per_day = max(0.0, float(proj.get("projected", 0))) / 7.0
            return {"value": value + per_day * remaining,
                    "confidence": proj.get("confidence", "low")}

    if value <= 0:
        # Nothing has happened yet, so a pace extrapolation would project zero
        # and print it as a forecast. Silence is the honest reading.
        return None
    return {"value": value / elapsed_days * full_days, "confidence": "low"}


def _twin_label(label: str) -> str:
    """What the arrow under a card is measured against, in words.

    It sits beside the number ("↑ 12% vs last week"), so it names the twin the
    way a person would say it out loud rather than printing its dates — the
    dates are in the section caption, once, instead of on all sixteen cards.

    Deliberately says "same days last month" and not "last month": the twin of
    an in-progress period is the matching partial slice, and a label claiming
    otherwise would misdescribe the arithmetic beneath it.
    """
    return {
        "This Week": t("vs last week"),
        "Last Week": t("vs the week before"),
        "This Month So Far": t("vs same days last month"),
        "Last Month": t("vs the month before"),
        "This Transfer So Far": t("vs same days last transfer"),
        "Last Transfer": t("vs the transfer before"),
    }.get(label, t("vs the period before"))


def _resolve_group_goal(
    metric: str, goals: dict | None, per_area_goals: dict, n_areas: int,
    transfer_weekly: dict | None = None, transfer_note: str = "",
    transfer_basis: int = 0,
    meta_weekly: dict | None = None, meta_basis: int = 0,
) -> tuple[float, str, int, str]:
    """This group's WEEKLY goal for `metric`, the arithmetic behind it, how many
    areas that goal covers, and WHICH source it came from.

    Four sources, most-specific first — one precedence rule for the whole app
    (PLAN §7.5), and the last two are new with Step 7:

      1. GOALS_CONFIG, summed across the group's areas by the caller. This is
         what the Goals page edits, so an entered goal always wins.
      2. ``AREA_TRANSFER_GOALS`` for the cycle this period sits in, summed over
         the group and divided by the cycle's weeks — its weekly equivalent, so
         it enters this function's contract like any other weekly number. When
         the period IS the transfer, the caller's ``_goal_factor`` multiplies it
         straight back to the transfer total.
      3. AGENT_CONFIG's ``GOAL_<metric>`` rows, which are PER AREA PER WEEK, so
         a group's goal is that number times how many areas are in it.
      4. The companionships' own summed ``ki_*_meta`` — what the areas set for
         THEMSELVES on the weekly form. A different kind of fact from a
         leadership target, so it is the last resort and the caller must label
         it as such; never silently presented as "the goal".

    In practice tiers 1 and 3 are empty for a Key Indicator: GOALS_CONFIG is an
    empty tab mission-wide and every AGENT_CONFIG.GOAL_* row is a nightly metric
    (probed live 2026-09-05). So tier 2 is what lights a KI bar once leadership
    enters a goal, and tier 4 is what holds the Panel and this page exactly as
    they are until then — nothing regresses before the first goal is saved.

    Conversely, tiers 2 and 4 are empty for a nightly metric, so the nightly
    grid's behaviour is unchanged by their existence.

    The returned note carries the arithmetic because the product alone is
    unreadable on screen: a bar saying "48% of 1.200" is 150 x 8 areas, and
    nothing else on the card says so. It is empty for an entered goal, which is
    its own explanation.

    The third value is the goal's BASIS — how many areas it is the goal FOR.
    render_kpi_row needs it beside the value's own basis, because a total from
    38 reporting areas over a goal set for 43 is not a percentage anyone should
    read (audit F8). Reduce both to per-area rates first and the mismatched
    denominators cancel.

    The fourth is the source — "config", "transfer", "agent", "meta" or "" for
    no goal at all. Only tier 4 changes what the card SAYS, but naming all four
    keeps the caller from inferring the source from the note's shape.
    """
    entered = float((goals or {}).get(metric, 0) or 0)
    if entered > 0:
        return entered, "", n_areas, "config"

    transfer = float((transfer_weekly or {}).get(metric, 0) or 0)
    if transfer > 0:
        return transfer, transfer_note, (transfer_basis or n_areas), "transfer"

    per_area = float((per_area_goals or {}).get(metric, 0) or 0)
    if per_area > 0 and n_areas > 0:
        return (per_area * n_areas,
                t("{per_area} per area x {n}",
                  per_area=fmt_int(per_area), n=fmt_int(n_areas)),
                n_areas, "agent")

    meta = float((meta_weekly or {}).get(metric, 0) or 0)
    if meta > 0 and meta_basis > 0:
        return (meta,
                t("the companionships' own goal — {n} areas set one",
                  n=fmt_int(meta_basis)),
                meta_basis, "meta")

    return 0.0, "", 0, ""


def _comparison_note(
    label: str, pr_start: date | None, pr_end: date | None,
    cur_days: int, prior_days: int,
) -> str:
    """One line saying what the arrows are measured against — or why there
    aren't any.

    A missing arrow with no explanation is the IA audit's own M7 finding (empty
    states that never say why), and on this page it would be actively
    misleading: DAILY_LOG begins 2026-08-09, so "This Month So Far" has a twin
    of 1-3 August that is legitimately empty. A reader seeing no arrows and no
    note would reasonably conclude the mission had not moved.

    Pure — it takes numbers and returns a string, so the four cases below are
    tested directly rather than through a rendered page.
    """
    if pr_start is None or pr_end is None:
        # t(label), not label: the period names are keys, and interpolating the
        # raw key printed "Custom no tiene un período anterior…" on a Spanish
        # page (seen live 2026-09-03).
        return t("{label} has no earlier period to compare against.",
                 label=t(label))

    window = t("{start}–{end}", start=fmt_day_month(pr_start), end=fmt_day_month(pr_end))

    if prior_days < MIN_COMPARABLE_DAYS:
        return t(
            "No comparison yet: {window} holds {n} days on which at least half "
            "this group's areas reported, and {need} are needed.",
            window=window, n=fmt_int(prior_days), need=fmt_int(MIN_COMPARABLE_DAYS))
    if cur_days < MIN_COMPARABLE_DAYS:
        return t(
            "No comparison yet: this period holds {n} reporting days so far, "
            "and {need} are needed.",
            n=fmt_int(cur_days), need=fmt_int(MIN_COMPARABLE_DAYS))
    return t(
        "Arrows compare against {window} — {n} reporting days, scaled onto this "
        "period's {m}.",
        window=window, n=fmt_int(prior_days), m=fmt_int(cur_days))


def _slice_to_window(
    frame: pd.DataFrame, start: date | None, end: date | None
) -> pd.DataFrame:
    """`frame` cut to [start, end] on its Date column, both ends inclusive.

    Date is a normalised YYYY-MM-DD string, so a lexicographic compare is a
    correct date compare and needs no parsing. An empty frame, a missing Date
    column or a None bound all return the frame unchanged — the same rule the
    current-period slice has always applied.
    """
    if frame is None or frame.empty or "Date" not in frame.columns:
        return frame if frame is not None else pd.DataFrame()
    if start is None or end is None:
        return frame
    return frame[
        (frame["Date"] >= start.isoformat()) & (frame["Date"] <= end.isoformat())
    ]


# ══════════════════════════════════════════════════════════════════════════════
# CACHED LOADERS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def _load_daily_history() -> pd.DataFrame:
    """DAILY_LOG as far back as it goes — powers the KPI cards' All Time and
    month periods. read_tab reads (and caches) the whole tab, so this is not a
    second Sheets read."""
    return get_daily_log(_KPI_HISTORY_DAYS)


def _group_area_names(areas_all: pd.DataFrame, col: str, value: str) -> set:
    """The areas MISSION_ORG currently lists for this zone/district.

    MISSION_ORG is the roster of record, so membership is decided here and
    nowhere else — see _scope_to_areas().
    """
    if areas_all.empty or col not in areas_all.columns:
        return set()
    sel = areas_all[areas_all[col].astype(str).str.strip() == value]
    return set(sel["Area_Name"].astype(str).str.strip())


def _scope_to_areas(df: pd.DataFrame, area_col: str, areas: set) -> pd.DataFrame:
    """Filter a frame to a group by AREA NAME against MISSION_ORG's roster.

    Deliberately not filtered on the frame's own Zone/District column: those
    record where an area was *at the time the row was written*. DAILY_LOG keeps
    every historical row, so an area that has since left the mission still
    carries its old zone and would keep showing up on that zone's charts
    forever (and one that moved zones would be counted under its old zone).
    Filtering on the current roster instead means a closed area disappears
    everywhere the moment MISSION_ORG marks it inactive.
    """
    if df.empty or area_col not in df.columns or not areas:
        return pd.DataFrame()
    return df[df[area_col].astype(str).str.strip().isin(areas)].copy()


@st.cache_data(ttl=300)
def _load_zones() -> list:
    return get_zones()


@st.cache_data(ttl=300)
def _nice_count_dtick(y_max: float, target_ticks: int = 6) -> int:
    """Smallest 1/2/5×10ⁿ tick step, floored at 1, giving ~`target_ticks`
    gridlines over [0, y_max]. Every trend metric is a whole-number count
    (people, lessons, baptisms — never a rate), so a step under 1 would put a
    gridline at "2.5 people", which nothing on this chart can ever equal.
    Above that floor it still picks a normal step (2/5/10/20/50…) rather than
    forcing dtick=1 everywhere, or a zone with hundreds of contacts would get
    an unreadable wall of gridlines.
    """
    if y_max <= target_ticks:
        return 1
    raw = y_max / target_ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        step = m * magnitude
        if step >= raw:
            return int(step)
    return int(10 * magnitude)


def _isolating_trend_chart(fig: go.Figure, height: int = 520, enable_isolate: bool = True) -> None:
    """Render `fig` so a legend click switches straight to the clicked trace.

    Draws in a component iframe with its own plotly.js, which is the only way to
    replace Plotly's legend click behaviour from Streamlit — see the note above.

    `enable_isolate=False` (the area-level view, one line) skips attaching the
    click handler entirely. It's NOT enough to rely on the figure's own
    `legend.itemclick=False` while still attaching _LEGEND_ISOLATE_JS — that
    handler's `return false` only blocks PLOTLY's default handling, it doesn't
    stop the handler itself from firing and restyling traces. With one area
    there's nothing to isolate, and the handler's restoreAll logic assumes the
    bridge/✕ traces start hidden ('legendonly') so it can toggle them on — on
    the area view they're already forced `visible=True` from the start, so the
    handler instead flips them to 'legendonly' on the very first click and can
    never restyle them back (Carson: "the X's disappear and then it glitches
    and you can't reset it").
    """
    # The shared layout, the same one charts.chart() applies — the template,
    # the margins, the legend below the plot (plan step D4). Streamlit's own
    # plotly theming does not reach inside a component iframe, but a template
    # APPLIED to the figure is serialised with it by to_html, so the chart
    # arrives dressed. Only the iframe's own two needs are set after it.
    apply_layout(fig, height=height)
    fig.update_layout(autosize=True, height=height - 20)
    div_id = "trend-" + uuid.uuid4().hex
    chart = fig.to_html(
        # This iframe gets a fresh div_id (and so a fresh <script src=cdn>
        # fetch/parse/execute in a brand-new JS realm — no state carries over
        # between iframes even once the URL is browser-cached) on EVERY
        # fragment rerun that touches this chart, i.e. every single Zone/
        # District/Area/Period/Metric switch. Bundling plotly.js inline
        # removes that per-switch network+script dependency entirely so the
        # chart paints synchronously with the rest of the HTML instead of
        # popping in a beat later.
        include_plotlyjs=True,
        full_html=False,
        div_id=div_id,
        config={"responsive": True, "displayModeBar": False},
    )
    script = ("<script>" + (_LEGEND_ISOLATE_JS % {"div_id": div_id}) + "</script>"
              if enable_isolate else "")
    components.html(
        "<style>body{margin:0;background:transparent;overflow:hidden;}</style>"
        + chart + script,
        height=height,
    )


# ══════════════════════════════════════════════════════════════════════════════
# GROUP BREAKDOWN (zone or district) — the old Zone Breakdown body, scoped
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# TEACHING PIPELINE (group views)
# ══════════════════════════════════════════════════════════════════════════════

#: The teaching pipeline's five stages, in order (plan step D5). All five are
#: Key Indicators from the weekly form, which is the point: the funnel used to
#: take its "Enseñadas" stage from the Tableau export, so one bar of four
#: depended on when a scraper last ran and the other three did not. The Embudo
#: de Búsqueda page owns Tableau now, and this one is the mission's own report
#: end to end.
_PIPELINE_STAGES = (
    "ki_new_people_real",
    "ki_member_lessons_real",
    "ki_friends_sacrament_real",
    "ki_baptismal_date_real",
    "ki_baptized_confirmed_real",
)


def _render_teaching_pipeline(
    scope_value: str,
    kpi_period: str,
    p_start,
    p_end,
    in_progress: bool,
    span: str,
    rows,
    weekly_wk,
    group_areas: set,
    weekly_prior=None,
    twin_label: str = "",
) -> None:
    """The five Key Indicators as a pipeline, for one scope over one period.

    A module-level function rather than inline in render_group_breakdown
    because the trend above it returns early in three different states — no
    metrics, too many areas for a line chart, no weekly form yet — and any of
    those returns would otherwise take this section down with it.

    Every stage counts what HAPPENED inside the selected period, exactly like
    the Key Indicator cards — NOT a cohort ("people found this month who later
    got baptized"). The five are not subsets of each other either: a lesson
    with a member present is not one of the new people above it. The shape says
    "this is the order the work goes in", and the section's ⓘ says the rest.
    """
    # "This Week" is suppressed on purpose (Carson, 2026-07-17): every stage
    # comes from the weekly Sunday form, which keys on the week's ending
    # Sunday and so reads 0 every day Mon–Sat. A pipeline that bottoms out at
    # 0 mid-week is misleading, so the whole section is skipped rather than
    # shown empty.
    if kpi_period == "This Week":
        return

    def _total(frame, col: str):
        """Total for one already-scoped, already-period-cut column, or None
        when the frame does not carry it. None, not 0: a stage this mission
        never collects has no reading, and an honest zero is a different fact
        from an absent one."""
        if frame is None or frame.empty or col not in frame.columns:
            return None
        return float(pd.to_numeric(frame[col], errors="coerce").fillna(0).sum())

    stages = [(ki_short_label(k), _total(weekly_wk, k)) for k in _PIPELINE_STAGES]
    if not any(v for _, v in stages):
        render_section_label(
            t('Teaching Pipeline — {scope_value}', scope_value=scope_value))
        st.info(t('No pipeline activity recorded for {scope_value} in {kpi_period}.',
                  scope_value=scope_value, kpi_period=t(kpi_period).lower()))
        return

    twin = [_total(weekly_prior, k) for k in _PIPELINE_STAGES]
    has_twin = any(v is not None for v in twin)

    render_section_label(
        t('Teaching Pipeline — {scope_value}', scope_value=scope_value),
        right=span,
        info=t("The five Key Indicators in the order the work goes in, counting "
               "what happened inside this period — not a cohort: the people "
               "baptized here are not necessarily the ones found here. They are "
               "not subsets of each other either, so a percentage between two "
               "stages is a ratio of two counts and not a survival rate. Amigos "
               "en sacramental is a weekly headcount rather than a roster of "
               "names, so someone who attends several Sundays in this period is "
               "counted each week.")
        + (" " + t("The thin bar under each stage is {twin}.", twin=twin_label)
           if has_twin and twin_label else ""),
    )
    st.markdown(
        stage_bars(stages, highlight_worst=True,
                   twin=twin if has_twin else None, twin_label=twin_label),
        unsafe_allow_html=True)


# ── Form submission compliance calendars ──────────────────────────────────────
# Restored for all three levels 2026-07-17 (Carson). The AREA view gets the exact
# old per-day status calendar — on time / late / blitz / missed — since one area
# has a single unambiguous status each day. A ZONE/DISTRICT has several areas per
# day, so it gets the % calendar the Dashboard page already uses: each
# box is the share of that group's accountable areas that submitted, coloured on
# the same ≥85 / 70–84 / <70 thresholds as the compliance pills. A weekly-form
# row sits under each, same idea (discrete pills for an area, % for a group).
_COMPLIANCE_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_C_GREEN = ("rgba(34,197,94,0.25)", "#22c55e")
_C_AMBER = ("rgba(245,158,11,0.22)", "#f59e0b")
_C_RED   = ("rgba(239,68,68,0.20)", "#ef4444")
_C_BLITZ = ("rgba(139,92,246,0.22)", "#a78bfa")
_C_UPCOMING = ("rgba(255,255,255,0.03)", "#4b5563")


def _pct_color(pct: float) -> tuple:
    """Green ≥85, amber 70–84, red below — the compliance thresholds shared with
    the Dashboard calendar and the summary pills."""
    if pct >= 85:
        return _C_GREEN
    if pct >= 70:
        return _C_AMBER
    return _C_RED


def _compliance_legend(items: list) -> str:
    return (
        '<div style="font-size:0.72rem;color:#9ca3af;margin-bottom:0.75rem;">'
        + "".join(
            f'<span style="display:inline-block;width:10px;height:10px;background:{c};'
            f'border-radius:2px;margin-right:4px;"></span>{lbl}&nbsp;&nbsp;&nbsp;'
            for c, lbl in items
        )
        + "</div>"
    )


def _render_compliance(
    scope_kind: str,
    scope_value: str,
    group_areas: set,
    daily_hist: pd.DataFrame,
    area_floors: dict | None,
) -> None:
    """The nightly submission calendar + weekly-form row for one scope.

    daily_hist is DAILY_LOG already scoped to `group_areas` (full history);
    area_floors maps each area to the first date it's accountable from (system
    start, or the transfer start for an area created/renamed at the latest
    transfer). A single-area scope draws the per-day status calendar; a
    zone/district draws the per-day % calendar.
    """
    render_section_label(t('Form Submission Compliance — {scope_value}', scope_value=scope_value))

    _sys_start = get_config_value("SYSTEM_START_DATE", "")
    _anchor    = compliance_anchor_date()
    _win_end   = _anchor.isoformat()
    _thirty    = (_anchor - timedelta(days=29)).isoformat()
    _win_start = max(_sys_start, _thirty) if _sys_start else _thirty
    _floors    = area_floors or {}
    _is_area   = (scope_kind == "Area")

    _cal = build_calendar_data(set(), _win_end, n_weeks=5, anchor_date=_anchor)
    _hdr = "".join(
        f'<th style="text-align:center;padding:4px 8px;color:#9ca3af;'
        f'font-size:0.72rem;font-weight:600;">{t(d)}</th>'
        # es.py has carried Lun/Mar/Mié since the weekday work; this header
        # simply never asked for them, so a Spanish calendar wore English
        # column names.
        for d in _COMPLIANCE_DAYS
    )

    # Per-day submission facts, scoped to this group.
    _dl = daily_hist.copy() if daily_hist is not None else pd.DataFrame()
    if not _dl.empty and {"Area", "Date"} <= set(_dl.columns):
        _dl["Area"] = _dl["Area"].astype(str).str.strip()
        _dl["Date"] = _dl["Date"].astype(str)
    else:
        _dl = pd.DataFrame(columns=["Area", "Date"])

    if _is_area:
        _area = scope_value
        _submitted = set(_dl["Date"])
        _floor = _floors.get(_area, _sys_start)
        _timing = get_nightly_submission_timing()
        if not _timing.empty and "area" in _timing.columns:
            _ta = _timing[_timing["area"].astype(str).str.strip() == _area]
            _ontime = set(_ta[_ta["on_time"]]["report_date"])
            _late   = set(_ta[~_ta["on_time"]]["report_date"])
        else:
            _ontime, _late = set(), set()
        _blitz = get_blitz_dates(area=_area)

        def _cell(cell):
            d = cell["date"]
            if cell["future"]:
                bg, fg = _C_UPCOMING; return bg, f'<span style="color:{fg};">{d[8:]}</span>', f"{d} — upcoming"
            if d < _floor:
                bg, fg = _C_UPCOMING; return bg, f'<span style="color:{fg};">{d[8:]}</span>', f"{d} — before tracking started"
            if cell["date"] in _blitz and d in _submitted:
                bg, fg = _C_BLITZ; return bg, f'<span style="color:{fg};font-weight:500;">{d[8:]}</span>', f"{d} — submitted, Blitz day"
            if d in _submitted:
                if d in _late and d not in _ontime:
                    bg, fg = _C_AMBER; return bg, f'<span style="color:{fg};font-weight:500;">{d[8:]}</span>', f"{d} — submitted late"
                bg, fg = _C_GREEN; return bg, f'<span style="color:{fg};font-weight:500;">{d[8:]}</span>', f"{d} — submitted on time"
            bg, fg = _C_RED; return bg, f'<span style="color:{fg};font-weight:500;">{d[8:]}</span>', f"{d} — not submitted"

        _legend = _compliance_legend([
            (_C_GREEN[0], t("On time")), (_C_AMBER[0], t("Late")),
            (_C_BLITZ[0], t("Blitz day")), (_C_RED[0], t("Missed")),
            (_C_UPCOMING[0], t("Upcoming / pre-tracking")),
        ])
        _summary = None
    else:
        _per_day = _dl.groupby("Date")["Area"].nunique().to_dict()

        def _accountable(day_iso: str) -> int:
            return sum(1 for a in group_areas if _floors.get(a, _sys_start) <= day_iso)

        _pcts = []

        def _cell(cell):
            d = cell["date"]
            if cell["future"]:
                bg, fg = _C_UPCOMING
                return bg, f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{d[8:]}</div>'\
                           f'<div style="font-size:0.8rem;">&nbsp;</div>', t("{date} — upcoming", date=d)
            if d < _win_start:
                bg, fg = _C_UPCOMING
                return bg, f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{d[8:]}</div>'\
                           f'<div style="font-size:0.8rem;">&nbsp;</div>', t("{date} — before tracking started", date=d)
            _acc = _accountable(d)
            if _acc == 0:
                bg, fg = _C_UPCOMING
                return bg, f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{d[8:]}</div>'\
                           f'<div style="font-size:0.8rem;">&nbsp;</div>', t("{date} — no areas yet", date=d)
            _n = _per_day.get(d, 0)
            _pct = round(_n / _acc * 100)
            _pcts.append(_pct)
            bg, fg = _pct_color(_pct)
            return bg, (f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{d[8:]}</div>'
                        f'<div style="font-size:0.8rem;font-weight:700;color:{fg};">{_pct}%</div>'), \
                   t("{date} — {n}/{total} areas submitted ({pct}%)",
                     date=d, n=_n, total=_acc, pct=_pct)

        _legend = _compliance_legend([
            (_C_GREEN[0], "&ge;85%"), (_C_AMBER[0], "70–84%"),
            (_C_RED[0], "&lt;70%"), (_C_UPCOMING[0], t("Upcoming / pre-tracking")),
        ])
        _summary = _pcts  # filled as cells render

    _body = ""
    for _week in _cal:
        _cells = ""
        for _c in _week:
            _bg, _inner, _title = _cell(_c)
            _cells += (
                f'<td title="{_title}" style="text-align:center;padding:5px 4px;'
                f'background:{_bg};border-radius:4px;vertical-align:middle;">{_inner}</td>'
            )
        _body += f"<tr>{_cells}</tr>"

    st.markdown(
        '<table style="width:100%;border-collapse:separate;border-spacing:3px;margin-bottom:0.5rem;">'
        f'<thead><tr>{_hdr}</tr></thead><tbody>{_body}</tbody></table>{_legend}',
        unsafe_allow_html=True,
    )

    if not _is_area and _summary:
        _avg = round(sum(_summary) / len(_summary))
        st.markdown(
            '<p style="color:#9ca3af;font-size:0.82rem;margin-top:0;">'
            + t("Each box is the share of {scope}'s {n} areas that turned in "
                "the nightly form that day. Window average: {avg}%.",
                scope=html.escape(str(scope_value)),
                n=f'<strong style="color:#f4f4f8;">{len(group_areas)}</strong>',
                avg=f'<strong style="color:#f4f4f8;">{_avg}</strong>')
            + '</p>',
            unsafe_allow_html=True,
        )

    # ── Weekly report submission — one Mon–Sun box per due week ────────────────
    render_section_label(t('Weekly Report Submission — {scope_value}', scope_value=scope_value))
    _wk_all    = get_weekly_submission_data()
    _wk_anchor = latest_due_sunday()
    _due_weeks = weekly_due_weeks(_sys_start, anchor_sunday=_wk_anchor, n_weeks=8)

    if not _due_weeks:
        st.info(t("No weekly reporting weeks are due yet."))
        return

    if not _wk_all.empty and "area" in _wk_all.columns:
        _wk = _wk_all.copy()
        _wk["area"] = _wk["area"].astype(str).str.strip()
        _wk = _wk[_wk["area"].isin(group_areas)]
    else:
        _wk = pd.DataFrame(columns=["area", "week_end_date"])

    _wk_cells, _wk_pcts = "", []
    for _w in _due_weeks:
        _wd = date.fromisoformat(_w)
        _lbl = f"{_wd.month}/{_wd.day}"
        if _is_area:
            _got = (not _wk.empty) and (_w in set(_wk["week_end_date"]))
            _bg, _fg = (_C_GREEN if _got else _C_RED)
            _title = "Submitted" if _got else "Not submitted"
            _inner = (f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1.2;">{_lbl}</div>'
                      f'<div style="font-size:0.8rem;font-weight:600;color:{_fg};">'
                      f'{"✓" if _got else "✕"}</div>')
        else:
            _acc = sum(1 for a in group_areas if _floors.get(a, _sys_start) <= _w)
            _n = _wk[_wk["week_end_date"] == _w]["area"].nunique() if not _wk.empty else 0
            _pct = round(_n / _acc * 100) if _acc else 0
            _wk_pcts.append(_pct)
            _bg, _fg = _pct_color(_pct) if _acc else _C_UPCOMING
            _title = (t("{n}/{total} areas submitted ({pct}%)", n=_n, total=_acc, pct=_pct)
                      if _acc else t("no areas yet"))
            _inner = (f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1.2;">{_lbl}</div>'
                      f'<div style="font-size:0.8rem;font-weight:700;color:{_fg};">{_pct}%</div>')
        _wk_cells += (
            f'<td title="{t("Week ending {date} — {title}", date=_w, title=_title)}" style="text-align:center;'
            f'padding:6px 8px;background:{_bg};border-radius:4px;vertical-align:middle;'
            f'min-width:52px;white-space:nowrap;">{_inner}</td>'
        )

    if _is_area:
        _wk_legend = _compliance_legend([(_C_GREEN[0], "Submitted"), (_C_RED[0], "Missed")])
    else:
        _wk_legend = _compliance_legend([
            (_C_GREEN[0], "&ge;85%"), (_C_AMBER[0], "70–84%"), (_C_RED[0], "&lt;70%"),
        ])

    st.markdown(
        '<table style="border-collapse:separate;border-spacing:3px;margin-bottom:0.5rem;">'
        f'<tbody><tr>{_wk_cells}</tr></tbody></table>{_wk_legend}'
        '<p style="color:#9ca3af;font-size:0.75rem;margin-top:0;">'
        + t("Each box is a Mon–Sun week, labeled by its ending Sunday. "
            "Submission is credited by the day the weekly form arrived, not "
            "the date typed inside it.")
        + '</p>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# AREA LINEAGE — badge on a merge/split successor, redirect marker on a
# retired parent. Both read AREA_LINEAGE via app.db.queries; see
# docs/superpowers/specs/2026-07-19-area-lineage-completion-design.md.
# ══════════════════════════════════════════════════════════════════════════════

def render_lineage_badge(area: str) -> None:
    """If `area` is a lineage successor within the last-2-transfers window,
    render a small 'Combined' badge. No-op otherwise."""
    lineage = get_lineage_for_successor(area)
    if not lineage:
        return
    if not is_within_last_transfers(lineage.get("Transfer_Date", ""), n=2):
        return
    old_areas = str(lineage.get("Old_Areas", "")).replace(";", " +")
    st.markdown(
        f'<div style="display:inline-block;background:rgba(79,179,184,0.15);'
        f'border:1px solid rgba(79,179,184,0.4);border-radius:20px;'
        f'padding:4px 12px;margin-bottom:10px;font-size:0.82rem;color:#4fb3b8;">'
        f'Combined — merged from {html.escape(old_areas)}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_lineage_marker(area: str, area_val_key: str) -> bool:
    """If `area` is a retired lineage parent, render the redirect card and
    return True (caller should stop — there's no data left under the old
    name to show). Returns False if `area` has no lineage record.

    `area_val_key` is the scope_selector session_state key to update so the
    redirect button re-selects the successor (e.g. 'bd_area_val')."""
    lineage = get_lineage_for_retired_parent(area)
    if not lineage:
        return False
    new_area = str(lineage.get("New_Area", "")).strip()
    applied_at = str(lineage.get("Applied_At", "")).strip()
    st.info(
        f"**{html.escape(area)}** was combined into **{html.escape(new_area)}**"
        + (f" on {html.escape(applied_at)}." if applied_at else ".")
        + " View its continuous history there."
    )
    if st.button(t('View {new_area}', new_area=new_area), key=f"lineage_redirect_{area}"):
        st.session_state[area_val_key] = new_area
        # Plain st.rerun() defaults to a full-app rerun even when called from
        # inside the caller's st.fragment — that would tear down and resend the
        # global CSS/header/sidebar (the exact unstyled-flash bug the fragment in
        # 04_Desgloses.py was built to prevent). scope="fragment" keeps this
        # redirect inside the fragment like every other selector change.
        st.rerun(scope="fragment")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESSION HEADER — where this scope stands, above the fold
# ══════════════════════════════════════════════════════════════════════════════
# The audit's D1: the top of this page answered "what happened" and never "where
# does this leave us". These four lines do, without scrolling.
#
# Baptisms lead because that is the outcome the mission is measured on (Zackary,
# 2026-09-03) — but a zone baptises two or three people a month, so a
# baptisms-only header would read "0 · sin cambio" most weeks and teach the
# reader to skip it. The two indicators that PRECEDE a baptism ride underneath,
# so a zone at zero still sees whether its pipeline is filling or emptying,
# which is the fact it can act on this week.
def _weeks_in(weekly: pd.DataFrame, start: date | None, end: date | None):
    """`weekly` rows whose week_end_date falls inside [start, end]."""
    if weekly is None or weekly.empty or "week_end_date" not in weekly.columns:
        return weekly if weekly is not None else pd.DataFrame()
    if start is None or end is None:
        return weekly
    return weekly[(weekly["week_end_date"] >= start.isoformat())
                  & (weekly["week_end_date"] <= end.isoformat())]


def _header_window(weekly: pd.DataFrame, p_start: date | None, p_end: date | None):
    """Which weeks the header describes, and whether it had to look outside the
    selected period to find them. Returns ``(rows, week_ends, fell_back)``.

    These three indicators are collected once a week, on Sunday, so a period can
    be perfectly valid and contain no weekly report at all — "This Month So Far"
    on the third of the month is this page's own DEFAULT view, and the first
    Sunday has not come. An empty header there would blank the page's most
    prominent block on most days of most months.

    So: the weeks inside the period when there are any, otherwise the most
    recent completed week ending on or before the period's end. The caller
    always prints WHICH week it is reading, and says so explicitly when it fell
    back — that is what makes this honest rather than a quiet substitution. The
    reader can see that the header and the cards below it describe different
    windows, and why.
    """
    if weekly is None or weekly.empty or "week_end_date" not in weekly.columns:
        return pd.DataFrame(), [], False
    inside = _weeks_in(weekly, p_start, p_end)
    if not inside.empty:
        return inside, sorted(set(inside["week_end_date"])), False
    if p_end is None:
        return pd.DataFrame(), [], False
    earlier = weekly[weekly["week_end_date"] <= p_end.isoformat()]
    if earlier.empty:
        return pd.DataFrame(), [], False
    latest = max(earlier["week_end_date"])
    return earlier[earlier["week_end_date"] == latest], [latest], True


def _metas_for_weeks(weekly: pd.DataFrame, week_ends: list,
                     metrics) -> tuple[dict, dict]:
    """What the companionships in this frame set themselves for `week_ends`.

    Returns ``({metric: summed meta}, {metric: areas that set one})`` — the two
    halves of the Key Indicator card's goal bar under decision 6, where the bar
    is the companionships' own ``ki_*_meta`` and leadership's transfer goal is
    the mark beside it (PLAN-2026-09-18-data-pages.md §1).

    A week's meta is written on the PREVIOUS week's form — "las metas que usted
    estableció durante la planificación semanal para la SEMANA SIGUIENTE"
    (WeeklyReportForm_ES.gs) — so the rows carrying the goals FOR these weeks
    are the ones ending seven days earlier. Reading them off the same rows as
    the results grades a week against the target set for the week after it,
    which is the bug get_ki_goals_for_week exists to avoid.

    The weeks are passed in rather than derived from the period's dates,
    because the scoreboard falls back to the latest complete week when the
    selected period holds no weekly report at all: computed off p_start/p_end
    that fallback week would have been graded against nothing.

    The basis counts DISTINCT AREAS, not rows. A multi-week window holds one
    row per area per week, so counting rows reported "78 areas set a goal" on a
    mission that has 43 — and fed that 78 to render_kpi_row as the goal's
    basis, which then reduced a 41-area total against a 78-area goal and
    produced a percentage of nothing (audit F8, in reverse).

    A metric nobody wrote a meta for is absent from both dicts rather than
    present as a zero: an area that left the goal blank committed to nothing,
    and a zero goal would draw a full bar for any result at all (§1.1).
    """
    if (weekly is None or weekly.empty or not week_ends
            or "week_end_date" not in weekly.columns):
        return {}, {}
    wanted = {(date.fromisoformat(str(w)) - timedelta(days=7)).isoformat()
              for w in week_ends}
    rows = weekly[weekly["week_end_date"].astype(str).isin(wanted)]
    if rows.empty:
        return {}, {}
    totals, basis = {}, {}
    for metric in metrics:
        col = goal_metric_key(metric)
        if not col or col not in rows.columns:
            continue
        values = pd.to_numeric(rows[col], errors="coerce").fillna(0)
        total = float(values.sum())
        if total > 0:
            totals[metric] = total
            basis[metric] = (int(rows.loc[values > 0, "area"].nunique())
                             if "area" in rows.columns else 0)
    return totals, basis


#: The most areas the per-area trend will draw a line for (plan step D4).
#: CCSM's districts hold two to four areas and the area view holds one; a zone
#: holds nine and the mission forty-five, and the audit measured what that looks
#: like — forty-five lines is forty-five answers to "which area", which is not
#: the question a zone leader brings to a trend. Above this the section stands
#: down and the drill-down's "Por área" tab is the per-area view.
_TREND_MAX_AREAS = 8

#: How many complete weeks the nightly rows' sparkline shows (plan step D3).
_NIGHT_SPARK_WEEKS = 8

#: The nightly metrics that stay above the fold — decision 9, listed in
#: PLAN-2026-09-18-data-pages.md §1.2 and kept in the order it argued them
#: rather than the form's. The other twelve are one tap away under "Ver todos",
#: in the same component, so this is a fold and not a cut.
#:
#: `member_referrals_received`, not the plan's `referrals_received`: that key is
#: Utah Provo's, and a metric with no DAILY_LOG column is skipped silently —
#: the same correction step C4 had to make on the Panel.
_NIGHT_SHORTLIST = (
    "contacts_made",
    "contacts_attempted",
    "friend_lessons",
    "lessons_member_present",
    "baptismal_invitations",
    "church_invites",
    "member_referrals_received",
    "baptismal_calendars",
)

#: The four headings the rest are grouped under (§1.2). The titles are
#: callables, not strings, because a module-level t() would freeze the language
#: at import and a mid-session switch would leave the old one on screen.
#:
#: QUESTIONS_CONFIG is live and this list is not, so a question added to the
#: nightly form after today lands in an "Otros" group rather than disappearing
#: from the page — the grouping is an editorial convenience, never a filter.
_NIGHT_GROUPS = (
    (lambda: t("Contacting"), (
        "contacts_attempted", "contacts_made", "meaningful_conversations",
        "new_people_found")),
    (lambda: t("Teaching"), (
        "roleplays", "friend_lessons", "pmf_lessons", "rc_lessons",
        "rc_lessons_mcp", "baptism_doctrine_lessons")),
    (lambda: t("Working with members"), (
        "member_contacts", "lessons_member_present", "references_asked",
        "member_referrals_received")),
    (lambda: t("Inviting"), (
        "friend_texts", "friend_calls", "bom_shared", "church_invites",
        "baptismal_invitations", "baptismal_calendars")),
)


def _scoreboard_window_line(week_ends: list, reporting: int, total: int,
                            fell_back: bool, kpi_period: str) -> str:
    """The Key Indicators scoreboard's right-hand line: which weeks it is
    reading, how much of the scope stands behind them, and — when the selected
    period holds no weekly report at all — that it fell back to the latest one.

    The three facts the retired progression header carried as its title and its
    footer (PLAN-2026-09-18-data-pages.md §5, D1). Pure, and the only place
    this page states the scoreboard's own window, so the heading and the cards
    under it can never name different weeks.

    Every string here is one the header already used, so the Spanish is the
    Spanish the page has been printing since the header was built.
    """
    if not week_ends:
        return ""
    last = fmt_day_month(date.fromisoformat(week_ends[-1]))
    parts = [t("week ending {d}", d=last) if len(week_ends) == 1
             else t("{n} weeks to {d}", n=fmt_int(len(week_ends)), d=last)]
    if total:
        parts.append(t("{n} of {m} areas filed a weekly report · {pct}%",
                       n=fmt_int(reporting), m=fmt_int(total),
                       pct=fmt_int(round(reporting / total * 100))))
    if fell_back:
        # Sentence case, on the same line as the rest: uppercased in the
        # header's title it ran to two shouted lines above the numbers.
        parts.append(t("{period} holds no weekly report yet",
                       period=t(kpi_period).lower()))
    return " · ".join(p for p in parts if p)


def _totals_axis_spec(title: str, top: float) -> dict:
    """The right-hand y-axis the group total and its twin ride on.

    Split out of the layout so a test can hand it to plotly and find out
    whether plotly accepts it. The first cut used `titlefont`, which this build
    rejects outright — "Invalid property ... Did you mean tickfont?" — and that
    took the whole trend chart down with a ValueError printed where the chart
    should have been. Nothing in the suite touched the trend layout, so only
    opening the page found it.
    """
    dtick = _nice_count_dtick(top)
    return dict(
        title=dict(text=title, font=dict(color="#f4f4f8", size=11)),
        overlaying="y", side="right", rangemode="tozero",
        range=[0, max(top * 1.1, dtick)], dtick=dtick,
        showgrid=False,
        tickfont=dict(color="#f4f4f8", size=10),
    )


def _bucketed_totals(frame, metric: str, is_weekly: bool, granularity: str):
    """Group-wide totals per bucket, oldest first, for the twin overlay.

    Returns a bare list of numbers with no dates attached, and that is the
    point: the overlay is aligned by bucket INDEX against the current period —
    day 1 against day 1, week 1 against week 1 — so the twin's own dates are
    not merely unnecessary, they would be actively wrong to plot.

    Buckets are built the same three ways the trend chart builds its own
    (weekly form, Mon-Sun weeks, or single days), because a twin bucketed by a
    different rule than the line it sits behind is not a comparison.
    """
    if frame is None or frame.empty or metric not in frame.columns:
        return []
    f = frame.copy()
    if is_weekly:
        if "week_end_date" not in f.columns:
            return []
        f["_b"] = f["week_end_date"]
    else:
        if "Date" not in f.columns:
            return []
        if granularity == "Weeks":
            d = pd.to_datetime(f["Date"], errors="coerce")
            f["_b"] = (d + pd.to_timedelta(6 - d.dt.weekday, unit="D")
                       ).dt.strftime("%Y-%m-%d")
        else:
            f["_b"] = f["Date"]
    f[metric] = pd.to_numeric(f[metric], errors="coerce")
    totals = f.groupby("_b")[metric].sum(min_count=1).sort_index()
    return [None if pd.isna(v) else float(v) for v in totals.values]


def render_group_breakdown(
    scope_kind: str,          # "Zone", "District" or "Area" — labels only
    scope_value: str,         # the selected zone/district/area name
    daily_hist: pd.DataFrame,  # full-history DAILY_LOG for the scope
    goals: dict | None,        # weekly goals for the cards, or None/empty if none found
    group_areas: set,          # MISSION_ORG's current area names for this scope
    snap_scope: pd.DataFrame | None = None,   # LIVE_SNAPSHOT rows for the scope
    area_floors: dict | None = None,  # {area: first date it's accountable from}
) -> None:
    """Breakdown across the areas inside one zone or district — or ONE area.

    Identical sections for all three levels (Carson, 2026-07-17: "make the
    district and Area pages look and function exactly like the zone") — only
    the scoping of the incoming frames differs, which is why this takes
    pre-filtered frames rather than doing its own lookup. The area level is
    just a group of one: a single bar, a single trend line.

    One Period picker drives every section: the Key Indicators cards, the metric
    picker's bar chart and trend, and the Teaching Pipeline funnel all cover
    exactly the chosen range. The funnel's "Taught" bar carries the only caveat —
    it's the one number sourced from the Tableau export rather than the mission's
    own reports, so its coverage depends on when that export was last scraped
    (guarded in section 4).

    `snap_scope` decides which metrics get a Key Indicators card; `goals`
    decides whether the cards carry targets — zone and district both roll up
    their areas' goals (get_zone_goals/get_district_goals), an area has its
    own directly; a group with no goal rows in GOALS_CONFIG still just shows
    plain totals. A second, fixed-violet bar shows the group's summed
    AREA_TYPE_EXPECTATIONS reference instead (get_group_weekly_expectation_
    totals over `group_areas`, computed inline here — not a `goals`-style
    parameter, since it's the same set-of-areas sum at every level including
    Area's set-of-one).
    """
    # A single area is a group of one: the per-area BAR would be one lone bar, so
    # it's skipped (Carson, 2026-07-17), and its trend's red-✕ miss markers show
    # by default instead of only when a legend line is isolated — there's just
    # the one line, nothing to isolate.
    _is_area = (scope_kind == "Area")

    # ── Period — drives every section below ───────────────────────────────────
    # ── The transfer windows this picker can offer ───────────────────────────
    # Resolved once, here, and handed to both bounds functions. A transfer
    # label the schedule cannot supply is REMOVED from the picker rather than
    # offered and left to resolve to nothing — an option that does nothing is
    # worse than an absent one.
    _transfers = transfer_period_bounds()
    _cur_tw = transfer_window(0)
    if _cur_tw:
        # The whole cycle's end, so an in-progress transfer scales its goal by
        # six weeks rather than by however much of it has run.
        _transfers["_this_transfer_full"] = _cur_tw["end"]
    _prev2 = transfer_window(2)
    if _prev2:
        _transfers["_transfer_before_last"] = (_prev2["start"], _prev2["end"])

    _periods = [
        _p for _p in _KPI_PERIODS
        if _p not in ("This Transfer So Far", "Last Transfer") or _p in _transfers
    ]
    # The transfer is the unit the mission plans in, so it is what the page
    # opens on (Zackary, 2026-09-03). Falls back to the running month on a
    # mission whose TRANSFER_SCHEDULE cannot yet name a cycle.
    _default_period = ("This Transfer So Far" if "This Transfer So Far" in _periods
                       else "This Month So Far")

    _p_col, _, _ = st.columns(3)
    with _p_col:
        # Defaults to the running month (Carson, 2026-07-17) — index only sets
        # the FIRST render; the widget's own state wins after that.
        kpi_period = st.selectbox(
            t("Period"), _periods,
            index=_periods.index(_default_period),
            # The VALUE stays the English key — _kpi_period_bounds, the twin
            # table and this widget's session state are all keyed on it. Only
            # the displayed label is translated, which is why es.py has had
            # these five strings since the compliance rankings work and this
            # picker rendered them in English anyway.
            format_func=lambda p: t(p),
            key="bd_kpi_period",
        )
    p_start, p_end, p_days = _kpi_period_bounds(kpi_period, mission_today(),
                                                transfers=_transfers)

    _hist = daily_hist if daily_hist is not None else pd.DataFrame()

    # ── Custom: two dates instead of a named window ──────────────────────────
    # Every other period answers a question the page already knows how to ask.
    # This one exists for the questions it does not — a blitz week, the stretch
    # since a companionship arrived, the run-up to a stake conference.
    _floor = _records_floor(_hist)
    if kpi_period == "Custom":
        _today = mission_today()
        _c1, _c2, _ = st.columns(3)
        with _c1:
            _from = st.date_input(
                t("From"), value=max(_floor, _today - timedelta(days=27)),
                min_value=_floor, max_value=_today, key="bd_kpi_from",
            )
        with _c2:
            _to = st.date_input(
                t("To"), value=_today,
                min_value=_floor, max_value=_today, key="bd_kpi_to",
            )
        # st.date_input returns a tuple in range mode and a bare date otherwise;
        # these are two single-date widgets, but normalise anyway so a Streamlit
        # version change cannot turn p_start into a one-tuple and break every
        # comparison below with a TypeError nobody would trace back to here.
        _from = _from[0] if isinstance(_from, (list, tuple)) else _from
        _to = _to[0] if isinstance(_to, (list, tuple)) else _to
        if _to < _from:
            # Backwards is a slip, not a request. Say so and use the day itself
            # rather than rendering every section empty and blaming the data.
            st.warning(t("The end date is before the start date — showing {d}.",
                         d=fmt_day_month(_from)))
            _to = _from
        p_start, p_end = _from, _to
        # A custom range IS its own full period: the reader chose both ends, so
        # there is no larger window it is partway through and no pace to grade
        # against. p_days is its true length, which is what scales the goal.
        p_days = (p_end - p_start).days + 1
    rows = _slice_to_window(_hist, p_start, p_end)
    has_rows = not rows.empty

    # ── The twin: the same-shaped window immediately before this one ──────────
    # Every comparison on this page — the cards' arrows, the trend's dimmed
    # overlay, the per-area bar's ghost — reads from this ONE slice, so they can
    # never disagree about which days "before" means. None when the period has
    # no honest twin (All Time), and empty when the twin predates the mission's
    # own records, which is a different fact and is reported differently.
    prior_bounds = _kpi_prior_bounds(kpi_period, p_start, p_end, mission_today(),
                                     floor=_floor, transfers=_transfers)
    if prior_bounds is None:
        pr_start, pr_end = None, None
        rows_prior = pd.DataFrame()
    else:
        pr_start, pr_end = prior_bounds
        rows_prior = _slice_to_window(_hist, pr_start, pr_end)
    has_prior = not rows_prior.empty

    span = (
        f"{rows['Date'].min()} → {rows['Date'].max()}" if has_rows and p_start is None
        else "—" if not has_rows
        else p_start.isoformat() if p_start == p_end
        else f"{p_start.isoformat()} → {p_end.isoformat()}"
    )
    # An in-progress period holds only part of its days, so a vs-goal delta on it
    # would call a zone 4 days into a 7-day week "-33%" when it's actually ahead
    # of pace. Judge against the goal only once the period is complete.
    in_progress = kpi_period in ("This Week", "This Month So Far",
                                 "This Transfer So Far")

    if not has_rows:
        st.info(
            t('No {scope_value} activity recorded for {kpi_period} — the sections below cover this period only.', scope_value=scope_value, kpi_period=t(kpi_period).lower())
        )

    # `effort` (CHOICE) and `exchanges` (YESNO) hold the form's own Spanish word
    # in DAILY_LOG — 'Todo', 'La mayor parte', 'TRUE'. get_daily_log() coerces
    # every metric column to a number, so those land here as a hard 0 that is
    # indistinguishable from a real measured zero: an area that answered "Todo"
    # every single night would render as having given no effort at all. Consult
    # QUESTIONS_CONFIG's Data_Type rather than inspecting values, exactly as
    # Puntajes, Informes, Traslados and get_weekly_actuals_for_area already do.
    # Defined out here because BOTH consumers below need it — the Daily Activity
    # grid (which takes its keys from LIVE_SNAPSHOT, where a3_buildLiveSnapshot
    # writes these two as 0 for the same reason) and the Metric picker.
    _non_numeric = non_numeric_metrics()

    # ── Period scaling, shared by BOTH card sections ──────────────────────────
    # Hoisted out of the nightly grid when the Key Indicators row was added
    # (PLAN §7.5): two card sections scaling a weekly goal to the same period by
    # two copies of the same arithmetic is how they drift apart.
    #
    # Goal scales with the period: the store holds one WEEKLY goal per area, so a
    # 31-day month is goal*31/7. All Time has no meaningful goal. The expectation
    # bar (Carson, 2026-07-24) rides the exact same _goal_factor — keeping one
    # scaling convention for both bars is what makes them comparable on one card.
    _goal_factor = (p_days / 7) if p_days else None

    # AGENT_CONFIG's GOAL_* rows: the per-area weekly targets the mission itself
    # set. Every one of them is a NIGHTLY metric, so this tier fires for the grid
    # below and never for the Key Indicators row. Read once per render.
    _per_area_goals = get_area_weekly_goals()

    # How much of the period has actually run, and when it ends. Both are None on
    # a completed period and on All Time, which is what turns the pace tick off:
    # there is no "should be here by now" for a period that is already over.
    if in_progress and p_start is not None and p_days:
        _elapsed_days = (p_end - p_start).days + 1
        _pace_factor = _elapsed_days / 7
        _period_end_full = p_start + timedelta(days=p_days - 1)
    else:
        _elapsed_days = None
        _pace_factor = None
        _period_end_full = None

    _vs = _twin_label(kpi_period)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. INDICADORES CLAVE — the scoreboard this page opens on
    # ══════════════════════════════════════════════════════════════════════════
    # PLAN-2026-09-18-data-pages.md §5, step D1. The page used to open on a
    # three-line header block — baptisms, friends with a baptismal date,
    # friends at sacrament — sitting directly above a row of seven cards that
    # already carried all three of those metrics (audit D1: two blocks, one
    # subject). The header is retired: its window and coverage are this
    # section's right-hand line, its captions are the ⓘ, and its three numbers
    # are three of the seven cards.
    #
    # DECISION 6 IS APPLIED HERE and it reverses what this page's goal bar has
    # meant. The bar is now the COMPANIONSHIPS' own meta — the ki_*_meta each
    # area wrote on the previous week's form, which is the number the Church's
    # own app shows them — and leadership's transfer goal is the violet MARK on
    # the same bar. Until this step the card drew the leadership goal while the
    # drill-down directly beneath it drew the meta, and the two disagreed by
    # design (PLAN STATUS, B3 note b). The Panel made the same flip at C1, so
    # the three places a Key Indicator's goal appears now all draw one quantity.
    _ki_keys_weekly = list(key_indicator_metrics())
    _ki_scope_param = {"Zone": "bd_zone", "District": "bd_district",
                       "Area": "bd_area"}.get(scope_kind)
    _ki_scope_params = {_ki_scope_param: scope_value} if _ki_scope_param else {}
    _ki_wk_all = get_weekly_form_data()
    if not _ki_wk_all.empty and "area" in _ki_wk_all.columns:
        _ki_wk_all = _scope_to_areas(_ki_wk_all, "area", group_areas)

    # ── Which weeks the scoreboard reads ──────────────────────────────────────
    # The weeks inside the selected period — or, when it holds no weekly report
    # at all, the latest complete one, said out loud in the heading's
    # right-hand line. That rule and its tests come from the retired header,
    # which existed largely because of it: these seven are collected once a
    # week, so "This Week" before Sunday and "This Month So Far" on the 3rd are
    # both periods with nothing in them, and they are two of this page's most
    # common views. Without the fallback the top of the page goes blank on most
    # days of most months.
    _ki_cur, _ki_week_ends, _ki_fell_back = _header_window(_ki_wk_all, p_start, p_end)
    if _ki_fell_back and _ki_week_ends:
        # A fallback on the current side against a period-accurate twin would
        # compare two windows chosen by different rules. When the scoreboard
        # falls back, its twin is the week before the one actually shown.
        _ki_earlier = _ki_wk_all[_ki_wk_all["week_end_date"] < _ki_week_ends[0]]
        _ki_prior = (_ki_earlier[_ki_earlier["week_end_date"]
                                 == max(_ki_earlier["week_end_date"])]
                     if not _ki_earlier.empty else pd.DataFrame())
    elif pr_start is not None and pr_end is not None:
        _ki_prior, _, _ = _header_window(_ki_wk_all, pr_start, pr_end)
    else:
        # All Time has no twin. The header handed its own None bounds straight
        # to _header_window, whose _weeks_in returns the WHOLE frame for them —
        # so All Time quietly compared itself against itself and every arrow
        # read flat. Guarded here rather than inside _header_window, which is
        # right to treat None as "unbounded" for the window it is choosing.
        _ki_prior = pd.DataFrame()

    _ki_value_basis = (int(_ki_cur["area"].nunique())
                       if not _ki_cur.empty and "area" in _ki_cur.columns else 0)
    _ki_prior_basis = (int(_ki_prior["area"].nunique())
                       if _ki_prior is not None and not _ki_prior.empty
                       and "area" in _ki_prior.columns else 0)

    # ── The sparkline: the scope's last six well-reported weeks ───────────────
    # Only weeks at least half the scope's areas filed, the same gate the Panel
    # applies (C1) and the same one the arrows below pass: a weekly total is a
    # sum over whoever submitted, so a week 2 areas reported and a week 20 did
    # are not two points on one line — drawn together they make a collapse out
    # of a reporting gap. The gate also keeps the week in progress out without
    # needing a second definition of "this week".
    _KI_SPARK_WEEKS = 6
    _ki_spark_min = max(1, round(len(group_areas) * REPORTING_MIN_SHARE))
    _ki_spark_weeks: list = []
    if (not _ki_wk_all.empty and "week_end_date" in _ki_wk_all.columns
            and "area" in _ki_wk_all.columns):
        _ki_week_filers = _ki_wk_all.groupby("week_end_date")["area"].nunique()
        _ki_spark_weeks = [str(w) for w, n in sorted(_ki_week_filers.items())
                           if n >= _ki_spark_min][-_KI_SPARK_WEEKS:]

    def _ki_spark(metric: str) -> list | None:
        """The metric's last six well-reported weeks for this scope, or None
        when there is too little history to draw a line."""
        if len(_ki_spark_weeks) < 2 or metric not in _ki_wk_all.columns:
            return None
        return [
            float(pd.to_numeric(
                _ki_wk_all.loc[_ki_wk_all["week_end_date"].astype(str) == _w, metric],
                errors="coerce").fillna(0).sum())
            for _w in _ki_spark_weeks
        ]

    def _ki_window(df, start, end):
        """`df` rows whose week_end_date falls in [start, end]."""
        if df is None or df.empty or start is None or end is None:
            return df if df is not None else pd.DataFrame()
        if "week_end_date" not in df.columns:
            return pd.DataFrame()
        return df[(df["week_end_date"] >= start.isoformat())
                  & (df["week_end_date"] <= end.isoformat())]

    if not _ki_wk_all.empty and not _ki_cur.empty:
        # ── Leadership's goal for the cycle this period sits in ───────────────
        # A transfer goal is a period TOTAL, and it enters as a WEEKLY figure
        # (total ÷ the cycle's real weeks) so that _goal_factor returns it to
        # whatever the selected period is worth: on "This Transfer So Far" that
        # multiplies straight back to the transfer total, on "This Week" it is
        # one week's share. The mark therefore always means "leadership's
        # target for the period on screen", whichever period that is.
        _ki_transfer_weekly: dict = {}
        _ki_transfer_note = ""
        _ki_transfer_basis = 0
        _ki_cycle = None
        for _c in transfer_cycles():
            if p_end is not None and _c["start"] <= p_end <= _c["end"]:
                _ki_cycle = _c
                break
            if p_start is not None and _c["start"] <= p_start <= _c["end"]:
                _ki_cycle = _c
        if _ki_cycle is not None:
            _cyc_weeks = max(1.0, transfer_year.weeks_in_cycle(
                _ki_cycle["start"], _ki_cycle["end"]))
            _cyc_totals = group_goal_totals(_ki_cycle["start"], group_areas)
            # Scoped, like the total above it: the count and the total
            # must cover the same areas or the card divides them by
            # different denominators.
            _ki_transfer_basis = areas_with_goals(_ki_cycle["start"],
                                                  group_areas)
            _ki_transfer_weekly = {k: v / _cyc_weeks for k, v in _cyc_totals.items() if v}
            if _ki_transfer_weekly:
                _ki_transfer_note = t(
                    "goal for {cycle}, spread over its {weeks} weeks",
                    cycle=str(_ki_cycle.get("number") or "").strip()
                    or fmt_day_month(_ki_cycle["start"]),
                    weeks=fmt_number(_cyc_weeks, 0))

        # The companionships' metas for the weeks ON SCREEN — the bar itself,
        # after decision 6.
        _ki_meta_total, _ki_meta_basis = _metas_for_weeks(
            _ki_wk_all, _ki_week_ends, _ki_keys_weekly)

        _ki_row_cards = []
        _ki_any_goal = False
        _ki_any_meta = False
        for _k in _ki_keys_weekly:
            if _k not in _ki_cur.columns:
                continue
            _v = int(pd.to_numeric(_ki_cur[_k], errors="coerce").fillna(0).sum())
            # The whole card opens the drill-down on this metric, and the link
            # carries the scope so the full reload it causes lands back here
            # (render_scope_selectors seeds from the same params).
            _c: dict = {"label": ki_short_label(_k), "value": _v,
                        "href": ki_href(_k, _ki_scope_params),
                        "spark": _ki_spark(_k)}

            # The basis is REPORTING AREAS, not days: a weekly indicator does
            # not grow with the days behind it, it grows with the companionships
            # that filed. The prior week must carry at least half as many of
            # them, or a week gets reconstructed by scaling one companionship up
            # to stand for eight.
            if (_ki_prior is not None and not _ki_prior.empty
                    and _k in _ki_prior.columns and _ki_prior_basis
                    and _ki_prior_basis >= max(1, _ki_value_basis * REPORTING_MIN_SHARE)):
                _pv = int(pd.to_numeric(_ki_prior[_k], errors="coerce").fillna(0).sum())
                _chg = period_delta(_v, _pv, current_basis=_ki_value_basis,
                                    prior_basis=_ki_prior_basis, min_basis=1)
                if _chg is not None:
                    _c["change"] = _chg
                    _c["delta_label"] = _vs

            # ── The bar: decision 6 ──────────────────────────────────────────
            # The companionships' meta first. Only when nobody in scope wrote
            # one for these weeks does the card fall through the rest of the
            # precedence chain — an entered GOALS_CONFIG goal, or leadership's
            # target scaled to the period, is still a target; it is just not
            # theirs, and the note says which one it is.
            _goal_total = _ki_meta_total.get(_k, 0.0)
            _goal_basis = _ki_meta_basis.get(_k, 0)
            _is_meta = _goal_total > 0 and _goal_basis > 0
            _goal_note = (t("the companionships' own goal — {n} areas set one",
                            n=fmt_int(_goal_basis)) if _is_meta else "")
            if not _is_meta:
                _wg, _goal_note, _b, _src = _resolve_group_goal(
                    _k, goals, _per_area_goals, len(group_areas),
                    transfer_weekly=_ki_transfer_weekly,
                    transfer_note=_ki_transfer_note,
                    transfer_basis=_ki_transfer_basis)
                if _goal_factor and _wg > 0:
                    _goal_total, _goal_basis = _wg * _goal_factor, _b

            if _goal_total > 0:
                _ki_any_goal = True
                _ki_any_meta = _ki_any_meta or _is_meta
                _c["goal"] = _goal_total
                if _goal_note:
                    _c["goal_note"] = _goal_note
                if _ki_value_basis and _goal_basis:
                    _c["value_basis"] = _ki_value_basis
                    _c["goal_basis"] = _goal_basis
                # The violet mark beside the amber bar: leadership's goal for
                # this period. Drawn only when the bar IS the metas — a card
                # whose bar is already the leadership goal would otherwise
                # carry two ticks saying one thing.
                _mark = (float(_ki_transfer_weekly.get(_k, 0) or 0)
                         * float(_goal_factor or 0))
                if _is_meta and _mark > 0:
                    _c["mark"] = _mark
                    _c["mark_label"] = t("Leadership goal for this period")
            # No pace tick on these seven: their values are weekly-form totals
            # over COMPLETE weeks, so there is no part-period to be partway
            # through — a week is either reported or it is not, and the bar
            # covers exactly the weeks the value does. The pace against
            # leadership's target is the drill-down's, which draws it as a tick
            # on the weekly bars (B2).
            _ki_row_cards.append(_c)

        # ── The heading: its window, its coverage, and its explanation ────────
        _ki_right = _scoreboard_window_line(
            _ki_week_ends, _ki_value_basis, len(group_areas),
            _ki_fell_back, kpi_period)

        # Why an arrow is missing, said once. C2's rule: the sentence reaches
        # the ⓘ (for the phone, which has no hover) AND the card's own chip.
        _ki_no_change_reason = ""
        if _ki_prior is None or _ki_prior.empty:
            _ki_no_change_reason = t(
                "No comparison: there is no earlier weekly report to measure "
                "these weeks against.")
        elif _ki_prior_basis < max(1, _ki_value_basis * REPORTING_MIN_SHARE):
            _ki_no_change_reason = t(
                "No comparison: {n} areas filed the earlier weekly report and "
                "at least {need} are needed at this scope.",
                n=fmt_int(_ki_prior_basis),
                need=fmt_int(max(1, round(_ki_value_basis * REPORTING_MIN_SHARE))))

        _ki_info = t(
            "The seven indicators the mission is judged on, from the weekly "
            "Sunday form. The bar is the goal the companionships set "
            "themselves on the previous week's form — the same number the "
            "Church's app shows them — and the violet mark is the goal "
            "leadership set on the Metas page, scaled to this period. Totals "
            "are compared per reporting area, because a week's total is a sum "
            "over whoever filed. Tap any card for that indicator's history.")
        if not _ki_any_goal:
            _ki_info += " " + t(
                "No goal set for this cambio yet — set one on the Metas page "
                "and these bars light up.")
        elif not _ki_any_meta or any("mark" not in _c and "goal" in _c
                                     for _c in _ki_row_cards):
            # Decision 6 reversed which way this falls: the bar is the
            # companionships' meta, and where none was written for these weeks
            # it is leadership's goal instead. The old sentence said the
            # opposite, which was true of this page until this step.
            _ki_info += " " + t(
                "Where no companionship wrote a meta for these weeks the bar "
                "is leadership's goal for the period instead, and carries no "
                "violet mark.")
        if _ki_no_change_reason:
            _ki_info += " " + _ki_no_change_reason

        render_section_label(
            t('Key Indicators — {scope_value}', scope_value=scope_value),
            emphasis=True, right=_ki_right, info=_ki_info)

        for _c in _ki_row_cards:
            # A refused comparison is the card's own chip, not a paragraph
            # under the row (C2) — and only where there was a number to have
            # compared.
            if (_ki_no_change_reason and _c.get("change") is None
                    and isinstance(_c.get("value"), (int, float))):
                _c["change_note"] = t("no comparison")
                _c["change_note_title"] = _ki_no_change_reason
        render_kpi_row(_ki_row_cards)

        # The drill-down under the cards — the same panel the Panel draws,
        # on this scope (PLAN-2026-09-18-data-pages.md §3 B3).
        render_ki_drilldown(scope_kind, scope_value, group_areas, key="bd_ki")


    # ══════════════════════════════════════════════════════════════════════════
    # 2. ACTIVIDAD DIARIA — the nightly metrics, as rows
    # ══════════════════════════════════════════════════════════════════════════
    # PLAN-2026-09-18-data-pages.md §5, step D3. Twenty KPI cards became twenty
    # ROWS, eight of them above the fold and the other twelve behind "Ver todos"
    # in four groups (decision 9, §1.2).
    #
    # Twenty cards is not a scoreboard, it is an inventory: at 1400px they ran
    # five rows deep and pushed everything below them off the page, and no
    # reader has twenty questions. The eight in the shortlist are the ones the
    # mission acts on nightly; the other twelve are still here, one tap away,
    # in the same component so nothing about them changes except how much of
    # the page they cost.
    #
    # Each row says the same five things the card did — what it is, how much,
    # which way it moved, how far toward the period's goal, and the shape of
    # the last eight weeks — in one line instead of a tile, and the projection
    # that used to sit under the bar rides on the row's hover.
    #
    # The VALUES come from DAILY_LOG, the only source with the per-day
    # granularity an arbitrary period needs. All four scopes get them;
    # `goals` decides whether they carry a target — zone and district both roll
    # up their areas' goals, an area has its own directly.
    if snap_scope is not None and not snap_scope.empty and has_rows:
        # Rates can't be summed across areas or days. LIVE_SNAPSHOT is built
        # from DAILY_LOG counts so it shouldn't carry any — guard regardless.
        _kpi_keys = [
            c[:-3] for c in snap_scope.columns
            if c.endswith("_7d")
            and not is_rate_metric(c[:-3])
            and c[:-3] not in _non_numeric
        ]
        _expectation_totals = get_group_weekly_expectation_totals(group_areas)

        # How many of the group's areas actually filed anything this period.
        # The denominator behind every row's VALUE, as against the goal's own.
        _value_basis = (int(rows["Area"].nunique())
                        if "Area" in rows.columns else 0)

        # ── What each side of the comparison rests on ─────────────────────────
        # A date counts as a day of data for THIS GROUP only when at least half
        # its areas filed that night — period_delta's mission-wide rule, scoped
        # down. Without it 2026-08-09, which holds one area's row out of 42,
        # would count as a whole day and inflate every twin it falls inside.
        _report_dates = reporting_dates(_hist, len(group_areas))
        _cur_days = days_in_window(_report_dates, p_start, p_end)
        _prior_days = days_in_window(_report_dates, pr_start, pr_end)

        _night_rows: dict = {}
        _night_any_goal = False
        for _key in _kpi_keys:
            if _key not in rows.columns:
                continue  # active metric with no DAILY_LOG column yet
            _val = int(pd.to_numeric(rows[_key], errors="coerce").fillna(0).sum())
            _row: dict = {"name": format_metric_label(_key), "value": _val}
            _details = []

            # The arrow means ONE thing on this page: movement against the twin.
            # It used to mean distance from goal on a completed period and
            # nothing at all on a running one, so the same glyph in the same
            # place answered two different questions depending on the date.
            if has_prior and _key in rows_prior.columns:
                _prior_val = int(
                    pd.to_numeric(rows_prior[_key], errors="coerce").fillna(0).sum())
                _change = period_delta(
                    _val, _prior_val,
                    current_basis=_cur_days, prior_basis=_prior_days)
                if _change is not None:
                    _row["change"], _row["change_color"] = change_text(_change)
                    _details.append(f"{_row['change']} {_vs}")

            # Nightly metrics only reach tiers 1 and 3 — AREA_TRANSFER_GOALS and
            # the ki_*_meta goals are both keyed on the seven Key Indicators, so
            # the two KI tiers are empty here by construction.
            _weekly_goal, _derived_note, _goal_basis, _goal_src = _resolve_group_goal(
                _key, goals, _per_area_goals, len(group_areas))
            if _goal_factor and _weekly_goal > 0:
                _night_any_goal = True
                _goal = _weekly_goal * _goal_factor
                # A running period is graded against where it should be TODAY,
                # not against a month's goal it has had three days to meet. Two
                # days into a thirty-day month a zone exactly on pace has 7% of
                # the month's target, and grading that 7% told it it was
                # failing. The bar still fills toward the full goal; the colour
                # comes from the gap against the pace.
                #
                # Audit F8 rides in the same call: the value is a total across
                # the areas that REPORTED and the goal a total across the areas
                # that HAVE one, so both are reduced to per-area rates first —
                # on 2026-08-21 a tile read 2.040% for want of exactly that.
                _pace = _weekly_goal * _pace_factor if _pace_factor is not None else None
                _state = goal_bar_state(
                    _val, _goal, pace=_pace,
                    value_basis=_value_basis or None,
                    goal_basis=_goal_basis or None)
                # The bar is % OF GOAL, not the raw value: these twenty metrics
                # run from 36 calendars to 7.792 contact attempts, and a bar
                # scaled to the largest would leave eighteen of them invisible.
                # Every row's bar therefore means one thing — how far into this
                # period's goal it is — and they are comparable down the column.
                _row["bar"] = _state["width"]
                _row["status"] = goal_bar_status(_state["grade_pct"])
                _row["sub"] = t("{pct}% of {goal}",
                                pct=fmt_int(_state["pct"]), goal=fmt_int(_goal))
                if _pace is not None:
                    _details.append(t("{pace} expected by today",
                                      pace=fmt_int(_pace)))
                    if _period_end_full is not None:
                        _details.append(t("full goal {goal} by {date}",
                                          goal=fmt_int(_goal),
                                          date=fmt_day_month(_period_end_full)))
                if _derived_note:
                    _details.append(_derived_note)

            # ── The last eight complete weeks, and where this is heading ─────
            # ONE pass over the history for both. The sparkline runs up to the
            # period's own end, so the line ends where the number beside it
            # does; the projection is fitted only on the weeks BEFORE the
            # period, because a fit that included the period it is projecting
            # would be predicting what it had already been told.
            _wk_values, _wk_dates = _completed_weekly_series(
                _hist, _key, (p_end or mission_today()) + timedelta(days=1))
            if _wk_values:
                _row["spark"] = _wk_values[-_NIGHT_SPARK_WEEKS:]
            if _elapsed_days is not None and p_days:
                _before = [(v, d) for v, d in zip(_wk_values, _wk_dates)
                           if p_start is None or d < p_start.isoformat()]
                _projection = _landing_estimate(
                    _val, _elapsed_days, p_days,
                    [v for v, _ in _before], [d for _, d in _before])
                # The projection is the one figure here describing something
                # that has not happened, so it stays off the row itself and
                # rides on its hover, where it cannot be read as a measurement
                # (plan step D3). projection_caption carries the tilde and the
                # "early estimate" hedge the cards have always printed.
                _proj_line = projection_caption(_projection, fmt_int)
                if _proj_line:
                    _details.append(_proj_line)
            # The AREA-TYPE expectation is a different thing from the goal and
            # only ever drew a bar when the two disagreed — which, with
            # GOALS_CONFIG empty, they never do. It keeps its place in the
            # row's details rather than a second bar nobody has yet seen.
            _weekly_expectation = float(_expectation_totals.get(_key, 0) or 0)
            if (_goal_factor and _weekly_expectation > 0
                    and round(_weekly_expectation) != round(_weekly_goal)):
                _details.append(t("expectation {n} this period",
                                  n=fmt_int(_weekly_expectation * _goal_factor)))

            _row["rank"] = ""   # a fixed list, not a ranking — see _NIGHT_GROUPS
            _row["title"] = " · ".join([_row["name"]] + [d for d in _details if d])
            # The row opens the same drill-down a Key Indicator card does; the
            # panel reads DAILY_LOG bucketed into weeks for a nightly metric
            # (ki_history.daily_series). The link carries the scope so the full
            # reload it causes lands back here.
            _row["href"] = ki_href(_key, _ki_scope_params)
            _night_rows[_key] = _row

        # ── The heading ──────────────────────────────────────────────────────
        _night_right_parts = [span]
        if _cur_days:
            _night_right_parts.append(
                t("{n} reporting days", n=fmt_int(_cur_days)))
        _night_info = t(
            "Everything the companionships report at night, for this period. "
            "The bar on each row is how far into the period's goal it is, so "
            "the rows are comparable down the column however different their "
            "sizes; its colour is graded against where the period should "
            "stand TODAY, not against the whole goal. The line under each name "
            "is its last eight complete weeks. Hover a row for what it is on "
            "track to land at.")
        if not _night_any_goal:
            _night_info += " " + t("No goals are set at this level, so the rows "
                                   "carry totals and no bars.")
        _night_info += " " + _comparison_note(kpi_period, pr_start, pr_end,
                                              _cur_days, _prior_days)
        render_section_label(
            t('Daily Activity — {scope_value}', scope_value=scope_value),
            right=" · ".join(p for p in _night_right_parts if p),
            info=_night_info)

        if not _night_rows:
            st.info(t('No snapshot metrics found for {scope_value}.',
                      scope_value=scope_value))
        else:
            # The eight the mission acts on nightly, in the plan's own order
            # (§1.2) rather than the form's — this is a shortlist, and the
            # order it was chosen in is the order it was argued in.
            _short = [_night_rows[k] for k in _NIGHT_SHORTLIST if k in _night_rows]
            st.markdown(ranked_list(_short, bar_max=100), unsafe_allow_html=True)

            _rest = [k for k in _night_rows if k not in _NIGHT_SHORTLIST]
            if _rest:
                with st.expander(t("See every nightly indicator"), expanded=False):
                    _grouped = set()
                    for _title, _keys in _NIGHT_GROUPS:
                        _in_group = [_night_rows[k] for k in _keys
                                     if k in _night_rows and k in _rest]
                        _grouped.update(_keys)
                        if not _in_group:
                            continue
                        render_section_label(_title())
                        st.markdown(ranked_list(_in_group, bar_max=100),
                                    unsafe_allow_html=True)
                    # A question added to the nightly form after this grouping
                    # was written belongs SOMEWHERE. QUESTIONS_CONFIG is live
                    # and this list is not, so anything unplaced lands here
                    # rather than vanishing from the page.
                    _ungrouped = [_night_rows[k] for k in _rest
                                  if k not in _grouped]
                    if _ungrouped:
                        render_section_label(t("Other"))
                        st.markdown(ranked_list(_ungrouped, bar_max=100),
                                    unsafe_allow_html=True)


    # ══════════════════════════════════════════════════════════════════════════
    # 3. THE TREND — one metric over the period, one line per area
    # ══════════════════════════════════════════════════════════════════════════
    # PLAN-2026-09-18-data-pages.md §5, step D4. Three things went here:
    #
    #   * **The Metric picker.** It drove a forty-five-bar chart and this
    #     trend. The drill-down's "Por área" tab is the per-area view now, for
    #     any metric, and every card and row on this page is a link into it —
    #     so the page has one metric selector instead of two, and it is the one
    #     the reader already taps.
    #   * **The forty-five-bar chart.** Forty-five bars sorted by value, each
    #     with a ghost bar and a change chip, is a ranking drawn as a picture;
    #     the drill-down's ranked rows say the same thing in a column that also
    #     reads on a phone, and they are links.
    #   * **"All Metrics", the area view's own bar of every question.** Step D3
    #     made it redundant: at area scope the nightly rows already list all
    #     twenty with goals, sparklines and links, and the seven Key Indicators
    #     sit above them. It was also a thirty-category Plotly bar chart with
    #     -45° labels, which no phone has ever rendered legibly.
    #
    # What is left is the one thing the drill-down does NOT show: several areas'
    # lines over the same days, where the question is which area moved and
    # when. That only reads with a handful of lines — at mission scope it was
    # forty-five, which is forty-five answers to a question nobody asked — so
    # it draws at district and area scope and stands down above that.
    _weekly_keys = _weekly_metrics()
    _weekly_wk_all = get_weekly_form_data()
    if not _weekly_wk_all.empty:
        _weekly_wk_all = _scope_to_areas(_weekly_wk_all, "area", group_areas).rename(columns={"area": "Area"})
    # Per-metric, not one shared flag: a group can have baptisms but never
    # logged a friend with a baptismal date, or vice versa.
    _weekly_has = {
        k: (not _weekly_wk_all.empty and k in _weekly_wk_all.columns
            and _weekly_wk_all[k].notna().any())
        for k in _weekly_keys
    }

    def _weekly_slice(start, end):
        """The weekly frame cut to [start, end] on week_end_date."""
        if _weekly_wk_all.empty or start is None or end is None:
            return _weekly_wk_all
        return _weekly_wk_all[
            (_weekly_wk_all["week_end_date"] >= start.isoformat())
            & (_weekly_wk_all["week_end_date"] <= end.isoformat())
        ]

    _weekly_wk = _weekly_wk_all
    if any(_weekly_has.values()) and p_start is not None:
        _weekly_wk = _weekly_slice(p_start, p_end)
    # The twin, on the same source, so a weekly metric's overlay comes from the
    # weekly form and a nightly one's from DAILY_LOG — never a mix.
    _weekly_wk_prior = (_weekly_slice(pr_start, pr_end)
                        if pr_start is not None else pd.DataFrame())

    def _pipeline() -> None:
        """The teaching pipeline, called from every path out of the section
        below. The trend returns early in three states — no metrics, too many
        areas to draw a line each, no weekly form yet this period — and each
        of those returns used to carry its own copy of this call's nine
        arguments, which is three places for them to drift apart.
        """
        _render_teaching_pipeline(
            scope_value=scope_value, kpi_period=kpi_period,
            p_start=p_start, p_end=p_end, in_progress=in_progress, span=span,
            rows=rows, weekly_wk=_weekly_wk, group_areas=group_areas,
            weekly_prior=_weekly_wk_prior, twin_label=_vs)

    _catalog = metric_options()

    # ── Which metric the trend draws ─────────────────────────────────────────
    # The one the drill-down is open on, so a tapped card or row changes both
    # at once and the page never shows two different metrics as its subject.
    # With nothing open it falls to the mission's first Key Indicator, which is
    # also the first card on the page.
    #
    # `effort` and `exchanges` can never be it: they hold the form's own
    # Spanish words in DAILY_LOG ('Todo', 'TRUE') and get_daily_log() coerces
    # every metric column to a number, so a chart of either would be built from
    # zeros that look exactly like measured ones.
    _trend_pool = [k for k in _catalog
                   if not is_rate_metric(k) and k not in _non_numeric and (
                       (has_rows and k in rows.columns)
                       or (k in _weekly_keys and _weekly_has.get(k, False)))]
    if not _trend_pool:
        if has_rows or any(_weekly_has.values()):
            st.info(t("No daily-log metrics available for this group yet."))
        _pipeline()
        return

    _open_ki = selected_ki()
    metric = (_open_ki if _open_ki in _trend_pool
              else next((k for k in _ki_keys_weekly if k in _trend_pool),
                        _trend_pool[0]))
    m_label = _catalog.get(metric, metric)
    _is_weekly = metric in _weekly_keys

    # A trend of forty-five lines is not a trend, it is a thicket; the audit's
    # own count at mission scope. Districts hold two to four areas and the area
    # view holds one, which is what this chart was always for.
    if len(group_areas) > _TREND_MAX_AREAS:
        _pipeline()
        return

    if _is_weekly and _weekly_wk.empty:
        # A real gap, not a bug: no Sunday form has landed yet for this period
        # (e.g. "This Week" before Sunday). Skip the trend rather than drawing
        # a chart with nothing in it — the Teaching Pipeline still renders,
        # because two of its stages come from the nightly log.
        st.info(
            t("No weekly form submitted yet for {period} — {metric} reports "
              "once a week, on Sunday.",
              period=t(kpi_period).lower(), metric=m_label)
        )
        _pipeline()
        return

    # One style per area. Keyed by NAME off the group's sorted roster, never by
    # position in a chart, so an area wears the same colour however the lines
    # are ordered.
    _ordered_areas = sorted(group_areas)
    _style_of = {str(a): series_style(_i) for _i, a in enumerate(_ordered_areas)}
    _fallback = series_style(0)

    render_section_label(
        t('{m_label} Trend — {scope_value}', m_label=m_label,
          scope_value=scope_value),
        right=t('{n} areas · {span}', n=fmt_int(len(group_areas)), span=span),
        info=t("The metric the drill-down above is open on, day by day for "
               "each area in this scope. It draws at district and area "
               "scope only: a line per area is a way of asking which area "
               "moved and when, and forty-five of them answer nobody. Tap "
               "any card or row on this page to change the metric."))

    # A plain Streamlit button, not a chart control: a click just reruns the
    # script, and the trend below is rebuilt fresh every rerun anyway (fixed
    # axes, every line visible, new component each time) — so "rerun" already
    # IS "reset". Needs no on_click handler and, being a real st.button rather
    # than HTML drawn inside the chart's iframe, it matches the rest of the
    # app's buttons for free instead of carrying its own CSS.
    st.button(t("Reset Graph ↻"), key="bd_trend_reset")

    # A bucket only counts as missable once its day has passed the nightly
    # cutoff — the current day isn't held against anyone until 9:30 PM MT
    # (compliance_anchor_date, the same anchor the compliance calendars use),
    # and Agent3 only writes yesterday's rows at 6 AM anyway.
    _anchor_iso = compliance_anchor_date().isoformat()
    # Weekly-form buckets use their own anchor: a week's Sunday form is only
    # "due" once the week has ended (latest_due_sunday, the same anchor the
    # weekly compliance pills use), so the in-progress week never reads as a
    # miss.
    _wk_due_iso = latest_due_sunday().isoformat()

    # ── X-axis granularity — Days or Weeks ─────────────────────────────────
    # Weekly-form metrics (gate/date_metric/pew/renew) only ever exist as one
    # row per area per week — there's no daily grain to offer, so the toggle
    # below is skipped for them and they stay on Weeks. For a DAILY_LOG metric
    # the toggle is real: "Weeks" reuses the mission's Mon–Sun bucketing
    # (previously only forced on for "All Time", now available on any
    # period), "Days" plots one dot per report. Read from session_state
    # BEFORE the widget itself is instantiated so the control can be drawn
    # AFTER the chart (Carson: he wants it underneath) while still driving
    # this same build — the widget's own render further down reuses this key,
    # so the two stay in sync.
    _GRAN_OPTIONS = ["Days", "Weeks"]
    _gran_key = "bd_trend_granularity"
    _default_gran = "Weeks" if kpi_period == "All Time" else "Days"
    granularity = (
        "Weeks" if _is_weekly
        else st.session_state.get(_gran_key, _default_gran)
    )

    if _is_weekly:
        # Already one row per area per WEEK (week_end_date) — no daily
        # bucketing needed. Missed-form bridges ARE built (see below): a
        # submitted form with nothing to report records a 0, so a week with no
        # row is a missed Sunday form, not a zero.
        _t = _weekly_wk.copy()
        _t["_bucket"] = _t["week_end_date"]
        _x_title = t("Week Ending")
    else:
        _t = rows.copy()
        _t["Area"] = _t["Area"].astype(str).str.strip()  # match group_areas' names
        if granularity == "Weeks":
            # Bucket into the mission's Mon–Sun weeks, labelled by their
            # ending Sunday (same convention as WEEKLY_KI's week_end_date).
            # The still-in-progress week is dropped: it only holds part of
            # its days, so its dot always read as a dip.
            _d = pd.to_datetime(_t["Date"], errors="coerce")
            _t["_bucket"] = (
                _d + pd.to_timedelta(6 - _d.dt.weekday, unit="D")
            ).dt.strftime("%Y-%m-%d")
            _t = _t[_t["_bucket"] <= _anchor_iso]
            _x_title = t("Week Ending")
        else:
            _t["_bucket"] = _t["Date"]
            _x_title = t("Date")

    if _t.empty:
        st.info(t("No area data for the trend chart."))
    else:
        # The x-axis is EVERY bucket in the period, not just the ones that have
        # data. Feeding each trace only its own dates broke the chart two ways
        # on a category axis: plotly orders categories by first appearance
        # across traces, so a bucket the first-drawn area missed rendered out
        # of order at the END of the axis (lines zigzagged backwards through
        # time); and a missed bucket was bridged by the line as if data existed.
        if _is_weekly:
            # EVERY Sunday in the period, not just the weeks somebody
            # submitted: a week the whole group missed must still hold a slot
            # (its ✕s land there), and a lone submitted week between misses
            # was floating as a disconnected dot with nothing explaining the
            # gaps around it. Capped at the last DUE Sunday so the in-progress
            # week doesn't add an empty trailing slot; the union puts back any
            # early submission for a week not yet due.
            if p_start is not None:
                _wk_lo, _wk_hi = p_start.isoformat(), min(p_end.isoformat(), _wk_due_iso)
            else:
                _wk_lo, _wk_hi = _t["_bucket"].dropna().min(), _wk_due_iso
            _buckets = (
                pd.date_range(_wk_lo, _wk_hi, freq="W-SUN")
                .strftime("%Y-%m-%d").tolist()
                if _wk_lo <= _wk_hi else []
            )
            _buckets = sorted(set(_buckets) | set(_t["_bucket"].dropna()))
        elif granularity == "Weeks":
            # Same "every bucket, not just the ones with data" rule as the
            # weekly-form branch above. Weeks is now pickable on any period,
            # not just All Time, so bound by the period when one exists;
            # All Time has no p_start, so fall back to the data's own span.
            if p_start is not None:
                _p0 = pd.Timestamp(p_start)
                _wk_lo = (_p0 + pd.Timedelta(days=6 - _p0.weekday())).strftime("%Y-%m-%d")
                _wk_hi = min(p_end.isoformat(), _anchor_iso)
                _buckets = (
                    pd.date_range(_wk_lo, _wk_hi, freq="W-SUN")
                    .strftime("%Y-%m-%d").tolist()
                    if _wk_lo <= _wk_hi else []
                )
            else:
                _buckets = (
                    pd.date_range(_t["_bucket"].min(), _t["_bucket"].max(), freq="7D")
                    .strftime("%Y-%m-%d").tolist()
                    if not _t["_bucket"].dropna().empty else []
                )
            _buckets = sorted(set(_buckets) | set(_t["_bucket"].dropna()))
        else:
            # Days, on any period — All Time has no p_start, so fall back to
            # the data's own first/last report date the same way Weeks does.
            if p_start is not None:
                _range_end = min(p_end.isoformat(), _anchor_iso)
                _buckets = (
                    pd.date_range(p_start.isoformat(), _range_end)
                    .strftime("%Y-%m-%d").tolist()
                    if p_start.isoformat() <= _range_end else []
                )
            else:
                _dropped = _t["_bucket"].dropna()
                _d_lo = _dropped.min() if not _dropped.empty else None
                _d_hi = min(_dropped.max(), _anchor_iso) if _d_lo is not None else None
                _buckets = (
                    pd.date_range(_d_lo, _d_hi).strftime("%Y-%m-%d").tolist()
                    if _d_lo is not None and _d_lo <= _d_hi else []
                )
            _buckets = sorted(set(_buckets) | set(_t["_bucket"].dropna()))

        # One column per roster area over the full axis; NaN = no nightly report
        # that bucket (or, for gate, no data in this window). Reindexing to the
        # whole roster means an area with nothing in the period still shows —
        # as a blank line, not silence.
        pivot = (
            _t.groupby(["_bucket", "Area"])[metric].sum()
            .unstack("Area")
            .reindex(index=_buckets, columns=sorted(group_areas))
        )

        # Fixed y-axis, computed from EVERY area regardless of which ones end up
        # visible. Isolating one area via the legend only flips `visible` on its
        # traces (see _LEGEND_ISOLATE_JS) — with the axis left on Plotly's
        # default autorange, that made it re-fit to just the isolated area's own
        # max on every click, so the same number sat at a different height each
        # time (Carson: "confusing"). A step under 1 person is nonsensical for a
        # headcount metric, so the tick spacing is floored at 1 (_nice_count_dtick).
        _y_max = pivot.max(numeric_only=True).max()
        _y_max = 0.0 if pd.isna(_y_max) else float(_y_max)
        _y_dtick = _nice_count_dtick(_y_max)
        _y_top = max(_y_max * 1.1, _y_dtick)

        fig_trend = go.Figure()
        for _i, _area in enumerate(pivot.columns):
            _vals = pivot[_area]
            fig_trend.add_trace(go.Scatter(
                x=_buckets,
                # None (not NaN) so a missed bucket gets no dot and breaks the
                # line — plotly's default connectgaps=False does the rest.
                y=[None if pd.isna(v) else v for v in _vals],
                mode="lines+markers",
                name=str(_area),
                legendgroup=str(_area),
                # Same style map as the bar chart above — this area's colour is
                # its own, not a function of where it landed in either chart.
                # Past the 8th area the dash is what separates two lines that
                # share a hue; colour used to just wrap round and duplicate.
                line=dict(
                    color=_style_of.get(str(_area), _fallback)[0],
                    dash=_style_of.get(str(_area), _fallback)[1],
                    width=2,
                ),
                marker=dict(size=6, color=_style_of.get(str(_area), _fallback)[0]),
                # The y-axis is pinned at 0, so a dot ON zero sits exactly on
                # the plot edge and gets sliced to a half circle by default.
                # cliponaxis lets the marker draw whole over the axis line.
                cliponaxis=False,
            ))
            # Missed-report bridge, shown ONLY while this area is isolated via
            # the legend (visible=False here; _LEGEND_ISOLATE_JS flips it on by
            # its meta='bridge' tag). A bucket counts as missed when it has no
            # report — a nightly-report gap for daily metrics, an unsubmitted
            # Sunday form for weekly ones (a submitted form with nothing to
            # report records a 0, so a missing week IS a miss) — from the
            # area's accountability floor (an area created/renamed at the
            # latest transfer isn't blamed for weeks before it existed) up to
            # the source's own anchor: the nightly cutoff for daily buckets,
            # the last due Sunday for weekly ones.
            #
            # On the all-areas view a miss stays a clean gap (Carson: the main
            # page mustn't be jumbled with every area's ✕s at once). Isolated,
            # the gap is traced instead of disappearing: a dotted red line
            # bridging the neighbouring real dots with a red ✕ at each missed
            # bucket, heights interpolated between those dots (flat off the
            # ends; baseline 0 only if the area never reported at all), so the
            # ✕s ride the line's path rather than piling on the axis.
            _floor = (area_floors or {}).get(str(_area), "")
            _miss_cap = _wk_due_iso if _is_weekly else _anchor_iso
            _missed = [
                b for b in _buckets
                if pd.isna(_vals[b]) and b >= _floor and b <= _miss_cap
            ]
            if not _missed:
                continue
            _interp = (
                pd.to_numeric(_vals, errors="coerce")
                .interpolate(method="linear", limit_direction="both")
                .fillna(0.0)
            )
            # One None-separated segment per RUN of consecutive missed buckets,
            # each anchored on the real dot either side (when one exists) so
            # the bridge visually joins the line it stands in for.
            _missed_set = set(_missed)
            _runs, _run = [], []
            for b in _buckets:
                if b in _missed_set:
                    _run.append(b)
                elif _run:
                    _runs.append(_run)
                    _run = []
            if _run:
                _runs.append(_run)
            _bidx = {b: j for j, b in enumerate(_buckets)}
            _bx, _by = [], []
            for _r in _runs:
                _lo, _hi = _bidx[_r[0]] - 1, _bidx[_r[-1]] + 1
                seg = (
                    ([_buckets[_lo]] if _lo >= 0
                     and not pd.isna(_vals[_buckets[_lo]]) else [])
                    + _r
                    + ([_buckets[_hi]] if _hi < len(_buckets)
                       and not pd.isna(_vals[_buckets[_hi]]) else [])
                )
                if _bx:
                    _bx.append(None)
                    _by.append(None)
                _bx.extend(seg)
                _by.extend(float(_interp[b]) for b in seg)
            fig_trend.add_trace(go.Scatter(
                # The bridge's path — hover comes from the ✕ trace below, so a
                # real bucket this segment merely anchors on never claims "no
                # report" in the unified hover.
                x=_bx,
                y=_by,
                mode="lines",
                line=dict(color="#ef4444", width=1.5, dash="dot"),
                name=str(_area),
                legendgroup=str(_area),
                showlegend=False,
                # 'legendonly' = hidden (showlegend=False keeps it out of the
                # legend too). NOT visible=False: that crashes this plotly.js
                # build at render ("Cannot read properties of undefined") and
                # silently kills the legend.
                visible=(True if _is_area else "legendonly"),
                meta="bridge",
                hoverinfo="skip",
            ))
            fig_trend.add_trace(go.Scatter(
                x=_missed,
                y=[float(_interp[b]) for b in _missed],
                mode="markers",
                name=str(_area),
                legendgroup=str(_area),
                showlegend=False,
                # 'legendonly' = hidden (showlegend=False keeps it out of the
                # legend too). NOT visible=False: that crashes this plotly.js
                # build at render ("Cannot read properties of undefined") and
                # silently kills the legend.
                visible=(True if _is_area else "legendonly"),
                meta="bridge",
                marker=dict(symbol="x", size=8, color="#ef4444", opacity=0.9),
                # Same edge-clipping fix as the line markers: an ✕ at 0 would
                # otherwise render as its top half only.
                cliponaxis=False,
                hovertemplate=("no weekly form" if metric in _weekly_keys
                               else "no weekly total" if _is_weekly else "no report")
                              + "<extra>" + str(_area) + "</extra>",
            ))

        # ── The group's own line, and the twin behind it (audit C2) ──────────
        # Fifteen area lines answer "which area", never "is the zone up". The
        # bold total answers the second question, and the dimmed twin behind it
        # answers "compared to when".
        #
        # The twin is aligned by BUCKET INDEX, not by date: day 1 of this period
        # against day 1 of the one before, week 1 against week 1. Plotted on
        # absolute dates the twin would sit in its own stretch of the axis,
        # beside the current line rather than behind it, and the eye would have
        # to travel to make the comparison the chart exists to make.
        _y2 = None
        _totals = pivot.sum(axis=1, min_count=1)
        _has_total = int(_totals.notna().sum()) > 1
        if _has_total and not _is_area:
            _prior_frame = _weekly_wk_prior if _is_weekly else rows_prior
            _prior_totals = _bucketed_totals(
                _prior_frame, metric, _is_weekly, granularity)
            # Both ride a SECOND y-axis on the right. Forty-three areas summed
            # is an order of magnitude above any one of them — on the shared
            # axis the total topped 1.000 while the tallest area line sat at
            # 316, and all forty-three were pressed into the bottom eighth of
            # the plot (seen live 2026-09-03). They are also different
            # quantities: "how much did Huequen do" and "how much did the
            # mission do" are not two readings of one scale. The twin shares
            # the total's axis because the twin is a total.
            if _prior_totals:
                # Truncated to the shorter of the two: a twin one bucket longer
                # would draw a point with nothing to compare it against.
                _n = min(len(_buckets), len(_prior_totals))
                fig_trend.add_trace(go.Scatter(
                    x=_buckets[:_n],
                    y=_prior_totals[:_n],
                    mode="lines",
                    name=_twin_label(kpi_period),
                    yaxis="y2",
                    line=dict(color="rgba(203,203,210,0.45)", width=2, dash="dot"),
                    hovertemplate="%{y:.0f}<extra>"
                                  + html.escape(_twin_label(kpi_period))
                                  + "</extra>",
                    cliponaxis=False,
                ))
            fig_trend.add_trace(go.Scatter(
                x=_buckets,
                y=[None if pd.isna(v) else float(v) for v in _totals],
                mode="lines",
                name=t("{scope_value} total", scope_value=scope_value),
                yaxis="y2",
                line=dict(color="#f4f4f8", width=3),
                hovertemplate="%{y:.0f}<extra>" + t("total") + "</extra>",
                cliponaxis=False,
            ))
            # Both total lines share one range, or the comparison between them
            # — the only reason either is drawn — would be a lie told with two
            # scales.
            _t_max = float(_totals.max()) if _totals.notna().any() else 0.0
            _pt = [v for v in _prior_totals if v is not None]
            _t_max = max([_t_max] + _pt) if _pt else _t_max
            _y2 = _totals_axis_spec(
                t("{scope_value} total", scope_value=scope_value), _t_max)

        # ── Expectation reference line(s) ─────────────────────────────────────
        # A light-grey horizontal line at each area's expectation pace for the
        # selected metric, so you can see at a glance whether an area is hitting
        # the bar or sitting under it. ANY metric with an expectation defined in
        # Goals > Area Expectation Settings draws one (Carson, 2026-07-18:
        # adding a new expectation there must put a line here the moment that
        # metric is picked) — not a fixed metric list; a metric with no (or a
        # zero) expectation simply has no line to draw. An expectation can be
        # weekly OR monthly (per-indicator cadence); either way the line sits at
        # the pace matching the chart's buckets — the weekly pace, or /7 on
        # daily buckets — while the label keeps the stored figure ("1/mo" stays
        # 1/mo even though its line sits at ≈0.23/wk; get_area_expectation_entry
        # keeps that pace a float, since int-rounding it would collapse a
        # monthly 1 to no line at all). A group view can mix categories, so each
        # DISTINCT pace among its areas gets its own line, labeled by the
        # category(ies) that produced it — custom categories and exact-area
        # overrides included (resolve_area_category_label, which
        # get_area_language_group couldn't cover). add_hline shapes aren't
        # traces, so the isolate-legend JS leaves them alone and they stay put.
        if group_areas:
            _bucket_is_week = granularity == "Weeks"
            _paces = _expectation_paces(group_areas, metric)
            _multi_line = len(_paces) > 1
            _exp_heights = []
            for _p in sorted(_paces):
                _e, _cats = _paces[_p]
                _h = _p if _bucket_is_week else _p / 7.0
                _exp_heights.append(_h)
                _prefix = _expectation_prefix(_cats, _multi_line)
                _num = _expectation_rate(_e)
                # A monthly pace can be well under 0.1/day — two decimals
                # there so the label doesn't read "≈0.0/day".
                _pace_fmt = f"{_h:.2f}" if _h < 0.1 else f"{_h:.1f}"
                if _bucket_is_week:
                    _lbl = (f"{_prefix} {_num}" if _e["cadence"] == "weekly"
                            else f"{_prefix} {_num} (≈{_pace_fmt}/wk)")
                else:
                    _lbl = f"{_prefix} {_num} (≈{_pace_fmt}/day)"
                fig_trend.add_hline(
                    y=_h,
                    line=_EXP_LINE_STYLE,
                    annotation_text=_lbl,
                    annotation_position="top left",
                    annotation=dict(_EXP_ANNOTATION),
                )
            # A fixed y-axis won't autorange to include a shape, so lift the top
            # (and recompute the tick step) when the tallest expectation sits
            # above every area's data — otherwise the line clips off the chart.
            if _exp_heights:
                _exp_top = max(_exp_heights)
                if _exp_top * 1.1 > _y_top:
                    _y_top = _exp_top * 1.1
                    _y_dtick = _nice_count_dtick(max(_y_max, _exp_top))

        fig_trend.update_layout(
            # No in-chart title — see the bar chart above.
            xaxis_title=_x_title,
            # Bucket labels are categories, not timestamps; ISO dates sort
            # lexicographically = chronologically, so pin the order rather than
            # trusting first-appearance order across traces.
            xaxis=dict(type="category", categoryorder="category ascending"),
            # Fixed range + autorange=False so a legend click (which only
            # toggles trace visibility, not this layout) can never re-fit the
            # axis to whichever area is currently isolated. dtick is floored at
            # a whole person/lesson/baptism — see _nice_count_dtick.
            yaxis=dict(
                title=m_label,
                range=[0, _y_top],
                autorange=False,
                rangemode="tozero",
                dtick=_y_dtick,
                tick0=0,
            ),
            hovermode="x unified",
            # Legend below the plot: one trace per area, so a big zone wraps it
            # onto several rows, which grow down into the margin instead of up
            # into the chart.
            #
            # Isolating is done by _isolating_trend_chart's own click handler, so
            # Plotly's built-in click/double-click behaviour is switched off here
            # to keep it from fighting that handler.
            legend=dict(
                orientation="h", yanchor="top", y=-0.25, xanchor="left", x=0,
                itemclick=False, itemdoubleclick=False,
            ),
            # r=20 fitted a chart with nothing on its right edge. The totals'
            # axis lives there now and its tick labels need room.
            margin=dict(t=30, b=50, l=50, r=(60 if _y2 else 20)),
        )
        if _y2:
            fig_trend.update_layout(yaxis2=_y2)
        _isolating_trend_chart(fig_trend, enable_isolate=not _is_area)

        # X-axis granularity toggle, drawn UNDER the chart it controls
        # (Carson). Skipped for weekly-form metrics — there's no daily grain
        # to switch to. Reuses _gran_key so this render lines up with the
        # session_state read at the top of this section that already shaped
        # the chart above; `index` only seeds the value the first time this
        # key is ever created, same convention as the Period/Metric pickers.
        if not _is_weekly:
            _g_col, _, _ = st.columns(3)
            with _g_col:
                st.selectbox(
                    t("X-Axis"), _GRAN_OPTIONS,
                    index=_GRAN_OPTIONS.index(granularity),
                    key=_gran_key,
                )

        _unit = "week" if granularity == "Weeks" else "day"
        # One line (area view): its ✕s are always drawn, so there's nothing to
        # isolate — drop the click instruction. Multiple lines (group view): the
        # ✕s only appear once an area is isolated, to keep the all-areas view clean.
        if _is_area:
            _click_caption = t("Missed {unit}s are marked with a red ✕ and the "
                               "dotted red line traces where the trend went "
                               "through them.", unit=_unit)
        else:
            _click_caption = t("Click an area in the legend to see just that one — "
                               "its missed {unit}s are traced with red ✕s so the "
                               "line shows where it went instead of disappearing. "
                               "Click another area to switch straight to it, or "
                               "click it again to show all.", unit=_unit)
        if metric in _weekly_keys:
            st.caption(t("A gap in a line is a week with no weekly (Sunday) form "
                         "from that area; a submitted form with nothing to "
                         "report shows as a dot at 0.") + " " + _click_caption)
        elif _is_weekly:
            st.caption(t("A gap in a line is a week with no recorded weekly "
                         "total from that area.") + " " + _click_caption)
        else:
            st.caption(t("A gap in a line is a {unit} with no nightly report "
                         "from that area.", unit=_unit) + " " + _click_caption)

    _pipeline()

    # Daily Activity (date x metric grid) and the Tableau Ranking Snapshot
    # (area x metric grid) used to render here as raw tables. Removed
    # 2026-07-16 (Carson: redundant with the bar/trend above and the Tableau
    # snapshot pipeline elsewhere); only the extra table views are gone, the
    # DAILY_LOG data still feeds the bar and trend above.
    #
    # TABLEAU_RANKING is no longer read on this page at all — the funnel moved to
    # TABLEAU_DETAIL to follow the Period picker.
