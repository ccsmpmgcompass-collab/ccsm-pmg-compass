# PMG Compass — Dashboard Audit (tab by tab)

Started 2026-08-20. One tab per section. Goal: a clean, professional mission
data application that shows the right indicators, portrays them honestly, and
looks like it was designed rather than accumulated.

**Standing decisions that apply to every tab** (set 2026-08-20, Panel review):

| Decision | Answer |
|---|---|
| Primary audience | Mission president + APs |
| Page access | Stays open to every authenticated user — design *for* leadership, don't gate |
| Per-area callouts | **Positive only** (top performers). No bottom-N naming, because the missionaries named can read it |
| Zone comparison | **Per-area average**, never raw totals — zones range 8–13 areas |
| `AGENT_CONFIG.GOAL_*` semantics | **Per area, per week.** Mission-wide bar = goal × active area count |
| Language | Mission default is Spanish (`MISSION_LANGUAGE=ES`). No hardcoded English in user-facing strings |

---

# Tab 1 — Panel (`pages/01_Panel.py`)

**Audited 2026-08-20.** 621 lines, 9 stacked sections. Verified against live
`COMPASS_CCSM` data, not just read as code.

## Verdict

The page is structurally sound and well-commented, but it answers the wrong
question. It reports **effort inputs** when leadership needs **outcomes**, and
three of its numbers are actively wrong on screen right now.

---

## 🔴 Critical — wrong numbers on screen today

### C1. Key Indicator tiles show a 5%-complete week

`_ki_val()` reads `ki_df.iloc[-1]` — the newest week present, which is the
current in-progress one. Section 4's chart calls `exclude_current_week()`;
section 2's tiles do not. The same page shows two different "latest weeks."

| Week | Areas reporting | New People | Member Lessons | Sacrament | Bapt. Date | RC at Church |
|---|---|---|---|---|---|---|
| 2026-08-16 (last complete) | 31 / 43 | **190** | **147** | **59** | **34** | **66** |
| 2026-08-23 (**on screen now**) | **2 / 43** | 14 | 20 | 8 | 5 | 2 |

Understates the mission by ~13×.

**Fix:** route the tiles through `exclude_current_week()`, label the week
explicitly, and print the reporting denominator ("31 de 43 áreas informaron")
so a partial week can never again read as a collapse.

### C2. Zone leaderboard ranks by zone size — **DONE, item 3**

Raw 7-day totals, no normalization.

| Zone | Areas | Contact attempts | Per area |
|---|---|---|---|
| Los Angeles Norte | 11 | **1,289** ← shown #1 | 117.2 |
| Angol | 8 | 1,266 ← shown #2 | **158.2** ← actually #1 |
| Temuco Ñielol | 13 | 1,066 | 82.0 |
| San Pedro | 11 | 502 | 45.6 |

Also sorts on `contacts_attempted`, the most inflatable field on the form.

**Fix:** divide by active area count; rank on an outcome, not an input.
**Built 2026-08-21 — see “Item 3 as built” below.**

### C3. No KPI tile has a goal, though 19 are configured

`render_kpi_row` has goal bars built in. `_mission_goal()` returns 0 every
time: `DASHBOARD_SUMMARY.goal_weekly` is blank on all 23 MISSION rows, and the
`GOALS_CONFIG` fallback is **an empty tab**. Meanwhile `AGENT_CONFIG` holds
`GOAL_contacts_attempted=200`, `GOAL_new_people_found=7`, `GOAL_friend_lessons=30`
and 16 more that nothing on this page reads.

**Fix:** read `GOAL_*` from `AGENT_CONFIG`, multiply by active area count for
mission-level bars.

---

## 🟠 High — wrong emphasis

### H1. Headline row is 3 metrics, chosen by accident

`nightly_highlights` derives from `SCORE_CONFIG`'s `effort` weights →
`contacts_attempted`, `roleplays`, `member_contacts` (`effort` dropped, it's a
CHOICE field). That config exists to weight the *effort score*, not to choose
what a president sees first.

Absent from the entire Panel: Nuevas Personas Encontradas (283), Lecciones con
Amigos (649), Invitaciones al Bautismo (69), Libros de Mormón (74),
Invitaciones a la Iglesia (924). `contacts_attempted` appears **three times**
(tile, trend line, daily bar chart).

