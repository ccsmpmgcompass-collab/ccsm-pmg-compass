"""The productivity index and the reporting list — PLAN-2026-10-06 Phase 1.

Decision 45: units rank on output per ACTIVE companionship-week against the
mission's, weighted toward the results nearest baptism (P1: dates 3,
sacrament 2, recent converts 2, member lessons 1, new people 1, first week 1;
the form's baptisms are not a member). No goal goes into it, which is the
whole point — on 2026-10-06 the self-goal ranking put the least productive
zone at the top because it set the lowest goals (AUDIT-2026-10-06 C1).
"""

import pytest

from app.reports import model as M

DATE, SACR, RC = ("ki_baptismal_date_real", "ki_friends_sacrament_real",
                  "ki_rc_at_church_real")
NEW, BAUT = "ki_new_people_real", "ki_baptized_confirmed_real"


def _row(key, actual, per_active):
    return M.MetricRow(key=key, label=key, actual=actual,
                       per_active_area_week=per_active)


MISSION = [_row(DATE, 100, 1.0), _row(SACR, 200, 2.0), _row(NEW, 800, 8.0),
           _row(BAUT, 10, 0.1)]


def test_the_mission_is_100_by_construction():
    assert M.productivity(MISSION, MISSION).value == pytest.approx(100)


def test_members_are_weighted_toward_baptism():
    """Twice the mission's dates and the mission's pace on the rest: dates
    weigh 3 of 6 here (3 + 2 + 1), so the index is (3·200 + 2·100 + 100) / 6."""
    unit = [_row(DATE, 20, 2.0), _row(SACR, 20, 2.0), _row(NEW, 80, 8.0)]
    assert M.productivity(unit, MISSION).value == pytest.approx(900 / 6)


def test_the_form_s_baptisms_are_not_a_member():
    """Seven events a transfer across the mission: one baptism would move a
    unit by a third."""
    unit = [_row(DATE, 10, 1.0), _row(BAUT, 5, 5.0)]
    idx = M.productivity(unit, MISSION)
    assert idx.value == pytest.approx(100)
    assert BAUT not in dict(idx.members)


def test_a_member_s_ratio_is_capped():
    unit = [_row(DATE, 2, 10.0)]
    assert M.productivity(unit, MISSION).ratio(DATE) == M.INDEX_CAP


def test_a_unit_nobody_reported_for_has_no_index():
    """Not zero: silence is the reporting list's business."""
    unit = [_row(DATE, None, None), _row(SACR, None, None)]
    assert M.productivity(unit, MISSION).value is None


def test_few_events_are_said_to_be_few():
    thin = M.productivity([_row(DATE, 3, 1.0)], MISSION)
    assert thin.thin and thin.value == pytest.approx(100)
    assert not M.productivity([_row(DATE, 30, 1.0)], MISSION).thin


def test_another_mission_s_catalogue_weighs_everything_but_baptisms():
    weights = M.index_weights(["ki_custom_a_real", "ki_custom_b_real", BAUT])
    assert weights == {"ki_custom_a_real": 1, "ki_custom_b_real": 1}


def test_the_reporting_list_puts_the_quietest_unit_first():
    """Decision 45's separate list: reporting is its own ranking."""
    from datetime import date
    from app.reports import periods as P
    from app.reports import scope as S

    def child(name, reported, silent):
        cov = P.week_coverage(
            P.Period(key="x", label="x", start=date(2026, 9, 7),
                     end=date(2026, 9, 20),
                     weeks=(date(2026, 9, 13), date(2026, 9, 20)),
                     full_end=date(2026, 9, 20), full_weeks=2),
            {"2026-09-13": reported, "2026-09-20": reported}, 4)
        return M.ChildRow(scope=S.Scope(level=S.ZONE, name=name, areas=()),
                          rank=1, coverage=cov, areas_silent=silent)

    model = M.ReportModel(
        scope=S.Scope(level=S.MISSION, name="M", areas=()), period=None,
        comparison=None, mission_name="M", today=date(2026, 9, 21),
        children=(child("Llena", 4, ()), child("Callada", 1, ("A", "B"))))
    assert [c.name for c in model.reporting_ranked] == ["Callada", "Llena"]
