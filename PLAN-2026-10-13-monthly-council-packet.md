# PMG Compass — The Monthly Council Packet

**Written 2026-10-13**, from `AUDIT-2026-10-12-packet-professional.md`. The
audit's §7 holds Zackary's answers. The audit found the packet to be *"a very
good analyst's workbook, not yet an operating review"*. This plan turns it into
the document a **monthly** council works from.

The audit is the evidence and this file is the build. Read the audit's §3
before using any finding id (F1–F10) or change id (C1–C13) below.

**Convention, as before:**
- One commit per step, named with the step id.
- Every step is verified before its commit.
- The suite runs against baseline before every push.
- STATUS is appended after every step.
- **One phase per chat.** The chat is cleared between phases, so this file must
  be enough to resume from.
- A push that touches `dashboard/app/` or `dashboard/views/` needs a **Reboot**
  of the deployed app (`dashboard/DEPLOYING.md`).

**Target date:** the first council under this plan is the **first week of
November 2026**. Phases 1 and 2 should be live before 2026-11-02. Phases 3 and
4 can follow before the December council.

---

## §1 — Decisions (Zackary, 2026-10-13): never re-open

They continue the packet rebuild's decisions 44–57.

| # | Decision | Replaces |
|---|---|---|
| 58 | Who and when: the council is the **ZLs, the STLs (hcaps), the APs and the President**, meeting **once a month, in the first week of the month**. The packet is built for that meeting. | — |
| 59 | **A Key Indicator's colour is what was done, counting every area, against leadership's FULL goal for the period.** That goal is prorated to the period's weeks and summed over every area. An area-week with no report counts as zero. The companionship's own goal stays an uncoloured *compromiso* column. Forecasts stay uncoloured (decision 48 holds). | **44** |
| 60 | **Reporting is a headline KPI**, with a target, a trend, and the zone leaders named as owners, on the mission page and every zone page. | — |
| 61 | **"Mes pasado" is a new period: the calendar month just closed.** It counts the complete weeks that **end** inside that month. **It is the council packet's default.** | 49/50's transfer default, for the packet only |
| 62 | **No page for the STLs.** | — |
| 63 | **No commitments tab or data entry.** The packet **remembers itself**: "Desde el último consejo" rebuilds last month's packet from today's sheet and shows whether its focus list and its zone questions moved (the same recompute-not-store rule as decision 53). | — |
| 64 | **527 is fixed.** The packet shows the gap between the forecast and 527, and what each measured lever would close of it. **It never suggests recasting the goal.** | — |
| 65 | **The 2026 jump in found people and dates is stated with both readings**: real work and recording practice, which Zackary believes is "a mix of both". The packet leads with measures that do not depend on how finding is recorded. Phase 0.1 measures which measures those are. | — |
| 66 | (Phase 0, A1) **Decision 59 is graded over the area-weeks that carry a leadership goal.** Inside those, a silent area-week counts as 0. With complete goals this is exactly decision 59. With a gap (2026-5 had goals for 1 area), only the uncovered weeks drop out, never whole areas. The meta reads "sobre N de M semanas-área con meta". | 1.3's "areas with a goal" rule |
| 67 | (Phase 0, A2) **The reporting KPI's trend is the last 8 complete weeks** (areas reporting per week). It switches to six closed months once six exist (about Feb 2027). The weekly form began on the week ending 2026-08-16. | 1.4's "six closed months" |
| 68 | (Phase 0, Q-F) **The open-dates pipeline is fitted on the last 6 month-ends only**, because 2026 dates convert at about half the 2025 rate, and the 15-month pooled fit has overshot ×1,7–2,1 since June. Step 2.0, before any bet uses it. | `FIT_MONTHS = 15` |

### §1.1 — Defaults this plan sets (Zackary may amend; otherwise they hold)

- **D1 — The screen's default tab stays *Este traslado*.** People use the screen
  between councils, so a weekly user should not land on a month that is 2–6
  weeks old. Instead:
  - the screen gains a *Mes pasado* tab;
  - the screen gains a button that always builds **the council packet** for
    *Mes pasado*, whatever tab is open;
  - the existing button still builds whichever period is selected.

  This departs from decision 51 (one model for screen and packet) **only for the
  default tab**. The model and the renderers stay one.
- **D2 — Reporting target: 95%.** Bands: green at 95% or more, amber 85–94%,
  red below 85%.
- **D3 — The council packet and the hand-outs become two PDFs** (C9).
  - **The council packet:** about 15–18 pages (front, mission, zones, data
    note).
  - **The annex:** districts and areas.

  This replaces decision 57's ≈48 pages and decision 50's "weekly packet keeps
  the full structure". Any period can still build both PDFs.

---

## §2 — Build steps

### Phase 0 — measure before building (one chat; NO change to output)

Each measurement uses the live sheet. Write each result into STATUS as a table.

- **0.1 — Is the 2026 jump real?** (F1, decision 65). Tableau detail, with
  2025 and 2026 for the same weeks (7 Sep – 10 Oct) and for Jun–Aug.
  1. **Found by source:** which sources grew? If the growth is concentrated in
     paid ads and Facebook, that leans towards a recording or channel change.
     If it is street and door-to-door, that leans towards real work.
  2. **What happened to the people found:** the share of found people who
     reached *contact* and *lesson* within 30 days. A collapse in that share
     suggests looser recording of finding.
  3. **Date quality:** for dates set in Jun–Aug 2025 and Jun–Aug 2026, the
     share baptized within 6 weeks and within 12 weeks. This measure is
     independent of how finding is recorded.
  4. **Date inventory:** the age profile of open dates now, against the same
     day in 2025.

  **Output:** say which of these four the packet should lead with. If 3 or 4
  show a real fall in date quality, that is the headline finding. If nothing
  separates the two readings, the packet states both readings and leads with
  item 4 alone.
