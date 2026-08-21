"""Change over time — app/analytics/period_delta.py.

The module exists because the obvious version of this feature was wrong: on
2026-08-21 a plain val_14d - val_7d comparison put +134% on contact attempts and
+236% on church invites, purely because DAILY_LOG began eleven days earlier and
the "prior seven days" held five. Several tests below are that exact shape.
"""

from datetime import date

import pandas as pd
import pytest

from app.analytics.period_delta import (
    ABSOLUTE, DOWN, FLAT, MIN_COMPARABLE_DAYS, PERCENT, UP, WINDOW_DAYS,
    days_in_window, period_delta, reporting_dates, window_areas, window_pair,
    window_totals,
)


def _log(rows):
    """rows = [(date, area, contacts_attempted)]"""
    return pd.DataFrame(
        [{"Date": d, "Area": a, "contacts_attempted": v} for d, a, v in rows]
    )


def _days(start_day, n_days, n_areas, per_area=10):
    return [
        (date(2026, 8, start_day + d), f"Area {i}", per_area)
        for d in range(n_days)
        for i in range(n_areas)
    ]


# ── reporting_dates ───────────────────────────────────────────────────────────

def test_a_date_below_half_the_areas_is_not_a_reporting_day():
    """The live case: 2026-08-09 held one row from one area out of 43. Counted
    naively it is a seventh of a week and inflates everything measured against
    it."""
    rows = _days(10, 4, 34) + [(date(2026, 8, 9), "Area 0", 10)]
    dates = reporting_dates(_log(rows), active_areas=43)
    assert date(2026, 8, 9) not in dates
    assert len(dates) == 4


def test_exactly_half_the_areas_counts():
    dates = reporting_dates(_log(_days(10, 1, 22)), active_areas=43)
    assert dates == [date(2026, 8, 10)]


def test_unknown_area_count_falls_back_to_any_row():
    """Better a degraded reading than a blank page: with no active-area count
    there is no share to take."""
    dates = reporting_dates(_log([(date(2026, 8, 9), "Area 0", 1)]),
                            active_areas=0)
    assert dates == [date(2026, 8, 9)]


def test_empty_and_malformed_frames_are_empty():
    assert reporting_dates(pd.DataFrame(), 43) == []
    assert reporting_dates(pd.DataFrame({"Date": [date(2026, 8, 9)]}), 43) == []


# ── window_pair ───────────────────────────────────────────────────────────────

def test_windows_are_seven_days_each_and_do_not_overlap():
    """CCSM_Agent3.gs cuts at `date >= today - 7`, which spans EIGHT dates while
    the prior window implied by val_14d - val_7d spans seven. That asymmetry is
    the ~14% inflation this function exists to avoid."""
    cur_s, cur_e, prev_s, prev_e = window_pair(date(2026, 8, 20))
    assert (cur_e - cur_s).days + 1 == WINDOW_DAYS
    assert (prev_e - prev_s).days + 1 == WINDOW_DAYS
    assert cur_s == date(2026, 8, 14) and cur_e == date(2026, 8, 20)
    assert prev_s == date(2026, 8, 7) and prev_e == date(2026, 8, 13)
    assert prev_e < cur_s


# ── window_totals / window_areas / days_in_window ─────────────────────────────

def test_window_totals_sums_only_the_window():
    df = _log(_days(10, 5, 2, per_area=10))
    totals = window_totals(df, date(2026, 8, 11), date(2026, 8, 12))
    assert totals["contacts_attempted"] == 40   # 2 days x 2 areas x 10


def test_window_totals_coerces_non_numeric_columns_to_zero():
    """DAILY_LOG stores effort as 'Todo' and exchanges as 'TRUE'."""
    df = pd.DataFrame([
        {"Date": date(2026, 8, 10), "Area": "A", "effort": "Todo",
         "contacts_attempted": 5},
    ])
    totals = window_totals(df, date(2026, 8, 10), date(2026, 8, 10))
    assert totals["effort"] == 0
    assert totals["contacts_attempted"] == 5


def test_window_totals_rejects_a_backwards_range():
    df = _log(_days(10, 3, 2))
    assert window_totals(df, date(2026, 8, 12), date(2026, 8, 10)) == {}


def test_window_areas_counts_distinct_areas():
    df = _log(_days(10, 3, 4))
    assert window_areas(df, date(2026, 8, 10), date(2026, 8, 12)) == 4
    assert window_areas(df, date(2026, 8, 1), date(2026, 8, 5)) == 0


