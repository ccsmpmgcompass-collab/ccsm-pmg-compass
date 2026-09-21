"""The printed page's furniture and its five vector charts — PLAN step P1.

Three properties this file is really about.

**Every primitive returns a Drawing of the size it declared.** A chart that
sizes itself to its content is how a page ends up one row taller than the frame
and silently starts a new one.

**Every colour comes from `config/theme.py`.** The Phase F lesson: a hex
literal written into a renderer is the first of two greens that both mean
"good". The walker below collects every fill and stroke the primitives produce
and fails on anything the theme does not name.

**Nothing prints in the wrong typeface.** ReportLab silently font-switches a
character the base-14 encoding cannot reach — a "↑" comes out in Symbol, a "▲"
in ZapfDingbats — so `text()` is the gate and this file pins its behaviour.
"""

import io
import re

import pytest
from reportlab.graphics.shapes import (Circle, Drawing, Group, Line, Polygon,
                                       PolyLine, Rect, String)
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate

import app.reports.packet_parts as PP
from app.config import theme

# ── Helpers ───────────────────────────────────────────────────────────────────


def _shapes(node):
    """Every shape in a Drawing, groups flattened."""
    for shape in getattr(node, "contents", []):
        if isinstance(shape, (Group, Drawing)):
            yield from _shapes(shape)
        else:
            yield shape


def _colors_used(drawing):
    out = set()
    for shape in _shapes(drawing):
        for attr in ("fillColor", "strokeColor"):
            c = getattr(shape, attr, None)
            if c is not None:
                out.add(c.hexval())
    return out


def _theme_colors():
    """Every colour the theme names, as ReportLab hexvals."""
    names = [theme.PRINT_INK, theme.PRINT_INK_2, theme.PRINT_INK_3,
             theme.PRINT_RULE, theme.PRINT_RULE_SOFT, theme.PRINT_TINT,
             theme.PRINT_PAPER, theme.PRINT_MARK, theme.PRINT_ACCENT,
             theme.MISSION_NAVY]
    names += list(theme.PRINT_STATUS.values()) + list(theme.SERIES_COLORS)
    return {PP.pc(n).hexval() for n in names}


def _render(flowables, *, pages=1):
    """Run the flowables through a real document and hand back its bytes."""
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=PP.PAGE_SIZE,
                          leftMargin=PP.MARGIN_X, rightMargin=PP.MARGIN_X,
                          topMargin=PP.MARGIN_TOP, bottomMargin=PP.MARGIN_BOTTOM)
    frame = Frame(PP.MARGIN_X, PP.MARGIN_BOTTOM, PP.CONTENT_WIDTH,
                  PP.CONTENT_HEIGHT, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="pmg", frames=[frame],
                                       onPageEnd=PP.draw_furniture)])
    doc.build(list(flowables))
    return buf.getvalue()


def _page_texts(pdf_bytes):
    from pypdf import PdfReader
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf_bytes)).pages]


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


# ── The module stays pure ─────────────────────────────────────────────────────

def test_packet_parts_does_not_pull_in_streamlit():
    """The same acceptance every module in `app/reports` carries: the packet is
    built in a background process and in a test, neither of which has a
    browser."""
    assert not _imports_streamlit("app.reports.packet_parts")


# ── Geometry ──────────────────────────────────────────────────────────────────

def test_the_content_box_and_the_margins_account_for_the_whole_page():
    assert PP.CONTENT_WIDTH + 2 * PP.MARGIN_X == pytest.approx(PP.PAGE_WIDTH)
    assert (PP.CONTENT_HEIGHT + PP.MARGIN_TOP + PP.MARGIN_BOTTOM
            == pytest.approx(PP.PAGE_HEIGHT))


def test_the_furniture_sits_outside_the_content_box():
    """Decision 25's acceptance is a page that survives "Actual size". The head
    rule must clear the top of the frame and the footer rule its bottom, or a
    table's first row prints over the running head."""
    frame_top = PP.PAGE_HEIGHT - PP.MARGIN_TOP
    assert PP.HEAD_RULE_Y > frame_top
    assert PP.HEAD_BASELINE > PP.HEAD_RULE_Y
    assert PP.FOOT_RULE_Y < PP.MARGIN_BOTTOM
    assert PP.FOOT_BASELINE < PP.FOOT_RULE_Y


# ── Each primitive returns a Drawing of the size it declared ──────────────────

