# CCSM Streamlit Dashboard — Design

**Date:** 2026-07-28
**Status:** Approved, ready for implementation planning

## Problem

CCSM (Chile Concepción South Mission) has a live PMG Compass deployment — the
`COMPASS_CCSM` sheet, Apps Script agents, and both Google Forms — but no
dashboard. The Utah Provo Mission runs a Streamlit dashboard against its own
`COMPASS_Main` sheet. CCSM needs the equivalent, standing entirely on its own:
no shared code path, no shared runtime, no possibility that a change to Provo's
app alters CCSM's, or the reverse.

## Goal

A standalone Streamlit dashboard, living in CCSM's own repository, reading
`COMPASS_CCSM`, fully bilingual (English/Spanish) with a language switch on the
home page, verified running locally. Cloud deployment is explicitly out of scope
for this round.

## Current state (verified 2026-07-28, not assumed)

`COMPASS_CCSM` (`1DA1UHAZSGLFn5Dc1RtI_9g2Y0qYIibpFKVPt3SmFTaI`) has 28 tabs;
Provo's `COMPASS_Main` has 49.

`AGENT_CONFIG` shows `SYSTEM_START_DATE = 2026-07-27` — CCSM went live one day
ago. `MISSION_LANGUAGE = ES`, `MISSION_TIMEZONE = America/Santiago`,
`MISSION_LOCALE = es_CL`, `TEST_MODE = TRUE`.

Row counts on the tabs that matter:

| Tab | Rows |
|---|---|
| `MISSION_ORG` | 98 |
| `LIVE_SNAPSHOT` | 98 |
| `SCORES` | 98 |
| `DASHBOARD_SUMMARY` | 360 |
| `DAILY_LOG` | **0** |
| `WEEKLY_BREAKDOWNS` | **0** |
| `GOALS_CONFIG` | **0** |
| `NIGHTLY_FORM_RAW` | **0** |
| `WEEKLY_FORM_RAW` | **0** |

No missionary has submitted a report yet.

### Coupling points found in the Provo app

1. **Sheet targeting is already clean.** `app/db/sheets_client.py:70` opens the
   spreadsheet **by name** via `st.secrets["COMPASS_SHEET_NAME"]`. One secret
   redirects the entire data layer.
2. **Mission identity is data-driven.** `MISSION_NAME` is read from the sheet's
   `AGENT_CONFIG` through `get_config_value()`. CCSM's `AGENT_CONFIG` has no
   `MISSION_NAME` row, so headers would read "Mission".
3. **Auth is hardcoded to Provo.** `app/auth/auth.py:23` `_ALWAYS_ALLOWED`
   contains `pmg.compass@gmail.com`, `jason.ellis2@churchofjesuschrist.org`,
   `naomi.ellis@churchofjesuschrist.org`.
4. **Supabase is nearly vestigial.** `app/db/{notes,area_goals,pipeline}_queries.py`
   are imported by nothing under `pages/` or `Home.py` — only by ingestion
   scripts. Among pages, only `pages/12_Transfer_Flow.py` imports
   `app/config/settings.py`, which hard-requires `SUPABASE_URL`,
   `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_KEY` at import time.

## Design

### 1. Location

