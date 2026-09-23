# PMG Compass — Council Packet Clarity Plan

**Written 2026-09-23**, after the Informes rebuild shipped (phases R, P, T, V —
`PLAN-2026-09-21-informes.md`, closed). Zackary: *"we will go through the whole
thing and look for things to improve to make it more clear for someone looking
through it on the first pass through."*

The audit is a doc, not a repo file this time:

https://claude.ai/code/artifact/0683222a-4609-4b12-a4f2-c9e4d28dd9d3

Twelve findings (A1–A4 mislead, B5–B8 cannot be decoded unaided, C9–C12
placement), each with what a first-pass reader concludes and what is true. The
doc's own "Answered" section records the five decisions below; this file is the
build.

Convention as before: one commit per step, named with the step id, every step
verified before its commit, the suite run against baseline before every push,
the STATUS section appended after every step. A push touching `app/` needs a
Reboot of the deployed app (`dashboard/DEPLOYING.md`).

---

## §1 — Decisions (Zackary, 2026-09-23)

Recorded here so no step below re-opens them.

| # | Decision | Consequence |
|---|---|---|
| 36 | **The first-pass reader is BOTH** the president meeting the packet cold and a leader handed five loose pages. | All twelve findings, Rounds 1–3 in order. Nothing dropped for being irrelevant to one of the two. |
| 37 | **Baptisms are not eligible for "lo más fuerte" or "lo que hay que mover."** | Those two sentences only ever name an indicator the packet fully trusts. Baptisms keep their tile, their Key Indicator row and their own page — just not the opening sentence of a unit. |
| 38 | **A change with no base is not printed.** The cell reads `—` and the column head carries the reason: `CAMBIO — sin base este período`. | Supersedes the current behaviour of printing the figure and disowning it in a note four lines below. Decision 6 (a partial comparison is SHOWN with its coverage) still holds for every comparison that HAS a base; this covers the case where it does not. |
| 39 | **The cover stays a cover.** No figures on page 1. | Its lower 44% is empty by decision, not by neglect. Do not "fill" it in a future density pass. |
| 40 | **A third front-matter page**, "Cómo leer este paquete". | The run sheet keeps its NOTAS column. 106 → 107 pages before Round 3's savings. |
| 41 | **The baptism block follows the selected period.** | New requirement, §4 Round 0. See §2 for why it is not simply a filter. |

### 1.1 — Zackary's own words on decision 41

> "Make sure as well that the baptism figure is as up to date as the option
> chosen before creating the pdf. For example if it's for transfer up to date,
> put all of them, if it's for the month, just include the baptisms up to the
> close of the month."

---

## §2 — The one hard problem: a period-scoped baptism figure

**The baptism block ignores the period pills entirely today.** Whatever period
is selected, it prints the calendar YEAR: 319 certified through August, the 527
annual goal, the pace mark, the projection to 478, and a month-by-month table —
plus a note that 24 more are uncertified in the open month.

Decision 41 asks it to follow the period. The obstacle is the source.

- **`TABLEAU_BAPTISMS` is certified and MONTHLY.** It can answer "Mes
  calendario" and "Año" exactly, because those align to whole months.
- **It cannot answer "Este traslado"** (2026-6 is 7 Sep – 18 Oct), "Semana
  pasada" or "Últimas 6 semanas". They start and end mid-month and there is no
  certified figure at day resolution.
- **`TABLEAU_DETAIL` carries dated baptisms per person** — the finding funnel
  already reads them (`analytics/finding_funnel.py`). That is a day-resolution
  source, but it is the *detail* figure, not the *certified* one.

**Decision 21 forbids quietly swapping one for the other, and forbids summing
them.** So a transfer-scoped baptism figure is only honest if it is labelled a
different source from the certified year-to-date printed beside it.

**Step R0 below measures whether `TABLEAU_DETAIL` can carry it at all before
anything is designed on top of it.** Do not skip to the rendering.