def _every_primitive():
    return {
        "bar_vs_goal": PP.bar_vs_goal(200.0, pct=71.0, status="warn",
                                      mark_pct=82.0),
        "sparkline": PP.sparkline(150.0, 18.0, [3, 5, 4, 9, 7],
                                  boundaries=[0.5]),
        "stage_bars": PP.stage_bars(400.0, [("Nuevas", 330), ("Otra vez", 185),
                                            ("Iglesia", 107), ("Fecha", 52),
                                            ("Bautizadas", 33)]),
        "share_bar": PP.share_bar(400.0, [("Misioneros", 230),
                                          ("Miembros", 95), ("Medios", 6)]),
        "ranked_row": PP.ranked_row(
            PP.RankedSpec(width=PP.CONTENT_WIDTH, cells=("NUEVAS", "BAUT.")),
            rank=1, name="Los Angeles Norte", sub="12 áreas · 50% informaron",
            status="bad", cells=("3,9", "0,1"), value="61%", bar=61,
            bar_max=100),
    }


@pytest.mark.parametrize("name", sorted(_every_primitive()))
def test_every_primitive_is_a_drawing_of_its_declared_size(name):
    d = _every_primitive()[name]
    assert isinstance(d, Drawing)
    assert d.width > 0 and d.height > 0
    assert list(_shapes(d)), f"{name} drew nothing"


def test_the_two_fixed_height_primitives_honour_the_height_asked_for():
    assert PP.bar_vs_goal(200.0, pct=50, height=9.0).height == 9.0
    assert PP.sparkline(150.0, 22.0, [1, 2, 3]).height == 22.0


def test_the_three_growing_primitives_size_themselves_to_their_content():
    """A stage chart of five stages is taller than one of three, and the height
    it reports is the height it drew — that is what lets the caller know
    whether the section still fits on the page."""
    three = PP.stage_bars(400.0, [("a", 3), ("b", 2), ("c", 1)])
    five = PP.stage_bars(400.0, [("a", 5), ("b", 4), ("c", 3), ("d", 2),
                                 ("e", 1)])
    assert five.height > three.height
    one_row = PP.share_bar(300.0, [("a", 1), ("b", 1)])
    two_rows = PP.share_bar(300.0, [("a", 1)] * 4)
    assert two_rows.height > one_row.height
    assert (PP.ranked_row(PP.RankedSpec(width=300.0), name="x", header=True).height
            < PP.ranked_row(PP.RankedSpec(width=300.0), name="x").height)


# ── Every colour comes from the theme ─────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(_every_primitive()))
def test_a_primitive_draws_no_colour_the_theme_does_not_name(name):
    allowed = _theme_colors()
    used = _colors_used(_every_primitive()[name])
    assert used <= allowed, f"{name} drew {sorted(used - allowed)}"


def test_the_print_palette_is_the_same_three_states_and_no_more():
    assert set(theme.PRINT_STATUS) == set(theme.STATUS) == {"good", "warn", "bad"}
    assert set(PP.STATUS_WORD) == set(theme.PRINT_STATUS)


def test_an_ungraded_thing_is_grey_and_not_a_fourth_hue():
    """"No reading" must never borrow a grading colour — the same rule the
    calendar's two ungraded cells follow."""
    assert PP.status_color(None).hexval() == PP.INK_3.hexval()
    assert PP.status_color("").hexval() == PP.INK_3.hexval()
    for state in theme.PRINT_STATUS:
        assert PP.status_color(state).hexval() != PP.INK_3.hexval()


# ── Text that is safe to print ────────────────────────────────────────────────

def test_spanish_survives_unchanged():
    for s in ["Purén y Los Sauces", "Temuco Ñielol", "Misión Concepción Sur",
              "2 de 6 semanas · 70% informaron", "meta no utilizable",
              "¿Qué área?", "7 sep – 18 oct", "área"]:
        assert PP.is_printable(s), s
        assert PP.text(s) == s


def test_every_word_this_module_ships_is_printable():
    assert all(PP.is_printable(w) for w in PP.STATUS_WORD.values())


def test_the_characters_reportlab_would_font_switch_are_caught():
    """Measured 2026-09-21: each of these makes ReportLab emit the run in
    Symbol or ZapfDingbats without a word of warning."""
    for bad in ["↑", "↓", "▲", "▼"]:
        assert not PP.is_printable(f"cambio {bad} 12%")


def test_the_substitutions_are_made_rather_than_dropped():
    assert PP.text("2026-09-07 → 2026-10-18") == "2026-09-07 - 2026-10-18"
    assert PP.text("−5%") == "-5%"
    assert PP.text("dos semanas") == "dos semanas"


def test_an_unexpected_character_is_folded_before_it_is_dropped():
    """A name is worth more half-right than absent: an accent ReportLab cannot
    set is stripped from the letter rather than taking the letter with it."""
    assert PP.text("Hǎi") == "Hai"
    assert PP.text("a☃b") == "ab"


