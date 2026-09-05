"""Transfer_Number is a LABEL, and two functions parsed it as an integer.

CCSM's live TRANSFER_SCHEDULE numbers its cycles "2026-4", "2026-5", … — a
format nothing in this app or in the Apps Script that writes the tab enforces.
Two callers assumed a bare integer:

  * ``queries.get_recent_transfer_dates`` coerced the column with
    ``pd.to_numeric``, so every live row became NaN and was dropped. Verified
    against the live sheet 2026-09-05: it returned ``[]``, and
    ``is_within_last_transfers()`` was False for every date in the mission.
  * ``transfer_engine.next_schedule_update`` called ``int("2026-4")``, which
    throws. The exception was caught and ``max_num`` stayed 0, so appending a
    cycle to a tab reading 2026-4 … 2026-8 would have numbered it "1".

Neither had visible impact — the first feeds only the area-lineage badge, whose
AREA_LINEAGE tab does not exist — so nothing on screen would have reported
either one. They are fixed here because Step 7 keys goals off this tab and has
to read it reliably. See PLAN-2026-09-05-backlog.md §7.9.
"""

import datetime as dt

import pandas as pd
import pytest

import app.db.queries as q
import app.ingestion.transfer_engine as te

#: The live tab as of 2026-09-05, verbatim — the shape both bugs met in production.
LIVE_SCHEDULE = pd.DataFrame([
    {"Transfer_Number": "2026-4", "Start_Date": "2026-06-15", "Weeks": "6", "Status": "Actual"},
    {"Transfer_Number": "2026-5", "Start_Date": "2026-07-27", "Weeks": "6", "Status": "Actual"},
    {"Transfer_Number": "2026-6", "Start_Date": "2026-09-07", "Weeks": "6", "Status": "Scheduled"},
    {"Transfer_Number": "2026-7", "Start_Date": "2026-10-19", "Weeks": "6", "Status": "Scheduled"},
    {"Transfer_Number": "2026-8", "Start_Date": "2026-11-30", "Weeks": "6", "Status": "Scheduled"},
])


@pytest.fixture
def schedule(monkeypatch):
    """Serve a TRANSFER_SCHEDULE frame to queries.read_tab, nothing else."""
    def _serve(df):
        monkeypatch.setattr(
            q, "read_tab",
            lambda tab, *a, **k: df.copy() if tab == "TRANSFER_SCHEDULE" else pd.DataFrame())
    return _serve


# ── get_recent_transfer_dates ────────────────────────────────────────────────

def test_recent_dates_reads_the_live_yyyy_n_format(schedule):
    """The regression: two Actual rows, and both must come back."""
    schedule(LIVE_SCHEDULE)
    assert q.get_recent_transfer_dates(2) == ["2026-07-27", "2026-06-15"]


def test_recent_dates_order_is_by_date_not_by_label(schedule):
    """A mission renumbering at the calendar year sorts wrong on the label.

    "2027-1" is alphabetically and numerically below "2026-9" while being the
    LATER cycle, so ordering on the number would put them backwards. The date
    cannot be fooled that way.
    """
    schedule(pd.DataFrame([
        {"Transfer_Number": "2026-9", "Start_Date": "2026-11-30", "Weeks": "6", "Status": "Actual"},
        {"Transfer_Number": "2027-1", "Start_Date": "2027-01-11", "Weeks": "6", "Status": "Actual"},
    ]))
    assert q.get_recent_transfer_dates(2) == ["2027-01-11", "2026-11-30"]


def test_recent_dates_ignores_non_actual_rows(schedule):
    """Status still filters — CCSM_Agent2.gs reads only Actual rows too."""
    schedule(LIVE_SCHEDULE)
    assert "2026-09-07" not in q.get_recent_transfer_dates(5)


def test_recent_dates_tolerates_a_time_component(schedule):
    """A Start_Date read back as "2026-06-15 00:00:00" is still that date.

    Dropping a real cycle over its formatting is the same class of bug as the
    numeric coercion this replaces.
    """
    schedule(pd.DataFrame([
        {"Transfer_Number": "2026-4", "Start_Date": "2026-06-15 00:00:00",
         "Weeks": "6", "Status": "Actual"},
    ]))
    assert q.get_recent_transfer_dates(1) == ["2026-06-15 00:00:00"]


def test_recent_dates_empty_when_no_actual_rows(schedule):
    schedule(LIVE_SCHEDULE[LIVE_SCHEDULE["Status"] == "Scheduled"])
    assert q.get_recent_transfer_dates(2) == []


def test_recent_dates_empty_when_tab_missing(schedule):
    schedule(pd.DataFrame())
    assert q.get_recent_transfer_dates(2) == []


def test_is_within_last_transfers_now_fires(schedule):
    """The consumer's own symptom: False for every date in the mission."""
    schedule(LIVE_SCHEDULE)
    assert q.is_within_last_transfers("2026-07-27") is True
    assert q.is_within_last_transfers("2026-06-15") is True
    assert q.is_within_last_transfers("2025-01-01") is False


# ── next_transfer_number / next_schedule_update ──────────────────────────────

def test_next_number_keeps_the_prefix_and_increments():
    assert te.next_transfer_number(LIVE_SCHEDULE.to_dict("records")) == "2026-9"


def test_next_number_still_handles_a_bare_integer():
    """The pre-existing convention keeps working — see test_transfer_engine.py."""
    assert te.next_transfer_number([{"Transfer_Number": "5"}]) == "6"


def test_next_number_follows_the_last_row_not_the_largest():
    """Sheet order is the order the cycles run, so the last row sets the pattern."""
    rows = [{"Transfer_Number": "2026-12"}, {"Transfer_Number": "2027-1"}]
    assert te.next_transfer_number(rows) == "2027-2"


def test_next_number_ignores_rows_with_no_digits():
    rows = [{"Transfer_Number": "2026-4"}, {"Transfer_Number": ""},
            {"Transfer_Number": "TBD"}]
    assert te.next_transfer_number(rows) == "2026-5"


def test_next_number_falls_back_to_one_on_an_empty_tab():
    assert te.next_transfer_number([]) == "1"


def test_append_no_longer_numbers_a_live_row_one():
    """The bug end to end: appending after 2026-8 gave "1"."""
    rows = LIVE_SCHEDULE.assign(Status="Actual").to_dict("records")
    out = te.next_schedule_update(rows, dt.date(2027, 1, 11))
    assert len(out) == len(rows) + 1
    assert out[-1]["Transfer_Number"] == "2026-9"
    assert out[-1]["Start_Date"] == "2027-01-11"
    assert out[-1]["Status"] == "Actual"


def test_append_leaves_a_planned_row_alone():
    """Flipping Planned -> Actual still wins over appending."""
    rows = [{"Transfer_Number": "2026-4", "Start_Date": "2026-06-15",
             "Weeks": "6", "Status": "Actual"},
            {"Transfer_Number": "2026-5", "Start_Date": "",
             "Weeks": "6", "Status": "Planned"}]
    out = te.next_schedule_update(rows, dt.date(2026, 7, 27))
    assert len(out) == 2
    assert out[1]["Status"] == "Actual"
    assert out[1]["Start_Date"] == "2026-07-27"
