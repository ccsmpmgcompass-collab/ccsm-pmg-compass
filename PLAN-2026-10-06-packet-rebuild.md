# PMG Compass — Council Packet Rebuild (for the mission president)

**Written 2026-10-06**, from `AUDIT-2026-10-06-council-packet.md` (scored
41.5/100, answered the same day as decisions 44–51). Zackary: *"the best
numerical informe … focus a mission president looking for areas to focus on
and grow."*

The audit is the evidence and this file is the build. Read the audit's §2–§4
for any finding id used below (C1–C4, H1–H6, M1–M6, L1–L2).

Convention as before: one commit per step, named with the step id, every step
verified before its commit, the suite run against baseline before every push,
STATUS appended after every step. **One phase per chat** — the chat is cleared
between phases, so this file must be enough to resume from. A push touching
`dashboard/app/` or `dashboard/views/` needs a **Reboot** of the deployed app
(`dashboard/DEPLOYING.md`).

---

## §1 — Decisions (Zackary, 2026-10-06) — never re-open

Carried from AUDIT §7.1. They continue the clarity pass's 36–43.

| # | Decision | Replaces |
|---|---|---|
| 44 | Every Key Indicator is **graded (coloured) against leadership's goal** (`AREA_TRANSFER_GOALS`). The companionship's own goal prints as an uncoloured *compromiso* column. | 11 |
| 45 | Units are **ranked by a goal-free productivity index**: output per active companionship-week relative to the mission (100 = mission), weighted toward the results nearest baptism. Reporting becomes its own list. | 14 |
| 46 | **The 527 annual goal (all ten zones) is the baptism target.** Leadership's transfer baptism goals may be shown; they never drive colour. | — |
| 47 | **Zones and districts get a baptism figure from Tableau's person-level export** (`confirmation_date` by roster area), labelled "registros de Tableau". The mission keeps the certified figure. | 42, below mission level only |
| 48 | **All four forecasts print** — transfer finish, needed per week, annual landing, baptism pipeline — at mission and zone level, always a range with a one-line method, never coloured as a verdict. | — |
| 49 | **About 45 pages** for a full transfer copy (from 104). | 25 |
| 50 | The weekly packet keeps **the same structure** as the transfer packet. No short variant. | — |
| 51 | **Both renderers change** — the Informes screen and the PDF. One model (decision 30 holds). | — |
| 52 | (P6, 2026-10-07) **Same weeks in other years, Tableau only**, in its own block, never a tablero column (decision 34). | — |
| 53 | (P7) **"Qué cambió" is recomputed** from today's sheet, not stored; it says "con los informes de hoy". | — |
| 54 | (P8) **Lever sizing**: per zone, what closing its biggest leak to the mission's rate would add, a range, uncoloured, ranked; mission page + zone opening. | — |
| 55 | (P9) **District pipeline** on the district page; under 15 open dates "pocas fechas", no range. | — |
| 56 | (P10) **Goal sanity line**: leadership's transfer goal against the mission's best transfer; grading stays on leadership's goal (44 holds). | — |
| 57 | (P11) **A one-page *Resumen* as page 2**; *Cómo leer* moves to page 3; **≈48 pages is fine** for a transfer copy. | 49's ≈45 |

Decisions 1–43 still hold except where a row above names them.

---

## §2 — Proposals for the details §7.1 left open (NOT decided — need his word before the phase that uses them)

Each is measured on live data, 2026-10-06, *Este traslado* (2026-6, 4 of 6
weeks complete).

### P1 — Index members and weights (Phase 1)

**Proposal: six Key Indicators, weighted 3 · 2 · 2 · 1 · 1 · 1.**

| Member | Weight | Why |
|---|---:|---|
| Amigos con Fecha Bautismal | 3 | The result nearest baptism with enough volume to trust (167 this transfer) |
| Amigos en la Reunión Sacramental | 2 | Near baptism, 216 |
| Conversos Recientes en la Iglesia | 2 | Retention; 210 |
| Lecciones con Miembros | 1 | Activity, 528 |
| Nuevas Personas Encontradas | 1 | Activity, 806 |
| Amigos en la Iglesia (Primera Semana) | 1 | Near baptism but thin (41) |
| *Bautizados y Confirmados (form)* | 0 | 7 events mission-wide; decision 37's reasoning. Phase 2 may add Tableau baptisms at zone level as a separate line, not inside the index |

Index = Σ wₖ · (unit's rate per active area-week ÷ mission's) / Σ wₖ × 100.
Each member's ratio is **capped at 250** so one tiny count cannot carry a unit,
and a unit whose weighted event count is under 20 prints its index with
"pocas cifras" and no colour.

Measured (each member as % of the mission, then the index):

| Zone | new | mlz | sac | 1wk | date | rc | **P1 index** | audit's 3-member |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Temuco Ñielol | 106 | 90 | 82 | 93 | 77 | 69 | **82** | 76 |
| Angol | 83 | 96 | 127 | 98 | 108 | 45 | **94** | 93 |
| Los Angeles Norte | 115 | 119 | 78 | 82 | 128 | 123 | **110** | 110 |
| San Pedro | 91 | 95 | 123 | 130 | 91 | 156 | **115** | 123 |

