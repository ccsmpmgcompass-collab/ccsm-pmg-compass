// test_agent1c_consistency_glossary.js — CCSM_Agent1C.gs consistency block
// + glossary (Stage 5, the last of the coaching-letter-detail port). Same
// Wednesday-gap pattern as tests/test_agent1a_derived.js's Stage 1 test, run
// through the full 1A -> 1B -> 1C chain this time so the rendered email body
// can be inspected directly.
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
const today = new Date();
today.setHours(0, 0, 0, 0);
const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
const monday = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - 6);
const weekDates = [];
for (let i = 0; i < 7; i++) weekDates.push(toDateStr(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)));

// Wednesday (index 2) missing -- proves the day-by-day grid shows the real
// gap, not a fabricated full week.
const nightlyRows = weekDates
  .map((d, i) => ({
    zone: 'Arauco', area: 'Arauco 1', report_date: d, exchanges: 'Sí', effort: 'Algo',
    ...(i === 0 ? { contacts_attempted: 14, contacts_made: 7 } : {}),
  }))
  .filter((_, i) => i !== 2);
addNightlyRaw(env, ss, nightlyRows);
scope.runAgent3();

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
messageBank.appendRow(['S-CR-001', 'SUNDAY_COACHING_STRENGTH', 'contact_rate', '', '¡Excelente!', 'Cuerpo.', '157', 'Contactar', 'D. y C. 4:4-5', 'Escritura', 'TRUE']);
messageBank.appendRow(['S-ES-001', 'SUNDAY_COACHING_STRENGTH', 'effort_score', '', '¡Gran esfuerzo!', 'Cuerpo.', '', '', '', '', 'TRUE']);
messageBank.appendRow(['G-CL-001', 'SUNDAY_COACHING_GROWTH', 'close_rate', '', 'Oportunidad', 'Cuerpo.', '205', 'Invitar', 'Moroni 10:4', 'Escritura', 'TRUE']);

scope.runAgent1A();
scope.runAgent1B();
scope.runAgent1C();

const testEmail = env.state.emails.find((e) => e.to === 'CCSM.PMG.Compass@gmail.com');
assert.ok(testEmail, 'expected an email captured to the TEST_MODE inbox');
const body = testEmail.htmlBody || '';

// ===========================================================================
// Consistency block: title, real gap (6/7, not a fabricated 7/7), streak.
// ===========================================================================
assert.ok(body.includes('Esfuerzo y Constancia'), 'expected the Spanish consistency block title');
assert.ok(body.includes('6/7 reportes nocturnos'), 'expected the real 6/7 gap (Wednesday missing), not a fabricated full week');
assert.ok(body.includes('racha de 4 días'), 'expected the streak counted backward from Sunday to stop at the Wednesday gap');
assert.ok(body.includes('Esfuerzo en el altar'), 'expected the effort-segment legend');
// Every reported night answered 'Algo' (ccsmEffortScore=1), so all 6 land in
// the "Algo" bucket, none in Todo/La mayor parte.
assert.ok(body.includes('Algo ×6'), 'expected the Algo segment count for the 6 "Algo" nights');
assert.ok(body.includes('Todo ×0'), 'expected zero in the Todo segment -- no night answered "Todo"');

console.log('consistency block OK');

// ===========================================================================
// Glossary: present once, Spanish title, rate-metric formulas, no Provo
// terms (NM/LSI/LA/RC/pew/gate/renew) at all.
// ===========================================================================
assert.ok(body.includes('Qué significan las abreviaturas'), 'expected the Spanish glossary title');
assert.ok(body.includes('Contactos Logrados ÷ Contactos Intentados'), 'expected the contact_rate formula in the glossary');
assert.ok(!/\bNM\b|\bLSI\b|\bLA\b|\bRC\b|\bpew\b|\bgate\b|\brenew\b/.test(body),
  'no Provo-only glossary abbreviations may appear -- CCSM has none of these metrics');

console.log('glossary OK');

console.log('agent1c consistency+glossary OK');
