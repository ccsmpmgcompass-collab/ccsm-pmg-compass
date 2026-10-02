# PLAN — Goals: one rule, one basis, reachable numbers

Written 2026-10-02 from an audit run the same day against the live sheet and
the code. This is the goals workstream that `PLAN-2026-09-21-informes.md` §6
deferred. The plan is self-sufficient: §1 holds the decisions (never re-open),
§2 what the audit measured, §3 the steps, and STATUS at the bottom records each
step as it lands.

---

## §1 — Decisions (Zackary, 2026-10-02)

- **G-D1. The 20 nightly `GOAL_*` numbers are TARGETS, not the president's
  standards.** They are reset to what the mission actually does, plus the
  same stretch every other recommendation in the app uses.
- **G-D2. No area's baptism goal may be 0.** The leadership recommendation
  keeps its floor of 1 baptism per area per cycle. Accepted consequence: the
  pilot's summed baptism goal stays well above its pace (68 set for 2026-6
  against ~20 a transfer), so that one bar will read low. Not a defect.
- **G-D3. The annual goal stays 527.** The Panel (`ab.landing_estimate`) and
  the packet (`Baptisms.landing`) already print the honest year-end estimate
  beside it, so nothing is built for this.
- **G-D4. Retire `runAgent2`** ("do what you think is best"). One
  recalibration rule for every goal: each unit's own recent average plus the
  `rec_stretch_pct` nudge (10%), proposed by the app, applied by leadership on
  Metas. Agent2's trend label (this transfer against the last) moves to that
  screen.
- **G-D5. A nightly goal is measured per REPORTED night.** A companionship's
  pace on the nights it filed is held to the goal; the share of nights filed
  is printed beside it as its own number, never folded into the percentage.
  This replaces three bases that disagreed (§2.3). Cross-unit rankings in the
  packet keep their per-active-area basis (decision 12 of the Informes plan) —
  a zone whose areas go silent should rank lower — but no percentage of a
  nightly GOAL is taken over unreported nights any more.
- **G-D6. Decision 31 (the packet grades nightly on movement, one blue bar)
  stays for now.** Its reason — goals at ~2× performance — is removed by G3,
  but re-colouring the packet is a layout project and should be judged on one
  full transfer under the new goals. Revisit when 2026-7 closes (2026-11-29).
  Only the sentence that says the goals are "cerca del doble" changes.

### §1b — Per-sector nightly goals (Zackary, 2026-10-02, later the same day)

He asked: "not generalized for the whole mission, but individualized by sector
based off of their previous numbers ... where they are at plus 10% ... and
automatically adjusted slightly every week for the weekly emails." His four
answers are G-D8, G-D10, G-D11 and the push of G1–G5 (`98f0db6..752aee9`).

- **G-D7. Every sector gets its OWN nightly goal per metric**, recomputed every
  Monday morning: its pace per reported night over the last six complete weeks
  × 7, plus the `rec_stretch_pct` nudge (10%), rounded up, never below 1.
  Supersedes G-D1's single mission-wide re-base; **G3 is dropped** — the
  `AGENT_CONFIG.GOAL_*` rows stay as the last fallback only.
- **G-D8. The goal follows the sector, capped.** In one week it moves at most
  `max(1, 10% of last week's goal)` up or down. No cap when there is no
  previous computed goal (the first run, or last week's was leadership's), so
  the first run lands on each sector's own pace rather than crawling down from
  the launch numbers.
- **G-D9. A sector with too little history borrows.** Fewer than 14 reported
  nights in the window (new, renamed or silent sectors) → its zone's median
  pace among sectors that qualify → the mission's pooled pace.
- **G-D10. Leadership's goal wins.** A goal typed on Metas for a sector stays
  until cleared (`NIGHTLY_GOAL_OVERRIDES`); the weekly job sets only the rest.
  Metas shows which are which.
- **G-D11. The Monday email shows last week against the goal that was in force
  for that week, and next week's goal beside it** ("58 · próx. 60"). It keeps
  grading the week's TOTAL — for one companionship a missed report is its own,
  and the email already shows the nights filed. The dashboard keeps G-D5.
- **G-D12. Storage.** `AREA_WEEKLY_GOALS` (Week_Start | Area | Overridden |
  one column per nightly metric) keeps every week's effective goals, so any
  past week is graded against the goal it actually had. `GOALS_CONFIG` holds
  the current week's — the tab every Apps Script reader (Agent1A, 5B, Scores)
  already reads, so the Friday email and the scores need no change.

