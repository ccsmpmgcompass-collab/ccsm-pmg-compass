"""One set of numbers, for one unit, over one period — and nothing that draws.

`build_report(scope, period, comparison, data)` returns a `ReportModel`: plain
dataclasses, no Streamlit, no ReportLab. `views/11_Informes.py` renders it to
the screen and `reports/packet.py` renders it to the council PDF. Neither does
arithmetic of its own. That is the whole of decision 30, and it is what stops
the printed packet and the page on screen disagreeing about the same week.

**The two sides of a percentage must rest on the same population.** This is the
single largest hazard in the file. A week's Key Indicator RESULTS come from
WEEKLY_KI, which `CCSM_Agent5A.gs` writes after filtering to the roster; a
week's GOALS come from the previous week's form rows, which is a different set
of areas — 39 areas set the goals for the week ending 2026-09-20 and 27 filed
results for it. Summing both and dividing gives a number with no meaning. On
2026-08-21 a Panel tile really did read 2.040% this way. So every figure that is
compared to another is reduced to a RATE first, and each rate carries the count
it was divided by.

Three bases appear here, and they are not interchangeable:

  ``actual``                   the raw sum. The headline (decision 12), never
                               compared to anything.
  ``per_reporting_area_week``  the sum over the area-weeks that actually filed.
                               What attainment and change are computed on,
                               because it is the only basis where a swing in how
                               many areas reported cannot masquerade as work.
                               Measured 2026-09-21: `contacts_attempted` rose
                               19.3% between two weeks per active area and 2.6%
                               per reporting area. The second is the true one.
  ``per_active_area_week``     the sum over every roster area, reporting or not.
                               Decision 12's basis for comparing UNITS, where a
                               zone whose areas go silent should rank lower on
                               purpose — `zone_comparison`'s standing rule.

Loading is separate from building. `load_data()` reads every frame once;
`build_report` is pure over it. The packet renders 63 scopes from one load.

See PLAN-2026-09-21-informes.md §2 and §4 steps R3–R4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from app.reports import periods as P
from app.reports import scope as S
from app.reports.grading import Grade, goal_is_unusable, grade_ki

#: How much DAILY_LOG history to pull. The `days` argument is a client-side
#: filter — `read_tab` reads and caches the whole tab either way — so a wide
#: window costs no extra Sheets read and lets any period resolve.
HISTORY_DAYS = 3650


# ── Coverage ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NightlyCoverage:
    """Nightly reporting over the period's days — decision 19's other half.

    Counted in area-DAYS, because that is the grain the nightly form is filed
    at. Measured over the current transfer's two complete weeks: 456 of a
    possible 630, and all 45 areas filed at least once.
    """

    days_possible: int
    days_reported: int
    areas_reporting: int
    areas_in_scope: int

    @property
    def rate(self) -> float | None:
        return self.days_reported / self.days_possible if self.days_possible else None

    @property
    def label(self) -> str:
        return f"{self.days_reported} de {self.days_possible} días-área"


# ── One metric ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MetricRow:
    """One metric, for one unit, over one period.

    Every count that a figure was divided by is carried beside it. A renderer
    that wants to say "sobre 27 de 45 áreas" has the numbers; a renderer that
    divides two of these fields together to invent a new ratio is the bug this
    shape exists to prevent.
    """

    key: str
    label: str

    actual: float | None = None
    actual_area_weeks: int = 0

    #: The companionships' own summed goal for the period's weeks. The bar
    #: fills against this (decision 11).
    #:
    #: ``meta_area_weeks`` is the divisor: every area-week that FILED the form
    #: the goal was written on, whether or not it wrote a number in this
    #: metric's box. A blank meta is a commitment to nothing, so it belongs in
    #: the denominator — dividing by ``meta_set_by`` instead would read two
    #: areas' baptism goal of 2 as "the mission is aiming at 2 per area per
    #: week" when 37 of the 39 areas that answered aimed at none.
    #: ``meta_set_by`` is for the caption, never for arithmetic.
    meta: float | None = None
    meta_area_weeks: int = 0
    meta_set_by: int = 0

    #: Leadership's AREA_TRANSFER_GOALS figure — the violet mark (decision 11),
    #: pro-rated to the part of the cycle this period covers.
    leadership_goal: float | None = None
    leadership_goal_areas: int = 0
    leadership_goal_complete: bool = False

    per_active_area_week: float | None = None
    per_reporting_area_week: float | None = None
    before_per_reporting_area_week: float | None = None

    grade: Grade = field(default_factory=Grade)

    @property
    def meta_per_area_week(self) -> float | None:
        if self.meta is None or not self.meta_area_weeks:
            return None
        return self.meta / self.meta_area_weeks

    @property
    def has_leadership_goal(self) -> bool:
        """Whether the violet mark can honestly be drawn.

        False reads "sin meta" (decision 23). It is all-or-nothing on purpose:
        2026-5 has a transfer goal for exactly one of its 45 areas, and a
        mission bar marked with one companionship's target would be a
        fabricated figure wearing the mission's name. Scaling that one goal up
        to 45 would be worse — decision 23 forbids inventing a back-dated goal,
        and this is the same invention with arithmetic in front of it.
        """
        return self.leadership_goal is not None and self.leadership_goal_complete


# ── The model ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReportModel:
    """Everything one unit's pages need, for one period. The contract of §2."""

    scope: S.Scope
    period: P.Period
    comparison: P.Comparison
    mission_name: str
    today: date

    #: Weekly-form coverage of the period, and of whatever it is held against.
    #: Decision 19 puts this in the subtitle at every level: it qualifies every
    #: other number on the page.
    coverage: P.Coverage = None
    comparison_coverage: P.Coverage | None = None
    nightly_coverage: NightlyCoverage | None = None

    #: Roster areas that filed a weekly form in the period, and those that did
    #: not. The silent list is named, at every level, including the mission
    #: (decision 16).
    areas_reporting: tuple[str, ...] = ()
    areas_silent: tuple[str, ...] = ()

    #: The seven, always, in the catalogue's order (decision 10).
    key_indicators: tuple[MetricRow, ...] = ()

    # ── Filled by step R4; declared here so the shape never changes ──────────
    nightly_metrics: tuple[MetricRow, ...] = ()
    scores: dict = field(default_factory=dict)
    rates: tuple = ()
    children: tuple = ()
    series: dict = field(default_factory=dict)
    tableau: object | None = None

    @property
    def compliance_label(self) -> str:
        """Weekly-form compliance, phrased so it cannot flatter.

        Over a single week it is the plain count: "27 de 45 áreas informaron".
        Over more than one it is the area-WEEK rate — "63 de 90 informes
        semanales (70%)" — because the count of areas that filed at least once
        is the flattering number. 39 of 45 areas touched the current transfer's
        two weeks; only 27 filed the second of them, and a subtitle reading
        "39 de 45" would hide that.
        """
        cov = self.coverage
        if cov is None or cov.weeks_expected == 0:
            return "sin semanas completas"
        if cov.weeks_expected == 1:
            noun = "área informó" if self.scope.area_count == 1 else "áreas informaron"
            return f"{len(self.areas_reporting)} de {self.scope.area_count} {noun}"
        rate = cov.reporting_rate or 0
        return (f"{cov.area_weeks_reported} de {cov.area_weeks_expected} "
                f"informes semanales ({rate:.0%})")

    @property
    def subtitle(self) -> str:
        """The line under the unit's name: period, progress, compliance.

        Decision 19 — compliance is a headline, not a footnote, because it
        qualifies everything above it.
        """
        bits = [self.period.label]
        if self.period.in_progress:
            bits.append(self.period.progress_label)
        bits.append(self.compliance_label)
        return " · ".join(bits)

    def ki(self, key: str) -> MetricRow | None:
        return next((r for r in self.key_indicators if r.key == key), None)


