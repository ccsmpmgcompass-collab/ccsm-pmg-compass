// test_agent1ab.js — CCSM_Agent1A.gs (Sunday coaching metrics) +
// CCSM_Agent1B.gs (strength/growth message selection).
//
// Follows the Task 5/6 pattern: build the in-memory COMPASS_CCSM
// spreadsheet, seed a real week of DAILY_LOG via Agent3 on fixture nightly
// raw rows, run the 1A->1B chain, then assert against Script Properties
// (via the real saveTempData/loadTempData contract in CCSM_Helpers.gs).
//
// Agent1A computes its "current week" from the REAL wall-clock date (see
// CCSM_Agent1A.gs runAgent1A — most recent Sunday in getMissionTimezone()),
// exactly like CCSM_Agent5A's a5a_getCurrentWeekStart() (test_agent5a.js
// relies on the same real-clock behavior). This suite must therefore seed
// DAILY_LOG for THIS WEEK (Monday..Sunday, computed from today), not a
// fixed calendar week.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs'],
  env.globals
);
const ss = makeCcsmSpreadsheet(env, scope);

// runAgent3 gates on AGENT_CONFIG dates — the builder leaves both blank.
// Set them safely in the past so this week's data is never excluded.
setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');

// ---------------------------------------------------------------------------
// Compute THIS week's Monday..Sunday (local calendar), matching
// CCSM_Agent1A.gs's own week calculation (most recent Sunday, back up 6 days
// for Monday) so the seeded DAILY_LOG rows land inside runAgent1A()'s window
// regardless of which day the suite happens to run on.
// ---------------------------------------------------------------------------
function toDateStr(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
const today = new Date();
today.setHours(0, 0, 0, 0);
const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
const monday = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - 6);
const weekDates = [];
for (let i = 0; i < 7; i++) {
  weekDates.push(toDateStr(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)));
}
const weekStartStr = weekDates[0];
const weekEndStr = weekDates[6];

// ---------------------------------------------------------------------------
// Seed a full week of nightly submissions for 'Arauco 1' (zone 'Arauco').
// contacts_attempted/contacts_made are concentrated on Monday so the summed
// week ratio is unambiguous: 7/14 = 0.5 (matches CONTACT_RATE_TARGET
// default of 0.50 exactly -> pct 1.0, the clear #1 strength).
// Every day's effort is 'Algo' (ccsmEffortScore=1) -> effort_score = 1.0,
// pct = 1.0/2.75 (EFFORT_SCORE_TARGET default) ~= 0.364 -> clear #2 strength.
// meaningful_conversations/friend_lessons/baptismal_invitations stay 0 all
// week -> mc_rate/lesson_rate/close_rate all compute to 0 (den-guarded to 0
// where applicable) -> tied last; close_rate is the last metric in
// A1A_RATE_METRICS push order among that 0-pct group, so it lands as growth.
// ---------------------------------------------------------------------------
const nightlyRows = weekDates.map((d, i) => ({
  zone: 'Arauco',
  area: 'Arauco 1',
  report_date: d,
  exchanges: 'Sí',
  effort: 'Algo',
  ...(i === 0 ? { contacts_attempted: 14, contacts_made: 7 } : {}),
}));
addNightlyRaw(env, ss, nightlyRows);
scope.runAgent3();

// Sanity: DAILY_LOG really has all 7 days for Arauco 1 inside the window
// Agent1A will scan.
const dailyLog = ss.getSheetByName('DAILY_LOG').getDataRange().getValues();
const dlHeaders = dailyLog[0];
const dateIdx = dlHeaders.indexOf('Date');
const areaIdx = dlHeaders.indexOf('Area');
const arauco1Rows = dailyLog.filter((r, i) => i > 0 && r[areaIdx] === 'Arauco 1');
assert.strictEqual(arauco1Rows.length, 7, 'expected 7 DAILY_LOG rows for Arauco 1 this week');
arauco1Rows.forEach((r) => {
  assert.ok(r[dateIdx] >= weekStartStr && r[dateIdx] <= weekEndStr, 'row date must be inside this week');
});

// ---------------------------------------------------------------------------
// Seed MESSAGE_BANK — 3 minimal Spanish rows (Task 13 authors the real
// content), one per message slot the chain will select for Arauco 1:
// strength1=contact_rate, strength2=effort_score, growth=close_rate.
// ---------------------------------------------------------------------------
const messageBank = ss.getSheetByName('MESSAGE_BANK');
messageBank.appendRow([
  'S-CR-001', 'SUNDAY_COACHING_STRENGTH', 'contact_rate', '',
  '¡Excelente tasa de contacto!', 'Su compañía está contactando muy bien a los amigos esta semana.',
  '157', 'Contactar con amor', 'D. y C. 4:4-5', 'Escritura sobre el servicio', 'TRUE',
]);
messageBank.appendRow([
  'S-ES-001', 'SUNDAY_COACHING_STRENGTH', 'effort_score', '',
  '¡Gran esfuerzo esta semana!', 'Su compañía ha dado un buen esfuerzo constante.',
  '', '', '', '', 'TRUE',
]);
messageBank.appendRow([
  'G-CL-001', 'SUNDAY_COACHING_GROWTH', 'close_rate', '',
  'Oportunidad: invitaciones al bautismo', 'Consideren invitar más a menudo a la fecha bautismal.',
  '205', 'Invitar a comprometerse', 'Moroni 10:4', 'Escritura sobre la fe', 'TRUE',
]);

