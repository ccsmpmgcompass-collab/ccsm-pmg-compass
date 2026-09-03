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
        "Since Training", date(2026, 8, 9), date(2026, 9, 3), date(2026, 9, 3)
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


# ══════════════════════════════════════════════════════════════════════════════
# Step 2 (A3) — what the arrow under a card is allowed to say
# ══════════════════════════════════════════════════════════════════════════════

from app import i18n
from app.analytics.period_delta import MIN_COMPARABLE_DAYS, UP, period_delta
from app.breakdowns_engine import _comparison_note, _twin_label


@pytest.fixture
def english(monkeypatch):
    """These assertions are about WHAT the page says, not which language it says
    it in. CCSM's MISSION_LANGUAGE is ES, so t() returns Spanish by default and
    an assertion on the English wording would fail for the wrong reason. The
    Spanish side is held by test_i18n_coverage, which fails if any of these
    strings is missing from es.py — as it did when they were first written."""
    monkeypatch.setattr(i18n, "get_lang", lambda: "en")


def test_the_twin_label_never_claims_a_whole_month_on_a_partial_one(english):
    """"This Month So Far" is compared against the same ELAPSED days of last
    month, so its label must not read "vs last month" — that would describe an
    arithmetic the code does not perform."""
    assert _twin_label("This Month So Far") == "vs same days last month"
    assert _twin_label("Last Month") == "vs the month before"


def test_every_period_has_a_twin_label(english):
    for label in _KPI_PERIODS:
        assert _twin_label(label), label


def test_an_unlabelled_period_still_gets_an_honest_label(english):
    """A period added later gets a true-but-vague label rather than a KeyError
    or a blank space beside an arrow. ("This Transfer So Far" used to stand in
    here; it has had a label of its own since the transfer periods landed.)"""
    assert _twin_label("Since Training") == "vs the period before"


# ── _comparison_note: a missing arrow always says why ────────────────────────

def test_all_time_says_it_has_nothing_to_compare_against(english):
    note = _comparison_note("All Time", None, None, 25, 0)
    assert "no earlier period" in note


def test_a_twin_with_too_few_reporting_days_says_so_and_names_the_window(english):
    """The live 2026-09-03 case: This Month So Far's twin is 1-3 August and
    DAILY_LOG starts on the 9th, so the twin holds zero reporting days. The
    reader must not be left to infer the mission stood still."""
    note = _comparison_note("This Month So Far", date(2026, 8, 1), date(2026, 8, 3), 3, 0)
    assert "No comparison yet" in note
    assert "0" in note and str(MIN_COMPARABLE_DAYS) in note


def test_a_thin_current_period_says_so_rather_than_blaming_the_twin(english):
    """Two days into a month, the twin can be perfectly healthy and the
    comparison still impossible. The note must name the side that is actually
    short."""
    note = _comparison_note("This Month So Far", date(2026, 8, 1), date(2026, 8, 2), 2, 30)
    assert "this period holds" in note


def test_a_usable_comparison_states_the_window_and_both_bases(english):
    note = _comparison_note("Last Week", date(2026, 8, 17), date(2026, 8, 23), 7, 7)
    assert "Arrows compare against" in note
    assert "17" in note and "23" in note


# ── The arrow itself ─────────────────────────────────────────────────────────

def test_a_card_gets_an_arrow_once_both_sides_have_enough_days():
    """The shape the engine hands render_kpi_row: period_delta's dict, not a
    bare percentage — it has already chosen percent vs absolute and already
    passed the move through the neutral band."""
    change = period_delta(120, 100, current_basis=7, prior_basis=7)
    assert change is not None
    assert change["direction"] == UP
    assert change["show"] in ("percent", "absolute")


def test_no_arrow_below_the_minimum_basis():
    """Four reporting days is not a week. The card shows its number and no
    arrow, and _comparison_note explains the gap."""
    assert period_delta(120, 100, current_basis=4, prior_basis=7) is None
    assert period_delta(120, 100, current_basis=7, prior_basis=4) is None