### H2. The four rate metrics — the best data in the system — appear nowhere

`CCSM_Agent1A.gs` computes four ratios, each with a configured target, a
Preach My Gospel page reference and a scripture:

| Rate | Formula | Actual | Target | Status |
|---|---|---|---|---|
| Contacto | made / attempted | 46.0% | 50% | ⚠️ near |
| Conversaciones Significativas | meaningful / made | 51.6% | 50% | ✅ |
| Lecciones | lessons / attempted | 15.7% | 20% | ⚠️ under |
| **Invitación Bautismal** | **invitations / lessons** | **10.6%** | **25%** | 🔴 **42% of target** |

**The mission is teaching well and not inviting.** 649 lessons produced 69
baptismal invitations. That is the single most actionable fact in the dataset
and the Panel does not mention it.

### H3. No time comparison anywhere

`DASHBOARD_SUMMARY` already carries `val_7d`, `val_14d`, `val_28d`,
`val_transfer`. The Panel reads only `val_7d`. `render_kpi_row` already accepts
a `delta`. Cheapest high-value fix available — data is computed and unused.

### H4. Cannot answer "who needs help?" — IN SCOPE, positive framing only

Mission and zone totals only. The `SCORES` tab (Effort / Skill / KI /
Effectiveness per area per week, 282 rows) is never touched.
Constrained by the open-access decision → **top performers only**
(positive framing, no bottom-N naming).

**Decision (2026-08-20, reversed same day): back in scope.** New small block
near ⑤ Zonas — top 5 areas mission-wide by Effectiveness score, no bottom
list. See build queue item 15.

---

## 🟡 Medium — correctness and polish

| # | Finding |
|---|---|
| M1 | "8-Week Trend" renders 1–2 points. `SYSTEM_START_DATE=2026-08-10`; `val_14d == val_28d` confirms ~2 weeks of history. Needs an honest "semana 2 de 8" building state |
| M2 | Effort section says everything twice — bar chart, then three `st.metric` tiles with the same numbers. Also the only place using `st.metric` instead of `render_kpi_row`: two card styles on one page |
| M3 | Effort denominator silently excludes non-submitters. EFFORT rows total 36/31/34/33/30/36/33 — submitters, not 43 areas. "16 All, 17 Most, 3 Some" hides 7 areas that reported nothing |
| M4 | ~20 hardcoded English strings on a Spanish-default page: calendar headers Mon/Tue/Wed, "Area Effort Levels Across Last 7 Days", bars labeled All/Most/Some (form says *Todo / La mayor parte / Algo*), the four compliance tiles, both explanatory paragraphs, the combined-compliance strip |
| M5 | Four compliance numbers (all-time %, 30-day calendar avg, 8-week grid avg, average-of-averages), no single verdict |
| M6 | Section 5 "Daily Trend" is a 7-bar chart of `contacts_attempted` — third appearance of one number |
| M7 | Nine sections in one scroll, no anchors; `_EMPTY_MSG` in six places never says *why* a section is empty; calendar tooltips use `title=`, which does not exist on touch — and this is read on phones |

---

## Proposed structure

```
PMG Compass · Panel Ejecutivo
Chile Concepción South Mission          Semana del 11–16 de agosto
────────────────────────────────────────────────────────────────
① VEREDICTO
   One honest line: reporting rate + the single worst rate vs target.
────────────────────────────────────────────────────────────────
② INDICADORES CLAVE — semana que terminó el 16 de agosto
   7 KI tiles · value · ▲▼ vs prior week · goal bar
   Footnote: "31 de 43 áreas informaron"          [C1, C3, H3]
────────────────────────────────────────────────────────────────
③ EFECTIVIDAD — tasas vs meta
   Compressed 4-segment band, color-graded, → link to Embudo   [H2]
────────────────────────────────────────────────────────────────
④ ACTIVIDAD NOCTURNA — últimos 7 días
   6 outcome-weighted tiles, each w/ delta + goal          [H1, H3]
────────────────────────────────────────────────────────────────
⑤ ZONAS — promedio por área
   Rank · zone · #areas · per-area metrics · effectiveness    [C2]
   └ Top 5 áreas — Effectividad (positive-only, no bottom list)  [H4]
────────────────────────────────────────────────────────────────
⑥ TENDENCIA — 8 semanas (or "construyendo historial")        [M1]
────────────────────────────────────────────────────────────────
⑦ CUMPLIMIENTO — one number, one calendar               [M5, M3]
   └ expander: per-area detail, effort breakdown        [M2, M6]
```

