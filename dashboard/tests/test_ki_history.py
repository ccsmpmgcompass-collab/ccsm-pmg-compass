"""The series behind the Key Indicator drill-down — app/analytics/ki_history.py.

PLAN-2026-09-18-data-pages.md §3, step B1. Synthetic weekly frames throughout,
with a fixed `today`: against the live sheet these would pass or fail by
calendar accident.

The cycle under test is 2026-6, Mon 7 Sep → Sun 18 Oct 2026 (six weeks), and
its twin 2026-5, Mon 27 Jul → Sun 6 Sep. Today is Fri 18 Sep, week 2 of 6.
"""

from datetime import date

import pandas as pd
import pytest

from app.analytics.ki_history import (
    AreaRow, CyclePoint, WeekPoint,
    area_rows, cycle_position, cycle_series, cycle_weeks,
    leadership_total, leadership_weekly_mark, meta_key, sundays_between,
    twin_weekly, weekly_series,
)
from app.analytics.period_delta import ABSOLUTE, UP

TODAY = date(2026, 9, 18)
CUR = {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18), "weeks": 6}
PREV = {"number": "2026-5", "start": date(2026, 7, 27), "end": date(2026, 9, 6), "weeks": 6}
OLD = {"number": "2026-4", "start": date(2026, 6, 15), "end": date(2026, 7, 26), "weeks": 6}

METRIC = "ki_new_people_real"


def _frame(rows) -> pd.DataFrame:
    """rows: (week_end, area, real, meta) → the frame get_weekly_form_data returns."""
    return pd.DataFrame([
        {"week_end_date": w, "area": a, "zone": "Angol",
         "ki_new_people_real": real, "ki_new_people_meta": meta}
        for w, a, real, meta in rows
    ])


@pytest.fixture
def weekly() -> pd.DataFrame:
    return _frame([
        # 2026-5, partial twin: data from 08-09 only (no row for 08-02).
        ("2026-08-09", "A", 2, 4),
        ("2026-08-09", "B", 1, 3),
        ("2026-08-16", "A", 3, 5),
        ("2026-08-16", "B", 2, 2),
        ("2026-08-23", "A", 4, 5),
        ("2026-08-30", "A", 1, 6),
        ("2026-08-30", "B", 3, 3),
        # The 09-06 row carries the metas FOR the cycle's first week (09-13).
        ("2026-09-06", "A", 5, 7),
        ("2026-09-06", "B", 2, 4),
        # 2026-6, week 1 (ends 09-13): results + metas for week 2.
        ("2026-09-13", "A", 6, 8),
        ("2026-09-13", "B", 4, 0),      # B set no meta for week 2
        # An area outside the scope, to be filtered out by name.
        ("2026-09-13", "Z", 99, 99),
    ])


# ── Calendar ─────────────────────────────────────────────────────────────────

def test_cycle_weeks_are_six_mon_sun_weeks():
    weeks = cycle_weeks(CUR)
    assert len(weeks) == 6
    assert weeks[0] == (date(2026, 9, 7), date(2026, 9, 13))
    assert weeks[-1] == (date(2026, 10, 12), date(2026, 10, 18))


def test_cycle_weeks_snap_a_midweek_start_to_its_monday():
    weeks = cycle_weeks({"start": date(2026, 9, 9), "end": date(2026, 9, 27)})
    assert weeks[0][0] == date(2026, 9, 7)
    assert len(weeks) == 3


def test_cycle_position_today_is_week_two_of_six():
    assert cycle_position(CUR, TODAY) == (2, 6)
    assert cycle_position(CUR, date(2026, 9, 1)) == (0, 6)
    assert cycle_position(CUR, date(2026, 12, 1)) == (6, 6)


def test_sundays_between():
    assert sundays_between(date(2026, 9, 7), date(2026, 9, 27)) == [
        date(2026, 9, 13), date(2026, 9, 20), date(2026, 9, 27)]