Same order as the audit's measure; the packet today prints the reverse
(Angol last, Ñielol first).

### P2 — How a zone's baptisms are graded under decision 46 (Phase 2)

527 is a ten-zone figure and the roster knows four zones, so a "zone share" has
to come from Tableau, which knows all ten.

**Proposal:** a zone's reference line = 527 × the zone's share of the
mission's Tableau baptisms over the trailing 12 closed months — "lo que le toca
si la misión llega a 527 repartida como siempre". **Printed, never coloured**
(decision 48's spirit). The zone's colour on baptisms comes from nowhere; its
place comes from the index (P1) and its baptisms per companionship-week beside
the pilot's. Districts get the count only, no reference line (too few events —
see P3).

### P3 — The small-count rule (H5; built in Phase 0 as 0.5)

- **When the comparison period's count, rescaled to this period's reports, is
  under 25**, a change prints as a **signed count**, not a percentage: this
  period's count minus what the comparison period's rate would have produced
  on this period's reports ("−3", "+4"). Same per-reporting basis every change
  already rests on. 25 is not new: it is `period_delta.SMALL_COUNT_MAX`, the
  rule the Panel's cards already follow, so the app keeps one threshold (the
  audit's "~20" was a guess before this was found).
- **An arrow only when the move clears a Poisson band**: the two-rate test
  z = (r₁ − r₀) / √(λ(1/a₁ + 1/a₀)), λ = pooled rate, a = reporting
  area-weeks; arrow when |z| ≥ 1.96. Otherwise the figure prints flat, no
  colour.
- Nightly rows keep the ±15% `FLAT_BAND` **and** must clear the same test to
  carry a colour.

### P4 — The pipeline model (Phase 2)

- **Who is in it:** people in Tableau detail with a baptismal date set and no
  `confirmation_date`, by roster area.
- **Fit:** for every person whose date was set ≥ 180 days before the export,
  the share baptised within 42 days *given* they were still unbaptised at age
  a (days since the date was set), in buckets 0–14 · 15–30 · 31–60 · 61–90 ·
  91–180 · >180. Refit every build (it is a groupby over ~1.000 rows).
- **Forecast:** Σ p(bucket) over the open dates = expected baptisms in the next
  six weeks. **Range:** the 10th–90th percentile of that sum as a
  Poisson-binomial, widened by the backtest's error (the same forecast made at
  each of the last 12 month-ends, against what then happened). The method line
  prints the backtest's typical miss.
- Audit facts it must reproduce: 391 open dates in the last 90 days; 26%
  baptised ≤ 42 days, 34% ≤ 90, median 32 days.

### P5 — The page budget does not add up to 45 yet (Phase 3)

§5 of the audit allots mission ~6, zone 2, district 1, area ½. On CCSM's
roster that is 2 front + 6 + 4×2 + 13×1 + 45×½ + 1 note = **≈ 53 pages**.
Reaching ~45 needs one more economy, and it is his call when Phase 3 starts:
(a) an area at a third of a page (→ ≈ 45), (b) a district's page shared with
its areas' first block, or (c) accept ≈ 53. Recommendation: **(a)**, because
the area block's sparklines go anyway (M5) and the nightly inputs fit in a
four-line strip.

---

## §3 — Build steps

### Phase 0 — defects (no decision needed; this chat)

**0.1 (C3) — the false baptism sentence.** `packet.py:1891-1905`
(`baptism_page`), `packet.py:645-649` (`_two_baptism_figures`),
`packet.py:991-997` (`NOT_FOR_VERDICTS` comment) and the screen's info text
`views/11_Informes.py:747-756`. Replace "los misioneros no siempre anotan el
campo" with the scope truth: the certified figure counts all ten zones, the
form counts the four pilot zones, so the two are not compared. Retraction:
`PLAN-2026-10-02-goals.md` §2.5.

**0.2 (H2) — conversion rates.** `model._rates` (`model.py:1157`) attaches each
rate's Spanish label from `data.labels`, so neither renderer can fall back to
the key (`packet.py:1040`). The packet's rate table gets its change column —
`rate["change"]` in points, which `point_delta` already computes and nothing
prints — and each rate's note says what it divides ("de 1.234 intentos de
contacto"), which is how *Tasa de Lecciones*' denominator stops being a
surprise. The screen already reads labels; it gets the same note.

