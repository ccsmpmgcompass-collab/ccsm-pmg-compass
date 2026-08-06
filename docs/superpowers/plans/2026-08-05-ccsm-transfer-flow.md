# CCSM Transfer Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give CCSM's dashboard a working Transfer Flow — pull the roster from the IMOS portal via Playwright, preview the diff against `MISSION_ORG`, apply it, sync the nightly/weekly form area dropdowns — running from CCSM's own GitHub Actions cloud workflow, with no dependency on Provo's infrastructure and no dependency on any specific laptop being on.

**Architecture:** Literal ports of Provo's `PMG-Compass` modules into CCSM's own repo (`Worldwide PMG Compass\CCSM PMG Compass\`), re-targeted at `COMPASS_CCSM` and CCSM's own credentials. No Drive automation. The existing read-only `pages/12_Traslados.py` gets extended in place with write/pull sections rather than replaced by a new page.

**Tech Stack:** Python 3.14 / Streamlit 1.40.0 / gspread / Playwright 1.49.0 (`mcr.microsoft.com/playwright/python:v1.49.0-jammy` container) / Google Apps Script / GitHub Actions.

## Global Constraints

- No Drive folder automation (move/rename/create/archive) — explicitly out of scope.
- No shared runtime or code path with Provo's `PMG-Compass` repo — every file below is a new file in CCSM's own repo, even when the content is a verbatim or near-verbatim copy.
- Real credential values are never typed, pasted, or echoed by the assistant into chat, committed files, or artifacts. The user pastes every secret themselves.
- Every write against live `MISSION_ORG` requires the user's explicit go-ahead at the moment it runs — never automated in a test, never run unattended the first time.
- CCSM sheet writes go through the existing `app/db/sheets_client.py` helpers (`read_values`, `overwrite_tab`, `update_cell`, `append_row`) — confirmed present with these exact signatures; no lower-level Sheets-API plumbing gets re-ported.
- CCSM's live `MISSION_ORG` schema (confirmed via gspread, 2026-08-05) is `Area_Code, Area_Name, Zone, District, Companion1_Name, Companion1_Email, Companion2_Name, Companion2_Email, Is_DL, Is_ZL, Is_STL, Is_AP, Is_MP, Active` — **no `Language_Type`, no `Companion3_Name`/`Companion4_Name`, no `Area_ID`** (Provo has all of those). Ported code must not assume any of the missing columns exist.

## Correction to the approved spec (found while writing this plan)

The spec (`docs/superpowers/specs/2026-08-05-ccsm-transfer-flow-design.md`) lists **`AREA_LINEAGE`** among the 5 tabs to create. That's wrong: `AREA_LINEAGE` is written only by `docs/LineageReview.gs`'s `applyLineage()` — a separate area-merge/split/retire feature — and used only by `app/integrations/drive_transfer_sync.py`'s rename suggestions in Provo's Transfer Flow page. Neither `transfer_engine.py` nor `transfer_apply_service.py` reads or writes it (confirmed by reading both files in full plus every call site of `AREA_LINEAGE` in Provo's `app/` and `docs/`). Since Drive/rename tracking is explicitly out of scope here, **`AREA_LINEAGE` is dropped from Task 1** — only 4 tabs get created: `TRANSFER_IMPORT`, `MISSION_ORG_SNAPSHOT`, `TRANSFER_LOG`, `CLOUD_JOB_STATUS`.

Also not carried over from `transfer_engine.py`: `build_rezone_diff()` and `suggest_area_renames()` — both exist solely to feed Provo's Drive-preview UI (rename-candidate pairs, rezone-move list). Porting them would be dead code with no caller, since Drive is out of scope.

Also skipped: `app/ingestion/mission_org_merge_preview.py` (a standalone offline CSV dry-run tool). `transfer_apply_service.preview()` already gives a live preview through the Streamlit page — this tool would be a second, redundant way to get the same answer.

---

### Task 1: Add COMPASS_CCSM sheet tabs

**Files:**
- Modify: `BuildCcsmSheet.gs` (repo root — add a new function, called manually once; does not touch existing functions)
- Test: a throwaway verification script run locally (not committed) against the live sheet

**Interfaces:**
- Produces: 4 new tabs on `COMPASS_CCSM` — `TRANSFER_IMPORT` (headers: `Area, Zone, District, Companion1_Name, Companion2_Name, Companion3_Name, Companion4_Name, Calling, Area_Email`), `MISSION_ORG_SNAPSHOT` (headers matching CCSM's real `MISSION_ORG`: `Area_Code, Area_Name, Zone, District, Companion1_Name, Companion1_Email, Companion2_Name, Companion2_Email, Is_DL, Is_ZL, Is_STL, Is_AP, Is_MP, Active`), `TRANSFER_LOG` (headers: `Timestamp, Function, Result, Details`), `CLOUD_JOB_STATUS` (headers: `job_id, job_type, status, progress_text, started_at, updated_at, result_summary`).

`TRANSFER_IMPORT` keeps the 4-companion-slot shape even though CCSM's `MISSION_ORG` only has 2 — the IMOS roster transform (Task 6) always emits 4 slots, and `transfer_engine.py`'s merge only copies whichever columns exist in the live `MISSION_ORG` header row, so the extra slots are harmless if ever populated.

- [ ] **Step 1: Add `ccsm_buildTransferTabs()` to `BuildCcsmSheet.gs`**

Open `BuildCcsmSheet.gs` and add this function (append at the end of the file, do not touch anything existing):

```javascript
// ── Transfer Flow tabs (added 2026-08-05) ──────────────────────────────────────
// One-time setup — run ccsm_buildTransferTabs() once from the Apps Script editor
// (Run > select function > ccsm_buildTransferTabs) after pasting this into the
// live COMPASS_CCSM Apps Script project. Idempotent: safe to re-run, it only
// creates a tab + header row if the tab doesn't already exist.
function ccsm_buildTransferTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var specs = [
    { name: 'TRANSFER_IMPORT', headers: ['Area', 'Zone', 'District',
        'Companion1_Name', 'Companion2_Name', 'Companion3_Name', 'Companion4_Name',
        'Calling', 'Area_Email'] },
    { name: 'MISSION_ORG_SNAPSHOT', headers: ['Area_Code', 'Area_Name', 'Zone',
        'District', 'Companion1_Name', 'Companion1_Email', 'Companion2_Name',
        'Companion2_Email', 'Is_DL', 'Is_ZL', 'Is_STL', 'Is_AP', 'Is_MP', 'Active'] },
    { name: 'TRANSFER_LOG', headers: ['Timestamp', 'Function', 'Result', 'Details'] },
    { name: 'CLOUD_JOB_STATUS', headers: ['job_id', 'job_type', 'status',
        'progress_text', 'started_at', 'updated_at', 'result_summary'] },
  ];

  var created = [];
  specs.forEach(function(spec) {
    var sheet = ss.getSheetByName(spec.name);
    if (sheet) return;   // already exists — never re-touch an existing tab's data
    sheet = ss.insertSheet(spec.name);
    sheet.getRange(1, 1, 1, spec.headers.length).setValues([spec.headers]);
    sheet.setFrozenRows(1);
    created.push(spec.name);
  });

  Logger.log(created.length
    ? 'Created: ' + created.join(', ')
    : 'All 4 tabs already existed — nothing created.');
}
```

- [ ] **Step 2: Paste into the live Apps Script editor and run it (manual, user-confirmed)**

This is a `.gs` file — per this repo's own boundary convention (same rule Provo's `CLAUDE.md` documents), editing it here does nothing live. Confirm with the user by filename ("`BuildCcsmSheet.gs` — OK to paste?") before pasting, then:
1. Open `COMPASS_CCSM` in Google Sheets → Extensions → Apps Script.
2. Paste the new `ccsm_buildTransferTabs` function into `BuildCcsmSheet.gs` there (append, don't replace the file).
3. Save, select `ccsm_buildTransferTabs` in the function dropdown, click Run.
4. Approve the OAuth prompt if this is the first time this script has needed sheet-edit access.

- [ ] **Step 3: Verify the tabs exist with the right headers (live check, not a unit test)**

Run this from the `dashboard/` venv (reads the same `.streamlit/secrets.toml` already in place — no new credentials needed):

```bash
cd "Worldwide PMG Compass/CCSM PMG Compass/dashboard"
venv/Scripts/python.exe -c "
import toml, gspread
secrets = toml.load('.streamlit/secrets.toml')
gc = gspread.service_account_from_dict(secrets['gcp_service_account'])
sh = gc.open(secrets['COMPASS_SHEET_NAME'])
for name in ['TRANSFER_IMPORT', 'MISSION_ORG_SNAPSHOT', 'TRANSFER_LOG', 'CLOUD_JOB_STATUS']:
    ws = sh.worksheet(name)
    print(name, '->', ws.row_values(1))
"
```

Expected: all 4 tabs print their headers exactly as specified above, with no `WorksheetNotFound` error.

- [ ] **Step 4: Commit**

```bash
git add BuildCcsmSheet.gs
git commit -m "feat(transfer): add ccsm_buildTransferTabs to scaffold the 4 Transfer Flow tabs"
```

---

### Task 2: Port `transfer_engine.py` (pure logic, no Drive)

**Files:**
- Create: `dashboard/app/ingestion/__init__.py` (empty — the directory doesn't exist yet)
- Create: `dashboard/app/ingestion/transfer_engine.py`
- Test: `dashboard/tests/test_transfer_engine.py`

**Interfaces:**
- Produces: `parse_roster(import_rows: list[dict]) -> list[dict]`, `run_guards(roster_rows, mission_org, override=False) -> dict`, `build_diff(roster_rows, mission_org) -> dict`, `apply_transfer(roster_rows, mission_org, headers) -> tuple[list[dict], dict]`, `rows_to_grid(rows, headers) -> list[list]`, `next_schedule_update(schedule_rows, today) -> list[dict]`, plus helpers `calling_to_flags`, `is_leadership_row`, `is_senior_row`, `is_non_teaching_row`. Consumed by Task 3.

- [ ] **Step 1: Create the ingestion package**

```bash
mkdir -p dashboard/app/ingestion
touch dashboard/app/ingestion/__init__.py
```

- [ ] **Step 2: Write `dashboard/app/ingestion/transfer_engine.py`**

Verbatim port of Provo's `app/ingestion/transfer_engine.py`, with `build_rezone_diff()` and `suggest_area_renames()` removed (Drive-only, no caller in this build — see the correction note above) and the module docstring updated:

```python
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
```

Note: this dropped Provo's `new_areas_language`/`_derive_language_type` handling along with the `_LANGUAGE_NAME_MARKERS` table — CCSM's `MISSION_ORG` has no `Language_Type` column at all (confirmed live), so that logic would be genuinely dead code here, not just harmlessly absent.

- [ ] **Step 3: Write `dashboard/tests/test_transfer_engine.py`**

Ported from Provo's `tests/test_ingestion/test_transfer_engine.py`, fixtures updated to CCSM's real `MISSION_ORG` header shape (2 companions, no `Language_Type`/`Area_ID`) and every test that exercised `Companion3_Name`/`Companion4_Name`/`Language_Type` behavior dropped (there's nothing CCSM-specific left to assert about columns that don't exist):

```python
"""Unit tests for transfer_engine — CCSM's port of the pure roster-merge logic
(see dashboard/app/ingestion/transfer_engine.py for provenance). Pure functions
only; no Google Sheets access.
"""

