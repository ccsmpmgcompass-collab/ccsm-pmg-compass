"""The cover, the print guide and the run sheet — PLAN step P2.

The property this file exists for is the one nobody can eyeball on a 66-page
document: **the page numbers the cover claims are the pages the sections
actually start on.** The contents and the run sheet are written before the
document has been laid out, so they are built from a measured pass and the
build repeats until a pass confirms the numbers it was handed. Everything else
here — who gets how many copies, which district has no leader — is the run
sheet refusing to guess where MISSION_ORG cannot answer.
"""

import io
import re
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

#: Two zones, three districts, five areas. Norte's D1 has a district leader and
#: D2 has none — the shape CCSM is really in, where twelve of thirteen
#: districts carry one.
ROSTER = pd.DataFrame([
    {"Area_Name": "A1", "Zone": "Norte", "District": "D1", "Is_ZL": "TRUE",
     "Is_DL": "FALSE", "Is_AP": "FALSE"},
    {"Area_Name": "A2", "Zone": "Norte", "District": "D1", "Is_ZL": "FALSE",
     "Is_DL": "TRUE", "Is_AP": "FALSE"},
    {"Area_Name": "A3", "Zone": "Norte", "District": "D2", "Is_ZL": "FALSE",
     "Is_DL": "FALSE", "Is_AP": "FALSE"},
    {"Area_Name": "B1", "Zone": "Sur", "District": "D3", "Is_ZL": "TRUE",
     "Is_DL": "TRUE", "Is_AP": "TRUE"},
    {"Area_Name": "B2", "Zone": "Sur", "District": "D3", "Is_ZL": "FALSE",
     "Is_DL": "FALSE", "Is_AP": "FALSE"},
])

NEW = "ki_new_people_real"
WEEKLY_KI = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", NEW: 10},
    {"_week": "2026-09-13", "_area": "B1", NEW: 30},
    {"_week": "2026-09-20", "_area": "A1", NEW: 12},
])


def _ki_goals(week, areas=None):
    return {NEW: 60.0}, {NEW: 2}, date(2026, 9, 6), 2


def _models():
    data = M.ReportData(
        roster=ROSTER, weekly_ki=WEEKLY_KI, cycles=CYCLES, ki_keys=(NEW,),
        labels={NEW: "Nuevas Personas"}, mission_name="Misión de Prueba",
        today=TODAY, anchor=W2, ki_goals_fn=_ki_goals)
    return M.build_all(data=data)


@pytest.fixture(scope="module")
def models():
    return _models()


@pytest.fixture(scope="module")
def pdf(models):
    return PK.build_packet(models, ROSTER)


def _pages(pdf_bytes):
    return [(p.extract_text() or "")
            for p in PdfReader(io.BytesIO(pdf_bytes)).pages]


def _imports_streamlit(module: str) -> bool:
    """Whether importing `module` in a FRESH interpreter pulls in Streamlit.

    A subprocess, not `sys.modules` surgery. Deleting streamlit from this
    process and reloading proved the point and then broke 122 later tests in
    the same session — every one that had monkeypatched something inside the
    module object it no longer shared. A cold interpreter is both isolated and
    a stronger claim: it tests the import GRAPH rather than what this session
    happens to have loaded already.
    """
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    code = (f"import {module}, sys; "
            "sys.exit(1 if 'streamlit' in sys.modules else 0)")
    done = subprocess.run([sys.executable, "-c", code], cwd=str(root),
                          capture_output=True, text=True)
    assert done.returncode in (0, 1), done.stderr
    return done.returncode == 1


# ── Ranges ────────────────────────────────────────────────────────────────────

def test_a_sections_last_page_is_the_page_before_the_next_one_begins():
    pag = PK.Pagination(starts={"sec:a": 3, "sec:b": 8, "sec:c": 20}, total=25)
    sections = [PK.Section("sec:a", "A", ""), PK.Section("sec:b", "B", ""),
                PK.Section("sec:c", "C", "")]
    assert [(s.first_page, s.last_page) for s in pag.resolve(sections)] == [
        (3, 7), (8, 19), (20, 25)]