## §2 — What the audit measured (2026-10-02, live sheet)

### 2.1 Four goal systems

| Goal | Stored | Set by | State |
|---|---|---|---|
| Nightly (20 metrics) | `AGENT_CONFIG.GOAL_*`, one per area per week | typed at launch | never changed; `GOALS_CONFIG` override EMPTY |
| Leadership KI goals | `AREA_TRANSFER_GOALS` per area per cycle | Zackary, Metas | 2026-6 all 45; **2026-7 none** |
| Companionships' KI goals | weekly form `ki_*_meta` | missionaries | weekly |
| Annual baptisms | `AGENT_CONFIG.GOAL_ANNUAL_baptisms` = 527 | once | whole mission |

### 2.2 Attainment, 2026-6 weeks ending 09-13..09-27

- Nightly: **73% of area-nights reported.** Per active area-week the median
  metric sits at 43% (6–65%); per reported night ×7 most run 60–89%.
  Genuinely out of reach even per reported night: `rc_lessons_mcp` 8%,
  `baptismal_calendars` 28%, `references_asked` 38%, `bom_shared` 39%,
  `pmf_lessons` 47%, `rc_lessons` 48%, `church_invites` 49%.
- Leadership KI goals: 69–93% on six of seven — the Metas REC works.
  Baptisms 18% (G-D2).
- Certified baptisms Jan–Sep 2026: 347 → ~463 for the year against 527.

### 2.3 Three nightly bases in use, none per reported night

- **Desgloses rows** (`breakdowns_engine`, `_value_basis`): an area that filed
  ONE night is held to a full week's goal.
- **Drill-down** (`ki_history.daily_series` / `daily_cycle_series`): goal ×
  areas with ≥1 night that week — same flaw.
- **Panel activity cards** (`_mission_goal`): goal × every active area,
  value a raw sum — a missed night is a zero.
- **Packet / Informes** (`model._nightly_rows`): attainment per ACTIVE
  area-week — a missed night is a zero. Change already per reported night.

### 2.4 Agent2 is broken and invisible

Run on transfer day (the runbook's order) the "current" window is empty and
the oldest window predates DAILY_LOG, so on 2026-09-08 every one of its 1,035
suggestions was the current goal ×1.10, every trend "Inconsistent". No view
calls `get_goal_recalibration`; the "Goal Recalibration tab" its header points
at does not exist. It also analysed `report_date`, `exchanges` and `effort`.

### 2.5 Retracted

"The weekly form's baptism field is under-filled (5 vs 12)" compared the four
pilot zones' form against the whole mission's certified figure. Like for like
(Tableau Detail, pilot areas, 2026-6 to 09-27): 6 vs form 5, area by area.

---

## §3 — Steps (one commit each, named by id)

### G0 — 2026-7 leadership goals *(Zackary; DATED: before 2026-10-19)*

Metas → Área → "Metas para este traslado" → pick 2026-7 → "Fill all
recommended" → save. No code. Independent of every step below.

### G1 — One nightly basis: per reported night (G-D5)

Shared arithmetic first, then each surface. Each surface states the share of
nights filed beside its figures.

- **G1.1** `app/analytics/period_delta.py`: `area_nights(rows)` — distinct
  (Area, Date) pairs — and `reporting_equivalents(rows, days)` = area-nights ÷
  days, the number of full-time areas the rows amount to. Tests.
- **G1.2** Desgloses nightly rows: `_value_basis` becomes
  `reporting_equivalents(rows, span)` where span is the days the period has run;
  the pace tick and the % then read per reported night. Heading's right line
  carries "N de M noches informadas (X%)".
- **G1.3** Drill-down: `daily_series` / `daily_cycle_series` goal =
  `goal_per_area × area_nights / 7`. Tests updated.
- **G1.4** Panel activity cards: `value_basis` / `goal_basis` on the card, so
  the bar reads per reported night against the per-area goal.
- **G1.5** Packet + Informes screen: `grade_nightly(now_rate, …)`, flags on
  `now_rate`; the "% meta" column's sub-label, page 3's rule and the
  "Por qué el trabajo nocturno va sin color" sentence say per reported night
  and drop "cerca del doble".

**Acceptance:** at 1400px and 375px, a mission-scope nightly row reads the same
% on Desgloses, the drill-down, the Panel card and the Informes screen for the
same window (±1 point for rounding); suite at the 11-failure baseline.

### G2 — "Recalibrar metas nocturnas" on Metas → Goal Settings (G-D1, G-D4)

A table, one row per `GOAL_*` metric: current goal · last six complete weeks'
mission pace per reported night ×7 · proposed = `ceil(pace × (1 + nudge))`,
minimum 1 · this transfer against the last (the trend label Agent2 carried) ·
the proposed change. One button writes every proposed value into
`AGENT_CONFIG` (`Key`/`Value`, the `_set_transfer_start_date` pattern: assert
one row per key, update the Value cell only, refuse otherwise), gated on
`auth.can_set_goals`, logged to `AUDIT_LOG` if the tab takes rows. Pure
arithmetic in `app/analytics/goal_recalibration.py` with tests.

### G3 — ~~The first re-base~~ *(DROPPED by G-D7 — per-sector goals replace it)*

Print G2's table from the live sheet, Zackary approves, then write — via the
G2 function, so the first write proves the button. Before/after printed.
Reminder: `CCSM_Agent1A` (coaching), `5B` (recognition) and `AgentScores`
read the same `GOAL_*` rows, so their letters and effort scores move with it —
intended.

### G4 — Retire Agent2 (G-D4)

- Transfer-day runbook step 6 becomes "Metas → Goal Settings → Recalibrar".
- `CCSM_Setup.gs` / `CCSM_DEPLOYMENT.md`: runAgent2 documented as RETIRED
  (code left in place, never run; Apps Script redeploy not required).
- `queries.get_goal_recalibration` / `apply_goal_recalibration_suggestion`
  deleted (no callers). `GOAL_RECALIBRATION` tab left alone.

### G6 — The per-sector rule (pure)

`app/analytics/area_goals.py`: given DAILY_LOG, the roster (area → zone), the
metric keys, last week's `AREA_WEEKLY_GOALS` row per area and the overrides,
return each area's goal and its source (`leadership` / `own` / `zone` /
`mission`) for one week. G-D7..G-D10 exactly; tests for each branch.

