# PMG Compass — Roster, Access and Cleanup Plan

**Written 2026-10-05.** Zackary asked for the cleanup items and his own decisions
left from the app-wide audit (`AUDIT-IA-2026-08-22.md` → `PLAN-2026-08-22.md` →
`PLAN-2026-09-05-backlog.md`), and asked: *"What do the APs not have access to and
what does that mean for the app?"* He then chose: fill new areas' emails
automatically, an `AREA_LINEAGE` tab, and more companion columns.

Same convention as every plan here: findings (§0), decisions (§1), numbered
steps with one commit each (§2), and a STATUS table updated after every step.

---

## §0 — What the investigation found (2026-10-05, live sheet + code)

### 0.1 — Who the app thinks the leaders are

- **MISSION_ORG cannot name the President or the APs.** Its one `Is_AP=TRUE` row
  is La Marina 1, whose four missionaries (Phillips, Egbers, Heath, Blood) share
  one mailbox, `500407562@missionary.org`. No row is flagged `Is_MP`.
- **So sign-in rests on hand-typed addresses in `auth.py`** (`_ALWAYS_ALLOWED`):
  Presidente Gutierrez, Phillips and Egbers. Every transfer that changes an AP is
  a code edit + push + Reboot; until then the new AP is locked out, and the old
  one keeps access until someone removes him (Hyrum Turner, 2026-09-08).
- **The President receives no email from the system at all.**
  `CCSM_AgentMissionReport.gs` (Monday mission numbers) and the mission section
  of `CCSM_Agent1C.gs`'s letter go to every MISSION_ORG row flagged AP or MP —
  i.e. only the La Marina 1 shared mailbox.
- **The reverse gap:** `auth.is_leadership()` admits role `"leader"` (any
  `Is_ZL`/`Is_STL`/`Is_DL` row). Leaders sign in with their AREA mailbox, so 19
  mailboxes — and every companion who shares one — can open Traslados' *Apply a
  transfer*, Editar Envíos, Mantenimiento's settings, Centro de Acción and
  Sugerencias. The 2026-08-22 policy says the audience is the President and APs.

### 0.2 — New areas' email

`apply_transfer` creates a new area with blank `Companion1_Email` /
`Companion2_Email`, and the reminder agent mails only those columns, so a new
area is never asked to report and never shows as missing. `TRANSFER_IMPORT`
already carries `Area_Email` (104 of 105 rows; only `MLS Pucón` is blank). On
the live sheet today all 45 active areas match the roster's address exactly; 37
of 45 carry it in both columns, 8 only in Companion1.

### 0.3 — Area lineage

The 2026-09-07 transfer retired five areas and opened seven (derived from
`MISSION_ORG_SNAPSHOT` vs `MISSION_ORG`, matched by the companions who moved):

| New area | From | Kind | Evidence |
|---|---|---|---|
| Collipulli 1 | Collipulli | split | Parker Kimball |
| Collipulli 2 | Collipulli | split | Bruno Andrade |
| Galvarino 1 | Galvarino | rename | Gustavo dos Santos Ribeiro |
| Huepil & Tucapel | Huepil & Tucapel & Villa Obispo | rename | John Kearns |
| Purén y Los Sauces | Los Sauces | rename | Conner Miller |
| Villa Obispo 1 | Villa Obispo | split | Melina Lagraña |
| Villa Obispo 2 | Villa Obispo | split | Milagros Bravo |

DAILY_LOG is keyed by name, so each new area started from zero: Purén y Los
Sauces has 10 filed nights and Collipulli 2 has 13, under the sector-goal
rule's 14-night minimum, so both still borrow their zone's median.

The READ side already exists: `queries.get_lineage_for_successor` /
`get_lineage_for_retired_parent` / `get_lineage_visible_areas` and Desgloses'
`render_lineage_badge` / `render_lineage_marker` are wired
(`views/04_Desgloses.py:209,234,298`) and wait for an `AREA_LINEAGE` tab
(Provo schema: `Applied_At | Transfer_Date | Change_Type | Old_Areas | New_Area`).
Nothing writes it. `TRANSFER_SCHEDULE` now has three `Actual` rows, so the
badge's "last two transfers" window works.

### 0.4 — Companion columns

MISSION_ORG has two companion columns. **Both** multi-missionary areas today
have FOUR in IMOS: La Marina 1 (Phillips, Egbers, Heath, Blood) and Los Huertos
(Butterfield, +3). `transfer_engine._ROSTER_COPY_COLS` already carries slots 3-4;
`apply_transfer` writes whatever columns the tab's own header has, so adding
the columns to the sheet is what makes them flow.

### 0.5 — The cleanup

