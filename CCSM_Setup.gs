/**
 * ============================================================
 * CCSM_Setup.gs — Project triggers, smoke tests, operator entry points
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Forked in spirit from docs/Setup.gs in PMG-Compass (Provo), which carries
 * the same "one file that installs every trigger" role. The schedule itself
 * is CCSM's own — see the table below — and every hour is MISSION-LOCAL, not
 * Provo-local.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * REQUIRED ONE-TIME MANUAL STEP — PROJECT TIMEZONE
 * ─────────────────────────────────────────────────────────────────────────
 * Open the bound Apps Script project (COMPASS_CCSM -> Extensions -> Apps
 * Script) -> Project Settings -> Time zone, and set it to:
 *
 *     (GMT-04:00) Santiago  —  America/Santiago
 *
 * Every trigger created below ALSO pins .inTimezone(getConfig('MISSION_TIMEZONE')),
 * so the schedule is correct even if the project setting is wrong — but the
 * Apps Script execution log, Logger timestamps and the trigger UI all read
 * from the PROJECT setting, so leaving it on the account default makes every
 * on-call diagnosis read hours off. Set it.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * PROJECT TRIGGER SCHEDULE (all times America/Santiago)
 * ─────────────────────────────────────────────────────────────────────────
 *   runAgent3            Daily     6:00 AM   nightly refresh + missed-day alerts
 *   runAgent3Evening     Daily     9:00 PM   second daily refresh
 *   runAgent5A           Daily    12:00 PM   dashboard summary + WEEKLY_KI
 *   runAgent1A           Monday    9:15 PM   Monday coaching (chains 1B -> 1C)
 *   runAgent5B           Friday   12:00 PM   Friday encouragement (chains Agent6)
 *   runAgentReminder     Sunday    6:00 PM   NOTES reminders (+ weekly compliance, see below)
 *   runAgentDuplicate    Daily     9:30 PM   duplicate nightly-submission sweep
 *   runAgentEscalation   Daily     7:00 AM   escalation System 1 + System 2
 *   runAgent4            Monday    7:00 AM   system health check + self-heal
 *   runAgentScores       Monday   12:05 AM   weekly area scores
 *   runAgentMissionReport Monday  10:00 PM   mission-wide numbers for AP/MP
 *   runAgent2            (none)              MANUAL — run once per transfer
 *
 * Plus TWO installable form-submit triggers, which are NOT time-based and so
 * are not part of the table above (they fire when a missionary presses Submit,
 * not on a clock):
 *
 *   onNightlyFormSubmit  on submit   validation + duplicate detection (CCSM_AgentDuplicate.gs)
 *   onQAFormSubmit       on submit   question/suggestion handling    (CCSM_AgentQA.gs)
 *
 * setupAllCcsmTriggers() installs those two as well, and deliberately leaves
 * any already-installed form-submit trigger alone.
 *
 * runAgent2 is deliberately NOT scheduled: goal recalibration is a per-transfer
 * judgement call the mission president signs off on, not an automatic weekly
 * rewrite of every area's goals.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * DEPLOYMENT DECISION THE MISSION MUST CONFIRM — WEEKLY_REMINDER_OWNER
 * ─────────────────────────────────────────────────────────────────────────
 * TWO agents can remind companionships who have not submitted the WEEKLY
 * form, and both build the SAME Spanish subject line
 * ("Recordatorio: Informe Semanal — <mission>"):
 *
 *   1. CCSM_AgentReminder.gs -> ar_checkWeeklyCompliance()
 *      One reminder per non-submitting area per week. No leader escalation.
 *      Only fires Monday/Tuesday, 8 AM–9 PM mission time.
 *   2. CCSM_AgentEscalation.gs -> runWeeklyEscalation()  ("System 2")
 *      Staged: Monday reminder 1 -> Tuesday reminder 2 -> Wednesday escalate
 *      to the District Leader.
 *
 * Left both enabled, every non-submitting companionship gets nagged TWICE on
 * Monday by two different agents. That failure mode has happened for real on
 * the Provo system this fork descends from; both source files already carried
 * a "pick one mechanism in production" warning that nothing enforced.
 *
 * AGENT_CONFIG key `WEEKLY_REMINDER_OWNER` now enforces it:
 *
 *   'AGENT_ESCALATION'  (SHIPPED DEFAULT) — System 2 owns weekly reminders;
 *                        ar_checkWeeklyCompliance() returns immediately.
 *   'AGENT_REMINDER'   — ar_checkWeeklyCompliance() owns them; System 2's
 *                        weekly half returns immediately (System 1, the
 *                        NIGHTLY escalation, is unaffected either way).
 *   'BOTH'             — gate disabled, both run. Duplicate reminders WILL be
 *                        sent. Present only so the behaviour is testable and
 *                        so nobody has to edit agent code to get it back.
 *
 * WHY AGENT_ESCALATION IS THE DEFAULT: the schedule above fires
 * runAgentReminder on SUNDAY at 6 PM, and ar_checkWeeklyCompliance() only
 * acts on Monday/Tuesday. On this schedule the AgentReminder path can never
 * fire at all, so choosing it would silently disable weekly reminders
 * entirely. runAgentEscalation runs DAILY at 7 AM, so System 2 reaches its
 * Monday/Tuesday/Wednesday stages normally. AgentReminder's Sunday trigger
 * still does its other, unrelated job: NOTES reminders.
 *
 * >>> If the mission would rather have the simpler one-and-done reminder with
 * >>> no District Leader escalation, set WEEKLY_REMINDER_OWNER =
 * >>> 'AGENT_REMINDER' *and* move the runAgentReminder trigger to Monday, or
 * >>> the reminders will never send. Confirm this choice before go-live.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * SHIP STATE
 * ─────────────────────────────────────────────────────────────────────────
 * AGENT_CONFIG ships with TEST_MODE = TRUE and TEST_INBOX_EMAIL =
 * CCSM.PMG.Compass@gmail.com, so EVERY email any agent sends is redirected to
 * that inbox and prefixed [TEST]. No trigger is created automatically —
 * setupAllCcsmTriggers() exists but nothing calls it. A human must open the
 * editor and run it. Do not go live until the mission has read the
 * WEEKLY_REMINDER_OWNER decision above and TEST_MODE has been flipped
 * deliberately (CCSM_AgentTestMode.gs disableTestMode()).
 *
 * ─────────────────────────────────────────────────────────────────────────
 * OPERATOR ENTRY POINTS (all ZERO-ARGUMENT — the editor's Run button passes
 * no arguments and there is no console)
 * ─────────────────────────────────────────────────────────────────────────
 *   setupAllCcsmTriggers()     converge this project's triggers to the table
 *                              above + the two form-submit triggers. Safe to
 *                              re-run; it is the ONLY trigger installer an
 *                              operator should ever need.
 *   deleteAllCcsmTriggers()    remove every trigger in this project, including
 *                              the two form-submit ones
 *   smokeTestPipeline()        read-only pre-flight; sends nothing, writes nothing
 *   previewOneCoachingEmail()  one sample coaching email to the test inbox
 *
 * The editor's function dropdown also still lists the older per-agent
 * installers. They fall into three groups:
 *
 *   setupReminderTrigger(), setupEscalationTriggers(),
 *   setupSuggestionNotifyTrigger(), setupAgent1ATrigger(),
 *   setupAgent4Trigger(), setupAgent5ATrigger() — each of these disagreed
 *   with CCSM_TRIGGER_SCHEDULE (the first three installed OFF-TABLE handler
 *   names entirely; the latter three installed the right handler on a
 *   SCHEDULE that had drifted from the table — Agent1A on Sunday vs the
 *   table's Monday, Agent4 on Tue+Sat vs the table's Monday-only, Agent5A
 *   daily vs the table's weekly Sunday). Each is now a delegating shim:
 *   running one by mistake converges the project rather than silently
 *   replacing the canonical schedule with a stale one. See "LEGACY
 *   PER-AGENT INSTALLERS" below.
 *
 *   setupAgentMissionReportTrigger() — brand new (Phase 6, no legacy
 *   history to drift from), but built as a shim from day one rather than a
 *   direct installer: after finding three direct installers drift silently
 *   above, "install directly, hope it never gets edited independently" is
 *   the pattern to stop repeating, not extend.
 *
 *   setupAgentDuplicateTrigger(), setupQAFormTrigger() — these two still
 *   install directly, and must: they create the form-submit triggers in
 *   CCSM_FORM_SUBMIT_TRIGGERS, which setupAllCcsmTriggers() installs by
 *   calling them. Delegating would recurse. They are already idempotent
 *   (each deletes its own handler first), so running one by hand is safe.
 *
 *   setupAgent3Trigger(), setupAgent3EveningTrigger(), setupAgent5BTrigger(),
 *   setupAgentScoresTrigger(), setupAgent2OnceTrigger() — these install
 *   directly too, but their schedules already MATCH the table (or, for
 *   Agent2, are the documented manual/one-shot path — Agent2 is
 *   deliberately not on the table at all). deleteTriggerByName() clears the
 *   canonical trigger first, so running one by hand just recreates the same
 *   schedule under a new trigger ID — harmless, left as direct installers.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * LEGACY PER-AGENT INSTALLERS
 * ─────────────────────────────────────────────────────────────────────────
 * Before this file existed, each agent shipped its own setup*Trigger()
 * function. Three of them installed handler names that are NOT in
 * CCSM_TRIGGER_SCHEDULE at all:
 *
 *   setupReminderTrigger()          runReminderAgent, HOURLY
 *   setupEscalationTriggers()       runNightlyEscalation 10:00, runWeeklyEscalation 20:45
 *   setupSuggestionNotifyTrigger()  notifyAcceptedSuggestions, every 10 minutes
 *
 * Left as they were, an operator picking one out of the dropdown would get
 * escalation firing at 07:00 AND 10:00 AND 20:45 and the reminder agent
 * firing hourly — the exact duplicate-nagging failure WEEKLY_REMINDER_OWNER
 * exists to prevent, through a different door.
 *
 * A second audit (2026-08-01, while retiming Agent1A for Phase 5) found
 * three MORE that install the correct handler name but on a schedule that
 * had drifted from the table — worse, because deleteTriggerByName() means
 * running one doesn't just add a duplicate, it DELETES the canonical
 * trigger and replaces it with the stale one:
 *
 *   setupAgent1ATrigger()  installed Monday (table said Sunday until this fix)
 *   setupAgent4Trigger()   installs Tuesday + Saturday 7 AM (table: Monday only)
 *   setupAgent5ATrigger()  installs DAILY at noon (table: weekly, Sunday 10 PM)
 *
 * All six are therefore now delegating shims (they log what they used to
 * do, then converge).
 *
 * >>> ONE CONSEQUENCE THE MISSION MUST CONFIRM: notifyAcceptedSuggestions()
 * >>> (AgentQA's "email COMPASS when a suggestion is finally approved" poll)
 * >>> is not on CCSM_TRIGGER_SCHEDULE, so after convergence it is NOT
 * >>> scheduled at all. The function still exists and is zero-argument, so it
 * >>> can be run by hand. If the mission wants it automated, add a row to
 * >>> CCSM_TRIGGER_SCHEDULE (a daily hour is plenty; the original 10-minute
 * >>> poll burns ~144 executions/day for a low-volume queue) rather than
 * >>> re-enabling the old installer.
 */


