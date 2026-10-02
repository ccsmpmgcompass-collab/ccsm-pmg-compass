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

### G3 — The first re-base *(sheet write — needs Zackary's yes on the numbers)*

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