import datetime as dt

import pytest

from app.ingestion import transfer_engine as te


# ── Fixtures ──────────────────────────────────────────────────────────────────

MISSION_ORG_HEADERS = [
    "Area_Code", "Area_Name", "Zone", "District",
    "Companion1_Name", "Companion1_Email", "Companion2_Name", "Companion2_Email",
    "Is_DL", "Is_ZL", "Is_STL", "Is_AP", "Is_MP", "Active",
]


def _org_row(name, zone="Angol", district="Alemania 2", active="TRUE",
             c1="", c2="", email="", **flags):
    row = {h: "" for h in MISSION_ORG_HEADERS}
    row.update({
        "Area_Name": name, "Zone": zone, "District": district,
        "Companion1_Name": c1, "Companion2_Name": c2,
        "Companion1_Email": email, "Active": active,
        "Is_ZL": "FALSE", "Is_STL": "FALSE", "Is_DL": "FALSE",
        "Is_AP": "FALSE", "Is_MP": "FALSE",
    })
    row.update(flags)
    return row


def _roster_import(area, zone="Angol", district="Alemania 2",
                   c1="Elder A", c2="", calling="", email=""):
    """A TRANSFER_IMPORT-shaped row (header keys: Area, Zone, ...)."""
    return {
        "Area": area, "Zone": zone, "District": district,
        "Companion1_Name": c1, "Companion2_Name": c2,
        "Companion3_Name": "", "Companion4_Name": "",
        "Calling": calling, "Area_Email": email,
    }


# ── parse_roster ────────────────────────────────────────────────────────────────

def test_parse_roster_maps_area_and_sets_active_true():
    rows = te.parse_roster([_roster_import("Alemania 2")])
    assert len(rows) == 1
    r = rows[0]
    assert r["Area_Name"] == "Alemania 2"
    assert r["Active"] == "TRUE"


def test_parse_roster_skips_blank_area():
    rows = te.parse_roster([_roster_import(""), _roster_import("Real Area")])
    assert [r["Area_Name"] for r in rows] == ["Real Area"]


@pytest.mark.parametrize("calling,flag", [
    ("ZL", "Is_ZL"),
    ("STL", "Is_STL"),
    ("DL", "Is_DL"),
    ("AP", "Is_AP"),
    ("MP", "Is_MP"),
])
def test_parse_roster_calling_sets_correct_flag(calling, flag):
    r = te.parse_roster([_roster_import("A", calling=calling)])[0]
    assert r[flag] == "TRUE"
    others = {"Is_ZL", "Is_STL", "Is_DL", "Is_AP", "Is_MP"} - {flag}
    assert all(r[o] == "FALSE" for o in others)


def test_parse_roster_no_calling_all_flags_false():
    r = te.parse_roster([_roster_import("A", calling="")])[0]
    assert all(r[f] == "FALSE" for f in ("Is_ZL", "Is_STL", "Is_DL", "Is_AP", "Is_MP"))


# ── non-teaching-row detection ──────────────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "Mission President",
    "Assistant to President 1",
    "Zone Leader 1 - Angol",
    "Sister Training Leader - Temuco",
    "District Leader - Villarrica",
])
def test_is_non_teaching_row_true(name):
    assert te.is_non_teaching_row(_org_row(name)) is True


def test_is_non_teaching_row_false_for_real_area_with_leadership_flag():
    assert te.is_non_teaching_row(_org_row("Alemania 2", Is_DL="TRUE")) is False


# ── run_guards ───────────────────────────────────────────────────────────────────

def test_run_guards_blocks_empty_roster():
    guard = te.run_guards([], [_org_row("A")])
    assert guard["ok"] is False


def test_run_guards_blocks_over_30pct_deactivation():
    org = [_org_row(f"Area{i}") for i in range(10)]
    roster = te.parse_roster([_roster_import("Area0"), _roster_import("Area1")])
    guard = te.run_guards(roster, org)
    assert guard["ok"] is False
    assert "80%" in guard["msg"]


def test_run_guards_override_skips_the_check():
    org = [_org_row(f"Area{i}") for i in range(10)]
    roster = te.parse_roster([_roster_import("Area0")])
    guard = te.run_guards(roster, org, override=True)
    assert guard["ok"] is True


def test_run_guards_ignores_non_teaching_rows_in_denominator():
    org = [_org_row("Area0"), _org_row("Mission President")]
    roster = te.parse_roster([_roster_import("Area0")])
    guard = te.run_guards(roster, org)
    assert guard["ok"] is True


# ── build_diff ───────────────────────────────────────────────────────────────────

def test_build_diff_flags_new_area():
    diff = te.build_diff(te.parse_roster([_roster_import("New Area")]), [])
    assert any("New Area" in a for a in diff["added"])


def test_build_diff_flags_deactivated_area():
    org = [_org_row("Gone Now")]
    diff = te.build_diff([], org)
    assert diff["deactivated"] == ["Gone Now"]


def test_build_diff_flags_companion_change():
    org = [_org_row("A", c1="Elder Old")]
    roster = te.parse_roster([_roster_import("A", c1="Elder New")])
    diff = te.build_diff(roster, org)
    assert len(diff["changed"]) == 1
    assert "Elder Old" in diff["changed"][0] and "Elder New" in diff["changed"][0]


def test_build_diff_flags_reactivation():
    org = [_org_row("A", active="FALSE")]
    roster = te.parse_roster([_roster_import("A", c1="Elder New")])
    diff = te.build_diff(roster, org)
    assert len(diff["reactivated"]) == 1


# ── apply_transfer ───────────────────────────────────────────────────────────────

def test_apply_transfer_updates_matched_area_preserves_email():
    org = [_org_row("A", c1="Elder Old", email="500001@missionary.org")]
    roster = te.parse_roster([_roster_import("A", c1="Elder New")])
    new_rows, summary = te.apply_transfer(roster, org, MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "A")
    assert row["Companion1_Name"] == "Elder New"
    assert row["Companion1_Email"] == "500001@missionary.org"
    assert row["Active"] == "TRUE"


def test_apply_transfer_deactivates_unmatched_active_area():
    org = [_org_row("Gone", email="500002@missionary.org")]
    new_rows, summary = te.apply_transfer([], org, MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "Gone")
    assert row["Active"] == "FALSE"
    assert row["Companion1_Name"] == ""
    assert "Gone (500002@missionary.org)" in summary["deactivated_with_email"]


def test_apply_transfer_appends_new_area_blank_email():
    roster = te.parse_roster([_roster_import("Brand New")])
    new_rows, summary = te.apply_transfer(roster, [], MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "Brand New")
    assert row["Companion1_Email"] == ""
    assert "Brand New" in summary["new_emails_needed"]


def test_apply_transfer_never_touches_leadership_rows():
    org = [_org_row("Mission President", c1="President Smith")]
    new_rows, _ = te.apply_transfer([], org, MISSION_ORG_HEADERS)
    row = next(r for r in new_rows if r["Area_Name"] == "Mission President")
    assert row["Companion1_Name"] == "President Smith"


# ── next_schedule_update ─────────────────────────────────────────────────────────

def test_next_schedule_update_flips_planned_to_actual():
    rows = [{"Transfer_Number": "5", "Start_Date": "", "Weeks": "6", "Status": "Planned"}]
    out = te.next_schedule_update(rows, dt.date(2026, 8, 5))
    assert out[0]["Status"] == "Actual"
    assert out[0]["Start_Date"] == "2026-08-05"


def test_next_schedule_update_appends_when_none_planned():
    rows = [{"Transfer_Number": "5", "Start_Date": "2026-06-01", "Weeks": "6", "Status": "Actual"}]
    out = te.next_schedule_update(rows, dt.date(2026, 8, 5))
    assert len(out) == 2
    assert out[1]["Transfer_Number"] == "6"
    assert out[1]["Status"] == "Actual"
