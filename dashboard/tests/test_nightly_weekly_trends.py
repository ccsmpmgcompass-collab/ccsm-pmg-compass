"""Nightly metrics must have a weekly source.

CCSM's WEEKLY_KI is structurally different from Utah Provo's. Provo derives
WEEKLY_KI from DAILY_LOG, so it holds nightly rollups and any nightly metric
can be trended straight off it. CCSM_Agent5A.gs replaced that wholesale — its
header says so explicitly under "STRUCTURAL CHANGE vs Provo" — and CCSM's
WEEKLY_KI is a parse of the weekly form's Real/Meta columns, holding ONLY the
seven ki_* pairs and no nightly metric at all.

So every nightly metric routed to get_weekly_ki_trends() found no such column.
A trend or projection over a missing column is not an error: it is an empty or
flat series that renders as a confident-looking chart of nothing.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

import app.db.queries as q

# CCSM's real WEEKLY_KI schema, per CCSM_Agent5A.gs — ki_* pairs only.
WEEKLY_KI = pd.DataFrame([
    {"week_end_date": "2026-08-09", "area": "Arauco 1", "zone": "Arauco",
     "district": "Arauco", "ki_new_people_real": 3, "ki_new_people_meta": 5},
    {"week_end_date": "2026-08-16", "area": "Arauco 1", "zone": "Arauco",
     "district": "Arauco", "ki_new_people_real": 4, "ki_new_people_meta": 5},
])


def _daily_log_rows():
    """Two full Mon–Sun weeks of nightly submissions for two areas."""
    rows = []
    # 2026-08-03 is a Monday; 2026-08-09 the Sunday that ends that week.
    start = date(2026, 8, 3)
    for wk in range(2):
        for day in range(7):
            d = start + timedelta(days=wk * 7 + day)
            for area in ("Arauco 1", "Lota 1"):
                rows.append({
                    "Date": d.isoformat(), "Area": area, "Zone": "Arauco",
                    "District": "Arauco",
                    "contacts_attempted": 10,
                    "contacts_made": 4,
                })
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    daily = _daily_log_rows()

    def fake(tab_name, header_marker=None):
        if tab_name == "DAILY_LOG":
            return daily.copy()
        if tab_name == "WEEKLY_KI":
            return WEEKLY_KI.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    for fn in (q.get_daily_log, q.get_weekly_ki):
        fn.clear()
    yield
    for fn in (q.get_daily_log, q.get_weekly_ki):
        fn.clear()


def test_weekly_ki_really_does_lack_nightly_metrics():
    """The premise. If this ever fails, CCSM_Agent5A changed and the extra
    DAILY_LOG path below may no longer be needed."""
    wki = q.get_weekly_ki()
    assert "ki_new_people_real" in wki.columns
    assert "contacts_attempted" not in wki.columns


def test_nightly_metrics_bucket_into_weeks_from_daily_log():
    trends = q.get_nightly_weekly_trends(n_weeks=8)
    assert not trends.empty, "no weekly trend produced from a full DAILY_LOG"
    assert "contacts_attempted" in trends.columns
    assert set(trends["week_end_date"]) == {"2026-08-09", "2026-08-16"}, \
        f"weeks did not snap to Sunday: {sorted(trends['week_end_date'])}"


def test_weekly_totals_are_the_sum_of_that_week_only():
    """2 areas x 7 days x 10 attempts = 140 per week. A wrong week boundary
    shows up here as 280 (both weeks merged) or 20 (one day)."""
    trends = q.get_nightly_weekly_trends(n_weeks=8).set_index("week_end_date")
    assert float(trends.loc["2026-08-09", "contacts_attempted"]) == 140.0
    assert float(trends.loc["2026-08-16", "contacts_attempted"]) == 140.0
    assert float(trends.loc["2026-08-09", "contacts_made"]) == 56.0


def test_meta_columns_are_not_summed_as_metrics():
    trends = q.get_nightly_weekly_trends(n_weeks=8)
    for col in ("Area", "Zone", "District", "Date"):
        assert col not in trends.columns


def test_projection_falls_through_to_daily_log_for_a_nightly_metric(monkeypatch):
    """The routing fix. A nightly metric must reach a real series instead of
    silently projecting an absent WEEKLY_KI column."""
    seen = {}
    real = q.get_nightly_weekly_trends

    def spy(*a, **k):
        seen["called"] = True
        return real(*a, **k)

    monkeypatch.setattr(q, "get_nightly_weekly_trends", spy)
    q.project_next_week(metric_key="contacts_attempted", n_weeks=4)
    assert seen.get("called"), \
        "a nightly metric did not fall through to the DAILY_LOG weekly series"


def test_projection_does_not_use_daily_log_for_a_weekly_form_metric(monkeypatch):
    """The other direction: a weekly-form metric must stay on the weekly-form
    source, or it would be projected off a series that does not contain it."""
    seen = {}
    monkeypatch.setattr(q, "get_nightly_weekly_trends",
                        lambda *a, **k: seen.setdefault("called", True) or pd.DataFrame())
    q.project_next_week(metric_key="ki_new_people_real", n_weeks=4)
    assert not seen.get("called"), \
        "a weekly-form metric was routed to the nightly DAILY_LOG series"


def test_empty_daily_log_yields_no_trend_rather_than_a_fake_one():
    import app.db.sheets_client as sc
    sc._read_tab_cached = lambda tab, header_marker=None: pd.DataFrame()
    q.get_daily_log.clear()
    assert q.get_nightly_weekly_trends(n_weeks=8).empty
