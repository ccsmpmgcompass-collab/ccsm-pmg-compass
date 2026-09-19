# Tableau auto-sync — plan

**Written 2026-09-19.** Supersedes the cadence and the acquisition mechanism of
`PLAN-2026-09-05-backlog.md` Step 6 ("Phase 3.4: automation"), which specified a
monthly Playwright pull. Everything else in Step 6 — reusing `cloud_job_wrapper`,
`CLOUD_JOB_STATUS` and `cloud_job_ui.py` unchanged, writing through
`save_dataframe(..., uploaded_by="auto:tableau")` — still holds.

Two tracks. **Track 1 needs nothing from anyone and is built first.** Track B is
the acquisition layer and is gated on Zackary putting credentials into GitHub.

---

## §0 — What the audit established

### 0.1 The monthly ceiling is ours, not Tableau's

Stated the other way round at first and corrected by Zackary. The evidence:

- The Summary PDF prints its own window — `tableau_summary_parser._RE_WINDOW`
  reads `Start Date … End Date` out of the file, and `MonthlySummary` already
  carries `start_date` and `end_date` as fields. **We then discard both** and
  key on `month`, derived from the start date (`tableau_summary_parser.py:150`).
- `get_baptisms_actual`'s docstring names its upstream source as
  `referral_system/baptisms_capture.py`, **"run daily"** (`queries.py:3474`).
  Daily capture rewriting the current month is the design this was ported from.
- `queries.get_tableau_daterange()` (`queries.py:3585`) already parses a
  `_range:START|END` marker described as one "the scraper stamps" into the
  metadata row. **Nothing in this repo writes it.**
- `merge_baptism_rows` already merges rather than replaces, treating a
  re-download of a month as "the corrected version of it"
  (`tableau_upload.py:134`).

So `get_baptisms_actual_for_range` returning `None` for a partial month
(`queries.py:3529`) is a consequence of monthly STORAGE, not a fact about the
source. Tableau will answer for any window.

### 0.2 Acquisition: REST API was better, and is blocked

The view is **Tableau Cloud**, not an internal server:

```
https://prod-useast-b.online.tableau.com/t/churchofjesuschrist/views/MissionFindingSummaryStephen/MissionFindingSummary
```

Site contentUrl `churchofjesuschrist`, workbook `MissionFindingSummaryStephen`,
view `MissionFindingSummary`. Tableau Cloud exposes a REST API whose
`/views/<id>/data`, `/pdf` and `/image` endpoints **all accept
`vf_<fieldname>=value` filters** — exactly the programmatic window control this
plan needs, with no browser at all.

**It is blocked.** Creating the required Personal Access Token returns
*"Su administrador de sitio ha deshabilitado la creación de PAT."* Tableau
disables PAT creation by default on sites activated June 2023 or later, so this
is plausibly an untouched default rather than a policy. A request to enable it
is out with Zackary; **if it is granted, Track B is replaced wholesale and
nothing else in this plan changes** — that is the point of isolating
acquisition.

Username/password REST sign-in is not a fallback: the site has **no MFA**, and
Tableau Cloud has required MFA for TableauID auth since 2022, which implies SAML
SSO — and SAML users cannot use the username/password `signin` endpoint.

### 0.3 The surface Track 1 touches

| Where | What it does today |
|---|---|
| `tableau_summary_parser.baptisms_rows` | emits `[zone, month, baptized]`; **raises** when two summaries for one month disagree |
| `tableau_upload.merge_baptism_rows` | merges by `(zone, month)`, new row wins |
| `queries.get_baptisms_actual` | one month, `MISSION` rows, `match.iloc[-1]` |
| `queries.get_mission_baptisms_by_month` | whole series for the annual chart |
| `queries.get_baptisms_actual_for_range` | `None` unless `full_month_range` |
| `finding_funnel.full_month_range` | start on the 1st, end on month's last day |
| `views/07_Embudo_de_Búsqueda.py:294-324` | parse → `baptisms_rows` → merge → save |
| `views/07_Embudo_de_Búsqueda.py:446,522` | the "Official Baptisms" KPI card |
| `views/01_Panel.py:832-870` | annual cumulative chart |
| `analytics/annual_baptisms.cumulative` | stops at the first missing month |

Tests already cover every pure piece: `test_tableau_summary_parser.py`,
`test_tableau_upload.py`, `test_baptisms_actual_for_range.py`,
`test_annual_baptisms.py`, `test_finding_funnel.py`.

---

## §1 — Track 1: window-aware baptism storage *(build now)*

