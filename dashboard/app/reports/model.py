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

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

import pandas as pd

from app.analytics.area_goals import weighted_goal

from app.reports import periods as P
from app.reports import tableau as TB
from app.reports import scope as S
from app.reports.grading import (
    Grade, attainment, goal_is_unusable, grade_ki, grade_nightly,
)

#: Below this share of a row's reporting area-weeks carrying a leadership
#: goal, the row is not graded at all — "sin meta del liderazgo" (decisions
#: 23, 44). A period straddling a cycle nobody set goals for would otherwise
#: be graded on a sliver of its weeks.
LEAD_MIN_SHARE = 0.5

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
    #: The last night the window counts — the period's end or the compliance
    #: anchor, whichever comes first. The nightly figures run to here while
    #: the Key Indicators stop at the last complete week, which is why the
    #: same name can carry two counts on one page (AUDIT-2026-10-06 H4).
    through: date | None = None

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

    #: The companionships' own summed goal for the period's weeks — the
    #: *compromiso*, printed and never coloured since decision 44.
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

    #: Leadership's AREA_TRANSFER_GOALS figure for EVERY area in scope,
    #: pro-rated to the part of the cycle this period covers (the graded
    #: figure is `lead_goal`, over the area-weeks that reported).
    leadership_goal: float | None = None
    leadership_goal_areas: int = 0
    leadership_goal_complete: bool = False

    #: Leadership's goal over exactly the area-weeks that REPORTED and have a
    #: goal, and the actual over those same area-weeks — the two sides the
    #: row is graded on since decision 44 (PLAN-2026-10-06, 1.1). Rule 1 of
    #: the Informes layer: both sides of a percentage rest on one population.
    #: ``lead_area_weeks`` is that population's size.
    lead_goal: float | None = None
    lead_actual: float | None = None
    lead_area_weeks: int = 0

    per_active_area_week: float | None = None
    per_reporting_area_week: float | None = None
    before_per_reporting_area_week: float | None = None
    #: A nightly row's goal per sector-week: the unit's sectors' own goals for
    #: the nights they filed, averaged (G10), or the mission-wide figure.
    goal_per_area_week: float | None = None

    grade: Grade = field(default_factory=Grade)

    @property
    def meta_per_area_week(self) -> float | None:
        if self.meta is None or not self.meta_area_weeks:
            return None
        return self.meta / self.meta_area_weeks

    @property
    def own_pct(self) -> float | None:
        """The companionships' own *compromiso*, as a percentage — printed,
        never coloured (decision 44). Per reporting area-week on both sides,
        which is the population the goal form was filed by."""
        return attainment(self.per_reporting_area_week,
                          self.meta_per_area_week)

    @property
    def lead_goal_rate(self) -> float | None:
        """Leadership's goal per reporting area-week, on the graded basis."""
        if self.lead_goal is None or not self.lead_area_weeks:
            return None
        return self.lead_goal / self.lead_area_weeks

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
class Productivity:
    """The goal-free productivity index (decision 45, PLAN P1).

    Output per ACTIVE companionship-week, each member as a percentage of the
    mission's own rate, averaged with weights toward the results nearest
    baptism. 100 is the mission; 120 is a unit producing a fifth more per
    companionship than the mission does. It says nothing about goals, which
    is the point: a unit that sets low goals cannot read well on it, and one
    that aims high is not punished for it (AUDIT-2026-10-06 C1).

    ``members`` is ``((key, ratio or None), ...)`` in catalogue order;
    ``events`` the raw count behind the members, and ``thin`` says it is too
    few to rank on with any confidence — printed, uncoloured.
    """

    value: float | None = None
    members: tuple = ()
    events: float = 0.0

    @property
    def thin(self) -> bool:
        return self.events < INDEX_MIN_EVENTS

    def ratio(self, key: str) -> float | None:
        return next((r for k, r in self.members if k == key), None)


#: P1, approved 2026-10-06. Baptismal dates weigh most: the result nearest
#: baptism with volume enough to trust. The form's baptisms are not a member —
#: seven events across the mission in a transfer (decision 37's reasoning).
INDEX_WEIGHTS = {
    "ki_baptismal_date_real": 3,
    "ki_friends_sacrament_real": 2,
    "ki_rc_at_church_real": 2,
    "ki_member_lessons_real": 1,
    "ki_new_people_real": 1,
    "ki_friends_first_week_real": 1,
}

#: A member's ratio is capped, so one tiny count cannot carry a unit: an area
#: with two baptismal dates where the mission averages 0,6 reads 330% on that
#: member alone.
INDEX_CAP = 250.0

#: Fewer events than this behind a unit's index and it is printed "pocas
#: cifras" — the same order of size as the small-count rule (25).
INDEX_MIN_EVENTS = 20.0

#: Never in the index, never coloured by leadership's transfer goal: the 527
#: annual goal is the baptism target (decision 46).
UNCOLOURED_KI = frozenset({"ki_baptized_confirmed_real"})


def index_weights(keys) -> dict:
    """`INDEX_WEIGHTS` over the keys a mission actually has. A catalogue
    with none of them (a different mission's Key Indicators) weighs every key
    but the form's baptisms equally, rather than having no index at all."""
    present = {k: w for k, w in INDEX_WEIGHTS.items() if k in keys}
    if present:
        return present
    return {k: 1 for k in keys if k not in UNCOLOURED_KI}


def productivity(rows, mission_rows) -> Productivity:
    """The index for one unit's Key Indicator rows against the mission's."""
    mission = {r.key: r.per_active_area_week for r in mission_rows}
    weights = index_weights([r.key for r in rows])
    members, total, weight, events = [], 0.0, 0.0, 0.0
    any_reading = False
    for row in rows:
        if row.key not in weights:
            continue
        base = mission.get(row.key)
        ratio = None
        if row.actual is not None:
            any_reading = True
            events += row.actual
        if base and row.per_active_area_week is not None:
            ratio = min(INDEX_CAP, row.per_active_area_week / base * 100)
            total += weights[row.key] * ratio
            weight += weights[row.key]
        members.append((row.key, ratio))
    value = total / weight if weight and any_reading else None
    return Productivity(value=value, members=tuple(members), events=events)


@dataclass(frozen=True)
class Forward:
    """What is coming, for one unit — decision 48 (PLAN-2026-10-06 Phase 2).

    ``finish`` is every Key Indicator's current transfer finished forward
    (`forecast.KIFinish`), mission and zone. ``year`` is the year's baptisms
    against the annual goal: certified at mission level, Tableau's person
    records at zone level against the zone's share of 527 (P2). ``pipeline``
    is the open baptismal dates and the baptisms they are likely to become in
    six weeks. ``baptisms`` is a zone's or district's baptisms in the period,
    from Tableau's records (decision 47). ``zones`` is the mission's pipeline
    by Tableau zone, all ten — the one place the export's own zone column is
    the authority (decision 24's precedent).
    """

    transfer: str = ""
    finish: tuple = ()
    year: object = None
    pipeline: object = None
    baptisms: object = None
    zones: tuple = ()
    #: How the same forecasts did before (PLAN 4C.1): the year's landing made
    #: at this month of earlier years, and the transfer finish's method run
    #: on Tableau's weekly milestones — ``((label, Backtest), ...)``.
    year_check: object = None
    finish_check: tuple = ()
    #: What closing each zone's largest leak to the mission's rate would add
    #: (PLAN 4C.2, decision 54) — `focus.Lever`s, largest first.
    levers: tuple = ()

    @property
    def present(self) -> bool:
        return bool(self.finish or self.year or self.pipeline or self.baptisms)


#: Under this index in EVERY transfer shown, on enough figures each time, a
#: unit is "debajo de la misión, traslado tras traslado" (PLAN 4B.3). The
#: quadrant's corner cannot carry "chronic": its six-week trend is mostly
#: noise at district level (4A.1); the index over a whole transfer is not.
CHRONIC_BELOW = 90.0