### G7 — The weekly job

`app/ingestion/area_goals_runner.py` (no Streamlit, `gcp_creds` like the
Tableau runner): read → compute for the week starting this Monday → upsert that
week's rows in `AREA_WEEKLY_GOALS` (idempotent: a re-run replaces them) →
rewrite `GOALS_CONFIG` (Area + every QUESTIONS_CONFIG key, the shape the agents
read). `--dry-run` prints counts only — **the repo is public; no sector names
or figures in logs.**

### G8 — Schedule it

`.github/workflows/area-goals.yml`: Monday 12:00 UTC (8–9 AM Chile, after
Agent3's 6 AM DAILY_LOG refresh, before Agent1A's 9:15 PM email) and
`workflow_dispatch`; reports into `CLOUD_JOB_STATUS` via `cloud_job_wrapper`.

### G9 — Metas

- The per-sector "Metas del formulario nocturno" grid saves to
  `NIGHTLY_GOAL_OVERRIDES` (only values that differ from the computed goal;
  equal = cleared) and updates that sector's `GOALS_CONFIG` row at once; each
  box says whether its goal is leadership's or computed.
- "Recomendar todas las metas de área" writes only the transfer KI goals — its
  weekly half would have turned every sector's goal into an override.
- G2's section becomes read-only: this week's sector goals, summed, beside the
  mission's pace; the AGENT_CONFIG write button goes.

### G10 — The dashboard reads sector goals

Panel cards, Desgloses rows, the drill-down and the packet take each sector's
goal for each week from `AREA_WEEKLY_GOALS` (current week: `GOALS_CONFIG`),
falling back to `AGENT_CONFIG`; still per reported night (G-D5): the expected
figure is Σ goal(sector, week) × nights filed / 7.

### G11 — The email *(Apps Script — Zackary pastes two files)*

`CCSM_Agent1A.gs`: grade the week against `AREA_WEEKLY_GOALS` for that week's
Monday (fallback `GOALS_CONFIG`, then `AGENT_CONFIG`), and carry next week's.
`CCSM_Agent1C.gs`: the scoreboard's Meta cell reads "58 · próx. 60". Until the
paste, the old Agent1A grades last week against the new week's goal — off by
one capped step, nothing breaks.

### G12 — First live run *(sheet write — Zackary's OK on the dry run first)*

### G5 — Housekeeping