**0.3 (H1) — the flag is the mission's verdict pasted on every unit.**
`grading.grade_ki` (`grading.py:226`). A unit's row carries the mission's flag
only when **its own** attainment is outside the band in the same direction;
never when its own attainment is ≥ 100%. Both renderers read `grade.flag`, so
neither changes. (Phase 1 retires the Key Indicator flag outright once
leadership's goal is the yardstick.)

**0.4 (H4) — the nightly table.** `packet.nightly_page` (`packet.py:1413`),
`nightly_lines` (`packet.py:810`), `ReportModel.nightly_weakest_first`
(`model.py:452`) and the screen's `_nightly_rows` (`views/11_Informes.py:405`).
REAL becomes the **per area-week** figure the percentage is taken on, beside a
META on the same basis; the period total moves into the row's note. Flagged
rows sort last. The head says what the order is ("más lejos de su meta
primero"), and one sentence says why a nightly count is not the Key
Indicator of the same name (nights through yesterday vs complete weeks of the
weekly form — 900 vs 806 on 2026-10-06).

**0.5 (H5) — small counts.** P3 above, in `grading` (one function, used by
both `grade_ki` and `grade_nightly`), carried on `Grade`, printed by
`packet._change` and the screen's KI cards and nightly rows.

**0.6 (M4) — developer language.** No "decisión NN" and no tab name in any
sentence a reader meets, packet or screen. The data note's *Fuente* column
keeps the tab name as a second, smaller line under a plain Spanish source
name, because that page exists for the reader who wants to argue with a
number.

**0.7 — verify Phase 0.** Suite against baseline; the packet built from the
live sheet, rasterised and READ (pages 3–8, Angol, El Mirador); the screen at
1400px and 375px. Push, and tell him to Reboot.

### Phase 1 — yardstick and ranking (decisions 44, 45; needs P1)

1.1 `MetricRow` gains `leadership_pct` (attainment against the pro-rated
leadership goal, on the active basis); `grade_ki` grades on it. The
companionship's goal becomes `compromiso`, printed uncoloured.
1.2 Retire the Key Indicator flag (decision 22 stays for nightly).
1.3 `model.productivity_index(rows, mission_rows)` per P1; `_rank_scopes`,
`_ladder`, `_siblings`, `_areas_ranked` order on it. `_mean_attainment` stays
only where a goal-attainment figure is still printed.
1.4 Reporting as its own ranked list (silent and late areas), mission and
zone.
1.5 Both renderers: ranked tables, ladder, sibling strip, tiles, page 3's
"Contra qué se mide" rule, the column glossary.
1.6 Verify (as 0.7).

### Phase 2 — the forward view (decisions 46, 47, 48; needs P2, P4)

2.1 Zone and district baptisms from Tableau detail by roster area, labelled
"registros de Tableau" (decision 47).
2.2 Transfer finish and needed-per-week, per Key Indicator, mission and zone
(AUDIT C4(a)).
2.3 Annual landing range from the four anchors, year-over-year by month
(2024, 2025, 2026), required monthly rate against the best month ever
(AUDIT C4(b)).
2.4 The pipeline forecast per P4, mission and zone, with its backtest.
2.5 Both renderers; verify.

### Phase 3 — the front section and the diet (decisions 49, 50; needs P5)

3.1 *El tablero* (§5 item 1). 3.2 *Dónde enfocar* — Pareto of the shortfall,
productivity × trend quadrant, reporting list (H6). 3.3 *Bautismos: el año y
lo que viene*. 3.4 *Palancas* — mature-cohort funnel and result → driver
lines (M2, M3). 3.5 a fixed 12-week strip on every unit page (H3). 3.6 zone 2
pages, district 1, area per P5 with nightly inputs (M5); scores only with a
comparator (M1); the zones table shows all seven or the index's members (M6);
print guide off page 2 (L1). 3.7 verify, page count measured against 45.

---

## §4 — How to resume

1. Read §1 (never re-open), §2 for the proposal the phase needs, then the
   phase's steps in §3 and the last STATUS entry.
2. **Phases 1–3 each need his word on their proposal first** (P1 → Phase 1,
   P2 + P4 → Phase 2, P5 → Phase 3). Ask once, with the measured table.
3. Live data: `model.load_data()` (~45 s) and pickle the `ReportData`; a packet
   is `packet.build(period_key, data=data)`. Re-load when the date moves.
4. Reading a page: `pip install --target <scratchpad>/pylib pypdfium2`,
   rasterise, `Read` the PNG. Never into the venv.
5. The screen: preview `ccsm-dashboard` (`.claude/launch.json`), **restart it
   after every edit** — the watcher misses `app/` and `views/`.
6. Suite against baseline, compare FAILURES not the passed count, and never
   edit the tree while it runs.
7. This machine's Git Bash heredocs collapse backslashes: write scripts with
   backslashes through the Write tool.

---

## §5 — Phase 4: the road to 95 (PROPOSED 2026-10-07 — NOT started, needs his word on P6–P11)

Zackary, 2026-10-07: *"what is your plan to get it to 95."* Scored on the
audit's §1 rubric, live packet of 2026-10-07 after `954f650`:

| # | Dimension | Weight | Was | Now | Target | Points | What closes the gap |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | Trust | 15% | 6.5 | 8.5 | 9.5 | +1.5 | 4A.2 silence split · 4C.1 every forecast backtested |
| 2 | The yardstick | 15% | 3.0 | 8.5 | 9.5 | +1.5 | 4D.1 goal sanity line · 4D.2 the index tested against baptisms |
| 3 | Focus signal | 15% | 3.0 | 8.0 | 9.5 | +2.25 | 4A.1 trend noise rule · 4A.2 · 4B.2 what changed · 4E.1 the one page |
| 4 | Comparability | 10% | 6.0 | 8.0 | 9.5 | +1.5 | 4B.1 same weeks last year · 4B.3 index over transfers |
| 5 | Trend and history | 10% | 3.0 | 6.5 | 9.5 | +3.0 | 4B.1 · 4B.2 · 4B.3 · 4A.4 numbers on the sparks |
| 6 | Projection | 12% | 1.5 | 8.0 | 9.5 | +1.8 | 4C.1 · 4C.2 lever sizing · 4C.3 district pipeline |
| 7 | Diagnosis | 8% | 4.0 | 7.5 | 9.5 | +1.6 | 4C.2 · 4C.4 lead → lag inside zones |
| 8 | Small numbers | 5% | 5.0 | 7.0 | 9.5 | +1.25 | 4A.1 · 4A.3 intervals and "pocas personas" |
| 9 | Economy | 5% | 4.0 | 8.0 | 9.0 | +0.5 | 4E.1 (decision 50 caps this: a weekly packet stays full length) |
| 10 | Visual craft | 5% | 8.5 | 8.5 | 9.5 | +0.5 | 4A.4 · 4A.5 blank feet under 15% |
| | **Total** | | **41.5** | **≈79** | | **+15.4** | **≈95** |

**Honest limits.** (a) The weekly form starts **2026-08-09**: no
"same weeks last year" exists for a form-only Key Indicator, so 4B.1 uses the
four Tableau carries (found, date set, first church attendance, baptisms).
(b) 4D.2 needs three transfers of form data — it can run once **2026-7 closes
(2026-11-29)**. Rounds 4A–4C and 4E get to ≈93–94; 4D.2 is the last point.
(c) Decision 50 keeps a weekly packet at full length, so dimension 9 stops at 9.

### Proposals P6–P11 (NOT decided)

- **P6 — Same weeks last year, Tableau only (4B.1).** Its own small block
  under the tablero, never a tablero column: decision 34 forbids a Tableau
  figure sharing a table with a form figure. Four rows × 2024 · 2025 · 2026.
  *Recommend: yes.*
- **P7 — "Qué cambió" is recomputed, not stored (4B.2).** The prior period is
  rebuilt from today's sheet (`build_all(prior)`), so no new tab. Cost: a
  late report can make last packet's figure differ slightly from what was
  printed then; the block says "con los informes de hoy". The alternative is
  a `PACKET_SNAPSHOTS` tab written on every build. *Recommend: recompute.*
- **P8 — Lever sizing (4C.2).** Per zone: if its biggest leak converted at
  the mission's rate, how many more dates and baptisms in the next six weeks,
  as a range, uncoloured, ranked. *Recommend: yes, mission page + zone
  opening.*
- **P9 — District pipeline (4C.3).** Expected baptisms in six weeks per
  district, on the district page; under 15 open dates it prints "pocas
  fechas" and no range. *Recommend: yes.*
- **P10 — Goal sanity line (4D.1).** Beside each Key Indicator: leadership's
  transfer goal against the mission's best transfer since forms began (and,
  for the four Tableau carries, since 2024): "pide 1,4× el mejor traslado".
  Grading stays on leadership's goal (decision 44 holds); this only says when
  the goal itself is out of reach. It is a statement about leadership's goal
  printed in leadership's own packet — *his call.*
- **P11 — A one-page "Resumen" as page 2, about +2 pages total (4E.1).**
  Five lines: where we are · the three units to visit and why · what is coming
  · what changed · the question to ask each zone. *Cómo leer* moves to page 3.
  With 4B.1 and 4B.2 the transfer copy lands ≈48 pages against decision 49's
  ≈45. *Recommend: yes; confirm 48 is fine.*

### Steps

**Round 4A — small numbers and focus (no decision needed).**
- 4A.1 Trend noise rule. `focus.trend_change` (`focus.py:101`) returns a
  direction only when the change clears the unit's own week-to-week spread
  over the 12 weeks AND each half has ≥ 6 reports; otherwise "estable" or
  "pocas cifras". The quadrant draws those on the 0 line, hollow. Today it
  prints Collipulli 1 −84% and El Mirador +47% on 3-area districts.
- 4A.2 Silence split. `focus.pareto` splits each unit's share of the
  shortfall into *por silencio* (area-weeks with no report × their goal) and
  *por trabajo*; the bar draws both shades and silent rows carry "sin informe".
  Today Los Confines is #1 partly because one area never reported.
- 4A.3 Small samples. Funnel rows under 100 found print "pocas personas" and
  name no leak; zone conversion rates get a Wilson 80% range in the note.
- 4A.4 Numbers on the sparks: first and last value at each end of every
  12-week line (tablero, area rows).
- 4A.5 Blank feet: measure every page's empty foot; target < 15% average,
  none > 40% except a section's last page.

**Round 4B — history and change (needs P6, P7).**
- 4B.1 *Las mismas semanas, otros años* (Tableau): mission and zone.
- 4B.2 *Qué cambió desde el último período*: units that entered/left
  "debajo y bajando", the five largest index moves, how each forecast moved.
- 4B.3 Index over transfers: each zone and district's index for every
  transfer with form data, and "crónico" when a unit sits in the focus corner
  two transfers running.

**Round 4C — forecasts proven and levers sized (needs P8, P9).**
- 4C.1 Backtest the transfer finish and the year landing on Tableau history
  (2024–2026) at the same point of the period/year; print the typical miss
  beside each range, as the pipeline already does (8%).
- 4C.2 Lever sizing per P8.
- 4C.3 District pipeline per P9.
- 4C.4 Lead → lag inside a zone: the result → cause line per district on zone
  pages, and each lagging Key Indicator tied to its nightly input (member
  lessons ↔ *Lecciones con Miembro Presente*).

**Round 4D — the yardstick audited (P10; 4D.2 dated).**
- 4D.1 Goal sanity line per P10.
- 4D.2 **After 2026-11-29:** does a district's index predict its Tableau
  baptisms 6–12 weeks later, member by member? Print the result on *Cómo
  leer*. If the weights should move, take it to him MEASURED — decision 45 is
  not reopened by the test itself.

**Round 4E — the one page (P11).**
- 4E.1 *Resumen* per P11, both renderers (the screen's top card).

**4F — verify.** Suite against baseline; both live packets built, read as
images; screen headless at mission/zone/district; re-score on the §1 rubric
and record it here.

---

## STATUS

### 2026-10-06 — the plan is written; Phase 0 starts

Suite baseline before any change: **0 failed / 1883 passed / 1 skipped**
(4 min 50 s).

Live state at the start: *Este traslado* packet 104 pages; mission against
leadership's goal at 4 of 6 weeks — new people 806 of 1.359, member lessons
528 of 1.017, sacrament 216 of 329, first week 41 of 54, dates 167 of 223,
form baptisms 7 of 45, RC 210 of 351. All seven leadership goals are complete
for 2026-6 (every area has one), so decision 44 has a goal to grade against
everywhere.

### 2026-10-06 — 0.1 (C3) done · `4b86ac4`

The false sentence is gone from all four places it lived: the baptism page,
page 3's "Dos cifras de bautismos", the no-capture sentence in
`tableau.PeriodBaptisms.sentence` (a fourth copy the plan had not listed) and
the screen's info text. Each now says the certified figure counts every zone
and the form only the pilot's (`packet._pilot_zones`, "las 4 zonas del
piloto", from the mission's children). New test pins "no siempre" out of both
packet texts.

### 2026-10-06 — 0.2 (H2) done · `b8a7a8d`

`model._rates` attaches `label` and `denominator_label`; the packet's rate
table has a real change column in points (`_rate_change`, "sin base" head
when no rate has one) and every note names its denominator. Live, this
transfer: contacto 45,1% (−2,2 pp) "7.413 de 16.428 intentos de contacto";
lecciones 13,6% (−2,8 pp) "2.230 de 16.428 intentos de contacto"; invitación
13,0% (+3,9 pp). Widest note 105pt of 143.

### 2026-10-06 — 0.3 (H1) done

`grading.flag_here`: the mission's verdict sticks to a unit only where the
unit's own reading is outside the band in the same direction; applied inside
`grade_ki` and `grade_nightly`, so neither renderer changed. The old test that
pinned an area at 50% as flagged was rewritten to the new rule. Live, this
transfer (only *Primera Semana* is flagged at mission level): unit rows
carrying the flag **59 → 37**; now graded — San Pedro 30%, El Mirador
**117% · al ritmo**, Huepil & Tucapel 28%, Laja 1 28%, Los Huertos 27%,
San Pedro 1 39%, Lautaro 2 44%. The weekly packet has no flag at all, so the
two packets still disagree about *Primera Semana* at mission level — that
goes when Phase 1 retires the KI flag.

### 2026-10-06 — 0.4 (H4) done

Nightly REAL is now the per-area-week figure the percentage rests on
(`per_reporting_area_week`), beside META on the same basis; the period total
is the row's note ("total del período: 3.248"), and the effort score's note
says it is a 1-3 average instead. `NightlyCoverage.through` carries the last
night counted, and `ReportModel.nightly_source_note` — one sentence, both
renderers — says why a nightly count is not the Key Indicator of the same
name. Flagged rows sort last (*Lecciones con CR* left the top). Head:
"más lejos de su meta primero". Live mission, this transfer: Invitaciones a
la Iglesia 25 against 45 (55%), Nuevas Personas 6,8 against 8,0 (85%).
The screen's nightly list leads with the same per-area-week figure and drops
its "/informó" cell (it IS the value now). Three tests that pinned the old
heads and note were rewritten; two new ones pin the order and the sentence.

### 2026-10-06 — 0.5 (H5) done — P3 as built

`grading.count_change` (expected at the old pace on this period's exposure,
the signed difference, the two-rate Poisson z) feeds two new `Grade` fields,
`change_count` (set only when expected < 25, `period_delta.SMALL_COUNT_MAX`)
and `change_clear` (|z| ≥ 1,96). The model passes raw counts and exposures —
area-weeks for Key Indicators, area-nights for nightly. Packet `_change` and
the screen's KI cards and nightly cells print "+20" for a small count and no
triangle for a move inside the noise; a nightly status inside the noise reads
"warn" (steady). Page 3's glossary explains it in one sentence.

Live, El Mirador this transfer: sacrament +260% → **+20** ▲, first week
+133% → +4 (flat), dates +111% → +10 (flat), RC −70% → **−12** ▼. Mission:
form baptisms −35% → −4 (flat); sacrament −17% and dates +4% lose their
triangles. Zone/district/mission KI change cells: this transfer 57 in %, 55
in units, 29 with a triangle; last week 14 in %, 112 in units, **3** with a
triangle.

### 2026-10-06 — 0.6 (M4) done

No "decisión NN", no tab name and no `COMPASS_CCSM`/`AGENT_CONFIG`/
`CCSM_AgentScores` in any sentence a reader meets, packet or screen: the
organigrama, "la hoja de datos de la misión", "la captura mensual / por
período", "el análisis de los agentes". The data note's *Fuente* column is now
a plain name with "pestaña X" under it in note type (`data_note.source`), the
one place a tab name may print. Two stale facts fixed on the way: the data
note said nightly goals come from AGENT_CONFIG as one mission-wide figure
(they are per sector, recalculated each Monday, since PLAN-2026-10-02 G-D7),
and "companería" was misspelt. `test_no_page_speaks_developer_language`
sweeps every unit page, page 3 and the data note. The two screen messages
for a missing roster/unit keep the tab name as "(pestaña MISSION_ORG)" only
where an administrator has to act on it.

### 2026-10-06 — 0.7 verified · PHASE 0 COMPLETE

- **Suite: 0 failed / 1909 passed / 1 skipped** (baseline 0 / 1883 / 1; +26
  new tests).
- **Both live packets built** from the sheet loaded at 19:45 (this transfer
  and last week): **104 pages each**, as before — Phase 0 changes no length.
  Rasterised and read: p5 (zones + nightly table), p6 (nightly tail +
  baptism page), p8 (rates + scores), p29–30 (El Mirador), p104 (data note).
  No "no siempre", no "decisión", no `contact_rate` anywhere in the text;
  `MISSION_ORG` appears only as p104's "pestaña" line.
- El Mirador now opens "Lo más fuerte: Amigos en la Iglesia (Primera Semana)
  va en 117% de la meta — 7 contra 6", where it used to be told to revise
  that goal; its change column reads +20 ▲ · +4 · +10 · −12 ▼.
- Side effect to know about for Phase 1: with per-unit flags, San Pedro's
  zone mean moved 55% → **50%** (its 30% *Primera Semana* is now graded).
  The zone order on p5 is unchanged (Angol 41 · LAN 46 · SP 50 · Ñielol 56)
  and is still the wrong one — Phase 1 replaces it.
- **Screen** (preview, live data): KI cards, rates and the nightly list show
  the same figures and rules as the packet at 1400px; at 375px no horizontal
  overflow.
- Not pushed at the time of writing; the deployed app needs a Reboot after
  the push.

**Next: Phase 1** — needs his word on **P1** (index members and weights)
first.

### 2026-10-06 — Zackary: "Go through the rest of the packet rebuild!!"

Taken as the go for Phases 1–3 in one run, and as approval of P1–P5 **as
recommended** (P1 weights 3·2·2·1·1·1 with form baptisms out; P2 a zone's
share of 527 printed uncoloured; P3 as built; P4 the age-bucketed pipeline;
P5 option (a), an area at a third of a page). Any fork the build hits that
the plan did not foresee goes back to him measured, as before.

### 2026-10-06 — PHASE 1 COMPLETE (1.1–1.6, one commit: the steps share every function they touch)

- **1.1 Yardstick (decision 44).** `MetricRow.lead_goal / lead_actual /
  lead_area_weeks`: leadership's AREA_TRANSFER_GOALS spread per area-week
  (`ReportData.lead_week_goal`), summed over exactly the area-weeks that
  REPORTED — rule 1, both sides one population. Graded only if ≥ 50% of the
  reports carry a goal (`LEAD_MIN_SHARE`), else "sin meta del liderazgo".
  **Deviation from the plan's text, on purpose:** the plan said "on the
  active basis"; that would mix silence into the grade, which decision 45
  gives its own list, so the grade is on the reporting basis. The
  companionships' goal is `own_pct` and the new **Compromiso** column
  (`PP.KI_COLUMNS`, 7 columns, 56pt). Form baptisms: percentage shown, never
  coloured (`UNCOLOURED_KI`, decision 46).
- **1.2** The Key Indicator flag is retired (`ki_goal_flags` deleted); the
  nightly flag stays.
- **1.3 Index (decision 45, P1).** `model.productivity` / `Productivity`,
  `INDEX_WEIGHTS` 3·2·2·1·1·1, cap 250, "pocas cifras" under 20 events.
  `ChildRow`, `LadderRow` and `ReportModel` carry `index`; ranking, ladder,
  siblings and areas order on it. `mean_attainment`, `_mean_attainment` and
  `attainment_per_active_area` are gone.
- **1.4** `ReportModel.reporting_ranked` → "Quién informó" (packet
  `reporting_block`, mission and zone; screen section under the children).
- **1.5 Renderers.** Ranked tables show all six index members (fixes M6),
  no grade dots, a 100 tick on a 0–200 bar; the strip plot gets index ticks
  ("100 = misión"); unit pages say "Productividad: 94 — cada compañería
  produce un 6% menos que el promedio de la misión"; area lines "Productividad
  106 (misión = 100) · su distrito 108 · su zona 94". Page 3 rule 1, the
  column glossary, GRADED/COMPARED/BASIS notes and the data note rewritten.
  Screen: KI cards graded on leadership (violet tick = compromiso), index
  tables, ladder, sibling sentence, reporting list.
- **1.6 Verified.** Suite **0 failed / 1920 passed / 1 skipped** (26 old
  tests rewritten to the new decisions, 12 added incl. `test_report_index`).
  Live packet: 104 pages (no length change yet). Zones now **Temuco Ñielol 82
  · Angol 94 · Los Angeles Norte 110 · San Pedro 114**; mission KIs against
  leadership: new 81% · member lessons 70% · sacrament 87% · first week 104%
  · dates 96% · RC 85% · baptisms 20% (uncoloured). Pages 4, 5, 9 and 81
  read. Screen: mission checked live in the preview; zone and district run
  headless through Streamlit's AppTest (the pane was hidden and would not
  draw) with no exceptions — `scratchpad/apptest_informes.py rep_zone=Angol`
  is the harness, query param `rep_<level>`.

### 2026-10-06 — PHASE 2 COMPLETE (2.1–2.5)

New module `app/reports/forecast.py` (pure), `model.Forward` on every
mission/zone/district model (`_forward`), `ReportData.tableau_dates()` parses
the export once and fits the pipeline once for all 63 scopes.

- **2.1 Zone/district baptisms (decision 47).** `forecast.unit_baptisms`:
  `confirmation_date` in the period by roster area, labelled "registros de
  Tableau", on every zone and district opening (`UnitBaptisms.sentence`, both
  renderers). P2 as built: `share` = the unit's part of every Tableau baptism
  in the last 12 closed months, `reference` = 527 × share, printed only.
  Live, 2026-6 to date: Angol 3 · LAN 2 · San Pedro 2 · Ñielol 1; shares
  7,9% · 11,5% · 15,1% · 8,2% → references 42 · 61 · 80 · 43.