## Build order

| # | Item | Type | Notes |
|---|---|---|---|
| 1 | ~~KI tiles → last complete week + denominator footnote~~ | 🔴 bug | C1 — **DONE `dcb3012`** |
| 2 | ~~Goal bars from `AGENT_CONFIG.GOAL_*` × active areas~~ | 🔴 bug | C3 — **DONE**, see below |
| 3 | ~~Zone leaderboard → per-area average~~ | 🔴 bug | C2 — **DONE**, see below |
| 4 | Add `delta` (7d vs prior 7d) to every tile | 🟠 | H3 |
| 5 | Headline row → 7 Key Indicators | 🟠 | H1 — decided |
| 6 | Nightly row → 6 outcome metrics, not effort inputs | 🟠 | H1 |
| 7 | Rate-vs-target strip + Embudo link | 🟠 | H2 — decided |
| 8 | Verdict line at top | 🟠 | new |
| 9 | Effort denominator → all active areas | 🟡 | M3 |
| 10 | Translate every hardcoded string | 🟡 | M4 |
| 11 | Collapse compliance to one number + one calendar | 🟡 | M5 |
| 12 | Merge effort chart/tiles into expander | 🟡 | M2, M6 |
| 13 | "Building history" state for the trend | 🟡 | M1 |
| 14 | Empty states that say *why*; drop `title=` tooltips | 🟡 | M7 |
| 15 | Top 5 areas by Effectiveness score, near ⑤ Zonas — positive-only, no bottom list | 🟠 | H4 |

---

## Item 2 as built (2026-08-21) — and what it uncovered

C3 assumed one fix: read `GOAL_*` and multiply by active areas. Against live
data it turned out to be two problems, and the audit only knew about one.

**The Key Indicators have no `GOAL_*` row at all.** All 19 are *nightly* metric
keys (`GOAL_contacts_attempted=200`); none is a `ki_*_real`. So the configured
route gives the seven headline tiles nothing.

**A week's KI goals are written on the PREVIOUS week's form.** This is stated in
the form's own section help (`WeeklyReportForm_ES.gs:113-118`):

> Real — *"los resultados obtenidos durante la **semana pasada**"*
> Meta — *"las metas que usted estableció durante la planificación semanal para
> la **semana siguiente**"*

So one `WEEKLY_KI` row carries week W's results beside week W+1's goals.

### 🔴 A live bug this uncovered — `CCSM_AgentScores.gs`

`asc_loadAreaGoals()` read the meta off the **same** row as the actuals, so
every area's KI score — and therefore every `Effectiveness_Score` in `SCORES`,
the tab item 15 is built on — was graded against the target set for the week
*after* the one being scored. Fixed by loading a second KI map at
`asc_previousWeekEnd()`. **Not yet pasted into the live Apps Script editor**, and
existing `SCORES` rows keep their old values until recomputed.

### Decisions made with the user

| Question | Answer |
|---|---|
| KI goal source | Sum the `_meta` column from the previous week's forms |
| Nightly multiplier | All 43 active areas — a non-submitter counts as a zero |
| Over 100% | Show the true percentage; only the bar's width is capped |
| Dead sources | Keep `goal_weekly` / `GOALS_CONFIG` ahead of `AGENT_CONFIG` |
| Blank `_meta` | Counts as zero, with a footnote naming how many areas set one |
| Layout | Current week leads; last complete week below |
| Current-week values | 3 KIs counted live from the nightly form, Mon→today, with pace |
| The other 4 | Shown with their goal and an em dash, never a zero |
| Baptismal tile | Relabelled *Calendarios Bautismales Entregados* — and given **no goal bar**, because calendars handed out (a flow) is not friends holding a date (a standing count) |
| Tile labels | Shortened; the form's `(Real)` suffix dropped |

### The 2.040% problem, and the permanent fix

Week 08-16 had 33 areas' results (204 new people) over 1 area's goal (10) —
the only prior week predates launch. Total-over-total read **2.040%**.

