"""
sheets_client.py
────────────────────────────────────────────────────────────
Gspread connection and base read/write helpers for COMPASS_CCSM.

All read functions are cached with st.cache_data(ttl=300).
Write functions (notes only) bypass cache and call cache_clear() after.

Credentials come from st.secrets["gcp_service_account"].
Sheet name comes from st.secrets["COMPASS_SHEET_NAME"].
"""

import time

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from app.i18n import t

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

_BACKOFF_SECONDS = 15


@st.cache_resource
def _failure_backoff() -> dict:
    """Shared-across-all-users, in-memory circuit breaker: key -> monotonic
    timestamp of the last failed read. Prevents a genuinely persistent failure
    (e.g. a real, sustained quota outage) from being retried against the live
    API on every single page load — without this, removing the old "cache the
    failure for 5 minutes" behavior (see read_tab()) would let concurrent
    users hammer a still-broken API once per page load instead of once per
    _BACKOFF_SECONDS. The warning is still shown on every skipped attempt —
    this only skips the network call, never the visible error."""
    return {}


def _recently_failed(key: str) -> bool:
    ts = _failure_backoff().get(key)
    return ts is not None and (time.monotonic() - ts) < _BACKOFF_SECONDS


def _record_failure(key: str) -> None:
    _failure_backoff()[key] = time.monotonic()


@st.cache_resource
def _get_client() -> gspread.Client:
    import json, base64
    if "GCP_SA_B64" in st.secrets:
        creds_dict = json.loads(base64.b64decode(st.secrets["GCP_SA_B64"]).decode("utf-8"))
    else:
        creds_dict = dict(st.secrets["gcp_service_account"])
        pk = creds_dict.get("private_key", "")
        pk = pk.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
        creds_dict["private_key"] = pk
    creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    # BackOffHTTPClient retries 429 quota errors with exponential backoff
    # instead of surfacing them — the read quota (60/min/user) is shared by
    # every signed-in user of the app, so brief bursts must self-heal.
    return gspread.authorize(creds, http_client=gspread.BackOffHTTPClient)


@st.cache_resource
def _get_spreadsheet() -> gspread.Spreadsheet:
    client = _get_client()
    return client.open(st.secrets["COMPASS_SHEET_NAME"])


@st.cache_resource(ttl=300)
def _get_worksheet(tab_name: str) -> gspread.Worksheet:
    """
    Resolve a worksheet by title. Cached 5 min — gspread's Spreadsheet.worksheet()
    calls fetch_sheet_metadata() (a full spreadsheet-metadata GET) on every call,
    so an uncached lookup silently doubles the read-quota cost of every read_tab()/
    read_values() call. Caching this cut quota usage in half and fixed 429s.
    """
    return _get_spreadsheet().worksheet(tab_name)


@st.cache_data(ttl=300)
def _read_tab_cached(tab_name: str, header_marker: str = None) -> pd.DataFrame:
    """Cached implementation. Only WorksheetNotFound (a stable, structural fact)
    is handled here — other exceptions (e.g. a transient 429) must propagate
    uncaught so Streamlit does NOT memoize a failure. See read_tab()."""
    try:
        ws = _get_worksheet(tab_name)
        rows = ws.get_all_values()
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
        headers = rows[header_idx]
        # Deduplicate blank/duplicate headers so DataFrame builds cleanly
        seen = {}
        clean_headers = []
        for h in headers:
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
        # Drop fully-blank columns (were empty header cells)
        df = df.loc[:, ~df.columns.str.startswith("_blank")]
        # Drop repeated header rows (agents rewrite their header on each run)
        if header_marker and header_marker in df.columns:
            df = df[df[header_marker].astype(str).str.strip() != header_marker]
        return df
    except gspread.exceptions.WorksheetNotFound:
        return pd.DataFrame()