`Worldwide PMG Compass\CCSM PMG Compass\dashboard\` — a new subfolder inside the
existing CCSM git repo, which already holds the `.gs` agents, deployment docs,
and `tools/`. One repository to hand to the CCSM Tag Missionary, consistent with
the existing `CCSM Independence Handoff Guide.html`.

A full standalone copy: `Home.py`, `pages/`, the reachable subset of `app/`,
`requirements.txt`, its own `venv/`, its own `.streamlit/`. No import may
resolve outside `dashboard/`.

### 2. Scope — pages kept and cut

**Kept (9):** Dashboard, Goals, Breakdowns, Scores, Finding Funnel, Notes,
Suggestions, Action Center, Maintenance, plus the `Home.py` chat page.

**Cut**, because the tabs behind them do not exist in `COMPASS_CCSM`:

| Page | Missing tabs |
|---|---|
| `pages/11_Reports.py` | `TABLEAU_DETAIL`, `TABLEAU_RANKING`, `TABLEAU_BAPTISMS` — and it hardcodes a Provo stake list at line 301 |
| `pages/12_Transfer_Flow.py` | `AREA_LINEAGE`, `TRANSFER_LOG`, `TRANSFER_IMPORT`; also needs Supabase and a `TransferWebApp.gs` deployment |
| `pages/14_Referrals.py` | `REFERRAL_DATA`, `REFERRAL_SUMMARY`, plus the Provo referral-scraper pipeline |
| Miracles tab within `pages/15_Suggestions_&_Miracles.py` | `Miracles` |

They are deleted, not gated behind a "not configured" notice. Streamlit builds
its navigation from the `pages/` directory, so deleting the files removes them
from the sidebar with no nav list to maintain.

For `app/`, the implementation computes the **actual import closure** of the
surviving pages programmatically and copies only that. `app/ingestion/` and
`app/integrations/` are expected to fall out entirely — they are Provo
automation (IMOS, Tableau, transfer bridge, cloud job status).

**Consequence:** with Transfer Flow removed, nothing imports
`app/config/settings.py`, so **CCSM requires no Supabase at all.** An entire
external dependency is eliminated rather than reconfigured.

### 3. Configuration

`dashboard/.streamlit/secrets.toml`, gitignored:

```toml
COMPASS_SHEET_NAME = "COMPASS_CCSM"
GEMINI_API_KEY     = "<CCSM's own key>"
STREAMLIT_DEV_EMAIL = "<local dev only, blank in production>"

