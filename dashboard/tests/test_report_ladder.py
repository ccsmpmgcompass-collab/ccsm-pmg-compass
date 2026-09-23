"""The comparison ladder — Phase V.

Zackary, 2026-09-23: "I want for every zone to show how the zone is doing in
comparison to the mission averages, and for every district showing them how
the district is doing in comparison to the zone that they're in's average."

`ReportModel.ladder` is that, built once in the model so the screen and the
printed packet cannot disagree about the sign of a gap (decision 30). Every
figure on it is attainment per ACTIVE area — the cross-unit basis of §1's
rule 2 — because a zone whose areas went silent must not outrank one whose
areas all filed.

The fixture is deliberately lopsided: Norte's two districts report unevenly and
Sur files one weak week, so the mission's mean sits between the two zones and
every rung of the ladder carries a different number.
"""

from datetime import date

import pandas as pd
import pytest

from app.reports import model as M
from app.reports import periods as P
from app.reports import scope as S

TODAY = date(2026, 9, 21)

CYCLES = [
    {"number": "2026-5", "start": date(2026, 7, 27), "end": date(2026, 9, 6),
     "weeks": 6, "status": "Actual"},
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
     "weeks": 6, "status": "Actual"},
]

ROSTER = pd.DataFrame([
    {"Area_Name": "A1", "Zone": "Norte", "District": "D1"},
    {"Area_Name": "A2", "Zone": "Norte", "District": "D1"},
    {"Area_Name": "A3", "Zone": "Norte", "District": "D2"},
    {"Area_Name": "B1", "Zone": "Sur", "District": "D3"},
])

NEW = "ki_new_people_real"
SACR = "ki_friends_at_sacrament_real"

# The goal works out at 20 new people and 4 friends per area-week. D1 files
# both weeks for both areas and hits both goals exactly; D2 files one week and
# misses; Sur files one weak week. So every rung of the ladder — the district,
# its zone, the mission — lands on a different number, which is the only way a
# test can tell a real comparison from three copies of one figure.
WEEKLY_KI = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", NEW: 20, SACR: 4},
    {"_week": "2026-09-13", "_area": "A2", NEW: 20, SACR: 4},
    {"_week": "2026-09-20", "_area": "A1", NEW: 20, SACR: 4},
    {"_week": "2026-09-20", "_area": "A2", NEW: 20, SACR: 4},
    {"_week": "2026-09-20", "_area": "A3", NEW: 10, SACR: 0},
    {"_week": "2026-09-20", "_area": "B1", NEW: 5, SACR: 0},
])

LABELS = {NEW: "Nuevas Personas", SACR: "Amigos en la Reunion Sacramental"}


def _ki_goals(week, areas=None):
    return {NEW: 80.0, SACR: 16.0}, {NEW: 4, SACR: 4}, date(2026, 9, 6), 4


def _data(**over) -> M.ReportData:
    kw = dict(roster=ROSTER, today=TODAY, anchor=date(2026, 9, 20),
              weekly_ki=WEEKLY_KI, cycles=CYCLES, ki_keys=(NEW, SACR),
              labels=LABELS, mission_name="Mision de Prueba",
              ki_goals_fn=_ki_goals)
    kw.update(over)
    return M.ReportData(**kw)


@pytest.fixture
def data():
    return _data()


@pytest.fixture
def period(data):
    return P.resolve(P.THIS_TRANSFER, TODAY, data.cycles)


def _report(data, period, level=None, **where):
    sc = S.resolve(data.roster, level, mission_name=data.mission_name, **where)
    comp = P.comparison_for(period, TODAY, data.cycles,
                            against=P.COMPARE_PRECEDING)
    return M.build_report(sc, period, comp, data)


def _roles(model):
    return [r.role for r in model.ladder]


# ── What the ladder is ───────────────────────────────────────────────────────

def test_a_zone_is_compared_to_the_mission(data, period):
    """Zackary's ask, at zone level: two rungs, itself and the mission."""
    m = _report(data, period, S.ZONE, zone="Norte")
    assert _roles(m) == ["esta zona", "la misión"]
    assert [r.scope.name for r in m.ladder] == ["Norte", "Mision de Prueba"]


