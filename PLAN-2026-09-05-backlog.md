# PMG Compass — Backlog Plan

**Written 2026-09-05.** Covers the four-item queue agreed after the Desgloses
progression build closed (`PLAN-2026-09-03-desgloses-progression.md`).

One file rather than the usual paired `AUDIT-*` + `PLAN-*`, deliberately: three
of the four items were already diagnosed in `PLAN-2026-08-22.md`, and the only
genuinely new investigation is §0 below. Padding that into a separate audit
document would add pages without adding a finding.

---

## §0 — What the audit found (2026-09-05)

Two of the four items were **materially misdiagnosed** in the backlog notes.
Both corrections shorten the work.

### 0.1 — The effort/exchanges zeros are a dashboard bug, not a data gap

The backlog recorded this as "almost certainly a parse/write gap in the nightly
agent." **It is not.** Probed live 2026-09-05, `DAILY_LOG` holds 869 rows and
both columns are correctly populated:

| Column | Live values |
|---|---|
| `effort` | `Todo` ×515, `La mayor parte` ×303, `Algo` ×51 — **every row answered** |
| `exchanges` | `TRUE` ×155, blank ×714 |

The Apps Script chain is doing exactly what it was designed to do.
`QUESTIONS_CONFIG` types them `YESNO` and `CHOICE` (`Q-N-002`, `Q-N-023`),
`a3_buildDailyRecords` (`CCSM_Agent3.gs:443`) seeds those two types as `''`
rather than `0`, and writes the form's own Spanish word through. Both
`CCSM_Agent1A.gs:566` and `a3_buildLiveSnapshot`'s docstring already state in
comments that these columns are non-numeric by design and parse to 0 wherever
they are summed.

The zero is minted on the **Python** side. `get_daily_log()`
(`dashboard/app/db/queries.py:966`) runs every metric column through `_num()`,
which coerces `"Todo"` to `NaN` and then fills it with `0`
(`queries.py:54`) — so by the time a value reaches a page, a CHOICE answer is
indistinguishable from a real measured zero.

**The guard for this already exists and is already documented.**
`non_numeric_metrics()` (`dashboard/app/config/metric_catalog.py:236`) returns
exactly these keys, and its docstring warns that "an area that answered 'Todo'
every single day would otherwise be scored as having given no effort at all."
Five call sites honor it — `flavor_loader.py:190`, `queries.py:2417`,
`06_Puntajes.py:802`, `11_Informes.py:197`, `12_Traslados.py:205`.

**Desgloses is the one page that does not.** `breakdowns_engine.py:2011` takes
the whole `metric_options()` catalogue unfiltered, so `effort` and `exchanges`
enter the metric vocabulary and land on cards as a measured `0`.

The correct read path also already exists: `get_daily_effort_log()`
(`queries.py:986`) returns the raw Spanish text, and
`app/analytics/effort_breakdown.py` already counts it properly for the Panel,
denominator-first, with the "answered vs. did not file" split intact.

**So this is a code-only fix on one page, reusing machinery that is built,
tested and in production elsewhere.** No sheet write, no Apps Script change.

### 0.2 — Phase 3.3's backfill is already done

`PLAN-2026-08-22.md` §3.3 is written as pending. Probed live, both halves have
landed:

- `TABLEAU_BAPTISMS` — 33 rows, 31 monthly `MISSION` rows (`2024-01` onward),
  stamped `_uploaded_by:backfill:tableau-pdfs`, `_uploaded_at:2026-08-23`.
- `TABLEAU_DETAIL` — not a sheet tab, as decided in §3.2g; it is a Drive blob,
  and `AGENT_CONFIG.TABLEAU_DETAIL_FILE_ID` is set to
  `1yzxOAju1qaShMs5VL3Ri5ywQzwXlnOcl` (commit `363f4f3`).

What §3.3 still owes is only its **acceptance check** — confirm the three
consumers actually woke up. That is Step 3 below, and it is verification work,
not a build.

### 0.3 — Confirmed unchanged

- `TRANSFER_SCHEDULE` — 3 rows, last is `2026-6` / `2026-09-07` / `6` /
  `Scheduled`, ending **2026-10-18**. Step 1 stands.
- `GOALS_CONFIG` — still empty (not even a header row).
- `MISSION_GOALS`, `AREA_MONTHLY_GOALS`, `AREA_TYPE_EXPECTATIONS` — **still do
  not exist.** No goal has ever been saved in production. §4.2 stands.
- `TABLEAU_BAPTISMS.zone` — `MISSION` on all 31 rows. The by-zone chart is
  still blocked on a per-zone export.
- `SUGGESTIONS` (1 response) and `QA_FORM_RESPONSES` (1 response) hold **the
  same** submission — Hermana Wood, 2026-08-22. So the Form *is* linked and the
  copy path *does* run. §4.3 shrinks to "confirm the app reads the populated
  one," a five-minute check rather than an investigation.

---

## §1 — Steps

One commit per step, as with every queue on this project.

