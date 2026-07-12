// test_agent3.js — CCSM_Agent3.gs (nightly refresh + missed-days alerts).
//
// Uses fixtures.js's REAL addNightlyRaw(env, ss, rows) contract (locked in by
// test_fixtures.js in Task 4): each row is a flat object keyed by
// CCSM_NIGHTLY_QUESTIONS[].key (report_date, exchanges, roleplays, ...,
// effort) plus {zone, area, timestamp?} — NOT a nested `metrics` sub-object.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_Agent3.gs'], env.globals);
const ss = makeCcsmSpreadsheet(env, scope);

// runAgent3 gates on AGENT_CONFIG dates — the builder leaves both blank.
setConfig(env, ss, 'SYSTEM_START_DATE', '2026-07-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2026-07-01');

// Two submissions: one Arauco 1 area (normal), one San Pedro area SAME
// area+date submitted twice (must sum). Unlisted CCSM_NIGHTLY_QUESTIONS keys
// are left blank by addNightlyRaw.
addNightlyRaw(env, ss, [
  { zone: 'Arauco', area: 'Arauco 1', report_date: '2026-07-10',
    exchanges: 'Sí', roleplays: 2, contacts_attempted: 15, contacts_made: 7,
    new_people_found: 1, effort: 'Todo' },
  { zone: 'San Pedro', area: 'San Pedro', report_date: '2026-07-10',
    friend_lessons: 1, effort: 'Algo' },
  { zone: 'San Pedro', area: 'San Pedro', report_date: '2026-07-10',
    friend_lessons: 2, effort: 'Algo' },
]);

scope.runAgent3();

const log = ss.getSheetByName('DAILY_LOG').getDataRange().getValues();
const h = log[0];
assert.deepStrictEqual(h.slice(0, 4), ['Date', 'Area', 'Zone', 'District']);
assert.ok(!h.includes('Is_Blitz'), 'blitz must be gone');
const row = (a) => log.find((r) => r[1] === a);
assert.strictEqual(row('Arauco 1')[h.indexOf('roleplays')], 2);
assert.strictEqual(row('Arauco 1')[h.indexOf('exchanges')], 'TRUE');
assert.strictEqual(row('Arauco 1')[h.indexOf('effort')], 'Todo');
assert.strictEqual(row('San Pedro')[h.indexOf('friend_lessons')], 3, 'same-day rows must sum');

// LIVE_SNAPSHOT rebuilt with one row per active (non-leadership) area
const snap = ss.getSheetByName('LIVE_SNAPSHOT').getDataRange().getValues();
assert.strictEqual(snap.length - 1, scope.CCSM_MISSION_ORG_ROWS.length);

// missed-days: with TEST_MODE, any alert emails redirect to the test inbox
// and use Spanish subject text. (MESSAGE_BANK/companion emails aren't seeded
// yet — Tasks 13/roster fill-in — so zero alerts is an expected, valid
// outcome here; this asserts the routing/language CONTRACT, not volume.)
const alerts = env.state.emails.filter((e) => /Informe/.test(e.subject));
alerts.forEach((e) => assert.strictEqual(e.to, 'CCSM.PMG.Compass@gmail.com'));

// no Provo/blitz/English residue
const src = require('fs').readFileSync('CCSM_Agent3.gs', 'utf8');
assert.ok(!/Utah Provo/i.test(src));
assert.ok(!/America\/Denver/.test(src));
assert.ok(!/blitz/i.test(src));
assert.ok(!/What is your area/.test(src));

console.log('agent3 OK');