**Why this first.** It needs no admin, no credentials and no automation, and it
pays off immediately on the MANUAL path: Zackary can hand-export a month-to-date
Summary PDF today and have it stored and displayed honestly instead of
overwriting the month as though it were finished. It is also exactly the code
the automated path needs later, so none of it is throwaway.

**The invariant that governs every step below:** a partial window must never be
silently readable as a complete one. Every existing guarantee about undercounting
is preserved; the new capability is opt-in at each call site.

### 1a — Schema, parser, and the merge guards

`TABLEAU_BAPTISMS` goes from `zone | month | baptisms` to
**`zone | month | baptisms | start_date | end_date`**.

- `month` stays the key and stays derived from the start date, so nothing that
  reads the tab today breaks.
- **`provisional` is DERIVED, never stored** — a row is provisional when
  `end_date` is earlier than the last day of `month`. One source of truth; a
  stored flag could disagree with its own dates.
- The 31 existing rows have no date columns. **Blank dates mean "assume the
  whole month"**, which is what those rows are.

`baptisms_rows` emits the two new columns. **Its same-month disagreement guard
is fixed, not removed:**

- identical window, different counts → **still raises**. Two files claiming the
  same thing and disagreeing is exactly as alarming as it ever was.
- different windows → **keep the later `end_date`**, which is the more complete
  capture. This is the case that fires every single day under a nightly re-pull
  (Sep 1–19 vs Sep 1–20) and today would abort the whole job.

`merge_baptism_rows` gains the same rule against what is already stored: for one
`(zone, month)`, **the later `end_date` wins, ties go to the incoming row.** This
stops a narrow re-upload (Sep 1–5) from clobbering a finished month — the
baptism-side equivalent of the `narrower` check `describe_replacement` already
performs for Detail.

### 1b — Readers

- **`get_baptisms_actual(month_start)` stays strict.** It returns a figure only
  when the stored row covers the whole month. Every existing caller keeps the
  guarantee it was written against; no caller silently starts receiving a
  partial.
- **New `get_baptisms_capture(month)`** returns the whole record — count, start,
  end, and whether it is provisional — for the call sites that want to show
  month-to-date deliberately.
- **`get_mission_baptisms_by_month()` returns complete months only**, so the
  annual chart's existing behaviour is untouched. The provisional tail is
  fetched separately and drawn separately.
- **`get_baptisms_actual_for_range(start, end)` gains one case:** when a single
  stored row's window matches the requested `[start, end]` exactly, return it.
  Otherwise the existing whole-month sum, otherwise `None`. This is what makes
  Embudo's Official Baptisms card answerable for a custom window.

### 1c — Embudo

The Official Baptisms card answers whenever 1b can answer, and its note names
which case it used: certified whole months, an exactly-matching capture, or the
dash. The upload success message reports the window it stored, not just a count
of months.

### 1d — Panel's annual chart

`cumulative()` keeps taking complete months and keeps stopping at the first gap
— that contract is load-bearing and is not touched. The provisional month is
drawn as **one additional open-marker point on a dashed segment**, and the
section's right-hand line changes from "certified through {month}" to name the
month-to-date window when one exists.

Without this, a mid-month capture plotted as an ordinary point makes September
read as a collapse every time the page is opened.

### 1e — Tests

Extend the five existing test modules. The cases that matter: a legacy
three-column row still reads; a wider window beats a narrower one in both merge
paths; an identical window with a different count still raises; a provisional
row is invisible to `get_baptisms_actual` and to the annual series; an exact
window match answers in `get_baptisms_actual_for_range`.

**Acceptance:** the 11-failure baseline is unchanged (`test_effort_reporting_scope`
×3, `test_goals_duplicate_metric_keys` ×2, `test_renders_ccsm_with_data` ×6 —
stash and re-run before blaming anything here), and the live Panel and Embudo
pages render with the real 31-row tab untouched.

---

## §2 — Track B: acquisition *(gated on Zackary)*

Mirrors the proven chain in `views/12_Traslados.py`: a button dispatches
`workflow_dispatch` via `integrations/github_actions.py`, a Playwright container
runs the pull, `cloud_job_wrapper` reports into `CLOUD_JOB_STATUS`, and
`cloud_job_ui.py` polls it. **All four are reused unchanged.**

New: `.github/workflows/tableau-reports.yml` and
`app/ingestion/tableau_finding_runner.py`.

### 2.1 — What Zackary must do first

| Secret | Value |
|---|---|
| `CCSM_TABLEAU_USERNAME` | the Tableau/Church sign-in |
| `CCSM_TABLEAU_PASSWORD` | its password |

