# AUDIT 2026-10-12 — The council packet, read as a professional operating review

**Asked (Zackary, 2026-10-12):** re-audit the live council packet with fresh
eyes. Don't use the old rubric and don't look at earlier scores. Read it the way
a professional would. Is the information useful? Does it widen the view of the
people who receive it? Does it show where we are going, or only what we are
doing and have done? How useful would it be at Fortune 500 scale? What would
you change?

**Status: AUDIT DONE, Q1–Q5 ANSWERED (§7). P-M approved and P-S declined (2026-10-13). The build is `PLAN-2026-10-13-monthly-council-packet.md`.** Several recommendations would reverse
earlier decisions, chiefly 44 (grading against reported weeks only) and 50
(the weekly packet keeps the full structure). Each recommendation names the
decision it touches.

---

## §0 — What was read

- **The packet:** the live *Este traslado* packet (2026-6, 5 of 6 weeks
  complete), built today from the live sheet with `app.reports.packet.build()`.
  It came out at **48 pages** and took 40 s.
- **How it was read:** every page as text, with pages 2, 4, 6, 11 and 32 also
  checked as images.
- **Where the figures come from:** every figure below is from that PDF, apart
  from simple arithmetic on its own numbers.

---

## §1 — The verdict in one paragraph

**This packet is a very good analyst's workbook. It is not yet an operating
review.** On analytical honesty it is above what most Fortune 500 regional
reviews contain:

- cohort-based funnels
- forecasts tested against past years
- each unit's share of the gap, ranked largest first
- data completeness stated on every page
- "how much would fixing this leak be worth" sizing

As a management instrument it falls short. It describes and diagnoses very
well, but it does not:

- **decide**: no decisions requested, no owners, no commitments;
- **remember**: nothing carries over from the last council, so you cannot tell
  whether what you tried worked;
- **tell a story**: the most important strategic fact in the data is spread
  across pages 6 and 9 and never connected.

Most of the paper looks backward. The forward-looking parts are honest, but
they are projections of the status quo, not a plan.

---

## §2 — Does it show where we are going?

**Partly. It shows where we land if nothing changes. It does not show where we
are trying to go, or what it would take to get there.**

| Forward-looking element | Where | Quality |
|---|---|---|
| Year landing 446–468 of 527, tested against 2024 and 2025 | p2, p6 | Excellent: a range with its method |
| Open baptismal dates → 45–63 baptisms in 6 weeks | p2, p6–7 | Excellent: cohort-based |
| Transfer finish ("Termina en") and needed per week ("Falta") | tablero columns | **Arrives too late** (see F3) |
| What each zone's biggest leak is worth | p8, zone pages | Very good |
| Year landing per zone vs its share of 527 | zone page, one sentence | Good, but buried in text |

Roughly **4 of 48 pages** look forward. The other ~44 report what happened.

What a professional operating review would add:

- **a plan path**: where each zone should be by month to reach its share of
  527, and where it is against that path;
- **scenarios**: "if reporting rose to 95%" or "if Angol converted dates like
  the mission";
- **the gap-closing bets** leadership is making, and next time, whether they
  worked.

---

## §3 — Findings

### F1 — The biggest strategic story is in the packet but never told

> **Corrected by Phase 0.1 (2026-10-13, PLAN-2026-10-13 STATUS):**
> - **Certified baptisms are UP, not down:** +18% for Jan–Sep and +15% for
>   Jun–Sep. The −15% below is a single five-week window.
> - **The 66% stale share is not new:** it was 73% a year ago.
> - **The real fall is in what a date is worth:** 39% of dates set in
>   Jun–Jul 2025 were baptized within 12 weeks, against 13% in 2026.

Tableau, same calendar weeks (7 Sep – 10 Oct), page 9:

| | 2024 | 2025 | 2026 | 2026 vs 2025 |
|---|---|---|---|---|
| People found | 2.597 | 2.875 | **5.267** | **+83%** |
| Baptismal dates set | 54 | 57 | **182** | **+219%** |
| First time at church | 267 | 226 | 229 | +1% |
| Baptized | 24 | 27 | **23** | **−15%** |

The open dates on page 6 point the same way:

- **811 of the 1.226 open dates (66%) are more than 90 days old.**
- Dates that old convert at about **1%** within six weeks.
- Of the 45–63 expected baptisms, only about **9** come from that stale 66%.

**In one sentence:** the mission has nearly doubled its finding and tripled
its date-setting, but baptisms have not moved, and two-thirds of its date
inventory is stale.

