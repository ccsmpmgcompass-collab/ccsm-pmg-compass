"""Where to go, and what to pull — the president's front section
(PLAN-2026-10-06 Phase 3, AUDIT-2026-10-06 H6, M2, M3).

Three readings, each a different question:

  * **the shortfall, by unit** (`pareto`) — of everything the mission is
    short of leadership's goal, which units hold most of it. Absolute
    numbers, weighted like the productivity index, so a big zone's gap is
    not hidden behind a percentage;
  * **productivity × trend** (`trend_change`) — a unit below the mission
    AND falling is the focus list; below and rising is recovering;
  * **the mature funnel** (`mature_funnel`) — people found three to six
    months ago, followed to today, so the lower funnel (church, date,
    baptism) has had time to happen. The packet's window funnel never shows
    its bottom (the cohort-maturity rule is right to refuse it); this one
    can, and names each unit's largest leak against the mission.

Pure: frames and model rows in, dataclasses out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

# ── The shortfall, by unit ────────────────────────────────────────────────────


@dataclass(frozen=True)
class FocusRow:
    """One unit's part of the mission's shortfall against leadership's goal.

    ``share`` is the unit's weighted part of the total shortfall (0-100) and
    ``cumulative`` the running total down the list — the Pareto. ``gaps`` is
    ``((key, missing), ...)`` in raw counts; ``worst`` the member whose gap is
    the largest part of the mission's.
    """

    scope: object
    share: float
    cumulative: float
    gaps: tuple = ()
    worst: str | None = None
    index: float | None = None
    trend: "Trend | float | None" = None
    #: The part of ``share`` that is goal for area-weeks NOBODY REPORTED
    #: (PLAN-2026-10-06 4A.2). A district at the top of the list because an
    #: area never filed is a reporting problem, not a work problem, and the
    #: president goes there for a different conversation.
    silent: float = 0.0

    @property
    def name(self) -> str:
        return self.scope.name

    @property
    def mostly_silent(self) -> bool:
        """More than half of this unit's part is weeks nobody filed — its
        cause reads "sin informe", in both renderers."""
        return bool(self.share) and self.silent > self.share / 2


def pareto(units, weights: dict) -> tuple:
    """``units`` is ``[(scope, ki_rows, index value, trend[, silent goals])]``.

    A unit's gap on a member is leadership's goal for the period over EVERY
    area in it — silent ones included, because a goal not met by a silent
    area is still not met — less what it reported, floored at zero: a unit
    ahead of its goal does not cancel another's shortfall. Each member's gaps
    become shares of that member's total and are averaged with the index's
    weights.

    ``silent goals`` (``{key: goal}``) is leadership's goal for the
    area-weeks that filed nothing. That much of a gap — never more than the
    gap — is silence and the rest is work; `FocusRow.silent` carries the
    silence's part of the share.
    """
    totals: dict = {}
    per_unit = []
    for unit in units:
        scope, rows, index, trend = unit[:4]
        quiet = unit[4] if len(unit) > 4 else {}
        gaps, silent = {}, {}
        for r in rows:
            if r.key not in weights or r.leadership_goal is None:
                continue
            gaps[r.key] = max(0.0, r.leadership_goal - (r.actual or 0.0))
            silent[r.key] = min(gaps[r.key], max(0.0, quiet.get(r.key, 0.0)))
            totals[r.key] = totals.get(r.key, 0.0) + gaps[r.key]
        per_unit.append((scope, gaps, silent, index, trend))
    keys = [k for k, v in totals.items() if v > 0]
    if not keys:
        return ()
    weight = sum(weights[k] for k in keys)
    rows = []
    for scope, gaps, silent, index, trend in per_unit:
        parts = {k: gaps.get(k, 0.0) / totals[k] for k in keys}
        share = 100 * sum(weights[k] * parts[k] for k in keys) / weight
        quiet = 100 * sum(weights[k] * silent.get(k, 0.0) / totals[k]
                          for k in keys) / weight
        worst = max(keys, key=lambda k: weights[k] * parts[k]) if share else None
        rows.append((share, scope, tuple((k, gaps.get(k, 0.0)) for k in keys),
                     worst, index, trend, quiet))
    rows.sort(key=lambda r: (-r[0], r[1].name))
    out, run = [], 0.0
    for share, scope, gaps, worst, index, trend, quiet in rows:
        run += share
        out.append(FocusRow(scope=scope, share=share, cumulative=run,
                            gaps=gaps, worst=worst, index=index, trend=trend,
                            silent=quiet))
    return tuple(out)


# ── Productivity × trend ──────────────────────────────────────────────────────

#: A move smaller than this, in either direction, is "steady" on the quadrant.
TREND_FLAT = 5.0

#: Each half of the comparison needs this many weekly reports before the
#: trend says anything (PLAN-2026-10-06 4A.1): a district of three areas with
#: two silent compared a handful of reports and printed "−84%".
TREND_MIN_REPORTS = 6

#: The noise band is this many standard errors of one three-week mean against
#: another — 1,28 is the two-sided 80% the forecasts already use.
TREND_Z = 1.28


@dataclass(frozen=True)
class Trend:
    """A unit's six-week move, and whether it is one.

    ``value`` is the weighted change, last three weeks against the three
    before, per reporting area-week. ``band`` is how large a move the unit's
    own week-to-week wandering makes by chance; a move inside it (or inside
    TREND_FLAT) is "estable". ``reports`` is the weekly reports behind each
    half, and fewer than TREND_MIN_REPORTS on either side is "pocas cifras".
    """

    value: float
    band: float = 0.0
    reports: tuple = (0, 0)

    @property
    def thin(self) -> bool:
        return min(self.reports) < TREND_MIN_REPORTS

    @property
    def direction(self) -> int:
        if self.thin or abs(self.value) < max(TREND_FLAT, self.band):
            return 0
        return 1 if self.value > 0 else -1

    @property
    def words(self) -> str:
        if self.thin:
            return "pocas cifras"
        return {1: "subiendo", -1: "bajando", 0: "estable"}[self.direction]


def _noise_band(rows: pd.DataFrame, weights: dict, history) -> float:
    """How large a three-weeks-against-three move the unit makes by chance.

    Each week's level is the weighted mean of the members' per-report rates,
    each over its own twelve-week mean; the band is TREND_Z standard errors
    of the difference of two three-week means of that level, in percent. A
    real trend inside the twelve weeks widens it a little, which errs toward
    "estable" — the safe side for a list that sends the president somewhere.
    """
    hist = rows[rows["_week"].isin(set(history or ()))]
    if hist.empty or hist["_week"].nunique() < 6:
        return 0.0
    vals = {k: pd.to_numeric(hist[k], errors="coerce").fillna(0.0)
            for k in weights if k in hist.columns}
    means = {k: float(v.mean()) for k, v in vals.items() if v.mean() > 0}
    if not means:
        return 0.0
    weight = sum(weights[k] for k in means)
    levels = [sum(weights[k] * float(vals[k].loc[idx].mean()) / means[k]
                  for k in means) / weight
              for _, idx in hist.groupby("_week").groups.items()]
    level = np.asarray(levels, dtype=float)
    centre = float(level.mean())
    if len(level) < 2 or centre <= 0:
        return 0.0
    return TREND_Z * float(level.std(ddof=1)) * (2 / 3) ** 0.5 / centre * 100


def trend_change(weekly: pd.DataFrame, areas, weights: dict, recent, prior,
                 history=None) -> "Trend | None":
    """The weighted change, in percent, between two runs of weeks.

    Per REPORTING area-week on each side — rule 2 of the Informes layer:
    every CHANGE is per reporting area. Measured on raw sums it called all
    four zones "rising" on 2026-10-06, because the earlier weeks sat at the
    end of a transfer where a third of the forms were filed. Members with
    nothing in the prior weeks are left out rather than read as infinite
    growth. None when no member can be measured.

    ``history`` (the strip's twelve weeks) sets the noise band; without it
    only TREND_FLAT applies.
    """
    if weekly is None or weekly.empty or not recent or not prior:
        return None
    rows = weekly[weekly["_area"].isin(set(areas))]
    now = rows[rows["_week"].isin(set(recent))]
    before = rows[rows["_week"].isin(set(prior))]
    if now.empty or before.empty:
        return None
    total, weight = 0.0, 0.0
    for key, w in weights.items():
        if key not in rows.columns:
            continue
        a = float(pd.to_numeric(now[key], errors="coerce").sum()) / len(now)
        b = float(pd.to_numeric(before[key], errors="coerce").sum()) / len(before)
        if b <= 0:
            continue
        total += w * max(-100.0, min(100.0, (a - b) / b * 100))
        weight += w
    if not weight:
        return None
    return Trend(value=total / weight,
                 band=_noise_band(rows, weights, history),
                 reports=(len(now), len(before)))


def trend_value(trend) -> float | None:
    """The number a trend is, `Trend` or bare."""
    if trend is None:
        return None
    return trend.value if isinstance(trend, Trend) else float(trend)


def trend_step(trend) -> int | None:
    """−1 · 0 · +1, or None when there are too few reports to say."""
    if trend is None:
        return None
    if isinstance(trend, Trend):
        return None if trend.thin else trend.direction
    return -1 if trend <= -TREND_FLAT else (1 if trend >= TREND_FLAT else 0)


def trend_words(trend, signed) -> str:
    """What a trend cell prints: the move when it is one, otherwise why it
    is not ("estable", "pocas cifras"). ``signed`` formats the number."""
    step = trend_step(trend)
    if trend is None:
        return "—"
    if step is None:
        return "pocas cifras"
    if step == 0:
        return "estable"
    return signed(trend_value(trend))


def quadrant(index: float | None, trend) -> str | None:
    """Which corner of productivity × trend a unit sits in, in words.

    A `Trend` places a unit by its DIRECTION — a move inside its own noise
    is "estable" — and one on too few reports is not placed at all. A bare
    number is read against TREND_FLAT alone."""
    step = trend_step(trend)
    if index is None or step is None:
        return None
    below = index < 100
    if step < 0:
        return "debajo y bajando" if below else "encima y bajando"
    if step > 0:
        return "debajo y subiendo" if below else "encima y subiendo"
    return "debajo y estable" if below else "encima y estable"


# ── The mature funnel ────────────────────────────────────────────────────────

#: The cohort: people found between six and three months ago. Ninety days is
#: past the p75 lag to a baptismal date (52 days) and near the median lag to
#: baptism, so the lower funnel has had time to happen for most of them.
MATURE_FROM, MATURE_TO = 180, 90

#: A unit needs this many people in the cohort before its leak is named, and
#: a step this many people entering it before it can be the leak. Under
#: LEAK_MIN_FOUND the row prints "pocas personas" (PLAN-2026-10-06 4A.3):
#: at 30, a district's 0,4% baptism step was three people.
LEAK_MIN_FOUND = 100
LEAK_MIN_STEP = 20

#: And the step has to convert under this share of the mission's own rate to
#: count as a leak at all: 90% against the mission's 91% is not a finding.
LEAK_RATIO = 0.85

#: Short stage names for the leak sentence and the table heads.
SHORT_STAGES = {"Encontradas": "encontradas", "Intento de Contacto": "intento",
                "Contactadas con Éxito": "contacto",
                "Recibiendo Lecciones": "lecciones",
                "Asistió a la Iglesia": "iglesia",
                "Fecha de Bautismo Fijada": "fecha",
                "Bautizados": "bautismo"}


@dataclass(frozen=True)
class FunnelRow:
    """One unit's cohort: how many were found, and the share reaching each
    stage. ``leak`` names the step where it falls furthest below the
    mission's own conversion, as "de A a B"."""

    name: str
    found: int
    reached: tuple = ()          # count per stage after "found"
    pilot: bool = True
    leak: str | None = None
    #: The leak's own step, as ``(this unit's %, the mission's %)`` of the
    #: people entering it who went on — what the table prints beside the
    #: name, so a reader can check the leak without dividing two shares of
    #: the cohort by each other.
    leak_step: tuple | None = None
    #: The leak's step, as the index of the stage it fails to reach.
    leak_index: int | None = None

    def pct(self, i: int) -> float | None:
        return self.reached[i] / self.found * 100 if self.found else None

    def step(self, i: int) -> float | None:
        """Of the people who entered step ``i``, the share (0-100) who went
        on to stage ``i`` -- the rate a leak is named on, or None when fewer
        than LEAK_MIN_STEP entered it."""
        before = self.found if i == 0 else self.reached[i - 1]
        return (self.reached[i] / before * 100
                if before >= LEAK_MIN_STEP else None)

    @property
    def thin(self) -> bool:
        """Too few people for its shares to mean much — "pocas personas"."""
        return self.found < LEAK_MIN_FOUND


# ── Conversion rates against the mission, outside chance ─────────────────────

def wilson(num: float, den: float, z: float = 1.28) -> tuple | None:
    """The 80% Wilson range of ``num / den``, in percent (0-100)."""
    if not den or den <= 0:
        return None
    p = max(0.0, min(1.0, num / den))
    centre = (p + z * z / (2 * den)) / (1 + z * z / den)
    half = (z * ((p * (1 - p) / den + z * z / (4 * den * den)) ** 0.5)
            / (1 + z * z / den))
    return (max(0.0, centre - half) * 100, min(1.0, centre + half) * 100)


def rate_gap(unit: dict | None, mission: dict | None) -> float | None:
    """A unit's rate minus the mission's, in points — None when the
    mission's rate sits inside the unit's own 80% range, so a zone is never
    named for a gap its own counts could produce by chance (PLAN 4A.3)."""
    if (not unit or not mission or unit.get("value") is None
            or mission.get("value") is None):
        return None
    span = wilson(unit.get("numerator") or 0.0, unit.get("denominator") or 0.0)
    if span is not None and span[0] <= mission["value"] <= span[1]:
        return None
    return unit["value"] - mission["value"]


def lowest_rate(unit_rates, mission_rates) -> tuple | None:
    """``(gap, key)`` of the rate furthest UNDER the mission's, outside
    chance; None when no rate is."""
    mission = {r["key"]: r for r in mission_rates}
    gaps = [(g, r["key"]) for r in unit_rates
            if (g := rate_gap(r, mission.get(r["key"]))) is not None and g < 0]
    return min(gaps) if gaps else None


@dataclass(frozen=True)
class MatureFunnel:
    start: date
    end: date
    stages: tuple = ()           # Spanish labels, after "found"
    rows: tuple = ()
    mission: FunnelRow | None = None


def mature_funnel(found_d, stage_dates, stage_labels, groups, today: date,
                  *, found_label: str = "Encontradas") -> MatureFunnel | None:
    """``groups`` is ``[(name, mask, pilot)]``; ``stage_dates`` the parsed
    date column of each stage after "found", in funnel order."""
    start = today - timedelta(days=MATURE_FROM)
    end = today - timedelta(days=MATURE_TO)
    found = np.asarray(pd.to_datetime(pd.Series(found_d)),
                       dtype="datetime64[ns]")
    lo = np.datetime64(pd.Timestamp(start).to_datetime64(), "ns")
    hi = np.datetime64(pd.Timestamp(end).to_datetime64(), "ns")
    cohort = (found >= lo) & (found <= hi)
    reached = [~np.isnat(np.asarray(pd.to_datetime(pd.Series(s)),
                                    dtype="datetime64[ns]")) for s in stage_dates]

    def row(name, mask, pilot):
        mask = cohort & np.asarray(mask, dtype=bool)
        n = int(mask.sum())
        return FunnelRow(name=name, found=n, pilot=pilot,
                         reached=tuple(int((mask & r).sum()) for r in reached))

    mission = row("la misión", np.ones(len(found), dtype=bool), True)
    if not mission.found:
        return None
    labels = (found_label,) + tuple(stage_labels)

    def conv(r, i):
        before = r.found if i == 0 else r.reached[i - 1]
        return r.reached[i] / before if before >= LEAK_MIN_STEP else None

    rows = []
    for name, mask, pilot in groups:
        r = row(name, mask, pilot)
        leak = step = at = None
        if r.found >= LEAK_MIN_FOUND:
            ratios = [(conv(r, i) / conv(mission, i), i)
                      for i in range(len(stage_labels))
                      if conv(r, i) is not None and conv(mission, i)]
            if ratios:
                ratio, i = min(ratios)
                if ratio < LEAK_RATIO:
                    leak = (f"{SHORT_STAGES.get(labels[i], labels[i].lower())}"
                            f" a {SHORT_STAGES.get(labels[i + 1], labels[i + 1].lower())}")
                    step = (conv(r, i) * 100, conv(mission, i) * 100)
                    at = i
        rows.append(FunnelRow(name=r.name, found=r.found, reached=r.reached,
                              pilot=pilot, leak=leak, leak_step=step,
                              leak_index=at))
    return MatureFunnel(start=start, end=end, stages=tuple(stage_labels),
                        rows=tuple(rows), mission=mission)


# ── What each leak is worth (PLAN-2026-10-06 4C.2, decision 54) ──────────────

#: The mature cohort spans this many days of finding; a lever is scaled from
#: it to one transfer's six weeks.
COHORT_DAYS = MATURE_FROM - MATURE_TO
LEVER_DAYS = 42


@dataclass(frozen=True)
class Lever:
    """If a unit's largest leak converted at the mission's rate: how many
    more baptismal dates and baptisms per six weeks of finding, as ranges.

    The range carries two uncertainties: the unit's own conversion at the
    leak (its 80% Wilson range), and what happens downstream of it (the
    unit's own later steps, or the mission's, whichever gives less and
    more). Never coloured; a lever is a size, not a verdict.
    """

    name: str
    leak: str
    pilot: bool = True
    dates: tuple | None = None          # (low, high) per six weeks
    baptisms: tuple | None = None

    @property
    def size(self) -> float:
        lo, hi = self.baptisms or (0.0, 0.0)
        return (lo + hi) / 2


def _step(r, i):
    before = r.found if i == 0 else r.reached[i - 1]
    return r.reached[i] / before if before else None


def levers(funnel) -> tuple:
    """Every unit with a named leak in a `MatureFunnel`, largest first."""
    if funnel is None or funnel.mission is None:
        return ()
    labels = tuple(funnel.stages)
    try:
        date_i = labels.index("Fecha de Bautismo Fijada")
        bapt_i = labels.index("Bautizados")
    except ValueError:
        return ()
    m = funnel.mission
    scale = LEVER_DAYS / COHORT_DAYS
    out = []
    for r in funnel.rows:
        i = r.leak_index
        if i is None or r.thin:
            continue
        entering = r.found if i == 0 else r.reached[i - 1]
        own, target = _step(r, i), _step(m, i)
        span = wilson(r.reached[i], entering)
        if own is None or target is None or span is None:
            continue
        lo_extra = max(0.0, entering * (target - span[1] / 100))
        hi_extra = max(0.0, entering * (target - span[0] / 100))

        def carried(k):
            if k < i:
                return None
            if k == i:
                return (lo_extra * scale, hi_extra * scale)
            factors = []
            for row in (r, m):
                f = 1.0
                for j in range(i + 1, k + 1):
                    c = _step(row, j)
                    if c is None:
                        c = _step(m, j) or 0.0
                    f *= c
                factors.append(f)
            return (lo_extra * min(factors) * scale,
                    hi_extra * max(factors) * scale)

        out.append(Lever(name=r.name, leak=r.leak, pilot=r.pilot,
                         dates=carried(date_i), baptisms=carried(bapt_i)))
    return tuple(sorted(out, key=lambda v: (-v.size, v.name)))
