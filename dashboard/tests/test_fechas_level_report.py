"""Fechas are a level in the Informes model — PLAN-2026-10-17-fechas-level.md
steps 2, 3 and 5 (L1–L4).

"Amigos con Fecha Bautismal" is how many friends hold a date that week. A
period's figure is its LAST complete week (L3), a silent area counting zero
(L4), with the period's mean level beside it; leadership's goal is a level,
never multiplied by weeks (L2). The flows around it are untouched.

Five areas over two zones, two complete weeks of 2026-6, the same shape as
`test_report_model_ki`: week 1 holds 5 friends with a date (A1 3, A2 1, B1 1),
week 2 holds 6 (A1 4, A3 2). Every area's goal is a level of 2.
"""

from datetime import date

import pandas as pd
import pytest

from app.reports import model as M
from app.reports import periods as P
from app.reports import scope as S
from tests.test_report_model_ki import (CYCLES, DAILY, NEW, ROSTER, TODAY, W1,
                                        W2)

FECHA = "ki_baptismal_date_real"

WEEKLY_KI = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", NEW: 10, FECHA: 3},
    {"_week": "2026-09-13", "_area": "A2", NEW: 20, FECHA: 1},
    {"_week": "2026-09-13", "_area": "B1", NEW: 30, FECHA: 1},
    {"_week": "2026-09-20", "_area": "A1", NEW: 12, FECHA: 4},
    {"_week": "2026-09-20", "_area": "A3", NEW: 8, FECHA: 2},
])

# The model reads a level goal as a level (goals_queries converts the old
# cycles' six-week totals before it gets here).
GOALS = pd.DataFrame(
    [{"area": a, "transfer_start": "2026-09-07", NEW: 30, FECHA: 2}
     for a in ("A1", "A2", "A3", "B1", "B2")])


def _ki_goals(week, areas=None):
    if week == W1:
        return {NEW: 80.0, FECHA: 9.0}, {NEW: 4, FECHA: 4}, date(2026, 9, 6), 4
    return {NEW: 100.0, FECHA: 10.0}, {NEW: 5, FECHA: 5}, date(2026, 9, 13), 5


def _data(**over) -> M.ReportData:
    kw = dict(
        roster=ROSTER, weekly_ki=WEEKLY_KI, daily_log=DAILY,
        transfer_goals=GOALS, cycles=CYCLES, ki_keys=(NEW, FECHA),
        labels={NEW: "Nuevas Personas", FECHA: "Amigos con Fecha Bautismal"},
        mission_name="Misión de Prueba", today=TODAY, anchor=W2,
        ki_goals_fn=_ki_goals)
    kw.update(over)
    return M.ReportData(**kw)


@pytest.fixture
def data():
    return _data()


@pytest.fixture
def period(data):
    return P.resolve(P.THIS_TRANSFER, TODAY, data.cycles)


def _row(data, period, key=FECHA, level=None, **where):
    sc = S.resolve(data.roster, level, mission_name=data.mission_name, **where)
    comp = P.comparison_for(period, TODAY, data.cycles)
    return M.build_report(sc, period, comp, data).ki(key)


def test_the_figure_is_the_last_week_never_the_sum(data, period):
    row = _row(data, period)
    assert row.level and row.level_week == W2
    assert row.actual == 6            # not 5 + 6 = 11
    assert row.average == pytest.approx(5.5)
    assert row.area_week_sum == 11


def test_the_goal_is_a_level_not_multiplied_by_weeks(data, period):
    row = _row(data, period)
    assert row.leadership_goal == 10          # five areas holding 2 each
    assert row.lead_goal == 10 and row.lead_actual == 6
    assert row.lead_area_weeks == 5 and row.lead_area_weeks_possible == 5
    assert row.grade.pct == pytest.approx(60.0)


def test_a_silent_area_holds_zero(data, period):
    """A2 filed week 1 but not week 2: its level is 0, graded 0% (L4)."""
    row = _row(data, period, level=S.AREA, area="A2")
    assert row.actual == 0
    assert row.grade.pct == 0
    assert row.average == pytest.approx(0.5)


def test_an_area_that_never_filed_has_no_reading(data, period):
    row = _row(data, period, level=S.AREA, area="B2")
    assert row.actual is None and row.grade.pct is None


def test_the_companionships_meta_is_that_weeks_level(data, period):
    row = _row(data, period)
    assert row.meta == 10 and row.meta_area_weeks == 5


def test_flows_still_add_up(data, period):
    row = _row(data, period, key=NEW)
    assert not row.level and row.actual == 80


def test_the_index_still_counts_every_report(data, period):
    """The productivity index keeps the average level per companionship
    (decision 45) and counts the reports behind it, not one week's level."""
    row = _row(data, period)
    assert row.per_active_area_week == pytest.approx(5.5 / 5)


def test_the_old_cycles_read_as_levels(monkeypatch):
    """2026-6 was saved as six-week totals: read as levels they are the
    total over six, unrounded (L5); 2026-7 stores the level."""
    import app.db.goals_queries as gq
    rows = pd.DataFrame([
        {"area": "A1", "transfer_start": "2026-09-07", FECHA: "29"},
        {"area": "A2", "transfer_start": "2026-09-07", FECHA: "4"},
        {"area": "A1", "transfer_start": "2026-10-19", FECHA: "4"}])
    monkeypatch.setattr(gq, "read_tab",
                        lambda tab, header_marker=None: rows.copy())
    monkeypatch.setattr(gq, "_metric_cols", lambda: [FECHA])
    monkeypatch.setattr(gq, "_cycle_weeks",
                        lambda: {"2026-09-07": 6, "2026-10-19": 6})
    every = gq.all_area_transfer_goals(levels=True)
    assert every[FECHA].tolist() == pytest.approx([29 / 6, 4 / 6, 4.0])