def test_a_district_is_compared_to_its_zone_and_the_mission(data, period):
    """And at district level: itself, the zone it is in, the mission."""
    m = _report(data, period, S.DISTRICT, zone="Norte", district="D1")
    assert _roles(m) == ["este distrito", "su zona", "la misión"]
    assert [r.scope.name for r in m.ladder] == ["D1", "Norte", "Mision de Prueba"]


def test_an_area_climbs_the_whole_ladder(data, period):
    """An area gets all three rungs above it, coarsest last."""
    m = _report(data, period, S.AREA, zone="Norte", district="D1", area="A1")
    assert _roles(m) == ["esta área", "su distrito", "su zona", "la misión"]


def test_the_mission_has_no_ladder(data, period):
    """Nothing is above it, and a rung against itself is a row of zeroes
    wearing a comparison's clothes."""
    assert _report(data, period).ladder == ()


def test_the_first_rung_is_the_unit_itself(data, period):
    m = _report(data, period, S.ZONE, zone="Norte")
    assert m.ladder[0].is_self is True
    assert all(r.is_self is False for r in m.ladder[1:])


# ── The numbers on it ────────────────────────────────────────────────────────

def test_every_rung_reads_per_active_area(data, period):
    """Rule 2: the cross-unit basis, divided by every roster area-week and not
    only the ones that filed.

    D1's four area-weeks all filed and all hit the goal — 100%. Norte's 90 new
    people spread over six active area-weeks is 15 a week against 20 (75%),
    and its 16 friends over six is 2,67 against 4 (67%). The mission's 95 over
    eight is 11,875 (59%) and its 16 over eight is 2 (50%).
    """
    m = _report(data, period, S.DISTRICT, zone="Norte", district="D1")
    own, zone, mission = m.ladder
    assert own.mean_attainment == pytest.approx(100.0)
    assert zone.mean_attainment == pytest.approx((75 + 100 * (16 / 6) / 4) / 2)
    assert mission.mean_attainment == pytest.approx((59.375 + 50) / 2)


def test_the_units_own_rung_repeats_its_own_key_indicators(data, period):
    """The ladder is not a second opinion about the unit — rung zero carries
    exactly the rows the rest of the page prints."""
    m = _report(data, period, S.ZONE, zone="Norte")
    assert m.ladder[0].metrics == m.key_indicators


def test_the_delta_is_this_unit_minus_the_rung(data, period):
    """In percentage points, and signed the way a reader expects: a zone above
    the mission is positive."""
    m = _report(data, period, S.ZONE, zone="Norte")
    own, mission = m.ladder
    assert own.delta is None
    assert mission.delta == pytest.approx(
        own.mean_attainment - mission.mean_attainment)
    assert mission.delta > 0          # Norte files; Sur does not


def test_a_zone_below_the_mission_gets_a_negative_delta(data, period):
    """Sur filed one weak week, so it sits under the mission — and the sign
    says so without the reader having to subtract anything."""
    m = _report(data, period, S.ZONE, zone="Sur")
    assert m.ladder[1].delta < 0


def test_a_unit_that_filed_nothing_has_no_gap_to_report(data, period):
    """Not a gap of its whole attainment: a zone nobody reported for has no
    reading, and printing "−53 puntos" would be a statement about the forms
    dressed up as a statement about the work."""
    quiet = _data(weekly_ki=WEEKLY_KI[WEEKLY_KI["_area"] != "B1"])
    m = _report(quiet, P.resolve(P.THIS_TRANSFER, TODAY, quiet.cycles),
                S.ZONE, zone="Sur")
    assert m.ladder[0].mean_attainment is None
    assert m.ladder[1].delta is None


def test_there_is_one_delta_per_key_indicator_in_order(data, period):
    """`deltas` lines up with the rung's own metrics, so a renderer can print
    a gap beside each indicator without doing arithmetic of its own."""
    m = _report(data, period, S.DISTRICT, zone="Norte", district="D1")
    zone = m.ladder[1]
    assert len(zone.deltas) == len(zone.metrics) == 2
    for delta, row in zip(zone.deltas, zone.metrics):
        own = m.ki(row.key)
        assert delta == pytest.approx(own.attainment_per_active_area
                                      - row.attainment_per_active_area)
    assert m.ladder[0].deltas == ()