A management consultant would put this on page 1. The packet shows the numbers
on two separate pages and never draws the conclusion.

**There are two possible readings, and the packet should say which is true:**

1. **The work changed.** Dates are being set earlier or more loosely, so the
   quality of a date has fallen.
2. **The recording changed.** Tableau entry practice changed in 2026, so the
   comparison is not like for like.

Either answer is a strategic fact. The first is a coaching problem; the second
is a measurement problem.

### F2 — "Green" does not mean "on track"

On page 4, *Amigos en la Iglesia (Primera Semana)* is green at **104%**. The
same row says it needs **29 in the last week, 3,2× the current pace**, to make
the transfer goal. Page 2 says **0 of 6 indicators** will reach leadership's
goal for the whole transfer.

The cause is in the design:

- **The colour** is graded only on the weeks and areas that reported
  (decision 44).
- **The forecast** counts every area.
- With 75% reporting, every colour is generous.

A professional review uses **one status per line: forecast against the full
plan.** Two numbers on the same row that disagree make a reader trust neither.

*Reverses decision 44.*

### F3 — The forecast columns arrive when it is too late to act

At week 5 of 6, "Falta por semana" reads:

| Indicator | Needed per week | Multiple of current pace |
|---|---|---|
| Nuevas Personas | 993 | 4,9× |
| Lecciones con Miembros | 819 | 6,0× |
| Bautizados | 60 | 36× |

These are true but useless: nobody can act on "36× the pace" with one week
left. The same calculation is valuable in **weeks 1–3**, when it can still
change behaviour. By the end of a transfer, this space should show next
transfer's starting position instead.

### F4 — Reporting is the #1 operating problem, but it is treated as a caveat

- **56%** of everything the mission is short of comes from weeks nobody
  reported.
- Reporting is **75%** (168 of 225 weekly reports).
- The weekly count of areas reporting runs **26–37 of 45**.
- Three of the top four "where to focus" districts are there mainly because of
  **silence**, not weak work.

The packet says all of this honestly, but as caveats and footnotes. In a
Fortune 500 review, data completeness this low is itself a red KPI, with:

- a target (≥95%),
- a trend line,
- a named owner per zone,
- the non-reporters listed on page 1.

Fixing it is the cheapest gain available. It also makes every other number in
the packet trustworthy.

### F5 — It diagnoses but never asks for a decision, and has no memory

There is no section for:

- **decisions needed** from this council;
- **commitments**: who will do what, measured by which metric, by when;
- **follow-up**: what the last council decided, and whether the targeted
  number moved.

Each packet starts from zero. *"Una pregunta para cada zona"* (page 2) is the
best idea in the document and the closest it comes to driving action. But the
answer is never recorded, so the next packet cannot report on it.

This accountability loop is the single most important feature of a corporate
operating review.

### F6 — The 527 goal is unreachable on current trajectory, and nobody is asked to decide

The packet's own figures:

- The year lands at **446–468**.
- Reaching 527 needs **60 a month**.
- The best month on record is **50**.
- **Three of the four pilot zones** land well below their share:

| Zone | Year landing | Its share of 527 |
|---|---|---|
| Angol | 29–32 | 42 |
| Los Angeles Norte | 44–51 | 63 |
| Temuco Ñielol | 28–33 | 45 |
| San Pedro | 72–83 | 78 (on track) |

A professional pack states this plainly and offers options: recast the goal,
or name the specific bets that close roughly 70 baptisms. The packet reports
the facts precisely and then stays neutral.

### F7 — Too much method, too little message

- The finished packet uses "sin color" **42 times** and names Tableau **75
  times**.
- Nearly every block ends with a paragraph explaining its method.
- Section titles are labels ("EL TABLERO", "DÓNDE ENFOCAR", "PALANCAS"), not
  conclusions.

Corporate packs use **action titles**: the heading *is* the finding. For
example: *"Angol bautiza 6 de cada 100 fechas; la misión, 16"*. Method belongs
in one appendix, which this packet already has (the data note, page 47).

The disclaimers read as if written to stop someone misreading the page. That
was right while the numbers were being trusted for the first time. Now it
buries the message. The readers include 19–25-year-old zone and district
leaders.

### F8 — Two different yardsticks for the same areas

Areas are ranked by the **productivity index** everywhere in the packet. On
the area pages, though, the last line ranks them by the agents' **"Efectividad"**
score ("2º de 3 en su distrito, por efectividad"). Next to it sits a third
number, "Indicadores Clave 37,5".

A reader cannot tell which number decides. A professional pack has one
yardstick per level.

### F9 — It is heavy on paper and light on pictures

