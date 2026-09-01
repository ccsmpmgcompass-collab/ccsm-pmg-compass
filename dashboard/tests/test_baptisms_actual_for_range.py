"""get_baptisms_actual_for_range sums TABLEAU_BAPTISMS one whole calendar
month at a time. It exists because the Finding Funnel's own "Baptized" stage
counts Detail's confirmation_date instead, and was found live to disagree
with Tableau's own certified monthly PDFs by ~25% over a full year (301
tracked vs. 403 certified) -- this is the number that should be trusted for
reporting, and it must never return a partial (silently low) sum.
"""

from datetime import date

from app.db import queries
from app.db.queries import get_baptisms_actual_for_range

MONTHLY = {
    "2025-01": 30, "2025-02": 25, "2025-03": 40, "2025-11": 35, "2025-12": 38,
}


def _install(monkeypatch, table=MONTHLY):
    monkeypatch.setattr(queries, "get_baptisms_actual",
                        lambda month_start: table.get(str(month_start)[:7]))


def test_sums_a_single_whole_month(monkeypatch):
    _install(monkeypatch)
    assert get_baptisms_actual_for_range(date(2025, 1, 1), date(2025, 1, 31)) == 30


def test_sums_several_whole_months_across_a_year_boundary(monkeypatch):
    _install(monkeypatch)
    table = {**MONTHLY, "2026-01": 20}
    _install(monkeypatch, table)
    assert get_baptisms_actual_for_range(date(2025, 11, 1), date(2026, 1, 31)) == 35 + 38 + 20


def test_accepts_string_dates_too(monkeypatch):
    _install(monkeypatch)
    assert get_baptisms_actual_for_range("2025-01-01", "2025-01-31") == 30


def test_none_when_range_is_not_whole_calendar_months(monkeypatch):
    _install(monkeypatch)
    assert get_baptisms_actual_for_range(date(2025, 1, 5), date(2025, 1, 31)) is None
    assert get_baptisms_actual_for_range(date(2025, 1, 1), date(2025, 1, 30)) is None


def test_none_rather_than_a_partial_sum_when_a_month_is_missing(monkeypatch):
    """2025-04 has no capture -- must not silently return just January-March's 95."""
    _install(monkeypatch)
    assert get_baptisms_actual_for_range(date(2025, 1, 1), date(2025, 4, 30)) is None
