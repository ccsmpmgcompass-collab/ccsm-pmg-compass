# -*- coding: utf-8 -*-
"""Phase T step T3 — the finding blocks.

The funnel, the channel mix, the top sources, the unit rankings and the year's
baptisms. The load-bearing test here is the maturity one: the funnel is a
COHORT reading, so a young window's bottom stages are empty by construction,
and a council packet that printed "Bautizados: 0" beside a September baptism
figure of 19 would be contradicting itself on one page.
"""

from datetime import date

import pandas as pd
import pytest

from app.analytics import finding_funnel as FF
from app.reports import periods as P
from app.reports import scope as S
from app.reports import tableau as T

from tests.test_report_tableau_gate import period, span


def people(rows) -> pd.DataFrame:
    """A Detail frame. Each row is a dict of the columns that test cares about;
    absent milestone columns are filled with NaT, as the real export does."""
    cols = ["event_date_selected", "latest_zone_name", "latest_district_name",
            "latest_teaching_area_name", "finding_source",
            "finding_category_(copy)"]
    cols += [c for _, c in FF.FUNNEL_STAGES if c]
    return pd.DataFrame([{c: r.get(c, "") for c in cols} for r in rows])


def person(found, *, area="El Mirador", zone="Angol", source="Contacting in Public",
           category="Missionary", **milestones):
    row = {"event_date_selected": found, "latest_zone_name": zone,
           "latest_teaching_area_name": area, "finding_source": source,
           "finding_category_(copy)": category}
    row.update(milestones)
    return row


#: One transfer cycle in `periods.load_cycles`' own shape.
CYCLE = {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
         "weeks": 6, "status": "Active"}

WINDOW = T.clip(period("2026-09-07", "2026-09-17"),
                T.read_export(span("2024-01-01", "2026-09-17")))


# ── The vocabulary ────────────────────────────────────────────────────────────

def test_the_packet_and_the_embudo_page_use_the_same_spanish():
    """`tableau.py` cannot import `app.i18n` — that package pulls in Streamlit
    and the report layer is pure — so the strings are repeated. This is the
    test that stops the two copies drifting."""
    from app.i18n.es import ES

    shared = {**T.STAGE_LABELS, **T.CATEGORY_LABELS}
    checked = 0
    for english, spanish in shared.items():
        if english in ES:
            assert ES[english] == spanish, english
            checked += 1
    assert checked >= 10, "expected the shared vocabulary to overlap"


def test_a_finding_source_nobody_has_translated_prints_as_written():
    """Free text from Tableau. A source the mission has never used before
    should appear on the page, not turn into "Desconocido"."""
    assert T.finding_source_label("Hot Air Balloon") == "Hot Air Balloon"
    assert T.finding_source_label("English Class") == "Clase de inglés"


# ── Maturity ──────────────────────────────────────────────────────────────────

def test_maturity_is_measured_from_the_export_not_hardcoded():
    det = people([
        person("2026-01-01", first_contact_attempt_event_date="2026-01-03"),
        person("2026-01-01", first_contact_attempt_event_date="2026-01-05"),
        person("2026-01-01", first_contact_attempt_event_date="2026-01-11"),
        person("2026-01-01", first_contact_attempt_event_date="2026-01-21"),
    ])
    lags = T.maturity_days(det)
    assert lags["Contact Attempted"] == pytest.approx(12.5)   # p75 of 2,4,10,20


def test_a_stage_slower_than_the_window_keeps_its_count_and_loses_its_rate():
    """Decision 25 says no compression, so the row stays. It just stops
    claiming a direction it cannot support."""
    det = people([person("2026-09-10", confirmation_date="2026-09-12")])
    before = people([person("2026-08-30")])
    stages = T.funnel(det, WINDOW, before=before,
                      maturity={"Baptized": 133.0, "Contact Attempted": 6.0})
    baptized = next(s for s in stages if s.label == "Bautizados")
    assert baptized.count == 1
    assert not baptized.mature and baptized.lag_days == 133.0
    assert baptized.change is None


def test_a_stage_the_window_outlasts_keeps_its_direction():
    det = people([person("2026-09-10", first_contact_attempt_event_date="2026-09-11")] * 3)
    before = people([person("2026-08-30", first_contact_attempt_event_date="2026-08-31")] * 2)
    stages = T.funnel(det, WINDOW, before=before, maturity={"Contact Attempted": 6.0})
    row = next(s for s in stages if s.label == "Intento de Contacto")
    assert row.mature and row.change == pytest.approx(50.0)


def test_the_maturity_note_names_the_stages_it_is_about():
    det = people([person("2026-09-10")])
    block = T.build_block(det, T.read_export(span("2024-01-01", "2026-09-17")),
                          period("2026-09-07", "2026-09-17"),
                          maturity={"Baptized": 133.0})
    assert "Bautizados tardan más que la ventana" in block.maturity_note
    # Only the mission has a baptism page to send a reader to (R3.2).
    assert "página de bautismos" not in block.maturity_note
    mission = T.build_block(det, T.read_export(span("2024-01-01", "2026-09-17")),
                            period("2026-09-07", "2026-09-17"),
                            maturity={"Baptized": 133.0}, whole_mission=True)
    assert "página de bautismos" in mission.maturity_note