def read_tab(tab_name: str, header_marker: str = None) -> pd.DataFrame:
    """
    Read a COMPASS_CCSM tab and return as a DataFrame. Cached 5 min.

    header_marker: name of a column that must exist in the real header row.
    Agent-written tabs (DASHBOARD_SUMMARY, WEEKLY_KI, LIVE_SNAPSHOT) carry their
    own header, which can sit below a stale manually-created header because
    Apps Script overwriteTab() preserves row 1. When a marker is given, the
    header row is located by scanning the first rows instead of assuming row 1,
    and any repeated header rows in the data are dropped.

    Transient failures (e.g. a Sheets API 429) are caught HERE, outside the
    cache boundary, so they are never memoized as a "successful" empty result —
    otherwise a single rate-limit blip would get frozen in and replayed as a
    failure to every user for the rest of the 5-minute TTL, even after the
    real quota had already recovered. Each call retries for real until it
    succeeds, at which point the good result gets cached normally.

    If a read just failed, retries are backed off for _BACKOFF_SECONDS (the
    warning still shows every time — only the live API call is skipped) so a
    genuinely persistent failure can't be hammered once per page load.
    """
    key = f"{tab_name}::{header_marker}"
    if _recently_failed(key):
        st.warning(t("Could not read tab '{tab_name}': recent read failure, backing off before retrying.", tab_name=tab_name))
        return pd.DataFrame()
    try:
        return _read_tab_cached(tab_name, header_marker)
    except Exception as e:
        _record_failure(key)
        st.warning(t("Could not read tab '{tab_name}': {e}", tab_name=tab_name, e=e))
        return pd.DataFrame()


read_tab.clear = _read_tab_cached.clear


@st.cache_data(ttl=300)
def _read_values_cached(tab_name: str) -> list:
    """Cached implementation — see read_values()."""
    try:
        ws = _get_worksheet(tab_name)
        return ws.get_all_values()
    except gspread.exceptions.WorksheetNotFound:
        return []


def read_values(tab_name: str) -> list:
    """
    Return a tab's raw cell grid as a list of row-lists (positional, header
    included as row 0). Unlike read_tab, this does NOT interpret or dedupe the
    header row — use it for tabs whose header labels are unreliable and must be
    read by column position (e.g. the form-linked SUGGESTIONS response sheet).
    Cached 5 min. Returns [] if the tab is missing.

    Transient failures are caught outside the cache boundary — see read_tab()'s
    docstring for why (otherwise a single 429 gets replayed as a failure for
    the whole TTL instead of self-healing on the next successful call), and
    back off for _BACKOFF_SECONDS after a failure (warning still shown every
    time; only the live API call is skipped) to avoid hammering a persistent
    outage once per page load.
    """
    key = f"values::{tab_name}"
    if _recently_failed(key):
        st.warning(t("Could not read tab '{tab_name}': recent read failure, backing off before retrying.", tab_name=tab_name))
        return []
    try:
        return _read_values_cached(tab_name)
    except Exception as e:
        _record_failure(key)
        st.warning(t("Could not read tab '{tab_name}': {e}", tab_name=tab_name, e=e))
        return []


read_values.clear = _read_values_cached.clear


# ── Write helpers (notes) ──────────────────────────────────────────────────────

def _clear_read_caches(scope_tab: str | None = None) -> None:
    """Invalidate cached reads after a write. Default clears everything.

    Pass scope_tab (with scoped=True on the write helpers) to drop ONLY that
    tab's read_values entry, leaving every other tab's cache warm — after a
    write, the rerun then re-reads one tab instead of the whole page, which
    is what kept burst edits (Transfer Schedule) under the read quota.
    ONLY valid for tabs never read via read_tab: read_tab's cache key
    includes header_marker, so per-tab clearing can't target it."""
    if scope_tab is not None:
        _read_values_cached.clear(scope_tab)
    else:
        read_tab.clear()
        read_values.clear()


def append_row(tab_name: str, row: list, scoped: bool = False) -> None:
    """Append one row to a tab. Clears read cache after write (see
    _clear_read_caches for what scoped=True means)."""
    ws = _get_worksheet(tab_name)
    ws.append_row(row, value_input_option="USER_ENTERED")
    _clear_read_caches(tab_name if scoped else None)