def test_fit_truncates_by_measure_and_not_by_character_count():
    long_name, short_name = "Purén y Los Sauces", "Angol"
    assert PP.fit(short_name, PP.CELL, 150) == short_name
    assert PP.width_of(long_name, PP.CELL) < 150     # the real roster's widest
    assert PP.fit(long_name, PP.CELL, 150) == long_name
    cut = PP.fit(long_name, PP.CELL, 40)
    assert cut.endswith("...") and PP.width_of(cut, PP.CELL) <= 40


# ── The direction mark is drawn, never typed ──────────────────────────────────

def test_a_direction_is_a_triangle_in_the_status_colour():
    up = PP.change_mark(0, 0, 1)
    down = PP.change_mark(0, 0, -1)
    assert isinstance(up, Polygon) and isinstance(down, Polygon)
    assert up.fillColor.hexval() == PP.STATUS["good"].hexval()
    assert down.fillColor.hexval() == PP.STATUS["bad"].hexval()
    assert up.points != down.points


def test_no_direction_draws_nothing():
    """"sin cambio" is a sentence, not a sideways arrow."""
    assert PP.change_mark(0, 0, 0) is None


# ── The charts say what they mean ─────────────────────────────────────────────

def test_a_bar_over_its_goal_stops_at_the_end_of_the_track():
    """A bar that ran past its track would have to rescale every other bar on
    the page; the figure beside it carries the overshoot instead."""
    track = PP.bar_vs_goal(200.0, pct=None).contents[0]
    over = PP.bar_vs_goal(200.0, pct=180.0, status="good")
    fills = [s for s in _shapes(over) if isinstance(s, Rect)]
    assert max(f.width for f in fills) <= track.width


def test_a_bar_with_no_reading_draws_an_empty_track_not_a_zero_fill():
    empty = PP.bar_vs_goal(200.0, pct=None)
    assert len(list(_shapes(empty))) == 1


def test_the_leadership_mark_is_violet_and_stays_on_the_track():
    inside = PP.bar_vs_goal(200.0, pct=40.0, status="bad", mark_pct=80.0)
    violet = [s for s in _shapes(inside)
              if getattr(s, "fillColor", None) is not None
              and s.fillColor.hexval() == PP.MARK.hexval()]
    assert len(violet) == 1
    assert violet[0].x + violet[0].width <= 200.0


def test_a_goal_past_the_end_of_the_track_says_so_instead_of_sitting_on_it():
    """Clamped, four different leadership goals all read as "exactly at the
    line" — and on CCSM they routinely exceed the companionships' own meta,
    so that is the common case rather than the edge one."""
    over = PP.bar_vs_goal(200.0, pct=40.0, status="bad", mark_pct=140.0)
    violet = [s for s in _shapes(over)
              if getattr(s, "fillColor", None) is not None
              and s.fillColor.hexval() == PP.MARK.hexval()]
    assert len(violet) == 2
    rule = next(s for s in violet if isinstance(s, Rect))
    head = next(s for s in violet if isinstance(s, Polygon))
    assert rule.x + rule.width <= 200.0
    assert min(head.points[0::2]) > 200.0        # the arrowhead is outside it


def test_a_sparkline_breaks_at_a_week_nobody_reported():
    """The screen's spark filters the gaps out and draws through them. On paper
    a straight run through a silent week is a claim that the week happened."""
    whole = PP.sparkline(150.0, 18.0, [3, 5, 4, 9])
    gapped = PP.sparkline(150.0, 18.0, [3, 5, None, 4, 9])
    assert len([s for s in _shapes(whole) if isinstance(s, PolyLine)]) == 1
    assert len([s for s in _shapes(gapped) if isinstance(s, PolyLine)]) == 2


def test_a_sparkline_with_one_reading_draws_no_line_at_all():
    assert not [s for s in _shapes(PP.sparkline(150.0, 18.0, [7]))
                if isinstance(s, PolyLine)]


def test_a_transfer_boundary_is_a_dashed_rule_on_the_axis():
    """Decision 9 — every time axis carries them."""
    lines = [s for s in _shapes(PP.sparkline(150.0, 18.0, [1, 2, 3],
                                             boundaries=[0.25, 0.75]))
             if isinstance(s, Line)]
    assert len(lines) == 2
    assert all(line.strokeDashArray for line in lines)
    assert [round(line.x1, 1) for line in lines] == [37.5, 112.5]


