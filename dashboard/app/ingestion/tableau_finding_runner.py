"""
tableau_finding_runner.py — CLI entry point for CCSM's nightly Tableau pull.

Runs standalone (GitHub Actions or a local shell), with no Streamlit context —
so it authenticates to Sheets directly through ``gcp_creds`` and writes with
the pure helpers in ``app/db/tabular_io.py`` rather than ``sheets_client``,
which needs ``st.secrets`` and a Streamlit that is not installed in the cloud
job's container.

Usage::

    python -m app.ingestion.tableau_finding_runner              # the nightly job
    python -m app.ingestion.tableau_finding_runner --no-detail  # baptisms only
    python -m app.ingestion.tableau_finding_runner --months 4   # deeper backfill

**What it does, and why in this order.**

1. **Baptisms first.** Each run re-pulls the current month AND the previous one
   (``--months``), because a baptism performed on the 18th may not be in
   Tableau on the 19th. Revisiting a month that already looks finished is the
   single biggest accuracy gain over the manual process, which captures a month
   once and never comes back to it. Nightly, because the source itself
   refreshes daily — it stamped ``Data Last Updated: 9/18/2026 12:55 PM`` when
   read on 2026-09-19.

2. **Detail second, and always in full.** A Detail write REPLACES the store;
   it cannot merge, because the only stable per-person key is the ``person_id``
   the privacy decision drops at ingest. ``describe_replacement``'s ``narrower``
   check is what stands between a partial export and 2.6 years of history, and
   it stays armed here: a narrower pull is REFUSED, loudly, rather than stored.

**Every stored figure is verified against the file it came from.** The window
is applied as a URL parameter (see ``tableau_finding_portal``), and a URL
parameter that silently fails to apply would hand back a plausible export for
the wrong days. So each Summary PDF is parsed and its own printed window is
compared against the window that was requested; a mismatch aborts before
anything is written. The Detail export gets the equivalent check through its
date span. Nothing reaches the sheet on the strength of the request alone.

Failures are per-part: a run that stores the baptism months and then refuses a
narrower Detail export has done the useful half of its job, says so, and exits
non-zero so the cloud job reports ERROR.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from app.db.tabular_io import (
    encode_blob, frame_from_values, meta_row, plan_write_chunks,
)
from app.ingestion.tableau_detail_transform import clean_detail
from app.ingestion.tableau_summary_parser import baptisms_rows, parse_summary_pdf
from app.ingestion.tableau_upload import (
    date_span, describe_replacement, is_provisional, merge_baptism_rows,
    read_tabular, summarize_months,
)
from app.integrations.gcp_creds import get_service_account_dict
from app.utils.area_helpers import mission_today
from app.utils.logger import get_logger

_logger = get_logger("ingestion.tableau_finding_runner")

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

#: Stamped into the metadata row. ``_source_caption`` on the Embudo page reads
#: an ``auto:`` prefix and renders "Auto-synced · tableau · {when}" instead of
#: "Uploaded by …", so a nightly write never looks like somebody's manual one.
UPLOADED_BY = "auto:tableau"

BAPTISMS_TAB = "TABLEAU_BAPTISMS"
DETAIL_TAB = "TABLEAU_DETAIL"
AGENT_CONFIG_TAB = "AGENT_CONFIG"
DETAIL_FILE_ID_KEY = "TABLEAU_DETAIL_FILE_ID"

#: The floor for a FULL Detail pull. The stored export reaches back to early
#: 2024; asking for less than everything is the one thing the Detail path must
#: never do, so the request starts here (or earlier, if the store already does)
#: and runs to today.
DETAIL_FLOOR = date(2024, 1, 1)


# ══════════════════════════════════════════════════════════════════════════════
# PURE
# ══════════════════════════════════════════════════════════════════════════════

def capture_windows(today: date, months_back: int = 2) -> list[tuple[date, date]]:
    """The windows a run should capture, oldest first.

    ``months_back=2`` on 2026-09-19 gives August whole (1st-31st) and September
    to date (1st-19th). The current month's window ENDS TODAY rather than on the
    month's last day, which is what makes it provisional downstream — see
    ``tableau_upload.is_provisional``. Finished months are re-pulled with their
    real last day, so re-capturing one promotes it from provisional to certified
    without any special case.
    """
    months_back = max(1, months_back)
    year, month = today.year, today.month
    windows = []
    for _ in range(months_back):
        last = date(year, month, calendar.monthrange(year, month)[1])
        windows.append((date(year, month, 1), min(last, today)))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(windows))


def detail_window(today: date, existing_start: date | None) -> tuple[date, date]:
    """The window for a FULL Detail pull: never narrower than what is stored."""
    start = DETAIL_FLOOR if existing_start is None else min(existing_start, DETAIL_FLOOR)
    return start, today


def verify_window(summary, start: date, end: date) -> None:
    """Refuse a summary whose own printed window is not the one we asked for.

    This is the check that makes a URL-parameter filter safe to rely on. The
    PDF prints ``Start Date … End Date`` and the parser reads it out of the
    file, so a parameter that failed to apply — a renamed workbook parameter, a
    saved custom view, a silent fallback to the default window — is caught here
    instead of being stored as a correct-looking figure for the wrong days.
    """
    got = (summary.start_date, summary.end_date)
    want = (start.isoformat(), end.isoformat())
    if got != want:
        raise RuntimeError(
            f"Tableau returned the window {got[0]}..{got[1]} but {want[0]}.."
            f"{want[1]} was requested — the date parameters did not apply. "
            f"Nothing stored."
        )


def guard_detail_replacement(stored: pd.DataFrame, clean: pd.DataFrame,
                             stats: dict) -> None:
    """Raise unless replacing the Detail store with ``clean`` is safe.

    Two refusals, in this order, and the order is the point.

    **Is this file even the Detail view?** An export of the wrong sheet cleans
    to something with none of the recognised milestone columns and therefore no
    date span at all — which ``narrower`` reads as "nothing to lose" and would
    wave straight through, on top of 2.6 years of history. So identity is
    checked first and independently.

    **Is it narrower than what we hold?** ``describe_replacement``'s existing
    verdict. The Embudo page can offer "Replace anyway" because a human is
    standing there; an unattended run has nobody to ask, so it simply refuses.
    """
    plan = describe_replacement(stored, clean)
    if clean.empty or (not stored.empty and plan["incoming_span"] == (None, None)):
        raise RuntimeError(
            f"REFUSED: the Detail export cleaned to {len(clean)} rows with no "
            f"usable dates (columns missing: "
            f"{stats.get('missing_expected') or 'none'}) — that is not the "
            f"Detail view. Nothing written."
        )
    if plan["narrower"]:
        o1, o2 = plan["existing_span"]
        n1, n2 = plan["incoming_span"]
        raise RuntimeError(
            f"REFUSED: the Detail export covers {n1}..{n2} "
            f"({plan['incoming_rows']} people) but the store covers {o1}..{o2} "
            f"({plan['existing_rows']}). A Detail write replaces rather than "
            f"merges, so this would destroy history. Nothing written."
        )


def status(msg: str) -> None:
    """One progress line, in the shape ``cloud_job_wrapper`` parses.

    The wrapper mirrors whatever a runner prints into CLOUD_JOB_STATUS, so this
    text is what the person watching the Embudo page's spinner actually reads.
    """
    print(json.dumps({"type": "status", "msg": msg}), flush=True)
    _logger.info(msg)


# ══════════════════════════════════════════════════════════════════════════════
# SHEETS — the same bytes sheets_client writes, without Streamlit
# ══════════════════════════════════════════════════════════════════════════════

def _open_sheet():
    creds = Credentials.from_service_account_info(
        get_service_account_dict(), scopes=_SCOPES)
    client = gspread.authorize(creds)
    name = os.environ.get("COMPASS_SHEET_NAME", "COMPASS_CCSM")
    return client.open(name), client


def _read_tab(sh, tab_name: str, header_marker: str | None = None) -> pd.DataFrame:
    try:
        ws = sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        return pd.DataFrame()
    return frame_from_values(ws.get_all_values(), header_marker)


def _write_tab(sh, tab_name: str, df: pd.DataFrame) -> None:
    """Overwrite a tab, header + metadata row + data, chunked — save_dataframe's
    write without save_dataframe's Streamlit."""
    n_cols = len(df.columns)
    if n_cols == 0:
        raise ValueError("refusing to write a frame with no columns")
    rows = [df.columns.tolist(), meta_row(n_cols, UPLOADED_BY)] + df.values.tolist()
    try:
        ws = sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows=max(len(rows), 100), cols=n_cols)
    ws.clear()
    if ws.row_count != len(rows) or ws.col_count != n_cols:
        ws.resize(rows=max(len(rows), 1), cols=n_cols)
    plan = plan_write_chunks(len(rows), n_cols)
    for i, (rng, lo, hi) in enumerate(plan, 1):
        try:
            ws.update(rows[lo:hi], rng, value_input_option="USER_ENTERED")
        except Exception as e:
            raise RuntimeError(
                f"{tab_name}: chunk {i} of {len(plan)} (rows {lo + 1}-{hi}) "
                f"failed: {e}") from e


