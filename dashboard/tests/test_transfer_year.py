"""A transfer cycle straddling New Year, filed and pro-rated two different ways.

The rules are Zackary's, settled 2026-09-05 (PLAN §7.3), and the two halves are
deliberately not the same answer:

  * FILING — the year holding more of the cycle's days owns it; an exact 21/21
    split goes to the year it ENDS in.
  * PRO-RATING — a cycle's GOAL splits by days, so a year's goal covers the same
    span as its actuals.

The worked example both are checked against is CCSM's own: `2026-8` runs
2026-11-30 to 2027-01-10 — 32 days in 2026, 10 in 2027, filed under 2026,
contributing 32/42 and 10/42 of its goal. The counter-example is the 2027
year-end cycle, 2027-12-13 to 2028-01-23, which files under **2028** despite
being labelled a 2027 cycle: 23 days against 19. That is the case that rules out
"the year it starts in".
"""

from datetime import date

import pytest

from app.analytics import transfer_year as ty
from app.utils.transfer_helpers import transfer_cycles

# CCSM's live schedule as of 2026-09-05, with the end dates transfer_cycles
# derives (the day before the next cycle starts; the last row falls back to
# start + weeks).
C_2026_4 = {"number": "2026-4", "start": date(2026, 6, 15), "end": date(2026, 7, 26), "weeks": 6}
C_2026_5 = {"number": "2026-5", "start": date(2026, 7, 27), "end": date(2026, 9, 6), "weeks": 6}
C_2026_6 = {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18), "weeks": 6}
C_2026_7 = {"number": "2026-7", "start": date(2026, 10, 19), "end": date(2026, 11, 29), "weeks": 6}
C_2026_8 = {"number": "2026-8", "start": date(2026, 11, 30), "end": date(2027, 1, 10), "weeks": 6}
LIVE = [C_2026_4, C_2026_5, C_2026_6, C_2026_7, C_2026_8]

#: 2027-12-13 -> 2028-01-23. The tie-break's real target.
C_2027_YEAR_END = {"number": "2027-9", "start": date(2027, 12, 13), "end": date(2028, 1, 23), "weeks": 6}


# ── cycle_days ───────────────────────────────────────────────────────────────

def test_cycle_days_is_inclusive():
    """Six weeks is 42 days, not 41 — both ends count."""
    assert ty.cycle_days(date(2026, 9, 7), date(2026, 10, 18)) == 42


def test_cycle_days_single_day():
    assert ty.cycle_days(date(2026, 9, 7), date(2026, 9, 7)) == 1


@pytest.mark.parametrize("start,end", [
    (None, date(2026, 1, 1)),
    (date(2026, 1, 1), None),
    (date(2026, 5, 1), date(2026, 4, 1)),   # end before start
])
def test_cycle_days_zero_for_unusable_pairs(start, end):
    """Never negative: a negative denominator would invert every share."""
    assert ty.cycle_days(start, end) == 0


# ── days_in_year / year_share ────────────────────────────────────────────────

def test_the_worked_example_splits_32_10():
    s, e = C_2026_8["start"], C_2026_8["end"]
    assert ty.days_in_year(s, e, 2026) == 32
    assert ty.days_in_year(s, e, 2027) == 10
    assert ty.days_in_year(s, e, 2026) + ty.days_in_year(s, e, 2027) == ty.cycle_days(s, e)


def test_year_share_is_the_plan_s_32_42_and_10_42():
    s, e = C_2026_8["start"], C_2026_8["end"]
    assert ty.year_share(s, e, 2026) == pytest.approx(32 / 42)
    assert ty.year_share(s, e, 2027) == pytest.approx(10 / 42)
    assert ty.year_share(s, e, 2026) + ty.year_share(s, e, 2027) == pytest.approx(1.0)


def test_an_ordinary_cycle_gives_its_year_everything():
    """The common case is the general case with a share of one."""
    s, e = C_2026_6["start"], C_2026_6["end"]
    assert ty.year_share(s, e, 2026) == 1.0
    assert ty.year_share(s, e, 2027) == 0.0
    assert ty.days_in_year(s, e, 2025) == 0