- **2.2 Transfer finish + needed per week.** `forecast.transfer_finish`: so
  far + weeks left × (worst, mean, best) of the last 6 complete weeks' raw
  totals; goal = leadership's whole-transfer goal, all areas. Live mission:
  new people 806 → 1.124–1.254 of 2.038, needs 616/week = 3,3× pace; dates
  167 → 225–265 of 334 (2,2×); form baptisms 7 → 7–21 of 68 (11,4×).
- **2.3 Year landing.** `forecast.year_landing`: the four anchors give
  **443–467** against 527, **60/month needed vs a best month of 50 (dic
  2024)**, **+17% on 2025's same 9 months** (296) — the audit's C4(b) to the
  unit. Month table carries 2024 · 2025 · 2026 · cumulative · goal pace.
  Zones get the same from Tableau records against their 527 share.
- **2.4 Pipeline (P4).** `forecast.fit_pipeline` pools 15 month-ends (each
  with six full weeks after it): P(baptised within 6 weeks | still open at
  age a) = 21% · 16% · 8% · 4% · 2% · 1% for 0-14 · 15-30 · 31-60 · 61-90 ·
  91-180 · 181-365 days. **Backtest: 8% typical miss over the last 12
  month-ends.** Live: 1.159 dates open (set in the last year), **40–57
  baptisms expected in 6 weeks** (centre 49); 267 set in the last 60 days. By
  zone (all ten, Tableau's own zone column, decision 24's precedent): San
  Pedro 4–10 … Victoria 1–6. Range = 80%: the wider of the Poisson-binomial
  spread and the backtest miss.
