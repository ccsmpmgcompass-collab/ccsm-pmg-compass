"""
drive_blob.py
──────────────────────────────────────────────────────────────────────────────
Store a large DataFrame as a gzipped CSV in Google Drive instead of a tab.

**Why.** Measured against the real Tableau Detail export (89,824 rows x 14
cols): as a Sheets tab it is a **17.35 MB** JSON payload and **1,257,536** of
the spreadsheet's 10M cells, and the Sheets values API delivers about
**1.4 MB/s** — roughly **12.6 s** per uncached page load, almost all of it
transfer. The same data gzips to **1.16 MB** and reads in about a second.
Transfer dominates and parse is noise, so the win comes entirely from
compression — which a Sheets tab cannot do and a Drive file can.

⚠️ **The service account cannot CREATE Drive files.** Its
``storageQuota.limit`` is 0 bytes (probed live, 2026-08-22). A human must
create the file and share it as **Editor** with the service account; from then
on the SA can overwrite its contents indefinitely, because an update charges
the file OWNER's quota rather than the updater's. COMPASS_CCSM is owned by a
personal gmail account and is not in a Shared Drive, so neither a Shared Drive
nor domain-wide delegation is available as an alternative. See
``PLAN-2026-08-22.md`` Part F §3.2g.

No new dependency: gspread already holds an ``AuthorizedSession``.
"""

import gzip
import io
import json
import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app.db.sheets_client import _get_client
from app.i18n import t

_DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
_DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"

#: First line of the decompressed payload. Carries what the tab's metadata row
#: carried, so get_tableau_detail() can still report "uploaded by / when"
#: without a second Drive round-trip just to read file properties.
_MAGIC = "#PMGBLOB1 "

_TIMEOUT = 120


# ══════════════════════════════════════════════════════════════════════════════
# PURE — encode / decode. No network, so the payload format is unit-testable.
# ══════════════════════════════════════════════════════════════════════════════

def _one_line(value) -> str:
    """Collapse any whitespace run to a single space.

    Applied to the metadata VALUES, not to the serialized JSON. json.dumps
    already escapes a newline to \\n, so the payload was never in danger of
    growing a forged second line — but the escape survives the round trip and
    json.loads hands back a genuine newline, which then lands in a caption.
    Sanitize the input; the output escaping is not the problem.
    """
    return " ".join(str(value or "").split())


def encode_blob(df: pd.DataFrame, uploaded_by: str = "", uploaded_at: str = "") -> bytes:
    """DataFrame -> gzipped `magic-line + CSV` bytes."""
    at = uploaded_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = _MAGIC + json.dumps({"uploaded_by": _one_line(uploaded_by),
                                  "uploaded_at": _one_line(at)}) + "\n"
    body = df.to_csv(index=False)
    return gzip.compress((header + body).encode("utf-8"), 6)


def decode_blob(data: bytes) -> tuple:
    """gzipped bytes -> (df, uploaded_by, uploaded_at).

    Everything is read back as text, matching read_tab(): every consumer
    re-parses dates itself, and letting pandas infer types here would make a
    column behave differently depending on whether a blank happened to appear.
    """
    if not data:
        return pd.DataFrame(), "", ""
    raw = gzip.decompress(data).decode("utf-8")
    by = at = ""
    if raw.startswith(_MAGIC):
        line, _, raw = raw.partition("\n")
        try:
            meta = json.loads(line[len(_MAGIC):])
            by, at = str(meta.get("uploaded_by", "")), str(meta.get("uploaded_at", ""))
        except (ValueError, AttributeError):
            # A malformed metadata line must not cost us the data itself.
            by = at = ""
    if not raw.strip():
        return pd.DataFrame(), by, at
    df = pd.read_csv(io.StringIO(raw), dtype=str, keep_default_na=False)
    return df, by, at


# ══════════════════════════════════════════════════════════════════════════════
# IO
# ══════════════════════════════════════════════════════════════════════════════