- **The 11 "pre-existing" test failures were misdiagnosed.** The notes said six
  asserted on Panel sections the redesign removed. Measured today: **9 are date
  time-bombs** — fixtures pinned to 2026-07-27…08-05 and read through windows
  measured from `today` (`test_effort_reporting_scope` ×3,
  `test_renders_ccsm_with_data` ×6). The other **2 test a Metas section that no
  longer exists** ("Mission Goals", deleted in Step 7 §7.4a), so the whole file
  passes or fails vacuously. Baseline today: 11 failed / 1808 passed / 1 skipped.
- **Section numbers drifting on Desgloses is moot**: no page passes
  `numbered=True` since the 2026-09-18 redesign.
- **Sheet capacity, measured:** 2.25M grid cells = 22.5% of the 10M cap; 1.5M of
  them empty grid. **Not trimmed, on purpose** — see §1 D8.
  `NIGHTLY_FORM_RAW` is the real constraint: 272 columns, ~950 rows a month at
  the pilot's 45 areas = ~260k cells/month.
- **Ownership:** `COMPASS_CCSM` is owned by `ccsm.pmg.compass@gmail.com` (the
  system account) and shared only with the dashboard's service account.

---

## §1 — Decisions

Zackary's (2026-10-05), all four the recommended option:

- **D1 — A leadership tab.** `MISSION_LEADERSHIP`: `Name | Email | Role | Active
  | Notes`, Role `president` or `assistant`. Sign-in, goal-setting and the
  leadership pages read it; the Monday mission report and Agent1C's mission
  letter send to it. Edited on Traslados. Changing an AP = editing one row.
- **D2 — Leadership pages are President, APs and the owner only.** Role
  `"leader"` (ZL/STL/DL) no longer passes `is_leadership()`. Sign-in stays open
  to every area mailbox (his 2026-08-22 decision is untouched).
- **D3 — Lineage carries goals history plus a badge.** A new area that has not
  yet filed enough nights of its own counts its parent's nights from before the
  change — in the Monday sector-goal job, the Metas REC pill and the Metas
  transfer-goal REC. Charts are not stitched.
- **D4 — Companion 3 and 4.**

Mine, stated so they can be overruled:

- **D5 — Email fill.** Blank email on an active area after apply → the roster's
  `Area_Email`, in `Companion1_Email`, and in `Companion2_Email` when there is a
  second companion (the 37-of-45 convention). A NON-blank address that differs
  from the roster is **kept and flagged**, never overwritten — zero cases today,
  and a hand-set address may be deliberate.
- **D6 — Lineage rows are proposed, never guessed silently.** At Preview, a new
  area that shares a companion with an area being deactivated in the same apply
  is proposed as its successor; the user confirms each row before Apply writes
  it. Traslados also gets an editor for the tab, for corrections and backfill.
- **D7 — A merged area inherits all its parents' nights**, which the pace rule
  (total ÷ nights filed × 7) turns into roughly their average — a merge is one
  companionship, not the sum of two.
- **D8 — No blanket grid trim.** Trimming rows to the data would make every Apps
  Script writer that appends with `getRange(lastRow + 1, …)` throw on its next
  run (only `appendRow` extends the grid), and the sheet sits at 22.5% of the
  cap. The real fix is archiving old `NIGHTLY_FORM_RAW` rows — queued as its own
  project (§3).
- **D10 — (Zackary, 2026-10-05, after the push) The mission report goes ONLY
  to MISSION_LEADERSHIP** — no fallback to the AP area's shared mailbox, and an
  empty tab sends nothing and logs an ERROR. **That shared mailbox gets its
  district's section of the weekly letter, as district leader**, instead of the
  mission section: an `Is_AP` row is treated as its district's DL in
  `a1c_buildPeopleMap` (IMOS gives La Marina 1 only the calling "AP", so
  MISSION_ORG never flags it `Is_DL`). The President keeps the report.
- **D11 — (Zackary, 2026-10-05) D9 is REVERSED.** The AP area's shared mailbox
  no longer opens the leadership pages or sets goals: "president" and
  "assistant" come only from MISSION_LEADERSHIP, and an `Is_AP` / `Is_MP`
  MISSION_ORG row's mailbox is a "leader" (it still signs in). Centro de
  Acción's task roster is the tab too. LEADERSHIP_TASKS does not exist yet, so
  no task was assigned to the shared mailbox.
- **D9 (superseded by D11)** — The MISSION_ORG `Is_AP` / `Is_MP` flags still count as a leadership
  role** alongside the tab, so nothing that works today stops working. The
  shared La Marina 1 mailbox therefore keeps leadership access — the same as
  before this plan.

---

## §2 — Steps (one commit each)

