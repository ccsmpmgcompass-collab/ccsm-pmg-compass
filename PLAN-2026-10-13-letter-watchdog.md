# PLAN: The weekly letters retry themselves (2026-10-13)

**Why.** Mon 2026-10-12, the first v2 send: `runAgent1A` started 21:27:38 and
was killed at Apps Script's 6-minute limit ("Exceeded maximum execution time").
Its last log line was at 21:28:13. The stall sat in reads that take 13.5 s on a
normal day (measured 10-13), so it was a one-off. A killed run writes no
AGENT_RUN_LOG row, so nothing noticed and 0 letters went out. Zackary re-ran it
by hand Tue 12:48: 48 sent, 0 errors, 11 PDFs. The same silent death hit
Agent1C on 28 Sep and 17 Aug. Nothing restarted the chain or said so.

## 1. Decisions (Zackary, 2026-10-13; do not re-ask)

1. **The chain restarts itself** from the step that died. Finished steps are
   never redone.
2. **It keeps trying until Tuesday 09:00** (mission time). A Tuesday letter
   beats no letter.
3. **Only Zackary is told** when it still has not gone out by then: one email
   to `AGENT_CONFIG.LETTER_ALERT_EMAIL`.
4. **A retry counts the forms that came in after the first try** (WEEKLY_KI is
   rebuilt again). A retried Agent1A keeps this week's PDF request and the
   PDFs already built from it, so no GitHub step is needed. The PDFs may
   differ from the letter by a late form or two.
5. **No double sends.** Agent1C remembers who got this week's letter and
   skips them on a restart.
6. **The President gets the mission KI PDF**, like the APs. He already gets
   the AP mission letter (since v2, 2026-10-12).
7. **The old mission report is retired.** It comes off the trigger schedule,
   the missed-run check and the Liderazgo help text. The file stays, unused,
   until the old-builder cleanup.

## 2. How it works

- **State.** One Script Property, `LETTER_CHAIN_STATE` = `{week, step, state,
  at, note}`, written by every step (`letterChainMark_`, CCSM_Helpers.gs).
  - `running`: the step started.
  - `scheduled`: the next step's one-shot trigger was made, or Agent1C is
    waiting for the PDFs.
  - `failed`: it threw and logged ERROR.
  - `done`: Agent1C's send loop finished.
- **The watchdog** (`CCSM_LetterWatchdog.gs`). It acts only between Monday
  21:30 and Tuesday 09:00 of the week being graded.
  - **This week done** → stop.
  - **In flight** (`running` < 7 min old, `scheduled` < 10 min old) → check
    again in 15 min.
  - **Otherwise** restart the furthest step whose input exists: Agent1B's
    payload → 1C, Agent1A's → 1B, neither → 1A. Log `LetterWatchdog RETRY`,
    check again in 15 min.
  - **Past Tuesday 09:00 and still not done** → one alert email, log ERROR,
    stop.
- **Triggers.**
  - Agent1A schedules the first check 10 min after it starts
    (`runLetterWatchdogRetry`, one-shot). Monday's death would have been
    caught at about 21:38.
  - A fixed weekly `runLetterWatchdog` (Monday 23:00) covers an Agent1A that
    never started at all.
  - Two handler names, because `scheduleNext` deletes every trigger of its
    function name.

## 3. Steps

- **W1. State + no double sends.** `letterChainMark_` in Helpers; 1A/1B/1C
  mark their state; Agent1C keeps a per-week sent ledger (`A1C_SENT_<week>`).
- **W2. The watchdog.** New `CCSM_LetterWatchdog.gs`, schedule rows, 1A's
  first check, the alert email.
- **W3. A retried 1A keeps this week's PDF request.**
- **W4. The President gets the mission PDF; the old report is retired.**
- **W5. Verify.** JS suite (baseline: 38 pass, 5 fail, the known five), pytest,
  a full render, then push.
  - **Zackary pastes:** CCSM_Helpers.gs, CCSM_Agent1A.gs, CCSM_Agent1B.gs,
    CCSM_Agent1C.gs, CCSM_Setup.gs, and the NEW CCSM_LetterWatchdog.gs.
  - **Then he runs `setupAllCcsmTriggers()`** (not mid-chain). It installs
    the watchdog and also the triggers owed since 10-05.
  - **Then Reboot** the app (help text + agent_runs.py).

## STATUS

- 2026-10-13: plan written; decisions 1–7 from Zackary.
- 2026-10-13: **W1–W4 built and verified.**
  - **JS suite:** 39 pass, 5 fail. The 5 are the known baseline, the same
    assertion text as at HEAD. The new `tests/test_letter_watchdog.js` covers
    every watchdog decision and a restarted 1C skipping who already has it.
    `test_agent1a_ki_request.js` covers a retry keeping the request and PDFs.
  - **pytest:** the touched tests pass (agent_runs, i18n, Traslados).
    - `test_nightly_weekly_trends` fails at HEAD too.
    - The Informes / report-period failures come from another session's
      uncommitted work in the same tree.
  - **Live-data render** (`render.js --now 2026-10-12T22:00`): all 48 letters
    are byte-identical to the pre-change render.
  - **To resend a week on purpose,** delete the Script Property
    `A1C_SENT_<week end>` first. Otherwise everyone is skipped as already sent.
  - **Still owed:**
    - `AGENT_CONFIG.LETTER_ALERT_EMAIL` row.
    - Push.
    - Zackary's paste + `setupAllCcsmTriggers()` + Reboot (§3 W5).
