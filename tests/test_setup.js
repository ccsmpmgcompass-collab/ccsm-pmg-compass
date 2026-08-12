// test_setup.js — CCSM_Setup.gs (trigger installer + operator entry points).
//
// Asserts:
//   (a) setupAllCcsmTriggers() installs EXACTLY the project trigger schedule
//       documented in CCSM_Setup.gs's header (function, day/interval, hour,
//       minute, timezone), and installs NO trigger for runAgent2 (manual,
//       once per transfer).
//   (b) It is idempotent — running it twice leaves the same trigger count and
//       the same per-function counts (it deletes same-named triggers first).
//   (c) deleteAllCcsmTriggers() removes every one of them.
//   (d) Every operator entry point is ZERO-ARGUMENT. The Apps Script editor's
//       Run button passes no arguments and there is no console, so anything a
//       human runs by hand must take none.
//   (e) smokeTestPipeline() sends no email and mutates no tab.
//   (f) previewOneCoachingEmail() sends exactly one Spanish email, to the
//       TEST inbox.
//   (g) setupAllCcsmTriggers() CONVERGES: whatever off-table time-based
//       triggers a legacy per-agent installer left behind, one run leaves the
//       project's time-based triggers exactly equal to CCSM_TRIGGER_SCHEDULE —
//       while the two installable FORM-SUBMIT triggers survive untouched.
//   (h) The legacy per-agent installers cannot re-create a competing schedule.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, setConfig } = require('./fixtures');
const assert = require('assert');

const TEST_INBOX = 'CCSM.PMG.Compass@gmail.com';
const MISSION_TZ = 'America/Santiago';

const GS_FILES = [
  'CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
  'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs', 'CCSM_Agent2.gs',
  'CCSM_Agent3.gs', 'CCSM_Agent4.gs', 'CCSM_Agent5A.gs', 'CCSM_Agent5B.gs',
  'CCSM_Agent6.gs', 'CCSM_AgentDuplicate.gs', 'CCSM_AgentEscalation.gs',
  'CCSM_AgentMissionReport.gs', 'CCSM_AgentQA.gs', 'CCSM_AgentReminder.gs',
  'CCSM_AgentScores.gs', 'CCSM_AgentValidation.gs', 'CCSM_SeedContent.gs',
  'CCSM_Setup.gs',
];

// The two installable form-submit triggers. Not on CCSM_TRIGGER_SCHEDULE
// (they are not time-based), but setupAllCcsmTriggers() must install them,
// never sweep them, and smokeTestPipeline() must fail when they are absent.
const EXPECTED_FORM_SUBMIT = ['onNightlyFormSubmit', 'onQAFormSubmit'];

const clockTriggers = () => env.state.triggers.filter((t) => t.getEventType() === 'CLOCK');
const submitTriggers = () => env.state.triggers.filter((t) => t.getEventType() === 'ON_FORM_SUBMIT');

const env = makeGasEnv();
const scope = loadGs(GS_FILES, env.globals);
const ss = makeCcsmSpreadsheet(env, scope);