// ═════════════════════════════════════════════════════════════════════════════
// THE SCHEDULE — single source of truth for setup, delete and smoke test
// ═════════════════════════════════════════════════════════════════════════════

/**
 * One entry per trigger in the table above. `weekDay` and `everyDays` are
 * mutually exclusive: `weekDay` produces a weekly trigger, `everyDays` a daily
 * one. `minute` is optional (omitted => Apps Script picks within the hour).
 */
var CCSM_TRIGGER_SCHEDULE = [
  { fn: 'runAgent3',          everyDays: 1,          hour: 6,                describe: 'Daily 6:00 AM' },
  { fn: 'runAgent3Evening',   everyDays: 1,          hour: 21,               describe: 'Daily 9:00 PM' },
  { fn: 'runAgent5A',         everyDays: 1,          hour: 12,               describe: 'Daily 12:00 PM' },
  { fn: 'runAgent1A',         weekDay: 'MONDAY',     hour: 21, minute: 30,   describe: 'Monday ~9:15-9:30 PM (chains 1B -> 1C)' },
  { fn: 'runAgent5B',         weekDay: 'FRIDAY',     hour: 12,               describe: 'Friday 12:00 PM (chains Agent6)' },
  { fn: 'runAgentReminder',   weekDay: 'SUNDAY',     hour: 18,               describe: 'Sunday 6:00 PM' },
  { fn: 'runAgentDuplicate',  everyDays: 1,          hour: 21, minute: 30,   describe: 'Daily 9:30 PM' },
  { fn: 'runAgentEscalation', everyDays: 1,          hour: 7,                describe: 'Daily 7:00 AM' },
  { fn: 'runAgent4',          weekDay: 'MONDAY',     hour: 7,                describe: 'Monday 7:00 AM' },
  { fn: 'runAgentScores',     weekDay: 'MONDAY',     hour: 0,  minute: 5,    describe: 'Monday 12:05 AM' },
  { fn: 'runAgentMissionReport', weekDay: 'MONDAY',  hour: 22,               describe: 'Monday 10:00 PM (mission-wide numbers, AP/MP)' }
];

/**
 * Handler functions the chain schedules for itself at runtime via
 * CCSM_Helpers.scheduleNext() (one-shot "after N minutes" triggers). They are
 * never part of CCSM_TRIGGER_SCHEDULE, but deleteAllCcsmTriggers() and the
 * smoke test's inventory both need to know they are legitimate.
 */
var CCSM_CHAINED_HANDLERS = ['runAgent1B', 'runAgent1C', 'runAgent6'];

