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

Two things here are CCSM-specific and were rewritten on 2026-09-08, after a
live probe found both broken on this mission's real data (see
PLAN-2026-09-08-transfer-day.md §1):

  * `_advance_schedule` / `_set_transfer_start_date` describe the CYCLE, not
    the day Apply was clicked. Each function's docstring carries what it used
    to do and what that cost.
  * The roster is filtered to `AGENT_CONFIG.PILOT_ZONES` before anything is
    compared or written, because CCSM runs a four-zone pilot against an
    eleven-zone IMOS roster. See `pilot_zones()` and
    `transfer_engine.filter_roster_to_zones`.
"""

from __future__ import annotations

from datetime import date, datetime

from app.db import queries as q
from app.db import sheets_client as sc
from app.ingestion import transfer_engine as te
from app.utils import transfer_helpers as th
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


def pilot_zones() -> list[str]:
    """The zones this mission actually runs PMG Compass in, from AGENT_CONFIG's
    `PILOT_ZONES` (comma-separated). Empty or missing means the whole mission.

    CCSM has been a four-zone pilot since 2026-08-19 while the IMOS roster
    covers all eleven — see `transfer_engine.filter_roster_to_zones` for why an
    unfiltered apply reactivates the entire mission.
    """
    raw = (q.get_config_value("PILOT_ZONES", "") or "").strip()
    return [z.strip() for z in raw.split(",") if z.strip()]


def load_state() -> tuple[list[str], list[dict], list[dict], list[str]]:
    """(MISSION_ORG headers, MISSION_ORG rows, roster rows, unknown pilot zones).

    The roster is already cut to `pilot_zones()`; `unknown` names any configured
    zone that matched no roster row, which the callers treat as a hard stop.
    """
    org_headers, org = read_records(MISSION_ORG_TAB)
    _, imp = read_records(IMPORT_TAB)
    roster = te.parse_roster(imp)
    roster, unknown = te.filter_roster_to_zones(roster, pilot_zones())
    return org_headers, org, roster, unknown


# ── preview ─────────────────────────────────────────────────────────────────────

def preview() -> dict:
    org_headers, org, roster, unknown = load_state()
    guard = te.run_guards(roster, org)
    diff = te.build_diff(roster, org)
    return {
        "guard": guard,
        "diff": diff,
        "roster_count": len(roster),
        "org_count": len(org),
        "pilot_zones": pilot_zones(),
        "unknown_zones": unknown,
    }


# ── apply ───────────────────────────────────────────────────────────────────────

def apply(override: bool = False, today: date | None = None) -> dict:
    """Snapshot -> merge MISSION_ORG -> advance schedule/config -> log. Returns
    the apply summary (new_emails_needed, deactivated_with_email). Raises
    TransferBlocked if the deactivation guard trips and override is False."""
    today = today or date.today()
    org_headers, org, roster, unknown = load_state()

    # A pilot zone that matched no roster row is a spelling drift, not an empty
    # zone — and proceeding would DEACTIVATE every area in it (they are active in
    # MISSION_ORG and absent from the filtered roster). Refuse rather than let
    # the 30% guard be the only thing standing in the way.
    if unknown:
        raise TransferBlocked(
            "AGENT_CONFIG PILOT_ZONES names zone(s) that appear nowhere in "
            f"TRANSFER_IMPORT: {', '.join(unknown)}. Fix the spelling to match "
            "the roster's own Zone column before applying — applying now would "
            "deactivate every area in them."
        )

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
    q.get_mission_transfer_expectation_total.clear()

    # Both of these describe the CYCLE, not the day someone happened to click
    # Apply. transfer_window() is the app's one answer to "which transfer is
    # this" (app/utils/transfer_helpers.py) — reading it here rather than
    # re-deriving keeps the schedule, AGENT_CONFIG and every page in agreement.
    cycle_start = _current_cycle_start(today)
    schedule_updated = _advance_schedule(cycle_start)
    config_updated = _set_transfer_start_date(cycle_start)

    _log(summary, schedule_updated, config_updated)

    summary["schedule_updated"] = schedule_updated
    summary["config_updated"] = config_updated
    return summary


def _current_cycle_start(today: date) -> date:
    """The start date of the transfer cycle `today` falls in.

    Delegates to `transfer_helpers.transfer_window`, which is the single answer
    to "which transfer is this" for every page in the app. Falls back to `today`
    only when the schedule is empty AND AGENT_CONFIG has no usable
    TRANSFER_START_DATE — at which point there is nothing better to say.
    """
    from app.utils.transfer_helpers import transfer_window

    win = transfer_window(0, today)
    return win["start"] if win else today


def _advance_schedule(cycle_start: date) -> bool:
    """Mark the TRANSFER_SCHEDULE row for `cycle_start` as Actual.

    Only the Status cell is written. The Start_Date already on the row is the
    mission's real, pre-scheduled Monday and is what `transfer_window()` — and
    therefore every period-scoped page — keys on; overwriting it with the day
    someone clicked Apply would move the cycle.

    Two bugs this replaces, both confirmed against the live tab on 2026-09-08:

    1. It looked for `Status == "Planned"`. CCSM writes **"Scheduled"**, so no
       row ever matched and every apply fell through to the append branch.
    2. The append branch picked its number with `.isdigit()`. CCSM's
       Transfer_Number values read "2026-4" … "2026-8" (and are in fact
       date-typed cells displayed by a `yyyy-m` format), so nothing was a bare
       digit, `nums` came out empty, and the new number became `0 + 1`.

    Together they meant Apply would have APPENDED `['1', '<today>', '', 'Actual']`
    to a five-row tab reading 2026-4 … 2026-8 — a cycle numbered 1, dated today
    rather than the Monday, with a blank Weeks. `transfer_rows()` takes the
    latest row whose start has arrived, so that row would immediately have become
    "the current transfer" for Desgloses, the Panel rankings, Puntajes and Metas'
    cycle picker.

    Appending is now the exception rather than the rule: it happens only when no
    scheduled row covers this cycle at all, and the label comes from
    `transfer_engine.next_transfer_number()`, which already knows how to
    increment "2026-8" into "2026-9" (PLAN-2026-09-05-backlog §7.4).

    Returns True when a cell was written.
    """
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

    rows = [list(r) + [""] * (len(headers) - len(r)) for r in grid[1:]]

    for offset, row in enumerate(rows):
        try:
            row_start = date.fromisoformat(str(row[start_i]).strip()[:10])
        except ValueError:
            continue
        if row_start != cycle_start:
            continue
        if str(row[status_i]).strip() == "Actual":
            return False          # already recorded — nothing to write
        sc.update_cell(SCHEDULE_TAB, _a1(offset + 2, status_i + 1), "Actual")
        return True

    # No scheduled row covers this cycle. Append one rather than leave the
    # mission with no record of the transfer that just happened.
    dicts = [{h: row[i] for i, h in enumerate(headers)} for row in rows]
    new_row = [""] * len(headers)
    new_row[num_i] = te.next_transfer_number(dicts)
    new_row[start_i] = cycle_start.strftime("%Y-%m-%d")
    new_row[status_i] = "Actual"
    if "Weeks" in headers:
        new_row[headers.index("Weeks")] = str(th.DEFAULT_WEEKS)
    sc.append_row(SCHEDULE_TAB, new_row)
    return True


def _set_transfer_start_date(cycle_start: date) -> bool:
    """Point AGENT_CONFIG's TRANSFER_START_DATE at `cycle_start`.

    This used to write `today`. Transfers are applied the day after the cycle
    begins about as often as on the day itself — 2026-6 started Monday
    2026-09-07 and was being applied on Tuesday the 8th — and the day of the
    click is not the start of anything. Writing it cost two things: Monday's
    DAILY_LOG rows fell outside the window, so every LIVE_SNAPSHOT
    `<metric>_transfer` total silently lost day one; and the value then
    disagreed with TRANSFER_SCHEDULE, which is exactly the mismatch
    views/12_Traslados.py warns about on screen.

    CCSM's AGENT_CONFIG is a plain Key/Value tab (no Config_Key/Config_Value/
    Last_Updated like Provo's) — this updates the Value cell of the
    TRANSFER_START_DATE row and nothing else.
    """
    grid = sc.read_values(CONFIG_TAB)
    if not grid:
        return False
    headers = [str(h).strip() for h in grid[0]]
    try:
        key_i = headers.index("Key")
        val_i = headers.index("Value")
    except ValueError:
        return False
    start_str = cycle_start.strftime("%Y-%m-%d")
    for r in range(1, len(grid)):
        if str(grid[r][key_i]).strip() == "TRANSFER_START_DATE":
            sc.update_cell(CONFIG_TAB, _a1(r + 1, val_i + 1), start_str)
            return True
    return False


def _log(summary: dict, schedule_updated: bool, config_updated: bool) -> None:
    parts = ["Applied via CCSM dashboard (Traslados)."]
    zones = pilot_zones()
    parts.append("PILOT_ZONES=" + (", ".join(zones) if zones else "(none — whole mission)"))
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
