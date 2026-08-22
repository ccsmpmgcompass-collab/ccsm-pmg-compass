"""Tests for app/ingestion/tableau_upload.py — the Embudo upload path.

Three things here can lose data quietly, which is why they are tested rather
than trusted: reading the wrong file format, replacing 2.6 years of Detail
with a two-month slice, and overwriting thirty months of baptism counts with
the one month someone just downloaded.
"""

import io
from datetime import date

import pandas as pd
import pytest

from app.ingestion.tableau_upload import (
    UploadError,
    date_span,
    describe_replacement,
    merge_baptism_rows,
    read_tabular,
    summarize_months,
    upload_token,
)


def _csv_bytes(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode("utf-8"))


def _xlsx_bytes(df: pd.DataFrame) -> io.BytesIO:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return buf


# ── reading the file ──────────────────────────────────────────────────────────

def test_reads_the_xlsx_the_real_export_actually_is():
    """The uploader was pd.read_csv only; the Tableau Detail view exports
    .xlsx, so the real file could never be loaded through the page."""
    src = pd.DataFrame({"Event Date Selected": ["2026-08-01"],
                        "Latest Zone": ["Temuco Ñielol"]})
    out = read_tabular(_xlsx_bytes(src), "Detail.xlsx")
    assert list(out.columns) == ["event_date_selected", "latest_zone"]
    assert out.iloc[0]["latest_zone"] == "Temuco Ñielol"


def test_still_reads_csv():
    out = read_tabular(_csv_bytes("Event Date Selected,Full Name\n2026-08-01,X\n"),
                       "export.csv")
    assert list(out.columns) == ["event_date_selected", "full_name"]


def test_everything_is_read_as_text():
    """Letting pandas infer types makes two uploads of the same view behave
    differently — a column of digits becomes ints in one file and strings in
    another depending on whether a blank sneaks in."""
    out = read_tabular(_csv_bytes("Person Id,Event Date Selected\n007,2026-08-01\n"),
                       "export.csv")
    assert out.iloc[0]["person_id"] == "007"


def test_an_unreadable_extension_is_refused_by_name():
    with pytest.raises(UploadError, match="Unsupported file type"):
        read_tabular(io.BytesIO(b"x"), "summary.pdf")


def test_an_empty_file_is_refused_rather_than_saved_as_nothing():
    with pytest.raises(UploadError, match="no rows"):
        read_tabular(_csv_bytes("a,b\n"), "export.csv")


# ── the replace guard ─────────────────────────────────────────────────────────

def _det(dates):
    return pd.DataFrame({"event_date_selected": dates})


def test_date_span_reads_the_window_the_export_covers():
    assert date_span(_det(["2024-01-01", "2026-08-03", ""])) == (
        date(2024, 1, 1), date(2026, 8, 3))


def test_date_span_of_nothing_is_nothing():
    assert date_span(pd.DataFrame()) == (None, None)
    assert date_span(_det(["", "nope"])) == (None, None)


def test_a_narrower_export_is_flagged_because_it_would_destroy_history():
    """A Detail upload replaces the tab — it cannot merge, because the only
    stable per-person key is the person_id dropped for privacy."""
    stored = _det(["2024-01-01", "2026-08-03"])
    incoming = _det(["2026-06-01", "2026-08-03"])
    plan = describe_replacement(stored, incoming)
    assert plan["narrower"] is True
    assert plan["existing_span"] == (date(2024, 1, 1), date(2026, 8, 3))
    assert plan["incoming_span"] == (date(2026, 6, 1), date(2026, 8, 3))


def test_an_export_ending_earlier_is_also_narrower():
    plan = describe_replacement(_det(["2024-01-01", "2026-08-03"]),
                                _det(["2024-01-01", "2025-01-01"]))
    assert plan["narrower"] is True


