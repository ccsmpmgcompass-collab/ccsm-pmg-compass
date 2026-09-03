"""The mission's year against its baptismal goal.

Every other number on this dashboard describes a week or a month. This one
describes the year the mission is actually judged on, and it is the only place
the annual goal appears at all.

Three things have to be true of it or it is worse than nothing:

  * **Cumulative, not monthly.** A bar chart of monthly baptisms answers "was
    July good", which nobody is asking in September. The question is whether
    the year gets there, and only a running total can answer it.

  * **One source.** The counts come from TABLEAU_BAPTISMS — the certified
    "Total People Baptized" figure — and never from the weekly form's own
    field, which `queries.get_baptisms_actual` documents as undercounting
    badly (~18-20 against an official 41 for one month, because missionaries
    do not fill it in reliably). Splicing the two would produce a line that
    bends wherever the sources change hands.

  * **Honest about how far it reaches.** The Tableau capture runs monthly and
    lags: on 2026-09-03 the newest month it held was July. A cumulative line
    drawn to today would flatten across August and September and read as a
    mission that stopped baptising. It stops where the data stops, and says so.

Pure: no Streamlit, no sheet access. `views/01_Panel.py` renders what this
returns.
"""

from __future__ import annotations

MONTHS_IN_YEAR = 12


def _year_months(year: int) -> list[str]:
    return [f"{year:04d}-{m:02d}" for m in range(1, MONTHS_IN_YEAR + 1)]


def cumulative(monthly: dict, year: int) -> list[int | None]:
    """A year's running baptism total, one entry per month, oldest first.

    ``None`` from the first month with no capture onward — not zero, and not a
    flat continuation of the last real figure. Both of those draw a line
    through months the mission has no reading for, and the flat one is the more
    dangerous because it looks like data.

    A gap in the MIDDLE of a year ends the series there too. The running total
    after an unknown month is itself unknown, and carrying on past it would
    quietly understate every month that followed.
    """
    out: list[int | None] = []
    total = 0
    for key in _year_months(year):
        value = monthly.get(key)
        if value is None:
            out.append(None)
            continue
        if out and out[-1] is None:
            # Already broken: everything downstream rests on a total we do not
            # have, so it stays unknown even though this month itself is known.
            out.append(None)
            continue
        total += int(value)
        out.append(total)
    return out


def months_covered(series: list) -> int:
    """How many leading months of `series` are real."""
    n = 0
    for v in series:
        if v is None:
            break
        n += 1
    return n


def goal_pace(goal: float | None) -> list[float] | None:
    """The straight line to `goal`, one point per month-end.

    Deliberately linear rather than shaped to any historical seasonality. The
    mission's own months swing between 17 and 50 with no stable pattern across
    2024 and 2025, so a "seasonal" pace would be a curve fitted to noise and
    would move the finish line every time it was recomputed. A flat pace is a
    claim anyone can check: a twelfth of the goal a month.
    """
    if not goal or float(goal) <= 0:
        return None
    step = float(goal) / MONTHS_IN_YEAR
    return [step * (i + 1) for i in range(MONTHS_IN_YEAR)]


def landing_estimate(series: list, goal: float | None = None) -> dict | None:
    """Where the year ends if the months so far are representative.

    Returns ``{"value", "months", "gap"}`` — the projected year-end total, how
    many months it rests on, and how far that lands from the goal (positive is
    over, negative is short; ``None`` with no goal).

    Straight pace, and no confidence tier: unlike the Desgloses cards there is
    only ever one series here and at most twelve points in it, so a fitted
    trend would be a line through a handful of noisy months dressed up as a
    forecast. The reader is told how many months it rests on and can weigh it
    themselves.

    ``None`` before any month is captured, and once the year is complete —
    a finished year has landed, and the total is the answer.
    """
    n = months_covered(series)
    if n <= 0 or n >= MONTHS_IN_YEAR:
        return None
    total = series[n - 1]
    if not total:
        return None
    value = total / n * MONTHS_IN_YEAR
    gap = (value - float(goal)) if goal and float(goal) > 0 else None
    return {"value": value, "months": n, "gap": gap}


def pace_gap(series: list, goal: float | None) -> float | None:
    """How far ahead of (or behind) the goal's pace the year stands right now,
    measured at the last captured month.

    This is the number the landing estimate is built from, said plainly: at the
    end of month N the mission should be N/12 of the way to the goal, and this
    is the difference. Positive is ahead.
    """
    n = months_covered(series)
    pace = goal_pace(goal)
    if n <= 0 or pace is None:
        return None
    return float(series[n - 1]) - pace[n - 1]
