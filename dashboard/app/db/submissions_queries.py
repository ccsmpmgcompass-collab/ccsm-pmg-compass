"""Read and correct submitted reports.

Which tab a correction belongs in
─────────────────────────────────
NOT the form response sheets. NIGHTLY_FORM_RAW and WEEKLY_FORM_RAW are Google
Forms' own linked sheets, and editing them would achieve nothing anyway:
CCSM_Agent3 appends a DAILY_LOG row only for an Area|Date it has not already
seen (a3_updateDailyLog's `existing` map), so a raw-sheet edit for a date the
agent has already processed is never re-read. Same for the weekly parser.

Corrections therefore go to the NORMALISED stores the dashboard and the agents
both read — DAILY_LOG (nightly) and WEEKLY_KI (weekly). Both are append-only
from the agents' side, so an edited row survives every subsequent run, and
LIVE_SNAPSHOT is rebuilt from DAILY_LOG on the next Agent3 pass, which is what
carries a correction through to the rest of the app.

Layouts, mirrored from CCSM_Agent3.gs so a correction cannot desync from what
the agent writes:

    DAILY_LOG   Date | Area | Zone | District | <one column per active
                NIGHTLY Metric_Key, in QUESTIONS_CONFIG order>
    WEEKLY_KI   Week_End_Date | Area | Zone | District | <ki_*_real / ki_*_meta>

Agent3 creates DAILY_LOG's header itself on its first run. If the header is
absent this module REFUSES to write rather than inventing one: a header written
here in a different column order than the agent expects would silently
mis-file every metric from then on.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app.db.sheets_client import append_row, read_values, update_cells
from app.utils.area_helpers import mission_timezone

DAILY_LOG_TAB = "DAILY_LOG"
WEEKLY_KI_TAB = "WEEKLY_KI"
AUDIT_TAB = "AUDIT_LOG"

#: Columns that identify a DAILY_LOG / WEEKLY_KI row rather than measure
#: anything. Never editable — changing one would move the row to a different
#: area or date instead of correcting its numbers.
_NIGHTLY_KEYS = ("Date", "Area", "Zone", "District")
_WEEKLY_KEYS = ("Week_End_Date", "Area", "Zone", "District")


def col_a1(col_0based: int) -> str:
    """0-based column index -> A1 letters."""
    letters = ""
    n = col_0based + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def _find_header(rows: list[list], marker: str) -> tuple[int, list[str]]:
    """Locate the real header row.

    Returns (0-based row index, headers) or (-1, []) when the tab has no header
    at all. Scans the first few rows rather than assuming row 1: these tabs can
    carry a stale manually-created row above the agent's own header, which is
    the same reason read_tab() takes a header_marker.
    """
    for i, row in enumerate(rows[:5]):
        cells = [str(c).strip() for c in row]
        if marker in cells:
            return i, cells
    return -1, []


def _rows_for(tab: str, marker: str) -> tuple[list[list], int, list[str]]:
    rows = read_values(tab)
    hdr_i, headers = _find_header(rows, marker)
    return rows, hdr_i, headers


def _match(rows, hdr_i, headers, key_col: str, key_val: str,
           area_val: str) -> int:
    """1-based sheet row number of the Area+key row, or -1.

    Dates are compared on their first 10 characters so a cell Google has typed
    as a datetime ("2026-08-01 0:00:00") still matches "2026-08-01".
    """
    try:
        ki, ai = headers.index(key_col), headers.index("Area")
    except ValueError:
        return -1
    for i in range(hdr_i + 1, len(rows)):
        row = list(rows[i]) + [""] * len(headers)
        if (str(row[ai]).strip() == str(area_val).strip()
                and str(row[ki]).strip()[:10] == str(key_val).strip()[:10]):
            return i + 1
    return -1


# ── Read ──────────────────────────────────────────────────────────────────────

def _get_submission(tab: str, marker: str, area: str, key_val: str) -> dict | None:
    rows, hdr_i, headers = _rows_for(tab, marker)
    if hdr_i < 0:
        return None
    n = _match(rows, hdr_i, headers, marker, key_val, area)
    if n < 0:
        return None
    row = list(rows[n - 1]) + [""] * len(headers)
    return {h: str(row[i]).strip() for i, h in enumerate(headers) if h}


def get_nightly_submission(area: str, date: str) -> dict | None:
    """One DAILY_LOG row as {column: value}, or None if that area never
    reported that date."""
    return _get_submission(DAILY_LOG_TAB, "Date", area, date)


def get_weekly_submission(area: str, week_end: str) -> dict | None:
    return _get_submission(WEEKLY_KI_TAB, "Week_End_Date", area, week_end)


def _submitted_keys(tab: str, marker: str, area: str) -> list[str]:
    rows, hdr_i, headers = _rows_for(tab, marker)
    if hdr_i < 0:
        return []
    try:
        ki, ai = headers.index(marker), headers.index("Area")
    except ValueError:
        return []
    out = []
    for i in range(hdr_i + 1, len(rows)):
        row = list(rows[i]) + [""] * len(headers)
        if str(row[ai]).strip() == str(area).strip():
            val = str(row[ki]).strip()[:10]
            if val:
                out.append(val)
    return sorted(set(out), reverse=True)


def nightly_dates_for_area(area: str) -> list[str]:
    """Every date this area has a DAILY_LOG row for, newest first."""
    return _submitted_keys(DAILY_LOG_TAB, "Date", area)


def weekly_weeks_for_area(area: str) -> list[str]:
    return _submitted_keys(WEEKLY_KI_TAB, "Week_End_Date", area)


def editable_columns(tab: str, marker: str, identity: tuple) -> list[str]:
    """Metric columns of a tab — everything that is not an identity column.

    Read from the SHEET's own header rather than from the metric catalogue: the
    goal is to edit the columns that actually exist in the tab. A metric added
    to QUESTIONS_CONFIG but not yet present in DAILY_LOG has no cell to write
    to, and writing one by position would shift every later value.
    """
    _rows, hdr_i, headers = _rows_for(tab, marker)
    if hdr_i < 0:
        return []
    return [h for h in headers if h and h not in identity]


def nightly_metric_columns() -> list[str]:
    return editable_columns(DAILY_LOG_TAB, "Date", _NIGHTLY_KEYS)


def weekly_metric_columns() -> list[str]:
    return editable_columns(WEEKLY_KI_TAB, "Week_End_Date", _WEEKLY_KEYS)


# ── Write ─────────────────────────────────────────────────────────────────────

def _audit(action: str, area: str, detail: str) -> None:
    """Append an AUDIT_LOG row. Best-effort: a correction that saved must not
    be reported as failed because its audit line could not be written.

    AUDIT_LOG carries no header row — its shape is positional, taken from the
    rows the agents already write:
    Timestamp | Source | Action | Count | Area | Detail
    """
    try:
        import zoneinfo
        now = datetime.now(zoneinfo.ZoneInfo(mission_timezone()))
    except Exception:
        now = datetime.now()
    try:
        append_row(AUDIT_TAB, [now.strftime("%Y-%m-%d %H:%M:%S"),
                               "Dashboard", action, "1", area, detail])
    except Exception:
        pass


def _save(tab: str, marker: str, identity: tuple, area: str, key_val: str,
          values: dict, edited_by: str, allow_create: bool) -> tuple[int, str]:
    """Write `values` into the Area+key row. Returns (fields_written, error).

    Only columns present in the sheet's header are written, and identity
    columns are refused outright — an edit must correct a report, never move it
    to another area or date.
    """
    rows, hdr_i, headers = _rows_for(tab, marker)
    if hdr_i < 0:
        return 0, (
            f"{tab} has no header row yet, so there is nothing to correct. "
            "The agents create it on their first successful run."
        )

    editable = {h for h in headers if h and h not in identity}
    unknown = [k for k in values if k not in editable]
    if unknown:
        return 0, f"{tab} has no column(s): {', '.join(sorted(unknown))}"

    n = _match(rows, hdr_i, headers, marker, key_val, area)

    if n < 0:
        if not allow_create:
            return 0, f"No {tab} row for {area} on {key_val}."
        # Backfill. Identity columns come from the caller's key, metrics from
        # `values`, everything else blank — matching the agent's column order
        # exactly, since a positional append is the only way to add a row.
        new = []
        for h in headers:
            if h == marker:
                new.append(key_val)
            elif h == "Area":
                new.append(area)
            else:
                new.append(values.get(h, ""))
        append_row(tab, new)
        _audit(f"{tab}_BACKFILL", area,
               f"{key_val} created by {edited_by} ({len(values)} field(s))")
        return len(values), ""

    updates = []
    for col, val in values.items():
        updates.append((f"{col_a1(headers.index(col))}{n}", val))
    if not updates:
        return 0, ""
    update_cells(tab, updates)
    _audit(f"{tab}_EDIT", area,
           f"{key_val} edited by {edited_by}: "
           + ", ".join(f"{k}={v}" for k, v in sorted(values.items())))
    return len(updates), ""


def save_nightly_submission(area: str, date: str, values: dict,
                            edited_by: str, allow_create: bool = False):
    """Correct one DAILY_LOG row. Returns (fields_written, error_message)."""
    return _save(DAILY_LOG_TAB, "Date", _NIGHTLY_KEYS, area, date, values,
                 edited_by, allow_create)


def save_weekly_submission(area: str, week_end: str, values: dict,
                           edited_by: str, allow_create: bool = False):
    """Correct one WEEKLY_KI row. Returns (fields_written, error_message)."""
    return _save(WEEKLY_KI_TAB, "Week_End_Date", _WEEKLY_KEYS, area, week_end,
                 values, edited_by, allow_create)


def clear_caches() -> None:
    """These reads go through read_values, which is cached for five minutes.
    Call after a save so the page re-reads what it just wrote instead of
    showing the pre-edit values back to the person who edited them."""
    try:
        read_values.clear()
    except Exception:
        pass
