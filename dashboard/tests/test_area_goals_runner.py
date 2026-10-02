"""The weekly sector-goals job's grid handling —
app/ingestion/area_goals_runner.py (PLAN-2026-10-02-goals.md, G7)."""

import ast
import sys
from datetime import date
from pathlib import Path

import pytest

from app.analytics import area_goals as AG
from app.ingestion import area_goals_runner as R

WEEK = date(2026, 10, 5)


def test_the_roster_is_active_sectors_without_leadership_rows():
    grid = [["Area_Name", "Zone", "Active"],
            ["Alemania 2", "Angol", "TRUE"],
            ["Zone Leader - Angol", "Angol", "TRUE"],
            ["Coronel", "Concepción", "FALSE"],
            ["", "Angol", "TRUE"]]
    assert R.roster(grid) == {"Alemania 2": "Angol"}


def test_the_metric_list_is_agent1as():
    grid = [["Metric_Key", "Active", "Data_Type", "Form_Type"],
            ["contacts_attempted", "TRUE", "NUMBER", "NIGHTLY"],
            ["effort", "TRUE", "CHOICE", "NIGHTLY"],
            ["ki_new_people_real", "TRUE", "NUMBER", "WEEKLY"],
            ["roleplays", "FALSE", "NUMBER", "NIGHTLY"]]
    assert R.nightly_keys(grid) == ["contacts_attempted"]


def test_configured_goals_skip_the_annual_and_the_blank():
    cfg = {"GOAL_roleplays": "7", "GOAL_ANNUAL_baptisms": "527",
           "GOAL_x": "", "TRANSFER_START_DATE": "2026-09-07"}
    assert R.configured_goals(cfg) == {"roleplays": 7.0}


@pytest.mark.parametrize("grid, want", [
    ([], 1.10),
    ([["key", "value"], ["rec_stretch_pct", "20"]], 1.20),
    ([["key", "value"], ["rec_stretch_pct", "oops"]], 1.10),
])
def test_stretch(grid, want):
    assert R.stretch(grid) == pytest.approx(want)


def test_last_weeks_row_and_its_leadership_keys():
    grid = [["Week_Start", "Area", "Overridden", "a", "b"],
            ["2026-09-28", "A", "b", "12", "30"],
            ["2026-10-05", "A", "", "13", "31"]]
    goals, over = R.history_week(grid, date(2026, 9, 28))
    assert goals == {"A": {"a": 12.0, "b": 30.0}} and over == {"A": {"b"}}


def test_a_blank_override_cell_is_no_override():
    grid = [["Area", "a", "b"], ["A", "", "40"], ["B", "", ""]]
    assert R.overrides(grid) == {"A": {"b": 40}}


def _goals():
    return {"B": {"a": AG.AreaGoal(5, AG.OWN), "b": AG.AreaGoal(40, AG.LEADERSHIP)},
            "A": {"a": AG.AreaGoal(None, AG.CONFIG), "b": AG.AreaGoal(7, AG.ZONE)}}


def test_history_rows_record_which_goals_were_leaderships():
    rows = R.history_rows(WEEK, _goals(), ["a", "b"])
    assert rows == [["2026-10-05", "A", "", "", 7],
                    ["2026-10-05", "B", "b", 5, 40]]


def test_a_rerun_replaces_its_own_week_and_keeps_the_rest():
    old = [["Week_Start", "Area", "Overridden", "a"],
           ["2026-09-28", "A", "", "3"],
           ["2026-10-05", "A", "", "999"]]
    new = R.history_rows(WEEK, _goals(), ["a", "b"])
    merged = R.merged_history(old, WEEK, new, ["a", "b"])
    assert merged[0] == ["Week_Start", "Area", "Overridden", "a", "b"]
    assert merged[1] == ["2026-09-28", "A", "", "3", ""]   # b did not exist then
    assert merged[2:] == new


def test_goals_config_is_the_shape_the_agents_read():
    grid = R.goals_config_grid(_goals(), ["a", "b"])
    assert grid == [["Area", "a", "b"], ["A", "", 7], ["B", 5, 40]]


def test_the_printed_summary_carries_no_names():
    assert R.summary(_goals()) == {AG.OWN: 1, AG.LEADERSHIP: 1,
                                   AG.CONFIG: 1, AG.ZONE: 1}


def test_the_runner_does_not_import_streamlit():
    """It runs in a GitHub Actions container with no Streamlit installed."""
    src = Path(R.__file__).read_text(encoding="utf-8")
    imported = {n.names[0].name.split(".")[0] if isinstance(n, ast.Import)
                else (n.module or "").split(".")[0]
                for n in ast.walk(ast.parse(src))
                if isinstance(n, (ast.Import, ast.ImportFrom))}
    assert "streamlit" not in imported
    for mod in ("app.analytics.area_goals", "app.analytics.goal_recalibration",
                "app.analytics.period_delta"):
        assert "streamlit" not in Path(sys.modules[mod].__file__).read_text(encoding="utf-8")
