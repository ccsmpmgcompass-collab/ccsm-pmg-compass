# AUDIT 2026-10-06 — The council packet, read as a mission president

**Asked (Zackary, 2026-10-06):** a deep, very critical technical audit and
scoring of the council packet ("Paquete del Consejo") — how usable its
information is, how easily it compares units and shows where growth is needed,
and whether it projects the future. The reader to optimise for is **a mission
president looking for where to focus and grow**. Target: the best numerical
informe that can be made.

**Status: AUDIT DONE, QUESTIONS ANSWERED (§7.1, decisions 44–51). Nothing is
built.** Next step: write `PLAN-2026-10-XX-packet-rebuild.md` from §5, §7.1
and §8, then build phase by phase. Several recommendations re-open earlier
decisions (11, 14, 21, 22, 42). That is on purpose, and each one says which
decision it re-opens and gives the evidence.

---

## §0 — How this was measured

- **Two live packets were generated** on 2026-10-06 from the live sheet with
  `app.reports.packet.build(period, data=load_data())`: *Este traslado* (2026-6,
  4 of 6 weeks complete) and *Semana pasada* (28 Sep – 4 Oct). **Both are 104
  pages.** Every page was rasterised and its text extracted (pypdfium2, in the
  scratchpad, not installed into the venv).
- I read the mission pages (4–8), one full zone (Angol, 9–13), one full
  district (El Mirador, 29–32), area pages (81–82), the front matter (1–3) and
  the data note (104), as images and as text.
- Model-level measurements came from `model.build_all('this_transfer')`
  against the same `ReportData`: goal agreement, ranking agreement, per-
  companionship productivity, the Tableau detail history, and the baptism
  pipeline.
- Code read: `app/reports/{packet,model,grading,tableau}.py`,
  `app/analytics/{rate_metrics,annual_baptisms}.py`, and
  `PLAN-2026-09-21-informes.md` §1.

Page numbers below are from the *Este traslado* packet.

---

## §1 — The score

Each dimension is scored 0–10 **for a mission president deciding where to
focus**, not for technical craft in general.

| # | Dimension | Weight | Score | Why, in one line |
|---|---|---:|---:|---|
| 1 | Trust: correctness, honest statements, provenance | 15% | 6.5 | Arithmetic is careful and sourced, but the packet prints one false explanation, raw English keys, and a flag that contradicts its own numbers |
| 2 | Validity of the yardstick | 15% | 3.0 | It grades against goals the companionships set for themselves. Those goals range 0.46×–3.5× leadership's goals, so the grade measures ambition as much as work |
| 3 | Focus signal (does it point at the right units?) | 15% | 3.0 | The zone ranking points the wrong way (§2, C1) |
| 4 | Comparability: peers and the ladder | 10% | 6.0 | The ladder and sibling strip are good ideas, but they compare attainment of self-set goals, so they inherit C1 |
| 5 | Trend and history | 10% | 3.0 | Shows only the period's own weeks and one comparison period. A weekly packet's "trend" is one column. 2½ years of Tableau history go unused |
| 6 | Projection and forward view | 12% | 1.5 | One naive straight-line annual projection. No transfer-end projection, no required rate, no pipeline forecast, no feasibility |
| 7 | Diagnosis: from lead indicators to results | 8% | 4.0 | Funnel and rates exist, but nothing links a lagging Key Indicator to the activity behind it. The mature lower funnel is never shown |
| 8 | Statistical care with small numbers | 5% | 5.0 | Coverage is handled well. Percentage changes on single-digit counts (+260%, +133%, −70%) are not |
| 9 | Economy and first-pass reading | 5% | 4.0 | 104 pages whatever the period. No single page answers "where do I go this week?" |
| 10 | Visual encoding and print craft | 5% | 8.5 | Clean, consistent, vector, colour-disciplined. The best part of the packet |
| | **Weighted total** | 100% | **41.5 / 100** | |

**Verdict.** It is a well-built *record* of what was reported, and an
unreliable *instrument* for deciding where to go. The craft is high. The
problem is the yardstick and the missing forward view. Fixing the five
critical and high findings below would, on the same rubric, put it around
**80/100**. Most of that gain comes from dimensions 2, 3 and 6.

---

