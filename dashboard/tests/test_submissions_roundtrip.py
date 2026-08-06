"""Corrections must round-trip: write, read back, compare.

Asserting "update_cells was called" passes on a save that writes to the wrong
column, drops half the fields, or targets the wrong row — which is exactly how
CCSM's Monthly Goals save reported success while writing nothing. So this file
stands up a FAKE SHEET that implements the same read/write surface as
app.db.sheets_client and then reads the values back through the real query
functions.

The fake is deliberately faithful to the awkward parts of the real thing:
positional A1 writes, a header that is not necessarily row 1, and a DAILY_LOG
that starts out completely empty — which is what COMPASS_CCSM's actually looked
like on 2026-08-01, before the nightly agent had ever populated it.

Never runs against the live sheet.
"""

import re

import pytest

from app.db import submissions_queries as sq


# ── A fake COMPASS_CCSM ───────────────────────────────────────────────────────

class FakeSheet:
    def __init__(self, tabs: dict[str, list[list]]):
        self.tabs = {k: [list(r) for r in v] for k, v in tabs.items()}
        self.write_calls = 0

    # -- mirrors app.db.sheets_client --
    def read_values(self, tab):
        return [list(r) for r in self.tabs.get(tab, [])]

    def append_row(self, tab, row, scoped=False):
        self.write_calls += 1
        self.tabs.setdefault(tab, []).append(list(row))

    def update_cells(self, tab, updates, scoped=False):
        self.write_calls += 1
        grid = self.tabs.setdefault(tab, [])
        for a1, value in updates:
            m = re.fullmatch(r"([A-Z]+)(\d+)", a1)
            assert m, f"malformed A1 reference {a1!r}"
            col_letters, row_no = m.group(1), int(m.group(2))
            col = 0
            for ch in col_letters:
                col = col * 26 + (ord(ch) - ord("A") + 1)
            col -= 1
            while len(grid) < row_no:
                grid.append([])
            row = grid[row_no - 1]
            while len(row) <= col:
                row.append("")
            row[col] = value


NIGHTLY_HEADER = ["Date", "Area", "Zone", "District",
                  "contacts_attempted", "contacts_made",
                  "meaningful_conversations", "effort"]

WEEKLY_HEADER = ["Week_End_Date", "Area", "Zone", "District",
                 "ki_new_people_real", "ki_new_people_meta",
                 "ki_baptized_confirmed_real"]


def _populated_tabs():
    return {
        "DAILY_LOG": [
            NIGHTLY_HEADER,
            ["2026-07-30", "Arauco 1", "Arauco", "Arauco", "40", "22", "9", "Todo"],
            ["2026-07-31", "Arauco 1", "Arauco", "Arauco", "35", "18", "7", "Algo"],
            ["2026-07-31", "Lota 2", "Arauco", "Lota", "50", "30", "12", "Todo"],
        ],
        "WEEKLY_KI": [
            WEEKLY_HEADER,
            ["2026-07-26", "Arauco 1", "Arauco", "Arauco", "3", "5", "0"],
        ],
        "AUDIT_LOG": [],
    }


@pytest.fixture
def sheet(monkeypatch):
    fake = FakeSheet(_populated_tabs())
    monkeypatch.setattr(sq, "read_values", fake.read_values)
    monkeypatch.setattr(sq, "append_row", fake.append_row)
    monkeypatch.setattr(sq, "update_cells", fake.update_cells)
    return fake


# ── Reading ───────────────────────────────────────────────────────────────────

def test_reads_the_right_row(sheet):
    row = sq.get_nightly_submission("Arauco 1", "2026-07-31")
    assert row["contacts_attempted"] == "35"
    assert row["effort"] == "Algo"
    assert row["Zone"] == "Arauco"


def test_area_and_date_must_both_match(sheet):
    """Two areas share 2026-07-31 and one area has two dates. Matching on
    either alone returns another companionship's report."""
    assert sq.get_nightly_submission("Lota 2", "2026-07-31")["contacts_attempted"] == "50"
    assert sq.get_nightly_submission("Arauco 1", "2026-07-30")["contacts_attempted"] == "40"
    assert sq.get_nightly_submission("Lota 2", "2026-07-30") is None


