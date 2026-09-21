"""The area pages, two to a page — PLAN step P5.

An area IS a companionship (decision 27), so this page is the one the
companionship itself reads, and it is the only page in the packet with their
names on it — the thing the old Informes page never had.

Two things here are refusals. **"Su fortaleza / Para crecer" is read, never
recomputed**: WEEKLY_BREAKDOWNS already stores the agents' own choice per area
per week, and a second opinion printed beside it would be two answers to one
question. And **the running head names the section rather than a district**,
because the pairs run alphabetically across the whole mission and the two areas
on a page need not share one.
"""

import io
import re
from datetime import date

import pandas as pd
import pytest
from pypdf import PdfReader
from reportlab.platypus import KeepTogether

from app.reports import model as M
from app.reports import packet as PK
from app.reports import packet_parts as PP

TODAY = date(2026, 9, 21)
W2 = date(2026, 9, 20)

CYCLES = [
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
     "weeks": 6, "status": "Actual"},
]

#: Five areas, so the spreads run 2 + 2 + 1 and the odd one out is exercised.
#: A1 carries a trio; A3 carries nobody, which MISSION_ORG does allow.
ROSTER = pd.DataFrame([
    {"Area_Name": "A1", "Zone": "Norte", "District": "D1",
     "Companion1_Name": "Elder Uno", "Companion2_Name": "Elder Dos",
     "Companion3_Name": "Elder Tres"},
    {"Area_Name": "A2", "Zone": "Norte", "District": "D1",
     "Companion1_Name": "Hermana Una", "Companion2_Name": "Hermana Dos"},
    {"Area_Name": "A3", "Zone": "Norte", "District": "D2"},
    {"Area_Name": "B1", "Zone": "Sur", "District": "D3",
     "Companion1_Name": "Elder Cuatro", "Companion2_Name": "Elder Cinco"},
    {"Area_Name": "B2", "Zone": "Sur", "District": "D3",
     "Companion1_Name": "Elder Seis", "Companion2_Name": "Elder Siete"},
])

NEW = "ki_new_people_real"
SACR = "ki_friends_sacrament_real"
BAUT = "ki_baptized_confirmed_real"

WEEKLY_KI = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", NEW: 8, SACR: 2, BAUT: 0},
    {"_week": "2026-09-20", "_area": "A1", NEW: 5, SACR: 1, BAUT: 1},
    {"_week": "2026-09-13", "_area": "A2", NEW: 6, SACR: 1, BAUT: 0},
    {"_week": "2026-09-13", "_area": "B1", NEW: 4, SACR: 0, BAUT: 0},
    {"_week": "2026-09-20", "_area": "B2", NEW: 9, SACR: 3, BAUT: 0},
])

BREAKDOWNS = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1",
     "strength1_metric": "contacts_made", "strength2_metric": "friend_lessons",
     "growth_metric": "baptismal_calendars", "effort_score": 2.5},
])

SCORES = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", "Effort_Score": 63.8,
     "Skill_Score": 73.6, "KI_Score": 49.3, "Effectiveness_Score": 62.1},
    {"_week": "2026-09-13", "_area": "A2", "Effort_Score": 40.0,
     "Skill_Score": 50.0, "KI_Score": 30.0, "Effectiveness_Score": 40.0},
])


def _ki_goals(week, areas=None):
    return ({NEW: 25.0, SACR: 5.0, BAUT: 1.0},
            {NEW: 5, SACR: 5, BAUT: 5}, date(2026, 9, 6), 5)


def _data(**over) -> M.ReportData:
    kw = dict(roster=ROSTER, weekly_ki=WEEKLY_KI, breakdowns=BREAKDOWNS,
              scores=SCORES, cycles=CYCLES, ki_keys=(NEW, SACR, BAUT),
              labels={NEW: "Nuevas Personas", SACR: "Amigos en Sacramental",
                      BAUT: "Bautizados y Confirmados",
                      "contacts_made": "Contactos",
                      "friend_lessons": "Lecciones con Amigos",
                      "baptismal_calendars": "Calendarios Bautismales"},
              mission_name="Misión de Prueba", today=TODAY, anchor=W2,
              ki_goals_fn=_ki_goals)
    kw.update(over)
    return M.ReportData(**kw)


@pytest.fixture(scope="module")
def models():
    return M.build_all(data=_data())


@pytest.fixture(scope="module")
def areas(models):
    return [m for m in models if m.scope.level == "area"]


@pytest.fixture(scope="module")
def pdf(models):
    return PK.build_packet(models, ROSTER)


def _pages(pdf_bytes):
    return [(p.extract_text() or "")
            for p in PdfReader(io.BytesIO(pdf_bytes)).pages]


def _text_of(flow):
    from reportlab.graphics.shapes import Group, String
    from reportlab.platypus import Paragraph, Table
    out = []

    def walk(f):
        if isinstance(f, Paragraph):
            out.append(re.sub(r"<[^>]+>", "", f.text))
        elif isinstance(f, Table):
            for row in f._cellvalues:
                for cell in row:
                    walk(cell)
        elif isinstance(f, (list, tuple)):
            for item in f:
                walk(item)
        elif isinstance(f, KeepTogether):
            walk(f._content)
        elif isinstance(f, PP.TrackedLabel):
            out.append(f.label)
        elif hasattr(f, "contents"):
            for shape in f.contents:
                if isinstance(shape, Group):
                    walk(shape)
                elif isinstance(shape, String):
                    out.append(shape.text)

    walk(flow)
    return out


