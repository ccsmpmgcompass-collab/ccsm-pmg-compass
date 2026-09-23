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
| 42 | **Every period prints the CERTIFIED figure — the nightly sync captures the windows that are not months.** (2026-09-23, after R0.1) | No detail-export baptism count is printed anywhere, labelled or not. The four periods that are not whole months get their certified figure from TABLEAU_BAPTISM_WINDOWS, which the nightly job fills; a period with no capture yet prints `—` and says why. Chosen over "detail, labelled" and over "both, in order". |

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

**R0.2 — the sync captures the period windows** (decision 42, which replaced
the detail-figure design this step first had). `tableau_finding_runner` asks
`periods.resolve` for last week, this transfer, last transfer and the last six
weeks, exports the Summary PDF for each, verifies its printed window, and
merges the figures into a NEW tab, `TABLEAU_BAPTISM_WINDOWS` — never into the
month-keyed TABLEAU_BAPTISMS, where a 10 Aug – 20 Sep window would be stored
as August. Its own try block: a window that will not export costs neither the
months nor the Detail pull.

**R0.3 — the model.** `ReportModel.baptisms` gains the period's own figure,
certified in every case: the month capture for "Mes calendario", the closed
months plus the open month's capture for "Año", and the window capture for the
other four. Looked up by DAYS — same first day, the latest last day not past
the period's — so a capture a night behind answers with its own shorter window
and says so; below the 25% floor, or with no capture at all, it is refused with
its reason. Never a detail count, never summed with one (decisions 21, 34, 42).

**R0.4 — both renderers.** The baptism page and the screen's block print the
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

### 2026-09-23 — R0.1: the source, measured

Against the live export (auto-sync, uploaded 2026-09-23 14:08 UTC, 99.897
people, found-dates 2024-01-01 → 2026-09-21) and TABLEAU_BAPTISMS. Read-only;
no code changed.

