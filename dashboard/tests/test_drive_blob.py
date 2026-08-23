"""Tests for app/db/drive_blob.py.

The Drive blob replaces a Sheets tab as the store for the Tableau Detail
export. Two things here are load-bearing and easy to get wrong: the payload
format (a metadata line ahead of the CSV, gzipped) and the fact that the
service account can only ever PATCH an existing file — it has a 0-byte storage
quota, so a POST that creates a file fails, and nothing about that failure
looks like a quota problem at the call site.
"""

import gzip
import json

import pandas as pd
import pytest

from app.db import drive_blob as db
from app.db.drive_blob import decode_blob, encode_blob


def _frame():
    return pd.DataFrame({
        "event_date_selected": ["2026-08-01", "2026-08-02", ""],
        "latest_zone_name": ["Temuco Ñielol", "Arauco", "Villarrica"],
        "person_count": ["007", "12", ""],
    })


# ── payload format ────────────────────────────────────────────────────────────

def test_round_trip_preserves_the_frame_exactly():
    df = _frame()
    out, by, at = decode_blob(encode_blob(df, "someone@example.org"))
    pd.testing.assert_frame_equal(out, df)
    assert by == "someone@example.org"
    assert at


def test_blank_cells_stay_blank_rather_than_becoming_nan():
    """read_tab() hands back empty strings, and every consumer's blank check
    is written for that. NaN here would change what 'reached this milestone'
    means."""
    out, _, _ = decode_blob(encode_blob(_frame()))
    assert out.iloc[2]["event_date_selected"] == ""
    assert out["event_date_selected"].notna().all()


def test_everything_comes_back_as_text():
    """Type inference would make a column behave differently depending on
    whether a blank happened to appear in it."""
    out, _, _ = decode_blob(encode_blob(_frame()))
    assert out.iloc[0]["person_count"] == "007"
    assert all(out.dtypes == object)


def test_the_metadata_line_records_who_and_when():
    payload = encode_blob(_frame(), "me@example.org", "2026-08-22 20:00 UTC")
    first = gzip.decompress(payload).decode("utf-8").split("\n", 1)[0]
    assert first.startswith("#PMGBLOB1 ")
    assert json.loads(first[len("#PMGBLOB1 "):]) == {
        "uploaded_by": "me@example.org", "uploaded_at": "2026-08-22 20:00 UTC"}


def test_a_newline_in_the_uploader_name_cannot_forge_a_second_line():
    """Otherwise the injected line becomes the CSV header and every column
    shifts."""
    out, by, _ = decode_blob(encode_blob(_frame(), "evil\nname,cols\n1,2"))
    assert list(out.columns) == list(_frame().columns)
    assert "\n" not in by


def test_a_malformed_metadata_line_does_not_cost_us_the_data():
    good = gzip.decompress(encode_blob(_frame(), "x@y.z")).decode("utf-8")
    broken = "#PMGBLOB1 {not json\n" + good.split("\n", 1)[1]
    out, by, at = decode_blob(gzip.compress(broken.encode("utf-8")))
    assert len(out) == 3
    assert by == "" and at == ""


def test_a_payload_with_no_metadata_line_still_reads():
    """Belt and braces: a file written by hand, or by an older version."""
    out, by, _ = decode_blob(gzip.compress(_frame().to_csv(index=False).encode()))
    assert len(out) == 3
    assert by == ""


def test_nothing_decodes_to_nothing():
    df, by, at = decode_blob(b"")
    assert df.empty and by == "" and at == ""


def test_the_payload_actually_compresses():
    """The entire reason for this module. The real export is 11.9 MB of CSV
    and 1.16 MB gzipped; anything near 1:1 means compression silently broke."""
    big = pd.DataFrame({"zone": ["Temuco Ñielol"] * 5000,
                        "date": ["2026-08-01"] * 5000})
    raw = len(big.to_csv(index=False).encode("utf-8"))
    assert len(encode_blob(big)) < raw / 10


# ── IO ────────────────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status=200, content=b"", payload=None):
        self.status_code, self.content = status, content
        self._payload, self.text = payload, ""
        self.ok = 200 <= status < 300

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, **responses):
        self.responses = responses
        self.calls = []

    def patch(self, url, **kw):
        self.calls.append(("PATCH", url, kw))
        return self.responses.get("patch", _Resp())

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return self.responses.get("post", _Resp())

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self.responses.get("get", _Resp())


@pytest.fixture
def fake(monkeypatch):
    s = _FakeSession()
    monkeypatch.setattr(db, "_session", lambda: s)
    return s


def test_upload_patches_and_never_posts(fake):
    """POST would CREATE a file, which the service account cannot do — its
    Drive storage quota is 0 bytes. This is the whole reason a human has to
    create the file first."""
    db.upload_blob("FILE123", b"payload")
    methods = [c[0] for c in fake.calls]
    assert methods == ["PATCH"]
    assert "POST" not in methods
    url, kw = fake.calls[0][1], fake.calls[0][2]
    assert url.endswith("/FILE123")
    assert "upload/drive/v3" in url
    assert kw["params"]["uploadType"] == "media"
    assert kw["data"] == b"payload"


def test_a_failed_upload_raises_rather_than_reporting_success(fake):
    fake.responses["patch"] = _Resp(403)
    with pytest.raises(RuntimeError, match="403"):
        db.upload_blob("FILE123", b"x")


def test_download_asks_for_the_media_not_the_metadata(fake):
    fake.responses["get"] = _Resp(content=b"bytes")
    assert db.download_blob("FILE123") == b"bytes"
    assert fake.calls[0][2]["params"] == {"alt": "media"}


def test_probe_names_the_two_failures_that_actually_happen(fake):
    fake.responses["get"] = _Resp(404)
    assert "not found" in db.probe_blob("F")["error"]
    fake.responses["get"] = _Resp(403)
    assert "not an Editor" in db.probe_blob("F")["error"]


def test_probe_reports_size_when_the_file_is_there(fake):
    fake.responses["get"] = _Resp(payload={"id": "F", "name": "tableau_detail.csv.gz",
                                           "size": "1216000",
                                           "modifiedTime": "2026-08-22T20:00:00Z"})
    out = db.probe_blob("F")
    assert out["ok"] and out["size"] == 1_216_000
    assert out["name"] == "tableau_detail.csv.gz"


def test_saving_an_empty_frame_is_refused_not_written(fake):
    """An empty frame reaching here means an upstream parse failed. Writing it
    would replace 2.6 years of data with nothing, and the blob has no undo."""
    out = db.save_dataframe_blob("F", pd.DataFrame())
    assert out["ok"] is False
    assert fake.calls == []


def test_a_successful_save_reports_what_it_wrote(fake):
    out = db.save_dataframe_blob("F", _frame(), uploaded_by="me@example.org")
    assert out["ok"] is True
    assert out["rows"] == 3
    assert out["bytes"] > 0


def test_reading_without_a_configured_file_id_is_empty_not_an_error(fake):
    df, by, at = db.read_dataframe_blob("")
    assert df.empty and by == "" and at == ""
    assert fake.calls == []


def test_a_read_failure_returns_empty_instead_of_exploding(fake, monkeypatch):
    monkeypatch.setattr(db, "_read_blob_cached",
                        lambda fid: (_ for _ in ()).throw(RuntimeError("boom")))
    df, by, at = db.read_dataframe_blob("F")
    assert df.empty
