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
  ``per_reporting_area_week``  the sum over the area-weeks (or area-days) that
                               actually filed. The only basis where a swing in
                               how many areas reported cannot masquerade as
                               work, so every CHANGE is computed on it.
                               Measured 2026-09-21: `contacts_attempted` rose
                               19.3% between two weeks per active area and 2.6%
                               per reporting area. The second is the true one.
  ``per_active_area_week``     the sum over every roster area, reporting or not.
                               The basis for comparing UNITS (decision 12), where
                               a zone whose areas go silent should rank lower on
                               purpose — `zone_comparison`'s standing rule.

**Attainment takes whichever basis matches its own goal's population.** A Key
Indicator's goal is the companionships' own summed meta, whose population is the
areas that filed the goal form, so the result is reduced the same way — per
reporting area-week. A nightly goal is one mission-wide `GOAL_*` number per area
per week, whose population is every active area, so the result is reduced over
all of them; an unreported night is work nobody recorded, and counting it as
work would flatter. That is also the basis §1.1 measured on and the one decision
22's 25% floor was calibrated against.

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
from app.reports.grading import (
    Grade, attainment, goal_is_unusable, grade_ki, grade_nightly,
)

#: How much DAILY_LOG history to pull. The `days` argument is a client-side
#: filter — `read_tab` reads and caches the whole tab either way — so a wide
#: window costs no extra Sheets read and lets any period resolve.
HISTORY_DAYS = 3650

#: The nightly form's YESNO question. DAILY_LOG stores "TRUE" or a blank, so it
#: is reported as the number of NIGHTS an exchange happened — a real figure,
#: where summing a word would be nothing at all.
EXCHANGES = "exchanges"
EXCHANGE_TRUE = "TRUE"

#: The nightly form's CHOICE question (Todo / La mayor parte / Algo) as the
#: agents already score it, 1 to 3, in WEEKLY_BREAKDOWNS. Averaged across areas
#: and weeks, never summed — it is a rate, and forty areas' scores added
#: together is a number with no meaning.
EFFORT_SCORE = "effort_score"

#: The four Effectiveness components, in SCORES' own order (decision 18).
SCORE_COLS = ("Effort_Score", "Skill_Score", "KI_Score", "Effectiveness_Score")

#: WEEKLY_BREAKDOWNS' own pick of what an area is strong at and what it is
#: growing. The Apps Script agents choose these; the report READS them and must
#: not recompute them (§1.2).
STRENGTH_COLS = ("strength1_metric", "strength2_metric")
GROWTH_COL = "growth_metric"


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
    def usable(self) -> bool:
        """Whether any night was filed in this window at all.

        The nightly twin of `periods.Coverage.usable`, and needed for the same
        reason: DAILY_LOG begins 2026-08-09, so the default comparison for the
        current transfer — the first two weeks of 2026-5 — holds almost no
        nights. A change computed across it is arithmetic over one area's
        evening, and the row has to be able to say so.
        """
        return self.days_reported > 0

    @property
    def thin(self) -> bool:
        """Reported so sparsely that a figure over it is one or two areas.

        Same quarter-of-possible floor as `periods.Coverage.thin`, and for the
        same measured reason: CCSM's real nightly weeks run 68%–72% of possible
        area-days, while the windows this catches are a rounding error away
        from empty.
        """
        return self.rate is not None and self.rate < P.THIN_REPORTING_RATE

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
    def attainment_per_active_area(self) -> float | None:
        """Attainment reduced over EVERY roster area, silent ones included.

        `grade.pct` is the unit's own reading, on the population that filed.
        This is the cross-UNIT reading (decision 12), and the two are
        different numbers: a zone where seven of eleven areas went quiet is at
        59% of goal among those that reported and 26% of the zone. A table
        comparing units has to use this one, or its rows do not add up to the
        headline beside them.
        """
        return attainment(self.per_active_area_week, self.meta_per_area_week)

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


