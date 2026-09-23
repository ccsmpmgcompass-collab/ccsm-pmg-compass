"""The zone and district pages — PLAN step P4.

The district page exists for one thing the audit named and nothing in Compass
did before: **a 73% means nothing until you can see the zone at 78 and the
mission at 76.** `ladder_rows` is that comparison, and since Phase V it reads
`ReportModel.ladder` — the model does the arithmetic once so the screen and
the printed page cannot disagree about the sign of a gap (decision 30).

The rest is about a ranked table refusing to overstate what it knows: a unit
nobody filed a form for keeps its place at the end of the list and loses its
rank number, because it is not the ninth-best area — it is an area nobody can
rank.
"""

import io
import re
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest
from pypdf import PdfReader

from app.reports import model as M
from app.reports import packet as PK
from app.reports import packet_parts as PP
from app.reports import scope as S

TODAY = date(2026, 9, 21)
W2 = date(2026, 9, 20)

CYCLES = [
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
     "weeks": 6, "status": "Actual"},
]

#: Norte holds two districts; D2's single area files nothing, which is what
#: puts an unrankable row in front of every table below.
ROSTER = pd.DataFrame([
    {"Area_Name": "A1", "Zone": "Norte", "District": "D1"},
    {"Area_Name": "A2", "Zone": "Norte", "District": "D1"},
    {"Area_Name": "A3", "Zone": "Norte", "District": "D2"},
    {"Area_Name": "B1", "Zone": "Sur", "District": "D3"},
])

NEW = "ki_new_people_real"
SACR = "ki_friends_sacrament_real"
BAUT = "ki_baptized_confirmed_real"

WEEKLY_KI = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", NEW: 30, SACR: 6, BAUT: 1},
    {"_week": "2026-09-13", "_area": "A2", NEW: 10, SACR: 1, BAUT: 0},
    {"_week": "2026-09-13", "_area": "B1", NEW: 20, SACR: 4, BAUT: 0},
    {"_week": "2026-09-20", "_area": "A1", NEW: 25, SACR: 5, BAUT: 0},
])

DAILY = pd.DataFrame(
    [{"_day": d, "_area": a, "contacts_attempted": 30}
     for d in ("2026-09-14", "2026-09-15") for a in ("A1", "B1")]
)


def _ki_goals(week, areas=None):
    return ({NEW: 120.0, SACR: 24.0, BAUT: 4.0},
            {NEW: 4, SACR: 4, BAUT: 4}, date(2026, 9, 6), 4)


def _data(**over) -> M.ReportData:
    kw = dict(roster=ROSTER, weekly_ki=WEEKLY_KI, daily_log=DAILY,
              cycles=CYCLES, ki_keys=(NEW, SACR, BAUT),
              nightly_keys=("contacts_attempted",),
              nightly_goals={"contacts_attempted": 150.0},
              labels={NEW: "Nuevas Personas", SACR: "Amigos en Sacramental",
                      BAUT: "Bautizados y Confirmados",
                      "contacts_attempted": "Intentos de Contacto"},
              mission_name="Misión de Prueba", today=TODAY, anchor=W2,
              ki_goals_fn=_ki_goals)
    kw.update(over)
    return M.ReportData(**kw)


@pytest.fixture(scope="module")
def models():
    return M.build_all(data=_data())


@pytest.fixture(scope="module")
def peers(models):
    return {m.scope.key: m for m in models}


@pytest.fixture(scope="module")
def zone(peers):
    return peers["zone:Norte"]


@pytest.fixture(scope="module")
def district(peers):
    return peers["district:Norte/D1"]


@pytest.fixture(scope="module")
def pdf(models):
    return PK.build_packet(models, ROSTER, _data().nightly_goals)


def _pages(pdf_bytes):
    return [(p.extract_text() or "")
            for p in PdfReader(io.BytesIO(pdf_bytes)).pages]


def _strings(drawing):
    from reportlab.graphics.shapes import Group, String
    for shape in getattr(drawing, "contents", []):
        if isinstance(shape, Group):
            yield from _strings(shape)
        elif isinstance(shape, String):
            yield shape.text