def test_the_stage_chart_names_the_step_that_loses_the_most_people():
    """Absolute, not the lowest rate: 2.378 people lost at an 88% step is the
    pipeline's problem, and a 4% step costing 65 is not."""
    drawn = PP.stage_bars(400.0, [("a", 2545), ("b", 167), ("c", 68), ("d", 3)])
    said = [s.text for s in _shapes(drawn) if isinstance(s, String)]
    assert sum("mayor caída" in t for t in said) == 1
    worst = next(t for t in said if "mayor caída" in t)
    assert worst.startswith("7%")       # 167 of 2.545, the widest fall


def test_a_stage_that_widens_prints_no_conversion():
    """People reach a milestone inside the window whose earlier milestone fell
    before it, so a later stage can exceed an earlier one — and a percentage
    over 100 there is arithmetic about two different cohorts."""
    said = [s.text for s in _shapes(PP.stage_bars(400.0, [("a", 10), ("b", 30)]))
            if isinstance(s, String)]
    assert not [t for t in said if "del anterior" in t]


def test_the_share_bar_is_one_bar_whose_segments_fill_it_exactly():
    drawn = PP.share_bar(300.0, [("a", 50), ("b", 30), ("c", 20)])
    segs = [s for s in _shapes(drawn)
            if isinstance(s, Rect) and s.height == PP.SHARE_BAR_HEIGHT]
    assert len(segs) == 3
    assert sum(s.width for s in segs) == pytest.approx(300.0)


def test_a_sliver_keeps_its_colour_and_its_legend_and_drops_its_label():
    drawn = PP.share_bar(300.0, [("grande", 97), ("astilla", 3)])
    inside = [s.text for s in _shapes(drawn)
              if isinstance(s, String) and s.text.endswith("%")
              and s.textAnchor == "middle"]
    assert inside == ["97%"]
    swatches = [s for s in _shapes(drawn) if isinstance(s, Rect) and s.width == 5]
    assert len(swatches) == 2


def test_an_empty_mix_draws_nothing_rather_than_a_full_bar():
    assert not list(_shapes(PP.share_bar(300.0, [])))
    assert not list(_shapes(PP.share_bar(300.0, [("a", 0), ("b", 0)])))


def test_a_ranked_list_and_its_header_line_up_on_one_spec():
    spec = PP.RankedSpec(width=520.0, cells=("NUEVAS", "SACR.", "BAUT."))
    head = PP.ranked_row(spec, name="zona", header=True)
    row = PP.ranked_row(spec, rank=1, name="Angol", status="warn",
                        cells=("4,6", "1,3", "0,1"), value="74%", bar=74,
                        bar_max=100)
    assert head.width == row.width == spec.width
    assert spec.name_x < spec.cells_x < spec.bar_x <= spec.value_x
    assert spec.name_width > PP.width_of("Los Angeles Norte", PP.CELL)


def test_a_ranked_row_carries_its_rank_its_dot_and_its_value():
    spec = PP.RankedSpec(width=520.0)
    row = PP.ranked_row(spec, rank=4, name="Angol", sub="9 áreas", status="bad",
                        value="74%", bar=74, bar_max=100)
    said = [s.text for s in _shapes(row) if isinstance(s, String)]
    assert "4" in said and "74%" in said and "Angol" in said
    dots = [s for s in _shapes(row) if isinstance(s, Circle)]
    assert len(dots) == 1
    assert dots[0].fillColor.hexval() == PP.STATUS["bad"].hexval()


# ── The page frame ────────────────────────────────────────────────────────────

def test_the_running_head_and_the_footer_print_on_the_page_that_set_them():
    """The one that matters. The furniture is drawn on **onPageEnd**, so a
    marker at the top of a section reaches the head of the page it opens; on
    onPage it would land a page late and only the first page of each unit would
    be wrong — which is every page anybody checks last."""
    mission = PP.Furniture(eyebrow="Misión Concepción Sur",
                           period="Este traslado", mission="CCSM")
    zone = PP.Furniture(eyebrow="Zona · San Pedro", period="Este traslado",
                        trail="San Pedro", mission="CCSM")
    pages = _page_texts(_render([
        PP.SetFurniture(mission), PP.SectionHead("Donde estamos"),
        PageBreak(),
        PP.SetFurniture(zone), PP.SectionHead("La zona"),
    ]))
    assert len(pages) == 2
    assert "MISIÓN CONCEPCIÓN SUR" in pages[0].upper()
    assert "ZONA · SAN PEDRO" in pages[1].upper()
    assert "San Pedro" not in pages[0]
    assert "Página 1" in pages[0] and "Página 2" in pages[1]


