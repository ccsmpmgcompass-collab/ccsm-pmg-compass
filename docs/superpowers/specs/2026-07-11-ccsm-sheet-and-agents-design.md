# CCSM Sheet + Agent Suite — Design

**Date:** 2026-07-11
**Status:** Approved pending user review
**Project:** CCSM PMG Compass (Chile Concepción South Mission)

## Goal

Build the production backend for CCSM: the `COMPASS_CCSM` Google Sheet and the full PMG Compass agent suite, adapted from the live Utah Provo Mission system. The Provo `COMPASS_Main` sheet is a **format reference only — no Provo data is ever copied** (confidential missionary info). Provo's live `docs/*.gs` files are never edited.

## Confirmed scope decisions

- **Approach:** builder script (`BuildCcsmSheet.gs`) creates the whole sheet from scratch — reproducible, zero Provo-data exposure. Same standalone-script pattern as the four form builders.
- **Agents:** full Provo suite, minus the cuts listed below. **The entire Sister Ellis system is cut** (Agent7, `SISTER_ELLIS_LOG` tab, `SISTER_ELLIS_EMAIL` / `A7_SPIRITUAL_THOUGHT_*` config keys).
- **Language:** Spanish only. Only the ES forms (`DailyReportForm_ES.gs` / `WeeklyReportForm_ES.gs` builds) get attached to the sheet. All parsing targets Spanish headers; all emails are Spanish.
- **Forms:** already built; the user attaches their response destinations to the new sheet.
- **Dashboard:** out of scope this round (sheet + Apps Scripts only).
- **Missionary emails:** the IMOS `CurrentOrganization` export has no email column. `MISSION_ORG` ships with blank email columns; emails are filled later via the existing Provo Playwright scraper (`scrape_and_fill_area_emails.py` + the `transfer-roster-playwright` worktree's `imos_portal` scraper — CCSM is on the same IMOS/mail.missionary.org system).

## Deliverable 1 — `BuildCcsmSheet.gs`

Standalone Apps Script: paste at script.google.com, run `buildCcsmSheet()`, it creates a new `COMPASS_CCSM` spreadsheet and prints its URL. Safe to re-run (each run = fresh spreadsheet, never edits an existing one).

**Verify pass (required):** after building, re-open the spreadsheet via `SpreadsheetApp.openById()` and confirm every tab exists and every header cell matches the expected value; re-apply any misses; repeat until a fresh read-back is clean (the lesson from the forms' dropped-writes bug — never trust in-place reads of just-written state).

### Tabs created

| Group | Tabs | Notes |
|---|---|---|
| Raw form data | *(none — see Form attachment flow)* | Google Forms creates its own tab on attach; user renames to `NIGHTLY_FORM_RAW` / `WEEKLY_FORM_RAW` |
| Processed data | `DAILY_LOG`, `LIVE_SNAPSHOT`, `WEEKLY_KI`, `DASHBOARD_SUMMARY`, `WEEKLY_BREAKDOWNS`, `SCORES`, `GOAL_RECALIBRATION` | Created **empty** — the agents write their own header rows on first run (Provo pattern), which prevents header drift between builder and agents |
| Transfer data | `TRANSFER_SCHEDULE` | Header only; user fills transfer dates (needed by Agent2 goal recalibration — this is just a date table, not the cut transfer tooling) |
| Org & config | `MISSION_ORG`, `AGENT_CONFIG`, `QUESTIONS_CONFIG`, `GOALS_CONFIG`, `SCORE_CONFIG` | Pre-filled (below) |
| Content | `MESSAGE_BANK`, `KNOWLEDGE_BASE` | Seeded with Spanish rows keyed to CCSM metrics |
| Logs & misc | `AGENT_RUN_LOG`, `AUDIT_LOG`, `MISSING_LOG`, `FEEDBACK_HISTORY`, `ENCOURAGEMENT_HISTORY`, `SUGGESTIONS`, `SUGGESTIONS_REVIEW`, `NOTES` | Header row only |

Header schemas are derived from the same Provo `docs/*.gs` code the CCSM agents are adapted from, so agents and sheet stay in sync by construction. Each tab gets a frozen header row and header formatting consistent with Provo's look.

### `AGENT_CONFIG` initial contents

| Key | Value |
|---|---|
| `MISSION_NAME` | `Chile Concepción South Mission` |
| `MISSION_LANGUAGE` | `ES` |
| `MISSION_TIMEZONE` | `America/Santiago` |
| `MISSION_LOCALE` | `es_CL` |
| `TEST_MODE` | `TRUE` |
| `TEST_INBOX_EMAIL` | `CCSM.PMG.Compass@gmail.com` |
| `SEND_FROM_EMAIL` | `CCSM.PMG.Compass@gmail.com` |
| `SYSTEM_START_DATE` | *(blank — user fills)* |
| `NIGHTLY_FORM_LINK` / `WEEKLY_FORM_LINK` | *(blank — user fills)* |
| `RELAY_1_URL` / `RELAY_2_URL` / `RELAY_SECRET` | *(blank — user fills if relays used)* |
| `GEMINI_API_KEY` / `GEMINI_QA_MODEL` | *(blank / `gemini-2.5-flash` — user fills key)* |
| `MISSED_DAYS_LOOKBACK` | `3` |
| `CONTACT_RATE_TARGET` | `0.50` |

### `MISSION_ORG` pre-population

One row per area from the `ZONES` data already verified in the form builders (10 zones, ~101 areas, source: `CurrentOrganization-Excel (3).xls`). District, missionary **names**, and **leadership flags** come from re-parsing that export (391 missionary rows; Position codes: `(DL)`, `(ZL1)`/`(ZL2)`, `(STL1)`/`(STL2)`/`(STLT)`, `(AP)`, plus `(JC)`/`(SC)`/`(TR)` companion markers → `Is_DL`/`Is_ZL`/`Is_STL`/`Is_AP`). Columns follow Provo's schema (Area_Code/Area_Name/Zone/District/name + email columns/Is_DL/Is_ZL/Is_STL/Is_AP/Is_MP/Active). **Email columns are left blank** for the Playwright scraper/office to fill; `Active = TRUE`.

### `QUESTIONS_CONFIG` — the metric mapping (critical)

One row per form question. `Form_Column_Header` is the **exact Spanish question text copied verbatim from the ES form builders** (accents included) so parsing matches the live forms character-for-character. Schema follows Provo (`Question_ID`, `Form_Type`, `Form_Column_Header`, `Metric_Key`, `Metric_Display_Name`, `Data_Type`, include-flags, `Display_Order`, `Active`).

**Daily (Form_Type = NIGHTLY):**

| Metric_Key | Form_Column_Header (verbatim ES) | Type |
|---|---|---|
| `report_date` | ¿Qué fecha está ingresando? | DATE |
| `exchanges` | ¿Participó en uno o más intercambios? | YESNO |
| `roleplays` | Prácticas de enseñanza realizadas hoy | NUMBER |
| `contacts_attempted` | Intentos de contacto con amigos | NUMBER |
| `contacts_made` | Contactos con amigos | NUMBER |
| `meaningful_conversations` | Conversaciones significativas con amigos | NUMBER |
| `new_people_found` | Nuevas personas encontradas | NUMBER |
| `friend_lessons` | Lecciones con amigos | NUMBER |
| `pmf_lessons` | Lecciones con familias en las que no todos son miembros | NUMBER |
| `rc_lessons` | Lecciones con conversos recientes | NUMBER |
| `rc_lessons_mcp` | Lecciones con conversos recientes usando Mi Senda de los Convenios | NUMBER |
| `friend_texts` | Mensajes de texto enviados a amigos | NUMBER |
| `friend_calls` | Llamadas telefónicas a amigos | NUMBER |
| `member_contacts` | Contactos realizados con miembros del barrio | NUMBER |
| `lessons_member_present` | Lecciones con un miembro presente | NUMBER |
| `references_asked` | Referencias solicitadas | NUMBER |
| `member_referrals_received` | Referencias de miembros recibidas hoy | NUMBER |
| `bom_shared` | Copias del Libro de Mormón entregadas | NUMBER |
| `church_invites` | Invitaciones a la Iglesia extendidas | NUMBER |
| `baptism_doctrine_lessons` | Lecciones en las que se enseñó la doctrina del bautismo | NUMBER |
| `baptismal_invitations` | Invitaciones al bautismo extendidas | NUMBER |
| `baptismal_calendars` | Calendarios bautismales entregados | NUMBER |
| `effort` | ¿Dio todo, la mayor parte o algo de esfuerzo en el altar del sacrificio hoy? | CHOICE (Todo / La mayor parte / Algo) |

Zone/area come from the branching questions `¿En qué zona sirve?` / `¿En qué área sirve?`.

**Weekly (Form_Type = WEEKLY):** `report_date` (same date question), `leader_call` (¿Recibió una llamada de sus líderes?), `correlation_meeting` (¿Usted y sus líderes locales realizaron una reunión de coordinación semanal?), then 7 KIs × 2. KI column headers are the KI title + ` (Real)` or ` (Meta)` suffix, e.g. `Nuevas personas encontradas (Real)`:

| Metric_Key base | ES KI title |
|---|---|
| `ki_new_people` | Nuevas personas encontradas |
| `ki_member_lessons` | Lecciones con miembros |
| `ki_friends_sacrament` | Amigos en la reunión sacramental |
| `ki_friends_first_week` | Amigos en la Iglesia durante su primera semana de enseñanza |
| `ki_baptismal_date` | Amigos con fecha bautismal |
| `ki_baptized_confirmed` | Bautizados y confirmados |
| `ki_rc_at_church` | Conversos recientes en la Iglesia |

Each yields `<base>_real` and `<base>_meta` keys.

## Form attachment flow (user step, documented in the builder's log output)

1. Open each ES form → Responses → Select response destination → choose `COMPASS_CCSM`.
2. Google Forms **creates its own new tab** (it will not write into a pre-made empty tab). Rename that tab to `NIGHTLY_FORM_RAW` (daily form) / `WEEKLY_FORM_RAW` (weekly form) — renaming is safe; the form link follows the tab.
3. **Duplicate-header columns:** because both forms use one section per zone, the raw tabs contain ~10 copies of each question column (one per zone branch); each submission fills only its zone's columns. Raw-tab parsing in the agents must **coalesce columns with identical headers, taking the non-empty value per row** (Provo's form has the same architecture, so the ported parsing logic should already handle this — verify during implementation, and treat it as a hard requirement of CCSM_Agent3/5A).

## Deliverable 2 — CCSM agent suite

Forked from `C:\Users\2011794-MTS\Desktop\PMG-Compass\docs\*.gs` into `CCSM_*.gs` files in this folder. User pastes them into the `COMPASS_CCSM` bound Apps Script project (Helpers first). Common adaptations to every file: mission identity read from `AGENT_CONFIG` (never hardcoded), Spanish email/user-facing text, CCSM metric keys, `America/Santiago` for all date logic, no references to the Provo sheet ID anywhere.

| CCSM file | From | Adaptation highlights |
|---|---|---|
| `CCSM_Helpers.gs` | Helpers.gs | `MISSION_NAME`/`MISSION_LANGUAGE`/`MISSION_TIMEZONE` from config; `SENDER_NAME = 'PMG Compass — ' + MISSION_NAME` |
| `CCSM_Agent3.gs` | Agent3.gs | Nightly raw → `DAILY_LOG` via QUESTIONS_CONFIG (Spanish headers, duplicate-column coalescing); missed-days alerts in Spanish |
| `CCSM_Agent5A.gs` | Agent5A.gs | `DASHBOARD_SUMMARY` from DAILY_LOG (as in Provo), **plus** `WEEKLY_KI` parsed from `WEEKLY_FORM_RAW`'s Real/Meta columns — structural change vs Provo, whose WEEKLY_KI derives from daily data (CCSM's KIs are self-reported and not derivable from the daily form) |
| `CCSM_Agent5B.gs` | Agent5B.gs | Friday encouragement qualifier (chains to Agent6) |
| `CCSM_Agent2.gs` | Agent2.gs | Per-transfer goal recalibration over CCSM metrics (reads TRANSFER_SCHEDULE, writes GOAL_RECALIBRATION) |
| `CCSM_Agent1A/1B/1C.gs` | Agent1A–1C | Sunday coaching chain: CCSM coaching metrics, Spanish MESSAGE_BANK, Spanish emails |
| `CCSM_Agent4.gs` | Agent4.gs | System health report (Spanish) |
| `CCSM_Agent6.gs` | Agent6.gs | Encouragement emails (Spanish) |
| `CCSM_AgentReminder.gs` | AgentReminder.gs | Weekly submission reminders (Spanish) |
| `CCSM_AgentDuplicate.gs` | AgentDuplicate.gs | Duplicate detection on raw tabs |
| `CCSM_AgentEscalation.gs` | AgentEscalation.gs | DL/ZL escalation (Spanish, Santiago TZ) |
| `CCSM_AgentQA.gs` | AgentQA.gs | Gemini Q&A answering in Spanish; Spanish KNOWLEDGE_BASE |
| `CCSM_AgentScores.gs` | AgentScores.gs | Effort/Skill/KI scores over CCSM metric keys; SCORE_CONFIG defaults |
| `CCSM_AgentValidation.gs` | AgentValidation.gs | Data validation checks |
| `CCSM_AgentTestMode.gs` | AgentTestMode.gs | TEST_MODE toggle helpers |
| `CCSM_Setup.gs` | *(new)* | All trigger-setup functions (times in America/Santiago; project TZ set to Santiago) + smoke-test functions |

