# Audit: the Monday letters, and what breaks at the mission's full size

2026-10-28. Asked by Zackary: "figure out what is going on with the Monday
letters so they can go out with no problem when we over double the scale."
Nothing has been changed yet. This is the diagnosis and the proposed fixes,
for his OK before any code (his working style: audit, then plan, then build).

Evidence comes from the live sheet (AGENT_RUN_LOG, KI_PDF_OUTBOX,
NIGHTLY_FORM_RAW, sheet metadata), GitHub's public Actions API for this repo,
the 10-13 letter renders in `tools/email_preview/.data/sent_1013/`, and the
code as it stands at `f8f7ee1`.

## 1. Bottom line

The letters have gone out every week since the watchdog was built, but both
weeks needed it. They hit **two real bugs and one weakness that has not been
explained yet**. None of the three is caused by the size of the mission yet,
but all three get worse when it doubles:

| # | What went wrong | Cause | Status |
|---|---|---|---|
| A | **10-26: Agent1A never started at 21:30.** The letters went at 23:47, about 2 h late. | **A bug in the watchdog.** When it restarted Agent1A on 10-19, it deleted the Monday 21:30 trigger. | **Proven.** Still broken: **Mon Nov 2 will also start late** unless the triggers are reinstalled. |
| B | **10-19: the letters went without the KI PDFs.** The APs, ZLs, STLs and the President got none. | **GitHub runs the scheduled PDF job 2½–4¼ h late.** Agent1C waits 10 min, then sends without them. | **Proven.** It happens every week. 10-26 only escaped because Agent1A was late too. |
| C | **The first, scheduled Agent1A run was killed** at the 6-minute limit on 10-12 and 10-19. Every re-run finished in about 1½ min. | Unproven. The best lead is that it runs during the nightly-form rush. | **Open.** The watchdog covers it, at a cost of about 10 min. |

Two smaller findings: **D**, the KI PDFs and the letter count forms against
clocks 3 h apart (4 h after Nov 1); and **E**, the largest ZL letter is already
at 96% of Gmail's clipping limit.

## 2. What happened, minute by minute (Chile time)

AGENT_RUN_LOG prints its timestamps in the spreadsheet's zone, America/Denver,
which is Santiago − 3 h. The times below are converted to Chile time.

**Mon 10-19**

| Time | Event |
|---|---|
| ~21:27 | Agent1A starts (the scheduled trigger). It writes the KI REQUEST (cutoff 21:27:37). |
| 21:27–21:33 | **Agent1A is killed at 6 min.** No log row; the chain state says "running". |
| 21:38 | The watchdog sees it and restarts Agent1A **through `scheduleNext('runAgent1A', 1)`**. |
| 21:40 | Agent1A SUCCESS (about 1½ min). It keeps the 21:27 request. |
| 21:42 | Agent1B SUCCESS. |
| 21:43–21:53 | Agent1C waits for the PDFs 5 × 2 min. "not ready". |
| 21:57 | **Agent1C sends 48 letters WITHOUT the PDFs** (logged as ERROR). |
| **23:00** | The GitHub "Weekly KI PDFs" job finally starts (due 20:30) and builds the PDFs in 30 s. Nobody attaches them. |

**Mon 10-26**

| Time | Event |
|---|---|
| 21:30 | **Nothing.** The weekly runAgent1A trigger no longer exists (see A). |
| 23:19 | The GitHub job starts (due 20:30) and waits for a request. |
| 23:39 | The watchdog's fixed 23:00 trigger fires: "Agent1A never started this week". It restarts Agent1A, **again through `scheduleNext`**. |
| 23:41 | Agent1A SUCCESS, about 1½ min. REQUEST cutoff 23:41:11. |
| 23:41–23:42 | The waiting GitHub job sees the request and builds the PDFs. |
| 23:44 / 23:46 | Agent1B, then Agent1C: **50 letters, 0 errors, 14 PDFs**, about 2¼ h late. |

## 3. The causes

### A. The watchdog deletes the Monday trigger it depends on (proven)

