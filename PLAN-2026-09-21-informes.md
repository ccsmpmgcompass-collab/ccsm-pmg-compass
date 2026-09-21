# PMG Compass — Informes Rebuild Plan

**Written 2026-09-21.** `views/11_Informes.py` replaced: a four-level leadership
report on screen, and a printable council packet generated from the same
numbers. Paired with the audit artifact (findings F1–F9, the level mockups, the
chart inventory, questions Q1–Q28):
https://claude.ai/artifact/LTpn93j4EMYauhGgrSUc9u

Model supplied by Zackary: the Utah Provo mission's own PMG Compass packets —
`AP-MP Council Packet (1).pdf` (45 pp) and
`Provo North & West (PN-W) Zone Packet (1).pdf` (21 pp), both in his Downloads.

Convention as before: audit first, then this numbered plan, one commit per step,
every step verified before its commit, the suite run against its baseline before
every push. A push touching `app/` needs a Reboot of the deployed app
(`dashboard/DEPLOYING.md`).

---

## §1 — Decisions (Zackary, 2026-09-21, answering Q1–Q28)

Recorded here so no step below re-opens them.

| # | Q | Decision | Consequence |
|---|---|---|---|
| 1 | Q1 | **The deliverable is the full packet.** One PDF: cover, print guide, the mission, all 4 zones, all 13 districts, all 45 areas. | §4 Phase P. The screen is still rebuilt (§3), because it is where scope and period are chosen and where the drill-down lives. |
| 2 | Q2 | **Audience is Zackary and the mission president only.** | No role gating (MISSION_ORG cannot support it — decision 33). No per-zone self-serve packet in v1; the run sheet says which pages to hand out on paper. |
| 3 | Q3 | **Spanish only**, screen and packet. | No `t()` wrapping on new strings for this page; Spanish literals, consistent with page names being proper nouns. Existing shared components keep their own i18n. |
| 4 | Q4 | **Cover page, print guide and hand-out run sheet**, as Provo does. | §4 Steps P1, P2. |
| 5 | Q5 | Default period **"Este traslado"**. Full set: Semana pasada · Este traslado · Traslado pasado · Últimas 6 semanas · Mes calendario · Año. | §4 Step R2. |
| 6 | Q6 | **Partial comparisons are shown, with coverage stated** ("4 de 6 semanas"). | Never silently prorate. `sin comparación` chip only when there is genuinely nothing. |
| 7 | Q7 | **"Traslado pasado" means the same number of weeks elapsed**, not all six. | §4 Step R2. |
| 8 | Q8 | **Calendar month is a period too.** | It is the only period that reconciles with TABLEAU_BAPTISMS (decision 21). |
| 9 | Q9 | **Transfer boundaries are drawn on every time axis.** | §4 Step R4. A dashed rule + the cycle number. |
| 10 | Q10 | **All seven Key Indicators at every level, always.** | Standing rule, [[project_seven_key_indicators]]. |
| 11 | Q11 | **Bar fills against the companionships' own `_meta`; leadership's `AREA_TRANSFER_GOALS` is the violet mark.** | Identical to Panel and Desgloses (data-pages decision 6). One vocabulary app-wide. |
| 12 | Q12 | **Raw sum is the headline; per-active-area for every cross-unit comparison.** | A zone league table on raw sums ranks zones by size. `zone_comparison.py`'s rule, inherited. |
| 13 | Q13 | **Conversion rates at mission and zone**, alongside the counts. | §4 Step R5. |
| 14 | Q14 | **Children rank by mean KI attainment**, with a re-rank control on the screen (packet uses the mean). | Not Effectiveness_Score — a composite of a composite is unexplainable in council. |
| 15 | Q15 | **Every child listed, weakest first.** No top-N truncation. | 45 areas at mission scope sit behind a drawer on screen; in the packet they are pages. |
| 16 | Q16 | **Name the weakest units by name at every level, mission included.** | Overrides the audit's "softened at mission" instinct. Safe because of decision 2 — this packet has two readers. |
| 17 | Q17 | **All 21 nightly metrics** per unit, not the 8-metric shortlist. | Provo's "EVERY TRACKED METRIC" table, weakest first. See decision 31 for how they grade. |
| 18 | Q18 | **Scores: the full four at area level with the area's rank in its district; one summary row at zone and mission.** | A table of 45 scores stays Puntajes' job. |
| 19 | Q19 | **Compliance is a headline**, in the subtitle beside the period, at every level. | It qualifies every other number on the page. |
| 20 | Q20 | **Tableau finding data is included**, in its own dated section. | §4 Phase T. Freshness strip mandatory — see decision 32. |
| 21 | Q21 | **Official baptism number where it exists, submitted number elsewhere, each labelled.** | Provo's "About the baptism figure" note, copied in intent. The two will not agree. |
| 22 | Q22 | **A goal that is not a usable yardstick is flagged, not scored.** | §4 Step R6. Fires both directions (too high and too low). |
| 23 | Q23 | **2026-5's 44 areas without a transfer goal read "sin meta"**; compare actuals to actuals. | Never fabricate a back-dated goal. |
| 24 | Q24 | **All 10 zones appear in the Tableau section**, including the six that run no Compass forms. | §4 Step T3. **Form data and Tableau data are never summed into one figure or one table** — see decision 34. |
| 25 | Q25 | **No compression.** Take the pages the content needs. | The packet is ~62 pages (§3.2). The screen keeps detail behind tabs rather than cutting it. |
| 26 | Q26 | **Charts and tables both, and progression shown for every unit** — area, district, zone, mission. | Every unit page carries its own week-by-week strip, not just the mission. |
| 27 | Q27 | **Companionship ≡ area.** One companionship per area; the area view is the companionship view, with their names on it. | Per-missionary history (MISSION_ORG_SNAPSHOT) is explicitly out of scope. |
| 28 | Q28 | **The screen's KI cards reuse the `?ki=` drill-down** from Panel and Desgloses. | `app/components/ki_drilldown.py`, unchanged. |

### 1.1 — Decisions I made from the answers, recorded so they are not re-opened

| # | Decision | Why |
|---|---|---|
| 29 | **PDF engine is ReportLab and nothing else.** Charts are drawn with `reportlab.graphics`, vector, in-process. | Verified 2026-09-21: `pip install reportlab` → 5.0.1, `platypus` + `graphics.charts` import clean. No matplotlib, no Kaleido, no WeasyPrint, **no `packages.txt`** — the repo has never had one and a headless-browser or cairo/Pango dependency is the likeliest way to break the Streamlit Cloud deploy. Vector also prints sharper than any PNG. |
| 30 | **One analytics layer, two renderers.** `app/reports/model.py` builds a pure report model (dataclasses/dicts, no Streamlit, no ReportLab) for any scope × period; `views/11_Informes.py` renders it to screen; `app/reports/packet.py` renders it to PDF. | This is what stops the screen and the packet drifting, and it makes the whole thing testable without either a browser or a PDF reader. It is also the only way P-phase steps can be built and tested before the screen is finished. |
| 31 | **Nightly metrics grade on change, not on the 90/60 bands.** The goal is drawn as a secondary mark and the row's status comes from its movement vs the comparison period. The 90/60 bands (data-pages decision 10) stay for Key Indicators only. | Measured live 2026-09-21 over the current transfer's two complete weeks, per ACTIVE area per week: attainment runs **6% – 67%, median ~42%**. Under 90/60 that is ~18 of 20 rows red every single week, which is precisely what decision 10 exists to prevent. The goals are stretch targets at roughly 2× current performance; the report should not be a wall of red because of it. |
| 32 | **The Tableau section carries a freshness strip and refuses to render a period it cannot cover.** | The stored export ends **2026-08-03** and was uploaded 2026-08-23 — 49 days stale on the day this plan was written, and [[project_tableau_autosync]] has never run live. A packet dated November that silently shows August finding data is worse than a packet with no finding section. |
| 33 | **No role gating anywhere in this work.** | MISSION_ORG has **no `Is_MP` row at all** and exactly one `Is_AP` (a missionary-ID mailbox, not the address he signs in with). Gating today locks out the president. Fixing the roster is a separate, sheet-side task. |
| 34 | **Form-sourced and Tableau-sourced figures never share a total or a table.** | Compass forms cover the 4 pilot zones (45 areas). Tableau covers all 10 zones — and the pilot zones are only **44%** of mission finding volume. Mixing them is the single most misleading thing this packet could do. Every Tableau block is captioned `fuente: Tableau`. |
| 35 | **Tableau names are reconciled against MISSION_ORG, and the misses are reported.** | Measured: the export carries 11 districts and 42 areas for the pilot zones, against 13 and 45 in the roster. Unmatched rows are excluded from roster-scoped figures and their count + volume printed in a data note, exactly as Provo's packet does ("12 area names … accounting for 52 attempts — about 0.6% of activity"). |

