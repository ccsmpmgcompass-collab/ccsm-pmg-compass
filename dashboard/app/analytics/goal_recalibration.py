"""The nightly goals, recalibrated from what the mission actually does.

PLAN-2026-10-02-goals.md, steps G2/G3. This replaces `CCSM_Agent2.gs`
(decision G-D4), which suggested the same kind of number but read it from the
CURRENT transfer — empty on the transfer day the runbook ran it — so every one
of its 1,035 suggestions on 2026-09-08 was the old goal plus 10%, and no screen
ever showed them.

The rule is the one every recommendation in the app already follows: the
mission's own recent pace, plus the `rec_stretch_pct` nudge. Concretely, for
each nightly metric that has a `GOAL_*` row:

  * **pace** — the total over the last six complete Monday–Sunday weeks,
    divided by the nights actually filed, times seven: what a reporting area
    does in a week (decision G-D5, the same basis every screen now grades on).
    Only the roster's active areas count, so a retired area's old rows do not
    pull the figure.
  * **proposed** — ``ceil(pace x (1 + nudge))``, never below 1 (decision G-D2's
    spirit: a goal of 0 is not a goal).

The trend beside it is the one useful thing Agent2 carried: this transfer's
pace against the last one's, on the same per-reported-night basis.

Pure: no Streamlit, no sheet access.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from app.analytics.period_delta import area_nights

#: How many complete weeks the pace is measured over — one transfer's length,
#: so on transfer day the window is exactly the cycle that just closed.
WINDOW_WEEKS = 6

#: How far this transfer's pace must move from the last one's before the trend
#: says it moved. Agent2's own 10% threshold, kept so the label means what it
#: meant there.
TREND_BAND = 0.10

UP, DOWN, FLAT = "up", "down", "flat"


@dataclass(frozen=True)
class Window:
    start: date
    end: date
    nights: int
    possible: int

    @property
    def filed_share(self) -> float | None:
        return self.nights / self.possible if self.possible else None


@dataclass(frozen=True)
class Proposal:
    key: str
    current: float | None
    pace: float | None
    proposed: int | None
    this_cycle: float | None = None
    last_cycle: float | None = None

    @property
    def change(self) -> float | None:
        if self.proposed is None or self.current is None:
            return None
        return self.proposed - self.current

    @property
    def attainment(self) -> float | None:
        """The measured pace as a percentage of the CURRENT goal."""
        if self.pace is None or not self.current:
            return None
        return self.pace / self.current * 100.0

    @property
    def trend(self) -> str:
        """This transfer against the last, or "" when either side is missing."""
        if self.this_cycle is None or not self.last_cycle:
            return ""
        ratio = self.this_cycle / self.last_cycle
        if ratio > 1 + TREND_BAND:
            return UP
        if ratio < 1 - TREND_BAND:
            return DOWN
        return FLAT


def last_complete_sunday(today: date) -> date:
    """The most recent Sunday whose whole week is behind ``today``.

    On a Sunday that is the Sunday BEFORE: that day's reports are still
    arriving, so its week is not complete yet.
    """
    back = today.weekday() + 1          # Monday 1 ... Sunday 7
    return today - timedelta(days=back)


def measure_window(today: date, weeks: int = WINDOW_WEEKS) -> tuple[date, date]:
    end = last_complete_sunday(today)
    return end - timedelta(days=7 * weeks - 1), end


def _slice(daily: pd.DataFrame, areas: set, start: date, end: date) -> pd.DataFrame:
    if daily is None or daily.empty or "Date" not in daily.columns:
        return pd.DataFrame()
    d = pd.to_datetime(daily["Date"], errors="coerce").dt.date
    out = daily[(d >= start) & (d <= end)]
    if areas and "Area" in out.columns:
        out = out[out["Area"].astype(str).str.strip().isin(areas)]
    return out


def pace(rows: pd.DataFrame, key: str) -> float | None:
    """``key``'s total over the nights in ``rows``, per reporting area-week."""
    nights = area_nights(rows)
    if not nights or key not in rows.columns:
        return None
    total = float(pd.to_numeric(rows[key], errors="coerce").fillna(0).sum())
    return total / nights * 7.0


def proposed_goal(measured: float | None, stretch: float) -> int | None:
    """``ceil(measured x stretch)``, never below 1; None with no measurement.

    The tiny epsilon keeps a pace that is exactly whole after the stretch
    (10 x 1.1 = 11.000000000000002) from ceiling to 12.
    """
    if measured is None:
        return None
    return max(1, math.ceil(measured * stretch - 1e-9))


def _cycle_bounds(cycles: list[dict], end: date) -> tuple[tuple | None, tuple | None]:
    """(this cycle's start..end, the previous cycle's) as seen from ``end``.

    "This" runs from the start of the cycle holding ``end`` up to ``end``
    itself, so it covers complete weeks only.
    """
    ordered = sorted((c for c in cycles or [] if c.get("start")),
                     key=lambda c: c["start"])
    for i, c in enumerate(ordered):
        if c["start"] <= end <= c["end"]:
            this = (c["start"], end)
            last = ((ordered[i - 1]["start"], ordered[i - 1]["end"])
                    if i > 0 else None)
            return this, last
    return None, None


def propose(daily: pd.DataFrame, areas, goals: dict, keys, *, today: date,
            stretch: float = 1.10, cycles: list[dict] | None = None,
            weeks: int = WINDOW_WEEKS) -> tuple[Window, list[Proposal]]:
    """Every ``keys`` metric's measured pace and proposed goal.

    ``goals`` is `{metric: current per-area weekly goal}`; ``areas`` the active
    roster's area names; ``cycles`` `transfer_cycles()`, for the trend.
    """
    areas = {str(a).strip() for a in (areas or []) if str(a).strip()}
    start, end = measure_window(today, weeks)
    rows = _slice(daily, areas, start, end)
    window = Window(start=start, end=end, nights=area_nights(rows),
                    possible=len(areas) * 7 * weeks)

    this_b, last_b = _cycle_bounds(cycles, end)
    this_rows = _slice(daily, areas, *this_b) if this_b else pd.DataFrame()
    last_rows = _slice(daily, areas, *last_b) if last_b else pd.DataFrame()

    out = []
    for key in keys:
        measured = pace(rows, key)
        current = goals.get(key)
        out.append(Proposal(
            key=key,
            current=float(current) if current not in (None, "") else None,
            pace=measured,
            proposed=proposed_goal(measured, stretch),
            this_cycle=pace(this_rows, key) if not this_rows.empty else None,
            last_cycle=pace(last_rows, key) if not last_rows.empty else None,
        ))
    return window, out