- `scheduleNext(fn, min)` **deletes every trigger whose handler is `fn`**
  before it creates the one-shot (`CCSM_Helpers.gs:790-795`).
- The watchdog restarts a dead step with `scheduleNext(LW_STEP_FN[step], 1)`
  (`CCSM_LetterWatchdog.gs:105`). For step 1A, that is
  `scheduleNext('runAgent1A', 1)`, which deletes the **weekly** runAgent1A
  trigger installed by `setupAllCcsmTriggers()`.
- The watchdog's own header already names this trap, and uses two handler
  names for itself (`runLetterWatchdog` / `runLetterWatchdogRetry`) to avoid
  it. Agent1A, the one fixed trigger it restarts, did not get the same
  treatment. Restarts of 1B and 1C are safe, because those handlers are only
  ever one-shots.
- So: the 10-19 restart removed it, 10-26 never started, and the 10-26 restart
  ran through the same path. **Right now, no weekly runAgent1A trigger exists**
  (inferred from the code path and from 10-26). Nov 2 will repeat 10-26: the
  letters go out around 23:00–23:59, whenever the watchdog's hourly trigger
  fires.

### B. GitHub's schedule is hours late, every week (proven)

| Workflow | Due (UTC) | Actually started (UTC) | Late by |
|---|---|---|---|
| ki-pdfs | Mon 23:30 | 10-13 03:45 · 10-20 02:00 · 10-27 02:19 | **4 h 15 · 2 h 30 · 2 h 49** |
| area-goals | Mon 12:00 | 10-05 19:56 · 10-12 20:36 · 10-19 17:58 · 10-26 17:56 | **7 h 56 · 8 h 36 · 5 h 58 · 5 h 56** |

- GitHub only promises "best effort" for `schedule:` events, and both of this
  repo's Monday jobs have been late on every run on record. The PDF job is
  meant to be up and waiting by 20:30 Chile time. In practice it starts
  between 23:00 and 00:45.
- Agent1C waits **10 minutes** (`A1C_KI_PDF_MAX_WAITS = 5` × 2 min). **On any
  Monday when Agent1A runs on time, the PDFs will miss the letters.** The
  "dress rehearsal PASSED 10-11" was a manual `workflow_dispatch`, which
  starts within seconds. That is why it hid this.
- The goals job has always landed before 21:30 Chile time so far, so the
  letter's "próx." column has been filled. But at 6–8½ h late it has only about
  1 h of margin left.
- When the repo goes private, a job that sits waiting up to 210 min every
  Monday spends GitHub Actions minutes, and there are 2,000 free a month.

### C. The scheduled Agent1A run dies; re-runs don't (unproven)

| Monday | First (scheduled) run | Re-runs |
|---|---|---|
| 10-05 (before the R1 code) | ✓ | — |
| 10-12 | **killed at 360.8 s** (Executions page). It stalled after the AREA_WEEKLY_GOALS log line, inside the DAILY_LOG / NIGHTLY_FORM_RAW reads. | Tue by hand ✓ |
| 10-19 | **killed** (watchdog: "started 10 min ago and never finished") | 21:39 ✓ ~1½ min |
| 10-26 | never fired (A) | 23:40 ✓ ~1½ min |

- An uncontended Agent1A takes **about 85–90 s** at 45–47 areas. The 10-13
  timing test put its four big reads at 13.5 s in total. A 6-minute stall is
  not the work itself. It is waiting on the spreadsheet.
- **What else runs at 21:27 on a Monday:** `runAgent3Evening` (daily, some time
  in the 21:00 hour; it rewrites DAILY_LOG and rebuilds LIVE_SNAPSHOT; ended
  21:50 on 10-12), `runAgentDuplicate` (scheduled 21:30, **and fired by every
  nightly form submission**, ~25 times on a Monday evening, and each time it
  reads all of NIGHTLY_FORM_RAW with `getDataRange().getValues()`), and Google
  Forms writing the nightly rows themselves. Since 10-12, Agent1A also
  **writes** first (the WEEKLY_KI rebuild and the outbox request) before its
  heavy reads. On 10-05, before that change, it survived the same rush.