# ── Loading ───────────────────────────────────────────────────────────────────

@dataclass
class ReportData:
    """Every frame the model reads, loaded once and shared by 63 scopes.

    Not frozen: it memoises the two lookups that would otherwise be repeated
    per scope — the W-7 goal read and the mission-scope verdict on whether a
    goal is a usable yardstick.
    """

    roster: pd.DataFrame
    weekly_ki: pd.DataFrame
    daily_log: pd.DataFrame
    transfer_goals: pd.DataFrame
    cycles: list[dict]
    ki_keys: tuple[str, ...]
    labels: dict[str, str]
    mission_name: str
    today: date
    #: The last day that counts toward nightly compliance — today once the
    #: evening refresh has run, yesterday before it. Resolved once at load so
    #: `build_report` stays pure and a packet cannot straddle the 9:30 PM
    #: cutoff halfway through its 63 scopes.
    anchor: date
    #: `queries.get_ki_goals_for_week`, injected rather than imported so a test
    #: can hand in a week's goals without a sheet. The W-7 rule it implements —
    #: a week's goals are written on the PREVIOUS week's form — stays in
    #: queries.py, where it has one home and one set of tests.
    ki_goals_fn: object = None
    _goals: dict = field(default_factory=dict, repr=False)
    _flags: dict = field(default_factory=dict, repr=False)

    def ki_goals_for_week(self, week: date, areas: frozenset) -> tuple:
        """`get_ki_goals_for_week`, memoised on (week, areas).

        The W-7 lookup itself stays in `queries.py` — a week's goals are
        written on the PREVIOUS week's form, and that rule has one home. This
        only stops the packet asking the same question 378 times.
        """
        cache_key = (week, areas)
        if cache_key not in self._goals:
            if self.ki_goals_fn is None:
                return ({}, {}, None, 0)
            self._goals[cache_key] = self.ki_goals_fn(week, areas=set(areas))
        return self._goals[cache_key]

    def ki_goal_flags(self, period: P.Period) -> dict:
        """Which Key Indicator goals are not yardsticks, judged at MISSION scope.

        Asked once for the whole mission and handed down to every unit — see
        `grading.goal_is_unusable`. Asked per area it would answer "the goal is
        broken" every time a companionship had a bad fortnight.
        """
        if period.key not in self._flags:
            mission = S.mission_scope(self.roster, self.mission_name)
            rows = _ki_rows(self, mission, period)
            self._flags[period.key] = {
                r.key: goal_is_unusable(r.per_reporting_area_week,
                                        r.meta_per_area_week)
                for r in rows
            }
        return self._flags[period.key]