```

- [ ] **Step 4: Run the tests**

```bash
cd "Worldwide PMG Compass/CCSM PMG Compass/dashboard"
venv/Scripts/python.exe -m pytest tests/test_transfer_engine.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/ingestion/__init__.py dashboard/app/ingestion/transfer_engine.py dashboard/tests/test_transfer_engine.py
git commit -m "feat(transfer): port transfer_engine.py roster-merge logic from Provo, no Drive"
```

---

### Task 3: Port `transfer_apply_service.py`

**Files:**
- Create: `dashboard/app/ingestion/transfer_apply_service.py`

**Interfaces:**
- Consumes: `transfer_engine.parse_roster/run_guards/build_diff/apply_transfer/rows_to_grid` (Task 2); `app.db.sheets_client.read_values/overwrite_tab/update_cell/append_row` (confirmed present); `app.db.queries.get_area_language_group`, `_resolve_area_category`, `get_mission_weekly_expectation_total`, `get_mission_monthly_expectation_total` (confirmed present in CCSM's `queries.py` with these exact names, all `@st.cache_data(ttl=300)`).
- Produces: `preview() -> dict`, `apply(override: bool = False, today: date | None = None) -> dict`, `TransferBlocked` exception. Consumed by Task 4.

- [ ] **Step 1: Write `dashboard/app/ingestion/transfer_apply_service.py`**

Near-verbatim port — every `sc.*` call it makes (`read_values`, `overwrite_tab`, `update_cell`, `append_row`) exists in CCSM's `sheets_client.py` under the identical name, and every `q.*` cache-clear call exists in CCSM's `queries.py` under the identical name, so no renaming is needed anywhere in this file, only the module docstring:

```python
"""
transfer_apply_service.py — Streamlit-side orchestration for CCSM's Transfer
Flow: reads MISSION_ORG / TRANSFER_IMPORT / TRANSFER_SCHEDULE / AGENT_CONFIG
from COMPASS_CCSM, runs the pure transfer_engine, and writes the results back.

Ported from Utah Provo's app/ingestion/transfer_apply_service.py. All Google
Sheets I/O goes through app.db.sheets_client (gspread service account). The
pure logic lives in transfer_engine; this module only wires it to the live
sheet, so it is exercised in the app rather than unit-tested.
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
    grid = sc.read_values(CONFIG_TAB)
    if not grid:
        return False
    headers = [str(h).strip() for h in grid[0]]
    try:
        key_i = headers.index("Config_Key")
        val_i = headers.index("Config_Value")
    except ValueError:
        return False
    upd_i = headers.index("Last_Updated") if "Last_Updated" in headers else -1
    today_str = today.strftime("%Y-%m-%d")
    for r in range(1, len(grid)):
        if str(grid[r][key_i]).strip() == "TRANSFER_START_DATE":
            sc.update_cell(CONFIG_TAB, _a1(r + 1, val_i + 1), today_str)
            if upd_i >= 0:
                sc.update_cell(CONFIG_TAB, _a1(r + 1, upd_i + 1), today_str)
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
```

Note: `AGENT_CONFIG`'s real column names must be confirmed before this ships — Provo's `_set_transfer_start_date` assumes `Config_Key`/`Config_Value`/`Last_Updated`. Check with:

```bash
venv/Scripts/python.exe -c "
import toml, gspread
secrets = toml.load('.streamlit/secrets.toml')
gc = gspread.service_account_from_dict(secrets['gcp_service_account'])
sh = gc.open(secrets['COMPASS_SHEET_NAME'])
print(sh.worksheet('AGENT_CONFIG').row_values(1))
"
```

If the headers differ, update `_set_transfer_start_date`'s three `headers.index(...)` calls to match before Task 8's live test — this function fails closed (`return False`, no exception) on a header mismatch, so a mismatch would silently skip updating `TRANSFER_START_DATE` rather than crash the apply, but it should still be fixed rather than left silently failing.

- [ ] **Step 2: Commit**

```bash
git add dashboard/app/ingestion/transfer_apply_service.py
git commit -m "feat(transfer): port transfer_apply_service.py orchestration from Provo"
```

---

### Task 4: Extend `pages/12_Traslados.py` with Pull / Preview / Apply / Sync

**Files:**
- Modify: `dashboard/pages/12_Traslados.py` (append new sections; the existing read-only content above stays untouched)

**Interfaces:**
- Consumes: `transfer_apply_service.preview()/apply()/TransferBlocked` (Task 3); `transfer_bridge.form_sync()` (Task 5, added in this task as a new small module); `app.db.sheets_client.read_values` (existing).

- [ ] **Step 1: Add a `transfer_bridge.py` bridge module for form sync**

```python
"""
transfer_bridge.py — HTTP client for CCSM_TransferWebApp.gs (see Task 5). The
gspread service account behind this dashboard has no Forms API access, so
nightly/weekly form dropdown sync has to run in Apps Script; this module is
the bridge that calls it from Streamlit.

TRANSFER_WEBAPP_URL / TRANSFER_WEBAPP_SECRET come from Streamlit secrets —
set after CCSM_TransferWebApp.gs is deployed (Task 5, Step 3).
"""
from __future__ import annotations

import requests
import streamlit as st


class FormSyncError(Exception):
    pass


def form_sync(which: str = "both") -> dict:
    """which: 'nightly' | 'weekly' | 'both'. Returns the parsed JSON response
    from CCSM_TransferWebApp.gs's doPost({action:'formSync', which})."""
    url = st.secrets.get("TRANSFER_WEBAPP_URL", "")
    secret = st.secrets.get("TRANSFER_WEBAPP_SECRET", "")
    if not url or not secret:
        raise FormSyncError(
            "TRANSFER_WEBAPP_URL / TRANSFER_WEBAPP_SECRET not set in secrets — "
            "deploy CCSM_TransferWebApp.gs first (see Task 5)."
        )
    resp = requests.post(
        url, json={"secret": secret, "action": "formSync", "which": which},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise FormSyncError(data.get("error", "Unknown form sync failure."))
    return data
```

Create it at `dashboard/app/integrations/transfer_bridge.py` (the `app/integrations/` directory doesn't exist yet either):

```bash
mkdir -p dashboard/app/integrations
touch dashboard/app/integrations/__init__.py
```

- [ ] **Step 2: Append the write sections to `pages/12_Traslados.py`**

Add these imports near the top (alongside the existing ones):

```python
from app.ingestion import transfer_apply_service as tas
from app.integrations.transfer_bridge import FormSyncError, form_sync
```

Update the module docstring's last line (`"This page is READ-ONLY. It plans nothing and moves nobody."`) to:

```python
"""
...(everything above this line stays as-is)...

Below the read-only view, this page can also PULL the roster (via the cloud
Playwright job — see Task 6/7), PREVIEW the diff against MISSION_ORG, APPLY
it, and SYNC the nightly/weekly form area dropdowns. No Drive automation —
CCSM has none, and this build doesn't add any.
"""
```

Append this at the end of the file (after the existing "Roster" section):

```python
# ── Apply a transfer ─────────────────────────────────────────────────────────────

render_section_label(t("Apply a Transfer"))

st.caption(
    t("Pull the current roster from IMOS, preview what would change in "
      "MISSION_ORG, then apply it. Each step needs a separate click — nothing "
      "here runs automatically.")
)

_import_rows = sc.read_values("TRANSFER_IMPORT")
if len(_import_rows) <= 1:
    st.info(
        t("TRANSFER_IMPORT is empty. Pull the roster first (below), or paste "
          "it into the TRANSFER_IMPORT tab by hand.")
    )
else:
    st.caption(
        t("TRANSFER_IMPORT has {count} rows.", count=fmt_int(len(_import_rows) - 1))
    )

if st.button(t("1 · Preview"), key="tf_preview_btn"):
    with st.spinner(t("Reading MISSION_ORG and TRANSFER_IMPORT...")):
        st.session_state["tf_preview"] = tas.preview()

_preview = st.session_state.get("tf_preview")
if _preview:
    _guard, _diff = _preview["guard"], _preview["diff"]
    st.caption(
        t("{roster} roster rows vs {org} MISSION_ORG rows.",
          roster=fmt_int(_preview["roster_count"]), org=fmt_int(_preview["org_count"]))
    )
    if not _guard["ok"]:
        st.error(_guard["msg"])
    for _label, _key in [(t("New areas"), "added"), (t("Deactivating"), "deactivated"),
                         (t("Changed"), "changed"), (t("Reactivating"), "reactivated")]:
        _items = _diff[_key]
        if _items:
            with st.expander(f"{_label} ({fmt_int(len(_items))})"):
                for _item in _items:
                    st.write(f"- {_item}")

    _override = False
    if not _guard["ok"]:
        _override = st.checkbox(
            t("Override the deactivation guard (only if this many deactivations "
              "is genuinely correct)"),
            key="tf_override",
        )

    if st.button(t("2 · Apply"), key="tf_apply_btn", disabled=(not _guard["ok"] and not _override)):
        with st.spinner(t("Applying to MISSION_ORG...")):
            try:
                _summary = tas.apply(override=_override)
            except tas.TransferBlocked as e:
                st.error(str(e))
            else:
                st.success(t("Applied."))
                if _summary.get("new_emails_needed"):
                    st.warning(
                        t("New areas need an email address added by hand: {areas}",
                          areas=", ".join(_summary["new_emails_needed"]))
                    )
                st.session_state.pop("tf_preview", None)

st.divider()

if st.button(t("3 · Sync nightly + weekly form dropdowns"), key="tf_sync_btn"):
    with st.spinner(t("Syncing form dropdowns...")):
        try:
            _result = form_sync("both")
        except FormSyncError as e:
            st.error(str(e))
        else:
            for _label, _key in [("Nightly", "nightly"), ("Weekly", "weekly")]:
                _r = _result.get(_key)
                if _r:
                    (st.success if _r["status"] == "OK" else st.warning)(
                        f"{_label}: {_r['msg']}"
                    )
```

Also add `from app.db import sheets_client as sc` to the imports (used above for the `TRANSFER_IMPORT` row count) — `read_tab` is already imported for the read-only section above; this adds the raw-values sibling.

- [ ] **Step 3: Manual smoke test (no automated test — this reads/writes live sheet state)**

Run the dashboard locally and click through Preview only (not Apply) against the real `COMPASS_CCSM`:

```bash
cd "Worldwide PMG Compass/CCSM PMG Compass/dashboard"
venv\Scripts\streamlit.exe run Home.py --server.port 8502
```

Navigate to Traslados, confirm the existing read-only sections still render exactly as before, then click "1 · Preview" and confirm it shows a guard result + diff without raising. **Do not click Apply yet** — `TRANSFER_IMPORT` is still empty at this point (Task 6 fills it), so Apply would try to deactivate every active area and should be blocked by the 30% guard; confirming that block fires correctly IS the useful signal here.

- [ ] **Step 4: Commit**

```bash
git add dashboard/pages/12_Traslados.py dashboard/app/integrations/__init__.py dashboard/app/integrations/transfer_bridge.py
git commit -m "feat(transfer): add Pull/Preview/Apply/Sync sections to Traslados page"
```

---

### Task 5: `CCSM_TransferWebApp.gs` — the form-sync Apps Script Web App

CCSM has no `AgentTransfer.gs` equivalent, so the helper functions Provo's `docs/TransferWebApp.gs` calls into (`at_getOrgZones_`, `at_readFormStructure_`, `at_repairFormRouting_`, `at_cloneItem_`, `at_log_`) don't exist here. Both files below are new; together they're CCSM's self-contained equivalent.

**Files:**
- Create: `CCSM_TransferHelpers.gs` (repo root, new — the renamed port of the `at_*` helpers this needs)
- Create: `CCSM_TransferWebApp.gs` (repo root, new — the Web App entry point, same design as Provo's)

**Interfaces:**
- Produces: an `/exec` URL that `transfer_bridge.form_sync()` (Task 4) POSTs to.

- [ ] **Step 1: Write `CCSM_TransferHelpers.gs`**

Ported from `docs/AgentTransfer.gs` (Provo repo) lines 144-155, 200-276, 771-845, 933-971, 1104-1177 — every `at_` prefix renamed to `cct_` (CCSM's Apps Script global namespace already uses several prefixes like `av_`/`at_` would collide with nothing today, but `cct_` keeps this file's globals unambiguously scoped to Transfer):

```javascript
// ── CCSM_TransferHelpers.gs ────────────────────────────────────────────────────
// Ported from Utah Provo's docs/AgentTransfer.gs (lines 144-155, 200-276,
// 771-845, 933-971, 1104-1177) — every at_ prefix renamed cct_. CCSM has no
// AgentTransfer.gs of its own, so these helpers (MISSION_ORG reading, zone
// dropdown structure reading, item cloning, routing repair) are ported fresh
// rather than reused from an existing file.

var CCT_MISSION_ORG_TAB = 'MISSION_ORG';
var CCT_TRANSFER_LOG_TAB = 'TRANSFER_LOG';

function cct_log_(fnName, result, details) {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CCT_TRANSFER_LOG_TAB);
  if (!sheet) {
    sheet = ss.insertSheet(CCT_TRANSFER_LOG_TAB);
    sheet.appendRow(['Timestamp', 'Function', 'Result', 'Details']);
    sheet.setFrozenRows(1);
  }
  sheet.appendRow([new Date(), fnName, result, details]);
}