- **2.5 Renderers.** Packet `finish_block`, `year_block`, `pipeline_block`
  after the Key Indicators on mission and zone pages (Phase 3 re-orders);
  screen section "1c · Lo que viene" with the same three. Nothing coloured.
  Packet now **112 pages** (+8) — Phase 3 is the diet.
- Verified: suite **0 failed / 1931 passed / 1 skipped**; 11 new tests in
  `test_report_forecast.py`. Pages 4–6 read. Screen: mission, zone and
  district run headless with no exceptions. Found and fixed on the way: on
  this stack (NumPy 2.5, pandas 2.3) a datetime Series compared with a
  Timestamp, and `pd.date_range`, raise a DeprecationWarning from inside
  pandas — 758 per suite run — so the forecast works on `datetime64[ns]`
  arrays and builds month-ends from plain dates.

### 2026-10-07 — PHASE 3 COMPLETE (3.1–3.7) · THE REBUILD IS BUILT

**The full transfer copy is 46 pages (from 104); 74 sheets a run (from 148).**
Measured on the live sheet for four periods (this transfer, last week, last
transfer, calendar month): every one lands at mission 6 · each zone 2 · each
district 1 · areas three to a page (15) · front 2 · data note + print guide 2.
P5 (a) as recommended — no further cut was needed.