/**
 * The project's two INSTALLABLE FORM-SUBMIT triggers. They are not on
 * CCSM_TRIGGER_SCHEDULE because they are not time-based — they fire when a
 * missionary presses Submit — but they are just as required, and every
 * function in this file has to know about them:
 *
 *   - setupAllCcsmTriggers() installs any that is missing, and never deletes
 *     one that is already there (deleting and recreating a form-submit
 *     trigger is not free — it re-authorizes and can drop in-flight events).
 *   - deleteAllCcsmTriggers() DOES remove them, like everything else.
 *   - smokeTestPipeline() treats their ABSENCE as an error rather than their
 *     presence as an unknown handler.
 *
 * `install` calls the agent file's own installer so the trigger is built
 * exactly one way, in one place.
 */
var CCSM_FORM_SUBMIT_TRIGGERS = [
  {
    fn: 'onNightlyFormSubmit',
    describe: 'On form submit — nightly validation + duplicate detection (CCSM_AgentDuplicate.gs)',
    install: function() { setupAgentDuplicateTrigger(); }
  },
  {
    fn: 'onQAFormSubmit',
    describe: 'On form submit — question/suggestion handling (CCSM_AgentQA.gs)',
    install: function() { setupQAFormTrigger(); }
  }
];

/** Handler names of CCSM_FORM_SUBMIT_TRIGGERS. Private to CCSM_Setup.gs. */
function cs_formSubmitHandlerNames_() {
  return CCSM_FORM_SUBMIT_TRIGGERS.map(function(s) { return s.fn; });
}

/**
 * True when `fn` names a function that actually exists in this project.
 *
 * Used by smokeTestPipeline() to catch the one failure no trigger inventory
 * can see: a trigger naming a handler whose .gs file was never pasted into the
 * online editor. See the "6b" section there for the Agent1C case that motivated
 * it.
 *
 * Direct eval, deliberately, because it is the only lookup that resolves in
 * BOTH environments this code runs in. Live, every pasted file's functions are
 * globals, so `this[fn]` would work. Under tests/load_gs.js every .gs file is
 * evaluated inside a single Function body where those same functions are
 * locals that never reach globalThis, so `this[fn]` is always undefined and the
 * check would report every handler missing. Direct eval uses the lexical scope
 * chain, which is correct in both. `typeof <name>` is also the one form that
 * does not throw on an undeclared identifier.
 *
 * `fn` only ever comes from this file's own constant arrays, never from user
 * input or sheet data; the identifier guard is belt-and-braces so this can
 * never become an injection point if a future caller passes something else.
 *
 * Private to CCSM_Setup.gs.
 */
function cs_handlerIsDefined_(fn) {
  if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(String(fn))) return false;
  try {
    return eval('typeof ' + fn) === 'function';
  } catch (e) {
    return false;
  }
}

/**
 * True when `trigger` is a time-based (clock) trigger — the only kind
 * setupAllCcsmTriggers() owns and is allowed to sweep away.
 *
 * Private to CCSM_Setup.gs.
 */
function cs_isTimeBased_(trigger) {
  try {
    return String(trigger.getEventType()) === String(ScriptApp.EventType.CLOCK);
  } catch (e) {
    // Defensive only. If getEventType() is ever unavailable, fall back to
    // handler names so that a converge run can still never destroy the two
    // installable form-submit triggers.
    return cs_formSubmitHandlerNames_().indexOf(trigger.getHandlerFunction()) === -1;
  }
}


// ═════════════════════════════════════════════════════════════════════════════
// TRIGGER INSTALL / REMOVE
// ═════════════════════════════════════════════════════════════════════════════

/**
 * CONVERGES this project's triggers to CCSM_TRIGGER_SCHEDULE, in mission-local
 * time, and makes sure the two form-submit triggers exist.
 *
 * "Converge", not "refresh": EVERY time-based trigger in the project is
 * deleted first — not just the ten this table names — and only then are the
 * table's ten created. That is what makes the table the single source of
 * truth. A per-name refresh could not clear an off-table handler such as
 * runReminderAgent (hourly) or runWeeklyEscalation (20:45) left behind by one
 * of the legacy per-agent installers, so escalation would end up firing at
 * 07:00 AND 10:00 AND 20:45. See "LEGACY PER-AGENT INSTALLERS" in the header.
 *
 * The sweep also removes any one-shot chain trigger CCSM_Helpers.scheduleNext()
 * has pending (runAgent1B / runAgent1C / runAgent6). That is correct and
 * intended — a pending one-shot is a leftover from a chain that is mid-flight,
 * and the next scheduled runAgent1A / runAgent5B re-creates it. Do not run
 * this in the middle of a Sunday-evening chain.
 *
 * Form-submit triggers are NOT time-based and are never swept; any missing one
 * is installed at the end.
 *
 * Idempotent and zero-argument — run it straight from the Apps Script editor.
 *
 * Nothing calls this automatically. Installing triggers means real emails
 * start flowing on a schedule, so it stays a deliberate human action.
 */
function setupAllCcsmTriggers() {
  var tz = getMissionTimezone();

  // ── Converge: clear EVERY time-based trigger, whatever installed it ──────
  var swept = [];
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (!cs_isTimeBased_(t)) return;   // form-submit triggers survive
    swept.push(t.getHandlerFunction());
    ScriptApp.deleteTrigger(t);
  });
  if (swept.length) {
    Logger.log('CCSM_Setup: swept ' + swept.length +
      ' existing time-based trigger(s) before installing the table: ' + swept.join(', '));
  }

  CCSM_TRIGGER_SCHEDULE.forEach(function(spec) {
    var builder = ScriptApp.newTrigger(spec.fn).timeBased();
    if (spec.weekDay) {
      builder = builder.onWeekDay(ScriptApp.WeekDay[spec.weekDay]);
    } else {
      builder = builder.everyDays(spec.everyDays);
    }
    builder = builder.atHour(spec.hour);
    if (spec.minute !== undefined) builder = builder.nearMinute(spec.minute);
    builder.inTimezone(tz).create();

    Logger.log('CCSM_Setup: installed ' + spec.fn + ' — ' + spec.describe + ' (' + tz + ')');
  });

  // ── Form-submit triggers: install only the ones that are missing ─────────
  var haveSubmit = {};
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (!cs_isTimeBased_(t)) haveSubmit[t.getHandlerFunction()] = true;
  });

  CCSM_FORM_SUBMIT_TRIGGERS.forEach(function(spec) {
    if (haveSubmit[spec.fn]) {
      Logger.log('CCSM_Setup: ' + spec.fn + ' form-submit trigger already installed — left alone.');
      return;
    }
    try {
      spec.install();
      Logger.log('CCSM_Setup: installed ' + spec.fn + ' — ' + spec.describe);
    } catch (e) {
      Logger.log('CCSM_Setup: FAILED to install ' + spec.fn + ' — ' + e.message +
        '. Install it by hand and re-run smokeTestPipeline().');
    }
  });

  Logger.log('CCSM_Setup: ' + CCSM_TRIGGER_SCHEDULE.length +
    ' scheduled trigger(s) + ' + CCSM_FORM_SUBMIT_TRIGGERS.length +
    ' form-submit trigger(s) in place. runAgent2 is intentionally NOT scheduled — ' +
    'run it manually once per transfer.');
}