### 1.2 — Measured facts this plan is built on (live probe, 2026-09-21)

- `WEEKLY_KI` 184 rows. Complete weeks **2026-08-16 → 2026-09-20 (6)**. Two
  stray rows: `2026-08-09` (1 area) and `2026-09-27` (1 area, a future week).
- `DAILY_LOG` 1,397 rows, **2026-08-09 → 2026-09-20**, 43 distinct dates.
- `WEEKLY_BREAKDOWNS` 217 rows — carries `strength1_metric`,
  `strength2_metric`, `growth_metric` per area per week, already chosen by the
  Apps Script agents. **The area page's "Su fortaleza / Para crecer" reads
  these; it does not recompute them.**
- `SCORES` 501 rows, 9 weeks **2026-07-26 → 2026-09-20**.
- `AREA_TRANSFER_GOALS` 46 rows: all 45 areas for **2026-6**, exactly **one**
  (Los Huertos) for 2026-5.
- `TRANSFER_SCHEDULE`: 2026-4 (06-15), 2026-5 (07-27), **2026-6 (09-07, current)**,
  2026-7 (10-19), 2026-8 (11-30). All six weeks.
- `MISSION_ORG`: **45 active areas, 4 zones, 13 districts** — Angol 9/3,
  Los Angeles Norte 12/4, San Pedro 11/3, Temuco Ñielol 13/3.
- Tableau detail: 89,824 person-rows, **2024-01-01 → 2026-08-03**, uploaded
  2026-08-23. 10 zones, 21 finding sources, 4 finding categories.
- `TABLEAU_BAPTISMS`: 32 rows, MISSION-level by month 2024-01 → 2026-07.
- Nightly reporting in the current transfer's two complete weeks: **456
  area-days of a possible 630 (72%), and all 45 areas reported at least once.**
- Weekly-form reporting by week: 31 · 32 · 30 · 26 · 36 · 27 of 45.

### 1.3 — The comparison constraint

**A transfer-vs-transfer Key Indicator comparison is not honestly available
yet.** WEEKLY_KI starts 2026-08-16; 2026-5 (07-27 → 09-06) has 4 of 6 weeks and
its first two are empty; 2026-6 is 2 weeks old. Neither whole-transfer nor
same-weeks-elapsed has both sides.

- Asterisked comparison available **2026-10-18** (full 2026-6 vs four-sixths of 2026-5).
- First clean one **2026-11-29**, when 2026-7 closes.
- Comparable **today**: the 2 weeks since transfer day (09-13, 09-20) against the
  2 before it (08-30, 09-06) — this measures the transfer-day discontinuity.
- **The reporting-rate trap**: 26 of 45 areas on 09-06 vs 36 on 09-13. Raw sums
  would print a +38% "improvement" that is entirely more forms arriving. Every
  cross-period figure is per-active-area (decision 12) or captioned with its
  reporting rate (decision 6).

Every comparison this report makes must therefore degrade **visibly**. That is a
requirement, not a caveat.

---

## §2 — Architecture

```
app/reports/
  __init__.py
  scope.py       Scope resolution: mission | zone | district | area → area set,
                 children, parents, labels. MISSION_ORG is the only authority.
  periods.py     Period + comparison windows. Transfer/week/month arithmetic,
                 coverage reporting, same-weeks-elapsed pairing.
  model.py       build_report(scope, period, compare) -> ReportModel.
                 Pure. No Streamlit, no ReportLab, no I/O beyond app.db.queries.
  grading.py     Attainment, the 90/60 KI bands, the nightly change bands,
                 and the "meta no utilizable" flag (decisions 22, 31).
  packet.py      ReportModel(s) -> a single PDF. ReportLab only.
  packet_parts.py  Cover, print guide, run sheet, page furniture, the five
                 vector chart primitives.
views/11_Informes.py   ReportModel -> screen.
```

`ReportModel` is the contract. Every step below either fills it or renders it.
It carries, for one scope and one period: identity (level, name, parents,
areas, companion names), coverage (areas active / reporting, days reported),
the seven KIs (actual, meta, leadership goal, change, status), the 21 nightly
metrics (same shape), the four scores, the conversion rates, the ranked
children, the week-by-week series per metric, and the Tableau block (or the
reason it is absent).

---

## §3 — What gets rendered

### 3.1 — The screen (`views/11_Informes.py`)

Control bar: the existing `render_scope_selectors` (prefix `rep`, unchanged) +
Período pills + Comparar-contra pills + **Generar paquete** button. Then the
level-specific body from the audit's §3 mockups, with the `?ki=` drill-down
under the KI cards.

### 3.2 — The packet (~62 pages)

| Pages | Section | Content |
|---|---|---|
| 1 | Cover | Prepared for · period · complete weeks · baptisms this transfer · contents |
| 2 | Print guide | What to print, section→pages→audience table, the hand-out run sheet |
| 3–9 | Mission (7) | M1 where we stand · M2 every KI vs goal · M3 the seven week-by-week · M4 zones ranked · M5 all 21 nightly · M6 baptisms YTD vs 527 · M7 finding, all 10 zones |
| 10–25 | Zones (4 × 4) | Z1 at a glance + 7 KIs · Z2 every KI + all 21 nightly · Z3 districts + all areas weakest-first · Z4 finding + week-by-week |
| 26–38 | Districts (13 × 1) | KIs, areas weakest-first, the three-way line (district / zone / mission), top finding sources |
| 39–61 | Areas (45, 2/page) | Names, 7 KIs vs own goal, fortaleza/crecer, scores + rank, week-by-week |
| 62 | Data note | Sources, the Tableau window, unmatched-name count, which baptism figure is which |

Order within every unit is the same and is deliberate: **outcomes → activity →
process.** KIs, then finding, then nightly work, then compliance and scores.

---

## §4 — Build steps

Phases run **R → P → T → V**. R is the analytics layer plus the screen; P is
the packet; T is the Tableau block for both; V is verification. P depends on R1–R6
but not on the screen steps, so it can start as soon as the model is filled.

### Phase R — the report model and the screen

**R1 — `app/reports/scope.py` + `periods.py`**
New files. Scope resolution from MISSION_ORG (`get_areas_df`), children/parents
per level, and the period windows. Transfer arithmetic reads `TRANSFER_SCHEDULE`
via `get_recent_transfer_dates` (`queries.py:4201`) and
`analytics/transfer_year.py`; weeks are Mon–Sun ending Sunday, matching
WEEKLY_KI. Same-weeks-elapsed pairing (decision 7) and coverage reporting
(decision 6) live here.
*Tests:* `tests/test_report_periods.py` — every period's bounds, the elapsed-weeks
pairing across a transfer boundary, coverage fractions, the 2026-5 partial case.
*Acceptance:* pure functions, no Streamlit import.

**R2 — `app/reports/grading.py`**
Attainment, the KI 90/60 bands (reuse `design_system.goal_bar_status`, do not
re-implement), the nightly change bands (decision 31), and
`goal_is_unusable(actual, goal)` (decision 22) firing below 25% and above 250%
of a normalised pace.
*Tests:* `tests/test_report_grading.py` — band edges, both flag directions, and a
regression asserting the nightly path never returns a 90/60 status.
*Acceptance:* the 20 nightly metrics measured in §1.1 produce 18 usable / 2
flagged, not 18 red.

