"""
probe_live.py — read-only inspector for the live COMPASS_CCSM sheet.
────────────────────────────────────────────────────────────────────
Standalone: needs NO Streamlit runtime. Reads credentials straight out of
dashboard/.streamlit/secrets.toml (the same service account the app uses),
so it can be run from a plain shell while the app is not running.

STRICTLY READ-ONLY. Nothing in this file writes, appends, or clears. Every
COMPASS_CCSM write during the go-live program must be drafted, shown to the
user, and confirmed before it happens — this tool exists so that drafting can
be based on what the sheet actually holds instead of on recollection.

Usage (always via the dashboard venv):

    venv\\Scripts\\python.exe tools\\probe_live.py tabs
    venv\\Scripts\\python.exe tools\\probe_live.py config
    venv\\Scripts\\python.exe tools\\probe_live.py questions
    venv\\Scripts\\python.exe tools\\probe_live.py org
    venv\\Scripts\\python.exe tools\\probe_live.py health
    venv\\Scripts\\python.exe tools\\probe_live.py dump NIGHTLY_FORM_RAW --rows 3
    venv\\Scripts\\python.exe tools\\probe_live.py headers NIGHTLY_FORM_RAW

Add --out <path> to any subcommand to also write the report to a UTF-8 file.
Sheet data is full of Spanish accents and `grep` on this machine silently
drops non-ASCII lines, so pipe to --out and read the file rather than
filtering stdout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

try:  # py3.11+ stdlib, falls back to the vendored copy for older interpreters
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

_SECRETS = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"


def _open_sheet() -> gspread.Spreadsheet:
    if not _SECRETS.exists():
        sys.exit(f"secrets.toml not found at {_SECRETS}")
    with _SECRETS.open("rb") as fh:
        secrets = tomllib.load(fh)
    creds_dict = dict(secrets["gcp_service_account"])
    # secrets.toml stores the PEM with real newlines, but tolerate the escaped
    # form too — the Cloud copy of this file has been hand-edited before.
    pk = creds_dict.get("private_key", "")
    creds_dict["private_key"] = pk.replace("\\n", "\n").replace("\r\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    client = gspread.authorize(creds, http_client=gspread.BackOffHTTPClient)
    return client.open(secrets["COMPASS_SHEET_NAME"])


class Report:
    """Collects lines so they can go to stdout and/or a UTF-8 file. Windows
    consoles are cp1252 here; printing Spanish accents straight to stdout
    raises UnicodeEncodeError, so stdout writes go through a replacing
    encoder while --out keeps the real characters."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str = "") -> None:
        self.lines.append(line)
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(line.encode(enc, "replace").decode(enc) + "\n")

    def save(self, path: str | None) -> None:
        if path:
            Path(path).write_text("\n".join(self.lines), encoding="utf-8")
            sys.stdout.write(f"\n[written to {path}]\n")


# ── subcommands ───────────────────────────────────────────────────────────────

def cmd_tabs(sh: gspread.Spreadsheet, out: Report, args) -> None:
    out(f"Spreadsheet: {sh.title}  ({sh.id})")
    out(f"{'TAB':<28} {'ROWS':>6} {'COLS':>6}  {'USED ROWS':>10}")
    out("-" * 56)
    for ws in sh.worksheets():
        # row_count is the allocated grid size, not the populated size — the
        # difference is the whole point of this tool (98 allocated vs 0 used
        # is what "no data yet" actually looks like).
        used = len(ws.get_all_values())
        out(f"{ws.title:<28} {ws.row_count:>6} {ws.col_count:>6}  {used:>10}")


def cmd_config(sh: gspread.Spreadsheet, out: Report, args) -> None:
    rows = sh.worksheet("AGENT_CONFIG").get_all_values()
    out(f"AGENT_CONFIG — {len(rows)} rows (header: {rows[0] if rows else 'NONE'})")
    out("-" * 78)
    for i, r in enumerate(rows[1:], start=2):
        key = (r[0] if len(r) > 0 else "").strip()
        val = (r[1] if len(r) > 1 else "").strip()
        if not key:
            continue
        if args.key and args.key.upper() not in key.upper():
            continue
        out(f"row {i:>3}  {key:<26} = {val!r}")


