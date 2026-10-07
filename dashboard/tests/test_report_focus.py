"""Where to focus and what to pull — PLAN-2026-10-06 Phase 3.

`focus.pareto` divides the mission's shortfall against leadership's goal
among its units (AUDIT H6); `trend_change` is the quadrant's other axis, per
reporting area-week (rule 2 — on raw sums it called every zone "rising");
`mature_funnel` follows people found three to six months ago so the lower
funnel has had time to happen (AUDIT M2).
"""

from datetime import date

import pandas as pd
import pytest

from app.reports import focus as FC
from app.reports import model as M
from app.reports import scope as S

DATE, NEW = "ki_baptismal_date_real", "ki_new_people_real"
W = {DATE: 3, NEW: 1}


def _unit(name, rows):
    return S.Scope(level=S.DISTRICT, name=name, areas=())


def _row(key, goal, actual):
    return M.MetricRow(key=key, label=key, leadership_goal=goal, actual=actual)


# ── The Pareto ───────────────────────────────────────────────────────────────

def test_the_shortfall_is_shared_out_by_weighted_parts():
    """A is short 30 of the 40 dates missing and 0 of the 100 new people; B
    the other 10 dates and all 100 new people. Dates weigh 3, new people 1:
    A = (3·75 + 1·0)/4 = 56,25%, B = (3·25 + 1·100)/4 = 43,75%."""
    a = (_unit("A", 0), [_row(DATE, 40, 10), _row(NEW, 100, 150)], 80.0, -10.0)
    b = (_unit("B", 0), [_row(DATE, 20, 10), _row(NEW, 200, 100)], 120.0, 5.0)
    rows = FC.pareto([a, b], W)
    assert [r.name for r in rows] == ["A", "B"]
    assert rows[0].share == pytest.approx(56.25)
    assert rows[1].share == pytest.approx(43.75)
    assert rows[-1].cumulative == pytest.approx(100)
    assert rows[0].worst == DATE and rows[1].worst == NEW


def test_a_unit_ahead_of_its_goal_cancels_nobody():
    """Over-delivery is floored at zero, so it cannot hide another's gap."""
    a = (_unit("A", 0), [_row(DATE, 10, 50)], None, None)
    b = (_unit("B", 0), [_row(DATE, 10, 0)], None, None)
    rows = FC.pareto([a, b], W)
    assert rows[0].name == "B" and rows[0].share == pytest.approx(100)


def test_no_leadership_goal_is_no_pareto():
    a = (_unit("A", 0), [_row(DATE, None, 5)], None, None)
    assert FC.pareto([a], W) == ()


# ── The trend ────────────────────────────────────────────────────────────────

def test_the_trend_is_per_reporting_area_week():
    """Twice the reports, the same work per report: no trend at all."""
    weekly = pd.DataFrame(
        [{"_week": "w1", "_area": "A", DATE: 2}]
        + [{"_week": "w2", "_area": a, DATE: 2} for a in ("A", "B")])
    assert FC.trend_change(weekly, ["A", "B"], W, recent=["w2"],
                           prior=["w1"]) == pytest.approx(0)


@pytest.mark.parametrize("index,trend,words", [
    (80, -20, "debajo y bajando"), (80, 20, "debajo y subiendo"),
    (120, -20, "encima y bajando"), (120, 2, "encima y estable"),
    (None, 5, None),
])
def test_the_quadrant_in_words(index, trend, words):
    assert FC.quadrant(index, trend) == words


# ── The mature funnel ────────────────────────────────────────────────────────

def test_the_mature_funnel_follows_a_three_to_six_month_cohort():
    today = date(2026, 10, 6)
    found = pd.Series(pd.to_datetime(
        ["2026-05-01"] * 40 + ["2026-09-30"] * 40))       # second lot too new
    reached = pd.Series(pd.to_datetime(["2026-06-01"] * 20 + [None] * 60))
    group = pd.Series([True] * 80)
    fn = FC.mature_funnel(found, [reached], ["Bautizados"],
                          [("Z", group, True)], today)
    assert fn.mission.found == 40
    assert fn.mission.pct(0) == pytest.approx(50)
    assert fn.start == date(2026, 4, 9) and fn.end == date(2026, 7, 8)


def test_a_leak_is_named_only_when_it_is_material():
    """A step converting under 85% of the mission's own rate is the leak;
    a step at 99% of it is not a finding."""
    today = date(2026, 10, 6)
    n = 200
    found = pd.Series(pd.to_datetime(["2026-05-01"] * n))
    zone = pd.Series([i < 100 for i in range(n)])
    # Mission converts 60%; zone Z converts 30% (its own 100 rows), the rest 90%.
    hit = [i < 30 for i in range(100)] + [i < 90 for i in range(100)]
    reached = pd.Series(pd.to_datetime(
        ["2026-06-01" if h else None for h in hit]))
    fn = FC.mature_funnel(found, [reached], ["Intento de Contacto"],
                          [("Z", zone, True), ("Y", ~zone, True)], today)
    leaks = {r.name: r.leak for r in fn.rows}
    assert leaks["Z"] == "encontradas a intento"
    assert leaks["Y"] is None


def test_a_named_leak_carries_its_own_step_and_the_mission_s():
    """2026-10-07: the table printed 0% down the baptism column under a leak
    named "fecha a bautismo" — the reader could not check it. The leak now
    carries the step's conversion here and in the mission."""
    today = date(2026, 10, 6)
    n = 200
    found = pd.Series(pd.to_datetime(["2026-05-01"] * n))
    zone = pd.Series([i < 100 for i in range(n)])
    hit = [i < 30 for i in range(100)] + [i < 90 for i in range(100)]
    reached = pd.Series(pd.to_datetime(
        ["2026-06-01" if h else None for h in hit]))
    fn = FC.mature_funnel(found, [reached], ["Intento de Contacto"],
                          [("Z", zone, True), ("Y", ~zone, True)], today)
    steps = {r.name: r.leak_step for r in fn.rows}
    assert steps["Z"] == pytest.approx((30.0, 60.0))
    assert steps["Y"] is None
