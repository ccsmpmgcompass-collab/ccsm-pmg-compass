# PLAN — Transfer day: bringing PMG Compass onto cycle 2026-6

**Date:** 2026-09-08 (Tuesday). **Cycle 2026-6 began Monday 2026-09-07.**
Written after a live probe of COMPASS_CCSM, per the convention in
`PLAN-2026-08-22.md` / `PLAN-2026-09-05-backlog.md`: findings first, then
numbered steps with acceptance criteria.

Everything below was verified against the live sheet on 2026-09-08, not
inferred from code.

---

## §0 — What the live sheet says right now

| Thing | Live value | Should be | Status |
|---|---|---|---|
| `AGENT_CONFIG.TRANSFER_START_DATE` | **2026-07-27** | 2026-09-07 | BROKEN — one cycle behind |
| `TRANSFER_SCHEDULE` `2026-6` Status | **Scheduled** | Actual | WARN — cosmetic now, matters next cycle |
| `TRANSFER_IMPORT` | 97 areas, pulled **2026-08-09** | this week's roster | BROKEN — stale, pre-transfer |
| `MISSION_ORG` active teaching areas | **43**, in **4 zones** | see §2 decision | DECISION NEEDED |
| `MISSION_ORG` inactive teaching areas | **58**, in 6 zones | see §2 decision | DECISION NEEDED |
| `AREA_TRANSFER_GOALS` | 1 row — Los Huertos, cycle **2026-5** | goals for 2026-6 | BROKEN — nothing set for the new cycle |
| `runAgent2` (goal recalibration) | manual, once per transfer | run after §1 | PENDING |
| `DAILY_LOG` | 945 rows, through 2026-09-07 | — | OK |
| `WEEKLY_KI` | 138 rows, weeks 08-09 → 09-13 | — | OK |

**Good news first:** the first live goal save *did* happen —
`AREA_TRANSFER_GOALS` exists and holds Los Huertos for cycle 2026-5. That
long-open item from `PLAN-2026-09-05-backlog.md` §7 is closed. The tab's
header and shape are correct and `read_tab(header_marker="transfer_start")`
parses it.

### §0.1 — The thing that is wrong *this minute*

`TRANSFER_START_DATE` is still `2026-07-27`. `CCSM_Agent1A`, `CCSM_Agent2`,
`CCSM_Agent3` and `CCSM_Agent5A` all measure "since transfer" from that key
(`CCSM_Agent3.gs:120`, `CCSM_Agent2.gs:170`). So every
`LIVE_SNAPSHOT.<metric>_transfer` column, and the whole "Area Performance This
Transfer" table on Traslados, is currently summing **six weeks of the previous
cycle plus this one**.