def load_data(today: date | None = None) -> ReportData:
    """Read every source once. The only impure function in this module."""
    from app.config.flavor_loader import flavor
    from app.config.metric_catalog import (
        format_metric_label, key_indicator_metrics, strip_form_suffix,
    )
    from app.db.goals_queries import all_area_transfer_goals
    from app.db.queries import (
        get_config_value, get_daily_log, get_ki_goals_for_week, get_weekly_ki,
    )
    from app.utils.area_helpers import compliance_anchor_date, mission_today

    today = today or mission_today()

    weekly_ki = get_weekly_ki()
    if not weekly_ki.empty:
        weekly_ki = weekly_ki.copy()
        weekly_ki["_area"] = weekly_ki["area"].astype(str).str.strip()
        weekly_ki["_week"] = weekly_ki["week_end_date"].astype(str).str[:10]

    daily = get_daily_log(HISTORY_DAYS)
    if not daily.empty:
        daily = daily.copy()
        daily["_area"] = daily["Area"].astype(str).str.strip()
        daily["_day"] = daily["Date"].astype(str).str[:10]

    ki_keys = tuple(key_indicator_metrics())
    return ReportData(
        roster=S.load_roster(),
        weekly_ki=weekly_ki,
        daily_log=daily,
        transfer_goals=all_area_transfer_goals(),
        cycles=P.load_cycles(),
        ki_keys=ki_keys,
        # The mission's own Spanish names, from QUESTIONS_CONFIG, without the
        # form's "(Real)" tail. Spanish literals, no t() — decision 3.
        labels={k: strip_form_suffix(format_metric_label(k, "es"))
                for k in ki_keys},
        mission_name=get_config_value("MISSION_NAME", flavor.display_name),
        today=today,
        anchor=compliance_anchor_date(),
        ki_goals_fn=get_ki_goals_for_week,
    )


# ── Building ──────────────────────────────────────────────────────────────────

def _weekly_rows(data: ReportData, scope: S.Scope,
                 period: P.Period) -> pd.DataFrame:
    """WEEKLY_KI rows for this unit's areas in this period's complete weeks.

    Membership is the roster's, never the row's own Zone column — an area that
    transferred would otherwise keep reporting under the zone it left.
    """
    df = data.weekly_ki
    if df is None or df.empty or not period.weeks:
        return pd.DataFrame()
    weeks = {w.isoformat() for w in period.weeks}
    return df[df["_week"].isin(weeks) & df["_area"].isin(set(scope.areas))]


