"""Who an Informes report is about — `app/reports/scope.py`.

A fixture roster, never the live sheet: these tests are about the resolution
rules, and a mission that reorganises its districts should not turn them red.

The rule under test throughout is that MISSION_ORG decides membership. Every
data tab in this app — WEEKLY_KI, SCORES, DAILY_LOG — carries its own Zone and
District columns recording where an area was when the row was written, and an
area that has since transferred would keep reporting under its old zone if
anything here ever read one of those.
"""

import pandas as pd
import pytest

from app.reports import scope as S

# Two zones, five areas, and four districts spread over three district NAMES —
# enough to tell the levels apart, small enough to hold in your head while
# reading a failure. "Ribera" sits in both zones on purpose; see the key test
# below.
ROSTER = pd.DataFrame([
    {"Area_Name": "Alemania 1", "Zone": "Angol", "District": "El Mirador",
     "Companion1_Name": "Said Adasme", "Companion2_Name": "Gustavo Caetano"},
    {"Area_Name": "Alemania 2", "Zone": "Angol", "District": "El Mirador",
     "Companion1_Name": "Benny Jimenez", "Companion2_Name": ""},
    {"Area_Name": "Collipulli", "Zone": "Angol", "District": "Ribera",
     "Companion1_Name": "", "Companion2_Name": ""},
    {"Area_Name": "Laja 1", "Zone": "San Pedro", "District": "Ribera",
     "Companion1_Name": "Melina Anfuso", "Companion2_Name": "Kenzie Linton"},
    {"Area_Name": " Lomas ", "Zone": " San Pedro ", "District": "Costanera",
     "Companion1_Name": "Ana Rojas", "Companion2_Name": "Sara Vidal"},
])

MISSION_NAME = "Misión Concepción Sur"


# ── The levels ────────────────────────────────────────────────────────────────

def test_the_mission_holds_every_area_on_the_roster():
    m = S.mission_scope(ROSTER, MISSION_NAME)
    assert m.level == S.MISSION
    assert m.area_count == 5
    assert m.key == "mission"


def test_names_are_stripped_once_so_every_later_test_compares_like_with_like():
    """SCORES and DAILY_LOG both carry names with stray whitespace. The roster
    is cleaned here, at the only point membership is decided."""
    assert "Lomas" in S.mission_scope(ROSTER).areas
    assert [z.name for z in S.zone_scopes(ROSTER)] == ["Angol", "San Pedro"]


def test_a_zone_holds_its_own_areas():
    angol = S.resolve(ROSTER, S.ZONE, zone="Angol")
    assert angol.areas == ("Alemania 1", "Alemania 2", "Collipulli")
    assert angol.zone == "Angol"


def test_districts_are_grouped_by_zone_not_by_name_alone():
    """Nothing guarantees district names are unique across zones — CCSM's 13
    happen to be, and that is not a fact worth resting a packet on. Two zones
    with a "Ribera" are two districts, with two keys."""
    riberas = [d for d in S.district_scopes(ROSTER) if d.name == "Ribera"]
    assert len(riberas) == 2
    assert {d.key for d in riberas} == {
        "district:Angol/Ribera", "district:San Pedro/Ribera"}
    assert {d.areas for d in riberas} == {("Collipulli",), ("Laja 1",)}


def test_a_district_is_resolved_within_its_zone():
    d = S.resolve(ROSTER, S.DISTRICT, zone="San Pedro", district="Ribera")
    assert d.areas == ("Laja 1",)


def test_an_area_carries_its_companionship():
    """Decision 27: one companionship per area, so the area view IS the
    companionship view and has their names on it."""
    a = S.resolve(ROSTER, S.AREA, area="Alemania 1")
    assert a.companions == ("Said Adasme", "Gustavo Caetano")
    assert a.areas == ("Alemania 1",)


def test_a_solo_or_unstaffed_area_does_not_invent_a_blank_missionary():
    assert S.resolve(ROSTER, S.AREA, area="Alemania 2").companions == ("Benny Jimenez",)
    assert S.resolve(ROSTER, S.AREA, area="Collipulli").companions == ()