def test_meta_key_by_name():
    assert meta_key("ki_new_people_real") == "ki_new_people_meta"
    assert meta_key("contacts_made") is None


# ── weekly_series ────────────────────────────────────────────────────────────

def test_week_one_actual_is_the_scope_sum_and_the_meta_comes_from_the_week_before(weekly):
    pts = weekly_series({"A", "B"}, METRIC, CUR, weekly=weekly, today=TODAY)
    assert len(pts) == 6
    w1 = pts[0]
    assert isinstance(w1, WeekPoint)
    assert w1.actual == 10            # 6 + 4, Z excluded
    assert w1.meta == 11              # written on the 09-06 rows: 7 + 4
    assert w1.meta_set_by == 2
    assert w1.reporting == 2
    assert not w1.is_current and not w1.is_future


def test_week_two_is_current_its_meta_comes_from_week_one_rows(weekly):
    pts = weekly_series({"A", "B"}, METRIC, CUR, weekly=weekly, today=TODAY)
    w2 = pts[1]
    assert w2.is_current
    assert w2.actual is None          # no 09-20 row yet: not a zero
    assert w2.meta == 8               # A's 8; B's blank meta adds nothing
    assert w2.meta_set_by == 1


def test_future_weeks_have_no_actual_and_no_meta(weekly):
    pts = weekly_series({"A", "B"}, METRIC, CUR, weekly=weekly, today=TODAY)
    for p in pts[2:]:
        assert p.is_future
        assert p.actual is None
        assert p.meta is None
        assert p.meta_set_by == 0


def test_a_meta_nobody_set_is_none_not_zero():
    frame = _frame([("2026-09-06", "A", 5, 0), ("2026-09-13", "A", 6, 0)])
    pts = weekly_series({"A"}, METRIC, CUR, weekly=frame, today=TODAY)
    assert pts[0].meta is None
    assert pts[0].actual == 6


def test_scope_filters_by_area_name(weekly):
    pts = weekly_series({"A"}, METRIC, CUR, weekly=weekly, today=TODAY)
    assert pts[0].actual == 6
    assert pts[0].reporting == 1


def test_empty_scope_yields_empty_points(weekly):
    pts = weekly_series(set(), METRIC, CUR, weekly=weekly, today=TODAY)
    assert all(p.actual is None and p.meta is None for p in pts)


# ── twin_weekly ──────────────────────────────────────────────────────────────

def test_twin_is_the_previous_cycle_at_the_same_week_index(weekly):
    twin = twin_weekly({"A", "B"}, METRIC, CUR, PREV, weekly=weekly)
    assert len(twin) == 6
    # 2026-5 weeks end 08-02, 08-09, 08-16, 08-23, 08-30, 09-06.
    assert twin[0] is None            # 08-02: no row — the partial twin
    assert twin[1] == 3               # 08-09: 2 + 1
    assert twin[2] == 5               # 08-16: 3 + 2
    assert twin[3] == 4               # 08-23: A only
    assert twin[4] == 4               # 08-30: 1 + 3
    assert twin[5] == 7               # 09-06: 5 + 2


def test_twin_is_truncated_past_the_previous_cycles_weeks(weekly):
    short = {"number": "x", "start": date(2026, 8, 10), "end": date(2026, 8, 23)}
    twin = twin_weekly({"A", "B"}, METRIC, CUR, short, weekly=weekly)
    assert twin[:2] == [5, 4]
    assert twin[2:] == [None] * 4


def test_no_previous_cycle_means_all_none(weekly):
    assert twin_weekly({"A"}, METRIC, CUR, None, weekly=weekly) == [None] * 6


# ── cycle_series ─────────────────────────────────────────────────────────────