Retractions in `PLAN-2026-09-05-backlog.md` / `PLAN-2026-09-21-informes.md` §6
pointing here; `dashboard/DEPLOYING.md`'s "Local dev runs 3.14.4" corrected.

---

## STATUS

- **2026-10-02** — Plan written from the audit; decisions G-D1..G-D6 recorded.
- **G1.1** `bb32e4a` — `period_delta.area_nights` / `reporting_equivalents`.
- **G1.2** `61045c2` — Desgloses nightly rows per reported night; heading
  reads "804 de 1.170 noches informadas (69%)" for 2026-6 to 10-02.
- **G1.3** `ded4bb9` — drill-down: `_load_daily` carries nights per area-week
  (`__nights`, distinct dates); goal = per-area × nights / 7.
- **G1.4** `bfa8312` — Panel activity cards carry `value_basis` = nights as
  full-time areas; heading counts nights filed. Book of Mormon shared read 42%
  (was 28% on the active basis) for 25 Sep–1 Oct.
- **G1.5** `fefdf65` — packet/Informes grade and flag on `now_rate`. Verified
  live: Desgloses and Informes both put contact attempts at 127,7 per reporting
  area-week (85% of 150) for 2026-6 to 10-02. Mid-build: with the launch goals
  still in place, `rc_lessons_mcp` is the one nightly goal the flag still
  catches (8%); `baptismal_calendars` no longer flags (28% per reported night).
- **G2** `4c99180` — `app/analytics/goal_recalibration.py`,
  `goals_queries.plan_config_updates` / `set_nightly_goals`, the Metas table.
  Verified live at 1400px and 375px (no page scroll; the table scrolls in its
  own box like Metas' other tables): window 17 Aug–27 Sep, 69% of nights filed,
  19 of 20 goals would change. Mid-build: trend values under 10 print one
  decimal ("baja: 0,3 vs 0,8"), since "1 vs 1" beside "baja" read as a bug.
- **G4** `985cd8d` — Agent2 retired in the runbook, CCSM_Setup.gs comments,
  CCSM_DEPLOYMENT.md; dead `queries` readers deleted. Comment-only `.gs`
  edits: no Apps Script redeploy needed.
- **G5** `9ee655c` — pointers from the backlog and Informes plans; DEPLOYING.md.
- Suite **11 failed / 1771 passed** — the same 11 baseline failures.
- **Open:** G0 (Zackary, before 2026-10-19) and G3 (the first write, waiting on
  his yes to the table's 19 numbers). Nothing pushed yet.
- **Pushed** `98f0db6..752aee9` (G1–G5) on Zackary's word, 2026-10-02.
- **G6** `5db68a6` — `app/analytics/area_goals.py` (`compute`, the cap with a
  minimum step of 1, zone → mission borrowing, leadership wins).
- **G7** `6563dee` — `app/ingestion/area_goals_runner.py`. Live dry run for the
  week of 09-28: 45 sectors × 20 metrics, 37 on their own pace, 8 borrowing
  their zone's (the sectors created or renamed on 09-07). Contact attempts
  range 15–283 against the old single 150.
- **G8** `5f00633` — `.github/workflows/area-goals.yml`, Monday 12:00 UTC.
- **G11** `33f8b62` — Agent1A grades against AREA_WEEKLY_GOALS for the graded
  week (per metric, then GOALS_CONFIG, then default) and carries next week's;
  Agent1C prints "20 · próx. 23". New `tests/test_agent1c_sector_goals.js`; the
  5 JS suites that fail failed before (stash-verified).
- **G10** `cb8283f` — `queries.get_sector_goal_lookup` → picklable
  `area_goals.GoalBook`; `area_goals.weighted_goal` on Desgloses, Panel,
  drill-down and packet.
- **G9** `fb602ef` — Metas grid/override/reset, bulk = transfer goals only,
  G2's table read-only. Mid-build: a repair script matched an older string and
  deleted 561 lines of es.py; restored from HEAD before commit, caught by
  `test_translation_coverage_is_complete`. `goal_recalibration.py` and
  `goals_queries.set_nightly_goals` stay (tested; G2's table still uses
  `propose` for the mission pace and trend) but nothing writes AGENT_CONFIG.
- Suite **11 failed / 1808 passed** — the same 11.
- **Open:** G12 (first live write — Zackary's OK; then push G6–G11, which also
  turns on Monday's cron) · Zackary re-pastes `CCSM_Agent1A.gs` and
  `CCSM_Agent1C.gs` · G0 (2026-7 KI goals before 10-19).
