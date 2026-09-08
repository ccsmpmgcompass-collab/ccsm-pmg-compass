"""What Apply writes back to the sheet after a transfer.

Three defects found by probing the live COMPASS_CCSM sheet on 2026-09-08, the
day after cycle 2026-6 began (PLAN-2026-09-08-transfer-day.md §1). All three
were reachable from one click on the Traslados page, and none was covered by a
test:

1. `_advance_schedule` looked for `Status == "Planned"`. CCSM writes
   **"Scheduled"**, so no row ever matched.
2. Falling through to its append branch, it picked a number with `.isdigit()`.
   CCSM's Transfer_Number values read "2026-4" … "2026-8", so nothing was a bare
   digit and the new number came out `0 + 1`. Simulated against the live grid,
   Apply would have appended `['1', '2026-09-08', '', 'Actual']` — the row
   `transfer_window()` would then have called "the current transfer", with a
   blank length, for Desgloses, the Panel rankings, Puntajes and Metas.
3. `_set_transfer_start_date` wrote `today`. Cycle 2026-6 started Monday
   2026-09-07 and was applied on Tuesday the 8th, which would have dropped
   Monday out of every `<metric>_transfer` total and left AGENT_CONFIG
   disagreeing with TRANSFER_SCHEDULE.

Plus the pilot-zone filter those same probes made necessary: MISSION_ORG had 43
active areas in 4 zones while TRANSFER_IMPORT carried 97 areas in 11, and
`apply_transfer` activates every area it finds in the roster.
"""

from datetime import date

import pytest

from app.ingestion import transfer_apply_service as tas
from app.ingestion import transfer_engine as te

#: The live tab as it stood on 2026-09-08 — the shape the old code broke on.
LIVE_SCHEDULE = [
    ["Transfer_Number", "Start_Date", "Weeks", "Status"],
    ["2026-4", "2026-06-15", "6", "Actual"],
    ["2026-5", "2026-07-27", "6", "Actual"],
    ["2026-6", "2026-09-07", "6", "Scheduled"],
    ["2026-7", "2026-10-19", "6", "Scheduled"],
    ["2026-8", "2026-11-30", "6", "Scheduled"],
]

LIVE_CONFIG = [
    ["Key", "Value"],
    ["MISSION_NAME", "Chile Concepcion South"],
    ["TRANSFER_START_DATE", "2026-07-27"],
    ["SYSTEM_START_DATE", "2026-08-10"],
]

CYCLE_6 = date(2026, 9, 7)      # the Monday the cycle began
APPLIED_ON = date(2026, 9, 8)   # the Tuesday someone clicked Apply


@pytest.fixture
def sheet(monkeypatch):
    """In-memory TRANSFER_SCHEDULE / AGENT_CONFIG that record every write."""
    state = {
        "TRANSFER_SCHEDULE": [list(r) for r in LIVE_SCHEDULE],
        "AGENT_CONFIG": [list(r) for r in LIVE_CONFIG],
        "cells": [],
        "appended": [],
    }

    def fake_read_values(tab):
        return [list(r) for r in state.get(tab, [])]

    def fake_update_cell(tab, a1, value):
        state["cells"].append((tab, a1, value))

    def fake_append_row(tab, row, scoped=False):
        state["appended"].append((tab, list(row)))
        state.setdefault(tab, []).append(list(row))

    monkeypatch.setattr(tas.sc, "read_values", fake_read_values)
    monkeypatch.setattr(tas.sc, "update_cell", fake_update_cell)
    monkeypatch.setattr(tas.sc, "append_row", fake_append_row)
    return state


# ── _advance_schedule ────────────────────────────────────────────────────────

def test_marks_the_scheduled_row_actual(sheet):
    """"Scheduled" is the status CCSM actually writes — it must be recognised."""
    assert tas._advance_schedule(CYCLE_6) is True
    # Column D (Status) of row 4 — the 2026-6 row.
    assert sheet["cells"] == [("TRANSFER_SCHEDULE", "D4", "Actual")]


def test_never_appends_a_row_for_a_cycle_already_scheduled(sheet):
    """The regression that would have put ['1', <today>, '', 'Actual'] on the tab."""
    tas._advance_schedule(CYCLE_6)
    assert sheet["appended"] == []


def test_leaves_start_date_alone(sheet):
    """The pre-scheduled Monday is what every period-scoped page keys on."""
    tas._advance_schedule(CYCLE_6)
    written_cols = {a1[0] for _, a1, _ in sheet["cells"]}
    assert "B" not in written_cols          # B is Start_Date
    assert sheet["TRANSFER_SCHEDULE"][3][1] == "2026-09-07"