@dataclass(frozen=True)
class IndexHistory:
    """Each unit's productivity index in every transfer the weekly form
    reaches (PLAN-2026-10-06 4B.3): ``transfers`` is the labels, oldest
    first; ``rows`` is ``((scope, (Productivity, ...)), ...)`` in the same
    order, least productive now first."""

    transfers: tuple = ()
    rows: tuple = ()

    @staticmethod
    def chronic(values) -> bool:
        seen = [v for v in values if v is not None and v.value is not None]
        return (len(seen) >= 2 and len(seen) == len(values)
                and all(not v.thin and v.value < CHRONIC_BELOW for v in seen))

    @property
    def chronic_names(self) -> tuple:
        return tuple(s.name for s, values in self.rows if self.chronic(values))


@dataclass(frozen=True)
class Changes:
    """What moved since the period it is compared with (PLAN 4B.2, decision
    53): recomputed from today's sheet, so "antes" is with today's reports,
    late ones included — said on the page.

    ``entered`` / ``left`` are the units that joined or dropped out of the
    head of "Dónde enfocar" (the units carrying 80% of the shortfall).
    ``landing_then`` is the year's landing as it read a closed month ago.
    """

    against: str = ""
    history: IndexHistory | None = None
    entered: tuple = ()
    left: tuple = ()
    landing_then: object = None
    landing_then_label: str = ""


#: The nightly activity a companionship controls behind each Key Indicator
#: of the index (PLAN 4C.4): what to ask about when that result lags.
NIGHTLY_INPUT = {
    "ki_new_people_real": "contacts_made",
    "ki_member_lessons_real": "lessons_member_present",
    "ki_friends_sacrament_real": "church_invites",
    "ki_friends_first_week_real": "church_invites",
    "ki_baptismal_date_real": "baptismal_invitations",
    "ki_rc_at_church_real": "rc_lessons",
}


@dataclass(frozen=True)
class Driver:
    """One unit a level down, read from result to cause (AUDIT M3, PLAN
    4C.4): the index member it produces least of, the conversion rate
    furthest under the mission's outside chance (zones only — decision 13),
    its mature funnel's largest leak, and the nightly input behind the
    lagging result against its goal."""

    name: str
    low_key: str | None = None
    low_label: str = ""
    low_ratio: float | None = None
    rate: tuple | None = None        # (label, value, mission value)
    leak: str | None = None
    leak_step: tuple | None = None
    input: tuple | None = None       # (label, per area-week, goal, pct)


@dataclass(frozen=True)
class LadderRow:
    """One rung of the comparison ladder: this unit, the unit above it, the
    mission — the same measure on every scale it can be read at.

    The whole point of a unit's page. Since decision 45 the measure is the
    productivity index: a district at 92 is a fact about nothing until its
    zone's 104 and the mission's 100 are printed beside it.

    ``delta`` and ``deltas`` are THIS UNIT minus this rung, in index points —
    the overall index and each member's ratio — computed here rather than in
    a renderer, so the screen and the printed page cannot disagree about the
    sign of a gap (decision 30). Both are None on the unit's own rung.
    """

    scope: S.Scope
    role: str
    is_self: bool = False
    index: Productivity = field(default_factory=Productivity)
    metrics: tuple[MetricRow, ...] = ()
    delta: float | None = None
    deltas: tuple[float | None, ...] = ()

    @property
    def name(self) -> str:
        return self.scope.name