/**
 * Removes EVERY trigger in this Apps Script project — the ten scheduled ones,
 * any one-shot chain trigger CCSM_Helpers.scheduleNext() left behind, any
 * stale handler from an earlier setup, AND the two installable form-submit
 * triggers (onNightlyFormSubmit, onQAFormSubmit). The CCSM project hosts
 * nothing but PMG Compass, so "all triggers" and "all CCSM triggers" are the
 * same set.
 *
 * Because the form-submit triggers go too, submit-time duplicate detection and
 * all of AgentQA stop until something reinstalls them. setupAllCcsmTriggers()
 * does — it is the single command that brings everything back.
 *
 * Zero-argument. Use before a maintenance window, or to stop all automation
 * immediately.
 */
function deleteAllCcsmTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  var removed  = [];

  triggers.forEach(function(t) {
    removed.push(t.getHandlerFunction());
    ScriptApp.deleteTrigger(t);
  });

  Logger.log('CCSM_Setup: deleted ' + removed.length + ' trigger(s)' +
    (removed.length ? ': ' + removed.join(', ') : '') + '. No automation is scheduled now.');
  return removed.length;
}


// ═════════════════════════════════════════════════════════════════════════════
// SMOKE TEST — read-only pre-flight
// ═════════════════════════════════════════════════════════════════════════════

/**
 * In-sheet dry run. Sends NO email, writes NO cell, creates NO trigger — it
 * only reads and reports, so it is always safe to run against production.
 *
 * Reads through a handle re-opened by ID rather than whatever the caller
 * happened to have: an in-place read after a write returns the LOCAL PENDING
 * value in Apps Script, and the whole point of a pre-flight is true server
 * state.
 *
 * Zero-argument. Open View -> Logs after running.
 *
 * @returns {{ok: boolean, errors: string[], warnings: string[], lines: string[]}}
 */