# ── Scores, series, children ──────────────────────────────────────────────────

@dataclass(frozen=True)
class Scores:
    """SCORES' four numbers over the period, and where the unit sits.

    Averaged across the period's scored weeks and across the unit's areas. An
    area the scoring agent wrote no row for contributes nothing rather than a
    zero: "not scored yet" and "scored zero" are different claims, and
    `CCSM_AgentScores` writes a genuine 0.0 for a week an area had no goals to
    be scored against.

    ``rank`` / ``of`` are filled at AREA level only — the area's place among
    its district's areas, on Effectiveness (decision 18). That is SCORES' own
    composite and the ranking Puntajes already shows; the CHILDREN table ranks
    on mean Key Indicator attainment instead, because a composite of a
    composite cannot be explained in a council (decision 14).
    """

    effort: float | None = None
    skill: float | None = None
    ki: float | None = None
    effectiveness: float | None = None
    areas_scored: int = 0
    weeks: int = 0
    rank: int | None = None
    of: int | None = None

    @property
    def measured(self) -> bool:
        return self.areas_scored > 0


@dataclass(frozen=True)
class SeriesPoint:
    """One complete week of a metric, for the week-by-week strip."""

    week: date
    actual: float | None
    reporting: int
    per_reporting_area: float | None = None


@dataclass(frozen=True)
class Series:
    """A metric's weeks, with the transfer boundaries it crosses (decision 9).

    ``boundaries`` are `(date, cycle number)`. On a weekly axis each falls
    BETWEEN two Sundays — 2026-09-07 sits between the weeks ending 09-06 and
    09-13 — and placing it there is the renderer's business.
    """

    key: str
    label: str
    points: tuple[SeriesPoint, ...] = ()
    boundaries: tuple[tuple[date, str], ...] = ()

    @property
    def reported_points(self) -> tuple[SeriesPoint, ...]:
        return tuple(p for p in self.points if p.actual is not None)


@dataclass(frozen=True)
class ChildRow:
    """One unit a level down, ranked and named (decisions 14, 15, 16).

    ``mean_attainment`` is the mean of the unit's Key Indicator percentages —
    not Effectiveness. A council can be told "this zone is at 54% of the goals
    its companionships set themselves"; nobody can explain a composite of a
    composite out loud.

    ``rank`` is 1 for the WEAKEST, because that is the order the table prints
    in and the order a council reads down.
    """

    scope: S.Scope
    rank: int
    mean_attainment: float | None
    metrics: tuple[MetricRow, ...] = ()
    coverage: P.Coverage = None
    areas_silent: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self.scope.name


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
    comparison_nightly_coverage: NightlyCoverage | None = None

    #: Roster areas that filed a weekly form in the period, and those that did
    #: not. The silent list is named, at every level, including the mission
    #: (decision 16).
    areas_reporting: tuple[str, ...] = ()
    areas_silent: tuple[str, ...] = ()

    #: The seven, always, in the catalogue's order (decision 10).
    key_indicators: tuple[MetricRow, ...] = ()

    #: Every tracked nightly metric (decision 17), weakest first is the
    #: renderer's business — here they keep the catalogue's order.
    nightly_metrics: tuple[MetricRow, ...] = ()

    #: The four scores and, at area level, where the area ranks in its
    #: district (decision 18).
    scores: "Scores | None" = None

    #: The four conversion rates (decision 13). Empty below zone level, where
    #: a ratio over one companionship's fortnight is noise.
    rates: tuple = ()

    #: The units one level down, weakest first (decisions 14, 15).
    children: tuple = ()

    #: Every AREA inside the unit, weakest first. Mission and zone only — at
    #: district level the areas are already `children`.
    areas_ranked: tuple = ()

    #: `{metric key: Series}` for the seven, week by week (decision 26).
    series: dict = field(default_factory=dict)

    #: What this companionship is strong at and what they are growing —
    #: WEEKLY_BREAKDOWNS' own choice, read and never recomputed (§1.2).
    strengths: tuple[str, ...] = ()
    growth: str | None = None

    # ── Filled by phase T ────────────────────────────────────────────────────
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

    @property
    def nightly_weakest_first(self) -> tuple[MetricRow, ...]:
        """Decision 17's table order: furthest from its goal at the top.

        Attainment, not movement — the ORDER is about which metric is furthest
        behind, while the row's colour is about which way it moved (decision
        31). A metric with no goal to be measured against sorts to the end
        rather than to the top: it is not the weakest, it is unmeasured.

        Lives on the model rather than in either renderer, so the screen and
        the printed page list them in the same order.
        """
        return tuple(sorted(
            self.nightly_metrics,
            key=lambda r: (r.grade.pct is None,
                           r.grade.pct if r.grade.pct is not None else 0,
                           r.label),
        ))