One thing already known and not to be re-derived: the funnel reads baptisms as
a **cohort** — the people FOUND in the window who have since been baptised,
which over eleven days is 0 because the p75 lag from found to baptism is 133
days. **That is a different question** from "how many baptisms HAPPENED in this
window", which is what decision 41 wants. R0 must query the second, not reuse
the first.

---

## §3 — What each round is for

| Round | Findings | What a reader gains | Cost |
|---|---|---|---|
| 0 | decision 41 | The baptism figure answers the period the packet is about. | Unknown until R0 measures the source |
| 1 | A1 A2 A3 A4 | Stops four wrong conclusions. | A few hours |
| 2 | B5 B7 B8 | The page explains itself without page 106. | Half a day |
| 3 | C9 C11 | The rules arrive before the numbers; the boilerplate stops drowning the specifics. | A day. Saves 2–3 pages, spends 1 |
| — | B6 C10 C12 | Left alone on purpose — see §5. | — |

---

## §4 — Build steps

### Round 0 — the baptism figure follows the period

**R0.1 — measure the source.** Against the live export: can `TABLEAU_DETAIL`
answer "baptisms whose baptism date falls in [start, end]" for each of the six
periods? How many rows carry a usable baptism date, over what window, and how
does the count for August compare with `TABLEAU_BAPTISMS`' certified 36? A
detail count that disagrees with the certified one by a wide margin is a
finding for Zackary, not a number to print. **Write the answer into STATUS
before writing any code.**

**R0.2 — the model.** `ReportModel.baptisms` gains the period's own window: the
certified figure where the period aligns to whole months, the detail figure
where it does not, each carrying which source it came from and the window it
covers. Never both summed (decision 21, decision 34).

**R0.3 — both renderers.** The baptism page and the screen's block print the
period's figure as the headline, with the year-to-date and the annual goal kept
as context below it rather than as the headline. The source label is not
optional.

*Acceptance:* switching the period pill changes the baptism headline, and the
page says which source answered it and over what dates.

### Round 1 — the four that mislead

**R1.1 (A1)** — `_best_and_worst` excludes `ki_baptized_confirmed_real` from
both sentences (decision 37). The tile, the row and the baptism page are
unchanged.

**R1.2 (A2)** — when `_weekly_comparable` is false, or the comparison coverage
is `thin`, the CAMBIO cell prints `—` and the column head reads
`CAMBIO — sin base este período` (decision 38). The existing "sin dirección"
note under the table goes; the head says it now.

**R1.3 (A3)** — `GRADED_NOTE`'s last sentence currently reads *"Nada aquí
compara un área, distrito o zona con otra"*, and since Phase V it sits directly
under a section that does exactly that. Reword: *"Cada porcentaje es esta
unidad contra su propia meta. La sección de arriba es la única que la compara
con otra."*

**R1.4 (A4)** — `nightly_page`'s table takes its own column heads:
`REAL (período)` and `META (área/semana)`. `metric_table` already accepts
`headers`; no new primitive.

### Round 2 — the page explains itself

**R2.1 (B5)** — the leadership goal under a metric name rounds and says what it
is: `meta del traslado · 2 de 6 semanas: 679`, not `meta de traslado 679,3`.

**R2.2 (B7)** — `CONTRA LA META` becomes `CONTRA SU PROPIA META`; `CAMBIO`
becomes `CAMBIO vs <comparison label>` where there is a base (and R1.2's head
where there is not).

**R2.3 (B8)** — the "Áreas que informaron, de 45" line moves out of the grey
note into the week table's own footer row at body weight. It is the reporting-
rate trap the whole plan rests on and it is currently the least visible thing
on the sheet.

### Round 3 — where things live

**R3.1 (C9)** — a third front-matter page, "Cómo leer este paquete"
(decision 40). Six rules, generated not hardcoded: what each percentage is
measured against, which areas filed nothing this period, why the nightly table
is not graded, the two baptism figures, what the finding section covers, and
where the full data note is. The page-106 data note stays as the reference.