- **0.2 — What *Mes pasado* would print for September 2026,** using a
  throwaway `Period` built by hand:
  - the weeks counted (expected: the weeks ending 6, 13, 20 and 27 Sep, which
    cover 31 Aug – 27 Sep);
  - reporting;
  - each indicator's prorated leadership goal;
  - whether the certified monthly baptism capture answers for 1–30 Sep.
- **0.3 — The colours under decision 59,** for September and for 2026-6 so
  far: how many of the six graded indicators change band, at mission level and
  for each zone. **Expect most things to turn amber or red.** That is the
  point of the decision, but show him the before/after table before Phase 1
  ships.
- **0.4 — Record the suite baseline** in STATUS.

### Phase 1 — the monthly period, the honest colour, reporting as a KPI (decisions 59, 60, 61; D1, D2)

- **1.1 `periods.py` — `LAST_MONTH = "last_month"`:**
  - label `"Mes pasado"`; `WITHIN_LABELS` "En el mes pasado";
  - the period's own label is the month's name, e.g. "septiembre 2026", as
    `_cycle_label` does for transfers.
  - `resolve`: start = the first of the previous month; end = its last day;
    `weeks` = `complete_weeks` that END in the month (`weeks_ending_in`).
  - `comparison_for`: the month before it, whole (`PREVIOUS`).
  - Add it to `PERIOD_KEYS`, next to `CALENDAR_MONTH`, and to `available`.
  - **Tests:** a month whose first day is a Sunday; February; January (the
    year boundary); a month containing a transfer day. Also: a comparison
    month the weekly form had not reached (August 2026 read 42% only because
    the form launched 16 Aug). It must print *sin comparación*, not a false
    rise.
- **1.2 Baptisms for the month.** `tableau.period_baptisms` looks figures up
  by days, so the closed month's certified monthly capture should answer for
  `LAST_MONTH`.
  - Pin that with a test.
  - Pin that `_year_to_date` is untouched.
  - The week-versus-day mismatch (31 Aug – 27 Sep of form weeks against
    1–30 Sep of certified baptisms) gets one sentence in the data note.
- **1.3 Decision 59 in `model._ki_rows`** (`model.py:1268`):
  - **What gets graded:** `grade_ki` grades `actual` (every reported
    area-week) against `mark` (`_leadership_goals`, `model.py:1220`): the full
    prorated goal over every area in scope. Silent area-weeks are zero by
    construction.
  - **Partial goals (decision 66):** grade over the area-weeks that carry a
    goal, using `data.lead_week_goal(area, week)` for each area in scope ×
    each week of the period. The goal is the sum over those area-weeks. The
    actual is those same area-weeks' reported figures, with silent ones
    counting 0. The `meta` header says "sobre N de M semanas-área con meta".
    **Test:** September 2026 must grade 136 of 180 area-weeks. Mission
    Nuevas Personas then reads 61% (amber), not 267%.
  - **Fields:** the `lead_goal` / `lead_actual` / `lead_area_weeks` path of
    decision 44 is retired. Keep the fields only if the screen still reads
    them, and grep for that first.
  - **`grading.flag_here`** stays as it is.
  - **Area level:** an area that reported 3 of 5 weeks is graded against 5
    weeks of goal. Its reporting fraction is already printed next to its name.
- **1.4 Reporting KPI (decision 60, D2).**
  - **New model field** `ReportModel.reporting`, holding:
    - the rate;
    - the target (95%);
    - a status in D2's bands;
    - a trend (decision 67): areas reporting in each of the last 8 complete
      weeks (`_reported_by_week`), switching to six closed months' rates once
      the form has six;
    - the owners: the zone leaders' names, from the roster (`packet.leadership`,
      `packet.py:215`, already finds leadership companionships).
  - **Rendered as** one headline row above the tablero on the mission page and
    each zone page: "Informes 75% · meta 95% · [spark of 8 weeks] ·
    responsables: Élder X y Élder Y".
  - **On the mission page,** the zones table gains each zone's owners.
- **1.5 Both renderers.** These need rewriting to match decision 59: the
  tablero headers, `how_to_read` rule 1 (`packet.py:547`), `COLUMN_GLOSSARY`
  (`packet.py:667`), `summary.where_we_are` (`summary.py:43`), and the
  screen's matching text in `views/11_Informes.py`.

  **No sentence may still say "sobre las semanas y áreas que informaron".**
- **1.6 Screen (D1).**
  - The *Mes pasado* tab.
  - `packet.build()`'s default becomes `LAST_MONTH` (`packet.py:3236`).
  - A second button, "Paquete del consejo — {mes}", that always builds
    `LAST_MONTH` (`views/11_Informes.py:126-170` holds the existing two-control
    pattern).
  - `P.DEFAULT_PERIOD` stays `THIS_TRANSFER` for the screen.
- **1.7 Verify.**
  - The suite against baseline.
  - Build the *Mes pasado* (September) packet and the *Este traslado* packet
    from the live sheet. Rasterise them and READ the mission page, one zone
    and one area page.
  - Run the screen headless (AppTest) on the new tab.
  - Push, and tell him to Reboot.

### Phase 2 — the forward view for a monthly council (C5, C6, C7, C8; decision 64)

