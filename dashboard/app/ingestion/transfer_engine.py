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


def filter_roster_to_zones(roster_rows: list[dict],
                           zones) -> tuple[list[dict], list[str]]:
    """`roster_rows` cut to `zones`, plus any configured zone that matched nothing.

    CCSM does not run PMG Compass mission-wide. Since 2026-08-19 it has been a
    pilot in four zones — Angol, Los Angeles Norte, San Pedro, Temuco Nielol —
    while the other six stay `Active=FALSE` in MISSION_ORG. The IMOS roster is
    always the WHOLE mission (97 areas, 11 zones on the 2026-08-09 pull), and
    `apply_transfer` sets `Active="TRUE"` for every area it finds in the roster,
    so applying an unfiltered pull silently reactivates the entire mission and
    the next form sync puts all eleven zones back in the dropdowns.

    Filtering here rather than by hand-deleting rows from TRANSFER_IMPORT means
    a new area OPENED in a pilot zone this transfer still arrives — which is the
    whole point, and the thing hand-trimming a 97-row tab every six weeks gets
    wrong.

    An empty/missing `zones` returns the roster unchanged: no configuration means
    the whole mission, so this is inert for a mission that never pilots.

    The second return value is the configured zones that matched NO roster row.
    That is almost always a spelling drift rather than a zone with no areas —
    "Los Angeles Norte" against the export's "Los Ángeles Norte" would quietly
    drop eleven real areas, and since they are active in MISSION_ORG and absent
    from the filtered roster, `apply_transfer` would DEACTIVATE all eleven. The
    caller is expected to refuse rather than proceed on a non-empty list.
    """
    wanted = {str(z).strip().casefold() for z in (zones or []) if str(z).strip()}
    if not wanted:
        return list(roster_rows), []
    kept = [r for r in roster_rows
            if str(r.get("Zone", "")).strip().casefold() in wanted]
    seen = {str(r.get("Zone", "")).strip().casefold() for r in roster_rows}
    unknown = sorted(z for z in (zones or [])
                     if str(z).strip() and str(z).strip().casefold() not in seen)
    return kept, unknown


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

#: A Transfer_Number's trailing integer, and whatever prefix precedes it.
#: "2026-4" -> ("2026-", "4"); "5" -> ("", "5"); "Cambio 12" -> ("Cambio ", "12").
_TRANSFER_NUMBER_TAIL = re.compile(r"^(.*?)(\d+)\s*$")


def next_transfer_number(schedule_rows: list[dict]) -> str:
    """The label to give a cycle appended after `schedule_rows`.

    Transfer_Number has no enforced format. CCSM writes "2026-4", "2026-5", …,
    so the `int()` this replaces threw on every live row; the exception was
    caught and `max_num` stayed 0, which would have appended a cycle numbered
    "1" to a tab whose other rows read 2026-4 through 2026-8.

    The trailing integer is incremented and its prefix kept, so "2026-8" becomes
    "2026-9" and a mission numbering plainly from "5" still gets "6". The LAST
    row carrying digits sets the pattern — the rows arrive in sheet order, which
    is the order the cycles run. A tab with no usable number at all falls back
    to "1".

    This deliberately does NOT know that a mission may renumber at the calendar
    year: 2026-8 ends 2027-01-10, and whether its successor is "2026-9" or
    "2027-1" is the mission's convention, not a fact the sheet records. Raised
    with Zackary 2026-09-05, unanswered — and cosmetic either way, because every
    keyed lookup in this app uses Start_Date, never the number (PLAN §7.2).
    """
    prefix, last = "", 0
    for r in schedule_rows:
        m = _TRANSFER_NUMBER_TAIL.match(str(r.get("Transfer_Number", "")).strip())
        if m:
            prefix, last = m.group(1), int(m.group(2))
    return f"{prefix}{last + 1}"


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

    rows.append({
        "Transfer_Number": next_transfer_number(schedule_rows),
        "Start_Date": today_str,
        "Weeks": "",
        "Status": "Actual",
    })
    return rows
