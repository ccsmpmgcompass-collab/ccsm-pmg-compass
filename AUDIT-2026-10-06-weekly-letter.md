# AUDIT — The weekly letter (Entrenamiento Semanal), 2026-10-06

**Question (Zackary):** missionaries aren't eager to open the weekly email. Why
not, and what would make it something they look forward to and use: simpler,
easier to compare with earlier weeks, more useful? Should it be different for
companionships, DLs, ZLs/STLs and APs? Should the KI PDFs or the council packet
be attached?

**What was looked at:**
- All 45 letters for the week ending 4 Oct, rendered by the shipping code
  (`tools/email_preview/render.js`, against the 5 Oct sheet dump). Each was
  measured at phone width (375 px).
- `AGENT_RUN_LOG` and `FEEDBACK_HISTORY` on the live sheet.
- `WEEKLY_FORM_RAW` timestamps from `tools/dump.json` (6 Oct).
- The code: `CCSM_Agent1C.gs` (the letter), `CCSM_Setup.gs:207` (the schedule),
  and `CCSM_Agent1A.gs:153` (where the KIs are read).

The coaching paragraphs show as `[VISTA PREVIA]` in the preview because the
service account can't read the message spreadsheet. The live letters do carry
the real text; `FEEDBACK_HISTORY` proves it. Nothing below depends on that text.

---

## 1. Why they don't look forward to it

### F1. It often says they didn't report when they did

The letter is built Monday at 21:30 (`CCSM_Setup.gs:211`). It reads the Key
Indicators from `WEEKLY_KI` (`CCSM_Agent1A.gs:153`), and `runAgent5A` refreshes
that tab only once a day, at 12:00. So any weekly form that arrives after Monday
noon is missing from the letter.

Distinct sectors per week, out of 45:

| Week ending | Reported at all | In the letter (by Mon 12:00) | By Mon 21:30 | By Tue 12:00 |
|---|---|---|---|---|
| 6 sep  | 29 | 20 | 21 | 28 |
| 13 sep | 36 | 27 | 30 | 33 |
| 20 sep | 33 | 27 | 27 | 31 |
| 27 sep | 35 | 29 | 30 | 34 |
| 4 oct  | 33 | 24 | 28 | 33 |

Every week, between **16 and 25 of the 45 letters** open on an empty box: *"No
recibimos su informe semanal de indicadores clave"*. That is the letter's most
important section, and it sits first. For **4 to 9 of those sectors** the
message is simply wrong: they had already sent the form, and the letter went
out before it was read. A missionary who did their part and is told they didn't
learns that the letter isn't about them.

Leaders get the same problem one level up. The rendered San Pedro ZL letter
grades the zone **"3 / 6 metas alcanzadas"** from **"1 / 11 áreas que
informaron"**. A zone KI block built from one area is noise, and leaders learn
to skip it.

### F2. It doesn't arrive reliably

`AGENT_RUN_LOG`, Mondays since 3 Aug:
- **Not sent:** 3 Aug and 10 Aug (property quota), 17 Aug (Agent1C never ran),
  and **28 Sep** (Agent1B ran, Agent1C never did).
- **Late:** the 23 Aug letter went out on Wednesday the 26th.
- **On time:** 31 Aug, 7 Sep, 14 Sep, 21 Sep and 5 Oct.

A habit needs a ritual: the same moment every week, every week. The 28 Sep miss
is already flagged by the missed-run check (`ec114d2`,
`app/analytics/agent_runs.py:49`). But nothing tells the missionaries, and
nothing resends the letter.

### F3. The subject line is the same every week

`a1c_buildSubject` (`CCSM_Agent1C.gs:671`) sends the same subject to all 45
recipients:

> PMG Compass — Entrenamiento Semanal | 4 de octubre

It carries no sector name, no number and no news. The inbox preview line
repeats it ("PMG Compass — Entrenamiento Semanal / Semana que termina el…").
Nothing in the inbox hints that this week differs from last week, and that hint
is the main reason anyone opens an email.

### F4. The coaching is the same every week

The "Área de Crecimiento" is the metric furthest below its goal. In
`FEEDBACK_HISTORY`, **32 of the 50 growth messages on record are Calendarios
Bautismales**. Those 32 rotate between only two texts, `MSG-CG-BAPCALENDAR-01`
and `-03`, 16 times each. Villa Obispo 1 got `-03` on 14 Sep and `-01` on
21 Sep. So most companionships get the same advice each week, alternating
between two paragraphs. The calendar goal is 1 a week, so most weeks it sits at
0 and keeps winning "furthest below goal". Once they've read the paragraph
twice, there's nothing new for them in that section.

### F5. The numbers that matter are buried among the ones that don't

The mission works on the **seven KIs**
(`metric_catalog.key_indicator_metrics()`). The companionship letter shows them
once, as this week against the goal, with **no last week and no trend**. Then it
spends most of its length on nightly metrics:
- **"Su semana — todos los indicadores":** 26 rows × 6 columns (Esta Sem /
  Meta / % Meta / Sem Pasada / Δ, plus "próx.").
