"""
transfer_engine.py — pure roster-merge logic for CCSM's Transfer Flow.

Ported from Utah Provo's app/ingestion/transfer_engine.py (docs/AgentTransfer.gs's
sheet-side logic). Drive-only helpers (build_rezone_diff, suggest_area_renames)
were dropped — CCSM's Transfer Flow has no Drive integration.

Everything here is pure (in-memory lists/dicts, no I/O) so it is unit-testable
and callable from the Streamlit page via app.db.sheets_client. The FORM sync
half runs in Apps Script — see CCSM_TransferWebApp.gs.

MISSION_ORG rows and roster rows are dicts keyed by column name. MISSION_ORG
uses `Area_Name`; a raw TRANSFER_IMPORT row uses `Area` (+ `Calling`), which
parse_roster() normalizes into the MISSION_ORG shape. CCSM's live MISSION_ORG
has no Language_Type, Area_ID, Companion3_Name, or Companion4_Name — every
function below reads via .get(col, default), so those columns being absent is
harmless (diffs against them always come out equal, new-area code that would
set them just adds keys nothing reads).
"""

from __future__ import annotations

import datetime as dt
import re

# Same substring-match rules as AT_CALLING_FLAGS in docs/AgentTransfer.gs.
CALLING_FLAGS = {
    "Is_ZL": ["zl", "zone leader"],
    "Is_STL": ["stl", "sister training leader"],
    "Is_DL": ["dl", "district leader"],
    "Is_AP": ["ap", "assistant to the president"],
    "Is_MP": ["mp", "mission president"],
}

# Columns copied straight through from the roster onto a matched area row.
_ROSTER_COPY_COLS = [
    "Zone", "District",
    "Companion1_Name", "Companion2_Name", "Companion3_Name", "Companion4_Name",
]

_COMPANION_COLS = [
    "Companion1_Name", "Companion2_Name", "Companion3_Name", "Companion4_Name",
]

# at_isLeadershipRow_ — keyed off Area_Name, NOT the Is_* flags (a real area
# can carry a leadership flag when its companion holds a calling).
_LEADERSHIP_NAME_RE = re.compile(
    r"^(Mission President|Assistant to President|Zone Leader|"
    r"Sister Training Leader -|District Leader -)",
    re.IGNORECASE,
)
# at_isSeniorRow_ — senior-missionary-couple tracking rows.
_SENIOR_RE = re.compile(r"\bSenior\b", re.IGNORECASE)

DEACTIVATION_GUARD_PCT = 0.30


# ── helpers ─────────────────────────────────────────────────────────────────────

def calling_to_flags(calling: str) -> dict:
    c = (calling or "").strip().lower()
    return {flag: ("TRUE" if any(s in c for s in subs) else "FALSE")
            for flag, subs in CALLING_FLAGS.items()}


def is_leadership_row(row: dict) -> bool:
    return bool(_LEADERSHIP_NAME_RE.match((row.get("Area_Name") or "").strip()))


def is_senior_row(row: dict) -> bool:
    return bool(_SENIOR_RE.search((row.get("Area_Name") or "").strip()))


def is_non_teaching_row(row: dict) -> bool:
    """Leadership + senior tracking rows — never created, updated, reactivated,
    deactivated, or counted toward the deactivation guard."""
    return is_leadership_row(row) or is_senior_row(row)


def _is_true(val) -> bool:
    return str(val or "").strip().upper() == "TRUE"


# ── parse_roster ────────────────────────────────────────────────────────────────