# ── Resolution ────────────────────────────────────────────────────────────────

def test_no_level_means_the_whole_mission():
    """`render_scope_selectors` returns None for its fourth value when nothing
    is picked."""
    assert S.resolve(ROSTER, None, mission_name=MISSION_NAME).level == S.MISSION


def test_a_unit_that_is_not_on_the_roster_resolves_to_nothing():
    """None, not a mission-wide scope. A zone that has left MISSION_ORG should
    say so rather than quietly reporting the whole mission under its name."""
    assert S.resolve(ROSTER, S.ZONE, zone="Provo North") is None
    assert S.resolve(ROSTER, S.AREA, area="Nowhere") is None


def test_an_empty_roster_resolves_to_an_empty_mission_rather_than_crashing():
    empty = S.mission_scope(pd.DataFrame())
    assert empty.level == S.MISSION and empty.areas == ()
    assert S.zone_scopes(pd.DataFrame()) == []


# ── Walking up and down ───────────────────────────────────────────────────────

def test_children_step_exactly_one_level_down():
    m = S.mission_scope(ROSTER, MISSION_NAME)
    assert [c.name for c in S.children(ROSTER, m)] == ["Angol", "San Pedro"]
    angol = S.resolve(ROSTER, S.ZONE, zone="Angol")
    assert [c.name for c in S.children(ROSTER, angol)] == ["El Mirador", "Ribera"]
    mirador = S.resolve(ROSTER, S.DISTRICT, zone="Angol", district="El Mirador")
    assert [c.name for c in S.children(ROSTER, mirador)] == ["Alemania 1", "Alemania 2"]


def test_an_area_has_no_children():
    """Per-missionary history is explicitly out of scope (decision 27)."""
    a = S.resolve(ROSTER, S.AREA, area="Alemania 1")
    assert S.children(ROSTER, a) == []
    assert a.child_level is None


def test_a_parent_chain_reaches_the_mission():
    a = S.resolve(ROSTER, S.AREA, area="Laja 1")
    d = S.parent(ROSTER, a)
    z = S.parent(ROSTER, d)
    m = S.parent(ROSTER, z, MISSION_NAME)
    assert [d.name, z.name, m.name] == ["Ribera", "San Pedro", MISSION_NAME]
    assert S.parent(ROSTER, m) is None


def test_a_parent_lookup_does_not_cross_into_the_other_zones_namesake():
    """Laja 1's district is San Pedro's Ribera, not Angol's."""
    a = S.resolve(ROSTER, S.AREA, area="Laja 1")
    assert S.parent(ROSTER, a).areas == ("Laja 1",)


def test_the_running_head_names_the_ancestors_and_not_the_unit_itself():
    a = S.resolve(ROSTER, S.AREA, area="Laja 1")
    assert a.trail == ("San Pedro", "Ribera")
    assert S.resolve(ROSTER, S.ZONE, zone="San Pedro").trail == ()


# ── Packet order ──────────────────────────────────────────────────────────────

def test_walk_visits_every_scope_once_level_by_level():
    """PLAN §3.2's order: the mission, then all zones, then all districts, then
    all areas — because that is how the packet is handed out, a block at a
    time. On CCSM this is 1 + 4 + 13 + 45 = 63."""
    walked = S.walk(ROSTER, MISSION_NAME)
    assert [s.level for s in walked] == (
        [S.MISSION] + [S.ZONE] * 2 + [S.DISTRICT] * 4 + [S.AREA] * 5)
    assert len({s.key for s in walked}) == len(walked)


@pytest.mark.parametrize("level,expected", [
    (S.MISSION, S.ZONE), (S.ZONE, S.DISTRICT),
    (S.DISTRICT, S.AREA), (S.AREA, None),
])
def test_child_level_walks_the_ladder(level, expected):
    assert S.Scope(level=level, name="x", areas=()).child_level == expected
