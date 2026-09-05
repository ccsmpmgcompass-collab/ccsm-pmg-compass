"""Saving a cycle's goals must actually store what was typed.

Ported from test_area_monthly_goals.py when AREA_MONTHLY_GOALS became
AREA_TRANSFER_GOALS (PLAN §7.2, §7.10). The bug it guards against is unchanged
and worth restating, because the new tab is built the same way and could fail
the same way:

AREA_MONTHLY_GOALS had a fixed schema of Utah Provo's six Key Indicators —
gate | date_metric | new_found | pew | renew | member_lessons — and its upsert
took those six as keyword arguments. Once the page started offering CCSM's
seven KIs, every one of those lookups returned 0 and every CCSM value was
dropped on the floor. The write succeeded, the page printed "goals saved", and
nothing the user typed was stored. Silent data loss that looks exactly like
success — the user would only find it by reopening the page later and finding
their goals gone.

The cycle-keying, summing and year-facing reads the transfer tab adds are
tested here too: they are what the year summary and the goal bars rest on.

These tests round-trip through the sheet layer: write, read back, compare.
"""

from datetime import date

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

#: CCSM's live cycles. 2026-8 is the straddler the year summary pro-rates.
T6 = "2026-09-07"
T7 = "2026-10-19"
T8 = "2026-11-30"


@pytest.fixture
def sheet(monkeypatch):
    """An in-memory AREA_TRANSFER_GOALS that overwrite_tab really writes to."""
    state: dict = {"grid": []}

    def fake_read(tab_name, header_marker=None):
        if tab_name == "QUESTIONS_CONFIG":
            return QUESTIONS.copy()
        if tab_name == "AREA_TRANSFER_GOALS" and state["grid"]:
            grid = state["grid"]
            return pd.DataFrame(grid[1:], columns=grid[0])
        return pd.DataFrame()

    def fake_write(tab_name, rows):
        if tab_name == "AREA_TRANSFER_GOALS":
            state["grid"] = [list(r) for r in rows]

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake_read)
    monkeypatch.setattr(gq, "read_tab", lambda t, header_marker=None: fake_read(t, header_marker))
    monkeypatch.setattr(gq, "overwrite_tab", fake_write)
    mc.clear_cache()
    yield state
    mc.clear_cache()


def _save(sheet_state, area, start, goals, number=""):
    row, err = gq.upsert_area_transfer_goal(
        area, start, goals=goals, set_by="mp@example.org", transfer_number=number)
    assert err is None, err
    return row


# ── the schema ───────────────────────────────────────────────────────────────

def test_the_schema_is_the_missions_key_indicators(sheet):
    cols = gq._metric_cols()
    assert set(cols) == {"ki_new_people_real", "ki_baptized_confirmed_real"}
    assert not ({"gate", "date_metric", "new_found", "pew", "renew",
                 "member_lessons"} & set(cols))


def test_meta_keys_are_not_columns(sheet):
    """`_meta` is the goal a companionship set for itself. A goal-for-a-goal
    column is meaningless, and would double the width of the tab."""
    assert "ki_new_people_meta" not in gq._metric_cols()


def test_nightly_metrics_are_not_columns(sheet):
    """Nightly metrics keep their weekly targets in GOALS_CONFIG/AGENT_CONFIG."""
    assert "contacts_attempted" not in gq._metric_cols()


def test_the_header_row_is_keyed_by_the_start_date(sheet):
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 12}, number="2026-6")
    header = sheet["grid"][0]
    assert header[:3] == ["area", "transfer_start", "transfer_number"]
    assert "ki_new_people_real" in header
    assert "gate" not in header
    assert "month_start" not in header


# ── the round trip ───────────────────────────────────────────────────────────

def test_a_saved_goal_reads_back(sheet):
    """The round trip that used to lose everything."""
    _save(sheet, "Arauco 1", T6,
          {"ki_new_people_real": 12, "ki_baptized_confirmed_real": 3})
    assert sheet["grid"], "nothing was written to the sheet at all"

    back = gq.get_area_transfer_goal("Arauco 1", T6)
    assert back is not None, "the saved row could not be read back"
    assert back["ki_new_people_real"] == 12
    assert back["ki_baptized_confirmed_real"] == 3


def test_updating_the_same_area_and_cycle_overwrites_rather_than_appends(sheet):
    for value in (5, 9):
        _save(sheet, "Arauco 1", T6, {"ki_new_people_real": value})
    assert len(sheet["grid"]) == 2, \
        f"expected header + one row, got {len(sheet['grid'])} rows"
    assert gq.get_area_transfer_goal("Arauco 1", T6)["ki_new_people_real"] == 9