def test_an_empty_twin_produces_no_arrow_at_all():
    """A twin window that predates DAILY_LOG sums to zero on every metric. Zero
    prior with a positive current is a RISE FROM NOTHING to period_delta — true
    for a real zero, a lie for a window the mission simply has no records for.
    The engine's has_prior guard is what keeps the two apart, so it is asserted
    here at the level the engine uses it."""
    empty = _slice_to_window(_log("2026-08-23"), date(2026, 8, 1), date(2026, 8, 3))
    assert empty.empty  # -> has_prior is False -> no "change" key on any card


# ══════════════════════════════════════════════════════════════════════════════
# Step 6 (A1b) — an arbitrary range, and the floor its twin may not cross
# ══════════════════════════════════════════════════════════════════════════════

_FLOOR = date(2026, 8, 9)   # DAILY_LOG's first row, live


def test_a_custom_range_twins_the_equal_length_window_before_it():
    """Seven days chosen by hand get the seven days immediately before them —
    same rule as every named period, applied to a window nobody named."""
    assert _kpi_prior_bounds(
        "Custom", date(2026, 8, 24), date(2026, 8, 30), date(2026, 9, 3),
        floor=_FLOOR) == (date(2026, 8, 17), date(2026, 8, 23))


def test_a_one_day_custom_range_twins_the_day_before():
    assert _kpi_prior_bounds(
        "Custom", date(2026, 8, 20), date(2026, 8, 20), date(2026, 9, 3),
        floor=_FLOOR) == (date(2026, 8, 19), date(2026, 8, 19))


def test_a_custom_twin_reaching_past_the_records_is_no_twin_at_all():
    """The live shape of this: DAILY_LOG begins 2026-08-09, so a range starting
    on the 12th has only three days of history behind it and cannot have a
    seven-day twin. A CLAMPED twin would be worse than none — three days
    measured against seven looks like a real comparison and is not."""
    assert _kpi_prior_bounds(
        "Custom", date(2026, 8, 12), date(2026, 8, 18), date(2026, 9, 3),
        floor=_FLOOR) is None


def test_a_custom_twin_landing_exactly_on_the_floor_is_kept():
    """The boundary is inclusive: a twin starting on the first day of records
    is entirely inside them."""
    assert _kpi_prior_bounds(
        "Custom", date(2026, 8, 16), date(2026, 8, 22), date(2026, 9, 3),
        floor=_FLOOR) == (date(2026, 8, 9), date(2026, 8, 15))


def test_a_custom_twin_needs_no_floor_to_be_computed():
    """`floor` is optional — without one, the arithmetic still holds and only
    the records check is skipped."""
    assert _kpi_prior_bounds(
        "Custom", date(2026, 8, 24), date(2026, 8, 30), date(2026, 9, 3)
    ) == (date(2026, 8, 17), date(2026, 8, 23))


def test_custom_is_offered_in_the_picker():
    assert "Custom" in _KPI_PERIODS


def test_custom_falls_through_to_an_honest_twin_label(english):
    """It has no name of its own to compare against, so it says the true, vague
    thing rather than claiming a week or a month."""
    from app.breakdowns_engine import _twin_label
    assert _twin_label("Custom") == "vs the period before"


# ══════════════════════════════════════════════════════════════════════════════
# Step 5 (A1) — the two transfer periods, unblocked 2026-09-03
# ══════════════════════════════════════════════════════════════════════════════
# The windows come from TRANSFER_SCHEDULE and are handed in by the caller
# rather than read here, so both bounds functions stay pure and the drift test
# in test_compliance_rankings can hold them to the same days.

_TRANSFERS = {
    "This Transfer So Far": (date(2026, 7, 27), date(2026, 9, 3)),
    "Last Transfer": (date(2026, 6, 15), date(2026, 7, 26)),
    "_this_transfer_full": date(2026, 9, 6),
}


