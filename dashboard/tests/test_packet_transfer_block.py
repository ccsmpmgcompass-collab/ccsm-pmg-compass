"""The transfer in progress, in its own block — PLAN-2026-10-13 step 2.1 (C7).

The tablero is a closed-period table: a month's review never prints another
period's forecast beside it. Under it, on the mission and zone pages, the
transfer in progress AT BUILD TIME, in one of three shapes:

* running (2+ complete weeks, 1+ left): *Termina en* and *Falta por semana*;
* starting (under 2 complete weeks, e.g. the December council when 2026-8
  starts 30 Nov): "Cómo empieza", how the last transfer closed against its
  full goal, and the new one's goal per week;
* ended (no week left): the closed result.
"""

from datetime import date

import pandas as pd

from app.reports import model as M
from app.reports import packet as PK
from app.reports import summary as SM
from tests.test_packet_mission import BAUT, NEW, SACR, _data
from tests.test_packet_tableau import words

#: 2026-5's goals as well as 2026-6's, and one 2026-5 week of reports.
GOALS = pd.DataFrame(
    [{"area": a, "transfer_start": start, NEW: 120, SACR: 48, BAUT: 6}
     for a in ("A1", "A2", "B1") for start in ("2026-07-27", "2026-09-07")])
WEEKLY = pd.DataFrame([
    {"_week": "2026-09-06", "_area": "A1", NEW: 200, SACR: 10, BAUT: 1},
    {"_week": "2026-09-13", "_area": "A1", NEW: 20, SACR: 4, BAUT: 1},
    {"_week": "2026-09-13", "_area": "B1", NEW: 30, SACR: 6, BAUT: 0},
    {"_week": "2026-09-20", "_area": "A1", NEW: 10, SACR: 2, BAUT: 0},
])


def _built(today, key=None):
    data = _data(today=today, transfer_goals=GOALS, weekly_ki=WEEKLY)
    return M.build_all(key or "this_transfer", data=data)


def test_the_tablero_no_longer_carries_the_forecast_columns():
    mission = _built(date(2026, 9, 21))[0]
    tablero = PK.tablero_block(mission)
    table = next(f for f in tablero if f.__class__.__name__ == "Table")
    assert len(table._cellvalues[0]) == 8          # no Termina en / Falta


def test_two_complete_weeks_and_some_left_finish_forward():
    built = _built(date(2026, 9, 21))
    mission = built[0]
    assert mission.forward.transfer_state == M.TRANSFER_RUNNING
    text = words(PK.transfer_block(mission))
    assert "El traslado en curso" in text and "2026-6" in text
    assert "2 de 6 semanas completas" in text
    assert "Termina en" in text and "Falta" in text
    norte = next(m for m in built if m.scope.name == "Norte")
    assert "Termina en" in words(PK.transfer_block(norte))


def test_under_two_weeks_it_shows_how_the_last_transfer_closed():
    """The December-council case: one complete week of 2026-6. 2026-5 closed
    on 200 new people against a full goal of 360 (three areas × 120): 56%,
    printed and uncoloured. 2026-6's goal is 360 over six weeks: 60 a week."""
    built = _built(date(2026, 9, 15))
    mission = built[0]
    fwd = mission.forward
    assert fwd.transfer_state == M.TRANSFER_STARTING
    assert fwd.previous_transfer == "2026-5"
    text = words(PK.transfer_block(mission))
    assert "Cómo empieza 2026-6" in text
    assert "cómo cerró 2026-5" in text
    assert "200" in text and "360" in text and "56%" in text
    assert "60,0" in text
    assert "Termina en" not in text
    said = " ".join(SM.whats_coming(mission))
    assert "El traslado 2026-5 cerró con" in said
    assert "2026-6 recién empieza" in said
    assert "al mejor ritmo reciente" not in said


def test_a_new_transfer_without_goals_says_so():
    goals = GOALS[GOALS["transfer_start"] == "2026-07-27"]
    data = _data(today=date(2026, 9, 15), transfer_goals=goals,
                 weekly_ki=WEEKLY)
    mission = M.build_all("this_transfer", data=data)[0]
    text = words(PK.transfer_block(mission))
    assert "sin meta" in text and "todavía no está guardada" in text


def test_a_transfer_with_no_week_left_prints_its_closed_result():
    """The schedule runs out after 2026-6, so on 20 October it has ended."""
    mission = _built(date(2026, 10, 20), key="last_month")[0]
    assert mission.forward.transfer_state == M.TRANSFER_ENDED
    text = words(PK.transfer_block(mission))
    assert "El traslado 2026-6" in text and "terminado" in text
    assert "Cerró en" in text and "Termina en" not in text


def test_a_district_has_no_transfer_block():
    built = _built(date(2026, 9, 21))
    district = next(m for m in built if m.scope.level == "district")
    assert PK.transfer_block(district) == []