## §2 — Critical findings

### C1. The ranking measures goal ambition, not performance — and on live data it points the president at the wrong zone

**What the packet says (p5):** zones "más atrasada primero" — **1 Angol 41%**
· 2 Los Angeles Norte 46% · 3 San Pedro 55% · **4 Temuco Ñielol 56%**. Each
figure is the mean of the seven Key Indicators against *the companionships'
own* goals, per active area (decisions 11, 14).

**What the work says.** Output per active companionship-week, as a
percentage of the mission's rate (silent areas counted as zero, the packet's
own strict basis):

| Zone | Packet rank | Sacrament | Baptismal date | Baptisms (form) | RC at church | New people |
|---|---|---:|---:|---:|---:|---:|
| Angol | 1 — "most behind" | **127** | **108** | **143** | 45 | 83 |
| Los Angeles Norte | 2 | 78 | 128 | 107 | 123 | 115 |
| San Pedro | 3 | 123 | 91 | 117 | 156 | 91 |
| Temuco Ñielol | 4 — "least behind" | **82** | **77** | **49** | **69** | 106 |

Angol is ranked worst, yet per companionship it beats the mission on three of
the four results closest to baptism. Temuco Ñielol is ranked best while
trailing the mission on five of seven. It also has the best reporting in the
mission (85%), so silence does not explain the gap. Ñielol simply **sets
the lowest goals**: sacrament 2.5 per area-week against Angol's 4.3, and
baptismal dates 1.8 against 2.7.

Averaging the three results nearest baptism that have enough volume to trust
(sacrament, baptismal date, RC at church; form baptisms are left out as only
1–2 events), the order **weakest first** is **Temuco Ñielol 76 · Angol 93 ·
Los Angeles Norte 110 · San Pedro 123**. The packet's order is Angol · LAN ·
San Pedro · Ñielol. **The zone the packet calls strongest is the weakest per
companionship.**

**How widespread.** Across the 206 area-level Key Indicator rows that carry
both goals, **88 (43%) change colour band** depending on which goal is
used. The ratio of self-set goal to leadership goal runs **0.46× (p10) →
1.12× (median) → 3.5× (p90)**. The ranking of *areas* is more robust
(Spearman 0.83 between the two goal bases; 8 of the bottom 10 are the same),
so the damage is concentrated at zone and district level, where the president
makes the first decision.

**Why it matters.** Grading against self-set goals rewards low goals. A
companionship that aims low reads green. A zone leader who pushes ambitious
goals turns the zone red. In council, the president is told to focus on
Angol.

**Fix (re-opens decisions 11 and 14):**
1. **Rank on a goal-free productivity index**: output per active
   companionship-week relative to the mission (100 = mission rate), weighted
   toward the results closest to baptism. It is explainable out loud: "Angol
   brings 27% more friends to sacrament per companionship than the mission
   does."
2. **Grade against one goal, leadership's** (`AREA_TRANSFER_GOALS`). Keep the
   companionship's own goal as a printed column called *compromiso*. It
   should never colour the row.
3. **Separate reporting from performance.** "Angol: 2 areas silent all
   transfer" belongs in its own ranked action list, not folded into a
   performance mean.

### C2. Baptisms read "al ritmo" in zones that are at 9–30% of leadership's goal

The Key Indicator tiles and tables grade *Bautizados y Confirmados* against the
companionships' own baptism goal, which is close to zero (0.0–0.1 per
area-week):

| Unit | Packet prints | Against leadership's transfer goal |
|---|---|---:|
| Mission | 7 · atrasado · **77%** | **15%** (7 of 45.3) |
| Temuco Ñielol | 1 · **105%** | **9%** |
| San Pedro | 2 · **94%** | **11%** |
| Angol | 2 · al ritmo · **100%** (green tile, p9) | **30%** |

Below the mission, **no certified baptism figure exists anywhere in the
packet**. The certified block appears on the mission pages only (p6). Zones,
districts and areas see only the form figure, graded against a near-zero goal.
It is also the first tile on every unit page, which goes against the spirit
of decision 37.

A related goal-system inconsistency the president should see: leadership's
transfer goals for baptisms in the **four pilot zones** sum to **68 per
transfer**, about **590 a year**. The **whole-mission annual goal for ten zones
is 527**. Both can't be the target.