def parse_roster(import_rows: list[dict]) -> list[dict]:
    """TRANSFER_IMPORT rows (keys: Area, Zone, District, Companion1-4_Name,
    Calling, Area_Email) -> roster objects in MISSION_ORG shape (Area_Name,
    Zone, District, Companion1-4_Name, Is_* flags, Active=TRUE)."""
    out = []
    for raw in import_rows:
        area = str(raw.get("Area", "") or "").strip()
        if not area:
            continue   # skip blank rows, like at_parseRoster_
        obj = {
            "Area_Name": area,
            "Zone": str(raw.get("Zone", "") or "").strip(),
            "District": str(raw.get("District", "") or "").strip(),
            "Active": "TRUE",
            "Area_Email": str(raw.get("Area_Email", "") or "").strip(),
        }
        for col in _COMPANION_COLS:
            obj[col] = str(raw.get(col, "") or "").strip()
        obj.update(calling_to_flags(raw.get("Calling", "")))
        out.append(obj)
    return out


def _roster_map(roster_rows: list[dict]) -> dict:
    return {r["Area_Name"].lower().strip(): r for r in roster_rows}


# ── guards ──────────────────────────────────────────────────────────────────────

def run_guards(roster_rows: list[dict], mission_org: list[dict],
               override: bool = False) -> dict:
    """Mirror at_runGuards_: block an empty roster, and (unless override) block
    when more than 30% of active teaching areas would deactivate."""
    if not roster_rows:
        return {"ok": False, "msg": "Roster is empty."}

    if override:
        return {"ok": True, "msg": ""}

    active_rows = [r for r in mission_org
                   if _is_true(r.get("Active")) and not is_non_teaching_row(r)]
    active_count = len(active_rows)
    keys = set(_roster_map(roster_rows))
    deactivate_count = sum(
        1 for r in active_rows if (r.get("Area_Name") or "").lower().strip() not in keys
    )

    if active_count > 0 and deactivate_count / active_count > DEACTIVATION_GUARD_PCT:
        pct = round(deactivate_count / active_count * 100)
        return {
            "ok": False,
            "msg": (f"{deactivate_count} of {active_count} active areas would be "
                    f"deactivated ({pct}%). If correct, re-run with override "
                    f"enabled."),
        }
    return {"ok": True, "msg": ""}


# ── build_diff (preview) ────────────────────────────────────────────────────────

def build_diff(roster_rows: list[dict], mission_org: list[dict]) -> dict:
    """Preview summary: added / deactivated / changed / reactivated."""
    rmap = _roster_map(roster_rows)
    org_keys = {(r.get("Area_Name") or "").lower().strip() for r in mission_org}

    added, deactivated, changed, reactivated = [], [], [], []

    for existing in mission_org:
        if is_non_teaching_row(existing):
            continue
        key = (existing.get("Area_Name") or "").lower().strip()
        if not key:
            continue

        if _is_true(existing.get("Active")):
            r = rmap.get(key)
            if not r:
                deactivated.append(existing["Area_Name"])
                continue
            diffs = []
            for col in ["Zone", "District"] + _COMPANION_COLS:
                old, new = existing.get(col, "") or "", r.get(col, "") or ""
                if old != new:
                    diffs.append(f'{col}: "{old}" → "{new}"')
            for flag in CALLING_FLAGS:
                old = str(existing.get(flag, "FALSE") or "FALSE").upper()
                new = str(r.get(flag, "FALSE") or "FALSE").upper()
                if old != new:
                    diffs.append(f"{flag}: {old} → {new}")
            if diffs:
                changed.append(existing["Area_Name"] + ": " + "; ".join(diffs))
        else:
            r = rmap.get(key)
            if r:
                comp = r.get("Companion1_Name") or "(no comp1)"
                if r.get("Companion2_Name"):
                    comp += " & " + r["Companion2_Name"]
                reactivated.append(f"{existing['Area_Name']}: was inactive → "
                                   f"reactivating with {comp}")

    for r in roster_rows:
        if r["Area_Name"].lower().strip() not in org_keys:
            added.append(r["Area_Name"] + " (NEW — needs email address after apply)")

    return {"added": added, "deactivated": deactivated,
            "changed": changed, "reactivated": reactivated}


# ── apply ───────────────────────────────────────────────────────────────────────