**R3.2 (C11)** — each repeated explanation prints **once per unit** rather than
once per section, and the grading bands move to R3.1's page. Measured: the
same three paragraphs appear in every one of the 18 unit sections.

*Acceptance:* the packet's page count is measured after R3 and recorded. R3.1
spends a page; R3.2 should save two or three.

### Round 4 — verification

**V.1** the suite against baseline (**11 failed / 1664 passed** after the
Informes project; compare FAILURES, never the passed count).
**V.2** the screen at 1400px and 375px, measured with `javascript_tool`.
**V.3** the packet rasterised and READ — nine pages minimum, the same nine the
audit read, so the before and after are comparable.
**V.4** white space re-measured against Phase V's **10,3%** and **106 pages**.

---

## §5 — What is deliberately not being done

- **B6 — the colourless nightly table.** Twenty-two rows, all the same blue, no
  verdict, because decision 31 puts the colour in the movement and there is no
  movement to measure yet. It fixes itself as DAILY_LOG accumulates. Forcing a
  verdict now means grading against goals set at roughly twice current
  performance, which is the exact thing decision 31 exists to prevent.
- **C10 — the cover.** Decision 39. Its lower half stays empty.
- **C12 — sparklines left of their numbers.** A real cost, a small one, and
  moving the column is the most disruptive change on the list for the least
  gain.

---

## §6 — Still open from the Informes project

1. **The weekly form reported ONE baptism this transfer against 19 certified in
   September** (24 by 2026-09-23). The packet prints both under their own names
   and never sums them, and says so out loud — but the gap is a real reporting
   problem and it belongs with the goals workstream, not here. Round 0 will
   make it more visible, not less.
2. **`AREA_TRANSFER_GOALS` for 2026-7 must be set before 2026-10-19** or the
   next packet prints "sin meta" for the leadership mark (decision 23). Dated,
   operational, only Zackary can do it, on the Metas page.
3. **The goals workstream** (`PLAN-2026-09-21-informes.md` §6) is still
   deferred: the nightly goals are stretch targets at ~2× current performance,
   and nothing recalibrates the seven Key Indicators.

---

## §7 — How to resume

1. Read §1 first (decisions 36–41, **never re-open them**), then §2, then §4's
   entry for the round you are on.
2. Build one step at a time, one commit each, named with the step id.
3. Verify in the running app at **1400px AND 375px** (preview tool,
   `.claude/launch.json` name `ccsm-dashboard`). **Restart the preview server
   after every edit** — Streamlit's watcher does not pick up changes under
   `views/` or `app/`.
4. Verifying a printed page is `pypdfium2`: install it, rasterize to PNG,
   `Read` the image, **uninstall it afterwards** — it is not in requirements.
   A `ReportData` pickles (7,8 MB), which is how a layout change is measured in
   30 seconds instead of 90.
5. Run the suite against baseline — **11 failed, 1664 passed**. Compare
   FAILURES, and **never edit the tree while a suite is running**.
6. Append to STATUS and commit it with the step.
7. Push at the end of the round and **tell him to Reboot**.

---

## STATUS

### 2026-09-23 — the plan is written, nothing is built

The audit is done and answered; no step below R0.1 has been started. The
packet as it stands is the one Phase V shipped: **106 pages, 10,3% blank at
the foot of the average page, 53 double-sided sheets per copy**, last built
from the live sheet at 18:00 on 2026-09-23.

Two things landed today that are not part of this plan and are already pushed
(`961c0c2`):

- **`AGENT_CONFIG.MISSION_NAME` is Spanish** — "Chile Concepción South
  Mission" → **"Misión Chile Concepción Sur"**, row 2, written after a dry run
  that asserted exactly one matching key row. The seed row in `CcsmData.gs`
  changed with it so a re-run of setup cannot put the English name back. It
  also fixes the name in the app's page headers and in every reminder the
  Apps Script agents email a companionship.
- **106 pages stays.** Decision 25 is not re-opened; decision 39 now says the
  cover's white space is deliberate too.