**Fix:** grade baptisms only against leadership's goal. Give every zone and
district a baptism figure from Tableau's `confirmation_date` by roster area
(see Q5: this re-opens decision 42). Reconcile the transfer goals with the
annual goal, or say on the page which one rules.

### C3. The packet tells the president something false about the missionaries

Page 6 and page 3: *"El formulario semanal … informó 7 en 2026-6, y las dos no
coinciden: **los misioneros no siempre anotan el campo**."*

The 22 certified baptisms cover **all ten zones**. The 7 from the form cover
**the four pilot zones**. That gap was diagnosed and **retracted on
2026-10-02** (`PLAN-2026-10-02-goals.md` §2.5 "Retracted"): it is a scope
difference, not under-reporting. The packet still prints the old explanation
in a document whose readers lead those missionaries.

**Fix:** compare like with like (certified or detail-export baptisms for the
pilot zones' roster areas against the form), and delete the sentence.

### C4. Almost nothing looks forward

The only projection in 104 pages is "SI EL AÑO SIGUE ASÍ **463**" (p6), a
straight line from 347 over nine months. It has no range, no required rate
and no feasibility check. The president's three forward questions go
unanswered:

**(a) "Where will this transfer finish?"** Not shown. With live numbers
(mission, raw sums at today's 76% reporting, leadership's full-transfer
goal):

| Key Indicator | 4 weeks | At this pace, week 6 | Goal | Finish | Needed per week, weeks 5–6 | × current rate |
|---|---:|---:|---:|---:|---:|---:|
| New people | 806 | 1,209 | 2,038 | 59% | 616 | 3.1× |
| Member lessons | 528 | 792 | 1,525 | 52% | 366 | 2.8× |
| Friends at sacrament | 216 | 324 | 493 | 66% | 138 | 2.6× |
| Baptismal dates | 167 | 251 | 334 | 75% | 84 | 2.0× |
| RC at church | 210 | 315 | 527 | 60% | 159 | 3.0× |
| Baptized (form) | 7 | 11 | 68 | 15% | 31 | 17× |

In one table, the president learns that the transfer's outcome is already
largely set. The useful question is no longer "are we behind?" but "which
two indicators can still move, and where?"

**(b) "Will we make 527?"** The packet says −48 in red. It does not say:
- **2026 is the mission's best year in three.** Jan–Sep: **347** against
  296 (2025, **+17%**) and 290 (2024, **+20%**). `baptisms_by_month` has held
  2024 and 2025 since the data-pages work; the Panel draws them; the packet
  does not.
- **The goal needs 60 a month for Oct–Dec.** The best month in 33 months of
  history is **50** (Dec 2024). Q4 has run 95 (2024) and 107 (2025).
- **The landing is a range, not a point:** last two months' pace → 443;
  last three → 458; straight line → 463; prior Q4s scaled by this year's
  growth → 467. **443–467**, which is 84–89% of goal.
- **The months are falling:** Jul 47 → Aug 36 → Sep 28, the lowest since
  January. Sep 2025 was 20 and Sep 2024 was 39, so September alone may be
  seasonal. Three falling months is still a trend worth naming.

**(c) "What's coming in the next six weeks?"** Tableau's detail export knows
who has a baptismal date and no baptism yet. **391 people** had a date set in
the last 90 days and are not yet baptized (pilot zones: San Pedro 58, Angol
56, Los Angeles Norte 39, Temuco Ñielol 37). Of everyone given a date in
2025-01 → 2026-03, **26% were baptized within 42 days and 34% within 90**
(median 32 days from date to baptism). An age-adjusted pipeline forecast per
zone is the best leading indicator the mission has. The packet doesn't use it.

**Fix:** a forward page at mission and zone level (§5). Every projection is
printed as a range with its method in one line, never as a point.

---

## §3 — High findings

### H1. "Meta no utilizable" is the mission's verdict, pasted onto every unit, and it flips with the period
- `grade_ki(flag=…)` receives the **mission-scope** verdict (grading.py:238).
  So El Mirador (p29) prints *"7 contra una meta declarada de 6 … la meta hay
  que revisarla"* for a goal it **beat**. Of the 18 units that print the flag
  sentence, **7 are at or above the rule's own 25% floor** (31%, 116%, 30%,
  30%, 25%, 50%, 41%).