[gcp_service_account]
# service account JSON
```

No `.env` and no Supabase keys are needed.

**Credential caveat:** the service account currently holding Editor on
`COMPASS_CCSM` is Provo's (`pmg-compass-dashboard@gen-lang-client-0214221824.iam.gserviceaccount.com`).
It is used for local verification because it already has access. Creating a
CCSM-owned GCP service account is a deploy-time item, already covered as Step 2
of the Independence Handoff Guide, and is out of scope here.

### 4. Code changes

1. `app/auth/auth.py:23` — replace `_ALWAYS_ALLOWED` with CCSM's own accounts.
   Seeded with `CCSM.PMG.Compass@gmail.com` (from `AGENT_CONFIG`); the CCSM
   Mission President's email is an **open item** to be supplied before this file
   is finalized.
2. Remove the Miracles tab from `pages/15_Suggestions_&_Miracles.py`.

Plus one write to the live CCSM sheet, confirmed separately with the user before
execution: add a `MISSION_NAME` row to `AGENT_CONFIG` with the value
`Chile Concepción South Mission`.

### 4a. Bilingual UI (English / Spanish)

The dashboard is fully bilingual, with a language switch at the top of `Home.py`.
This is the largest single component of the project.

**Size, measured not estimated:** 578 translatable string literals appear in
direct Streamlit UI calls across the 10 pages. That is a floor — it excludes
text embedded in `unsafe_allow_html` markdown blocks and in
`app/components/design_system.py`. Realistic total is 700–900.

Distribution is lopsided; Maintenance, Goals, and Scores together are 59% of it:

| Page | Strings | Page | Strings |
|---|---|---|---|
| Maintenance | 143 | Suggestions | 47 |
| Goals | 107 | Notes | 44 |
| Scores | 92 | Finding Funnel | 42 |
| Action Center | 34 | Dashboard | 31 |
| Breakdowns | 21 | Home | 17 |

**Mechanism.** A new `app/i18n/` package:

- `app/i18n/__init__.py` — exposes `t(text, **kwargs)`, `get_lang()`, `set_lang(lang)`.
- `app/i18n/es.py` — a single `ES: dict[str, str]` mapping English source string
  to Spanish.

**The English source string is itself the lookup key.** `t("Area Scores")`
returns the Spanish value if present and otherwise returns `"Area Scores"`
unchanged. This makes the retrofit mechanical, requires no invented key
namespace, and makes an untranslated or renamed string degrade to English
rather than to a raw key or an exception. Interpolation goes through
`t("Welcome back, {name}", name=...)`, which looks up the template before
formatting so word order can differ in Spanish.

**State.** The selection lives in `st.session_state["pmg_lang"]`, defaulting to
`"en"`. The switch renders at the top of `Home.py` as specified, and is mirrored
in `render_sidebar()` so the choice can be changed from any page and does not
reset on navigation.

**Sidebar navigation labels** are derived from filenames under Streamlit's
file-based page discovery, so `t()` cannot reach them. Translating them requires
converting `Home.py` to the `st.navigation` / `st.Page` API (available in the
pinned 1.40.0). This is the structurally riskiest change in the project — it
alters page URLs — so it is sequenced **last**, and can be abandoned without
affecting any other translated string.

**Translation quality.** The ~800 Spanish strings are machine-written and must
get a native-speaker proofread before CCSM relies on them. `MISSION_LOCALE` is
`es_CL`; prefer Chilean usage and the formal register appropriate to mission
leadership. Recorded here once as a known limitation, not a blocker.

**Content vs. chrome.** Only UI chrome is translated. Mission content — metric
labels, mission name, knowledge base, notes — flows from the sheet, which is
already Spanish, and must not be passed through `t()`.

**Streamlit version.** `requirements.txt:6` pins `streamlit==1.40.0`
deliberately: newer releases through 1.59.1 have a `st.selectbox` regression
where clicking a searchable selectbox fails to clear the input. CCSM's venv
installs the pin. (Note: the Provo working venv has drifted to 1.57.0; CCSM
should not copy that drift.)

### 5. Empty-tab behavior

`read_tab()` returns an empty DataFrame on `WorksheetNotFound`, so absent tabs
degrade rather than crash. Empty *existing* tabs are the real risk: Dashboard,
Breakdowns, Finding Funnel, and Goals will render against zero rows.

Expect some pages to show a graceful empty state and others to raise on an empty
DataFrame. Identifying and fixing those failures is a substantial share of the
implementation, not an afterthought. Every fix must preserve correct behavior
once data arrives — no special-casing that would misreport real data later.

## Verification

Isolation, checked as artifacts rather than claimed:

1. No import inside `dashboard/` resolves outside `dashboard/`.
2. Grep the copy for `COMPASS_Main`, `Provo`, and the three Provo emails —
   zero hits outside inert docstrings.
3. `git status` in `PMG-Compass` shows this work added nothing there.

Function:

4. Run on **port 8502** (Provo's dev app uses 8501) against `COMPASS_CCSM`.
5. Walk all 9 pages plus Home; record which render, which are empty, which
   raise. Fix every raise.
6. Confirm the running app never opens `COMPASS_Main`.

Bilingual UI:

7. `t()` returns the English key verbatim for any string absent from `ES` —
   asserted by a unit test, so a missing translation can never raise.
8. Toggle to Spanish on Home, navigate to another page, confirm the language
   persists via `st.session_state["pmg_lang"]`.
9. A coverage check reports how many extracted UI strings have `ES` entries, so
   remaining gaps are a known number rather than a surprise.
10. Walk all 10 pages in each language and confirm neither raises.

## Out of scope

- Streamlit Cloud deployment and the CCSM-owned GitHub remote (the CCSM repo
  currently has no remote at all).
- A CCSM-owned GCP project and service account.
- Native-speaker proofreading of the Spanish translations.
- Translating sheet-sourced mission content (it is already Spanish).
- Building the missing tabs or the referral/Tableau/transfer pipelines.
- `RELAY_2_URL`, still blank in `AGENT_CONFIG` — a known open item from the
  original CCSM deployment, unrelated to the dashboard.

## Open items

- CCSM Mission President's email address, for `_ALWAYS_ALLOWED`.
- Explicit confirmation before writing `MISSION_NAME` into the live
  `AGENT_CONFIG` tab.
