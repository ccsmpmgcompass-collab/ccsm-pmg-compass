# -*- coding: utf-8 -*-
"""Phase T step T4 — the packet's finding pages, and Phase T's acceptance.

§4 T3's acceptance is that no Tableau figure ever appears in the same total or
table as a form figure (decision 34). That is the last test here, and it is
checked structurally — the finding and baptism pages are asserted never to
build a metric table — rather than by reading the rendered text, because a
page can name both figures honestly (decision 21 requires it) and only a
shared TOTAL is the thing decision 34 forbids.
"""

import re
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


def models(*, export=None, detail=None, baptisms=CERTIFIED, windows=(),
           period_key=P.DEFAULT_PERIOD):
    data = M.ReportData(
        roster=ROSTER, today=date(2026, 9, 21), cycles=[CYCLE],
        tableau_detail=DETAIL if detail is None else detail,
        tableau_export=(export if export is not None
                        else T.read_export(span("2024-01-01", "2026-09-17"))),
        tableau_maturity={"Attended Church": 33.0, "Baptism Date Set": 52.0,
                          "Baptized": 133.0},
        tableau_reconciliation=T.reconcile(DETAIL, S._clean(ROSTER)),
        baptisms_by_month=baptisms, annual_goal=527,
        baptisms_open=("2026-09", 19, date(2026, 9, 21)),
        baptism_windows=windows)
    return M.build_all(period_key, data=data), data


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

def test_the_mission_page_says_it_counts_ten_zones_and_the_rest_count_four():
    """Decision 34's hard case. Nothing else in the packet changes population
    from one page to the next, so it is said outright."""
    text = words(PK.data_note(models()[0]))
    assert "Tableau las 10" in text
    assert "sólo sus áreas del organigrama" in text


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


def test_the_two_figures_differ_by_scope_not_by_missionaries_skipping_it():
    """AUDIT-2026-10-06 C3. The packet said the two disagree because "los
    misioneros no siempre anotan el campo" — retracted 2026-10-02: the
    certified figure counts every zone, the form only the pilot's, and like
    for like they agree. Said on the baptism page and on page 3 alike."""
    mission = of(S.MISSION)
    for text in (words(PK.baptism_page(mission)),
                 PK._two_baptism_figures(mission)):
        assert "no siempre" not in text
        assert "todas las zonas de la misión" in text
        assert "del piloto" in text
        assert "las 1 zonas" not in text       # this roster has one zone


def test_the_open_month_is_kept_out_of_the_year_s_total_on_the_page():
    text = words(PK.baptism_page(of(S.MISSION)))
    assert "319" in text          # the closed months; tile labels are tracked
    assert "sin cerrar" in text
    assert "no en el ritmo ni en la proyección" in text


# ── M6 · the period leads (decisions 41, 42) ──────────────────────────────────

#: What the nightly job would have stored for "Este traslado" on 2026-09-21.
TRANSFER_WINDOW = ((date(2026, 9, 7), date(2026, 9, 21), 17),)


def _mission(**kw):
    built, _ = models(**kw)
    return next(m for m in built if m.scope.level == S.MISSION)


def test_the_page_leads_with_the_period_s_own_certified_figure():
    flow = PK.baptism_page(_mission(windows=TRANSFER_WINDOW))
    assert isinstance(flow[0], PP.SectionHead)
    assert flow[0].label == "Bautismos · 2026-6"
    lead = words(flow[:4])
    assert "17" in lead
    assert "7 de sep - 21 de sep de 2026" in lead
    # The year to date beside it: the closed months and September so far.
    assert "338" in lead
    m = _mission(windows=TRANSFER_WINDOW)
    tiles = PK._period_tiles(m.tableau.baptisms, m.period)
    assert [(t.label, t.value) for t in tiles] == [
        ("En este traslado", "17"), ("En lo que va de 2026", "338")]


def test_the_year_follows_as_context_under_its_own_head():
    flow = PK.baptism_page(_mission(windows=TRANSFER_WINDOW))
    heads = [f.label for f in flow if isinstance(f, PP.SectionHead)]
    assert heads[:2] == ["Bautismos · 2026-6",
                         "Bautismos 2026: cómo cierra el año"]


def test_a_period_with_no_capture_prints_a_dash_and_says_why():
    flow = PK.baptism_page(_mission(windows=()))
    lead = words(flow[:4])
    assert "sin cifra certificada" in lead
    assert "No hay cifra certificada de bautismos para 2026-6" in lead
    assert "sólo cubre las zonas del piloto" in lead
    assert "no siempre" not in lead


def test_a_capture_a_night_behind_says_how_many_days_it_covers():
    behind = ((date(2026, 9, 7), date(2026, 9, 20), 16),)
    lead = words(PK.baptism_page(_mission(windows=behind))[:5])
    assert "14 de 15 días del período" in lead