**Cut:** Agent7/Sister Ellis (everything), AgentTransfer + TransferWebApp + LineageReview (Provo-specific transfer tooling — add later if wanted), CleanupParkCity, ward-plan/intake/miracle-form utilities, referral relay files (unless/until CCSM adopts the referral system).

## Deliverable 3 — Spanish content

- **MESSAGE_BANK:** ~3 Spanish coaching messages (strength + growth variants) per coaching metric, keyed to CCSM metric keys, drafted by Claude following Provo's tone (warm, mission-focused, scripture references using Spanish LDS book names). **User reviews before go-live.**
- **KNOWLEDGE_BASE:** starter Spanish Q&A rows (how to submit forms, what the KIs mean, who to contact), same 8-column Provo schema.
- **SCORE_CONFIG:** default weights over CCSM metrics with an `ALL` mission-wide fallback row, mirroring Provo's two-section layout.

## Safety & testing

- Ships with `TEST_MODE = TRUE` → all email goes to `TEST_INBOX_EMAIL` until the user flips it.
- No triggers exist until the user runs the `CCSM_Setup.gs` functions.
- Builder verify pass guarantees tab/header integrity.
- Smoke tests (in `CCSM_Setup.gs`): submit one test row to each form → run Agent3/5A → assert the row lands in `DAILY_LOG`/`WEEKLY_KI` with every metric mapped (no blank/missing keys); run missed-days preview; run one coaching-chain cycle in test mode and inspect the Spanish email.
- Provo boundary: nothing in this effort edits `PMG-Compass/docs/*.gs` or touches the live COMPASS_Main.

## Out of scope (this round)

- Streamlit dashboard deployment + repo multi-mission/i18n refactor (setup guide Steps 2–3, 9).
- Referral system.
- Transfer-board tooling.
- Filling missionary emails (later, via the existing Playwright scraper).

## Open items

- User fills after build: form links, `SYSTEM_START_DATE`, Gemini API key, relay URLs (if used).
- Verify during implementation how Provo's Agent3 coalesces duplicate zone-section columns and port that exact behavior.
- MISSION_ORG: MP row + leadership emails once known (AP/ZL/DL/STL flags already derived from the export's Position codes; emails still pending).