# ── The district against its zone and the mission ─────────────────────────────

def test_a_district_is_printed_beside_its_zone_and_the_mission(district):
    """The audit's own sentence: a district leader has no way to know whether
    73% is good until they can see the zone at 78 and the mission at 76."""
    spec = PP.RankedSpec(width=520.0, cells=("Nuevas", "Sacr.", "Baut."))
    rows = PK.ladder_rows(district, spec)
    said = " ".join(t for row in rows for t in _strings(row))
    assert "D1" in said and "Norte" in said and "Misión de Prueba" in said
    assert "este distrito" in said and "su zona" in said and "la misión" in said


def test_a_zone_is_printed_beside_the_mission(zone):
    """Zackary, 2026-09-23 — the zone pages carry the same comparison the
    district pages always had, one rung up."""
    spec = PP.RankedSpec(width=520.0, cells=("Nuevas", "Sacr.", "Baut."))
    said = " ".join(t for row in PK.ladder_rows(zone, spec)
                    for t in _strings(row))
    assert "esta zona" in said and "la misión" in said
    assert "su zona" not in said          # nothing between a zone and the top


def test_the_ladder_is_read_off_the_model(district):
    """`ReportModel.ladder` is the contract; the page draws it and computes
    nothing (decision 30)."""
    assert [r.role for r in district.ladder] == [
        "este distrito", "su zona", "la misión"]


def test_a_unit_at_the_top_prints_no_comparison(peers):
    """The mission has no ladder, so the section simply is not there."""
    assert PK.ladder_rows(peers["mission"], PP.RankedSpec(width=520.0)) == []
    assert PK.ladder_block(peers["mission"]) == []


def test_every_rung_of_the_ladder_is_measured_the_same_way(district, peers):
    """Each row is that unit's mean Key Indicator attainment per ACTIVE area.
    Three rows on three different bases would be three numbers that cannot be
    compared, printed in a table whose whole purpose is comparison."""
    for unit in (district, peers["zone:Norte"], peers["mission"]):
        by_hand = [r.attainment_per_active_area for r in unit.key_indicators
                   if r.attainment_per_active_area is not None
                   and not r.grade.flag]
        assert unit.mean_attainment == pytest.approx(
            sum(by_hand) / len(by_hand))


def test_a_units_rung_and_its_row_in_its_parents_table_agree(district, peers):
    """One rule for the headline, in the model. A district reading 61 on its
    own page and 58 in its zone's table would be the same unit measured two
    ways, three pages apart."""
    row = next(c for c in peers["zone:Norte"].children
               if c.scope.key == district.scope.key)
    assert row.mean_attainment == pytest.approx(district.mean_attainment)


def test_a_flagged_goal_is_left_out_of_the_mean(district):
    """It would drag the unit's headline for the goal's sake, not the work's."""
    rows = list(district.key_indicators)
    from app.reports import grading as G
    rows[0] = replace(rows[0], grade=G.Grade(pct=2.0, flag=G.GOAL_TOO_HIGH))
    with_flag = replace(district, key_indicators=tuple(rows)).mean_attainment
    assert with_flag == pytest.approx(replace(
        district, key_indicators=tuple(rows[1:])).mean_attainment)


# ── A ranked table and what it refuses to claim ───────────────────────────────

def test_a_unit_nobody_reported_keeps_its_place_and_loses_its_number(zone):
    """It is not the third-best district; it is a district nobody can rank."""
    spec = PP.RankedSpec(width=520.0, cells=PK._child_cells(zone))
    rows = PK.ranked_unit_rows(zone.children, zone, spec)
    silent = [c for c in zone.children if c.mean_attainment is None]
    assert silent, "the fixture's D2 should have reported nothing"
    said = [list(_strings(row)) for row in rows[1:]]
    for child, texts in zip(zone.children, said):
        if child.mean_attainment is None:
            assert str(child.rank) not in texts
            assert any("sin informes" in t for t in texts)
        else:
            assert str(child.rank) in texts