def test_cycle_series_lists_only_cycles_with_data(weekly):
    goals = {date(2026, 9, 7): {METRIC: 60}}
    pts = cycle_series({"A", "B"}, METRIC, cycles=[OLD, PREV, CUR],
                       weekly=weekly, goals_by_cycle=goals, today=TODAY)
    assert [p.number for p in pts] == ["2026-5", "2026-6"]
    cur = pts[-1]
    assert isinstance(cur, CyclePoint)
    assert cur.is_current
    assert cur.actual == 10
    assert cur.meta_so_far == 19      # week 1's 11 + the current week's 8
    assert cur.leadership == 60
    assert cur.weeks_covered == 1 and cur.weeks_total == 6


def test_cycle_with_no_goal_saved_has_no_leadership(weekly):
    pts = cycle_series({"A", "B"}, METRIC, cycles=[PREV, CUR], weekly=weekly,
                       goals_by_cycle={}, today=TODAY)
    assert all(p.leadership is None for p in pts)
    prev = pts[0]
    assert prev.actual == 2 + 1 + 3 + 2 + 4 + 1 + 3 + 5 + 2
    assert prev.weeks_covered == 5    # 08-02 has no row


# ── area_rows ────────────────────────────────────────────────────────────────

def test_area_rows_rank_by_pct_of_meta_and_keep_the_silent_area(weekly):
    week1 = (date(2026, 9, 7), date(2026, 9, 13))
    rows = area_rows({"A", "B", "C"}, METRIC, week1, weekly=weekly, today=TODAY)
    assert [r.area for r in rows] == ["B", "A", "C"]
    b, a, c = rows
    assert isinstance(a, AreaRow)
    assert a.actual == 6 and a.meta == 7 and round(a.pct) == 86
    assert b.actual == 4 and b.meta == 4 and b.pct == 100
    assert c.actual == 0 and c.meta is None and c.pct is None
    assert not c.reported and a.reported


def test_area_change_uses_a_basis_of_one_each_side(weekly):
    week1 = (date(2026, 9, 7), date(2026, 9, 13))
    twin = (date(2026, 8, 3), date(2026, 8, 9))
    rows = {r.area: r for r in area_rows({"A", "B", "C"}, METRIC, week1, twin,
                                         weekly=weekly, today=TODAY)}
    # A: 6 now vs 2 then — small counts print the absolute rise.
    assert rows["A"].change is not None
    assert rows["A"].change["change"] == 4
    assert rows["A"].change["show"] == ABSOLUTE
    assert rows["A"].change["direction"] == UP
    # C has no row in the twin either: nothing to compare against.
    assert rows["C"].change is None


def test_nights_missed_counts_only_up_to_yesterday(weekly):
    daily = pd.DataFrame([
        {"Date": "2026-09-14", "Area": "A"},
        {"Date": "2026-09-15", "Area": "A"},
        {"Date": "2026-09-17", "Area": "A"},
    ])
    window = (date(2026, 9, 14), date(2026, 9, 20))
    rows = {r.area: r for r in area_rows({"A", "B"}, METRIC, window,
                                         weekly=weekly, daily=daily, today=TODAY)}
    # Mon 14 – Thu 17 are due (today is Fri 18): A missed the 16th only.
    assert rows["A"].nights_missed == 1
    assert rows["B"].nights_missed == 4


def test_nights_missed_is_none_without_a_daily_frame(weekly):
    rows = area_rows({"A"}, METRIC, (date(2026, 9, 7), date(2026, 9, 13)),
                     weekly=weekly, today=TODAY)
    assert rows[0].nights_missed is None


# ── leadership marks ─────────────────────────────────────────────────────────

def test_leadership_weekly_mark_is_the_total_over_the_cycles_real_weeks():
    assert leadership_weekly_mark({"A"}, CUR, METRIC, totals={METRIC: 60}) == 10
    assert leadership_total({"A"}, CUR, METRIC, totals={METRIC: 60}) == 60


def test_no_leadership_goal_is_none_not_zero():
    assert leadership_weekly_mark({"A"}, CUR, METRIC, totals={}) is None
    assert leadership_weekly_mark({"A"}, CUR, METRIC, totals={METRIC: 0}) is None