- The likely reading, **not proven**: the scheduled run collides with the
  nightly-form rush, and its reads wait behind the other writers. The
  Executions page that could prove it keeps only 7 days, and the run log has
  no timings (every `Duration_Sec` is 0).
- **At full size this gets worse in both directions.** There will be about
  twice as many nightly forms in that same hour (twice as many AgentDuplicate
  runs, each reading a bigger tab). Agent1A will also have twice the areas to
  build.

### D. The PDFs and the letter use clocks 3 hours apart (proven, smaller)

- The spreadsheet's time zone is **America/Denver**, but the mission's is
  America/Santiago (AGENT_CONFIG.MISSION_TIMEZONE). Form timestamps in
  WEEKLY_FORM_RAW are written in Denver time.
- Agent1A writes its cutoff in **Santiago** time. The PDF job reads the form
  timestamps as text and compares the two directly
  (`ki_ranking.py:185-187`), so it keeps forms sent up to **3 h after** the
  letter's cutoff.
- With the job running 2–4 h late, a form sent between 21:30 and midnight is
  counted in the PDFs but not in the letter. That breaks K3 ("the letter and
  the PDFs count exactly the same forms").
- **US daylight saving time ends Sun Nov 1**, and from then on Denver is
  Santiago − 4 h. Any other code that reads these timestamps as text has the
  same problem. I have not checked those yet.

### E. ZL letters are near Gmail's clipping limit (measured, smaller)

Gmail clips a message whose HTML is over 102 KB, and hides the rest behind
"View entire message". As sent on 10-13:

| Letter | Sectors | Size |
|---|---|---|
| ZL/STL Los Ángeles Norte | 12 | **97.7 KB** (96% of the limit) |
| ZL/STL Temuco Ñielol | 13 | 89.9 KB |
| ZL/STL San Pedro | 11 | 84.9 KB |
| ZL/STL Angol | 9 | 82.3 KB |
| DL (largest) | 5 | 52.0 KB |
| AP / President | mission | 32.2 KB |
| Companionship | 1 | 18.8–21.3 KB |

Zone sizes stay about the same mission-wide; the largest are San Pedro 14,
Temuco Ñielol 13, Los Ángeles Norte 12 and Villarrica 12. But Los Ángeles
Norte is already at 97.7 KB, so **a large zone with many districts will cross
the limit**. The AP letter grows with the number of zones (4 → 10), and should
stay under 50 KB.

## 4. Headroom at about 106 areas

The roster pull on 10-22 had 106 teaching areas once the office, MLS and
service areas were removed.

| Piece | Today (45–47 areas) | Estimated mission-wide | Limit | Verdict |
|---|---|---|---|---|
| Agent1A, uncontended | ~1½ min | ~3 min | 6 min | OK, if C is fixed |
| Agent1A, first scheduled run | killed 2 of 2 | worse | 6 min | **fix (C)** |
| Agent1B | ~1 min | ~2 min | 6 min | OK |
| Agent1C | ~100 s for 50 letters (~1.8 s each) | ~3½–4 min for ~110 | 6 min, **resumable** | OK. A kill costs ~15 min (the watchdog resumes it; nobody gets two letters). |
| A1C_SENT ledger (one Script Property) | ~2 KB | ~3 KB | 9 KB | OK |
| KI PDFs | 5 documents, 14 attachments | 11 documents, ~30 attachments | 25 MB per email | OK |
| Emails per Monday | 50 via the relay | ~110 | relay (Workspace) ~1,500/day | OK. **If the relay ever fails**, the fallback is the gmail account, capped at 100/day, and the Agent1C guard logs who was skipped. |
| ZL letter size | up to 97.7 KB | ~100–110 KB for the biggest zones | 102 KB | **at risk (E)** |
| Spreadsheet cells | 2.72 M (NIGHTLY_FORM_RAW 0.97 M) | +~0.25 M a week | 10 M per spreadsheet | **~7 months** (around May 2027). Not for November. |
| Trigger run time (gmail account) | not measured | AgentDuplicate ×2 per evening, each reading a bigger tab | 90 min/day on a consumer account | **unknown. Measure it.** |

## 5. Proposed fixes, in order

**F0 — Zackary, before Mon Nov 2 21:00 (2 min, no code).** In the Apps Script
editor, run `setupAllCcsmTriggers()` once. Don't run it while the chain is
going (Mon 21:00–Tue 01:00). It puts the 21:30 runAgent1A trigger back. Until
F1 ships, any watchdog restart of Agent1A deletes it again, so check the
trigger list after any Monday that shows a `LetterWatchdog RETRY … Agent1A`
row.

**F1 — The watchdog never deletes the weekly trigger (code; fixes A).**
- Restart Agent1A through its own one-shot handler, `runAgent1ARetry()` (which
  just calls `runAgent1A`), listed in `CCSM_CHAINED_HANDLERS`.
- Make `scheduleNext()` refuse to run on a handler that is in
  `CCSM_TRIGGER_SCHEDULE`, so this can't happen again.
- Have the Monday watchdog check that the runAgent1A weekly trigger exists,
  reinstall it if it doesn't, and log that.
- Add JS tests for all three.

**F2 — Agent1A starts the PDF job itself (code + one token from Zackary;
fixes B).** Right after it writes the REQUEST, Agent1A calls GitHub's
`workflow_dispatch` API for ki-pdfs.yml. A dispatched run starts in seconds;
the 10-13 dispatch built everything in 29 s. That fits inside Agent1C's 10 min.
- The cron stays as a backup, and the job no longer sits waiting for hours.
- This needs a fine-grained GitHub token, limited to this one repo with
  "Actions: write", saved as a Script Property. Only Zackary can make it; I'll
  write the click-by-click steps.
- The same call can dispatch the area-goals job Monday morning, removing its
  shrinking margin.

**F3 — Timings in the run log (code; makes C provable).** `logRun` gets a real
`Duration_Sec`, and Agent1A notes how long each phase took (WEEKLY_KI rebuild,
the reads, building, saving). The next stall then says where it happened.

**F4 — Lighter Agent1A (code; protects C at twice the size).**
- Agent1A reads NIGHTLY_FORM_RAW twice and DAILY_LOG twice. Read each once and
  share the result.
- Read only the last ~9 weeks of rows, not the whole tab, so it stops growing
  with history.
- This roughly halves its spreadsheet time, and keeps it flat as the mission
  doubles.

**F5 — Decision for Zackary: move Agent1A out of the nightly rush?**
- You chose to keep the 21:30 send (Q1, 10-06), so the default is to keep it
  and rely on F3 + F4, with the watchdog as the net. With F1 and F2 fixed, a
  killed first run costs about 10 minutes, not hours.
- If F3's timings show contention, move `runAgent3Evening` and AgentDuplicate's
  scheduled run to 22:00 on Mondays. That would leave 21:30 clear without
  changing the letter's time.
- Moving Agent1A itself to 22:15 is the other option. It is not my
  recommendation, because it changes the time the missionaries get the letter.

**F6 — The ZL letter stays under Gmail's limit (code; fixes E).**
- Agent1C measures each letter's HTML before sending, and logs the largest one
  each week.
- Over 95 KB, the "Todos los datos" table drops its 4-week history columns for
  that letter. The totals and ▲▼ stay.
- The exact trimming is your design call. I'll show you a render first.

**F7 — The PDFs read the form clock in the right zone (code; fixes D).**
`ki_ranking` converts the sheet's Denver timestamps to Santiago time before
comparing them with the cutoff, using the sheet's own time zone, not a fixed
3 h. I'll also sweep the Python side for other places that read form
timestamps as text, before Nov 1 moves the gap to 4 h. Setting the spreadsheet
itself to America/Santiago is the cleaner fix, but it touches every timestamp
the app reads, so it needs its own audit.

**F8 — A full-size dress rehearsal (Zackary + me).**
- *Before Nov 16:* render all ~110 letters locally against the whole roster
  set active, to check sizes and build time. Run the chain once in TEST_MODE
  (everything goes to TEST_INBOX_EMAIL) to check the 6-minute margins with real
  triggers.
- *Wed–Fri Nov 18–20:* repeat in TEST_MODE with the first real week of
  mission-wide forms, before the first real mission-wide letters on Mon Nov 23.

## 6. What this needs from Zackary

1. **F0 now:** run `setupAllCcsmTriggers()` before Monday.
2. **OK to build F1, F2, F3, F4, F6 (logging part) and F7.** Your part after
   that is pasting the .gs files and making the token for F2.
3. **F5:** keep 21:30 and measure first (my recommendation), or move something
   now.
4. **F6:** whether trimming the history columns is the right cut for large ZL
   letters.

## STATUS

**2026-10-28: F1, F2, F3, F4, the logging half of F6, and F7 BUILT.** Zackary
OK'd it, and said to keep 21:30 (F5 = measure first).

- **F1:** the watchdog restarts Agent1A through `runAgent1ARetry`
  (CCSM_LetterWatchdog.gs). `scheduleNext()` throws for any handler in
  CCSM_TRIGGER_SCHEDULE (CCSM_Helpers.gs). Every watchdog check reinstalls a
  missing Monday runAgent1A trigger and logs `LetterWatchdog REPAIRED`. The
  installer's builder is shared as `installScheduledTrigger_` (CCSM_Setup.gs).
- **F2:** `a1a_dispatchKiPdfJob_` (CCSM_Agent1A.gs) POSTs a
  `workflow_dispatch` for ki-pdfs.yml with `week_end`, when it writes the
  REQUEST, and again on a retry while the PDFs are not built. The token is the
  Script Property `GITHUB_DISPATCH_TOKEN`; without it the note says so and the
  late schedule stays the only builder. The cron is unchanged, as the backup.
- **F3:** Agent1A/1B/1C pass their real duration to `logRun` (Duration_Sec).
  Agent1A adds `Timings: config, WEEKLY_KI rebuild, PDF request, nightly forms
  read (N rows), nightly history, weekly KI, build, save`, and logs each lap to
  the execution log as it ends.
- **F4:** Agent1A caches DAILY_LOG, NIGHTLY_FORM_RAW and WEEKLY_KI for the
  run (one read each), and reads NIGHTLY_FORM_RAW only from 14 days before the
  oldest of its 8 weeks (`a1a_readNightlyTail_`). DAILY_LOG stays a full read:
  the consistency streak looks further back.
- **F6 (logging):** Agent1C notes `Largest letter: N KB (subject)`, and a
  WARNING when any letter is over 95 KB. Trimming the letter is still his
  design call.
- **F7:** ki_pdf_runner moves the cutoff onto the sheet's clock
  (`to_sheet_clock`, using the spreadsheet's own time zone) before `ki_ranking`
  compares it with the form stamps. The outbox and the PDF footer still say
  mission time. Swept: the other Python reads of form timestamps
  (queries.py's weekly submission week, and the nightly on-time check, whose
  English headers never match CCSM's forms) use only the DATE, so a few
  late-night forms can land a day early. Not changed. Setting the spreadsheet
  itself to America/Santiago needs its own audit.

Tests: JS 41 pass, the same 5 known failures as HEAD (same messages). New:
`tests/test_agent1a_nightly_tail.js` and `tests/test_agent1a_ki_dispatch.js`;
`test_letter_watchdog.js` has a part C. Python: `test_ki_pdf_runner.py` adds 2.

**Owed by Zackary:** paste CCSM_Helpers, CCSM_Setup, CCSM_LetterWatchdog,
CCSM_Agent1A, CCSM_Agent1B and CCSM_Agent1C into Apps Script. Make the GitHub
token and add the Script Property. Run `setupAllCcsmTriggers()` once
(not Mon 21:00–Tue 01:00). The ki-pdfs.yml / runner changes are live on push.

**Check on Tue Nov 3:** Agent1A's row has `Timings:` and `PDF job started`,
Agent1C has `KI PDFs attached` and `Largest letter`, and there is no
`LetterWatchdog RETRY` row. If there is a RETRY, the first run's Timings
(execution log) say where it stalled.