The mismatch is structural, not transitional: the set of areas that submitted
last week is never exactly the set that submits this week, and transfers make it
worse. **Both sides are now reduced to a per-area rate before the ratio is
taken** — 6.2 against 10.0, i.e. 62%. This is the same rule this audit already
sets for zone comparison, for the same reason. Where the two bases are equal it
is identical to a plain ratio, so it costs nothing in the steady state.

It also corrected the *current* week: 39 areas file nightly reports while 33 set
goals, so Nuevas Personas moved 64% → 54%. The old figure flattered by 10 points.

### Rejected: a computed goal (avg of prior weeks + 10%)

Considered at the user's suggestion. **The mechanism already exists** —
`CCSM_Agent2.gs` (Transfer Goal Recalibration) computes per-area weekly averages
and suggests `avg × 1.05` when beating goal / `avg × 1.10` when below, capped at
`current × 1.5`, writing to `GOAL_RECALIBRATION` for leadership to approve. It
has **never run** (that tab holds only its header row) and cannot yet: it needs
transfer-length history, and `DAILY_LOG` holds 12 days.

Not adopted as the KI goal even once history exists, because:
1. the `_meta` column already *is* the goal — set by the companionship in weekly
   planning, which is what PMG asks; computing one removes the missionary from
   their own goal;
2. a baseline ratchets — a strong week raises the bar, a slump lowers it, so the
   percentage ends up describing variance rather than performance;
3. a self-referential goal can never report under-performance against a standard
   — `close_rate` at 42% of target would read "on track".

It **is** the right tool for the stale nightly `GOAL_*` numbers (`member_contacts`
runs at 196% of goal, `roleplays` at 33%). Revisit ~20 Sept, via Agent2.

---

## Item 3 as built (2026-08-21)

C2's fix was one line of arithmetic. The section around it was rebuilt to make
that arithmetic legible, on the user's calls.

**Where the logic lives.** `dashboard/app/analytics/zone_comparison.py` — a pure
module, no Streamlit, no sheet. `zone_per_area_table()` takes the ZONE frame,
MISSION_ORG's submitting areas and one week of SCORES and returns unformatted
floats; the page ranks and formats. That split is what let item 3 ship with
sixteen unit tests instead of an AppTest fixture (`tests/test_zone_per_area.py`).

**The table, as decided with the user:**

| Decision | Chosen | Why |
|---|---|---|
| Columns | The funnel, in travel order: Intentos → Contactos → Lecciones c/ Amigos → Inv. al Bautismo | Shows *where* a zone leaks, not just how loud it is |
| Rank | User-switchable, any visible column | The president compares different things on different weeks |
| Default rank | Efectividad, with an automatic fallback | See below |
| Divisor | **All** active areas in the zone | Same rule as the goal bars. A zone with silent areas ranks lower on purpose |
| Window | Rolling 7 days, said so in the heading | No new plumbing; the difference from §2 is now explicit |
| Format | One decimal + an Áreas column | The divisor prints, so the arithmetic is checkable on the page |
| Reading | A **Mostrar** switch: promedio por área (default) or total de la zona | Follow-up, same session. Totals are the president's volume reading; they rank by size, so they are never the default |
| Rates | None | The rate story is item 7, mission-wide. Not duplicated here |

**Live effect (2026-08-21):**

| Zona | Áreas | Intentos | Contactos | Lecciones | Inv. al Bautismo | Efectividad |
|---|---|---|---|---|---|---|
| Angol | 8 | 160,1 | 79,4 | 26,1 | 3,2 | 48,5 |
| Los Angeles Norte | 11 | 113,5 | 47,8 | 16,1 | 0,8 | 35,3 |
| Temuco Ñielol | 13 | 88,2 | 38,2 | 15,5 | 1,6 | 43,7 |
| San Pedro | 11 | 38,9 | 22,4 | 7,7 | 0,8 | 38,7 |

The sort genuinely re-ranks: by Inv. al Bautismo, Temuco moves to 2nd; by
Efectividad, Los Angeles Norte falls from 2nd to 4th. Flipping **Mostrar** to
*Total de la zona* re-ranks again — Temuco to 2nd, Los Angeles Norte to 3rd —
which is the size bias, visible and opt-in rather than silent and default.

### The follow-up pass (same session)

Three changes on the user's call, after seeing it live:

