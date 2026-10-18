"""Fechas are a level on Panel, Metas, Desgloses and the drill-down —
PLAN-2026-10-17-fechas-level.md step 6 (L1–L4).

The drill-down's arithmetic (`ki_history`) reads a level's LAST reported week
for a cambio or a window, never its weeks added up, and leadership's goal is
the level to hold, never spread over the cambio's weeks. The flow beside it
keeps its sums. Same calendar as `test_ki_history`: 2026-6 runs 7 Sep → 18
Oct, its twin 2026-5 27 Jul → 6 Sep.
"""

from datetime import date

import pandas as pd
import pytest

from app.analytics.ki_history import (area_rows, cycle_series,
                                      leadership_weekly_mark)

FECHA = "ki_baptismal_date_real"
NEW = "ki_new_people_real"
TODAY = date(2026, 9, 25)
CUR = {"number": "2026-6", "start": date(2026, 9, 7),
       "end": date(2026, 10, 18), "weeks": 6}
PREV = {"number": "2026-5", "start": date(2026, 7, 27),
        "end": date(2026, 9, 6), "weeks": 6}


def _frame(rows) -> pd.DataFrame:
    """(week_end, area, fechas, fechas meta, new people)."""
    return pd.DataFrame([
        {"week_end_date": w, "area": a, FECHA: f, "ki_baptismal_date_meta": m,
         NEW: n}
        for w, a, f, m, n in rows])


@pytest.fixture
def weekly():
    return _frame([
        ("2026-08-30", "A", 2, 3, 5),
        ("2026-09-06", "A", 3, 4, 5),     # carries the metas for 09-13
        ("2026-09-06", "B", 1, 2, 5),
        ("2026-09-13", "A", 4, 5, 6),     # week 1: level 4 + 2 = 6
        ("2026-09-13", "B", 2, 1, 6),
        ("2026-09-20", "A", 5, 5, 7),     # week 2: B silent, level 5
    ])


def test_a_cambio_is_its_last_reported_week(weekly):
    points = cycle_series(["A", "B"], FECHA, cycles=[PREV, CUR],
                          weekly=weekly, today=TODAY,
                          goals_by_cycle={CUR["start"]: {FECHA: 5.5}})
    cur = points[-1]
    assert cur.actual == 5                 # not 6 + 5 = 11
    assert cur.meta_so_far == 6            # the metas written for 09-20
    assert cur.leadership == 5.5           # the level to hold
    prev = points[0]
    assert prev.actual == 4                # 2026-5's last week, 09-06


def test_a_flow_still_adds_its_weeks(weekly):
    cur = cycle_series(["A", "B"], NEW, cycles=[CUR], weekly=weekly,
                       today=TODAY, goals_by_cycle={})[-1]
    assert cur.actual == 19


def test_an_area_reads_the_scopes_last_week(weekly):
    """09-20 is the window's last reported week: B filed nothing that week
    and holds 0 (L4); its meta is the one written for 09-20."""
    rows = {r.area: r for r in area_rows(
        ["A", "B"], FECHA, (CUR["start"], TODAY), weekly=weekly, today=TODAY)}
    assert rows["A"].actual == 5 and rows["A"].meta == 5
    assert rows["B"].actual == 0 and rows["B"].weeks_reported == 1


def test_the_weekly_mark_is_the_level_itself():
    totals = {FECHA: 5.5, NEW: 60.0}
    assert leadership_weekly_mark(["A"], CUR, FECHA, totals=totals) == 5.5
    assert leadership_weekly_mark(["A"], CUR, NEW, totals=totals) == 10.0


def test_a_week_still_being_filed_is_not_a_level(weekly):
    """On Sunday 20 Sep the week ending that day is still being filed: the
    cambio reads its last finished week, 13 Sep, and so do the areas."""
    sunday = date(2026, 9, 20)
    cur = cycle_series(["A", "B"], FECHA, cycles=[CUR], weekly=weekly,
                       today=sunday, goals_by_cycle={})[-1]
    assert cur.actual == 6
    rows = {r.area: r for r in area_rows(
        ["A", "B"], FECHA, (CUR["start"], sunday), weekly=weekly,
        today=sunday)}
    assert rows["A"].actual == 4 and rows["B"].actual == 2
