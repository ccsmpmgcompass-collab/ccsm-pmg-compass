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
assert.ok(body.includes('Su Propio Progreso'), 'expected the You-vs-You title in the formal usted register');
assert.ok(body.includes('Esta Semana'), 'expected the "Esta Semana" row');
assert.ok(body.includes('Semana Pasada'), 'expected the "Semana Pasada" row');
assert.ok(body.includes('Prom. del Cambio'), 'expected the "Prom. del Cambio" row ("transfer" is an anglicism)');
assert.ok(body.includes('Su Mejor Marca'), 'expected the "Su Mejor Marca" row');
assert.ok(!/This Week|Last Week|Transfer Avg|Your Best/.test(body), 'no English You-vs-You labels may leak');

// ===========================================================================
// Regression coverage for a real shipped bug (found in code review,
// 2026-08-01): a1a_loadMultiWeekHistory never derived rate metrics per
// week, so You-vs-You's "Semana Pasada"/"Prom. del Cambio"/"Su Mejor Marca" rows
// for a rate-metric growth pick (close_rate here) silently repeated THIS
// week's own value instead of real history. Known close_rate per week from
// the friend_lessons/baptismal_invitations numbers seeded above: twoAgo
// 0/7=0%, lastWeek 1/14=7% (rounds from 7.14), current 1/20=5%. Both the
// real last-week value (7%) and the current value (5%) must appear,
// proving the panel shows genuinely different historical numbers, not the
// current week repeated on every row.
// ===========================================================================
assert.ok(body.includes('5%'), 'expected the current week\'s real close_rate (5%) on the "Esta Semana" row');
assert.ok(body.includes('7%'), 'expected last week\'s REAL close_rate (7%, from 1/14) on "Semana Pasada"/"Su Mejor Marca" -- not a repeat of this week\'s 5%');

console.log('You-vs-You OK (including real-history regression check)');

// ===========================================================================
// Funnel: title, Spanish stage labels, current week's real numbers, no LSI
// tile/note at all (CCSM has no LSI metric).
//
// The funnel is STACKED, not a horizontal strip (2026-08-24) -- the old strip
// was one table row of 5 tiles + 4 fixed-34px arrows and had a 412px
// min-content width, the widest block in the letter and the only reason the
// email forced a horizontal scroll on a phone.
// ===========================================================================
assert.ok(body.includes('Su Embudo Esta Semana'), 'expected the Spanish funnel title (formal "Su", not "Tu")');
assert.ok(!body.includes('Tu Embudo'), 'the informal "Tu Embudo" title must be gone');

// Stage labels must be CcsmData.gs displayEs verbatim -- the same words the
// companionship reads on the nightly form. The old strip used clipped
// fragments and one term ('Nuevas Amistades') the form never uses.
['Intentos de Contacto', 'Conversaciones Significativas',
 'Lecciones con Amigos', 'Nuevas Personas Encontradas'].forEach(function(label) {
  assert.ok(body.includes(label), 'expected the funnel stage label "' + label + '" (CcsmData displayEs)');
});
// Scoped to the funnel block itself: the leadership KPI tile strip further
// down the letter legitimately abbreviates in its 4-across tiles, so this
// check must not reach into it.
const funnelBlock = body.slice(body.indexOf('Su Embudo Esta Semana'),
                               body.indexOf('Esfuerzo y Constancia'));
assert.ok(funnelBlock.length > 200, 'failed to slice out the funnel block');
['Intentados', 'Significativas', 'Nuevas Amistades'].forEach(function(frag) {
  assert.ok(!funnelBlock.includes('>' + frag + '<'),
    'the old clipped funnel tile "' + frag + '" must be gone');
});

// Current week: attempted=30, contacted=15 -> contactedPct = 50%.
assert.ok(/50% de los intentos/.test(body),
  'expected the stage caption "50% de los intentos" (contacted/attempted)');

// The old fixed-width arrow cell is what made the block unshrinkable.
assert.ok(!/width:34px/.test(body), 'the fixed-34px arrow cells must be gone');

assert.ok(!/LSI|NM Doors|New Friends(?!\p{L})/u.test(body), 'no Provo LSI/door funnel strings may appear');

console.log('funnel OK');

console.log('agent1c you-vs-you + funnel OK');
