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
  'CCSM_AgentReminder.gs', 'CCSM_AgentScores.gs', 'CCSM_AgentValidation.gs',
  'CCSM_SeedContent.gs', 'CCSM_Setup.gs',
];

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
  { fn: 'runAgent5A',         onWeekDay: 'SUNDAY', atHour: 22 },
  { fn: 'runAgent1A',         onWeekDay: 'SUNDAY', atHour: 21 },
  { fn: 'runAgent5B',         onWeekDay: 'FRIDAY', atHour: 12 },
  { fn: 'runAgentReminder',   onWeekDay: 'SUNDAY', atHour: 18 },
  { fn: 'runAgentDuplicate',  everyDays: 1,        atHour: 21, nearMinute: 30 },
  { fn: 'runAgentEscalation', everyDays: 1,        atHour: 7 },
  { fn: 'runAgent4',          onWeekDay: 'MONDAY', atHour: 7 },
  { fn: 'runAgentScores',     onWeekDay: 'MONDAY', atHour: 0,  nearMinute: 5 },
];

scope.setupAllCcsmTriggers();

assert.strictEqual(
  env.state.triggers.length, EXPECTED_TRIGGERS.length,
  'setupAllCcsmTriggers must install exactly ' + EXPECTED_TRIGGERS.length +
  ' triggers, got ' + env.state.triggers.length + ': ' +
  env.state.triggers.map((t) => t.handlerFunctionName).join(', ')
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

assert.strictEqual(env.state.triggers.length, EXPECTED_TRIGGERS.length,
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
// Source hygiene — same acceptance greps every other CCSM file carries.
// ===========================================================================
const src = require('fs').readFileSync('CCSM_Setup.gs', 'utf8');
assert.ok(!/Utah Provo/i.test(src), 'CCSM_Setup.gs must not contain "Utah Provo"');
assert.ok(!/America\/Denver/.test(src), 'CCSM_Setup.gs must not contain "America/Denver"');
assert.ok(!/Session\.getScriptTimeZone/.test(src),
  'CCSM_Setup.gs must read the timezone from AGENT_CONFIG, not Session.getScriptTimeZone()');
assert.ok(!/sister|ellis|agent7|referral/i.test(src),
  'CCSM_Setup.gs must not reintroduce the deliberately-unported systems');
assert.ok(/America\/Santiago/.test(src),
  'CCSM_Setup.gs header must document the required America/Santiago project timezone');

console.log('setup OK');
