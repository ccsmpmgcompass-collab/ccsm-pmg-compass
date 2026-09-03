"""The year against the baptismal goal — app/analytics/annual_baptisms.py.

This is the only place on the dashboard where the annual goal appears, and the
only chart whose horizon is a year rather than a week. Three properties decide
whether it helps or misleads, and the tests are grouped by them:

  * the line is CUMULATIVE, because "does the year get there" cannot be read
    off monthly bars;
  * it stops where the data stops — the Tableau capture lags, and on 2026-09-03
    the newest month it held was July, so a line drawn to today would flatten
    across August and read as a mission that stopped baptising;
  * the pace it is judged against is a flat twelfth of the goal per month, not
    a curve fitted to two years of noisy seasonality.

Live figures used throughout: 2024 finished 385, 2025 finished 403, and 2026
stood at 283 through July against a goal of 527.
"""

import pytest

from app.analytics import annual_baptisms as ab

# 2026 as captured on 2026-09-03: January through July, nothing after.
_2026 = {"2026-01": 19, "2026-02": 37, "2026-03": 47, "2026-04": 44,
         "2026-05": 43, "2026-06": 46, "2026-07": 47}
_GOAL = 527


# ── Cumulative, and stopping where the data stops ────────────────────────────

def test_the_series_is_a_running_total():
    series = ab.cumulative(_2026, 2026)
    assert series[:7] == [19, 56, 103, 147, 190, 236, 283]


def test_it_stops_at_the_last_captured_month():
    """Not zero and not a flat carry-forward. Both draw a line through months
    with no reading, and the flat one is the more dangerous because it looks
    like data."""
    series = ab.cumulative(_2026, 2026)
    assert series[7:] == [None] * 5
    assert ab.months_covered(series) == 7


def test_a_gap_in_the_middle_ends_the_series_there():
    """The running total after an unknown month is itself unknown. Carrying on
    past it would understate every month that followed and never say so."""
    monthly = {"2026-01": 19, "2026-02": 37, "2026-04": 44}
    series = ab.cumulative(monthly, 2026)
    assert series[:2] == [19, 56]
    assert series[2] is None
    assert series[3] is None      # known month, unknowable total
    assert ab.months_covered(series) == 2


def test_a_year_with_no_capture_at_all_is_all_unknown():
    assert ab.months_covered(ab.cumulative({}, 2026)) == 0


def test_a_complete_year_reaches_its_real_total():
    monthly = {f"2025-{m:02d}": v for m, v in enumerate(
        [24, 33, 30, 37, 35, 44, 41, 32, 20, 32, 44, 31], start=1)}
    series = ab.cumulative(monthly, 2025)
    assert ab.months_covered(series) == 12
    assert series[-1] == 403


# ── The pace the year is judged against ──────────────────────────────────────

def test_the_goal_pace_is_a_flat_twelfth_a_month():
    """Linear on purpose. The mission's own months swing between 17 and 50 with
    no stable pattern across 2024 and 2025, so a seasonal pace would be a curve
    fitted to noise that moved the finish line each time it was recomputed."""
    pace = ab.goal_pace(_GOAL)
    assert pace[0] == pytest.approx(527 / 12)
    assert pace[-1] == pytest.approx(527)
    assert len(pace) == 12


def test_no_goal_means_no_pace_line():
    """The chart still draws the year; it simply has nothing to aim at. That is
    the state before anyone puts GOAL_ANNUAL_baptisms in AGENT_CONFIG."""
    assert ab.goal_pace(None) is None
    assert ab.goal_pace(0) is None


def test_the_pace_gap_is_measured_at_the_last_captured_month():
    """283 through July against a goal of 527: seven twelfths of 527 is 307,4,
    so the mission is about 24 short — not 244, which is what comparing 283
    against the whole 527 in September would suggest."""
    gap = ab.pace_gap(ab.cumulative(_2026, 2026), _GOAL)
    assert gap == pytest.approx(283 - 527 * 7 / 12, abs=0.01)
    assert -30 < gap < -18


def test_no_pace_gap_without_a_goal_or_without_data():
    assert ab.pace_gap(ab.cumulative(_2026, 2026), None) is None
    assert ab.pace_gap(ab.cumulative({}, 2026), _GOAL) is None


# ── Where the year lands ─────────────────────────────────────────────────────

def test_the_landing_estimate_extrapolates_the_months_so_far():
    """283 in seven months is 40,4 a month, so the year lands near 485."""
    est = ab.landing_estimate(ab.cumulative(_2026, 2026), _GOAL)
    assert est["value"] == pytest.approx(283 / 7 * 12, abs=0.01)
    assert est["months"] == 7


def test_the_landing_estimate_says_how_far_it_falls_from_the_goal():
    est = ab.landing_estimate(ab.cumulative(_2026, 2026), _GOAL)
    assert est["gap"] < 0                       # short of 527
    assert est["gap"] == pytest.approx(283 / 7 * 12 - 527, abs=0.01)


def test_the_estimate_reports_how_many_months_it_rests_on():
    """Instead of a confidence tier. There is one series here and at most twelve
    points in it, so a fitted trend would be a line through a handful of noisy
    months dressed up as a forecast — the month count lets the reader weigh it
    themselves."""
    assert ab.landing_estimate(ab.cumulative({"2026-01": 19}, 2026), _GOAL)["months"] == 1


def test_a_finished_year_has_nothing_left_to_project():
    monthly = {f"2025-{m:02d}": 30 for m in range(1, 13)}
    assert ab.landing_estimate(ab.cumulative(monthly, 2025), _GOAL) is None


def test_a_year_with_no_data_projects_nothing():
    assert ab.landing_estimate(ab.cumulative({}, 2026), _GOAL) is None


def test_a_year_that_has_started_at_zero_projects_nothing():
    """A pace extrapolation of zero is correct arithmetic and a useless claim:
    it prints a prediction of failure over a year that has barely begun."""
    assert ab.landing_estimate(ab.cumulative({"2026-01": 0}, 2026), _GOAL) is None
