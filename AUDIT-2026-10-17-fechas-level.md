# Audit — "Amigos con Fecha Bautismal" is a level, not a weekly count

**Written 2026-10-17**, from Zackary's report (same day). No code has
changed. §6 is the questions that come before a plan.

---

## 1. What Zackary said (the two facts this audit rests on)

- **F1. The weekly figure is a level.** "The number of current fechas is
  the sum total of what is put for that week, not the sum total of all of
  the past and current fechas." The week's number is how many friends hold
  a baptismal date that week. It changes week to week by:
  - **+** new dates set;
  - **−** baptisms;
  - **−** dates dropped.
- **F2. Leadership's goal is a level to hold.** It is not a number of
  dates to set over the transfer.

## 2. What the data says (live sheet, 2026-10-16)

### 2.1 The form already behaves like a level

Each area's figure was compared with the same area's figure the following
week. The pilot has 304 area-weeks since 16 Aug.

| Key Indicator | mean per area-week | r with next week | identical next week |
|---|---|---|---|
| **Amigos con Fecha Bautismal** | **1,25** | **0,60** | **47%** |
| Conversos Recientes en la Iglesia | 1,68 | 0,65 | 51% |
| Amigos en la Reunión Sacramental | 1,64 | 0,51 | 33% |
| Lecciones con Miembros | 4,57 | 0,55 | 13% |
| Nuevas Personas | 6,50 | 0,31 | 10% |
| Primera semana | 0,27 | 0,31 | 71% (mostly zeros) |
| Bautizados | 0,08 | −0,02 | 89% (mostly zeros) |

**Fechas repeat exactly half the time; a flow like new people repeats 10%
of the time.** Conversos Recientes also persists, but it is a Sunday
attendance count. The same recent converts attend week after week, which
is persistence without being a level (see Q1).

### 2.2 The mission's level, week by week (pilot, areas that filed)

| week ending | 23 ago | 30 ago | 6 sep | 13 sep | 20 sep | 27 sep | 4 oct | 11 oct |
|---|---|---|---|---|---|---|---|---|
| fechas (level) | 38 | 30 | 29 | 49 | 41 | 35 | 45 | **71** |
| areas filed | 32 | 30 | 26 | 36 | 33 | 36 | 38 | 38 |

The September packet's tablero prints **"Real 125"** for this row. That is
four Sundays' levels added together (29 + 49 + 41 + 35, with partial-goal
filtering). There were never 125 friends with dates.

### 2.3 The stored goals are six levels added up

The 2026-6 goals were all saved by the bulk *Recomendar*. The transfer
recommender (`app/db/queries.py:3207`, `get_recommended_transfer_goals`)
computes **the area's weekly average × 1.1 × the cycle's 6 weeks**. That is
a transfer total, the right shape for a flow like new people.

Checked area by area for fechas: **23 of the 36 areas with history have a
stored goal exactly equal to ceil(weekly average × 1.1 × 6)**, and 32 are
within 1. Some examples:
- Alemania 1: average 4,25 a week → stored **29**;
- Boca de la Costa 2: 3,0 → **20**;
- Almirante Latorre: 0,5 → **4**.

The other areas borrowed their zone's median (no history yet).

So the sheet's **334** for the mission (7,4 per area) means *"hold about
**56** friends with dates, every week"* (334 ÷ 6). It does not mean "hold
334".

### 2.4 Why the grades are roughly right while the numbers are wrong

`ReportData.lead_week_goal` (`app/reports/model.py:1086`) spreads the cycle
goal evenly over its weeks (÷ 6). `_ki_rows` (`model.py:1481`, lines
1505–1525) then sums the weekly goal and the weekly level over the same
area-weeks. A sum of levels divided by a sum of level-goals is a ratio of
averages.

**The two errors cancel in the percentage.** September's 74% is "the
average level against the goal level", give or take silent weeks (§4,
Q3). **Every printed count, the transfer projection and every
"falta" are wrong.**

### 2.5 The form against Tableau (the same people, counted two ways)

On 11 Oct, the pilot's 45 areas:

| Source | Count | Note |
|---|---|---|
| Weekly form | **71** | 38 areas filed |
| Tableau, open dates | 562 | all ages |
| Tableau, set in the last 90 days | 205 | |
| Tableau, set in the last 60 days | 155 | |
| Tableau, set in the last 30 days | 85 | |

Missionaries report the dates that are alive. Tableau keeps every date
nobody dropped. The form's level is closest to Tableau's dates **under 30
days old**. That is a finding in its own right: about 7 in 8 of Tableau's
"open" dates in the pilot are dates the companionships no longer count.
It fits the date-quality finding (`project_date_quality_2026`): a date
set in 2026 is worth about a third of one set in 2025.