- **An 8-week chart for one nightly metric**, the growth metric. That is usually
  calendarios, so the same chart every week.
- **"Su propio progreso":** the same metric again as four bars.
- **A 5-step funnel**, then a consistency strip.
- **A glossary**, which a letter only needs when it uses words its reader
  doesn't know: "Prom. del Cambio", "pp", "Tasa de Lecciones = Lecciones con
  Amigos ÷ Intentos de Contacto".

Zackary's question was how they compare with earlier weeks. The letter answers
that well for contacts and text messages, and not at all for the seven numbers
the mission actually goals.

### F6. Leaders get analysis, not a to-do list

Measured length at 375 px, in phone screens:

| Letter | Screens |
|---|---|
| Companionship | 2.3–3.5 |
| DL | 4.8–6.0 |
| ZL / STL | 7.0–9.1 |

The ZL section has seven blocks:
1. Zone KIs
2. "El Rumbo": 12 indicators as per-day averages with pp deltas
3. "Las Metas y el Esfuerzo"
4. A seven-tile KPI strip
5. A 5-column area table
6. "Cómo Ayudar a Cada Área": four rates per area against the zone median,
   e.g. "240% sobre la zona"
7. Two compliance tables

It's all correct, but it's an analyst's view. A DL on Monday night needs
something shorter:
- who to call
- who to go on exchanges with
- who to congratulate
- whether the district beat last week

Today those answers have to be dug out of several tables.

### F7. Nothing to celebrate and no shared story

By design, a companionship letter contains only that companionship's numbers.
That rule is inherited from the Provo coaching letter: "no area-vs-area/mission
averages". So no one learns anything about the mission:
- who was baptized
- which district hit all seven
- the mission's progress toward 527

People open a letter for **news and recognition** as much as for their own
grade. The letter has neither.

### F8. Nothing in it is a commitment for next week

The goals they set for the coming week (the `ki_*_meta` from their own form)
appear nowhere as goals. The nightly "próx." targets sit in small grey text
inside table cells. The letter ends by looking back. Nothing in it says
"this is what you said you'd do this week; here's one way to do it".

---

## 2. What would make them want to open it

Four rules, in priority order:
1. **Their real week.** Never wrong about whether they reported.
2. **One glance:** the seven KIs against goal, with the last few weeks beside
   them.
3. **One action** for the coming week, tied to their own goal.
4. **One piece of good news** from beyond their area.

Everything else goes behind a link or out of the letter.

### R1. Fix the data first (prerequisite; nothing else matters without it)

- **Read the KIs from `WEEKLY_FORM_RAW` at send time.** `ki_from_raw` in
  `tools/build_ki_ranking.py` already ports `a5a_writeWeeklyKI` and matched all
  244 rows of `WEEKLY_KI`. Agent1A can call Agent5A's writer, or run
  `runAgent5A()` itself, just before it reads. Then every form submitted before
  the letter is built is in the letter.
- **Make the deadline public, and make the letter the reward for meeting it.**
  The Sunday reminder (`runAgentReminder`) should say: "Envíen el informe
  semanal antes del lunes a las 20:00 para ver sus resultados en el correo de
  esta semana."
- **If a sector still hasn't reported, say it kindly and briefly.** One line,
  plus the link to the form. Never an empty box at the top.
- **Send it at the same time every week.** If the chain fails, resend
  automatically and add one line to the missed-run check's notice.

### R2. Companionship letter: 1 to 1.5 phone screens

A **subject line that carries news**, different every week. For example:
- *"Bosque Mar 2 · 4 de 7 metas · ▲ Amigos en la Iglesia: 3"*
- or *"…· ¡Nueva mejor marca: 3 amigos en la Reunión Sacramental!"*

Then, in order:
1. **The seven KIs as a small heat-map row**, the same visual language as the
   KI PDFs Zackary already approved. The big number is the result, with "de
   <meta>" beside it. **Behind each KI, the last 4 weeks as four small cells.**
   This is the "easy to compare with earlier weeks" answer: one row, at a
   glance, no table.
