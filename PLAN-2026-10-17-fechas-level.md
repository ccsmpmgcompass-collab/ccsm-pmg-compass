# PMG Compass — Fechas as a level

**Written 2026-10-17**, from `AUDIT-2026-10-17-fechas-level.md`. Read the
audit's §3 before using a finding id (G1–G4, R1–R9, P1–P5).

**Convention:**
- One commit per step, named with the step id.
- Each step is verified before its commit.
- The suite runs before every push.
- STATUS is appended after every step.
- A push touching `dashboard/app/` needs a **Reboot**
  (`dashboard/DEPLOYING.md`).

---

## §1 — Decisions (Zackary, 2026-10-17): never re-open

| # | Decision |
|---|---|
| L1 | **"Amigos con Fecha Bautismal" is a level**: how many friends hold a baptismal date that week. It moves by new dates, minus baptisms, minus dates dropped. **It is never added across weeks.** It is the only level among the seven; Conversos Recientes and the sacrament counts stay weekly Sunday counts (audit Q1). |
| L2 | **Leadership's goal for it is a level to hold.** AREA_TRANSFER_GOALS stores the level itself, not multiplied by the cycle's weeks. A unit's goal is the sum of its areas' levels. |
| L3 | **A period's figure for a level is its LAST complete week** (Q2). The period's weekly average is printed beside it as context. |
| L4 | **A silent area-week counts as zero** in a level too (Q3), as decision 59 does for the counts. The reporting KPI says how much of that zero is silence. |
| L5 | **Amended the same day — a cutover, no rewrite of history.** Cycles starting before **2026-10-19** (2026-7) keep their fecha goals as saved: the old recommender's six-week totals (2026-6's 334 = a level of 55,7). From 2026-7 on, AREA_TRANSFER_GOALS stores the level. Rounding the old goals up to whole friends would have made 2026-6's level 77, not 55,7, and dropped September's fecha grade from 74% to about 54% after the fact. Every conversion lives in `goals_queries.py` (`LEVELS_STORED_FROM`). |
| L6 | (Default, amendable; Q5 was not asked) The mission's "Fechas" block prints the form's level beside Tableau's open dates by age, named and never summed (decision 34). |

---

## §2 — Steps

### Step 1 — the goal is a level (before Monday 2026-10-19)

- **1.1 The list.** `app/config/metric_catalog.py`: `LEVEL_METRICS =
  frozenset({"ki_baptismal_date_real"})` and `is_level(key)`, next to
  `ROSTER_CAPPED_METRICS` (line 82).
- **1.2 The recommender** (`app/db/queries.py:3207`,
  `get_recommended_transfer_goals`):
  - a level key gets `max(1, ceil(weekly stretch mean))`, not multiplied by
    weeks;
  - the roster ceiling is asked with `weeks=1` for it (only Conversos
    Recientes is capped today).
- **1.3 The cutover and the bridge** (`app/db/goals_queries.py`, L5).
  - `LEVELS_STORED_FROM = 2026-10-19` and `stores_levels(start)`.
  - **The Metas box reads and writes a level for any cycle**
    (`_row_to_dict` / `_new_row`). An old cycle's value is converted by its
    weeks both ways, so a past-cycle edit stays consistent.
  - **The bridge, `_levels_as_cycle_totals`:** the readers that sum goals
    over a cycle (`get_area_transfer_goals`, `all_area_transfer_goals`,
    `goals_by_cycle_start`) get the old cycle total. An old row is left
    as it is; a new row gets level × weeks. Nothing they print changes
    until Steps 2–6 switch them one reader at a time.
- **1.4 Metas** (`views/02_Metas.py`, the per-area transfer boxes around
  line 1371 and the bulk preview around line 1025): the fecha box and column
  say *"a mantener"*, and the help text says it is how many friends with a
  date the area should have each week.
- **1.5 The sheet.** Not rewritten (L5 amended). No row is touched.
- **1.6 Verify:**
  - the suite;
  - Metas run headless shows "a mantener";
  - the recommender for three areas gives the level;
  - the September packet's fecha row grades the same within rounding;
  - push, then **Reboot before pressing Recomendar**.

### Step 2 — the model reads a level (R1, R6, R8)

`app/reports/model.py` `_ki_rows` (line 1481). For a level key:
- `actual` = the unit's level in the period's **last complete week** (the
  sum of its areas' reports that week; a silent area counts 0, L4);
- `average` = the mean of the period's weekly levels;
- `lead_goal` = the areas' goal levels (no × weeks); `lead_actual` = the last
  week's level over the areas that carry a goal (decision 66's rule);
