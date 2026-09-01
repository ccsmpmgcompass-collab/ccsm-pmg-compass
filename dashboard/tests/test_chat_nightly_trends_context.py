"""Regression: the Mission Assistant's "nightly form" trend section was empty.

load_weekly_trends_context() called get_weekly_ki_trends(8) and labelled the
result "Mission-wide weekly totals from the nightly form" — but that function
only ever returns the WEEKLY form's ki_* columns (see AUDIT-IA-2026-08-22.md's
B2, and get_nightly_weekly_trends' own docstring). A nightly metric like
contacts_attempted could never appear there, so the model silently received an
empty nightly section under a confident label every single call.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

import app.chat.gemini_chat as gc
from app.db import queries as q


def _daily_log_rows():
    rows = []
    start = date(2026, 8, 3)  # a Monday
    for wk in range(2):
        for day in range(7):
            d = start + timedelta(days=wk * 7 + day)
            rows.append({
                "Date": d.isoformat(), "Area": "Arauco 1", "Zone": "Arauco",
                "District": "Arauco", "contacts_attempted": 10,
            })
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    daily = _daily_log_rows()

    def fake(tab_name, header_marker=None):
        if tab_name == "DAILY_LOG":
            return daily.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    q.get_daily_log.clear()
    yield
    q.get_daily_log.clear()


def test_nightly_trends_context_carries_real_nightly_numbers():
    text = gc.load_weekly_trends_context()
    assert "nightly form" in text
    assert "contacts_attempted=70" in text, (
        "nightly section of the chat context is empty even with two full "
        f"weeks of DAILY_LOG data. Got:\n{text}"
    )
