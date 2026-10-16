"""Page 1, "La historia de este mes" — PLAN-2026-10-13 step 3.3 (C1).

Candidate findings, each sized as the part of its gap it moves, the three
largest printed as action titles with one number each, and a question per
finding for the council.
"""

from datetime import date
from types import SimpleNamespace as NS

import pytest

from app.reports import focus as FC
from app.reports import forecast as F
from app.reports import model as M
from app.reports import packet as PK
from app.reports import scope as S
from app.reports import story as ST
from tests.test_report_date_quality import LIVE

TODAY = date(2026, 10, 16)
MISSION = S.Scope(level=S.MISSION, name="Misión", areas=())


def _focus(name, zone, share, silent=0.0):
    return FC.FocusRow(scope=S.Scope(level=S.DISTRICT, name=name, areas=(), zone=zone),
                       share=share, cumulative=share, silent=silent)


def _model(**over):
    year = F.year_landing({f"2026-{m:02d}": 39 for m in range(1, 10)}, 2026,
                          goal=527)
    gap = F.YearGap(goal=527, low=59, high=82,
                    bets=(F.Bet("La mayor fuga de cada zona", 10, 38),
                          F.Bet("Las fechas de 91 a 180 días", 11, 20)))
    funnel = FC.MatureFunnel(
        start=TODAY, end=TODAY,
        rows=(FC.FunnelRow(name="Angol", found=1266, leak="fecha a bautismo",
                           leak_step=(4.7, 15.4), leak_index=5),),
        mission=FC.FunnelRow(name="la misión", found=14000))
    forward = M.Forward(
        year=year, gap=gap, dates=LIVE,
        levers=(FC.Lever(name="Angol", leak="fecha a bautismo",
                         baptisms=(2.0, 4.0)),))
    kw = dict(scope=MISSION, today=TODAY, forward=forward, funnel=funnel,
              reporting=M.Reporting(reported=131, possible=180),
              focus=(_focus("Los Confines", "Angol", 40.0, silent=30.0),
                     _focus("San Pedro 1", "San Pedro", 60.0, silent=29.0)),
              changes=None)
    kw.update(over)
    return NS(**kw)


def test_every_finding_is_sized_as_a_share_of_its_gap():
    found = {f.key: f for f in ST.candidates(_model())}
    assert found["gap"].weight == 100
    assert found["reporting"].weight == pytest.approx(59)
    # 11-20 old-date baptisms against a gap of 59-82: 15,5 of 70,5.
    assert found["dates"].weight == pytest.approx(15.5 / 70.5 * 100)
    assert found["gap"].unit == found["dates"].unit == ST.BAPTISMS
    assert found["reporting"].unit == ST.LEAD_GOAL


def test_the_three_largest_print_largest_first():
    keys = [f.key for f in ST.story(_model())]
    assert keys == ["gap", "reporting", "dates"]


def test_titles_are_conclusions():
    found = {f.key: f for f in ST.candidates(_model())}
    assert found["gap"].title.startswith("El año cierra en ")
    assert "faltan 59-82 para 527" in found["gap"].title
    assert found["reporting"].title == ("El 59% de lo que falta para la meta "
                                        "del liderazgo es de semanas sin "
                                        "informe")
    assert found["lever"].title == ("Angol bautiza 5 de cada 100 fechas; la "
                                    "misión, 15")
    assert found["dates"].title.startswith(
        "De cada 100 fechas fijadas entre junio y agosto, 13 terminaron en "
        "bautismo en seis semanas; en 2025, 23")


def test_the_lever_is_carried_to_31_december():
    lever = next(f for f in ST.candidates(_model()) if f.key == "lever")
    transfers = F.transfers_left(2026, TODAY)
    assert f"{round(2 * transfers)}-{round(4 * transfers)} bautismos más " \
           "hasta el 31 de dic" in lever.support


def test_reporting_at_target_is_no_finding():
    full = M.Reporting(reported=180, possible=180)
    assert ST.reporting_finding(_model(reporting=full)) is None


def test_a_year_at_its_goal_has_no_gap_finding():
    ahead = F.YearGap(goal=527, low=0, high=0)
    m = _model(forward=M.Forward(year=_model().forward.year, gap=ahead))
    assert ST.gap_finding(m) is None


def test_every_finding_asks_a_question_and_none_moves_527():
    for f in ST.candidates(_model()):
        assert f.question.startswith("¿") and f.question.endswith("?")
        for phrase in ("recalibr", "ajustar la meta", "cambiar la meta",
                       "bajar la meta"):
            assert phrase not in (f.title + f.support + f.question).lower()


def test_a_zone_level_model_tells_no_story():
    assert ST.story(_model(scope=S.Scope(level=S.ZONE, name="Angol", areas=()))) == ()


def test_the_council_finding_follows_last_month_s_first_unit():
    council = M.SinceCouncil(
        then_label="septiembre 2026",
        focus=(M.CouncilFocus(scope=S.Scope(level=S.DISTRICT, areas=(),
                                            name="Los Confines"),
                              share_then=16.4, share_now=15.0),))
    m = _model(changes=M.Changes(council=council))
    f = ST.council_finding(m)
    assert f.title == ("Desde el último consejo, Los Confines sigue con el "
                       "15% de lo que falta")
    assert f.weight == 15.0


def test_page_one_prints_the_story_the_questions_and_the_contents():
    from tests.test_packet_tableau import models, words
    built, _ = models()
    mission = next(m for m in built if m.scope.level == S.MISSION)
    text = words(PK.story_page(mission, PK.sections_for(built)))
    assert "La historia de este mes" in text
    assert "Para decidir en este consejo" in text
    assert "En este paquete" in text
    for f in ST.story(mission):
        assert f.title in text and f.question in text