function cct_loadMissionOrg_() {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CCT_MISSION_ORG_TAB);
  if (!sheet) throw new Error('MISSION_ORG tab not found');
  var data = sheet.getDataRange().getValues();
  if (data.length < 2) throw new Error('MISSION_ORG is empty');

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var map     = {};

  for (var i = 1; i < data.length; i++) {
    var obj = {};
    headers.forEach(function(h, idx) { obj[h] = String(data[i][idx] || '').trim(); });
    var key = (obj['Area_Name'] || '').toLowerCase().trim();
    if (key) map[key] = { obj: obj, rowIndex: i, headers: headers };
  }

  return { map: map, headers: headers, data: data, sheet: sheet };
}

// Keyed off Area_Name, not the Is_* flags — a real teaching-area row can
// legitimately carry a leadership flag when its companion holds that calling.
function cct_isLeadershipRow_(obj) {
  var name = (obj['Area_Name'] || '').trim();
  return /^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name);
}

function cct_isSeniorRow_(obj) {
  var name = (obj['Area_Name'] || '').trim();
  return /\bSenior\b/i.test(name);
}

function cct_isNonTeachingRow_(obj) {
  return cct_isLeadershipRow_(obj) || cct_isSeniorRow_(obj);
}

function cct_getOrgZones_() {
  var orgData = cct_loadMissionOrg_();
  var zones   = {};
  Object.keys(orgData.map).forEach(function(k) {
    var obj = orgData.map[k].obj;
    if ((obj['Active'] || '').toUpperCase() !== 'TRUE') return;
    if (cct_isNonTeachingRow_(obj)) return;
    var zone = (obj['Zone']      || '').toLowerCase().trim();
    var area = (obj['Area_Name'] || '').trim();
    if (!zone || !area) return;
    if (!zones[zone]) zones[zone] = [];
    zones[zone].push(area);
  });
  return zones;
}

function cct_normalizeZoneSectionTitle_(title) {
  return String(title || '')
    .replace(/\s+Zone Section\s*$/i, '')
    .toLowerCase()
    .trim();
}

function cct_readFormStructure_(formId) {
  var form  = FormApp.openById(formId);
  var items = form.getItems();

  var zoneItem = null;
  items.forEach(function(item) {
    if (item.getType() !== FormApp.ItemType.LIST) return;
    var t = item.getTitle().toLowerCase();
    if (t.indexOf('zone') >= 0 && t.indexOf('area') < 0) zoneItem = item.asListItem();
  });
  if (!zoneItem) throw new Error('Could not find "What zone are you in?" list item in the form.');

  var pageBreakItems = [];
  items.forEach(function(item) {
    if (item.getType() === FormApp.ItemType.PAGE_BREAK) {
      pageBreakItems.push(item.asPageBreakItem());
    }
  });

  var pbItemIndices = [];
  items.forEach(function(item, idx) {
    if (item.getType() === FormApp.ItemType.PAGE_BREAK) pbItemIndices.push(idx);
  });

  var zoneSections = pageBreakItems.map(function(pb, sectionIdx) {
    var startIdx = pbItemIndices[sectionIdx];
    var endIdx   = sectionIdx + 1 < pbItemIndices.length
      ? pbItemIndices[sectionIdx + 1]
      : items.length;

    var sectionItems = items.slice(startIdx, endIdx);

    var areaItem = null;
    sectionItems.forEach(function(item) {
      if (item.getType() === FormApp.ItemType.LIST &&
          item.getTitle().toLowerCase().indexOf('area') >= 0 &&
          !areaItem) {
        areaItem = item.asListItem();
      }
    });

    return {
      pageBreak:       pb,
      zoneName:        cct_normalizeZoneSectionTitle_(pb.getTitle()) || null,
      areaItem:        areaItem,
      allSectionItems: sectionItems,
      sectionIdx:      sectionIdx
    };
  });

  return { form: form, zoneItem: zoneItem, zoneSections: zoneSections };
}

function cct_cloneItem_(form, sourceItem) {
  var type  = sourceItem.getType();
  var title = sourceItem.getTitle();
  switch (type) {
    case FormApp.ItemType.TEXT:
      return form.addTextItem().setTitle(title)
        .setRequired(sourceItem.asTextItem().isRequired());
    case FormApp.ItemType.PARAGRAPH_TEXT:
      return form.addParagraphTextItem().setTitle(title)
        .setRequired(sourceItem.asParagraphTextItem().isRequired());
    case FormApp.ItemType.MULTIPLE_CHOICE:
      var mc = sourceItem.asMultipleChoiceItem();
      return form.addMultipleChoiceItem().setTitle(title)
        .setChoiceValues(mc.getChoices().map(function(c) { return c.getValue(); }))
        .setRequired(mc.isRequired());
    case FormApp.ItemType.CHECKBOX:
      var cb = sourceItem.asCheckboxItem();
      return form.addCheckboxItem().setTitle(title)
        .setChoiceValues(cb.getChoices().map(function(c) { return c.getValue(); }))
        .setRequired(cb.isRequired());
    case FormApp.ItemType.DATE:
      return form.addDateItem().setTitle(title)
        .setRequired(sourceItem.asDateItem().isRequired());
    case FormApp.ItemType.LIST:
      var li = sourceItem.asListItem();
      return form.addListItem().setTitle(title)
        .setChoiceValues(li.getChoices().map(function(c) { return c.getValue(); }))
        .setRequired(li.isRequired());
    case FormApp.ItemType.SCALE:
      var si = sourceItem.asScaleItem();
      return form.addScaleItem().setTitle(title)
        .setBounds(si.getLowerBound(), si.getUpperBound())
        .setRequired(si.isRequired());
    default:
      Logger.log('cct_cloneItem_: unknown type ' + type + ' for "' + title + '" — added as text');
      return form.addTextItem().setTitle(title);
  }
}

function cct_repairFormRouting_(formId) {
  var form  = FormApp.openById(formId);
  var items = form.getItems();

  var zoneItem = null;
  items.forEach(function(item) {
    if (item.getType() !== FormApp.ItemType.LIST) return;
    var t = item.getTitle().toLowerCase();
    if (t.indexOf('zone') >= 0 && t.indexOf('area') < 0) zoneItem = item.asListItem();
  });
  if (!zoneItem) throw new Error('Zone dropdown not found in form.');

  var orgZones = cct_getOrgZones_();

  var areaToZone = {};
  Object.keys(orgZones).forEach(function(zone) {
    orgZones[zone].forEach(function(area) {
      areaToZone[area.toLowerCase()] = zone;
    });
  });

  var pbItemIndices = [];
  items.forEach(function(item, idx) {
    if (item.getType() === FormApp.ItemType.PAGE_BREAK) pbItemIndices.push(idx);
  });

  var pbByZone = {};
  pbItemIndices.forEach(function(startIdx, sectionIdx) {
    var endIdx = sectionIdx + 1 < pbItemIndices.length
      ? pbItemIndices[sectionIdx + 1]
      : items.length;
    var pb = items[startIdx].asPageBreakItem();
    for (var j = startIdx + 1; j < endIdx; j++) {
      if (items[j].getType() === FormApp.ItemType.LIST &&
          items[j].getTitle().toLowerCase().indexOf('area') >= 0) {
        var choices = items[j].asListItem().getChoices();
        for (var c = 0; c < choices.length; c++) {
          var zone = areaToZone[choices[c].getValue().toLowerCase()];
          if (zone) { pbByZone[zone] = pb; break; }
        }
        break;
      }
    }
  });

  var orgDataForDisplay = cct_loadMissionOrg_();
  var zoneDisplayMap = {};
  Object.keys(orgDataForDisplay.map).forEach(function(k) {
    var obj = orgDataForDisplay.map[k].obj;
    if ((obj['Active'] || '').toUpperCase() !== 'TRUE') return;
    if (cct_isNonTeachingRow_(obj)) return;
    var dn = (obj['Zone'] || '').trim();
    if (dn) zoneDisplayMap[dn.toLowerCase()] = dn;
  });

  var orgZoneNames = Object.keys(orgZones).sort();
  var missing = [];
  var newChoices = orgZoneNames.map(function(zoneName) {
    var pb = pbByZone[zoneName];
    var dn = zoneDisplayMap[zoneName] || zoneName;
    if (!pb) { missing.push(zoneName); return zoneItem.createChoice(dn); }
    return zoneItem.createChoice(dn, pb);
  });
  zoneItem.setChoices(newChoices);

  return { zonesRouted: orgZoneNames.length - missing.length, zonesTotal: orgZoneNames.length, missing: missing };
}
```

- [ ] **Step 2: Write `CCSM_TransferWebApp.gs`**

Ported from `docs/TransferWebApp.gs` (Provo repo), calling the `cct_*` helpers from Step 1 instead of `at_*`, and its own `AT_NIGHTLY_FORM_ID`/`AT_WEEKLY_FORM_ID` replaced with `CCT_NIGHTLY_FORM_ID`/`CCT_WEEKLY_FORM_ID` placeholders the user fills in:

```javascript
// ── CCSM_TransferWebApp.gs ──────────────────────────────────────────────────────
// Headless HTTPS bridge so the CCSM dashboard's Traslados page can trigger the
// nightly + weekly form zone/area dropdown sync WITHOUT anyone opening the
// sheet's Apps Script editor. The gspread service account behind the dashboard
// has NO Forms API access, so form sync must run here.
//
// Ported from Utah Provo's docs/TransferWebApp.gs. Calls CCSM_TransferHelpers.gs
// (cct_getOrgZones_, cct_readFormStructure_, cct_repairFormRouting_,
// cct_cloneItem_, cct_log_) — same Apps Script project = shared global scope.
//
// ── ONE-TIME SETUP (before deploy) ───────────────────────────────────────────
// 1. Set CCT_NIGHTLY_FORM_ID / CCT_WEEKLY_FORM_ID below to CCSM's real form
//    edit IDs — open each Google Form's edit URL
//    (docs.google.com/forms/d/<FORM_ID>/edit) and copy the ID out of it.
//    AGENT_CONFIG's NIGHTLY_FORM_LINK/WEEKLY_FORM_LINK store the published
//    viewform URL, which has a DIFFERENT id — that one will not work here.
// 2. Set CCT_SHARED_SECRET below to a long random string.
//
// ── ONE-TIME DEPLOY ──────────────────────────────────────────────────────────
// 3. Paste this file AND CCSM_TransferHelpers.gs into the COMPASS_CCSM Apps
//    Script project.
// 4. Deploy → New deployment → type "Web app":
//       Execute as:      Me
//       Who has access:  Anyone
//    Copy the /exec URL.
// 5. In dashboard/.streamlit/secrets.toml set:
//       TRANSFER_WEBAPP_URL    = <that /exec URL>
//       TRANSFER_WEBAPP_SECRET = <the same secret as CCT_SHARED_SECRET>
// Re-deploy (Manage deployments → edit → new version) whenever this file changes.