def test_a_funnel_with_nothing_slow_in_it_says_nothing_about_maturity():
    det = people([person("2026-09-10")])
    block = T.build_block(det, T.read_export(span("2024-01-01", "2026-09-17")),
                          period("2026-09-07", "2026-09-17"), maturity={})
    assert block.maturity_note == ""


# ── The blocks ────────────────────────────────────────────────────────────────

def test_the_funnel_reads_at_least_this_far_so_it_cannot_widen():
    """A person taught with no logged contact plainly was contacted;
    `finding_funnel` documents the bulge that taught this."""
    det = people([person("2026-09-10",
                         first_new_person_being_taught_date="2026-09-12")])
    counts = {s.label: s.count for s in T.funnel(det, WINDOW)}
    assert counts["Contactadas con Éxito"] == 1
    assert counts["Recibiendo Lecciones"] == 1


def test_the_channel_mix_is_translated_and_biggest_first():
    det = people([person("2026-09-10", category="Media")] * 3
                 + [person("2026-09-10", category="Missionary")] * 5)
    mix = T.channel_mix(det)
    assert [m.label for m in mix] == ["Misioneros", "Medios"]
    assert mix[0].share_of(8) == pytest.approx(62.5)


def test_top_sources_are_capped_and_ordered():
    det = people([person("2026-09-10", source="Contacting in Public")] * 4
                 + [person("2026-09-10", source="Member")] * 2
                 + [person("2026-09-10", source="Service")])
    rows = T.top_sources(det, limit=2)
    assert [r.label for r in rows] == ["Contacto en la calle", "Miembro"]


def test_every_zone_the_export_knows_appears_and_says_whether_it_is_a_pilot():
    """Decision 24: the six zones that run no Compass forms are on the
    mission's page, marked, so nobody reads them as zones that reported nothing."""
    det = people([person("2026-09-10", zone="Angol",
                         first_successful_contact_attempt_event_date="2026-09-11")] * 8
                 + [person("2026-09-10", zone="Villarrica")] * 4)
    rows = T.zone_rows(det, ["Angol"])
    assert {r.name for r in rows} == {"Angol", "Villarrica"}
    assert [r.roster for r in rows] == [False, True]      # weakest rate first
    assert rows[1].contact_rate == pytest.approx(100.0)


def test_a_child_with_no_finding_rows_keeps_its_row_at_the_bottom():
    """A unit nobody found anybody in is a finding, not an absence to drop."""
    roster = pd.DataFrame([{"Area_Name": "El Mirador", "Zone": "Angol",
                            "District": "D1"},
                           {"Area_Name": "Los Huertos", "Zone": "Angol",
                            "District": "D2"}])
    det = people([person("2026-09-10", area="El Mirador")])
    rows = T.unit_rows(det, S.district_scopes(roster))
    assert [r.name for r in rows] == ["D1", "D2"]
    assert rows[1].found == 0 and rows[1].contact_rate is None


# ── The gate, from the block's side ──────────────────────────────────────────

def test_a_refused_window_yields_a_block_that_carries_only_its_reason():
    det = people([person("2026-09-10")])
    block = T.build_block(det, T.read_export(span("2024-01-01", "2026-08-03")),
                          period("2026-09-07", "2026-09-21"))
    assert not block.present
    assert block.stages == () and block.mix == () and block.sources == ()
    assert "no alcanza este período" in block.reason


def test_the_mission_block_says_it_covers_more_of_the_mission_than_the_rest():
    """Decision 34's one hard case: the finding section counts ten zones while
    every form-sourced figure in the packet counts four."""
    det = people([person("2026-09-10")])
    export = T.read_export(span("2024-01-01", "2026-09-17"))
    whole = T.build_block(det, export, period("2026-09-07", "2026-09-17"),
                          whole_mission=True)
    scoped = T.build_block(det, export, period("2026-09-07", "2026-09-17"),
                           areas=["El Mirador"])
    assert "10 zonas" in whole.scope_note
    assert "Ninguna cifra de Tableau se suma" in whole.scope_note
    assert "MISSION_ORG" in scoped.scope_note


def test_a_scoped_block_drops_rows_from_areas_the_roster_does_not_carry():
    det = people([person("2026-09-10", area="El Mirador"),
                  person("2026-09-10", area="Caupolican")])
    block = T.build_block(det, T.read_export(span("2024-01-01", "2026-09-17")),
                          period("2026-09-07", "2026-09-17"),
                          areas=["El Mirador"])
    assert block.found == 1


# ── The year's baptisms (M6) ─────────────────────────────────────────────────

CERTIFIED = {"2026-01": 19, "2026-02": 37, "2026-03": 47, "2026-04": 44,
             "2026-05": 43, "2026-06": 46, "2026-07": 47, "2026-08": 36}


