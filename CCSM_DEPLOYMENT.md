# CCSM PMG Compass — Deployment Runbook

**Mission:** Chile Concepción South Mission (CCSM)
**Sheet:** `COMPASS_CCSM` (created by this runbook — it does not exist yet)
**Language:** Spanish · **Timezone:** `America/Santiago`
**Status when you start:** nothing has ever been deployed. Every file in this repo is written and tested, but no Google account has ever run any of it.

This document takes you from an empty Google account to a running system. It assumes **no programming knowledge**. You will copy and paste text, click menu items, and press a Run button. You will never write code.

Read the two gotchas below before you start. They are the two ways this deployment goes wrong.

---

## The two gotchas that break deployments

### Gotcha 1 — Editing a file in this repo does NOT change the live system

Apps Script only ever runs the code that is **pasted into its own online editor**. The `.gs` files sitting in this folder on the computer are the *source of truth for humans*; Google has never seen them.

- Every file has to be pasted in, by hand, once.
- If anyone later changes a `.gs` file in this folder — fixes a typo, adjusts a message — that change does **nothing** until someone re-pastes that file into the editor and saves.
- Likewise, if someone edits code *inside the Apps Script editor*, this folder is now out of date. Copy the change back.

There is no automatic sync in either direction. When something behaves like an old version, the first thing to check is whether the editor actually has the current paste.

### Gotcha 2 — The Apps Script project timezone must be set by hand, once

The agents mix two kinds of date work: some dates are formatted through the mission timezone (`getMissionTimezone()`, which reads `MISSION_TIMEZONE` from the sheet), and some week arithmetic uses the project's plain local calendar. If the Apps Script **project** timezone is left on the Google account default (usually a US timezone), derived week-end dates can land **a day off** — reports attach to the wrong week, and nothing errors out to tell you.

Setting `MISSION_TIMEZONE` in the sheet is **not** enough. You must also set the project timezone in Apps Script → Project Settings. This is Step 3.2 and it is not optional.



## Three decisions the mission has to make

These are **not** bugs and **not** things a programmer can decide for you. Each one is written out in full at the step where it actually matters, so you do not have to decide anything now — just know they are coming.