def test_a_section_that_never_started_is_left_out_of_the_contents():
    """Decision 32 lets the Tableau block be absent from a packet. A contents
    line pointing at nothing is worse than a shorter contents."""
    pag = PK.Pagination(starts={"sec:a": 3}, total=6)
    resolved = pag.resolve([PK.Section("sec:a", "A", ""),
                            PK.Section("sec:gone", "B", "")])
    assert [s.key for s in resolved] == ["sec:a"]


def test_a_one_page_section_prints_one_number_and_not_a_range():
    pag = PK.Pagination(starts={"sec:a": 8, "sec:b": 9}, total=9)
    assert [s.page_label for s in pag.resolve(
        [PK.Section("sec:a", "A", ""), PK.Section("sec:b", "B", "")])] == \
        ["8", "9"]


def test_an_unresolved_section_says_so_rather_than_claiming_page_one():
    assert PK.Section("sec:a", "A", "").page_label == "—"
    assert PK.Section("sec:a", "A", "").page_count == 0


# ── The two passes agree ──────────────────────────────────────────────────────

def test_the_contents_names_the_pages_the_sections_really_start_on(models, pdf):
    """The whole point of building twice. Printing the first pass's numbers can
    lengthen the guide by a row and move everything after it, so the build
    repeats until a pass confirms what it was given — and this reads the
    finished document to check that it did."""
    pages = _pages(pdf)
    cover = pages[0]
    claimed = dict(re.findall(r"(La misión|Nota de datos)\s+(\d+)", cover))
    assert claimed, cover
    # The mission's own page carries its name as a title; the data note carries
    # its heading. Both must be on the page the cover sent the reader to.
    assert "Misión de Prueba" in pages[int(claimed["La misión"]) - 1]
    assert "NOTA DE DATOS" in pages[int(claimed["Nota de datos"]) - 1].upper()


def test_the_run_sheet_sends_a_zone_leader_to_their_own_zones_pages(models, pdf):
    """Their row reads "the mission's pages + their zone's", and both halves
    have to land on the pages that really carry them."""
    pages = _pages(pdf)
    guide = pages[1]
    row = re.search(r"Líderes de zona · Norte\s+(\d+)[–\d]*\s*\+\s*(\d+)", guide)
    assert row, guide
    mission_page, zone_page = int(row.group(1)), int(row.group(2))
    assert "Misión de Prueba" in pages[mission_page - 1]
    assert "Norte" in pages[zone_page - 1]


def test_the_last_page_number_the_guide_promises_is_the_last_page(pdf):
    pages = _pages(pdf)
    total = len(pages)
    assert f"1–{total}" in pages[1]
    assert f"Página {total}" in pages[-1]


def test_the_build_settles_rather_than_running_to_the_ceiling(models, monkeypatch):
    """Two passes is the usual answer. If the packet ever needs the third, the
    document is oscillating and that is worth knowing about."""
    lengths = []
    original = PK._render

    def counting(flow):
        pdf, pages = original(flow)
        lengths.append(pages)
        return pdf, pages

    monkeypatch.setattr(PK, "_render", counting)
    PK.build_packet(models, ROSTER)
    assert len(lengths) <= 2
    assert len(set(lengths)) == 1          # every pass the same length


# ── Who gets paper ────────────────────────────────────────────────────────────

def test_the_copy_counts_come_off_the_roster_and_not_off_the_org_chart():
    lead = PK.leadership(ROSTER)
    assert lead.zone_leaders == {"zone:Norte": 1, "zone:Sur": 1}
    assert lead.district_leaders == {"district:Norte/D1": 1,
                                     "district:Norte/D2": 0,
                                     "district:Sur/D3": 1}
    assert lead.assistants == 1


