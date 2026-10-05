"""AREA_LINEAGE: proposing, storing and reading the link between a new area and
the area it continues.

PLAN-2026-10-05-roster-access.md R6 / D3 / D6. Everything in CCSM is keyed by
area NAME, so a renamed or split area starts from nothing. The 2026-09-07
transfer closed five areas and opened seven; the fixtures below are those
areas and the missionaries in them, as MISSION_ORG_SNAPSHOT and MISSION_ORG
recorded them.
"""

from datetime import date

import pandas as pd
import pytest

from app.db import queries as q
from app.ingestion import area_goals_runner as R
from app.ingestion import transfer_engine as te


def _org(name, zone, c1, c2="", active="TRUE"):
    return {"Area_Name": name, "Zone": zone, "District": "", "Active": active,
            "Companion1_Name": c1, "Companion2_Name": c2,
            "Companion1_Email": "", "Companion2_Email": "",
            "Is_DL": "FALSE", "Is_ZL": "FALSE", "Is_STL": "FALSE",
            "Is_AP": "FALSE", "Is_MP": "FALSE"}


def _roster(name, zone, c1, c2=""):
    return {"Area": name, "Zone": zone, "District": "", "Companion1_Name": c1,
            "Companion2_Name": c2, "Companion3_Name": "", "Companion4_Name": "",
            "Calling": "", "Area_Email": ""}


ANG, LAN = "Angol", "Los Angeles Norte"

#: MISSION_ORG before the 2026-09-07 apply: the five areas it closed, plus one
#: that carried on unchanged.
BEFORE = [
    _org("Collipulli", ANG, "Bruno Andrade", "Parker Kimball"),
    _org("Los Sauces", ANG, "Bitner Tiul Poou", "Conner Miller"),
    _org("Galvarino", LAN, "Gustavo dos Santos Ribeiro", "Samuel Rondina"),
    _org("Huepil & Tucapel & Villa Obispo", LAN, "John Kearns", "Aarón Arens Rodas"),
    _org("Villa Obispo", LAN, "Melina Lagraña", "Milagros Bravo"),
    _org("Alemania 2", ANG, "Benny Jimenez", "Gabriel Settle"),
]

#: The roster the apply used: the seven it opened, plus the one that stayed.
AFTER = te.parse_roster([
    _roster("Collipulli 1", ANG, "Douglas Garcia", "Parker Kimball"),
    _roster("Collipulli 2", ANG, "Bruno Andrade"),
    _roster("Purén y Los Sauces", ANG, "Conner Miller", "Kimball Evans"),
    _roster("Galvarino 1", LAN, "Gustavo dos Santos Ribeiro", "Drake Lewis"),
    _roster("Huepil & Tucapel", LAN, "John Kearns"),
    _roster("Villa Obispo 1", LAN, "Melina Lagraña", "Eliza Rampton"),
    _roster("Villa Obispo 2", LAN, "Milagros Bravo", "Katie Keller"),
    _roster("Alemania 2", ANG, "Benny Jimenez", "Gabriel Settle"),
])


def _by_new(proposals):
    return {p["New_Area"]: p for p in proposals}


# ── proposals ─────────────────────────────────────────────────────────────────

def test_the_2026_09_07_transfer_is_proposed_exactly():
    got = _by_new(te.propose_lineage(AFTER, BEFORE))
    assert {k: (v["Old_Areas"], v["Change_Type"]) for k, v in got.items()} == {
        "Collipulli 1": (["Collipulli"], "split"),
        "Collipulli 2": (["Collipulli"], "split"),
        "Purén y Los Sauces": (["Los Sauces"], "rename"),
        "Galvarino 1": (["Galvarino"], "rename"),
        "Huepil & Tucapel": (["Huepil & Tucapel & Villa Obispo"], "rename"),
        "Villa Obispo 1": (["Villa Obispo"], "split"),
        "Villa Obispo 2": (["Villa Obispo"], "split"),
    }
    assert got["Collipulli 1"]["Shared"] == ["Parker Kimball"]
    assert not got["Collipulli 1"]["By_Name"]


def test_a_shared_missionary_beats_a_similar_name():
    """"Villa Obispo 1" is also contained in "Huepil & Tucapel & Villa
    Obispo". The missionary who moved is what says which area it continues."""
    got = _by_new(te.propose_lineage(AFTER, BEFORE))
    assert got["Villa Obispo 1"]["Old_Areas"] == ["Villa Obispo"]


