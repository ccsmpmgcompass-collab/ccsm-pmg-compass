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
 *   runAgent5A           Sunday   10:00 PM   dashboard summary + WEEKLY_KI
 *   runAgent1A           Sunday    9:00 PM   Sunday coaching (chains 1B -> 1C)
 *   runAgent5B           Friday   12:00 PM   Friday encouragement (chains Agent6)
 *   runAgentReminder     Sunday    6:00 PM   NOTES reminders (+ weekly compliance, see below)
 *   runAgentDuplicate    Daily     9:30 PM   duplicate nightly-submission sweep
 *   runAgentEscalation   Daily     7:00 AM   escalation System 1 + System 2
 *   runAgent4            Monday    7:00 AM   system health check + self-heal
 *   runAgentScores       Monday   12:05 AM   weekly area scores
 *   runAgent2            (none)              MANUAL — run once per transfer
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
 *   setupAllCcsmTriggers()     install the whole table (safe to re-run)
 *   deleteAllCcsmTriggers()    remove every trigger in this project
 *   smokeTestPipeline()        read-only pre-flight; sends nothing, writes nothing
 *   previewOneCoachingEmail()  one sample coaching email to the test inbox
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
  { fn: 'runAgent5A',         weekDay: 'SUNDAY',     hour: 22,               describe: 'Sunday 10:00 PM' },
  { fn: 'runAgent1A',         weekDay: 'SUNDAY',     hour: 21,               describe: 'Sunday 9:00 PM (chains 1B -> 1C)' },
  { fn: 'runAgent5B',         weekDay: 'FRIDAY',     hour: 12,               describe: 'Friday 12:00 PM (chains Agent6)' },
  { fn: 'runAgentReminder',   weekDay: 'SUNDAY',     hour: 18,               describe: 'Sunday 6:00 PM' },
  { fn: 'runAgentDuplicate',  everyDays: 1,          hour: 21, minute: 30,   describe: 'Daily 9:30 PM' },
  { fn: 'runAgentEscalation', everyDays: 1,          hour: 7,                describe: 'Daily 7:00 AM' },
  { fn: 'runAgent4',          weekDay: 'MONDAY',     hour: 7,                describe: 'Monday 7:00 AM' },
  { fn: 'runAgentScores',     weekDay: 'MONDAY',     hour: 0,  minute: 5,    describe: 'Monday 12:05 AM' }
];

/**
 * Handler functions the chain schedules for itself at runtime via
 * CCSM_Helpers.scheduleNext() (one-shot "after N minutes" triggers). They are
 * never part of CCSM_TRIGGER_SCHEDULE, but deleteAllCcsmTriggers() and the
 * smoke test's inventory both need to know they are legitimate.
 */
var CCSM_CHAINED_HANDLERS = ['runAgent1B', 'runAgent1C', 'runAgent6'];


// ═════════════════════════════════════════════════════════════════════════════
// TRIGGER INSTALL / REMOVE
// ═════════════════════════════════════════════════════════════════════════════

/**
 * Installs every trigger in CCSM_TRIGGER_SCHEDULE, in mission-local time.
 *
 * Idempotent: each function's existing triggers are deleted immediately
 * before its new one is created, so running this twice leaves exactly one
 * trigger per scheduled function. Zero-argument — run it straight from the
 * Apps Script editor.
 *
 * Nothing calls this automatically. Installing triggers means real emails
 * start flowing on a schedule, so it stays a deliberate human action.
 */
function setupAllCcsmTriggers() {
  var tz = getMissionTimezone();

  CCSM_TRIGGER_SCHEDULE.forEach(function(spec) {
    deleteTriggerByName(spec.fn);

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

  Logger.log('CCSM_Setup: ' + CCSM_TRIGGER_SCHEDULE.length +
    ' trigger(s) installed. runAgent2 is intentionally NOT scheduled — run it manually once per transfer.');
}

/**
 * Removes EVERY trigger in this Apps Script project — the scheduled ones, any
 * one-shot chain trigger CCSM_Helpers.scheduleNext() left behind, and any
 * stale handler from an earlier setup. The CCSM project hosts nothing but
 * PMG Compass, so "all triggers" and "all CCSM triggers" are the same set.
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

  var missingTabs = CCSM_TAB_SPECS.filter(function(t) { return !present[t.name]; })
                                  .map(function(t) { return t.name; });
  if (missingTabs.length) fail('Missing tab(s): ' + missingTabs.join(', ') + '. Run buildCcsmSheet().');
  else ok('All ' + CCSM_TAB_SPECS.length + ' required tabs present.');

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

  var kb = present['KNOWLEDGE_BASE'];
  if (kb) {
    var kbRows = Math.max(kb.getLastRow() - 1, 0);
    if (kbRows > 0) ok('KNOWLEDGE_BASE: ' + kbRows + ' entry(ies).');
    else warn('KNOWLEDGE_BASE is empty — run seedCcsmKnowledgeBase().');
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

  var known = CCSM_TRIGGER_SCHEDULE.map(function(s) { return s.fn; }).concat(CCSM_CHAINED_HANDLERS);
  Object.keys(counts).forEach(function(fn) {
    if (known.indexOf(fn) === -1) warn('Unrecognized trigger handler installed: ' + fn + '.');
  });
  if (counts['runAgent2']) {
    warn('runAgent2 is scheduled. It is meant to be run MANUALLY once per transfer.');
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
 * see what missionaries will actually receive, without waiting for Sunday and
 * without running the 1A -> 1B -> 1C chain over real data.
 *
 * The sample text is REAL MESSAGE_BANK content, picked (never generated) the
 * same way Agent1B picks it — that is the whole point of the preview. It reads
 * MESSAGE_BANK and MISSION_ORG only; it writes nothing.
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
  cs_loggedRun_('AgentEscalation', function() {
    runNightlyEscalation();
    runWeeklyEscalation();
  });
}

/**
 * Runs `body` and records the outcome in AGENT_RUN_LOG.
 *
 * CCSM_AgentReminder.gs and CCSM_AgentEscalation.gs are the only two agents on
 * the trigger schedule that never call CCSM_Helpers.logRun() themselves — both
 * report to AUDIT_LOG instead. That leaves AGENT_RUN_LOG (and therefore
 * Agent4's CHECK 10 "did every agent run recently" audit, and any human
 * scanning the tab after an incident) with no record that they ever fired.
 * The trigger entry point is the right place to close that gap without
 * changing either agent's own behaviour.
 *
 * Never rethrows: a failed run must still leave an ERROR row behind.
 * Private to CCSM_Setup.gs.
 */
function cs_loggedRun_(agentName, body) {
  var startMs = new Date().getTime();
  var status  = 'SUCCESS';
  var note    = 'Ran from the ' + agentName + ' trigger (CCSM_Setup.gs).';
  var errMsg  = '';

  try {
    body();
  } catch (e) {
    status = 'ERROR';
    errMsg = e.message;
    note   = 'FATAL: ' + e.message;
    Logger.log(agentName + ' FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  logRun(agentName, status, null, null, new Date().getTime() - startMs, note, errMsg);
}