- The same indicator, *Amigos en la Iglesia (Primera Semana)*, is **flagged and
  excluded** in the transfer packet (24%, just under the 25% floor) and is the
  **#1 "lo que hay que mover"** in the weekly packet (31%). The president gets
  opposite instructions from two packets printed the same day.
- **Fix:** evaluate the flag per unit, or (better, with C1) retire it for Key
  Indicators once leadership's goal is the yardstick. Never print the
  "revise the goal" sentence when real ≥ goal.

### H2. Conversion rates print raw code keys
Pages 8 and 13 (and every zone's rates page) print `contact_rate`, `mc_rate`,
`lesson_rate`, `close_rate`. `rate_row()` returns no `label`, and
`packet.rate_lines` falls back to `key` (packet.py:1041). The screen
looks the label up in `_data.labels` (views/11_Informes.py:823); the packet
does not. The rate's computed **change is never printed**, and *lesson_rate*'s
denominator (contact attempts, not contacts) is never stated.

### H3. No history beyond the period
- *Semana a semana* shows only the period's weeks. In the weekly packet it is
  **one column**, a trend made of a single point.
- `WEEKLY_KI` holds 8+ weeks, `DAILY_LOG` runs from 2026-08-09, Tableau detail
  from 2024-01-01, and certified baptisms by month from 2024-01. None of it is
  used for trend.
- *Mes a mes* (p6) has no 2025 or 2024 column. Year-over-year is the only
  comparison that controls for seasonality, which matters a lot in Chile
  (September holidays, December).
- **Fix:** every unit page carries a fixed 12-week strip whatever the period,
  with transfer boundaries. The mission carries year-over-year for every
  Tableau-backed measure.

### H4. The nightly table makes the reader do arithmetic and shows two numbers for one thing
- **REAL** is the period total (3.248), **META** is per area per week (44,8),
  and the label underneath says "meta 45/área/sem". That makes two goal
  figures and **no actual per area-week**, so real and goal can't be compared
  without dividing.
- *Nuevas Personas Encontradas* is **806** on p4 (weekly form) and **900** on
  p5 (nightly), with no sentence connecting them.
- Rows are ordered "más atrasado primero" by distance to goal, while the same
  block says nightly rows are judged by movement, not distance (decision 31).
  The flagged *Lecciones con CR* still sits at the top.

### H5. Percentage changes on tiny counts
El Mirador (p30): **+260%**, **+133%**, **+111%**, **−70%** on counts of 5–27.
Mission: *Bautizados* **−35%** on 7. The ±15% flat band (`FLAT_BAND`) applies
to nightly rows only. Key Indicator arrows fire at any size. A president
reading arrows will chase noise.
**Fix:** below ~20 events print the absolute difference ("+19", "−3"), and
give no arrow unless the change clears a simple Poisson band.

### H6. No page answers "where do I go?"
The packet runs 104 pages, the same length for a week as for a transfer.
Page 4's "Lo que hay que mover" names a *metric*, never a *place*. Nothing
says which three units account for most of the mission's shortfall, which
areas are declining, or which have gone silent. The president has to build
that picture from 63 unit sections.
**Fix:** a one-page *Dónde enfocar* (§5): the gap in absolute numbers
broken down by unit (Pareto), a productivity × trend quadrant, and the
reporting list.

---

## §4 — Medium and low findings

- **M1. Scores without meaning** (p8, p13, p30): "Esfuerzo 59,2 de 100" has no
  comparator, no trend and no definition. Only area pages give a rank.
  Either give the score a ladder and a trend, or drop it from mission and
  zone pages.
- **M2. The funnel never shows its bottom.** The cohort-maturity rule is
  right, but it means church → date → baptism is "aún madurando" in every
  packet. The lower funnel is what the president cares about. **Fix:** add
  a *mature cohort* funnel, people found 90–180 days ago followed to today,
  per zone against the mission. The zones-of-the-mission table (p7–8) also
  prints an unlabelled percentage beside "Enseñándose".
- **M3. Lead indicators and results are never linked.** Angol's close rate
  is 7,7% against a 25% target (p13) while its baptismal dates run *above* the
  mission. The packet prints both and never asks what that means. A
  "result → driver" line per lagging Key Indicator would turn findings into
  coaching.
- **M4. Developer language in a president's document:** "decisión 21",
  "decisión 42", `WEEKLY_KI`, `MISSION_ORG`, `COMPASS_CCSM`,
  `TABLEAU_BAPTISM_WINDOWS`, `AGENT_CONFIG` (pp. 2, 6, 104).
- **M5. Area pages:** the sparklines have no values or scale, and there are
  no nightly activity figures, which are the inputs a companionship controls.
  "Contra su distrito +22 · su zona +0 · la misión −8" inherits C1.
- **M6. The zones table shows 3 of the 7 Key Indicators** (NUEVAS · SACR. ·
  BAUT.) beside a mean of all seven. The four hidden ones drive a figure the
  reader can't check.
- **L1.** The print guide is page 2 of the president's copy.
- **L2.** Weekly packets repeat a 23-page area section for one week of data.

---

## §5 — What the best numerical informe looks like

Same data, same renderers, same vocabulary. The packet gets reorganised
around the president's three questions: *how are we doing, where should I
focus, what is coming?*

**Mission section, ~6 pages:**
1. **El tablero** — the seven Key Indicators in one table: per
   companionship-week · against leadership's goal · against last transfer ·
   against the same weeks last year (Tableau-backed ones) · 12-week sparkline
   · **projected finish with range** · **needed per week**.
2. **Dónde enfocar** — (a) the shortfall against leadership's goal in absolute
   numbers, broken down by zone and district (Pareto); (b) a quadrant of
   productivity index (vs mission) × 6-week trend, where "below and
   falling" is the focus list; (c) silent and late reporters as their own
   list.
3. **Bautismos: el año y lo que viene** — cumulative 2026 against 2025 and
   2024 and the goal line; required monthly rate against the best month ever;
   landing range; **pipeline forecast by zone** (dates set, expected baptisms
   in the next 6 weeks).
4. **Palancas** — mature-cohort funnel and conversion rates by zone against
   the mission, with each zone's largest leak named.
5. **Trabajo nocturno** — per companionship-week against goal, with change
   arrows that clear a noise band.
6. **Datos y cumplimiento** — reporting, freshness and sources, in plain
   Spanish.

**Zone, 2 pages:** tablero + productivity ladder (zone/mission) + its own
Dónde enfocar (districts and areas) + pipeline + funnel.
**District, 1 page.** **Area, half a page** with nightly inputs.
**Estimate: ~45 pages for a transfer packet (from 104).** *(The
short weekly variant proposed here was declined. Decision 50: a weekly packet
keeps the same structure.)*

**Projection rules (so nothing is over-claimed):**
- Always a range, always with its method in one line, never coloured as a
  verdict.
- Transfer finish = current per-reporting-area-week rate × active areas ×
  remaining weeks, with a range from the period's own week-to-week spread.
- Annual = the four anchors in C4(b), printed as min–max.
- Pipeline = open dates × historical conversion by days since the date was
  set, refit nightly from Tableau detail.

---

## §6 — What to keep

These are real strengths and the rebuild should not lose them:
- **Coverage honesty.** Compliance in every subtitle, "Áreas que informaron"
  under every weekly table, silent areas named. Nothing is quietly prorated.
- **The cohort-maturity rule** on the funnel is statistically correct and
  rare in dashboards like this.
- **Never summing Tableau and form figures** (decision 34).
- **The ladder and sibling strip** as *forms*. They need a better measure
  inside them (C1), not removal.
- **Certified baptism windows** (decision 42's sync) and the data note's
  provenance.
- **Print craft**: vector, consistent palette, a status vocabulary that
  means the same thing everywhere.

---

## §7 — Questions for Zackary (answers decide the plan)

1. **Yardstick (re-opens 11).** Grade every Key Indicator against
   *leadership's transfer goal*, with the companionship's own goal printed
   as an uncoloured *compromiso* column? **Recommended: yes.**
2. **Ranking (re-opens 14).** Rank units by a goal-free *productivity index*
   (per companionship-week vs mission, weighted toward the results closest
   to baptism), with reporting as a separate list? **Recommended: yes.**
3. **Which baptism goal rules:** the 527 annual (ten zones) or leadership's
   transfer goals (about 590/yr for four zones)? This is a question for the
   president, and the packet should print whichever he chooses.
4. **Forecasts in a council document.** Is the president comfortable with
   printed projection *ranges* (transfer finish, annual landing, pipeline)?
   And is there a page budget for the full copy? **Recommended: ranges, yes;
   ~45 pages.**
5. **Zone-level baptisms (re-opens 42).** Decision 42 banned detail-export
   counts because they ran 0–11% low on closed months. Per zone, the
   certified figure doesn't exist. Use detail-export baptisms by roster area,
   labelled "registros de Tableau", for zones and districts only?
   **Recommended: yes.** September matched exactly this time (28 vs 28).

## §7.1 — ANSWERED (Zackary, 2026-10-06): decisions 44–51

These carry on from the clarity pass's 36–43. Don't re-open them.

| # | Question | Decision |
|---|---|---|
| 44 | Yardstick | **Every Key Indicator is graded (coloured) against leadership's goal** (`AREA_TRANSFER_GOALS`). The companionship's own goal is printed as an uncoloured *compromiso* column. Replaces decision 11. |
| 45 | Ranking | **Units are ranked by a goal-free productivity index**: output per active companionship-week relative to the mission (100 = mission), weighted toward the results nearest baptism. Reporting becomes its own list. Replaces decision 14. |
| 46 | Baptism goal | **The 527 annual goal (all ten zones) is the baptism target.** Leadership's transfer goals for baptisms may be shown but do not drive the colour. |
| 47 | Zone baptisms | **Zones and districts get a baptism figure from Tableau's person-level export** (`confirmation_date`, by roster area), labelled "registros de Tableau". The mission keeps the certified figure. Re-opens decision 42 below mission level only. |
| 48 | Forecasts | **All four are printed**: transfer finish, needed per week, annual landing, baptism pipeline. Mission and zone level. Always a range with a one-line method, never coloured as a verdict. |
| 49 | Length | **About 45 pages for a full transfer copy** (from 104): mission ~6, zone 2, district 1, area ½ with nightly inputs. Replaces decision 25's "no compression". |
| 50 | Weekly packet | **Same structure as the transfer packet**, every level. No short weekly variant. |
| 51 | Screen | **Both renderers change**: the Informes screen and the PDF. One model, two renderers (decision 30). |

**Details left for the plan to propose (not decided):**
- **Index weights and members.** Which Key Indicators go in, and with what
  weights. The audit used sacrament, baptismal date and RC at church,
  unweighted, and left form baptisms out as too few.
- **How a zone's baptisms are graded under decision 46.** 527 is a
  mission-wide figure. Propose: a zone's share of 527 in proportion to its
  share of finding volume or of active areas. Otherwise show the zone's
  baptisms against the mission's per-companionship rate (the index) with
  no goal colour.
- **Small-count rule (H5):** where the threshold sits (~20 events) and the
  Poisson band.
- **Pipeline model:** conversion conditioned on days since the date was set,
  refit from Tableau detail, and its horizon (6 weeks).

## §8 — Proposed sequence (now unblocked by §7.1; not started)

- **Phase 0 — defects, no decisions needed:** C3 sentence; H2 labels and rate
  change; H1 per-unit flag (or none); M4 jargon; H4 one goal figure plus actual
  per area-week; H5 small-number rule. *Cheap, and each is a correctness fix.*
- **Phase 1 — yardstick and ranking** (Q1, Q2, Q3): leadership-goal grading,
  productivity index, separate reporting list. Touches `model._mean_attainment`,
  `_ladder`, `grading.grade_ki`, both renderers.
- **Phase 2 — the forward view** (Q4, Q5): transfer finish and required rate;
  annual landing range with year-over-year; the pipeline forecast from Tableau
  detail; zone-level baptisms.
- **Phase 3 — the president's front section and the diet:** *El tablero*,
  *Dónde enfocar*, *Palancas*; 12-week strips everywhere; area half-pages with
  nightly inputs; a short weekly packet.

Each phase is verifiable against the live packet the same way this audit
was: generate, rasterise, read.