2. **One self-comparison highlight**, chosen automatically. Never against
   another area:
   - a new personal best ("su mejor semana en Lecciones con Miembros desde que
     llegaron al área")
   - a streak ("3 semanas seguidas con amigos en la Iglesia")
   - a recovery ("subieron de 0 a 2")
3. **"Su enfoque esta semana":** the weakest *KI* (not a nightly metric), the
   one nightly habit that feeds it, and the goal they set for it.
   `a1c_weakestKiChain_` and `a1c_feedsFrom_` already compute this for leaders.
   Then one message-bank paragraph with its PMG reference. Fix the repetition
   from F4 by choosing among the KIs, and by never using the same topic two
   weeks running (`FEEDBACK_HISTORY.Last_Growth_Metric` already records it).
4. **"Sus metas para esta semana":** the seven goals they set on their own
   form, shown as a commitment.
5. ~~**"En la misión":** two or three lines of mission good news.~~
   **Dropped from every letter (Zackary, 2026-10-06).** No letter carries a
   mission news section. The APs' own mission figures are their letter's
   content, not this section.
6. **The nightly detail goes.** The 26-row table, the funnel, the 8-week chart
   of one nightly metric and the glossary all leave the letter. They become one
   button to the dashboard if companionships have access (Q3), or a single
   collapsed line ("Ver todos los indicadores nocturnos") if not.

### R3. DL letter: their own letter (R2), plus one district section of about 1.5 screens

1. **A district KI grid:** areas as rows, the seven KIs as columns, as a heat
   map, plus the district total with last week beside it. This is one district's
   slice of the KI PDF, drawn inline.
2. **"Esta semana":** three short lists, generated from data the letter already
   computes:
   - **Llamar a:** didn't report, or reported fewer than 4 nights.
   - **Felicitar a:** met 6 or 7 goals, or set a personal best.
   - **Intercambio sugerido:** the area whose funnel breaks hardest. Today's
     capsule diagnosis, e.g. "enseña pero no invita", becomes the reason.
3. "El Rumbo", the per-day averages, the zone-median percentages and the
   compliance history tables all move to the dashboard.

### R4. ZL/STL letter: their own letter, plus a zone section of about 2 screens, plus an attachment

1. A zone KI grid by **district** (not by area), with this week against last
   week.
2. The same "Llamar / Felicitar / Intercambio" lists, one level up: which
   districts and DLs need what.
3. **Attachment: their zone's KI PDF** (`Indicadores_clave_<Zona>.pdf`, 3
   pages). The area-by-area detail lives in the PDF, so the email body stays
   short. This is the auto-send already queued.

### R5. AP letter: mission section plus attachments

- A zone-by-zone grid (four zones × seven KIs, this week against last week) and
  the mission totals against goal.
- Attach the mission KI PDF and all four zone PDFs, as already queued.
- The APs already get `runAgentMissionReport` 30 minutes later, so they receive
  two weekly emails with overlapping content. Merge the two: the mission report
  becomes the AP section of this letter, or the AP section shrinks to a pointer
  to it.

### R6. The attachments question

| Attachment | To whom | Why |
|---|---|---|
| Zone KI PDF (3 pp) | ZLs/STLs of that zone | They use it to plan calls and exchanges. Short, already designed, already approved. |
| Mission + all zone KI PDFs | APs | Same, mission-wide. Already queued. |
| Zone KI PDF | DLs? | Possibly. See Q4. |
| Any PDF | Companionships | **No.** Attachments on a phone are friction, and a ranking PDF breaks the self-comparison rule. Their row belongs inline. |
| **The council packet (104 pp)** | **Nobody, weekly** | It's built for the leadership council, on a chosen period. Nobody opens 104 pages on a phone on Monday night. Attaching it every week would teach leaders to ignore attachments altogether, including the 3-page zone PDF that matters. Keep it on the Informes page for council. |

---

## 3. Questions for Zackary (they change the build)

**Q1. When should it arrive?**
- Is Monday P-day, and when do companionships do weekly planning?
- Options:
  - (a) Keep Monday 21:30 and read the raw forms (R1). This gains 1–4 sectors
    a week.
  - (b) Move to Tuesday 07:00 with a Monday 22:00 deadline. This gains 4–9
    sectors a week and lands before the day starts.
- Recommendation: **(b)**, if weekly planning isn't Monday night.

**Q2. May a companionship see anyone else's results?**
- Today the rule is "only yourself" (inherited from the Provo letter).
- Options:
  - (a) Keep it.
  - (b) Allow positive-only mentions: areas that hit 7/7, baptisms by area.
  - (c) Show their place in the district.
- Recommendation: **(b)**. Recognition with no losers named.

**Q3. Do companionships have access to the dashboard?**
- If they do, the nightly detail becomes a link.
- If not, it stays as one short collapsed line.

**Q4. Should DLs get their zone's KI PDF?**
- It ranks their district's areas against the rest of the zone.

**Q5. Should the mission report and the AP section merge into one weekly email?**

---

## 4. Proposed sequence (for a PLAN file once approved)

1. **R1: data timing and reliability.** Small, and the most visible fix: the
   empty KI box disappears.
2. **R2: the new companionship letter.** The subject, the KI row with four
   weeks, the highlight, the focus, the goals and the mission news; nightly
   detail out. Preview with `render.js`, and measure it at 375 px.
3. **R3 and R4: leader sections rebuilt as grids plus "Esta semana" lists.**
4. **R4 and R5 attachments:** the queued KI-PDF auto-send.
   - The PDFs are built by Python; Apps Script sends the email.
   - Bridging the two needs a GitHub job that writes to Drive, which Agent1C
     then attaches.
   - The job must run after the deadline chosen in Q1.
5. Merge the AP section with the mission report (if Q5 is yes).

Each step is previewable before anything is sent: `node
tools/email_preview/render.js` renders every recipient's letter from the real
code.