# ── Loading ───────────────────────────────────────────────────────────────────

@dataclass
class ReportData:
    """Every frame the model reads, loaded once and shared by 63 scopes.

    Not frozen: it memoises the two lookups that would otherwise be repeated
    per scope — the W-7 goal read and the mission-scope verdict on whether a
    goal is a usable yardstick.
    """

    roster: pd.DataFrame
    today: date

    #: Everything below defaults to empty. A caller that only exercises Key
    #: Indicators should not have to hand in a SCORES frame to do it, and a
    #: mission that has never run the scoring agent should get a report with
    #: an empty scores block rather than an exception.
    weekly_ki: pd.DataFrame = field(default_factory=pd.DataFrame)
    daily_log: pd.DataFrame = field(default_factory=pd.DataFrame)
    breakdowns: pd.DataFrame = field(default_factory=pd.DataFrame)
    scores: pd.DataFrame = field(default_factory=pd.DataFrame)
    transfer_goals: pd.DataFrame = field(default_factory=pd.DataFrame)
    cycles: list[dict] = field(default_factory=list)
    ki_keys: tuple[str, ...] = ()
    nightly_keys: tuple[str, ...] = ()
    nightly_goals: dict = field(default_factory=dict)
    agent_config: dict = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    mission_name: str = S.DEFAULT_MISSION_NAME
    #: The last day that counts toward nightly compliance — today once the
    #: evening refresh has run, yesterday before it. Resolved once at load so
    #: `build_report` stays pure and a packet cannot straddle the 9:30 PM
    #: cutoff halfway through its 63 scopes. Defaults to `today`.
    anchor: date | None = None
    #: `queries.get_ki_goals_for_week`, injected rather than imported so a test
    #: can hand in a week's goals without a sheet. The W-7 rule it implements —
    #: a week's goals are written on the PREVIOUS week's form — stays in
    #: queries.py, where it has one home and one set of tests.
    ki_goals_fn: object = None
    _goals: dict = field(default_factory=dict, repr=False)
    _flags: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        if self.anchor is None:
            self.anchor = self.today

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
        cache_key = ("ki", period.key)
        if cache_key not in self._flags:
            mission = S.mission_scope(self.roster, self.mission_name)
            rows = _ki_rows(self, mission, period)
            self._flags[cache_key] = {
                r.key: goal_is_unusable(r.per_reporting_area_week,
                                        r.meta_per_area_week)
                for r in rows
            }
        return self._flags[cache_key]

    def nightly_goal_flags(self, period: P.Period) -> dict:
        """The same verdict for the nightly `GOAL_*` numbers.

        Judged on attainment per ACTIVE area-week, which is the basis §1.1
        measured and the basis decision 22's 25% floor was calibrated against:
        it catches `rc_lessons_mcp` at 6.4% and `baptismal_calendars` at 21.7%
        and nothing else. On the reporting basis every figure rises by about
        forty per cent and only one of the two would flag.
        """
        cache_key = ("nightly", period.key)
        if cache_key not in self._flags:
            mission = S.mission_scope(self.roster, self.mission_name)
            self._flags[cache_key] = {
                r.key: goal_is_unusable(r.per_active_area_week,
                                        self.nightly_goals.get(r.key))
                for r in _nightly_rows(self, mission, period)
            }
        return self._flags[cache_key]


