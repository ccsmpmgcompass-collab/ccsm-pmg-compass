# Desgloses — Progression Build Plan

Executable version of the audit published 2026-09-02 (full findings + rationale
at https://claude.ai/code/artifact/61f350aa-2dd5-4251-ae1b-7b6c9aeb1c32 — read
that first if the "why" behind a step is unclear; this file is the "how").

**The one idea everything below implements:** give every period a twin — the
same-shaped window immediately before it — and draw the page against that twin
as well as against the goal. Fourteen steps, five groups, all in
`dashboard/app/breakdowns_engine.py` unless noted.

**Baseline, verified 2026-09-03:** `dashboard/venv/Scripts/python.exe -m
pytest tests/ -q` → **704 passed, 13 pre-existing failures, 1 skipped.** Stash
before blaming your own change — these 13 predate this plan.

**Rules from PLAN-2026-08-22.md that still apply:** one commit per numbered
step below. Run the full suite after each. Restart
`dashboard/venv/Scripts/streamlit.exe run Home.py --server.port 8502` after
any edit under `app/` — Streamlit serves the cached module otherwise. A
mission rate is the ratio of totals, not the mean of area rates. A missing row
renders an em dash, never `0`.

---

## Before you start — two open questions that gate specific steps

Neither blocks Group A2/A3/B; both are asked directly in the audit's
"Questions before building" section.

- **Blocks Step 5 (A1).** Is `TRANSFER_SCHEDULE` populated with real `Actual`
  rows today? If it's empty, "This Transfer So Far" / "Last Transfer" fall
  back to a 6-week guess from `TRANSFER_START_DATE` and "last transfer"
  becomes an assumption, not a fact. If that's the case when you reach Step 5,
  do Steps 1–4 and 6–13 first, come back to A1 once the schedule is filled in.
- **Blocks Step 8 (D1).** What's the one indicator that should lead the
  progression header — the number an AP screenshots into a message? Pick one
  before writing Step 8; everything else in the plan is unaffected either way.

Two more questions were asked and are treated as **decided** unless you say
otherwise: the twin comparison is automatic (no second "compare to" control),
and the landing estimate (Step 7) shows a point figure with the range on
hover, labelled "early estimate" under low confidence. Zone-vs-zone
leaderboard (which zone improved *most*) was named out of scope for this page
— it's a Panel candidate, not part of this plan.

---

## Group A — Make the comparison exist

### Step 1 — A2: give every period a prior window
- **File:** `app/breakdowns_engine.py`, `_kpi_period_bounds` (~182–214) and
  `_KPI_PERIODS` (~167–174).
