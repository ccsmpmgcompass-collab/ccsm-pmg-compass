"""Desde el último consejo — PLAN-2026-10-13 step 3.2 (decision 63).

No commitments tab: the packet remembers itself. Last month's packet is
rebuilt from today's sheet, and the mission page shows whether its focus
units and its zone questions moved, and how the year's landing moved.
"""

from datetime import date

import pandas as pd
import pytest

from app.reports import focus as FC
from app.reports import model as M
from app.reports import packet as PK
from app.reports import periods as P
from app.reports import scope as S
from app.reports import summary as SM
from tests.test_packet_tableau import words
from tests.test_report_model_ki import (LESSONS, NEW, ROSTER, _data,
                                        _ki_goals)
from tests.test_report_tableau_blocks import people, person

NOV = date(2026, 11, 2)
CYCLES = [
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
     "weeks": 6, "status": "Actual"},
    {"number": "2026-7", "start": date(2026, 10, 19), "end": date(2026, 11, 29),
     "weeks": 6, "status": "Actual"},
]
SEP = P.weeks_ending_in(date(2026, 9, 1), date(2026, 9, 30))
OCT = P.weeks_ending_in(date(2026, 10, 1), date(2026, 10, 31))
# September: D1 (A1, A2) silent, the rest file. October: everyone files,
# each short of the 10 a week the goal asks.
WEEKLY = pd.DataFrame(
    [{"_week": w.isoformat(), "_area": a, NEW: 10, LESSONS: 5}
     for w in SEP for a in ("A3", "B1", "B2")]
    + [{"_week": w.isoformat(), "_area": a, NEW: 8, LESSONS: 4}
       for w in OCT for a in ("A1", "A2", "A3", "B1", "B2")])
GOALS = pd.DataFrame(
    [{"area": a, "transfer_start": c["start"].isoformat(), NEW: 60,
      LESSONS: 30} for c in CYCLES for a in ROSTER["Area_Name"]]
    + [{"area": a, "transfer_start": "2026-07-27", NEW: 60, LESSONS: 30}
       for a in ROSTER["Area_Name"]])


def _nov(**over):
    kw = dict(weekly_ki=WEEKLY, transfer_goals=GOALS, today=NOV,
              cycles=CYCLES, ki_keys=(NEW, LESSONS), anchor=OCT[-1])
    kw.update(over)
    return _data(**kw)


def _mission(d, key=P.LAST_MONTH):
    return next(m for m in M.build_all(key, data=d)
                if m.scope.level == S.MISSION)


def test_the_last_council_is_the_month_before_mes_pasado():
    c = _mission(_nov()).changes.council
    assert c.then_label == "septiembre 2026"
    assert c.then_day == date(2026, 10, 2)
    assert c.reason == ""


def test_its_focus_is_september_s_rebuilt_and_followed_into_october():
    """D1 was silent all September, so it led that council's list; in
    October every area filed, so its part of the shortfall shrank."""
    d = _nov()
    c = _mission(d).changes.council
    sep = P.resolve(P.LAST_MONTH, date(2026, 10, 2), CYCLES)
    then = M._focus(d, d.mission, sep, None)
    assert [f.name for f in c.focus] == [r.name for r in then[:3] if r.share]
    first = c.focus[0]
    assert first.name == "D1" and first.silent_then
    assert first.share_now < first.share_then


def test_a_council_before_the_form_has_nothing_to_remember():
    """On 21 September "Mes pasado" is August, the form's launch month: the
    block says so instead of rebuilding a month nobody reported."""
    d = _data()
    c = _mission(d).changes.council
    assert c.then_label == "" and c.focus == ()
    flow = PK.since_block(_mission(d))
    assert "No hay consejo anterior que recordar" in words(flow)


def test_only_mes_pasado_remembers_a_council():
    d = _nov()
    assert _mission(d, P.THIS_TRANSFER).changes.council is None
    assert PK.since_block(_mission(d, P.THIS_TRANSFER)) == []


def test_the_block_and_the_resumen_say_it_with_today_s_reports():
    m = _mission(_nov())
    text = words(PK.since_block(m))
    assert "Desde el último consejo" in text
    assert "septiembre 2026 contra octubre 2026" in text
    assert "rehecho con la hoja de hoy" in text
    assert "se corre un mes" in text
    line = SM.council_line(m)
    assert line.startswith("Desde el último consejo (septiembre 2026)")
    assert "D1 de " in line
    assert line in SM.what_changed(m)


def test_a_funnel_step_is_the_share_of_those_entering_it():
    row = FC.FunnelRow(name="x", found=200, reached=(100, 40, 4))
    assert row.step(0) == pytest.approx(50)
    assert row.step(1) == pytest.approx(40)
    assert row.step(2) == pytest.approx(10)
    assert FC.FunnelRow(name="y", found=200, reached=(10, 1)).step(1) is None


def test_a_funnel_rebuilt_a_month_back_counts_only_what_had_happened():
    """Found in June: on 2 October they are the mature cohort (90-180 days),
    and the 20 baptised on 20 October had not been baptised yet."""
    detail = people(
        [person("2026-06-10", area="A1", zone="Norte",
                first_contact_attempt_event_date="2026-06-11",
                confirmation_date=("2026-10-20" if i < 20 else ""))
         for i in range(150)])
    d = _nov(tableau_detail=detail)
    then = M._funnel(d, d.mission, date(2026, 10, 2))
    now = M._funnel(d, d.mission)
    baptized = len(then.stages) - 1
    assert then.mission.found == now.mission.found == 150
    assert then.mission.reached[baptized] == 0
    assert now.mission.reached[baptized] == 20