function smokeTestPipeline() {
  var errors   = [];
  var warnings = [];
  var lines    = [];

  function ok(msg)   { lines.push('  OK    ' + msg); }
  function warn(msg) { warnings.push(msg); lines.push('  WARN  ' + msg); }
  function fail(msg) { errors.push(msg);   lines.push('  ERROR ' + msg); }

  lines.push('=== CCSM smoke test — ' + new Date().toISOString() + ' (no email, no writes) ===');

  // ── 1. Spreadsheet reachable by ID ───────────────────────────────────────
  var ss;
  try {
    ss = SpreadsheetApp.openById(getSpreadsheet().getId());
    ok('Spreadsheet "' + ss.getName() + '" reachable by ID.');
  } catch (e) {
    fail('Cannot open the bound spreadsheet: ' + e.message);
    lines.forEach(function(l) { Logger.log(l); });
    return { ok: false, errors: errors, warnings: warnings, lines: lines };
  }

  // ── 2. Every tab in the spec exists ──────────────────────────────────────
  var present = {};
  ss.getSheets().forEach(function(s) { present[s.getName()] = s; });

  // MESSAGE_BANK / LEADERSHIP_MESSAGE_BANK may have been split into their own
  // spreadsheet (CCSM_SeedContent.gs splitMessageBanksToOwnSpreadsheet()) —
  // ss.getSheets() above only sees the bound spreadsheet, so those two need a
  // second, split-aware lookup layered on top rather than being judged solely
  // by whether they're in COMPASS_CCSM.
  CCSM_SPLIT_TABS.forEach(function(name) {
    try {
      var sheet = ccsmSpreadsheetForTab_(name).getSheetByName(name);
      if (sheet) present[name] = sheet;
    } catch (e) { /* bad/unreadable MESSAGE_BANK_SPREADSHEET_ID — treat as missing below */ }
  });

  var missingTabs  = CCSM_TAB_SPECS.filter(function(t) { return !present[t.name]; })
                                   .map(function(t) { return t.name; });
  var missingSplit = missingTabs.filter(function(n) { return CCSM_SPLIT_TABS.indexOf(n) !== -1; });
  var missingOther = missingTabs.filter(function(n) { return CCSM_SPLIT_TABS.indexOf(n) === -1; });
  if (missingOther.length) fail('Missing tab(s): ' + missingOther.join(', ') + '. Run buildCcsmSheet().');
  if (missingSplit.length) fail('Missing tab(s): ' + missingSplit.join(', ') + '. If these were split ' +
    'into their own spreadsheet, check MESSAGE_BANK_SPREADSHEET_ID in AGENT_CONFIG is set and correct.');
  if (!missingTabs.length) ok('All ' + CCSM_TAB_SPECS.length + ' required tabs present.');

  // The two raw form tabs only appear once the Google Forms are attached.
  ['NIGHTLY_FORM_RAW', 'WEEKLY_FORM_RAW'].forEach(function(name) {
    if (present[name]) ok(name + ' present (' + Math.max(present[name].getLastRow() - 1, 0) + ' response row(s)).');
    else warn(name + ' does not exist yet — attach the Google Form response destination.');
  });

  // ── 3. Config keys ───────────────────────────────────────────────────────
  var requiredConfig = [
    'MISSION_NAME', 'MISSION_LANGUAGE', 'MISSION_TIMEZONE', 'MISSION_LOCALE',
    'TEST_INBOX_EMAIL', 'SEND_FROM_EMAIL', 'SYSTEM_START_DATE', 'TRANSFER_START_DATE',
    'NIGHTLY_FORM_LINK', 'WEEKLY_FORM_LINK', 'MISSED_DAYS_LOOKBACK', 'WEEKLY_REMINDER_OWNER'
  ];
  var blankConfig = requiredConfig.filter(function(k) {
    var v = getConfig(k);
    return v === null || v === undefined || String(v).trim() === '';
  });
  if (blankConfig.length) fail('AGENT_CONFIG key(s) blank: ' + blankConfig.join(', ') + '.');
  else ok('All ' + requiredConfig.length + ' required AGENT_CONFIG keys are set.');

  if (String(getConfig('MISSION_TIMEZONE') || '').trim() !== 'America/Santiago') {
    warn('MISSION_TIMEZONE is "' + getConfig('MISSION_TIMEZONE') + '", expected America/Santiago.');
  }

  // ── 3b. Apps Script PROJECT timezone vs MISSION_TIMEZONE ─────────────────
  // Final-review finding (integration I-4). Triggers are pinned with
  // .inTimezone(MISSION_TIMEZONE), but the agents ALSO do plain local-calendar
  // arithmetic (new Date()/getDay() in CCSM_Agent1A.gs and elsewhere), and
  // that resolves against the Apps Script PROJECT timezone — a separate
  // setting, in Project Settings, that nothing in this code can control.
  //
  // On a project whose timezone was never set (it defaults to the creating
  // Google account's) the two disagree and the coaching week silently slips:
  // reports get attributed to the wrong week and the Sunday chain can compute
  // the wrong week boundary. Nothing else in the system detects this.
  //
  // There is no API to SET the project timezone, so the smoke test is the only
  // place this can be caught — and it fails rather than warns, because the
  // symptom is silent and off-by-a-day rather than a visible outage.
  var projectTz = (typeof Session !== 'undefined' && Session.getScriptTimeZone)
    ? String(Session.getScriptTimeZone() || '').trim()
    : '';
  var missionTz = String(getConfig('MISSION_TIMEZONE') || '').trim();
  if (!projectTz) {
    warn('Could not read the Apps Script project timezone to compare with MISSION_TIMEZONE.');
  } else if (projectTz !== missionTz) {
    fail('Apps Script PROJECT timezone is "' + projectTz + '" but MISSION_TIMEZONE is "' +
         missionTz + '". Fix it in Project Settings → Time zone. Until they match, every ' +
         'date the agents compute can be off by a day.');
  } else {
    ok('Project timezone matches MISSION_TIMEZONE (' + projectTz + ').');
  }

  if (String(getConfig('MISSION_LANGUAGE') || '').trim().toUpperCase() !== 'ES') {
    warn('MISSION_LANGUAGE is "' + getConfig('MISSION_LANGUAGE') + '", expected ES.');
  }

  // ── 4. Test mode + the weekly-reminder deployment decision ───────────────
  if (isTestMode()) {
    warn('TEST_MODE = TRUE — every email is redirected to ' + getTestInbox() +
         ' and prefixed [TEST]. No missionary receives anything. This is the SHIP state.');
  } else {
    warn('TEST_MODE = FALSE — emails go to REAL missionaries and leaders.');
  }

  var owner = String(getConfig('WEEKLY_REMINDER_OWNER') || 'AGENT_ESCALATION').trim().toUpperCase();
  if (owner === 'AGENT_ESCALATION') {
    ok('WEEKLY_REMINDER_OWNER = AGENT_ESCALATION (default) — System 2 owns weekly reminders.');
  } else if (owner === 'AGENT_REMINDER') {
    ok('WEEKLY_REMINDER_OWNER = AGENT_REMINDER — ar_checkWeeklyCompliance owns weekly reminders.');
    warn('AGENT_REMINDER only acts Monday/Tuesday, but runAgentReminder is scheduled for Sunday ' +
         '6 PM — move that trigger to Monday or weekly reminders will never send. See CCSM_Setup.gs header.');
  } else if (owner === 'BOTH') {
    fail('WEEKLY_REMINDER_OWNER = BOTH — AgentReminder AND AgentEscalation will each remind every ' +
         'non-submitting companionship. Pick one. See CCSM_Setup.gs header.');
  } else {
    fail('WEEKLY_REMINDER_OWNER = "' + owner + '" is not a recognized value ' +
         '(AGENT_ESCALATION | AGENT_REMINDER | BOTH).');
  }

  // ── 5. Reference data ────────────────────────────────────────────────────
  var orgSheet = present['MISSION_ORG'];
  if (orgSheet) {
    var orgData = orgSheet.getDataRange().getValues();
    var actCol  = orgData.length ? orgData[0].indexOf('Active') : -1;
    var active  = orgData.slice(1).filter(function(r) {
      return actCol === -1 || String(r[actCol]).trim().toUpperCase() === 'TRUE';
    }).length;
    if (active > 0) ok('MISSION_ORG: ' + active + ' active area row(s).');
    else fail('MISSION_ORG has no active area rows.');

    var e1 = orgData.length ? orgData[0].indexOf('Companion1_Email') : -1;
    var e2 = orgData.length ? orgData[0].indexOf('Companion2_Email') : -1;
    var reachable = orgData.slice(1).filter(function(r) {
      return (e1 !== -1 && String(r[e1] || '').indexOf('@') > 0) ||
             (e2 !== -1 && String(r[e2] || '').indexOf('@') > 0);
    }).length;
    if (reachable === 0) warn('No MISSION_ORG row has a companion email — no agent can reach anyone yet.');
    else ok('MISSION_ORG: ' + reachable + ' row(s) have at least one companion email.');
  }

  var qc = present['QUESTIONS_CONFIG'];
  if (qc) {
    var qcRows = Math.max(qc.getLastRow() - 1, 0);
    if (qcRows > 0) ok('QUESTIONS_CONFIG: ' + qcRows + ' question row(s).');
    else fail('QUESTIONS_CONFIG is empty — no agent can parse a form response.');
  }

  var mb = present['MESSAGE_BANK'];
  if (mb) {
    var mbRows = Math.max(mb.getLastRow() - 1, 0);
    if (mbRows > 0) ok('MESSAGE_BANK: ' + mbRows + ' message row(s).');
    else fail('MESSAGE_BANK is empty — run seedCcsmMessageBank(). Agents PICK message text, ' +
              'they never generate it, so an empty bank means silent coaching.');
  }

  var lmb = present['LEADERSHIP_MESSAGE_BANK'];
  if (lmb) {
    var lmbRows = Math.max(lmb.getLastRow() - 1, 0);
    if (lmbRows > 0) ok('LEADERSHIP_MESSAGE_BANK: ' + lmbRows + ' message row(s).');
    else fail('LEADERSHIP_MESSAGE_BANK is empty — run seedCcsmLeadershipMessageBank() once. ' +
              'Zone/district leadership letters need at least one message per theme.');
  }

  // SCORE_CONFIG has no header row in CCSM_TAB_SPECS — setupCcsmScoreConfig()
  // writes its own two-section layout (see CCSM_AgentScores.gs), so "populated"
  // means "has any row at all", not "has more than a header".
  var sc = present['SCORE_CONFIG'];
  if (sc) {
    var scRows = sc.getLastRow();
    if (scRows > 0) ok('SCORE_CONFIG: ' + scRows + ' row(s).');
    else fail('SCORE_CONFIG is empty — run setupCcsmScoreConfig(). runAgentScores ' +
              '(Monday 12:05 AM) has no weights without it.');
  }

  var kb = present['KNOWLEDGE_BASE'];
  if (kb) {
    var kbRows = Math.max(kb.getLastRow() - 1, 0);
    if (kbRows > 0) ok('KNOWLEDGE_BASE: ' + kbRows + ' entry(ies).');
    else warn('KNOWLEDGE_BASE is empty — run seedCcsmKnowledgeBase().');
  }

  // ── 5b. Nightly/weekly form area dropdowns vs MISSION_ORG (drift detector) ──
  // The live Google Form's area dropdowns are a COPY of MISSION_ORG baked in by
  // CCSM_TransferWebApp.gs's formSync (cct_applyFormSync_) — they do NOT update
  // themselves when MISSION_ORG changes (e.g. a transfer). If that sync step is
  // forgotten, a missionary who picks a since-renamed/removed area is silently
  // dropped by CCSM_Agent3.gs's a3_buildDailyRecords ("Unrecognized area", now
  // also written to AUDIT_LOG) — and is then falsely told by
  // CCSM_AgentEscalation.gs System 1 (and/or Agent3's own missed-day alert)
  // that they never submitted. This check is read-only (FormApp.openById +
  // getChoices() only) and safe against production, same contract as every
  // other check in this function.
  try {
    if (typeof cct_getOrgZones_ !== 'function' || typeof cct_readFormStructure_ !== 'function') {
      warn('CCSM_TransferHelpers.gs is not pasted into this project — cannot check the form ' +
        'dropdowns against MISSION_ORG.');
    } else if (typeof CCT_NIGHTLY_FORM_ID === 'undefined' || typeof CCT_WEEKLY_FORM_ID === 'undefined') {
      warn('CCSM_TransferWebApp.gs is not pasted into this project — cannot check the form ' +
        'dropdowns against MISSION_ORG.');
    } else {
      var orgZones = cct_getOrgZones_();
      var orgAreas = {};
      Object.keys(orgZones).forEach(function(z) {
        orgZones[z].forEach(function(a) { orgAreas[a.toLowerCase()] = a; });
      });
      var orgAreaCount = Object.keys(orgAreas).length;

      var formIdsToCheck = { nightly: CCT_NIGHTLY_FORM_ID, weekly: CCT_WEEKLY_FORM_ID };
      Object.keys(formIdsToCheck).forEach(function(label) {
        var formId = formIdsToCheck[label];
        if (!formId || String(formId).indexOf('CHANGE_ME') === 0) {
          warn('CCT_' + label.toUpperCase() + '_FORM_ID is not set (CCSM_TransferWebApp.gs) — ' +
            'cannot check the ' + label + ' form dropdown against MISSION_ORG.');
          return;
        }
        try {
          var struct = cct_readFormStructure_(formId);
          var formAreas = {};
          struct.zoneSections.forEach(function(sec) {
            if (!sec.areaItem) return;
            sec.areaItem.getChoices().forEach(function(c) {
              formAreas[String(c.getValue()).toLowerCase().trim()] = true;
            });
          });

          var missingFromForm = Object.keys(orgAreas).filter(function(k) { return !formAreas[k]; })
            .map(function(k) { return orgAreas[k]; });
          var staleInForm = Object.keys(formAreas).filter(function(k) { return !orgAreas[k]; });

          if (missingFromForm.length || staleInForm.length) {
            var msg = label.toUpperCase() + ' form dropdown is OUT OF SYNC with MISSION_ORG.';
            if (missingFromForm.length) {
              msg += ' Active area(s) missing from the form (a missionary here cannot select their ' +
                'area, or picks a near-miss that silently fails to match): ' + missingFromForm.join(', ') + '.';
            }
            if (staleInForm.length) {
              msg += ' Stale choice(s) still in the form (renamed/removed in MISSION_ORG): ' +
                staleInForm.join(', ') + '.';
            }
            msg += ' Fix: dashboard Traslados page -> "3 · Sync nightly + weekly form dropdowns".';
            fail(msg);
          } else {
            ok(label.toUpperCase() + ' form dropdown matches MISSION_ORG (' + orgAreaCount + ' area(s)).');
          }
        } catch (e) {
          warn('Could not read the ' + label + ' form (' + formId + ') to check its dropdown: ' + e.message);
        }
      });
    }
  } catch (e) {
    warn('Form-dropdown drift check failed unexpectedly: ' + e.message);
  }

  // ── 6. Trigger inventory ─────────────────────────────────────────────────
  var counts = {};
  ScriptApp.getProjectTriggers().forEach(function(t) {
    var fn = t.getHandlerFunction();
    counts[fn] = (counts[fn] || 0) + 1;
  });

  var missingTriggers = [];
  CCSM_TRIGGER_SCHEDULE.forEach(function(spec) {
    if (!counts[spec.fn]) missingTriggers.push(spec.fn + ' (' + spec.describe + ')');
    else if (counts[spec.fn] > 1) warn('Duplicate trigger: ' + spec.fn + ' has ' + counts[spec.fn] +
                                       ' triggers. Re-run setupAllCcsmTriggers().');
  });
  if (missingTriggers.length) {
    fail('Missing trigger(s): ' + missingTriggers.join('; ') + '. Run setupAllCcsmTriggers().');
  } else {
    ok('All ' + CCSM_TRIGGER_SCHEDULE.length + ' scheduled triggers installed.');
  }

  var missingSubmit = CCSM_FORM_SUBMIT_TRIGGERS.filter(function(spec) { return !counts[spec.fn]; })
                                               .map(function(spec) { return spec.fn + ' (' + spec.describe + ')'; });
  if (missingSubmit.length) {
    fail('Missing form-submit trigger(s): ' + missingSubmit.join('; ') + '. Run setupAllCcsmTriggers().');
  } else {
    ok('Both form-submit triggers installed (' + cs_formSubmitHandlerNames_().join(', ') + ').');
  }

  // DUPLICATE form-submit triggers (final review, known-open minor (d)).
  // The check above only asks "is there at least one?", so a project with the
  // handler installed TWICE passed silently. Duplicates are easy to create —
  // the converge sweep deliberately spares form-submit triggers, so attaching
  // a form again, or running an installer against a project that already had
  // one, adds a second — and the consequence is that every form submission
  // fires the handler twice: two duplicate-detection passes, two AgentQA
  // answers, two emails to the same missionary.
  var duplicateSubmit = CCSM_FORM_SUBMIT_TRIGGERS
    .filter(function(spec) { return counts[spec.fn] > 1; })
    .map(function(spec) { return spec.fn + ' x' + counts[spec.fn]; });
  if (duplicateSubmit.length) {
    fail('Duplicate form-submit trigger(s): ' + duplicateSubmit.join('; ') +
         '. Every submission fires the handler that many times (duplicate emails). ' +
         'Delete the extras in Triggers, or run deleteAllCcsmTriggers() then ' +
         'setupAllCcsmTriggers().');
  }

  var known = CCSM_TRIGGER_SCHEDULE.map(function(s) { return s.fn; })
                                   .concat(CCSM_CHAINED_HANDLERS)
                                   .concat(cs_formSubmitHandlerNames_());
  Object.keys(counts).forEach(function(fn) {
    if (known.indexOf(fn) === -1) warn('Unrecognized trigger handler installed: ' + fn + '.');
  });
  if (counts['runAgent2']) {
    warn('runAgent2 is scheduled. It is meant to be run MANUALLY once per transfer.');
  }

  // ── 6b. Every handler this project schedules actually EXISTS ─────────────
  //
  // The inventory above only asks whether a TRIGGER exists. A trigger can name
  // a function this project does not define — that is what happens when an
  // agent's .gs file was never pasted into the online editor, since the editor
  // runs only what is pasted into it and nothing in git reaches it.
  //
  // This is not hypothetical. Agent1B logged "Agent1C scheduled in ~1 min" on
  // 2026-07-26 and Agent1C never appeared in AGENT_RUN_LOG at all — not even an
  // ERROR row, which runAgent1C would have written for any exception inside
  // itself, because its logRun() sits outside its try/catch. The function never
  // started. Apps Script reports that as "Script function not found" in the
  // Executions list ONLY: nothing reaches the sheet, no email is sent, and this
  // smoke test reported "All 10 scheduled triggers installed" in green.
  //
  // Chained handlers are checked too, and matter MORE than the scheduled ones:
  // they have no standing trigger to be missing, so a missing runAgent1C is
  // invisible to every other check in this file.
  var handlersToCheck = CCSM_TRIGGER_SCHEDULE.map(function(s) { return s.fn; })
                                             .concat(CCSM_CHAINED_HANDLERS)
                                             .concat(cs_formSubmitHandlerNames_());
  var undefinedHandlers = handlersToCheck.filter(function(fn) {
    return !cs_handlerIsDefined_(fn);
  });

  if (undefinedHandlers.length) {
    fail('Handler function(s) NOT DEFINED in this project: ' + undefinedHandlers.join(', ') +
         '. The matching CCSM_*.gs file was never pasted into this Apps Script editor ' +
         '(committing it to git does not install it). Any trigger naming one of these ' +
         'fails silently with "Script function not found" and writes nothing to ' +
         'AGENT_RUN_LOG. Paste the file, then re-run this smoke test.');
  } else {
    ok('All ' + handlersToCheck.length + ' scheduled/chained/form-submit handlers are defined.');
  }

  // ── Summary ──────────────────────────────────────────────────────────────
  lines.push('=== smoke test: ' + errors.length + ' error(s), ' + warnings.length + ' warning(s) ===');
  lines.forEach(function(l) { Logger.log(l); });

  return { ok: errors.length === 0, errors: errors, warnings: warnings, lines: lines };
}