- **Add** a sibling function, `_kpi_prior_bounds(label, cur_start, cur_end,
  today) -> tuple[date, date] | None` — the twin window for each label: This
  Week → last week; Last Week → the week before that; This Month So Far → the
  *same elapsed days* of last month; Last Month → the month before it; All
  Time → `None` (no twin — say so, don't invent one).
- **Thread it through** `render_group_breakdown` (~969): alongside `rows`
  (current-period `daily_hist` slice), build `rows_prior` the same way, sliced
  to the twin window. This step is plumbing only — no visible change yet.
- **Test:** new `tests/test_breakdowns_period_twin.py` — table-test every
  label against a fixed `today`, asserting exact `(start, end)` tuples,
  including the elapsed-days-matching case for This Month So Far and the
  `None` case for All Time.
- **Acceptance:** test passes; page looks identical to today.

### Step 2 — A3: wire `period_delta` into the Key Indicator cards
- **File:** `app/breakdowns_engine.py`, Key Indicators section (~1058–1185).
- For each metric: sum `rows_prior[key]` the same way `_val` sums `rows[key]`;
  compute `current_basis`/`prior_basis` via
  `app.analytics.period_delta.reporting_dates` + `days_in_window` scoped to
  `group_areas` (same pattern as `views/01_Panel.py:251–255,332`); call
  `period_delta.period_delta(val, prior_val, current_basis=..., prior_basis=...)`
  and set `card["change"]` to the result. `render_kpi_row` already renders
  `change=` — no change needed in `design_system.py` for this step.
- **Test:** extend the new test file — assert a card's `change` dict has the
  right shape for a period with enough reporting days, and is absent/`None`
  below `period_delta.MIN_COMPARABLE_DAYS`.
- **Acceptance:** on a *completed* period (Last Week, Last Month), every Key
  Indicator card shows an arrow and a movement figure against its twin.

---

## Group B — Make the goal honest while it's still running

### Step 3 — B1: pro-rate the goal on an in-progress period
- **Files:** `app/breakdowns_engine.py` (~1105–1185) and
  `app/components/design_system.py`, `render_kpi_row` (~648–700).
- In `breakdowns_engine.py`: when `in_progress`, compute `elapsed_days =
  (mission_today() - p_start).days + 1` and `pace_goal = weekly_goal *
  (elapsed_days / 7)`. Pass `card["pace"] = pace_goal` alongside the existing
  full-period `card["goal"]`.
- In `design_system.py`: `render_kpi_row` grows an optional `pace` param — a
  tick mark on the goal-bar track at `pace/goal` width, and the four-tier
  grading (≥90/≥60/≥50/below, same thresholds) switches to grading
  `value/pace` instead of `value/goal` whenever `pace` is present. Caption
  becomes "N of pace-goal expected by today · full goal M by [date]" instead
  of "N% of M goal."
- **Test:** unit-test the pace-tick position and the grading-source switch in
  isolation (pure arithmetic, no Streamlit needed — extract the calculation
  into a small helper if it isn't already separable).
- **Acceptance:** a zone exactly on pace two days into a thirty-day month
  reads green, not red (the F2 case from the audit).

### Step 4 — B2: turn the vs-goal delta back on for running periods
- **File:** `app/breakdowns_engine.py` (~1105–1185).
- Remove the `if not in_progress:` guard on `_card["delta"]`. When
  `in_progress`, compute delta against `pace_goal` from Step 3 instead of the
  full-period goal; when not, keep computing against the full goal as today.
- **Test:** assert an in-progress card's `delta`/`delta_label` is populated,
  not blank.
- **Acceptance:** the page's *default* view (This Month So Far, whole
  mission) now carries a real number and judgment on every card — closes F1.

---

## Group A, continued — the two period types that need new plumbing

### Step 5 — A1: add transfer periods to the picker (folds in E2)
- **New file:** `app/utils/transfer_helpers.py` — extract one
  `transfer_window(offset=0) -> tuple[date, date, str] | None` (start, end,
  label) built from `app/db/queries.py`'s `get_recent_transfer_dates()`
  (:3810) and `TRANSFER_SCHEDULE`'s `Weeks` column, mirroring
  `views/12_Traslados.py:79–105`'s `_transfer_rows()` / current-transfer
  resolution — including its `TRANSFER_START_DATE` fallback when the schedule
  is empty.
- **Refactor** `views/12_Traslados.py` to call the new shared helper instead
  of its private copy — this *is* E2 from the audit; do it now so there's
  never a second copy to drift.
- **File:** `app/breakdowns_engine.py` — add `"This Transfer So Far"` and
  `"Last Transfer"` to `_KPI_PERIODS`; extend `_kpi_period_bounds` and
  `_kpi_prior_bounds` (Step 1) to resolve them via the new helper. Make
  `"This Transfer So Far"` the new default *only if* `TRANSFER_SCHEDULE` has
  real `Actual` rows — otherwise leave the default at `"This Month So Far"`
  and log why (see the open question above).
- **Test:** new `tests/test_transfer_window.py` — current/last transfer
  against a stub schedule, and the `TRANSFER_START_DATE` fallback path.
  Regression-check `views/12_Traslados.py`'s own numbers are unchanged after
  the refactor (existing Traslados tests, if any, must still pass).
- **Acceptance:** picker offers both transfer periods at every scope; every
  section (cards, bar, trend, funnel) renders for them exactly as it does for
  the fixed periods.

### Step 6 — A1b: add a Custom range to the picker
- **File:** `app/breakdowns_engine.py` — add `"Custom"` to `_KPI_PERIODS`.
  When selected, render two `st.date_input` widgets (From / To) bounded to
  `[get_config_value("SYSTEM_START_DATE", "2026-06-08"), mission_today()]`
  (default `"2026-06-08"` matches the value already used elsewhere in
  `app/db/queries.py`). Feed the chosen range into the same `p_start`/`p_end`
  pipeline every other period uses.
- Extend `_kpi_prior_bounds` (Step 1): for `"Custom"`, the twin is the
  equal-length window immediately before `From` (i.e. `(From - length, From -
  1 day)`), clamped at `SYSTEM_START_DATE` — if the twin would start before
  that floor, there is no twin (say so, same rule as All Time).
- **Test:** assert the prior-window arithmetic and the floor-clamping.
- **Acceptance:** picking two arbitrary dates renders every section
  correctly; weekly-only metrics still round outward to whole weeks (existing
  behavior for every other period — verify it isn't broken here).

---

## Group C — Make direction visible

### Step 7 — C1: a landing estimate on every card
- **Files:** `app/breakdowns_engine.py` (Key Indicators section) and
  `app/components/design_system.py` (`render_kpi_row`).
- For an in-progress period: simple pace extrapolation
  (`value / elapsed_days * full_period_days`) when fewer than 4 weeks of
  weekly history exist for that metric+scope; `app.analytics.trends.
  compute_projection()` once 4+ weeks exist. Pass `card["projection"] =
  {"value": ..., "confidence": "high"|"low"|None}`.
- `render_kpi_row` grows a small caption line under the goal/pace bar: "on
  pace for ~N by [date]" — append "(early estimate)" when confidence is
  `"low"` or the projection function reports `"insufficient"`.
- **Test:** unit-test the caption-formatting function directly for
  high/low/insufficient cases (pure function).
- **Acceptance:** This Week / This Month So Far / This Transfer So Far cards
  show a landing line; All Time and any completed period don't (nothing left
  to project).

### Step 8 — D1: a progression header under the scope bar
- **File:** `views/04_Desgloses.py` or `app/breakdowns_engine.py`
  (`render_group_breakdown`, right after the scope selectors, before Section
  1).
- Three or four lines, plain numbers not prose, built from data the cards
  already computed (current value, `change` from Step 2, `projection` from
  Step 7) for **the one indicator named in the open question above**.
- **Test:** assert the header renders with the right scope name and degrades
  gracefully (no crash, honest "not enough data" state) when the lead metric
  has no data yet for the group.
- **Acceptance:** the top four lines of the page answer "where does this
  scope stand" without scrolling.

### Step 9 — C2: prior-period overlay and a group total on the trend
- **File:** `app/breakdowns_engine.py`, trend chart section (~1404–1690).
- Add one dimmed `go.Scatter` trace: the twin period's per-bucket values,
  aligned by **bucket index** (day-of-period / week-of-period), not absolute
  date. Add one bold aggregate trace: the sum across all areas in
  `group_areas`, alongside the existing per-area lines.
- **Test:** assert the prior-period trace's values equal the twin window's
  per-bucket totals; assert the aggregate trace equals the per-bucket sum of
  the individual area traces.
- **Acceptance:** confirmed visually — screenshot via the browser tool per
  the project's usual verification step.

### Step 10 — C3: movement on the per-area bar
- **File:** `app/breakdowns_engine.py`, per-area bar section (~1330–1400).
- Add a ghost/outline bar per area at its prior-period value (Step 1's
  `rows_prior`, grouped by area), plus a small delta chip per bar. Keep the
  existing sort (current value, descending) — this adds movement, it doesn't
  re-rank.
- **Test:** assert ghost-bar values equal each area's prior-window total.
- **Acceptance:** confirmed visually.

---

## Group B, continued — one more honesty fix

### Step 11 — B3: `value_basis`/`goal_basis` on group cards
- **File:** `app/breakdowns_engine.py`, Key Indicators section.
- Pass `value_basis = len(group_areas with data this period)` and
  `goal_basis = len(group_areas with a GOALS_CONFIG row)` into each card,
  mirroring how `views/01_Panel.py`'s rate cards already do it.
- **Test:** a zone with 2 of its areas missing goal rows shows the per-area
  basis pair in its caption instead of a bare, silently-inflated ratio.
- **Acceptance:** matches the fix described for F8.

---

## Group D, continued

### Step 12 — D2: reporting coverage badge in the header
- **File:** same header from Step 8.
- Add "N of M areas reporting, X%" beside the progression numbers, sourced
  from the same reporting-dates logic `_render_compliance` already uses
  (~718–915) — reuse it, don't recompute.
- **Test:** assert the badge's count matches the compliance calendar's count
  for the same period and scope.
- **Acceptance:** visible beside D1's header; the arrows above it now have a
  visible caveat instead of a hidden one.

---

## Group E — Housekeeping

### Step 13 — E1: route the engine's remaining literals through `t()`
- **File:** `app/breakdowns_engine.py` — trend captions, the goal/pace note,
  the funnel's four stage labels ("Found", "Taught", "At Sacrament",
  "Baptized"), and any new copy Steps 1–12 added along the way.