@dataclass(frozen=True)
class ChildRow:
    """One unit a level down, ranked and named (decisions 15, 16, 45).

    Ranked on the productivity ``index`` — output per companionship against
    the mission's — and not on attainment of self-set goals, which on
    2026-10-06 put the mission's least productive zone at the top of the
    table because it set the lowest goals (AUDIT-2026-10-06 C1). It can be
    said out loud: "Angol brings 27% more friends to sacrament per
    companionship than the mission does."

    ``rank`` is 1 for the LEAST productive, because that is the order the
    table prints in and the order a council reads down.
    """

    scope: S.Scope
    rank: int
    index: Productivity = field(default_factory=Productivity)
    metrics: tuple[MetricRow, ...] = ()
    #: The weighted change of the index's members, last three complete weeks
    #: against the three before (`focus.trend_change`) — the quadrant's other
    #: axis (PLAN-2026-10-06 Phase 3).
    trend: float | None = None
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

    #: This unit, the unit above it and the mission, in that order — the
    #: comparison ladder. Empty at mission level, which has nothing above it.
    ladder: tuple[LadderRow, ...] = ()

    #: Every unit at this level under the same parent, weakest first, this one
    #: among them. Where the unit SITS, as against what it is worth.
    siblings: tuple = ()

    #: Every AREA inside the unit, weakest first. Mission and zone only — at
    #: district level the areas are already `children`.
    areas_ranked: tuple = ()

    #: This unit's productivity index against the mission (decision 45).
    index: Productivity = field(default_factory=Productivity)

    #: The forward view (decision 48). Empty at area level.
    forward: Forward = field(default_factory=Forward)

    #: `{metric key: Series}` over the last TWELVE complete weeks, whatever
    #: the period — the trend strip every unit page carries (AUDIT H3). A
    #: weekly packet's "trend" used to be one column.
    trend_series: dict = field(default_factory=dict)

    #: This unit's own 6-week trend (`ChildRow.trend`'s figure).
    trend: float | None = None

    #: Where the shortfall against leadership's goal sits: the mission's
    #: districts, a zone's areas (`focus.pareto`). Empty below zone level.
    focus: tuple = ()

    #: The mature-cohort funnel (`focus.mature_funnel`): the mission's ten
    #: Tableau zones, a zone's districts. None without an export.
    funnel: object = None

    #: The mission's zones with their conversion rates, for the levers page.
    child_rates: tuple = ()

    #: `{metric key: Series}` for the seven, week by week (decision 26).
    series: dict = field(default_factory=dict)

    #: What this companionship is strong at and what they are growing —
    #: WEEKLY_BREAKDOWNS' own choice, read and never recomputed (§1.2).
    strengths: tuple[str, ...] = ()
    growth: str | None = None

    #: Tableau's milestones over the same days of other years (PLAN 4B.1,
    #: decision 52). Mission and zone.
    years: object = None

    #: What moved since the comparison period, and every unit's index by
    #: transfer (PLAN 4B.2-4B.3, decision 53). Mission and zone.
    changes: Changes | None = None

    #: The goal sanity line (PLAN 4D.1, decision 56): ``{key: (ratio, best,
    #: best label)}`` — leadership's goal for the period over the most the
    #: unit did in any one transfer, pro-rated to the same weeks. Mission
    #: and zone.
    goal_reach: dict = field(default_factory=dict)

    #: Result to cause, one per unit a level down (PLAN 4C.4). Mission and
    #: zone.
    drivers: tuple = ()

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

    @property
    def reporting_ranked(self) -> tuple:
        """The units one level down, worst REPORTING first — decision 45's
        separate list. Reporting stays out of the productivity index's
        meaning (a silent area still counts zero there, on purpose), and gets
        its own ranked list so "Angol: 2 areas silent all transfer" is said
        as what it is rather than folded into a performance figure."""
        def rate(c):
            cov = c.coverage
            return (cov.reporting_rate if cov is not None
                    and cov.reporting_rate is not None else 0.0)
        return tuple(sorted(self.children,
                            key=lambda c: (rate(c), -len(c.areas_silent),
                                           c.name)))

    def ki(self, key: str) -> MetricRow | None:
        return next((r for r in self.key_indicators if r.key == key), None)

    @property
    def nightly_source_note(self) -> str:
        """Why "Nuevas Personas Encontradas" can read 900 in the nightly table
        and 806 among the Key Indicators (AUDIT-2026-10-06 H4): two forms, two
        windows. The nightly form counts every night through
        `NightlyCoverage.through`, the week in progress included; the weekly
        form, complete weeks only. Both renderers print this sentence."""
        from app.config import es_display
        cov = self.nightly_coverage
        through = (f" hasta el {es_display.day_month(cov.through)}"
                   if cov is not None and cov.through is not None else "")
        return (f"Estas cifras salen del informe de cada noche{through}; los "
                f"Indicadores Clave, del formulario semanal y sólo de semanas "
                f"completas. Una medida con el mismo nombre puede dar dos "
                f"cifras.")

    @property
    def nightly_weakest_first(self) -> tuple[MetricRow, ...]:
        """Decision 17's table order: furthest from its goal at the top.

        Attainment, not movement — the ORDER is about which metric is furthest
        behind, while the row's colour is about which way it moved (decision
        31); both renderers say so in the section's head. A metric with no
        goal to be measured against sorts to the end rather than to the top:
        it is not the weakest, it is unmeasured. So does a FLAGGED goal: it is
        not a yardstick, and "Lecciones con CR" sat at the top of every table
        for a goal nobody could meet (AUDIT-2026-10-06 H4).

        Lives on the model rather than in either renderer, so the screen and
        the printed page list them in the same order.
        """
        return tuple(sorted(
            self.nightly_metrics,
            key=lambda r: (r.grade.pct is None or bool(r.grade.flag),
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
    #: Each sector's own nightly goal for each week — `area_goals.GoalBook`,
    #: called as (area, monday, key) (PLAN-2026-10-02-goals.md, G10). None
    #: leaves every row on `nightly_goals`' one mission-wide figure.
    nightly_goal_for: object = None
    agent_config: dict = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    mission_name: str = S.DEFAULT_MISSION_NAME
    #: The last day that counts toward nightly compliance — today once the
    #: evening refresh has run, yesterday before it. Resolved once at load so
    #: `build_report` stays pure and a packet cannot straddle the 9:30 PM
    #: cutoff halfway through its 63 scopes. Defaults to `today`.
    anchor: date | None = None
    #: The stored Tableau export and everything derived from it once rather
    #: than 63 times: the frame itself, its description, the p75 milestone
    #: lags the funnel's maturity verdict rests on, and the roster
    #: reconciliation of decision 35. All empty when no export is stored,
    #: which is a report with no finding section and a stated reason — not an
    #: error (decision 32).
    tableau_detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    tableau_export: object = None
    tableau_maturity: dict = field(default_factory=dict)
    tableau_reconciliation: object = None
    #: TABLEAU_BAPTISMS, certified months only, and the open month held apart
    #: from them (decision 21).
    baptisms_by_month: dict = field(default_factory=dict)
    baptisms_open: tuple = ()
    #: TABLEAU_BAPTISM_WINDOWS as `(start, end, count)`: the certified figure
    #: for each report period that is not a month (decision 42).
    baptism_windows: tuple = ()
    annual_goal: float | None = None
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

    def tableau_windows(self, period: P.Period) -> tuple:
        """`(window, comparison window)` for this period, resolved once.

        The gate runs per PERIOD, not per scope: the same eleven days answer
        for the mission and for every one of the 45 areas, and asking 63 times
        would re-read the export's bounds 63 times.
        """
        cache_key = ("tableau", period.key)
        if cache_key not in self._flags:
            export = self.tableau_export or TB.Export()
            window = TB.clip(period, export)
            before = TB.clamp(TB.preceding(window), export)
            self._flags[cache_key] = (window, before)
        return self._flags[cache_key]

    def tableau_rows(self, period: P.Period) -> tuple:
        """The export's rows inside the period's window and the window before
        it, filtered once for all 63 scopes.

        `in_window` over 99.425 rows is the expensive part of the whole block;
        every unit then cuts its own areas out of a frame of a few thousand.
        """
        cache_key = ("tableau_rows", period.key)
        if cache_key not in self._flags:
            window, before = self.tableau_windows(period)
            self._flags[cache_key] = (
                TB.in_window(self.tableau_detail, window),
                TB.in_window(self.tableau_detail, before) if before.usable else None,
            )
        return self._flags[cache_key]

    def baptism_year(self, period: P.Period) -> object:
        """The baptism block (decision 21), for the mission's page only: the
        selected period's own certified figure first (decisions 41, 42), then
        the year it sits in."""
        month, count, through = (self.baptisms_open or (None, None, None))

        def certified_for(p):
            return TB.period_baptisms(p, certified=self.baptisms_by_month,
                                      open_month=self.baptisms_open,
                                      windows=self.baptism_windows)

        this_year = P.resolve(P.YEAR, self.today, self.cycles)
        return TB.Baptisms(
            period=certified_for(period),
            year_to_date=(certified_for(this_year)
                          if this_year.end.year == period.end.year else None),
            year=period.end.year,
            goal=self.annual_goal,
            certified={k: v for k, v in self.baptisms_by_month.items()
                       if k.startswith(f"{period.end.year:04d}-")},
            provisional=(count if month and month.startswith(
                f"{period.end.year:04d}-") else None),
            provisional_through=through,
        )

    def tableau_dates(self) -> tuple:
        """`(area names, date set, confirmation date, pipeline fit)` off the
        export, parsed and fitted once for all 63 scopes — or () with no
        export."""
        if "tableau_dates" not in self._flags:
            det = self.tableau_detail
            if det is None or det.empty:
                self._flags["tableau_dates"] = ()
            else:
                from app.analytics import finding_funnel as FF
                from app.reports import forecast as F
                set_d = FF.parse_dates(det, "first_baptism_goal_date_set")
                conf = FF.parse_dates(det, "confirmation_date")
                self._flags["tableau_dates"] = (
                    TB._names(det, TB.AREA_COL), set_d, conf,
                    F.fit_pipeline(set_d, conf, self.today))
        return self._flags["tableau_dates"]

    @property
    def mission(self) -> S.Scope:
        if "mission_scope" not in self._flags:
            self._flags["mission_scope"] = S.mission_scope(self.roster,
                                                           self.mission_name)
        return self._flags["mission_scope"]

    @property
    def weekly_records_from(self) -> date | None:
        """The first week the weekly form really covered the mission, or None.

        "Really" is `periods.THIN_REPORTING_RATE` of the mission's areas, so
        the single stray row dated 2026-08-09 does not count as the start and
        the week ending 2026-08-16 (31 of 45 areas) does. "Mes pasado" uses it
        to refuse a comparison with the form's launch month.
        """
        if "records_from" not in self._flags:
            first = None
            areas = self.mission.area_count
            df = self.weekly_ki
            if areas and df is not None and not df.empty:
                mine = df[df["_area"].isin(set(self.mission.areas))]
                counts = mine.groupby("_week")["_area"].nunique()
                weeks = [P._as_date(w) for w, n in counts.items()
                         if n >= P.THIN_REPORTING_RATE * areas]
                first = min((w for w in weeks if w is not None), default=None)
            self._flags["records_from"] = first
        return self._flags["records_from"]

    def lead_week_goal(self, area: str, week: str) -> dict | None:
        """Leadership's goal for one area for one week, or None.

        The area's AREA_TRANSFER_GOALS row for the cycle the week falls in,
        spread evenly over the cycle's weeks — `_leadership_goals`' own
        pro-rating rule, applied per area-week so a row can be graded on
        exactly the area-weeks that reported (decision 44, rule 1). None when
        the area has no goal that cycle: "any of its seven non-zero" is
        `goals_queries.areas_with_goals`' rule for having one.
        """
        if "lead_table" not in self._flags:
            self._flags["lead_table"] = self._lead_table()
            self._flags["week_cycle"] = {}
        cycles = self._flags["week_cycle"]
        if week not in cycles:
            day = date.fromisoformat(str(week)[:10])
            cycles[week] = next((c["start"].isoformat() for c in self.cycles
                                 if c["start"] <= day <= c["end"]), None)
        start = cycles[week]
        if start is None:
            return None
        return self._flags["lead_table"].get((str(area).strip(), start))

    def _lead_table(self) -> dict:
        from app.analytics.transfer_year import weeks_in_cycle
        df = self.transfer_goals
        if df is None or df.empty or "area" not in df.columns:
            return {}
        spans = {c["start"].isoformat():
                 (weeks_in_cycle(c["start"], c["end"]) or 1)
                 for c in self.cycles}
        keys = [k for k in self.ki_keys if k in df.columns]
        out = {}
        for _, row in df.iterrows():
            start = str(row.get("transfer_start", "") or "").strip()[:10]
            if start not in spans:
                continue
            values = {}
            for key in keys:
                value = pd.to_numeric(row.get(key), errors="coerce")
                values[key] = 0.0 if pd.isna(value) else float(value)
            if not any(values.values()):
                continue
            out[(str(row["area"]).strip(), start)] = {
                k: v / spans[start] for k, v in values.items()}
        return out

    def nightly_goal_flags(self, period: P.Period) -> dict:
        """The same verdict for the nightly `GOAL_*` numbers.

        Judged on the same basis the row's percentage now uses — per REPORTED
        night (PLAN-2026-10-02-goals.md, decision G-D5). It was per active
        area-week, where an unfiled night counted as a zero and a goal could
        be called unusable for want of reports rather than of work.
        """
        cache_key = ("nightly", period.key)
        if cache_key not in self._flags:
            mission = S.mission_scope(self.roster, self.mission_name)
            self._flags[cache_key] = {
                r.key: goal_is_unusable(r.per_reporting_area_week,
                                        r.goal_per_area_week)
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


def _annual_goal(get_config_value) -> float | None:
    """`GOAL_ANNUAL_baptisms`, or None when the mission has not set one.

    A missing goal is not zero: `annual_baptisms.goal_pace` draws no line for
    it, and the page prints the year without a target rather than a year that
    missed one.
    """
    raw = str(get_config_value("GOAL_ANNUAL_baptisms", "") or "").strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _open_baptism_month(certified: dict, by_month, capture) -> tuple:
    """`(month, count, through)` for the month still being counted, or `()`.

    TABLEAU_BAPTISMS stores the current month as a row that stops short of the
    month's last day, and `get_mission_baptisms_by_month` leaves it out of the
    certified series for a reason (2026-09-19: plotted as an ordinary point it
    draws the year collapsing every time the packet is built mid-month). The
    packet still wants it — said as the open thing it is — so it is fetched
    separately here and never merged into `certified`.
    """
    everything = by_month(include_provisional=True)
    extra = [k for k in everything if k not in certified]
    if not extra:
        return ()
    month = max(extra)
    row = capture(month) or {}
    end = str(row.get("end_date", "") or "").strip()
    through = None
    if len(end) >= 10:
        try:
            through = date.fromisoformat(end[:10])
        except ValueError:
            through = None
    return (month, int(everything[month]), through)


def load_data(today: date | None = None) -> ReportData:
    """Read every source once. The only impure function in this module."""
    from app.config.flavor_loader import flavor
    from app.config.metric_catalog import (
        format_metric_label, key_indicator_metrics, nightly_metrics,
        non_numeric_metrics, strip_form_suffix,
    )
    from app.db.goals_queries import all_area_transfer_goals
    from app.db.queries import (
        get_agent_config, get_area_weekly_goals, get_baptism_windows,
        get_sector_goal_lookup,
        get_baptisms_capture, get_config_value, get_daily_log, get_ki_goals_for_week,
        get_mission_baptisms_by_month, get_scores, get_tableau_detail,
        get_weekly_ki,
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

    roster = S.load_roster()
    # The export is read once for the whole packet. Its p75 milestone lags and
    # its reconciliation against the roster are properties of the export, not
    # of any period, so they are computed here too.
    detail, uploaded_by, uploaded_at = get_tableau_detail()
    export = TB.read_export(detail, uploaded_by, uploaded_at)

    certified = get_mission_baptisms_by_month()
    open_month = _open_baptism_month(certified, get_mission_baptisms_by_month,
                                     get_baptisms_capture)

    return ReportData(
        roster=roster,
        weekly_ki=weekly_ki,
        daily_log=daily,
        breakdowns=breakdowns,
        scores=scores,
        transfer_goals=all_area_transfer_goals(),
        cycles=P.load_cycles(),
        ki_keys=ki_keys,
        nightly_keys=nightly_keys,
        nightly_goals=get_area_weekly_goals(),
        nightly_goal_for=get_sector_goal_lookup(),
        agent_config=get_agent_config(),
        # The mission's own Spanish names, from QUESTIONS_CONFIG, without the
        # form's "(Real)" tail. Spanish literals, no t() — decision 3.
        labels=labels,
        mission_name=get_config_value("MISSION_NAME", flavor.display_name),
        tableau_detail=detail,
        tableau_export=export,
        tableau_maturity=TB.maturity_days(detail),
        tableau_reconciliation=TB.reconcile(detail, S._clean(roster)),
        baptisms_by_month=certified,
        baptisms_open=open_month,
        baptism_windows=tuple(get_baptism_windows()),
        annual_goal=_annual_goal(get_config_value),
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
        return NightlyCoverage(max(0, possible), 0, 0, scope.area_count,
                               through=end if days > 0 else None)
    window = df[(df["_day"] >= period.start.isoformat())
                & (df["_day"] <= end.isoformat())
                & df["_area"].isin(set(scope.areas))]
    return NightlyCoverage(
        days_possible=possible,
        days_reported=len(window),
        areas_reporting=int(window["_area"].nunique()) if not window.empty else 0,
        areas_in_scope=scope.area_count,
        through=end,
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
             comparison: P.Comparison | None = None) -> list[MetricRow]:
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

    # Leadership's goal over exactly the area-weeks that reported (decision
    # 44), with the actual over the same area-weeks — an area-week with no
    # goal leaves BOTH sides, so the percentage never mixes populations.
    lead_goal: dict = {}
    lead_actual: dict = {}
    lead_weeks = 0
    if not rows.empty:
        for (area, week), group in rows.groupby(["_area", "_week"]):
            goal = data.lead_week_goal(area, week)
            if goal is None:
                continue
            lead_weeks += 1
            for key in data.ki_keys:
                lead_goal[key] = lead_goal.get(key, 0.0) + goal.get(key, 0.0)
                if key in group.columns:
                    lead_actual[key] = lead_actual.get(key, 0.0) + float(
                        pd.to_numeric(group[key], errors="coerce").sum())
    graded = (lead_weeks > 0
              and lead_weeks >= LEAD_MIN_SHARE * reporting_area_weeks)

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
        mark, mark_areas, mark_complete = marks.get(key, (None, 0, False))

        goal_sum = lead_goal.get(key) if graded else None
        done_sum = lead_actual.get(key, 0.0) if graded else None
        grade = grade_ki(
            done_sum / lead_weeks if goal_sum else None,
            goal_sum / lead_weeks if goal_sum else None,
            before=before_rate, now=per_reporting,
            # The raw counts behind the change, so a change on single digits
            # prints as "+4" and a move inside Poisson noise prints without a
            # direction (H5).
            counts=(actual, reporting_area_weeks, before, before_area_weeks))
        if key in UNCOLOURED_KI:
            # Shown against leadership's transfer goal, never coloured by it:
            # the 527 annual goal is the baptism target (decision 46).
            grade = replace(grade, status=None)

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
            lead_goal=goal_sum,
            lead_actual=done_sum,
            lead_area_weeks=lead_weeks if graded else 0,
            per_active_area_week=per_active,
            per_reporting_area_week=per_reporting,
            before_per_reporting_area_week=before_rate,
            grade=grade,
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

    **Attainment and change both rest on the nights actually filed**
    (PLAN-2026-10-02-goals.md, decision G-D5). The goal is one mission-wide
    `GOAL_*` number per area per week, so the row's figure is the total over
    the nights filed, times seven, against it. It used to divide by every
    ACTIVE area-week, which counted an unfiled night as a zero and so mixed
    how much was reported into how much was done; how many nights went
    unfiled is printed above the table instead, as its own number.
    `per_active_area_week` is still carried for the tables that rank units.

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

        # Each sector's own goal for the nights it filed (G10), averaged; the
        # mission-wide figure when there is no lookup or no filed night.
        if data.nightly_goal_for is not None and not rows.empty:
            goal = weighted_goal(
                pd.DataFrame({"Date": rows["_day"], "Area": rows["_area"]}),
                key, data.nightly_goal_for) or goal
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
            goal_per_area_week=goal,
            grade=grade_nightly(now_rate, goal, before=before_rate,
                                now=now_rate, flag=(flags or {}).get(key),
                                counts=(actual, area_days, before,
                                        before_days)),
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

    # The Spanish names travel with the row, so neither renderer can fall back
    # to the key: the packet printed "contact_rate" on every zone's rates page
    # until 2026-10-06 (AUDIT-2026-10-06 H2). The denominator is named too —
    # Tasa de Lecciones divides by contact ATTEMPTS, not by contacts, and a
    # reader who is not told assumes the other.
    out = []
    for row in rate_rows(
            totals(rows), totals(prior), data.agent_config,
            current_days=int(rows["_day"].nunique()) if not rows.empty else 0,
            prior_days=prior_days):
        num, den = row["metric"].numerator, row["metric"].denominator
        out.append({**row,
                    "label": data.labels.get(row["key"], row["key"]),
                    "numerator_label": data.labels.get(num, num),
                    "denominator_label": data.labels.get(den, den)})
    return tuple(out)


# ── Children, ranked weakest first (decisions 14, 15) ────────────────────────

def _mission_rows(data: ReportData, period: P.Period,
                  comparison: P.Comparison | None) -> tuple:
    """The mission's Key Indicator rows — every index's denominator."""
    return _ki_rows_for(data, data.mission, period, comparison)


def _index_for(data: ReportData, rows, period: P.Period,
               comparison: P.Comparison | None) -> Productivity:
    return productivity(rows, _mission_rows(data, period, comparison))


#: What the ladder calls each rung. Only "distrito" is masculine, so the
#: demonstrative is carried per level rather than assembled from a noun.
LADDER_SELF = {S.MISSION: "la misión", S.ZONE: "esta zona",
               S.DISTRICT: "este distrito", S.AREA: "esta área"}
LADDER_ABOVE = {S.MISSION: "la misión", S.ZONE: "su zona",
                S.DISTRICT: "su distrito"}


def _ki_rows_for(data: ReportData, scope: S.Scope, period: P.Period,
                 comparison: P.Comparison | None) -> tuple:
    """`_ki_rows`, memoised on the scope and the period.

    Without it the ladder is the most expensive thing in the packet: 63 units
    each ask their ancestors for Key Indicators that 63 other builds have
    already computed — 122 extra passes over WEEKLY_KI for answers that exist.
    With it a zone's rung is computed once, by whichever unit asks first.
    """
    cache_key = ("ki_rows", scope.key, period.key,
                 comparison.period.key
                 if comparison is not None and comparison.period is not None
                 else None)
    if cache_key not in data._flags:
        data._flags[cache_key] = tuple(_ki_rows(
            data, scope, period, comparison=comparison))
    return data._flags[cache_key]


def _ladder(data: ReportData, scope: S.Scope, period: P.Period,
            comparison: P.Comparison | None) -> tuple:
    """This unit against every scale above it, coarsest last.

    Every figure on it is the productivity index (decision 45): output per
    ACTIVE companionship-week against the mission's, so a zone whose areas
    went quiet does not outrank one whose areas all filed, and a zone that set
    itself low goals does not outrank one that worked harder.

    Empty at mission level — the mission is the top of the ladder and is 100
    by construction.
    """
    chain, node = [scope], scope
    while True:
        up = S.parent(data.roster, node, data.mission_name)
        if up is None or up.key == node.key or up.key in {s.key for s in chain}:
            break
        chain.append(up)
        node = up
    if len(chain) < 2:
        return ()

    own_metrics = _ki_rows_for(data, scope, period, comparison)
    own = _index_for(data, own_metrics, period, comparison)

    rows = []
    for rung in chain:
        is_self = rung.key == scope.key
        metrics = (own_metrics if is_self
                   else _ki_rows_for(data, rung, period, comparison))
        index = (own if is_self
                 else _index_for(data, metrics, period, comparison))
        role = (LADDER_SELF.get(rung.level, "esta unidad") if is_self
                else LADDER_ABOVE.get(rung.level, "la misión"))
        rows.append(LadderRow(
            scope=rung, role=role, is_self=is_self, index=index,
            metrics=metrics,
            delta=(None if is_self or index.value is None or own.value is None
                   else own.value - index.value),
            deltas=() if is_self else tuple(
                None if (own.ratio(k) is None or index.ratio(k) is None)
                else own.ratio(k) - index.ratio(k)
                for k, _ in index.members),
        ))
    return tuple(rows)


def _rank_scopes(data: ReportData, scopes: list, period: P.Period,
                 comparison: P.Comparison | None) -> tuple:
    """Units ranked least productive first — no top-N (decisions 15, 45).

    A unit with no index at all sorts to the END rather than to the top: it
    is not the least productive, it is unmeasured, and printing it first
    would put "no data" where a council looks for its biggest problem. It
    appears on the reporting list instead, which is where silence belongs.
    """
    out = []
    for child in scopes:
        rows = _ki_rows_for(data, child, period, comparison)
        child_rows = _weekly_rows(data, child, period)
        reported = set(child_rows["_area"]) if not child_rows.empty else set()
        out.append(ChildRow(
            scope=child, rank=0,
            index=_index_for(data, rows, period, comparison),
            trend=_trend_for(data, child, period),
            metrics=rows,
            coverage=P.week_coverage(period, _reported_by_week(child_rows),
                                     child.area_count),
            areas_silent=tuple(sorted(set(child.areas) - reported)),
        ))
    out.sort(key=lambda c: (c.index.value is None,
                            c.index.value if c.index.value is not None else 0,
                            c.scope.name))
    return tuple(replace(c, rank=i + 1) for i, c in enumerate(out))


def _ranked_children_of(data: ReportData, parent: S.Scope, period: P.Period,
                        comparison: P.Comparison | None) -> tuple:
    """`_rank_scopes` over a unit's children, memoised on the PARENT.

    Every unit wants the same list twice over: once as its own `children`, and
    once as the `siblings` of each of those children. Ranked once, it is free
    both times — 18 rankings for CCSM's 63 scopes instead of 80.
    """
    cache_key = ("children", parent.key, period.key,
                 comparison.period.key
                 if comparison is not None and comparison.period is not None
                 else None)
    if cache_key not in data._flags:
        data._flags[cache_key] = _rank_scopes(
            data, S.children(data.roster, parent), period, comparison)
    return data._flags[cache_key]


def _siblings(data: ReportData, scope: S.Scope, period: P.Period,
              comparison: P.Comparison | None) -> tuple:
    """Every unit at this level under the same parent, this one included.

    What turns an index into a position. The ladder says how the unit
    compares with the scale above it; this says how it compares with the units
    beside it — the half a leader can do something about, because the unit
    two rows up is run by somebody in the same room.

    Empty at mission level, which has no siblings, and empty where a unit is
    an only child: a strip of one dot is a picture of nothing.
    """
    parent = S.parent(data.roster, scope, data.mission_name)
    if parent is None:
        return ()
    rows = _ranked_children_of(data, parent, period, comparison)
    return rows if len(rows) > 1 else ()


def _areas_ranked(data: ReportData, scope: S.Scope, period: P.Period,
                  comparison: P.Comparison | None) -> tuple:
    """Every AREA inside the unit, least productive first — §3.2's Z3, and
    the drawer the mission page keeps 45 of them behind (decision 15).

    Empty at district level, where the areas ARE the children and the same
    list twice is noise, and at area level, which has no areas below it.
    """
    if scope.child_level != S.DISTRICT and scope.level != S.MISSION:
        return ()
    scopes = S.area_scopes(data.roster,
                           zone=scope.zone if scope.level == S.ZONE else None)
    return _rank_scopes(data, scopes, period, comparison)

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


def _tableau_block(data: ReportData, scope: S.Scope, period: P.Period):
    """This unit's finding section, or the gate's reason there is not one.

    Three things differ by level and nothing else does:

    * the MISSION's block covers every zone the export knows, not the
      roster's four (decision 24), and carries the year's baptisms (M6);
    * a zone or a district is roster-scoped and ranks its own children;
    * an AREA gets no block at all. Its half page has 338pt and P5 measured
      the existing block at 142-280pt of it, and eleven days of one
      companionship's finding is four people — a funnel drawn over four people
      is decoration. The area's finding work is in its Key Indicators, which
      are its own report of it.
    """
    export = data.tableau_export
    if export is None or scope.level == S.AREA:
        return None

    window, before = data.tableau_windows(period)
    rows, prior = data.tableau_rows(period) if window.usable else (None, None)
    whole_mission = scope.level == S.MISSION
    children = S.children(data.roster, scope)
    nouns = {S.MISSION: "zonas", S.ZONE: "distritos", S.DISTRICT: "áreas"}

    units = ()
    if window.usable:
        if whole_mission:
            zones = sorted({z for z in S._clean(data.roster)["Zone"] if z})
            units = TB.zone_rows(rows, zones)
        else:
            units = TB.unit_rows(TB.for_areas(rows, scope.areas), children)

    return TB.build_block(
        data.tableau_detail, export, period,
        areas=(None if whole_mission else scope.areas),
        units=units,
        unit_noun=nouns.get(scope.level, ""),
        whole_mission=whole_mission,
        reconciliation=data.tableau_reconciliation,
        baptisms=(data.baptism_year(period) if whole_mission else None),
        maturity=data.tableau_maturity,
        window=window,
        before=before,
    )


# ── Phase 3: trend, focus and levers (PLAN-2026-10-06) ───────────────────────

#: How many complete weeks the trend strip covers, whatever the period.
TREND_WEEKS = 12


def _trend_weeks(data: ReportData, period: P.Period) -> tuple:
    """The last twelve complete weeks ending with the period's last one."""
    end = period.weeks[-1] if period.weeks else None
    if end is None:
        last = P.resolve(P.LAST_WEEK, data.today, data.cycles)
        end = last.weeks[-1] if last is not None and last.weeks else None
    if end is None:
        return ()
    return tuple(end - timedelta(weeks=i) for i in reversed(range(TREND_WEEKS)))


def _trend_period(data: ReportData, period: P.Period) -> P.Period | None:
    cache_key = ("trend_period", period.key)
    if cache_key not in data._flags:
        weeks = _trend_weeks(data, period)
        data._flags[cache_key] = (P.Period(
            key="trend", label="12 semanas", start=weeks[0] - timedelta(days=6),
            end=weeks[-1], weeks=weeks, full_end=weeks[-1],
            full_weeks=len(weeks)) if weeks else None)
    return data._flags[cache_key]


def _trend_for(data: ReportData, scope: S.Scope, period: P.Period):
    """`focus.trend_change` over the trend strip's last six weeks."""
    from app.reports import focus as FC
    cache_key = ("trend", scope.key, period.key)
    if cache_key not in data._flags:
        tp = _trend_period(data, period)
        history = [w.isoformat() for w in tp.weeks] if tp else []
        weeks = history[-6:]
        data._flags[cache_key] = FC.trend_change(
            data.weekly_ki, scope.areas, index_weights(data.ki_keys),
            recent=weeks[3:], prior=weeks[:3], history=history)
    return data._flags[cache_key]


def _silent_goals(data: ReportData, scope: S.Scope, period: P.Period) -> dict:
    """Leadership's goal for the area-weeks in the period that filed NOTHING
    — the part of a unit's shortfall that is silence (PLAN 4A.2)."""
    rows = _weekly_rows(data, scope, period)
    filed = (set(zip(rows["_area"], rows["_week"])) if not rows.empty
             else set())
    out: dict = {}
    for week in period.weeks:
        key = week.isoformat()
        for area in scope.areas:
            if (area, key) in filed:
                continue
            goal = data.lead_week_goal(area, key)
            for k, v in (goal or {}).items():
                out[k] = out.get(k, 0.0) + v
    return out


def _focus(data: ReportData, scope: S.Scope, period: P.Period,
           comparison: P.Comparison | None) -> tuple:
    """The shortfall by unit: the mission's districts, a zone's areas."""
    from app.reports import focus as FC
    if scope.level == S.MISSION:
        units = [d for z in S.children(data.roster, scope)
                 for d in S.children(data.roster, z)]
    elif scope.level == S.ZONE:
        units = list(S.area_scopes(data.roster, zone=scope.zone))
    else:
        return ()
    rows = []
    for unit in units:
        ki = _ki_rows_for(data, unit, period, comparison)
        rows.append((unit, ki, _index_for(data, ki, period, comparison).value,
                     _trend_for(data, unit, period),
                     _silent_goals(data, unit, period)))
    return FC.pareto(rows, index_weights(data.ki_keys))


def _funnel(data: ReportData, scope: S.Scope):
    """The mature-cohort funnel: the mission's Tableau zones (all ten), a
    zone's districts by roster area."""
    from app.analytics import finding_funnel as FF
    from app.reports import focus as FC
    if scope.level not in (S.MISSION, S.ZONE):
        return None
    det = data.tableau_detail
    if det is None or det.empty:
        return None
    if "funnel_dates" not in data._flags:
        stages = [(TB.STAGE_LABELS.get(label, label), FF.parse_dates(det, col))
                  for label, col in FF.FUNNEL_STAGES if col is not None]
        data._flags["funnel_dates"] = (
            FF.parse_dates(det, "event_date_selected"), stages)
    found, stages = data._flags["funnel_dates"]
    if scope.level == S.MISSION:
        zone_col = TB._names(det, TB.ZONE_COL)
        pilot = {z.name for z in S.children(data.roster, scope)}
        groups = [(z, zone_col == z, z in pilot)
                  for z in sorted(set(zone_col) - {"", "nan"})]
    else:
        area_col = TB._names(det, TB.AREA_COL)
        groups = [(d.name, area_col.isin(set(d.areas)), True)
                  for d in S.children(data.roster, scope)]
    return FC.mature_funnel(found, [s for _, s in stages],
                            [label for label, _ in stages], groups, data.today,
                            found_label=TB.STAGE_LABELS.get("Found",
                                                            "Encontradas"))


def _child_rates(data: ReportData, scope: S.Scope, period: P.Period,
                 comparison: P.Comparison | None) -> tuple:
    """Each zone's conversion rates, for the mission's levers page. Zones
    only: below them a rate is a ratio of two small integers (decision 13)."""
    if scope.level != S.MISSION:
        return ()
    return tuple((z, _rates(data, z, period, comparison))
                 for z in S.children(data.roster, scope))


def _transfer_goals_full(data: ReportData, scope: S.Scope,
                         cycle_start: date) -> tuple[dict, bool]:
    """Leadership's goal for the WHOLE cycle, summed over the scope's areas,
    and whether every area has one (decision 23's all-or-nothing)."""
    df = data.transfer_goals
    if df is None or df.empty or "area" not in df.columns:
        return {}, False
    rows = df[(df["transfer_start"].astype(str).str[:10] == cycle_start.isoformat())
              & df["area"].astype(str).str.strip().isin(set(scope.areas))]
    keys = [k for k in data.ki_keys if k in rows.columns]
    if rows.empty or not keys:
        return {}, False
    values = rows[keys].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    with_goal = int((values.sum(axis=1) > 0).sum())
    return ({k: float(values[k].sum()) for k in keys},
            with_goal == scope.area_count)


def _forward(data: ReportData, scope: S.Scope, period: P.Period) -> Forward:
    """The forward view for one unit (decision 48). Mission and zone get the
    four forecasts; a district gets its Tableau baptisms; an area nothing."""
    from app.reports import forecast as F

    if scope.level == S.AREA:
        return Forward()
    dates = data.tableau_dates()
    names, set_d, conf, fit = dates if dates else (None, None, None, None)
    mask = (names.isin(set(scope.areas))
            if names is not None and scope.level != S.MISSION else None)

    baptisms = None
    if conf is not None and scope.level != S.MISSION:
        baptisms = F.unit_baptisms(conf, mask, period.start,
                                   min(period.end, data.today),
                                   today=data.today,
                                   annual_goal=data.annual_goal)
    if scope.level == S.DISTRICT:
        # 4C.3 (decision 55): the district's open dates and what they are
        # likely to become; the renderers say "pocas fechas" under 15.
        return Forward(baptisms=baptisms, pipeline=(
            F.pipeline(set_d, conf, data.today, fit, mask=mask)
            if fit is not None else None))

    finish, label = (), ""
    cycle = P.resolve(P.THIS_TRANSFER, data.today, data.cycles)
    pace = P.resolve(P.LAST_6_WEEKS, data.today, data.cycles)
    if cycle is not None:
        start = cycle.start
        label = next((str(c.get("number", "")) for c in data.cycles
                      if c["start"] == start), cycle.label)
        goals, complete = _transfer_goals_full(data, scope, start)
        finish = F.transfer_finish(
            data.weekly_ki, scope.areas, data.ki_keys, data.labels,
            cycle_weeks=[w.isoformat() for w in cycle.weeks],
            full_weeks=cycle.full_weeks,
            pace_weeks_list=([w.isoformat() for w in pace.weeks]
                             if pace is not None else []),
            goals=goals, goals_complete=complete)

    year = pipeline = None
    zones = ()
    if scope.level == S.MISSION:
        month, count, _ = (data.baptisms_open or (None, None, None))
        year = F.year_landing(data.baptisms_by_month, data.today.year,
                              goal=data.annual_goal,
                              open_count=(count if month and month.startswith(
                                  f"{data.today.year:04d}-") else None),
                              source="cifra certificada")
        if fit is not None:
            pipeline = F.pipeline(set_d, conf, data.today, fit)
            zone_names = TB._names(data.tableau_detail, TB.ZONE_COL)
            pilot = {s.name for s in S.children(data.roster, scope)}
            zones = tuple(
                (z, z in pilot, F.pipeline(set_d, conf, data.today, fit,
                                           mask=zone_names == z))
                for z in sorted(set(zone_names) - {"", "nan"}))
    elif fit is not None:
        pipeline = F.pipeline(set_d, conf, data.today, fit, mask=mask)
        year = F.year_landing(F.monthly_counts(conf, mask, data.today),
                              data.today.year,
                              goal=baptisms.reference if baptisms else None,
                              source="registros de Tableau")
    return Forward(transfer=label, finish=finish, year=year,
                   pipeline=pipeline, baptisms=baptisms, zones=zones)


# ── History, change, levers and the goal's reach (PLAN-2026-10-06 Phase 4) ───

def _other_years(data: ReportData, scope: S.Scope, period: P.Period):
    """Tableau's milestones over the period's days in this year and the two
    before (4B.1, decision 52): the mission's ten zones, a zone's roster
    areas — decision 47's join, so it matches the zone's other Tableau
    figures."""
    from app.analytics import finding_funnel as FF
    from app.reports import forecast as F
    if scope.level not in (S.MISSION, S.ZONE):
        return None
    det, export = data.tableau_detail, data.tableau_export
    if det is None or det.empty or export is None or export.last is None:
        return None
    if "other_year_cols" not in data._flags:
        data._flags["other_year_cols"] = [
            (label, FF.parse_dates(det, col)) for label, col in F.OTHER_YEAR_ROWS
            if col in det.columns]
    mask = (None if scope.level == S.MISSION
            else TB._names(det, TB.AREA_COL).isin(set(scope.areas)))
    return F.other_years(data._flags["other_year_cols"], mask, period.start,
                         min(period.end, export.last))


def _transfer_periods(data: ReportData) -> tuple:
    """The transfers the weekly form reaches, oldest first, at most three —
    the form starts 2026-08-09, so on CCSM today that is 2026-5 and 2026-6."""
    if "transfer_periods" not in data._flags:
        df = data.weekly_ki
        first = (str(df["_week"].min()) if df is not None and not df.empty
                 else None)
        out = []
        for offset in (2, 1, 0):
            p = P.transfer_period(data.cycles, data.today, offset)
            if (p is None or not p.weeks or first is None
                    or p.weeks[-1].isoformat() < first):
                continue
            out.append(p)
        data._flags["transfer_periods"] = tuple(out)
    return data._flags["transfer_periods"]


def _index_history(data: ReportData, scope: S.Scope) -> IndexHistory | None:
    """Every zone and district (mission) or a zone's districts, by transfer."""
    if scope.level == S.MISSION:
        units = [u for z in S.children(data.roster, scope)
                 for u in [z] + list(S.children(data.roster, z))]
    elif scope.level == S.ZONE:
        units = list(S.children(data.roster, scope))
    else:
        return None
    periods = _transfer_periods(data)
    if not periods:
        return None
    rows = []
    for unit in units:
        rows.append((unit, tuple(
            _index_for(data, _ki_rows_for(data, unit, p, None), p, None)
            for p in periods)))
    rows.sort(key=lambda r: (r[1][-1].value is None, r[1][-1].value or 0.0,
                             r[0].name))
    return IndexHistory(transfers=tuple(p.label for p in periods),
                        rows=tuple(rows))


def _head(rows) -> set:
    """The units carrying the first 80% of a Pareto."""
    cut = next((i for i, r in enumerate(rows, start=1) if r.cumulative >= 80),
               len(rows))
    return {r.name for r in rows[:cut]}


def _changes(data: ReportData, scope: S.Scope, period: P.Period,
             comparison: P.Comparison | None, focus_now: tuple):
    """4B.2 (decision 53): recomputed against the comparison period."""
    from app.reports import forecast as F
    if scope.level not in (S.MISSION, S.ZONE):
        return None
    entered = left = ()
    against = ""
    if (comparison is not None and comparison.period is not None
            and comparison.period.weeks):
        # A comparison period carries its period's KEY (periods.comparison_for)
        # and every memo here is keyed on it: renamed, so the comparison's
        # rows and trends can never be served for the period's own.
        then = replace(comparison.period, key=f"{period.key}:antes")
        before = _focus(data, scope, then, None)
        if focus_now and before:
            now_head, then_head = _head(focus_now), _head(before)
            entered = tuple(sorted(now_head - then_head))
            left = tuple(sorted(then_head - now_head))
        against = comparison.period.label
    landing_then, then_label = None, ""
    if scope.level == S.MISSION and data.baptisms_by_month:
        year = data.today.year
        closed = sorted(k for k, v in data.baptisms_by_month.items()
                        if v is not None and k.startswith(f"{year:04d}-")
                        and k < f"{data.today:%Y-%m}")
        if len(closed) >= 2:
            cut = {k: v for k, v in data.baptisms_by_month.items()
                   if k < closed[-1]}
            landing_then = F.year_landing(cut, year, goal=data.annual_goal)
            month = int(closed[-2][5:7])
            then_label = f"a fin de {F.MONTH_ABBR[month - 1]}"
    return Changes(against=against, history=_index_history(data, scope),
                   entered=entered, left=left, landing_then=landing_then,
                   landing_then_label=then_label)


def _goal_reach(data: ReportData, scope: S.Scope, rows) -> dict:
    """4D.1 (decision 56): leadership's goal per reporting area-week over the
    best per-report rate the unit reached in any transfer the form covers.
    Grading is untouched — this only says when the goal asks for more than
    the unit has ever done."""
    if scope.level not in (S.MISSION, S.ZONE):
        return {}
    periods = _transfer_periods(data)
    if not periods:
        return {}
    best: dict = {}
    for p in periods:
        for r in _ki_rows_for(data, scope, p, None):
            v = r.per_reporting_area_week
            if v is not None and (r.key not in best or v > best[r.key][0]):
                best[r.key] = (v, p.label)
    out = {}
    for r in rows:
        if r.key in UNCOLOURED_KI or r.key not in best:
            continue
        goal, (top, label) = r.lead_goal_rate, best[r.key]
        if goal and top:
            out[r.key] = (goal / top, top, label)
    return out


def _nightly_rows_for(data: ReportData, scope: S.Scope, period: P.Period,
                      comparison: P.Comparison | None) -> tuple:
    """`_nightly_rows`, memoised: a zone's drivers and each district's own
    page ask for the same rows."""
    key = ("nightly", scope.key, period.key,
           comparison.period.key
           if comparison is not None and comparison.period is not None
           else None)
    if key not in data._flags:
        data._flags[key] = tuple(_nightly_rows(
            data, scope, period, comparison=comparison,
            flags=data.nightly_goal_flags(period)))
    return data._flags[key]


def _drivers(data: ReportData, scope: S.Scope, period: P.Period,
             comparison: P.Comparison | None, children, funnel,
             child_rates, mission_rates) -> tuple:
    """`Driver` per child: the mission's zones, a zone's districts."""
    from app.reports import focus as FC
    if scope.level not in (S.MISSION, S.ZONE):
        return ()
    leaks = ({r.name: r for r in funnel.rows} if funnel is not None else {})
    rates = {z.key: rs for z, rs in child_rates}
    out = []
    for child in children:
        members = [(r, k) for k, r in child.index.members if r is not None]
        low_ratio, low_key = min(members) if members else (None, None)
        labels = {m.key: m.label for m in child.metrics}
        rate = None
        low = FC.lowest_rate(rates.get(child.scope.key, ()), mission_rates)
        if low is not None:
            row = next(r for r in rates[child.scope.key] if r["key"] == low[1])
            mission = next(r for r in mission_rates if r["key"] == low[1])
            rate = ((row.get("label") or low[1]), row["value"],
                    mission["value"])
        f = leaks.get(child.name)
        inp = None
        night = NIGHTLY_INPUT.get(low_key)
        if night:
            n = next((r for r in _nightly_rows_for(data, child.scope, period,
                                                   comparison)
                      if r.key == night), None)
            if n is not None and n.per_reporting_area_week is not None:
                inp = (n.label, n.per_reporting_area_week,
                       n.goal_per_area_week, n.grade.pct)
        out.append(Driver(
            name=child.name, low_key=low_key,
            low_label=labels.get(low_key, low_key or ""), low_ratio=low_ratio,
            rate=rate,
            leak=(f.leak if f is not None and not f.thin else None),
            leak_step=(f.leak_step if f is not None and not f.thin else None),
            input=inp))
    return tuple(out)


def _forward_checks(data: ReportData, scope: S.Scope, period: P.Period,
                    fwd: Forward, funnel) -> Forward:
    """4C.1's backtests and 4C.2's levers, added onto a unit's Forward."""
    from app.analytics import finding_funnel as FF
    from app.reports import focus as FC
    from app.reports import forecast as F
    if scope.level not in (S.MISSION, S.ZONE):
        return fwd
    year_check = None
    if fwd.year is not None:
        by_month = (data.baptisms_by_month if scope.level == S.MISSION
                    else None)
        if by_month is None:
            names = TB._names(data.tableau_detail, TB.AREA_COL)
            dates = data.tableau_dates()
            by_month = (F.monthly_counts(dates[2], names.isin(set(scope.areas)),
                                         data.today) if dates else {})
        year_check = F.landing_backtest(by_month, fwd.year.year,
                                        fwd.year.months)
    finish_check = ()
    det = data.tableau_detail
    cycle = P.resolve(P.THIS_TRANSFER, data.today, data.cycles)
    if (scope.level == S.MISSION and det is not None and not det.empty
            and cycle is not None and 0 < len(cycle.weeks) < cycle.full_weeks):
        if "finish_check" not in data._flags:
            data._flags["finish_check"] = tuple(
                (label, F.finish_backtest(FF.parse_dates(det, col), data.today,
                                          weeks_done=len(cycle.weeks),
                                          weeks_total=cycle.full_weeks))
                for label, col in (("Personas encontradas",
                                    "event_date_selected"),
                                   ("Fecha bautismal fijada",
                                    "first_baptism_goal_date_set")))
        finish_check = data._flags["finish_check"]
    # A zone's lever is ITS row of the mission's funnel (decision 54: per
    # zone); the zone's own funnel is by district, too small to size.
    if "mission_levers" not in data._flags:
        data._flags["mission_levers"] = FC.levers(_funnel(data, data.mission))
    levers = data._flags["mission_levers"]
    if scope.level == S.ZONE:
        levers = tuple(v for v in levers if v.name == scope.name)
    return replace(fwd, year_check=year_check, finish_check=finish_check,
                   levers=levers)


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

    strengths, growth = _strengths(data, scope, period)
    own = _ki_rows_for(data, scope, period, comparison)
    focus = _focus(data, scope, period, comparison)
    funnel = _funnel(data, scope)
    children = _ranked_children_of(data, scope, period, comparison)
    rates = _rates(data, scope, period, comparison)
    child_rates = _child_rates(data, scope, period, comparison)
    if scope.level == S.MISSION:
        # The mission's funnel is already in hand: size its levers once here
        # rather than refit it when each zone asks (`_forward_checks`).
        from app.reports import focus as FC
        data._flags["mission_levers"] = FC.levers(funnel)

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
        key_indicators=own,
        nightly_metrics=_nightly_rows_for(data, scope, period, comparison),
        scores=_scores(data, scope, period),
        rates=rates,
        children=children,
        ladder=_ladder(data, scope, period, comparison),
        siblings=_siblings(data, scope, period, comparison),
        areas_ranked=_areas_ranked(data, scope, period, comparison),
        index=_index_for(data, own, period, comparison),
        forward=_forward_checks(data, scope, period,
                                _forward(data, scope, period), funnel),
        trend_series=(_series(data, scope, _trend_period(data, period))
                      if _trend_period(data, period) else {}),
        trend=_trend_for(data, scope, period),
        focus=focus,
        funnel=funnel,
        child_rates=child_rates,
        series=_series(data, scope, period),
        strengths=strengths,
        growth=growth,
        years=_other_years(data, scope, period),
        changes=_changes(data, scope, period, comparison, focus),
        goal_reach=_goal_reach(data, scope, own),
        drivers=_drivers(data, scope, period, comparison, children, funnel,
                         child_rates, rates),
        tableau=_tableau_block(data, scope, period),
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
                                  against=against,
                                  records_from=data.weekly_records_from)
    return [build_report(s, period, comparison, data)
            for s in S.walk(data.roster, data.mission_name)]