def test_days_in_window_counts_only_reporting_dates():
    dates = [date(2026, 8, d) for d in (10, 11, 13, 20)]
    assert days_in_window(dates, date(2026, 8, 10), date(2026, 8, 16)) == 3
    assert days_in_window([], date(2026, 8, 10), date(2026, 8, 16)) == 0


# ── period_delta: the gate ────────────────────────────────────────────────────

def test_a_short_prior_window_is_not_compared():
    """The whole reason this module exists. Seven days against four is not a
    134% rise, it is a system that started recently."""
    assert period_delta(4104, 1757, current_basis=7, prior_basis=4) is None


def test_the_gate_opens_at_five_days():
    out = period_delta(700, 500, current_basis=7,
                       prior_basis=MIN_COMPARABLE_DAYS)
    assert out is not None


def test_a_short_current_window_is_not_compared_either():
    assert period_delta(300, 700, current_basis=3, prior_basis=7) is None


def test_non_numeric_input_is_not_compared():
    assert period_delta(None, 500, current_basis=7, prior_basis=7) is None
    assert period_delta(500, "x", current_basis=7, prior_basis=7) is None


# ── period_delta: scaling the prior side ──────────────────────────────────────

def test_the_prior_side_is_scaled_onto_the_current_basis():
    """5 days of 100/day against 7 days of 100/day is flat, not +40%."""
    out = period_delta(700, 500, current_basis=7, prior_basis=5)
    assert out["prior_adjusted"] == pytest.approx(700)
    assert out["direction"] == FLAT
    assert out["pct"] == pytest.approx(0)


def test_equal_bases_leave_the_arithmetic_untouched():
    out = period_delta(660, 600, current_basis=7, prior_basis=7)
    assert out["prior_adjusted"] == pytest.approx(600)
    assert out["change"] == pytest.approx(60)
    assert out["pct"] == pytest.approx(10)


def test_the_change_stays_in_the_tiles_own_units():
    """Not a per-day rate: the number above the arrow is a mission total, and
    so is the change printed under it."""
    out = period_delta(700, 250, current_basis=7, prior_basis=5)
    assert out["change"] == pytest.approx(700 - 350)


def test_a_weekly_comparison_scales_by_reporting_areas():
    """31 areas' week against 1 area's week — per area, or not at all."""
    out = period_delta(204, 6, current_basis=31, prior_basis=31)
    assert out["pct"] == pytest.approx(3300)
    assert period_delta(204, 6, current_basis=31, prior_basis=1,
                        min_basis=22) is None


# ── period_delta: direction and the neutral band ──────────────────────────────

@pytest.mark.parametrize("current,expected", [
    (1000, UP),      # +11%
    (920, FLAT),     # +2%, inside the band
    (880, FLAT),     # -2%
    (800, DOWN),     # -11%
])
def test_the_neutral_band_absorbs_noise(current, expected):
    out = period_delta(current, 900, current_basis=7, prior_basis=7)
    assert out["direction"] == expected


def test_a_change_that_rounds_to_nothing_is_flat():
    """An absolute change of 0.4 is not a rise, whatever its percentage says."""
    out = period_delta(10.4, 10, current_basis=7, prior_basis=7)
    assert out["show"] == ABSOLUTE
    assert out["direction"] == FLAT


# ── period_delta: percent vs absolute ─────────────────────────────────────────

def test_small_counts_report_an_absolute_change():
    """Baptisms 3 -> 5 is '+2', not '+67%'. Same fact, and only one of the two
    admits how small the sample is."""
    out = period_delta(5, 3, current_basis=7, prior_basis=7)
    assert out["show"] == ABSOLUTE
    assert out["change"] == pytest.approx(2)


def test_large_counts_report_a_percentage():
    out = period_delta(4104, 3600, current_basis=7, prior_basis=7)
    assert out["show"] == PERCENT


def test_the_small_count_test_uses_the_scaled_prior():
    """A prior of 20 over 5 days scales to 28 over 7 — above the threshold, so
    the percentage is the honest reading."""
    out = period_delta(30, 20, current_basis=7, prior_basis=5)
    assert out["prior_adjusted"] == pytest.approx(28)
    assert out["show"] == PERCENT


# ── period_delta: nothing to divide by ────────────────────────────────────────

def test_a_rise_from_zero_is_reported_as_an_absolute():
    """0 baptisms last week, 5 this week is the best news the page can carry;
    a division by zero should not swallow it."""
    out = period_delta(5, 0, current_basis=7, prior_basis=7)
    assert out["pct"] is None
    assert out["show"] == ABSOLUTE
    assert out["direction"] == UP
    assert out["change"] == pytest.approx(5)


def test_zero_against_zero_says_nothing():
    assert period_delta(0, 0, current_basis=7, prior_basis=7) is None
