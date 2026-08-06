"""
transfer_apply_service.py — Streamlit-side orchestration for CCSM's Transfer
Flow: reads MISSION_ORG / TRANSFER_IMPORT / TRANSFER_SCHEDULE / AGENT_CONFIG
from COMPASS_CCSM, runs the pure transfer_engine, and writes the results back.

Ported from Utah Provo's app/ingestion/transfer_apply_service.py. All Google
Sheets I/O goes through app.db.sheets_client (gspread service account). The
pure logic lives in transfer_engine; this module only wires it to the live
sheet, so it is exercised in the app rather than unit-tested.

CCSM's AGENT_CONFIG has only two columns (Key, Value) — no Config_Key/
Config_Value/Last_Updated like Provo's. _set_transfer_start_date reads
Key/Value and does not touch a Last_Updated column, since none exists.
"""

from __future__ import annotations

from datetime import date, datetime

from app.db import queries as q
from app.db import sheets_client as sc
from app.ingestion import transfer_engine as te
from app.utils.logger import get_logger

_logger = get_logger("ingestion.transfer_apply_service")

MISSION_ORG_TAB = "MISSION_ORG"
SNAPSHOT_TAB = "MISSION_ORG_SNAPSHOT"
IMPORT_TAB = "TRANSFER_IMPORT"
SCHEDULE_TAB = "TRANSFER_SCHEDULE"
CONFIG_TAB = "AGENT_CONFIG"
LOG_TAB = "TRANSFER_LOG"


class TransferBlocked(RuntimeError):
    """Raised when the deactivation guard blocks an apply."""


# ── grid helpers ────────────────────────────────────────────────────────────────

def _a1_col(col_1based: int) -> str:
    letters = ""
    while col_1based > 0:
        col_1based, rem = divmod(col_1based - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _a1(row_1based: int, col_1based: int) -> str:
    return f"{_a1_col(col_1based)}{row_1based}"


def read_records(tab: str) -> tuple[list[str], list[dict]]:
    """Return (headers, [row-dict, ...]) using the tab's own header row, padding
    short rows so every record has every column."""
    grid = sc.read_values(tab)
    if not grid:
        return [], []
    headers = [str(h).strip() for h in grid[0]]
    records = []
    for row in grid[1:]:
        padded = list(row) + [""] * (len(headers) - len(row))
        records.append({h: padded[i] for i, h in enumerate(headers)})
    return headers, records


def load_state() -> tuple[list[str], list[dict], list[dict]]:
    org_headers, org = read_records(MISSION_ORG_TAB)
    _, imp = read_records(IMPORT_TAB)
    roster = te.parse_roster(imp)
    return org_headers, org, roster


# ── preview ─────────────────────────────────────────────────────────────────────

def preview() -> dict:
    org_headers, org, roster = load_state()
    guard = te.run_guards(roster, org)
    diff = te.build_diff(roster, org)
    return {
        "guard": guard,
        "diff": diff,
        "roster_count": len(roster),
        "org_count": len(org),
    }


# ── apply ───────────────────────────────────────────────────────────────────────

def apply(override: bool = False, today: date | None = None) -> dict:
    """Snapshot -> merge MISSION_ORG -> advance schedule/config -> log. Returns
    the apply summary (new_emails_needed, deactivated_with_email). Raises
    TransferBlocked if the deactivation guard trips and override is False."""
    today = today or date.today()
    org_headers, org, roster = load_state()

    guard = te.run_guards(roster, org, override=override)
    if not guard["ok"]:
        raise TransferBlocked(guard["msg"])

    # Snapshot the current grid BEFORE any mutation.
    current_grid = sc.read_values(MISSION_ORG_TAB)
    if current_grid:
        sc.overwrite_tab(SNAPSHOT_TAB, current_grid)

    new_rows, summary = te.apply_transfer(roster, org, org_headers)
    sc.overwrite_tab(MISSION_ORG_TAB, te.rows_to_grid(new_rows, org_headers))
    # Cached per-area lookups must not serve stale data for up to 5 min after
    # a roster apply changes the area list/zone/district — same ttl=300 fix
    # Provo applied for its Mission Goals fraction totals.
    q.get_area_language_group.clear()
    q._resolve_area_category.clear()
    q.get_mission_weekly_expectation_total.clear()
    q.get_mission_monthly_expectation_total.clear()

    schedule_updated = _advance_schedule(today)
    config_updated = _set_transfer_start_date(today)

    _log(summary, schedule_updated, config_updated)

    summary["schedule_updated"] = schedule_updated
    summary["config_updated"] = config_updated
    return summary


def _advance_schedule(today: date) -> bool:
    """Flip the first still-'Planned' TRANSFER_SCHEDULE row to Actual with
    today's date, editing only its Start_Date + Status cells so the derived
    Weeks formula survives; append a new Actual row if none is Planned."""
    grid = sc.read_values(SCHEDULE_TAB)
    if not grid or len(grid) < 2:
        return False
    headers = [str(h).strip() for h in grid[0]]
    try:
        num_i = headers.index("Transfer_Number")
        start_i = headers.index("Start_Date")
        status_i = headers.index("Status")
    except ValueError:
        return False

    today_str = today.strftime("%Y-%m-%d")
    for r in range(1, len(grid)):
        row = list(grid[r]) + [""] * (len(headers) - len(grid[r]))
        if str(row[status_i]).strip() == "Planned":
            sc.update_cell(SCHEDULE_TAB, _a1(r + 1, start_i + 1), today_str)
            sc.update_cell(SCHEDULE_TAB, _a1(r + 1, status_i + 1), "Actual")
            return True

    nums = [int(str(grid[j][num_i]).strip()) for j in range(1, len(grid))
            if str(grid[j][num_i]).strip().isdigit()]
    new_row = [""] * len(headers)
    new_row[num_i] = str((max(nums) if nums else 0) + 1)
    new_row[start_i] = today_str
    new_row[status_i] = "Actual"
    sc.append_row(SCHEDULE_TAB, new_row)
    return True


def _set_transfer_start_date(today: date) -> bool:
    """CCSM's AGENT_CONFIG is a plain Key/Value tab (no Config_Key/Config_Value/
    Last_Updated like Provo's) — updates the Value cell of the TRANSFER_START_DATE
    row and nothing else."""
    grid = sc.read_values(CONFIG_TAB)
    if not grid:
        return False
    headers = [str(h).strip() for h in grid[0]]
    try:
        key_i = headers.index("Key")
        val_i = headers.index("Value")
    except ValueError:
        return False
    today_str = today.strftime("%Y-%m-%d")
    for r in range(1, len(grid)):
        if str(grid[r][key_i]).strip() == "TRANSFER_START_DATE":
            sc.update_cell(CONFIG_TAB, _a1(r + 1, val_i + 1), today_str)
            return True
    return False


def _log(summary: dict, schedule_updated: bool, config_updated: bool) -> None:
    parts = ["Applied via CCSM dashboard (Traslados)."]
    if summary.get("new_emails_needed"):
        parts.append("NEW areas need email: " + ", ".join(summary["new_emails_needed"]))
    if summary.get("deactivated_with_email"):
        parts.append("Deactivated w/ email: " + ", ".join(summary["deactivated_with_email"]))
    parts.append(f"schedule_updated={schedule_updated} config_updated={config_updated}")
    try:
        sc.append_row(LOG_TAB, [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "applyTransfer (CCSM dashboard)", "OK", " | ".join(parts),
        ])
    except Exception as e:   # logging must never fail the apply
        _logger.warning("Could not append TRANSFER_LOG row: %s", e)