def test_another_cycle_is_preserved(sheet):
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 4})
    _save(sheet, "Arauco 1", T7, {"ki_new_people_real": 8})
    assert gq.get_area_transfer_goal("Arauco 1", T6)["ki_new_people_real"] == 4
    assert gq.get_area_transfer_goal("Arauco 1", T7)["ki_new_people_real"] == 8


def test_an_unknown_key_is_dropped_not_written(sheet):
    """The tab's columns come from the catalogue. Widening the schema from
    caller input is how a typo becomes a permanent column."""
    _save(sheet, "Arauco 1", T6,
          {"ki_new_people_real": 3, "totally_made_up": 99})
    assert "totally_made_up" not in sheet["grid"][0]


def test_a_missing_metric_saves_as_zero_not_as_a_crash(sheet):
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 7})   # the other KI omitted
    assert gq.get_area_transfer_goal("Arauco 1", T6)["ki_baptized_confirmed_real"] == 0


def test_the_transfer_number_rides_along_but_nothing_keys_on_it(sheet):
    """§7.2: the number is a display label. Two cycles could carry the same one
    and the lookup would still be right, because it goes by the date."""
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 4}, number="2026-6")
    _save(sheet, "Arauco 1", T7, {"ki_new_people_real": 5}, number="2026-6")
    assert gq.get_area_transfer_goal("Arauco 1", T6)["ki_new_people_real"] == 4
    assert gq.get_area_transfer_goal("Arauco 1", T7)["ki_new_people_real"] == 5


def test_a_date_object_and_its_iso_string_are_the_same_cycle(sheet):
    """A sheet round trip can hand back "2026-09-07 00:00:00"; a lookup that
    treats that as a different cycle silently loses a saved goal."""
    _save(sheet, "Arauco 1", date(2026, 9, 7), {"ki_new_people_real": 6})
    assert gq.get_area_transfer_goal("Arauco 1", T6)["ki_new_people_real"] == 6
    assert gq.get_area_transfer_goal("Arauco 1", date(2026, 9, 7))["ki_new_people_real"] == 6
    assert gq.get_area_transfer_goal("Arauco 1", "2026-09-07 00:00:00")["ki_new_people_real"] == 6


def test_an_area_with_no_goal_reads_as_none_not_as_zeros(sheet):
    """"Nobody set one" and "somebody set zero" are different facts."""
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 4})
    assert gq.get_area_transfer_goal("Lota 1", T6) is None


def test_deleting_removes_only_that_row(sheet):
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 4})
    _save(sheet, "Lota 1", T6, {"ki_new_people_real": 5})
    assert gq.delete_area_transfer_goal("Arauco 1", T6) is None
    assert gq.get_area_transfer_goal("Arauco 1", T6) is None
    assert gq.get_area_transfer_goal("Lota 1", T6)["ki_new_people_real"] == 5


# ── the bulk write ───────────────────────────────────────────────────────────

def test_bulk_save_stores_every_area_in_one_write(sheet):
    writes = {"n": 0}
    inner = gq.overwrite_tab
    gq.overwrite_tab = lambda *a, **k: (writes.__setitem__("n", writes["n"] + 1), inner(*a, **k))[1]
    try:
        n, err = gq.bulk_upsert_area_transfer_goals(
            T6,
            {"Arauco 1": {"ki_new_people_real": 6},
             "Lota 1": {"ki_new_people_real": 11, "ki_baptized_confirmed_real": 2}},
            set_by="mp@example.org",
        )
    finally:
        gq.overwrite_tab = inner
    assert err is None, err
    assert n == 2
    assert writes["n"] == 1, "forty areas must not be forty Sheets writes"
    assert gq.get_area_transfer_goal("Arauco 1", T6)["ki_new_people_real"] == 6
    lota = gq.get_area_transfer_goal("Lota 1", T6)
    assert lota["ki_new_people_real"] == 11
    assert lota["ki_baptized_confirmed_real"] == 2


def test_bulk_save_preserves_other_cycles_and_unnamed_areas(sheet):
    _save(sheet, "Concepción 2", T7, {"ki_new_people_real": 3})
    _save(sheet, "Lota 1", T6, {"ki_new_people_real": 1})
    gq.bulk_upsert_area_transfer_goals(
        T6, {"Arauco 1": {"ki_new_people_real": 6}}, set_by="mp@example.org")
    assert gq.get_area_transfer_goal("Concepción 2", T7)["ki_new_people_real"] == 3
    assert gq.get_area_transfer_goal("Lota 1", T6)["ki_new_people_real"] == 1