def test_date_cell_typed_as_a_datetime_still_matches(sheet):
    """Google frequently stores a date cell as '2026-07-31 0:00:00'. Comparing
    the raw strings would find no row and silently offer to backfill a
    duplicate."""
    sheet.tabs["DAILY_LOG"][1][0] = "2026-07-30 0:00:00"
    assert sq.get_nightly_submission("Arauco 1", "2026-07-30") is not None


def test_lists_dates_newest_first(sheet):
    assert sq.nightly_dates_for_area("Arauco 1") == ["2026-07-31", "2026-07-30"]


def test_editable_columns_exclude_identity(sheet):
    cols = sq.nightly_metric_columns()
    assert "contacts_attempted" in cols
    for identity in ("Date", "Area", "Zone", "District"):
        assert identity not in cols


# ── The round trip ────────────────────────────────────────────────────────────

def test_edit_round_trips(sheet):
    written, err = sq.save_nightly_submission(
        "Arauco 1", "2026-07-31",
        {"contacts_attempted": 99, "meaningful_conversations": 12},
        edited_by="lider@missionary.org",
    )
    assert err == ""
    assert written == 2

    back = sq.get_nightly_submission("Arauco 1", "2026-07-31")
    assert back["contacts_attempted"] == "99"
    assert back["meaningful_conversations"] == "12"


def test_edit_leaves_every_other_field_alone(sheet):
    """A save that rewrites the whole row would quietly zero the metrics the
    editor did not show."""
    before_other_area = sq.get_nightly_submission("Lota 2", "2026-07-31")
    before_same_area = sq.get_nightly_submission("Arauco 1", "2026-07-30")

    sq.save_nightly_submission("Arauco 1", "2026-07-31",
                               {"contacts_attempted": 99},
                               edited_by="lider@missionary.org")

    after = sq.get_nightly_submission("Arauco 1", "2026-07-31")
    assert after["contacts_made"] == "18", "an untouched metric changed"
    assert after["effort"] == "Algo", "a CHOICE metric was overwritten"
    assert after["Zone"] == "Arauco"
    assert sq.get_nightly_submission("Lota 2", "2026-07-31") == before_other_area
    assert sq.get_nightly_submission("Arauco 1", "2026-07-30") == before_same_area


def test_choice_metric_round_trips_as_text_not_a_number(sheet):
    """`effort` is answered Todo / La mayor parte / Algo. If a correction path
    coerced it, a real answer would come back as 0 and be indistinguishable
    from no effort at all."""
    _, err = sq.save_nightly_submission("Arauco 1", "2026-07-31",
                                        {"effort": "La mayor parte"},
                                        edited_by="lider@missionary.org")
    assert err == ""
    assert sq.get_nightly_submission("Arauco 1", "2026-07-31")["effort"] == "La mayor parte"


def test_weekly_round_trips(sheet):
    _, err = sq.save_weekly_submission("Arauco 1", "2026-07-26",
                                       {"ki_baptized_confirmed_real": 2},
                                       edited_by="lider@missionary.org")
    assert err == ""
    back = sq.get_weekly_submission("Arauco 1", "2026-07-26")
    assert back["ki_baptized_confirmed_real"] == "2"
    assert back["ki_new_people_real"] == "3"


def test_zero_is_written_not_skipped(sheet):
    """0 is a real report — the companionship attempted nothing that day. A
    falsy check on the value would drop it and leave the old number standing."""
    _, err = sq.save_nightly_submission("Arauco 1", "2026-07-31",
                                        {"contacts_attempted": 0},
                                        edited_by="lider@missionary.org")
    assert err == ""
    assert sq.get_nightly_submission("Arauco 1", "2026-07-31")["contacts_attempted"] == "0"


# ── Refusals ──────────────────────────────────────────────────────────────────