// CCSM_Helpers.readAgentConfig() caches AGENT_CONFIG for the whole execution
// (globals reset between real Apps Script runs, so that is correct there).
// Every config value this suite depends on must therefore be written BEFORE
// the first getConfig() call — i.e. before any agent or setup function runs.
setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');
setConfig(env, ss, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
setConfig(env, ss, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');

// ===========================================================================
// (a) The trigger table — verbatim from the task brief / CCSM_Setup.gs header.
// ===========================================================================
const EXPECTED_TRIGGERS = [
  { fn: 'runAgent3',          everyDays: 1,        atHour: 6 },
  { fn: 'runAgent3Evening',   everyDays: 1,        atHour: 21 },
  { fn: 'runAgent5A',         everyDays: 1,        atHour: 12 },
  { fn: 'runAgent1A',         onWeekDay: 'MONDAY', atHour: 21, nearMinute: 30 },
  { fn: 'runAgent5B',         onWeekDay: 'FRIDAY', atHour: 12 },
  { fn: 'runAgentReminder',   onWeekDay: 'SUNDAY', atHour: 18 },
  { fn: 'runAgentDuplicate',  everyDays: 1,        atHour: 21, nearMinute: 30 },
  { fn: 'runAgentEscalation', everyDays: 1,        atHour: 7 },
  { fn: 'runAgent4',          onWeekDay: 'MONDAY', atHour: 7 },
  { fn: 'runAgentScores',     onWeekDay: 'MONDAY', atHour: 0,  nearMinute: 5 },
  { fn: 'runAgentMissionReport', onWeekDay: 'MONDAY', atHour: 22 },
];

scope.setupAllCcsmTriggers();

assert.strictEqual(
  clockTriggers().length, EXPECTED_TRIGGERS.length,
  'setupAllCcsmTriggers must install exactly ' + EXPECTED_TRIGGERS.length +
  ' time-based triggers, got ' + clockTriggers().length + ': ' +
  clockTriggers().map((t) => t.handlerFunctionName).join(', ')
);

assert.deepStrictEqual(
  submitTriggers().map((t) => t.handlerFunctionName).sort(),
  EXPECTED_FORM_SUBMIT.slice().sort(),
  'setupAllCcsmTriggers must also install both installable form-submit triggers'
);

EXPECTED_TRIGGERS.forEach((want) => {
  const got = env.state.triggers.filter((t) => t.handlerFunctionName === want.fn);
  assert.strictEqual(got.length, 1, 'expected exactly one trigger for ' + want.fn);
  const t = got[0];
  assert.strictEqual(t.type, 'CLOCK', want.fn + ' must be a time-based trigger');
  assert.strictEqual(t.atHour, want.atHour, want.fn + ' must fire at hour ' + want.atHour);
  assert.strictEqual(t.timeZone, MISSION_TZ,
    want.fn + ' must be pinned to the mission timezone, got ' + t.timeZone);
  if (want.everyDays !== undefined) {
    assert.strictEqual(t.everyDays, want.everyDays, want.fn + ' must repeat every ' + want.everyDays + ' day(s)');
    assert.strictEqual(t.onWeekDay, undefined, want.fn + ' is a daily trigger, not a weekly one');
  } else {
    assert.strictEqual(t.onWeekDay, want.onWeekDay, want.fn + ' must fire on ' + want.onWeekDay);
    assert.strictEqual(t.everyDays, undefined, want.fn + ' is a weekly trigger, not a daily one');
  }
  if (want.nearMinute !== undefined) {
    assert.strictEqual(t.nearMinute, want.nearMinute, want.fn + ' must aim for minute ' + want.nearMinute);
  }
});

// runAgent2 is explicitly "none (manual, once per transfer)".
assert.ok(
  !env.state.triggers.some((t) => t.handlerFunctionName === 'runAgent2'),
  'runAgent2 must NOT be scheduled — it is run manually once per transfer'
);

console.log('setup trigger table OK');

// ===========================================================================
// (b) Idempotency — a second run must not double anything up.
// ===========================================================================
const firstCounts = {};
env.state.triggers.forEach((t) => {
  firstCounts[t.handlerFunctionName] = (firstCounts[t.handlerFunctionName] || 0) + 1;
});

scope.setupAllCcsmTriggers();

const secondCounts = {};
env.state.triggers.forEach((t) => {
  secondCounts[t.handlerFunctionName] = (secondCounts[t.handlerFunctionName] || 0) + 1;
});

assert.strictEqual(env.state.triggers.length, EXPECTED_TRIGGERS.length + EXPECTED_FORM_SUBMIT.length,
  'setupAllCcsmTriggers must be idempotent — second run left ' + env.state.triggers.length + ' triggers');
assert.deepStrictEqual(secondCounts, firstCounts,
  'per-function trigger counts must be identical after a second run');

console.log('setup idempotency OK');

// ===========================================================================
// (c) deleteAllCcsmTriggers() clears them.
// ===========================================================================
scope.deleteAllCcsmTriggers();
assert.strictEqual(env.state.triggers.length, 0,
  'deleteAllCcsmTriggers must remove every trigger, ' + env.state.triggers.length + ' left');

// Re-install so the smoke test below sees a healthy trigger inventory.
scope.setupAllCcsmTriggers();

console.log('deleteAllCcsmTriggers OK');

// ===========================================================================
// (g) CONVERGENCE — the canonical installer must clear OFF-TABLE handlers.
//
// The legacy per-agent installers used to create handler names that appear
// nowhere in CCSM_TRIGGER_SCHEDULE (runReminderAgent hourly,
// runNightlyEscalation 10:00, runWeeklyEscalation 20:45,
// notifyAcceptedSuggestions every 10 min). A per-name refresh cannot clear
// those, so escalation would fire at 07:00 AND 10:00 AND 20:45. Seed them
// directly through ScriptApp — the shape a project is in after someone picks
// one of those functions out of the editor dropdown — and assert one run of
// setupAllCcsmTriggers() leaves the time-based set EXACTLY equal to the table.
// ===========================================================================
const OFF_TABLE = ['runReminderAgent', 'runWeeklyEscalation', 'runNightlyEscalation',
                   'notifyAcceptedSuggestions'];

env.globals.ScriptApp.newTrigger('runReminderAgent').timeBased().everyHours(1).create();
env.globals.ScriptApp.newTrigger('runNightlyEscalation').timeBased()
  .everyDays(1).atHour(10).inTimezone(MISSION_TZ).create();
env.globals.ScriptApp.newTrigger('runWeeklyEscalation').timeBased()
  .everyDays(1).atHour(20).nearMinute(45).inTimezone(MISSION_TZ).create();
env.globals.ScriptApp.newTrigger('notifyAcceptedSuggestions').timeBased().everyMinutes(10).create();
// A pending one-shot chain trigger, the other thing a real project can be
// holding when someone runs setup.
env.globals.ScriptApp.newTrigger('runAgent1B').timeBased().after(300000).create();

const submitUidsBefore = submitTriggers().map((t) => t.uid).sort();
assert.strictEqual(submitUidsBefore.length, EXPECTED_FORM_SUBMIT.length,
  'precondition: both form-submit triggers are installed before the converge run');

scope.setupAllCcsmTriggers();

assert.deepStrictEqual(
  clockTriggers().map((t) => t.handlerFunctionName).sort(),
  EXPECTED_TRIGGERS.map((t) => t.fn).sort(),
  'setupAllCcsmTriggers must converge: the project\'s time-based triggers must end up ' +
  'exactly equal to CCSM_TRIGGER_SCHEDULE, got ' +
  clockTriggers().map((t) => t.handlerFunctionName).join(', ')
);

// Named, not merely counted — a matching count would also pass if the sweep
// had deleted a table handler and left an off-table one.
OFF_TABLE.concat(['runAgent1B']).forEach((fn) => {
  assert.ok(!env.state.triggers.some((t) => t.handlerFunctionName === fn),
    'off-table handler ' + fn + ' must be gone after setupAllCcsmTriggers()');
});

// Form-submit triggers must SURVIVE — same trigger objects, not deleted and
// recreated (recreating one re-authorizes and can drop in-flight events).
assert.deepStrictEqual(submitTriggers().map((t) => t.uid).sort(), submitUidsBefore,
  'the two form-submit triggers must survive a converge run untouched');

console.log('setup converge-to-table OK');

// ===========================================================================
// (h) The legacy per-agent installers can no longer create a competing
//     schedule — each one now delegates to setupAllCcsmTriggers(). Three
//     used to install off-table handler names; three more (found 2026-08-01
//     while retiming Agent1A for Phase 5) installed the RIGHT handler on a
//     schedule that had drifted from the table — Agent1A on Sunday (table:
//     Monday), Agent4 on Tue+Sat (table: Monday only), Agent5A daily
//     (table: weekly Sunday) — which is worse, since deleteTriggerByName()
//     means running one doesn't add a duplicate, it REPLACES the canonical
//     trigger with the stale schedule.
// ===========================================================================
['setupReminderTrigger', 'setupEscalationTriggers', 'setupSuggestionNotifyTrigger',
 'setupAgent1ATrigger', 'setupAgent4Trigger', 'setupAgent5ATrigger',
 'setupAgentMissionReportTrigger']
  .forEach((name) => {
    assert.strictEqual(typeof scope[name], 'function', name + ' must still exist');
    assert.strictEqual(scope[name].length, 0, name + ' must be zero-argument');

    scope[name]();

    assert.deepStrictEqual(
      clockTriggers().map((t) => t.handlerFunctionName).sort(),
      EXPECTED_TRIGGERS.map((t) => t.fn).sort(),
      name + '() must not install an off-table schedule — after running it the project\'s ' +
      'time-based triggers must still equal CCSM_TRIGGER_SCHEDULE, got ' +
      clockTriggers().map((t) => t.handlerFunctionName).join(', ')
    );
  });

console.log('legacy installers converge OK');

// ===========================================================================
// (d) Every human-invoked entry point takes ZERO arguments.
//     The Apps Script Run button passes none and the editor has no console.
// ===========================================================================
['setupAllCcsmTriggers', 'deleteAllCcsmTriggers', 'smokeTestPipeline', 'previewOneCoachingEmail']
  .forEach((name) => {
    assert.strictEqual(typeof scope[name], 'function', name + ' must exist');
    assert.strictEqual(scope[name].length, 0,
      name + ' must be zero-argument (Apps Script Run button passes no arguments), declares ' +
      scope[name].length);
  });

// The trigger handlers themselves must also be zero-argument — a time-based
// trigger passes an event object no handler here uses, and each is also run
// by hand from the editor during setup.
['runAgentReminder', 'runAgentDuplicate', 'runAgentEscalation'].forEach((name) => {
  assert.strictEqual(typeof scope[name], 'function', name + ' must exist');
  assert.strictEqual(scope[name].length, 0, name + ' must be zero-argument');
});

console.log('setup entry points zero-arg OK');

// ===========================================================================
// (e) smokeTestPipeline() is read-only: no emails, no tab mutation.
// ===========================================================================
scope.seedCcsmMessageBank();
scope.seedCcsmKnowledgeBase();
// runAgentScores (Monday 12:05 AM) is on the schedule, so an unseeded
// SCORE_CONFIG is a pre-flight ERROR, not a passing state.
scope.setupCcsmScoreConfig();

function snapshotTabs() {
  return JSON.stringify(ss.getSheets().map((s) => [s.getName(), s.getLastRow(), s.getLastColumn()]));
}

const beforeTabs = snapshotTabs();
const emailsBefore = env.state.emails.length;

const report = scope.smokeTestPipeline();

assert.strictEqual(env.state.emails.length, emailsBefore,
  'smokeTestPipeline must not send any email');
assert.strictEqual(snapshotTabs(), beforeTabs,
  'smokeTestPipeline must not mutate any tab');
assert.ok(report && Array.isArray(report.errors) && Array.isArray(report.warnings),
  'smokeTestPipeline must return { ok, errors[], warnings[], lines[] }');
assert.deepStrictEqual(report.errors, [],
  'smokeTestPipeline must report zero errors on a fully-configured sheet: ' + report.errors.join(' | '));
assert.strictEqual(report.ok, true, 'smokeTestPipeline must report ok=true on a healthy sheet');

// Negative controls — prove the two assertions above discriminate.
//
// 1. An unseeded SCORE_CONFIG must be an ERROR, not a silent pass: it is what
//    runAgentScores reads its weights from.
(() => {
  const sc = ss.getSheetByName('SCORE_CONFIG');
  const saved = sc.getDataRange().getValues();
  sc.clear();
  const broken = scope.smokeTestPipeline();
  assert.ok(broken.errors.some((e) => /SCORE_CONFIG/.test(e)),
    'an empty SCORE_CONFIG must be a smoke-test ERROR, got: ' + broken.errors.join(' | '));
  scope.overwriteTab('SCORE_CONFIG', saved);
})();

// 2. A missing form-submit trigger must be an ERROR (it silently disables
//    submit-time duplicate detection / all of AgentQA), never a "unrecognized
//    handler" WARNING for its presence.
(() => {
  const victim = env.state.triggers.find((t) => t.handlerFunctionName === 'onNightlyFormSubmit');
  env.globals.ScriptApp.deleteTrigger(victim);

  const broken = scope.smokeTestPipeline();
  assert.ok(broken.errors.some((e) => /onNightlyFormSubmit/.test(e)),
    'a missing onNightlyFormSubmit trigger must be a smoke-test ERROR, got: ' +
    broken.errors.join(' | '));

  // And nothing may ever call a legitimately-installed form-submit handler
  // "unrecognized".
  const healthy = (() => { scope.setupAllCcsmTriggers(); return scope.smokeTestPipeline(); })();
  assert.deepStrictEqual(healthy.errors, [],
    'restored project must be error-free: ' + healthy.errors.join(' | '));
  assert.ok(!healthy.warnings.some((w) => /Unrecognized trigger handler/.test(w)),
    'form-submit handlers must not be reported as unrecognized: ' + healthy.warnings.join(' | '));
})();

// 3. A project timezone that disagrees with MISSION_TIMEZONE must be an ERROR
//    (integration I-4). The Apps Script PROJECT timezone is a separate setting
//    from AGENT_CONFIG's MISSION_TIMEZONE, and plain local-date arithmetic in
//    the agents resolves against the PROJECT one. When they disagree the
//    coaching week silently slips a day — no exception, no failed send, just
//    wrong dates. There is no API to set the project timezone, so the smoke
//    test is the only thing that can catch it.
//
//    This needs its own env: the stub used to hardcode getScriptTimeZone() to
//    MISSION_TZ, which made the two permanently equal and this case impossible
//    to express — the harness was guaranteeing the invariant the production
//    code needed to verify.
(() => {
  const tzEnv = makeGasEnv({ scriptTimeZone: 'America/Los_Angeles' }); // the Apps Script default
  const tzScope = loadGs(GS_FILES, tzEnv.globals);
  const tzSs = makeCcsmSpreadsheet(tzEnv, tzScope);
  setConfig(tzEnv, tzSs, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
  setConfig(tzEnv, tzSs, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');

  const mismatched = tzScope.smokeTestPipeline();
  assert.ok(
    mismatched.errors.some((e) => /PROJECT timezone/i.test(e) && /America\/Los_Angeles/.test(e)),
    'a project timezone differing from MISSION_TIMEZONE must be a smoke-test ERROR naming ' +
    'both values, got: ' + mismatched.errors.join(' | ')
  );

  // And a matching project timezone must NOT produce that error.
  const okEnv = makeGasEnv({ scriptTimeZone: MISSION_TZ });
  const okScope = loadGs(GS_FILES, okEnv.globals);
  const okSs = makeCcsmSpreadsheet(okEnv, okScope);
  setConfig(okEnv, okSs, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
  setConfig(okEnv, okSs, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');
  const matched = okScope.smokeTestPipeline();
  assert.ok(!matched.errors.some((e) => /PROJECT timezone/i.test(e)),
    'a matching project timezone must not raise the timezone error: ' + matched.errors.join(' | '));
})();

// 4. A DUPLICATE form-submit trigger must be an ERROR (known-open minor (d)).
//    The inventory check only asked "at least one?", so a doubly-installed
//    handler passed silently — and it is easy to reach, because the converge
//    sweep deliberately spares form-submit triggers. Every submission then
//    fires the handler twice: duplicate emails to a real missionary.
(() => {
  const spec = env.state.triggers.find((t) => t.handlerFunctionName === 'onNightlyFormSubmit');
  assert.ok(spec, 'expected an installed onNightlyFormSubmit trigger to duplicate');

  // Install a SECOND trigger for the same handler, exactly as re-attaching the
  // form would.
  env.globals.ScriptApp.newTrigger('onNightlyFormSubmit')
    .forSpreadsheet(ss).onFormSubmit().create();

  const dup = scope.smokeTestPipeline();
  assert.ok(dup.errors.some((e) => /Duplicate form-submit/i.test(e) && /onNightlyFormSubmit/.test(e)),
    'a duplicate form-submit trigger must be a smoke-test ERROR, got: ' + dup.errors.join(' | '));

  // Re-running the INSTALLER alone must NOT be enough to clear this: the
  // converge sweep spares form-submit triggers by design, so it cannot remove
  // a duplicate one. Asserting that here keeps the remedy in the error message
  // honest — it tells the operator to deleteAll first, and this is why.
  scope.setupAllCcsmTriggers();
  const stillDup = scope.smokeTestPipeline();
  assert.ok(stillDup.errors.some((e) => /Duplicate form-submit/i.test(e)),
    'setupAllCcsmTriggers() alone cannot clear a duplicate form-submit trigger (the sweep ' +
    'spares them), so the error must persist — if this stops being true, update the ' +
    'remedy text in CCSM_Setup.gs');

  // The documented remedy does work.
  scope.deleteAllCcsmTriggers();
  scope.setupAllCcsmTriggers();
  const restored = scope.smokeTestPipeline();
  assert.deepStrictEqual(restored.errors, [],
    'deleteAllCcsmTriggers() + setupAllCcsmTriggers() must produce an error-free project: ' +
    restored.errors.join(' | '));
})();

console.log('smokeTestPipeline OK');

// ===========================================================================
// (f) previewOneCoachingEmail() — exactly one Spanish sample to the test inbox.
// ===========================================================================
const beforePreview = env.state.emails.length;
scope.previewOneCoachingEmail();
const previewEmails = env.state.emails.slice(beforePreview);

assert.strictEqual(previewEmails.length, 1, 'previewOneCoachingEmail must send exactly one email');
const pv = previewEmails[0];
assert.strictEqual(pv.to, TEST_INBOX, 'preview must land in the TEST inbox');
assert.ok(pv.subject.indexOf('[TEST] ') === 0, 'preview subject must carry the [TEST] prefix: ' + pv.subject);
assert.ok(/Muestra|Ejemplo|Entrenamiento|Informe/.test(pv.subject),
  'preview subject must be Spanish: ' + pv.subject);
assert.ok(!/Sample|Preview|Coaching Email/i.test(pv.subject),
  'preview subject must not leak English: ' + pv.subject);

console.log('previewOneCoachingEmail OK');

// ===========================================================================
// (i) A failed wrapped run must leave an AGENT_RUN_LOG ERROR row AND still
//     throw. Apps Script emails the project owner its automatic "your script
//     failed" notice only when a trigger handler throws; the eight unwrapped
//     handlers on the schedule all propagate, so swallowing here would make
//     AgentReminder and AgentEscalation the only two agents whose total
//     failure is silent until someone opens a tab.
// ===========================================================================
function runLogRows() {
  return ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
}
const beforeRunLog = runLogRows().length;

assert.throws(
  () => scope.cs_loggedRun_('AgentReminder', () => { throw new Error('boom-single'); }),
  /boom-single/,
  'cs_loggedRun_ must rethrow so Apps Script notifies the project owner'
);

const afterSingle = runLogRows();
assert.strictEqual(afterSingle.length, beforeRunLog + 1,
  'the failed run must still have left exactly one AGENT_RUN_LOG row');
const errRow = afterSingle[afterSingle.length - 1];
assert.ok(errRow.indexOf('ERROR') !== -1,
  'the row cs_loggedRun_ left behind must be an ERROR row: ' + JSON.stringify(errRow));

// cs_runAndLog_ is the multi-body form: it RETURNS the failure instead of
// throwing, which is what lets runAgentEscalation() run System 2 even when
// System 1 blew up (they had separate triggers before this file existed).
const ran = [];
const err1 = scope.cs_runAndLog_('AgentEscalation', 'System 1 (nightly form)', () => {
  ran.push('system1'); throw new Error('boom-nightly');
});
const err2 = scope.cs_runAndLog_('AgentEscalation', 'System 2 (weekly form)', () => {
  ran.push('system2');
});
assert.deepStrictEqual(ran, ['system1', 'system2'],
  'System 2 must still run after System 1 throws');
assert.ok(err1 instanceof Error && /boom-nightly/.test(err1.message),
  'cs_runAndLog_ must return the caught error rather than throwing it');
assert.strictEqual(err2, null, 'cs_runAndLog_ must return null on success');

console.log('cs_loggedRun_ logs and rethrows OK');

// ===========================================================================
// Source hygiene — same acceptance greps every other CCSM file carries.
// ===========================================================================
// Resolved against this file's own directory so the suite runs from anywhere,
// not only from the repo root.
const src = require('fs').readFileSync(
  require('path').join(__dirname, '..', 'CCSM_Setup.gs'), 'utf8');
assert.ok(!/Utah Provo/i.test(src), 'CCSM_Setup.gs must not contain "Utah Provo"');
assert.ok(!/America\/Denver/.test(src), 'CCSM_Setup.gs must not contain "America/Denver"');
// The rule this encodes is "timezones that get USED come from AGENT_CONFIG",
// not "the string Session.getScriptTimeZone never appears". Those were the
// same thing until integration I-4, whose fix must READ the project timezone
// in order to compare it with MISSION_TIMEZONE and reject a mismatch. A
// blanket ban would have forbidden the only available fix for a bug nothing
// else can detect, so it is narrowed to the actual intent.
// Counts INVOCATIONS, not mentions: the call site is guarded by a
// `typeof Session !== 'undefined' && Session.getScriptTimeZone` existence
// check, which names the method without calling it.
const scriptTzReads = (src.match(/Session\.getScriptTimeZone\(\)/g) || []).length;
assert.strictEqual(scriptTzReads, 1,
  'CCSM_Setup.gs should CALL Session.getScriptTimeZone() exactly once — solely to compare ' +
  'the project timezone against MISSION_TIMEZONE. Found ' + scriptTzReads + '.');
assert.ok(!/inTimezone\(\s*Session\./.test(src),
  'triggers must be pinned with the AGENT_CONFIG timezone, never Session.getScriptTimeZone()');
assert.ok(!/sister|ellis|agent7|referral/i.test(src),
  'CCSM_Setup.gs must not reintroduce the deliberately-unported systems');
assert.ok(/America\/Santiago/.test(src),
  'CCSM_Setup.gs header must document the required America/Santiago project timezone');

console.log('setup OK');