var CCT_SHARED_SECRET = 'CHANGE_ME_to_a_long_random_string';
var CCT_NIGHTLY_FORM_ID = 'CHANGE_ME_nightly_form_edit_id';
var CCT_WEEKLY_FORM_ID = 'CHANGE_ME_weekly_form_edit_id';

function doGet() {
  return cct_json_({ ok: true, service: 'CCSM_TransferWebApp', ts: new Date().toISOString() });
}

function doPost(e) {
  try {
    var body = {};
    if (e && e.postData && e.postData.contents) {
      body = JSON.parse(e.postData.contents);
    }
    if (String(body.secret || '') !== CCT_SHARED_SECRET) {
      return cct_json_({ ok: false, error: 'Unauthorized — bad or missing secret.' });
    }

    var action = String(body.action || '');
    if (action === 'formSync') {
      return cct_formSync_(body.which || 'both');
    }
    return cct_json_({ ok: false, error: 'Unknown action: ' + action });

  } catch (err) {
    return cct_json_({ ok: false, error: String(err && err.message || err) });
  }
}

function cct_formSync_(which) {
  var out = { ok: true };
  which = String(which || 'both').toLowerCase();

  if (which === 'nightly' || which === 'both') {
    out.nightly = cct_applyFormSync_(CCT_NIGHTLY_FORM_ID, 'nightly');
    if (out.nightly.status === 'ERROR') out.ok = false;
  }
  if (which === 'weekly' || which === 'both') {
    out.weekly = cct_applyFormSync_(CCT_WEEKLY_FORM_ID, 'weekly');
    if (out.weekly.status === 'ERROR') out.ok = false;
  }
  return cct_json_(out);
}

function cct_applyFormSync_(formId, label) {
  try {
    var orgZones   = cct_getOrgZones_();
    var formStruct = cct_readFormStructure_(formId);
    var form       = formStruct.form;
    var sections   = formStruct.zoneSections;
    var orgZoneNames = Object.keys(orgZones).sort();

    // Step 1: update area dropdowns in existing sections
    var handledZones = {};
    sections.forEach(function(sec) {
      if (!sec.zoneName) return;
      var key = (sec.zoneName || '').toLowerCase().trim();
      if (orgZones[key]) {
        if (sec.areaItem) sec.areaItem.setChoiceValues(orgZones[key]);
        handledZones[key] = sec.pageBreak;
      } else {
        if (sec.areaItem) sec.areaItem.setChoiceValues(['(No active areas)']);
      }
    });

    // Step 2: add new zone sections
    var templateSec = sections[0];
    orgZoneNames.forEach(function(zoneName) {
      if (handledZones[zoneName]) return;
      var newPb = form.addPageBreakItem().setTitle(zoneName + ' Zone Section');
      form.addListItem()
        .setTitle('What is your area?')
        .setChoiceValues(orgZones[zoneName])
        .setRequired(true);
      templateSec.allSectionItems.slice(2).forEach(function(item) {
        cct_cloneItem_(form, item);
      });
      handledZones[zoneName] = newPb;
    });

    // Step 3: rebuild zone dropdown choices + routing
    var repairResult = cct_repairFormRouting_(formId);

    // Step 4: verification pass
    var verErrors = [];
    if (repairResult.missing.length > 0) {
      verErrors.push('Could not route zones: ' + repairResult.missing.join(', '));
    }

    var status = verErrors.length === 0 ? 'OK' : 'WARN';
    var msg = verErrors.length === 0
      ? label + ' form sync complete. ' + orgZoneNames.length + ' zones verified.'
      : 'Sync applied but verification found issues: ' + verErrors.join(' | ');

    cct_log_('CCSM_TransferWebApp formSync [' + label + ']', status, msg);
    return { status: status, msg: msg };

  } catch (e) {
    cct_log_('CCSM_TransferWebApp formSync [' + label + ']', 'ERROR', e.message);
    return { status: 'ERROR', msg: e.message };
  }
}

function cct_json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
```

Note: this drops Provo's verification-pass area-count cross-checks (the block that compares each form section's area choice count against `orgZones[z].length`) — kept the simpler "routing succeeded" check only, since the more detailed check duplicates logic already in `cct_repairFormRouting_`'s own `missing` list without adding a new failure mode this port needs to catch. If real-world testing (Task 8) finds sync silently leaving a section's areas stale, add that check back in, mirroring `at_applyFormSyncCore_`'s Step 4 verbatim.

- [ ] **Step 3: Deploy (manual, user-confirmed — real form-edit access)**

Confirm both filenames with the user before pasting (per this repo's docs/ boundary convention), then:
1. Get the real `CCT_NIGHTLY_FORM_ID`/`CCT_WEEKLY_FORM_ID` from each form's edit URL and fill them in.
2. Generate a long random string for `CCT_SHARED_SECRET`.
3. Paste both files into the `COMPASS_CCSM` Apps Script project.
4. Deploy → New deployment → Web app → Execute as Me, access Anyone → copy the `/exec` URL.
5. Add `TRANSFER_WEBAPP_URL` and `TRANSFER_WEBAPP_SECRET` to `dashboard/.streamlit/secrets.toml` (local) — and, once the app is redeployed to Streamlit Cloud, to its Cloud secrets too (Settings → Secrets in the Streamlit Cloud dashboard). The user pastes the actual secret value in both places themselves.

- [ ] **Step 4: Manual test — health check + a real form sync (user-confirmed, changes a live form)**

```bash
curl <the /exec URL>
```
Expected: `{"ok":true,"service":"CCSM_TransferWebApp",...}`.

Then, with the user's go-ahead (this edits CCSM's live nightly/weekly forms), trigger the "3 · Sync nightly + weekly form dropdowns" button on the Traslados page and confirm both come back `OK` or a specific, readable `WARN`, not an exception.

- [ ] **Step 5: Commit**

```bash
git add CCSM_TransferHelpers.gs CCSM_TransferWebApp.gs
git commit -m "feat(transfer): add CCSM_TransferWebApp.gs + helpers for form dropdown sync"
```

---

### Task 6: Port the IMOS Playwright roster scraper

**Files:**
- Create: `dashboard/app/ingestion/imos_portal.py` (verbatim copy, zero logic changes)
- Create: `dashboard/app/ingestion/transfer_roster_transform.py` (adapted: empty zone-rename map, CCSM's own non-area-district exclusions)
- Create: `dashboard/app/ingestion/transfer_sheets_writer.py` (adapted: uses `sheets_client.overwrite_tab` instead of a raw `googleapiclient` call)
- Create: `dashboard/app/ingestion/imos_transfer_runner.py` (adapted: minimal settings loader instead of Provo's full `pydantic` settings module)
- Create: `dashboard/app/ingestion/ccsm_ingestion_settings.py` (new, small — the minimal settings loader)
- Create: `dashboard/.env` (real values typed in by the user, never by the assistant)
- Modify: `dashboard/requirements.txt` (add `playwright`)

**Interfaces:**
- Produces: `download_organization_roster_and_emails(username, password, output_dir, headless) -> (Path, dict)`, `transform_roster(path) -> list[dict]`, `write_transfer_import(sheet_id, rows) -> int`. Consumed by Task 7's workflow.

- [ ] **Step 1: Copy `imos_portal.py` verbatim**

No logic in this file references Provo's schema or credentials by name — it's pure Playwright automation against `imos.churchofjesuschrist.org`, parameterized entirely through its own function arguments. Copy it byte-for-byte:

```bash
cp "../../../PMG-Compass/app/ingestion/imos_portal.py" "dashboard/app/ingestion/imos_portal.py"
```

(Path is relative to the CCSM repo root — adjust if run from elsewhere. `../../../PMG-Compass` assumes the sibling-folder layout confirmed earlier: `Desktop/PMG-Compass` and `Desktop/Worldwide PMG Compass/CCSM PMG Compass` are siblings two levels up from `Desktop`.)

Confirm the copy is identical:
```bash
diff "../../../PMG-Compass/app/ingestion/imos_portal.py" "dashboard/app/ingestion/imos_portal.py"
```
Expected: no output (files identical).

- [ ] **Step 2: Write `transfer_roster_transform.py`**

Same logic as Provo's, with `ZONE_NAME_MAP` emptied (CCSM's own `MISSION_ORG` zone names — `Angol, Arauco, Camilo, Los Angeles Norte, Los Angeles Sur, San Pedro, Temuco Cautín, Temuco Ñielol, Victoria, Villarrica` — are plain title-case Spanish names with no parenthetical zone code, unlike Provo's `"kings peak (kp)"` style; there's no evidence yet that IMOS's own export uses a different spelling for CCSM, so the map starts empty and gets filled in only if Task 8's first real download shows a mismatch) and `_NON_AREA_DISTRICTS` kept as a starting guess to verify against a real export:

```python
"""
transfer_roster_transform.py — Transforms a raw IMOS "Organization Roster"
export into TRANSFER_IMPORT rows.

Ported from Utah Provo's app/ingestion/transfer_roster_transform.py.
ZONE_NAME_MAP starts EMPTY — Provo's export needed one because its zone names
carry a parenthetical code ("Kings Peak (KP)") that doesn't match MISSION_ORG's
plain-text zone names. CCSM's MISSION_ORG zones (Angol, Arauco, Camilo, Los
Angeles Norte, Los Angeles Sur, San Pedro, Temuco Cautín, Temuco Ñielol,
Victoria, Villarrica) have no such code, so there's no known mapping needed
yet — verify against a real IMOS download (Task 8) before relying on this,
and add entries here if the export's spelling doesn't match.
"""

from pathlib import Path

import pandas as pd

from app.utils.logger import get_logger

_logger = get_logger("ingestion.transfer_roster_transform")

# Column names as they appear in the raw "Current Organization" Excel export —
# UNVERIFIED for CCSM (Provo's own file carries the same caveat: these are
# best-known guesses from Provo's real 2026-07-01 export; CCSM's export
# format is assumed identical since it's the same IMOS portal, but this has
# not yet been confirmed against a real CCSM download).
RAW_HEADER_ROW = 2
RAW_COL_AREA = "Area"
RAW_COL_ZONE = "Zone"
RAW_COL_DISTRICT = "District"
RAW_COL_AREA_EMAIL = "Area Email"
RAW_COL_STATUS = "Status"
RAW_COL_POSITION = "Position"
RAW_COL_NAME = "Name"

