// test_agent1c_youvsyou_funnel.js — CCSM_Agent1C.gs You-vs-You + funnel
// strip (Stage 4 of the coaching-letter-detail port). Same 3-week seed
// shape as test_agent1c_trend_goalgrid.js, extended with new_people_found
// so the funnel strip's last tile has a real, non-zero value too.
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

// Same ranking shape as test_agent1c_trend_goalgrid.js: close_rate stays the
// lowest-ranked (growth) metric on the current week.
function seedWeek(sunday, attempted, made, meaningful, lessons, baptisms, newFound) {
  const dates = weekDatesEnding(sunday);
  const rows = dates.map((d, i) => ({
    zone: 'Arauco', area: 'Arauco 1', report_date: d, exchanges: 'Sí', effort: 'Algo',
    ...(i === 0 ? {
      contacts_attempted: attempted, contacts_made: made,
      meaningful_conversations: meaningful, friend_lessons: lessons,
      baptismal_invitations: baptisms, new_people_found: newFound,
    } : {}),
  }));
  addNightlyRaw(env, ss, rows);
  scope.runAgent3();
}
seedWeek(twoAgoSunday, 10, 2, 1, 7, 0, 1);
seedWeek(lastSunday, 20, 10, 5, 14, 1, 3);
seedWeek(thisSunday, 30, 15, 10, 20, 1, 4);

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

const messageBank = ss.getSheetByName('MESSAGE_BANK');
messageBank.appendRow(['S-LR-001', 'SUNDAY_COACHING_STRENGTH', 'lesson_rate', '', '¡Excelente!', 'Cuerpo.', '174', 'Enseñar', 'Alma 26:22', 'Escritura', 'TRUE']);
messageBank.appendRow(['S-MC-001', 'SUNDAY_COACHING_STRENGTH', 'mc_rate', '', '¡Buenas conversaciones!', 'Cuerpo.', '85', 'Conversar', 'D. y C. 11:21', 'Escritura', 'TRUE']);
messageBank.appendRow(['G-CL-001', 'SUNDAY_COACHING_GROWTH', 'close_rate', '', 'Oportunidad', 'Cuerpo.', '205', 'Invitar', 'Moroni 10:4', 'Escritura', 'TRUE']);

scope.runAgent1A();
scope.runAgent1B();
scope.runAgent1C();

const testEmail = env.state.emails.find((e) => e.to === 'CCSM.PMG.Compass@gmail.com');
assert.ok(testEmail, 'expected an email captured to the TEST_MODE inbox');
const body = testEmail.htmlBody || '';

// ===========================================================================
// You-vs-You: title + the 4 Spanish row labels for the growth metric.
// ===========================================================================
assert.ok(body.includes('Tú contra Ti'), 'expected the You-vs-You title');
assert.ok(body.includes('Esta Semana'), 'expected the "Esta Semana" row');
assert.ok(body.includes('Semana Pasada'), 'expected the "Semana Pasada" row');
assert.ok(body.includes('Prom. Transfer'), 'expected the "Prom. Transfer" row');
assert.ok(body.includes('Tu Mejor'), 'expected the "Tu Mejor" row');
assert.ok(!/This Week|Last Week|Transfer Avg|Your Best/.test(body), 'no English You-vs-You labels may leak');

// ===========================================================================
// Regression coverage for a real shipped bug (found in code review,
// 2026-08-01): a1a_loadMultiWeekHistory never derived rate metrics per
// week, so You-vs-You's "Semana Pasada"/"Prom. Transfer"/"Tu Mejor" rows
// for a rate-metric growth pick (close_rate here) silently repeated THIS
// week's own value instead of real history. Known close_rate per week from
// the friend_lessons/baptismal_invitations numbers seeded above: twoAgo
// 0/7=0%, lastWeek 1/14=7% (rounds from 7.14), current 1/20=5%. Both the
// real last-week value (7%) and the current value (5%) must appear,
// proving the panel shows genuinely different historical numbers, not the
// current week repeated on every row.
// ===========================================================================
assert.ok(body.includes('5%'), 'expected the current week\'s real close_rate (5%) on the "Esta Semana" row');
assert.ok(body.includes('7%'), 'expected last week\'s REAL close_rate (7%, from 1/14) on "Semana Pasada"/"Tu Mejor" -- not a repeat of this week\'s 5%');

console.log('You-vs-You OK (including real-history regression check)');

// ===========================================================================
// Funnel strip: title, Spanish tile labels, current week's real numbers,
// no LSI tile/note at all (CCSM has no LSI metric).
// ===========================================================================
assert.ok(body.includes('Tu Embudo Esta Semana'), 'expected the Spanish funnel strip title');
assert.ok(body.includes('Intentados'), 'expected the "Intentados" funnel tile');
assert.ok(body.includes('Nuevas Amistades'), 'expected the "Nuevas Amistades" funnel tile');
// Current week: attempted=30, contacted=15 -> contactedPct = 50%.
assert.ok(/50%/.test(body), 'expected the funnel arrow to show 50% (contacted/attempted)');
assert.ok(!/LSI|NM Doors|New Friends(?!\p{L})/u.test(body), 'no Provo LSI/door funnel strings may appear');

console.log('funnel strip OK');

console.log('agent1c you-vs-you + funnel OK');
