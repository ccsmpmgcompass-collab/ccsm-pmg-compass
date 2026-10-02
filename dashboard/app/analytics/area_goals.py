"""Each sector's own nightly goals, recomputed every week.

PLAN-2026-10-02-goals.md, step G6 (decisions G-D7..G-D10). Zackary asked for
goals "individualized by sector based off of their previous numbers ... where
they are at plus 10% ... automatically adjusted slightly every week". So, for
every active sector and every nightly metric, for the week starting
``week_start``:

  * **pace** — the sector's total over the six complete weeks before
    ``week_start``, divided by the nights it actually filed, times seven: what
    it does in a week on the nights it reports (G-D5's basis).
  * **too little history** (fewer than ``MIN_NIGHTS`` filed nights — a new,
    renamed or silent sector) borrows its zone's median pace among the sectors
    that do qualify, then the mission's pooled pace (G-D9). With no nightly data
    at all, the configured `AGENT_CONFIG` goal stands in, unstretched.
  * **goal** — ``ceil(pace x stretch)``, never below 1 (G-D7), moved at most
    ``max(1, CAP x last week's goal)`` from last week's computed goal (G-D8).
    The minimum step of 1 is what lets a small goal move at all: 10% of 2 is
    0.2, and a 2 that may only ever become 1.8..2.2 is a 2 forever.
  * **leadership's goal wins** (G-D10): an override replaces the computed goal
    and is recorded as such; next week the cap does not anchor on it.

Pure: no Streamlit, no sheet access. The weekly job (G7) and the dashboard
both call this, so the rule lives in one place.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from app.analytics.goal_recalibration import pace
from app.analytics.period_delta import area_nights

#: Complete weeks the pace is measured over — one transfer's length.
WINDOW_WEEKS = 6

#: Filed nights a sector needs in the window before its own pace is trusted:
#: two full weeks.
MIN_NIGHTS = 14

#: The most a goal may move in one week, as a share of last week's (G-D8).
CAP = 0.10

LEADERSHIP, OWN, ZONE, MISSION, CONFIG = (
    "leadership", "own", "zone", "mission", "config")


@dataclass(frozen=True)
class AreaGoal:
    goal: int | None
    source: str
    pace: float | None = None


def window(week_start: date, weeks: int = WINDOW_WEEKS) -> tuple[date, date]:
    """The six complete Monday–Sunday weeks that end the day before
    ``week_start``."""
    end = week_start - timedelta(days=1)
    return end - timedelta(days=7 * weeks - 1), end


def week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def capped(raw: float, previous: float | None, cap: float = CAP) -> float:
    """``raw`` held within one week's step of ``previous`` (G-D8)."""
    if previous is None or previous <= 0:
        return raw
    step = max(1.0, cap * previous)
    return min(max(raw, previous - step), previous + step)


def to_goal(raw: float | None) -> int | None:
    """Rounded up, never below 1. The epsilon keeps a value that is whole up to
    float noise (10 x 1.1) from rounding up a whole extra unit."""
    if raw is None:
        return None
    return max(1, math.ceil(raw - 1e-9))