def test_a_row_does_not_repeat_the_unit_its_page_is_already_about(zone):
    """On Norte's own page an area is "D1", not "Norte · D1" — the zone's name
    is in the running head and in the title above it."""
    spec = PP.RankedSpec(width=520.0, cells=PK._child_cells(zone))
    for child in zone.areas_ranked:
        assert zone.scope.name not in PK._child_sub(child, zone)


def test_the_areas_table_and_the_children_table_are_the_same_row(zone):
    """One builder for both, so a zone's districts and its areas cannot drift
    into two different-looking tables on the same page."""
    spec = PP.RankedSpec(width=520.0, cells=PK._child_cells(zone))
    a = PK.child_rows(zone, spec)[0]
    b = PK.ranked_unit_rows(zone.children, zone, spec)[0]
    assert list(_strings(a)) == list(_strings(b))


# ── Rates and scores land where they belong ───────────────────────────────────

def test_the_conversion_rates_stop_below_zone_level(district, zone):
    """Decision 13. A close rate over one companionship's three lessons is a
    ratio of two small integers wearing a percentage sign."""
    assert district.rates == ()
    assert PK.rate_lines(district) == []


def test_the_scores_print_ungraded(models):
    """They are the agent's own 0-100 composites, not a percentage of a goal,
    and the 90/60 bands would claim they were."""
    scores = pd.DataFrame([
        {"_week": "2026-09-13", "_area": "A1", "Effort_Score": 59.4,
         "Skill_Score": 69.7, "KI_Score": 37.6, "Effectiveness_Score": 55.4}])
    scored = M.build_all(data=_data(scores=scores))[0]
    tiles = PK.score_tiles(scored)
    assert [t.value for t in tiles] == ["59,4", "69,7", "37,6", "55,4"]
    assert all(t.status is None for t in tiles)


def test_a_unit_the_agent_never_scored_gets_no_score_band(district):
    assert PK.score_tiles(district) == []


# ── The pages themselves ──────────────────────────────────────────────────────

def _body_pages(pdf_bytes):
    """Everything after the cover and the print guide.

    The guide's run sheet says "Líderes de zona · Norte" and "Líderes de
    distrito · D1", which a plain search for a running head finds first and
    reports as the unit's own page.
    """
    return _pages(pdf_bytes)[2:]


def test_a_zone_opens_the_same_way_the_mission_does(pdf):
    """The reader is the same reader one rung down, and a leader who has read
    one unit's pages has read them all."""
    pages = _body_pages(pdf)
    first = next(p for p in pages if "ZONA · NORTE" in p.upper())
    assert "DÓNDE ESTAMOS" in first.upper()


def test_a_zone_lists_its_districts_and_every_one_of_its_areas(pdf):
    page = next(p for p in _body_pages(pdf)
                if "DISTRITOS" in p.upper() and "ÁREAS" in p.upper())
    for area in ("A1", "A2", "A3"):
        assert area in page
    assert "LAS 3 ÁREAS" in page.upper()


def test_a_district_page_carries_the_three_way_comparison(pdf):
    page = next(p for p in _body_pages(pdf) if "DISTRITO · D1" in p.upper())
    assert "CONTRA SU ZONA Y LA MISIÓN" in page.upper()


def test_the_contents_says_how_many_pages_a_unit_really_took(pdf):
    """§3.2 planned one page per district; they print several, because
    decision 10 gives every unit all seven Key Indicators and decision 17 all
    twenty-two nightly metrics. The contents describes the document that was
    built, not the one that was sketched."""
    cover = _pages(pdf)[0]
    row = re.search(r"Cada distrito . [0-9]+, ([0-9]+) páginas cada uno",
                    cover)
    assert row, cover
    assert int(row.group(1)) > 1


def test_every_unit_page_names_its_unit_in_the_running_head(pdf):
    """The furniture is drawn on onPageEnd, so it extracts LAST — the head and
    the footer are the tail of the page's text, not its first line."""
    for page in _body_pages(pdf):
        tail = " ".join(page.strip().splitlines()[-3:]).upper()
        assert ("MISIÓN DE PRUEBA" in tail or "ZONA ·" in tail
                or "DISTRITO ·" in tail or "ÁREA ·" in tail), tail