_STATUS_IN_FIELD = "In Field"

_CALLING_MAP = {
    "MP": "MP",
    "AP": "AP",
    "DL": "DL",
    "DT": "DL",
    "STL1": "STL", "STL2": "STL", "STLT": "STL",
    "ZL1": "ZL", "ZL2": "ZL",
}
_CALLING_PRIORITY = ["MP", "AP", "DL", "STL", "ZL"]

# Empty until a real CCSM IMOS export shows a zone-name mismatch — see the
# module docstring.
ZONE_NAME_MAP: dict[str, str] = {}

# Starting guess, carried over from Provo's own confirmed set — verify against
# a real CCSM export and adjust if CCSM's mission office/senior-couple rows
# use different Zone/District text.
_NON_AREA_DISTRICTS = {"office", "other districts", "mp senior"}


def _normalize_zone(zone) -> str:
    return ZONE_NAME_MAP.get(str(zone).strip().lower(), str(zone).strip())


def _is_non_area_row(zone, district) -> bool:
    z = str(zone).strip().lower()
    d = str(district).strip().lower()
    return z.startswith("sr ") or d in _NON_AREA_DISTRICTS or z.endswith(" sm")


def _format_name(raw: str) -> str:
    """First Name + Last Name only — drops middle names, handles 'Last, First'
    order. CCSM's MISSION_ORG already stores companion names in "Last, First
    Middle" form (confirmed live, e.g. "Rees, Nicolas Clay") — this function's
    comma-handling branch is what normalizes that into "First Last" for the
    roster import, same as it does for Provo."""
    raw = str(raw).strip()
    if not raw:
        return ""
    if "," in raw:
        last, _, rest = raw.partition(",")
        rest_parts = rest.strip().split()
        first = rest_parts[0] if rest_parts else ""
        return f"{first} {last.strip()}".strip()
    parts = raw.split()
    if len(parts) <= 2:
        return raw
    return f"{parts[0]} {parts[-1]}"


def _pick_companions(names: list, positions: list) -> tuple:
    """Companion1 = the Position=='SC' missionary (or first in file order if
    no SC present); Companion2/3/4 = everyone else, one name per slot. CCSM's
    MISSION_ORG only has 2 companion slots, but a companionship of 3+ is
    still possible in the field (e.g. a trio) — keep the 4-slot ceiling so a
    real trio/quad doesn't raise, even though only slots 1-2 currently have
    anywhere to land in MISSION_ORG (apply_transfer's headers-driven merge
    just drops the extra slots harmlessly — see transfer_engine.py)."""
    if len(names) > 4:
        raise ValueError(
            f"Companionship has {len(names)} missionaries — more than the "
            f"4-person ceiling this system supports. Names: {names}"
        )
    if len(names) == 1:
        return names[0], "", "", ""
    sc_idx = next((i for i, p in enumerate(positions) if p == "SC"), None)
    if sc_idx is not None:
        comp1 = names[sc_idx]
        rest = [n for i, n in enumerate(names) if i != sc_idx]
    else:
        comp1 = names[0]
        rest = names[1:]
    rest_padded = rest + [""] * (3 - len(rest))
    return comp1, rest_padded[0], rest_padded[1], rest_padded[2]


def _pick_calling(positions: list) -> str:
    found = {_CALLING_MAP[p] for p in positions if p in _CALLING_MAP}
    for rank in _CALLING_PRIORITY:
        if rank in found:
            return rank
    return ""


def build_transfer_rows(df: pd.DataFrame) -> list:
    """Raw roster DataFrame -> TRANSFER_IMPORT rows.

    Raises ValueError if any 'In Field' missionary is dropped during
    transform (e.g. a blank Area causes pandas groupby to silently exclude
    that row from every group).
    """
    df = df.dropna(how="all")
    df = df[df[RAW_COL_NAME].notna()]

    if RAW_COL_STATUS in df.columns:
        in_field = df[df[RAW_COL_STATUS].astype(str).str.strip() == _STATUS_IN_FIELD]
    else:
        in_field = df

    if len(in_field) > 0:
        non_area_mask = in_field.apply(
            lambda r: _is_non_area_row(r[RAW_COL_ZONE], r[RAW_COL_DISTRICT]), axis=1
        )
        in_field = in_field[~non_area_mask]

    total_missionaries = len(in_field)

    rows = []
    consumed = 0
    for area, group in in_field.groupby(RAW_COL_AREA):
        names = [_format_name(n) for n in group[RAW_COL_NAME]]
        positions = [str(p).strip().strip("()") for p in group[RAW_COL_POSITION]]
        comp1, comp2, comp3, comp4 = _pick_companions(names, positions)
        calling = _pick_calling(positions)
        consumed += len(names)
        area_email = group[RAW_COL_AREA_EMAIL].iloc[0] if RAW_COL_AREA_EMAIL in group.columns else ""
        rows.append({
            "Area": area,
            "Zone": _normalize_zone(group[RAW_COL_ZONE].iloc[0]),
            "District": group[RAW_COL_DISTRICT].iloc[0],
            "Companion1_Name": comp1,
            "Companion2_Name": comp2,
            "Companion3_Name": comp3,
            "Companion4_Name": comp4,
            "Calling": calling,
            "Area_Email": area_email,
        })

    if consumed != total_missionaries:
        raise ValueError(
            f"Transform dropped missionaries: {total_missionaries} 'In Field' "
            f"missionaries in the source file but only {consumed} were placed "
            f"into output rows (likely a blank Area value on one or more rows)."
        )

    _logger.info(f"Transformed {total_missionaries} missionaries into {len(rows)} area rows")
    return rows


def load_roster_excel(path) -> pd.DataFrame:
    return pd.read_excel(Path(path), header=RAW_HEADER_ROW)


def transform_roster(path) -> list:
    df = load_roster_excel(path)
    return build_transfer_rows(df)
```

- [ ] **Step 3: Write `transfer_sheets_writer.py`, adapted to `sheets_client`**

Provo's version calls the raw Google Sheets API directly via `googleapiclient` + its own settings module. CCSM already has an equivalent write path in `sheets_client.overwrite_tab()` — use that instead, so this file needs no separate service-account plumbing of its own:

```python
"""
transfer_sheets_writer.py — Clears and rewrites the TRANSFER_IMPORT tab with
rows produced by transfer_roster_transform.build_transfer_rows.

Ported from Utah Provo's app/ingestion/transfer_sheets_writer.py, adapted to
call app.db.sheets_client.overwrite_tab() instead of the raw Sheets API —
CCSM's sheets_client already has an equivalent clear+rewrite helper, so no
separate googleapiclient/service-account plumbing is needed here.

Mirrors the manual process's "select all, delete, paste" step exactly: one
all-or-nothing batched write, never partial rows.
"""

from app.db import sheets_client as sc
from app.utils.logger import get_logger

_logger = get_logger("ingestion.transfer_sheets_writer")

_TAB_NAME = "TRANSFER_IMPORT"
_HEADERS = ["Area", "Zone", "District", "Companion1_Name", "Companion2_Name",
            "Companion3_Name", "Companion4_Name", "Calling", "Area_Email"]


def write_transfer_import(rows: list) -> int:
    """Clears TRANSFER_IMPORT and writes header + rows in one batched call.
    Raises ValueError if rows is empty — never clears the tab with nothing
    to replace it."""
    if not rows:
        raise ValueError("Refusing to write TRANSFER_IMPORT: rows is empty.")

    grid = [_HEADERS] + [[r.get(h, "") for h in _HEADERS] for r in rows]
    sc.overwrite_tab(_TAB_NAME, grid)
    _logger.info(f"Wrote {len(rows)} rows to {_TAB_NAME}")
    return len(rows)
```

Note this drops the `sheet_id` parameter Provo's version took — `sheets_client.overwrite_tab` already resolves the sheet via `st.secrets["COMPASS_SHEET_NAME"]`/`gcp_service_account`, same as every other CCSM write, so there's no separate sheet-ID plumbing to thread through. This is a **Streamlit-context-only** function now (needs `st.secrets`) — see Step 5 for how the standalone CLI runner (which has no Streamlit context) reaches the sheet instead.

Also drops the `@with_retry` decorator Provo's version had — `sheets_client`'s own `gspread.BackOffHTTPClient` (confirmed in `_get_client()`) already retries 429s, so a second retry layer on top would be redundant.

- [ ] **Step 4: Write the minimal settings loader**

CCSM's dashboard has no `app/config/settings.py` (confirmed — only `flavor_loader.py`/`metric_catalog.py`/`metrics.py`/`theme.py` exist there). Rather than port Provo's much larger `pydantic`-based settings module (which carries many Provo-only fields — Church/Tableau/Supabase/etc. — CCSM doesn't need any of), write a minimal one with only what the IMOS runner needs:

```python
"""
ccsm_ingestion_settings.py — minimal .env-backed settings for the IMOS roster
runner. Deliberately NOT a port of Provo's app/config/settings.py — that
module carries many Provo-only fields (Church SSO, Tableau, Supabase) this
runner has no use for. Streamlit's own st.secrets is untouched by this;
Streamlit reads its own secrets.toml, this only serves the standalone CLI
runner (imos_transfer_runner.py), which runs outside any Streamlit context.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _resolve(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


IMOS_USERNAME = _resolve("CCSM_IMOS_USERNAME")
IMOS_PASSWORD = _resolve("CCSM_IMOS_PASSWORD")
IMOS_HEADLESS = _resolve("IMOS_HEADLESS", "true").lower() == "true"
COMPASS_SHEET_NAME = _resolve("COMPASS_SHEET_NAME", "COMPASS_CCSM")
GOOGLE_SHEETS_CREDENTIALS_JSON = _resolve("GOOGLE_SHEETS_CREDENTIALS_JSON")
```

Place at `dashboard/app/ingestion/ccsm_ingestion_settings.py`.

- [ ] **Step 5: Write `imos_transfer_runner.py`**

Since `transfer_sheets_writer.write_transfer_import()` now goes through `sheets_client` (which needs `st.secrets`, not available to a bare CLI process), the runner needs its own lightweight gspread write path instead of importing the Streamlit-context version — using `ccsm_ingestion_settings`'s `GOOGLE_SHEETS_CREDENTIALS_JSON` directly:

```python
"""
imos_transfer_runner.py — CLI entry point for CCSM's transfer roster
automation. Runs standalone (GitHub Actions or a local shell), no Streamlit
context — so it authenticates to Sheets directly via
GOOGLE_SHEETS_CREDENTIALS_JSON rather than through app.db.sheets_client
(which needs st.secrets).