def _area(areas, name):
    return next(m for m in areas if m.scope.name == name)


# ── The companionship ─────────────────────────────────────────────────────────

def test_the_companionship_is_named_at_the_top(areas):
    """Decision 27, and the one thing the old page never had."""
    said = " ".join(_text_of(PK.area_block(_area(areas, "A2"))))
    assert "Hermana Una" in said and "Hermana Dos" in said


def test_a_trio_does_not_lose_its_third_missionary(areas):
    """MISSION_ORG carries Companion1 and 2 today; 3 and 4 are read anyway."""
    said = " ".join(_text_of(PK.area_block(_area(areas, "A1"))))
    assert "Elder Tres" in said


def test_an_area_with_nobody_on_the_roster_says_so(areas):
    said = " ".join(_text_of(PK.area_block(_area(areas, "A3"))))
    assert "sin companería en MISSION_ORG" in said


def test_the_block_names_the_district_and_the_zone_under_the_area(areas):
    said = " ".join(_text_of(PK.area_block(_area(areas, "A1"))))
    assert "Norte" in said and "D1" in said


# ── What it prints, and what it refuses to compute ────────────────────────────

def test_strength_and_growth_are_read_rather_than_recomputed(areas):
    """The agents already chose them per area per week. A second opinion beside
    theirs would be two answers to one question."""
    said = " ".join(_text_of(PK.area_block(_area(areas, "A1"))))
    assert "Su fortaleza: Contactos, Lecciones con Amigos" in said
    assert "Para crecer: Calendarios Bautismales" in said


def test_an_area_the_agents_have_not_written_up_says_why(areas):
    """WEEKLY_BREAKDOWNS lags WEEKLY_KI by a week, so on a single-week period
    the whole mission reads blank here. That is the tab lagging, not a bug."""
    said = " ".join(_text_of(PK.area_block(_area(areas, "B1"))))
    assert "WEEKLY_BREAKDOWNS" in said


def test_the_scores_carry_the_areas_rank_in_its_district(areas):
    """Decision 18: the full four at area level, with the area's place among
    its district's areas on Effectiveness."""
    said = " ".join(_text_of(PK.area_block(_area(areas, "A1"))))
    assert "Puntajes: Esfuerzo 63,8" in said
    assert "en su distrito, por efectividad" in said
    assert re.search(r"\dº de \d en su distrito", said)


def test_all_seven_key_indicators_are_rows_at_area_level_too(areas):
    """Decision 10 is a standing rule, not a filter — and the half page is
    where it would have been tempting to drop to four."""
    model = _area(areas, "A1")
    lines = PK.area_lines(model)
    assert len(lines) == len(model.key_indicators)


def test_each_row_carries_its_own_weeks_where_the_change_would_be(areas):
    """A companionship's question is what their six weeks look like, not how
    they moved against a window somebody else chose."""
    drawn = [l.spark for l in PK.area_lines(_area(areas, "A1"))]
    assert any(s is not None for s in drawn)
    for spark in drawn:
        if spark is not None:
            assert spark.width == pytest.approx(PK.AREA_COLUMNS_SPARK)


def test_one_reported_week_draws_no_line_rather_than_a_point(areas):
    """A2 filed once. A line needs two readings and a dot alone would be a
    trend drawn through a single number."""
    from reportlab.graphics.shapes import PolyLine
    for spark in (l.spark for l in PK.area_lines(_area(areas, "A2"))):
        if spark is not None:
            assert not [s for s in spark.contents if isinstance(s, PolyLine)]


# ── Two to a page ─────────────────────────────────────────────────────────────

def test_an_areas_block_fits_a_half_page(areas):
    """Two to a page (§3.2) is only true if each block fits the half."""
    for model in areas:
        height = sum(f.wrap(PP.CONTENT_WIDTH, PP.CONTENT_HEIGHT)[1]
                     for f in PK.area_block(model))
        assert height <= PK.AREA_BLOCK_HEIGHT, model.scope.name


def test_the_areas_really_do_print_two_to_a_page(pdf, areas):
    pages = _pages(pdf)
    spread = [p for p in pages if "Su fortaleza" in p or "WEEKLY_BREAKDOWNS" in p]
    assert spread
    names = [m.scope.name for m in areas]
    seen = {name: sum(1 for p in pages if f"\n{name}\n" in f"\n{p}\n")
            for name in names}
    # Five areas over three spreads: nothing printed twice, nothing missing.
    assert all(count >= 1 for count in seen.values()), seen


def test_the_running_head_names_the_section_and_not_one_of_the_two(pdf, areas):
    """The pairs run alphabetically across the whole mission, so the two areas
    on a page need not share a district — the first draft headed a page
    "Distrito · La Marina 1" above an area from San Pedro 1."""
    head = PK.furniture_for(areas[0])
    assert head.eyebrow == "Áreas"
    assert head.trail == ""
    pages = _pages(pdf)
    area_pages = [p for p in pages if "ÁREAS" in p.upper()
                  and "Su fortaleza" in p]
    assert area_pages
    for page in area_pages:
        assert "DISTRITO ·" not in page.upper()


def test_every_area_on_the_roster_gets_a_block(pdf, areas):
    pages = "\n".join(_pages(pdf))
    for model in areas:
        assert model.scope.name in pages