def test_a_section_that_spills_keeps_the_furniture_of_the_unit_it_belongs_to():
    tall = [PP.SectionHead(f"Sección {i}") for i in range(60)]
    pages = _page_texts(_render(
        [PP.SetFurniture(PP.Furniture(eyebrow="Zona · Angol", period="Año",
                                      mission="CCSM"))] + tall))
    assert len(pages) > 1
    assert all("ZONA · ANGOL" in p.upper() for p in pages)


def test_a_page_with_no_marker_draws_no_furniture_rather_than_the_last_unit_s():
    pages = _page_texts(_render([PP.SectionHead("Sin dueño")]))
    assert "PMG Compass" not in pages[0]


def test_a_section_head_prints_its_label_and_its_note():
    pages = _page_texts(_render([
        PP.SetFurniture(PP.Furniture(eyebrow="Misión", period="Año")),
        PP.SectionHead("Todo el trabajo nocturno",
                       "más atrasado primero · 22 medidas"),
    ]))
    assert "TODO EL TRABAJO NOCTURNO" in pages[0].upper()
    assert "más atrasado primero" in pages[0]


def test_a_tracked_run_does_not_leave_its_spacing_behind():
    """`Tc` is text state and text state survives `ET`, so a tracked run leaves
    its spacing behind for whatever is drawn next. Left conditional, the section
    note inherited its label's 0.9pt and set 30pt wider than it measured, which
    put a right-aligned string over the right margin — and right-aligned text
    that overflows to the RIGHT is the half of that bug nothing else catches.

    The property: every text block that sets a string also states its own
    character spacing, so none of them can inherit the block before it.
    """
    from pypdf import PdfReader
    pdf = _render([
        PP.SetFurniture(PP.Furniture(eyebrow="Misión", period="Este traslado")),
        PP.SectionHead("Indicadores Clave", "contra la meta de las companerías"),
    ])
    stream = (PdfReader(io.BytesIO(pdf)).pages[0]
              .get_contents().get_data().decode("latin-1"))
    blocks = [b for b in re.findall(r"BT(.*?)ET", stream, re.S) if "Tj" in b]
    assert len(blocks) >= 6
    assert all(re.search(r"[0-9.]+ Tc", b) for b in blocks)
    tracked = [b for b in blocks if "0.9 Tc" in b or ".9 Tc" in b]
    assert len(tracked) == 1                    # only the uppercase label


def test_the_section_note_stays_inside_the_frame():
    long_note = "contra la meta de las companerías · la marca violeta es la meta de liderazgo"
    head = PP.SectionHead("Indicadores Clave", long_note)
    head.wrap(PP.CONTENT_WIDTH, PP.CONTENT_HEIGHT)
    used = PP.width_of("Indicadores Clave".upper(), PP.SECTION)
    shown = PP.fit(long_note, PP.SECTION_NOTE, PP.CONTENT_WIDTH - used - 14)
    assert PP.width_of(shown, PP.SECTION_NOTE) + used + 14 <= PP.CONTENT_WIDTH


def test_a_ranked_header_label_sits_over_the_numbers_it_names():
    spec = PP.RankedSpec(width=520.0, cells=("NUEVAS", "SACR.", "BAUT."))
    head = PP.ranked_row(spec, name="zona", header=True)
    row = PP.ranked_row(spec, rank=1, name="Angol", status="warn",
                        cells=("4,6", "1,3", "0,1"), value="74%")
    # The right edge of each header run and of the figure under it.
    head_right = sorted({round(s.x + PP.stringWidth(s.text, s.fontName,
                                                    s.fontSize), 0)
                         for s in _shapes(head) if isinstance(s, String)})
    cell_right = sorted({round(s.x, 0) for s in _shapes(row)
                         if isinstance(s, String) and s.textAnchor == "end"
                         and s.text in ("4,6", "1,3", "0,1")})
    for edge in cell_right:
        assert min(abs(edge - h) for h in head_right) <= 1.5


def test_the_metric_table_leaves_its_notes_room_on_the_same_page():
    """Measured: the nightly table is twenty-two rows, and with its three
    closing notes the block came to 693pt against 688pt of frame. Five points
    over put the last note alone on a page of its own behind every unit in the
    packet, which is the kind of thing only a rendered document shows."""
    lines = [PP.MetricLine(label=f"Métrica {i}", value="100", goal="200",
                           pct=50.0, magnitude=True, verdict="50% de la meta",
                           note="meta 10/área/sem")
             for i in range(22)]
    table = PP.metric_table(lines)
    _, height = table.wrap(PP.CONTENT_WIDTH, PP.CONTENT_HEIGHT)
    assert height <= PP.CONTENT_HEIGHT - 60, "no room left for the notes"