- **Paper:** 48 pages, or 80 double-sided sheets per print run, **every week**
  (decision 50).
- **Who uses what:** the council itself uses pages 1–18. Pages 19–46
  (districts and areas) are things to hand out, not things to discuss.
- **Pictures:** almost everything is a table.
  - The most important forward chart is the year's baptisms against the goal
    path with the forecast range. It is a table (page 6).
  - The summary page has no picture at all, and its bottom quarter is blank.

A Fortune 500 operating pack is about 10–15 pages plus an appendix, and its
first page carries one decisive chart.

### F10 — Smaller things

- **Tiny goals on area pages:** grades like **600%** (4 against a goal of 0,7)
  and **415%** (El Mirador, 9 against 2) carry no information. Below a small
  goal, show the count, not a percentage.
- **Two baptism figures in the top table:** the form's 8 sits in the mission
  tablero's top table next to the certified 23 on the next page. The text
  explains it, but it still confuses at a glance.
- **A non-reporting district ranks high:** El Mirador's district scores 147 on
  productivity while its own area reported nothing. It sits at #7 in "Dónde
  enfocar" only because of that silence.
- **No names for zone or district leaders:** area pages name the missionaries;
  zone and district pages do not name their leaders. Accountability needs a
  name.
- **Only four zones are covered in depth.** Six of the ten zones, about 57% of
  the mission's Tableau activity, appear only as rows. That is right for a
  pilot, but at scale the structure has to hold for ten.

---

## §4 — What it does better than most corporate packs (keep these)

1. **Backtested forecasts with ranges.** The year landing was tested on
   2024 and 2025 and stated as a range. Most companies print a single number.
2. **The mature-cohort funnel.** It follows people found 3–6 months ago, so
   conversion is measured fairly. That is real analytical discipline.
3. **Each unit's share of the gap, largest first, with silence split out.** It
   tells you where the gap is, not just that there is one.
4. **Lever sizing.** "Fixing this leak is worth 2–4 baptisms per transfer" is
   exactly the kind of number an executive needs to choose where to spend.
5. **"Una pregunta para cada zona."** It turns data into a conversation.
6. **Drill-down and distribution.** Summary → mission → zone → district →
   area, with a print guide that says who gets which pages.
7. **Honesty about data.** The data note and the reporting counts make every
   number defensible.

---

## §5 — Suggested changes, in order of value

### Tier 1 — change what the council *does*

**C1. Page 1 becomes "La historia de este traslado."**
- Three findings, each with an action title.
- One chart: the year's baptisms against the goal path, with the forecast
  range.
- A box: "Decisiones para este consejo."
- The current Resumen text moves under it.

**C2. Close the loop with council commitments.**
- A new sheet tab, `COUNCIL_COMMITMENTS`: who, what, which metric, by when.
- 3–5 commitments filled in after each council.
- The next packet opens with "Lo que nos comprometimos y qué pasó", each
  commitment with its metric before and after.
- *(This one is new functionality, not a re-layout.)*

**C3. One status colour: forecast against the full goal.**
- The colour shows whether the unit will make leadership's goal for the whole
  transfer, counting every area.
- Reporting gets its own headline KPI, with a target, a trend and an owner per
  zone.
- *Reverses decision 44.*

**C4. Tell the funnel-quality story (F1).**
- A mission block: same weeks year on year (found, dates, baptisms) placed
  next to the age of the open dates.
- Per zone: the share of its open dates older than 90 days, plus a "revisar o
  liberar" list for district leaders.
- *First needs Zackary's answer on whether the 2026 jump is real (Q2).*

### Tier 2 — make it look forward

**C5. A plan path per zone.**
- Each zone's share of 527 as a month-by-month path.
- Where the zone is against that path, and its forecast range.
- A chart on each zone page.

**C6. Scenarios on the summary page.** Two or three "what if" lines with
sizes, all built from numbers the packet already computes:
- reporting at 95%;
- every zone's biggest leak converting like the mission;
- stale dates cleared.

**C7. Put the forecast columns where they can still change behaviour.**
- Weeks 1–3: "Termina en / Falta" lead the tablero.
- Final weeks: the space turns into "cómo empieza el próximo traslado".

**C8. Ask the 527 question explicitly.**
- One line on the summary page: "Con la trayectoria actual, 527 no se alcanza:
  recalibrar o nombrar las apuestas."
- The decision itself is the President's.

### Tier 3 — form

**C9. Split the council packet from what gets distributed.**
- **Council packet:** about 15 pages (summary, mission, zones).
- **District and area pages:** sent digitally. The weekly letter and the KI
  PDFs already reach those people.
