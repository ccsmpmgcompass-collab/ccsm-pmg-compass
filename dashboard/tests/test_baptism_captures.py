"""TABLEAU_BAPTISMS rows carry the window their export was run for (2026-09-19).

Before that, the tab held `zone | month | baptisms` and nothing else, so a
month-to-date capture was indistinguishable from a finished month. The rule
these tests pin down is the one that makes the extra columns safe:

    a partial window must never be silently readable as a complete one.

`get_baptisms_actual` and the annual series therefore refuse a provisional row
outright; anything that wants the month-to-date figure asks for it by name and
is thereby obliged to label it.
"""

from datetime import date

import pandas as pd

from app.db import queries
from app.db.queries import (
    get_baptisms_actual,
    get_baptisms_actual_for_range,
    get_baptisms_capture,
    get_mission_baptisms_by_month,
)

#: The metadata row save_dataframe stamps at the top, which read_tab hands back
#: as ordinary data.
_META = ["_uploaded_by:someone@example.org", "_uploaded_at:2026-09-19 00:00 UTC",
         "", "", ""]


def _install(monkeypatch, rows, columns=("zone", "month", "baptisms",
                                         "start_date", "end_date")):
    meta = _META[:len(columns)]
    df = pd.DataFrame([meta] + [list(r) for r in rows], columns=list(columns))
    monkeypatch.setattr(queries, "read_tab", lambda *a, **k: df)


# ── legacy rows: no date columns at all ───────────────────────────────────────

def test_a_legacy_three_column_row_still_answers(monkeypatch):
    """The 31 rows on the live tab have no dates and every one is a finished
    month. A blank has to read as complete or the whole history goes dark."""
    _install(monkeypatch, [["MISSION", "2026-07", "43"]],
             columns=("zone", "month", "baptisms"))
    assert get_baptisms_actual("2026-07-01") == 43
    assert get_mission_baptisms_by_month() == {"2026-07": 43}


# ── provisional rows are refused by the strict readers ────────────────────────

def test_a_provisional_row_is_invisible_to_get_baptisms_actual(monkeypatch):
    _install(monkeypatch, [["MISSION", "2026-09", "18", "2026-09-01", "2026-09-19"]])
    assert get_baptisms_actual("2026-09-01") is None


def test_a_complete_row_with_dates_answers_normally(monkeypatch):
    _install(monkeypatch, [["MISSION", "2026-09", "41", "2026-09-01", "2026-09-30"]])
    assert get_baptisms_actual("2026-09-01") == 41


def test_the_annual_series_leaves_the_provisional_month_out(monkeypatch):
    """Plotted as an ordinary point, a month-to-date figure makes the
    cumulative line read as a collapse every time the page is opened."""
    _install(monkeypatch, [
        ["MISSION", "2026-07", "43", "2026-07-01", "2026-07-31"],
        ["MISSION", "2026-08", "46", "2026-08-01", "2026-08-31"],
        ["MISSION", "2026-09", "18", "2026-09-01", "2026-09-19"],
    ])
    assert get_mission_baptisms_by_month() == {"2026-07": 43, "2026-08": 46}
    assert get_mission_baptisms_by_month(include_provisional=True) == {
        "2026-07": 43, "2026-08": 46, "2026-09": 18}


# ── asking for the partial on purpose ─────────────────────────────────────────

def test_get_baptisms_capture_reports_the_window_and_the_flag(monkeypatch):
    _install(monkeypatch, [["MISSION", "2026-09", "18", "2026-09-01", "2026-09-19"]])
    assert get_baptisms_capture("2026-09") == {
        "baptisms": 18,
        "start_date": "2026-09-01",
        "end_date": "2026-09-19",
        "provisional": True,
    }


def test_get_baptisms_capture_is_none_when_nothing_is_stored(monkeypatch):
    _install(monkeypatch, [["MISSION", "2026-07", "43", "2026-07-01", "2026-07-31"]])
    assert get_baptisms_capture("2026-09") is None


def test_a_legacy_row_reports_itself_as_complete(monkeypatch):
    _install(monkeypatch, [["MISSION", "2026-07", "43"]],
             columns=("zone", "month", "baptisms"))
    assert get_baptisms_capture("2026-07")["provisional"] is False


# ── the one non-month window that CAN be answered ─────────────────────────────

def test_a_range_matching_a_stored_capture_exactly_is_answered(monkeypatch):
    """Not a whole month, but it is precisely the window Tableau was asked
    for — so it is the certified figure for exactly these days, not a partial
    sum of anything."""
    _install(monkeypatch, [["MISSION", "2026-09", "18", "2026-09-01", "2026-09-19"]])
    assert get_baptisms_actual_for_range(date(2026, 9, 1), date(2026, 9, 19)) == 18


def test_a_range_that_merely_overlaps_the_capture_is_still_refused(monkeypatch):
    _install(monkeypatch, [["MISSION", "2026-09", "18", "2026-09-01", "2026-09-19"]])
    assert get_baptisms_actual_for_range(date(2026, 9, 1), date(2026, 9, 15)) is None
    assert get_baptisms_actual_for_range(date(2026, 9, 3), date(2026, 9, 19)) is None


def test_a_whole_month_request_is_refused_while_only_a_partial_is_stored(monkeypatch):
    """September is not finished; asking for all of it must not get 19 days'
    worth dressed up as the month."""
    _install(monkeypatch, [["MISSION", "2026-09", "18", "2026-09-01", "2026-09-19"]])
    assert get_baptisms_actual_for_range(date(2026, 9, 1), date(2026, 9, 30)) is None


def test_whole_month_sums_still_work_over_legacy_rows(monkeypatch):
    _install(monkeypatch, [["MISSION", "2026-07", "43"], ["MISSION", "2026-08", "46"]],
             columns=("zone", "month", "baptisms"))
    assert get_baptisms_actual_for_range(date(2026, 7, 1), date(2026, 8, 31)) == 89