- the grade is the last week against the goal;
- "Cambio" = the last week's level against the comparison period's last
  week.

`lead_week_goal` (line 1086) stops dividing a level by weeks, and the model
reads raw levels (the bridge goes for `all_area_transfer_goals`). The
productivity index keeps its per-companionship-week average (an average
level).

### Step 3 — the transfer in progress (R2)

`forecast.transfer_finish` (`forecast.py:91`). For a level key:
- **Hoy:** the latest week's level;
- **Meta:** the goal level;
- **Al cierre:** the latest level plus the weeks left × the lowest and
  highest weekly change of the last six weeks, floored at 0;
- **Falta:** the goal minus today's level, a gap and not "por semana".

The "Cómo empieza" and "terminado" cases print the closing week's level.

### Step 4 — the renderers (R3, R4, R7)

- **Tablero:** "Real" for fechas reads "71" with "prom. 50" under it; its
  head names the week.
- **"Las últimas 12 semanas":** a level row's last column is "Último", not
  "Total".
- **Area rows** follow `ki_lines`.
- **Updated text:** the screen's cards and drill-down, `summary`, `story`,
  `section_methods`, *Cómo leer*'s column glossary, and the data note.

### Step 5 — "Dónde enfocar" (R5)

- `focus.pareto`: a level's gap is the goal level minus the last week's
  level, per unit.
- `_silent_goals`: the goal level of the areas silent in that last week.

### Step 6 — Panel, drill-down, Metas, Desgloses (P1–P5)

- `ki_history.cycle_points` / `_area_window` / `leadership_total` and the
  Panel's `_ki_cycle_card` (`01_Panel.py:660`): a level shows the last week
  against the goal level.
- `02_Metas.py:778–900` (cycle and year): a level row shows its latest week
  against the current cycle's goal level.
- `breakdowns_engine.py:1742/1936` and `period_delta.py:164`: a level's
  window figure is its last week.
- The bridge (1.3) is removed for each reader, and then deleted.

### Step 7 — the form against Tableau (L6)

The mission's "Fechas: cuántas, qué edad, cuántas llegan" block gains one
line: the form's level for the last week beside Tableau's open dates under
30, 60 and 90 days and in all. They are named and never summed.

### Step 8 — verify

- The suite.
- The September and *Este traslado* council packets: read the mission page,
  one zone and one area.
- AppTest on Informes, Panel, Metas and Desgloses.
- Push, and Reboot.

---

## STATUS

### 2026-10-17 — the plan is written

Zackary's answers:
- Q1: only fechas is a level;
- Q2: the last week;
- Q3: zero;
- Q4: fix it before Monday.

Q5 was not asked; its recommendation is L6, amendable. **Next: Step 1**, now.

### 2026-10-17 — Step 1 built, verified and pushed

- **1.1** `metric_catalog.LEVEL_METRICS = {ki_baptismal_date_real}` and
  `is_level()`.
- **1.2** The transfer recommender gives a level its weekly stretch, never
  multiplied by weeks (the roster ceiling is asked with 1 week).
  - **Live:** Alemania 1 → 3, Boca de la Costa 2 → 2, Los Huertos → 1,
    Almirante Latorre → 1.
  - Flows are unchanged (sacrament at Alemania 1: 14).
- **1.3** The cutover (L5 amended) and the bridge.
  - **Live:** 2026-6's summed fecha goal still reads **334**.
  - The 2026-6 Metas box shows the level it stood for (Alemania 1: 29 → 5).
  - On Monday the bulk button targets `transfer_window(0)` = 2026-7, which
    stores levels. A Sunday press would target 2026-6 and is stored as that
    cycle's total, so both are consistent.
- **1.4** Metas:
  - one caption under the transfer grid: *"Amigos con Fecha Bautismal es un
    nivel a mantener…"*;
  - the bulk preview column reads *"(nivel a mantener)"*;
  - a weekly expectation's fraction is not multiplied by weeks for a level.
- **1.5** Nothing written to the sheet.
- **Verify:**
  - Suite: 1 failed / 2076 passed / 1 skipped (the baseline's
    date-sensitive failure). `test_fechas_level_goals.py` is new (7 tests).
  - Metas run headless on live data: no exception, and the caption shows.
  - The Informes model reads exactly what it read before (no row past the
    cutover yet).

**Zackary: Reboot before pressing Recomendar on Monday.**
**Next: Step 2**, when he says go.