| # | Decision | Where it bites |
|---|---|---|
| 1 | **Who sends weekly-form reminders** — AgentEscalation (shipped default) or AgentReminder | [Step 9 · Decision 1](#decision-1--who-sends-weekly-form-reminders-weekly_reminder_owner) |
| 2 | **Should approved suggestions be emailed automatically** — currently not scheduled at all | [Step 9 · Decision 2](#decision-2--should-approved-suggestions-notify-automatically) |
| 3 | **Confirm the form-submit triggers survive a re-run** — needs one real check nobody could do offline | [Step 9 · Decision 3](#decision-3--confirm-form-submit-triggers-survive-re-running-the-installer) |

Decision 1 has a trap. Read it before you touch triggers.

## What you need before you start

- [ ] The CCSM Google account signed in (the account that will own the sheet, the forms and the script — `CCSM.PMG.Compass@gmail.com` is the address the system ships configured to use for test mail and as the sender).
- [ ] This folder open on the computer, so you can open the `.gs` files and copy their contents.
- [ ] A Gemini API key (free tier is fine) — needed for the Q&A agent and for leadership narrative text. You can deploy without it and add it later; the parts that need it simply log "not set" and skip.
- [ ] About 2 hours for Steps 1–7. Steps 8–10 (content review, triggers, go-live) happen later, after the mission has read the Spanish content.



---

# STEP 1 — Build the `COMPASS_CCSM` sheet

The sheet is built by a script, not by hand. That guarantees all 23 tabs, every header, all 99 area rows and all 42 config rows are exactly what the agents expect.

This step uses a **standalone** script project — one that is not attached to any spreadsheet. You will throw it away afterwards.

### 1.1 Create the builder project

1. Sign in to Google as the CCSM account.
2. Go to **script.google.com**.
3. Click **New project** (top left).
4. Rename it something like `CCSM Sheet Builder` by clicking "Untitled project" at the top.

### 1.2 Paste the two builder files

The editor starts with one file called `Code.gs` containing an empty `myFunction()`.

1. Open `CcsmData.gs` from this folder in a text editor. Select all, copy.
2. In Apps Script, click the **`Code.gs`** file, select everything in the editor, and paste over it. Rename that file to `CcsmData` (click the ⋮ next to the filename → Rename).
3. Click the **+** next to "Files" → **Script**. Name it `BuildCcsmSheet`.
4. Open `BuildCcsmSheet.gs` from this folder, copy all of it, and paste over the contents of the new file.
5. Press **Ctrl+S** (save).

Order matters: `BuildCcsmSheet` reads variables that `CcsmData` defines.

### 1.3 Run the builder

1. In the toolbar, open the function dropdown (it will say `buildCcsmSheet` or the name of another function) and select **`buildCcsmSheet`**.
2. Click **Run**.
3. Google will ask you to authorize. Click through: Review permissions → choose the CCSM account → "Google hasn't verified this app" → **Advanced** → **Go to (project name) (unsafe)** → **Allow**. This warning is expected for a script you wrote yourself.
4. Wait. It creates 23 tabs and then re-reads every one of them to check nothing was dropped.

### 1.4 Read the log

Open **Execution log** (bottom panel, or View → Logs). You should see:

```
COMPASS_CCSM created: https://docs.google.com/spreadsheets/d/...
VERIFY: all tabs & headers correct.
NEXT STEPS: ...
```

- [ ] The log says **`VERIFY: all tabs & headers correct.`**
  If it says `VERIFY WARNING: see fix log above`, **stop** and get help — do not continue on a sheet that failed verification.
- [ ] **Save the spreadsheet URL** from the log. You need it constantly from here on.

Open the sheet. It should be named `COMPASS_CCSM` and have 23 tabs. `MISSION_ORG` should be full of Chilean area names; `AGENT_CONFIG` should have a `Key`/`Value` list starting with `MISSION_NAME`.

> Re-running `buildCcsmSheet()` never edits an existing sheet — it creates a brand new one each time. If you run it twice by accident you get two sheets; delete the extra one and be careful which URL you keep.

You can now close and delete the builder project. It is not needed again.

---

# STEP 2 — Attach the two Spanish forms and rename their tabs

CCSM uses two Google Forms, both Spanish:

| Form | Title | Feeds tab |
|---|---|---|
| Nightly | `Informe Diario Misional` | `NIGHTLY_FORM_RAW` |
| Weekly | `Informe Semanal Misional` | `WEEKLY_FORM_RAW` |

### 2.1 If the forms do not exist yet

Build each one from its own standalone script project, the same way as Step 1:

- `DailyReportForm_ES.gs` → run `buildDailyReportFormES()`
- `WeeklyReportForm_ES.gs` → run `buildWeeklyReportFormES()`

**Use a separate project for each.** The two files both define helper functions with the same names (`setMeta_`, `verifyAndFix_`), so pasting them into one project makes one silently override the other.

Each builder logs the form's edit URL, its live URL, and the URL of a **new responses spreadsheet it creates for itself** (`Informe Diario Misional (Respuestas)` / `Informe Semanal Misional (Respuestas)`). That throwaway responses sheet is not `COMPASS_CCSM` — Step 2.2 moves the form off it.

Save the **live (published) URL** of each form. Those go into `AGENT_CONFIG` in Step 6.

### 2.2 Point each form's responses at `COMPASS_CCSM`

Do this once per form.

1. Open the form in edit mode.
2. Go to the **Responses** tab.
3. Use the responses-destination control (a spreadsheet icon / "Link to Sheets" / a ⋮ menu with "Select response destination") and choose **Select existing spreadsheet** → `COMPASS_CCSM`.

> **Not verified:** the exact wording and position of this control in the current Google Forms interface changes from time to time, and could not be confirmed from the code. Look for the green spreadsheet icon or a three-dot menu on the Responses tab. The outcome you want is: this form's responses land in `COMPASS_CCSM`. If the form is currently linked to its own builder-created responses sheet, you may need to **unlink** it first before you can link it to `COMPASS_CCSM`.

### 2.3 Rename the new tabs

Google Forms **always creates its own new tab** when you link it — it will not write into a tab you pre-made, and this is why the builder in Step 1 does not create `NIGHTLY_FORM_RAW` or `WEEKLY_FORM_RAW`.

In `COMPASS_CCSM` you will now see a new tab named after the form (e.g. `Respuestas de formulario 1`).

1. Right-click the tab created by the **nightly** form → **Rename** → `NIGHTLY_FORM_RAW` (exact spelling, all caps, underscores).
2. Right-click the tab created by the **weekly** form → **Rename** → `WEEKLY_FORM_RAW`.

Renaming is safe. The form keeps writing into the tab it created, whatever you call it.

- [ ] `COMPASS_CCSM` now has a `NIGHTLY_FORM_RAW` tab
- [ ] `COMPASS_CCSM` now has a `WEEKLY_FORM_RAW` tab

> **Expect very wide tabs with repeated column headers.** Both forms use one section per zone, so the raw tabs carry roughly ten copies of every question column, and each submission fills only its own zone's copies. That is by design; the agents coalesce identical headers and take the non-empty value. Do not delete the "empty" duplicate columns.

---

# STEP 3 — Create the bound script project and paste the agents

### 3.1 Open the script editor from the sheet

1. Open `COMPASS_CCSM`.
2. **Extensions → Apps Script**.

This creates a script project **bound** to this spreadsheet. Bound is essential — every agent calls `SpreadsheetApp.getActiveSpreadsheet()` and would have nothing to read otherwise. Never do this step from script.google.com.

Rename the project (click the title) to something like `COMPASS_CCSM Agents`.

### 3.2 Set the project timezone — DO THIS NOW, BEFORE PASTING

See Gotcha 2. This is the step people skip.

1. Click the **gear icon (Project Settings)** in the left sidebar.
2. Find **Time zone**.
3. Set it to **`(GMT-04:00) Santiago — America/Santiago`**.
4. Confirm it saved (navigate away and back).

- [ ] Project timezone reads `America/Santiago`

### 3.3 Paste all 21 files

For each file below, in this order:

1. Click **+** next to "Files" → **Script**
2. Name it exactly as in the "Name in editor" column (Apps Script adds `.gs` itself — do not type the extension)
3. Open the matching file from this folder, select all, copy
4. Paste over everything in the new editor file
5. Save (Ctrl+S)

The very first one replaces the starter `Code.gs`: paste `CcsmData.gs` into it and rename it to `CcsmData`.

| # | File in this folder | Name in editor | What it is |
|---|---|---|---|
| 1 | `CcsmData.gs` | `CcsmData` | Tab list, config rows, area roster, form question map — **must be first**; nearly every other file reads its variables |
| 2 | `CCSM_Helpers.gs` | `CCSM_Helpers` | Shared library every agent calls (sheet access, email, dates, Gemini) |
| 3 | `CCSM_AgentTestMode.gs` | `CCSM_AgentTestMode` | The TEST_MODE safety switch |
| 4 | `CCSM_AgentValidation.gs` | `CCSM_AgentValidation` | Form-row validation |
| 5 | `CCSM_Agent3.gs` | `CCSM_Agent3` | Nightly form → `DAILY_LOG`, missed-day alerts |
| 6 | `CCSM_Agent5A.gs` | `CCSM_Agent5A` | Daily dashboard + `WEEKLY_KI` |
| 7 | `CCSM_Agent5B.gs` | `CCSM_Agent5B` | Friday encouragement qualifier |
| 8 | `CCSM_Agent6.gs` | `CCSM_Agent6` | Friday encouragement emails |
| 9 | `CCSM_Agent1A.gs` | `CCSM_Agent1A` | Monday coaching — metrics |
| 10 | `CCSM_Agent1B.gs` | `CCSM_Agent1B` | Monday coaching — message selection |
| 11 | `CCSM_Agent1C.gs` | `CCSM_Agent1C` | Monday coaching — sends the emails |
| 12 | `CCSM_Agent2.gs` | `CCSM_Agent2` | Per-transfer goal recalibration (manual) |
| 13 | `CCSM_Agent4.gs` | `CCSM_Agent4` | Weekly system health check + self-heal |
| 14 | `CCSM_AgentScores.gs` | `CCSM_AgentScores` | Weekly area scores + `SCORE_CONFIG` setup |
| 15 | `CCSM_AgentReminder.gs` | `CCSM_AgentReminder` | NOTES reminders (+ optional weekly compliance) |
| 16 | `CCSM_AgentDuplicate.gs` | `CCSM_AgentDuplicate` | Duplicate nightly-submission detection |
| 17 | `CCSM_AgentEscalation.gs` | `CCSM_AgentEscalation` | Missed-report escalation to leaders |
| 18 | `CCSM_AgentQA.gs` | `CCSM_AgentQA` | Gemini Q&A + suggestions |
| 19 | `CCSM_SeedContent.gs` | `CCSM_SeedContent` | The 193 Spanish messages + 10 knowledge-base rows |
| 20 | `CCSM_Setup.gs` | `CCSM_Setup` | Triggers, smoke test, email preview |
| 21 | `CCSM_AgentMissionReport.gs` | `CCSM_AgentMissionReport` | Monday mission-wide numbers email for AP/MP |

**Do NOT paste into this project:** `BuildCcsmSheet.gs` (already used, standalone only), or any of the four form builders (`DailyReportForm.gs`, `DailyReportForm_ES.gs`, `WeeklyReportForm.gs`, `WeeklyReportForm_ES.gs`).

- [ ] All 21 files pasted and saved
- [ ] No red error markers in the editor

If the editor reports something like `X is not defined` when you later run a function, the usual cause is a file that was missed or pasted only partially. Compare the function list in the Run dropdown against this table.

---

# STEP 4 — Store the Gemini API key

The Gemini key is deliberately **not** kept in the spreadsheet — a spreadsheet gets shared with people who should not see an API key. It lives in Script Properties, which only the script can read.

1. In the Apps Script editor, click the **gear icon (Project Settings)**.
2. Scroll to **Script Properties** → **Add script property**.
3. Property: `GEMINI_API_KEY`
4. Value: your key
5. **Save script properties**.

- [ ] `GEMINI_API_KEY` saved in Script Properties

> There is **no** `GEMINI_API_KEY` row in the `AGENT_CONFIG` tab, and that is deliberate — the tab is built by a script (Step 1) and gets shared with mission leadership, so no cell exists for the key to leak into. Every place in the code that needs the key reads Script Properties, never the spreadsheet. If you are looking for somewhere to paste the key into the sheet, stop — Script Properties, above, is the only place it goes.

The model name *is* read from the sheet: `AGENT_CONFIG` → `GEMINI_QA_MODEL`, which ships as `gemini-2.5-flash`.

Without a key: the Q&A agent logs `GEMINI_API_KEY not set in Script Properties` and answers nothing, and leadership narrative paragraphs are skipped. Everything else — coaching emails, scores, reminders, alerts — works normally, because missionary-facing message text is **never** AI-generated. It is always picked verbatim from `MESSAGE_BANK`.

---

# STEP 5 — Seed the content and score weights

Run each of these from the Apps Script editor: pick the function in the dropdown, click **Run**, then read the Execution log. All three are zero-argument and safe to re-run.

### 5.1 `seedCcsmMessageBank()`

Writes 193 Spanish message rows into `MESSAGE_BANK` (75 coaching-strength, 75 coaching-growth, 40 Friday encouragement, 3 missed-days), then re-reads the tab to confirm the row count.

- [ ] Log says `MESSAGE_BANK written and verified — 193 rows.`

### 5.2 `seedCcsmKnowledgeBase()`

Writes 10 starter Spanish Q&A rows into `KNOWLEDGE_BASE`.

- [ ] Log says `KNOWLEDGE_BASE written and verified — 10 rows.`

*(`seedCcsmContent()` runs both in one click, if you prefer.)*

Both seeders **rewrite their tab from scratch** every run. If someone has hand-edited messages in the sheet, re-running wipes those edits. Make content edits in `CCSM_SeedContent.gs` and re-paste (Gotcha 1), not in the sheet.

### 5.3 `setupCcsmScoreConfig()`

Writes the default scoring weights into `SCORE_CONFIG` (two sections: per-metric weights, then effort/skill/KI blend).

Unlike the seeders this one is **skip-if-populated**: if `SCORE_CONFIG` already has data rows it logs `already populated ... Skipping.` and changes nothing. That is deliberate, so a re-run never discards weights the mission has tuned. To start over, clear the tab first.

- [ ] Log says `SCORE_CONFIG setup complete. N rows written.`

> The shipped weights are **starting defaults**, not mission policy. Leadership should look at them once real scores appear and retune directly in the `SCORE_CONFIG` tab (that is a normal sheet edit — no re-paste needed).

---

# STEP 6 — Fill in the blanks in `AGENT_CONFIG`

Open `COMPASS_CCSM` → `AGENT_CONFIG` tab. It has two columns, `Key` and `Value`. Fill the `Value` cell for each key below. Do not add, rename or reorder rows.

### Required — the smoke test fails without these

| Key | What to put |
|---|---|
| `SYSTEM_START_DATE` | The date the system goes live, as `YYYY-MM-DD`. Data before this date is ignored. |
| `TRANSFER_START_DATE` | Start date of the current transfer, `YYYY-MM-DD`. Used by goal recalibration. |
| `NIGHTLY_FORM_LINK` | The published (live) URL of `Informe Diario Misional` — appears as a clickable link in reminder and alert emails. |
| `WEEKLY_FORM_LINK` | The published (live) URL of `Informe Semanal Misional`. |

### Already filled — check, do not change

| Key | Ships as |
|---|---|
| `MISSION_NAME` | `Chile Concepción South Mission` |
| `MISSION_LANGUAGE` | `ES` |
| `MISSION_TIMEZONE` | `America/Santiago` |
| `MISSION_LOCALE` | `es_CL` |
| `TEST_MODE` | `TRUE` ← leave it until Step 10 |
| `TEST_INBOX_EMAIL` | `CCSM.PMG.Compass@gmail.com` |
| `SEND_FROM_EMAIL` | `CCSM.PMG.Compass@gmail.com` |
| `WEEKLY_REMINDER_OWNER` | `AGENT_ESCALATION` ← see Decision 1 in Step 9 |
| `MISSED_DAYS_LOOKBACK` | `3` |
| `GEMINI_QA_MODEL` | `gemini-2.5-flash` |
| `CONTACT_RATE_TARGET` / `MC_RATE_TARGET` / `LESSON_RATE_TARGET` / `CLOSE_RATE_TARGET` / `EFFORT_SCORE_TARGET` | `0.50` / `0.50` / `0.20` / `0.25` / `2.75` — mission-tunable targets |

### Optional — leave blank unless used

| Key | Note |
|---|---|
| `RELAY_1_URL`, `RELAY_2_URL`, `RELAY_SECRET` | The email-relay system. CCSM does not use it; blank is correct and the health check knows that. |
| `GOAL_*` (20 rows) | Mission-wide fallback goals per metric. Blank means the agents fall back to their own defaults. Fill later once real numbers exist. |

There is no `AGENT_CONFIG` row for the Gemini key — it goes in Script Properties only (Step 4).

### Missionary email addresses

Open the `MISSION_ORG` tab. Every area row has names and leadership flags filled in, and **both email columns blank**.

**No agent can email anybody until these are filled.** Everything else works — the sheet fills with data, scores compute, logs write — but no missionary receives anything, because there is nowhere to send it. `smokeTestPipeline()` warns about exactly this.

Fill `Companion1_Email` / `Companion2_Email` from the mission office roster. This does not have to be complete before you test — but it must be complete and verified before Step 10.

- [ ] All four required `AGENT_CONFIG` keys filled
- [ ] `MISSION_ORG` emails filled (or knowingly deferred)

---

# STEP 7 — Test it

Everything here happens with `TEST_MODE = TRUE`, so **no missionary can receive email**. Every message is redirected to `CCSM.PMG.Compass@gmail.com` and its subject is prefixed `[TEST]`.

> **What TEST_MODE does and does not do.** It redirects **email**. It does **not** redirect writes: running an agent in test mode writes real rows into `DAILY_LOG`, `SCORES`, `AUDIT_LOG` and the rest. That is fine and expected during setup, but it means the sheet is not pristine afterwards. (You may see a `setupTestTabs()` function in the dropdown, which creates parallel `TEST_*` tabs. The CCSM agents do not use those tabs — do not run it.)

### 7.1 `smokeTestPipeline()`

The pre-flight check. **Read-only: it sends no email and writes nothing.** Run it and read the Execution log.

It checks: the sheet opens by ID; all 23 tabs exist; the two raw form tabs exist; the required config keys are non-blank; the timezone and language are as expected; **the Apps Script project timezone matches `MISSION_TIMEZONE`**; whether `TEST_MODE` is on; the `WEEKLY_REMINDER_OWNER` value is valid; `MISSION_ORG` has active rows and reachable emails; `QUESTIONS_CONFIG`, `MESSAGE_BANK`, `SCORE_CONFIG`, `KNOWLEDGE_BASE` are populated; and the full trigger inventory, **including duplicate form-submit triggers**.

> **Gotcha 2 is now caught here.** The project-timezone check compares Project Settings against `MISSION_TIMEZONE` and reports an **ERROR** naming both values. That mismatch used to be invisible — it produced dates a day off with no error anywhere — so if you see it, fix Project Settings before doing anything else. It is not cosmetic and it will not "sort itself out".
>
> The duplicate-trigger check matters for the same reason: a form-submit handler installed **twice** fires twice on every submission, which means duplicate emails to a real missionary. Note that re-running `setupAllCcsmTriggers()` does **not** clear duplicates — the installer deliberately leaves form-submit triggers alone. The fix is `deleteAllCcsmTriggers()` first, then `setupAllCcsmTriggers()`.

The log ends with `=== smoke test: N error(s), M warning(s) ===`.

- [ ] **Exactly 2 errors, and both are about missing triggers.** No triggers exist yet — that happens in Step 9 — so `smokeTestPipeline()` will always report two `ERROR` lines here: `Missing trigger(s): ...` and `Missing form-submit trigger(s): ...`. Those two, and only those two, are expected right now; do not try to fix them. **Any other `ERROR` line must be fixed before going further** — each error message names the function to run or the tab to fix.

Warnings you should expect at this point, all correct:

- `TEST_MODE = TRUE — every email is redirected...` — that is the ship state.
- `No MISSION_ORG row has a companion email` — if you deferred emails.

### 7.2 `previewOneCoachingEmail()`

Sends **one** sample Spanish coaching email to the test inbox, built from real `MESSAGE_BANK` rows picked the same way the real agent picks them.

Its purpose is to let the mission judge **the words**, not the layout — the email is marked `MUESTRA` and its HTML is the preview's own, not the real Agent1C template.

- [ ] A `[TEST] Muestra: Entrenamiento Semanal — ...` email arrives at `CCSM.PMG.Compass@gmail.com`
- [ ] The Spanish reads correctly to a native speaker

### 7.3 Submit one real response to each form

This is the first time real data flows end to end, and it is the only way to catch a form/sheet mismatch.

1. Open the **live** nightly form. Pick a real zone and area. Enter obvious dummy numbers (1, 2, 3…). Submit.
2. Open the **live** weekly form. Same area. Submit.
3. In `COMPASS_CCSM`, confirm a new row appeared in `NIGHTLY_FORM_RAW` and in `WEEKLY_FORM_RAW`.

- [ ] A row landed in `NIGHTLY_FORM_RAW`
- [ ] A row landed in `WEEKLY_FORM_RAW`

If a row does not appear, the form is still linked to its own responses spreadsheet — go back to Step 2.2.

### 7.4 `runAgent3()` and check `DAILY_LOG`

Run `runAgent3()` from the editor.

- [ ] A row for your test area and today's date appears in `DAILY_LOG`
- [ ] **Every metric column has a value** — the numbers you typed, in the right columns. A blank or missing metric means the form headers and `QUESTIONS_CONFIG` disagree; stop and get that fixed rather than working around it.
- [ ] `LIVE_SNAPSHOT` has one row for the area
- [ ] A row appears in `AGENT_RUN_LOG` with `Agent3` and `SUCCESS`

### 7.5 `runAgent5A()` and check `WEEKLY_KI`

Run `runAgent5A()`.

- [ ] `WEEKLY_KI` has a row for your test area with the Real and Meta values you submitted
- [ ] `DASHBOARD_SUMMARY` is populated

### 7.6 One coaching-chain cycle

Run `runAgent1A()`. It does not do the whole job itself: it schedules `runAgent1B` roughly one minute later, which schedules `runAgent1C` roughly a minute after that. Google is not punctual about these one-shot triggers, so **wait about five minutes** before checking.

- [ ] `AGENT_RUN_LOG` shows Agent1A, then Agent1B, then Agent1C
- [ ] `[TEST]`-prefixed coaching emails arrive at the test inbox
- [ ] `FEEDBACK_HISTORY` records which message went to which area

### 7.7 Optional spot checks

Each is zero-argument and safe under `TEST_MODE`:

| Function | What it does |
|---|---|
| `runAgentScores()` | Fills `SCORES` for the last completed week |
| `runAgent4()` | Full health check → emails a Spanish system report |
| `verifyTestModeSetup()` | Prints `TEST_MODE` / `TEST_INBOX_EMAIL` for a quick confirmation |
| `runAgent2()` | Goal recalibration — writes `GOAL_RECALIBRATION`. Never scheduled; run once per transfer by hand. |

### 7.8 Clean up the test data

Before go-live, delete the dummy rows you created: the test rows in `NIGHTLY_FORM_RAW` and `WEEKLY_FORM_RAW`, and the rows the agents derived from them in `DAILY_LOG`, `LIVE_SNAPSHOT`, `WEEKLY_KI`, `SCORES` and `FEEDBACK_HISTORY`. Leave the log tabs alone — they are a useful record.

---

# STEP 8 — Content review gate (blocks go-live)

**`TEST_MODE` must stay `TRUE` until this is signed off.** This is a hard gate, not a formality.

The seeded content banks — plus the hardcoded leadership messages — are listed in **`CONTENT_REVIEW.md`** in this folder. Selection from the banks is *pick-not-generate*: the agents choose a row by ID and send it verbatim. Nothing in the banks is invented at send time.

> **`CONTENT_REVIEW.md` used to claim it listed every missionary-facing word. It did not,** and that false claim is what hid the problem in 8.3 below. The banks are only part of the outgoing text: individual agents also build subjects and bodies from hardcoded Spanish templates. The leadership messages are now included; roughly 27 reminder, escalation, validation and duplicate templates are still **not** listed and still want a Spanish read.

**Budget for this step: 4–6 hours, one Spanish speaker, one sitting.** Scripture texts 45–90min · native pass 60–90min · leadership scriptures 60–90min · template polish 60–90min.

Three things must happen before go-live.

### 8.1 Fill in the scripture text — 193 of 193 rows ship blank

Every message row has a scripture **reference** but an empty **`Scripture_Text`** cell. This is deliberate: nobody would invent the wording of Spanish LDS scripture, and a plausible-sounding paraphrase would be far worse than a blank. The agents render a blank verse cleanly — they simply show the reference.

The 193 blanks resolve to only **20 distinct references** (listed with their row counts in `CONTENT_REVIEW.md`). Fill those 20 from the real Spanish edition and every row is covered.

Because the seeders rewrite `MESSAGE_BANK` from scratch, put the verse text into **`CCSM_SeedContent.gs`** and re-paste + re-run `seedCcsmMessageBank()` (Gotcha 1) — not straight into the sheet, or the next seed run erases it. After editing the `.gs`, regenerate the review document with `node tools/gen_content_review.js` so the two cannot drift.

- [ ] All 20 distinct scripture references filled with exact Spanish-edition wording
- [ ] `seedCcsmMessageBank()` re-run and `MESSAGE_BANK` shows the verse text

### 8.2 Native-speaker review of the Spanish

The Spanish in all 193 messages and 10 knowledge-base rows was **model-written**. It is grammatical but has never been read by a native Chilean speaker. Word choice a reviewer should specifically rule on includes *paradero* and *amigos* (both flagged in `CONTENT_REVIEW.md`).

- [ ] A native Spanish speaker has read every row in `CONTENT_REVIEW.md`
- [ ] Mission leadership has approved the tone and the doctrine
- [ ] Any corrections were made in `CCSM_SeedContent.gs`, re-pasted, re-seeded, and `CONTENT_REVIEW.md` regenerated

### 8.3 Verify the 10 leadership scriptures — these are NOT blank

This one is different from 8.1, and more urgent. The ten leadership messages — now in the **`LEADERSHIP_MESSAGE_BANK`** sheet tab (formerly hardcoded in `CCSM_Agent1C.gs` as `_LEADERSHIP_MSGS`) — ship with their scripture text **already written**, and that text was written by a model, not copied from the official Spanish edition. It is exactly the fabrication the 193 blank rows exist to avoid, and it escaped the gate only because it lived in an agent file rather than the seed content.

**At least two are attached to the wrong verse.** The text printed under `D. y C. 4:4-5` is actually D&C 4:2; `D. y C. 11:21` carries something else again. These messages go to zone leaders, district leaders, APs and **the mission president**.

All ten are now listed in `CONTENT_REVIEW.md` under *MENSAJES DE LIDERAZGO*, each flagged for verification. For every one: confirm the **reference** is right, then confirm the **wording** against the official Spanish edition. Six of them also carry *Predicad Mi Evangelio* page numbers taken from the **English** edition — check those too.

**Corrections now go directly in the `LEADERSHIP_MESSAGE_BANK` sheet tab — edit the `Scripture`/`Scripture_Text`/`PMG_Page` columns, no code deploy or re-paste needed.** `CCSM_Agent1C.gs`'s `a1c_pickRelevantLeadershipMsg_` caller still withholds those three columns from the rendered letter regardless of what they say — that gate has to be lifted separately (see the citation-withholding note at the render call site in `CCSM_Agent1C.gs`) once every row has been verified. `Theme`/`Subject_Line`/`Body_Text` are already safe to edit any time.

- [ ] All 10 leadership scripture **references** verified
- [ ] All 10 leadership scripture **texts** verified word-for-word against the Spanish edition
- [ ] The 6 PMG page numbers checked against the Spanish edition
- [ ] `CCSM_Agent1C.gs` re-pasted if anything changed

**Signed off by: ______________________  Date: ____________**

---

# STEP 9 — Decisions, then install the triggers

Until now nothing has run on its own; you have pressed Run every time. This step makes the system autonomous. Make the three decisions **first** — two of them change what you do here.

### 9.0 — ⚠️ Read this before you run `setupAllCcsmTriggers()` for any reason

Several of the steps below — Decision 1's "switch to `AGENT_REMINDER`" path, Decision 3's check, and 9.1 itself — end with an instruction to run `setupAllCcsmTriggers()`. Before you run it, for any reason, know this:

The Sunday coaching chain schedules its own follow-on triggers (`runAgent1B`, `runAgent1C`) as one-shot "in a few minutes" jobs. `setupAllCcsmTriggers()`'s sweep removes any pending one-shot along with everything else. Running the installer on a **Sunday evening while the chain is in flight** drops that week's coaching emails. Nothing is corrupted — the chain just stops — but that week's missionaries get nothing.

**Install triggers on a weekday morning.** If you must fix something on a Sunday night, wait for the chain to finish (watch `AGENT_RUN_LOG` for Agent1C) or accept losing that week.

### Decision 1 — Who sends weekly-form reminders (`WEEKLY_REMINDER_OWNER`)

**The choice.** Two different agents can email companionships who have not submitted the weekly form, and both build the *same* Spanish subject line (`Recordatorio: Informe Semanal — <mission>`). Exactly one must own the job.

| Option | Behaviour |
|---|---|
| **`AGENT_ESCALATION`** *(shipped default)* | Staged, with leadership follow-up: Monday reminder 1 → Tuesday reminder 2 → Wednesday escalate to the District Leader. |
| **`AGENT_REMINDER`** | Simpler: one reminder per non-submitting area per week, no leader escalation. |
| **`BOTH`** | Gate off — **both agents send**. Every non-submitting companionship gets nagged twice on Monday by two different agents. This has actually happened on the mission system this one was forked from. Do not choose it. |

**⚠️ THE TRAP — read this before choosing `AGENT_REMINDER`.**
`AgentReminder`'s weekly-compliance check only acts on **Monday or Tuesday**, but the shipped schedule fires `runAgentReminder` on **Sunday at 6 PM**. On the shipped schedule that check can never run. So choosing `AGENT_REMINDER` **and changing nothing else silently disables weekly reminders entirely** — no error, no log line, no reminders, ever. This is the single reason `AGENT_ESCALATION` is the default.

**What to do:**

- **To keep the default (recommended):** nothing. `AGENT_CONFIG` → `WEEKLY_REMINDER_OWNER` already reads `AGENT_ESCALATION`. `runAgentEscalation` runs daily at 7 AM, so it reaches its Monday/Tuesday/Wednesday stages normally.
- **To switch to `AGENT_REMINDER`:** you must do **both** of these, or you get no reminders at all.
  1. Set `AGENT_CONFIG` → `WEEKLY_REMINDER_OWNER` = `AGENT_REMINDER`.
  2. **Move the `runAgentReminder` trigger to Monday.** Edit the `runAgentReminder` row in `CCSM_TRIGGER_SCHEDULE` (top of `CCSM_Setup.gs`) from `weekDay: 'SUNDAY'` to `weekDay: 'MONDAY'`, re-paste the file, and re-run `setupAllCcsmTriggers()`.

  `smokeTestPipeline()` warns you if you do step 1 without step 2 — but only if someone runs it and reads the warning. Do not rely on that.

  Either way, `AgentReminder`'s Sunday trigger still does its other, unrelated job (NOTES reminders), so do not simply delete it.

- [ ] **Decision 1 made.** `WEEKLY_REMINDER_OWNER` = ______________ (and if `AGENT_REMINDER`, the trigger was moved to Monday: ☐)

### Decision 2 — Should approved suggestions notify automatically?

**The choice.** `notifyAcceptedSuggestions()` emails the COMPASS inbox when a missionary suggestion is finally approved in `SUGGESTIONS_REVIEW`. It used to run on a **10-minute poll** — about 144 executions a day to service a queue that sees a handful of items a week. It is now **deliberately not scheduled at all**.

| Option | Result |
|---|---|
| **Leave it unscheduled** *(shipped state)* | Nobody is emailed when a suggestion is approved. The function still exists and is zero-argument, so anyone can run it by hand from the editor. |
| **Schedule it** | Add one row to `CCSM_TRIGGER_SCHEDULE` in `CCSM_Setup.gs`, e.g. `{ fn: 'notifyAcceptedSuggestions', everyDays: 1, hour: 8, describe: 'Daily 8:00 AM' }`, re-paste, re-run `setupAllCcsmTriggers()`. A daily run is ample. |

**Do not** re-enable it by running the old `setupSuggestionNotifyTrigger()` from the dropdown — that function is now a shim that just converges the whole schedule, and the 10-minute poll is not coming back.

- [ ] **Decision 2 made.** Automate suggestion notifications: ☐ no (default)  ☐ yes, scheduled daily at ______

### Decision 3 — Confirm form-submit triggers survive re-running the installer

**Why you are being asked.** `setupAllCcsmTriggers()` deliberately sweeps away every *time-based* trigger before installing the schedule, while leaving the two *form-submit* triggers alone. Telling those two kinds apart depends on a Google API call (`trigger.getEventType()`) that the offline test suite can only imitate. Sixteen test files say it works; no real Google project has ever confirmed it.

**One real check settles it forever.** Do it now, right after 9.1:

1. Run `setupAllCcsmTriggers()`.
2. Open **Triggers** (alarm-clock icon, left sidebar) and confirm `onNightlyFormSubmit` and `onQAFormSubmit` are both listed.
3. Run `setupAllCcsmTriggers()` **a second time**.
4. Open Triggers again.

- [ ] **Decision 3 checked.** After the second run, `onNightlyFormSubmit` and `onQAFormSubmit` are **still present** and appear **exactly once each**.

If either disappeared, or you now see two of one: re-run `setupAllCcsmTriggers()` (it is idempotent for the time-based ones) and report it — the sweep is misclassifying trigger types and needs a code fix before go-live.

### 9.1 Run `setupAllCcsmTriggers()`

This is the **only** trigger installer anyone should ever need. It is safe to re-run, and re-running is how you repair a schedule that has drifted.

It installs 10 scheduled triggers plus the 2 form-submit triggers:

| Function | When (Santiago) | Purpose |
|---|---|---|
| `runAgent3` | Daily 6:00 AM | Nightly refresh + missed-day alerts |
| `runAgent3Evening` | Daily 9:00 PM | Second daily refresh |
| `runAgentEscalation` | Daily 7:00 AM | Escalation systems 1 and 2 |
| `runAgentDuplicate` | Daily 9:30 PM | Duplicate-submission sweep |
| `runAgent5B` | Friday 12:00 PM | Friday encouragement (chains Agent6) |
| `runAgentReminder` | Sunday 6:00 PM | NOTES reminders |
| `runAgent1A` | Sunday 9:00 PM | Sunday coaching (chains 1B → 1C) |
| `runAgent5A` | Daily 12:00 PM | Dashboard summary + `WEEKLY_KI` |
| `runAgentScores` | Monday 12:05 AM | Weekly area scores |
| `runAgent4` | Monday 7:00 AM | System health check + self-heal |
| `onNightlyFormSubmit` | on submit | Validation + duplicate detection |
| `onQAFormSubmit` | on submit | Question / suggestion handling |

`runAgent2` (goal recalibration) is intentionally **not** scheduled — it is a per-transfer judgement call the mission president signs off on, run by hand once per transfer.

### 9.2 Never run the other installers

The Run dropdown still lists older per-agent installers: `setupReminderTrigger`, `setupEscalationTriggers`, `setupSuggestionNotifyTrigger`, `setupAgentDuplicateTrigger`, `setupQAFormTrigger`, `setupAgentScoresTrigger`, `setupQA`.

They exist for historical reasons and fall into two groups. `setupReminderTrigger`, `setupEscalationTriggers` and `setupSuggestionNotifyTrigger` are delegating shims — each just converges the whole schedule by calling `setupAllCcsmTriggers()` instead of installing anything of its own. `setupAgentDuplicateTrigger`, `setupQAFormTrigger`, `setupAgentScoresTrigger` and `setupQA` install their own single trigger directly (delete-then-recreate); `setupAllCcsmTriggers()` itself calls the first two of those to create the form-submit triggers, so they cannot delegate without recursing. Either way, misclicking one from the dropdown is idempotent and does not corrupt the schedule — but **the rule is still simple: use `setupAllCcsmTriggers()` and nothing else.**

One exception worth knowing: `setupQA()` also writes a header row into the `SUGGESTIONS` tab (the builder leaves that tab empty), installs the `onQAFormSubmit` trigger, and re-checks that `KNOWLEDGE_BASE` has entries. It is idempotent and harmless. Run it once if you want the `SUGGESTIONS` tab labelled; otherwise the agent appends rows there regardless.

### 9.2b The Q&A form does not exist yet

`onQAFormSubmit` handles a **third**, separate Google Form — a Spanish "question or suggestion" form. **There is no builder for it in this repo**, and the mission has never created it. Installing the trigger is harmless: the handler fires for every form linked to the sheet and immediately ignores any submission that is not a question/suggestion.

So until someone builds that form, `CCSM_AgentQA.gs` simply never has anything to do. This is a known gap, not a fault. Whoever builds the form must match the field order the handler expects:

| Field | Question |
|---|---|
| 0 | Timestamp (automatic) |
| 1 | ¿Es una pregunta o una sugerencia? |
| 2–4 | Nombre / Correo / Mensaje *(sección de sugerencia)* |
| 5–7 | Nombre / Correo / Mensaje *(sección de pregunta)* |

> **Not verified:** that field order was read from the handler's own documentation in `CCSM_AgentQA.gs`. It has never been checked against a real CCSM Q&A form, because no such form exists. Test one submission end to end when the form is built.

### 9.3 Verify

Run `smokeTestPipeline()` again.

- [ ] `All 10 scheduled triggers installed.`
- [ ] `Both form-submit triggers installed (onNightlyFormSubmit, onQAFormSubmit).`
- [ ] No `Duplicate trigger:` warnings
- [ ] No `Unrecognized trigger handler installed:` warnings
- [ ] The only remaining warning about live mail is the expected `TEST_MODE = TRUE` one

Then **let it run for at least one full week in test mode.** Every email goes to the test inbox. Read them. Watch `AGENT_RUN_LOG` fill up. This week costs nothing and catches the problems no checklist predicts.

---

# STEP 10 — Go live

Do not do this step until every box below is ticked. After it, real missionaries receive real email.

- [ ] Step 8 content gate signed off — scripture text filled, native-speaker review done
- [ ] `MISSION_ORG` emails filled in **and verified** — spot-check a handful against the office roster. A wrong address means a companionship silently never hears from the system.
- [ ] The system has run a full week in test mode with no errors in `AGENT_RUN_LOG`
- [ ] Mission leadership has read actual sample emails from the test inbox and approved them
- [ ] `smokeTestPipeline()` reports **0 errors**
- [ ] Someone has told the missionaries this is starting

### Flip the switch

Run **`disableTestMode()`** from the Apps Script editor.

It sets `AGENT_CONFIG` → `TEST_MODE` = `FALSE`, logs `System is now LIVE`, and records the change in `AUDIT_LOG`.

- [ ] Log says `disableTestMode: TEST_MODE set to FALSE. System is now LIVE.`
- [ ] `AGENT_CONFIG` → `TEST_MODE` reads `FALSE`
- [ ] `smokeTestPipeline()` now warns `TEST_MODE = FALSE — emails go to REAL missionaries and leaders.`

### If something goes wrong

Run **`enableTestMode()`** immediately. Every subsequent email is redirected back to the test inbox. It takes effect on the next agent run — it cannot recall mail already sent.

To stop everything entirely, run **`deleteAllCcsmTriggers()`**. That removes all triggers including the two form-submit ones; forms still collect responses, but no agent processes them and nothing is emailed. `setupAllCcsmTriggers()` puts it all back.

### First live week

- [ ] Day 1: check `AGENT_RUN_LOG` — `runAgent3` ran at 6 AM Santiago time, status `SUCCESS`
- [ ] Day 1: confirm the 6 AM run really was 6 AM *Santiago* (Gotcha 2 — a wrong project timezone shows up here first)
- [ ] Monday: `runAgent4`'s health report arrives and is clean
- [ ] Monday: `SCORES` has rows for the completed week
- [ ] Sunday+1: coaching emails went out, and a missionary confirms receiving one



---

# Design-spec testing checklist

From the "Safety & testing" section of `docs/superpowers/specs/2026-07-11-ccsm-sheet-and-agents-design.md`. Every item restated as something you can tick off, with where in this runbook it happens.

- [ ] **Ships with `TEST_MODE = TRUE`** → all email goes to `TEST_INBOX_EMAIL` until deliberately flipped. *(Verify in Step 6; flipped in Step 10.)*
- [ ] **No triggers exist until you run the `CCSM_Setup.gs` installer.** *(Step 9. Before then, `smokeTestPipeline()` reporting missing triggers is correct.)*
- [ ] **Builder verify pass is clean** — `buildCcsmSheet()` logged `VERIFY: all tabs & headers correct.` *(Step 1.4.)*
- [ ] **Smoke test — one test row to each form.** Submit one nightly and one weekly response. *(Step 7.3.)*
- [ ] **Smoke test — run Agent3 and Agent5A.** The rows land in `DAILY_LOG` and `WEEKLY_KI`. *(Steps 7.4, 7.5.)*
- [ ] **Smoke test — every metric maps.** No blank or missing metric key in `DAILY_LOG` / `WEEKLY_KI` for the test row. *(Step 7.4. This is the check that catches a form/`QUESTIONS_CONFIG` mismatch, and the one people skim past.)*
- [ ] **Missed-days preview.** `runAgent3()` also runs the missed-day alert pass; confirm any `[TEST]` alert email it produces reads correctly in Spanish. *(Step 7.4.)*
- [ ] **One coaching-chain cycle in test mode, Spanish email inspected.** `runAgent1A()` → wait → 1B → 1C; read the resulting email. *(Step 7.6, plus `previewOneCoachingEmail()` in 7.2 for the message text alone.)*
- [ ] **Provo boundary respected.** Nothing in this deployment touches the Utah Provo `COMPASS_Main` sheet or its scripts. They are separate Google files owned by a separate account; this runbook never opens them.



---

# Reference

## Every function you may be told to run

All of these take **no arguments**, because the Apps Script Run button cannot pass any and there is no console. Anything not on this list should not be run from the dropdown.

### In the standalone builder projects

| Function | File | Effect |
|---|---|---|
| `buildCcsmSheet()` | `BuildCcsmSheet.gs` | Creates a **new** `COMPASS_CCSM` spreadsheet. Never edits an existing one. |
| `buildDailyReportFormES()` | `DailyReportForm_ES.gs` | Creates `Informe Diario Misional` + its own responses sheet |
| `buildWeeklyReportFormES()` | `WeeklyReportForm_ES.gs` | Creates `Informe Semanal Misional` + its own responses sheet |

### In the bound project — setup

| Function | Effect | Re-runnable? |
|---|---|---|
| `seedCcsmMessageBank()` | Writes 193 Spanish message rows | Yes — **overwrites** the tab |
| `seedCcsmKnowledgeBase()` | Writes 10 Q&A rows | Yes — **overwrites** the tab |
| `seedCcsmContent()` | Both of the above | Yes — overwrites both |
| `setupCcsmScoreConfig()` | Writes default scoring weights | Yes — **skips** if already populated |
| `setupAllCcsmTriggers()` | Converges all triggers to the schedule | Yes — this is the intended repair action |
| `deleteAllCcsmTriggers()` | Removes every trigger, form-submit ones included | Yes |

### In the bound project — checks and safety

| Function | Effect |
|---|---|
| `smokeTestPipeline()` | Read-only pre-flight. Sends nothing, writes nothing. |
| `previewOneCoachingEmail()` | Sends one sample coaching email to the test inbox |
| `verifyTestModeSetup()` | Prints `TEST_MODE` / `TEST_INBOX_EMAIL` |
| `enableTestMode()` | `TEST_MODE = TRUE` — redirects all mail to the test inbox |
| `disableTestMode()` | `TEST_MODE = FALSE` — **goes live** |

### In the bound project — agents you can run by hand

`runAgent1A`, `runAgent1B`, `runAgent1C`, `runAgent2`, `runAgent3`, `runAgent3Evening`, `runAgent4`, `runAgent5A`, `runAgent5B`, `runAgent6`, `runAgentScores`, `runAgentReminder`, `runAgentDuplicate`, `runAgentEscalation`, `notifyAcceptedSuggestions`.

`onNightlyFormSubmit` and `onQAFormSubmit` are the two form-submit handlers. They expect an event from Google and should be left to their triggers, not run from the dropdown.

## The 23 tabs

| Tab | Filled by | Notes |
|---|---|---|
| `MISSION_ORG` | Builder | 99 area rows, names + leadership flags. **Email columns blank — you fill them.** |
| `AGENT_CONFIG` | Builder | 42 key/value rows; 4 required blanks you fill (Step 6) |
| `QUESTIONS_CONFIG` | Builder | Maps Spanish form headers to metric keys. Do not hand-edit. |
| `MESSAGE_BANK` | `seedCcsmMessageBank()` | 193 Spanish messages |
| `KNOWLEDGE_BASE` | `seedCcsmKnowledgeBase()` | 10 Q&A rows |
| `SCORE_CONFIG` | `setupCcsmScoreConfig()` | Weights — mission-tunable in the sheet |
| `GOALS_CONFIG` | You (optional) | Per-area goals |
| `TRANSFER_SCHEDULE` | You | Transfer dates; needed by `runAgent2` |
| `NIGHTLY_FORM_RAW` | Google Forms | Created on attach; you rename it (Step 2.3) |
| `WEEKLY_FORM_RAW` | Google Forms | Created on attach; you rename it |
| `DAILY_LOG` | Agent3 | Headers written by the agent on first run |
| `LIVE_SNAPSHOT` | Agent3 | One row per area |
| `WEEKLY_KI` | Agent5A | Weekly key indicators, Real + Meta |
| `DASHBOARD_SUMMARY` | Agent5A | |
| `WEEKLY_BREAKDOWNS` | Agent1C | |
| `SCORES` | AgentScores | |
| `GOAL_RECALIBRATION` | Agent2 | |
| `FEEDBACK_HISTORY` | Agent1C | Which message went to which area — prevents repeats |
| `ENCOURAGEMENT_HISTORY` | Agent5B / Agent6 | |
| `AGENT_RUN_LOG` | All agents | **First place to look when something is wrong** |
| `AUDIT_LOG` | Several agents | Per-event trail |
| `MISSING_LOG` | Agent3 | |
| `SUGGESTIONS` / `SUGGESTIONS_REVIEW` | AgentQA | |
| `NOTES` | The mission | Notes + reminders |

*(`NIGHTLY_FORM_RAW` and `WEEKLY_FORM_RAW` are not part of the 23 — they are created by Google Forms, which brings the live sheet to 25 tabs.)*

## Troubleshooting

| Symptom | Most likely cause |
|---|---|
| A code change had no effect | The editor was never re-pasted. **Gotcha 1.** |
| Agents run at the wrong hour; week-end dates are a day off | Project timezone is not `America/Santiago`. **Gotcha 2.** |
| `X is not defined` when running a function | A file was missed or half-pasted in Step 3.3 |
| Form responses never appear in `COMPASS_CCSM` | The form is still linked to its own responses sheet (Step 2.2) |
| `DAILY_LOG` rows appear with blank metrics | Form question headers and `QUESTIONS_CONFIG` disagree — do not work around this |
| No email arrives anywhere | `MISSION_ORG` email columns are blank |
| Email arrives only at the test inbox | `TEST_MODE = TRUE`. Correct until Step 10. |
| Companionships get reminded twice | `WEEKLY_REMINDER_OWNER` = `BOTH`. See Decision 1. |
| No weekly reminders at all | `WEEKLY_REMINDER_OWNER` = `AGENT_REMINDER` with the trigger still on Sunday. **The Decision 1 trap.** |
| Nobody is told when a suggestion is approved | Expected — `notifyAcceptedSuggestions` is unscheduled. Decision 2. |
| An agent stopped running | Check **Triggers** in the editor, then re-run `setupAllCcsmTriggers()` |
| Coaching emails missing for one week | Someone ran the trigger installer mid-chain on Sunday night (Step 9.0) |
| Gemini answers nothing | `GEMINI_API_KEY` missing from Script Properties (Step 4) — note it is **not** read from the sheet |

## Related documents

| File | What it is |
|---|---|
| `CONTENT_REVIEW.md` | Every missionary-facing word. **The Step 8 launch gate.** |
| `docs/superpowers/specs/2026-07-11-ccsm-sheet-and-agents-design.md` | Why the system is built this way |
| `New_Mission_Setup_Guide.md` | The older, broader guide for standing up *any* new mission, including the Streamlit dashboard. **Its Step 6 builds the CCSM sheet by duplicating the Provo sheet — that approach was replaced by `buildCcsmSheet()`. Where the two disagree about CCSM, this runbook wins.** Its dashboard sections (Steps 2–3, 9) are still the reference for work that is out of scope here. |
| `tools/gen_content_review.js` | Regenerates `CONTENT_REVIEW.md` from `CCSM_SeedContent.gs` |



---

# What this runbook could not verify

Everything in this document was checked against the actual code in this folder — file names, paste order, function names, whether each function takes arguments, config keys, tab names, log messages. The list below is what could **not** be checked, and is flagged inline where it appears. If any of it turns out differently in practice, correct this file.

1. **The Google Forms response-destination click path (Step 2.2).** Google changes this interface periodically and it cannot be read from code. The document describes the outcome you want and where to look, rather than inventing a confident sequence of clicks.
2. **The Google authorization dialog wording (Step 1.3).** Google revises these screens; the described route ("Advanced" → "Go to … (unsafe)") is the long-standing one for unverified personal scripts, but the exact labels may differ.
3. **Whether form-submit triggers survive a re-run of `setupAllCcsmTriggers()` (Decision 3).** The distinction depends on a Google API (`trigger.getEventType()`) that the offline test suite can only imitate. The runbook makes confirming it a required, explicit check the operator performs once.
4. **The Q&A form's field order (Step 9.2b).** Documented from the handler's own comments; there is no Q&A form in existence to check it against.
5. **Every agent's behaviour against real Google infrastructure.** All 16 test files pass, but they run against a Node stand-in for Google Apps Script. Nothing in this system has ever run on Google. That is the whole reason Steps 7 and 9 insist on a real test submission and a full week in `TEST_MODE` before go-live.

