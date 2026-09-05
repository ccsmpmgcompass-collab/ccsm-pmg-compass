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
- **5.2 (§4.2)** ~~Test the Goals save path end to end.~~ **Superseded by Step 7**
  (2026-09-05): goals move from monthly to per-transfer, and Step 7's acceptance
  is the same end-to-end save test against the new tabs. Nothing is lost by
  retiring it here — no goal has ever been saved, so there is no monthly path
  worth certifying.
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

## §1b — Step 7: transfer goals *(added 2026-09-05; design settled 2026-09-05)*

Goals are keyed by **transfer**, not by calendar month. Raised after Steps 1-2a
landed; supersedes Step 5.2 entirely.

Rewritten 2026-09-05 after a code audit and a live probe answered twelve design
questions. **Every decision below is Zackary's and settled — do not re-litigate
them.** What changed from the first draft: the scope is larger (mission goals go
KI-only, the goal bars get wired, a year summary is built) and four facts about
the codebase turned out to be different from what the draft assumed.

### 7.0 — What the audit found *(2026-09-05, live probe + code read)*

**Five goal paths exist, not three.** The draft counted three.

| Path | Tab / source | Cadence | Read by |
|---|---|---|---|
| Per-area weekly | `GOALS_CONFIG` | weekly | **`CCSM_AgentScores.gs`** scores against it |
| Mission goals | `MISSION_GOALS` | monthly | Metas only |
| Per-area goals | `AREA_MONTHLY_GOALS` | monthly | Metas only |
| Expectations | `AREA_TYPE_EXPECTATIONS` | weekly / monthly | Metas' `/N` fractions |
| Mission defaults | `AGENT_CONFIG.GOAL_*` | weekly, per area | Panel + Desgloses goal bars |

…and a **sixth** the draft did not know about at all: the weekly form asks each
companionship for its own `ki_*_meta` goals for the coming week, and
`views/01_Panel.py:214` already draws the Panel's KI bars from them through
`get_ki_goals_for_week()` (`queries.py:740`). See §7.6.

Four findings that change the build:

**a. Transfers align exactly to reporting weeks.** `WEEKLY_KI.Week_End_Date` is
**Sunday on all 109 live rows**; every `TRANSFER_SCHEDULE` start is a **Monday**.
A six-week transfer is exactly six whole weekly rows — 2026-6 runs 09-07 (Mon)
→ 10-18 (Sun), covering week-ends 09-13 … 10-18. There is no partial-week
arithmetic anywhere in this step, and Sundays-in-window is exactly `Weeks`.
Transfer goals are *cleaner* to compute than the monthly ones they replace,
which cut weeks in half and needed `_weeks_in_month` / `_sundays_in_month`
estimates (`02_Metas.py:573`, `:581`) to paper over it. **Those estimates are
deleted on this path, not ported.**

**b. No goal of any kind exists for the seven Key Indicators.** Probed live:
every `AGENT_CONFIG.GOAL_*` row is a NIGHTLY metric (`GOAL_contacts_attempted`,
`GOAL_roleplays`, …) — not one KI. `GOALS_CONFIG` is an empty header.
So `_resolve_group_goal` (`breakdowns_engine.py:482`) can return nothing for a
KI, and **no KI card on Desgloses has ever drawn a goal bar or could.** This is
why §7.5 exists: wiring transfer goals in is what finally lights them.

**c. Certified baptism counts cannot describe a transfer.**
`get_baptisms_actual_for_range` (`queries.py:3253`) returns `None` — never a
partial sum — unless the range is whole calendar months, because
`TABLEAU_BAPTISMS` only holds monthly figures. A transfer never is. The Metas
baptism row depends on it today (`02_Metas.py:880`). See §7.7.

**d. The Apps Script side already thinks in transfers.** `CCSM_Agent2.gs`
recalibrates per-area goals **once per transfer cycle**, reading
`TRANSFER_SCHEDULE`'s real `Actual` rows (`CCSM_Agent2.gs:161`, `:218`) and
writing suggestions to `GOAL_RECALIBRATION` → `GOALS_CONFIG`, expressed as a
weekly number. A transfer-cadence goal engine exists; it just speaks weekly.
Nothing in this step touches it — see §7.4's last bullet.

