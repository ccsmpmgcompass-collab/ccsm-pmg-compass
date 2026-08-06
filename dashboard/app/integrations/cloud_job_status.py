"""
cloud_job_status.py — read/write helper for the CLOUD_JOB_STATUS sheet tab in
COMPASS_CCSM. Shared status channel between the dashboard (wherever it's
running) and GitHub Actions workflows.

Ported from Utah Provo's app/integrations/cloud_job_status.py, adapted to open
the sheet by NAME (COMPASS_SHEET_NAME) rather than by ID — matching CCSM's
own convention everywhere else (app/db/sheets_client.py), and avoiding the
need for a separate COMPASS_SHEET_ID secret Provo's version required.

Works both inside a bare GitHub Actions runner and inside Streamlit — see
gcp_creds.get_service_account_dict() for how credentials resolve in each.
"""
import os
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from app.integrations.gcp_creds import get_service_account_dict

SHEET_TAB = "CLOUD_JOB_STATUS"
HEADERS = ["job_id", "job_type", "status", "progress_text",
           "started_at", "updated_at", "result_summary"]
_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def _get_sheet_name() -> str:
    name = os.environ.get("COMPASS_SHEET_NAME", "")
    if name:
        return name
    import streamlit as st
    return st.secrets["COMPASS_SHEET_NAME"]


_ws_cache: gspread.Worksheet | None = None
_row_cache: dict[str, int] = {}


def _get_worksheet() -> gspread.Worksheet:
    """Cached per-process — see Provo's identical caching rationale: opening
    once and reusing the handle avoids re-authenticating + re-fetching
    spreadsheet metadata on every 3-second poll tick."""
    global _ws_cache
    if _ws_cache is None:
        creds_dict = get_service_account_dict()
        creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
        client = gspread.authorize(creds)
        sh = client.open(_get_sheet_name())
        _ws_cache = sh.worksheet(SHEET_TAB)
    return _ws_cache


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_row(ws: gspread.Worksheet, job_id: str) -> int | None:
    row = _row_cache.get(job_id)
    if row is not None:
        return row
    cell = ws.find(job_id, in_column=1)
    if cell is None:
        return None
    _row_cache[job_id] = cell.row
    return cell.row


def create_job(job_id: str, job_type: str) -> None:
    ws = _get_worksheet()
    now = _now()
    ws.append_row([job_id, job_type, "QUEUED", "", now, now, ""],
                  value_input_option="RAW")


def update_job(job_id: str, status: str, progress_text: str = "",
               result_summary: str = "") -> None:
    ws = _get_worksheet()
    row = _find_row(ws, job_id)
    if row is None:
        create_job(job_id, "unknown")
        row = _find_row(ws, job_id)
    now = _now()
    ws.update(f"C{row}:D{row}", [[status, progress_text]], value_input_option="RAW")
    ws.update(f"F{row}:G{row}", [[now, result_summary]], value_input_option="RAW")


def get_job(job_id: str) -> dict | None:
    ws = _get_worksheet()
    row = _find_row(ws, job_id)
    if row is None:
        return None
    values = ws.row_values(row)
    values = list(values) + [""] * (len(HEADERS) - len(values))
    return dict(zip(HEADERS, values))
