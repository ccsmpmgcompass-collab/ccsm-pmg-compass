"""Every KPI period's twin — app/breakdowns_engine.py's _kpi_prior_bounds.

The Desgloses page shows what a zone did. It could not show whether that was
better or worse than what the zone did before, because no code anywhere named
"before". This is that name: for each period the picker offers, the same-shaped
window immediately preceding it.

"Same-shaped" is the whole point and the reason these tests are mostly about
in-progress periods. Three days into September, holding 1-3 September against
the whole of August is not a comparison — it is arithmetic guaranteed to report
a collapse. The twin of a partial period is the matching partial slice of the
period before it.

Fixed `today` values throughout: a twin computed from date.today() would pass in
September and fail in October.
"""

from datetime import date

import pandas as pd
import pytest

from app.breakdowns_engine import (
    _KPI_PERIODS,
    _kpi_period_bounds,
    _kpi_prior_bounds,
    _slice_to_window,
)


def _twin(label, today):
    """The twin of `label` on `today`, resolved through the real current
    bounds — the two functions are always used as a pair, so they are tested as
    one."""
    cur_start, cur_end, _ = _kpi_period_bounds(label, today)
    return _kpi_prior_bounds(label, cur_start, cur_end, today)


# ── Completed periods: the twin is the whole period before ───────────────────

def test_last_week_twins_the_week_before_it():
    # 2026-09-03 is a Thursday. Last week is Mon 24 - Sun 30 August; the week
    # before it is Mon 17 - Sun 23.
    assert _twin("Last Week", date(2026, 9, 3)) == (date(2026, 8, 17), date(2026, 8, 23))


def test_last_month_twins_the_month_before_it():
    # Last month is August; its twin is the whole of July, all 31 days.
    assert _twin("Last Month", date(2026, 9, 3)) == (date(2026, 7, 1), date(2026, 7, 31))


def test_last_month_twin_crosses_the_year_boundary():
    """January's twin is December of the previous year, not December of this
    one — the arithmetic walks back a day from the period start rather than
    decrementing a month field."""
    assert _twin("Last Month", date(2026, 2, 10)) == (date(2025, 12, 1), date(2025, 12, 31))


# ── In-progress periods: the twin matches the ELAPSED shape ──────────────────

def test_this_week_twins_the_same_elapsed_days_of_last_week():
    """Thursday 3 September: the current window is Mon 31 Aug - Thu 3 Sep, four
    days. The twin is the FIRST FOUR days of last week (Mon 24 - Thu 27), not
    all seven — a seven-day ghost bar beside a four-day bar reports a collapse
    that did not happen."""
    assert _twin("This Week", date(2026, 9, 3)) == (date(2026, 8, 24), date(2026, 8, 27))


def test_this_week_on_a_monday_twins_exactly_one_day():
    """The degenerate case. On Monday the current window is one day long, so the
    twin is one day: last Monday. Anything wider would be measuring a full week
    against a single morning."""
    assert _twin("This Week", date(2026, 8, 31)) == (date(2026, 8, 24), date(2026, 8, 24))


def test_this_month_so_far_twins_the_same_elapsed_days_of_last_month():
    """3 September -> 1-3 August. The live case on the day this was written:
    DAILY_LOG starts 2026-08-09, so this twin is legitimately EMPTY, and the
    page must say "no comparison yet" rather than invent one."""
    assert _twin("This Month So Far", date(2026, 9, 3)) == (
        date(2026, 8, 1), date(2026, 8, 3))


def test_this_month_so_far_clamps_when_last_month_is_shorter():
    """31 March is the 31st elapsed day, and February has 28. The twin ends at
    28 February rather than spilling forward into March — days that are already
    inside the CURRENT window cannot also be its baseline."""
    assert _twin("This Month So Far", date(2026, 3, 31)) == (
        date(2026, 2, 1), date(2026, 2, 28))


def test_this_month_so_far_twin_crosses_the_year_boundary():
    assert _twin("This Month So Far", date(2026, 1, 5)) == (
        date(2025, 12, 1), date(2025, 12, 5))


# ── No twin at all ───────────────────────────────────────────────────────────

def test_all_time_has_no_twin():
    """Unbounded history has nothing before it. None, not an empty range: the
    caller renders "no comparison" rather than "compared against nothing"."""
    assert _twin("All Time", date(2026, 9, 3)) is None


def test_an_unknown_period_gets_no_twin_rather_than_a_wrong_one():
    """A period added to _KPI_PERIODS without a twin rule must fall through to
    None. The alternative — defaulting to "the seven days before" — would put a
    confident arrow on a window nobody defined."""
    assert _kpi_prior_bounds(
        "This Transfer So Far", date(2026, 8, 9), date(2026, 9, 3), date(2026, 9, 3)
    ) is None


def test_every_period_the_picker_offers_resolves_without_raising():
    """The picker and the twin table are two lists that must stay in step. This
    catches a period added to one and not the other."""
    today = date(2026, 9, 3)
    for label in _KPI_PERIODS:
        twin = _twin(label, today)
        assert twin is None or (twin[0] <= twin[1]), label


# ── The twin never overlaps the window it is a twin of ───────────────────────

@pytest.mark.parametrize("label", ["This Week", "Last Week", "This Month So Far",
                                   "Last Month"])
@pytest.mark.parametrize("today", [date(2026, 9, 3), date(2026, 3, 31),
                                   date(2026, 1, 1), date(2026, 12, 31)])
def test_a_twin_never_overlaps_its_own_period(label, today):
    """The one invariant that makes every downstream number honest: a day may
    not be counted as both the measurement and the baseline."""
    cur_start, cur_end, _ = _kpi_period_bounds(label, today)
    twin = _kpi_prior_bounds(label, cur_start, cur_end, today)
    assert twin is not None, label
    assert twin[1] < cur_start, f"{label} on {today}: twin ends inside the period"


# ── _slice_to_window ─────────────────────────────────────────────────────────

def _log(*dates):
    return pd.DataFrame([{"Date": d, "Area": "Alemania 1", "new_people_found": 1}
                         for d in dates])


def test_slice_keeps_both_ends_inclusive():
    out = _slice_to_window(_log("2026-08-23", "2026-08-24", "2026-08-25"),
                           date(2026, 8, 23), date(2026, 8, 24))
    assert sorted(out["Date"]) == ["2026-08-23", "2026-08-24"]


def test_slice_with_no_bounds_returns_everything():
    """All Time passes None bounds; the frame comes back whole rather than
    empty."""
    frame = _log("2026-08-23", "2026-08-24")
    assert len(_slice_to_window(frame, None, None)) == 2


def test_slice_of_a_window_before_the_records_is_empty_not_an_error():
    """The live 2026-09-03 case: This Month So Far's twin is 1-3 August and
    DAILY_LOG begins on the 9th. Empty is the correct, honest answer."""
    out = _slice_to_window(_log("2026-08-23"), date(2026, 8, 1), date(2026, 8, 3))
    assert out.empty


def test_slice_of_an_empty_frame_does_not_raise():
    assert _slice_to_window(pd.DataFrame(), date(2026, 8, 1), date(2026, 8, 3)).empty