def append_rows(tab_name: str, rows: list[list], scoped: bool = False) -> None:
    """Append several rows in ONE API call (vs. one call per append_row —
    burst appends were tripping the per-minute quota). Clears cache after."""
    ws = _get_worksheet(tab_name)
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    _clear_read_caches(tab_name if scoped else None)


def update_row(tab_name: str, row_number: int, row: list) -> None:
    """Overwrite a specific 1-based row (row 1 = header). Clears cache after."""
    ws = _get_worksheet(tab_name)
    ws.update(f"A{row_number}", [row])
    read_tab.clear()
    read_values.clear()


def update_cell(tab_name: str, a1: str, value) -> None:
    """Write a single cell by A1 reference (e.g. 'B3'). Clears cache after.
    Used when a full-row overwrite would clobber neighbouring formulas
    (e.g. TRANSFER_SCHEDULE's derived Weeks column)."""
    ws = _get_worksheet(tab_name)
    ws.update(a1, [[value]], value_input_option="USER_ENTERED")
    read_tab.clear()
    read_values.clear()


def update_cells(tab_name: str, updates: list[tuple[str, object]],
                 scoped: bool = False) -> None:
    """Write several (A1, value) cells in ONE batch API call — a multi-cell
    save must not cost one round-trip per cell (each carries a metadata read
    that counts against the read quota). Clears cache after."""
    ws = _get_worksheet(tab_name)
    ws.batch_update(
        [{"range": a1, "values": [[value]]} for a1, value in updates],
        value_input_option="USER_ENTERED",
    )
    _clear_read_caches(tab_name if scoped else None)


def delete_row(tab_name: str, row_number: int, scoped: bool = False) -> None:
    """Delete a specific 1-based row. Clears cache after."""
    ws = _get_worksheet(tab_name)
    ws.delete_rows(row_number)
    _clear_read_caches(tab_name if scoped else None)


def overwrite_tab(tab_name: str, rows: list[list]) -> None:
    """
    Clear a tab and write a 2D list of rows (header + data) in one batch.
    Creates the tab if it doesn't exist. Clears read cache after.
    Used for config tabs that must be rewritten cleanly (e.g. SCORE_CONFIG)
    rather than appended to.
    """
    try:
        ws = _get_worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = _get_spreadsheet().add_worksheet(title=tab_name, rows=max(1000, len(rows) + 50), cols=20)
    ws.clear()
    if rows:
        ws.update(rows, value_input_option="USER_ENTERED")
    read_tab.clear()
    read_values.clear()


def get_last_row_number(tab_name: str) -> int:
    """Return the 1-based index of the last data row (including header)."""
    ws = _get_worksheet(tab_name)
    return ws.row_count if ws.row_count else 1


def save_dataframe(tab_name: str, df: pd.DataFrame, uploaded_by: str = "") -> None:
    """
    Overwrite a tab completely with a DataFrame.
    Writes header row + all data rows. Clears read cache after.
    Used for Tableau CSV persistence — stores the last upload for all users.
    """
    try:
        try:
            ws = _get_worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = _get_spreadsheet().add_worksheet(title=tab_name, rows=5000, cols=50)

        ws.clear()

        # Add metadata row at top for "last uploaded by / when"
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        meta = [f"_uploaded_by:{uploaded_by}", f"_uploaded_at:{ts}"] + [""] * max(0, len(df.columns) - 2)
        # Header row first so read_tab() returns df.columns = real column names;
        # meta row becomes df.iloc[0] so get_tableau_*() can extract uploaded_by/at.
        rows = [df.columns.tolist(), meta[:len(df.columns)]] + df.values.tolist()
        ws.update(rows, value_input_option="USER_ENTERED")
        read_tab.clear()
        read_values.clear()
    except Exception as e:
        import streamlit as _st
        _st.warning(t("Could not save to '{tab_name}': {e}", tab_name=tab_name, e=e))