What the packet is now, page by page:

1. **Cover**, then **Cómo leer** (page 2; the print guide moved to the last
   page, AUDIT L1). Rule 5 now describes the forecasts, the Tableau-record
   baptisms below mission and the mature funnel (it described the old window
   funnel, which no longer prints).
2. **Mission (6)**: *Dónde estamos* + **El tablero** (3.1 — the seven, real,
   per companionship-week, *Propia* = the compromiso, the bar and % against
   leadership's goal, the change, a 12-week spark, the transfer's finish range
   and what each week left would need); **Dónde enfocar** (3.2 — the
   shortfall Pareto by district, a productivity × trend quadrant with the
   "debajo y bajando" corner tinted, and the list); the zones by index and
   **Quién informó**; **Bautismos: el año y lo que viene** (3.3 — the period's
   certified figure, the year with 2024/2025 and the 527 pace, the pipeline
   by age and by all ten zones); **Palancas** (3.4 — the mature funnel by
   zone with each zone's largest leak, the four rates by zone with what each
   divides by, and one result → cause line per pilot zone, M3); **Las
   últimas 12 semanas** (3.5); the nightly work.
3. **Zone (2)**: the same opening (with "lo que viene" and "quién informó" as
   sentences), the tablero, the ladder against the mission with the sibling
   strip, its districts, *Dónde enfocar* among its areas (cut at 80% with the
   rest named; falls back to every area by index when no goal exists), its
   mature funnel by district.