**Confirmed by probe, 2026-09-05:** `MISSION_GOALS`, `AREA_MONTHLY_GOALS`,
`AREA_TYPE_EXPECTATIONS` and `APP_SETTINGS` **do not exist as tabs**;
`GOALS_CONFIG` and `GOAL_RECALIBRATION` are empty headers. Nothing to migrate.
`get_area_monthly_goals()` (`goals_queries.py:204`) has **no consumer at all** —
its docstring cites `app/analytics/mlc_rollups.py`, which does not exist.

### 7.1 — The seven Key Indicators, constant across the app *(Zackary's rule)*

The KI vocabulary is the sheet's, and it is these seven — confirmed against
`QUESTIONS_CONFIG` (`Q-W-004` … `Q-W-016`), which is exactly what
`metric_catalog.key_indicator_metrics()` already returns:

| Key | `Metric_Display_Name` on the sheet |
|---|---|
| `ki_new_people_real` | Nuevas Personas Encontradas |
| `ki_member_lessons_real` | Lecciones con Miembros |
| `ki_friends_sacrament_real` | Amigos en la Reunión Sacramental |
| `ki_friends_first_week_real` | Amigos en la Iglesia (Primera Semana) |
| `ki_baptismal_date_real` | Amigos con Fecha Bautismal |
| `ki_baptized_confirmed_real` | Bautizados y Confirmados — **short label "Bautismos"** |
| `ki_rc_at_church_real` | Conversos Recientes en la Iglesia |

**These seven are the KI set everywhere in the app.** Baptisms and confirmations
stay ONE metric — the mission's own form asks them as one question — and the
short label is "Bautismos".

This retires the legacy goal-key vocabulary on the mission path.
`flavor.featured_goals` gives six keys (`baptisms`, `confirmations`, `on_date`,
`at_sacrament`, `new_people_to_teach`, `rc_at_church`,
`members_nonmember_lessons` — `standard.json`), which `GOAL_TO_ACTUAL`
(`flavor_loader.py:95`) maps onto only six metrics: `baptisms` and
`confirmations` **both** point at `ki_baptized_confirmed_real`, and
`ki_friends_first_week_real` has no goal key at all. So Mission Goals today
renders one metric twice and omits another entirely. Fixed here by keying on
the seven directly.

### 7.2 — Data model

Two tabs, created on first save, replacing the never-created monthly pair:

| Tab | Key | Columns |
|---|---|---|
| `MISSION_TRANSFER_GOALS` | `transfer_start` | `transfer_start`, `transfer_number`, the **seven `ki_*_real` columns**, `set_by`, `notes` |
| `AREA_TRANSFER_GOALS` | `area` + `transfer_start` | `area`, `transfer_start`, `transfer_number`, the **seven `ki_*_real` columns**, `set_by`, `notes` |

One vocabulary across both tabs, per §7.1. **No `extra_goals` JSON column** —
mission goals are KI-only now (§7.4), so there is nothing for it to hold.

**Keyed by `transfer_start` (ISO date), not `Transfer_Number`.** The number is
carried as a label only. The number has no code-enforced format and two
functions already mis-parse the live `2026-4` style values (§7.9). A start date
is unambiguous, sorts correctly, and is how `transfer_window()` already
identifies a cycle.

### 7.3 — Which year a transfer belongs to, and how a year totals