def cmd_questions(sh: gspread.Spreadsheet, out: Report, args) -> None:
    rows = sh.worksheet("QUESTIONS_CONFIG").get_all_values()
    if not rows:
        out("QUESTIONS_CONFIG is empty.")
        return
    hdr = [c.strip() for c in rows[0]]
    out(f"QUESTIONS_CONFIG header: {hdr}")
    out(f"{len(rows) - 1} data rows")
    out("-" * 100)
    idx = {name: i for i, name in enumerate(hdr)}
    for i, r in enumerate(rows[1:], start=2):
        def col(name: str) -> str:
            j = idx.get(name)
            return (r[j] if j is not None and j < len(r) else "").strip()
        out(f"row {i:>3} | {col('Form_Type'):<8} | {col('Metric_Key'):<26} | "
            f"{col('Active'):<6} | {col('Question_Text')}")


def cmd_org(sh: gspread.Spreadsheet, out: Report, args) -> None:
    rows = sh.worksheet("MISSION_ORG").get_all_values()
    if not rows:
        out("MISSION_ORG is empty.")
        return
    hdr = [c.strip() for c in rows[0]]
    idx = {name: i for i, name in enumerate(hdr)}
    out(f"MISSION_ORG header ({len(hdr)} cols): {hdr}")
    out(f"{len(rows) - 1} data rows")

    def col(r: list, name: str) -> str:
        j = idx.get(name)
        return (r[j] if j is not None and j < len(r) else "").strip()

    def truthy(v: str) -> bool:
        return v.strip().upper() in ("TRUE", "YES", "1")

    leader_flags = [c for c in hdr if c.startswith("Is_")]
    active = sum(1 for r in rows[1:] if truthy(col(r, "Active")))
    out(f"\nActive=TRUE: {active} / {len(rows) - 1}")
    for flag in leader_flags:
        n = sum(1 for r in rows[1:] if truthy(col(r, flag)))
        out(f"  {flag:<10} TRUE on {n} row(s)")

    leaders = [r for r in rows[1:] if any(truthy(col(r, f)) for f in leader_flags)]
    out(f"\nRows with ANY leader flag: {len(leaders)}")
    if args.verbose:
        out("-" * 100)
        for i, r in enumerate(rows[1:], start=2):
            flags = ",".join(f for f in leader_flags if truthy(col(r, f))) or "-"
            out(f"row {i:>3} | {col(r, 'Zone'):<18} | {col(r, 'District'):<18} | "
                f"{col(r, 'Area'):<22} | Active={col(r, 'Active'):<6} | {flags}")


def cmd_health(sh: gspread.Spreadsheet, out: Report, args) -> None:
    for tab in ("AGENT_RUN_LOG", "HEALTH_LOG", "MISSING_LOG", "AUDIT_LOG"):
        try:
            rows = sh.worksheet(tab).get_all_values()
        except gspread.exceptions.WorksheetNotFound:
            out(f"\n=== {tab} — TAB DOES NOT EXIST ===")
            continue
        out(f"\n=== {tab} — {max(0, len(rows) - 1)} data rows ===")
        if not rows:
            continue
        out(f"header: {rows[0]}")
        for r in rows[-args.rows:][1:] if len(rows) <= args.rows else rows[-args.rows:]:
            out("  " + " | ".join(str(c) for c in r))


def cmd_dump(sh: gspread.Spreadsheet, out: Report, args) -> None:
    rows = sh.worksheet(args.tab).get_all_values()
    out(f"{args.tab} — {len(rows)} rows total")
    for i, r in enumerate(rows[: args.rows + 1], start=1):
        out(f"\n--- row {i} ---")
        for j, c in enumerate(r):
            if c.strip() or args.verbose:
                out(f"  col {j + 1:>3}: {c}")


