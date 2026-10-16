"""The year's path — PLAN-2026-10-13 step 2.2 (C5).

The mission's year block draws the cumulative certified baptisms against a
straight path to 527, with the landing range as a pale fan to December. The
month-by-month table it used to carry moves to the data note. Each pilot
zone's path, against its share of 527, sits under the mission's as a small
multiple. Nothing is coloured as a verdict.
"""

from dataclasses import replace

from reportlab.graphics.shapes import Polygon, PolyLine, String
from reportlab.platypus import Table

from app.reports import forecast as F
from app.reports import packet as PK
from app.reports import packet_parts as PP
from app.reports import scope as S
from tests.test_packet_tableau import models, words

MONTHS = F.MONTH_ABBR
PATH = [527 * (i + 1) / 12 for i in range(12)]


def _shapes(d, kind):
    return [c for c in d.contents if isinstance(c, kind)]


def test_the_path_is_a_line_a_dashed_goal_and_a_fan():
    d = PP.year_path_chart(400, 150, MONTHS, PATH, [30, 64, 106], 420, 460,
                           goal_label="meta 527", actual_label="106 a mar",
                           range_label="cierra 420-460")
    lines = _shapes(d, PolyLine)
    assert len(lines) == 2
    assert any(line.strokeDashArray for line in lines)       # the goal path
    assert len(_shapes(d, Polygon)) == 1                       # the fan
    text = " ".join(s.text for s in _shapes(d, String))
    assert "meta 527" in text and "cierra 420-460" in text
    assert "106 a mar" in text and "ene" in text and "dic" in text


def test_the_path_carries_no_status_colour():
    d = PP.year_path_chart(400, 150, MONTHS, PATH, [30, 64, 106], 420, 460)
    status = {(c.red, c.green, c.blue) for c in PP.STATUS.values()}
    for shape in d.contents:
        for attr in ("fillColor", "strokeColor"):
            c = getattr(shape, attr, None)
            if c is not None:
                assert (c.red, c.green, c.blue) not in status


def test_a_closed_year_has_no_fan():
    actual = [44 * (i + 1) for i in range(12)]
    d = PP.year_path_chart(400, 150, MONTHS, PATH, actual, 528, 528)
    assert _shapes(d, Polygon) == []


def test_the_right_margin_labels_never_sit_on_each_other():
    """The goal ends at 527 and the fan's middle at 520: a few points apart,
    so the two labels are pushed at least 9pt apart."""
    d = PP.year_path_chart(400, 150, MONTHS, PATH, [30, 64, 106], 515, 525,
                           goal_label="meta 527", range_label="cierra 515-525")
    ys = sorted(s.y for s in _shapes(d, String)
                if s.text in ("meta 527", "cierra 515-525"))
    assert ys[1] - ys[0] >= 9 - 1e-6


def test_the_small_multiple_has_no_scale_and_no_months():
    d = PP.year_path_chart(120, 54, MONTHS, PATH, [30, 64, 106], 420, 460,
                           axis=False)
    assert [s for s in _shapes(d, String)] == []


def test_the_mission_s_year_block_draws_the_path_and_drops_the_table():
    built, _ = models()
    mission = next(m for m in built if m.scope.level == S.MISSION)
    block = PK.year_block(mission)
    text = words(block)
    assert "meta 527" in text and "cierra" in text
    assert not any(isinstance(f, Table) for f in block)
    assert "Mes a mes, en la nota de datos" in text
    note = words(PK.data_note(built))
    assert "Bautismos de la misión, mes a mes" in note
    table = PK.year_table(mission.forward.year)
    assert isinstance(table[1], Table) and len(table[1]._cellvalues) == 13


def test_each_zone_s_path_sits_under_the_mission_s():
    """The fixture's zone has no confirmations, so it is handed a year."""
    built, _ = models()
    peers = {m.scope.key: m for m in built}
    zone = next(m for m in built if m.scope.level == S.ZONE)
    year = F.year_landing({"2026-01": 3, "2026-02": 4, "2026-03": 5}, 2026,
                          goal=42, source="registros de Tableau")
    peers[zone.scope.key] = replace(
        zone, forward=replace(zone.forward, year=year))
    mission = next(m for m in built if m.scope.level == S.MISSION)
    text = words(PK.zone_paths(mission, peers))
    assert "Las zonas en 2026" in text and "Angol" in text
    assert "su parte de 527" in text
    assert "12 a mar de 42" in text
    assert PK.zone_paths(zone, peers) == []
    assert PK.zone_paths(mission, {}) == []