**R3 — `app/reports/model.py`: identity, coverage, Key Indicators**
`build_report()` for all four levels. KIs read `get_weekly_ki` +
`get_ki_goals_for_week` (`queries.py:740`, keep its W-7 lookup — audit "what's
worth keeping") for the meta, and `AREA_TRANSFER_GOALS` for the mark
(decision 11). Coverage per decision 19.
*Tests:* `tests/test_report_model_ki.py` — the four levels against a fixture
roster; a scope with zero reporting areas; decision 12's sum-vs-per-area split.

**R4 — model: nightly, scores, rates, children, series**
All 21 nightly metrics (decision 17) from `get_daily_log` / `WEEKLY_BREAKDOWNS`;
the four scores (decision 18); the conversion rates via
`analytics/rate_metrics.py` (decision 13); children ranked by mean KI attainment
(decision 14); per-metric week series via `analytics/ki_history.py`
(`weekly_series:216`, `daily_series:443`) with transfer boundaries marked
(decision 9).
*Tests:* `tests/test_report_model_rest.py`.

**R5 — the screen: control bar + mission level**
Rewrite `views/11_Informes.py`. Keep `render_scope_selectors` (prefix `rep`) and
the roster membership rule; delete the week selectbox, the three tables, the two
CSV buttons, and the `get_daily_log(365)` call (F9). Spanish literals
(decision 3).
*Acceptance:* verified at 1400px **and** 375px, zero sideways scroll, measured
with `javascript_tool` not eyeballed.

**R6 — the screen: zone, district, area levels + the `?ki=` drill-down**
The three remaining bodies from the audit mockups, plus `ki_drilldown` under the
cards (decision 28) and `render_companionship_card` at area level (decision 27).

### Phase P — the packet

**P1 — `packet_parts.py`: furniture and the five chart primitives**
Page frame (running head, footer with page number, the "PMG Compass ·
Misión Concepción Sur" rule), the type scale, the three status colours from
`theme.py` (never a second palette — the Phase F lesson), and five vector charts
drawn in `reportlab.graphics`: horizontal bar vs goal with a mark, sparkline,
stage bars, share bar, ranked row.
*Tests:* `tests/test_packet_parts.py` — each primitive returns a Drawing of the
declared size; colours come from `theme.py`.

**P2 — cover, print guide, run sheet** (decision 4). The run sheet's copy counts
come from MISSION_ORG, as Provo's does.

**P3 — the mission pages (M1–M6)**, from one `ReportModel`.

**P4 — the zone pages (Z1–Z3) and the district pages**, looping the model.

**P5 — the area pages**, two to a page, reading `WEEKLY_BREAKDOWNS`'
strength/growth columns (§1.1).

**P6 — assembly, pagination, contents, and the button**
`build_packet(period) -> bytes`, wired to **Generar paquete** with a
`st.download_button`. Page numbers resolve in a second pass so the contents page
and the print guide can name real ranges.
*Acceptance:* a 60+ page PDF opens clean, every footer numbered, Letter, no
clipped furniture at "Actual size".

### Phase T — Tableau

**T1 — freshness gate** (decision 32): the export's real window, its age, and a
refusal path when the requested period falls outside it.
**T2 — roster reconciliation** (decision 35) with the unmatched count surfaced.
**T3 — the blocks**: funnel, channel mix, top sources, outcomes-by-zone — for
all 10 zones at mission level (decision 24), pilot zones at zone/district level.
Reuse `analytics/finding_funnel.py` (`window_buckets:249`, `previous_window:238`).
*Acceptance:* no Tableau figure ever appears in the same total or table as a
form figure (decision 34).

### Phase V — verification

**V1** — the suite against baseline (**11 failed / 1186 passed** as of 2026-09-19;
compare FAILURES, and stash-and-rerun before blaming a change).
**V2** — the screen at 1400px and 375px, both measured.
**V3** — the packet printed to paper at "Actual size" and read.
**V4** — a checklist commit, as Phase F did.

---

## §5 — Risks

1. **The packet is the long pole.** ~62 pages of hand-built layout. If it slips,
   Phase R still ships a usable screen on its own.
2. **Tableau may stay stale.** Decision 32 means the finding section can be
   absent from a packet. That is correct behaviour, not a bug — but it means the
   packet's page count is not fixed, and the contents page must be generated,
   never hardcoded.
3. **`AREA_TRANSFER_GOALS` for 2026-7** must be set before 2026-10-19 or the
   next transfer's packet has no leadership goal to mark (decision 11) — the
   same failure 2026-5 already has.
4. Streamlit 1.40.0 is pinned (`requirements.txt`) for a selectbox regression.
   Adding `reportlab` must not move it.

---

## §6 — AFTER this project: the goals workstream

**Zackary, 2026-09-21: "flag the goals as something we need to work on after
this project is finished."** Not in scope for any step above. Nothing here
blocks the build — the report renders honestly against the goals as they stand,
which is what decisions 22, 23 and 31 are for.

Three separate problems, all about goals, all deferred:

1. **`AREA_TRANSFER_GOALS` has no rows for 2026-7** (starts 2026-10-19). Only
   Zackary can set them, on the Metas page. If this work is still running then,
   the packet correctly prints **"sin meta"** for the leadership mark
   (decision 23) — degraded, not broken. Same gap 2026-5 already has, where 44
   of 45 areas have no goal.
2. **The nightly goals in `AGENT_CONFIG` are stretch targets at roughly 2×
   current performance.** Measured 2026-09-21 per active area per week over the
   current transfer: 6%–67% attainment, median ~42%, e.g. `contacts_attempted`
   97.9 against a configured 150. Decision 31 works around this; it does not fix
   it. *(This supersedes the "242 configured vs ~42 actual" figure in the
   2026-09-19 verification note — that comparison was distorted by the
   reported-days denominator, which was the second of those two open questions.)*
3. **Nothing recalibrates the seven Key Indicators.** `CCSM_Agent2.gs`
   recalibrates NIGHTLY goals every cycle into `GOAL_RECALIBRATION`; the KIs
   stay hand-set forever. A gap to decide about, not a bug.

Sequence when it comes up: (1) is operational and dated; (2) and (3) want a
short audit of their own before anything is changed.

---

## STATUS

*One line per step: step id, commit, any decision made mid-build.*

- **2026-09-21** — Plan written. Audit artifact published. No code yet.
  Answers to Q1–Q28 recorded in §1. Feasibility verified: ReportLab 5.0.1
  installs clean with platypus + graphics; nightly attainment measured at
  6–67% (median ~42%), which set decision 31; Tableau pilot zones measured at
  44% of mission finding volume, which made decision 24 worth doing and
  decision 34 necessary.
- **2026-09-21** — **R1 landed.** `app/reports/` exists: `scope.py` (MISSION_ORG
  is the only authority; `Scope` with its areas, companions, key, trail and
  child level; `resolve` / `children` / `parent` / `walk`) and `periods.py`
  (the six periods of decision 5, complete-week arithmetic, the elapsed-weeks
  pairing of decision 7, transfer boundaries, and `Coverage`). Both pure — the
  acceptance check asserts `streamlit` is absent from `sys.modules` after
  importing them; `load_roster()` and `load_cycles()` are the only two impure
  calls and do nothing but delegate. Tests: `test_report_scope.py` (20),
  `test_report_periods.py` (43). Verified against the live sheet: 45 areas / 4
  zones / 13 districts, `walk()` = 63 scopes, and every period's real window on
  2026-09-21 (this transfer = 2026-6, 09-07..09-21, semana 2 de 6). Suite
  **11 failed / 1310 passed** — the same 11, and the step is purely additive
  (no existing file touched). Decisions made mid-build:
  (a) **a second comparison window**, `COMPARE_PRECEDING` — the same number of
  complete weeks immediately before the period began. §3.1 asks for
  "Comparar-contra **pills**", which needs more than one option, and §1.3
  measured the only honest one available today: the 2 weeks since transfer day
  against the 2 before it (2026-08-30, 09-06), where decision 7's own twin —
  2026-5's first two weeks — rests on a single area. Capped at `ROLLING_WEEKS`
  so "Año" is not offered "38 semanas anteriores", and `available_comparisons`
  drops it when it resolves to the same window as the period's own twin.
  Decision 7 is unchanged and is still the default pill.
  (b) **2026-5 reads "5 de 6 semanas", not §1.3's narrative "4 de 6"** — the
  stray single-area row dated 2026-08-09 is a reported week under any rule that
  does not hide it. `Coverage.reporting_rate` (44.4% of possible area-weeks)
  and `Coverage.thin` carry what a week count cannot.
  (c) **`Coverage.thin`** at 25% of possible area-weeks — marks a window,
  never hides one, so decision 6 ("partial comparisons are shown") stands. The
  floor is measured, not picked: CCSM's real weeks run 26–36 areas of 45
  (58–80%), while the windows it catches sit at 1.1% and 0.4%.
  (d) `transfer_boundaries` (decision 9) lives in `periods.py` now rather than
  waiting for R4 — it is transfer arithmetic — and excludes a cycle starting on
  the window's own first day, since a dashed rule on the axis edge is noise.
  (e) Two test files, not the one §4 names: `scope.py` needs its own.
  (f) The picker's label and the period's label are different strings on
  purpose — the pill reads "Este traslado", the caption reads "2026-6".
  Noted, not fixed: `last_complete_week` delegates to
  `area_helpers.latest_due_sunday` rather than copying its "if today IS Sunday"
  step back; a cycle's final week is therefore not complete on the cycle's own
  last day, which is correct and is pinned by a test.
- **2026-09-21** — **R2 landed.** `app/reports/grading.py`: `attainment`,
  `paced_goal`, `change` / `change_status`, `goal_is_unusable`, and the `Grade`
  both renderers consume via `grade_ki` / `grade_nightly`. Tests:
  `test_report_grading.py` (36). Suite **11 failed / 1346 passed** — the same
  11. **Acceptance met**: on the twenty real measured nightly figures,
  `goal_is_unusable` flags exactly two — `rc_lessons_mcp` (6.4% of goal) and
  `baptismal_calendars` (21.7%) — and nothing comes near the ceiling, so 18
  usable / 2 flagged. Decisions made mid-build:
  (a) **`goal_bar_status`, `goal_bar_color` and the 90/60 tiers moved from
  `design_system.py` to `config/theme.py`**, beside the STATUS palette they
  colour with, and are re-exported from design_system under their original
  names so no existing caller changed. §4 R2 says reuse them rather than
  re-implement, and design_system imports Streamlit — grading cannot. This is
  the only edit to a shipped file in Phase R so far; the 123 tests over
  `test_kpi_pace_goal` / `test_kpi_goal_bar` / `test_ki_drilldown` /
  `test_charts` pass unchanged.
  (b) **`FLAT_BAND` is ±15%**, measured rather than picked: across 100
  metric-weeks (20 metrics × the five week-over-week steps) the median absolute
  change is 15.6%–19.6% on all three candidate bases, so ±15% sits near the
  middle of the real distribution and about half the rows carry a direction.
  ±5% would colour 80–88% of rows — decision 10's wall of red wearing arrows —
  and ±25% would call a genuine quarter-sized drop "steady".
  (c) **The unusable-goal flag is a mission-scope verdict handed down, not
  computed per row.** `grade_ki` / `grade_nightly` take `flag=` as an argument.
  Computing it per row turned "this area produced nothing this fortnight" into
  "the goal is broken", which buries the news — and a `GOAL_*` is one
  mission-wide configured number, so whether it is a usable yardstick is a
  property of the goal, not of one companionship.
  (d) `change_status` distinguishes `before=None` (no comparison period) from
  `before=0` (the comparison period recorded nothing). Conflating them turned
  every absent comparison into good news; a test caught it.
  (e) **Exact counts, correcting §1.1's approximations.** There are **20**
  numeric nightly metrics, not 21 — `effort` is CHOICE and `exchanges` is
  YESNO, both dropped by `non_numeric_metrics()`. Under 90/60 they are **17
  red, 3 amber, none green** (§1.1's "~18 of 20" rounds that). The three above
  60% are `contacts_attempted` 65.3%, `new_people_found` 61.3%,
  `member_contacts` 67.4%.
  (f) **For R4, measured and not to be re-derived:** the 26→36 reporting
  whipsaw of §1.3 is the WEEKLY form, not the nightly one. Areas filing at
  least one nightly report per week run 35 · 35 · 36 · 37 · 43 · 45 of 45. The
  basis still changes the answer, though — `contacts_attempted`'s 09-06→09-13
  step reads **+19.3% per active area and +2.6% per reporting area** — so R4
  must choose the change basis deliberately and say which it used.
- **2026-09-21** — **R3 landed.** `app/reports/model.py`: `ReportModel`,
  `MetricRow`, `NightlyCoverage`, `load_data`, `build_report`, `build_all`. The
  whole §2 contract is declared; R4's fields default empty so the shape never
  changes under the renderers. Tests: `test_report_model_ki.py` (26). Suite
  **11 failed / 1373 passed** — the same 11. Verified live: the four levels
  against CCSM, 63 models in 3.3s from one load, nightly coverage **456 de 630
  (72%)** matching §1.2 exactly. Decisions made mid-build:
  (a) **Loading is split from building.** `load_data()` reads every source
  once; `build_report` is pure over the `ReportData` it returns. The packet's
  63 scopes cannot each re-read the sheet inside what §2 calls a pure layer.
  Two dependencies are injected rather than imported — `ki_goals_fn` (queries'
  W-7 lookup, which keeps its one home) and `transfer_goals`, the whole
  AREA_TRANSFER_GOALS tab via a new `goals_queries.all_area_transfer_goals()`.
  That is what makes the model testable with no sheet at all.
  (b) **Three bases, each named and each carried beside the count it was
  divided by.** `actual` is the headline (decision 12) and is never compared;
  `per_active_area_week` is decision 12's cross-UNIT basis, where a zone whose
  areas go silent ranks lower on purpose (`zone_comparison`'s standing rule);
  `per_reporting_area_week` is what attainment and CHANGE are computed on.
  **This settles R2's open question (f)**: the change basis is per reporting
  area, because it is the only one where a swing in how many areas filed
  cannot masquerade as work.
  (c) **The companionship goal's divisor is every area-week that FILED the
  source form — not `meta_set_by`.** Found by running it live: 2 areas of 39
  wrote a baptism goal of 2 each, and dividing by those 2 read the mission as
  aiming at 2 baptisms per area per week, which flagged the goal unusable at
  0.8%. Dividing by the 68 area-weeks that filed gives 26.2% and no flag. A
  blank meta is a commitment to nothing and belongs in the denominator;
  `meta_set_by` is a caption and never arithmetic.
  (d) **Nightly coverage stops at `compliance_anchor_date`**, not at the
  period's end. Without it a packet built on a Monday morning counted 45
  unfiled reports for a day that had barely started — 456 of 675 instead of
  456 of 630.
  (e) **The compliance headline is the area-WEEK rate over a multi-week
  period** ("63 de 90 informes semanales (70%)"), not the count of areas that
  filed at least once. 39 of 45 areas touched this transfer's two weeks; only
  27 filed the second of them, and "39 de 45" would hide that. A single-week
  period keeps the plain count, which is the sentence a person would say.
  (f) A goal nobody wrote a number in, on a form areas DID file, reads **0 and
  ungraded** — a real commitment to nothing, distinct from a missing goal.
  (g) **The scope's areas are passed to `get_ki_goals_for_week` at every level,
  the mission included.** The old page passed them only when scoped, so five
  off-roster names in WEEKLY_FORM_RAW (Collipulli, Galvarino, Los Sauces,
  Villa Obispo, Huepil & Tucapel & Villa Obispo) fed the mission's goal totals.
  (h) `metric_catalog.strip_form_suffix` made public: the report needs the
  mission's own Spanish names without the form's "(Real)" tail and cannot call
  `ki_short_label`, which translates through Streamlit session state.
  **For R5/P, measured and not to be re-derived:**
  - The two KI sources differ **by design**. `get_weekly_ki` is roster-filtered
    by `CCSM_Agent5A.gs` and lags the raw form by a few areas in the newest
    week (36 vs 39 for 2026-09-13); the form parse carries the five off-roster
    names above. Actuals come from the first, goals from the second, and they
    are only ever compared as rates.
  - At mission scope the DEFAULT comparison pill prints **−63.9%** on new
    people, computed off the single area-week 2026-5's first two weeks hold.
    `comparison_coverage.thin` is True there. Decision 6 says show it with its
    coverage stated, so R5 renders the thin marker — it does not suppress the
    number, and it must not present it bare either.
  - **A real finding for the council**: `ki_friends_first_week_real` is flagged
    `meta no utilizable: demasiado alta` at mission scope — 12 achieved against
    a stated goal of 81 across the transfer's two weeks, 15.5%. It is the only
    one of the seven that flags.
- **2026-09-21** — **R4 landed. Phase R's model is complete.** Added to
  `model.py`: the nightly table, `Scores`, the four conversion rates,
  `ChildRow`, `Series`/`SeriesPoint`, and the strength/growth an area's page
  reads. Tests: `test_report_model_rest.py` (28). Suite **11 failed / 1401
  passed** — the same 11. `build_all` renders all 63 scopes in **1.6s** from
  one load. Decisions made mid-build:
  (a) **The nightly table is 22 rows, not 21.** The 20 summable metrics plus
  the two the nightly form asks that are not numbers: `exchanges` (YESNO) as a
  count of NIGHTS an exchange happened, and `effort` as the agents' own 1–3
  `effort_score` from WEEKLY_BREAKDOWNS, averaged and never summed. Dropping
  them would have been the shortlist decision 17 exists to reject.
  (b) **`get_daily_log` destroys `exchanges`.** Its `_num` pass coerces the
  word "TRUE" to NaN and fills it with 0, so the column arrives as a wall of
  zeros with nothing about the values revealing they were never numbers — the
  exact trap `non_numeric_metrics` documents. `_restore_exchanges` re-derives
  it from the raw tab and merges back on (day, area). 30 nights in the current
  transfer's fortnight, not zero.
  (c) **Attainment takes whichever basis matches its own goal's population.** A
  Key Indicator's goal is the companionships' summed meta, whose population is
  the areas that filed the goal form → per reporting area-week (R3). A nightly
  goal is one mission-wide `GOAL_*` per area per week, whose population is
  every active area → per active area-week. This is what keeps R2's acceptance
  intact: on the reporting basis every nightly figure rises about 40% and only
  one of the two flagged goals would still flag. **Change is always on the
  reporting basis**, both paths.
  (d) `grade_ki` / `grade_nightly` gained a `now=` keyword so attainment and
  change can rest on different bases without a caller assembling `Grade` by
  hand and re-implementing the bands.
  (e) **Children rank on mean attainment per ACTIVE area-week, not on
  `grade.pct`.** A test caught it: a zone of two areas where one filed one week
  and did 30 reads 150% of goal per reporting area-week and would top the
  table; per active area-week it reads 37.5% and is last, which is the zone.
  Decision 12's cross-unit rule, and `zone_comparison`'s standing one. Live,
  the zones rank **San Pedro 29.2% · Los Angeles Norte 32.2% · Temuco Ñielol
  33.5% · Angol 34.3%**.
  (f) **`ki_history.weekly_series` is deliberately NOT reused**, though §4 R4
  names it. It reads WEEKLY_FORM_RAW — five off-roster names, and a few areas
  ahead of WEEKLY_KI in the newest week — while the report's Key Indicator
  actuals come from WEEKLY_KI. A card reading 364 above a strip totalling 430
  is the one failure decision 30 exists to prevent. The strip is built from
  `data.weekly_ki`, the same frame the cards sum, and a test asserts the two
  add up to each other.
  (g) **Strength/growth moved forward from P5 into the model.** P5 reading
  WEEKLY_BREAKDOWNS itself would put a sheet read inside a renderer. Area level
  only — the columns hold one companionship's judgement.
  (h) Every `ReportData` field defaults to empty. A mission that has never run
  the scoring agent gets an empty scores block rather than an exception, and a
  test that only exercises Key Indicators need not hand in a SCORES frame.
  (i) `rates` is `()` below zone level (decision 13), so no renderer can print
  a close rate over one companionship's three lessons by accident.
  **Live figures for R5/P, not to be re-derived:** conversion rates read
  contact **44.7%** (89% of a 50% target), mc **44.2%** (88%), lesson **12.7%**
  (63% of 20%), close **12.3%** (49% of 25%) — the mission still teaches well
  and does not invite, though close_rate has risen from the audit's 9.7%.
  Mission scores over the transfer's two weeks: effort **59.4**, skill
  **69.7**, KI **37.6**, effectiveness **55.4**.
- **2026-09-21** — **R5 landed.** `views/11_Informes.py` rewritten against the
  model: the control bar (scope selectors, Período pills, Comparar-contra
  pills) and seven sections — Indicadores Clave, Semana a semana, the ranked
  children, Trabajo nocturno, Tasas de conversión, Puntajes, Cumplimiento. The
  week selectbox, the three tables, the two CSV buttons and the
  `get_daily_log(365)` call (F9) are all gone. Suite **11 failed / 1402
  passed** — the same 11. **Acceptance met, measured with `javascript_tool`
  and not eyeballed**: at 1400px and at 375px the main pane's `scrollWidth`
  equals its `clientWidth` (1060 and 371) and NO element inside it overflows
  without its own `overflow-x`. Decisions made mid-build:
  (a) **The body renders at every level, not only the mission.** The model has
  the same shape at all four, so one body serves them; R6 adds the
  level-specific extras (the `?ki=` drill-down, `render_companionship_card` at
  area level, the district's three-way line) rather than the bodies
  themselves. A page that broke the moment someone picked a zone would not
  have been shippable on its own, which §5 risk 1 asks Phase R to be.
  (b) **The nightly table is a `ranked_list`, not a `render_table`.** Measured
  at 375px: nine columns rendered 892px wide inside a 338px box. That
  measurement is the one that put `ranked_list`'s wrapping cell strip into the
  design system (auditoría P5), so the remedy already existed. Ordered
  weakest-first (decision 17) via a new `ReportModel.nightly_weakest_first`, so
  the screen and the packet list them the same way.
  (c) **The nightly change needs its own coverage gate.** DAILY_LOG begins
  2026-08-09, so the default comparison — 2026-5's first two weeks — holds
  almost no nights, and the rows were printing "↓ 91%" off one area's evening.
  `NightlyCoverage` gained `usable`/`thin` and the model now carries
  `comparison_nightly_coverage`; the view suppresses both the change and the
  row's colour when it is thin, and says why.
  (d) **The zone table's cells were on the wrong basis.** They were each
  unit's own `grade.pct` while the headline beside them was the per-active-area
  mean, so a row's cells did not average to its own value. Added
  `MetricRow.attainment_per_active_area`, which is also what `_mean_attainment`
  now uses.
  (e) **`render_section_tabs` opens on the first option, which is display order,
  not the default.** Seeded `rep_period_section` to `P.DEFAULT_PERIOD` so the
  page opens on "Este traslado" (decision 5).
  (f) **Decision 3 collided with a project-wide guard.**
  `test_final_verification.test_no_ui_literal_bypasses_translation` fails any
  UI literal that does not reach `t()`, and this page is Spanish-only by
  Zackary's answer to Q3. Resolved with an opt-in per-file marker —
  `tools/i18n_coverage.SPANISH_ONLY_MARKER`, declared in the page's own
  docstring — rather than a directory exclusion that would have taken a dozen
  bilingual pages with it. A new test pins the opt-out list to exactly
  `["views/11_Informes.py"]`, so the next page to try it has to change that
  list first.
  (g) **Generar paquete is deliberately absent**, not present-and-disabled. It
  arrives with P6.
  **Noted, not fixed:** WEEKLY_BREAKDOWNS' newest week is **2026-09-13**, a
  week behind WEEKLY_KI's 09-20, so on "Semana pasada" the effort score and the
  strength/growth lines read "—" for the whole mission. That is the tab
  lagging, not a bug here, but P5 should expect it.
- **2026-09-21** — **R6 landed. PHASE R IS COMPLETE.** The `?ki=` drill-down
  sits under the Key Indicator cards (decision 28, `ki_drilldown` unchanged),
  `render_companionship_card` heads the area page (decision 27), "Su fortaleza
  · Para crecer" reads WEEKLY_BREAKDOWNS' own choice, and every area of a
  mission or a zone is ranked behind a drawer. Tests: +3, 31 in
  `test_report_model_rest.py`. Suite **11 failed / 1407 passed** — the same 11.
  **Verified at 1400px and 375px at all four levels with the drill-down open**:
  the main pane's `scrollWidth` equals its `clientWidth` at both, and the only
  elements reporting overflow are SVG `<text>` nodes inside the drill-down's
  own Plotly chart, which are bounded by its viewBox. Decisions made mid-build:
  (a) **R6 is the level-specific EXTRAS, not three more bodies.** R5 already
  rendered every level from the model, so the three remaining mockups needed
  the companionship card, the strengths block and the area drawer — not three
  parallel page bodies that would have had to be kept in step.
  (b) **`Period.progress_label` now reads "2 de 6 semanas completas".** The
  drill-down prints "cambio 2026-6 · semana 3 de 6" — the week today falls in —
  on the same screen, and "semana 2 de 6" beside it reads like one of them is
  wrong. Both are true; mine now says which it means. Changed here rather than
  in the shared component, which decision 28 keeps unchanged.
  (c) Card links go through `ki_href` carrying `rep_zone` / `rep_district` /
  `rep_area`, so the full reload a drill-down link causes lands back on the
  same unit instead of the whole mission.
  (d) `areas_ranked` is filled at mission and zone only — at district level the
  areas already ARE `children`, and the same list under two headings is noise.
  (e) **The district's three-way line (district / zone / mission) is not on
  screen; it moves to P4**, where §3.2 actually places it — the packet's
  district page. `build_all` already returns all 63 models, so P4 looks up the
  parent and the mission by `Scope.key` rather than the model growing a
  peer-series field that only one page would read.

- **2026-09-21** — **P1 landed.** `app/reports/packet_parts.py`: the page
  (Letter, the margins, the running head and the footer), the type scale (nine
  steps, base-14 Helvetica, no font file ships), the print colour tokens, and
  the five vector charts of §4 P1 — `bar_vs_goal`, `sparkline`, `stage_bars`,
  `share_bar`, `ranked_row`. Tests: `test_packet_parts.py` (45). `reportlab`
  added to `requirements.txt`; it pulls only pillow and charset-normalizer,
  both already resolved, and **does not move the streamlit pin** (§5 risk 4,
  checked with `pip install --dry-run`). Decisions made mid-build:
  (a) **The print palette lives in `theme.py` beside the screen's, as
  PRINT_\*.** Measured on white, STATUS' green reads **2.03:1** and its amber
  **1.89:1** — a highlighter, not a grade. The print values are the audit
  artifact's own light-mode tokens (good 3.49:1, warn 3.90:1, bad 4.69:1, mark
  4.88:1). This is not a second palette: it is the same three states re-valued
  for the other surface, in the same file, which is what "never a second
  palette" was protecting. **SERIES_COLORS needed no print variant at all** —
  measured on white the eight run 3.07:1 to 4.95:1, because a categorical
  palette is built for separation rather than brightness, so a zone is the
  same colour on the screen and on the page.
  (b) **3:1, not 4.5:1, and colour is never the only channel.** A status is
  carried by a filled dot or bar AND by the word beside it (`STATUS_WORD`:
  "al ritmo" / "atrasado" / "muy atrasado"), so the non-text threshold is the
  right one — and half these pages get photocopied in black and white.
  (c) **Every direction is a drawn triangle, never a typed arrow.** Measured:
  ReportLab silently font-switches a character the base-14 encoding cannot
  reach — "↑" is emitted in **Symbol**, "▲" in **ZapfDingbats** — so a change
  chip would print in a different typeface from the number beside it and
  nothing in the build would say so. Every string goes through `text()`, which
  normalises the ten characters the app's vocabulary carries and folds or drops
  the rest; a test runs the packet's strings through it and fails if any
  changes.
  (d) **The furniture is drawn on `onPageEnd`, not `onPage`.** A `SetFurniture`
  marker at the top of a unit's first page has not run yet when onPage fires,
  so the head would name the *previous* unit — wrong on exactly the first page
  of every section, which is the page anybody checks.
  (e) **`Tc` is text state and survives `ET`.** Setting the character spacing
  only when non-zero left the section note inheriting its label's 0.9pt: it set
  30pt wider than it measured and ran over the right margin. Found by rendering
  a page and looking at it, not by a test — right-aligned text that overflows
  to the RIGHT is invisible to anything measuring widths. `draw_tracked` now
  always emits it, and a test reads the content stream to pin that.
  (f) **The sparkline BREAKS at a week nobody reported** rather than joining
  across it, which is where it parts company with `design_system.sparkline_svg`
  (that filters the gaps out). On a 96px card drawing through is right; on a
  printed page a straight run through a silent week is a claim that the week
  happened, and this packet's argument is that a silent week is news.
  (g) `ranked_row` draws a whole row as one Drawing — rank, dot, name, sub,
  measures, bar, value — rather than being assembled from table cells, so the
  screen's row and the printed row cannot drift. Names truncate by MEASURE:
  the widest of the 45 real areas ("Purén y Los Sauces") sets at 67pt against a
  column of 246, so nothing truncates today.
  **For P2–P6, measured and not to be re-derived:** the content box is
  **520 × 688pt**; a `RankedSpec` at that width leaves a 246pt name column with
  three measure columns; `stage_bars` of five stages is 111pt tall and
  `share_bar` of three parts 27pt. Verification of a printed page is
  `pypdfium2` (installed into the venv, **not** in requirements) rendering to
  PNG — the browser pane cannot screenshot a local PDF.

- **2026-09-21** — **P2 and P3 landed, in one commit.** The two steps' edits
  interleave in the same two files — P3's page blocks are built on the table
  helper P2 added — and splitting them after the fact would have meant
  reverting working code to fabricate a boundary. Recorded here rather than
  pretended away; the next steps go back to one commit each.
  `app/reports/packet.py` is new: `Section` / `HandOut` / `Pagination` /
  `SectionStart`, `leadership`, `hand_outs`, `sections_for`, `front_matter`,
  the mission pages M1–M5, and `build_packet`. `packet_parts.py` gained
  `TrackedLabel`, `table`, `cover_page`, `print_guide`, and the page blocks
  `stat_tiles`, `metric_table`, `week_table` and `legend`. Tests:
  `test_packet_front_matter.py` (20) and `test_packet_mission.py` (22). Suite
  **11 failed / 1494 passed** — the same 11. Live: **63 models, 71 pages, 3.0s
  to render** from one sheet read. Decisions made mid-build:
  (a) **Page numbers resolve by laying the document out repeatedly until a
  pass confirms what it was handed** — not by a fixed two passes. Printing the
  first pass's ranges lengthens the guide, which moves everything after it, and
  that correction can itself move a row. `MAX_PASSES` is 3; the live packet
  settles in 2, and a test asserts it.
  (b) **`app/config/es_display.py`** holds the Spanish month names, the date
  shapes and the number conventions, because `app/i18n/__init__.py` imports
  Streamlit and the report layer cannot. `i18n/formats.py` now takes its
  Spanish tables and its digit grouping from there, so a month still cannot be
  spelled two ways. Same move, same reason, as R2's goal-bar tiers.
  `Period.window_label` / `elapsed_label` were added on top of it.
  (c) **The run sheet names every zone and every district by name**, with its
  own page range and its own copy count, instead of Provo's single "give them
  their own zone packet" row — decision 2 means there is no separate zone PDF
  to give them. **Measured: 4 zone leaders and 12 district leaders in
  MISSION_ORG against 13 districts**; San Pedro's La Marina 1 has none and is
  the assistants' own area. That row prints 0 copies and says why, and the
  closing note carries the count. Never one copy for a leader the roster does
  not know about.
  (d) **M6 and M7 move to phase T.** §3.2 puts baptisms-vs-the-annual-goal and
  the finding section on the mission's pages, but both read TABLEAU_BAPTISMS
  and the Tableau export. Building them here would have put a Tableau figure on
  a form-sourced page without the freshness gate (decision 32) or decision 34's
  separation. P3 is therefore M1–M5.
  (e) **A change measured across a THIN window keeps its number and loses its
  arrow.** `Coverage.thin` marks the live default comparison — 2026-5's first
  two weeks, one area — and every one of the seven Key Indicators prints
  between −36% and −65% off it. Seven red triangles down a council page would
  report that area's fortnight as the mission collapsing. Decision 6 says show
  the partial comparison; §1.3 says degrade visibly; so the figure prints grey
  with no triangle and the note says there is nothing to sustain a direction.
  (f) **The week-by-week block prints the weeks' own figures, not just a
  line.** A line through two points is a straight line whatever the points
  are, and the current transfer has exactly two complete weeks — the first
  version of that page was seven identical diagonal strokes. `week_table` adds
  a column per week up to **six** (`WEEK_COLUMN_LIMIT`; "Año" runs to 38 and
  falls back to the line) **and a footer row counting the areas that filed each
  week** — 36 then 27 live. Without it, 211 → 153 new people reads as the
  mission halving when nine fewer companionships sent a form (§1.3's trap).
  (g) **A nightly bar draws in the magnitude blue, not in a grade colour.**
  Decision 31 puts the row's status on its movement; the bar is its distance
  from a goal set at roughly twice what the mission does, so `bar_vs_goal`
  gained a `fill` override and the ungraded grey stays for "no reading".
  (h) **The purity tests run in a subprocess.** The first version deleted
  streamlit from `sys.modules` and reloaded — it passed, and broke **122** later
  tests in the same session, every one that had monkeypatched something inside
  the module object it no longer shared. A cold interpreter is isolated and is
  the stronger claim: it tests the import graph, not what the session happens
  to have loaded.
  **Found by rendering and looking, not by a test:** `ranked_row`'s sub-line
  sat at y = −0.7 and printed over whatever the page put underneath (a Drawing
  does not clip, so nothing complains); a table cell holding a LIST of
  flowables printed its own repr, three hundred characters of ParaFrag per row,
  across the whole 22-row nightly table; and tile labels truncated to "AMIGOS
  EN LA REUNIÓN SACR..." until they learned to wrap onto a second line.
  **For P4–P6, measured and not to be re-derived:** the mission section is 5
  pages; the whole packet with stub zone/district/area pages is 71; a
  `RankedSpec` at 520pt with three measure columns leaves a 246pt name column;
  `metric_table`'s six columns are 150/44/44/120/96/66; `week_table` is
  150 + 70 + weeks + 48.

- **2026-09-21** — **P4 landed.** The zone pages and the district pages, from
  the same builders the mission uses. `packet.py` gained `at_a_glance`,
  `key_indicator_page`, `week_page`, `children_page`, `areas_page`,
  `nightly_page`, `rates_and_scores`, `ranked_unit_rows`, `peer_rows`,
  `zone_pages` and `district_pages`; `PAGES` dispatches on level. Tests:
  `test_packet_units.py` (16). Suite **11 failed / 1512 passed** — the same 11.
  Live: **130 pages**. Decisions made mid-build:
  (a) **One set of blocks serves every level**, as R5 decision (a) found for
  the screen: the model has the same shape at all four, the reader is the same
  reader one rung down, and Provo opens a zone page exactly like its mission
  page. The district's order differs (its three-way comparison comes second)
  and nothing else does.
  (b) **The district's three-way comparison is three ranked ROWS, not a line.**
  It is the page's reason for existing — "a 73% means nothing until you can
  see the zone at 78 and the mission at 76" — and three rows of the packet's
  own ranked shape print legibly at 7,5pt and photocopy, which a three-series
  line chart at that size does not. It reads `build_all`'s own models by
  `Scope.key` (R6's note), so nothing is recomputed.
  (c) **A unit nobody reported keeps its place and loses its rank NUMBER.** An
  area that filed no form is not the ninth-best area; it is one nobody can
  rank, and printing "9" beside it invites exactly the reading the grey dot is
  trying to prevent. Its sub-line says "sin informes en el período".
  (d) **A ranked row does not repeat the unit whose page it is on**: on Angol's
  own page an area is "El Mirador", not "Angol · El Mirador".
  (e) **A leadership goal past the end of the bar gets an arrowhead outside the
  track, and its figure in the row's note.** Clamped, four different transfer
  goals all read as "exactly at the line" — and on CCSM that is the common
  case, because leadership routinely asks for more than the companionships
  promised.
  (f) **Outcomes, then activity, then process.** The rates and the scores moved
  to the END of a unit's pages. A council reads a judgement about how the work
  was done after it knows what the work was, and the scores are ungraded on
  purpose: they are the agent's 0–100 composites, not a percentage of a goal,
  and the 90/60 bands would claim they were.
  (g) **§3.2's "13 districts, one page each" was an estimate and the decisions
  outrank it.** Decision 10 gives every unit all seven Key Indicators and
  decision 17 all twenty-two nightly metrics, so a district prints five pages
  and the packet is **130**. The contents no longer asserts a count: `describe`
  measures it after a pass and writes "5 páginas cada uno". **Worth raising
  with Zackary** — 130 pages at two full copies is 220 sheets, and decision 25
  (no compression) is his to revisit.
  (h) The zone's district table and its area table share a page rather than
  each starting one: a zone of three districts left two thirds of a sheet
  blank.
  **Found by rendering, not by a test:** the nightly block measured **693pt
  against 688pt of frame** — five points over — which put its last note alone
  on a page of its own behind every unit in the packet. `metric_table`'s row
  padding is 3.5pt now and a test pins the height budget.

- **2026-09-21** — **P5 landed.** The area pages, two to a page. `area_block`
  in `packet.py`, `area_metric_table` / `AREA_COLUMNS` / `companionship_line`
  in `packet_parts.py`, and `_body` now groups the areas into spreads instead
  of one unit per page. Tests: `test_packet_areas.py` (16). Suite **11 failed /
  1526 passed** — the same 11. Live: **108 pages** (the 45 areas print on 23
  sheets instead of 45). Decisions made mid-build:
  (a) **Each Key Indicator carries its own weeks in the column where the change
  would be.** §3.2 asks the area page for a week-by-week and there is no room
  for a table of its own on a half page — and a companionship's question is
  not "how did this move against a window somebody else chose" but "what have
  our six weeks looked like". `MetricLine.spark` takes the change chip's
  column when it is present.
  (b) **All seven Key Indicators at area level too.** The half page is exactly
  where it would have been tempting to drop to four; decision 10 is a standing
  rule, not a filter, and `AREA_COLUMNS` buys the room by narrowing the figure
  columns, which at area level hold single and double digits.
  (c) **The running head on an area spread says "Áreas", not a district.** The
  pairs run alphabetically across the whole mission, so the two areas on a page
  need not share one — the first draft headed a page "Distrito · La Marina 1"
  above an area from San Pedro 1. Each block states its own district under its
  own name.
  (d) **`scope.companion_names` printed "nan".** An empty companion cell
  arrives from pandas as `float("nan")` and `str(nan)` is the four-letter word,
  which the old one-liner put on the page as a missionary's name. Found by a
  fixture whose area had no companions at all; the live roster fills blanks
  with empty strings, so nothing had shown it. Both the float and the string
  are dropped now.
  (e) "Su fortaleza / Para crecer" is **read**, and an area the agents have not
  written up says which tab is lagging rather than going blank.
  **Measured:** an area's block is 142–280pt against a half page of 338pt, and
  a test asserts every one of them fits.

- **2026-09-21** — **P6 landed. PHASE P IS COMPLETE.** The data note, the one
  call the screen makes (`packet.build(period) -> bytes`, plus `filename`), and
  **Generar paquete** on `views/11_Informes.py`. Tests:
  `test_packet_build.py` (18) — this file IS the phase's acceptance. Suite
  **11 failed / 1544 passed** — the same 11. Decisions made mid-build:
  (a) **Two controls, not one.** `st.download_button` needs the bytes before it
  is drawn and building them takes about a minute on the live sheet, so a
  download button on its own would rebuild the whole packet on every rerun —
  including the reruns a period pill causes. The first button builds and parks
  the result in session state keyed by the period; the second hands it over.
  Changing the período pill therefore offers a fresh build rather than
  yesterday's bytes under today's label.
  (b) **The packet is always the whole mission**, whatever the selectors point
  at: it contains that unit's pages either way, and a packet whose contents
  changed with a dropdown would be a different document under the same name.
  (c) **The data note names what is missing, not only what is there** — the six
  silent areas by name, the goals that are not yardsticks (Key Indicator and
  nightly), and why there is no finding section at all. A reader who wants to
  argue with a number should be able to find out what it is made of without
  asking anybody; that is the only thing that makes the rest safe to hand out.
  (d) The contents' page counts read as Spanish: "dos por página" rather than
  "0,5 páginas cada una", and "cada una" for a zona or an área.
  **ACCEPTANCE MET, and measured rather than eyeballed.** `test_packet_build.py`
  checks all four of §4 P6's: every page is **612 × 792** (Letter); every page
  but the cover carries its own number; no page is blank; and nothing is drawn
  into the running head's band or the footer's — read off each page's content
  stream, tracking the `q`/`cm`/`Q` translations, because a `Tm` inside a
  flowable is in local coordinates and the first version of that test read a
  footer at y=1.5 and called it a flowable in the margin. In the running app at
  **1400px and at 375px**: the button builds the real packet (**108 pages, 374
  KB**), the download button appears carrying
  `paquete-consejo-this_transfer-2026-09-21.pdf`, and the main pane's
  `scrollWidth` equals its `clientWidth` at both (1060 and 371) with nothing
  overflowing at 375.
  **Note:** `pypdfium2` was installed into the venv to rasterize pages for
  looking at, and **uninstalled at the end of the phase** — it is not in
  `requirements.txt` and nothing in the app or the tests imports it.

- **2026-09-21** — **T1 landed.** `app/reports/tableau.py`: `Export` (the
  stored export described rather than trusted — its real first and last
  found-date, its age, the freshness strip decision 32 makes mandatory) and
  `Window` + `clip` / `preceding` / `clamp` (what a period can honestly be
  answered over). Pure, and the purity test runs in a subprocess as P3's does.
  Tests: `test_report_tableau_gate.py` (20). Decisions made mid-build:
  (a) **The export is no longer stale. The premise of decision 32 has
  changed, the decision has not.** [[project_tableau_autosync]]'s run #17
  landed at 19:47 UTC today: the stored export is **99.425 people ending
  2026-09-17**, four days behind, against the 2026-08-03 / 49 days the plan
  was written on. So the packet WILL have a finding section — but the gate is
  what makes that a fact rather than an assumption, and it is built exactly as
  planned.
  (b) **The gate keys on COVERAGE OF THE PERIOD, not on the age of the
  export.** Those come apart and conflating them fails both ways: "Traslado
  pasado" closed on 09-06 and an export a month late still answers every day
  of it, while "Semana pasada" against an export six days behind covers one
  day of seven. Age is printed (the freshness strip) and never gated on. §4
  T1's "refusal path when the requested period falls outside it" is coverage,
  read literally.
  (c) **`MIN_WINDOW_COVERAGE` is 25%**, the same floor as
  `periods.THIN_REPORTING_RATE` and for the same reason. Measured against the
  live export, the six periods cover **57% · 73% · 100% · 93% · 81% · 98%** of
  their own days, so nothing is refused today; the floor bites when the export
  goes a week behind, which is when "Semana pasada" would print one evening
  under a week's name.
  (d) **The comparison is taken from the CLIPPED window, not from the
  period.** Eleven days of this transfer against forty-two of the last one
  would print a collapse that is entirely the two windows being different
  sizes. `preceding` is `finding_funnel.previous_window` over the clipped
  window, so both sides are always the same length, and `clamp` refuses
  outright rather than returning a short one — an unequal comparison is worse
  than none.
  (e) The window's own caption carries `fuente: Tableau` (decision 34) rather
  than leaving it to each caller, so a block cannot be drawn without it.
  **Measured live, not to be re-derived:** the export holds **99.425 rows,
  2024-01-01 → 2026-09-17**, uploaded `auto:tableau` 2026-09-21 19:47 UTC; the
  pilot four zones are **42.9%** of its volume (42.616 rows), close to §1.1's
  44%; it carries **10 zones, 4 finding categories and 21 finding sources**.

- **2026-09-21** — **T2 landed.** `Reconciliation` / `reconcile` /
  `for_areas` / `in_window` in `tableau.py`. Tests: +7, **27** in
  `test_report_tableau_gate.py`. Decisions made mid-build:
  (a) **A row is claimed by AREA NAME and by nothing else.** The export
  carries its own zone, district and area columns; only the area one decides
  membership, and the zone and district a figure is filed under are
  MISSION_ORG's — `scope.py`'s standing rule, because those columns record
  where an area was when the row was written. **The export's district column
  disagrees with the roster about four district names today** (Alemania 2,
  Boca Sur 1, Cabrero, Caopolicán 1 1 against 13 roster districts) and it
  changes no figure in this packet, because nothing reads it. Reporting that
  mismatch would be reporting a discrepancy with no consequence; the data
  note says instead that zone and district come from MISSION_ORG.
  (b) **Reconciliation is scoped to the pilot zones.** The other six zones are
  not unmatched names, they are zones this pilot does not cover, and counting
  them as misses would report **57% of the mission** as a data error.
  (c) **The miss is reported both directions.** `unknown` is export names the
  roster does not carry — dropped from every roster-scoped figure, which is
  decision 35's exclusion. `missing` is roster areas the export never names,
  which is not an exclusion but a silence a zone leader should know about.
  Zero of those today.
  (d) The unmatched names print separated by middots, not commas: one of the
  three live names is "Huequen, Renaico & Tijeral 2" and a comma-separated
  list reads it as two areas.
  **Measured live, and much better than §1.1 assumed:** all **45** roster
  areas now appear in the export, and the unmatched names are **3**, worth
  **23 people — 0,05%** of the pilot zones' 42.616. Decision 35 was written
  against 11 districts and 42 areas; the fresh export carries every roster
  area. The four zones in the current transfer's window hold 130 · 181 · 188 ·
  187 rows.

- **2026-09-21** — **T3 landed** (the analytics; the two renderers are T4 and
  T5 — see (a)). `tableau.py` gained the Spanish vocabulary, `maturity_days`,
  `Stage` / `Share` / `UnitRow`, `funnel` / `channel_mix` / `top_sources` /
  `zone_rows` / `unit_rows`, `Baptisms`, and `Block` + `build_block`;
  `model.py` loads the export once and `ReportModel.tableau` is filled at last.
  Tests: `test_report_tableau_blocks.py` (24). Suite **11 failed / 1595
  passed** — the same 11. Live: **63 models in 4.7s** (from 1.6s — the export
  read is 21s of the load, once). Decisions made mid-build:
  (a) **Phase T runs in five steps, not three.** §4 names T1–T3 and P3's note
  (d) moved M6 and M7 here as well, so "the blocks" is the analytics AND two
  renderers AND two new mission pages. Split: T3 is the model, T4 the packet,
  T5 the screen. One commit each, as the convention asks.
  (b) **THE BIG ONE — the funnel is a COHORT reading, and a young cohort's
  bottom is empty by construction.** `compute_funnel_stage_counts` takes the
  people FOUND in the window and asks how far each has since travelled.
  Measured over the whole export, days from found to milestone (p75, among
  those who got there): contact attempted **6** · contacted **10** · being
  taught **5** · attended church **33** · baptism date **52** · **baptized
  133**. Over this transfer's eleven days exactly **1%** of eventual baptisms
  have happened, so the row reads **0** — on a packet whose baptism page says
  19 for September. A flat contradiction, on two pages of one document.
  **So a stage is MATURE only when the window is at least as long as its own
  p75 lag.** An immature stage keeps its count (decision 25) and loses its
  percentage, its direction and its eligibility to be the funnel's named worst
  step; the block carries a sentence saying which stages those are and
  pointing at the baptism page for the real figure. Live, the top four mature
  and the bottom three do not. p75 rather than the median because a median
  means half the events have not happened yet; measured from the export rather
  than hardcoded, so it tracks the mission's own pace.
  (c) **An AREA gets no Tableau block.** Its half page is 338pt against a
  block P5 measured at 142–280pt, and eleven days of one companionship's
  finding is four people; a funnel over four people is decoration. Its finding
  work is in its Key Indicators, which are its own report of it.
  (d) **The mission's block is the only place in this report where MISSION_ORG
  is not the authority.** Decision 24 puts all ten zones on it, and six of them
  have no roster, so it reads the export's own zone column and every row says
  whether it is a pilot zone. `Block.scope_note` prints that difference out
  loud, because nothing else in the packet changes population from one page to
  the next.
  (e) **The open month is held apart from the certified series** — the same
  trap `get_mission_baptisms_by_month` learned on 2026-09-19. September's 19
  is printed as "sin cerrar" beside the year, never as a point on it, or the
  cumulative line collapses every time the packet is built mid-month.
  (f) **The finding SOURCES are translated here for the first time.** Nothing
  in the app had Spanish for them — the Embudo prints them as written — and
  decision 3 is Spanish only. Free text from Tableau, so an unlisted value
  falls back to itself: a source the mission has never used should appear, not
  vanish into "Desconocido". The stage and category strings are repeated from
  `app/i18n/es.py` (which cannot be imported — Streamlit) and a test asserts
  the two copies agree.
  (g) The gate and the windowed frames are memoised **per period, not per
  scope**: the same eleven days answer for the mission and for all 45 areas,
  and `in_window` over 99.425 rows is the whole cost of the block.
  **Measured live, not to be re-derived:** this transfer's window holds **1.633
  people** mission-wide against 1.581 in the fortnight before (+3%); the mix is
  **Misioneros 1.279 · Medios 298 · Miembros 53 · Centros 3**; the top sources
  are contacto en la calle 678 and casa por casa 515. Zones by contact rate,
  weakest first: **Temuco Cautín 55% · Temuco Ñielol 64% · Arauco 67% · San
  Pedro 70%**, best Los Angeles Norte 83%. Baptisms: **319 certified through
  August against a goal of 527** — 60,5% of the year's goal, **32,3 behind
  pace**, landing at **478** — plus 19 uncertified in September.

### Phase R is done. What Phase P starts from

`app/reports/` is `scope.py`, `periods.py`, `grading.py`, `model.py` — all
pure, all tested (**156 tests across five files**), and `build_all()` returns
the 63 `ReportModel`s the packet prints in **1.6 seconds from one sheet read**.
`views/11_Informes.py` renders one of them and does no arithmetic. P1–P6 render
the same objects to ReportLab; nothing in Phase P should need a new query.