def test_identity_columns_cannot_be_edited(sheet):
    for bad in ({"Area": "Lota 2"}, {"Date": "2026-01-01"}, {"Zone": "Otra"}):
        written, err = sq.save_nightly_submission(
            "Arauco 1", "2026-07-31", bad, edited_by="x")
        assert written == 0
        assert "no column" in err.lower(), err
    assert sheet.write_calls == 0, "a refused edit still wrote to the sheet"


def test_unknown_metric_is_refused_not_appended(sheet):
    """Writing a column the tab does not have would either land in the wrong
    cell or extend the row past the header."""
    written, err = sq.save_nightly_submission(
        "Arauco 1", "2026-07-31", {"lsi_given": 5}, edited_by="x")
    assert written == 0
    assert "lsi_given" in err
    assert sheet.write_calls == 0


def test_missing_row_is_refused_unless_backfill_is_asked_for(sheet):
    written, err = sq.save_nightly_submission(
        "Arauco 1", "2026-08-01", {"contacts_attempted": 10}, edited_by="x")
    assert written == 0
    assert "No DAILY_LOG row" in err
    assert sheet.write_calls == 0


def test_backfill_creates_a_row_in_the_agents_column_order(sheet):
    written, err = sq.save_nightly_submission(
        "Arauco 1", "2026-08-01", {"contacts_attempted": 10, "effort": "Todo"},
        edited_by="lider@missionary.org", allow_create=True)
    assert err == ""
    assert written == 2

    back = sq.get_nightly_submission("Arauco 1", "2026-08-01")
    assert back["contacts_attempted"] == "10"
    assert back["effort"] == "Todo"
    assert back["Area"] == "Arauco 1"
    assert back["Date"] == "2026-08-01"
    # Unsupplied metrics stay blank rather than becoming 0 — nobody reported
    # them, and "" is how that reads back.
    assert back["contacts_made"] == ""


# ── The empty tab COMPASS_CCSM actually had ───────────────────────────────────

def test_refuses_to_write_a_header_into_an_empty_daily_log(monkeypatch):
    """COMPASS_CCSM's DAILY_LOG was genuinely empty — no header, no rows —
    on 2026-08-01. CCSM_Agent3 writes that header itself, in QUESTIONS_CONFIG
    order. A header invented here in a different order would mis-file every
    metric the agent later appended, permanently and invisibly.
    """
    fake = FakeSheet({"DAILY_LOG": [], "WEEKLY_KI": [], "AUDIT_LOG": []})
    monkeypatch.setattr(sq, "read_values", fake.read_values)
    monkeypatch.setattr(sq, "append_row", fake.append_row)
    monkeypatch.setattr(sq, "update_cells", fake.update_cells)

    assert sq.get_nightly_submission("Arauco 1", "2026-07-31") is None
    assert sq.nightly_metric_columns() == []

    written, err = sq.save_nightly_submission(
        "Arauco 1", "2026-07-31", {"contacts_attempted": 1},
        edited_by="x", allow_create=True)
    assert written == 0
    assert "no header row yet" in err
    assert fake.write_calls == 0


# ── Audit ─────────────────────────────────────────────────────────────────────

def test_every_successful_edit_is_audited(sheet):
    sq.save_nightly_submission("Arauco 1", "2026-07-31",
                               {"contacts_attempted": 99},
                               edited_by="lider@missionary.org")
    audit = sheet.tabs["AUDIT_LOG"]
    assert len(audit) == 1
    line = " | ".join(str(c) for c in audit[0])
    assert "lider@missionary.org" in line
    assert "Arauco 1" in line
    assert "contacts_attempted=99" in line


def test_a_failed_audit_does_not_fail_the_save(sheet, monkeypatch):
    """The correction is the thing that matters. Reporting a saved edit as
    failed would have someone save it a second time."""
    def boom(*a, **k):
        raise RuntimeError("quota")
    monkeypatch.setattr(sq, "append_row", boom)

    written, err = sq.save_nightly_submission(
        "Arauco 1", "2026-07-31", {"contacts_attempted": 77},
        edited_by="lider@missionary.org")
    assert err == ""
    assert written == 1
    assert sq.get_nightly_submission("Arauco 1", "2026-07-31")["contacts_attempted"] == "77"
