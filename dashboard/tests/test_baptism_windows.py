"""R0.2 (decision 42): the nightly job captures the certified baptism figure for
each report period that is not a whole month, into its own tab.

Two things have to be right for the packet to find those figures: the job must
capture exactly the windows the packet will look up, and storing a night's
captures must neither lose a window still being asked for nor pile up one row
per night for a window that grows.
"""

from datetime import date

import pandas as pd
import pytest

from app.ingestion.tableau_finding_runner import WINDOW_PERIODS, period_windows
from app.ingestion.tableau_upload import (
    BAPTISM_WINDOW_COLUMNS, UploadError, merge_window_rows, stored_window_rows,
)
from app.reports import periods as P
from app.utils.transfer_helpers import rows_from_frame, transfer_cycles

#: TRANSFER_SCHEDULE as the live tab held it on 2026-09-23.
SCHEDULE = pd.DataFrame({
    "Transfer_Number": ["2026-4", "2026-5", "2026-6", "2026-7", "2026-8"],
    "Start_Date": ["2026-06-15", "2026-07-27", "2026-09-07", "2026-10-19",
                   "2026-11-30"],
    "Weeks": ["6", "6", "6", "6", "6"],
    "Status": ["Actual", "Actual", "Actual", "Scheduled", "Scheduled"],
})
CYCLES = transfer_cycles(rows_from_frame(SCHEDULE))


def _stored(rows) -> pd.DataFrame:
    """A tab read: header, the writer's metadata row, then the data."""
    meta = ["_uploaded_by:auto:tableau", "_uploaded_at:2026-09-23 09:04 UTC",
            "", "", ""]
    return pd.DataFrame([meta] + [list(r) for r in rows],
                        columns=list(BAPTISM_WINDOW_COLUMNS))


# ── which windows ─────────────────────────────────────────────────────────────

def test_the_schedule_parses_the_same_way_the_app_reads_it():
    assert [c["start"] for c in CYCLES][:3] == [
        date(2026, 6, 15), date(2026, 7, 27), date(2026, 9, 7)]
    assert CYCLES[1]["end"] == date(2026, 9, 6)


def test_the_four_windows_on_the_day_r01_measured():
    got = period_windows(date(2026, 9, 23), CYCLES)
    assert got == [
        (P.LAST_WEEK, date(2026, 9, 14), date(2026, 9, 20)),
        (P.THIS_TRANSFER, date(2026, 9, 7), date(2026, 9, 23)),
        (P.LAST_TRANSFER, date(2026, 7, 27), date(2026, 9, 6)),
        (P.LAST_6_WEEKS, date(2026, 8, 10), date(2026, 9, 20)),
    ]


def test_the_windows_are_the_ones_the_packet_resolves():
    """The whole point: the job and the packet ask `periods.resolve` the same
    question, so a stored window is always one the packet will look for."""
    today = date(2026, 10, 2)
    for key, start, end in period_windows(today, CYCLES):
        period = P.resolve(key, today, CYCLES)
        assert (period.start, period.end) == (start, end)


def test_the_month_periods_are_left_to_the_month_captures():
    assert P.CALENDAR_MONTH not in WINDOW_PERIODS
    assert P.YEAR not in WINDOW_PERIODS


def test_without_a_schedule_only_the_calendar_windows_are_captured():
    keys = [k for k, _, _ in period_windows(date(2026, 9, 23), [])]
    assert keys == [P.LAST_WEEK, P.LAST_6_WEEKS]


def test_two_periods_on_the_same_days_are_captured_once():
    """A one-week schedule makes last week and last transfer the same days."""
    one_week = transfer_cycles(rows_from_frame(pd.DataFrame({
        "Transfer_Number": ["a", "b", "c"],
        "Start_Date": ["2026-09-07", "2026-09-14", "2026-09-21"],
        "Weeks": ["1", "1", "1"], "Status": ["", "", ""],
    })))
    got = period_windows(date(2026, 9, 23), one_week)
    days = [(s, e) for _, s, e in got]
    assert len(days) == len(set(days))
    assert (P.LAST_TRANSFER, date(2026, 9, 14), date(2026, 9, 20)) not in got


# ── storing them ──────────────────────────────────────────────────────────────

def test_the_metadata_row_is_not_read_as_a_window():
    rows = stored_window_rows(_stored([
        ("last_week", "2026-09-14", "2026-09-20", "5", "2026-09-22")]))
    assert rows == [["last_week", "2026-09-14", "2026-09-20", 5, "2026-09-22"]]


def test_a_recapture_of_the_same_days_replaces_the_old_figure():
    """A baptism recorded late lands in tonight's capture of the same days."""
    out = merge_window_rows(
        _stored([("last_week", "2026-09-14", "2026-09-20", "5", "2026-09-21")]),
        [("last_week", "2026-09-14", "2026-09-20", 6, "2026-09-22")])
    assert out.values.tolist() == [
        ["last_week", "2026-09-14", "2026-09-20", 6, "2026-09-22"]]


def test_a_growing_window_keeps_one_row_not_one_per_night():
    stored = _stored([("this_transfer", "2026-09-07", "2026-09-22", "11",
                       "2026-09-22")])
    out = merge_window_rows(stored, [("this_transfer", "2026-09-07",
                                      "2026-09-23", 12, "2026-09-23")])
    assert out.values.tolist() == [
        ["this_transfer", "2026-09-07", "2026-09-23", 12, "2026-09-23"]]


def test_a_week_sharing_its_first_day_with_the_transfer_survives():
    """14 Sep: last week is 7–13 Sep and this transfer is 7–14 Sep. Pruning by
    first day alone would throw the week away for the transfer's longer row."""
    out = merge_window_rows(_stored([]), [
        ("last_week", "2026-09-07", "2026-09-13", 4, "2026-09-14"),
        ("this_transfer", "2026-09-07", "2026-09-14", 4, "2026-09-14"),
    ])
    assert [(r[0], r[2]) for r in out.values.tolist()] == [
        ("last_week", "2026-09-13"), ("this_transfer", "2026-09-14")]


def test_a_transfer_that_closes_keeps_its_final_figure_under_its_new_name():
    stored = _stored([("this_transfer", "2026-07-27", "2026-09-06", "43",
                       "2026-09-06")])
    out = merge_window_rows(stored, [
        ("last_transfer", "2026-07-27", "2026-09-06", 44, "2026-09-07"),
        ("this_transfer", "2026-09-07", "2026-09-07", 0, "2026-09-07"),
    ])
    assert out.values.tolist() == [
        ["last_transfer", "2026-07-27", "2026-09-06", 44, "2026-09-07"],
        ["this_transfer", "2026-09-07", "2026-09-07", 0, "2026-09-07"],
    ]


def test_windows_nobody_asks_for_tonight_are_kept():
    """A night whose capture fails must not cost the figures already stored."""
    stored = _stored([("last_6_weeks", "2026-08-03", "2026-09-13", "45",
                       "2026-09-20")])
    out = merge_window_rows(stored, [("last_week", "2026-09-14", "2026-09-20",
                                      5, "2026-09-21")])
    assert len(out) == 2


def test_a_window_that_ends_before_it_starts_is_refused():
    with pytest.raises(UploadError):
        merge_window_rows(_stored([]), [("last_week", "2026-09-20",
                                         "2026-09-14", 5, "")])


def test_the_stored_frame_has_the_tabs_columns():
    out = merge_window_rows(None, [("last_week", "2026-09-14", "2026-09-20",
                                    5, "2026-09-21")])
    assert tuple(out.columns) == BAPTISM_WINDOW_COLUMNS