Usage:
    python -m app.ingestion.imos_transfer_runner

Downloads the Organization Roster from imos.churchofjesuschrist.org,
transforms it into TRANSFER_IMPORT rows, and writes them to COMPASS_CCSM's
TRANSFER_IMPORT tab. Never calls apply()/form_sync() — the mission office
still reviews and applies from the Traslados page.

Ported from Utah Provo's app/ingestion/imos_transfer_runner.py.
"""

import json
import sys
import tempfile
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from app.ingestion import ccsm_ingestion_settings as settings
from app.ingestion.imos_portal import download_organization_roster_and_emails
from app.ingestion.transfer_roster_transform import transform_roster
from app.utils.logger import get_logger

_logger = get_logger("ingestion.imos_transfer_runner")

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
_HEADERS = ["Area", "Zone", "District", "Companion1_Name", "Companion2_Name",
            "Companion3_Name", "Companion4_Name", "Calling", "Area_Email"]


def match_area_emails(rows: list[dict], area_emails: dict) -> tuple[int, int, list[str]]:
    """Fills in row["Area_Email"] in place from the scraped area_emails dict.
    Exact match first, then a prefix match only when exactly one candidate
    qualifies (never misassigns an email between two different areas)."""
    matched = 0
    fuzzy_matched = 0
    email_lookup = {k.strip().lower(): v for k, v in area_emails.items()}
    unmatched_areas = []
    for row in rows:
        area_key = str(row["Area"]).strip().lower()
        email = email_lookup.get(area_key)
        if not email:
            candidates = [k for k in email_lookup
                          if k.startswith(area_key) or area_key.startswith(k)]
            if len(candidates) == 1:
                email = email_lookup[candidates[0]]
                fuzzy_matched += 1
        if email:
            row["Area_Email"] = email
            matched += 1
        else:
            unmatched_areas.append(row["Area"])
    return matched, fuzzy_matched, unmatched_areas


def _write_transfer_import(rows: list[dict]) -> int:
    creds_dict = json.loads(settings.GOOGLE_SHEETS_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    client = gspread.authorize(creds)
    sh = client.open(settings.COMPASS_SHEET_NAME)
    ws = sh.worksheet("TRANSFER_IMPORT")
    ws.clear()
    grid = [_HEADERS] + [[r.get(h, "") for h in _HEADERS] for r in rows]
    ws.update(grid, value_input_option="RAW")
    return len(rows)


def main() -> None:
    if not settings.IMOS_USERNAME or not settings.IMOS_PASSWORD:
        _logger.error("CCSM_IMOS_USERNAME/CCSM_IMOS_PASSWORD not set — aborting.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        _logger.info("Downloading Organization Roster and area emails...")
        roster_path, area_emails = download_organization_roster_and_emails(
            username=settings.IMOS_USERNAME,
            password=settings.IMOS_PASSWORD,
            output_dir=Path(tmp),
            headless=settings.IMOS_HEADLESS,
        )

        _logger.info("Transforming roster...")
        rows = transform_roster(roster_path)
        if not rows:
            _logger.error("Transform produced zero rows — aborting before Sheets write.")
            sys.exit(1)

        matched, fuzzy_matched, unmatched_areas = match_area_emails(rows, area_emails)
        _logger.info(f"Matched {matched}/{len(rows)} areas to an email "
                      f"({fuzzy_matched} via prefix fallback, {len(area_emails)} emails scraped)")
        if unmatched_areas:
            _logger.info(f"Areas with no matching email (check manually): {unmatched_areas}")

        _logger.info(f"Writing {len(rows)} rows to TRANSFER_IMPORT...")
        written = _write_transfer_import(rows)
        _logger.info(f"Done — {written} rows written. Review on the Traslados page "
                      f"before applying.")


if __name__ == "__main__":
    main()
```

Note this drops the `--sheet-id` CLI argument Provo's version required (a deliberate safety rail against accidentally targeting production while testing) — CCSM only has one sheet (`COMPASS_CCSM`, resolved by name from `ccsm_ingestion_settings.COMPASS_SHEET_NAME`), so there's no second sheet to guard against confusing it with. If CCSM ever gets a test/staging sheet, re-add an explicit target argument rather than defaulting to a hardcoded name.

- [ ] **Step 6: Add a new `.env` (values typed by the user, not the assistant)**

Create `dashboard/.env` (gitignored — confirm `dashboard/.gitignore` or the repo root `.gitignore` already excludes `.env`; if not, add it before this step) with these keys, template only:

```
CCSM_IMOS_USERNAME=
CCSM_IMOS_PASSWORD=
IMOS_HEADLESS=true
COMPASS_SHEET_NAME=COMPASS_CCSM
GOOGLE_SHEETS_CREDENTIALS_JSON=
```

Tell the user: "Open Provo's `.env` at `Desktop\PMG-Compass\.env`, find `CCSM_IMOS_USERNAME` and `CCSM_IMOS_PASSWORD` (they're already there, just unused), and copy those two values into the new `dashboard/.env` file at the paths above — I won't read or type the values myself." For `GOOGLE_SHEETS_CREDENTIALS_JSON`, the user pastes the same service-account JSON already sitting in `dashboard/.streamlit/secrets.toml`'s `[gcp_service_account]` section, but as a single-line JSON string (not TOML) — tell them exactly which existing secret to copy from, not to create a new one.

- [ ] **Step 7: Add Playwright to `requirements.txt`**

```
playwright==1.49.0
```

Append to `dashboard/requirements.txt`, matching the version Provo pins and the `mcr.microsoft.com/playwright/python:v1.49.0-jammy` container Task 7's workflow uses (version mismatch between the pinned package and the container's baked-in browsers causes install failures).

- [ ] **Step 8: Manual local test (user-run, real IMOS login, headless off)**

```bash
cd "Worldwide PMG Compass/CCSM PMG Compass/dashboard"
venv\Scripts\pip.exe install playwright==1.49.0
venv\Scripts\playwright.exe install chromium
```

Then temporarily set `IMOS_HEADLESS=false` in `.env` and have the user run:

```bash
venv\Scripts\python.exe -m app.ingestion.imos_transfer_runner
```

Watch the browser window with the user — confirm it logs in, downloads a roster, and writes rows to `TRANSFER_IMPORT` (check via the same gspread snippet from Task 1 Step 3, reading `TRANSFER_IMPORT` instead). Expect the login selectors from `imos_portal.py` (copied unmodified from Provo) to need adjustment on the first real run — its own module docstring already warns "have not yet been verified against the live portal." Set `IMOS_HEADLESS` back to `true` in `.env` once confirmed.

- [ ] **Step 9: Commit**

```bash
git add dashboard/app/ingestion/imos_portal.py dashboard/app/ingestion/transfer_roster_transform.py dashboard/app/ingestion/transfer_sheets_writer.py dashboard/app/ingestion/ccsm_ingestion_settings.py dashboard/app/ingestion/imos_transfer_runner.py dashboard/requirements.txt
git commit -m "feat(transfer): port IMOS Playwright roster scraper for CCSM"
```

(`.env` is gitignored — never committed.)

---

### Task 7: Cloud automation — CCSM's own GitHub Actions workflow

**Files:**
- Create: `dashboard/app/integrations/gcp_creds.py` (verbatim)
- Create: `dashboard/app/integrations/cloud_job_status.py` (adapted: sheet-name-based open, matching CCSM's own pattern, instead of open-by-key)
- Create: `dashboard/app/integrations/github_actions.py` (adapted: CCSM's own repo)
- Create: `dashboard/app/ingestion/cloud_job_wrapper.py` (verbatim)
- Create: `dashboard/app/components/cloud_job_ui.py` (verbatim)
- Create: `.github/workflows/transfer-roster-pull.yml` (repo root, adapted)
- Create: `requirements_cloud.txt` (repo root)
- Modify: `dashboard/pages/12_Traslados.py` (wire the "Pull" button to `run_cloud_job`)

**Interfaces:**
- Consumes: `imos_transfer_runner.main()` (Task 6), dispatched inside the workflow container.
- Produces: a "Pull from IMOS (cloud)" button on the Traslados page that dispatches the workflow and polls `CLOUD_JOB_STATUS` to completion.

- [ ] **Step 1: Copy `gcp_creds.py` verbatim**

Nothing in this file is Provo-specific (it reads `GOOGLE_SHEETS_CREDENTIALS_JSON` from the environment, or falls back to `st.secrets["gcp_service_account"]` — CCSM's `gcp_service_account` secret key is the same name). Copy unmodified:

```bash
mkdir -p dashboard/app/components
touch dashboard/app/components/__init__.py
cp "../../../PMG-Compass/app/integrations/gcp_creds.py" "dashboard/app/integrations/gcp_creds.py"
```

- [ ] **Step 2: Write `cloud_job_status.py`, adapted to open by name**

Provo's version opens the sheet by ID (`client.open_by_key(_get_sheet_id())`), needing a `COMPASS_SHEET_ID` secret CCSM doesn't have configured anywhere yet. CCSM's own convention (every other module in this codebase) opens by name via `COMPASS_SHEET_NAME` — use that instead, so no new sheet-ID secret needs introducing:

```python
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
```

- [ ] **Step 3: Write `github_actions.py`, repointed at CCSM's repo**

```python
"""github_actions.py — fires workflow_dispatch events against CCSM's own
GitHub Actions workflows.

Ported from Utah Provo's app/integrations/github_actions.py, with _API_BASE
repointed from pmgcompass-upm/PMG-Compass to CCSM's own repo.
"""
import os

import requests

_API_BASE = "https://api.github.com/repos/ccsmpmgcompass-collab/ccsm-pmg-compass"


class DispatchError(Exception):
    pass


def _get_token() -> str:
    try:
        import streamlit as st
        if "GITHUB_ACTIONS_TOKEN" in st.secrets:
            return st.secrets["GITHUB_ACTIONS_TOKEN"]
    except Exception:
        pass
    token = os.environ.get("GITHUB_ACTIONS_TOKEN", "")
    if not token:
        raise DispatchError(
            "GITHUB_ACTIONS_TOKEN not found in st.secrets or the environment."
        )
    return token


def dispatch_workflow(workflow_file: str, inputs: dict, ref: str = "main") -> None:
    """Fire a workflow_dispatch event on workflow_file. All input values are
    stringified — GitHub's API requires workflow_dispatch inputs to be strings."""
    token = _get_token()
    resp = requests.post(
        f"{_API_BASE}/actions/workflows/{workflow_file}/dispatches",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"ref": ref, "inputs": {k: str(v) for k, v in inputs.items()}},
        timeout=15,
    )
    if resp.status_code != 204:
        raise DispatchError(f"Dispatch failed ({resp.status_code}): {resp.text}")
