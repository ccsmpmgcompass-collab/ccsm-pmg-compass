"""R0.3 (decisions 41, 42): the baptism figure follows the selected period, and
it is the certified figure in every case or no figure at all.

The numbers are the ones R0.1 measured on 2026-09-23: 319 certified through
August, 24 in September's month-to-date capture (1–23 Sep), and — once the
nightly job has run — a window capture for each period that is not a month.
"""

from datetime import date

import pandas as pd

from app.reports import periods as P
from app.reports import tableau as TB
from app.utils.transfer_helpers import rows_from_frame, transfer_cycles

TODAY = date(2026, 9, 23)
CYCLES = transfer_cycles(rows_from_frame(pd.DataFrame({
    "Transfer_Number": ["2026-4", "2026-5", "2026-6", "2026-7"],
    "Start_Date": ["2026-06-15", "2026-07-27", "2026-09-07", "2026-10-19"],
    "Weeks": ["6", "6", "6", "6"],
    "Status": ["Actual", "Actual", "Actual", "Scheduled"],
})))

CERTIFIED = {"2026-01": 19, "2026-02": 37, "2026-03": 47, "2026-04": 44,
             "2026-05": 43, "2026-06": 46, "2026-07": 47, "2026-08": 36}
OPEN = ("2026-09", 24, date(2026, 9, 23))
WINDOWS = (
    (date(2026, 9, 14), date(2026, 9, 20), 5),
    (date(2026, 9, 7), date(2026, 9, 23), 12),
    (date(2026, 7, 27), date(2026, 9, 6), 48),
    (date(2026, 8, 10), date(2026, 9, 20), 51),
)


def _period(key, today=TODAY):
    return P.resolve(key, today, CYCLES)


def _figure(key, *, certified=CERTIFIED, open_month=OPEN, windows=WINDOWS,
            today=TODAY):
    return TB.period_baptisms(_period(key, today), certified=certified,
                              open_month=open_month, windows=windows)


# ── each period answers with its own days ─────────────────────────────────────

def test_the_month_is_its_own_month_to_date_capture():
    fig = _figure(P.CALENDAR_MONTH)
    assert fig.present and fig.count == 24
    assert (fig.window.start, fig.window.end) == (date(2026, 9, 1),
                                                  date(2026, 9, 23))
    assert not fig.window.clipped


def test_the_transfer_is_its_window_capture():
    fig = _figure(P.THIS_TRANSFER)
    assert fig.count == 12
    assert fig.window.label == "7 de sep - 23 de sep de 2026"
    assert fig.caption == ("cifra certificada · fuente: Tableau · "
                           "7 de sep - 23 de sep de 2026")


def test_each_window_period_gets_its_own_figure():
    got = {k: _figure(k).count for k in (P.LAST_WEEK, P.THIS_TRANSFER,
                                         P.LAST_TRANSFER, P.LAST_6_WEEKS)}
    assert got == {P.LAST_WEEK: 5, P.THIS_TRANSFER: 12,
                   P.LAST_TRANSFER: 48, P.LAST_6_WEEKS: 51}


def test_the_year_is_the_closed_months_and_the_open_one():
    """Zackary: "if it's for transfer up to date, put all of them"."""
    fig = _figure(P.YEAR)
    assert fig.count == 319 + 24
    assert (fig.window.start, fig.window.end) == (date(2026, 1, 1),
                                                  date(2026, 9, 23))
    assert (fig.closed, fig.closed_months, fig.open_count) == (319, 8, 24)
    assert fig.composition == ("319 de meses cerrados y 24 de septiembre, "
                               "que todavía no cierra")


# ── a capture that stops short says so ────────────────────────────────────────

def test_a_capture_a_night_behind_answers_with_its_own_days():
    windows = ((date(2026, 9, 7), date(2026, 9, 22), 11),)
    fig = _figure(P.THIS_TRANSFER, windows=windows)
    assert fig.count == 11
    assert fig.window.clipped
    assert fig.window.shortfall_label == "16 de 17 días del período"
    assert fig.caption.endswith("16 de 17 días del período")


def test_the_latest_capture_that_fits_wins():
    windows = ((date(2026, 9, 7), date(2026, 9, 21), 10),
               (date(2026, 9, 7), date(2026, 9, 22), 11))
    assert _figure(P.THIS_TRANSFER, windows=windows).count == 11


def test_a_week_is_not_answered_by_the_longer_transfer_sharing_its_first_day():
    """On 14 Sep last week is 7–13 Sep and the transfer 7–14 Sep."""
    today = date(2026, 9, 14)
    windows = ((date(2026, 9, 7), date(2026, 9, 13), 4),
               (date(2026, 9, 7), date(2026, 9, 14), 5))
    assert _figure(P.LAST_WEEK, windows=windows, today=today).count == 4
    assert _figure(P.THIS_TRANSFER, windows=windows, today=today).count == 5


def test_a_capture_for_days_after_the_period_is_never_used():
    windows = ((date(2026, 9, 14), date(2026, 9, 21), 6),)
    assert not _figure(P.LAST_WEEK, windows=windows).present


def test_the_year_without_an_open_capture_stops_at_august_and_says_so():
    fig = _figure(P.YEAR, open_month=())
    assert fig.count == 319
    assert fig.window.end == date(2026, 8, 31)
    assert fig.window.clipped
    assert fig.composition == ""


def test_the_year_stops_at_a_missing_month_rather_than_skipping_it():
    """A running total after an unknown month is itself unknown."""
    gappy = {k: v for k, v in CERTIFIED.items() if k != "2026-03"}
    fig = _figure(P.YEAR, certified=gappy)
    assert fig.count != sum(gappy.values()) + 24
    assert not fig.present or fig.window.end <= date(2026, 2, 28)


# ── no figure rather than the wrong one ───────────────────────────────────────

def test_a_period_nothing_has_captured_is_refused_with_its_reason():
    fig = _figure(P.THIS_TRANSFER, windows=())
    assert not fig.present
    assert fig.count is None
    assert "sincronización nocturna" in fig.reason


def test_a_capture_covering_under_a_quarter_of_the_period_is_refused():
    windows = ((date(2026, 7, 27), date(2026, 8, 2), 7),)
    fig = _figure(P.LAST_TRANSFER, windows=windows)
    assert not fig.present
    assert "7 de 42 días" in fig.reason


def test_a_year_with_no_capture_at_all_is_refused():
    fig = _figure(P.YEAR, certified={}, open_month=())
    assert not fig.present and "2026" in fig.reason


def test_the_resolver_takes_no_detail_export_at_all():
    """Decision 42 is structural: there is no argument to hand it one."""
    import inspect
    params = inspect.signature(TB.period_baptisms).parameters
    assert set(params) == {"period", "certified", "open_month", "windows",
                           "floor"}