The Traslados page already detects this and is showing the warning at
`views/12_Traslados.py:150-167` ("TRANSFER_SCHEDULE says this transfer began 7
sep, but AGENT_CONFIG's TRANSFER_START_DATE still says 27 jul"). Open the page
and you will see it. That warning is the symptom; §1 is the fix.

---

## §1 — Two defects in the Apply path, both confirmed by simulation

The Traslados "2 · Apply" button is supposed to do four things
(`app/ingestion/transfer_apply_service.py:116-117`): merge MISSION_ORG, advance
the schedule, set `TRANSFER_START_DATE`, and log. **The middle two are broken
on CCSM's data.** Both were simulated against the live grid; neither is a
theory.

### §1a — `_advance_schedule` would corrupt TRANSFER_SCHEDULE

`app/ingestion/transfer_apply_service.py:126-157`.

Two independent failures compound:

1. **Line 144 looks for `Status == "Planned"`.** CCSM's rows say
   **`Scheduled`**. No row matches, so it falls through to the append branch.
2. **Line 150 filters with `.isdigit()`.** CCSM's `Transfer_Number` values are
   `2026-4` … `2026-8` — and the live cells are in fact *date-typed* (serials
   46113…46235, displayed by a `yyyy-m` number format). Nothing is a bare
   digit, so `nums` is empty and the new number becomes `(0) + 1`.

Simulated against the live five-row grid, Apply would **append**:

```
['1', '2026-09-08', '', 'Actual']
```

A row numbered `1`, dated *today* rather than the Monday, with a **blank
Weeks** — appended to the tab that `transfer_window()` uses to decide which
cycle every period-scoped page is showing (Desgloses, Panel rankings, Puntajes,
Metas' cycle picker). `transfer_rows()` takes the latest row whose start has
arrived, so that junk row would immediately become "the current transfer" with
an empty length.

**This is the one that must not be allowed to happen.**

Note the pure engine already has the correct helper —
`transfer_engine.next_transfer_number()` (`transfer_engine.py:292`) was written
on 2026-09-05 precisely to fix the `int("2026-4")` bug, with a docstring
explaining it. The apply service never got wired to it and carries its own
second copy, which is exactly the duplication `views/12_Traslados.py:88-92`
warns against. (`transfer_engine.next_schedule_update():320-328` has the same
`"Planned"` assumption but is currently unused.)

### §1b — `_set_transfer_start_date` writes the wrong day

`app/ingestion/transfer_apply_service.py:159-176` writes **`today`**
(2026-09-08). The cycle began **2026-09-07**. One day off, and the consequences
are not cosmetic:

- Monday 2026-09-07's `DAILY_LOG` rows fall outside the transfer window, so
  every `*_transfer` total silently loses day one.
- It re-triggers the very mismatch warning from §0.1, because
  `TRANSFER_SCHEDULE` says 09-07 and the config would say 09-08.

The correct value is the **cycle's scheduled start date**, which the app
already treats as the source of truth everywhere else (`transfer_helpers.py:13`
— "the current transfer is the latest row whose start date has arrived").

### §1c — Recommended fix

Rewrite both functions to key off the cycle the schedule already describes,
rather than off `today`:

- `_advance_schedule`: find the row whose `Start_Date` is the current cycle's
  start; flip **only its Status** to `Actual`. Do **not** overwrite
  `Start_Date` — the pre-scheduled Monday is correct and the whole app keys on
  it. Only append when no row covers today, and use
  `transfer_engine.next_transfer_number()` for the label instead of the local
  `isdigit()` block.
- `_set_transfer_start_date`: take the cycle start as an argument and write
  that, not `date.today()`.
- Accept `"Scheduled"` as well as `"Planned"` wherever status is read.

Small, well-scoped, and covered by the existing
`tests/test_transfer_engine.py` / `test_transfer_number_parses.py` patterns.

### §1d — Pilot-zone scoping (added for the §2 decision)

`transfer_engine.filter_roster_to_zones()` cuts the parsed roster to
`AGENT_CONFIG.PILOT_ZONES` (comma-separated) before anything is compared or
written. Empty or missing means the whole mission, so this is inert for a
mission that never pilots.

The failure mode it has to defend against is a **spelling drift**: if
`PILOT_ZONES` said "Los Angeles Norte" and the export spelled it "Los Ángeles
Norte", the eleven areas in that zone would be absent from the filtered roster
while still active in MISSION_ORG — and `apply_transfer` would deactivate every
one of them. So any configured zone matching no roster row is reported by
`preview()` and makes `apply()` raise `TransferBlocked` outright, rather than
leaving the 30% deactivation guard as the only thing in the way.

The Roster Update tab states the scope above the buttons, before anything is
clicked, and says "whole mission" just as plainly when the key is unset.

> **Deploy note.** `app/ingestion/transfer_apply_service.py` is outside
> `views/`, so per `dashboard/DEPLOYING.md` a push is **not** enough —
> **reboot the app** (Manage app → ⋮ → Reboot) or the new page will run against
> the old module.

---

## §2 — The decision: 4-zone pilot, or the whole mission?

This is the one thing in this plan that is genuinely your call, and it changes
what Apply does.

**`MISSION_ORG` currently has 43 active teaching areas in 4 zones** — Angol,
Los Ángeles Norte, San Pedro, Temuco Ñielol. The other **58 areas across 6
zones** (Arauco, Camilo, Los Ángeles Sur, Temuco Cautín, Victoria, Villarrica)
are `Active=FALSE`, with their companion names and area emails preserved.

This is not corruption — it is consistent across the whole system:

- `DAILY_LOG` since 2026-08-25: 425 rows, **42 distinct areas, those same 4 zones**.
- `LIVE_SNAPSHOT`: 43 rows, those same 4 zones.
- `TRANSFER_LOG`: form sync on **2026-08-19** reports "**4 zones verified**",
  where every sync on 08-09 reported "11 zones".

So the mission was deliberately narrowed to a 4-zone pilot on 2026-08-19, by
hand (there is no `applyTransfer` entry after 2026-08-09).

**`TRANSFER_IMPORT`'s 97 areas span 11 zones.** `apply_transfer()` sets
`Active = "TRUE"` for every area present in the roster
(`transfer_engine.py:224`), so **applying a fresh full pull reactivates all 58
areas and puts the mission-wide roster back**. The form dropdowns would go back
to 11 zones on the next sync, and every companionship in those 6 zones would
start being asked to report.

### DECIDED 2026-09-08 (Zackary): stay on the four pilot zones

> *"Stay on the four pilot zones, but I know a bunch of new areas got opened
> this last transfer. There should only be 10 zones and 102 areas or so total,
> but still only keep active the areas and new areas of San Pedro, Los Angeles
> Norte, Angol, and Temuco Ñielol."*

So: the four zones stay, and **a newly opened area inside one of them must
still arrive.** That rules out hand-trimming `TRANSFER_IMPORT` — trimming a
97-row tab down to four zones every six weeks is exactly where a new area gets
missed, and it has to be redone every cycle.

**Built instead (2026-09-08):** a zone filter driven by a new `AGENT_CONFIG`
key, `PILOT_ZONES` — see §1d. Existing areas in the four zones update, new
areas in them are added, and every area in the other six zones is left exactly
as it is, including the 58 already inactive. Clearing the key goes mission-wide,
so option A remains one cell away whenever the pilot ends.

---

## §3 — The steps

Ordering matters: the roster must be right before goals are set against it, and
`TRANSFER_START_DATE` must be right before `runAgent2` recalibrates against it.

### Step 1 — Land the §1 fix, then reboot — **CODE DONE 2026-09-08**

1.1 ~~Fix `_advance_schedule` and `_set_transfer_start_date` per §1c~~ **done**,
    plus the §1d pilot filter and 16 new tests in
    `dashboard/tests/test_transfer_apply_cycle.py`.
1.2 ~~Run the suite~~ **done** — 977 passing, **13 failing**, exactly the
    documented baseline and the same test names.
1.3 ~~Commit, push~~ **done** — `4458616`, `805ca79`, `19f21df` on `main`.
1.4 **Reboot the Streamlit app** — https://ccsm-pmg-compass-dvqpedw6bqixxscth8zapn.streamlit.app/
    (Manage app → ⋮ → Reboot). ← *the only part left, and it is Zackary's.*
1.5 ~~Set `AGENT_CONFIG.PILOT_ZONES`~~ **done 2026-09-08** —
    `Angol, Los Angeles Norte, San Pedro, Temuco Ñielol`, derived from
    MISSION_ORG's own active zones and checked against TRANSFER_IMPORT's
    spelling rather than typed by hand.

**Acceptance:** Traslados loads; the Roster Update tab's first caption reads
"Scoped to 4 pilot zone(s): Angol, Los Angeles Norte, San Pedro, Temuco
Ñielol".

> **Shortcut if you would rather not wait:** skip Step 1 and do Steps 2-4
> instead, then repair the two cells by hand (Step 5.1 + 5.2). The *only* thing
> you must not do is click **2 · Apply** with the current code, because of §1a.

### Step 2 — Pull a fresh roster

2.1 Traslados → **Roster Update** → **0 · Pull roster from IMOS (cloud)**.
    Wait for the success message.

**Do not skip this.** `TRANSFER_IMPORT` holds the **2026-08-09** pull — last
cycle's companionships. Applying it would write the pre-transfer roster over
MISSION_ORG.

**Acceptance:** `CLOUD_JOB_STATUS` gains a `transfer_pull` row with
`status=SUCCESS`; the page's caption reports the new row count.

### Step 3 — Preview, then apply

3.1 **1 · Preview.** Read all four groups: New / Deactivating / Changed /
    Reactivating.
3.2 Sanity-check against §2. With `PILOT_ZONES` set you should see **no
    Reactivating entries at all** — the six non-pilot zones are filtered out
    before the diff is built. New areas opened in the four pilot zones appear
    under **New**; that is the group to read carefully this cycle.
3.3 If the deactivation guard blocks (>30% of active areas would go inactive —
    `transfer_engine.py:DEACTIVATION_GUARD_PCT`), **stop and re-read the diff**
    before ticking the override. A blocked guard after a normal transfer
    usually means a bad pull, not a real mission-wide closure.
3.4 **2 · Apply.**
3.5 Note any "New areas need an email address added by hand" warning and fill
    `Companion1_Email` in `MISSION_ORG` for each — new areas are appended with
    blank email columns (`transfer_engine.py:apply_transfer`), and an area with
    no email gets no nightly reminder.

**Acceptance:** `TRANSFER_LOG` gains an `applyTransfer (CCSM dashboard)` row;
`MISSION_ORG` active count matches what Preview said; `MISSION_ORG_SNAPSHOT`
holds the pre-apply grid (written before any mutation — this is your undo).

### Step 4 — Sync the form dropdowns

4.1 Traslados → **3 · Sync nightly + weekly form dropdowns**.

**Run this from the deployed app, not local dev.** `form_sync()` needs
`TRANSFER_WEBAPP_URL` / `TRANSFER_WEBAPP_SECRET`
(`app/integrations/transfer_bridge.py:23-30`), and the local
`dashboard/.streamlit/secrets.toml` **does not have them** — locally it will
raise `FormSyncError`. Production evidently does have them: the 2026-08-19 sync
succeeded.

4.2 Check `TRANSFER_LOG`'s two new rows say `OK`. Both failure modes from
    August are worth recognising if they come back:
    - `You do not have permission to call FormApp.openById` → the Apps Script
      deployment needs the Forms scope re-authorised.
    - `Could not find the zone ("zona") list item` → the Spanish weekly form's
      zone question was renamed; the finder at
      `CCSM_TransferHelpers.gs:cct_readFormStructure_` matches on the title.

**Acceptance:** `TRANSFER_LOG` shows `nightly form sync complete. N zones
verified.` and the same for weekly, where **N must be 4**. If it says 11, the
pilot filter did not apply — stop and check `PILOT_ZONES` before letting the
forms go out.

### Step 5 — Set the transfer window straight — **DONE 2026-09-08**

Done ahead of the roster steps rather than after them, because §0.1 was wrong on
the live app every minute it stood. Both writes are idempotent, so the Apply in
Step 3 re-confirming them changes nothing.

5.1 ~~`AGENT_CONFIG.TRANSFER_START_DATE`~~ **`2026-07-27` → `2026-09-07`**.
5.2 ~~`TRANSFER_SCHEDULE` row `2026-6` Status~~ **`Scheduled` → `Actual`**
    (Start_Date untouched).

Verified after the write: current cycle resolves to **2026-6, 2026-09-07 →
2026-10-18, week 1 of 6**; no junk row on the tab; schedule still covers two
cycles ahead.

On 5.2: `transfer_window()` does not read Status
(`transfer_helpers.py:13-17`), so nothing on the dashboard changes today. It
matters **next** cycle — `CCSM_Agent2.gs:a2_loadRealTransferHistory_` builds
its "Previous / 2 Ago" comparison periods from `Actual` rows only, falling back
to a fixed 42-day guess otherwise. Leaving 2026-6 as `Scheduled` quietly
degrades the next recalibration. (Checked: the `Start_Date` cells are real
date-typed cells, so that function's `d instanceof Date` test passes.)

**Acceptance:** the Traslados mismatch warning from §0.1 is **gone**, and the
header reads "Transfer 2026-6 · Week 1 · 7 sep to 18 oct".

### Step 6 — Recalibrate the nightly goals

6.1 Open the COMPASS_CCSM Apps Script editor and run **`runAgent2`** once.

This is deliberate design, not an oversight: `CCSM_Setup.gs:40,52` document
`runAgent2` as **MANUAL — run once per transfer**, and `CCSM_Setup.gs:756`
actively warns if someone schedules it. It recalibrates each area's nightly
metric goals from the last three transfer windows into `GOAL_RECALIBRATION`.

**Run it after Step 5**, not before — it reads `TRANSFER_START_DATE` at
`CCSM_Agent2.gs:170` and would otherwise recalibrate against the old window.

**Acceptance:** `AGENT_RUN_LOG` gains an `Agent2` SUCCESS row;
`GOAL_RECALIBRATION` (currently an empty header) has rows.

### Step 7 — Set the seven Key Indicator goals for 2026-6

7.1 Metas → **Area Goal Customization**. The Cambio picker defaults to the
    cycle containing today (`views/02_Metas.py:292-313`), which is now
    **2026-6 · 7 sep – 18 oct**. Confirm that is what is selected.
7.2 Set goals per area. The REC badge recommends from each area's completed
    weekly history, rounded once and clamped for roster-capped metrics.
7.3 Use the bulk button to apply recommendations across a zone rather than
    typing 43 (or 97) areas by hand.

`AREA_TRANSFER_GOALS` holds **one row** — Los Huertos, cycle `2026-5`, which
ended 2026-09-06. **No area has a goal for 2026-6.** Until they do, Metas'
"Resumen de la misión" shows "No area has set a goal for 2026-6 yet" and every
KI goal bar on Desgloses and the Panel has nothing to draw against.

**Acceptance:** `AREA_TRANSFER_GOALS` gains rows with
`transfer_start = 2026-09-07`; Metas' cycle summary renders totals instead of
the empty-state notice.

---

## §3.6 — What the real Preview turned up (2026-09-08), and the four things it leaves open

The pull ran and the diff was read: **7 new areas, 5 deactivating, 38 changed,
0 reactivating** — the pilot filter held. All five "deactivations" are renames
or splits, not closures, and they map cleanly onto the seven new areas:

| Closing | Becomes |
|---|---|
| Collipulli | Collipulli 1 + Collipulli 2 |
| Villa Obispo | Villa Obispo 1 + Villa Obispo 2 |
| Huepil & Tucapel & Villa Obispo | Huepil & Tucapel |
| Los Sauces | Purén y Los Sauces |
| Galvarino | Galvarino 1 |

Net **43 → 45 active areas**. The guard did not fire (5 of 43 = 12%, under the
30% threshold).

**F1 — The 7 new areas have no email, and will silently stop reporting.**
`apply_transfer` preserves existing email columns but creates new areas with
blank ones, and `CCSM_AgentReminder.gs:584` sends only to `Companion1_Email` /
`Companion2_Email`. Until those seven are filled in on MISSION_ORG they get no
nightly reminder — and the failure is invisible, because an area that is never
asked simply never appears in the missing-report counts as a *drop*. **This is
the highest-value follow-up on this page.**

**F2 — Renamed areas start from zero history.** DAILY_LOG and WEEKLY_KI are
keyed by area NAME, so Collipulli's record stays under "Collipulli" while
"Collipulli 1" begins empty. Nothing is lost and nothing carries forward.
Consequences: the seven get **no REC badge** on Metas (the recommendation
averages completed weekly history), their goal boxes must be set by judgment,
and any transfer-over-transfer comparison for them starts fresh. Worth deciding
one day whether a rename should carry its predecessor's history — there is no
`AREA_LINEAGE` tab on this sheet, which is exactly what one would be for.

**F3 — Four-person companionships lose two names.** La Marina 1 (Phillips,
Egbers, Heath, Blood) and Los Huertos (Butterfield, Laiton, Monroe) arrive with
Companion3/Companion4 populated, but MISSION_ORG has only two companion columns,
so `rows_to_grid`'s headers-driven merge drops slots 3 and 4. Reporting is
unaffected — reminders go to slots 1 and 2 and the form is answered per AREA —
but those missionaries are invisible in the roster view and in any headcount
taken from MISSION_ORG. Adding `Companion3_Name`/`Companion4_Name` columns to
the tab would fix it; `_ROSTER_COPY_COLS` already carries them.

**F4 — The AP seat is filled by hand, every transfer.** Presley Egbers moved
into La Marina 1 (the `Is_AP` area) replacing Hyrum Turner, and was added to
`_ALWAYS_ALLOWED` on 2026-09-08. This will recur: MISSION_ORG's `Is_AP` row
carries the shared mailbox `500407562@missionary.org` for every companion in it,
never the personal address an assistant signs in with, so **every transfer that
changes an assistant locks the new one out until someone edits `auth.py`.** The
durable fix is §4.2 — put the real sign-in addresses in MISSION_ORG.

## §4 — Housekeeping this transfer surfaces

**4.1 — AP1's access. HALF DONE 2026-09-08 (`19f21df`).** Zackary confirmed
Hyrum Turner went home this transfer; his address is out of `_ALWAYS_ALLOWED`
and `_GOAL_SETTERS`. **The incoming AP is still locked out** and cannot be added
from the roster: MISSION_ORG's one `Is_AP` row carries the shared mailbox
`500407562@missionary.org` for *both* companions, never the
`firstname.lastname@missionary.org` address an AP actually signs in with. Once
the Step 2 pull names him, that address goes on the line the comment marks.

**4.2 — MISSION_ORG still carries no leadership sign-in addresses.** Probed
again today: no row is flagged `Is_MP`, and the only `Is_AP=TRUE` row holds a
missionary-ID mailbox. Every role-derived check in the app is therefore wrong
about the president and both assistants, and they reach the app only through
the hardcoded `_ALWAYS_ALLOWED` list. A transfer is the natural moment to fix
the sheet. Still your call, unchanged from 2026-09-05.

**4.3 — Schedule coverage is fine.** `TRANSFER_SCHEDULE` runs through
**2027-01-10**. The standing rule from `PLAN-2026-09-05-backlog.md` — keep two
rows ahead — is satisfied. Next row due **before 2027-01-10**, and the open
question of whether the successor to `2026-8` is `2026-9` or `2027-1` is still
unanswered.

**4.4 — `Transfer_Number` cells are date-typed.** Sheets coerced `2026-4` into
a real date (serial 46113 = 2026-04-01) displayed by a `yyyy-m` format.
Harmless today — nothing keys on the number
(`goals_queries.py`, "Why keyed by the START DATE") — but worth knowing before
anyone tries to sort or parse that column.

**4.5 — Weekly reporting dipped.** `WEEKLY_KI` has 35-37 areas for the weeks
ending 08-16 / 08-23 / 08-30, then **28** for 09-06. Transfer week, most
likely. Worth a second look next Sunday before reading anything into it.

---

## §5 — The short version

1. ~~Fix the two Apply defects (§1), push, set `PILOT_ZONES`, fix the transfer
   window, drop the departed AP1~~ — **all done 2026-09-08**. **Reboot the app.**
2. Pull a fresh roster — the one on the sheet is from 2026-08-09.
3. Decide §2 (4 zones or 11), preview, apply, fill in new-area emails.
4. Sync the form dropdowns **from the deployed app**; confirm the zone count.
5. ~~`TRANSFER_START_DATE` → `2026-09-07`; `2026-6` → `Actual`~~ — done.
6. Run `runAgent2` once, manually, in Apps Script.
7. Set the 2026-6 goals on Metas.
8. ~~Check whether AP1 has gone home~~ — he did; ~~add the new AP~~ Presley
   Egbers added 2026-09-08.
9. **Fill in `Companion1_Email` for the 7 new areas** — §3.6 F1, the one that
   silently stops them reporting.
