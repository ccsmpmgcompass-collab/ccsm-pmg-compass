"""Regression for audit finding B1 (AUDIT-IA-2026-08-22.md).

get_weekly_ki() called read_tab("WEEKLY_KI", header_marker="week_end_date"),
but CCSM_Agent5A.gs's a5a_writeWeeklyKI (CCSM_Agent5A.gs:739) writes the real
header row as Week_End_Date|Area|Zone|District — Proper_Case, not lower_case.
sheets_client._read_tab_cached's header_marker match is a case-sensitive `in`
check, so the marker never matched and get_weekly_ki() silently returned empty
every single call — 34 good WEEKLY_KI rows were unreachable in production.

Unlike test_nightly_weekly_trends.py's fixture (which patches
_read_tab_cached directly and so bypasses the header_marker matching that this
bug lives in), this test patches one level lower, at _get_worksheet, so the
real header-row scan in _read_tab_cached actually runs.
"""

import pandas as pd
import pytest

from app.db import sheets_client as sc
from app.db import queries as q


class _FakeWorksheet:
    def __init__(self, rows):
        self._rows = rows

    def get_all_values(self):
        return self._rows


# The exact header CCSM_Agent5A.gs writes (CCSM_Agent5A.gs:739-741).
REAL_HEADER = ["Week_End_Date", "Area", "Zone", "District",
               "ki_new_people_real", "ki_new_people_meta",
               "leader_call", "correlation_meeting"]


@pytest.fixture(autouse=True)
def _fake_sheet(monkeypatch):
    rows = [
        REAL_HEADER,
        ["2026-08-16", "Arauco 1", "Arauco", "Arauco", "3", "5", "Si", "No"],
        ["2026-08-16", "Arauco 2", "Arauco", "Arauco", "4", "5", "No", "Si"],
    ]
    ws = _FakeWorksheet(rows)
    monkeypatch.setattr(sc, "_get_worksheet", lambda name: ws)
    q.get_weekly_ki.clear()
    yield
    q.get_weekly_ki.clear()


def test_get_weekly_ki_reads_the_real_proper_case_header():
    df = q.get_weekly_ki()
    assert not df.empty, (
        "get_weekly_ki() returned nothing against the real WEEKLY_KI header "
        "shape — the header_marker case mismatch (B1) is back"
    )
    assert len(df) == 2
    assert set(df["area"]) == {"Arauco 1", "Arauco 2"}


def test_get_weekly_ki_normalises_columns_to_lowercase():
    df = q.get_weekly_ki()
    for col in ("week_end_date", "area", "zone", "district"):
        assert col in df.columns, f"expected lowercase '{col}' in {list(df.columns)}"
    assert "Week_End_Date" not in df.columns