def test_a_district_with_no_leader_asks_for_no_copies_and_says_why():
    """Printing one copy for a leader the roster does not know about is how a
    stack of paper ends up on a table with nobody to hand it to."""
    lead = PK.leadership(ROSTER)
    assert lead.districts_without_a_leader == ["district:Norte/D2"]
    sections = [PK.Section(PK.MISSION, "La misión", "", first_page=3,
                           last_page=3)]
    units = [(S.district_scopes(ROSTER)[1], (9, 9))]     # Norte / D2
    rows = PK.hand_outs(sections, units, ROSTER)
    d2 = next(r for r in rows if "D2" in r.who)
    assert d2.copies == 0
    assert "MISSION_ORG" in d2.note


def test_that_note_reaches_the_printed_guide(pdf):
    guide = _pages(pdf)[1]
    assert "Sin líder de distrito en MISSION_ORG" in guide
    assert "2 de 3 distritos" in guide


def test_the_president_and_the_assistants_get_the_whole_packet():
    sections = [PK.Section(PK.MISSION, "La misión", "", first_page=3,
                           last_page=9)]
    rows = PK.hand_outs(sections, [], ROSTER)
    assert rows[0].who.startswith("Presidente")
    assert rows[0].pages == "1–9" and rows[0].copies == 1
    assert rows[1].who == "Asistentes" and rows[1].copies == 1


def test_paper_is_counted_double_sided_and_per_copy():
    rows = [PK.HandOut("uno", "1–9", 2, "", 9),      # 5 sheets each
            PK.HandOut("dos", "1–4", 3, "", 4)]      # 2 sheets each
    assert PK.sheets(rows) == 5 * 2 + 2 * 3


def test_a_row_nobody_takes_costs_no_paper():
    assert PK.sheets([PK.HandOut("nadie", "8", 0, "", 1)]) == 0


# ── The pages themselves ──────────────────────────────────────────────────────

def test_the_cover_carries_no_running_head_and_no_page_number(pdf):
    """Nothing sets the furniture before it, so there is nothing to draw."""
    cover = _pages(pdf)[0]
    assert "PMG Compass ·" not in cover
    assert "Página 1" not in cover
    assert "Paquete del Consejo" in cover


def test_every_page_after_the_cover_is_numbered(pdf):
    pages = _pages(pdf)
    for i, page in enumerate(pages[1:], start=2):
        assert f"Página {i}" in page, f"page {i} has no footer"


def test_the_cover_states_the_period_the_progress_and_the_compliance(models, pdf):
    cover = _pages(pdf)[0]
    mission = models[0]
    assert mission.period.window_label in cover
    assert mission.period.progress_label in cover
    assert mission.compliance_label in cover


def test_the_guide_tells_the_printer_not_to_scale_the_page(pdf):
    """Decision 25's acceptance in one sentence: "Fit to page" clips the
    footers, and the person at the printer is not the person who built it."""
    guide = _pages(pdf)[1]
    assert "Tamaño real" in guide and "Ajustar a la página" in guide


def test_every_string_the_front_matter_prints_survives_the_encoding(models):
    """`text()` folds or drops what the base-14 fonts cannot reach. If it
    changes anything here, something is about to print in ZapfDingbats."""
    mission = models[0]
    sections = PK.sections_for(models)
    flows = PK.front_matter(mission, sections, [], ROSTER, total_pages=20)
    seen = 0
    for flow in flows:
        for line in _strings(flow):
            seen += 1
            assert PP.is_printable(line), repr(line)
    assert seen > 30


def _strings(flow):
    """Every string a flowable will print, however deeply it is nested."""
    from reportlab.platypus import Paragraph, Table
    if isinstance(flow, Paragraph):
        yield re.sub(r"<[^>]+>", "", flow.text)
    elif isinstance(flow, Table):
        for row in flow._cellvalues:
            for cell in row:
                yield from _strings(cell)
    elif isinstance(flow, PP.TrackedLabel):
        yield flow.label
    elif isinstance(flow, PP.SectionHead):
        yield flow.label
        if flow.note:
            yield flow.note


# ── Purity ────────────────────────────────────────────────────────────────────

def test_the_whole_packet_builds_without_streamlit():
    """Decision 30's boundary, checked on the import graph rather than on what
    this session happens to have loaded."""
    assert not _imports_streamlit("app.reports.packet")