# ── owning_year ──────────────────────────────────────────────────────────────

def test_2026_8_is_filed_under_2026():
    assert ty.owning_year(C_2026_8["start"], C_2026_8["end"]) == 2026


def test_the_2027_year_end_cycle_is_filed_under_2028():
    """23 days against 19 — and the reason "the year it starts in" was rejected."""
    s, e = C_2027_YEAR_END["start"], C_2027_YEAR_END["end"]
    assert ty.days_in_year(s, e, 2027) == 19
    assert ty.days_in_year(s, e, 2028) == 23
    assert ty.owning_year(s, e) == 2028
    assert ty.owning_year(s, e) != s.year


def test_an_exact_21_21_split_goes_to_the_year_it_ends_in():
    """2026-12-11 -> 2027-01-21: 21 days each side, and the later year wins."""
    s, e = date(2026, 12, 11), date(2027, 1, 21)
    assert ty.days_in_year(s, e, 2026) == 21
    assert ty.days_in_year(s, e, 2027) == 21
    assert ty.owning_year(s, e) == 2027


def test_owning_year_is_none_for_an_unusable_pair():
    assert ty.owning_year(None, None) is None
    assert ty.owning_year(date(2026, 5, 1), date(2026, 4, 1)) is None


def test_every_cycle_is_filed_exactly_once():
    """The point of filing: no cycle appears twice and none goes missing."""
    filed = [ty.owning_year(c["start"], c["end"]) for c in LIVE]
    assert all(y is not None for y in filed)
    assert sum(len(ty.cycles_owned_by(LIVE, y))
               for y in ty.years_in_schedule(LIVE)) == len(LIVE)


# ── prorate / year_goal_total ────────────────────────────────────────────────

def test_prorate_splits_a_goal_by_days():
    assert ty.prorate(42, C_2026_8["start"], C_2026_8["end"], 2026) == pytest.approx(32.0)
    assert ty.prorate(42, C_2026_8["start"], C_2026_8["end"], 2027) == pytest.approx(10.0)


def test_prorate_does_not_round():
    """Rounding per cycle drifts a year total; the caller rounds at display."""
    v = ty.prorate(10, C_2026_8["start"], C_2026_8["end"], 2027)
    assert v == pytest.approx(10 * 10 / 42)
    assert v != round(v)


def test_prorate_handles_a_blank_goal():
    assert ty.prorate(None, C_2026_8["start"], C_2026_8["end"], 2026) == 0.0
    assert ty.prorate(0, C_2026_8["start"], C_2026_8["end"], 2026) == 0.0


def test_year_goal_total_sums_whole_cycles_and_the_straddler_s_share():
    """Four whole 2026 cycles at 10 each, plus 32/42 of the straddler's 10."""
    goals = {c["start"]: {"ki_new_people_real": 10} for c in LIVE}
    total = ty.year_goal_total(LIVE, goals, "ki_new_people_real", 2026)
    assert total == pytest.approx(40 + 10 * 32 / 42)


def test_year_goal_total_gives_2027_only_the_january_days():
    """A year owning no cycle still receives its pro-rated share."""
    goals = {c["start"]: {"ki_new_people_real": 10} for c in LIVE}
    assert ty.year_goal_total(LIVE, goals, "ki_new_people_real", 2027) == pytest.approx(10 * 10 / 42)


def test_year_goal_total_ignores_cycles_with_no_saved_goal():
    """The normal case while the tab is being filled in — hence the caption."""
    goals = {C_2026_6["start"]: {"ki_new_people_real": 10}}
    assert ty.year_goal_total(LIVE, goals, "ki_new_people_real", 2026) == pytest.approx(10.0)


def test_year_goal_total_is_zero_for_an_unknown_metric():
    goals = {c["start"]: {"ki_new_people_real": 10} for c in LIVE}
    assert ty.year_goal_total(LIVE, goals, "ki_rc_at_church_real", 2026) == 0.0


# ── pickers and captions ─────────────────────────────────────────────────────