- **`Invitaciones` → `Inv. al Bautismo`.** The short form collided with
  `church_invites` (*Invitaciones a la Iglesia*). The one abbreviation among the
  column headers, chosen over the unabbreviated *Invitaciones al Bautismo*
  because that wraps the column — naming the wrong metric is the worse failure.
- **The week came out of the Efectividad header,** and was not moved anywhere
  else — the user's explicit choice. The column reads *Efectividad*; nothing on
  screen now states that it describes a completed week while its neighbours are
  a rolling 7 days.
- **A `Mostrar` radio switches every count between per-area and raw zone total.**
  Counts lose their decimal in totals mode. **Effectiveness ignores the switch
  and stays a per-area average in both** — it is a 0-100 score, so summing it
  gives an uninterpretable number (388) and puts the size bias back into the one
  column that is supposed to be size-neutral. Totals mode prints a caption
  naming the range of zone sizes, so the bias is stated where it applies.

`zone_per_area_table()` became `zone_comparison_table(..., per_area=True)`; the
old name would have been a lie in half its calls. Both Panel controls key on
stable identifiers with a `format_func` rather than on the translated label —
a mid-session language switch would otherwise leave a stored Spanish string in a
widget whose options had turned English.

### ⚠️ What this uncovered — Effectiveness is missing a third of itself

`Effectiveness_Score` is a weighted composite of Effort, Skill and KI. For the
last complete week (2026-08-16) **exactly one area of 43 has a non-zero
`KI_Score`** — Vilcun, at 56.67. Every other area scores 0 on the KI third, so
every zone's Efectividad is depressed by roughly a third and the number ranks on
two components while claiming to rank on three.

Cause, and it is the same offset item 2 found: `KI_Score` grades an area's
`ki_*_real` against its own `ki_*_meta` goals, and **a week's goals are written
on the previous week's form**. `WEEKLY_KI` holds 31 rows for week 08-16 but only
**1 row for 08-09** — so for 42 of 43 areas the goal denominator simply does not
exist. It should self-heal as consecutive weeks accumulate.

Until it does, the section refuses to rank on it silently. `effectiveness_is_rankable()`
requires a non-zero `KI_Score` on at least **half the mission's active areas**
(`DEFAULT_KI_MIN_SHARE = 0.5`); below that the default sort falls back to
Lecciones c/ Amigos and the table prints why. Efectividad stays selectable
throughout — the fallback governs the default, not the option.

### Smaller decisions worth not re-deriving

- **A zone with no `DASHBOARD_SUMMARY` row renders an em dash, not 0.0.** "Not
  written yet" and "did nothing this week" are different claims, and a 0 would
  also sort above a genuinely idle zone.
- **Effectiveness is summed per zone and divided by the active area count**, not
  averaged over the SCORES rows that exist. Averaging would reward a zone for
  its missing rows.
- **Zone names are stripped on both sides** before matching. MISSION_ORG and
  DASHBOARD_SUMMARY are written by different agents; one trailing space would
  have blanked a real zone's entire row.
- **The column set is hardcoded, not `flavor.nightly_highlights`.** That property
  reads SCORE_CONFIG's *effort* weights — it yields `contacts_attempted`,
  `roleplays`, `member_contacts`, two of which are inputs. Same root cause as H1.
- Column headers are trimmed phrases in the `_KI_SHORT_LABELS` style: *Intentos,
  Contactos, Lecciones c/ Amigos, Invitaciones*. Eleven new strings in `es.py`;
  the retired `"Zone Leaderboard — Last 7 Days"` key was deleted.

**Tests:** 360 passing, the same 5 pre-existing failures as at `8960af0`.

---

## Side findings (not Panel work)

- `app/auth/auth.py` `_ALWAYS_ALLOWED` carries two stale entries:
  `grayden16gmc@gmail.com` marked *"TEMPORARY — remove before go-live"*, and
  `hyrum.turner@missionary.org` marked *"TODO: remove ~mid-Sept 2026, goes
  home in 6 weeks (as of 2026-07-31)"*. Both still present.
- `GOALS_CONFIG` tab is empty but is still read by `get_goals_df()` /
  `get_mission_goals()`. Either populate it or retire it — right now it's a
  silent zero source feeding several pages.
- `is_leadership()` returns True for anyone in `_ALWAYS_ALLOWED`, which was
  meant for *login* convenience, not authority. Tech-admin access and pastoral
  authority are conflated. Pre-existing; flagged 2026-08-19.