- **File:** `app/i18n/es.py` — add the Spanish entries.
- **Test:** `dashboard/venv/Scripts/python.exe -m pytest
  tests/test_i18n_coverage.py -k leftovers -q` — must go clean.
- **Acceptance:** a Spanish-speaking AP sees no English on this page.

**Step 14 — E2** is already done — folded into Step 5 (A1) so the shared
transfer-window helper never exists as three separate copies, even briefly.
Nothing to do here.

---

## Order and check-in points

1 → 2 → 3 → 4 (Groups A2/A3 then B1/B2 — the two cheapest, highest-visibility
correctness wins) → 5 → 6 (the two new period types) → 7 → 8 (the payoff:
projection, then the header that uses it) → 9 → 10 → 11 → 12 → 13.

Good places to pause and look at the running app rather than push straight
through: **after Step 4** (every card on the default view now carries a real
judgment — this alone is worth showing), **after Step 6** (the full period
picker is complete), and **after Step 10** (every chart now shows movement,
not just state).

---

## STATUS — updated 2026-09-03, end of build

**All thirteen steps are built, tested and verified in the running app.**
One commit per step, all on `main`:

| Step | Commit | What landed |
|---|---|---|
| 1 (A2) | `60ab7bf` | `_kpi_prior_bounds` — every period has a twin |
| 2 (A3) | `5a2bd91` | the arrow on a card means progression, always |
| 3 (B1) + goal fallback | `545772c` | pace-graded bar, tick, and a goal bar at all |
| 4 (B2) | — | delivered by Step 3; see the decision below |
| 6 (A1b) | `f8c1a58` | Custom date range |
| 7 (C1) | `fff3a10` | landing estimate on every running card |
| 8 + 12 (D1/D2) | `52abc46` | progression header with coverage badge |
| 9, 10, 11 (C2/C3/B3) | `7071a2b` | movement on both charts, honest bases |
| 13 (E1) | `87a9991` | the last English on a Spanish page |
| 5 (A1+E2) | `e6318e5` | transfer periods; "Este cambio hasta hoy" the default |
| — | `e122f79` | Panel: the year against the 527 baptismal goal |