def test_years_in_schedule_offers_only_years_that_own_a_cycle():
    """2027 receives ten days from 2026-8 but owns nothing, so it is not offered."""
    assert ty.years_in_schedule(LIVE) == [2026]
    assert ty.years_in_schedule(LIVE + [C_2027_YEAR_END]) == [2026, 2028]


def test_cycles_owned_by_is_the_caption_s_denominator():
    assert len(ty.cycles_owned_by(LIVE, 2026)) == 5
    assert ty.cycles_owned_by(LIVE, 2027) == []


def test_straddlers_for_year_names_the_split_cycle_from_both_sides():
    assert ty.straddlers_for_year(LIVE, 2026) == [C_2026_8]
    assert ty.straddlers_for_year(LIVE, 2027) == [C_2026_8]
    assert ty.straddlers_for_year(LIVE, 2025) == []


# ── year_bounds ──────────────────────────────────────────────────────────────

def test_a_running_year_is_measured_to_today():
    """Otherwise a year in progress reports its goal against a full year of days."""
    assert ty.year_bounds(2026, date(2026, 9, 5)) == (date(2026, 1, 1), date(2026, 9, 5))


def test_a_finished_or_future_year_gets_its_whole_self():
    assert ty.year_bounds(2025, date(2026, 9, 5)) == (date(2025, 1, 1), date(2025, 12, 31))
    assert ty.year_bounds(2027, date(2026, 9, 5)) == (date(2027, 1, 1), date(2027, 12, 31))


def test_year_bounds_without_a_today_is_the_whole_year():
    assert ty.year_bounds(2026) == (date(2026, 1, 1), date(2026, 12, 31))


# ── weeks_in_cycle ───────────────────────────────────────────────────────────

def test_weeks_in_cycle_reads_the_dates_not_the_weeks_column():
    assert ty.weeks_in_cycle(C_2026_6["start"], C_2026_6["end"]) == 6.0


def test_weeks_in_cycle_keeps_the_fraction_of_a_short_cycle():
    """A cycle cut to 35 days is 5.0; one run to 44 is 6.29, not 6."""
    assert ty.weeks_in_cycle(date(2026, 9, 7), date(2026, 10, 11)) == 5.0
    assert ty.weeks_in_cycle(date(2026, 9, 7), date(2026, 10, 20)) == pytest.approx(44 / 7)


def test_weeks_in_cycle_zero_for_an_unusable_pair():
    """Callers divide by this — see §7.5's transfer_goal / cycle_weeks."""
    assert ty.weeks_in_cycle(None, None) == 0.0


# ── transfer_cycles: the end-date rule, in one place ─────────────────────────

def test_transfer_cycles_ends_the_day_before_the_next_one_starts():
    rows = [{"number": n, "start": s, "weeks": 6, "status": "Actual"}
            for n, s in [("2026-4", date(2026, 6, 15)),
                         ("2026-5", date(2026, 7, 27)),
                         ("2026-6", date(2026, 9, 7))]]
    out = transfer_cycles(rows)
    assert [c["end"] for c in out[:2]] == [date(2026, 7, 26), date(2026, 9, 6)]


def test_transfer_cycles_last_row_falls_back_to_its_own_weeks():
    """Nothing follows the final row to bound it — the Step 1 failure mode."""
    rows = [{"number": "2026-6", "start": date(2026, 9, 7), "weeks": 6, "status": "Scheduled"}]
    assert transfer_cycles(rows)[0]["end"] == date(2026, 10, 18)


def test_transfer_cycles_describes_a_short_cycle_as_it_really_ran():
    """A five-week cycle is five weeks, not the six its Weeks column claims."""
    rows = [{"number": "a", "start": date(2026, 9, 7), "weeks": 6, "status": ""},
            {"number": "b", "start": date(2026, 10, 12), "weeks": 6, "status": ""}]
    out = transfer_cycles(rows)
    assert out[0]["end"] == date(2026, 10, 11)
    assert ty.weeks_in_cycle(out[0]["start"], out[0]["end"]) == 5.0


def test_transfer_cycles_is_empty_for_an_empty_schedule():
    assert transfer_cycles([]) == []