def _reported_by_week(rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {}
    return rows.groupby("_week")["_area"].nunique().to_dict()


def _nightly_coverage(data: ReportData, scope: S.Scope,
                      period: P.Period) -> NightlyCoverage:
    """Area-days filed against area-days possible over the period's own days.

    The window is the period's elapsed DAYS, not its complete weeks: the
    nightly form is filed every night, and a period two days into its third
    week has two more days that could have been reported.

    It stops at `data.anchor`, not at the period's end. The last day is not a
    miss until the evening refresh has run — `area_helpers.compliance_anchor_date`,
    the same 9:30 PM cutoff every compliance figure in this app already uses.
    Without it a packet built on a Monday morning counts 45 unfiled reports
    against the mission for a day that has barely started.
    """
    end = min(period.end, data.anchor)
    days = (end - period.start).days + 1
    possible = max(0, days) * scope.area_count
    df = data.daily_log
    if df is None or df.empty or days <= 0:
        return NightlyCoverage(max(0, possible), 0, 0, scope.area_count)
    window = df[(df["_day"] >= period.start.isoformat())
                & (df["_day"] <= end.isoformat())
                & df["_area"].isin(set(scope.areas))]
    return NightlyCoverage(
        days_possible=possible,
        days_reported=len(window),
        areas_reporting=int(window["_area"].nunique()) if not window.empty else 0,
        areas_in_scope=scope.area_count,
    )


def _leadership_goals(data: ReportData, scope: S.Scope,
                      period: P.Period) -> dict:
    """`{metric: (value, areas_with_goals, complete)}` — decision 11's mark.

    AREA_TRANSFER_GOALS is set per CYCLE. A period is pro-rated across every
    cycle it touches, by the share of that cycle's weeks it covers: two weeks
    of a six-week cycle carry a third of its goal. A period spanning two cycles
    takes a share of each, which is how "Mes calendario" and "Año" resolve at
    all. This is `transfer_year.prorate`'s rule — a goal is a target spread
    evenly across a cycle — applied to weeks rather than days, because a cycle
    is a whole number of weekly rows and the report is keyed in weeks.

    `complete` is False unless EVERY area in scope has a goal in EVERY cycle
    the period touches — see `MetricRow.has_leadership_goal`.
    """
    from app.analytics.transfer_year import weeks_in_cycle

    df = data.transfer_goals
    if df is None or df.empty:
        return {}
    mine = df[df["area"].isin(set(scope.areas))]

    by_cycle: dict = {}
    for week in period.weeks:
        for cycle in data.cycles:
            if cycle["start"] <= week <= cycle["end"]:
                by_cycle.setdefault(cycle["start"], [cycle, 0])[1] += 1
                break

    metrics = [k for k in data.ki_keys if k in mine.columns]
    out: dict = {}
    min_areas = None
    complete = bool(by_cycle)
    for start, (cycle, n_weeks) in by_cycle.items():
        span = weeks_in_cycle(cycle["start"], cycle["end"]) or 1
        share = n_weeks / span
        rows = mine[mine["transfer_start"] == start.isoformat()]
        # An area counts as having a goal when ANY of its seven is non-zero —
        # `goals_queries.areas_with_goals`' rule, and the same basis every
        # summed total in this app is captioned with.
        n = int((rows[metrics].sum(axis=1) > 0).sum()) if not rows.empty else 0
        min_areas = n if min_areas is None else min(min_areas, n)
        complete = complete and n == scope.area_count
        for key in metrics:
            out[key] = out.get(key, 0.0) + float(rows[key].sum()) * share
    return {k: (v, min_areas or 0, complete) for k, v in out.items()}


def _ki_rows(data: ReportData, scope: S.Scope, period: P.Period, *,
             comparison: P.Comparison | None = None,
             flags: dict | None = None) -> list[MetricRow]:
    """The seven, always — present as a row even when nothing was reported.

    A Key Indicator that vanishes from the table because no one filed is a
    Key Indicator nobody asks about. Decision 10 is a standing rule, not a
    filter.
    """
    rows = _weekly_rows(data, scope, period)
    weeks = len(period.weeks)
    active_area_weeks = scope.area_count * weeks
    reporting_area_weeks = len(rows)

    before_rows = pd.DataFrame()
    before_area_weeks = 0
    if comparison and comparison.period is not None:
        before_rows = _weekly_rows(data, scope, comparison.period)
        before_area_weeks = len(before_rows)

    marks = _leadership_goals(data, scope, period)

    # The companionships' own goals, summed across the period's weeks. Each
    # week's goal lives on the PREVIOUS week's form (queries.py's W-7 lookup).
    # The divisor is how many areas FILED that source week — not how many wrote
    # a number in this particular box, which is `set_by` and is a caption.
    metas: dict = {}
    meta_set_by: dict = {}
    meta_area_weeks = 0
    frozen_areas = frozenset(scope.areas)
    for week in period.weeks:
        goals, set_by, _, source_areas = data.ki_goals_for_week(week, frozen_areas)
        meta_area_weeks += int(source_areas or 0)
        for key, value in goals.items():
            metas[key] = metas.get(key, 0.0) + float(value)
            meta_set_by[key] = meta_set_by.get(key, 0) + int(set_by.get(key, 0))

    out: list[MetricRow] = []
    for key in data.ki_keys:
        actual = (float(pd.to_numeric(rows[key], errors="coerce").sum())
                  if not rows.empty and key in rows.columns else None)
        before = (float(pd.to_numeric(before_rows[key], errors="coerce").sum())
                  if not before_rows.empty and key in before_rows.columns else None)

        per_reporting = (actual / reporting_area_weeks
                         if actual is not None and reporting_area_weeks else None)
        per_active = (actual / active_area_weeks
                      if actual is not None and active_area_weeks else None)
        before_rate = (before / before_area_weeks
                       if before is not None and before_area_weeks else None)

        # A key absent from every week's goals, while areas DID file the source
        # form, is a real commitment to zero — not a missing goal. Zero cannot
        # be graded against, so it reads 0 with no status, which is the truth.
        meta = metas.get(key, 0.0) if meta_area_weeks else None
        meta_rate = meta / meta_area_weeks if meta else None
        mark, mark_areas, mark_complete = marks.get(key, (None, 0, False))

        out.append(MetricRow(
            key=key,
            label=data.labels.get(key, key),
            actual=actual,
            actual_area_weeks=reporting_area_weeks,
            meta=meta,
            meta_area_weeks=meta_area_weeks,
            meta_set_by=meta_set_by.get(key, 0),
            leadership_goal=mark,
            leadership_goal_areas=mark_areas,
            leadership_goal_complete=mark_complete,
            per_active_area_week=per_active,
            per_reporting_area_week=per_reporting,
            before_per_reporting_area_week=before_rate,
            # Attainment and change are both on the per-reporting-area basis:
            # the only one where a swing in how many areas filed cannot read as
            # work. 39 areas set the goals for the week ending 2026-09-20 and 27
            # filed results for it — dividing those two sums would be the 2.040%
            # bug again.
            grade=grade_ki(per_reporting, meta_rate, before=before_rate,
                           flag=(flags or {}).get(key)),
        ))
    return out


def build_report(scope: S.Scope, period: P.Period, comparison: P.Comparison,
                 data: ReportData) -> ReportModel:
    """One unit, one period, every number its pages need. Pure over `data`."""
    rows = _weekly_rows(data, scope, period)
    reporting = (set(rows["_area"]) if not rows.empty else set())
    in_scope = set(scope.areas)

    coverage = P.week_coverage(period, _reported_by_week(rows), scope.area_count)
    comparison_coverage = None
    if comparison and comparison.period is not None:
        comparison_coverage = P.week_coverage(
            comparison.period,
            _reported_by_week(_weekly_rows(data, scope, comparison.period)),
            scope.area_count)

    return ReportModel(
        scope=scope,
        period=period,
        comparison=comparison,
        mission_name=data.mission_name,
        today=data.today,
        coverage=coverage,
        comparison_coverage=comparison_coverage,
        nightly_coverage=_nightly_coverage(data, scope, period),
        areas_reporting=tuple(sorted(reporting & in_scope)),
        areas_silent=tuple(sorted(in_scope - reporting)),
        key_indicators=tuple(_ki_rows(data, scope, period,
                                      comparison=comparison,
                                      flags=data.ki_goal_flags(period))),
    )


def build_all(period_key: str = P.DEFAULT_PERIOD,
              against: str = P.COMPARE_PRIOR,
              data: ReportData | None = None) -> list[ReportModel]:
    """Every scope the packet prints, in packet order (PLAN §3.2).

    63 models on CCSM today: the mission, 4 zones, 13 districts, 45 areas.
    """
    data = data or load_data()
    period = P.resolve(period_key, data.today, data.cycles)
    if period is None:
        return []
    comparison = P.comparison_for(period, data.today, data.cycles,
                                  against=against)
    return [build_report(s, period, comparison, data)
            for s in S.walk(data.roster, data.mission_name)]
