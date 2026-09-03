"""Where a running period is heading — the landing estimate.

Audit finding C1: every number on the Desgloses page described the past. A
Mission President looking at "This Month So Far" on the third could see what had
happened and what the goal was, and nothing at all about whether the one was
going to reach the other. This is that line.

The estimate is always ``what has already happened`` plus ``what the remaining
days are expected to add``. The days already banked are facts and are never
re-predicted — a forecast that can contradict the count printed above it is
worse than no forecast.
"""

from datetime import date

import pandas as pd
import pytest

from app import i18n
from app.analytics import trends
from app.breakdowns_engine import _completed_weekly_series, _landing_estimate
from app.components.design_system import projection_caption


@pytest.fixture
def english(monkeypatch):
    monkeypatch.setattr(i18n, "get_lang", lambda: "en")


def _fmt(n):
    return str(int(round(n)))


# ── Too little history: straight pace, honestly labelled ─────────────────────

def test_with_no_weekly_history_it_extrapolates_the_current_pace():
    """20 in 3 days of a 30-day month lands at 200."""
    est = _landing_estimate(20, 3, 30, [], [])
    assert est["value"] == pytest.approx(200.0)
    assert est["confidence"] == "low"


def test_three_completed_weeks_is_still_not_enough_to_fit_a_trend():
    """MIN_WEEKS is 4. Three points can be joined by a line, which is exactly
    why they must not be — the line would be the noise, drawn confidently."""
    assert trends.MIN_WEEKS == 4
    est = _landing_estimate(20, 3, 30, [100.0, 110.0, 120.0],
                            ["2026-08-16", "2026-08-23", "2026-08-30"])
    assert est["confidence"] == "low"
    assert est["value"] == pytest.approx(200.0)   # pace, not the fitted trend


# ── Enough history: the remaining days come from the trend ───────────────────

def test_four_completed_weeks_projects_the_remainder_from_the_trend():
    """A mission climbing 100 -> 130 a week is not credited with only the
    average it has managed so far. The already-banked value stays whole and the
    27 remaining days are valued at the projected weekly rate."""
    est = _landing_estimate(
        20, 3, 30, [100.0, 110.0, 120.0, 130.0],
        ["2026-08-09", "2026-08-16", "2026-08-23", "2026-08-30"])
    assert est is not None
    # Perfect straight line -> next week projects to 140, i.e. 20/day.
    assert est["value"] == pytest.approx(20 + (140.0 / 7) * 27, rel=0.02)
    assert est["confidence"] == "high"


def test_a_flat_series_is_projected_but_not_trusted():
    """A slope indistinguishable from zero still yields a number — the mission
    is doing about this much — but it is marked low so the card hedges it."""
    est = _landing_estimate(
        20, 3, 30, [100.0, 103.0, 99.0, 101.0],
        ["2026-08-09", "2026-08-16", "2026-08-23", "2026-08-30"])
    assert est is not None and est["confidence"] == "low"


# ── When there is nothing honest to say ──────────────────────────────────────

def test_a_completed_period_has_nothing_left_to_project():
    """30 days elapsed of 30. It has landed; the card shows the landing."""
    assert _landing_estimate(300, 30, 30, [], []) is None


def test_a_period_with_no_activity_yet_projects_nothing_rather_than_zero():
    """A pace extrapolation of zero is arithmetically correct and useless: it
    prints "on pace for ~0" over a metric the period simply has not reached
    yet, which reads as a prediction of failure."""
    assert _landing_estimate(0, 3, 30, [], []) is None


def test_nonsense_bounds_degrade_instead_of_raising():
    assert _landing_estimate(20, 0, 30, [], []) is None
    assert _landing_estimate(20, 31, 30, [], []) is None
    assert _landing_estimate("—", 3, 30, [], []) is None


# ── The weekly series behind the trend ───────────────────────────────────────

def _hist(rows):
    return pd.DataFrame([{"Date": d, "Area": "Alemania 1", "new_people_found": v}
                         for d, v in rows])


def test_the_series_buckets_into_sunday_ending_weeks():
    """The mission week runs Monday-Sunday, so 2026-08-24 (a Monday) and
    2026-08-30 (the Sunday) are one bucket."""
    values, weeks = _completed_weekly_series(
        _hist([("2026-08-24", 3), ("2026-08-30", 4)]),
        "new_people_found", date(2026, 9, 1))
    assert weeks == ["2026-08-30"]
    assert values == [7.0]


def test_the_series_excludes_the_period_being_projected():
    """Weeks are cut at the period's own start. Including the days already
    counted in `value` would let them into the forecast twice."""
    values, weeks = _completed_weekly_series(
        _hist([("2026-08-24", 1), ("2026-08-30", 3), ("2026-09-02", 9)]),
        "new_people_found", date(2026, 9, 1))
    assert weeks == ["2026-08-30"] and values == [4.0]


def test_an_absent_metric_yields_an_empty_series_not_an_error():
    assert _completed_weekly_series(_hist([("2026-08-30", 4)]),
                                    "baptismal_calendars", date(2026, 9, 1)) == ([], [])


def test_an_empty_frame_yields_an_empty_series():
    assert _completed_weekly_series(pd.DataFrame(), "x", date(2026, 9, 1)) == ([], [])


# ── What the card actually prints ────────────────────────────────────────────

def test_a_high_confidence_estimate_is_stated_plainly(english):
    assert projection_caption({"value": 450, "confidence": "high"}, _fmt) == \
        "on pace for ~450"


def test_a_low_confidence_estimate_says_so_in_words(english):
    """Not just a tilde. A reader who does not know that "~" means "roughly"
    would read the number as a commitment."""
    caption = projection_caption({"value": 450, "confidence": "low"}, _fmt)
    assert "early estimate" in caption


def test_no_projection_means_no_line(english):
    assert projection_caption(None, _fmt) == ""
    assert projection_caption({}, _fmt) == ""
    assert projection_caption({"value": None, "confidence": "high"}, _fmt) == ""


def test_a_week_truncated_by_the_start_of_records_is_not_counted():
    """The live 2026-09-03 bug. DAILY_LOG begins on Sunday 2026-08-09, so the
    week ending that day held one area-day and a total of 7 against a real
    week's ~180. The series read 7 -> 197 -> 127 -> 159, the fit saw a mission
    exploding out of nothing, and roleplays projected to land at 867 where a
    straight pace says ~220.

    Four buckets, three usable weeks — which is below MIN_WEEKS, so the
    estimate correctly falls back to pace rather than fitting a trend to a
    series whose first point is an artefact of when logging started."""
    rows = ([("2026-08-09", 7)]
            + [(d, 28) for d in ("2026-08-10", "2026-08-16")]
            + [(d, 18) for d in ("2026-08-17", "2026-08-23")]
            + [(d, 23) for d in ("2026-08-24", "2026-08-30")])
    values, weeks = _completed_weekly_series(_hist(rows), "new_people_found",
                                             date(2026, 9, 1))
    assert "2026-08-09" not in weeks
    assert weeks == ["2026-08-16", "2026-08-23", "2026-08-30"]
    assert len(values) < trends.MIN_WEEKS


def test_a_week_starting_exactly_on_the_first_record_is_counted():
    """The boundary is inclusive. Records beginning on a Monday means that week
    is whole, and dropping it would throw away real history."""
    rows = [("2026-08-10", 10), ("2026-08-16", 10)]   # Mon 10th - Sun 16th
    values, weeks = _completed_weekly_series(_hist(rows), "new_people_found",
                                             date(2026, 9, 1))
    assert weeks == ["2026-08-16"] and values == [20.0]