### Step 1 — `TRANSFER_SCHEDULE`: add the next cycle *(DATED — before 2026-10-18)*

**Why it is first:** it is the only item with a deadline, and it is the only one
that silently corrupts what leadership reads. Past 2026-10-18, `transfer_window(0)`
keeps returning `2026-6` and "Este cambio hasta hoy" freezes at (09-07, 10-18) —
because the last row's end is `start + weeks` with nothing following to bound it.
Desgloses, the Panel rankings and Puntajes would all show a stale window without
saying so.

**Change:** append to `TRANSFER_SCHEDULE`:

| Transfer_Number | Start_Date | Weeks | Status |
|---|---|---|---|
| `2026-7` | `2026-10-19` | `6` | `Scheduled` |
| `2026-8` | `2026-11-30` | `6` | `Scheduled` | *(pending decision Q2)*

`2026-10-19` is a Monday and abuts `2026-6`'s end exactly. No code change: Status
does not gate the rollover (`app/utils/transfer_helpers.py`), so the new row takes
over by itself on the day.

**Live-sheet write — requires Zackary's explicit approval.** Follow the
2026-09-03 pattern: derive the rows, print them with weekday and end date, ask,
then write; the script must refuse if the tab is not in the expected state
(assert the last row is `2026-6` before appending).

**Acceptance:** Traslados' Schedule half shows the new cycle; simulate a date
past 2026-10-18 and confirm `transfer_window(0)` rolls to `2026-7`.

> **DONE 2026-09-05.** Written to the live sheet with Zackary's explicit
> approval, after a dry run printed both rows with weekday and end date and the
> script asserted the tab held exactly the three audited rows. `TRANSFER_SCHEDULE`
> is now 5 rows; coverage runs through **2027-01-10**. Rollover verified by
> simulation against the live tab:
>
> | `today` | `transfer_window(0)` |
> |---|---|
> | 2026-10-18 | `2026-6` (2026-09-07 → 2026-10-18) |
> | **2026-10-19** | **`2026-7`** (2026-10-19 → 2026-11-29) |
> | 2026-11-30 | `2026-8` (2026-11-30 → 2027-01-10) |
>
> `2026-8` is numbered by its START year though it ends 2027-01-10, matching how
> `2026-4`/`2026-5` are numbered. If the mission renumbers at the calendar year
> it should become `2027-1` — flagged to Zackary, not raised as a blocker.
>
> **The next row is due before 2027-01-10.** Same failure returns if the tab is
> ever allowed to run to its last row again.

### Step 2 — Desgloses: stop reporting `effort` and `exchanges` as a measured zero

**2a — The guard (stops the lie).** Filter `non_numeric_metrics()` out of the
metric vocabulary, the same way the other five call sites do. Effect: the two
keys leave the picker and the cards, so nothing on the page claims a zero that
was never measured.

> **Built 2026-09-05.** There turned out to be **two** unfiltered consumers, not
> one, and the suite saw neither. The Metric picker takes its keys from
> `metric_options()`; the **Key Indicators card grid takes a separate list from
> `snap_scope`'s `*_7d` columns** — LIVE_SNAPSHOT, where `a3_buildLiveSnapshot`
> writes these two as 0 for exactly the same coercion reason. Fixing only the
> picker left `INTERCAMBIOS 0` sitting in section ① of the live page. `_non_numeric`
> is now resolved once above the `if snap_scope ...` block and applied at both
> sites. Verified in the running app: neither label appears anywhere on the page
> and neither is offered in the picker. Suite unchanged at 872 passing / 14
> pre-existing failures.

**2b — Render them honestly (restores the information).** Rather than only
hiding two real leadership metrics, give each its correct shape:

- `effort` → the 1–3 weighted score, via `app/analytics/effort_breakdown.py`
  and `get_daily_effort_log()` (`queries.py:986`). Both exist and are already
  proven on the Panel. Carry the reporting share beside it, as that module
  insists: a missing form is a compliance failure, not zero effort, and the two
  facts must never merge.
- `exchanges` → a count of days answered `TRUE` over the period, against the
  area-days possible. Reuse `compliance_rankings.area_floor` for the
  denominator so it cannot drift from the compliance numbers on the same page.

**Sequencing:** 2a is a small, safe commit that can land immediately; 2b is the
substantive one. Splitting them means the page stops lying on day one even if 2b
takes longer. **Gated on Q1.**

**Acceptance:** verify in the running app, not only in the suite — this build's
own lesson. Confirm on a zone that answered `Todo` most days that the card shows
a score near 3, not `0`.

### Step 3 — Close out Phase 3.3: confirm the consumers woke up

Verification only; the backfill is in (§0.2). In the running app, confirm:

1. **Embudo** draws from the Drive blob (`TABLEAU_DETAIL_FILE_ID` is set).
2. **Desgloses' Teaching Pipeline** fills on every scope, not just MISSION.
3. **Metas** has switched off the `gate` proxy.

Anything that did not wake up becomes its own numbered step here. Then mark
§3.3 closed in `PLAN-2026-08-22.md`, as `363548b` did for §3.2.