- **2.0 Refit the pipeline (decision 68).** `forecast.FIT_MONTHS` goes from
  15 to 6. Re-run the month-by-month backtest from Phase 0.1's table: June
  and July 2026 should now land near 1,0× (they were 1,70 and 2,09), and
  every sentence printing the range (`packet.py:650`, `:1866`, `:2558`)
  moves with it. Check that the 80% range still uses the backtest miss over
  the months available. **Commit this on its own**, because it changes a
  figure the live packet prints.
- **2.1 "El traslado en curso", its own block (C7).** The tablero becomes a
  closed-period table: Real · por comp. · compromiso · meta · % · cambio ·
  12 semanas. The *Termina en / Falta* columns leave it (`packet.tablero_block`,
  `packet.py:1769`; `PP.tablero_table`, `forecast=`). The new block, under the
  tablero on the mission and zone pages, reads the transfer in progress at
  build time:
  - **2 or more complete weeks and at least 1 week left:** *Termina en* and
    *Falta por semana* against the full goal, as now.
  - **Fewer than 2 complete weeks** (e.g. the December council, when 2026-8
    starts 30 Nov): "Cómo empieza 2026-8". It shows how the previous transfer
    closed (actual against full goal, uncoloured) and the new transfer's goal
    per week.
  - **The transfer has ended:** the closed result only.

  `model._forward` (`model.py:2000`) already resolves `THIS_TRANSFER` itself.
  Add the cases above as a `Forward.transfer_state`.
- **2.2 The plan path (C5).**
  - **What it shows:** the mission and each zone, month by month: cumulative
    baptisms against a straight path to the unit's share of 527, with the
    forecast range from today to 31 Dec.
    - The mission uses the certified figure.
    - Zones use Tableau records (decision 47). A zone's share of 527 is
      already defined in the data note: its share of the last twelve closed
      months.
  - **New primitive:** `PP.year_path_chart(width, height, months, path,
    actual, low, high)` in `packet_parts.py`: a cumulative line, the goal path
    dashed, and the forecast range as a pale fan, with no status colour.
  - **Where it goes:** the mission's year block (`packet.year_block`,
    `packet.py:1597`), where it replaces the monthly table. The table moves to
    the data note or the annex. Each zone page also gets a small version.