def test_a_missionary_moving_to_another_zone_is_not_a_link():
    before = [_org("Galvarino", LAN, "Samuel Rondina", "Someone Else")]
    after = te.parse_roster([_roster("Nueva", ANG, "Samuel Rondina")])
    assert te.propose_lineage(after, before) == []


def test_the_name_is_the_fallback_when_nobody_stayed():
    before = [_org("Galvarino", LAN, "Old One", "Old Two")]
    after = te.parse_roster([_roster("Galvarino 1", LAN, "New One", "New Two")])
    (p,) = te.propose_lineage(after, before)
    assert p["Old_Areas"] == ["Galvarino"] and p["By_Name"] and p["Shared"] == []


def test_two_closing_areas_into_one_is_a_merge():
    before = [_org("Norte", ANG, "Elder A", "Elder B"),
              _org("Sur", ANG, "Elder C", "Elder D")]
    after = te.parse_roster([_roster("Centro", ANG, "Elder A", "Elder C")])
    (p,) = te.propose_lineage(after, before)
    assert sorted(p["Old_Areas"]) == ["Norte", "Sur"] and p["Change_Type"] == "merge"


def test_an_area_that_stays_proposes_nothing():
    assert "Alemania 2" not in _by_new(te.propose_lineage(AFTER, BEFORE))


# ── the store ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tab(monkeypatch):
    state = {"rows": None}

    def fake_read(tab_name, header_marker=None):
        if tab_name == q.LINEAGE_TAB and state["rows"]:
            return pd.DataFrame(state["rows"][1:], columns=state["rows"][0])
        return pd.DataFrame()

    def fake_write(tab_name, rows):
        assert tab_name == q.LINEAGE_TAB
        state["rows"] = [list(r) for r in rows]

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake_read)
    monkeypatch.setattr("app.db.sheets_client.overwrite_tab", fake_write)
    return state


def _link(new, old, when="2026-09-07", kind="split"):
    return {"Applied_At": "2026-10-05 12:00:00", "Transfer_Date": when,
            "Change_Type": kind, "Old_Areas": old, "New_Area": new,
            "Recorded_By": "test", "Notes": ""}


def test_adding_creates_the_tab_with_its_header(tab):
    assert q.add_area_lineage([_link("Collipulli 1", ["Collipulli"])]) == 1
    assert tab["rows"][0] == q.LINEAGE_HEADERS
    assert tab["rows"][1][q.LINEAGE_HEADERS.index("Old_Areas")] == "Collipulli"


def test_re_applying_the_same_transfer_replaces_rather_than_duplicates(tab):
    q.add_area_lineage([_link("Collipulli 1", ["Collipulli"])])
    q.add_area_lineage([_link("Collipulli 1", ["Collipulli"], kind="rename")])
    assert len(tab["rows"]) == 2
    assert tab["rows"][1][q.LINEAGE_HEADERS.index("Change_Type")] == "rename"


def test_a_split_parent_lists_every_successor(tab):
    q.add_area_lineage([_link("Villa Obispo 2", ["Villa Obispo"]),
                        _link("Villa Obispo 1", ["Villa Obispo"])])
    assert [r["New_Area"] for r in q.get_lineage_successors("Villa Obispo")] == [
        "Villa Obispo 1", "Villa Obispo 2"]
    assert q.get_lineage_successors("Alemania 2") == []


def test_the_shared_parser_gives_each_parent_and_its_cutoff():
    grid = [q.LINEAGE_HEADERS,
            ["x", "2026-09-07", "merge", "Norte;Sur", "Centro", "", ""],
            ["x", "not a date", "rename", "Viejo", "Nuevo", "", ""],
            ["x", "2026-09-07", "rename", "Mismo", "Mismo", "", ""]]
    assert R.lineage(grid) == {
        "Centro": [("Norte", date(2026, 9, 7)), ("Sur", date(2026, 9, 7))]}


# ── the history a new area inherits (R7) ──────────────────────────────────────

from datetime import timedelta

from app.analytics import area_goals as AG

MONDAY = date(2026, 10, 5)
CUTOFF = date(2026, 9, 7)


def _nights(area, first, n, contacts):
    return [{"Date": (first + timedelta(days=i)).isoformat(), "Area": area,
             "contacts_made": str(contacts)} for i in range(n)]


def _daily(*chunks):
    return pd.DataFrame([r for c in chunks for r in c])