// ---------------------------------------------------------------------------
// Run the chain.
// ---------------------------------------------------------------------------
scope.runAgent1A();

// Agent1B releases A1A_DATA before writing A1B_DATA, so anything asserted
// about A1A_DATA's own contents must be read HERE, between the two runs.
const a1aDataMidChain = scope.loadTempData('A1A_DATA');
const a1aBytesMidChain = Object.entries(env.state.props.script || {})
  .filter(([k]) => /^A1A_DATA/.test(k))
  .reduce((n, [k, v]) => n + k.length + String(v).length, 0);

scope.runAgent1B();

// ---------------------------------------------------------------------------
// Script Properties assertions (via the real saveTempData/loadTempData
// contract, loaded straight from CCSM_Helpers.gs into `scope`).
// ---------------------------------------------------------------------------
// saveTempData() chunks large payloads across numbered properties (see
// CCSM_Helpers.gs TEMP_DATA_CHUNK_CHARS) — 68+ areas of stats routinely
// exceed the single-property cap, so check for either the direct key or its
// chunk-count marker rather than assuming an unchunked value.
function savedToProps(key) {
  const bucket = env.state.props.script || {};
  return Boolean(bucket[key] || bucket[key + '__chunks']);
}
assert.ok(a1aBytesMidChain > 0, 'A1A_DATA must be saved to Script Properties by Agent1A');
assert.ok(savedToProps('A1B_DATA'), 'A1B_DATA must be saved to Script Properties');

assert.strictEqual(a1aDataMidChain.weekStart, weekStartStr);
assert.strictEqual(a1aDataMidChain.weekEnd, weekEndStr);

// QUOTA REGRESSION GUARD. Script Properties is capped at 500KB script-wide.
// Against real 43-area data A1A_DATA is ~364KB and A1B_DATA ~426KB, so leaving
// both resident blew the cap and Agent1B died with "You have exceeded the
// property storage quota" — which is what killed the entire coaching chain on
// 2026-08-03 and why Agent1C had never run once in production. Agent1B must
// release A1A_DATA BEFORE writing A1B_DATA so only one payload is ever live.
const a1aBytesAfter = Object.entries(env.state.props.script || {})
  .filter(([k]) => /^A1A_DATA/.test(k))
  .reduce((n, [k, v]) => n + k.length + String(v).length, 0);
assert.ok(
  a1aBytesAfter < a1aBytesMidChain,
  `Agent1B must release A1A_DATA before saving A1B_DATA (was ${a1aBytesMidChain}B, still ${a1aBytesAfter}B)`
);

const a1bData = scope.loadTempData('A1B_DATA');
const arauco1 = a1bData.areas['Arauco 1'];
assert.ok(arauco1, 'expected an Arauco 1 entry in A1B_DATA');

// Known ratio: contacts_made(7) / contacts_attempted(14) = 0.5
assert.strictEqual(arauco1.stats.contact_rate, 0.5, 'contact_rate must be contacts_made/contacts_attempted');
assert.strictEqual(arauco1.stats.mc_rate, 0);
assert.strictEqual(arauco1.stats.lesson_rate, 0);
assert.strictEqual(arauco1.stats.close_rate, 0);
assert.ok(Math.abs(arauco1.stats.effort_score - 1) < 1e-9, 'effort_score must average ccsmEffortScore across the week');

// Ranking: contact_rate is the clear #1 strength (pct 1.0), close_rate ends
// up as growth (tied-0 group, last push order among A1A_RATE_METRICS).
assert.strictEqual(arauco1.strength1.key, 'contact_rate');
assert.strictEqual(arauco1.growth.key, 'close_rate');

// ---------------------------------------------------------------------------
// Message selection: strength + growth Message_IDs must come from the
// seeded MESSAGE_BANK — never generated text.
// ---------------------------------------------------------------------------
const bankIds = messageBank.getDataRange().getValues().slice(1).map((r) => r[0]);

assert.ok(arauco1.msg_strength1, 'expected a strength1 message to be selected');
assert.ok(bankIds.includes(arauco1.msg_strength1.messageId), 'msg_strength1 Message_ID must exist in MESSAGE_BANK');
assert.strictEqual(arauco1.msg_strength1.messageId, 'S-CR-001');

assert.ok(arauco1.msg_growth, 'expected a growth message to be selected');
assert.ok(bankIds.includes(arauco1.msg_growth.messageId), 'msg_growth Message_ID must exist in MESSAGE_BANK');
assert.strictEqual(arauco1.msg_growth.messageId, 'G-CL-001');

// No message TEXT was generated — the full row attached is exactly the
// seeded row's own subject/body, not synthesized.
assert.strictEqual(arauco1.msg_strength1.subjectLine, '¡Excelente tasa de contacto!');
assert.strictEqual(arauco1.msg_growth.subjectLine, 'Oportunidad: invitaciones al bautismo');

// Agent1C scheduled
assert.ok(env.state.triggers.some((t) => t.handlerFunctionName === 'runAgent1C'), 'expected Agent1C to be scheduled');

// ---------------------------------------------------------------------------
// No Provo/English/doors residue
// ---------------------------------------------------------------------------
const srcA = require('fs').readFileSync('CCSM_Agent1A.gs', 'utf8');
const srcB = require('fs').readFileSync('CCSM_Agent1B.gs', 'utf8');
[srcA, srcB].forEach((src) => {
  assert.ok(!/Utah Provo/i.test(src));
  assert.ok(!/America\/Denver/.test(src));
  assert.ok(!/nm_knocked/.test(src));
});

console.log('agent1ab OK');
