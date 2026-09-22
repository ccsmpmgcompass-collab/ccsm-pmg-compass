# -*- coding: utf-8 -*-
"""Phase T step T4 — the packet's finding pages, and Phase T's acceptance.

§4 T3's acceptance is that no Tableau figure ever appears in the same total or
table as a form figure (decision 34). That is the last test here, and it is
checked structurally — the finding and baptism pages are asserted never to
build a metric table — rather than by reading the rendered text, because a
page can name both figures honestly (decision 21 requires it) and only a
shared TOTAL is the thing decision 34 forbids.
"""

from datetime import date

import pandas as pd
import pytest
from reportlab.graphics.shapes import Drawing, Group
from reportlab.platypus import (KeepTogether, Paragraph, Spacer,
                                Table)

from app.reports import model as M
from app.reports import packet as PK
from app.reports import packet_parts as PP
from app.reports import periods as P
from app.reports import scope as S
from app.reports import tableau as T

from tests.test_report_tableau_blocks import CERTIFIED, CYCLE, people, person
from tests.test_report_tableau_gate import span


ROSTER = pd.DataFrame([
    {"Area_Name": "El Mirador", "Zone": "Angol", "District": "D1",
     "Companion1_Name": "Élder Díaz"},
    {"Area_Name": "Los Huertos", "Zone": "Angol", "District": "D1",
     "Companion1_Name": "Élder Soto"},
])

DETAIL = people(
    [person("2026-09-10", area="El Mirador",
            first_contact_attempt_event_date="2026-09-11",
            first_successful_contact_attempt_event_date="2026-09-12")] * 6
    + [person("2026-09-10", area="Los Huertos", source="Member",
              category="Member")] * 3
    + [person("2026-09-10", zone="Villarrica", area="Pucón")] * 4
    + [person("2026-09-10", zone="Angol", area="Caupolican")] * 2
    + [person("2026-08-30", area="El Mirador")] * 5)


def models(*, export=None, detail=None, baptisms=CERTIFIED):
    data = M.ReportData(
        roster=ROSTER, today=date(2026, 9, 21), cycles=[CYCLE],
        tableau_detail=DETAIL if detail is None else detail,
        tableau_export=(export if export is not None
                        else T.read_export(span("2024-01-01", "2026-09-17"))),
        tableau_maturity={"Attended Church": 33.0, "Baptism Date Set": 52.0,
                          "Baptized": 133.0},
        tableau_reconciliation=T.reconcile(DETAIL, S._clean(ROSTER)),
        baptisms_by_month=baptisms, annual_goal=527,
        baptisms_open=("2026-09", 19, date(2026, 9, 21)))
    return M.build_all(data=data), data


def shapes(node) -> str:
    """Every String inside a Drawing, including the nested Groups a chip or a
    sparkline is held in."""
    out = []
    for child in getattr(node, "contents", ()):
        if hasattr(child, "text"):
            out.append(str(child.text))
        elif hasattr(child, "contents"):
            out.append(shapes(child))
    return " ".join(out)


def words(flow) -> str:
    """Every string a page's flow would print: paragraphs, section heads,
    table cells and the text inside a Drawing."""
    out = []
    for item in flow if isinstance(flow, (list, tuple)) else [flow]:
        if isinstance(item, Paragraph):
            out.append(item.getPlainText())
        elif isinstance(item, (list, tuple)):
            out.append(words(item))
        elif isinstance(item, PP.SectionHead):
            out.append(f"{item.label} {item.note}")
        elif isinstance(item, Table):
            out.append(words([c for row in item._cellvalues for c in row]))
        elif isinstance(item, KeepTogether):
            out.append(words(item._content))
        elif isinstance(item, (Drawing, Group)):
            out.append(shapes(item))
        elif isinstance(item, str):
            out.append(item)
    return " ".join(out)


def of(level):
    built, _ = models()
    return next(m for m in built if m.scope.level == level)


# ── The finding page ──────────────────────────────────────────────────────────

