"""Tests for the chunked tab write in app/db/sheets_client.py.

save_dataframe used to be a single ws.update() of the whole frame. The real
Tableau Detail export is 89,824 x 14 = 1,257,536 cells, which serialises to a
17.4 MB request body — measured against the live file, not estimated — so the
write had to be split. The risk in splitting it is arithmetic: an A1 range off
by one shifts every row beneath it and nothing complains.
"""

import pandas as pd
import pytest

from app.db import sheets_client as sc
from app.db.sheets_client import _col_letter, plan_write_chunks


# ── the arithmetic ────────────────────────────────────────────────────────────

def test_col_letter_crosses_into_two_letters():
    assert _col_letter(1) == "A"
    assert _col_letter(14) == "N"     # the Detail export's width
    assert _col_letter(26) == "Z"
    assert _col_letter(27) == "AA"
    assert _col_letter(52) == "AZ"
    assert _col_letter(53) == "BA"


def test_a_frame_smaller_than_a_chunk_is_one_call():
    assert plan_write_chunks(5, 3) == [("A1:C5", 0, 5)]


def test_chunks_tile_the_rows_with_no_gap_and_no_overlap():
    plan = plan_write_chunks(25, 2, chunk_size=10)
    assert [r for r, _, _ in plan] == ["A1:B10", "A11:B20", "A21:B25"]
    covered = []
    for _, lo, hi in plan:
        covered.extend(range(lo, hi))
    assert covered == list(range(25))


def test_an_exact_multiple_does_not_emit_a_trailing_empty_chunk():
    plan = plan_write_chunks(20, 2, chunk_size=10)
    assert len(plan) == 2
    assert plan[-1] == ("A11:B20", 10, 20)


def test_nothing_to_write_plans_nothing():
    assert plan_write_chunks(0, 5) == []
    assert plan_write_chunks(5, 0) == []


def test_the_real_export_shape_fits_in_nine_calls():
    """89,824 data rows + header + meta, 14 columns."""
    plan = plan_write_chunks(89_826, 14)
    assert len(plan) == 9
    assert plan[0][0] == "A1:N10000"
    assert plan[-1][0] == "A80001:N89826"


# ── save_dataframe drives it correctly ────────────────────────────────────────

class _FakeWorksheet:
    def __init__(self, rows=5000, cols=50):
        self.row_count, self.col_count = rows, cols
        self.cleared = False
        self.resized_to = None
        self.writes = []

    def clear(self):
        self.cleared = True

    def resize(self, rows=None, cols=None):
        self.resized_to = (rows, cols)
        self.row_count, self.col_count = rows, cols

    def update(self, values, range_name=None, **kw):
        if len(values) > self.row_count:
            raise AssertionError("write ran past the grid — resize did not happen")
        self.writes.append((range_name, values))


@pytest.fixture
def fake_ws(monkeypatch):
    ws = _FakeWorksheet()
    monkeypatch.setattr(sc, "_get_worksheet", lambda name: ws)
    return ws


def test_save_dataframe_writes_every_row_exactly_once(fake_ws, monkeypatch):
    monkeypatch.setattr(sc, "WRITE_CHUNK_ROWS", 10_000)
    df = pd.DataFrame({"a": [str(i) for i in range(25)],
                       "b": [str(-i) for i in range(25)]})

    sc.save_dataframe("SOME_TAB", df, uploaded_by="tester@example.org")

    assert fake_ws.cleared
    written = [row for _, values in fake_ws.writes for row in values]
    # header, then the metadata row, then every data row in order
    assert written[0] == ["a", "b"]
    assert written[1][0] == "_uploaded_by:tester@example.org"
    assert written[1][1].startswith("_uploaded_at:")
    assert [r[0] for r in written[2:]] == [str(i) for i in range(25)]
    assert len(written) == 27


def test_save_dataframe_chunks_a_frame_bigger_than_the_limit(fake_ws, monkeypatch):
    monkeypatch.setattr(sc, "WRITE_CHUNK_ROWS", 10)
    df = pd.DataFrame({"a": [str(i) for i in range(48)]})

    sc.save_dataframe("SOME_TAB", df)

    # 48 data rows + header + meta = 50 rows at 10 per call
    assert len(fake_ws.writes) == 5
    assert [r for r, _ in fake_ws.writes] == [
        "A1:A10", "A11:A20", "A21:A30", "A31:A40", "A41:A50"]
    written = [row for _, values in fake_ws.writes for row in values]
    assert [r[0] for r in written[2:]] == [str(i) for i in range(48)]


def test_the_grid_is_resized_to_exactly_what_is_needed(fake_ws):
    """Not at-least: the 10M-cell cap counts empty grid cells too, so leaving
    a 89k-row tab 50 columns wide would burn 4.5M of the budget on nothing."""
    df = pd.DataFrame({"a": ["1"], "b": ["2"], "c": ["3"]})

    sc.save_dataframe("SOME_TAB", df)

    assert fake_ws.resized_to == (3, 3)  # header + meta + 1 data row, 3 columns


def test_a_frame_with_no_columns_is_refused_not_written(fake_ws):
    sc.save_dataframe("SOME_TAB", pd.DataFrame())
    assert fake_ws.writes == []


def test_a_failing_chunk_says_which_one_it_was(fake_ws, monkeypatch):
    """A chunked write that dies partway leaves the tab half-populated. The
    warning has to distinguish that from nothing having been written."""
    monkeypatch.setattr(sc, "WRITE_CHUNK_ROWS", 10)
    calls = {"n": 0}

    def boom(values, range_name=None, **kw):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("API 500")
        fake_ws.writes.append((range_name, values))

    monkeypatch.setattr(fake_ws, "update", boom)
    warnings = []
    monkeypatch.setattr(sc, "t", lambda text, **kw: text.format(**kw) if kw else text)

    import streamlit as st
    monkeypatch.setattr(st, "warning", lambda msg: warnings.append(str(msg)))

    sc.save_dataframe("SOME_TAB", pd.DataFrame({"a": [str(i) for i in range(48)]}))

    assert warnings, "a failed write must surface"
    assert "chunk 3 of 5" in warnings[0]
    assert "rows 21-30" in warnings[0]
