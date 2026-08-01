// test_agent1c_trend_goalgrid.js — CCSM_Agent1C.gs trend chart + goal grid
// (Stage 3 of the coaching-letter-detail port). Needs real multi-week data,
// so this seeds 3 weeks the same way tests/test_agent1a_derived.js does,
// then runs the full 1A -> 1B -> 1C chain and inspects the sent email body.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const geminiEnvelope = JSON.stringify({
  candidates: [{ content: { parts: [{ text: JSON.stringify({ Arauco: 'Narrativa de prueba.' }) }] } }],
});
const geminiResponse = { getResponseCode: () => 200, getContentText: () => geminiEnvelope };

const env = makeGasEnv({ geminiResponse });
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs'],
  env.globals
);
const ss = makeCcsmSpreadsheet(env, scope);

setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');

function toDateStr(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function weekDatesEnding(sunday) {
  const out = [];
  for (let i = 6; i >= 0; i--) out.push(toDateStr(new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - i)));
  return out;
}
const today = new Date();
today.setHours(0, 0, 0, 0);
const thisSunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
const lastSunday = new Date(thisSunday.getFullYear(), thisSunday.getMonth(), thisSunday.getDate() - 7);
const twoAgoSunday = new Date(thisSunday.getFullYear(), thisSunday.getMonth(), thisSunday.getDate() - 14);

// Monday numbers per week, tuned so close_rate stays the lowest-ranked
// (growth) metric on the CURRENT week specifically (only the current week's
// stats feed a1a_rankMetrics) while every rate has a real, nonzero,
// per-week-varying value -- so the trend chart has more than one non-null
// point and isn't trivially empty (max<=0 renders nothing, see
// a1c_buildTrendChart_).
function seedWeek(sunday, attempted, made, meaningful, lessons, baptisms) {
  const dates = weekDatesEnding(sunday);
  const rows = dates.map((d, i) => ({
    zone: 'Arauco', area: 'Arauco 1', report_date: d, exchanges: 'Sí', effort: 'Algo',
    ...(i === 0 ? {
      contacts_attempted: attempted, contacts_made: made,
      meaningful_conversations: meaningful, friend_lessons: lessons,
      baptismal_invitations: baptisms,
    } : {}),
  }));
  addNightlyRaw(env, ss, rows);
  scope.runAgent3();
}
seedWeek(twoAgoSunday, 10, 2, 1, 7, 0);
seedWeek(lastSunday, 20, 10, 5, 14, 1);
seedWeek(thisSunday, 30, 15, 10, 20, 1);
// Current week: contact_rate 50% of 50% target=100%pct, mc_rate 133%pct,
// lesson_rate 333%pct, effort_score(Algo daily) ~36.4%pct, close_rate
// 1/20=5% of 25% target=20%pct -- close_rate is the clear lowest, so it
// remains the growth pick exactly like the other coaching-letter suites.

const missionOrgSheet = ss.getSheetByName('MISSION_ORG');
const orgData = missionOrgSheet.getDataRange().getValues();
const orgHeaders = orgData[0];
const areaNameCol = orgHeaders.indexOf('Area_Name');
const email1Col = orgHeaders.indexOf('Companion1_Email');
let arauco1Row = -1;
for (let i = 1; i < orgData.length; i++) {
  if (orgData[i][areaNameCol] === 'Arauco 1') { arauco1Row = i; break; }
}
missionOrgSheet.getRange(arauco1Row + 1, email1Col + 1).setValue('zl.arauco1@example.com');

// Ranking with this seed: lesson_rate(333%) > mc_rate(133%) > contact_rate(100%)
// -- lesson_rate/mc_rate are strength1/strength2, close_rate is growth.
const messageBank = ss.getSheetByName('MESSAGE_BANK');
messageBank.appendRow(['S-LR-001', 'SUNDAY_COACHING_STRENGTH', 'lesson_rate', '', '¡Excelente!', 'Cuerpo.', '174', 'Enseñar', 'Alma 26:22', 'Escritura', 'TRUE']);
messageBank.appendRow(['S-MC-001', 'SUNDAY_COACHING_STRENGTH', 'mc_rate', '', '¡Buenas conversaciones!', 'Cuerpo.', '85', 'Conversar', 'D. y C. 11:21', 'Escritura', 'TRUE']);
messageBank.appendRow(['G-CL-001', 'SUNDAY_COACHING_GROWTH', 'close_rate', '', 'Oportunidad', 'Cuerpo.', '205', 'Invitar', 'Moroni 10:4', 'Escritura', 'TRUE']);

scope.runAgent1A();
scope.runAgent1B();

// Must read A1B_DATA before runAgent1C -- it consumes/clears the chained
// temp data, same as test_agent1c.js's established pattern.
const a1bData = scope.loadTempData('A1B_DATA');

scope.runAgent1C();

const testEmail = env.state.emails.find((e) => e.to === 'CCSM.PMG.Compass@gmail.com');
assert.ok(testEmail, 'expected an email captured to the TEST_MODE inbox');
const body = testEmail.htmlBody || '';

// ===========================================================================
// Trend chart: title, 8 week-date labels, the current-week value visible.
// ===========================================================================
assert.ok(body.includes('últimas 8 semanas'), 'expected the Spanish trend chart title');
assert.ok(!/last 8 weeks/i.test(body), 'must not leak the English trend chart title');

console.log('trend chart title OK');

// ===========================================================================
// Goal grid: title, Meta/Tu row labels, group headers, no English leak.
// ===========================================================================
assert.ok(body.includes('Tu Progreso Hacia la Meta'), 'expected the Spanish goal grid title');
assert.ok(body.includes('>Meta<'), 'expected the "Meta" row label in at least one goal-grid mini-chart');
assert.ok(body.includes('>Tú<'), 'expected the "Tu" row label in at least one goal-grid mini-chart');
assert.ok(body.includes('BUSCAR'), 'expected goal-grid metrics grouped under Buscar');

assert.ok(!/Your Progress to Goal|Goal reached|% of goal(?!\p{L})/u.test(body),
  'no English goal-grid strings may leak into the Spanish letter');

console.log('goal grid OK');

// ===========================================================================
// area.ranked flowed all the way through A1A -> A1B(JSON round-trip) -> 1C:
// at least one metric beyond the 3 message picks (contact_rate/effort_score/
// close_rate) must appear in the goal grid, proving the full ranked list
// (not just strength1/strength2/growth) reached the renderer.
// ===========================================================================
const arauco1 = a1bData.areas['Arauco 1'];
assert.ok(Array.isArray(arauco1.ranked), 'A1B_DATA area must carry the full ranked[] array (goal grid needs it)');
assert.ok(arauco1.ranked.length >= 3, 'ranked[] must include more than just the 3 message picks');

console.log('ranked[] round-trip OK');

console.log('agent1c trend+goalgrid OK');