def test_the_year_period_splits_into_closed_and_open_months():
    flow = PK.baptism_page(_mission(period_key=P.YEAR))
    lead = words(flow[:5])
    assert "338" in lead          # 319 closed + 19 September
    assert "319" in lead and "19" in lead
    assert "septiembre, todavía sin cerrar" in lead
    assert "Son 319 de meses cerrados y 19 de septiembre" in lead


def test_the_data_note_says_where_the_period_s_baptisms_came_from():
    built, _ = models(windows=TRANSFER_WINDOW)
    text = words(PK.data_note(built))
    assert "Bautismos de 2026-6: 17 certificados por Tableau" in text
    # Plain words in the sentence; the tab only in the source column, in
    # small type (AUDIT-2026-10-06 M4).
    assert "captura por período" in text
    assert "pestaña TABLEAU_BAPTISM_WINDOWS" in text
    assert "decisión" not in text


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
    assert "nunca se suma ni comparte una tabla" in text    # decision 34
    assert "no están en el organigrama" in text             # decision 35
    assert "por nombre de área" in text                     # how they match


def test_the_data_note_says_how_far_an_old_export_reaches():
    """Decision 32's point, kept: a reader must be able to see the export
    stops short."""
    built, _ = models(export=T.read_export(span("2024-01-01", "2026-08-03")))
    text = words(PK.data_note(built))
    assert "hasta el 3 de ago de 2026" in text


def test_the_sources_table_names_the_two_tableau_tabs():
    text = words(PK.data_note(models()[0]))
    assert "pestaña TABLEAU_DETAIL" in text and "pestaña TABLEAU_BAPTISMS" in text


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
        PK.pipeline_block(model)
        PK.levers_block(model)
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
        PK.tablero_block(model)
        PK.nightly_page(model, data.nightly_goals)
        PK.trend_block(model)
    assert calls == []


def test_the_whole_packet_still_builds_with_the_finding_pages_in_it():
    built, data = models()
    pdf = PK.build_packet(built, data.roster, data.nightly_goals)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000


JARGON = re.compile(r"decisi[oó]n(es)? \d|MISSION_ORG|COMPASS_CCSM|AGENT_CONFIG"
                    r"|CCSM_Agent|WEEKLY_[A-Z_]+|TABLEAU_[A-Z_]+|DAILY_LOG"
                    r"|AREA_TRANSFER_GOALS|\bSCORES\b")


def test_no_page_speaks_developer_language():
    """AUDIT-2026-10-06 M4: "decisión 42", MISSION_ORG, COMPASS_CCSM and tab
    names were printed for the president. A tab name may appear only as the
    small "pestaña X" line under a source in the data note."""
    built, _ = models(windows=TRANSFER_WINDOW)
    mission = next(m for m in built if m.scope.level == S.MISSION)
    text = " ".join(
        [words(PK.unit_pages(m, {})) for m in built]
        + [words(PK.how_to_read(mission, PK.sections_for(built))),
           words(PK.data_note(built))])
    leftover = [m.group(0) for m in JARGON.finditer(text)
                if not text[max(0, m.start() - 8):m.start()].endswith("pestaña ")]
    assert not leftover, leftover


# ── Who found them, back on the president's pages (2026-10-07) ────────────────

def test_the_mission_prints_who_found_them_and_from_where():
    """Phase 3 retired it with the window-funnel pages and no decision asked
    for that: it is the one place the packet says how little of the finding
    comes from members."""
    text = words(PK.finding_mix_block(of(S.MISSION)))
    assert "Quién las encontró y de dónde" in text
    assert "Miembro" in text
    assert "10 zonas" in text          # the mission's block is all ten


def test_a_zone_gets_who_found_them_as_one_sentence_not_a_section():
    """A zone's section cost it a third sheet; its opening carries the same
    in one line."""
    zone = of(S.ZONE)
    assert PK.finding_mix_block(zone) not in ([], None)   # data is there
    assert "Quién las encontró y de dónde" not in words(PK.zone_pages(zone, None))
    sentence = PK._mix_sentence(zone)
    assert sentence.startswith("Quién las encontró:")
    assert "miembros" in sentence and "(Tableau)." in sentence
    assert sentence in words(PK.opening(zone))


def test_no_finding_data_prints_no_mix():
    built, _ = models(detail=people([]))
    mission = next(m for m in built if m.scope.level == S.MISSION)
    assert PK.finding_mix_block(mission) == []


def test_last_month_s_data_note_says_weeks_are_not_days():
    """PLAN-2026-10-13 1.2: on 21 September "Mes pasado" is August, whose form
    weeks run 27 July – 30 August while its certified baptisms count 1–31
    August."""
    built, _ = models(period_key=P.LAST_MONTH)
    text = words(PK.data_note(built))
    assert "Las semanas no son los días del mes" in text
    assert "terminan en agosto 2026 (27 de jul - 30 de ago de 2026)" in text
    assert "los bautismos certificados, los días del mes" in text
    assert "Las semanas no son" not in words(PK.data_note(models()[0]))