| # | Step | Touches |
|---|---|---|
| C1 | Tests: date fixtures relative to today; Metas duplicate-key test retargeted at the nightly grid that survives | `tests/test_effort_reporting_scope.py`, `tests/test_renders_ccsm_with_data.py`, `tests/test_goals_duplicate_metric_keys.py` |
| C2 | Stale notes: backlog §2 + STATUS, PLAN-2026-08-22 §3.3/§3.4 | plan files |
| R1 | Apply fills new areas' email from the roster; preview says so; mismatches flagged | `transfer_engine.py`, `transfer_apply_service.py`, `12_Traslados.py`, tests |
| R2 | Companions 3 and 4 shown wherever a roster lists missionaries | Traslados roster table, `CCSM_AgentScores.gs` names, design_system area card, chat context |
| R3 | `MISSION_LEADERSHIP`: reader, roles, sign-in, D2's narrower `is_leadership` | `queries.py`, `auth.py`, tests |
| R4 | Traslados → "Liderazgo" section: edit the tab; transfer preview warns when an assistant is no longer in the AP area | `12_Traslados.py`, `es.py` |
| R5 | Apps Script: mission report + Agent1C mission letter go to `MISSION_LEADERSHIP` (MISSION_ORG flags as fallback) | `CCSM_AgentMissionReport.gs`, `CCSM_Agent1C.gs`, node tests |
| R6 | `AREA_LINEAGE` store + Preview proposals + Apply writes confirmed rows + editor | `transfer_engine.py`, `transfer_apply_service.py`, `queries.py`, `12_Traslados.py` |
| R7 | Goals inherit a parent's nights (sector goals + both REC pills) | `area_goals.py`, `area_goals_runner.py`, `queries.py`, `02_Metas.py` |
| S | Live-sheet writes, each approved: seed `MISSION_LEADERSHIP`; add `Companion3_Name`/`Companion4_Name` to MISSION_ORG; create `AREA_LINEAGE` with §0.3's seven rows | live sheet |

**Deploy order matters.** R3 removes the three hand-typed leaders from
`auth.py`. Push it only after `MISSION_LEADERSHIP` is seeded on the live sheet,
or the President and both APs are locked out until it is. After the push:
**Reboot** (it touches `app/`), and re-paste `CCSM_AgentMissionReport.gs`,
`CCSM_Agent1C.gs` and `CCSM_AgentScores.gs` into Apps Script.

---

## §3 — Not in this plan

- **Archive old `NIGHTLY_FORM_RAW` rows.** ~260k cells/month at 45 areas; the
  sheet reaches the 10M cap in roughly a year and a half at pilot size, sooner
  if more zones go live. Needs its own audit: which readers use the raw tab
  (submission timeliness, Editar Envíos) and how far back.
- **Ownership** of `COMPASS_CCSM` (a gmail system account) is Zackary's call
  for the handoff; nothing here changes it.

---

## STATUS

| Step | State | Commit |
|---|---|---|
| C1 | **DONE** — suite green (was 11 failed): 9 date time-bombs, 2 tests of a deleted section | `2f9f898` |
| C2 | **DONE** | `dd5c675` |
| R1 | **DONE** | `4a90f86` |
| R2 | **DONE** (+ `CCSM_AgentScores.gs` re-paste) | `e2c7e1f` |
| R3 | **DONE** | `319c989`, RAW writes `ddf5a3d` |
| R4 | **DONE**, verified in the local app; two-row layout after a live check | `2ae082e`, layout `2cecc00` |
| R5 | **DONE** (+ re-paste `CCSM_AgentMissionReport.gs`, `CCSM_Agent1C.gs`) | `53421b0` |
| R6 | **DONE**, verified in the local app (badge, closed-area card, Linaje table) | `693ded6` |
| R7 | **DONE** — live: Collipulli 2 and Purén y Los Sauces now source "lineage" | `b50ea08` |
| S | **DONE 2026-10-05**, all three approved by Zackary: MISSION_LEADERSHIP (3 rows), MISSION_ORG O:P companions 3-4 (La Marina 1, Los Huertos), AREA_LINEAGE (7 rows). MISSION_ORG still 108 rows. | live sheet |

Also found and fixed: `test_action_center_maintenance.py` replaced
`auth.is_leadership` without restoring it, which made everyone leadership for
every later test (`fbb9a16`).

**Not changed, noted:** five Apps Script node suites (`test_agent5b6`,
`test_ccsm_data`, `test_ccsm_helpers`, `test_harness_selftest`,
`test_quota_guards`) fail identically with and without this plan's changes.

**What takes effect when:**
- On push + Reboot: sign-in and leadership pages read MISSION_LEADERSHIP; the
  Liderazgo section, lineage proposals/editor and Spanish badge go live.
- On re-paste of the three .gs files: the President and both APs get the
  Monday mission report and the weekly letter's mission section under their own
  addresses; SCORES lists all four companions.
- Monday 2026-10-12, 12:00 UTC: the first sector-goal job that reads
  AREA_LINEAGE (this week's GOALS_CONFIG was written this morning without it).
  A goal still moves at most 10% a week from last week's, so the change arrives
  gradually.
- 2026-10-19 transfer: Preview proposes lineage for whatever opens; new areas
  get their mailbox from the roster; Preview warns if an assistant left the AP
  area — update Liderazgo the same day.