**The detail export CAN answer "baptisms that happened in [start, end]".** The
column is `confirmation_date` (the funnel's "Bautizados" stage). **890 rows
carry one, every one parses, none is later than the export's last found-date**,
span 2024-01-28 → 2026-09-20. 84% fall on a Sunday, 11% on a Saturday — it is
the confirmation, dated by the event, not by when it was typed in.

**It runs LOW against the certified figure, never high:**

| | detail | certified | gap |
|---|---|---|---|
| 2026-01 … 2026-08, month by month | 19 29 43 44 40 42 41 32 | 19 37 47 44 43 46 47 36 | 0 −8 −4 0 −3 −4 −6 −4 |
| 2026 Jan–Aug | **290** | **319** | **−29 (−9,1%)** |
| **September to date (1–23)** | **24** | **24** (capture 1–23 Sep, provisional) | **0** |
| 2025, month by month | — | — | −1 to −13 every month |

The gap is **zero in the open month** and opens up once a month closes. Why is
not provable from here (the certified figure is a PDF total, not people); the
direction is what matters — a detail figure is a **floor**, and the fresher the
window, the closer it sits to the certified one.

**The six periods, as built on 2026-09-23:**

| Period | Window | detail | certified available? |
|---|---|---|---|
| Semana pasada | 14–20 sep (7 d) | **5** | no — not whole months |
| Este traslado (2026-6) | 7–23 sep (17 d) | **12** | no |
| Traslado pasado (2026-5) | 27 jul – 6 sep (42 d) | **44** | no |
| Últimas 6 semanas | 10 ago – 20 sep (42 d) | **47** | no |
| Mes calendario | 1–23 sep (23 d) | 24 | **yes, exactly: 24** — the month-to-date capture ran for exactly 1–23 Sep |
| Año | 1 ene – 23 sep | 314 | **yes, exactly: 319 closed + 24 open = 343** — the same tab, no second source |

So **two of the six periods have a certified figure for exactly their own
days** (when the nightly capture ran today; a day behind, it covers one day
fewer and has to say so), and **four can only be answered by the detail
export**, which on the recent evidence reads 0–11% low.

**Something R0.1 found that the plan did not know.**
`tableau_finding_portal.download_summary_pdf(page, start, end)` already
exports the certified Summary for ANY window, not only whole months; the
runner just only ever asks it for months (`capture_windows`). The Sep 1–23
capture matching detail to the person says the Summary filters on the event
date, so a transfer window asked for directly would come back as Tableau's own
certified count for those days. That makes a third design possible: the
nightly sync ALSO captures the current transfer, the last transfer, the last
week and the last six weeks — one source for all six periods, and no detail
figure printed at all. Its cost: four more PDF exports a night on a run that
takes 2,5 minutes, a new window-keyed storage shape (TABLEAU_BAPTISMS is keyed
by month), and a fallback for any night the sync fails.

**This is Zackary's call before R0.2 is designed** — see the next entry.

### 2026-09-23 — decision 42, and R0.2: the sync captures the period windows

**Zackary chose "extend the nightly sync"** over "detail, labelled" and over
"both, in order". So the detail export is not a baptism source anywhere, and
§4 Round 0 is re-cut: R0.2 the sync, R0.3 the model, R0.4 the renderers.

**What R0.2 changed:**

- `tableau_finding_runner.period_windows(today, cycles)` — the four periods
  that are not months, resolved by `app.reports.periods.resolve`, the same
  function the packet calls. On 2026-09-23 they are 14–20 Sep, 7–23 Sep,
  27 Jul – 6 Sep and 10 Aug – 20 Sep.
- `pull_baptism_windows` exports each through the existing
  `portal.download_summary_pdf` and the existing `verify_window`, and runs in
  its own try between the month captures and the Detail pull.
- `tableau_upload.merge_window_rows` — the same days re-captured replace the
  old figure; a window that grew replaces its shorter self within one period
  (so "Este traslado" keeps one row, not one per night); a week that shares its
  first day with the transfer survives. Tab: **`TABLEAU_BAPTISM_WINDOWS`**
  (`period | start_date | end_date | baptisms | captured_on`), created by the
  first run that writes it.
- `transfer_helpers.rows_from_frame` — the schedule parser split out of
  `transfer_rows`, because the job reads TRANSFER_SCHEDULE through its own
  gspread client. One parser, so the job and the app cannot disagree about a
  transfer's days.
- `tests/test_baptism_windows.py`, 14 tests. The existing
  `test_the_runner_reaches_no_streamlit_when_it_starts_up` now walks
  `app.reports.periods` and `app.utils.transfer_helpers` too, and passes.

**Not yet proven live.** The four windows export through the same code path as
the month captures, which has run nightly since #17 — but a window crossing a
month boundary has never been asked of the Summary. The first run that writes
TABLEAU_BAPTISM_WINDOWS is the test, and until one does, every one of the four
periods prints its refusal instead of a figure.

### 2026-09-23 — R0.3: the model carries the period's own figure

- `tableau.PeriodBaptisms` + `tableau.period_baptisms(period, certified=,
  open_month=, windows=)`. Pure. **It takes no detail export at all** — a test
  asserts its signature, so decision 42 is structural rather than a habit.
- Lookup is by DAYS: a capture answers when it starts on the period's first
  day and ends on or before its last; the latest such capture wins. A capture a
  night behind answers with its own window and its shortfall ("16 de 17 días
  del período"); under the 25% floor, or with nothing captured, it is refused
  with its reason.
- **"Año" is the closed months plus the open month's capture** when that is
  the month right after them — both TABLEAU_BAPTISMS rows over adjoining days,
  so this is one source counted once, not the sum decision 21 forbids. It
  carries its `composition` so the page can say which part is still open. A
  missing month in the middle stops the year there, as `AB.cumulative` does.
- `Baptisms.period` holds it; `ReportData.baptism_windows` is read once in
  `load_data` from `queries.get_baptism_windows()`.
- `tests/test_report_period_baptisms.py`, 14 tests.

**Against the live sheet (2026-09-23):** Mes calendario **24** (1–23 sep),
Año **343** (319 closed + 24 September), and the other four refused — "la
sincronización nocturna todavía no ha capturado la cifra certificada de estos
días" — because TABLEAU_BAPTISM_WINDOWS does not exist until the sync's first
run with R0.2 in it.

### 2026-09-23 — R0.4: both renderers lead with the period

**The packet (M6).** Two heads where there was one:

1. **`Bautismos · <period>`** — `cifra certificada · fuente: Tableau`. A tile
   labelled by `periods.WITHIN_LABELS` ("En este traslado", not the head's
   own words repeated), and beside it either the year to date ("En lo que va
   de 2026 · 343 · hasta el 23 de sep") or, for "Año", the split into closed
   months (319) and the open month (24, "todavía sin cerrar"). Under it,
   `PeriodBaptisms.sentence`: the days the figure covers, the shortfall when
   the capture stops short, or — with no capture — "No hay cifra certificada
   … No se imprime otra en su lugar … (decisión 42)".
2. **`El año 2026 contra su meta`** — `meses cerrados · fuente: Tableau`. The
   old block unchanged: 319, 527, −32, 478, the bar, the month table. Its
   open-month note now says the month IS in the figure above and only kept
   out of the bar and the pace.

The data note's baptism sentences moved into `_baptism_sentences` and now
print **whether or not the finding section printed** — the baptism page does
not rest on the Detail export, so a refused finding section is no reason to
leave its source unexplained. They name the period's figure, and say which
tab each period reads from.

**The screen** mirrors it: two section labels, a card row per band, the same
`sentence` as caption. A refused period shows `—`, never 0 — and the year
block's three cards stopped printing 0 when a figure is missing, too.

**Verified.** Packet built from the live `ReportData` for three cases and
read at 150 dpi: "Este traslado" (refused — dash and reason), "Año" (343 =
319 + 24), and a SYNTHETIC one-night-behind capture for the transfer, used
only to see the layout of a present, clipped figure ("16 de 17 días del
período"). Page count unchanged: **106** for Este traslado. Screen driven at
1400px and 375px: both bands render, **zero sideways scroll** at 375.
Suite: **11 failed / 1698 passed** — the same 11 as baseline, +34 new tests.

**Round 0 is built.** What it cannot show until the sync runs: a real window
figure on the page. Every one of the four window periods prints its refusal
until TABLEAU_BAPTISM_WINDOWS exists.