// ═════════════════════════════════════════════════════════════════════════════
// SAMPLE COACHING EMAIL
// ═════════════════════════════════════════════════════════════════════════════

/**
 * Sends ONE sample Sunday-coaching email to the test inbox so the mission can
 * read the TONE AND CONTENT of the message bank, without waiting for Sunday
 * and without running the 1A -> 1B -> 1C chain over real data.
 *
 * The sample text is REAL MESSAGE_BANK content, picked (never generated) the
 * same way Agent1B picks it — that is the whole point of the preview. It reads
 * MESSAGE_BANK and MISSION_ORG only; it writes nothing.
 *
 * NOT a layout preview. The HTML below is this file's own, deliberately
 * marked MUESTRA; the email missionaries actually receive is rendered by
 * Agent1C's template over real weekly metrics. Judge the words here, not the
 * design.
 *
 * Zero-argument. Always addressed to getTestInbox(), and sendEmail() routes it
 * through the same TEST_MODE redirect every other agent uses.
 */
function previewOneCoachingEmail() {
  // Read MESSAGE_BANK by category only. getMessageBank() (CCSM_Helpers.gs)
  // requires a category AND a specific metric key; the preview does not care
  // which metric the sample happens to be about, so it reads the tab directly
  // through the same header-lookup helpers.
  function firstActive(category) {
    var rows = getTabData('MESSAGE_BANK');
    var cCat    = col_('MESSAGE_BANK', 'Category');
    var cActive = col_('MESSAGE_BANK', 'Active');
    for (var i = 0; i < rows.length; i++) {
      if (String(rows[i][cCat]).trim() !== category) continue;
      if (String(rows[i][cActive]).trim().toUpperCase() !== 'TRUE') continue;
      return {
        messageId:   String(rows[i][col_('MESSAGE_BANK', 'Message_ID')]),
        subjectLine: String(rows[i][col_('MESSAGE_BANK', 'Subject_Line')]),
        bodyText:    String(rows[i][col_('MESSAGE_BANK', 'Body_Text')]),
        scripture:   String(rows[i][col_('MESSAGE_BANK', 'Scripture')]),
        pmgChapter:  String(rows[i][col_('MESSAGE_BANK', 'PMG_Chapter')])
      };
    }
    return null;
  }

  var strength = firstActive('SUNDAY_COACHING_STRENGTH');
  var growth   = firstActive('SUNDAY_COACHING_GROWTH');

  if (!strength || !growth) {
    throw new Error('previewOneCoachingEmail: MESSAGE_BANK has no active ' +
      'SUNDAY_COACHING_STRENGTH / SUNDAY_COACHING_GROWTH rows. Run seedCcsmMessageBank() first.');
  }

  // A real area name, so the sample reads like the genuine article.
  var areaName = 'su área';
  var orgData  = getTabData('MISSION_ORG');
  if (orgData && orgData.length > 1) {
    var nameCol = orgData[0].indexOf('Area_Name');
    if (nameCol !== -1) {
      for (var i = 1; i < orgData.length; i++) {
        var candidate = String(orgData[i][nameCol] || '').trim();
        if (candidate) { areaName = candidate; break; }
      }
    }
  }

  var tz      = getMissionTimezone();
  var weekEnd = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');
  var subject = 'Muestra: Entrenamiento Semanal — ' + areaName;

  var html = [];
  html.push('<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;">');
  html.push('<p style="background:#fff4d6;border-left:4px solid #d9a300;padding:10px;">');
  html.push('<strong>MUESTRA</strong> — este es un correo de ejemplo generado con ');
  html.push('previewOneCoachingEmail(). No refleja datos reales de ninguna compañía.</p>');
  html.push('<h2 style="color:#1a4d7c;">Entrenamiento Semanal — ' + cs_esc_(areaName) + '</h2>');
  html.push('<p style="color:#6b7280;">Semana que termina el ' + cs_esc_(weekEnd) + '</p>');
  html.push(cs_messageBlock_('Fortaleza', strength, '#1f7a4d'));
  html.push(cs_messageBlock_('Oportunidad de Crecimiento', growth, '#b45309'));
  html.push('<p style="color:#6b7280;font-size:12px;margin-top:24px;">— PMG Compass (' +
    cs_esc_(getMissionName()) + ')</p>');
  html.push('</body></html>');

  sendEmail(getTestInbox(), subject, html.join('\n'));
  Logger.log('CCSM_Setup: sample coaching email sent to ' + getTestInbox() +
    ' using MESSAGE_BANK rows ' + strength.messageId + ' / ' + growth.messageId + '.');
}