- *Re-opens decisions 49, 50 and 57.*

**C10. Action titles, and method moved to the appendix.**
- Each heading states its conclusion.
- Each block keeps one short source line.
- All method text moves to the data note.

**C11. One yardstick per level.**
- Drop the "por efectividad" rank from area pages, or explain how it relates
  to the productivity index.

**C12. Charts where a table hides the shape.**
- Year path against goal (C5).
- Funnel against the mission.
- Distribution of districts (the strip plot already exists).

**C13. Smaller fixes.**
- Counts instead of percentages below small goals.
- Leader names on zone and district pages.
- The form baptism figure out of the mission tablero's top table.

---

## §6 — Questions for Zackary

1. **Q1 — Rhythm and room:** who is actually at the council, and does it meet
   weekly, every transfer, or both? The answer decides how long the packet
   should be (C9).
2. **Q2 — Is the 2026 jump real?** Found people are up 83% and dates set up
   219% on 2025 for the same weeks. Is that a change in the work, or a change
   in how Tableau is filled in? C4 and the headline story both depend on it.
3. **Q3 — Decision 44:** are you willing to reverse it, so the colour means
   "forecast against the full goal" (C3)?
4. **Q4 — Commitments:** would the President or the APs fill in a
   commitments tab after each council (C2)? If nobody does, the loop is empty
   paper.
5. **Q5 — The 527 goal:** is it fixed, or can the packet recommend recasting
   it (C8)?

---

## §7 — Zackary's answers (2026-10-13)

| Q | Answer | What it changes |
|---|---|---|
| Q1 | **Who attends:** the ZLs, the STLs (hcaps), the APs and the President. **When:** once a month, in the first week of the month. | The packet becomes a **monthly** document, for an audience that discusses **zones**. District and area pages are handed out, not discussed (C9 holds). See §7.1, the new issue this answer raises. |
| Q2 | **Not sure;** his guess is "a mix of both" (a real change in the work and a change in how Tableau is filled in). | C4 must not state the 2026 jump as fact. It should show the measures that do not depend on how finding is recorded: the age of open dates, and conversion from date to baptism, set against the same months of 2025. It should name the jump with both readings. |
| Q3 | **Yes**, reverse decision 44. | C3 is approved: the colour means forecast against leadership's **full** goal. Reporting becomes its own headline KPI. |
| Q4 | **Probably not.** Nobody will fill in a commitments tab. | C2 is dropped as data entry. In its place: **the packet remembers itself.** "Desde el último consejo" automatically re-reads the previous packet's focus list and zone questions, and shows whether those numbers moved. |
| Q5 | **527 will not be changed.** | C8 becomes **"the gap and the bets."** It names the gap between the forecast and 527, and sums the levers and scenarios (C6) against that gap. It never suggests recasting the goal. |

### §7.1 — A new issue raised by Q1: the default period does not suit a monthly council

`DEFAULT_PERIOD = THIS_TRANSFER` (`dashboard/app/reports/periods.py:93`).
The transfer calendar (`TRANSFER_SCHEDULE`):

- 2026-7 runs from 19 Oct to 29 Nov.
- 2026-8 runs from 30 Nov to 10 Jan.

What *Este traslado* would contain at each council:

| Council (first week) | *Este traslado* covers | Complete weeks |
|---|---|---|
| early November | 2026-7, week 3 | 2 |
| early December | 2026-8, days 1–5 | **0** |

So a packet built on the default period at the December council would be
**empty**. *Mes calendario* is no better: in the first week of a month it
covers only days 1–7.

**Proposal P-M:**
- **A new period, "Mes pasado"**: the calendar month just closed, counting the
  complete weeks that end inside it.
- **This becomes the council packet's default.**
- **Goals:** leadership's transfer goals are prorated to those weeks, which the
  model already does for any period.
- **The forward part follows the year and the transfer now running:**
  - the year path against 527, month by month;
  - the transfer in progress;
  - the open dates.
- **Why it fits:** certified baptisms are already captured by closed month, so
  the monthly council and the year path against 527 line up exactly.

**Needs his word before it is built.**

### §7.2 — Another open item raised by Q1: the STLs are in the room

The packet has no view of sister companionships. Every cut is by zone,
district or area. The STLs would have to find their sisters' areas one by one
on pages 32–46.

**Proposal P-S:** one "Hermanas" page. It would list every sister
companionship across the four zones, with productivity, reporting, and the
biggest gap for each.

**Needs his word.**