def test_the_page_opens_with_the_window_it_rests_on_and_the_export_behind_it():
    text = words(PK.finding_page(of(S.MISSION)))
    assert "fuente: Tableau" in text
    assert "17 de sep de 2026" in text          # where the export reaches
    assert "11 de 15 días del período" in text  # and how short of the period


def test_the_mission_page_says_it_counts_ten_zones_and_the_rest_count_four():
    """Decision 34's hard case. Nothing else in the packet changes population
    from one page to the next, so it is said outright."""
    assert "10 zonas" in words(PK.finding_page(of(S.MISSION)))
    assert "MISSION_ORG" in words(PK.finding_page(of(S.ZONE)))


def test_an_area_gets_no_finding_page():
    assert PK.finding_page(of(S.AREA)) == []


def test_a_refused_window_prints_the_reason_where_the_section_would_have_been():
    built, _ = models(export=T.read_export(span("2024-01-01", "2026-08-03")))
    text = words(PK.finding_page(built[0]))
    assert "Sin sección de hallazgo" in text
    assert "no alcanza este período" in text
    assert "no se estiman ni se rellenan" in text


def test_the_refusal_still_says_how_far_the_export_reaches():
    """A reader who notices the gap should not have to guess whether it is a
    bug."""
    built, _ = models(export=T.read_export(span("2024-01-01", "2026-08-03")))
    assert "3 de ago de 2026" in words(PK.finding_page(built[0]))


def test_the_unit_ranking_marks_the_zones_that_run_no_compass_forms():
    text = words(PK.finding_page(of(S.MISSION)))
    assert "sin formularios de Compass" in text
    assert "zona piloto de Compass" in text


def test_a_zone_ranks_its_own_children_and_never_the_export_s():
    """`Pucón` is in the export under a zone the roster does not carry; a
    zone's page must not pick it up."""
    assert "Pucón" not in words(PK.finding_page(of(S.ZONE)))


# ── The funnel's maturity, on the page ───────────────────────────────────────

def test_an_immature_stage_draws_no_conversion_and_cannot_be_the_worst_step():
    """Over eleven days "Bautizados" is 0 because a baptism takes 133 days.
    "0% del paso anterior · la mayor caída" printed there would be the
    packet's worst single sentence."""
    drawing = PP.stage_bars(520, [("Encontradas", 100), ("Contactadas", 90),
                                  ("Bautizados", 0)],
                            mature=[True, True, False])
    strings = [c.text for c in drawing.contents if hasattr(c, "text")]
    assert "aún madurando" in strings
    # The 100 -> 0 step loses everybody and is still not the widest drop, and
    # draws no conversion at all: the only one on the chart is the real step.
    conversions = [s for s in strings if "del paso anterior" in s]
    assert conversions == ["90% del paso anterior · la mayor caída"]


def test_a_mature_funnel_still_names_its_widest_drop():
    drawing = PP.stage_bars(520, [("Encontradas", 100), ("Contactadas", 40),
                                  ("Enseñándose", 35)])
    strings = [c.text for c in drawing.contents if hasattr(c, "text")]
    assert any("la mayor caída" in s for s in strings)


def test_the_change_rides_the_bar_instead_of_a_table_of_its_own():
    """A table repeating these counts to add one column cost a second sheet
    behind every zone and district in the packet."""
    plain = PP.stage_bars(520, [("Encontradas", 10), ("Contactadas", 8)])
    with_change = PP.stage_bars(520, [("Encontradas", 10), ("Contactadas", 8)],
                                changes=[(1, "+5%"), (-1, "-2%")])
    assert plain.height == with_change.height
    assert "+5%" in words(with_change) and "-2%" in words(with_change)


# ── M6 · the year ─────────────────────────────────────────────────────────────

def test_only_the_mission_gets_the_baptism_page():
    assert PK.baptism_page(of(S.MISSION))
    assert PK.baptism_page(of(S.ZONE)) == []
    assert PK.baptism_page(of(S.AREA)) == []


