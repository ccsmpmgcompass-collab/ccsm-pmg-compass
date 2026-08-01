"""Area expectations must be CCSM's, and must apply to CCSM's areas.

Utah Provo splits its roster six ways — English, Spanish, Bilingual,
Haitian/Creole/French, ASL, Chinese — and the inherited code hardcoded that
split, with a default expectation table per group over Provo's metrics
(nm_lessons 15/30/23, new_found, mmm_sent 70/10/40, pew, gate).

CCSM's MISSION_ORG has no Language_Type column at all. So every lookup returned
blank, `_language_group("")` fell through to Provo's "english" bucket, and all
98 Chilean areas were held to the STRICTEST of Provo's six expectation sets —
70 MMMs a week — for metrics they do not collect. Every expectation on the
Goals page therefore read as unmet, permanently, and the Area Expectation
Settings tab offered six editable categories where five could never match
anything.

Defaults now come from AGENT_CONFIG's GOAL_* keys: the weekly per-area targets
the mission set for itself, and the same numbers CCSM_Agent1A.gs coaches
against.
"""

import pandas as pd
import pytest

import app.db.queries as q

AGENT_CONFIG = pd.DataFrame([
    {"Key": "MISSION_NAME", "Value": "Chile Concepción South Mission"},
    {"Key": "GOAL_contacts_attempted", "Value": "200"},
    {"Key": "GOAL_roleplays", "Value": "8"},
    {"Key": "GOAL_new_people_found", "Value": "7"},
    {"Key": "GOAL_member_contacts", "Value": "15"},
    # A goal the mission has deliberately zeroed out.
    {"Key": "GOAL_baptismal_calendars", "Value": "0"},
    # Junk must not become an expectation.
    {"Key": "GOAL_broken", "Value": "n/a"},
])

# CCSM's real MISSION_ORG columns — note the absence of Language_Type.
MISSION_ORG = pd.DataFrame([
    {"Area_Code": "A014", "Area_Name": "Arauco 1", "Zone": "Arauco",
     "District": "Arauco", "Companion1_Email": "a@missionary.org",
     "Is_DL": "FALSE", "Is_ZL": "FALSE", "Is_STL": "FALSE",
     "Is_AP": "FALSE", "Is_MP": "FALSE", "Active": "TRUE"},
])


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    def fake(tab_name, header_marker=None):
        if tab_name == "AGENT_CONFIG":
            return AGENT_CONFIG.copy()
        if tab_name == "MISSION_ORG":
            return MISSION_ORG.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    for fn in (q.get_agent_config, q.get_area_language_group,
               q.get_all_area_type_indicators, q.get_submitting_areas):
        if hasattr(fn, "clear"):
            fn.clear()
    yield
    for fn in (q.get_agent_config, q.get_area_language_group,
               q.get_all_area_type_indicators, q.get_submitting_areas):
        if hasattr(fn, "clear"):
            fn.clear()


# ── Grouping ──────────────────────────────────────────────────────────────────

def test_a_roster_with_no_language_column_uses_the_default_group():
    """The bug: this returned Provo's "english" — its strictest bucket."""
    assert q._language_group("") == q.DEFAULT_AREA_TYPE_GROUP
    assert q._language_group(None) == q.DEFAULT_AREA_TYPE_GROUP
    assert q.get_area_language_group("Arauco 1") == q.DEFAULT_AREA_TYPE_GROUP


def test_no_provo_language_group_survives():
    assert q._language_group("") not in ("english", "haitian_creole", "asl", "chinese")
    assert set(q._AREA_TYPE_LABELS) == {q.DEFAULT_AREA_TYPE_GROUP}


def test_an_explicit_language_is_still_honoured():
    """CCSM has no language column today, but adding one later must work
    rather than being silently ignored."""
    assert q._language_group("Español") == "spanish"
    assert q._language_group("Spanish") == "spanish"
    assert q._language_group("Bilingual") == "bilingual"
    assert q._language_group("English") == "english"


def test_an_unknown_language_falls_back_rather_than_crashing():
    assert q._language_group("Mapudungun") == q.DEFAULT_AREA_TYPE_GROUP


def test_area_name_no_longer_forces_a_language_group():
    """Provo matched "Haitian"/"Creole"/"French" in the AREA NAME. A Chilean
    area could carry those letters by coincidence and be silently held to a
    different bar."""
    assert q._language_group("", "French Hill") == q.DEFAULT_AREA_TYPE_GROUP


# ── Defaults ──────────────────────────────────────────────────────────────────

def test_defaults_come_from_the_missions_own_goals():
    defaults = q._area_type_indicator_defaults()
    assert set(defaults) == {q.DEFAULT_AREA_TYPE_GROUP}
    got = {m: (c, v) for m, c, v in defaults[q.DEFAULT_AREA_TYPE_GROUP]}
    assert got["contacts_attempted"] == ("weekly", 200.0)
    assert got["roleplays"] == ("weekly", 8.0)
    assert got["new_people_found"] == ("weekly", 7.0)


def test_no_provo_metric_is_expected_of_anyone():
    defaults = q._area_type_indicator_defaults()
    metrics = {m for rows in defaults.values() for m, _, _ in rows}
    assert not (metrics & {"nm_lessons", "new_found", "mmm_sent", "pew", "gate"})


def test_a_zero_goal_is_not_an_expectation():
    """_scale_effort_metric() treats an expectation of 0 as "nothing was
    expected, full marks". Carrying a zeroed goal through would quietly award a
    perfect score for a metric nobody set a target on."""
    metrics = {m for m, _, _ in
               q._area_type_indicator_defaults()[q.DEFAULT_AREA_TYPE_GROUP]}
    assert "baptismal_calendars" not in metrics


def test_an_unparseable_goal_is_skipped_not_crashed():
    metrics = {m for m, _, _ in
               q._area_type_indicator_defaults()[q.DEFAULT_AREA_TYPE_GROUP]}
    assert "broken" not in metrics


def test_non_goal_config_keys_are_ignored():
    metrics = {m for m, _, _ in
               q._area_type_indicator_defaults()[q.DEFAULT_AREA_TYPE_GROUP]}
    assert "MISSION_NAME" not in metrics and "" not in metrics


def test_every_default_is_weekly():
    """Every GOAL_* in AGENT_CONFIG is a weekly per-area target. Provo's table
    mixed a monthly cadence in for `gate`; CCSM has no monthly goal key, and a
    weekly number read as monthly would set the bar 4x too low."""
    rows = q._area_type_indicator_defaults()[q.DEFAULT_AREA_TYPE_GROUP]
    assert {c for _, c, _ in rows} == {"weekly"}


def test_bootstrap_uses_the_default_label():
    """With AREA_TYPE_EXPECTATIONS empty, the whole tab bootstraps from the
    defaults — under a label that exists."""
    rows = q.get_all_area_type_indicators()
    assert rows, "an empty expectations tab must bootstrap from defaults"
    assert {r["category"] for r in rows} == {"Todas las Áreas"}


def test_resolution_reaches_the_default_group_for_a_real_area():
    exp = q.resolve_area_expectations("Arauco 1")
    assert exp, "a real area resolved to no expectations at all"
    assert "contacts_attempted" in exp
    assert exp["contacts_attempted"]["value"] == 200.0
    assert exp["contacts_attempted"]["cadence"] == "weekly"
