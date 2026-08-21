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

### C2. Zone leaderboard ranks by zone size

Raw 7-day totals, no normalization.

| Zone | Areas | Contact attempts | Per area |
|---|---|---|---|
| Los Angeles Norte | 11 | **1,289** ← shown #1 | 117.2 |
| Angol | 8 | 1,266 ← shown #2 | **158.2** ← actually #1 |
| Temuco Ñielol | 13 | 1,066 | 82.0 |
| San Pedro | 11 | 502 | 45.6 |

Also sorts on `contacts_attempted`, the most inflatable field on the form.

**Fix:** divide by active area count; rank on an outcome, not an input.

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
| 1 | KI tiles → last complete week + denominator footnote | 🔴 bug | C1 |
| 2 | Goal bars from `AGENT_CONFIG.GOAL_*` × active areas | 🔴 bug | C3 |
| 3 | Zone leaderboard → per-area average | 🔴 bug | C2 |
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