*(Zackary's rules, settled — unchanged from the previous draft.)*

Count the transfer's days in each calendar year; **the year holding more days
owns it.** On an exact 21/21 split, **the year it ends in wins.** Deliberately
not "the year it starts in":

| Cycle | Span | Split | Owns it |
|---|---|---|---|
| `2026-8` | 2026-11-30 → 2027-01-10 | 2026: 32 / 2027: 10 | **2026** |
| the 2027 year-end cycle | 2027-12-13 → 2028-01-23 | 2027: 19 / 2028: 23 | **2028** |

- **Actuals always follow the real date.** A yearly rollup counts each day's
  activity in the calendar year it actually happened. The January days of
  `2026-8` count toward **2027** whatever the transfer is labeled.
  `analytics/annual_baptisms.py` already works this way, keying off real
  `YYYY-MM` months. **Do not let the year assignment leak into annual
  aggregation** — this is a constraint to protect in review, not code to write.
- **Goal totals pro-rate by days.** A straddling transfer contributes
  `goal × (its days in that year / its total days)`, so a year's goal and its
  actuals cover the same span. `2026-8` contributes 32/42 to 2026, 10/42 to 2027.

The year assignment decides only which single year a transfer is *filed under*
for display and editing. Pro-rating governs yearly arithmetic.

### 7.4 — The Metas page *(full replacement)*

**The monthly path is deleted, not left dormant.** Nothing was ever saved
monthly, so no history is stranded, and one cadence means one answer to "what is
the goal".

- **Mission Goals** → per-transfer, **seven KI boxes only**. The "Other Metrics"
  grid and its `extra_goals` JSON are removed: nightly metrics already have
  per-area weekly targets in `AGENT_CONFIG` that the Panel and Desgloses read,
  and a second mission-wide transfer number for the same metric is a second
  answer to one question.
- **Area "Monthly Goals"** (`02_Metas.py:1305`) → **"Metas de este cambio"**,
  same seven KIs, written to `AREA_TRANSFER_GOALS`.
- **Picker**: every transfer in `TRANSFER_SCHEDULE` — past, current and next —
  defaulting to the current cycle from `transfer_window(0)`. The schedule runs
  through 2027-01-10 after Step 1, so "next" always exists. Goal history lists
  transfers newest first.
- **Wording**: **"cambio"**, matching Desgloses' period picker
  ("Este cambio hasta hoy"). "Metas de este cambio", "Cambio 2026-6". i18n done
  per sub-step, not deferred to the end.
- **REC pills**: the existing weekly stretch average **× that cycle's real
  `Weeks`** from `TRANSFER_SCHEDULE` — not an average cycle length, and not a
  per-transfer history average. `WEEKLY_KI` begins 2026-08-09, so **no area has
  one completed transfer of history**; averaging completed cycles would divide
  by zero cycles. `get_recommended_monthly_goals` (`queries.py:2714`) is not
  ported.
- **`/N` fractions**: kept. `AREA_TYPE_EXPECTATIONS.Cadence` gains `transfer`
  alongside `weekly`/`monthly` (`queries.py:1932` narrows it today, `:1885` is
  the header). A weekly-cadence expectation scales by the cycle's real `Weeks`;
  a `transfer`-cadence one counts as-is. Sunday-only KIs scale by the Sunday
  count, which per §7.0a is exactly `Weeks` — so the `_sundays_in_month` special
  case disappears rather than being ported.
- **Unchanged on this page**: the "Nightly Form Goals (weekly totals)" section.
  It writes `GOALS_CONFIG`, which `CCSM_AgentScores.gs` scores against weekly
  with no conversion, and which `CCSM_Agent2.gs` recalibrates every cycle
  (§7.0d). Making it transfer-scoped would silently break every area's weekly
  score. It stays weekly.

### 7.5 — Wire the goal bars *(the visible payoff)*

Per-area transfer goals feed the KI goal bars on Desgloses and the Panel. Per
§7.0b these bars have never been able to draw for a KI.

`_resolve_group_goal` (`breakdowns_engine.py:482`) returns a **weekly** goal
which the caller multiplies by `_goal_factor` (`:1839`, `p_days / 7`). A
transfer goal is a period TOTAL, so it enters that contract as
`transfer_goal / cycle_weeks` — its weekly equivalent. When the period IS the
transfer, `_goal_factor` reproduces the transfer total exactly; for any other
period it degrades to a sensible weekly rate.

**Precedence — Zackary's call: most-specific-entered-goal-wins, the existing
order, with the transfer goal slotted beneath `GOALS_CONFIG`:**

1. `GOALS_CONFIG`, summed across the group's areas *(wins where it exists)*
2. **`AREA_TRANSFER_GOALS` ÷ the cycle's weeks** *(new)*
3. `AGENT_CONFIG.GOAL_<metric>` × the area count

One precedence rule across the whole app. In practice the vocabularies barely
overlap — `AGENT_CONFIG.GOAL_*` is entirely nightly and `GOALS_CONFIG` is empty
mission-wide — so the transfer goal is what actually lights the KI bars.

The derived note must carry the arithmetic, as the existing branches do
(`:520`): a bar reading "48% de 1.200" is unreadable without it.

### 7.6 — The companionship's own goals stay visible *(§7.0's sixth path)*

The weekly form asks each companionship for its own `ki_*_meta` goals for the
coming week, and `get_ki_goals_for_week()` (`queries.py:740`) reads them with
the week-offset correction — a week's goals are written on the PREVIOUS week's
form. `views/01_Panel.py:209-217` draws the Panel's KI bars from them.

These are a different fact from a leadership-set target, and
`key_indicator_metrics()`'s own docstring warns they must never be added to a
real value or confused with one.

**Zackary's call: the leadership transfer goal is the bar; the companionship's
own goal is shown beside it** in the small print — "se propusieron N". Both
facts survive and neither is mistaken for the other. `_ki_goal_note`
(`01_Panel.py:524`) already renders small print under these bars and is where
this goes.

### 7.7 — Baptism actuals

Per §7.0c a transfer window cannot carry a certified count.

**On the transfer rows** (Metas' goals-vs-actuals, the goal bars): use
`ki_baptized_confirmed_real` summed over the cycle's weeks, **labeled as the
mission's own weekly report**, with a note that the certified figure is monthly.
`get_baptisms_actual` (`queries.py:3195`) documents that field as undercounting
badly (~18–20 against an official 41 for one month) — so it is shown named, never
silently substituted for the certified number.

**In the year summary** (§7.8): **show both**, as two named rows — the certified
`TABLEAU_BAPTISMS` figure (marked with how far the capture reaches; it lags a
month or two) and the self-reported weekly total. The gap between them is itself
worth seeing, and neither source quietly does the other's job.

**Never splice them into one series.** That is `annual_baptisms.py`'s "One
source" rule and the §7.3 guard.

### 7.8 — The KI year summary *(new section on Metas)*

A fifth section beside Area Goal Customization / Mission Goals / Goal Settings /
Area Expectation Settings. **Mission-wide, KI-only** — the seven of §7.1, not
nightly metrics and not per-area.

Per row: the year's goal (that year's transfer goals summed, straddlers
pro-rated by days per §7.3), the actual to date (by **real date**, per §7.3),
and % of goal. Baptisms appear as two rows per §7.7.

This gives §7.3's rules a real consumer rather than leaving them as an
unexercised library.

**`GOAL_ANNUAL_baptisms` = 527 and the Panel's annual chart are NOT touched.**
The chart keeps its own certified source and its own goal. See the acceptance
check.

### 7.9 — Fix the two numeric `Transfer_Number` parses *(folded in)*

This step depends on reading the schedule reliably:

- `get_recent_transfer_dates()` (`queries.py:3851`) coerces `Transfer_Number`
  with `pd.to_numeric`. `"2026-4"` → `NaN` → dropped. **Verified live: it
  returns `[]`, and `is_within_last_transfers()` is `False` for every date.**
  Sort by `Start_Date` instead.
- `next_schedule_update()` (`ingestion/transfer_engine.py:303`) does
  `int("2026-4")`, which throws. It is caught, so `max_num` stays `0` and the
  function would append a row numbered `"1"`.

**Current impact: none.** The only consumer is `render_lineage_badge()`
(`breakdowns_engine.py:1298`), which cannot draw anyway — the `AREA_LINEAGE` tab
does not exist. Latent, and it bites the day someone populates that tab.

### Build order — one commit each

| # | Commit | Touches |
|---|---|---|
| 7a | `Transfer_Number` parses fixed (§7.9) | `queries.py:3851`, `transfer_engine.py:303` |
| 7b | Transfer-year library: ownership, day-split, pro-rating (§7.3) | new `app/analytics/transfer_year.py`, pure + tested |
| 7c | `goals_queries.py`: the two transfer tabs replace the monthly pair (§7.2) | `goals_queries.py`, `tests/test_area_monthly_goals.py` ported |
| 7d | `transfer` cadence on expectations (§7.4) | `queries.py:1885`, `:1932`, `:2064` |
| 7e | Metas: Mission Goals → per-transfer, seven KIs (§7.4) | `02_Metas.py:553-921` |
| 7f | Metas: area goals → per-transfer (§7.4) | `02_Metas.py:1305-1470` |
| 7g | Goal bars read transfer goals (§7.5) | `breakdowns_engine.py:482`, `:1897` |
| 7h | Companionship's own goal shown beside the bar (§7.6) | `01_Panel.py:209-217`, `:524` |
| 7i | KI year summary (§7.8) | `02_Metas.py` new section |

7a and 7b have no dependencies and can land first. 7c blocks 7e/7f; 7e/7f block
7g; 7g blocks 7i.

### Acceptance

Verify in the running app, not only in the suite — the Step 2a lesson (a fix
that passed the suite still read "INTERCAMBIOS 0" on the live page).

1. Save a mission goal and an area goal for the current transfer; confirm both
   tabs are created with the shapes in §7.2. **This is the end-to-end test old
   Step 5.2 asked for, so 5.2 retires with this step.**
2. Confirm the metric columns are the **seven** of §7.1 — not the flavor's six
   goal keys. `AREA_MONTHLY_GOALS` once hardcoded Provo's
   `gate/date_metric/new_found/pew/renew/member_lessons`, so every value typed
   went to a column for a metric CCSM does not collect and the page reported
   "saved" having stored nothing. Fixed in code; never exercised against a real
   sheet.
3. A saved area transfer goal **draws a KI goal bar on Desgloses** where none
   could draw before (§7.0b), and its note carries the arithmetic.
4. A straddling transfer pro-rates 32/42 : 10/42 across 2026/2027 in the year
   summary.
5. The Panel's annual baptism chart is **unchanged** — same source, same 527
   goal, same reach. That is the §7.3 guard.
6. A KI card shows the leadership goal as its bar and the companionship's own
   `ki_*_meta` figure beside it, never summed (§7.6).
7. Baptism actuals are labeled by source everywhere they appear (§7.7).
8. Stash and re-run before blaming this work for any of the 14 baseline
   failures (§2).

**Creates two new tabs on the live sheet — needs Zackary's approval at the point
of first save**, same pattern as Step 1.

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
4. ~~**Step 5.2 creates three new tabs on the live sheet.**~~ Retired — Step 7
   supersedes 5.2, and carries its own approval point at first save.

**On Step 7 (asked and answered 2026-09-05):**

5. **Do annual rollups attribute by real date, or by the transfer's assigned
   year?** → **By real date.** A straddling transfer's actuals split across two
   years. §7.3.
6. **Which way does an exact 21/21 split go?** → **The year it ends in.** §7.2.
7. **How does a yearly goal total handle a straddling transfer?** →
   **Pro-rate its goal by days**, so a year's goal and actuals cover the same
   span. §7.3.

**Queue position — settled 2026-09-05.** Zackary moved Step 7 to the FRONT:
it runs now, ahead of Steps 3-6, which keep their relative order behind it.

**Twelve further design questions were asked and answered 2026-09-05** during
the Step 7 audit; every answer is written into §1b at the point it applies.
Summarised: full replacement of the monthly path; goal bars wired; weekly-form
baptism figure on transfer rows, both sources in the year summary; the seven
`ki_*_real` keys as the KI vocabulary app-wide; a KI-only mission-wide year
summary on Metas; picker covers past/current/next; REC is weekly × the cycle's
real weeks; `GOALS_CONFIG` keeps precedence over a transfer goal; wording is
"cambio"; `transfer` joins the expectation cadences; mission goals drop the
"Other Metrics" grid; and the companionship's own `ki_*_meta` goal is shown
beside the leadership bar, never as it.

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
| 7 — Transfer goals | **audited, plan rewritten, awaiting approval to build** | — |
