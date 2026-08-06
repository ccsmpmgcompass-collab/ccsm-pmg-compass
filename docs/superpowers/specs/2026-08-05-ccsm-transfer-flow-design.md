# CCSM Transfer Flow — Design

**Date:** 2026-08-05
**Status:** Approved, ready for implementation planning

## Problem

CCSM (Chile Concepción South Mission) has a standalone Streamlit dashboard
(see `2026-07-28-ccsm-streamlit-dashboard-design.md`) but it shipped with
Transfer Flow deliberately cut — at the time, `COMPASS_CCSM` had none of the
supporting tabs and no transfer data existed yet. The Provo mission's own
Transfer Flow (roster pull via IMOS Playwright → apply to `MISSION_ORG` →
sync nightly/weekly forms) has since matured and been moved off a
local-machine dependency onto GitHub Actions (see
`PMG-Compass/docs/superpowers/specs/2026-07-18-cloud-playwright-automation-design.md`
in Provo's repo). CCSM now needs the same capability, running from CCSM's own
GitHub repo with CCSM's own credentials — no dependency on Provo's
infrastructure and no dependency on any specific laptop being on.

## Goal

Port Transfer Flow (core only — **no Drive folder automation**, per explicit
scope decision below) into CCSM's dashboard, targeting `COMPASS_CCSM`, and
move the IMOS roster-pull step to CCSM's own GitHub Actions workflow so it
runs on demand from any machine.

## Scope decisions (locked with user, 2026-08-05)

1. **No Drive integration.** CCSM has zero Drive folder automation today (no
   move/rename/create/archive, no finding-summary storage in Drive). User
   explicitly chose to skip this and keep tonight's scope to roster pull →
   apply → form sync only. Building CCSM's own Drive OAuth/service-account
   setup is a separate future project if ever requested.
2. **Mirror Provo, no shared runtime.** Same principle the original CCSM
   dashboard was built on — literal ports of Provo's modules, own repo, own
   credentials, own sheet. Zero coupling to Provo's code path or infra.
3. **Secrets handoff is user-driven.** The assistant tells the user exactly
   which secret to create and where; the user pastes every credential
   themselves. Real credential values are never typed or echoed by the
   assistant into chat, files committed to git, or artifacts.

## Current state (verified 2026-08-05, not assumed)

- CCSM dashboard `pages/`: `01_dashboard.py`, `02_Goals.py`, `04_Breakdowns.py`,
  `06_Scores.py`, `07_Finding_Funnel.py`, `10_Notes.py`, `15_Suggestions.py`,
  `17_Action_Center.py`, `18_Maintenance.py`. No Transfer Flow page.
- CCSM dashboard `app/`: no `ingestion/` directory, no `integrations/`
  directory. None of Provo's transfer/Playwright/cloud-job modules exist yet.
- Live `COMPASS_CCSM` tabs (read directly via gspread): has `TRANSFER_SCHEDULE`.
  Missing `TRANSFER_IMPORT`, `MISSION_ORG_SNAPSHOT`, `AREA_LINEAGE`,
  `TRANSFER_LOG`, `CLOUD_JOB_STATUS`.
- `CCSM_IMOS_USERNAME` / `CCSM_IMOS_PASSWORD` already exist in **Provo's**
  `.env` (main `PMG-Compass` repo root) — CCSM's own IMOS missionary-portal
  login was already obtained by someone, just never wired up or moved into
  CCSM's own environment. This is the credential to reuse; no new IMOS
  account needs requesting.
- CCSM's GitHub repo (`ccsmpmgcompass-collab/ccsm-pmg-compass`) has no
  `.github/workflows/` for any Playwright job.

## Design

### 1. Sheet schema — add 5 tabs to `COMPASS_CCSM`

Headers copied verbatim from Provo's live `COMPASS_Main` so the ported engine
needs zero column-mapping changes:

| Tab | Headers |
|---|---|
| `TRANSFER_IMPORT` | Area, Zone, District, Companion1_Name, Companion2_Name, Companion3_Name, Companion4_Name, Calling, Area_Email |
| `MISSION_ORG_SNAPSHOT` | Area_ID, Area_Name, Zone, District, Language_Type, Companion1_Name, Companion1_Email, Companion2_Name, Companion2_Email, Is_DL, Is_ZL, Is_STL, Is_AP, Is_MP, Active, Companion3_Name, Companion4_Name |
| `AREA_LINEAGE` | Applied_At, Transfer_Date, Change_Type, Old_Areas, New_Area, Email_Action, Rewrite_Counts_JSON |
| `TRANSFER_LOG` | Timestamp, Function, Result, Details |
| `CLOUD_JOB_STATUS` | job_id, job_type, status, progress_text, started_at, updated_at, result_summary |

Created via an extension to `BuildCcsmSheet.gs` (CCSM's own sheet-scaffolding
script — same boundary rules as CCSM's other `.gs` files: paste into the live
Apps Script editor before it takes effect, confirmed with the user by name
before pasting).

### 2. Engine + page port (no Drive)

Port unchanged in logic, only sheet targeting changes (already redirected via
`COMPASS_SHEET_NAME=COMPASS_CCSM`):
- `app/ingestion/transfer_engine.py` — roster diff, 30% deactivation guard,
  `MISSION_ORG` apply, `TRANSFER_LOG` write. Existing 33 unit tests port over
  with schema-only diffs expected, not logic diffs.
- `app/ingestion/transfer_apply_service.py` — preview/apply orchestration
  against the live sheet.
- New `pages/12_Transfer_Flow.py` (or CCSM's next free page number) —
  Pull → Preview diff+guard → Apply → Sync forms. Drive preview
  expanders and create/archive sections are dropped entirely, not stubbed.
- Form sync (Forms API, outside gspread's reach) needs a CCSM-side
  `docs/TransferWebApp.gs` Web App, mirroring Provo's `docs/TransferWebApp.gs`
  — a NEW file, respects CCSM's own docs/ boundary. Exact filename confirmed
  with the user before any Apps Script paste.

### 3. IMOS Playwright port

Port `imos_portal.py`, `transfer_roster_transform.py`, `transfer_sheets_writer.py`
verbatim into CCSM's `app/ingestion/`. New CCSM-side `.env` (none exists today)
holding `CCSM_IMOS_USERNAME`/`CCSM_IMOS_PASSWORD` (moved from Provo's `.env`,
where they're currently stranded unused) plus `IMOS_HEADLESS`. Tested locally
first, headless off, against the real IMOS portal, before any cloud wiring.

### 4. Cloud automation

Port the shared cloud-job infra unchanged: `gcp_creds.py`, `cloud_job_status.py`,
`github_actions.py`, `app/ingestion/cloud_job_wrapper.py`,
`app/components/cloud_job_ui.py` (`run_cloud_job()`). New
`.github/workflows/transfer-roster-pull.yml` in CCSM's own repo, same shape as
Provo's proven workflow (`workflow_dispatch` + `CLOUD_JOB_STATUS` polling).

"Runs regardless of which laptop is on, stored securely in the cloud" is
answered by GitHub's own encrypted repo secrets — the same mechanism already
proven for Provo, not a new one. CCSM repo secrets needed:
- `GITHUB_ACTIONS_TOKEN` — a new fine-grained PAT scoped only to
  `ccsm-pmg-compass` (Actions + Secrets, read/write).
- `CCSM_IMOS_USERNAME` / `CCSM_IMOS_PASSWORD`.
- CCSM's Google service-account JSON (already exists, used by the dashboard's
  own `.streamlit/secrets.toml`; same key reused for write access to the new
  tabs).

The user pastes each of these into CCSM repo Settings → Secrets themselves,
one at a time, walked through by the assistant.

### Testing / safety

- Existing 33 `transfer_engine.py` unit tests ported and re-run against the
  new schema.
- 30% deactivation guard carried over unchanged — same protection against a
  bad roster pull silently misrouting live coaching/referral data.
- `Apply` against live `MISSION_ORG` only ever runs with the user's explicit
  go-ahead at each step (Pull, Preview, Apply, Sync are separate confirmed
  actions) — never as an unattended test, matching
  `feedback-stepwise-confirm-production-writes`.
- First live GitHub Actions dispatch is the real test of the cloud path,
  same as Provo's Task 7 — watched for actual success (real IMOS login, real
  roster rows written), not just a green workflow status.

## Out of scope (explicit)

- Drive folder move/rename/create/archive automation for CCSM.
- Any change to Provo's `PMG-Compass` repo, other than reading
  `CCSM_IMOS_USERNAME`/`PASSWORD` out of its `.env` to move them into CCSM's
  own environment.
- Tableau Cloud / residential-proxy work (unrelated Provo-only concern).
