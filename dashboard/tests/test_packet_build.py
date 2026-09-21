"""Assembly, the data note and the button — PLAN step P6.

This file is the phase's acceptance: **a 60+ page PDF opens clean, every footer
numbered, Letter, no clipped furniture at "Actual size".** Everything below is
one of those four, checked on a document built end to end rather than on a
block measured in isolation.

The data note is the other half. A reader who wants to argue with a number
should be able to find out what it is made of without asking anybody — which
is the only thing that makes the rest of the packet safe to hand out.
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

TODAY = date(2026, 9, 21)
W2 = date(2026, 9, 20)

CYCLES = [
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
     "weeks": 6, "status": "Actual"},
]

#: Eight areas over two zones — enough for a packet with every section in it
#: and every kind of page, without a test that takes a minute to run.
ROSTER = pd.DataFrame([
    {"Area_Name": f"{zone[0]}{i}", "Zone": zone, "District": f"{zone[0]}D{i//2}",
     "Companion1_Name": f"Elder {zone[0]}{i}"}
    for zone in ("Norte", "Sur") for i in range(4)
])

NEW = "ki_new_people_real"
SACR = "ki_friends_sacrament_real"

#: N3 and S3 never file, so the data note has silent areas to name.
WEEKLY_KI = pd.DataFrame([
    {"_week": "2026-09-13", "_area": a, NEW: 10, SACR: 2}
    for a in ("N0", "N1", "N2", "S0", "S1", "S2")
] + [
    {"_week": "2026-09-20", "_area": a, NEW: 8, SACR: 1}
    for a in ("N0", "N1", "S0")
])

DAILY = pd.DataFrame(
    [{"_day": d, "_area": a, "contacts_attempted": 20, "roleplays": 1}
     for d in ("2026-09-14", "2026-09-15") for a in ("N0", "N1", "S0")]
)


def _ki_goals(week, areas=None):
    """A baptismal-friends goal far above what anybody reaches, so the packet
    has a flagged Key Indicator to report — CCSM has exactly one."""
    return ({NEW: 90.0, SACR: 400.0}, {NEW: 6, SACR: 6}, date(2026, 9, 6), 6)


def _data(**over) -> M.ReportData:
    kw = dict(roster=ROSTER, weekly_ki=WEEKLY_KI, daily_log=DAILY,
              cycles=CYCLES, ki_keys=(NEW, SACR),
              nightly_keys=("contacts_attempted", "roleplays"),
              nightly_goals={"contacts_attempted": 150.0, "roleplays": 7.0},
              labels={NEW: "Nuevas Personas", SACR: "Amigos en Sacramental",
                      "contacts_attempted": "Intentos de Contacto",
                      "roleplays": "Prácticas de Enseñanza"},
              mission_name="Misión de Prueba", today=TODAY, anchor=W2,
              ki_goals_fn=_ki_goals)
    kw.update(over)
    return M.ReportData(**kw)


@pytest.fixture(scope="module")
def data():
    return _data()


@pytest.fixture(scope="module")
def pdf(data):
    return PK.build(data=data)


@pytest.fixture(scope="module")
def reader(pdf):
    return PdfReader(io.BytesIO(pdf))


def _pages(reader):
    return [(p.extract_text() or "") for p in reader.pages]


# ── One call, one PDF ─────────────────────────────────────────────────────────

def test_build_takes_a_period_and_returns_a_pdf(pdf):
    """`build_packet(period) -> bytes`, which is all the button needs to know."""
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 20_000


def test_build_reuses_the_data_it_is_handed(data, monkeypatch):
    """The screen already holds a cached `ReportData`; a packet built from the
    page must cost the render alone and not a second sheet read."""
    called = []
    monkeypatch.setattr(M, "load_data", lambda *a, **k: called.append(1))
    PK.build(data=data)
    assert called == []


def test_a_period_the_schedule_cannot_supply_is_refused(data):
    with pytest.raises(ValueError):
        PK.build("no-such-period", data=data)


def test_the_filename_is_a_key_and_not_a_sentence(data):
    models = M.build_all(data=data)
    name = PK.filename(models[0])
    assert name.endswith(".pdf")
    assert re.fullmatch(r"paquete-consejo-[a-z_]+-\d{4}-\d{2}-\d{2}\.pdf", name)


# ── The acceptance ────────────────────────────────────────────────────────────

def test_every_page_is_letter(reader):
    """Decision 25's acceptance rests on it: the layout is built to Letter
    margins and a page of another size would be scaled at print time."""
    for page in reader.pages:
        box = page.mediabox
        assert (round(float(box.width)), round(float(box.height))) == (612, 792)


def test_every_page_but_the_cover_carries_its_own_number(reader):
    pages = _pages(reader)
    assert len(pages) > 5
    assert "Página" not in pages[0]
    for i, page in enumerate(pages[1:], start=2):
        assert f"Página {i}" in page, f"page {i}"


def test_no_page_is_blank(reader):
    """An empty page in a council packet is a printing mistake somebody has to
    ask about. The nightly block came five points over the frame once and put
    its last note alone behind every unit."""
    for i, page in enumerate(_pages(reader), start=1):
        body = page.replace(f"Página {i}", "").strip()
        assert len(body) > 40, f"page {i} is all but empty"


def _text_baselines(page):
    """Every string's baseline on a page, in PAGE coordinates.

    A `Tm` inside a `q ... cm ... Q` block is in the translated space platypus
    put the flowable in, so the raw numbers are local and mean nothing on their
    own — the first version of this test read a footer at y=1.5 and called it a
    flowable in the margin. The translations are tracked here instead.
    """
    stream = page.get_contents().get_data().decode("latin-1")
    tokens = stream.replace(chr(10), " ").split()
    offset, stack, out = 0.0, [], []
    for i, token in enumerate(tokens):
        if token == "q":
            stack.append(offset)
        elif token == "Q" and stack:
            offset = stack.pop()
        elif token == "cm" and i >= 6:
            offset += float(tokens[i - 1])
        elif token == "Tm" and i >= 6:
            out.append(offset + float(tokens[i - 1]))
    return out


def test_nothing_is_drawn_into_the_furniture_band(reader):
    """"Actual size" is only safe if no flowable entered the running head's
    band or the footer's — decision 25's acceptance, checked on the document's
    own content stream rather than on a block measured in isolation."""
    top = PP.PAGE_HEIGHT - PP.MARGIN_TOP
    for i, page in enumerate(reader.pages, start=1):
        ys = _text_baselines(page)
        body = [y for y in ys
                if abs(y - PP.HEAD_BASELINE) > 0.5
                and abs(y - PP.FOOT_BASELINE) > 0.5]
        assert body, f"page {i} drew no text"
        assert max(body) <= top + 1, f"page {i} drew into the running head"
        # A baseline sits a little under the flowable's own bottom edge, so the
        # floor is the frame's, less one line.
        assert min(body) >= PP.MARGIN_BOTTOM - PP.CELL.leading,             f"page {i} drew into the footer"


def test_the_head_and_the_foot_really_are_where_the_geometry_says(reader):
    """Belt and braces on the parser above: every page after the cover carries
    a string on the head's baseline and one on the footer's."""
    for i, page in enumerate(reader.pages[1:], start=2):
        ys = _text_baselines(page)
        assert any(abs(y - PP.HEAD_BASELINE) < 0.5 for y in ys), f"page {i}"
        assert any(abs(y - PP.FOOT_BASELINE) < 0.5 for y in ys), f"page {i}"


def test_the_packet_holds_every_unit_of_the_mission(reader, data):
    text = "\n".join(_pages(reader))
    for model in M.build_all(data=data):
        assert model.scope.name in text, model.scope.key


# ── The data note ─────────────────────────────────────────────────────────────

def test_the_data_note_names_every_source_it_used(reader):
    note = _pages(reader)[-1]
    for tab in ("WEEKLY_KI", "AREA_TRANSFER_GOALS", "DAILY_LOG",
                "WEEKLY_BREAKDOWNS", "SCORES", "MISSION_ORG"):
        assert tab in note


def test_the_data_note_names_the_areas_that_reported_nothing(reader):
    """They count in every per-active-area denominator and appear in no sum;
    a reader is owed the list rather than the arithmetic alone."""
    note = _pages(reader)[-1]
    assert "N3" in note and "S3" in note
    assert "no informaron" in note


def test_the_data_note_names_the_goals_that_are_not_yardsticks(reader):
    """CCSM has exactly one such Key Indicator today, and it is a finding for
    the council rather than a footnote."""
    note = _pages(reader)[-1]
    assert "Meta no utilizable: Amigos en Sacramental" in note


def test_the_data_note_says_why_there_is_no_finding_section(reader):
    """Decision 32: a packet dated November showing August finding data is
    worse than one with no finding section, and the absence has to be stated."""
    note = _pages(reader)[-1]
    assert "Tableau" in note


def test_the_data_note_states_the_period_and_the_compliance(reader, data):
    note = _pages(reader)[-1]
    mission = M.build_all(data=data)[0]
    assert mission.period.window_label in note
    assert mission.compliance_label in note


# ── The contents reads as Spanish ─────────────────────────────────────────────

def test_a_section_of_half_pages_says_two_to_a_page():
    """"0,5 páginas cada una" is arithmetically right and reads like a
    mistake."""
    section = PK.Section("k", "Cada área — 45", "", units=45, feminine=True,
                         first_page=1, last_page=23)
    assert PK._titled(section) == "Cada área — 45, dos por página"


def test_the_count_agrees_with_the_noun():
    zone = PK.Section("k", "Cada zona — 4", "", units=4, feminine=True,
                      first_page=1, last_page=24)
    district = PK.Section("k", "Cada distrito — 13", "", units=13,
                          first_page=1, last_page=52)
    assert PK._titled(zone).endswith("6 páginas cada una")
    assert PK._titled(district).endswith("4 páginas cada uno")


def test_a_section_of_one_unit_states_no_count():
    section = PK.Section("k", "La misión", "", units=1, first_page=3,
                         last_page=8)
    assert PK._titled(section) == "La misión"