def _rows(daily: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if daily is None or daily.empty or "Date" not in daily.columns:
        return pd.DataFrame()
    d = pd.to_datetime(daily["Date"], errors="coerce").dt.date
    out = daily[(d >= start) & (d <= end)].copy()
    if "Area" in out.columns:
        out["Area"] = out["Area"].astype(str).str.strip()
    return out


def compute(daily: pd.DataFrame, roster: dict, keys, *, week_start: date,
            stretch: float = 1.10, previous: dict | None = None,
            previous_overridden: dict | None = None,
            overrides: dict | None = None, configured: dict | None = None,
            weeks: int = WINDOW_WEEKS, min_nights: int = MIN_NIGHTS,
            cap: float = CAP) -> dict:
    """``{area: {key: AreaGoal}}`` for every sector in ``roster``.

    ``roster`` — {area: zone} for the active sectors.
    ``previous`` — {area: {key: goal}}: last week's effective goals.
    ``previous_overridden`` — {area: set(keys)} that were leadership's last week.
    ``overrides`` — {area: {key: goal}} leadership's standing goals.
    ``configured`` — {key: goal}: AGENT_CONFIG's GOAL_* rows, the last fallback.
    """
    previous = previous or {}
    previous_overridden = previous_overridden or {}
    overrides = overrides or {}
    configured = configured or {}
    start, end = window(week_start, weeks)
    rows = _rows(daily, start, end)
    if not rows.empty and "Area" in rows.columns:
        rows = rows[rows["Area"].isin(set(roster))]

    by_area = ({a: g for a, g in rows.groupby("Area")}
               if not rows.empty and "Area" in rows.columns else {})
    nights = {a: area_nights(g) for a, g in by_area.items()}
    qualified = {a for a, n in nights.items() if n >= min_nights}

    out: dict = {}
    for key in keys:
        own = {a: pace(by_area[a], key) for a in qualified}
        own = {a: v for a, v in own.items() if v is not None}
        zone_paces: dict = {}
        for a, v in own.items():
            zone_paces.setdefault(roster.get(a, ""), []).append(v)
        zone_median = {z: statistics.median(v) for z, v in zone_paces.items() if v}
        mission = pace(rows, key) if not rows.empty else None

        for area, zone in roster.items():
            standing = (overrides.get(area) or {}).get(key)
            if standing is not None and standing > 0:
                out.setdefault(area, {})[key] = AreaGoal(
                    goal=int(standing), source=LEADERSHIP, pace=own.get(area))
                continue
            if area in own:
                measured, source = own[area], OWN
            elif zone in zone_median:
                measured, source = zone_median[zone], ZONE
            elif mission is not None:
                measured, source = mission, MISSION
            else:
                measured, source = None, CONFIG
            if measured is None:
                fallback = configured.get(key)
                out.setdefault(area, {})[key] = AreaGoal(
                    goal=to_goal(fallback) if fallback else None, source=CONFIG)
                continue
            prev = (previous.get(area) or {}).get(key)
            if key in (previous_overridden.get(area) or set()):
                prev = None          # do not anchor on leadership's number
            raw = capped(measured * stretch, prev, cap)
            out.setdefault(area, {})[key] = AreaGoal(
                goal=to_goal(raw), source=source, pace=measured)
    return out


def weighted_goal(rows: pd.DataFrame, key: str, goal_for) -> float | None:
    """The goal per sector-week that ``rows``' filed nights were held to.

    Each (sector, date) night carries the goal its sector had for that night's
    week — ``goal_for(area, monday, key)`` — and the result is their average,
    weighted by nights (PLAN-2026-10-02-goals.md, G10). Every screen divides
    by this exactly as it used to divide by the one mission-wide number, so
    ``actual / reporting_equivalents`` against it is the same as the actual
    against the sum of every sector's own goal for the nights it filed — and
    the screens cannot drift apart, because there is one copy of this.

    None when no filed night has a goal.
    """
    if rows is None or rows.empty or "Date" not in rows.columns or "Area" not in rows.columns:
        return None
    d = pd.to_datetime(rows["Date"], errors="coerce").dt.date
    nights = (pd.DataFrame({"Area": rows["Area"].astype(str).str.strip(), "d": d})
                .dropna().drop_duplicates())
    total, n = 0.0, 0
    for area, day in zip(nights["Area"], nights["d"]):
        g = goal_for(area, week_monday(day), key)
        if g is None or g <= 0:
            continue
        total += float(g)
        n += 1
    return total / n if n else None


@dataclass
class GoalBook:
    """``goal_for(area, monday, key)`` as a picklable object (a packet's
    ReportData is pickled to measure layouts; a closure would not be).

    ``by_week`` — {(area, "YYYY-MM-DD"): {key: goal}} from AREA_WEEKLY_GOALS;
    ``newest`` — the newest week in it; ``current`` — {area: {key: goal}} from
    GOALS_CONFIG, read only for weeks at or after ``newest``; ``defaults`` —
    {key: goal} from AGENT_CONFIG. See `queries.get_sector_goal_lookup`.
    """
    by_week: dict
    newest: str | None
    current: dict
    defaults: dict

    def __call__(self, area, monday, key):
        week = monday.isoformat() if hasattr(monday, "isoformat") else str(monday)
        g = self.by_week.get((area, week), {}).get(key)
        if g:
            return g
        if self.newest is None or week >= self.newest:
            g = self.current.get(area, {}).get(key)
            if g:
                return g
        return self.defaults.get(key)