/**
 * Read-only sanity check for the message-bank split. previewOneCoachingEmail()
 * above and smokeTestPipeline() both only ever touch MESSAGE_BANK / row
 * counts — neither exercises LEADERSHIP_MESSAGE_BANK's actual selection
 * logic (a1c_pickRelevantLeadershipMsg_, the function the real weekly
 * leadership letter calls). This calls it directly with harmless empty
 * inputs. Sends no email, writes nothing — safe to run any time.
 */
function verifyLeadershipMessagePick() {
  var msg = a1c_pickRelevantLeadershipMsg_({}, []);
  if (!msg) {
    Logger.log('verifyLeadershipMessagePick: FAILED — got null. Either ' +
      'LEADERSHIP_MESSAGE_BANK read as empty through the split, or it has ' +
      'no row with Active = TRUE.');
    return;
  }
  Logger.log('verifyLeadershipMessagePick: OK — picked ' + msg.messageId +
    ' (theme: ' + msg.theme + ')');
  Logger.log('  Subject: ' + msg.subject);
  Logger.log('  Body (first 80 chars): ' + String(msg.body).substring(0, 80) + '...');
}

/** Renders one MESSAGE_BANK row as an HTML block. Private to CCSM_Setup.gs. */
function cs_messageBlock_(label, msg, accentColor) {
  var out = [];
  out.push('<div style="border-left:4px solid ' + accentColor + ';padding:8px 14px;margin:16px 0;">');
  out.push('<div style="font-size:12px;text-transform:uppercase;color:' + accentColor + ';">' +
    cs_esc_(label) + '</div>');
  out.push('<div style="font-weight:bold;margin:4px 0;">' + cs_esc_(msg.subjectLine || '') + '</div>');
  out.push('<div>' + cs_esc_(msg.bodyText || '') + '</div>');
  if (msg.scripture)  out.push('<div style="color:#6b7280;font-size:12px;margin-top:6px;">' + cs_esc_(msg.scripture) + '</div>');
  if (msg.pmgChapter) out.push('<div style="color:#6b7280;font-size:12px;">PMG ' + cs_esc_(msg.pmgChapter) + '</div>');
  out.push('</div>');
  return out.join('\n');
}

