"""Which calendar year a transfer belongs to, and how a year's goals total.

A transfer cycle is six weeks long and the calendar year is not a multiple of
six weeks, so roughly one cycle a year straddles New Year's Day. `2026-8` runs
2026-11-30 to 2027-01-10: thirty-two days in 2026, ten in 2027.

Two different questions follow from that, and they get two different answers —
this is Zackary's ruling of 2026-09-05, and the distinction is the whole reason
this module exists rather than a one-line `start.year`:

**Which year is a cycle FILED under?**  The year holding more of its days owns
it, and an exact 21/21 split goes to the year it ENDS in. This decides one
thing only: where a cycle appears for display and editing, so every cycle
appears exactly once and none goes missing. `2026-8` files under 2026 (32 days
against 10); the 2027 year-end cycle, 2027-12-13 to 2028-01-23, files under
**2028** (23 days against 19) even though it is labelled a 2027 cycle. Filing by
"the year it starts in" would have put it in 2027, which is why that rule was
rejected.

**How much of a cycle's GOAL counts toward a year?**  Its days in that year, as
a fraction of its own length. `2026-8` contributes 32/42 of its goal to 2026 and
10/42 to 2027. Not its ownership — a year's goal and a year's actuals have to
cover the same span or the percentage between them means nothing.

**ACTUALS ARE NOT THIS MODULE'S BUSINESS.** They always follow the real date: a
day's work counts in the calendar year it actually happened, whatever cycle it
sat in and whatever that cycle is filed under. `analytics/annual_baptisms.py`
already works this way, keying off real `YYYY-MM` months, and the Panel's annual
chart rests on it. Nothing here should ever be reached for when summing what
happened — if a caller passes actuals through `prorate()`, that is the bug.

Pure: dates in, numbers out, no sheet access. See PLAN-2026-09-05-backlog.md
§7.3, and `utils.transfer_helpers.transfer_cycles()` for where the (start, end)
pairs come from.
"""

from __future__ import annotations

from datetime import date


def cycle_days(start: date, end: date) -> int:
    """How many days a cycle covers, both ends INCLUSIVE.

    Inclusive because that is what `transfer_window` returns and what "2026-09-07
    through 2026-10-18" means to a person: 42 days, not 41. Zero for an end
    before its start rather than a negative length — a mis-ordered pair is bad
    data, and a negative denominator would silently invert every share below.
    """
    if start is None or end is None or end < start:
        return 0
    return (end - start).days + 1


def days_in_year(start: date, end: date, year: int) -> int:
    """How many of the cycle's days fall in `year`.

    Computed by clipping the cycle to the year's own bounds rather than by
    walking days, so a caller cannot make this expensive by handing it a long
    range.
    """
    if cycle_days(start, end) == 0:
        return 0
    lo = max(start, date(year, 1, 1))
    hi = min(end, date(year, 12, 31))
    return cycle_days(lo, hi)


def years_spanned(start: date, end: date) -> list[int]:
    """Every calendar year the cycle touches, ascending.

    One year for the ordinary case, two for a straddler. Longer spans are not a
    real transfer cycle but are handled rather than rejected — a schedule row
    with a mistyped date should degrade, not crash a page.
    """
    if cycle_days(start, end) == 0:
        return []
    return list(range(start.year, end.year + 1))


def owning_year(start: date, end: date) -> int | None:
    """The single calendar year this cycle is FILED under.

    The year holding more of its days. **On an exact tie the year it ENDS in
    wins** — Zackary's call, and not an arbitrary tie-break: the alternative
    ("the year it starts in") files the 2027 year-end cycle under 2027 when 23
    of its 42 days are in 2028.

    None for an unusable pair, so a caller can drop a bad schedule row instead
    of filing it under a year it does not belong to.
    """
    if cycle_days(start, end) == 0:
        return None
    best_year, best_days = None, -1
    # Ascending, and the comparison is strictly greater — so a later year ties
    # its way past an earlier one, which IS the "the year it ends in" rule.
    for y in years_spanned(start, end):
        d = days_in_year(start, end, y)
        if d > best_days:
            best_year, best_days = y, d
        elif d == best_days:
            best_year = y
    return best_year


def year_share(start: date, end: date, year: int) -> float:
    """The fraction of this cycle that falls in `year`, 0.0 to 1.0.

    `2026-8` gives 32/42 for 2026 and 10/42 for 2027. A cycle wholly inside one
    year gives 1.0 for it and 0.0 for every other, so a caller never needs to ask
    whether a cycle straddles before pro-rating — the ordinary case is the
    general case with a share of one.
    """
    total = cycle_days(start, end)
    if not total:
        return 0.0
    return days_in_year(start, end, year) / total