### Step 4 — Phase 3.5: the payoff *(the largest remaining piece of value)*

With 2.6 years of person-level milestones already in hand:

- **The "By Cohort" vs "By Event Date" toggle.** Cohort mode answers *"of the
  people found in June, how many were baptized?"* — the question the nightly
  form structurally cannot reach, because Panel §1b's rates are same-window
  ratios of independent counts.
- **Finding-source effectiveness.** Each PDF breaks out 16 sources with the
  baptized share: Ward Council 57%, Contacting in Public 7%. That is the number
  that changes how a mission spends its hours.

Sub-steps to be written once Step 3 says what is actually live. **Gated on Q3.**

### Step 5 — Phase 4 sweep

- **5.1 (§4.1)** `GOALS_CONFIG` is empty; per-area goals would make the goal
  bars mean something per companionship. Desgloses and the Panel already fall
  back correctly (`_resolve_group_goal`), so this is an improvement, not a bug.
- **5.2 (§4.2)** Test the Goals save path end to end. Saving one goal creates
  three tabs that have never existed on the live sheet — **a live-sheet write,
  needs approval (Q4).** Then decide whether to keep the feature at all.
- **5.3 (§4.3)** Shrunk by §0.3 to: confirm the app reads the populated tab.
- **5.4 (§4.4)** Mantenimiento claims plumbing that does not exist —
  `referral-scraper.yml`, a `REFERRAL_DATA` tab, and `tableau-reports.yml`
  (which Step 6 would create). Correct the list.

### Step 6 — Phase 3.4: automation *(optional, last)*

Only once the manual path is known-good. Mirrors the proven chain —
`.github/workflows/tableau-reports.yml` + `app.ingestion.tableau_finding_runner`,
reusing `cloud_job_wrapper`, `CLOUD_JOB_STATUS` and `cloud_job_ui.py` unchanged,
writing through `save_dataframe(..., uploaded_by="auto:tableau")`. Monthly cadence
matches the data's own. Makes Mantenimiento's existing claim true.

---

## §2 — Not scheduled (carried forward, deliberately)

- **14 pre-existing test failures** — the standing baseline. **Corrected
  2026-09-05: it is 14, not the 13 carried in the notes.** Measured by stashing
  the working change and re-running: identical 14 either way. They cluster in
  five page-render files and several fail as "picker did not render", which
  looks like one shared harness/fixture cause rather than fourteen bugs. Worth a cleanup pass eventually. **Do not blame a new
  change for them: stash and re-run first.**
- **Section numbers drift on fragment reruns** — `design_system.py`'s
  label→number map keys on the full label, which is not stable.
- **A zone-vs-zone "who improved most" leaderboard** — ruled out of Desgloses
  scope; the twin machinery now exists and it would be cheap on the Panel.
- **Per-zone baptisms** — blocked on whether the Tableau view exposes them.
  Do **not** splice `WEEKLY_KI.ki_baptized_confirmed_real` into the certified
  series; it undercounts by roughly half (~18–20 against an official 41).
- **Sheet capacity and ownership** (`PLAN-2026-08-22.md` §3.2h) — ~650,000 empty
  cells reclaimable, `NIGHTLY_FORM_RAW` at 272 columns with unmeasured growth,
  and `COMPASS_CCSM` owned by a personal `gmail.com` account rather than a
  `churchofjesuschrist.org` one. That last one is a continuity/handoff question.
- **Nightly reporting compliance ~78%, dipped to 44% on 2026-09-02** —
  operational, not code.

---

## §3 — Questions, and Zackary's answers *(2026-09-05)*

1. **Step 2 — guard only, or guard plus proper rendering?**
   → **Guard, then render properly.** 2a lands first as its own commit so the
   page stops lying immediately; 2b is the real fix. Both steps stay.
2. **Step 1 — one row ahead or two?**
   → **Two rows**, `2026-7` and `2026-8`, straight 6-week continuation.
3. **Order of Steps 4–6.**
   → **Verify → payoff → sweep → automation**, i.e. Step 3 → 4 → 5 → 6 as
   numbered. The highest-value build goes ahead of the cheaper cleanup.
4. **Step 5.2 creates three new tabs on the live sheet.** Still open — not asked
   yet, because it does not gate anything until Step 5. Ask before doing it.

---

## STATUS

_Nothing started. Update this section as steps land, one line each, with the
commit — same as `PLAN-2026-09-03-desgloses-progression.md`._

| Step | State | Commit |
|---|---|---|
| 1 — Transfer row | **DONE** (live-sheet write, verified) | see plan commit |
| 2a — Desgloses guard | **built, verified in the app, uncommitted** | — |
| 2b — Effort/exchanges rendered | not started | — |
| 3 — Phase 3.3 acceptance | not started | — |
| 4 — Phase 3.5 payoff | not started | — |
| 5 — Phase 4 sweep | not started | — |
| 6 — Phase 3.4 automation | not started | — |
