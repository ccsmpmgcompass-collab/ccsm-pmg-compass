"""Regression for audit finding B4 (AUDIT-IA-2026-08-22.md).

06_Puntajes.py's Daily Activity tab lets the user filter to a Zone/District,
and every section on the tab (Mission Totals, Daily Trend, By Area) honoured
it — except Effort Reporting, which read DASHBOARD_SUMMARY's EFFORT rows.
Those rows are computed mission-wide by CCSM_Agent5A.gs's
a5a_getEffortBreakdown over a hardcoded last-7-days window and carry no
Zone/District column at all, so picking a zone above did nothing to that
section: it always showed the same mission-wide numbers.

The fix reads DAILY_LOG's own `effort` text via get_daily_effort_log()
(already scoped by Zone/District/Area, same as the rest of the tab) and
buckets it with effort_breakdown.normalize_level — the same Todo/La mayor
parte/Algo mapping CCSM_Helpers.gs's ccsmEffortScore uses. This test proves
that data path actually narrows per zone, which is the part
DASHBOARD_SUMMARY's EFFORT rows structurally could not do.
"""

import pandas as pd
import pytest

from app.analytics.effort_breakdown import normalize_level
from app.db import queries as q


def _daily_log_rows():
    # Arauco 1 (District Arauco) answers "Todo" every night; Lota 2 (District
    # Lota, same Zone) answers "Algo" every night. A zone-only filter cannot
    # tell them apart; a district filter must.
    rows = []
    for d in ("2026-08-03", "2026-08-04", "2026-08-05"):
        rows.append({"Date": d, "Area": "Arauco 1", "Zone": "Arauco",
                      "District": "Arauco", "effort": "Todo"})
        rows.append({"Date": d, "Area": "Lota 2", "Zone": "Arauco",
                      "District": "Lota", "effort": "Algo"})
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    daily = _daily_log_rows()

    def fake(tab_name, header_marker=None):
        if tab_name == "DAILY_LOG":
            return daily.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    q.get_daily_effort_log.clear()
    yield
    q.get_daily_effort_log.clear()


def _bucket(effort_log: pd.DataFrame) -> dict:
    """Mirrors 06_Puntajes.py's _render_daily_tab Effort Reporting bucketing."""
    levels = effort_log["effort"].apply(normalize_level)
    answered = effort_log.assign(_level=levels).dropna(subset=["_level"])
    return answered["_level"].value_counts().to_dict()


def test_district_filter_isolates_that_districts_own_answers():
    log = q.get_daily_effort_log(30)
    scoped = log[log["District"] == "Lota"]
    counts = _bucket(scoped)
    assert counts == {"some": 3}, (
        "District-scoped effort counts leaked another district's answers "
        f"(or fell back to a mission-wide total): {counts}"
    )


def test_a_zone_wide_view_still_sums_every_district_in_it():
    log = q.get_daily_effort_log(30)
    scoped = log[log["Zone"] == "Arauco"]
    counts = _bucket(scoped)
    assert counts == {"all": 3, "some": 3}


def test_scoping_actually_changes_the_result():
    """The regression's exact shape: before the fix, Effort Reporting showed
    identical numbers no matter what the Zone/District selector was set to."""
    log = q.get_daily_effort_log(30)
    lota_only = _bucket(log[log["District"] == "Lota"])
    arauco_only = _bucket(log[log["District"] == "Arauco"])
    assert lota_only != arauco_only