**Step 5 (A1+E2) landed later the same day** (`e6318e5`), once Zackary supplied
the real cycle: transfers run six weeks, the next begins 2026-09-07.
TRANSFER_SCHEDULE was filled in with 2026-06-15 and 2026-07-27 (`Actual`) and
2026-09-07 (`Scheduled`), numbered by position within the year. **All thirteen
steps are now built.**

`app/utils/transfer_helpers.py` is the single answer to "which transfer are we
in"; `views/12_Traslados.py` reads it instead of its own private copy, which
discharges E2. **"Este cambio hasta hoy" is the default period everywhere** —
Desgloses, the Panel's compliance rankings, and Puntajes (which also stopped
approximating the window as a rolling 42 days).

The rule to protect if this is ever refactored: **Status does not decide which
transfer is current.** The current transfer is the latest row whose start date
has arrived. Gating on `Status == "Actual"` would pin the dashboard to the old
cycle every time a new one began, until someone remembered to edit the tab.

**Still open:** AGENT_CONFIG's `TRANSFER_START_DATE` reads `2026-08-09`, which
is not on the six-week grid and looks like a launch-day placeholder. Agents 1A,
2 and 3 all measure from it, so until it is set to `2026-07-27` the dashboard
and the Apps Script side describe different windows. The Traslados page warns
about the mismatch on screen; the warning disappears by itself once the config
is updated.

### Decisions taken during the build that amend the plan above

- **Step 4 (B2) was rewritten, not dropped.** `render_kpi_row` has one delta
  slot and `change` beats `delta` (`design_system.py:564`), so the twin
  comparison and the vs-goal comparison could not both have it. Zackary chose:
  the arrow always means the twin, the goal keeps the bar and its caption.
  Step 3's pace caption ("22 de 129 esperado a hoy · meta completa 1.290 al 30
  de sep") is therefore what closes F1, and there is no `delta` to turn back on.
- **A goal-source fallback was added ahead of Group B.** `GOALS_CONFIG` is an
  empty tab mission-wide, so no card on this page had ever drawn a goal bar and
  B1/B2/B3 would have shipped invisible. `_resolve_group_goal` falls back to
  AGENT_CONFIG's per-area `GOAL_*` × the group's area count, the way
  `views/01_Panel.py:120` already does mission-wide.
- **The twin of an in-progress period matches its ELAPSED shape**, not its name
  — three days into September the twin of "This Month So Far" is 1-3 August.
- **Steps 8 and 12 shipped as one block.** An arrow is only as good as the
  share of areas behind it, so the coverage line belongs under the arrows it
  qualifies rather than in a separate row.
- **The header leads with baptisms plus the two indicators that precede them.**
  Baptisms alone would read "0 · sin cambio" for most zones most weeks.
- **i18n was done per step rather than saved for Step 13**, because the
  coverage tests enforce it at commit time. Step 13 was then the leaks the
  extractor cannot see: f-strings, and `t()`-wrapped sentences interpolating an
  untranslated `kpi_period`.

### Known state of the data, which shapes what the page can show

`DAILY_LOG` runs 2026-08-09 → 2026-09-02. So "Last Week" is the only period
with a full working twin today; "This Month So Far" correctly reports "Aún no
hay comparación" because its twin (1-3 Aug) predates the records. That is the
page being honest, not the page being broken.