def test_the_baptism_page_names_both_figures_and_sums_neither():
    """Decision 21, in one place where a reader can see them together."""
    text = words(PK.baptism_page(of(S.MISSION)))
    assert "CERTIFICADA" in text
    assert "formulario semanal" in text
    assert "nunca se suman" in text


def test_the_open_month_is_kept_out_of_the_year_s_total_on_the_page():
    text = words(PK.baptism_page(of(S.MISSION)))
    assert "319 bautismos certificados hasta agosto" in text
    assert "sin cerrar" in text
    assert "No entra en la barra" in text


@pytest.mark.parametrize("gap,expected", [
    (10.0, "good"), (-32.3, "warn"), (-90.0, "bad"), (None, None),
])
def test_a_year_behind_by_one_month_s_work_is_amber_not_red(gap, expected):
    """32 behind of 527 in September is a year to push, not a year lost."""
    assert PK._pace_status(gap) == expected


def test_a_mission_with_no_certified_month_gets_no_baptism_page_figures():
    built, _ = models(baptisms={})
    text = words(PK.baptism_page(built[0]))
    assert "sin meses certificados" in text


# ── The data note ─────────────────────────────────────────────────────────────

def test_the_data_note_no_longer_claims_there_is_no_tableau_data():
    built, _ = models()
    text = words(PK.data_note(built))
    assert "Sin datos de Tableau en este paquete" not in text
    assert "Exportación de Tableau" in text


def test_the_data_note_carries_the_four_things_that_make_the_rest_safe():
    text = words(PK.data_note(models()[0]))
    assert "hasta el 17 de sep de 2026" in text            # where it reaches
    assert "Nunca se suman ni comparten una tabla" in text  # decision 34
    assert "no están en MISSION_ORG" in text                # decision 35
    assert "por nombre de área" in text                     # how they match


def test_the_data_note_explains_an_absent_section_rather_than_omitting_it():
    built, _ = models(export=T.read_export(span("2024-01-01", "2026-08-03")))
    text = words(PK.data_note(built))
    assert "Sin sección de hallazgo en este paquete" in text
    assert "no alcanza este período" in text


def test_the_sources_table_names_the_two_tableau_tabs():
    text = words(PK.data_note(models()[0]))
    assert "TABLEAU_DETAIL" in text and "TABLEAU_BAPTISMS" in text


# ── PHASE T'S ACCEPTANCE (decision 34) ───────────────────────────────────────

def test_no_tableau_page_ever_builds_a_metric_table(monkeypatch):
    """§4 T3: no Tableau figure in the same total or table as a form figure.

    `metric_table` is how every form-sourced figure in this packet is drawn —
    the Key Indicators and the nightly work, each row a `MetricLine` carrying
    an actual against a goal. A Tableau page that built one would be putting a
    finding count into the form's own table, which is the single most
    misleading thing this packet could do (decision 34).
    """
    built, _ = models()
    calls = []
    monkeypatch.setattr(PP, "metric_table",
                        lambda *a, **k: calls.append(a) or Spacer(0, 0))
    for model in built:
        PK.finding_page(model)
        PK.baptism_page(model)
    assert calls == []


def test_the_form_s_pages_never_build_a_tableau_block(monkeypatch):
    """And the other direction: nothing form-sourced reaches for the export."""
    built, data = models()
    calls = []
    for name in ("funnel", "channel_mix", "top_sources", "zone_rows"):
        monkeypatch.setattr(T, name,
                            lambda *a, _n=name, **k: calls.append(_n) or ())
    for model in built:
        PK.at_a_glance(model, weekly_ok=True, weekly_sure=True)
        PK.key_indicator_page(model, weekly_ok=True, weekly_sure=True)
        PK.nightly_page(model, data.nightly_goals)
        PK.week_page(model)
    assert calls == []


def test_the_whole_packet_still_builds_with_the_finding_pages_in_it():
    built, data = models()
    pdf = PK.build_packet(built, data.roster, data.nightly_goals)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000