def cmd_headers(sh: gspread.Spreadsheet, out: Report, args) -> None:
    """Header row only, one column per line. Built for the *_FORM_RAW tabs,
    whose header repeats the whole question block once per Google Form section
    (one section per zone) — the repetition is only visible column by column."""
    rows = sh.worksheet(args.tab).get_all_values()
    if not rows:
        out(f"{args.tab} is empty.")
        return
    hdr = rows[0]
    out(f"{args.tab} header — {len(hdr)} columns, {len(rows) - 1} data rows")
    out("-" * 90)
    seen: dict[str, list[int]] = {}
    for j, c in enumerate(hdr, start=1):
        out(f"  col {j:>3}: {c}")
        seen.setdefault(c.strip(), []).append(j)
    dupes = {k: v for k, v in seen.items() if len(v) > 1 and k}
    out("\n" + "-" * 90)
    out(f"{len(dupes)} header label(s) appear more than once:")
    for label, cols in dupes.items():
        out(f"  x{len(cols):<3} cols {cols} : {label}")


def cmd_json(sh: gspread.Spreadsheet, out: Report, args) -> None:
    """Dump whole tabs as raw JSON grids, for test fixtures that must be built
    from what the sheet ACTUALLY holds rather than from the same CcsmData.gs
    the code under test reads. The node suite's fixtures.js generates the
    *_FORM_RAW headers from CcsmData.gs, so it can only ever prove the agents
    are self-consistent with that file — never that they match the live Google
    Form. This is the other side of that comparison."""
    import json

    payload = {}
    for tab in args.tabs:
        try:
            payload[tab] = sh.worksheet(tab).get_all_values()
        except gspread.exceptions.WorksheetNotFound:
            payload[tab] = None
            out(f"WARNING: tab {tab} does not exist")
    dest = Path(args.dest)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    for tab, grid in payload.items():
        n = "MISSING" if grid is None else f"{len(grid)} rows x " \
                                           f"{max((len(r) for r in grid), default=0)} cols"
        out(f"  {tab:<24} {n}")
    out(f"\n[wrote {dest}]")


def main() -> None:
    # --out lives on a shared parent so it works AFTER the subcommand too
    # (`probe_live.py tabs --out x.txt`), which is the order it gets typed in.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", help="also write the report to this UTF-8 file")

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tabs", parents=[common],
                   help="every tab with allocated vs used row counts")

    p = sub.add_parser("config", parents=[common], help="AGENT_CONFIG key/value dump")
    p.add_argument("--key", help="substring filter on the key name")

    sub.add_parser("questions", parents=[common],
                   help="QUESTIONS_CONFIG metric catalogue")

    p = sub.add_parser("org", parents=[common],
                       help="MISSION_ORG Active/leader-flag summary")
    p.add_argument("-v", "--verbose", action="store_true", help="one line per row")

    p = sub.add_parser("health", parents=[common], help="tail of the agent log tabs")
    p.add_argument("--rows", type=int, default=15)

    p = sub.add_parser("dump", parents=[common],
                       help="first N rows of a tab, column by column")
    p.add_argument("tab")
    p.add_argument("--rows", type=int, default=3)
    p.add_argument("-v", "--verbose", action="store_true", help="include blank cells")

    p = sub.add_parser("headers", parents=[common],
                       help="header row of a tab + duplicate-label report")
    p.add_argument("tab")

    p = sub.add_parser("json", parents=[common],
                       help="dump whole tabs to a JSON file (test fixtures)")
    p.add_argument("dest", help="output .json path")
    p.add_argument("tabs", nargs="+", help="tab names to dump")

    args = ap.parse_args()
    out = Report()
    sh = _open_sheet()
    {
        "tabs": cmd_tabs, "config": cmd_config, "questions": cmd_questions,
        "org": cmd_org, "health": cmd_health, "dump": cmd_dump,
        "headers": cmd_headers, "json": cmd_json,
    }[args.cmd](sh, out, args)
    out.save(args.out)


if __name__ == "__main__":
    main()
