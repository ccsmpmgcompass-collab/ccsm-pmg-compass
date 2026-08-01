"""Saving Monthly Goals must actually store what was typed.

AREA_MONTHLY_GOALS had a fixed schema of Utah Provo's six Key Indicators —
gate | date_metric | new_found | pew | renew | member_lessons — and
upsert_area_monthly_goal took those six as keyword arguments. The Goals page
passed gate=_mv("gate") and so on.

Once the page started offering CCSM's seven KIs, every one of those six lookups
returned 0 and every CCSM value was dropped on the floor. The write succeeded,
the page printed "Monthly goals saved", and nothing the user typed was stored.
Silent data loss that looks exactly like success — the user would only discover
it by reopening the page later and finding their goals gone.

These tests round-trip through the sheet layer: write, read back, compare.
"""

import pandas as pd
import pytest

import app.db.goals_queries as gq
from app.config import metric_catalog as mc

QUESTIONS = pd.DataFrame([
    {"Metric_Key": "ki_new_people_real", "Metric_Display_Name": "Nuevas Personas (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "ki_new_people_meta", "Metric_Display_Name": "Nuevas Personas (Meta)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "ki_baptized_confirmed_real",
     "Metric_Display_Name": "Bautizados y Confirmados (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "contacts_attempted", "Metric_Display_Name": "Intentos de Contacto",
     "Form_Type": "NIGHTLY", "Data_Type": "NUMBER", "Active": "TRUE"},
])


@pytest.fixture
def sheet(monkeypatch):
    """An in-memory AREA_MONTHLY_GOALS that overwrite_tab really writes to."""
    state: dict = {"grid": []}

    def fake_read(tab_name, header_marker=None):
        if tab_name == "QUESTIONS_CONFIG":
            return QUESTIONS.copy()
        if tab_name == "AREA_MONTHLY_GOALS" and state["grid"]:
            grid = state["grid"]
            return pd.DataFrame(grid[1:], columns=grid[0])
        return pd.DataFrame()

    def fake_write(tab_name, rows):
        if tab_name == "AREA_MONTHLY_GOALS":
            state["grid"] = [list(r) for r in rows]

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake_read)
    monkeypatch.setattr(gq, "read_tab", lambda t, header_marker=None: fake_read(t, header_marker))
    monkeypatch.setattr(gq, "overwrite_tab", fake_write)
    mc.clear_cache()
    yield state
    mc.clear_cache()


def test_the_schema_is_the_missions_key_indicators(sheet):
    cols = gq._area_int_cols()
    assert set(cols) == {"ki_new_people_real", "ki_baptized_confirmed_real"}
    assert not ({"gate", "date_metric", "new_found", "pew", "renew",
                 "member_lessons"} & set(cols))


def test_meta_keys_are_not_columns(sheet):
    """`_meta` is the goal a companionship set for itself. A goal-for-a-goal
    column is meaningless, and would double the width of the tab."""
    assert "ki_new_people_meta" not in gq._area_int_cols()


def test_nightly_metrics_are_not_monthly_ki_columns(sheet):
    assert "contacts_attempted" not in gq._area_int_cols()


def test_a_saved_goal_reads_back(sheet):
    """The round trip that used to lose everything."""
    row, err = gq.upsert_area_monthly_goal(
        "Arauco 1", "2026-08-01",
        goals={"ki_new_people_real": 12, "ki_baptized_confirmed_real": 3},
        set_by="mp@example.org",
    )
    assert err is None, err
    assert sheet["grid"], "nothing was written to the sheet at all"

    back = gq.get_current_area_monthly_goal("Arauco 1", "2026-08-01")
    assert back is not None, "the saved row could not be read back"
    assert back["ki_new_people_real"] == 12
    assert back["ki_baptized_confirmed_real"] == 3


def test_the_header_row_carries_the_ki_columns(sheet):
    gq.upsert_area_monthly_goal(
        "Arauco 1", "2026-08-01",
        goals={"ki_new_people_real": 12}, set_by="mp@example.org")
    header = sheet["grid"][0]
    assert header[0] == "area" and header[1] == "month_start"
    assert "ki_new_people_real" in header
    assert "gate" not in header


def test_updating_the_same_area_month_overwrites_rather_than_appends(sheet):
    for value in (5, 9):
        gq.upsert_area_monthly_goal(
            "Arauco 1", "2026-08-01",
            goals={"ki_new_people_real": value}, set_by="mp@example.org")
    assert len(sheet["grid"]) == 2, \
        f"expected header + one row, got {len(sheet['grid'])} rows"
    assert gq.get_current_area_monthly_goal(
        "Arauco 1", "2026-08-01")["ki_new_people_real"] == 9


def test_another_month_is_preserved(sheet):
    gq.upsert_area_monthly_goal(
        "Arauco 1", "2026-07-01",
        goals={"ki_new_people_real": 4}, set_by="mp@example.org")
    gq.upsert_area_monthly_goal(
        "Arauco 1", "2026-08-01",
        goals={"ki_new_people_real": 8}, set_by="mp@example.org")
    assert gq.get_current_area_monthly_goal(
        "Arauco 1", "2026-07-01")["ki_new_people_real"] == 4


def test_an_unknown_key_is_dropped_not_written(sheet):
    """The tab's columns come from the catalogue. Widening the schema from
    caller input is how a typo becomes a permanent column."""
    gq.upsert_area_monthly_goal(
        "Arauco 1", "2026-08-01",
        goals={"ki_new_people_real": 3, "totally_made_up": 99},
        set_by="mp@example.org")
    assert "totally_made_up" not in sheet["grid"][0]


def test_bulk_save_stores_every_area(sheet):
    n, err = gq.bulk_upsert_area_monthly_goals(
        "2026-08-01",
        {
            "Arauco 1": {"ki_new_people_real": 6},
            "Lota 1": {"ki_new_people_real": 11, "ki_baptized_confirmed_real": 2},
        },
        set_by="mp@example.org",
    )
    assert err is None, err
    assert n == 2
    assert gq.get_current_area_monthly_goal("Arauco 1", "2026-08-01")["ki_new_people_real"] == 6
    lota = gq.get_current_area_monthly_goal("Lota 1", "2026-08-01")
    assert lota["ki_new_people_real"] == 11
    assert lota["ki_baptized_confirmed_real"] == 2


def test_a_missing_metric_saves_as_zero_not_as_a_crash(sheet):
    row, err = gq.upsert_area_monthly_goal(
        "Arauco 1", "2026-08-01",
        goals={"ki_new_people_real": 7},          # the other KI omitted
        set_by="mp@example.org")
    assert err is None, err
    assert gq.get_current_area_monthly_goal(
        "Arauco 1", "2026-08-01")["ki_baptized_confirmed_real"] == 0