def test_an_indicator_nobody_can_grade_gets_no_delta(data, period):
    """A missing percentage is not a zero: subtracting from None would invent
    a gap out of a goal that was never set."""
    d = _data(ki_goals_fn=lambda week, areas=None: ({}, {}, date(2026, 9, 6), 0))
    m = _report(d, P.resolve(P.THIS_TRANSFER, TODAY, d.cycles),
                S.ZONE, zone="Norte")
    assert all(x is None for x in m.ladder[1].deltas)
    assert m.ladder[1].delta is None


# ── Sideways: the units beside this one ──────────────────────────────────────

def test_a_district_is_given_the_other_districts_of_its_zone(data, period):
    """The other half of "is 73% good". The ladder answers it upward; this
    answers it sideways, and sideways is the half a leader can act on."""
    m = _report(data, period, S.DISTRICT, zone="Norte", district="D1")
    assert sorted(c.name for c in m.siblings) == ["D1", "D2"]


def test_a_unit_is_among_its_own_siblings(data, period):
    """It has to be: the strip plot marks one dot, and a unit missing from its
    own distribution would be marking somebody else."""
    m = _report(data, period, S.ZONE, zone="Norte")
    assert [c.name for c in m.siblings] == ["Sur", "Norte"]   # weakest first
    assert any(c.name == m.scope.name for c in m.siblings)


def test_an_only_child_gets_no_siblings(data, period):
    """A strip of one dot is a picture of nothing."""
    m = _report(data, period, S.AREA, zone="Sur", district="D3", area="B1")
    assert m.siblings == ()


def test_the_mission_has_no_siblings(data, period):
    assert _report(data, period).siblings == ()


def test_a_sibling_carries_the_same_figure_as_its_own_page(data, period):
    """One rule for the headline. A district reading 61 on the strip and 58 on
    its own page would be the same unit measured two ways."""
    zone = _report(data, period, S.ZONE, zone="Norte")
    for child in zone.siblings:
        own = _report(data, period, S.ZONE, zone=child.name)
        assert child.mean_attainment == own.mean_attainment


# ── What it costs ────────────────────────────────────────────────────────────

def _ki_calls(data) -> list:
    """The scopes `build_all` reduces WEEKLY_KI for, in order.

    The counter is put back by hand rather than with `monkeypatch`, which
    stacks: a second call would wrap the first counter and both lists would
    fill.
    """
    calls, real = [], M._ki_rows

    def counted(*a, **kw):
        calls.append(a[1].key)
        return real(*a, **kw)

    M._ki_rows = counted
    try:
        M.build_all(P.THIS_TRANSFER, P.COMPARE_PRECEDING, data=data)
    finally:
        M._ki_rows = real
    return calls


def test_the_ladder_costs_no_extra_pass_over_the_weekly_form(monkeypatch):
    """Every rung is a unit the packet was already building.

    Without the memo the ladder is the most expensive thing in the document —
    63 units each asking their ancestors for Key Indicators that 63 other
    builds already computed. With it, turning the ladder off changes nothing.
    """
    with_ladder = _ki_calls(_data())
    monkeypatch.setattr(M, "_ladder", lambda *a, **kw: ())
    without = _ki_calls(_data())
    assert with_ladder == without


def _ranking_calls(data) -> int:
    """How many times `build_all` ranks a list of units."""
    calls, real = [], M._rank_scopes

    def counted(*a, **kw):
        calls.append(len(a[1]))
        return real(*a, **kw)

    M._rank_scopes = counted
    try:
        M.build_all(P.THIS_TRANSFER, P.COMPARE_PRECEDING, data=data)
    finally:
        M._rank_scopes = real
    return len(calls)


def test_siblings_cost_no_second_ranking(monkeypatch):
    """Every unit wants the same list twice — once as its own children and
    once as each child's siblings. Ranked once, it is free both times."""
    with_siblings = _ranking_calls(_data())
    monkeypatch.setattr(M, "_siblings", lambda *a, **kw: ())
    assert _ranking_calls(_data()) == with_siblings


def test_a_scope_is_reduced_once_per_build():
    """`build_all` ranks every zone twice over — once as the mission's child
    and once as its own model — and the memo means the frame is cut once."""
    calls = _ki_calls(_data())
    # The mission alone is asked twice: `ki_goal_flags` grades the goals at
    # mission scope, against no comparison, before any unit is built.
    assert calls.count("mission") == 2
    assert calls.count("zone:Norte") == 1
    assert calls.count("district:Norte/D1") == 1
    assert calls.count("area:A1") == 1