def _agent_config(sh) -> dict:
    df = _read_tab(sh, AGENT_CONFIG_TAB)
    if df.empty:
        return {}
    key_col = next((c for c in df.columns if c.strip().lower() in ("config_key", "key")), None)
    val_col = next((c for c in df.columns if c.strip().lower() in ("value", "config_value")), None)
    if not key_col or not val_col:
        return {}
    return dict(zip(df[key_col].astype(str).str.strip(),
                    df[val_col].astype(str).str.strip()))


def _read_detail(sh, client, file_id: str) -> pd.DataFrame:
    """What the Detail store currently holds — the blob when one is configured,
    the tab otherwise. The same choice ``get_tableau_detail`` makes on the way
    in, so the two can never disagree about where the data lives."""
    if file_id:
        from app.db.tabular_io import decode_blob
        r = client.http_client.session.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={"alt": "media"}, timeout=120)
        if r.ok:
            df, _, _ = decode_blob(r.content)
            return df
        _logger.warning(f"Detail blob unreadable (HTTP {r.status_code}) — "
                        f"falling back to the {DETAIL_TAB} tab")
    df = _read_tab(sh, DETAIL_TAB)
    return df.iloc[1:].reset_index(drop=True) if len(df) > 1 else pd.DataFrame()


def _write_detail(sh, client, file_id: str, df: pd.DataFrame) -> str:
    """Store the cleaned Detail export. Returns a one-line description of where
    it went, for the job's result summary."""
    if file_id:
        payload = encode_blob(df, uploaded_by=UPLOADED_BY)
        r = client.http_client.session.patch(
            f"https://www.googleapis.com/upload/drive/v3/files/{file_id}",
            params={"uploadType": "media"}, data=payload,
            headers={"Content-Type": "application/gzip"}, timeout=120)
        if not r.ok:
            # PATCH, never POST: the service account has a 0-byte quota and
            # cannot CREATE a Drive file, so a 404 here means a human has to
            # make a new one and re-share it. Retrying never helps.
            raise RuntimeError(f"Drive upload failed: HTTP {r.status_code}")
        return f"{len(df)} people to Drive ({len(payload) / 1e6:.2f} MB gzipped)"
    _write_tab(sh, DETAIL_TAB, df)
    return f"{len(df)} people to the {DETAIL_TAB} tab"


