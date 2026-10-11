# PLAN 2026-10-10 — the weekly KI PDFs, sent inside the weekly letter

Zackary, 2026-10-10, after seeing the AP preview
(`Vista_previa_KI_asistentes/correo_asistentes.html`): *"Follow the plans that
the letter redesign has put in place. Change the relay so it can carry pdfs.
Keep the timing the same, the goal is to teach missionaries to fill out the
forms when they are supposed to, not give them more latency."*

Sources: `AUDIT-2026-10-06-weekly-letter.md` §2 R1, R4, R5, R6 and §4 step 4;
the queued auto-send in memory (`project_pmg_compass`, "Queued").

## §1 Decisions (settled — do not re-open without him)

- **K1 Who gets what.** The APs (MISSION_LEADERSHIP, role `assistant`) get the
  mission document AND every zone document. The ZLs and STLs ("hcaps") of a
  zone, at their area mailbox (MISSION_ORG `Is_ZL` / `Is_STL`), get only that
  zone's document. Nobody else: DLs no (letter Q4), companionships no (R6), the
  President not asked for. The AP area's shared mailbox is read as a DL's and
  gets nothing.
- **K2 Inside the letter.** The PDFs ride as attachments on the Agent1C letter
  the recipient already gets. No second email. A boxed "📎 adjuntos" note under
  the letter's header says what is attached (the approved preview).
- **K3 Timing unchanged.** The chain still starts Monday ~21:30. The letter and
  the PDFs share ONE cutoff: the moment Agent1A reads the forms. A form sent
  after it is not in this week's letter or PDFs (the sector shows SIN INFORME).
  No extra wait to catch late forms.
