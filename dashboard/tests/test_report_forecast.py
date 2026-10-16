"""The forward view — PLAN-2026-10-06 Phase 2 (decision 48).

Every forecast is a range with a stated method, and none of them grades.
The live figures these reproduce (AUDIT-2026-10-06 C4): the year lands
443-467 against 527, needs 60 a month against a best month of 50, and runs
+17% on 2025's same nine months.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.reports import forecast as F

NEW = "ki_new_people_real"


# ── Transfer finish ──────────────────────────────────────────────────────────

def _weekly(rows):
    return pd.DataFrame([{"_week": w, "_area": a, NEW: v} for w, a, v in rows])


def test_the_finish_adds_the_weeks_left_at_worst_average_and_best():
    """Four of six weeks done (100 a week); the last six complete weeks ran
    80, 90, 100, 100, 110, 120. Two weeks left: 400 + 2 × (80, 100, 120)."""
    weeks = ["2026-08-30", "2026-09-06", "2026-09-13", "2026-09-20",
             "2026-09-27", "2026-10-04"]
    values = [80, 90, 100, 100, 110, 120]
    df = _weekly([(w, "A1", v) for w, v in zip(weeks, values)])
    (k,) = F.transfer_finish(
        df, ["A1"], [NEW], {NEW: "Nuevas"}, cycle_weeks=weeks[2:],
        full_weeks=6, pace_weeks_list=weeks, goals={NEW: 900.0},
        goals_complete=True)
    assert k.actual == 430
    assert (k.low, k.mid, k.high) == (590, 430 + 2 * 100, 670)
    assert k.weeks_left == 2
    assert k.needed_per_week == pytest.approx(235)
    assert k.factor == pytest.approx(2.35)
    assert k.pct(k.mid) == pytest.approx(630 / 900 * 100)


def test_a_week_nobody_reported_is_a_zero_in_the_pace():
    """A raw total carries the silence it will meet again."""
    df = _weekly([("2026-09-13", "A1", 100)])
    (k,) = F.transfer_finish(
        df, ["A1"], [NEW], {}, cycle_weeks=["2026-09-13"], full_weeks=3,
        pace_weeks_list=["2026-09-06", "2026-09-13"], goals={},
        goals_complete=False)
    assert k.low == 100 and k.high == 100 + 2 * 100
    assert k.needed_per_week is None           # no goal, nothing needed


def test_a_finished_transfer_projects_nothing():
    df = _weekly([("2026-09-13", "A1", 100)])
    (k,) = F.transfer_finish(
        df, ["A1"], [NEW], {}, cycle_weeks=["2026-09-13"], full_weeks=1,
        pace_weeks_list=["2026-09-13"], goals={NEW: 50.0}, goals_complete=True)
    assert k.weeks_left == 0 and k.low == k.high == 100
    assert k.needed_per_week is None


# ── The year ─────────────────────────────────────────────────────────────────

LIVE = {f"2024-{m:02d}": v for m, v in zip(range(1, 13),
        (26, 28, 40, 27, 30, 47, 22, 31, 39, 17, 28, 50))}
LIVE.update({f"2025-{m:02d}": v for m, v in zip(range(1, 13),
             (24, 33, 30, 37, 35, 44, 41, 32, 20, 32, 44, 31))})
LIVE.update({f"2026-{m:02d}": v for m, v in zip(range(1, 10),
             (19, 37, 47, 44, 43, 46, 47, 36, 28))})


def test_the_year_reproduces_the_audit_s_landing():
    y = F.year_landing(LIVE, 2026, goal=527)
    assert (y.total, y.months) == (347, 9)
    assert [round(v) for _, v in y.anchors] == [443, 458, 463, 467]
    assert (round(y.low), round(y.high)) == (443, 467)
    assert y.needed_per_month == pytest.approx(60)
    assert y.best == (50, "dic 2024")


def test_the_same_months_of_the_years_before():
    y = F.year_landing(LIVE, 2026, goal=527)
    assert y.same_months(2025) == 296 and y.same_months(2024) == 290


def test_a_year_with_no_closed_month_has_no_landing():
    assert F.year_landing({"2025-12": 31}, 2026, goal=527) is None


# ── The pipeline ─────────────────────────────────────────────────────────────

def _people(rows):
    """``(date set, confirmation or None)`` per person."""
    return (pd.Series([pd.Timestamp(s) for s, _ in rows]),
            pd.Series([pd.Timestamp(c) if c else pd.NaT for _, c in rows]))


def test_the_fit_is_conversion_within_six_weeks_by_age():
    """At each month-end the open dates are aged and checked six weeks on.
    Here every date converts 20 days after it is set, so only the youngest
    bucket ever converts within the horizon."""
    rows = []
    for i in range(15):
        month = date(2025 + i // 12, i % 12 + 1, 1)
        for day in (1, 10, 20):
            set_d = month.replace(day=day)
            rows.append((set_d.isoformat(),
                         (set_d + timedelta(days=20)).isoformat()))
    set_d, conf = _people(rows)
    fit = F.fit_pipeline(set_d, conf, date(2026, 6, 30))
    assert fit.p[0] > 0.5
    assert all(p == 0 for p in fit.p[2:])
    assert fit.backtests > 0


def test_month_ends_are_the_last_whose_six_weeks_have_happened():
    """6 October less six weeks is 25 August: August's end has not had its
    six weeks yet, so the latest month-end fitted is 31 July."""
    assert [e.date() for e in F._month_ends(date(2026, 10, 6), 3)] == [
        date(2026, 5, 31), date(2026, 6, 30), date(2026, 7, 31)]
    assert F._month_ends(date(2026, 9, 11), 1)[0].date() == date(2026, 7, 31)


def test_the_forecast_counts_only_dates_still_open_today():
    set_d, conf = _people([("2026-09-20", None), ("2026-09-01", "2026-09-30"),
                           ("2024-01-01", None)])     # too old: not open
    fit = F.PipelineFit(p=(0.5, 0.3, 0.1, 0.05, 0.02, 0.01))
    pl = F.pipeline(set_d, conf, date(2026, 10, 6), fit)
    assert pl.open_dates == 1
    assert pl.expected == pytest.approx(0.3)           # 16 days old
    assert pl.low <= pl.expected <= pl.high


def _monthly(first: date, months: int, convert) -> list:
    """A date on the 5th and the 25th of each month; ``convert(set_d)`` gives
    its baptism or None."""
    rows = []
    for i in range(months):
        y, m = first.year + (first.month - 1 + i) // 12, (first.month - 1 + i) % 12 + 1
        for day in (5, 25):
            set_d = date(y, m, day)
            c = convert(set_d)
            rows.append((set_d.isoformat(), c.isoformat() if c else None))
    return rows


def test_a_steady_mission_backtests_without_a_miss():
    """Every date converts on schedule (the 25th's ten days on, the 5th's
    thirty), so whatever the fit saw at each month-end, it forecast right."""
    rows = _monthly(date(2025, 1, 1), 16, lambda s: s + timedelta(
        days=10 if s.day == 25 else 30))
    fit = F.fit_pipeline(*_people(rows), date(2026, 4, 15))
    assert fit.backtests == 12
    assert fit.miss == pytest.approx(0) and fit.over == 0


def test_the_backtest_uses_the_fit_of_its_own_day():
    """Step 2.0: from January 2026 the 5th's dates stop converting. A
    month-end is forecast with the fit that existed then, so 2025's ten
    month-ends are exact and only January and February 2026 overshoot (2
    forecast, 1 baptism). A fit that had already seen 2026 would have missed
    every 2025 month-end low instead."""
    def convert(s):
        if s.day == 25:
            return s + timedelta(days=10)
        return s + timedelta(days=30) if s.year == 2025 else None
    rows = _monthly(date(2025, 1, 1), 16, convert)
    fit = F.fit_pipeline(*_people(rows), date(2026, 4, 15))
    assert fit.backtests == 12
    assert fit.over == 2
    assert fit.miss == pytest.approx(0)            # the median: 10 of 12 exact


def test_the_backtest_clause_says_which_way_it_missed():
    pl = F.Pipeline(open_dates=1250, expected=43.1, low=24, high=63,
                    miss=0.45, backtests=12, over=10)
    assert pl.miss_clause == ("en los últimos 12 cierres de mes, el cálculo "
                              "hecho en su momento falló por un 45% típico y "
                              "se quedó alto en 10")
    even = F.Pipeline(open_dates=1, expected=1, low=0, high=2, miss=0.2,
                      backtests=12, over=6)
    assert even.miss_clause.endswith("falló por un 20% típico")
    low = F.Pipeline(open_dates=1, expected=1, low=0, high=2, miss=0.2,
                     backtests=12, over=1)
    assert low.miss_clause.endswith("y se quedó bajo en 11")
    assert F.Pipeline(open_dates=1, expected=1, low=0, high=2).miss_clause == ""


def test_the_pipeline_is_fitted_on_six_month_ends():
    """Decision 68."""
    assert F.FIT_MONTHS == 6


def test_no_history_is_no_forecast():
    set_d, conf = _people([("2026-09-20", None)])
    assert F.pipeline(set_d, conf, date(2026, 10, 6), F.PipelineFit()) is None


# ── A unit's baptisms (decision 47) ──────────────────────────────────────────

def test_a_unit_s_share_of_527_is_its_share_of_the_last_twelve_months():
    conf = pd.Series(pd.to_datetime(
        ["2026-09-10", "2026-09-20", "2026-05-01", "2026-03-01",
         "2026-02-01", "2025-11-01", "2026-10-02"]))
    mask = pd.Series([True, True, True, False, False, False, True])
    ub = F.unit_baptisms(conf, mask, date(2026, 9, 7), date(2026, 10, 6),
                         today=date(2026, 10, 6), annual_goal=527)
    assert ub.count == 3                 # 10 sep, 20 sep, 2 oct
    assert ub.share == pytest.approx(3 / 6)   # closed months Oct 25-Sep 26
    assert ub.reference == pytest.approx(527 / 2)
    assert ub.year_total == 3 and ub.months == 9
    assert "registros de Tableau" in ub.sentence
