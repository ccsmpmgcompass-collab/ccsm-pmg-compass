"""
breakdowns_engine.py
────────────────────────────────────────────────────────────────────────────────
Rendering engine for pages/04_Desgloses.py: the metric catalogue, cached data
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

from app.components.design_system import render_kpi_row, render_section_label
from app.config.theme import series_style
from app.db.queries import (
    get_area_expectation_entry,
    get_area_type_category_labels,
    get_blitz_dates,
    get_config_value,
    get_daily_log,
    get_group_weekly_expectation_totals,
    get_lineage_for_retired_parent,
    get_lineage_for_successor,
    get_nightly_submission_timing,
    get_tableau_daterange,
    get_tableau_detail,
    get_weekly_form_data,
    get_weekly_ki,
    get_weekly_submission_data,
    get_zones,
    is_within_last_transfers,
    resolve_area_category_label,
)
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

from app.config.flavor_loader import GOAL_TO_ACTUAL
from app.config.metric_catalog import (
    is_rate_metric,
    key_indicator_metrics,
    metric_options,
    weekly_metric_keys,
)


def _primary_metrics() -> tuple[str, ...]:
    """The mission's headline Key Indicators, pinned to the top of the Metric
    picker and marked with a ★ prefix there.

    For CCSM these are the seven `ki_*_real` values the weekly form collects —
    the same set SCORE_CONFIG scores as the KI component — rather than a
    hand-listed six. The matching `_meta` keys are that companionship's GOAL for
    the week and are deliberately NOT pinned: a goal is not an achievement, and
    showing them side by side in one picker invites reading one as the other.

    The ★ prefix stays plain ASCII on purpose. st.selectbox's type-to-search
    matches the DISPLAYED text, so a Mathematical-Bold label (𝗣𝗼𝘁…) could never
    be found by typing "po".
    """
    return tuple(key_indicator_metrics())


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
        return "Expectation"
    rank = {lbl: i for i, lbl in enumerate(get_area_type_category_labels())}
    return "/".join(sorted(cats, key=lambda l: rank.get(l, len(rank)))) + " Expectation"


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
    "This Week",
    "Last Week",
    "This Month So Far",
    "Last Month",
    "All Time",
]

# DAILY_LOG history to pull for the cards. The `days` arg to get_daily_log is a
# client-side filter — read_tab reads (and caches) the whole tab either way — so
# a wide window costs no extra Sheets read. See sheets_client._read_tab_cached.
_KPI_HISTORY_DAYS = 3650


def _kpi_period_bounds(label: str, today: date) -> tuple[date | None, date | None, int | None]:
    """(start, end, days_in_full_period) for a KPI period label — both ends
    inclusive. Returns (None, None, None) for "All Time": no bounds, and no
    goal, since a goal over unbounded history is meaningless.

    The mission week runs Monday–Sunday (Agent5A.gs rolls back to Monday, and
    the weekly report covers Mon–Sun), so weeks anchor on Monday, not Sunday.

    days_in_full_period is the FULL length of the period, not the elapsed part,
    so an in-progress period's card reads as "progress toward this week's /
    this month's goal" rather than silently lowering the bar.
    """
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
    return None, None, None  # All Time


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
def _load_tableau_detail() -> pd.DataFrame:
    """One row per person found, carrying the milestone dates that make the
    funnel's "Taught" bar period-sliceable.

    TABLEAU_RANKING — the funnel's source until 2026-07-16 — is a pre-aggregated
    area x metric grid with no date column anywhere in it, so it could never
    follow the Period picker. This tab is the only source in the system that
    counts PEOPLE being taught (rather than lessons) against a date.
    """
    df, _, _ = get_tableau_detail()
    return df


@st.cache_data(ttl=300)
def _load_tableau_range() -> tuple:
    """The (start, end) window the Tableau scraper was last run for.

    The export tab is CLEARED and rewritten on every run
    (finding_funnel_export._write_to_sheets), so it holds only the LAST run's
    window — a period reaching outside it undercounts "Taught" silently unless
    we check. Returns ('', '') for pre-scraper manual uploads, which carry no
    _range: marker; the funnel falls back to the dates it can observe.
    """
    return get_tableau_daterange()


def _detail_col(df: pd.DataFrame, name: str):
    """Resolve a column in the Tableau detail export. Exact match (case-
    insensitive) wins; else the SHORTEST column whose lowercased name contains
    `name`.

    Shortest-match matters: Tableau emits a giant '..._and_5_more_(combined)'
    mashup column that contains the same substrings as the real, short columns,
    so a naive `in` check finds the mashup instead of the data. Same rule as
    _col() in 07_Embudo_de_Búsqueda.py — duplicated rather than shared because
    Streamlit's page model has no way to import across pages/. Worth promoting
    both copies into app/utils/ when something else needs them.
    """
    lowered = {str(c).lower(): c for c in df.columns}
    if name in lowered:
        return lowered[name]
    matches = [c for c in df.columns
               if name in str(c).lower() and "(combined)" not in str(c).lower()]
    return min(matches, key=lambda c: len(str(c))) if matches else None


# ══════════════════════════════════════════════════════════════════════════════
# CHART HELPERS (group views)
# ══════════════════════════════════════════════════════════════════════════════

# ── Trend chart with an isolating legend ──────────────────────────────────────
# Plotly's own legend can't do what we want here. Its isolate branch switches on
# the CLICKED trace's current visibility (plotly.js legend/handle_click.js):
#
#     switch (fullTrace.visible) {
#         case 'legendonly': setVisibility(_item, true);          // ALL back on
#         case true:         otherState = isIsolated ? true : 'legendonly';
#
# Once one area is isolated every other legend item is 'legendonly', so clicking
# a second area hits the first case and unhides everything — you have to click it
# again to isolate it. No itemclick/itemdoubleclick value avoids that, and
# st.plotly_chart gives no hook to override it, so the trend renders through its
# own Plotly instance with a plotly_legendclick handler instead (returning false
# blocks Plotly's default). Cost of that: no Streamlit chart theming inside the
# iframe, hence the explicit dark colours in _isolating_trend_chart().
#
# Everything else on the page keeps using st.plotly_chart.

_LEGEND_ISOLATE_JS = """
var gd = document.getElementById('%(div_id)s');
gd.on('plotly_legendclick', function(ev) {
    // An area is several traces sharing a legendgroup: its line plus its
    // hidden missed-report bridge (meta === 'bridge'), so isolation works on
    // groups, not single curves. Bridges only exist while their own area is
    // isolated — on the all-areas view they stay hidden so the chart isn't
    // jumbled with every area's misses at once.
    var grp = function(t) { return t.legendgroup || t.name; };
    var isBridge = function(t) { return t.meta === 'bridge'; };
    var clicked = grp(gd.data[ev.curveNumber]);
    var shown = {};
    gd.data.forEach(function(t) {
        // Bridges don't define the chart's state — with one area isolated its
        // bridge is `true` too, and counting it would double the group.
        if (!isBridge(t) && (t.visible === true || t.visible === undefined))
            shown[grp(t)] = true;
    });
    var shownGroups = Object.keys(shown);
    // Clicking the already-isolated area restores everyone; any other click
    // switches straight to it, however the chart got into its current state.
    var restoreAll = (shownGroups.length === 1 && shownGroups[0] === clicked);
    var vis = gd.data.map(function(t) {
        if (isBridge(t))
            return (!restoreAll && grp(t) === clicked) ? true : 'legendonly';
        return restoreAll ? true : (grp(t) === clicked ? true : 'legendonly');
    });
    Plotly.restyle(gd, {visible: vis});
    return false;
});
"""


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
    # Streamlit's plotly theming doesn't reach inside the iframe, so restate the
    # bits of it this chart relies on. The app is pinned to the dark theme
    # (.streamlit/config.toml), so these are constants rather than a lookup.
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="sans-serif", color="#f4f4f8", size=12),
        hoverlabel=dict(bgcolor="#0e0e15", font=dict(color="#f4f4f8")),
        xaxis=dict(gridcolor="#2a2a35", linecolor="#2a2a35", zerolinecolor="#2a2a35"),
        yaxis=dict(gridcolor="#2a2a35", linecolor="#2a2a35", zerolinecolor="#2a2a35"),
        autosize=True,
        height=height - 20,
    )
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
) -> None:
    """The group view's Teaching Pipeline funnel, for one scope over one period.

    A module-level function rather than inline in render_group_breakdown for one
    reason: the bar/trend section returns early when a weekly-form metric has no
    submission for the period yet (e.g. "gate" on "This Week" before Sunday),
    and that return would otherwise take this section down with it. The funnel
    doesn't depend on the Metric picker at all, so it renders on both paths.
    """
    # "This Week" is suppressed on purpose (Carson, 2026-07-17): its last two
    # bars — At Sacrament and Baptized — come from the weekly Sunday form, which
    # keys on the week's ending Sunday and so reads 0 every day Mon–Sat. A funnel
    # that always bottoms out at 0/0 mid-week is misleading, so the whole section
    # (label included) is skipped rather than shown collapsed.
    if kpi_period == "This Week":
        return

    # Every bar counts what HAPPENED inside the selected period, exactly like the
    # Key Indicators cards — NOT a cohort ("people found this month who later got
    # baptized"). The bars were never nested anyway: this section used to sum four
    # independent TABLEAU_RANKING columns and draw them funnel-shaped, so the
    # shape has always implied a nesting the numbers don't have.
    #
    # Sources are deliberately mixed, because no single one carries all four
    # stages against a date:
    #   Found        <- `rows`       (DAILY_LOG new_found; already scoped + cut)
    #   Taught       <- TABLEAU_DETAIL  (see below)
    #   At Sacrament <- `weekly_wk` (Sunday form pew; already scoped + cut)
    #   Baptized     <- `weekly_wk` (Sunday form gate; already scoped + cut)
    # "Taught" is the odd one out: no nightly or weekly field counts PEOPLE being
    # taught, only lessons, so it has to come from Tableau — and it's therefore
    # the only bar whose coverage depends on when the export was last scraped.
    # That's what the guard below exists to make visible. TABLEAU_RANKING, the old
    # source, has no date column at all and could never follow the picker.

    def _period_total(frame: pd.DataFrame, col: str) -> int:
        """Total for one already-scoped, already-period-cut metric column.
        Absent column -> 0: a metric this mission never collects should read as
        an honest zero, not drop its bar out of the funnel."""
        if frame.empty or col not in frame.columns:
            return 0
        return int(pd.to_numeric(frame[col], errors="coerce").fillna(0).sum())

    # Which metric backs each stage comes from GOAL_TO_ACTUAL — the mission's
    # own map from an outcome ("people found", "at sacrament", "baptized") to
    # the Key Indicator that carries its real value. The three keys used to be
    # spelled out as new_found / pew / gate: Utah Provo's. _period_total returns
    # 0 for a column that isn't there, so all three bars read 0 for CCSM and the
    # funnel showed a mission that found nobody, and baptized nobody, every
    # period since launch.
    #
    # All three now come from `weekly_wk`. Found was previously taken from the
    # nightly log, but CCSM states its finding outcome as a weekly Key
    # Indicator, and a funnel whose first bar is counted over a different
    # reporting cadence than the rest is not comparable stage to stage.
    _found = _period_total(weekly_wk, GOAL_TO_ACTUAL.get("new_people_to_teach", ""))
    _pew   = _period_total(weekly_wk, GOAL_TO_ACTUAL.get("at_sacrament", ""))
    _gate  = _period_total(weekly_wk, GOAL_TO_ACTUAL.get("baptisms", ""))

    # ── Taught, from the Tableau detail export ────────────────────────────────
    _det = _load_tableau_detail()
    _det_area_col = _detail_col(_det, "latest_teaching_area") if not _det.empty else None
    _taught_col = _detail_col(_det, "first_new_person_being_taught_date") if not _det.empty else None
    _taught = 0
    _taught_warning = None

    if _det.empty:
        _taught_warning = (
            "⚠ The Taught bar reads 0 because no Tableau finding export is "
            "loaded. The other three bars come from the mission's own reports "
            "and are unaffected. Upload the Finding Detail export on the "
            "Finding Funnel page, or let the morning sync run."
        )
    elif _det_area_col is None:
        # Scoping is not optional: an unscoped count would quietly attribute the
        # whole mission's teaching to this one zone.
        _taught_warning = (
            f"⚠ The Taught bar reads 0 — the Tableau export has no "
            f"latest_teaching_area column, so its rows can't be matched against "
            f"MISSION_ORG's roster for {scope_value}. Showing mission-wide "
            f"numbers here would misattribute other zones' teaching."
        )
    elif _taught_col is None:
        _taught_warning = (
            "⚠ The Taught bar reads 0 — the Tableau export has no "
            "first_new_person_being_taught_date column to count against."
        )
    else:
        # Scope on the AREA NAME against MISSION_ORG's current roster. The export
        # also carries latest_zone, which is deliberately NOT used: a frame's own
        # zone column records where an area sat when the row was written, so it
        # resurrects departed areas forever (see _scope_to_areas' docstring).
        _det_scoped = _scope_to_areas(_det, _det_area_col, group_areas)
        if not _det_scoped.empty:
            _t = pd.to_datetime(_det_scoped[_taught_col], errors="coerce", format="mixed")
            _in_period = _t.notna()
            if p_start is not None:
                # `< p_end + 1 day`, not `<= p_end`: this column can carry a time
                # component, and comparing against midnight would silently drop
                # everyone taught after 00:00 on the period's final day.
                _in_period &= (
                    (_t >= pd.Timestamp(p_start))
                    & (_t < pd.Timestamp(p_end + timedelta(days=1)))
                )
            _taught = int(_in_period.sum())

    # ── Does the export actually cover the period the user picked? ────────────
    # The export tab is cleared and rewritten on every scrape, so it holds only
    # the last run's window. Without this check, picking a period outside that
    # window makes Taught collapse while its neighbours stay healthy — which
    # reads as "teaching stopped" rather than "the export is short".
    _cov_start = _cov_end = None
    _rs, _re = _load_tableau_range()
    if _rs and _re:
        _cov_start, _cov_end = pd.to_datetime(_rs, errors="coerce"), pd.to_datetime(_re, errors="coerce")
    elif not _det.empty and _taught_col is not None:
        # No _range: marker — a pre-scraper manual upload. Fall back to the dates
        # we can observe, measured across the WHOLE export rather than this
        # group's slice: coverage is a property of the export, and a zone that
        # simply taught nobody would otherwise look like a broken upload.
        _all_t = pd.to_datetime(_det[_taught_col], errors="coerce", format="mixed").dropna()
        if not _all_t.empty:
            _cov_start, _cov_end = _all_t.min(), _all_t.max()
    if _cov_start is None or _cov_end is None or pd.isna(_cov_start) or pd.isna(_cov_end):
        _cov_start = _cov_end = None  # unknown window — degrade, never block

    _coverage_warning = None
    _coverage_note = None
    if _cov_start is not None and _taught_warning is None:
        _cs, _ce = _cov_start.date(), _cov_end.date()
        if p_start is None:
            # All Time means "as far back as each source goes" — and Taught's
            # source starts later than the other three, so say so rather than
            # let it read as a teaching drought in the mission's early months.
            _coverage_note = (
                f"All Time: Found, At Sacrament and Baptized run as far back as "
                f"the mission's own reports go; Taught only to {_cs} (the "
                f"Tableau export's start)."
            )
        elif _cs > p_start:
            _coverage_warning = (
                f"⚠ The Taught bar is undercounted — the current Tableau export "
                f"only covers {_cs} → {_ce}, but {kpi_period.lower()} starts "
                f"{p_start}. The other three bars come from the mission's own "
                f"reports and are complete. Re-run the export with "
                f"`--preset since_launch` to restore the full window."
            )
        elif _ce < p_end:
            _gap_days = (p_end - _ce).days
            if in_progress and _gap_days <= 1:
                # The morning scrape simply hasn't run yet. A warning here would
                # fire every day until people learned to ignore it.
                _coverage_note = (
                    f"Taught is current through {_ce}; today's records aren't in "
                    f"the Tableau export yet."
                )
            else:
                _coverage_warning = (
                    f"⚠ The Taught bar is undercounted — the current Tableau "
                    f"export only reaches {_ce}, but {kpi_period.lower()} runs to "
                    f"{p_end}. The other three bars come from the mission's own "
                    f"reports and are complete. Re-run the export with "
                    f"`--preset since_launch` to restore the full window."
                )

    if _taught_warning:
        st.warning(_taught_warning)
    elif _coverage_warning:
        st.warning(_coverage_warning)

    render_section_label(t('Teaching Pipeline — {scope_value}', scope_value=scope_value))

    # All four stages always, in this fixed order — a stage is never dropped for
    # being 0. On a short period (and on "This Week" until Sunday's form lands)
    # a real zero is the honest answer, and it has to stay visible as an empty
    # slot reading 0% rather than silently vanishing and making the funnel look
    # like it has fewer steps than it does.
    _funnel_vals = [
        ("Found",        _found),
        ("Taught",       _taught),
        ("At Sacrament", _pew),
        ("Baptized",     _gate),
    ]

    if any(v for _, v in _funnel_vals):
        _f_labels, _f_vals = zip(*_funnel_vals)
        fig_funnel = go.Figure(go.Funnel(
            y=list(_f_labels), x=list(_f_vals),
            # "auto", not "inside": a zero-width bar has no inside to draw a
            # label in, so a 0 stage would render as a silent blank. "auto"
            # leaves normal bars labelled inside exactly as before and pushes
            # only the empty ones' "0 0%" out where it can be read.
            textposition="auto", textinfo="value+percent initial",
            textfont=dict(color="#f4f4f8"),
            outsidetextfont=dict(color="#f4f4f8"),
            marker=dict(color=["#2563eb", "#15803d", "#b45309", "#b91c1c"]),
        ))
        fig_funnel.update_layout(
            template="pmg_dark", height=300,
            margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig_funnel, use_container_width=True)
        st.caption(
            t("{span}  |  {kpi_period} — counts what happened in this period. Found, At Sacrament and Baptized from the weekly Key Indicators, Taught from the Tableau export; the bars come from different reports and aren't subsets of each other.", span=span, kpi_period=kpi_period)
        )
        # At Sacrament (pew) is a raw weekly headcount the missionaries type into
        # the Sunday form, not a roster of named people — over a period spanning
        # several Sundays, the same repeat attender gets added again every week.
        # Taught, by contrast, counts each person once (their first-ever lesson
        # date), so it's normal for At Sacrament to run higher than Taught on
        # anything longer than a single week (Carson noticed this in Provo South,
        # 2026-07-17 — confirmed expected, not a bug).
        st.caption(
            t("At Sacrament is a weekly headcount, not unique people — someone who "
            "attends several Sundays in this period is added again each week, so "
            "it can run higher than Taught (which counts each person once).")
        )
        if _coverage_note:
            st.caption(_coverage_note)
    else:
        st.info(
            t('No pipeline activity recorded for {scope_value} in {kpi_period}.', scope_value=scope_value, kpi_period=kpi_period.lower())
        )


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
        f'font-size:0.72rem;font-weight:600;">{d}</th>'
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
            (_C_GREEN[0], "On time"), (_C_AMBER[0], "Late"),
            (_C_BLITZ[0], "Blitz day"), (_C_RED[0], "Missed"),
            (_C_UPCOMING[0], "Upcoming / pre-tracking"),
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
                           f'<div style="font-size:0.8rem;">&nbsp;</div>', f"{d} — upcoming"
            if d < _win_start:
                bg, fg = _C_UPCOMING
                return bg, f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{d[8:]}</div>'\
                           f'<div style="font-size:0.8rem;">&nbsp;</div>', f"{d} — before tracking started"
            _acc = _accountable(d)
            if _acc == 0:
                bg, fg = _C_UPCOMING
                return bg, f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{d[8:]}</div>'\
                           f'<div style="font-size:0.8rem;">&nbsp;</div>', f"{d} — no areas yet"
            _n = _per_day.get(d, 0)
            _pct = round(_n / _acc * 100)
            _pcts.append(_pct)
            bg, fg = _pct_color(_pct)
            return bg, (f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{d[8:]}</div>'
                        f'<div style="font-size:0.8rem;font-weight:700;color:{fg};">{_pct}%</div>'), \
                   f"{d} — {_n}/{_acc} areas submitted ({_pct}%)"

        _legend = _compliance_legend([
            (_C_GREEN[0], "&ge;85%"), (_C_AMBER[0], "70–84%"),
            (_C_RED[0], "&lt;70%"), (_C_UPCOMING[0], "Upcoming / pre-tracking"),
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
            f'<p style="color:#9ca3af;font-size:0.82rem;margin-top:0;">Each box is the share of '
            f'{scope_value}\'s <strong style="color:#f4f4f8;">{len(group_areas)}</strong> areas that '
            f'turned in the nightly form that day. Window average: '
            f'<strong style="color:#f4f4f8;">{_avg}%</strong>.</p>',
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
            _title = f"{_n}/{_acc} areas submitted ({_pct}%)" if _acc else "no areas yet"
            _inner = (f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1.2;">{_lbl}</div>'
                      f'<div style="font-size:0.8rem;font-weight:700;color:{_fg};">{_pct}%</div>')
        _wk_cells += (
            f'<td title="Week ending {_w} — {_title}" style="text-align:center;'
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
        'Each box is a Mon–Sun week, labeled by its ending Sunday. Submission is '
        'credited by the day the weekly form arrived, not the date typed inside it.'
        '</p>',
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
    _p_col, _, _ = st.columns(3)
    with _p_col:
        # Defaults to the running month (Carson, 2026-07-17) — index only sets
        # the FIRST render; the widget's own state wins after that.
        kpi_period = st.selectbox(
            t("Period"), _KPI_PERIODS,
            index=_KPI_PERIODS.index("This Month So Far"),
            key="bd_kpi_period",
        )
    p_start, p_end, p_days = _kpi_period_bounds(kpi_period, mission_today())

    rows = daily_hist if daily_hist is not None else pd.DataFrame()
    if not rows.empty and "Date" in rows.columns and p_start is not None:
        # Date is a normalised YYYY-MM-DD string, so a lexicographic compare is
        # a correct date compare and needs no parsing.
        rows = rows[
            (rows["Date"] >= p_start.isoformat())
            & (rows["Date"] <= p_end.isoformat())
        ]
    has_rows = not rows.empty

    span = (
        f"{rows['Date'].min()} → {rows['Date'].max()}" if has_rows and p_start is None
        else "—" if not has_rows
        else p_start.isoformat() if p_start == p_end
        else f"{p_start.isoformat()} → {p_end.isoformat()}"
    )
    # An in-progress period holds only part of its days, so a vs-goal delta on it
    # would call a zone 4 days into a 7-day week "-33%" when it's actually ahead
    # of pace. Judge against the goal only once the period is complete.
    in_progress = kpi_period in ("This Week", "This Month So Far")

    if not has_rows:
        st.info(
            t('No {scope_value} activity recorded for {kpi_period} — the sections below cover this period only.', scope_value=scope_value, kpi_period=kpi_period.lower())
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 1. KEY INDICATORS — every metric for the group, over the selected period
    # ══════════════════════════════════════════════════════════════════════════
    # WHICH metrics get a card comes from LIVE_SNAPSHOT's *_7d columns (that's
    # METRICS_CONFIG's active metric set); the VALUES come from DAILY_LOG, the
    # only source with the per-day granularity an arbitrary period needs. All
    # three levels get cards (Carson, 2026-07-17); `goals` decides whether they
    # carry a target — zone and district both roll up their areas' goals, an
    # area has its own directly (Carson, 2026-07-24: district wanted the same
    # goal bars zone/area already had).
    if snap_scope is not None and not snap_scope.empty and has_rows:
        render_section_label(t('Key Indicators — {scope_value}', scope_value=scope_value))

        # Rates can't be summed across areas or days (and render_kpi_row int()s
        # its value, so a 0.42 rate would read as 0). LIVE_SNAPSHOT is built from
        # DAILY_LOG counts so it shouldn't carry any — guard regardless.
        _kpi_keys = [
            c[:-3] for c in snap_scope.columns
            if c.endswith("_7d") and not is_rate_metric(c[:-3])
        ]
        # Goal scales with the period: the sheet stores one WEEKLY goal per area
        # (get_zone_goals sums them), so a 31-day month is goal*31/7. All Time
        # has no meaningful goal. The expectation bar (Carson, 2026-07-24) rides
        # the exact same _goal_factor — keeping one scaling convention for both
        # bars is what makes them directly comparable on one card.
        _goal_factor = (p_days / 7) if p_days else None
        _expectation_totals = get_group_weekly_expectation_totals(group_areas)

        _kpi_cards = []
        for _key in _kpi_keys:
            if _key not in rows.columns:
                continue  # active metric with no DAILY_LOG column yet
            _val = int(pd.to_numeric(rows[_key], errors="coerce").fillna(0).sum())
            _card: dict = {"label": format_metric_label(_key), "value": _val}
            _weekly_goal = float((goals or {}).get(_key, 0) or 0)
            if _goal_factor and _weekly_goal > 0:
                _goal = _weekly_goal * _goal_factor
                _card["goal"] = _goal
                if not in_progress:
                    _card["delta"] = round(_val / _goal * 100 - 100, 1)
                    _card["delta_label"] = f"goal {int(round(_goal))}"
            _weekly_expectation = float(_expectation_totals.get(_key, 0) or 0)
            if _goal_factor and _weekly_expectation > 0:
                _card["expectation"] = _weekly_expectation * _goal_factor
            _kpi_cards.append(_card)

        _goal_note = (
            "totals for the period — no goals at this level" if not goals
            else "no goal for unbounded history" if _goal_factor is None
            else "bar shows progress toward this period's goal (period still in "
                 "progress)" if in_progress
            else f"measured against the weekly goal × {_goal_factor:.2f}"
        )
        st.caption(f"{span}  |  {_goal_note}")

        if _kpi_cards:
            # render_kpi_row is a non-wrapping flex row, so cards shrink rather
            # than wrap — chunk them 4-up to keep labels on one line.
            for _i in range(0, len(_kpi_cards), 4):
                render_kpi_row(_kpi_cards[_i:_i + 4])
        else:
            st.info(t('No snapshot metrics found for {scope_value}.', scope_value=scope_value))

    # ══════════════════════════════════════════════════════════════════════════
    # 2. METRIC PICKER + PER-AREA BAR — the selected indicator, this period
    # ══════════════════════════════════════════════════════════════════════════
    # The pickable metrics are mostly the Key Indicators: DAILY_LOG-backed
    # counts. Rates and rc_total are weekly-grained and can't be cut to an
    # arbitrary period without spilling over its edges, so they aren't offered
    # here.
    #
    # The seven Key Indicators are the exception — they live only in the weekly
    # form, so each gets its own source instead of `rows`: WEEKLY_FORM_RAW via
    # get_weekly_form_data(), scoped to this group's areas. Whether EACH is
    # offered in the picker depends on the group having reported that field at
    # least once ever — not on the currently-selected period — because the
    # weekly form lands once a week: on "This Week" (the page's default) every
    # week_end_date is still in the future, so a period-scoped check would make
    # the options flicker in and out of the dropdown as Period changes, or hide
    # the mission's top metrics entirely most days of the week. The VALUES
    # plotted below are still cut to the period, so a period with no submitted
    # week yet correctly renders an empty chart rather than stale numbers.
    _weekly_keys = _weekly_metrics()
    _weekly_wk_all = get_weekly_form_data()
    if not _weekly_wk_all.empty:
        _weekly_wk_all = _scope_to_areas(_weekly_wk_all, "area", group_areas).rename(columns={"area": "Area"})
    # Provo merged a third source in here (mmm_sent from WEEKLY_KI). CCSM has no
    # equivalent: its WEEKLY_KI holds the same ki_* keys the weekly form already
    # supplies, so merging it would duplicate columns rather than add any.
    # Per-metric, not one shared flag: a group can have baptisms but never
    # logged a friend with a baptismal date, or vice versa.
    _weekly_has = {
        k: (not _weekly_wk_all.empty and k in _weekly_wk_all.columns
            and _weekly_wk_all[k].notna().any())
        for k in _weekly_keys
    }

    _weekly_wk = _weekly_wk_all
    if any(_weekly_has.values()) and p_start is not None:
        _weekly_wk = _weekly_wk_all[
            (_weekly_wk_all["week_end_date"] >= p_start.isoformat())
            & (_weekly_wk_all["week_end_date"] <= p_end.isoformat())
        ]

    _catalog = metric_options()
    _primary = _primary_metrics()

    metric_keys = [
        k for k in _catalog
        if not is_rate_metric(k) and (
            (has_rows and k in rows.columns)
            or (k in _weekly_keys and _weekly_has.get(k, False))
        )
    ]

    if not metric_keys:
        if has_rows or any(_weekly_has.values()):
            st.info(t("No daily-log metrics available for this group yet."))
        return

    # The headline KIs float to the top, ahead of the rest of the catalogue —
    # not a second copy, just a reorder of the same filtered list (a metric this
    # group has never reported is simply absent from both).
    metric_keys = (
        [k for k in _primary if k in metric_keys]
        + [k for k in metric_keys if k not in _primary]
    )

    # Default selection: the first pinned KI this group actually has data for,
    # else the first option. Provo defaulted to "nm_lessons" by name — a metric
    # CCSM does not collect, so that index lookup always missed and the picker
    # silently opened on whatever happened to sort first.
    _default_idx = next(
        (metric_keys.index(k) for k in _primary if k in metric_keys), 0)

    _m_col, _, _ = st.columns(3)
    with _m_col:
        metric = st.selectbox(
            t("Metric"),
            metric_keys,
            index=_default_idx,
            # The KIs get a ★ prefix so they stand out at the top — but the
            # label stays PLAIN ASCII. st.selectbox's type-to-search matches the
            # DISPLAYED text, so a Mathematical-Bold label (𝗣𝗼𝘁…) could never be
            # found by typing "po".
            format_func=lambda m: (
                f"★ {_catalog.get(m, m)}" if m in _primary
                else _catalog.get(m, m)
            ),
            key="bd_metric",
        )
    m_label = _catalog.get(metric, metric)
    _is_weekly = metric in _weekly_keys

    if _is_area:
        # Replaces the old per-area bar (Carson, 2026-07-17: "add a bar chart
        # that shows all the questions on the form and how many they did in
        # the selected time period") — every metric this area is offered in
        # the picker above (metric_keys: daily + weekly-form, rates excluded),
        # not just whichever ONE is currently selected. Rendered here, ahead of
        # the weekly-empty early-return below, so a stale-Sunday gap on the
        # PICKED metric can't hide this — it doesn't read the picker at all.
        render_section_label(t('All Metrics — {scope_value}', scope_value=scope_value))
        st.caption(t("{span}  |  {kpi_period}  |  every question this area has ever reported, totalled for this period (daily + weekly Sunday form; rates excluded — see the Metric picker below for a single metric's trend)", span=span, kpi_period=kpi_period))

        _area_color = series_style(0)[0]   # one area = the trend's own hue
        _all_vals = []
        for _mk in metric_keys:
            if _mk in _weekly_keys:
                _v = (
                    float(pd.to_numeric(_weekly_wk[_mk], errors="coerce").fillna(0).sum())
                    if (not _weekly_wk.empty and _mk in _weekly_wk.columns) else 0.0
                )
            else:
                _v = (
                    float(pd.to_numeric(rows[_mk], errors="coerce").fillna(0).sum())
                    if (has_rows and _mk in rows.columns) else 0.0
                )
            _all_vals.append(_v)
        _all_labels = [_catalog.get(k, k) for k in metric_keys]

        fig_all = go.Figure(go.Bar(
            x=_all_labels,
            y=_all_vals,
            marker=dict(color=_area_color),
            text=[f"{v:g}" for v in _all_vals],
            textposition="outside",
            cliponaxis=False,
        ))

        # Expectation markers — each metric's bar is a different indicator, so
        # a full-width hline can't work here; instead a grey dash floats at
        # the area's scaled expectation over its own bar (weekly pace × period
        # days / 7, same scaling as the group bar's lines; none on the
        # unbounded "All Time"). Only metrics with an expectation defined in
        # Goals > Area Expectation Settings get one — add an expectation
        # there and the dash appears here (Carson, 2026-07-18).
        _exp_factor = (p_days / 7) if p_days else None
        _exp_x, _exp_y, _exp_txt = [], [], []
        if _exp_factor and group_areas:
            # group_areas is a set; the area view always has exactly one.
            _area_name = next(iter(group_areas))
            for _mk, _lbl in zip(metric_keys, _all_labels):
                _e = get_area_expectation_entry(_area_name, _mk)
                if not _e:
                    continue
                _h = _e["weekly"] * _exp_factor
                _exp_x.append(_lbl)
                _exp_y.append(_h)
                _exp_txt.append(
                    f"Expectation {_expectation_rate(_e)} "
                    f"(≈{round(_h, 1):g} this period)"
                )
        if _exp_x:
            fig_all.add_trace(go.Scatter(
                x=_exp_x, y=_exp_y,
                mode="markers",
                marker=dict(
                    symbol="line-ew",
                    size=18,
                    line=dict(width=2, color=_EXP_LINE_STYLE["color"]),
                ),
                text=_exp_txt,
                hovertemplate="%{text}<extra></extra>",
                cliponaxis=False,
                showlegend=False,
            ))

        _all_top = max(max(_all_vals) if _all_vals else 0,
                       max(_exp_y) if _exp_y else 0)
        fig_all.update_layout(
            xaxis=dict(tickangle=-45),
            showlegend=False,
            margin=dict(t=30, b=150, l=50, r=20),
            yaxis=dict(
                title="Count",
                range=[0, max(_all_top * 1.15, 1)],
            ),
        )
        st.plotly_chart(fig_all, use_container_width=True)
    else:
        render_section_label(t('{m_label} by Area — {scope_value}', m_label=m_label, scope_value=scope_value))
        st.caption(f"{span}  |  {kpi_period}"
                   + ("  |  from the weekly Sunday form — one point per week, not per day"
                      if metric in _weekly_keys
                      else "  |  weekly totals — one point per week, not per day"
                      if _is_weekly else ""))

    if _is_weekly and _weekly_wk.empty:
        # A real gap, not a bug: no Sunday form has landed yet for this period
        # (e.g. "This Week" before Sunday). Skip straight past the bar/trend
        # rather than rendering charts with nothing in them.
        #
        # The Teaching Pipeline still renders: it doesn't read the Metric picker,
        # and 2 of its 4 bars come from the nightly log, which has plenty of data
        # for this period. Bailing out of the whole function here used to take the
        # funnel down with it — invisible on "This Week" + the default "gate"
        # metric, i.e. the page's own default view.
        st.info(
            f"No weekly form submitted yet for {kpi_period.lower()} — "
            f"{m_label} reports once a week, on Sunday."
            if metric in _weekly_keys else
            f"No weekly totals recorded yet for {kpi_period.lower()} — "
            f"{m_label} is tallied once a week."
        )
        _render_teaching_pipeline(
            scope_value=scope_value, kpi_period=kpi_period,
            p_start=p_start, p_end=p_end, in_progress=in_progress, span=span,
            rows=rows, weekly_wk=_weekly_wk, group_areas=group_areas,
        )
        return

    # One style per area, shared by this bar chart and the trend below so an
    # area wears the same colour in both. Keyed by NAME off the group's sorted
    # roster, never by position in a chart: this bar is sorted by value and the
    # trend by name, so an index-based colour would disagree between the two and
    # would repaint every bar whenever the ranking moved.
    _ordered_areas = sorted(group_areas)
    _style_of = {str(a): series_style(_i) for _i, a in enumerate(_ordered_areas)}
    _fallback = series_style(0)

    # The per-area bar is a group thing — for one area it would be a single bar
    # saying nothing the Key Indicators card above doesn't. Skip it; the trend
    # below still carries the area's own line.
    if not _is_area:
        by_area = (
            (_weekly_wk if _is_weekly else rows).groupby("Area")[metric].sum().reset_index()
            .sort_values(metric, ascending=False)
        )
        _bar_styles = [_style_of.get(str(a), _fallback) for a in by_area["Area"]]
        fig_bar = go.Figure(go.Bar(
            x=by_area["Area"],
            y=by_area[metric],
            marker=dict(
                color=[s[0] for s in _bar_styles],
                # Only ever non-empty past the 8th area, where hues start reusing —
                # the pattern is what keeps those bars from reading as duplicates.
                pattern=dict(shape=[s[2] for s in _bar_styles], fgcolor="#08080e", size=4),
            ),
            text=by_area[metric],
            textposition="outside",
            # Without this an outside label on the tallest bar gets clipped by
            # the plot area's top edge instead of drawing over it.
            cliponaxis=False,
        ))
        fig_bar.update_layout(
            # No in-chart title: the section label and caption above already say the
            # metric, scope and period.
            xaxis_title="Area",
            showlegend=False,          # single series — a legend would say nothing
            hovermode="x unified",
            margin=dict(t=30, b=80, l=50, r=20),
            yaxis=dict(
                title=m_label,
                # Headroom for the outside text label above the tallest bar —
                # with autorange the axis fits the bar VALUES only, not the
                # label text floating above them, so the top number still gets
                # cut off without this (same fix as the trend chart's fixed
                # range, and the funnel bars' *1.18/1.2 padding).
                range=[0, max(float(by_area[metric].max()) * 1.15, 1) if not by_area.empty else 1],
            ),
        )

        # Expectation line(s) — the same light-grey references the trend chart
        # below draws, but scaled to the selected PERIOD since these bars are
        # period totals: expected = weekly pace × (period days / 7). "All
        # Time" is unbounded, so there's no period total to expect — no line
        # (same rule as the KPI cards' "no goal for unbounded history").
        _exp_factor = (p_days / 7) if p_days else None
        if _exp_factor:
            _paces = _expectation_paces(group_areas, metric)
            _multi = len(_paces) > 1
            _bar_top = float(by_area[metric].max()) if not by_area.empty else 0.0
            for _p in sorted(_paces):
                _entry, _cats = _paces[_p]
                _h = _p * _exp_factor
                _bar_top = max(_bar_top, _h)
                fig_bar.add_hline(
                    y=_h,
                    line=_EXP_LINE_STYLE,
                    annotation_text=(
                        f"{_expectation_prefix(_cats, _multi)} "
                        f"{_expectation_rate(_entry)} (≈{round(_h, 1):g} this period)"
                    ),
                    annotation_position="top left",
                    annotation=dict(_EXP_ANNOTATION),
                )
            if _paces:
                # The fixed range above only fit the bars — lift it when the
                # tallest expectation line would clip off the top.
                fig_bar.update_layout(yaxis=dict(range=[0, max(_bar_top * 1.15, 1)]))

        st.plotly_chart(fig_bar, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # 3. TREND — the same metric over the same period, one line per area
    # ══════════════════════════════════════════════════════════════════════════
    render_section_label(t('{m_label} Trend — {scope_value}', m_label=m_label, scope_value=scope_value))

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
        _x_title = "Week Ending"
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
            _x_title = "Week Ending"
        else:
            _t["_bucket"] = _t["Date"]
            _x_title = "Date"

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
            margin=dict(t=30, b=50, l=50, r=20),
        )
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
            _click_caption = (f"Missed {_unit}s are marked with a red ✕ and the "
                              "dotted red line traces where the trend went "
                              "through them.")
        else:
            _click_caption = ("Click an area in the legend to see just that one — "
                              f"its missed {_unit}s are traced with red ✕s so the "
                              "line shows where it went instead of disappearing. "
                              "Click another area to switch straight to it, or "
                              "click it again to show all.")
        if metric in _weekly_keys:
            st.caption("A gap in a line is a week with no weekly (Sunday) form "
                       "from that area; a submitted form with nothing to "
                       "report shows as a dot at 0. " + _click_caption)
        elif _is_weekly:
            st.caption("A gap in a line is a week with no recorded weekly "
                       "total from that area. " + _click_caption)
        else:
            st.caption(f"A gap in a line is a {_unit} with no nightly report "
                       "from that area. " + _click_caption)

    _render_teaching_pipeline(
        scope_value=scope_value, kpi_period=kpi_period,
        p_start=p_start, p_end=p_end, in_progress=in_progress, span=span,
        rows=rows, weekly_wk=_weekly_wk, group_areas=group_areas,
    )

    # Daily Activity (date x metric grid) and the Tableau Ranking Snapshot
    # (area x metric grid) used to render here as raw tables. Removed
    # 2026-07-16 (Carson: redundant with the bar/trend above and the Tableau
    # snapshot pipeline elsewhere); only the extra table views are gone, the
    # DAILY_LOG data still feeds the bar and trend above.
    #
    # TABLEAU_RANKING is no longer read on this page at all — the funnel moved to
    # TABLEAU_DETAIL to follow the Period picker.
