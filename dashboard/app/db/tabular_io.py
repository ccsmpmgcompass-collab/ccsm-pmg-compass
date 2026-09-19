"""
tabular_io.py
──────────────────────────────────────────────────────────────────────────────
The Streamlit-free half of the storage layer: the A1 chunk arithmetic that
``sheets_client.save_dataframe`` writes through, and the payload format
``drive_blob`` stores the Detail export in.

**Why it is its own module.** The nightly Tableau job
(``app/ingestion/tableau_finding_runner.py``) runs inside a GitHub Actions
Playwright container against ``requirements_cloud.txt``, which deliberately
carries no Streamlit — the runner has no ``st.secrets``, no script context and
no reason to pay for the dependency. But ``sheets_client`` and ``drive_blob``
both ``import streamlit`` at module scope, so the runner cannot import either
one, and it still has to write exactly the bytes and land rows in exactly the
cells the app reads back.

The alternative was a second copy of the A1 arithmetic and the blob format
inside the runner. Those are the two places in the storage layer where a
silent divergence is least survivable: an off-by-one A1 range shifts every row
beneath it and nothing complains, and a payload the app cannot decode reads as
an empty funnel rather than an error. So the pure parts moved here and both
owners import them — ``sheets_client`` and ``drive_blob`` keep their public
names, so every existing caller and test is unaffected.
"""

from __future__ import annotations

import gzip
import io
import json
from datetime import datetime, timezone

import pandas as pd

#: Rows per ws.update() call. One update puts its whole payload in a single
#: JSON request body and the Sheets API caps that: measured against the real
#: Tableau Detail export (89,824 x 14 = 1,257,536 cells), one call is a 17.4 MB
#: body. At 10,000 rows a call it is 1.94 MB across 9 calls — comfortably
#: inside both the request cap and the 60-writes-per-minute-per-user quota.
WRITE_CHUNK_ROWS = 10_000

#: First line of the decompressed blob payload. Carries what the tab's metadata
#: row carries, so a reader can report "uploaded by / when" without a second
#: Drive round-trip just to read file properties.
BLOB_MAGIC = "#PMGBLOB1 "


# ══════════════════════════════════════════════════════════════════════════════
# A1 CHUNKING
# ══════════════════════════════════════════════════════════════════════════════

def col_letter(n: int) -> str:
    """1-based column index -> A1 letters ('A', 'Z', 'AA', 'AB')."""
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def plan_write_chunks(n_rows: int, n_cols: int, chunk_size: int = WRITE_CHUNK_ROWS,
                      start_row: int = 1) -> list:
    """[(a1_range, lo, hi)] slicing n_rows into writable chunks, where rows[lo:hi]
    is the slice and a1_range is exactly where it lands.

    Pure, and separated out so the arithmetic can be tested without a network:
    an A1 range off by one silently shifts every row beneath it, which is the
    kind of corruption nobody notices until a number looks wrong months later.
    """
    if n_rows <= 0 or n_cols <= 0:
        return []
    last = col_letter(n_cols)
    step = max(1, chunk_size)
    plan = []
    for lo in range(0, n_rows, step):
        hi = min(lo + step, n_rows)
        plan.append((f"A{start_row + lo}:{last}{start_row + hi - 1}", lo, hi))
    return plan


def utc_stamp() -> str:
    """The '_uploaded_at:' timestamp format the metadata row has always used."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def meta_row(n_cols: int, uploaded_by: str, uploaded_at: str = "") -> list:
    """The '_uploaded_by:… / _uploaded_at:…' row every tab write stamps on top.

    A reader (``get_tableau_detail``, ``get_tableau_ranking``) takes these two
    cells off ``df.iloc[0]``, so a writer that leaves them out shifts the real
    first row into the metadata position and loses it.
    """
    stamped = [f"_uploaded_by:{uploaded_by}", f"_uploaded_at:{uploaded_at or utc_stamp()}"]
    return (stamped + [""] * max(0, n_cols - 2))[:n_cols]


def frame_from_values(rows: list, header_marker: str | None = None) -> pd.DataFrame:
    """A tab's raw ``get_all_values()`` grid as the app reads it.

    Every rule here changes what a caller sees, so a second implementation of
    them would be a second opinion about the data: blank header cells become
    droppable ``_blank`` columns, duplicates get suffixed rather than colliding,
    and with a ``header_marker`` the header is FOUND rather than assumed to be
    row 1 — agent-written tabs carry their own header below a stale manual one,
    and repeated header rows are dropped from the body.
    """
    if not rows or len(rows) < 2:
        return pd.DataFrame()
    header_idx = 0
    if header_marker:
        for i, r in enumerate(rows[:5]):
            if header_marker in [str(c).strip() for c in r]:
                header_idx = i
                break
        else:
            return pd.DataFrame()
    seen: dict = {}
    clean_headers = []
    for h in rows[header_idx]:
        h = str(h).strip()
        if not h:
            h = "_blank"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 0
        clean_headers.append(h)
    df = pd.DataFrame(rows[header_idx + 1:], columns=clean_headers)
    df = df.loc[:, ~df.columns.str.startswith("_blank")]
    if header_marker and header_marker in df.columns:
        df = df[df[header_marker].astype(str).str.strip() != header_marker]
    return df


# ══════════════════════════════════════════════════════════════════════════════
# BLOB CODEC — no network, so the payload format is unit-testable
# ══════════════════════════════════════════════════════════════════════════════

def one_line(value) -> str:
    """Collapse any whitespace run to a single space.

    Applied to the metadata VALUES, not to the serialized JSON. json.dumps
    already escapes a newline to \n, so the payload was never in danger of
    growing a forged second line — but the escape survives the round trip and
    json.loads hands back a genuine newline, which then lands in a caption.
    Sanitize the input; the output escaping is not the problem.
    """
    return " ".join(str(value or "").split())


def encode_blob(df: pd.DataFrame, uploaded_by: str = "", uploaded_at: str = "") -> bytes:
    """DataFrame -> gzipped `magic-line + CSV` bytes."""
    at = uploaded_at or utc_stamp()
    header = BLOB_MAGIC + json.dumps({"uploaded_by": one_line(uploaded_by),
                                      "uploaded_at": one_line(at)}) + "\n"
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
    if raw.startswith(BLOB_MAGIC):
        line, _, raw = raw.partition("\n")
        try:
            meta = json.loads(line[len(BLOB_MAGIC):])
            by, at = str(meta.get("uploaded_by", "")), str(meta.get("uploaded_at", ""))
        except (ValueError, AttributeError):
            # A malformed metadata line must not cost us the data itself.
            by = at = ""
    if not raw.strip():
        return pd.DataFrame(), by, at
    df = pd.read_csv(io.StringIO(raw), dtype=str, keep_default_na=False)
    return df, by, at
