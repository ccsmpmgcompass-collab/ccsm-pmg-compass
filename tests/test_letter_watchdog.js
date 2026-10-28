// test_letter_watchdog.js — the Monday letters retry themselves
// (PLAN-2026-10-13-letter-watchdog.md).
//
// Part A runs the real 1A -> 1B -> 1C chain. Each step marks LETTER_CHAIN_STATE,
// Agent1A books the first watchdog check, and a restarted Agent1C skips
// whoever the killed run already reached (no double sends, D5).
//
// Part B drives the watchdog at chosen moments of the week ending Sun
// 2026-10-11, the week Apps Script killed runAgent1A at 21:33 on Monday. The
// process clock is pinned to America/Santiago (gas_stubs.js), so
// new Date(2026, 9, 12, 21, 40) is Monday 21:40 in mission time.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');

const GS = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
  'CCSM_Agent3.gs', 'CCSM_Agent5A.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs',
  'CCSM_LetterWatchdog.gs'];

const geminiEnvelope = JSON.stringify({
  candidates: [{ content: { parts: [{ text: JSON.stringify({ Arauco: 'Narrativa de prueba.' }) }] } }],
});

function setup(config) {
  const env = makeGasEnv({
    urlFetch: () => ({ getResponseCode: () => 200, getContentText: () => geminiEnvelope }),
  });
  const scope = loadGs(GS, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TEST_MODE', 'FALSE');
  Object.keys(config || {}).forEach((k) => setConfig(env, ss, k, config[k]));
  return { env, scope, ss };
}

const props = (env) => env.state.props.script;
const state = (env) => JSON.parse(props(env).LETTER_CHAIN_STATE || 'null');
const handlers = (env) => env.state.triggers.map((t) => t.handlerFunctionName);
function lastRun(ss) {
  const log = ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
  return log[log.length - 1];
}

// ── A. The real chain marks its state; a restarted 1C never sends twice. ──────
{
  const { env, scope, ss } = setup();
  addNightlyRaw(env, ss, []);
  // The fixture roster's addresses are placeholders Agent1C skips; give two
  // sectors real ones (as test_agent1c_ki_pdfs.js does).
  const org = ss.getSheetByName('MISSION_ORG');
  const data = org.getDataRange().getValues();
  const h = data[0];
  for (let i = 1; i < data.length; i++) {
    const area = data[i][h.indexOf('Area_Name')];
    if (area === 'Arauco 1') org.getRange(i + 1, h.indexOf('Companion1_Email') + 1).setValue('zl.arauco1@missionary.org');
    if (area === 'Arauco 2') org.getRange(i + 1, h.indexOf('Companion1_Email') + 1).setValue('arauco2@missionary.org');
  }
  ss.insertSheet('MISSION_LEADERSHIP').getRange(1, 1, 3, 5).setValues([
    ['Name', 'Email', 'Role', 'Active', 'Notes'],
    ['Presidente', 'presidente@churchofjesuschrist.org', 'president', 'TRUE', ''],
    ['AP Uno', 'ap.uno@missionary.org', 'assistant', 'TRUE', ''],
  ]);

  scope.runAgent1A();
  const week = scope.loadTempData('A1A_DATA').weekEnd;
  assert.deepStrictEqual([state(env).week, state(env).step, state(env).state], [week, '1B', 'scheduled'],
    'after Agent1A: Agent1B is scheduled');
  assert.ok(handlers(env).includes('runLetterWatchdogRetry'), 'Agent1A books the first watchdog check');

  scope.runAgent1B();
  assert.deepStrictEqual([state(env).step, state(env).state], ['1C', 'scheduled'], 'after Agent1B: Agent1C is scheduled');

  // Apps Script killed the first Agent1C after it had reached these two.
  props(env)['A1C_SENT_' + week] = JSON.stringify(['ap.uno@missionary.org', 'presidente@churchofjesuschrist.org']);
  props(env)['A1C_SENT_2026-01-04'] = JSON.stringify(['someone@missionary.org']);   // an old week's record
  scope.runAgent1C();

  const to = env.state.emails.map((e) => e.to);
  assert.ok(to.length > 0, 'the restart sends the rest');
  assert.ok(!to.includes('ap.uno@missionary.org') && !to.includes('presidente@churchofjesuschrist.org'),
    'nobody the killed run reached gets the letter twice: ' + to.join(', '));
  assert.ok(/Already sent before a restart, skipped: 2/.test(lastRun(ss)[7]), lastRun(ss)[7]);
  // AUDIT-2026-10-28 F3 + F6: the run says how long it took and how big its
  // biggest letter was.
  assert.ok(/Largest letter: \d+\.\d KB \(/.test(lastRun(ss)[7]), lastRun(ss)[7]);
  assert.ok(!/WARNING: \d+ letter\(s\) over/.test(lastRun(ss)[7]), 'the fixture letters are small');
  assert.strictEqual(typeof lastRun(ss)[3], 'number');
  assert.strictEqual(scope.a1c_utf8Bytes_('añ'), 3, 'an accented letter counts two bytes');
  assert.deepStrictEqual([state(env).step, state(env).state], ['1C', 'done'], 'Agent1C marks the week done');

  const ledger = JSON.parse(props(env)['A1C_SENT_' + week]);
  assert.strictEqual(ledger.length, to.length + 2, 'the record holds everyone who has the letter now');
  assert.ok(!('A1C_SENT_2026-01-04' in props(env)), 'an older week\'s record is dropped');

  // A third run (another restart) sends nobody anything.
  const before = env.state.emails.length;
  scope.saveTempData('A1B_DATA', scope.loadTempData('A1B_DATA') || { weekEnd: week, areas: {}, summaries: {} });
  scope.runAgent1C();
  assert.strictEqual(env.state.emails.length, before, 'everyone already has it: nothing is sent again');
}

// ── A2. A step that throws marks itself failed. ───────────────────────────────
{
  const { env, scope } = setup();
  scope.runAgent1B();   // no A1A_DATA: throws, logs ERROR
  assert.deepStrictEqual([state(env).step, state(env).state], ['1B', 'failed']);
  assert.ok(/A1A_DATA not found/.test(state(env).note));
}

// ── B. The watchdog's decisions, week ending Sun 2026-10-11. ──────────────────
const WEEK = '2026-10-11';
const MON = (h, m) => new Date(2026, 9, 12, h, m);
function mark(env, step, st, at, week) {
  env.globals.PropertiesService.getScriptProperties().setProperty('LETTER_CHAIN_STATE',
    JSON.stringify({ week: week || WEEK, step, state: st, at: at.getTime(), note: '' }));
}

{
  const { env, scope, ss } = setup({ LETTER_ALERT_EMAIL: 'zackary@example.org' });
  const check = (d) => scope.letterWatchdogCheck_(d);

  assert.strictEqual(check(new Date(2026, 9, 11, 22, 0)), 'outside', 'Sunday night is before the window');

  // Agent1A started two minutes ago: still running, look again later.
  mark(env, '1A', 'running', MON(21, 38));
  assert.strictEqual(check(MON(21, 40)), 'in flight');
  assert.ok(handlers(env).includes('runLetterWatchdogRetry') && !handlers(env).includes('runAgent1A'));

  // The 2026-10-12 case: started 21:27, nothing since -- Apps Script killed it.
  mark(env, '1A', 'running', MON(21, 27));
  assert.strictEqual(check(MON(21, 38)), 'restarted 1A');
  assert.ok(handlers(env).includes('runAgent1ARetry'), 'Agent1A is scheduled again, through its one-shot alias');
  assert.ok(!handlers(env).includes('runAgent1A'), 'never through runAgent1A itself');
  assert.strictEqual(props(env)['LETTER_RETRIES_' + WEEK], '1');
  assert.deepStrictEqual([state(env).step, state(env).state], ['1A', 'scheduled']);
  let run = lastRun(ss);
  assert.deepStrictEqual([run[1], run[2]], ['LetterWatchdog', 'RETRY']);
  assert.ok(/killed by Apps Script/.test(run[7]) && /restarted Agent1A/.test(run[7]), run[7]);

  // Agent1A's payload is there: restart from Agent1B, not from the top.
  scope.saveTempData('A1A_DATA', { weekEnd: WEEK, areas: {}, summaries: {} });
  mark(env, '1B', 'scheduled', MON(21, 30));
  assert.strictEqual(check(MON(21, 45)), 'restarted 1B', 'a scheduled step that never started');
  assert.ok(/never started/.test(lastRun(ss)[7]), lastRun(ss)[7]);

  // Agent1B's too: restart Agent1C.
  scope.saveTempData('A1B_DATA', { weekEnd: WEEK, areas: {}, summaries: {} });
  mark(env, '1C', 'failed', MON(21, 50));
  assert.strictEqual(check(MON(22, 5)), 'restarted 1C');
  assert.strictEqual(props(env)['LETTER_RETRIES_' + WEEK], '3');

  // Payloads from LAST week do not count: start over at Agent1A.
  scope.clearTempData('A1A_DATA');
  scope.saveTempData('A1B_DATA', { weekEnd: '2026-10-04', areas: {}, summaries: {} });
  mark(env, '1C', 'done', MON(12, 0), '2026-10-04');
  assert.strictEqual(check(MON(23, 5)), 'restarted 1A', 'Agent1A never started this week');
  assert.ok(/never started this week/.test(lastRun(ss)[7]), lastRun(ss)[7]);

  // Done: nothing to do, and no more checks booked.
  mark(env, '1C', 'done', MON(23, 20));
  assert.strictEqual(check(MON(23, 35)), 'done');
  assert.ok(!handlers(env).includes('runLetterWatchdogRetry'), 'the re-checks stop once the letters are out');
  assert.strictEqual(check(new Date(2026, 9, 13, 9, 30)), 'done', 'done stays done after the deadline: no alert');
  assert.strictEqual(env.state.emails.length, 0);

  // Tuesday 09:00 and still not done: one alert to LETTER_ALERT_EMAIL, once.
  mark(env, '1A', 'failed', new Date(2026, 9, 13, 8, 50));
  assert.strictEqual(check(new Date(2026, 9, 13, 9, 5)), 'alerted');
  assert.strictEqual(env.state.emails.length, 1);
  const mail = env.state.emails[0];
  assert.strictEqual(mail.to, 'zackary@example.org');
  assert.ok(/did NOT go out/.test(mail.subject) && /2026-10-11/.test(mail.subject), mail.subject);
  assert.ok(/runAgent1A/.test(mail.htmlBody), 'the alert says what to do');
  run = lastRun(ss);
  assert.deepStrictEqual([run[1], run[2]], ['LetterWatchdog', 'ERROR']);
  assert.strictEqual(check(new Date(2026, 9, 13, 9, 25)), 'gave up', 'the alert goes once');
  assert.strictEqual(env.state.emails.length, 1);
  assert.ok(!handlers(env).includes('runLetterWatchdogRetry'), 'and the re-checks stop');

  assert.strictEqual(check(new Date(2026, 9, 14, 10, 0)), 'outside', 'Wednesday is past the window');
}

// ── B2. No LETTER_ALERT_EMAIL: the run log says nobody was told. ──────────────
{
  const { env, scope, ss } = setup();
  mark(env, '1A', 'running', new Date(2026, 9, 12, 21, 27));
  assert.strictEqual(scope.letterWatchdogCheck_(new Date(2026, 9, 13, 9, 15)), 'alerted');
  assert.strictEqual(env.state.emails.length, 0);
  const run = lastRun(ss);
  assert.strictEqual(run[2], 'ERROR');
  assert.ok(/no LETTER_ALERT_EMAIL/.test(run[7]), run[7]);
}

// ── C. A restart keeps the Monday 21:30 trigger (AUDIT-2026-10-28, A). ───────
// On 2026-10-19 the watchdog restarted Agent1A with scheduleNext('runAgent1A'),
// which deleted the weekly trigger, and on 10-26 Agent1A never started.
{
  const env = makeGasEnv({
    urlFetch: () => ({ getResponseCode: () => 200, getContentText: () => geminiEnvelope }),
  });
  const scope = loadGs(GS.concat(['CCSM_Setup.gs']), env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'TEST_MODE', 'FALSE');
  scope.setupAllCcsmTriggers();
  const weekly = () => env.state.triggers.filter((t) => t.handlerFunctionName === 'runAgent1A');
  assert.strictEqual(weekly().length, 1, 'the installer puts in one Monday runAgent1A trigger');
  assert.strictEqual(weekly()[0].onWeekDay, 'MONDAY');

  mark(env, '1A', 'running', MON(21, 27));
  assert.strictEqual(scope.letterWatchdogCheck_(MON(21, 38)), 'restarted 1A');
  assert.strictEqual(weekly().length, 1, 'the restart leaves the weekly trigger alone');
  assert.strictEqual(weekly()[0].onWeekDay, 'MONDAY');
  assert.ok(handlers(env).includes('runAgent1ARetry'));

  // scheduleNext refuses any handler that has a fixed trigger.
  assert.throws(() => scope.scheduleNext('runAgent1A', 1), /fixed trigger/);
  assert.throws(() => scope.scheduleNext('runLetterWatchdog', 1), /fixed trigger/);
  assert.strictEqual(weekly().length, 1, 'and a refused call deletes nothing');

  // The trigger went missing anyway (a hand edit, or the old code on 10-19):
  // the next check puts it back and says so.
  env.globals.ScriptApp.deleteTrigger(weekly()[0]);
  mark(env, '1C', 'done', MON(23, 0));
  assert.strictEqual(scope.letterWatchdogCheck_(MON(23, 5)), 'done');
  assert.strictEqual(weekly().length, 1, 'the check reinstalls it');
  assert.deepStrictEqual([weekly()[0].onWeekDay, weekly()[0].atHour, weekly()[0].nearMinute,
    weekly()[0].timeZone], ['MONDAY', 21, 30, 'America/Santiago']);
  const run = lastRun(ss);
  assert.deepStrictEqual([run[1], run[2]], ['LetterWatchdog', 'REPAIRED']);
  assert.ok(/runAgent1A trigger was missing/.test(run[7]), run[7]);

  // With the trigger there, a check adds nothing.
  const n = env.state.triggers.length;
  scope.letterWatchdogCheck_(MON(23, 10));
  assert.strictEqual(weekly().length, 1);
  assert.strictEqual(env.state.triggers.length, n);

  // runAgent1ARetry is the real chain's entry point.
  addNightlyRaw(env, ss, []);
  scope.runAgent1ARetry();
  assert.ok(scope.loadTempData('A1A_DATA'), 'runAgent1ARetry runs Agent1A');
}

console.log('letter watchdog OK');