def apply_transfer(roster_rows: list[dict], mission_org: list[dict],
                   headers: list[str]) -> tuple[list[dict], dict]:
    """Mirror applyTransfer()'s MISSION_ORG merge. Returns (new_rows, summary).

    - Existing area in roster: Zone/District/Companions/flags updated, Active
      TRUE, **email columns preserved**.
    - Existing area NOT in roster (and active): deactivated — Active FALSE,
      companions + Is_* flags cleared, email preserved (kept for history).
    - Roster area not in MISSION_ORG: appended, email columns blank.
    - Leadership + senior rows: never touched.

    `new_rows` preserves MISSION_ORG's own column order via `headers`; new
    areas are grouped in with the other area rows (before the first leadership
    row) purely for readability.
    """
    rmap = _roster_map(roster_rows)
    output: list[dict] = []
    processed: set[str] = set()
    first_leadership_idx = None

    new_emails_needed: list[str] = []
    deactivated_with_email: list[str] = []

    for existing in mission_org:
        row = {h: existing.get(h, "") for h in headers}
        name = (row.get("Area_Name") or "").strip()
        key = name.lower()

        if is_non_teaching_row(row):
            if is_leadership_row(row) and first_leadership_idx is None:
                first_leadership_idx = len(output)
            processed.add(key)
            output.append(row)
            continue

        if not name:
            output.append(row)
            continue

        r = rmap.get(key)
        if r:
            for col in _ROSTER_COPY_COLS:
                row[col] = r.get(col, "")
            for flag in CALLING_FLAGS:
                row[flag] = r.get(flag, "FALSE")
            row["Active"] = "TRUE"
            processed.add(key)
        else:
            if _is_true(row.get("Active")):
                email = str(row.get("Companion1_Email", "") or "").strip()
                if email:
                    deactivated_with_email.append(f"{name} ({email})")
                row["Active"] = "FALSE"
                for col in _COMPANION_COLS:
                    row[col] = ""
                for flag in CALLING_FLAGS:
                    row[flag] = "FALSE"

        output.append(row)

    new_rows = []
    for key, r in rmap.items():
        if key in processed:
            continue
        nr = {h: "" for h in headers}
        nr["Area_Name"] = r["Area_Name"]
        for col in _ROSTER_COPY_COLS:
            nr[col] = r.get(col, "")
        for flag in CALLING_FLAGS:
            nr[flag] = r.get(flag, "FALSE")
        nr["Active"] = "TRUE"
        new_rows.append(nr)
        new_emails_needed.append(r["Area_Name"])

    insert_at = len(output) if first_leadership_idx is None else first_leadership_idx
    output[insert_at:insert_at] = new_rows

    summary = {
        "new_emails_needed": new_emails_needed,
        "deactivated_with_email": deactivated_with_email,
    }
    return output, summary


def rows_to_grid(rows: list[dict], headers: list[str]) -> list[list]:
    """Serialize row-dicts back to a 2D grid (header + rows) for overwrite_tab."""
    return [headers] + [[r.get(h, "") for h in headers] for r in rows]


# ── transfer schedule ───────────────────────────────────────────────────────────

def next_schedule_update(schedule_rows: list[dict], today: dt.date) -> list[dict]:
    """Mirror at_updateTransferSchedule_: flip the earliest still-'Planned' row
    to Actual with today's date; if none is Planned, append a new Actual row.
    Rows are dicts keyed Transfer_Number/Start_Date/Weeks/Status."""
    rows = [dict(r) for r in schedule_rows]
    today_str = today.strftime("%Y-%m-%d")

    for r in rows:
        if str(r.get("Status", "")).strip() == "Planned":
            r["Start_Date"] = today_str
            r["Status"] = "Actual"
            return rows

    max_num = 0
    for r in rows:
        try:
            n = int(str(r.get("Transfer_Number", "")).strip())
            max_num = max(max_num, n)
        except (ValueError, TypeError):
            pass
    rows.append({
        "Transfer_Number": str(max_num + 1),
        "Start_Date": today_str,
        "Weeks": "",
        "Status": "Actual",
    })
    return rows