at https://github.com/ccsmpmgcompass-collab/ccsm-pmg-compass/settings/secrets/actions,
plus `GITHUB_ACTIONS_TOKEN` present in the **deployed** Streamlit secrets
(it is in local `dashboard/.streamlit/secrets.toml`), unexpired, `workflow` scope.

### 2.2 — The live page, inspected 2026-09-19

Read through Zackary's authenticated Chrome with his explicit consent;
read-only, nothing clicked, submitted or downloaded. `imos_portal.py:8` admits
its own selectors were never verified and that runner has never completed a
live login — this pass exists so Track B does not repeat it. What it found
makes the runner *simpler* than planned, not harder.

**The date window is a URL parameter.** Verified live: loading the view with
`?Start%20Date=2026-09-01&End%20Date=2026-09-19` applied the filter — the page
rendered `Start Date 9/1/2026`, `End Date 9/19/2026`,
`Total People Baptized 19`. ISO dates are accepted though the control displays
`M/D/YYYY`.

**This removes canvas interaction from the runner entirely**, which turns out
to have been essential rather than merely convenient: the viz renders inside a
same-origin iframe as `canvas.tabCanvas` elements, and **the filter cards are
not in the DOM at all**. Only the toolbar is. A runner driving the date filter
by selector could never have worked, and driving it by pixel coordinate would
have been worse than the drift this plan set out to avoid.

So the runner is: navigate with parameters → click one stable toolbar button →
take the file. The selectors are Tableau's own `data-tb-test-id` hooks —
`viz-viewer-toolbar-button-download`, with `-subscribe`,
`-manage-customviews`, `-refresh` and `-share` alongside it.

**The workbook.** Site `churchofjesuschrist`, id **2388991**. Five sheets; the
view URL name is the title with spaces stripped — `MissionFindingSummary`,
`MissionFindingRankingList`, `MissionFindingComparison`,
`MissionFindingDetail`, `Definitions`.

Filters on the Summary: **Start Date** and **End Date** (typed parameters),
Finding Category, Finding Source, Area (`South America South Area`),
**Mission** (`Chile Concepción South`), Zone, District, Teaching Area. The
Mission filter is already scoped right, but the runner **sets it explicitly
rather than trusting a saved default** — a default that silently changes is
how a mission-wide export quietly becomes an area-wide one.

**The source refreshes daily**, stamping `Data Last Updated: 9/18/2026
12:55 PM` when read on 2026-09-19. Reporting lag is about a day, and that is
what justifies §2.4's nightly cadence over anything slower.

### 2.3 — Two hard constraints on the runner

- **The Detail export must stay a FULL pull.** It REPLACES stored data and
  `describe_replacement`'s `narrower` check exists to stop a partial export
  destroying 2.6 years of history. That guard stays armed in the runner.
- **Nothing sensitive may be published.** The repo is **public** (verified via
  the GitHub API, 2026-09-19), so Actions logs and artifacts are downloadable by
  anyone. This workflow uploads **no screenshots** and echoes no response bodies.
  Separately: `transfer-roster-pull.yml` currently uploads `debug/*.png` of a
  logged-in IMOS session on failure with 7-day retention, i.e. missionary names
  are public to whoever finds the run. **Standalone fix, flagged, undecided.**

### 2.4 — Cadence

Nightly, not monthly. Same code path behind both the cron and the button so the
two cannot drift. Each run re-pulls the **current and previous month** so that
late-entered records land — the single biggest accuracy gain over the manual
process, which captures a month once and never revisits it.

### 2.5 — The open unknown, resolved

Tableau documents `/data` as returning **summary-level data only**, which left
it unclear whether the person-level Detail export (89,824 × 14) could come
through. **It can.** Mission Finding Detail is a person-level sheet — "All
person records are tied to the first instance of the selected event or cohort
per person" — so its summary data *is* the person rows. Moot while Track B
drives the real Download menu, but it means the REST runner is viable the day
PATs are enabled.

### 2.6 — Noted for backlog Step 4

The view carries a **'By Cohort' vs 'By Event Date'** toggle at source. That is
the feature `PLAN-2026-09-05-backlog.md` Step 4 calls the largest remaining
piece of value, and it does not have to be computed from Detail after all —
Tableau already offers it, and a runner setting that parameter could capture
both framings.

---

## §3 — What automation cannot fix

**Reporting lag.** A baptism performed on the 18th may not be in Tableau on the
19th, so month-to-date reads low and fills in behind you. A property of the
source, not of any of this. Far smaller than being six weeks stale — but it
means the number is *current*, not *final*, and §1a's provisional derivation is
what keeps the page honest about the difference.
