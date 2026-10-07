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
    trend: float | None = None

    @property
    def name(self) -> str:
        return self.scope.name


def pareto(units, weights: dict) -> tuple:
    """``units`` is ``[(scope, ki_rows, index value, trend)]``.

    A unit's gap on a member is leadership's goal for the period over EVERY
    area in it — silent ones included, because a goal not met by a silent
    area is still not met — less what it reported, floored at zero: a unit
    ahead of its goal does not cancel another's shortfall. Each member's gaps
    become shares of that member's total and are averaged with the index's
    weights.
    """
    totals: dict = {}
    per_unit = []
    for scope, rows, index, trend in units:
        gaps = {}
        for r in rows:
            if r.key not in weights or r.leadership_goal is None:
                continue
            gaps[r.key] = max(0.0, r.leadership_goal - (r.actual or 0.0))
            totals[r.key] = totals.get(r.key, 0.0) + gaps[r.key]
        per_unit.append((scope, gaps, index, trend))
    keys = [k for k, v in totals.items() if v > 0]
    if not keys:
        return ()
    weight = sum(weights[k] for k in keys)
    rows = []
    for scope, gaps, index, trend in per_unit:
        parts = {k: gaps.get(k, 0.0) / totals[k] for k in keys}
        share = 100 * sum(weights[k] * parts[k] for k in keys) / weight
        worst = max(keys, key=lambda k: weights[k] * parts[k]) if share else None
        rows.append((share, scope, tuple((k, gaps.get(k, 0.0)) for k in keys),
                     worst, index, trend))
    rows.sort(key=lambda r: (-r[0], r[1].name))
    out, run = [], 0.0
    for share, scope, gaps, worst, index, trend in rows:
        run += share
        out.append(FocusRow(scope=scope, share=share, cumulative=run,
                            gaps=gaps, worst=worst, index=index, trend=trend))
    return tuple(out)


# ── Productivity × trend ──────────────────────────────────────────────────────

#: A move smaller than this, in either direction, is "steady" on the quadrant.
TREND_FLAT = 5.0


def trend_change(weekly: pd.DataFrame, areas, weights: dict, recent, prior):
    """The weighted change, in percent, between two runs of weeks.

    Per REPORTING area-week on each side — rule 2 of the Informes layer:
    every CHANGE is per reporting area. Measured on raw sums it called all
    four zones "rising" on 2026-10-06, because the earlier weeks sat at the
    end of a transfer where a third of the forms were filed. Members with
    nothing in the prior weeks are left out rather than read as infinite
    growth. None when no member can be measured.
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
    return total / weight if weight else None


def quadrant(index: float | None, trend: float | None) -> str | None:
    """Which corner of productivity × trend a unit sits in, in words."""
    if index is None or trend is None:
        return None
    below = index < 100
    if trend <= -TREND_FLAT:
        return "debajo y bajando" if below else "encima y bajando"
    if trend >= TREND_FLAT:
        return "debajo y subiendo" if below else "encima y subiendo"
    return "debajo y estable" if below else "encima y estable"


# ── The mature funnel ────────────────────────────────────────────────────────

#: The cohort: people found between six and three months ago. Ninety days is
#: past the p75 lag to a baptismal date (52 days) and near the median lag to
#: baptism, so the lower funnel has had time to happen for most of them.
MATURE_FROM, MATURE_TO = 180, 90

#: A unit needs this many people in the cohort before its leak is named, and
#: a step this many people entering it before it can be the leak.
LEAK_MIN_FOUND = 30
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

    def pct(self, i: int) -> float | None:
        return self.reached[i] / self.found * 100 if self.found else None


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
        leak = None
        if r.found >= LEAK_MIN_FOUND:
            ratios = [(conv(r, i) / conv(mission, i), i)
                      for i in range(len(stage_labels))
                      if conv(r, i) is not None and conv(mission, i)]
            if ratios:
                ratio, i = min(ratios)
                if ratio < LEAK_RATIO:
                    leak = (f"{SHORT_STAGES.get(labels[i], labels[i].lower())}"
                            f" a {SHORT_STAGES.get(labels[i + 1], labels[i + 1].lower())}")
        rows.append(FunnelRow(name=r.name, found=r.found, reached=r.reached,
                              pilot=pilot, leak=leak))
    return MatureFunnel(start=start, end=end, stages=tuple(stage_labels),
                        rows=tuple(rows), mission=mission)
