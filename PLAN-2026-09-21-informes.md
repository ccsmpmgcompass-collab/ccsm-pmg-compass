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