def test_this_transfer_so_far_runs_from_the_cycle_start_to_today():
    start, end, days = _kpi_period_bounds(
        "This Transfer So Far", date(2026, 9, 3), transfers=_TRANSFERS)
    assert (start, end) == (date(2026, 7, 27), date(2026, 9, 3))


def test_an_in_progress_transfer_is_measured_against_the_WHOLE_cycle():
    """days_in_full_period is the full six weeks, not the 39 days elapsed. It
    is what scales the goal, and scaling by the elapsed part instead would
    quietly lower the bar every morning — the same rule "This Month So Far"
    already follows."""
    _, _, days = _kpi_period_bounds(
        "This Transfer So Far", date(2026, 9, 3), transfers=_TRANSFERS)
    assert days == 42


def test_last_transfer_is_a_completed_cycle_and_its_length_is_its_own():
    start, end, days = _kpi_period_bounds(
        "Last Transfer", date(2026, 9, 3), transfers=_TRANSFERS)
    assert (start, end) == (date(2026, 6, 15), date(2026, 7, 26))
    assert days == 42


def test_a_transfer_period_with_no_window_resolves_to_nothing():
    """Rather than silently falling through to All Time's unbounded window,
    which would render the mission's entire history under a transfer label."""
    assert _kpi_period_bounds("This Transfer So Far", date(2026, 9, 3)) == (None, None, None)


def test_the_transfer_twin_matches_the_elapsed_shape():
    """39 days into the current cycle, the twin is the FIRST 39 days of the
    previous one — not all six weeks of it. Six weeks against 39 days would
    report a collapse on every card on the page's new default view."""
    twin = _kpi_prior_bounds(
        "This Transfer So Far", date(2026, 7, 27), date(2026, 9, 3),
        date(2026, 9, 3), transfers=_TRANSFERS)
    assert twin == (date(2026, 6, 15), date(2026, 7, 23))
    assert (twin[1] - twin[0]).days == (date(2026, 9, 3) - date(2026, 7, 27)).days


def test_the_transfer_twin_never_spills_past_the_previous_cycle():
    """A cycle that has run longer than the one before it clamps at that one's
    end rather than reaching forward into the current transfer's own days."""
    twin = _kpi_prior_bounds(
        "This Transfer So Far", date(2026, 7, 27), date(2026, 9, 6),
        date(2026, 9, 6),
        transfers={**_TRANSFERS,
                   "Last Transfer": (date(2026, 6, 15), date(2026, 7, 10))})
    assert twin[1] <= date(2026, 7, 10)


def test_last_transfer_has_no_twin_when_the_schedule_stops_there():
    """TRANSFER_SCHEDULE reaches back to 2026-06-15 and no further. Subtracting
    six weeks to manufacture a cycle the mission never recorded would be a
    guess wearing the shape of a fact."""
    assert _kpi_prior_bounds(
        "Last Transfer", date(2026, 6, 15), date(2026, 7, 26),
        date(2026, 9, 3), transfers=_TRANSFERS) is None


def test_last_transfer_gets_its_twin_once_an_earlier_cycle_exists():
    twin = _kpi_prior_bounds(
        "Last Transfer", date(2026, 6, 15), date(2026, 7, 26), date(2026, 9, 3),
        transfers={**_TRANSFERS,
                   "_transfer_before_last": (date(2026, 5, 4), date(2026, 6, 14))})
    assert twin == (date(2026, 5, 4), date(2026, 6, 14))


def test_both_transfer_periods_are_offered_by_the_picker():
    assert _KPI_PERIODS[0] == "This Transfer So Far"
    assert _KPI_PERIODS[1] == "Last Transfer"


def test_the_transfer_periods_have_their_own_twin_labels(english):
    assert _twin_label("This Transfer So Far") == "vs same days last transfer"
    assert _twin_label("Last Transfer") == "vs the transfer before"