def test_a_full_or_wider_export_is_not_flagged():
    stored = _det(["2026-06-01", "2026-08-03"])
    assert describe_replacement(stored, _det(["2026-06-01", "2026-08-03"]))["narrower"] is False
    assert describe_replacement(stored, _det(["2024-01-01", "2026-09-01"]))["narrower"] is False


def test_the_first_ever_upload_is_never_flagged():
    """Nothing stored means nothing to lose."""
    plan = describe_replacement(pd.DataFrame(), _det(["2026-06-01", "2026-08-03"]))
    assert plan["narrower"] is False
    assert plan["existing_rows"] == 0


# ── merging baptisms, never replacing them ────────────────────────────────────

def _stored(rows):
    """A TABLEAU_BAPTISMS read, metadata row included — read_tab() hands the
    row save_dataframe stamps at the top back as ordinary data."""
    meta = ["_uploaded_by:someone@example.org", "_uploaded_at:2026-08-01 00:00 UTC", ""]
    return pd.DataFrame([meta] + rows, columns=["zone", "month", "baptisms"])


def test_a_new_month_is_added_and_the_old_ones_survive():
    """Uploading next month's PDF must not wipe the previous thirty."""
    stored = _stored([["MISSION", "2026-06", "44"], ["MISSION", "2026-07", "43"]])
    out = merge_baptism_rows(stored, [["MISSION", "2026-08", 46]])
    assert list(out["month"]) == ["2026-06", "2026-07", "2026-08"]
    assert list(out["baptisms"]) == [44, 43, 46]


def test_the_metadata_row_never_becomes_a_month():
    out = merge_baptism_rows(_stored([["MISSION", "2026-06", "44"]]), [])
    assert list(out["month"]) == ["2026-06"]


def test_a_re_uploaded_month_wins_over_the_stored_one():
    """A re-download is the corrected version of that month."""
    out = merge_baptism_rows(_stored([["MISSION", "2026-07", "40"]]),
                             [["MISSION", "2026-07", 43]])
    assert list(out["baptisms"]) == [43]


def test_merging_into_an_empty_tab_just_writes_the_new_rows():
    out = merge_baptism_rows(pd.DataFrame(), [["MISSION", "2024-01", 26]])
    assert list(out.columns) == ["zone", "month", "baptisms"]
    assert len(out) == 1


def test_months_come_back_in_order_whatever_order_they_arrived_in():
    out = merge_baptism_rows(pd.DataFrame(), [
        ["MISSION", "2026-08", 46], ["MISSION", "2024-01", 26], ["MISSION", "2025-03", 30]])
    assert list(out["month"]) == ["2024-01", "2025-03", "2026-08"]


def test_a_bad_month_key_is_refused_not_stored():
    with pytest.raises(UploadError, match="not a YYYY-MM"):
        merge_baptism_rows(pd.DataFrame(), [["MISSION", "August 2024", 26]])


# ── odds and ends the page leans on ───────────────────────────────────────────

def test_upload_token_distinguishes_a_new_file_from_a_rerun():
    class F:
        def __init__(self, name, size):
            self.name, self.size = name, size

    assert upload_token(F("Detail.xlsx", 12)) == upload_token(F("Detail.xlsx", 12))
    assert upload_token(F("Detail.xlsx", 12)) != upload_token(F("Detail.xlsx", 13))
    assert upload_token(F("Detail.xlsx", 12)) != upload_token(F("Other.xlsx", 12))


def test_summarize_months_reports_a_complete_run():
    months = [f"2024-{m:02d}" for m in range(1, 13)]
    assert summarize_months(months) == "2024-01 → 2024-12 (12 months) — no gaps"


def test_summarize_months_counts_what_is_missing():
    assert "1 missing" in summarize_months(["2024-01", "2024-02", "2024-04"])


def test_summarize_months_ignores_junk():
    assert summarize_months(["_uploaded_by:x", "2024-01"]).startswith("2024-01")
    assert summarize_months([]) == "no months"
