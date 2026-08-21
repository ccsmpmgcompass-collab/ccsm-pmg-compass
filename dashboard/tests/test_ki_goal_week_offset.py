"""A week's Key Indicator goals are written on the PREVIOUS week's form.

The weekly form asks each companionship for two sets of seven numbers, and its
own section help (WeeklyReportForm_ES.gs:113-118) says which week each one is
about:

    Real — "los resultados obtenidos durante la semana pasada"
    Meta — "las metas que usted estableció durante la planificación semanal
            para la SEMANA SIGUIENTE"

So one WEEKLY_KI row carries week W's results beside week W+1's goals. Reading
the meta off the same row grades a week against the target set for the week
after it — which is what CCSM_AgentScores.gs did until this was found (audit
item 2, 2026-08-21), and what get_ki_goals_for_week exists to prevent.

Synthetic weeks throughout: against the live sheet these assertions would pass
or fail by calendar accident.
"""

from datetime import date

import pandas as pd
import pytest

from app.db import queries
from app.db.queries import get_ki_goals_for_week, get_area_weekly_goals

W1 = "2026-08-09"
W2 = "2026-08-16"
W3 = "2026-08-23"


def _weekly_form(rows) -> pd.DataFrame:
    """rows: (week, area, real, meta) -> the frame get_weekly_form_data returns."""
    return pd.DataFrame([
        {
            "week_end_date": w,
            "area": a,
            "zone": "Angol",
            "ki_new_people_real": real,
            "ki_new_people_meta": meta,
        }
        for w, a, real, meta in rows
    ])


@pytest.fixture
def form_data(monkeypatch):
    def _install(rows):
        monkeypatch.setattr(queries, "get_weekly_form_data",
                            lambda: _weekly_form(rows))
    return _install


# ── The offset itself ─────────────────────────────────────────────────────────

def test_a_weeks_goal_comes_from_the_previous_weeks_form(form_data):
    """The regression: week 3's goal is the meta written on week 2's row."""
    form_data([
        (W1, "Alemania 1", 16, 10),   # meta 10 is the goal for W2
        (W2, "Alemania 1", 12, 25),   # meta 25 is the goal for W3
    ])
    goals, _, source, _ = get_ki_goals_for_week(date(2026, 8, 23))
    assert goals["ki_new_people_real"] == 25
    assert source == date(2026, 8, 16)


def test_the_same_weeks_meta_is_never_used_as_that_weeks_goal(form_data):
    """The exact shape of the AgentScores bug: W2's own meta is W3's target and
    must not be returned as W2's."""
    form_data([
        (W1, "Alemania 1", 16, 10),
        (W2, "Alemania 1", 12, 25),
    ])
    goals, _, _, _ = get_ki_goals_for_week(date(2026, 8, 16))
    assert goals["ki_new_people_real"] == 10, "took the same row's meta"


def test_the_source_week_is_found_by_date_not_by_taking_the_row_before(form_data):
    """A skipped week must not donate a two-week-old goal. Nobody submitted W2,
    so W3 has no goal — not W1's."""
    form_data([(W1, "Alemania 1", 16, 10)])
    goals, _, source, areas = get_ki_goals_for_week(date(2026, 8, 23))
    assert goals == {}
    assert areas == 0
    assert source == date(2026, 8, 16)


# ── Summing across areas ──────────────────────────────────────────────────────

def test_goals_sum_across_every_area_that_submitted_the_source_week(form_data):
    form_data([
        (W2, "Alemania 1", 12, 25),
        (W2, "Collipulli", 8, 15),
        (W2, "Huequen", 5, 10),
    ])
    goals, set_by, _, areas = get_ki_goals_for_week(date(2026, 8, 23))
    assert goals["ki_new_people_real"] == 50
    assert set_by["ki_new_people_real"] == 3
    assert areas == 3


def test_a_blank_goal_counts_as_zero_and_is_reported_in_set_by(form_data):
    """An area that wrote down no goal committed to nothing, so it adds nothing
    to the total. set_by is what stops a goal resting on one area from reading
    like one every area signed up to — the live ki_baptized_confirmed case."""
    form_data([
        (W2, "Alemania 1", 12, 25),
        (W2, "Collipulli", 8, 0),
        (W2, "Huequen", 5, 0),
    ])
    goals, set_by, _, areas = get_ki_goals_for_week(date(2026, 8, 23))
    assert goals["ki_new_people_real"] == 25
    assert set_by["ki_new_people_real"] == 1
    assert areas == 3, "areas counts submitters, not goal-setters"


def test_a_metric_no_area_set_a_goal_for_gets_no_entry(form_data):
    """No bar at all, rather than a bar against zero."""
    form_data([(W2, "Alemania 1", 12, 0)])
    goals, _, _, _ = get_ki_goals_for_week(date(2026, 8, 23))
    assert "ki_new_people_real" not in goals


def test_real_columns_are_never_mistaken_for_goals(form_data):
    """_real is an outcome and _meta is a target; only _meta maps to a goal."""
    form_data([(W2, "Alemania 1", 999, 25)])
    goals, _, _, _ = get_ki_goals_for_week(date(2026, 8, 23))
    assert list(goals) == ["ki_new_people_real"]
    assert goals["ki_new_people_real"] == 25


# ── Degenerate inputs ─────────────────────────────────────────────────────────

def test_no_week_asked_for_returns_empty(form_data):
    form_data([(W2, "Alemania 1", 12, 25)])
    assert get_ki_goals_for_week(None) == ({}, {}, None, 0)


def test_an_empty_form_tab_returns_empty(monkeypatch):
    monkeypatch.setattr(queries, "get_weekly_form_data", lambda: pd.DataFrame())
    assert get_ki_goals_for_week(date(2026, 8, 23)) == ({}, {}, None, 0)


# ── AGENT_CONFIG per-area goals ───────────────────────────────────────────────

def test_goal_rows_are_read_as_per_area_weekly_targets(monkeypatch):
    monkeypatch.setattr(queries, "get_agent_config", lambda: {
        "GOAL_contacts_attempted": "200",
        "GOAL_roleplays": "8",
        "MISSION_NAME": "CCSM",
        "CONTACT_RATE_TARGET": "0.5",
    })
    goals = get_area_weekly_goals()
    assert goals == {"contacts_attempted": 200.0, "roleplays": 8.0}


def test_blank_and_zero_goals_are_dropped_not_returned_as_zero(monkeypatch):
    """A goal of zero is not a bar — and a caller drawing a progress bar against
    it would mark the metric fully met the moment it recorded anything."""
    monkeypatch.setattr(queries, "get_agent_config", lambda: {
        "GOAL_contacts_attempted": "200",
        "GOAL_pmf_lessons": "",
        "GOAL_rc_lessons": "0",
        "GOAL_friend_calls": "not a number",
    })
    assert get_area_weekly_goals() == {"contacts_attempted": 200.0}


def test_goal_keys_keep_their_lowercase_metric_key_casing(monkeypatch):
    """CcsmData.gs seeds GOAL_new_people_found, not GOAL_NEW_PEOPLE_FOUND, and
    CCSM_Agent2.gs's header calls out that no case transform may be applied."""
    monkeypatch.setattr(queries, "get_agent_config",
                        lambda: {"GOAL_new_people_found": "7"})
    assert "new_people_found" in get_area_weekly_goals()