- **2.3 The gap and the bets (C6, C8, decision 64).** A block on the mission
  page, with one line on page 1 (Phase 3).
  - **Gap** = 527 minus the landing range.
  - **Bets,** each sized in baptisms to 31 Dec:
    - (a) every zone's biggest leak converting like the mission
      (`Forward.levers`, scaled from "per transfer" to the transfers left in
      the year);
    - (b) open dates 91–180 days old converting like 31–60-day dates (from the
      pipeline fit's age buckets).
  - **The line it prints:** "Las palancas medidas suman A–B de los C–D que
    faltan para 527."
  - **Honesty rules:**
    - Reporting is NOT a baptism bet, because certified baptisms do not depend
      on forms.
    - Never print a sentence that suggests changing 527.
- **2.4 Verify** (as 1.7). Check by eye that a December-style build (pass a
  `today` in the first days of a transfer) prints "Cómo empieza".

### Phase 3 — the story and the memory (C1, C4; decisions 63, 65)

- **3.1 Date quality (C4, decision 65).** Use whichever measures Phase 0.1
  chose.
  - **Mission:** "Fechas: cuántas, qué edad, cuántas llegan", meaning the open
    dates' age profile now against a year ago, and date→baptism within 6
    weeks for dates set in the same months, 2025 against 2026.
  - **Zones:** each zone's share of open dates older than 90 days.
  - **District pages (annex):** a count per area of dates older than 90 days,
    under the heading "revisar o liberar". Counts only, **no names of
    people**.
  - **Wording:** the 2026 found-and-dates jump is printed once, with both
    readings, exactly as Phase 0.1 worded them.
- **3.2 "Desde el último consejo" (decision 63).**
  - **How it is built:** `build_report` for the mission and the zones on the
    month before *Mes pasado* (key re-keyed, as `_changes` does at
    `model.py:2140`, so no memo is shared).
  - **What it prints:**
    - that month's top-3 focus units, with their share and productivity then
      and now;
    - each zone's question (the leak rate) then and now;
    - the year landing then and now (`Changes.landing_then` exists).
  - **Note in the method line:** the mature cohort moves by a month between
    councils, so a leak rate moves slowly.
- **3.3 Page 1: "La historia de este mes" (C1).**
  - **New module `app/reports/story.py`, pure:** candidate findings, each
    sized in a common unit (baptisms to 31 Dec where possible, otherwise share
    of the gap to leadership's goal).
  - **The candidates:**
    - reporting's share of the shortfall;
    - the gap to 527;
    - stale-date share;
    - the biggest lever;
    - the largest zone move;
    - "Desde el último consejo" (3.2).
  - **What prints:** the top three, as **action titles** (the heading is the
    conclusion, e.g. "Angol bautiza 6 de cada 100 fechas; la misión, 16"),
    each with one supporting number.
  - **Also on the page:**
    - the mission's year-path chart (2.2);
    - "Para decidir en este consejo": two or three questions generated from
      those findings.
  - **Cover:** it shrinks to a header band on this page.
  - **Resumen:** stays as page 2. *Cómo leer* moves to the back as an
    appendix.
- **3.4 Verify** (as 1.7). Read page 1 and judge it as a stranger would.

### Phase 4 — form (C9–C13; D3)

- **4.1 Two PDFs (D3).**
  - **What goes where:**
    - `packet.build()` returns the council packet: the story, the resumen,
      the mission, the zones, the data note, *Cómo leer* and the print guide.
    - `packet.build_annex()` returns the districts and areas.
  - **Code:** `sections_for` (`packet.py:346`) gains a `part=` argument.
  - **Print guide:**
    - ZLs and STLs get the council packet;
    - DLs get their district page from the annex;
    - the President and the APs get both.
  - **Screen:** two download buttons.
  - **Target:** a council packet of 15–18 pages.
- **4.2 Action titles and method moved out (C10).**
  - **Headings:** every mission and zone section head carries a computed
    conclusion as its subtitle, keeping the label small above it.
  - **Method:** every block keeps **one** source line. The method paragraphs
    move to the data note (`packet.data_note`, `packet.py:2928`).
  - **Measure it:** in the built council packet, "sin color" appears 5 times
    or fewer (42 today), and every block's caption fits on one line.
- **4.3 One yardstick per level (C11).** Area pages drop "— Nº de N en su
  distrito, por efectividad" (`packet.area_block`, `packet.py:2807`). The
  scores line stays, unranked.
- **4.4 Smaller fixes (C13).**
  - **Small goals:** where an area's goal for the period is below 3, print
    the count against the goal with no percentage (no more 600% or 415%).
  - **Leader names:** the ZL's name goes on the zone page header and the DL's
    on the district page header (`packet.leadership`).
  - **The form baptism row:** it stays in the tablero (the seven are constant
    app-wide), but its label gains "(formulario)" and it is never in the
    mission's headline.
- **4.5 Charts where a table hides the shape (C12):**
  - the mission's funnel against the mission's rates as `PP.stage_bars`;
  - the districts' productivity as the existing `PP.strip_plot` on the
    mission page.
- **4.6 Verify** (as 1.7).
  - Measure the page count of both PDFs.
  - Rasterise and READ every page of the council packet.
  - Score nothing against the old rubric (the audit's instruction).

---

## §3 — Risks

1. **Decision 59 turns most of the packet amber or red.** With 75% reporting,
   an indicator can only reach about 75% even if every reporting area hits its
   goal. That is the intended message, because silence is the biggest problem
   (F4). Phase 0.3 shows him the before/after table first, and 1.4's reporting
   KPI sits directly above the tablero so the reason is visible.
2. **The weeks do not match the month's days.** *Mes pasado* counts form weeks
   ending in the month, while certified baptisms count the month's own days.
   They never share a table (decision 34), and the data note says so.
3. **The first "Desde el último consejo"** (November council) compares
   September with October. Both are rebuilt from today's sheet, so late
   reports can move both. The block says "con los informes de hoy" (decision
   53's wording).
4. **4D.2 from the previous plan is still dated after 2026-11-29.** It is
   independent of this plan. Run it in its own chat.
5. **`packet.py` is 3,261 lines.** Phase 4.1's split should move the annex
   builders into `packet_annex.py`, not grow the file.

---

## §4 — How to resume

1. Read §1 (never re-open) and §1.1, then the phase's steps in §2 and the last
   STATUS entry.
2. **Live data:**
   - Load it with `model.load_data()` (~45 s), from `dashboard/` with the
     venv's python. Pickle the `ReportData` and re-load when the date moves.
   - A packet is `packet.build(period_key, data=data)`.
   - A script lives in the scratchpad; insert `os.getcwd()` into `sys.path`.
3. **Reading a page:**
   - `pip install --target <scratchpad>/pylib pypdfium2`, never into the venv.
   - Rasterise at scale 1.6, and `Read` the PNG.
   - Text: `page.get_textpage().get_text_range()`.
4. **The screen:** run Streamlit's AppTest on `views/11_Informes.py`. The
   preview pane may not draw while it is hidden.
5. **Tests:** run the suite with `venv\Scripts\python.exe -m pytest tests/ -q`
   from `dashboard/` and compare FAILURES, not the passed count. Never edit the
   tree while it runs.
6. **Edit scripts:** this machine's Git Bash heredocs collapse backslashes, so
   write scripts that contain backslashes with the Write tool.
7. **Uncommitted on purpose:** `Modelo_correo_semanal_Temuco_Nielol.html`,
   `Vista_previa_KI_asistentes/` and `.claude/launch.json` are Zackary's. Never
   sweep them into a commit.

---

## STATUS

### 2026-10-13 — the plan is written

Zackary's answers are in the audit's §7. In short:
- the council is monthly (first week), with the ZLs, STLs, APs and President;
- decision 44 is reversed;
- no commitments tab;
- 527 is fixed;
- the 2026 jump is "a mix of both";
- "yes" to *Mes pasado* as the packet's default;
- "no" to an STL page.

The live packet on 2026-10-12 (*Este traslado*, 2026-6, 5 of 6 weeks) had 48
pages. Next: **Phase 0**, which only measures and changes no output.

**Suite baseline (2026-10-13, before any change): 1 failed / 1957 passed /
1 skipped (3 min 9 s).**

The one failure is
`tests/test_nightly_weekly_trends.py::test_weekly_totals_are_the_sum_of_that_week_only`.
It asserts that the week of 2026-08-09 totals 140, and it reads 120 today.

The likely cause is the date: the test calls `get_nightly_weekly_trends(n_weeks=8)`
relative to today, and that week is now at the window's edge. It is not caused
by this plan, because nothing has changed yet. Compare against this failure,
and fix it only as its own commit if it gets in the way.

### 2026-10-13 — Phase 0 measured (no output changed)

Live sheet loaded 2026-10-13. Tableau export: 103.059 people, found
2024-01-01 → 2026-10-10. The export holds only people **found since
2024-01-01**, so a 2025 baptism of someone found in 2023 is missing from it.
That is why every baptism count below comes from the **certified** monthly
figure and never from the person rows. The scripts were throwaway and are not
in the repo.

#### 0.1 — Is the 2026 jump real?

**1. Found, by source.** Missionary-found people make up 77–87% of the growth.
Street and door-to-door contacting together make up 74–82% of it. Paid ads and
Facebook make up 18–26%.

| Source | 7 Sep–10 Oct 2025 | same weeks 2026 | change | share of growth | Jun–Aug 2025 | Jun–Aug 2026 | change | share of growth |
|---|---|---|---|---|---|---|---|---|
| All | 2.875 | 5.267 | +83% | 100% | 7.591 | 14.271 | +88% | 100% |
| Contacto en la calle | 882 | 2.017 | +129% | 47% | 2.170 | 4.814 | +122% | 40% |
| Casa por casa | 936 | 1.589 | +70% | 27% | 2.419 | 5.205 | +115% | 42% |
| Facebook · anuncio de la misión | 201 | 673 | +235% | 20% | 521 | 1.090 | +109% | 9% |
| Anuncio pagado de las oficinas | 338 | 470 | +39% | 6% | 607 | 1.172 | +93% | 8% |
| Por alguien que recibe lecciones | 205 | 253 | +23% | 2% | 586 | 913 | +56% | 5% |

By the plan's rule this leans towards **real work**. It is not proof: a looser
habit of logging street contacts would look exactly the same.

**2. What happened to the people found** (cohorts by found month, 30 days
mature):

| Found in | Found | Contacted ≤30 d | Being taught ≤30 d | Taught ≤30 d (people) |
|---|---|---|---|---|
| Jun 2025 | 2.719 | 51,5% | 45,6% | 1.241 |
| Jul 2025 | 2.407 | 49,0% | 47,2% | 1.135 |
| Aug 2025 | 2.465 | 50,6% | 45,2% | 1.113 |
| Jun 2026 | 4.755 | 45,1% | 58,3% | 2.773 |
| Jul 2026 | 4.714 | 45,7% | 58,5% | 2.760 |
| Aug 2026 | 4.802 | 45,6% | 56,1% | 2.696 |

**There is no collapse.** The share of found people being taught within 30
days went *up*, and the number of people taught within 30 days more than
doubled. The extra people found are not empty records.

(In 2026 more people are "being taught" than "contacted" within 30 days, so
the contact milestone is under-recorded. It is a recording quirk, and it has
no effect on the conclusion.)

Events by month, any found date, Jun–Sep:

| | 2025 | 2026 | change |
|---|---|---|---|
| People starting lessons | 5.321 | 10.995 | ×2,1 |
| First time at church | 549 | 768 | +40% |
| Dates set | 208 | 690 | ×3,3 |
| **Certified baptisms** | **137** | **158** | **+15%** |

**3. Date quality. This is the real fall, and it does not depend on how finding
is recorded.**

| Dates set in | Dates | Baptized ≤6 wk | Baptized ≤12 wk |
|---|---|---|---|
| 1 Jun–20 Jul 2025 | 80 | 28,7% | **38,8%** |
| 1 Jun–20 Jul 2026 | 333 | 11,4% | **13,2%** |
| Jun–Aug 2025 | 158 | 23,4% | (38,6%) |
| Jun–Aug 2026 | 550 | 13,5% | (not mature) |

By month, the 12-week rate was 32–44% every month of 2025. It was 26–32% in
Jan–May 2026 and **13,5% in June 2026**.

*How* dates are set changed at the same time:

| Dates set Jun–Sep | 2025 | 2026 |
|---|---|---|
| Person had attended church before the date | ≈70% (58–83% by month) | ≈33% (26–38%) |
| Date set within 7 days of being found | 17–26% | **47–56%** (34–41% in Jan–May) |
| Date set on or before the first lesson | 9% (19 of 208) | **36% (245 of 690)** |

**This is mission-wide.** Every zone except Victoria set at least 2,5 times
as many dates. The share of dates set after church attendance fell in nine of
the ten zones, with San Pedro flat at 48% → 47% (for example Angol 83% → 17%,
Temuco Cautín 89% → 36%).

The step change is in **June 2026**: 229 dates, a median of 3 days from found
to date, and 26% after church. → Q-J below.

**4. Date inventory.** "Open" means set in the last 365 days and not yet
baptized. Tableau has no "dropped" field, so this count includes people who
are no longer progressing.

| As of | Open | >90 days | 0–30 days |
|---|---|---|---|
| 10 Oct 2024 | 286 | 158 (55%) | 48 (17%) |
| 10 Oct 2025 | 447 | 328 (73%) | 48 (11%) |
| 10 Oct 2026 | 1.229 | 810 (66%) | 177 (14%) |

The stale *share* is **not** worse than a year ago, because it was 73% then.
The stale *count* is 2,5 times larger.

**Two corrections to the audit's F1 (the build must not repeat them):**
- **(a) Baptisms are not down.** Certified Jan–Sep is 348 in 2026 against 296
  in 2025 (+18%), and Jun–Sep is +15%. The audit's "−15%" was one five-week
  window (27 → 23), which is inside the noise.
- **(b) "Two-thirds of the dates are stale" is not new.** It was 73% a year
  ago. What is new is the volume, and what a date is worth.

**0.1 OUTPUT. The packet leads with item 3 (date quality)**, with item 4's
count as support. The decision-65 wording for Phase 3.1 is:

> *En 2026 la misión encuentra casi el doble de personas, fija más del triple
> de fechas y bautiza un 15–18% más. Parte del salto puede ser cómo se
> registra; lo que no depende de eso es lo que vale una fecha: de las fijadas
> entre junio y julio de 2026, 13 de cada 100 terminaron en bautismo dentro
> de 12 semanas; en 2025, 39. Hoy la mitad de las fechas se fija en la primera
> semana después de encontrar a la persona, y dos de cada tres antes de que
> asista a la Iglesia.*

**A new problem found by 0.1: the pipeline forecast overshoots since June.**
`forecast.fit_pipeline` pools the last 15 month-ends, which straddle the two
regimes. Its 6-week conversion for a 0–14-day-old date is 21,5%. Fitted on
2025 month-ends alone it is 29,9%, and on 2026 month-ends alone 15,8%.

Its backtest, forecast against actual, month by month:

| Month-end | Open dates | Forecast | Actual | Forecast ÷ actual |
|---|---|---|---|---|
| 2026-01-31 | 495 | 29,6 | 29 | 1,02 |
| 2026-02-28 | 530 | 31,2 | 34 | 0,92 |
| 2026-03-31 | 601 | 40,4 | 42 | 0,96 |
| 2026-04-30 | 618 | 35,0 | 30 | 1,17 |
| 2026-05-31 | 713 | 44,4 | 41 | 1,08 |
| **2026-06-30** | **883** | **62,9** | **37** | **1,70** |
| **2026-07-31** | **961** | **54,4** | **26** | **2,09** |

The median-miss statistic (8%, over 12 backtests) hides this.

The **live** packet prints *"Las 1.229 fechas … valen entre 51 y 70"*
(`packet.py:650`, `:1866`, `:2558`). The last two months suggest about half of
that.

The year landing does NOT use the pipeline (`forecast.year_landing` reads
monthly certified figures), so the gap to 527 is unaffected. Phase 2.3's bet
(b) IS affected. → Q-F below.

#### 0.2 — What *Mes pasado* would print for September 2026

The test used a hand-built `Period` (key `CALENDAR_MONTH`, 1–30 Sep).

- **Weeks counted:** 6, 13, 20 and 27 Sep, which cover **31 Aug – 27 Sep**. ✓
  This is the expected result.
- **Reporting:**

  | Unit | Reported | Rate |
  |---|---|---|
  | Mission | 130 of 180 | **72%** |
  | Angol | 23 of 36 | 64% |
  | Los Ángeles Norte | 33 of 48 | 69% |
  | San Pedro | 31 of 44 | 70% |
  | Temuco Ñielol | 43 of 52 | 83% |

- **Certified baptisms 1–30 Sep:** the closed monthly capture answers, **29**.
  `period_baptisms` finds it by days with no code change, which confirms
  step 1.2's premise. October's capture is open: 7 through 12 Oct.
- **Prorated leadership goal (mission):** the week ending 6 Sep belongs to
  **2026-5, where only 1 of the 45 pilot areas has a leadership goal**.
  AREA_TRANSFER_GOALS holds 1 area for 2026-07-27 and 45 for 2026-09-07. So
  `_leadership_goals` returns `complete=False`, with "1 area with goal" for
  all seven. Of 180 area-weeks, 136 carry a goal.

  | Indicator | Goal over those 136 area-weeks | Actual |
  |---|---|---|
  | Nuevas Personas | 1.020 | 780 |
  | Lecciones con Miembros | 763,5 | 511 |
  | Amigos en la Reunión Sacramental | 248,5 | 170 |
  | Primera Semana | 41,5 | 29 |
  | Fecha | 168 | 153 |
  | Bautizados (form) | 35 | 7 |
  | Conversos Recientes | 266,5 | 202 |

- **The weekly form started the week ending 16 Aug 2026.** Weekly rows for the
  pilot are: 1 area on 9 Aug; 31, 32, 30, 26 areas through 6 Sep; then 33–37
  areas per week. Every month before August reads 0%, and **August reads 42%
  only because it is the launch month.**
- **Consequences:**
  - **For 1.4:** "the last six closed months" of reporting do not exist. By
    the November council there are three: August (launch), September and
    October. → A2 below.
  - **For 1.1:** *Mes pasado* compares with the whole previous month, so a
    September packet would set 72% against August's launch 42%. That only
    bites for September, because October against September is clean. A test
    should pin that a comparison month the form had not reached is *sin
    comparación*, not a false rise.
  - **For the first real council packet (October, 28 Sep–25 Oct form
    weeks):** the week ending 25 Oct is in **2026-7**. It is graded only if
    2026-7's leadership goals are saved. They are due Mon 2026-10-19 (Metas
    bulk Recomendar).

#### 0.3 — The colours under decision 59

**The plan's partial-goal rule fails on real data.** Step 1.3 says to grade
"only the areas that have a goal" when goals are incomplete. Because one cycle
had a single area with goals, September collapses to that one area: 267%,
300% and 164% green at mission level. That is junk.

The rule measured below is **A1**: grade over the **area-weeks that carry a
goal**. Inside those, a silent area-week counts as 0. With complete goals, A1
is exactly decision 59. With a gap, it drops only the uncovered weeks, not
whole areas.

Each cell reads *band %*, today's decision 44 → decision 59 under A1. The
indicators are, in order: Nuevas Personas · Lecciones con Miembros · Amigos en
la Reunión · Primera Semana · Fecha · Conversos.

**This transfer, 2026-6 (5 weeks, goals complete):**

| Unit | NP | LcM | Reunión | 1ª Sem | Fecha | Conversos | changed |
|---|---|---|---|---|---|---|---|
| Mission | warn 85→warn 65 | warn 76→**bad 58** | good 91→warn 71 | good 106→warn 83 | good 106→warn 84 | warn 84→warn 63 | 4/6 |
| Angol | warn 63→bad 41 | warn 62→bad 39 | good 170→good 104 | good 154→warn 86 | warn 87→warn 60 | bad 39→bad 21 | 3/6 |
| Los Ángeles Norte | good 93→warn 70 | good 91→warn 72 | warn 79→warn 62 | good 112→warn 87 | good 131→good 108 | good 98→warn 83 | 4/6 |
| San Pedro | warn 85→warn 68 | warn 66→bad 53 | warn 73→warn 60 | good 97→warn 83 | good 93→warn 79 | good 120→good 99 | 3/6 |
| Temuco Ñielol | good 97→warn 80 | warn 88→warn 72 | warn 90→warn 75 | good 91→warn 76 | good 116→good 95 | warn 65→bad 51 | 3/6 |

At mission level the bands go from **3 green / 3 amber / 0 red** to **0 green /
5 amber / 1 red**.

**September (A1: 136 of 180 area-weeks carry a goal):**

| Unit | NP | LcM | Reunión | 1ª Sem | Fecha | Conversos | changed |
|---|---|---|---|---|---|---|---|
| Mission | warn 82→warn 61 | warn 69→bad 52 | warn 73→bad 57 | warn 81→warn 63 | good 93→warn 74 | warn 85→warn 62 | 3/6 |
| Angol | bad 60→bad 40 | bad 60→bad 39 | good 149→good 94 | good 175→good 100 | warn 82→bad 58 | bad 31→bad 18 | 1/6 |
| Los Ángeles Norte | good 94→warn 73 | warn 81→warn 67 | bad 54→bad 43 | bad 46→bad 36 | good 132→good 111 | good 102→warn 86 | 2/6 |
| San Pedro | warn 87→warn 65 | bad 59→bad 46 | warn 64→bad 53 | good 97→warn 80 | warn 61→bad 53 | good 128→good 99 | 3/6 |
| Temuco Ñielol | warn 87→warn 65 | warn 77→bad 58 | warn 66→bad 54 | bad 56→bad 45 | good 99→warn 78 | warn 64→bad 45 | 4/6 |

At mission level the bands go from **1 green / 5 amber** to **0 green / 4 amber /
2 red**.

**As the plan expected, the mission loses every green.** It does not turn
all-red. Five zone cells stay green under decision 59, and they are the honest
ones:
- Angol, Amigos en la Reunión (104%, 94%);
- Los Ángeles Norte, Fecha (108%, 111%);
- San Pedro, Conversos (99%).

**This before/after table is what Zackary sees before Phase 1 ships** (risk 1).

#### 0.4 — Suite baseline

Re-run 2026-10-13 after the measurements, with no code changed: **1 failed /
1957 passed / 1 skipped** (2 min 6 s). The single failure is the same one,
`test_nightly_weekly_trends.py::test_weekly_totals_are_the_sum_of_that_week_only`,
so the result matches the baseline above.

#### Waiting on Zackary before Phase 1

- **A1 (amends 1.3's partial-goal sentence):** grade decision 59 over the
  area-weeks that carry a goal, with silent area-weeks inside them counting as
  0. The meta reads "sobre N de M semanas-área con meta". *Recommended.* The
  plan's literal rule prints 267–300% for September.
- **A2 (amends 1.4's trend):** the reporting spark shows **the last 8 complete
  weeks**, since the form only began on 16 Aug. It switches to six closed
  months once six exist (about Feb 2027). *Recommended.*
- **Q-F (new, for Phase 2):** the pipeline forecast has overshot by ×1,7–2,1
  since June. The options:
  - fit only on month-ends since the change (from 2026-06-30);
  - weight recent month-ends;
  - keep the fit, and print the backtest's last two misses beside the range.

  *Recommended: fit on the last 6 month-ends* (all within the 2026 regime by
  December), as a fix step at the start of Phase 2, before bet (b). The live
  "51–70" sentence stays as it is until then.
- **Q-J (context only, no build depends on it):** did something change in
  June 2026 in how dates are set (for example a date at the first lesson)?
  If so, the packet can name it in 3.1.

**Zackary answered 2026-10-13:** A1 yes, A2 yes, and for Q-F "fit the last 6
month-ends, as the first step of Phase 2". They are recorded as decisions
66–68 in §1, and steps 1.1, 1.3, 1.4 and 2.0 are amended. Q-J (what changed in
June): **Zackary does not know.** So the packet must NOT name a cause in 3.1.
It states the measured change and its date (June 2026) only.

**Next: Phase 1** (new chat), starting at 1.1.

### 2026-10-13 — Phase 1 built, verified and pushed

One commit per step: `07c0e19` 1.1 · `888408c` 1.2 · `7603722` 1.3 ·
`49a0408` 1.4 · `3baa6c7` 1.5 · `05c9ba3` 1.6 · `cf760e0` 1.7 (fixes found by
reading the live pages). **Suite: 1 failed / 1996 passed / 1 skipped**, the
same single date-sensitive failure as the baseline (+39 new tests).

**What exists now:**
- **1.1** `periods.LAST_MONTH` ("Mes pasado", label = the month's name, e.g.
  "septiembre 2026"), between *Últimas 6 semanas* and *Mes calendario*.
  `P.PACKET_PERIOD = LAST_MONTH`; `P.DEFAULT_PERIOD` stays `THIS_TRANSFER`.
  `comparison_for(..., records_from=)` makes the twin month
  `NO_COMPARISON` when it starts before the form really began.
  `ReportData.weekly_records_from` = the first week ≥ 25% of the mission's
  areas filed (live: **2026-08-16**). So September prints *"Sin comparación:
  El formulario semanal empezó la semana que termina el 16 de ago de 2026,
  así que agosto 2026 no es un mes completo de informes."* October will
  compare cleanly with September.
- **1.2** No code needed in `period_baptisms`; pinned by tests (September
  answers 29). The data note says weeks are not days, for *Mes pasado* only.
- **1.3** Decision 59/66 in `model._ki_rows`. New field
  `MetricRow.lead_area_weeks_possible`. `LEAD_MIN_SHARE` (0,5) is now a
  share of the POSSIBLE area-weeks. **Live check: September grades 136 of
  180 area-weeks and every cell matches Phase 0.3's table** (mission NP 61,
  LcM 52, Reunión 57, 1ª Sem 63, Fecha 74, Conversos 62).
  **One rule the plan did not state, decided in the build:** a unit that filed
  nothing at all keeps its goal and is NOT graded. Its rows read "sin
  informes" (not seven red zeros, and not "sin meta"). The reporting KPI
  carries its 0%.
- **1.4** `ReportModel.reporting` (`model.Reporting`: reported, possible,
  target 0,95, trend, trend_unit, owners) and `model.reporting_status` (D2).
  The owners are `scope.zone_leader_names` (the companions of `Is_ZL` areas,
  read like `packet.leadership`). `ChildRow.owners` too.
  `PP.reporting_line` / `packet.reporting_headline` draw it above the tablero
  on the mission and zone pages. The mission's "Quién informó" names each
  zone's owners and colours on 95/85. The trend's weeks before the form are
  gaps. Live September: mission 72% (130/180), Angol 64%, LAN 69%,
  San Pedro 70%, Temuco Ñielol 83%, all red.
- **1.5** The decision-44 sentences are gone from both renderers (a test
  guards it). With partial goals the tablero's REAL follows the graded
  area-weeks, the Meta head reads "136 de 180 sem.-área", and the note says
  so. The screen shows the reporting line above the seven cards.
  `summary.where_we_are` opens with reporting.
- **1.6** The screen has the *Mes pasado* tab and a primary button
  "Paquete del consejo — septiembre 2026" that always builds `LAST_MONTH`.
  A second button "Paquete · {período}" builds the selected tab and is hidden
  on *Mes pasado*. `packet.build()` with no period builds `PACKET_PERIOD`;
  `packet.filename_for(key, today)` is new.
- **1.7** Live builds (data pickled 2026-10-13): **Mes pasado (September) =
  50 pages, Este traslado (2026-6) = 49 pages** (48 before Phase 1).
  Read: mission p.4, Angol p.12, an area page (p.36), *Cómo leer*, the data
  note. Screen run headless (AppTest) on both tabs, with no exception.

**Two things for Zackary to know (not blocking):**
1. **Los Ángeles Norte's zone section went from 2 pages to 3** in both
   packets. The headline row (25 pt) leaves its first page 23 pt short for
   the 140 pt ladder block, which cannot split. Step 2.1 rebuilds exactly that
   tablero area (the *Termina en / Falta* columns and their note leave it), so
   it was left rather than squeezed.
2. The *Mes pasado* packet still prints the transfer forecast columns
   (*Termina en / Falta*) beside September's figures. They are about 2026-6,
   in progress. That is step 2.1's job.

**Next: Phase 2** (new chat), starting at **2.0** (the 6-month pipeline
refit, committed on its own). Phases 1–2 must be live before 2026-11-02.
**Zackary must Reboot the deployed app** after this push
(`dashboard/DEPLOYING.md`).

### 2026-10-16 — Phase 2, step 2.0 (the pipeline refit), committed `c763c5e`

The live sheet was loaded on 2026-10-16: 1.247 open dates.

**The refit does not reach the plan's "near 1,0×".** Dates are still losing
value month by month. The share of open dates that end in a baptism within 6
weeks was 6–7% at the month-ends of Jan–Mar 2026, 4,2% in June, and 2,7% in
July and August. Every fit looks backwards, so every fit length overshoots:

| Fit | Prints today | Jun / Jul / Aug, in-sample | Jun / Jul / Aug, with the fit of its own day |
|---|---|---|---|
| 15 month-ends (before) | 58 (49–67) | ×1,56 / 1,92 / 1,76 | ×2,08 / 2,53 / 2,14 |
| **6 (decision 68)** | **43 (24–63)** | ×1,19 / 1,46 / 1,34 | ×1,65 / 2,02 / 1,70 |
| 3 (June regime only) | 34 (27–42) | ≈1,0 by construction | ×1,66 / 1,99 / 1,47 |

(On 10-15 the 6-month fit gave 43,1. On 10-16 the packet prints 23–61.)

**A build-time rule (Zackary may amend):** the backtest miss used to be
measured **in-sample**: the fit had already seen the month it was checking.
Each of the last 12 month-ends is now forecast **with the fit that existed at
that month-end**, which is what the packet would have printed then. That
miss is 45% typical, and the forecast ran high in 10 of the 12. So the
80% range widens honestly (24–63 against an in-sample 29–57). Both renderers
now say *"el cálculo hecho en su momento falló por un 45% típico y se quedó
alto en 10"*. `Pipeline.over` and `Pipeline.miss_clause` are new. The method
text prints `FIT_MONTHS` instead of a hard-coded 15.

I asked Zackary to choose between this, the plain refit and a 3-month fit.
He declined the question and said "keep working", so the recommended option
was built.

**For 2.3's bet (b):** the pipeline still runs high (about ×1,5–2 in the last
three months). Bet (b) must be printed as a range that carries the same
caveat, or be read from the age-bucket *ratio* (91–180 against 31–60), which
the overshoot affects less than the level.

Suite: **1 failed / 2000 passed / 1 skipped**, the same single date-sensitive
failure. Four new tests.