# ══════════════════════════════════════════════════════════════════════════════
# THE TWO JOBS
# ══════════════════════════════════════════════════════════════════════════════

def pull_baptisms(page, sh, windows, tmp: Path) -> str:
    """Capture each window's Summary PDF and merge the lot into TABLEAU_BAPTISMS."""
    from app.ingestion import tableau_finding_portal as portal

    parsed = []
    for start, end in windows:
        status(f"Exporting the Summary for {start} to {end}...")
        pdf_path = portal.download_summary_pdf(page, start, end, tmp)
        summary = parse_summary_pdf(pdf_path)
        verify_window(summary, start, end)
        parsed.append(summary)
        _logger.info(f"{summary.month}: {summary.baptized} baptized "
                     f"({summary.start_date}..{summary.end_date})")

    merged = merge_baptism_rows(_read_tab(sh, BAPTISMS_TAB), baptisms_rows(parsed))
    _write_tab(sh, BAPTISMS_TAB, merged)

    provisional = [s.month for s in parsed if is_provisional(s.month, s.end_date)]
    note = f"{BAPTISMS_TAB}: {len(merged)} months · {summarize_months(merged['month'])}"
    if provisional:
        note += f" · {', '.join(provisional)} stored as month-to-date"
    return note


def pull_detail(page, sh, client, today: date, tmp: Path) -> str:
    """Take a FULL Detail export, clean it, and refuse it if it is narrower than
    what is already stored."""
    from app.ingestion import tableau_finding_portal as portal

    file_id = str(_agent_config(sh).get(DETAIL_FILE_ID_KEY, "")).strip()
    stored = _read_detail(sh, client, file_id)
    existing_start, _ = date_span(stored)
    start, end = detail_window(today, existing_start)

    status(f"Exporting the full Detail view ({start} to {end})...")
    path = portal.download_crosstab(page, portal.SHEET_DETAIL, start, end, tmp)
    raw = read_tabular(path, path.name)
    clean, stats = clean_detail(raw)

    guard_detail_replacement(stored, clean, stats)
    where = _write_detail(sh, client, file_id, clean)
    return (f"{DETAIL_TAB}: {where} · {stats.get('artifact_rows_dropped', 0)} "
            f"artifact rows dropped · names and person ids removed")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(description="Pull the Mission Finding exports from Tableau.")
    ap.add_argument("--months", type=int, default=2,
                    help="how many months back to re-capture (default 2: this "
                         "month to date and the whole month before it)")
    ap.add_argument("--no-detail", action="store_true",
                    help="skip the Detail export; capture baptisms only")
    ap.add_argument("--detail-only", action="store_true",
                    help="skip the baptism capture; pull Detail only")
    ap.add_argument("--headed", action="store_true",
                    help="show the browser (local debugging only)")
    args = ap.parse_args()

    # Stripped, and the stripping is REPORTED. A secret pasted out of a password
    # manager very often carries a trailing newline, GitHub stores exactly what
    # was pasted, and the sign-in then fails with a credential its owner is
    # certain of — which is a day of blaming the wrong thing. The boolean says
    # whether there was anything to strip; the value is never logged, and nor is
    # its length.
    username = os.environ.get("CCSM_TABLEAU_USERNAME", "")
    password = os.environ.get("CCSM_TABLEAU_PASSWORD", "")
    if username != username.strip() or password != password.strip():
        _logger.warning(
            f"Surrounding whitespace trimmed from the secrets "
            f"(username: {username != username.strip()}, "
            f"password: {password != password.strip()}) — worth removing at the "
            f"source, since anything else pasted with it is still there.")
    username, password = username.strip(), password.strip()
    if not username or not password:
        _logger.error("CCSM_TABLEAU_USERNAME/CCSM_TABLEAU_PASSWORD not set — aborting.")
        sys.exit(1)

    # The Church IdP wants a DIFFERENT credential from Tableau's own page: an
    # email gets you through Tableau and then fails at Okta as "Invalid username
    # and password combination", because Okta shows the password screen even for
    # usernames it does not know (runs 8-11).
    #
    # Default to the IMOS pair. It is the same Okta — imos_portal signs into
    # id.churchofjesuschrist.org with exactly these — and they are already
    # secrets on this repository, so the common case needs nothing added.
    # CCSM_CHURCH_* overrides when the Tableau account belongs to someone else.
    church_user = (os.environ.get("CCSM_CHURCH_USERNAME")
                   or os.environ.get("CCSM_IMOS_USERNAME") or "").strip()
    church_pass = (os.environ.get("CCSM_CHURCH_PASSWORD")
                   or os.environ.get("CCSM_IMOS_PASSWORD") or "").strip()
    _logger.info(
        "Church SSO credentials: "
        + ("CCSM_CHURCH_*" if os.environ.get("CCSM_CHURCH_USERNAME")
           else "CCSM_IMOS_* (same Okta as the roster pull)" if church_user
           else "none set — falling back to the Tableau pair, which Okta will "
                "refuse unless they happen to be the Church ones"))

    if args.detail_only and args.no_detail:
        _logger.error("--detail-only and --no-detail ask for nothing at all.")
        sys.exit(2)

    from app.ingestion import tableau_finding_portal as portal

    # Mission-local, not the container's UTC. The window's end date is stored
    # and displayed — the Panel labels the month-to-date line with it — and a
    # job run in the Chilean evening is already tomorrow by UTC.
    today = mission_today()
    windows = capture_windows(today, args.months)
    sh, client = _open_sheet()

    results, failures = [], []
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        status("Signing in to Tableau...")
        with portal.tableau_session(username, password, headless=not args.headed,
                                    church_username=church_user,
                                    church_password=church_pass) as page:
            if not args.detail_only:
                try:
                    results.append(pull_baptisms(page, sh, windows, tmp))
                except Exception as e:
                    # Keep going: the Detail pull is independent, and a run that
                    # salvages half is worth more than one that abandons both.
                    _logger.error(f"Baptism capture failed: {e}")
                    failures.append(f"baptisms: {e}")
            if not args.no_detail:
                try:
                    results.append(pull_detail(page, sh, client, today, tmp))
                except Exception as e:
                    _logger.error(f"Detail pull failed: {e}")
                    failures.append(f"detail: {e}")

    for line in results:
        status(line)
    if failures:
        status("FAILED — " + " | ".join(failures))
        sys.exit(1)
    status("Done — " + " | ".join(results))


if __name__ == "__main__":
    main()
