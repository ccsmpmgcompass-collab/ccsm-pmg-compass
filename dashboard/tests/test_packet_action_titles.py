"""Action titles and the method moved out — PLAN-2026-10-13 step 4.2 (C10).

Every mission and zone section head carries a computed conclusion under its
small label; every block keeps one source line, and the method paragraphs
live in the data note. Measured: "sin color" five times or fewer in the
council packet, and every caption on one line.
"""

import io

from pypdf import PdfReader
from reportlab.platypus import KeepTogether, Paragraph

from app.reports import packet as PK
from app.reports import packet_parts as PP
from app.reports import scope as S
from tests.test_packet_tableau import ROSTER, models, words


def _walk(flow):
    for f in flow:
        if isinstance(f, (list, tuple)):
            yield from _walk(f)
        elif isinstance(f, KeepTogether):
            yield from _walk(f._content)
        else:
            yield f


def _unit(level):
    built, _ = models()
    peers = {m.scope.key: m for m in built}
    m = next(m for m in built if m.scope.level == level)
    return m, list(_walk(PK.unit_pages(m, {}, peers)))


def test_a_head_carries_its_conclusion_under_its_label():
    flow = PK.action_head("Dónde enfocar", "Los primeros 3 distritos suman.")
    assert isinstance(flow[0], PP.SectionHead)
    assert flow[1].style.name == "action"
    assert PK.action_head("Sin conclusión")[1:] == []


def test_the_mission_s_heads_say_what_they_found():
    _, flow = _unit(S.MISSION)
    actions = [f.getPlainText() for f in flow
               if isinstance(f, Paragraph) and f.style.name == "action"]
    assert len(actions) >= 5
    assert any("de informes" in a for a in actions)
    assert any(a.startswith("El año cierra en") for a in actions)


def test_every_caption_on_the_mission_and_zone_pages_is_one_line():
    note = PP.styles()["note"]
    for level in (S.MISSION, S.ZONE):
        _, flow = _unit(level)
        for f in flow:
            if isinstance(f, Paragraph) and f.style.name == "note":
                _, h = f.wrap(PP.CONTENT_WIDTH, 1000)
                assert round(h / note.leading) <= 1, f.getPlainText()


def test_the_methods_live_in_the_data_note():
    built, _ = models()
    mission = next(m for m in built if m.scope.level == S.MISSION)
    methods = dict(PK.section_methods(mission))
    assert "El tablero" in methods and "Dónde enfocar" in methods
    assert "pesos del índice" in methods["Dónde enfocar"]
    text = words(PK.data_note(built))
    assert "Cómo se calcula cada sección" in text
    assert "«Sin informe»: más de la mitad de su parte" in text


def test_sin_color_is_said_five_times_or_fewer():
    built, data = models()
    pdf = PK.build_packet(built, ROSTER)
    text = " ".join((p.extract_text() or "")
                    for p in PdfReader(io.BytesIO(pdf)).pages).lower()
    assert text.count("sin color") <= 5