def prorate(value: float, start: date, end: date, year: int) -> float:
    """`value` scaled to the part of this cycle that lands in `year`.

    For GOALS only — see the module docstring. A goal is a target spread evenly
    across the cycle, so two thirds of the cycle carries two thirds of the
    target; an ACTUAL is a record of a day that either happened in the year or
    did not, and splitting one by ratio would invent activity.

    Returns a float. Rounding is the caller's business and belongs at the point
    of display: rounding each cycle before summing a year drifts the total by up
    to half a unit per cycle, which on seven metrics across eight cycles is a
    visible error in a table that is supposed to add up.
    """
    return float(value or 0) * year_share(start, end, year)


def cycles_owned_by(cycles: list[dict], year: int) -> list[dict]:
    """The cycles FILED under `year`, in the order given.

    `cycles` are dicts carrying at least ``start`` and ``end`` — the shape
    `transfer_helpers.transfer_cycles()` returns. Used for the year picker's
    "N of M cambios tienen metas" coverage caption: M is how many cycles the year
    owns, which is a question about filing, not about pro-rating.
    """
    return [c for c in cycles
            if owning_year(c.get("start"), c.get("end")) == year]


def years_in_schedule(cycles: list[dict]) -> list[int]:
    """Every year any cycle is filed under, ascending — the year picker's options.

    Deliberately ownership and not `years_spanned`: a year that only ever
    receives ten pro-rated days from one straddling cycle has no cycle of its
    own to set a goal on, and offering it as a year to plan would show a page
    with nothing on it.
    """
    years = {owning_year(c.get("start"), c.get("end")) for c in cycles}
    return sorted(y for y in years if y is not None)


def year_goal_total(cycles: list[dict], goals: dict, metric: str, year: int) -> float:
    """A metric's goal for `year`: every cycle's goal, each pro-rated by its days.

    `goals` maps a cycle's ``start`` (a `date`) to that cycle's saved goal dict —
    the shape `goals_queries` returns, keyed the way AREA_TRANSFER_GOALS is keyed
    (§7.2). Cycles with no saved goal contribute nothing, which is why the
    coverage caption is mandatory beside any number this returns: a year total
    resting on three of eight cycles must never read as the whole year's target.

    Every cycle in `cycles` is considered, not only the ones the year owns — that
    is the point of pro-rating. The straddler filed under 2026 still gives 2027
    its ten days.
    """
    total = 0.0
    for c in cycles:
        start, end = c.get("start"), c.get("end")
        row = goals.get(start)
        if not row:
            continue
        total += prorate(row.get(metric, 0), start, end, year)
    return total


def year_bounds(year: int, today: date | None = None) -> tuple[date, date]:
    """The span a year's ACTUALS are summed over: Jan 1 to Dec 31, or to today.

    A year still running is measured to today, not to its December 31st — the
    same "so far" rule the period pickers use, and without it a year in progress
    reports its goal against nine months of actuals and calls the mission
    behind. A past or future year gets its whole self.
    """
    start, end = date(year, 1, 1), date(year, 12, 31)
    if today is not None and start <= today <= end:
        return start, today
    return start, end


def weeks_in_cycle(start: date, end: date) -> float:
    """A cycle's length in weeks, from its real dates.

    `TRANSFER_SCHEDULE.Weeks` is what the mission INTENDED; the dates are what
    happened, and a cycle cut short or run long is described by its dates
    everywhere else in this app (see `transfer_cycles`). Used to turn a transfer
    goal into the weekly figure `_resolve_group_goal`'s contract expects (§7.5).

    Returns a float — 42 days is exactly 6.0, but a cycle that ran 44 days is
    6.29 and rounding it to 6 would hand back a weekly rate that does not
    reproduce the transfer total it came from.
    """
    days = cycle_days(start, end)
    return days / 7 if days else 0.0


def straddlers_for_year(cycles: list[dict], year: int) -> list[dict]:
    """Cycles that give `year` only part of their goal, oldest first.

    A cycle qualifies when it touches `year` and at least one other year — so a
    year normally has at most two: the one arriving from the previous December
    and the one leaving into next January.

    Not used by the arithmetic; `year_goal_total` already handles straddlers by
    construction. This is for saying out loud on the year summary WHICH cycle is
    split and by how much. A pro-rated total that does not explain itself is the
    "48% de 1.200" problem again.
    """
    out = [c for c in cycles
           if c.get("start") and c.get("end")
           and days_in_year(c["start"], c["end"], year) > 0
           and len(years_spanned(c["start"], c["end"])) > 1]
    return sorted(out, key=lambda c: c["start"])
