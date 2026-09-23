"""Upload-path helpers for the Tableau exports.

Pure: no Streamlit, no Sheets calls, no file paths. The Embudo page supplies
the uploaded file objects and does the saving; everything that can be reasoned
about — which reader to use, whether a replacement would destroy history, how
a month of baptisms merges into what is already stored — lives here so it can
be tested without a browser or a network.
"""

from __future__ import annotations

import calendar
import re
from datetime import date

import pandas as pd

from app.ingestion.tableau_detail_transform import normalize_headers

#: Readable spreadsheet extensions. The Mission Finding Summary Detail view
#: exports as .xlsx — the uploader was pd.read_csv only, so the real file
#: could never be loaded through it.
EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xls")
CSV_SUFFIXES = (".csv", ".txt", ".tsv")

#: TABLEAU_BAPTISMS' contract, per get_baptisms_actual(). The last two are
#: additive (2026-09-19): they record the window the export was actually run
#: for, so a month-to-date capture stops being indistinguishable from a
#: finished month. "Provisional" is derived from them, never stored.
BAPTISM_COLUMNS = ("zone", "month", "baptisms", "start_date", "end_date")

#: What a row must have to be READ at all. Deliberately NOT BAPTISM_COLUMNS:
#: the 31 rows already on the live tab predate the date columns, and requiring
#: those here would make _stored_baptism_rows() return nothing and the next
#: merge silently wipe two and a half years of history.
BAPTISM_CORE_COLUMNS = ("zone", "month", "baptisms")

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


def month_last_day(month: str) -> date:
    """The last calendar day of a 'YYYY-MM' month."""
    y, m = int(month[:4]), int(month[5:7])
    return date(y, m, calendar.monthrange(y, m)[1])


def effective_end(month: str, end_date: str) -> date:
    """The day a stored row actually reaches, for comparing two captures.

    **A blank ``end_date`` means the whole month**, not "unknown" and certainly
    not "day zero". Every row written before 2026-09-19 has no dates and every
    one of them is a finished month, so a blank has to rank as maximally
    complete — otherwise the first month-to-date upload would out-rank all 31
    of them and overwrite real history with a partial.
    """
    raw = str(end_date or "").strip()[:10]
    if not raw:
        return month_last_day(month)
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return month_last_day(month)


def is_provisional(month: str, end_date: str) -> bool:
    """True when a row stops short of its month's last day."""
    return effective_end(month, end_date) < month_last_day(month)


def _stored_baptism_rows(existing: pd.DataFrame) -> list[list]:
    """The real rows out of a TABLEAU_BAPTISMS read.

    read_tab() hands back the metadata row save_dataframe stamps at the top as
    ordinary data, so rows are kept only when ``month`` looks like YYYY-MM.

    Rows are normalised to the full five columns. Missing date columns read as
    empty strings rather than being rejected: see BAPTISM_CORE_COLUMNS for why
    requiring them would be a history-destroying bug.
    """
    if existing is None or existing.empty:
        return []
    cols = {c.lower(): c for c in existing.columns}
    if not all(c in cols for c in BAPTISM_CORE_COLUMNS):
        return []

    def _opt(r, key: str) -> str:
        return str(r[cols[key]]).strip() if key in cols else ""

    rows = []
    for _, r in existing.iterrows():
        month = str(r[cols["month"]]).strip()
        if not _MONTH_RE.match(month):
            continue
        try:
            count = int(float(str(r[cols["baptisms"]]).strip()))
        except (ValueError, TypeError):
            continue
        rows.append([str(r[cols["zone"]]).strip(), month, count,
                     _opt(r, "start_date"), _opt(r, "end_date")])
    return rows


def merge_baptism_rows(existing: pd.DataFrame, new_rows) -> pd.DataFrame:
    """Fold freshly parsed PDF rows into what TABLEAU_BAPTISMS already holds.

    MERGE, not replace. The mission's history is 31 monthly PDFs; uploading
    next month's export must not wipe the previous thirty. A month present in
    both wins from the new upload — a re-download of a month is the corrected
    version of it.

    Rows are (zone, month, baptisms, start_date, end_date) as
    ``baptisms_rows()`` produces them. Sorted by month within zone so the tab
    reads chronologically.

    **A narrower capture never beats a wider one.** New wins on ties, but for
    one (zone, month) the row reaching the later day is the one kept, so
    uploading Sep 1-5 cannot clobber a finished September. This is the
    baptism-side twin of the ``narrower`` check ``describe_replacement()``
    already performs for the Detail export, and it is what makes a repeated
    month-to-date capture safe to run unattended.
    """
    merged: dict[tuple, list] = {}
    for row in _stored_baptism_rows(existing):
        merged[(row[0], row[1])] = row
    for row in new_rows:
        zone, month, count = str(row[0]).strip(), str(row[1]).strip(), int(row[2])
        if not _MONTH_RE.match(month):
            raise UploadError(f"'{month}' is not a YYYY-MM month key")
        start = str(row[3]).strip() if len(row) > 3 else ""
        end = str(row[4]).strip() if len(row) > 4 else ""
        prior = merged.get((zone, month))
        if prior is not None and effective_end(month, end) < effective_end(month, prior[4]):
            continue  # the stored capture reaches further; keep it
        merged[(zone, month)] = [zone, month, count, start, end]
    ordered = [merged[k] for k in sorted(merged, key=lambda k: (k[0], k[1]))]
    return pd.DataFrame(ordered, columns=list(BAPTISM_COLUMNS))


