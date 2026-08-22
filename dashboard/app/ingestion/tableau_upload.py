"""Upload-path helpers for the Tableau exports.

Pure: no Streamlit, no Sheets calls, no file paths. The Embudo page supplies
the uploaded file objects and does the saving; everything that can be reasoned
about — which reader to use, whether a replacement would destroy history, how
a month of baptisms merges into what is already stored — lives here so it can
be tested without a browser or a network.
"""

from __future__ import annotations

import re
from datetime import date

import pandas as pd

from app.ingestion.tableau_detail_transform import normalize_headers

#: Readable spreadsheet extensions. The Mission Finding Summary Detail view
#: exports as .xlsx — the uploader was pd.read_csv only, so the real file
#: could never be loaded through it.
EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xls")
CSV_SUFFIXES = (".csv", ".txt", ".tsv")

#: TABLEAU_BAPTISMS' contract, per get_baptisms_actual().
BAPTISM_COLUMNS = ("zone", "month", "baptisms")

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


class UploadError(ValueError):
    """A file we cannot read, or can read but should not act on."""


def _suffix(filename: str) -> str:
    name = str(filename or "").lower()
    return name[name.rfind("."):] if "." in name else ""


def read_tabular(file_obj, filename: str) -> pd.DataFrame:
    """Read an uploaded Detail/Ranking export into a header-normalised frame.

    Everything is read as text. The milestone columns are dates that only ever
    get tested for presence and re-parsed downstream, and letting pandas type
    them differently per file is how two uploads of the same view end up
    behaving differently.

    Excel needs ``openpyxl``; the ImportError is translated because "No module
    named openpyxl" tells the mission president nothing actionable.
    """
    suffix = _suffix(filename)
    if suffix in EXCEL_SUFFIXES:
        try:
            df = pd.read_excel(file_obj, sheet_name=0, dtype=str)
        except ImportError as exc:
            raise UploadError(
                "Reading .xlsx needs the openpyxl package, which is not "
                "installed on this server."
            ) from exc
    elif suffix in CSV_SUFFIXES or suffix == "":
        df = pd.read_csv(file_obj, dtype=str)
    else:
        raise UploadError(
            f"Unsupported file type '{suffix}'. Upload the Tableau export as "
            f".xlsx or .csv."
        )
    if df.empty:
        raise UploadError("That file has no rows.")
    return normalize_headers(df)


def date_span(df: pd.DataFrame, column: str = "event_date_selected"):
    """(earliest, latest) date present in `column`, or (None, None)."""
    if df is None or df.empty or column not in df.columns:
        return None, None
    parsed = pd.to_datetime(df[column], errors="coerce", format="mixed").dropna()
    if parsed.empty:
        return None, None
    return parsed.min().date(), parsed.max().date()


def describe_replacement(existing: pd.DataFrame, incoming: pd.DataFrame) -> dict:
    """What replacing TABLEAU_DETAIL with `incoming` would cost.

    A Detail upload always REPLACES the whole tab; it cannot merge. Merging
    would need a stable per-person key and the only one the export carries is
    ``person_id``, which is dropped at ingest by the privacy decision (see
    tableau_detail_transform). So a partial export — someone pulling the last
    two months rather than the full view — silently destroys the history, and
    nothing about the upload looks any different at the time.

    Returns the spans plus ``narrower``: True when the incoming file starts
    later or ends earlier than what is already stored, i.e. when accepting it
    would lose data the tab currently holds.
    """
    old_lo, old_hi = date_span(existing)
    new_lo, new_hi = date_span(incoming)
    narrower = bool(
        old_lo and new_lo and old_hi and new_hi
        and (new_lo > old_lo or new_hi < old_hi)
    )
    return {
        "existing_span": (old_lo, old_hi),
        "incoming_span": (new_lo, new_hi),
        "existing_rows": 0 if existing is None else len(existing),
        "incoming_rows": 0 if incoming is None else len(incoming),
        "narrower": narrower,
    }


def _stored_baptism_rows(existing: pd.DataFrame) -> list[list]:
    """The real rows out of a TABLEAU_BAPTISMS read.

    read_tab() hands back the metadata row save_dataframe stamps at the top as
    ordinary data, so rows are kept only when ``month`` looks like YYYY-MM.
    """
    if existing is None or existing.empty:
        return []
    cols = {c.lower(): c for c in existing.columns}
    if not all(c in cols for c in BAPTISM_COLUMNS):
        return []
    rows = []
    for _, r in existing.iterrows():
        month = str(r[cols["month"]]).strip()
        if not _MONTH_RE.match(month):
            continue
        try:
            count = int(float(str(r[cols["baptisms"]]).strip()))
        except (ValueError, TypeError):
            continue
        rows.append([str(r[cols["zone"]]).strip(), month, count])
    return rows


def merge_baptism_rows(existing: pd.DataFrame, new_rows) -> pd.DataFrame:
    """Fold freshly parsed PDF rows into what TABLEAU_BAPTISMS already holds.

    MERGE, not replace. The mission's history is 31 monthly PDFs; uploading
    next month's export must not wipe the previous thirty. A month present in
    both wins from the new upload — a re-download of a month is the corrected
    version of it.

    Rows are (zone, month, baptisms) as ``baptisms_rows()`` produces them.
    Sorted by month within zone so the tab reads chronologically.
    """
    merged: dict[tuple, list] = {}
    for row in _stored_baptism_rows(existing):
        merged[(row[0], row[1])] = row
    for row in new_rows:
        zone, month, count = str(row[0]).strip(), str(row[1]).strip(), int(row[2])
        if not _MONTH_RE.match(month):
            raise UploadError(f"'{month}' is not a YYYY-MM month key")
        merged[(zone, month)] = [zone, month, count]
    ordered = [merged[k] for k in sorted(merged, key=lambda k: (k[0], k[1]))]
    return pd.DataFrame(ordered, columns=list(BAPTISM_COLUMNS))


def upload_token(uploaded) -> str:
    """A cheap identity for an uploaded file, so the page can tell a NEW upload
    from the same one surviving a rerun.

    Streamlit keeps an uploaded file in session_state across every rerun, and
    the page acted on whatever was there — so merely changing the date preset
    re-parsed and re-saved the export. Harmless for a small CSV; for a
    1.25M-cell Detail write it is nine API calls per click.
    """
    name = getattr(uploaded, "name", "") or ""
    size = getattr(uploaded, "size", None)
    if size is None:
        try:
            size = len(uploaded.getvalue())
        except Exception:
            size = -1
    return f"{name}:{size}"


def summarize_months(months) -> str:
    """'2024-01 → 2026-07 (31 months)', or a gap-aware note when months are
    missing, for the caption after a PDF upload."""
    uniq = sorted({str(m) for m in months if _MONTH_RE.match(str(m))})
    if not uniq:
        return "no months"
    span = f"{uniq[0]} → {uniq[-1]} ({len(uniq)} months)"
    lo = date(int(uniq[0][:4]), int(uniq[0][5:]), 1)
    hi = date(int(uniq[-1][:4]), int(uniq[-1][5:]), 1)
    expected = (hi.year - lo.year) * 12 + (hi.month - lo.month) + 1
    if expected != len(uniq):
        return f"{span} — {expected - len(uniq)} missing"
    return f"{span} — no gaps"
