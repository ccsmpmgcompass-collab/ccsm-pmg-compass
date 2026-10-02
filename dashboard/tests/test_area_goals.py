"""Each sector's own nightly goal — app/analytics/area_goals.py
(PLAN-2026-10-02-goals.md, G6: decisions G-D7..G-D10)."""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.analytics import area_goals as AG

KEY = "contacts_attempted"
#: Monday 2026-10-05: the window is the six weeks 08-24 .. 10-04.
WEEK = date(2026, 10, 5)
START = date(2026, 8, 24)


def _log(rows):
    return pd.DataFrame([{"Date": d.isoformat(), "Area": a, KEY: v}
                         for d, a, v in rows])


def _nights(area, n, value, start=START, every=1):
    return [(start + timedelta(days=i), area, value) for i in range(0, n * every, every)]


def test_the_window_is_the_six_weeks_before_the_monday():
    assert AG.window(WEEK) == (START, date(2026, 10, 4))
    assert AG.week_monday(date(2026, 10, 8)) == WEEK


def test_a_sectors_goal_is_its_own_pace_plus_ten_percent():
    """A files 30 nights at 20 a night: 140 a week on the nights it reports,
    so its goal is ceil(154) — not the mission's number."""
    goals = AG.compute(_log(_nights("A", 30, 20)), {"A": "Z"}, [KEY], week_start=WEEK)
    g = goals["A"][KEY]
    assert (g.goal, g.source) == (154, AG.OWN)
    assert g.pace == pytest.approx(140)


def test_two_sectors_get_two_goals():
    log = _log(_nights("A", 30, 20) + _nights("B", 30, 5))
    goals = AG.compute(log, {"A": "Z", "B": "Z"}, [KEY], week_start=WEEK)
    assert goals["A"][KEY].goal == 154 and goals["B"][KEY].goal == 39


def test_nights_outside_the_window_do_not_count():
    log = _log(_nights("A", 30, 20)
               + _nights("A", 5, 999, start=date(2026, 10, 5))   # this week
               + _nights("A", 5, 999, start=date(2026, 8, 1)))   # too old
    assert AG.compute(log, {"A": "Z"}, [KEY], week_start=WEEK)["A"][KEY].goal == 154


def test_a_sector_off_the_roster_is_ignored_and_gets_no_goal():
    log = _log(_nights("A", 30, 20) + _nights("Retired", 30, 500))
    goals = AG.compute(log, {"A": "Z"}, [KEY], week_start=WEEK)
    assert set(goals) == {"A"}


def test_the_cap_holds_a_goal_within_ten_percent_of_last_week():
    """Pace says 154, last week was 200: it may only come down to 180."""
    goals = AG.compute(_log(_nights("A", 30, 20)), {"A": "Z"}, [KEY],
                       week_start=WEEK, previous={"A": {KEY: 200}})
    assert goals["A"][KEY].goal == 180


def test_the_cap_works_upward_too():
    goals = AG.compute(_log(_nights("A", 30, 20)), {"A": "Z"}, [KEY],
                       week_start=WEEK, previous={"A": {KEY: 100}})
    assert goals["A"][KEY].goal == 110


def test_a_small_goal_can_still_move_one_step():
    """10% of 2 is 0.2; without the minimum step of 1 it could never change."""
    assert AG.capped(0.3, 2) == 1
    assert AG.capped(9.0, 2) == 3
    assert AG.to_goal(AG.capped(0.3, 2)) == 1


def test_the_first_run_has_no_cap():
    assert AG.capped(50, None) == 50


def test_a_new_sector_borrows_its_zones_median():
    """C filed three nights — too few. Its zone's qualified sectors run 140 and
    70 a week, so C starts from their median, 105."""
    log = _log(_nights("A", 30, 20) + _nights("B", 30, 10) + _nights("C", 3, 50))
    goals = AG.compute(log, {"A": "Z", "B": "Z", "C": "Z"}, [KEY], week_start=WEEK)
    assert goals["C"][KEY].source == AG.ZONE
    assert goals["C"][KEY].goal == AG.to_goal(105 * 1.1)


def test_a_zone_with_no_qualified_sector_falls_to_the_mission():
    log = _log(_nights("A", 30, 20) + _nights("C", 3, 50))
    goals = AG.compute(log, {"A": "Z1", "C": "Z2"}, [KEY], week_start=WEEK)
    assert goals["C"][KEY].source == AG.MISSION


def test_no_nightly_data_at_all_uses_the_configured_goal():
    goals = AG.compute(_log([]), {"A": "Z"}, [KEY], week_start=WEEK,
                       configured={KEY: 150})
    assert (goals["A"][KEY].goal, goals["A"][KEY].source) == (150, AG.CONFIG)


def test_leadership_wins():
    goals = AG.compute(_log(_nights("A", 30, 20)), {"A": "Z"}, [KEY],
                       week_start=WEEK, overrides={"A": {KEY: 175}})
    assert (goals["A"][KEY].goal, goals["A"][KEY].source) == (175, AG.LEADERSHIP)


def test_after_leadership_clears_its_goal_the_cap_does_not_anchor_on_it():
    goals = AG.compute(_log(_nights("A", 30, 20)), {"A": "Z"}, [KEY],
                       week_start=WEEK, previous={"A": {KEY: 400}},
                       previous_overridden={"A": {KEY}})
    assert goals["A"][KEY].goal == 154


def test_a_goal_is_never_below_one():
    goals = AG.compute(_log(_nights("A", 30, 0)), {"A": "Z"}, [KEY], week_start=WEEK)
    assert goals["A"][KEY].goal == 1


def test_the_weighted_goal_is_each_nights_own_sectors_goal():
    """A filed three nights in the week of 09-28 (goal 10) and one in the week
    of 10-05 (goal 14); B one night (goal 30). Average over five nights: 16."""
    goals = {("A", date(2026, 9, 28)): 10, ("A", date(2026, 10, 5)): 14,
             ("B", date(2026, 9, 28)): 30}
    rows = _log([(date(2026, 9, 28), "A", 1), (date(2026, 9, 29), "A", 1),
                 (date(2026, 9, 30), "A", 1), (date(2026, 10, 5), "A", 1),
                 (date(2026, 9, 28), "B", 1),
                 (date(2026, 9, 28), "B", 9)])        # filed twice: one night
    got = AG.weighted_goal(rows, KEY, lambda a, m, k: goals.get((a, m)))
    assert got == pytest.approx((10 * 3 + 14 + 30) / 5)


def test_no_goal_anywhere_is_none():
    rows = _log([(date(2026, 9, 28), "A", 1)])
    assert AG.weighted_goal(rows, KEY, lambda a, m, k: None) is None
    assert AG.weighted_goal(_log([]), KEY, lambda a, m, k: 5) is None


def test_the_goal_book_reads_history_then_current_then_default():
    import pickle
    book = AG.GoalBook(
        by_week={("A", "2026-09-28"): {KEY: 120}},
        newest="2026-09-28",
        current={"A": {KEY: 130}},
        defaults={KEY: 150})
    assert book("A", date(2026, 9, 28), KEY) == 120      # the week's own row
    assert book("A", date(2026, 10, 5), KEY) == 130      # now: GOALS_CONFIG
    assert book("A", date(2026, 9, 7), KEY) == 150       # before history: default
    assert book("B", date(2026, 9, 28), KEY) == 150
    assert pickle.loads(pickle.dumps(book))("A", date(2026, 9, 28), KEY) == 120