def _session():
    """The authorized session gspread already built for the Sheets API.

    Same credentials, same scopes — `_SCOPES` in sheets_client already includes
    full Drive — so the Drive REST API costs no extra dependency and no extra
    configuration.
    """
    return _get_client().http_client.session


def probe_blob(file_id: str) -> dict:
    """{ok, name, size, modified, error} for a blob, without downloading it.

    Used by the health check: the whole point of failure here is that the file
    was deleted or unshared, and that is worth naming precisely rather than
    surfacing as an empty funnel.
    """
    try:
        r = _session().get(f"{_DRIVE_FILES}/{file_id}",
                           params={"fields": "id,name,size,modifiedTime"},
                           timeout=_TIMEOUT)
        if r.status_code == 404:
            return {"ok": False, "error": "not found — deleted, or never shared "
                                          "with the service account"}
        if r.status_code == 403:
            return {"ok": False, "error": "access denied — the service account "
                                          "is not an Editor on this file"}
        if not r.ok:
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        d = r.json()
        return {"ok": True, "name": d.get("name", ""),
                "size": int(d.get("size") or 0),
                "modified": d.get("modifiedTime", ""), "error": ""}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def upload_blob(file_id: str, data: bytes) -> None:
    """Overwrite the file's contents. Raises on failure — callers decide.

    PATCH, never POST: POST would CREATE a file, which the service account
    cannot do (0-byte quota). If this starts 404ing, the file was deleted and a
    human has to make a new one and re-share it; no amount of retrying helps.
    """
    r = _session().patch(
        f"{_DRIVE_UPLOAD}/{file_id}",
        params={"uploadType": "media"},
        data=data,
        headers={"Content-Type": "application/gzip"},
        timeout=_TIMEOUT,
    )
    if not r.ok:
        raise RuntimeError(f"Drive upload failed: HTTP {r.status_code} {r.text[:200]}")


def download_blob(file_id: str) -> bytes:
    """The file's raw bytes. Raises on failure."""
    r = _session().get(f"{_DRIVE_FILES}/{file_id}", params={"alt": "media"},
                       timeout=_TIMEOUT)
    if not r.ok:
        raise RuntimeError(f"Drive download failed: HTTP {r.status_code} {r.text[:200]}")
    return r.content


def save_dataframe_blob(file_id: str, df: pd.DataFrame, uploaded_by: str = "") -> dict:
    """Encode and store. Returns {ok, bytes, rows, error}.

    Mirrors save_dataframe's contract of never raising into a page render, but
    unlike it returns whether the write actually happened — a silent failure
    here means the funnel keeps serving yesterday's data with no sign of it.
    """
    try:
        if df is None or df.empty:
            raise ValueError("refusing to overwrite the blob with an empty frame")
        payload = encode_blob(df, uploaded_by)
        upload_blob(file_id, payload)
        _read_blob_cached.clear()
        return {"ok": True, "bytes": len(payload), "rows": len(df), "error": ""}
    except Exception as e:
        st.warning(t("Could not save to Drive: {e}", e=e))
        return {"ok": False, "bytes": 0, "rows": 0, "error": str(e)}


@st.cache_data(ttl=300, show_spinner=False)
def _read_blob_cached(file_id: str) -> tuple:
    """Cached implementation — see read_dataframe_blob()."""
    df, by, at = decode_blob(download_blob(file_id))
    return df, by, at


def read_dataframe_blob(file_id: str) -> tuple:
    """(df, uploaded_by, uploaded_at), cached 5 minutes.

    Failures are caught HERE, outside the cache boundary, for the same reason
    read_tab() does it: a transient blip memoized as a "successful" empty
    result would be replayed to every user for the rest of the TTL, long after
    the real problem cleared.
    """
    if not file_id:
        return pd.DataFrame(), "", ""
    try:
        return _read_blob_cached(file_id)
    except Exception as e:
        st.warning(t("Could not read from Drive: {e}", e=e))
        return pd.DataFrame(), "", ""


read_dataframe_blob.clear = _read_blob_cached.clear
