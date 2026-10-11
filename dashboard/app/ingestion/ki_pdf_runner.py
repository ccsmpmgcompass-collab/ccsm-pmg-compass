"""The Monday job that builds the weekly KI PDFs for the weekly letter.

PLAN-2026-10-10-ki-autosend.md (K3, K5). Runs in GitHub Actions
(`.github/workflows/ki-pdfs.yml`), scheduled Monday evening, BEFORE the letter
chain starts. The handshake goes through one sheet tab, KI_PDF_OUTBOX:

  1. Agent1A (Monday ~21:30) reads the weekly forms for the letter and writes a
     REQUEST row: the week end and the cutoff — the moment it read them.
  2. This job waits for that row, builds the mission document and every zone's
     from the forms stamped at or before that cutoff (`ki_ranking`), and writes
     each PDF back as a PDF row, base64 in cells of at most 45,000 characters.
  3. Agent1C attaches them to the APs' and the zone leaders' letters.

So the letter and the PDFs count exactly the same forms, and a late form waits
for next week in both (K3). If this job never shows, Agent1C sends the letters
without the PDFs after ~10 minutes and logs it (K6).

No Streamlit. **The repository is public**, so nothing this prints names a
sector, a zone or a figure — counts only.

    python -m app.ingestion.ki_pdf_runner [--wait-minutes 210] [--week-end YYYY-MM-DD]
                                          [--now] [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from datetime import date, datetime, timedelta

OUTBOX_TAB = "KI_PDF_OUTBOX"
OUTBOX_HEADER = ["Kind", "Week_End", "Scope", "File_Name", "Stamp", "Pages", "Parts"]
#: A Sheets cell holds 50,000 characters; stay well under it.
PART_CHARS = 45_000
#: Agent1A writes its cutoff in this form, in mission time.
STAMP_FMT = "%Y-%m-%d %H:%M:%S"
SOURCE_TABS = ["WEEKLY_FORM_RAW", "MISSION_ORG", "QUESTIONS_CONFIG"]


def _status(msg: str) -> None:
    print(json.dumps({"type": "status", "msg": msg}), flush=True)


# ── Pure: the outbox ──────────────────────────────────────────────────────────

def last_sunday(today: date) -> date:
    """The Sunday ending the week the letter grades: today when today is a
    Sunday, else the one before. Same rule as runAgent1A's weekEnd."""
    return today - timedelta(days=(today.weekday() + 1) % 7)


def find_request(grid: list, week_end: date) -> datetime | None:
    """The cutoff of the REQUEST row Agent1A wrote for `week_end`, or None."""
    for row in grid[1:]:
        row = list(row) + [""] * len(OUTBOX_HEADER)
        if row[0] == "REQUEST" and row[1] == week_end.isoformat():
            try:
                return datetime.strptime(row[4].strip(), STAMP_FMT)
            except ValueError:
                return None
    return None


def already_built(grid: list, week_end: date, stamp: str) -> bool:
    return any(len(r) > 4 and r[0] == "PDF" and r[1] == week_end.isoformat()
               and r[4] == stamp for r in grid[1:])


def pdf_rows(docs: list, week_end: date, stamp: str) -> list[list]:
    """One PDF row per document, its bytes as base64 split over Part cells."""
    rows = []
    for d in docs:
        b64 = base64.b64encode(d["pdf"]).decode("ascii")
        parts = [b64[i:i + PART_CHARS] for i in range(0, len(b64), PART_CHARS)]
        rows.append(["PDF", week_end.isoformat(), d["scope"], d["file_name"], stamp,
                     str(d["pages"]), str(len(parts))] + parts)
    return rows


def outbox_grid(grid: list, week_end: date, new_rows: list) -> list[list]:
    """The tab after this run: the header, this week's REQUEST row kept as
    Agent1A wrote it, and the new PDF rows. Older weeks' rows go."""
    keep = [list(r) for r in grid[1:]
            if r and r[0] == "REQUEST" and r[1] == week_end.isoformat()]
    width = max([len(OUTBOX_HEADER)] + [len(r) for r in keep + new_rows])
    header = OUTBOX_HEADER + [f"Part_{i}" for i in range(1, width - len(OUTBOX_HEADER) + 1)]
    return [header] + keep + new_rows


def decode(row: list) -> bytes:
    """A PDF row back to its bytes (what Agent1C does in Apps Script)."""
    n = int(row[6])
    return base64.b64decode("".join(row[7:7 + n]))


# ── Sheets ────────────────────────────────────────────────────────────────────

def _sheet_io():
    # The goals job's Sheets helpers: same credentials, same RAW overwrite.
    from app.ingestion.area_goals_runner import _grid, _open_sheet, _overwrite
    return _open_sheet, _grid, _overwrite


def _mission_now(cfg_grid: list) -> datetime:
    """Now on the mission's clock, naive — the clock the form stamps use."""
    tz = next((r[1] for r in cfg_grid if len(r) > 1 and r[0] == "MISSION_TIMEZONE"), "")
    try:
        import zoneinfo
        return datetime.now(zoneinfo.ZoneInfo(tz or "America/Santiago")).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the weekly KI PDFs for the letter.")
    ap.add_argument("--week-end", help="The Sunday ending the graded week (default: the last one).")
    ap.add_argument("--wait-minutes", type=int, default=210,
                    help="How long to wait for Agent1A's REQUEST row.")
    ap.add_argument("--now", action="store_true",
                    help="Do not wait for a request: build from every form now.")
    ap.add_argument("--dry-run", action="store_true", help="Build and count; write nothing.")
    args = ap.parse_args()

    from app.reports import ki_ranking as KR
    open_sheet, grid_of, overwrite = _sheet_io()

    sh = open_sheet()
    cfg = grid_of(sh, "AGENT_CONFIG")
    week_end = (date.fromisoformat(args.week_end) if args.week_end
                else last_sunday(_mission_now(cfg).date()))

    cutoff = None
    if not args.now:
        _status(f"Waiting up to {args.wait_minutes} min for the letter's request, week ending {week_end}")
        deadline = time.monotonic() + args.wait_minutes * 60
        while True:
            cutoff = find_request(grid_of(sh, OUTBOX_TAB), week_end)
            if cutoff or time.monotonic() > deadline:
                break
            time.sleep(60)
        if not cutoff:
            print(f"ERROR: no request for the week ending {week_end} after "
                  f"{args.wait_minutes} min; the letter goes without PDFs", file=sys.stderr)
            sys.exit(1)
    stamp = (cutoff or _mission_now(cfg)).strftime(STAMP_FMT)
    if cutoff and already_built(grid_of(sh, OUTBOX_TAB), week_end, stamp):
        _status("Already built for this request - nothing to do")
        return

    _status("Reading the weekly forms")
    raw = {t: grid_of(sh, t) for t in SOURCE_TABS}
    docs = KR.build_documents(raw, week_end, cutoff, stamp[:16])
    rows = pdf_rows(docs, week_end, stamp)
    _status(f"Built {len(docs)} documents, {sum(d['pages'] for d in docs)} pages, "
            f"{sum(int(r[6]) for r in rows)} cells")
    if args.dry_run:
        _status("Dry run - nothing written")
        return
    # Re-read right before writing: the tab is Agent1A's too.
    overwrite(sh, OUTBOX_TAB, outbox_grid(grid_of(sh, OUTBOX_TAB), week_end, rows))
    _status(f"Done: {len(rows)} PDFs in {OUTBOX_TAB} for the week ending {week_end}")


if __name__ == "__main__":
    main()