4. **District (1)**: opening, tablero (no forecast columns), the ladder rows,
   its areas by index.
5. **Area (⅓)**: drawn fixed-height rows (`PP.area_ki_rows`) with the
   compromiso and twelve-week sparks, the productivity line against its
   district/zone/mission, its own nights per week against its goals (M5),
   the agents' strength line, and its scores with its rank in the district
   (M1: scores kept only where they have a comparator).

New code: `app/reports/focus.py` (pareto, trend_change per REPORTING
area-week, quadrant, mature_funnel — leak only when a step converts < 85% of
the mission's); model fields `trend_series` (12 weeks), `trend`,
`ChildRow.trend`, `focus`, `funnel`, `child_rates`, rate
`numerator_label`; packet_parts `TableroLine`/`tablero_table`, `quadrant`,
`area_ki_rows`, `week_table(columns=)`. The screen got "Dónde enfocar",
"Palancas" and "Tasas de conversión por zona" from the same fields.

Removed as dead once nothing called them (each found by an AST scan of
app/ + views/): at_a_glance, key_indicator_page, week_page, finding_page and
its funnel/mix/units blocks, rates_and_scores, score_tiles, rate_lines,
_headline_tiles, furthest_behind, finish_block, leadership_note,
GRADED/COMPARED/BASIS notes, the KI_COLUMNS seven-column metric table. Their
tests were ported to the new blocks where the behaviour survives (tablero,
trend strip, levers, pipeline, data note) and retired with the function where
it does not (the window-funnel pages, headline tiles, graded notes, score
tiles, leadership notes) — 31 retired, 20 added.

Found and fixed during Phase 3: the 6-week trend first read every zone
"rising" because it compared raw sums across weeks of very different
reporting; the tablero first had no compromiso column (decision 44) — caught
by the dead-code scan flagging the unused `_ki_headers`; a tiny leadership
goal printed "0" beside a 400% row; the funnel note widowed onto a page of
its own until it moved above its table.

Verified: suite **0 failed / 1922 passed / 1 skipped**; both live packets
(this transfer, last week) 46 pages, pages 1–7, 9–10, 17, 30, 45–46 read as
images; screen at mission, zone and district runs headless with no
exceptions.

**Nothing in the plan is outstanding.** Push, then Reboot the deployed app.

### 2026-10-07 — before/after comparison, three follow-ups built · `954f650`

Both packets built from the live sheet (before = `origin/main` via a temp
worktree, removed after): 104 → 46 pages, ~40k → ~22k words; re-scored
41.5 → ≈78. Zackary: fix the funnel bottom and the layout, bring back who
found them. Built:
- Mature funnel: shares under 10% print one decimal (the baptism column read
  0% in every row); a named leak prints its step's rate against the
  mission's on the same line ("fecha a bautismo · 8,0% vs 16%",
  `FunnelRow.leak_step`, `FUNNEL_COLUMNS` leak column 148pt — on a second
  line it grew two zones to three pages). Screen the same.
- `finding_mix_block` on the mission's pages (category share bar + top 8
  sources, share now and in the same days before). A zone gets it as one
  sentence of its opening (`_mix_sentence`): the section cost every zone a
  third sheet (measured: 50 pages).
- Quadrant labels and corner caption take the first free spot
  (`PP.quadrant`); `run_on` lets a section shorter than the 140pt floor start
  with its own height free; data note "Hallazgo" → "Personas encontradas".
- Verified: suite **0 failed / 1928 passed / 1 skipped** (+6); this
  transfer and last week both **46 pages**; pages 7, 9, 10, 12 read as
  images; Informes headless at mission and Angol, no exceptions. Re-scored
  ≈79.

**Not pushed** (14 commits ahead with this one). **Next: §5 Phase 4 — needs
his word on P6–P11.** Round 4A needs none and can start on his go.
