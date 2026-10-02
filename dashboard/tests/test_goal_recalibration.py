"""The nightly goals recalibrated from the mission's own pace —
app/analytics/goal_recalibration.py (PLAN-2026-10-02-goals.md, G2)."""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.analytics import goal_recalibration as GR

KEY = "contacts_attempted"
#: Friday 2026-10-02 — the audit's own day. The last complete week ends
#: Sunday 09-27, and six of them start Monday 08-17.
TODAY = date(2026, 10, 2)
CYCLES = [
    {"number": "2026-5", "start": date(2026, 7, 27), "end": date(2026, 9, 6)},
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18)},
]


def _log(nights):
    """nights: (date, area, value)"""
    return pd.DataFrame([{"Date": d.isoformat(), "Area": a, KEY: v}
                         for d, a, v in nights])


def _every_night(area, start, days, value):
    return [(start + timedelta(days=i), area, value) for i in range(days)]


def test_the_window_is_the_last_six_complete_weeks():
    assert GR.last_complete_sunday(TODAY) == date(2026, 9, 27)
    assert GR.measure_window(TODAY) == (date(2026, 8, 17), date(2026, 9, 27))


def test_on_a_sunday_that_sundays_week_is_not_complete():
    assert GR.last_complete_sunday(date(2026, 9, 27)) == date(2026, 9, 20)
    assert GR.last_complete_sunday(date(2026, 9, 28)) == date(2026, 9, 27)


def test_pace_is_per_reported_night_times_seven():
    """Area A files every night at 20; B files every other night at 20. Both
    work at 140 a week on the nights they report, and so does the mission."""
    start = date(2026, 8, 17)
    log = _log(_every_night("A", start, 42, 20)
               + [(start + timedelta(days=i), "B", 20) for i in range(0, 42, 2)])
    window, (p,) = GR.propose(log, {"A", "B"}, {KEY: 150}, [KEY], today=TODAY)
    assert p.pace == pytest.approx(140)
    assert window.nights == 42 + 21
    assert window.possible == 2 * 42
    assert window.filed_share == pytest.approx(63 / 84)


def test_proposed_is_the_pace_stretched_and_rounded_up():
    assert GR.proposed_goal(130.1, 1.10) == 144
    assert GR.proposed_goal(10.0, 1.10) == 11          # not 12 from float noise
    assert GR.proposed_goal(0.3, 1.10) == 1            # never below 1
    assert GR.proposed_goal(0.0, 1.10) == 1
    assert GR.proposed_goal(None, 1.10) is None


def test_areas_off_the_roster_do_not_count():
    start = date(2026, 8, 17)
    log = _log(_every_night("A", start, 42, 10) + _every_night("Retired", start, 42, 99))
    _, (p,) = GR.propose(log, {"A"}, {KEY: 150}, [KEY], today=TODAY)
    assert p.pace == pytest.approx(70)


def test_nights_outside_the_window_do_not_count():
    log = _log(_every_night("A", date(2026, 8, 17), 42, 10)
               + _every_night("A", date(2026, 9, 28), 4, 500))   # week in progress
    _, (p,) = GR.propose(log, {"A"}, {KEY: 150}, [KEY], today=TODAY)
    assert p.pace == pytest.approx(70)


def test_the_trend_is_this_transfer_against_the_last():
    """2026-5 at 10 a night, 2026-6's complete weeks at 13 — up 30%."""
    log = _log(_every_night("A", date(2026, 8, 10), 28, 10)    # in 2026-5
               + _every_night("A", date(2026, 9, 7), 21, 13))  # 2026-6 to 09-27
    _, (p,) = GR.propose(log, {"A"}, {KEY: 150}, [KEY], today=TODAY,
                         cycles=CYCLES)
    assert p.last_cycle == pytest.approx(70)
    assert p.this_cycle == pytest.approx(91)
    assert p.trend == GR.UP


@pytest.mark.parametrize("this, last, want", [
    (100, 100, GR.FLAT), (109, 100, GR.FLAT), (111, 100, GR.UP),
    (89, 100, GR.DOWN), (100, None, ""), (None, 100, ""), (5, 0, ""),
])
def test_trend_bands(this, last, want):
    p = GR.Proposal(key=KEY, current=1, pace=1, proposed=1,
                    this_cycle=this, last_cycle=last)
    assert p.trend == want


def test_a_metric_nobody_reported_has_no_proposal():
    _, (p,) = GR.propose(_log([]), {"A"}, {KEY: 150}, [KEY], today=TODAY)
    assert p.pace is None and p.proposed is None and p.change is None


def test_change_and_attainment_read_against_the_current_goal():
    p = GR.Proposal(key=KEY, current=150, pace=130.1, proposed=144)
    assert p.change == -6
    assert p.attainment == pytest.approx(130.1 / 150 * 100)


# ── The AGENT_CONFIG write plan (goals_queries.plan_config_updates) ──────────

from app.db.goals_queries import plan_config_updates

GRID = [["Key", "Value"],
        ["TRANSFER_START_DATE", "2026-09-07"],
        ["GOAL_contacts_attempted", "150"],
        ["GOAL_roleplays", "7"]]


def test_only_the_value_cells_of_existing_keys_are_written():
    updates, err = plan_config_updates(
        GRID, {"GOAL_contacts_attempted": 144, "GOAL_roleplays": 7})
    assert err is None
    assert updates == [("B3", 144), ("B4", 7)]


@pytest.mark.parametrize("values", [
    {"GOAL_missing": 5},                       # not in the tab
    {"GOAL_roleplays": 0},                     # below 1
    {"GOAL_roleplays": 2.5},                   # not whole
    {"GOAL_roleplays": True},                  # a bool is not a goal
    {},
])
def test_a_bad_value_writes_nothing(values):
    updates, err = plan_config_updates(GRID, values)
    assert updates == [] and err


def test_a_duplicated_key_refuses_the_whole_write():
    grid = GRID + [["GOAL_roleplays", "9"]]
    updates, err = plan_config_updates(
        grid, {"GOAL_contacts_attempted": 144, "GOAL_roleplays": 7})
    assert updates == [] and "2 times" in err


def test_a_tab_without_its_header_writes_nothing():
    assert plan_config_updates([["a", "b"]], {"GOAL_roleplays": 7})[0] == []
    assert plan_config_updates([], {"GOAL_roleplays": 7})[0] == []