## 3. Every place the seven are added across weeks

**Severity:**
- **A** — prints a wrong fecha number or a wrong forecast in front of the
  council.
- **B** — wrong but quieter (a comparison, a tie-break).
- **OK** — reads one week at a time, so it is already right for a level.

### 3.1 Goals (the root)

| # | Where | What it does | Sev. |
|---|---|---|---|
| G1 | `app/db/queries.py:3207` `get_recommended_transfer_goals` | Transfer goal = weekly average × 1.1 × weeks, for every KI including fechas | **A** |
| G2 | `views/02_Metas.py:964–1066` bulk *Recomendar* / *Save All* | Writes G1's numbers into AREA_TRANSFER_GOALS. **Due again Mon 2026-10-19 for 2026-7.** | **A** |
| G3 | `views/02_Metas.py` per-area transfer boxes | A person typing a fecha goal does not know whether the box means a level or a total | **A** |
| G4 | `app/reports/model.py:1086` `lead_week_goal`, `:1433` `_leadership_goals`, `:2212` `_transfer_goals_full` | Pro-rate the cycle goal by weeks and sum it | right by accident (§2.4) |

### 3.2 Informes: the council packet, the annex and the screen (one model)

| # | Where | Prints | Sev. |
|---|---|---|---|
| R1 | `model.py:1481` `_ki_rows`: `actual`, `lead_actual`, `meta` summed over the period's area-weeks | Tablero "Real 125", "Meta 168" (Sep); the screen's KI cards | **A** |
| R2 | `forecast.py:91` `transfer_finish` | "El traslado en curso": Lleva 241 · Meta 334 · Termina en 270–312 · **Falta 93 por semana, 2,1×**. As a level: 71 against a goal of 56. It is **above** goal, not 2,1× behind | **A** |
| R3 | `packet.py` `trend_block` "Las últimas 12 semanas" | Total column sums 12 levels (259) | **A** |
| R4 | `packet_annex.py` area rows (`ki_lines`) | An area's "Real" sums its weeks against a summed goal | **A** |
| R5 | `model.py:2131` `_silent_goals`, `focus.py:66` `pareto` | "Dónde enfocar": the fecha part of each unit's shortfall is goal-weeks minus level-weeks. Its share is roughly right (ratios), but a silent week counts as a fecha level of zero | **B** |
| R6 | `model.py` `_ki_rows` "Cambio" | Per reporting area-week, then compared, so it is a ratio of averages. Close, but it is not "the level moved from X to Y" | **B** |
| R7 | `summary.py`, `story.py`, `packet.tablero_conclusion` | Name fechas by its grade (e.g. "lo más fuerte, Amigos con Fecha Bautismal (74%)"). The grade itself is near-right (§2.4); the words around it are fine | OK once R1 is fixed |
| R8 | `model.py` productivity index (`INDEX_WEIGHTS`, fecha weight 3) | Average per companionship-week, so it is an average level. Right in kind; a silent week counts as 0 (Q3) | **B** |
| R9 | Tableau blocks: pipeline, "Fechas: cuántas…", district "revisar o liberar" | Built per person (set and not baptised), so they are a level already | OK |

### 3.3 Panel, Metas, Desgloses, KI drill-down

| # | Where | Prints | Sev. |
|---|---|---|---|
| P1 | `views/01_Panel.py:660–700` `_ki_cycle_card` (and `app/analytics/ki_history.py:270–300` `cycle_points`) | "Este cambio" card: value = the cycle's weekly levels summed; goal = metas summed; mark = the transfer goal | **A** |
| P2 | `app/analytics/ki_history.py:300–325` `_area_window` | Per-area window totals for the drill-down's area table | **A** |
| P3 | `views/02_Metas.py:778–840` "Misión — este cambio" | Actual = `_sum_ki` over the cycle; goal = the summed goal | **A** |
| P4 | `views/02_Metas.py:870–900` the year rows | The same, over the year | **A** |
| P5 | `app/breakdowns_engine.py:1742` / `:1936` (Desgloses KI cards) and `app/analytics/period_delta.py:164` | The window's levels summed, and the prior window's | **A** over multi-week windows; OK on one week |

### 3.4 Already right (one week at a time)

- **The weekly letter**, `CCSM_Agent1A.gs`:
  - `a1a_rollUpKi_` (line 1481) adds **areas** within one week, which is
    right for a level;
  - the letter's four weeks are shown week by week;
  - `a1a_pickFocus_` grades one week against the week-before meta.
- **The KI ranking PDFs** (`app/reports/ki_ranking.py`): `WeekView` grades
  one week. `Unit.R`/`G` (line 245) add the two weeks for the old `rank()`
  tie-break only (B, cosmetic).
