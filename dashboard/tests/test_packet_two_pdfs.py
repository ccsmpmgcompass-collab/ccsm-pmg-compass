"""The council packet and the annex — PLAN-2026-10-13 step 4.1 (D3).

The council packet is what the council reads together; the annex is the
districts and the areas, handed out. The run sheet in the packet names each
district leader's annex page; the annex's page 1 repeats it.
"""

import io
import re

from pypdf import PdfReader

from app.reports import packet as PK
from app.reports import packet_annex as PA
from app.reports import scope as S
from tests.test_packet_front_matter import ROSTER, _models


def _pages(pdf):
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages]


def test_the_two_parts_hold_different_sections():
    council = [s.key for s in PK.sections_for([])]
    annex = [s.key for s in PK.sections_for([], part=PK.ANNEX)]
    assert PK.DISTRICTS not in council and PK.AREAS not in council
    assert council[-3:] == [PK.DATA_NOTE, PK.HOW_TO_READ, PK.PRINT_GUIDE]
    assert annex == [PK.ANNEX_FRONT, PK.DISTRICTS, PK.AREAS]


def test_the_annex_starts_with_what_to_hand_each_district_leader():
    models = _models()
    pdf, layout = PA.build_annex_packet(models, ROSTER)
    pages = _pages(pdf)
    assert layout.total == len(pages)
    first = pages[0]
    assert "Anexo del Consejo" in first and "QUÉ ENTREGAR" in first.upper()
    districts = [m for m in models if m.scope.level == S.DISTRICT]
    assert [s.key for s, _ in layout.units] == [m.scope.key for m in districts]
    for scope, (a, b) in layout.units:
        assert f"DISTRITO · {scope.name}".upper() in pages[a - 1].upper()
        assert re.search(rf"{scope.name}\s+{a}\s", first), first


def test_the_council_guide_names_the_annex_pages():
    models = _models()
    _, layout = PA.build_annex_packet(models, ROSTER)
    pdf = PK.build_packet(models, ROSTER, annex=layout)
    pages = _pages(pdf)
    guide = pages[-1]
    total = len(pages)
    assert f"1–{total} + anexo 1–{layout.total}" in guide
    for scope, (a, _) in layout.units:
        assert re.search(rf"Líderes de distrito · {scope.name}\s+anexo {a}\s",
                         guide), guide
    assert "Anexo: cada distrito y cada área" in pages[0]


def test_the_training_leaders_come_off_the_roster():
    roster = ROSTER.assign(Is_STL=["TRUE", "", "TRUE", "", ""])
    assert PK.leadership(roster).training_leaders == 2
    sections = [PK.Section(PK.ZONES, "Zonas", "", first_page=3, last_page=9),
                PK.Section(PK.PRINT_GUIDE, "Guía", "", first_page=12,
                           last_page=12)]
    rows = {r.who: r for r in PK.hand_outs(sections, [], roster,
                                           annex_pages=20)}
    stl = rows["Hermanas líderes de capacitación"]
    assert (stl.pages, stl.copies) == ("1–9", 2)
    assert rows["Líderes de zona"].pages == "1–9"
    assert rows["Presidente de misión"].pages == "1–12 + anexo 1–20"
    none = {r.who: r for r in PK.hand_outs(sections, [], ROSTER)}
    assert none["Hermanas líderes de capacitación"].copies == 0


def test_the_files_say_which_part_they_are():
    from datetime import date
    day = date(2026, 11, 2)
    assert PK.filename_for("last_month", day) == \
        "paquete-consejo-last_month-2026-11-02.pdf"
    assert PK.filename_for("last_month", day, PK.ANNEX) == \
        "anexo-consejo-last_month-2026-11-02.pdf"


def test_the_area_builders_still_answer_under_their_old_names():
    """Step 4.1 moved them to `packet_annex` (risk 5); `packet` re-exports."""
    assert PK.area_block is PA.area_block
    assert PK.AREAS_PER_PAGE == PA.AREAS_PER_PAGE


# ── Step 4.4 (C13): smaller fixes ─────────────────────────────────────────────

def test_zone_and_district_pages_name_their_leaders():
    from tests.test_report_model_ki import _data, ROSTER as KI_ROSTER
    from app.reports import model as M
    roster = KI_ROSTER.assign(Is_ZL=["TRUE", "", "", "", ""],
                              Is_DL=["", "TRUE", "", "", ""])
    built = M.build_all(data=_data(roster=roster))
    norte = next(m for m in built if m.scope.level == S.ZONE
                 and m.scope.name == "Norte")
    assert norte.leaders == ("Elder Uno", "Elder Dos")
    head = " ".join(p.getPlainText() for p in PK._heading(norte))
    assert "Líderes de zona: Elder Uno y Elder Dos" in head
    d3 = next(m for m in built if m.scope.name == "D3")
    assert "sin líderes de distrito en el organigrama" in " ".join(
        p.getPlainText() for p in PK._heading(d3))


def test_an_area_s_small_goal_prints_a_count_not_a_percentage():
    from dataclasses import replace
    from tests.test_report_model_ki import _data
    from app.reports import model as M
    area = next(m for m in M.build_all(data=_data())
                if m.scope.level == S.AREA and m.scope.name == "A1")
    row = area.key_indicators[0]
    small = replace(area, key_indicators=(replace(
        row, lead_goal=1.0, actual=6.0,
        grade=replace(row.grade, pct=600.0, status="good")),))
    line = PK.ki_lines(small, comparable=False)[0]
    assert "600" not in line.verdict
    assert line.verdict == "al ritmo · 6 de 1,0"