def _key_columns(df: pd.DataFrame, area: str, day: str,
                 out_day: str = "_day") -> pd.DataFrame:
    """A frame with `_area` and a normalised date column, stripped once.

    Every membership test downstream compares against the roster's stripped
    names, and SCORES, DAILY_LOG and WEEKLY_BREAKDOWNS all carry stray
    whitespace. Doing it here means no per-scope filter pays for it 63 times.
    """
    if df is None or df.empty or area not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    out["_area"] = out[area].astype(str).str.strip()
    out[out_day] = (out[day].astype(str).str.strip().str[:10]
                    if day in out.columns else "")
    return out


def _restore_exchanges(daily: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Put `exchanges` back as a 1/0 night count.

    `get_daily_log` runs every metric column through `_num`, which coerces an
    unparseable value to NaN and then fills it with 0 — so a YESNO column
    arrives as a wall of zeros with nothing about the values revealing they
    were never numbers. The same trap `non_numeric_metrics` documents. The raw
    tab stores "TRUE" or a blank, which is a real count of nights, so it is
    re-derived here from the unconverted frame and merged back on (day, area).
    """
    if daily is None or daily.empty or raw is None or raw.empty:
        return daily
    if not {"Date", "Area", EXCHANGES} <= set(raw.columns):
        return daily
    flags = _key_columns(raw[["Date", "Area", EXCHANGES]], "Area", "Date")
    flags[EXCHANGES] = (flags[EXCHANGES].astype(str).str.strip().str.upper()
                        == EXCHANGE_TRUE).astype(int)
    flags = flags[["_day", "_area", EXCHANGES]].drop_duplicates(
        subset=["_day", "_area"])
    out = daily.drop(columns=[EXCHANGES], errors="ignore").merge(
        flags, on=["_day", "_area"], how="left")
    out[EXCHANGES] = out[EXCHANGES].fillna(0)
    return out


def load_data(today: date | None = None) -> ReportData:
    """Read every source once. The only impure function in this module."""
    from app.config.flavor_loader import flavor
    from app.config.metric_catalog import (
        format_metric_label, key_indicator_metrics, nightly_metrics,
        non_numeric_metrics, strip_form_suffix,
    )
    from app.db.goals_queries import all_area_transfer_goals
    from app.db.queries import (
        get_agent_config, get_area_weekly_goals, get_config_value,
        get_daily_log, get_ki_goals_for_week, get_scores, get_weekly_ki,
    )
    from app.db.sheets_client import read_tab
    from app.utils.area_helpers import compliance_anchor_date, mission_today

    today = today or mission_today()

    weekly_ki = _key_columns(get_weekly_ki(), "area", "week_end_date", "_week")
    daily = _key_columns(get_daily_log(HISTORY_DAYS), "Area", "Date")
    daily = _restore_exchanges(daily, read_tab("DAILY_LOG"))
    breakdowns = _key_columns(read_tab("WEEKLY_BREAKDOWNS"), "area",
                              "week_end_date", "_week")
    scores = _key_columns(get_scores(), "Area_Name", "Week_Ending_Date", "_week")

    ki_keys = tuple(key_indicator_metrics())
    skip = non_numeric_metrics()
    # Every tracked nightly metric (decision 17), in the form's own order.
    # `exchanges` and `effort` are not summable — see `_nightly_rows`, which
    # reports each of them the way its own data allows rather than dropping it.
    nightly_keys = tuple(k for k in nightly_metrics() if k not in skip)
    nightly_keys += tuple(k for k in (EXCHANGES, EFFORT_SCORE)
                          if k not in nightly_keys)

    # The four conversion rates get labels too: WEEKLY_BREAKDOWNS names one of
    # them as an area's strength, and "contact_rate" is not a thing to print in
    # a council packet.
    from app.analytics.rate_metrics import RATE_METRICS
    labelled = ki_keys + nightly_keys + tuple(m.key for m in RATE_METRICS)
    labels = {k: strip_form_suffix(format_metric_label(k, "es"))
              for k in labelled}
    labels.setdefault(EFFORT_SCORE, "Nivel de Esfuerzo (1–3)")

    return ReportData(
        roster=S.load_roster(),
        weekly_ki=weekly_ki,
        daily_log=daily,
        breakdowns=breakdowns,
        scores=scores,
        transfer_goals=all_area_transfer_goals(),
        cycles=P.load_cycles(),
        ki_keys=ki_keys,
        nightly_keys=nightly_keys,
        nightly_goals=get_area_weekly_goals(),
        agent_config=get_agent_config(),
        # The mission's own Spanish names, from QUESTIONS_CONFIG, without the
        # form's "(Real)" tail. Spanish literals, no t() — decision 3.
        labels=labels,
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


# ── Nightly (decision 17) ─────────────────────────────────────────────────────

def _daily_window(data: ReportData, scope: S.Scope, start: date,
                  end: date) -> pd.DataFrame:
    df = data.daily_log
    if df is None or df.empty or end < start:
        return pd.DataFrame()
    return df[(df["_day"] >= start.isoformat()) & (df["_day"] <= end.isoformat())
              & df["_area"].isin(set(scope.areas))]


def _nightly_totals(rows: pd.DataFrame, key: str) -> float | None:
    """One metric summed over a window of nights, or None if it is not there.

    `exchanges` sums as a count of nights, because `_restore_exchanges` has
    already turned the YESNO word into a 1 or a 0. `effort_score` is not in
    DAILY_LOG at all — the agents write it per week into WEEKLY_BREAKDOWNS —
    and is handled by its caller.
    """
    if rows.empty or key not in rows.columns:
        return None
    return float(pd.to_numeric(rows[key], errors="coerce").sum())


def _effort_score(data: ReportData, scope: S.Scope,
                  period: P.Period) -> tuple[float | None, int]:
    """The agents' own 1–3 effort score, averaged over the unit's area-weeks."""
    df = data.breakdowns
    if df is None or df.empty or EFFORT_SCORE not in df.columns:
        return None, 0
    weeks = {w.isoformat() for w in period.weeks}
    rows = df[df["_week"].isin(weeks) & df["_area"].isin(set(scope.areas))]
    values = pd.to_numeric(rows[EFFORT_SCORE], errors="coerce").dropna()
    return (float(values.mean()) if len(values) else None), len(values)


def _nightly_rows(data: ReportData, scope: S.Scope, period: P.Period, *,
                  comparison: P.Comparison | None = None,
                  flags: dict | None = None) -> list[MetricRow]:
    """Every tracked nightly metric for the unit — decision 17's whole table.

    **Two bases, each matched to what it is being compared with.** Attainment
    divides by every ACTIVE area-week, because the goal is one mission-wide
    `GOAL_*` number per area per week and an unreported night is work nobody
    recorded. That is the basis §1.1 measured on, the basis decision 22's 25%
    floor was calibrated against, and it reads `contacts_attempted` at 65% of
    goal rather than the 90% the reporting basis would flatter it to.

    The CHANGE divides by the area-DAYS that actually filed. Nightly reporting
    rose from 35 of 45 areas to 45 of 45 over six weeks; on the active basis
    that swing alone moves `contacts_attempted` 19.3% between two weeks, and
    on the reporting basis it moves 2.6%. Only the second is work.
    """
    end = min(period.end, data.anchor)
    rows = _daily_window(data, scope, period.start, end)
    weeks = len(period.weeks) or 1
    active_area_weeks = scope.area_count * weeks
    area_days = len(rows)

    before_rows = pd.DataFrame()
    before_days = 0
    if comparison and comparison.period is not None:
        cp = comparison.period
        before_rows = _daily_window(data, scope, cp.start,
                                    min(cp.end, data.anchor))
        before_days = len(before_rows)

    effort, effort_basis = _effort_score(data, scope, period)

    out: list[MetricRow] = []
    for key in data.nightly_keys:
        goal = data.nightly_goals.get(key)
        if key == EFFORT_SCORE:
            # A rate: already per area-week, so it is its own basis and the
            # active/reporting split does not apply.
            before_effort, _ = (_effort_score(data, scope, comparison.period)
                                if comparison and comparison.period else (None, 0))
            out.append(MetricRow(
                key=key, label=data.labels.get(key, key),
                actual=effort, actual_area_weeks=effort_basis,
                per_active_area_week=effort, per_reporting_area_week=effort,
                before_per_reporting_area_week=before_effort,
                grade=grade_nightly(effort, goal, before=before_effort),
            ))
            continue

        actual = _nightly_totals(rows, key)
        before = _nightly_totals(before_rows, key)
        per_active = (actual / active_area_weeks
                      if actual is not None and active_area_weeks else None)
        now_rate = (actual * 7 / area_days
                    if actual is not None and area_days else None)
        before_rate = (before * 7 / before_days
                       if before is not None and before_days else None)
        out.append(MetricRow(
            key=key, label=data.labels.get(key, key),
            actual=actual, actual_area_weeks=area_days,
            per_active_area_week=per_active,
            per_reporting_area_week=now_rate,
            before_per_reporting_area_week=before_rate,
            grade=grade_nightly(per_active, goal, before=before_rate,
                                now=now_rate, flag=(flags or {}).get(key)),
        ))
    return out


# ── Scores (decision 18) ──────────────────────────────────────────────────────

def _score_frame(data: ReportData, areas, period: P.Period) -> pd.DataFrame:
    df = data.scores
    if df is None or df.empty:
        return pd.DataFrame()
    weeks = {w.isoformat() for w in period.weeks}
    return df[df["_week"].isin(weeks) & df["_area"].isin(set(areas))]


def _scores(data: ReportData, scope: S.Scope, period: P.Period) -> Scores:
    rows = _score_frame(data, scope.areas, period)
    if rows.empty:
        return Scores(weeks=len(period.weeks))

    means = {c: (float(pd.to_numeric(rows[c], errors="coerce").mean())
                 if c in rows.columns else None)
             for c in SCORE_COLS}
    rank = of = None
    if scope.level == S.AREA and scope.district:
        # The area's place among its district's areas, weakest LAST — a rank of
        # 1 is the district's strongest, which is how Puntajes already reads.
        siblings = S.area_scopes(data.roster, zone=scope.zone,
                                 district=scope.district)
        peers = _score_frame(data, [s.name for s in siblings], period)
        if not peers.empty and "Effectiveness_Score" in peers.columns:
            by_area = (peers.groupby("_area")["Effectiveness_Score"]
                       .mean().sort_values(ascending=False))
            of = len(by_area)
            if scope.name in by_area.index:
                rank = int(list(by_area.index).index(scope.name)) + 1
    return Scores(
        effort=means.get("Effort_Score"), skill=means.get("Skill_Score"),
        ki=means.get("KI_Score"), effectiveness=means.get("Effectiveness_Score"),
        areas_scored=int(rows["_area"].nunique()), weeks=len(period.weeks),
        rank=rank, of=of,
    )


# ── Conversion rates (decision 13) ───────────────────────────────────────────

def _rates(data: ReportData, scope: S.Scope, period: P.Period,
           comparison: P.Comparison | None) -> tuple:
    """The four conversion rates, at mission and zone only.

    Decision 13 puts them at those two levels, and the arithmetic says why: a
    close rate over one companionship's fortnight of three lessons is a
    ratio of two small integers. `rate_metrics` owns the rules — the mission
    rate is the ratio of totals rather than the mean of the areas' own rates,
    and a missing denominator is no reading rather than zero.
    """
    from app.analytics.rate_metrics import rate_rows

    if scope.level not in (S.MISSION, S.ZONE):
        return ()
    end = min(period.end, data.anchor)
    rows = _daily_window(data, scope, period.start, end)
    prior = pd.DataFrame()
    prior_days = 0
    if comparison and comparison.period is not None:
        cp = comparison.period
        prior = _daily_window(data, scope, cp.start, min(cp.end, data.anchor))
        prior_days = int(prior["_day"].nunique()) if not prior.empty else 0

    def totals(frame):
        if frame.empty:
            return {}
        return {c: float(pd.to_numeric(frame[c], errors="coerce").sum())
                for c in frame.columns if c not in ("_area", "_day")}

    return tuple(rate_rows(
        totals(rows), totals(prior), data.agent_config,
        current_days=int(rows["_day"].nunique()) if not rows.empty else 0,
        prior_days=prior_days,
    ))


# ── Children, ranked weakest first (decisions 14, 15) ────────────────────────

def _mean_attainment(rows) -> float | None:
    """The mean of a unit's Key Indicator percentages, per ACTIVE area-week.

    **Not `grade.pct`**, which rests on the area-weeks that filed. Ranking one
    unit against another is exactly the comparison decision 12 reserves the
    active basis for: a zone of two areas where one filed one week and did 30
    reads 150% of goal per reporting area-week and would top the table, while
    per active area-week it reads 37.5% and is last, which is the truth about
    the zone. `zone_comparison`'s standing rule — a zone whose areas go silent
    ranks lower, on purpose.

    Only indicators that HAVE a percentage count. Treating an ungraded one as a
    zero would rank a unit down for a goal its companionships never set, which
    is a statement about the form and not about the work.
    """
    pcts = [p for p in (r.attainment_per_active_area for r in rows)
            if p is not None]
    return sum(pcts) / len(pcts) if pcts else None


def _rank_scopes(data: ReportData, scopes: list, period: P.Period,
                 comparison: P.Comparison | None, flags: dict) -> tuple:
    """Units ranked weakest first — no top-N (decision 15).

    Ranked on mean Key Indicator attainment (decision 14). A unit with no
    attainment at all sorts to the END rather than to the top: it is not the
    weakest, it is unmeasured, and printing it first would put "no data" where
    a council looks for its biggest problem.
    """
    out = []
    for child in scopes:
        rows = _ki_rows(data, child, period, comparison=comparison, flags=flags)
        child_rows = _weekly_rows(data, child, period)
        reported = set(child_rows["_area"]) if not child_rows.empty else set()
        out.append(ChildRow(
            scope=child, rank=0, mean_attainment=_mean_attainment(rows),
            metrics=tuple(rows),
            coverage=P.week_coverage(period, _reported_by_week(child_rows),
                                     child.area_count),
            areas_silent=tuple(sorted(set(child.areas) - reported)),
        ))
    out.sort(key=lambda c: (c.mean_attainment is None,
                            c.mean_attainment if c.mean_attainment is not None else 0,
                            c.scope.name))
    from dataclasses import replace
    return tuple(replace(c, rank=i + 1) for i, c in enumerate(out))


def _areas_ranked(data: ReportData, scope: S.Scope, period: P.Period,
                  comparison: P.Comparison | None, flags: dict) -> tuple:
    """Every AREA inside the unit, weakest first — §3.2's Z3, and the drawer
    the mission page keeps 45 of them behind (decision 15).

    Empty at district level, where the areas ARE the children and the same
    list twice is noise, and at area level, which has no areas below it.
    """
    if scope.child_level != S.DISTRICT and scope.level != S.MISSION:
        return ()
    scopes = S.area_scopes(data.roster,
                           zone=scope.zone if scope.level == S.ZONE else None)
    return _rank_scopes(data, scopes, period, comparison, flags)


# ── The week-by-week strip (decisions 9, 26) ─────────────────────────────────

def _series(data: ReportData, scope: S.Scope, period: P.Period) -> dict:
    """One `Series` per Key Indicator, over the period's complete weeks.

    Built from `data.weekly_ki` — the SAME frame the cards above are summed
    from. `analytics/ki_history.weekly_series` answers a near-identical
    question and is deliberately NOT used here: it reads WEEKLY_FORM_RAW,
    which carries five area names that are not on the roster and runs a few
    areas ahead of WEEKLY_KI in the newest week. A card reading 364 above a
    strip totalling 430 is the one failure this whole layer exists to prevent.
    """
    rows = _weekly_rows(data, scope, period)
    bounds = P.transfer_boundaries(data.cycles, period.start, period.end)
    out: dict = {}
    for key in data.ki_keys:
        points = []
        for week in period.weeks:
            wk = (rows[rows["_week"] == week.isoformat()]
                  if not rows.empty else pd.DataFrame())
            reporting = int(wk["_area"].nunique()) if not wk.empty else 0
            actual = (float(pd.to_numeric(wk[key], errors="coerce").sum())
                      if reporting and key in wk.columns else None)
            points.append(SeriesPoint(
                week=week, actual=actual, reporting=reporting,
                per_reporting_area=(actual / reporting
                                    if actual is not None and reporting else None),
            ))
        out[key] = Series(key=key, label=data.labels.get(key, key),
                          points=tuple(points), boundaries=bounds)
    return out


# ── Strength and growth, read and never recomputed (§1.2) ────────────────────

def _strengths(data: ReportData, scope: S.Scope,
               period: P.Period) -> tuple[tuple[str, ...], str | None]:
    """What the agents chose as this companionship's strengths and growth edge.

    From the unit's most recent WEEKLY_BREAKDOWNS week inside the period. Area
    level only: the columns hold ONE area's judgement, and a zone made of nine
    of them has no such row.
    """
    if scope.level != S.AREA:
        return (), None
    df = data.breakdowns
    if df is None or df.empty:
        return (), None
    weeks = {w.isoformat() for w in period.weeks}
    rows = df[df["_week"].isin(weeks) & (df["_area"] == scope.name)]
    if rows.empty:
        return (), None
    row = rows.sort_values("_week").iloc[-1]

    def label(col):
        key = str(row.get(col, "") or "").strip()
        return data.labels.get(key, key) if key else ""

    strengths = tuple(s for s in (label(c) for c in STRENGTH_COLS) if s)
    return strengths, (label(GROWTH_COL) or None)


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

    ki_flags = data.ki_goal_flags(period)
    strengths, growth = _strengths(data, scope, period)

    return ReportModel(
        scope=scope,
        period=period,
        comparison=comparison,
        mission_name=data.mission_name,
        today=data.today,
        coverage=coverage,
        comparison_coverage=comparison_coverage,
        nightly_coverage=_nightly_coverage(data, scope, period),
        comparison_nightly_coverage=(
            _nightly_coverage(data, scope, comparison.period)
            if comparison and comparison.period is not None else None),
        areas_reporting=tuple(sorted(reporting & in_scope)),
        areas_silent=tuple(sorted(in_scope - reporting)),
        key_indicators=tuple(_ki_rows(data, scope, period,
                                      comparison=comparison, flags=ki_flags)),
        nightly_metrics=tuple(_nightly_rows(
            data, scope, period, comparison=comparison,
            flags=data.nightly_goal_flags(period))),
        scores=_scores(data, scope, period),
        rates=_rates(data, scope, period, comparison),
        children=_rank_scopes(data, S.children(data.roster, scope), period,
                              comparison, ki_flags),
        areas_ranked=_areas_ranked(data, scope, period, comparison, ki_flags),
        series=_series(data, scope, period),
        strengths=strengths,
        growth=growth,
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