# ── Certified baptisms for a window that is not a month ──────────────────────
#
# Decision 42 (PLAN-2026-09-23-claridad.md): the council packet's baptism
# figure follows the selected period, and every period prints the CERTIFIED
# figure. Four of the six periods — last week, this transfer, last transfer,
# the last six weeks — start and end mid-month, so TABLEAU_BAPTISMS cannot
# answer them. The Summary PDF can: it takes any window and prints the one it
# ran for. So the nightly job captures those windows too, into their OWN tab.
#
# Never into TABLEAU_BAPTISMS. That tab is keyed by month, and a window of
# 10 Aug – 20 Sep parses to month "2026-08"; merged there it would be stored
# as August's certified figure. The two shapes are kept apart by construction.

#: TABLEAU_BAPTISM_WINDOWS' contract. `period` is the `periods.PERIOD_KEYS`
#: key the window was captured for — a label for the person reading the tab and
#: the grouping `merge_window_rows` prunes by. It is NOT how a figure is looked
#: up: the packet looks up by DAYS, so a window captured under one name answers
#: any period that covers exactly the same days.
BAPTISM_WINDOW_COLUMNS = ("period", "start_date", "end_date", "baptisms",
                          "captured_on")


def _iso(raw) -> date | None:
    try:
        return date.fromisoformat(str(raw or "").strip()[:10])
    except ValueError:
        return None


def stored_window_rows(existing: pd.DataFrame) -> list[list]:
    """The real rows out of a TABLEAU_BAPTISM_WINDOWS read, oldest first.

    The metadata row the writer stamps under the header comes back as ordinary
    data, and so does anything a person typed into the tab; a row is kept only
    when both of its dates parse and its count is a whole number.
    """
    if existing is None or existing.empty:
        return []
    cols = {str(c).strip().lower(): c for c in existing.columns}
    if not all(c in cols for c in ("start_date", "end_date", "baptisms")):
        return []
    rows = []
    for _, r in existing.iterrows():
        start, end = _iso(r[cols["start_date"]]), _iso(r[cols["end_date"]])
        if start is None or end is None or end < start:
            continue
        try:
            count = int(float(str(r[cols["baptisms"]]).strip()))
        except (ValueError, TypeError):
            continue
        period = str(r[cols["period"]]).strip() if "period" in cols else ""
        captured = (str(r[cols["captured_on"]]).strip()[:10]
                    if "captured_on" in cols else "")
        rows.append([period, start.isoformat(), end.isoformat(), count, captured])
    return sorted(rows, key=lambda r: (r[1], r[2]))


def merge_window_rows(existing: pd.DataFrame, new_rows) -> pd.DataFrame:
    """Fold freshly captured windows into what the tab already holds.

    Two rules, in this order:

    1. **The same days, re-captured, are replaced.** A window captured again
       tonight is the corrected version of last night's: a baptism recorded
       late lands in it. Keyed by (start, end), never by period name.

    2. **A window that grew replaces the shorter one it grew from — within one
       period.** "Este traslado" is captured every night as 7 Sep → today, so
       it would otherwise leave a row per night. Within one (period, start),
       only the row reaching the latest day is kept. The grouping is by period
       as well as start because two DIFFERENT questions can share a first day:
       on 14 Sep the last week is 7–13 Sep and the transfer is 7–14 Sep, and
       the week must survive the transfer's longer row.
    """
    merged: dict[tuple, list] = {}
    for row in stored_window_rows(existing):
        merged[(row[1], row[2])] = row
    for row in new_rows:
        period = str(row[0]).strip()
        start, end = _iso(row[1]), _iso(row[2])
        if start is None or end is None or end < start:
            raise UploadError(f"'{row[1]}'..'{row[2]}' is not a window")
        captured = str(row[4]).strip()[:10] if len(row) > 4 else ""
        merged[(start.isoformat(), end.isoformat())] = [
            period, start.isoformat(), end.isoformat(), int(row[3]), captured]

    longest: dict[tuple, str] = {}
    for period, start, end, _count, _captured in merged.values():
        key = (period, start)
        if end > longest.get(key, ""):
            longest[key] = end
    kept = [r for r in merged.values() if r[2] == longest[(r[0], r[1])]]
    kept.sort(key=lambda r: (r[1], r[2]))
    return pd.DataFrame(kept, columns=list(BAPTISM_WINDOW_COLUMNS))


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
