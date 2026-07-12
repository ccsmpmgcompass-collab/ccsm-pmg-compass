// test_agent5a.js — CCSM_Agent5A.gs (dashboard summary + WEEKLY_KI from the
// self-reported weekly form's Real/Meta columns).
//
// Follows the Task 5 (test_agent3.js) pattern: build the in-memory
// COMPASS_CCSM spreadsheet, seed raw form rows via fixtures.js's REAL
// addWeeklyRaw/addNightlyRaw contracts, run the agent(s), then assert
// against the written tabs.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, addWeeklyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_Agent3.gs', 'CCSM_Agent5A.gs'],
  env.globals
);
const ss = makeCcsmSpreadsheet(env, scope);

// Agent3 (used here only to seed DAILY_LOG for the DASHBOARD_SUMMARY half of
// this test) gates on these AGENT_CONFIG dates — the builder leaves both blank.
setConfig(env, ss, 'SYSTEM_START_DATE', '2026-07-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2026-07-01');

// ---------------------------------------------------------------------------
// Seed NIGHTLY_FORM_RAW + run Agent3 so DAILY_LOG / LIVE_SNAPSHOT exist —
// makes the DASHBOARD_SUMMARY assertion below real instead of vacuous.
// ---------------------------------------------------------------------------
addNightlyRaw(env, ss, [
  { zone: 'Arauco', area: 'Arauco 1', report_date: '2026-07-10',
    exchanges: 'Sí', roleplays: 2, contacts_attempted: 15, contacts_made: 7,
    new_people_found: 1, effort: 'Todo' },
]);
scope.runAgent3();

// ---------------------------------------------------------------------------
// Seed WEEKLY_FORM_RAW: two submissions for 'Arauco 1' in the SAME week
// (Mon 2026-07-06 - Sun 2026-07-12) — the second (later form timestamp) must
// win — plus one submission for 'Lota 1' in a different zone.
// ---------------------------------------------------------------------------
addWeeklyRaw(env, ss, [
  // Arauco 1 — first (earlier) submission: must be OVERWRITTEN, not summed.
  { zone: 'Arauco', area: 'Arauco 1',
    timestamp: new Date('2026-07-08T08:00:00'),
    report_date: '2026-07-07', leader_call: 'No', correlation_meeting: 'No',
    ki_new_people_real: 3, ki_new_people_meta: 5,
    ki_member_lessons_real: 1, ki_member_lessons_meta: 2 },
  // Arauco 1 — second (later) submission for the SAME week — must win.
  { zone: 'Arauco', area: 'Arauco 1',
    timestamp: new Date('2026-07-10T20:00:00'),
    report_date: '2026-07-09', leader_call: 'Sí', correlation_meeting: 'Sí',
    ki_new_people_real: 8, ki_new_people_meta: 10,
    ki_member_lessons_real: 4, ki_member_lessons_meta: 6 },
  // Lota 1 — different zone, single submission, same week.
  { zone: 'Camilo', area: 'Lota 1',
    timestamp: new Date('2026-07-09T10:00:00'),
    report_date: '2026-07-08', leader_call: 'Sí', correlation_meeting: 'No',
    ki_new_people_real: 2, ki_new_people_meta: 4 },
]);

scope.runAgent5A();

// ---------------------------------------------------------------------------
// WEEKLY_KI assertions
// ---------------------------------------------------------------------------
const ki = ss.getSheetByName('WEEKLY_KI').getDataRange().getValues();
const kh = ki[0];
assert.deepStrictEqual(kh.slice(0, 4), ['Week_End_Date', 'Area', 'Zone', 'District']);
assert.ok(kh.includes('ki_new_people_real'), 'header must include ki_new_people_real');
assert.ok(kh.includes('ki_new_people_meta'), 'header must include ki_new_people_meta');
assert.ok(kh.includes('leader_call'));
assert.ok(kh.includes('correlation_meeting'));
assert.strictEqual(ki.length - 1, 2, 'expected 2 WEEKLY_KI data rows (Arauco 1 deduped + Lota 1)');

const kiRow = (a) => ki.find((r) => r[1] === a);
const realIdx    = kh.indexOf('ki_new_people_real');
const metaIdx    = kh.indexOf('ki_new_people_meta');
const leaderIdx  = kh.indexOf('leader_call');
const corrIdx    = kh.indexOf('correlation_meeting');

const arauco1 = kiRow('Arauco 1');
assert.ok(arauco1, 'expected an Arauco 1 row in WEEKLY_KI');
assert.strictEqual(arauco1[realIdx], 8, 'later submission Real value must win (not summed with the first)');
assert.strictEqual(arauco1[metaIdx], 10, 'later submission Meta value must win (not summed with the first)');
assert.strictEqual(arauco1[leaderIdx], 'TRUE', 'Sí must convert to TRUE');
assert.strictEqual(arauco1[corrIdx], 'TRUE');

const lota1 = kiRow('Lota 1');
assert.ok(lota1, 'expected a Lota 1 row in WEEKLY_KI');
assert.strictEqual(lota1[realIdx], 2);
assert.strictEqual(lota1[metaIdx], 4);
assert.strictEqual(lota1[leaderIdx], 'TRUE');
assert.strictEqual(lota1[corrIdx], 'FALSE', 'No must convert to FALSE');

// ---------------------------------------------------------------------------
// DASHBOARD_SUMMARY assertions
// ---------------------------------------------------------------------------
const dash = ss.getSheetByName('DASHBOARD_SUMMARY').getDataRange().getValues();
assert.ok(dash.length > 1, 'DASHBOARD_SUMMARY should have data rows');
const dh = dash[0];
const recordTypeIdx = dh.indexOf('record_type');
assert.ok(recordTypeIdx >= 0, 'DASHBOARD_SUMMARY header must include record_type');
assert.ok(dash.some((r) => r[recordTypeIdx] === 'MISSION'), 'expected at least one MISSION-total row');

// ---------------------------------------------------------------------------
// No Provo/English residue
// ---------------------------------------------------------------------------
const src = require('fs').readFileSync('CCSM_Agent5A.gs', 'utf8');
assert.ok(!/Utah Provo/i.test(src));
assert.ok(!/America\/Denver/.test(src));

console.log('agent5a OK');
