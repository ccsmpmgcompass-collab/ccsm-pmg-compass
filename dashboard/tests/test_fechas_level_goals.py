"""Fechas are a level — PLAN-2026-10-17-fechas-level.md step 1 (L1, L2).

"Amigos con Fecha Bautismal" is how many friends hold a date that week, and
leadership's goal for it is a level to hold. So the transfer recommender gives
it the weekly stretch itself, never multiplied by the cycle's weeks, and the
tab stores that level. The readers that SUM goals over a cycle get the level
times the cycle's weeks back (the bridge), so they print what they printed
before until steps 2-6 teach them to read a level.
"""

from datetime import date

import pandas as pd
import pytest

import app.db.goals_queries as gq
import app.db.queries as q
from app.config import metric_catalog as mc
from tests.test_transfer_goal_recommendation import (NIGHTLY, QUESTIONS,
                                                     WEEKLY)

FECHA = "ki_baptismal_date_real"
LEVEL_QUESTIONS = pd.concat([QUESTIONS, pd.DataFrame([
    {"Metric_Key": FECHA,
     "Metric_Display_Name": "Amigos con Fecha Bautismal (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"}])],
    ignore_index=True)
# Los Huertos holds 3, 4 and 3 friends with a date: a mean of 3,33.
LEVEL_WEEKLY = WEEKLY.assign(**{FECHA: [3, 4, 3]})


def test_only_fechas_is_a_level():
    assert mc.LEVEL_METRICS == frozenset({FECHA})
    assert mc.is_level(FECHA)
    for key in ("ki_rc_at_church_real", "ki_friends_sacrament_real",
                "ki_new_people_real"):
        assert not mc.is_level(key)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(
        "app.db.sheets_client._read_tab_cached",
        lambda tab, header_marker=None: (
            LEVEL_QUESTIONS.copy() if tab == "QUESTIONS_CONFIG"
            else pd.DataFrame()))
    monkeypatch.setattr(q, "get_weekly_ki", lambda: NIGHTLY.copy())
    monkeypatch.setattr(q, "get_weekly_form_data", lambda: LEVEL_WEEKLY.copy())
    monkeypatch.setattr(q, "get_question_metrics", lambda: [
        (r["Metric_Key"], r["Metric_Display_Name"], r["Form_Type"])
        for _, r in LEVEL_QUESTIONS.iterrows()])
    monkeypatch.setattr(q, "get_rec_stretch_pct", lambda: 10)
    mc.clear_cache()
    q.get_recommended_transfer_goals.clear()
    yield
    q.get_recommended_transfer_goals.clear()
    mc.clear_cache()


def test_the_recommender_gives_a_level_not_a_six_week_total(live):
    """ceil(3,33 x 1,1) = 4 friends with a date to hold — not ceil(3,33 x
    1,1 x 6) = 22. Flows still scale by the cycle (sacrament: 2 a week)."""
    for weeks in (5.0, 6.0, 7.0):
        rec = q.get_recommended_transfer_goals("Los Huertos", weeks)
        assert rec[FECHA] == 4
    assert q.get_recommended_transfer_goals(
        "Los Huertos", 6.0)["ki_friends_sacrament_real"] == 14


# ── the cutover: old cycles keep their totals, new ones store levels ────────

T6, T7 = "2026-09-07", "2026-10-19"
CYCLES = [{"number": "2026-6", "start": date(2026, 9, 7),
           "end": date(2026, 10, 18), "weeks": 6, "status": "Actual"},
          {"number": "2026-7", "start": date(2026, 10, 19),
           "end": date(2026, 11, 29), "weeks": 6, "status": "Scheduled"}]


@pytest.fixture
def sheet(monkeypatch):
    """2026-6 as the old recommender saved it (fecha = 6-week totals), 2026-7
    as a level."""
    state = {"rows": pd.DataFrame([
        {"area": "A1", "transfer_start": T6, "transfer_number": "2026-6",
         "ki_new_people_real": "30", FECHA: "29", "set_by": "", "notes": ""},
        {"area": "A2", "transfer_start": T6, "transfer_number": "2026-6",
         "ki_new_people_real": "12", FECHA: "4", "set_by": "", "notes": ""},
        {"area": "A1", "transfer_start": T7, "transfer_number": "2026-7",
         "ki_new_people_real": "36", FECHA: "4", "set_by": "", "notes": ""}])}

    def write(tab, rows):
        state["rows"] = pd.DataFrame(rows[1:], columns=rows[0])

    monkeypatch.setattr(gq, "read_tab",
                        lambda tab, header_marker=None: state["rows"].copy())
    monkeypatch.setattr(gq, "overwrite_tab", write)
    monkeypatch.setattr(gq, "_metric_cols",
                        lambda: ["ki_new_people_real", FECHA])
    monkeypatch.setattr("app.utils.transfer_helpers.transfer_cycles",
                        lambda rows=None: CYCLES)
    return state


def test_the_cutover_is_2026_7():
    assert gq.LEVELS_STORED_FROM == date(2026, 10, 19)
    assert not gq.stores_levels(T6) and gq.stores_levels(T7)


def test_the_metas_box_always_reads_a_level(sheet):
    assert gq.get_area_transfer_goal("A1", T6)[FECHA] == 5      # 29 / 6
    assert gq.get_area_transfer_goal("A2", T6)[FECHA] == 1      # 4 / 6, at least 1
    assert gq.get_area_transfer_goal("A1", T7)[FECHA] == 4
    assert gq.get_area_transfer_goal("A1", T6)["ki_new_people_real"] == 30


def test_summed_readers_get_the_totals_they_had(sheet):
    """History untouched (29 + 4); 2026-7's level times its six weeks."""
    assert gq.group_goal_totals(T6) == {"ki_new_people_real": 42.0,
                                        FECHA: 33.0}
    by_cycle = gq.goals_by_cycle_start()
    assert by_cycle[date(2026, 9, 7)][FECHA] == 33.0
    assert by_cycle[date(2026, 10, 19)][FECHA] == 24.0
    every = gq.all_area_transfer_goals()
    assert sorted(every[FECHA].tolist()) == [4.0, 24.0, 29.0]
    # A flow is never touched by the bridge.
    assert sorted(every["ki_new_people_real"].tolist()) == [12.0, 30.0, 36.0]


def test_a_level_saved_for_each_side_of_the_cutover(sheet):
    gq.upsert_area_transfer_goal("A2", T7, {FECHA: 3, "ki_new_people_real": 40},
                                 set_by="x")
    gq.upsert_area_transfer_goal("A2", T6, {FECHA: 2, "ki_new_people_real": 12},
                                 set_by="x")
    rows = sheet["rows"].set_index(["area", "transfer_start"])
    assert rows.loc[("A2", T7), FECHA] == "3"        # a level, as typed
    assert rows.loc[("A2", T6), FECHA] == "12"       # 2 x 6, as 2026-6 stores it
    assert gq.get_area_transfer_goal("A2", T6)[FECHA] == 2