```

- [ ] **Step 4: Copy `cloud_job_wrapper.py` and `cloud_job_ui.py` verbatim**

Neither references Provo by name — both are generic subprocess/polling plumbing:

```bash
cp "../../../PMG-Compass/app/ingestion/cloud_job_wrapper.py" "dashboard/app/ingestion/cloud_job_wrapper.py"
cp "../../../PMG-Compass/app/components/cloud_job_ui.py" "dashboard/app/components/cloud_job_ui.py"
diff "../../../PMG-Compass/app/ingestion/cloud_job_wrapper.py" "dashboard/app/ingestion/cloud_job_wrapper.py"
diff "../../../PMG-Compass/app/components/cloud_job_ui.py" "dashboard/app/components/cloud_job_ui.py"
```
Expected: no diff output for either.

- [ ] **Step 5: Write `.github/workflows/transfer-roster-pull.yml`**

Adapted from Provo's workflow: fewer secrets (no Church/Tableau/Supabase — CCSM's runner doesn't need them), no `--sheet-id` argument (Task 6 Step 5 dropped it), and the runner module path updated:

```yaml
name: Transfer Roster Pull

on:
  workflow_dispatch:
    inputs:
      job_id:
        required: true
        type: string

concurrency:
  group: transfer-roster-pull
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest
    container:
      image: mcr.microsoft.com/playwright/python:v1.49.0-jammy
    timeout-minutes: 20
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install dependencies
        run: pip install --no-cache-dir -r requirements_cloud.txt

      - name: Run roster pull (tracked)
        working-directory: dashboard
        env:
          CCSM_IMOS_USERNAME: ${{ secrets.CCSM_IMOS_USERNAME }}
          CCSM_IMOS_PASSWORD: ${{ secrets.CCSM_IMOS_PASSWORD }}
          IMOS_HEADLESS: "true"
          GOOGLE_SHEETS_CREDENTIALS_JSON: ${{ secrets.GOOGLE_SHEETS_CREDENTIALS_JSON }}
          COMPASS_SHEET_NAME: COMPASS_CCSM
        run: >
          python -m app.ingestion.cloud_job_wrapper
          --job-id "${{ inputs.job_id }}" --job-type transfer_pull
          -- python -m app.ingestion.imos_transfer_runner

      - name: Upload debug screenshots on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: transfer-debug
          path: dashboard/debug/*.png
          if-no-files-found: ignore
          retention-days: 7
```

Note `cloud_job_wrapper` runs from `dashboard/` (the `working-directory:`), since that's where all the `app.*` modules live in this repo, unlike Provo where they sit at the repo root.

- [ ] **Step 6: Write `requirements_cloud.txt`**

```
# For GitHub Actions jobs running inside mcr.microsoft.com/playwright/python —
# Playwright itself and its browsers are already baked into that image.
playwright==1.49.0
gspread>=6.1.2
google-auth>=2.40.2
google-auth-oauthlib>=1.2.1
pandas>=2.0.0
xlrd>=2.0.1
python-dotenv>=1.0.0
requests>=2.31.0
```

Place at the CCSM repo root (`workflows` reference it un-prefixed, same as Provo's own layout).

- [ ] **Step 7: Wire the Pull button into `pages/12_Traslados.py`**

Add to the imports:

```python
from app.components.cloud_job_ui import CloudJobFailed, CloudJobTimeout, run_cloud_job
```

Insert above the existing "1 · Preview" button from Task 4 (so Pull comes before Preview in the UI flow):

```python
if st.button(t("0 · Pull roster from IMOS (cloud)"), key="tf_pull_btn"):
    try:
        run_cloud_job(
            job_type="transfer_pull",
            workflow_file="transfer-roster-pull.yml",
            dispatch_inputs={},
            running_label=t("Pulling the roster from IMOS..."),
        )
    except (CloudJobFailed, CloudJobTimeout):
        pass   # run_cloud_job already rendered the error/warning
    else:
        st.success(t("Roster pulled. Click Preview to see the diff."))
```

- [ ] **Step 8: Secrets walkthrough (assistant tells the user exactly what to paste, never pastes it themselves)**

Tell the user, one at a time, to add these to the CCSM GitHub repo's Settings → Secrets and variables → Actions:

| Secret name | Where the value comes from |
|---|---|
| `GITHUB_ACTIONS_TOKEN` | A new fine-grained personal access token, scoped ONLY to `ccsmpmgcompass-collab/ccsm-pmg-compass`, permissions: Actions (read/write) + Secrets (read/write). Create at github.com/settings/tokens?type=beta while signed into the CCSM-owned GitHub account. |
| `CCSM_IMOS_USERNAME` | The value already sitting in Provo's `.env` under this same key (unused there) — same value used in `dashboard/.env` (Task 6 Step 6). |
| `CCSM_IMOS_PASSWORD` | Same — the value already in Provo's `.env`. |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | The same service-account JSON already in `dashboard/.streamlit/secrets.toml`'s `[gcp_service_account]` section, flattened to one line of JSON (not TOML) — the user's own service account already has write access to `COMPASS_CCSM`. |

Also tell the user to add these to the CCSM dashboard's **Streamlit Cloud** app secrets (Settings → Secrets in the Streamlit Cloud dashboard — separate from the GitHub repo secrets above, needed so the deployed app's own polling code can resolve them):

| Secret name | Value |
|---|---|
| `GITHUB_ACTIONS_TOKEN` | The same token created above. |
| `TRANSFER_WEBAPP_URL` | The `/exec` URL from Task 5 Step 3. |
| `TRANSFER_WEBAPP_SECRET` | The same secret string set as `CCT_SHARED_SECRET` in Task 5. |

- [ ] **Step 9: Commit**

```bash
git add dashboard/app/integrations/gcp_creds.py dashboard/app/integrations/cloud_job_status.py dashboard/app/integrations/github_actions.py dashboard/app/ingestion/cloud_job_wrapper.py dashboard/app/components/__init__.py dashboard/app/components/cloud_job_ui.py .github/workflows/transfer-roster-pull.yml requirements_cloud.txt dashboard/pages/12_Traslados.py
git commit -m "feat(transfer): add CCSM's own GitHub Actions cloud Playwright automation"
```

---

### Task 8: End-to-end live verification

**Files:** none (verification only).

- [ ] **Step 1: Push and confirm the workflow file registers**

```bash
git push origin main
```

Confirm with the user first (pushing to their production repo). After push, check `github.com/ccsmpmgcompass-collab/ccsm-pmg-compass/actions` shows "Transfer Roster Pull" as a dispatchable workflow.

- [ ] **Step 2: Live dispatch test — real IMOS login, real Sheets write (needs the user's explicit go-ahead)**

With the user watching, click "0 · Pull roster from IMOS (cloud)" on the deployed (or local, pointed at the real secrets) Traslados page. Confirm:
- The GitHub Actions run shows up and completes with a real login + a real roster download (not just a green checkmark — open the run log and confirm actual IMOS login lines, matching the lesson from Provo's own Task 7: a wrapper reporting SUCCESS is not proof the underlying job did anything).
- `TRANSFER_IMPORT` now has real rows (verify via the Task 1 Step 3 gspread snippet, reading `TRANSFER_IMPORT`).

- [ ] **Step 3: Live Preview + Apply test (needs the user's explicit go-ahead — mutates production `MISSION_ORG`)**

Click "1 · Preview" and walk through the diff with the user before anything is applied. If the diff looks right (or the user consciously overrides the deactivation guard for a known reason), click "2 · Apply" and confirm:
- `MISSION_ORG` reflects the new roster.
- `MISSION_ORG_SNAPSHOT` has the pre-apply grid.
- `TRANSFER_LOG` has a new row.
- `TRANSFER_SCHEDULE`/`AGENT_CONFIG.TRANSFER_START_DATE` advanced.

- [ ] **Step 4: Live form-sync test (needs the user's explicit go-ahead — edits live Google Forms)**

Click "3 · Sync nightly + weekly form dropdowns" and confirm both come back `OK`, then have the user open the actual nightly/weekly Google Forms and spot-check that the zone/area dropdowns reflect the applied roster.

- [ ] **Step 5: Update memory**

Record in `project-ccsm-transfer-flow.md` (memory): final commit hashes, which of the 4 live tests in Steps 2-4 actually ran vs. were deferred, and any selector/schema adjustments made along the way (especially in `imos_portal.py`'s login flow and `transfer_roster_transform.py`'s `RAW_COL_*`/`ZONE_NAME_MAP` — both were flagged as unverified-until-first-real-run in Task 6).

---

## Self-review

**Spec coverage:** Sheet schema (§1 of the spec) → Task 1 (with the AREA_LINEAGE correction noted up top). Engine + page port, no Drive (§2) → Tasks 2-5. IMOS Playwright port (§3) → Task 6. Cloud automation (§4) → Task 7. Testing/safety (the spec's own section) → guard tests in Task 2, `TransferBlocked`-gated apply in Task 3/4, explicit user-confirmed live steps in Task 8 rather than automated. Out-of-scope items (Drive, Provo repo changes, Tableau proxy) → touched nowhere in any task, confirmed by re-reading Tasks 1-8.

**Placeholder scan:** no `TBD`/`TODO`/"add appropriate handling" found. Two spots are genuinely open questions rather than placeholders, called out explicitly rather than hidden: (1) `AGENT_CONFIG`'s real column names, flagged in Task 3 with the exact command to check and the exact fallback behavior if they differ; (2) `imos_portal.py`'s login selectors and `transfer_roster_transform.py`'s raw-export column assumptions, both flagged in Task 6/8 as unverified until a real CCSM IMOS download happens — this mirrors Provo's own file, which carries the identical caveat in its own docstring for the identical reason (nobody has run it against IMOS with CCSM's login yet).

**Type consistency:** `transfer_engine.parse_roster/run_guards/build_diff/apply_transfer/rows_to_grid` signatures in Task 2 match their call sites in Task 3's `transfer_apply_service.py` exactly (same parameter names/order). `transfer_apply_service.preview()/apply()/TransferBlocked` in Task 3 match Task 4's page code. `transfer_bridge.form_sync()`/`FormSyncError` in Task 4 match `cct_formSync_`'s JSON response shape from Task 5 (`{ok, nightly:{status,msg}, weekly:{status,msg}}`). `run_cloud_job(job_type, workflow_file, dispatch_inputs, running_label)` in Task 7's Traslados wiring matches its signature in the copied `cloud_job_ui.py`. `write_transfer_import(rows)` in Task 6 (no `sheet_id` param) is only ever called from `imos_transfer_runner.py`'s own `_write_transfer_import`, which doesn't call the `sheets_client`-based version at all — confirmed no other file references the removed parameter.