- **K4 The letter reads the raw forms at send time (R1).** Agent1A rebuilds
  WEEKLY_KI from WEEKLY_FORM_RAW (`a5a_writeWeeklyKI`) before it reads, so it no
  longer depends on Agent5A's noon run. A form dated after the graded week
  counts as the graded week when the sector has no report for it (the KI-PDF
  rule; Boca de la Costa 1 and Ñielol 2 typed 11 Oct on 4 Oct's form).
- **K5 The bridge is a sheet tab, `KI_PDF_OUTBOX`.** Agent1A writes a REQUEST
  row (week end + cutoff). A GitHub job (`ki-pdfs.yml`, scheduled Monday
  evening) waits for that row, builds the PDFs from forms stamped at or before
  the cutoff, and writes them back as base64 rows (RAW, ≤45,000 chars a cell).
  Agent1C reads them. No new secret, no Drive (a service account has no Drive
  quota), no public artifact (the repo is public).
- **K6 If the PDFs are late, the letter is not.** Agent1C waits at most ~10
  minutes (5 × 2 min) for the PDFs, then sends every letter without them and
  logs the run as ERROR saying so.
- **K7 The relay carries attachments.** `sendEmail(..., opts.attachments)`
  sends `[{name, mimeType, data(base64)}]`; the relay decodes them and replies
  with how many it attached. An outdated relay (not redeployed) still sends the
  letter, and the sender logs that the PDFs were dropped. Never a duplicate.
- **K8 The deadline is said out loud (R1).** The Monday 7 AM weekly reminder
  (AgentEscalation stage 1, the live owner) adds: "Envíen su informe semanal
  antes del lunes a las 21:00 para ver sus resultados en el correo de esta
  semana."
- **K9 The builder moves into the app.** `tools/build_ki_ranking.py` →
  `dashboard/app/reports/ki_ranking.py`, weekly document only (the A–D drafts
  go). The tools script stays as a thin CLI for hand builds. Same pages,
  byte-for-byte the same drawing.
- **K10 Deferred to the letter rebuild (not this plan):** R1's "say a missing
  report kindly, never an empty box" and "resend if the chain fails", and every
  layout change R2–R5. They wait for the Temuco Ñielol feedback.

## §2 Steps

1. **Builder into the app** (K9). Render 2026-10-04 before/after and compare
   page images pixel for pixel.
2. **Cutoff + runner + outbox + workflow** (K3, K5). `ki_from_raw(cutoff=)`,
   `app/ingestion/ki_pdf_runner.py`, `.github/workflows/ki-pdfs.yml`. Pytest.
3. **Relay + sendEmail attachments** (K7). `CCSM_RelayReceiver.gs`,
   `CCSM_Helpers.gs sendEmail`. JS tests.
4. **Agent1A: R1 + slip rule + REQUEST row** (K3, K4, K5). JS tests.
5. **Agent1C: wait, attach, note** (K1, K2, K6). JS tests; `render.js` preview.
6. **Deadline line** (K8). JS test.
7. **Verify**: Python suite, JS suite (baseline below), dry-run the runner on
   live data, render the AP and one ZL letter with their attachments.
8. **Handoff** to Zackary: push; re-paste the changed `.gs`; redeploy the relay
   as a new version of the SAME deployment (URL unchanged); Reboot.

Baselines before step 1: pytest 0 failed / 1947 passed; JS suite 5 failing
files that predate this work (`test_agent5b6`, `test_ccsm_data`,
`test_ccsm_helpers`, `test_harness_selftest`, `test_quota_guards`).

## §3 STATUS

**2026-10-10 — ALL STEPS 1–7 BUILT AND VERIFIED, NOT PUSHED.** Commits
601aa89 (1) · 243b04c (2) · 5fda050 (3) · a4c96f8 (4) · 8ae543c (5) ·
d2c7ba9 (5b) · fd4325f (6).

- **1** 23/23 pages pixel-identical to the approved PDFs (week ending 10-04).
- **2** Live dry run: 5 documents, 23 pages, 7 cells.
- **3** `test_relay_attachments.js` runs the real relay `doPost`.
- **4** Agent1A rebuilds WEEKLY_KI from the forms; the slip rule caught Boca
  de la Costa 1, Boca de la Costa 2 and Ñielol 2 on live data.
- **5** `render.js --ki-pdfs` on the live dump: 48 letters, 19 attachments
  (2 APs × 5 + all 9 ZL/STL mailboxes × 1), the AP letter says 39/45 like the
  PDF (was 36/45). Without the job: 0 attachments, letters as before.
- **5b (found by the full JS suite)** Agent1A requests PDFs only when
  KI_PDF_OUTBOX exists; the job creates it before waiting. So ANY deploy order
  is safe: .gs first → no tab → letters as today; job first → it waits, gives
  up, letters untouched; relay not redeployed → letters go once without PDFs
  and the run log says "redeploy". The missed-run check ignores WAITING rows.
- **6** Monday reminder carries the deadline line.
- **7** pytest 0 failed / 1958 passed; JS suite = the same 5 pre-existing
  failures and nothing else. Preview: `Vista_previa_KI_asistentes/`
  (untracked, real names) and `tools/email_preview/.data/modelo/ki_asistentes.html`.

**Still to do — Zackary's hands (step 8):**
1. Push (also pushes the 18 council-packet commits ahead of these).
2. Apps Script editor: paste `CCSM_Helpers.gs`, `CCSM_Agent1A.gs`,
   `CCSM_Agent1C.gs`, `CCSM_AgentEscalation.gs`.
3. Relay project (second Gmail account): paste `CCSM_RelayReceiver.gs`,
   Deploy → Manage deployments → pencil → Version: New version → Deploy.
4. Reboot the Streamlit app (`agent_runs.py` + the packet work).
5. First live run: Monday 2026-10-12, job 20:30, letters ~21:30. Check
   AGENT_RUN_LOG's Agent1C row for "KI PDFs attached: 19".

**Open, for Zackary:** the letter's KI totals still differ from the PDF's
(NP 235/294 vs 203/267) because the letter grades a sector that set no goal
last week against this week's own goal, while the PDF leaves it SIN META.
Not changed: it is a rule choice, not stale data.