def test_applying_a_day_late_still_resolves_to_the_cycle_not_the_day(sheet, monkeypatch):
    """Apply ran Tuesday the 8th; both writes must still describe Monday the 7th.

    `_current_cycle_start` is what carries that — it asks transfer_window(),
    the app's one answer to "which transfer is this", instead of trusting the
    calendar date of the click.
    """
    import app.utils.transfer_helpers as th
    monkeypatch.setattr(th, "transfer_window",
                        lambda offset=0, today=None: {"start": CYCLE_6, "end": date(2026, 10, 18),
                                                      "number": "2026-6", "weeks": 6,
                                                      "status": "Scheduled", "source": "schedule"})
    assert tas._current_cycle_start(APPLIED_ON) == CYCLE_6

    tas._advance_schedule(tas._current_cycle_start(APPLIED_ON))
    tas._set_transfer_start_date(tas._current_cycle_start(APPLIED_ON))
    assert sheet["cells"] == [("TRANSFER_SCHEDULE", "D4", "Actual"),
                              ("AGENT_CONFIG", "B3", "2026-09-07")]


def test_cycle_start_falls_back_to_today_when_nothing_is_scheduled(monkeypatch):
    import app.utils.transfer_helpers as th
    monkeypatch.setattr(th, "transfer_window", lambda offset=0, today=None: None)
    assert tas._current_cycle_start(APPLIED_ON) == APPLIED_ON


def test_already_actual_is_a_no_op(sheet):
    """Re-applying the same transfer must not rewrite anything."""
    assert tas._advance_schedule(date(2026, 7, 27)) is False
    assert sheet["cells"] == []
    assert sheet["appended"] == []


def test_appends_with_a_real_number_when_no_row_covers_the_cycle(sheet):
    """The fallback path keeps CCSM's own numbering instead of restarting at 1."""
    assert tas._advance_schedule(date(2027, 1, 11)) is True
    assert sheet["appended"] == [
        ("TRANSFER_SCHEDULE", ["2026-9", "2027-01-11", "6", "Actual"])
    ]


def test_unparseable_start_dates_do_not_crash_the_scan(sheet):
    sheet["TRANSFER_SCHEDULE"].insert(1, ["2026-3", "", "6", "Actual"])
    assert tas._advance_schedule(CYCLE_6) is True


# ── _set_transfer_start_date ─────────────────────────────────────────────────

def test_writes_the_cycle_start_not_today(sheet):
    """The bug: this wrote 2026-09-08, losing Monday from every transfer total."""
    assert tas._set_transfer_start_date(CYCLE_6) is True
    assert sheet["cells"] == [("AGENT_CONFIG", "B3", "2026-09-07")]


def test_reports_false_when_the_key_is_absent(sheet):
    sheet["AGENT_CONFIG"] = [["Key", "Value"], ["MISSION_NAME", "CCSM"]]
    assert tas._set_transfer_start_date(CYCLE_6) is False
    assert sheet["cells"] == []


# ── filter_roster_to_zones ───────────────────────────────────────────────────

def _r(area, zone):
    return {"Area_Name": area, "Zone": zone, "Active": "TRUE"}


ROSTER = [
    _r("Alemania 2", "Angol"),
    _r("Nacimiento", "Los Angeles Norte"),
    _r("Los Huertos", "San Pedro"),
    _r("Vilcun", "Temuco Ñielol"),
    _r("Cañete 1", "Arauco"),
    _r("Gorbea", "Villarrica"),
]

PILOT = ["Angol", "Los Angeles Norte", "San Pedro", "Temuco Ñielol"]


def test_keeps_only_the_pilot_zones():
    kept, unknown = te.filter_roster_to_zones(ROSTER, PILOT)
    assert [r["Area_Name"] for r in kept] == [
        "Alemania 2", "Nacimiento", "Los Huertos", "Vilcun"]
    assert unknown == []


def test_a_new_area_opened_in_a_pilot_zone_still_arrives():
    """The whole reason this filters instead of hand-trimming TRANSFER_IMPORT."""
    roster = ROSTER + [_r("San Pedro 3", "San Pedro")]
    kept, _ = te.filter_roster_to_zones(roster, PILOT)
    assert "San Pedro 3" in [r["Area_Name"] for r in kept]


def test_no_configured_zones_means_the_whole_mission():
    for empty in ([], None, [""], ["  "]):
        kept, unknown = te.filter_roster_to_zones(ROSTER, empty)
        assert len(kept) == len(ROSTER)
        assert unknown == []


def test_zone_matching_ignores_case_and_padding():
    kept, unknown = te.filter_roster_to_zones(ROSTER, ["  angol  "])
    assert [r["Area_Name"] for r in kept] == ["Alemania 2"]
    assert unknown == []


def test_a_misspelled_pilot_zone_is_reported_not_silently_dropped():
    """"Los Angeles Norte" vs the export's "Los Ángeles Norte" would otherwise
    deactivate every area in that zone."""
    kept, unknown = te.filter_roster_to_zones(ROSTER, ["Angol", "Los Ángeles Norte"])
    assert [r["Area_Name"] for r in kept] == ["Alemania 2"]
    assert unknown == ["Los Ángeles Norte"]


def test_apply_refuses_on_an_unknown_pilot_zone(monkeypatch):
    monkeypatch.setattr(tas, "load_state",
                        lambda: ([], [], ROSTER, ["Los Ángeles Norte"]))
    with pytest.raises(tas.TransferBlocked) as exc:
        tas.apply()
    assert "Los Ángeles Norte" in str(exc.value)
    assert "deactivate" in str(exc.value)