/** HTML-escapes a value for the sample email. Private to CCSM_Setup.gs. */
function cs_esc_(str) {
  return String(str === null || str === undefined ? '' : str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


// ═════════════════════════════════════════════════════════════════════════════
// TRIGGER HANDLERS
//
// The schedule above names these; each is a thin, ZERO-ARGUMENT wrapper so a
// human can also run it straight from the editor. Apps Script hands a
// time-based trigger an event object none of them use.
// ═════════════════════════════════════════════════════════════════════════════

/**
 * Sunday 6:00 PM. NOTES reminders (and, only if WEEKLY_REMINDER_OWNER =
 * AGENT_REMINDER, the weekly-form compliance check — see the file header).
 * Called with no options, so the Mon/Tue 8 AM–9 PM weekly-compliance time
 * gate stays active: the skipTimeGate bypass is test-only.
 *
 * Wrapped in cs_loggedRun_ because CCSM_AgentReminder.gs is one of only two
 * agents in the schedule that never calls logRun() itself (it reports to
 * AUDIT_LOG instead) — without this, a scheduled run of it is invisible in
 * AGENT_RUN_LOG and in Agent4's CHECK 10 freshness audit.
 */
function runAgentReminder() {
  cs_loggedRun_('AgentReminder', function() {
    runReminderAgent();
  });
}

/**
 * Daily 9:30 PM. Duplicate nightly-submission sweep. CCSM_AgentDuplicate.gs's
 * onNightlyFormSubmit(e) is also wired as an on-form-submit trigger and never
 * reads `e`; this nightly pass catches anything a missed submit event left
 * behind.
 */
function runAgentDuplicate() {
  onNightlyFormSubmit();
}

/**
 * Daily 7:00 AM. Both escalation systems, in order:
 *   System 1 — nightly form: day+2 reminder 1, day+3 reminder 2, day+4 leader.
 *   System 2 — weekly form: Mon reminder 1, Tue reminder 2, Wed leader.
 * System 2 no-ops unless WEEKLY_REMINDER_OWNER allows it (file header).
 * Both are called with no arguments, so every day/stage gate stays active.
 */
function runAgentEscalation() {
  // Each system gets its OWN logged run, and BOTH always run: System 2's
  // weekly reminders must not be skipped for the day just because System 1
  // threw. (Before this file existed they were on two separate triggers, so
  // that independence was free; it has to be spelled out now they share one.)
  var err1 = cs_runAndLog_('AgentEscalation', 'System 1 (nightly form)', runNightlyEscalation);
  var err2 = cs_runAndLog_('AgentEscalation', 'System 2 (weekly form)',  runWeeklyEscalation);

  // Rethrow AFTER both have run and both have left their AGENT_RUN_LOG row —
  // see cs_runAndLog_ for why a trigger handler must end up throwing.
  if (err1) throw err1;
  if (err2) throw err2;
}

/**
 * Runs `body`, records the outcome in AGENT_RUN_LOG, and RETURNS the caught
 * exception (null on success) rather than throwing it.
 *
 * CCSM_AgentReminder.gs and CCSM_AgentEscalation.gs are the only two agents on
 * the trigger schedule that never call CCSM_Helpers.logRun() themselves — both
 * report to AUDIT_LOG instead. That leaves AGENT_RUN_LOG (and therefore
 * Agent4's CHECK 10 "did every agent run recently" audit, and any human
 * scanning the tab after an incident) with no record that they ever fired.
 * The trigger entry point is the right place to close that gap without
 * changing either agent's own behaviour.
 *
 * Returning instead of throwing exists ONLY so a handler that has more than
 * one body to run (runAgentEscalation) can run all of them and still fail
 * afterwards. Every caller MUST end up throwing what this returns: Apps
 * Script emails the project owner its automatic "your script failed" notice
 * only when a trigger handler throws, and the eight unwrapped handlers on the
 * schedule all propagate. Swallowing here would make these two the only
 * agents whose total failure is silent until someone opens a tab. The
 * AGENT_RUN_LOG ERROR row is already written by the time this returns, so
 * rethrowing costs nothing.
 *
 * Private to CCSM_Setup.gs.
 *
 * @returns {Error|null} the exception `body` threw, or null
 */
function cs_runAndLog_(agentName, stage, body) {
  var startMs = new Date().getTime();
  var status  = 'SUCCESS';
  var label   = agentName + (stage ? ' — ' + stage : '');
  var note    = 'Ran ' + label + ' from the ' + agentName + ' trigger (CCSM_Setup.gs).';
  var errMsg  = '';
  var caught  = null;

  try {
    body();
  } catch (e) {
    caught = e;
    status = 'ERROR';
    errMsg = e.message;
    note   = 'FATAL in ' + label + ': ' + e.message;
    Logger.log(label + ' FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  logRun(agentName, status, null, null, new Date().getTime() - startMs, note, errMsg);
  return caught;
}

/**
 * Single-body form of cs_runAndLog_: logs the run, then rethrows any failure
 * so Apps Script's owner-notification email still fires.
 * Private to CCSM_Setup.gs.
 */
function cs_loggedRun_(agentName, body) {
  var err = cs_runAndLog_(agentName, '', body);
  if (err) throw err;
}