def _goal(daily, lineage=None, roster=None):
    roster = roster or {"Purén y Los Sauces": "Angol"}
    return AG.compute(daily, roster, ["contacts_made"], week_start=MONDAY,
                      stretch=1.0, lineage=lineage)


def test_a_new_area_short_of_nights_counts_its_parents_nights():
    """Purén y Los Sauces had 10 nights of its own on 2026-10-05; the rule
    wants 14, so it borrowed Angol's median. With the link it is measured on
    Los Sauces' nights before 09-07 plus its own."""
    daily = _daily(_nights("Los Sauces", date(2026, 8, 24), 14, 5),
                   _nights("Purén y Los Sauces", date(2026, 9, 24), 10, 5),
                   _nights("Alemania 2", date(2026, 8, 24), 40, 20))
    roster = {"Purén y Los Sauces": "Angol", "Alemania 2": "Angol"}
    without = _goal(daily, roster=roster)["Purén y Los Sauces"]["contacts_made"]
    assert without.source == AG.ZONE and without.goal == 140       # Alemania 2's 20/night
    links = {"Purén y Los Sauces": [("Los Sauces", CUTOFF)]}
    got = AG.compute(daily, roster, ["contacts_made"], week_start=MONDAY,
                     stretch=1.0, lineage=links)["Purén y Los Sauces"]["contacts_made"]
    assert got.source == AG.LINEAGE and got.goal == 35             # 5 a night, x7


def test_parent_nights_after_the_transfer_do_not_count():
    """A parent that somehow kept filing after it closed is not history the
    child inherits."""
    daily = _daily(_nights("Los Sauces", CUTOFF, 20, 9),
                   _nights("Purén y Los Sauces", date(2026, 9, 24), 10, 5))
    got = _goal(daily, {"Purén y Los Sauces": [("Los Sauces", CUTOFF)]})
    assert got["Purén y Los Sauces"]["contacts_made"].source != AG.LINEAGE


def test_an_area_with_enough_of_its_own_ignores_its_parent():
    daily = _daily(_nights("Los Sauces", date(2026, 8, 24), 14, 50),
                   _nights("Purén y Los Sauces", date(2026, 9, 7), 28, 5))
    got = _goal(daily, {"Purén y Los Sauces": [("Los Sauces", CUTOFF)]})
    g = got["Purén y Los Sauces"]["contacts_made"]
    assert g.source == AG.OWN and g.goal == 35


def test_a_merge_averages_its_parents_rather_than_adding_them():
    daily = _daily(_nights("Norte", date(2026, 8, 24), 14, 4),
                   _nights("Sur", date(2026, 8, 24), 14, 8))
    got = AG.compute(daily, {"Centro": "Angol"}, ["contacts_made"], week_start=MONDAY,
                     stretch=1.0,
                     lineage={"Centro": [("Norte", CUTOFF), ("Sur", CUTOFF)]})
    g = got["Centro"]["contacts_made"]
    assert g.source == AG.LINEAGE and g.goal == 42                 # (4+8)/2 x 7


def test_the_ki_rec_counts_a_parents_weeks_until_two_of_its_own(monkeypatch):
    weekly = pd.DataFrame([
        {"week_end_date": "2026-08-23", "area": "Los Sauces", "zone": "Angol", "ki_new_people_real": "10"},
        {"week_end_date": "2026-08-30", "area": "Los Sauces", "zone": "Angol", "ki_new_people_real": "10"},
        {"week_end_date": "2026-09-13", "area": "Purén y Los Sauces", "zone": "Angol", "ki_new_people_real": "4"},
    ])
    monkeypatch.setattr(q, "lineage_parents",
                        lambda: {"Purén y Los Sauces": [("Los Sauces", CUTOFF)]})
    framed, inherited = q._with_lineage(weekly, "Purén y Los Sauces")
    assert inherited
    mine = framed[framed["area"] == "Purén y Los Sauces"]
    assert sorted(mine["ki_new_people_real"].astype(int)) == [4, 10, 10]
    # Two weeks of its own and the parent stops counting.
    two = pd.concat([weekly, pd.DataFrame([{"week_end_date": "2026-09-20",
                     "area": "Purén y Los Sauces", "zone": "Angol",
                     "ki_new_people_real": "6"}])], ignore_index=True)
    _, inherited = q._with_lineage(two, "Purén y Los Sauces")
    assert not inherited