def test_the_year_reads_the_certified_months_and_stops_where_they_stop():
    """The live figures on 2026-09-21: 319 certified through August against a
    goal of 527."""
    bap = T.Baptisms(year=2026, goal=527, certified=CERTIFIED)
    assert bap.months == 8 and bap.total == 319
    assert bap.attainment == pytest.approx(60.5, abs=0.1)
    assert bap.gap == pytest.approx(-32.3, abs=0.1)
    assert bap.landing["value"] == pytest.approx(478.5, abs=0.1)
    assert "319 bautismos certificados hasta agosto" == bap.certified_label


def test_the_open_month_is_held_apart_from_the_certified_series():
    """Plotted as an ordinary point it draws the year collapsing every time the
    packet is built mid-month — the trap `get_mission_baptisms_by_month`
    already learned on 2026-09-19."""
    bap = T.Baptisms(year=2026, goal=527, certified=CERTIFIED, provisional=19,
                     provisional_through=date(2026, 9, 21))
    assert bap.total == 319                      # not 338
    assert bap.cumulative[8] is None             # September is not a point
    assert "19 más en el mes en curso" in bap.provisional_label
    assert "21 de sep" in bap.provisional_label
    assert "sin cerrar" in bap.provisional_label


def test_a_mission_with_no_annual_goal_gets_a_year_without_a_target():
    bap = T.Baptisms(year=2026, goal=None, certified=CERTIFIED)
    assert bap.pace is None and bap.attainment is None and bap.gap is None
    assert bap.total == 319


def test_a_year_with_nothing_captured_says_so_rather_than_printing_zero():
    bap = T.Baptisms(year=2026, goal=527, certified={})
    assert bap.total is None
    assert bap.certified_label == "sin meses certificados"
    assert bap.provisional_label == ""


# ── What the model hands the renderers ───────────────────────────────────────

def build(level, **kw):
    """One model over a tiny sheet, with a real export behind it."""
    roster = pd.DataFrame([{"Area_Name": "El Mirador", "Zone": "Angol",
                            "District": "D1"},
                           {"Area_Name": "Los Huertos", "Zone": "Angol",
                            "District": "D1"}])
    det = people([person("2026-09-10", area="El Mirador"),
                  person("2026-09-10", area="Los Huertos")])
    from app.reports import model as M

    data = M.ReportData(
        roster=roster, today=date(2026, 9, 21),
        cycles=[CYCLE],
        tableau_detail=det,
        tableau_export=T.read_export(span("2024-01-01", "2026-09-17")),
        tableau_maturity={"Baptized": 133.0},
        baptisms_by_month=CERTIFIED, annual_goal=527, **kw)
    per = P.resolve(P.THIS_TRANSFER, data.today, data.cycles)
    scope = {S.MISSION: S.mission_scope(roster),
             S.ZONE: S.zone_scopes(roster)[0],
             S.AREA: S.area_scopes(roster)[0]}[level]
    return M.build_report(scope, per, P.comparison_for(per, data.today,
                                                       data.cycles), data)


def test_an_area_gets_no_finding_block_at_all():
    """Its half page has 338pt and eleven days of one companionship's finding
    is four people. A funnel drawn over four people is decoration."""
    assert build(S.AREA).tableau is None


def test_the_mission_gets_the_whole_export_and_the_year_s_baptisms():
    block = build(S.MISSION).tableau
    assert block.present and block.whole_mission
    assert block.baptisms is not None and block.baptisms.total == 319
    assert block.found == 2


def test_a_zone_is_roster_scoped_and_carries_no_baptism_block():
    block = build(S.ZONE).tableau
    assert block.present and not block.whole_mission
    assert block.baptisms is None
    assert block.unit_noun == "distritos"


def test_a_mission_with_no_export_stored_reports_the_absence_not_an_error():
    from app.reports import model as M

    roster = pd.DataFrame([{"Area_Name": "El Mirador", "Zone": "Angol",
                            "District": "D1"}])
    data = M.ReportData(roster=roster, today=date(2026, 9, 21),
                        cycles=[CYCLE],
                        tableau_export=T.read_export(pd.DataFrame()))
    per = P.resolve(P.THIS_TRANSFER, data.today, data.cycles)
    block = M.build_report(S.mission_scope(roster), per,
                           P.comparison_for(per, data.today, data.cycles),
                           data).tableau
    assert not block.present
    assert block.reason == "no hay ninguna exportación de Tableau guardada"


def test_the_window_is_resolved_once_for_every_scope_not_once_per_scope():
    from app.reports import model as M

    roster = pd.DataFrame([{"Area_Name": "El Mirador", "Zone": "Angol",
                            "District": "D1"}])
    data = M.ReportData(roster=roster, today=date(2026, 9, 21),
                        cycles=[CYCLE],
                        tableau_export=T.read_export(span("2024-01-01", "2026-09-17")))
    per = P.resolve(P.THIS_TRANSFER, data.today, data.cycles)
    first = data.tableau_windows(per)
    assert data.tableau_windows(per) is first
