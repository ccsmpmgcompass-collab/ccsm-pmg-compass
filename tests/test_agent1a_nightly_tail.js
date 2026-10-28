// test_agent1a_nightly_tail.js — Agent1A reads each heavy tab once, and only
// the recent part of NIGHTLY_FORM_RAW (AUDIT-2026-10-28-monday-letters.md F3,
// F4).
//
// (a) a1a_readNightlyTail_ keeps the header and the rows SUBMITTED on or after
//     the cutoff, including a report dated a week ahead of when it was sent.
// (b) A stamp that is not a date reads the whole tab, as before.
// (c) A run of Agent1A logs its duration and its phase timings, and leaves no
//     cache behind for the next run.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');

const GS = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
  'CCSM_Agent3.gs', 'CCSM_Agent5A.gs', 'CCSM_Agent1A.gs'];

function setup() {
  const env = makeGasEnv({});
  const scope = loadGs(GS, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TEST_MODE', 'FALSE');
  return { env, scope, ss };
}

const night = (stamp, date) => ({ timestamp: stamp, zone: 'Arauco', area: 'Arauco 1',
  report_date: date, contacts_attempted: 5 });

// ── (a) the tail ──────────────────────────────────────────────────────────────
{
  const { env, scope, ss } = setup();
  addNightlyRaw(env, ss, [
    night(new Date(2026, 0, 5, 21, 0), '2026-01-04'),     // January: outside
    night(new Date(2026, 7, 30, 21, 0), '2026-08-30'),    // the day before the cutoff: outside
    night(new Date(2026, 8, 20, 21, 0), '2026-09-27'),    // sent 09-20, dated a week ahead: inside
    night(new Date(2026, 9, 12, 21, 0), '2026-10-11'),
    night(new Date(2026, 9, 12, 21, 5), '2026-10-12'),
  ]);
  const all = ss.getSheetByName('NIGHTLY_FORM_RAW').getDataRange().getValues();
  const tail = scope.a1a_readNightlyTail_('2026-08-31');
  assert.strictEqual(tail.length, 4, 'header + the three rows sent on or after 08-31');
  assert.deepStrictEqual(tail[0], all[0], 'the header comes first');
  assert.deepStrictEqual(tail.slice(1), all.slice(3), 'the rows are the last three, whole');

  assert.strictEqual(scope.a1a_readNightlyTail_('2026-11-01').length, 1, 'nothing that recent: the header only');
  assert.strictEqual(scope.a1a_readNightlyTail_('2025-01-01').length, all.length, 'an old cutoff: every row');
}

// ── (b) a stamp that is not a date ───────────────────────────────────────────
{
  const { env, scope, ss } = setup();
  addNightlyRaw(env, ss, [
    night('not a date', '2026-01-04'),
    night(new Date(2026, 9, 12, 21, 0), '2026-10-11'),
  ]);
  const all = ss.getSheetByName('NIGHTLY_FORM_RAW').getDataRange().getValues();
  assert.strictEqual(scope.a1a_readNightlyTail_('2026-08-31').length, all.length, 'cannot tell: read it all');
}

// ── (c) a run logs its time and drops its cache ──────────────────────────────
{
  const { env, scope, ss } = setup();
  addNightlyRaw(env, ss, []);
  scope.runAgent1A();
  const log = ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
  const row = log[log.length - 1];
  assert.deepStrictEqual([row[1], row[2]], ['Agent1A', 'SUCCESS'], row[7]);
  assert.strictEqual(typeof row[3], 'number', 'Duration_Sec is a number');
  assert.ok(/Timings: config \d+s, WEEKLY_KI rebuild \d+s, PDF request \d+s, nightly forms read \(\d+ rows\) \d+s, nightly history \d+s, weekly KI \d+s, build \d+s, save \d+s/.test(row[7]), row[7]);
  assert.strictEqual(scope.A1A_RUN_CACHE_, null, 'no cache survives the run');
}

console.log('agent1a nightly tail OK');