# ── the sums the mission's own figure rests on ───────────────────────────────

def test_group_goal_totals_is_the_missions_number_for_the_cycle(sheet):
    """§7.2: there is no mission row. The mission's figure IS the areas' sum."""
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 6, "ki_baptized_confirmed_real": 1})
    _save(sheet, "Lota 1", T6, {"ki_new_people_real": 11, "ki_baptized_confirmed_real": 2})
    totals = gq.group_goal_totals(T6)
    assert totals["ki_new_people_real"] == 17
    assert totals["ki_baptized_confirmed_real"] == 3


def test_group_goal_totals_scopes_to_a_zones_areas(sheet):
    """What the Desgloses goal bar asks for at zone and district scope."""
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 6})
    _save(sheet, "Lota 1", T6, {"ki_new_people_real": 11})
    assert gq.group_goal_totals(T6, ["Arauco 1"])["ki_new_people_real"] == 6
    assert gq.group_goal_totals(T6, [" arauco 1 "])["ki_new_people_real"] == 6, \
        "area names are matched loosely — MISSION_ORG's spacing is not reliable"


def test_group_goal_totals_is_empty_for_a_cycle_nobody_planned(sheet):
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 6})
    assert gq.group_goal_totals(T8) == {}


def test_areas_with_goals_counts_only_the_areas_that_set_one(sheet):
    """The basis shown beside any summed total — the _ki_goal_note problem."""
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 6})
    _save(sheet, "Lota 1", T6, {"ki_new_people_real": 0})   # saved nothing
    assert gq.areas_with_goals(T6) == 1


# ── what the year summary reads ──────────────────────────────────────────────

def test_goals_by_cycle_start_is_keyed_by_a_real_date(sheet):
    """It is handed straight to transfer_year.year_goal_total, which needs dates."""
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 6})
    _save(sheet, "Lota 1", T6, {"ki_new_people_real": 4})
    _save(sheet, "Arauco 1", T8, {"ki_new_people_real": 9})
    by_cycle = gq.goals_by_cycle_start()
    assert set(by_cycle) == {date(2026, 9, 7), date(2026, 11, 30)}
    assert by_cycle[date(2026, 9, 7)]["ki_new_people_real"] == 10
    assert by_cycle[date(2026, 11, 30)]["ki_new_people_real"] == 9


def test_goals_by_cycle_start_feeds_the_pro_rating_end_to_end(sheet):
    """The §7.3 worked example, through the real store: 2026-8 gives 2027 its
    ten January days and no more."""
    from app.analytics import transfer_year as ty
    _save(sheet, "Arauco 1", T8, {"ki_new_people_real": 42})
    cycles = [{"start": date(2026, 11, 30), "end": date(2027, 1, 10)}]
    goals = gq.goals_by_cycle_start()
    assert ty.year_goal_total(cycles, goals, "ki_new_people_real", 2026) == pytest.approx(32.0)
    assert ty.year_goal_total(cycles, goals, "ki_new_people_real", 2027) == pytest.approx(10.0)


def test_cycles_with_goals_ignores_a_row_of_zeros(sheet):
    """The coverage caption's numerator. A row of zeros is a stray save, not a
    plan — counting it would report a year as planned when it is not."""
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 6})
    _save(sheet, "Arauco 1", T7, {"ki_new_people_real": 0})
    assert gq.cycles_with_goals() == {date(2026, 9, 7)}


def test_cycles_with_goals_can_be_scoped_to_areas(sheet):
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 6})
    _save(sheet, "Lota 1", T7, {"ki_new_people_real": 8})
    assert gq.cycles_with_goals(["Lota 1"]) == {date(2026, 10, 19)}


def test_an_unparseable_start_date_is_dropped_not_filed_wrongly(sheet):
    """A goal that cannot be placed on a calendar cannot be pro-rated."""
    _save(sheet, "Arauco 1", T6, {"ki_new_people_real": 6})
    grid = sheet["grid"]
    grid.append(["Lota 1", "not a date", "", "5", "0", "mp@example.org", ""])
    assert set(gq.goals_by_cycle_start()) == {date(2026, 9, 7)}


# ── reads on an empty tab ────────────────────────────────────────────────────

def test_everything_degrades_quietly_on_an_empty_tab(sheet):
    """Day one, before the tab exists at all."""
    assert gq.get_area_transfer_goal("Arauco 1", T6) is None
    assert gq.group_goal_totals(T6) == {}
    assert gq.goals_by_cycle_start() == {}
    assert gq.cycles_with_goals() == set()
    assert gq.areas_with_goals(T6) == 0
    assert gq.get_area_transfer_goals(T6).empty