- **Scores**: `CCSM_AgentScores.gs:700–725` grades a week's real against
  that week's meta.
- **The companionships' own weekly meta** on the form is already a level
  (mean 2,15 against a real of 1,25).
- **The Gemini assistant** reads the latest week only. Its "conversion"
  (fechas → bautizados that week, `app/chat/gemini_chat.py:629`) divides a
  week's baptisms by the level. Fine as a ratio, but it is not a
  conversion rate (B, wording).

## 4. The rule a level should follow (proposed)

One list in `app/config/metric_catalog.py` names the KIs that are levels
(fechas only, unless Q1 adds Conversos Recientes). Every aggregator asks it.

For a **level** over a period of several weeks:

| Question | Flow (today, unchanged) | Level (proposed) |
|---|---|---|
| A unit's figure for one week | sum of its areas' reports | sum of its areas' reports (the same) |
| The period's "Real" | sum of the weeks | **the average of the weeks** (Q2), with **the last week** printed beside it as "hoy" |
| Leadership's goal | cycle goal ÷ weeks × weeks covered | **the goal level**, not multiplied by weeks |
| The grade | sum ÷ sum | average level ÷ goal level (the same percentage today, by §2.4) |
| "Cambio" | per area-week, against the twin | **level then → level now** |
| "El traslado en curso" | Lleva / Meta / Termina en / Falta por semana | **Hoy · Meta (nivel) · Al cierre (the level carried at recent pace) · Falta = meta − hoy** (a gap, not a weekly rate) |
| 12-week table | Total | **Último** (or Promedio) |
| A silent week | 0 | Q3 |

**The goal itself (G1–G3):**
- The recommender gives fechas **the weekly average × 1.1**: a level, not
  multiplied by weeks.
- Metas labels that box *"a mantener"*.
- Every reader treats the stored fecha goal as a level.

## 5. Time-sensitive

**Monday 2026-10-19 is the bulk *Recomendar* for 2026-7.** If it is pressed
on today's code, 2026-7's fecha goals are saved as six-week totals again,
and then either the sheet stays inconsistent or the build has to convert
them. Three ways through:

1. **(Recommended) Fix G1 + G3 first, before Monday:**
   - the recommender gives fechas a level;
   - Metas labels the box;
   - every reader keeps today's ÷-weeks behaviour for fechas until the rest
     of the build lands, so nothing prints differently on Monday;
   - in the same step, rewrite 2026-6's 45 fecha goals as level = stored ÷ 6
     (the sheet then means one thing).

   This is about one step, plus a push and a Reboot on Sunday.
2. Press *Recomendar* as is, and convert 2026-6 and 2026-7 together in the
   build.
3. Delay the 2026-7 save until the build is done (it is graded only from the
   November packet's last week).

## 6. Questions before the plan

- **Q1. Conversos Recientes en la Iglesia, and Amigos en la Reunión.** Read
  as a weekly Sunday count (the same converts attend each week, so the
  number persists), they stay summed. Your 2026-09-06 note on the roster
  ceiling ("six Sundays can only ever produce 12") already treats
  Conversos Recientes that way.
  - *Recommended: only fechas is a level.*
  - Or is Conversos Recientes also "how many recent converts are active"?
- **Q2. A level's figure for a month or a transfer:**
  - **the average** of its weeks (*recommended*, so one strong week doesn't
    stand for the month; it is also what the grade already measures);
  - or **the last week**?

  Either way the other number is printed beside it.
- **Q3. A silent week for a level.** The friends still have their dates.
  - **(a) Carry the area's last report forward**, at most within the same
    transfer, and say so (*recommended*). The reporting KPI still counts
    the silence.
  - (b) Zero, as decision 59 does for flows.
  - (c) Leave the area out of that week.
- **Q4. The 2026-6 goals already in the sheet:**
  - **rewrite them as levels** (stored ÷ 6, rounded up) in the Monday step
    (*recommended*);
  - or leave the sheet and divide at read time?
- **Q5. Form against Tableau (§2.5).** Print the form's level beside
  Tableau's open dates by age, named and never summed (decision 34), on the
  mission's "Fechas" block?
  - *Recommended: yes.* "71 amigos con fecha según los formularios ·
    Tableau: 85 fijadas hace menos de 30 días, 562 abiertas."

  The weekly change cannot be split into new / baptised / dropped from one
  source. The form has no new-dates count and Tableau has no drops, and
  combining the two would put a form figure and a Tableau figure in one
  sum. So the packet would show the level's change and Tableau's new
  dates and baptisms beside it, without netting them.

After your answers: `PLAN-2026-10-17-fechas-level.md`, numbered steps with
file:line, the Monday step first.
