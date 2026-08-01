// test_agent1c_numbers.js — CCSM_Agent1C.gs personal-section numbers
// (Stage 2 of the coaching-letter-detail port: goal bar, stat line, days-
// reported chip, full scoreboard). Reverses the file's old "intentionally
// NUMBER-FREE" personal section, same as Provo's own coaching letter did —
// see [[project-coaching-letter-accuracy-stats]] and the "PERSONAL-SECTION
// NUMBERS" note in CCSM_Agent1C.gs.
//
// Same seed as test_agent1c.js (contacts_attempted=14/contacts_made=7 on
// Monday, effort='Algo' every day) so the known ranking holds:
// strength1=contact_rate (50%), strength2=effort_score, growth=close_rate.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const geminiNarrativeJson = JSON.stringify({
  Arauco: 'Narrativa de prueba para la zona Arauco.',
});
const geminiEnvelope = JSON.stringify({
  candidates: [{ content: { parts: [{ text: geminiNarrativeJson }] } }],
});
const geminiResponse = {
  getResponseCode: () => 200,
  getContentText: () => geminiEnvelope,
};

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
for (let i = 0; i < 7; i++) {
  weekDates.push(toDateStr(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)));
}

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

const missionOrgSheet = ss.getSheetByName('MISSION_ORG');
const orgData = missionOrgSheet.getDataRange().getValues();
const orgHeaders = orgData[0];
const areaNameCol = orgHeaders.indexOf('Area_Name');
const email1Col = orgHeaders.indexOf('Companion1_Email');
let arauco1Row = -1;
for (let i = 1; i < orgData.length; i++) {
  if (orgData[i][areaNameCol] === 'Arauco 1') { arauco1Row = i; break; }
}
assert.ok(arauco1Row >= 0, 'expected an Arauco 1 row in MISSION_ORG');
missionOrgSheet.getRange(arauco1Row + 1, email1Col + 1).setValue('zl.arauco1@example.com');

const messageBank = ss.getSheetByName('MESSAGE_BANK');
messageBank.appendRow([
  'S-CR-001', 'SUNDAY_COACHING_STRENGTH', 'contact_rate', '',
  '¡Excelente tasa de contacto!', 'Cuerpo.', '157', 'Contactar', 'D. y C. 4:4-5', 'Escritura', 'TRUE',
]);
messageBank.appendRow([
  'S-ES-001', 'SUNDAY_COACHING_STRENGTH', 'effort_score', '',
  '¡Gran esfuerzo!', 'Cuerpo.', '', '', '', '', 'TRUE',
]);
messageBank.appendRow([
  'G-CL-001', 'SUNDAY_COACHING_GROWTH', 'close_rate', '',
  'Oportunidad', 'Cuerpo.', '205', 'Invitar', 'Moroni 10:4', 'Escritura', 'TRUE',
]);

scope.runAgent1A();
scope.runAgent1B();
scope.runAgent1C();

const emails = env.state.emails;
const testEmail = emails.find((e) => e.to === 'CCSM.PMG.Compass@gmail.com');
assert.ok(testEmail, 'expected an email captured to the TEST_MODE inbox');
const body = testEmail.htmlBody || '';

console.log('email captured OK');

// ===========================================================================
// Days-reported chip (a1c_buildAreaHeader_) — full week, no gaps.
// ===========================================================================
assert.ok(body.includes('7/7 días reportados'), 'expected the days-reported chip for a full week');

console.log('area header OK');

// ===========================================================================
// Stat line + goal bar under the strength1 message (contact_rate = 50%).
// ===========================================================================
assert.ok(/<strong>50%<\/strong>\s*\(meta/.test(body), 'expected the strength1 stat line showing 50% actual against its goal');
assert.ok(body.includes('de la meta') || body.includes('Meta alcanzada'), 'expected a goal-bar caption on at least one metric');

console.log('stat line + goal bar OK');

// ===========================================================================
// Full scoreboard: salted title, Buscar/Ensenar/Invitar groups, no English.
// ===========================================================================
assert.ok(body.includes('Tu Semana'), 'expected the scoreboard title');
assert.ok(body.includes('BUSCAR'), 'expected the Buscar scoreboard group');
assert.ok(body.includes('ENSEÑAR'), 'expected the Ensenar scoreboard group');
assert.ok(body.includes('INVITAR'), 'expected the Invitar scoreboard group');
assert.ok(body.includes('Contactos Intentados'), 'expected a real CCSM metric label in the scoreboard');

assert.ok(!/Goal reached|% of goal|This Wk|Last Wk|Xfer Avg|Metric<\/th>/.test(body),
  'no English scoreboard/goal-bar strings may leak into the Spanish letter');

// ===========================================================================
// Regression coverage for two real shipped bugs (found in code review,
// 2026-08-01):
//   1. effort_score was excluded from the "Otros" bucket but never placed
//      in any named group either, so it silently never appeared anywhere
//      in "Todos los Indicadores" despite being one of the 5 core metrics.
//   2. The raw junk 'effort' key (CHOICE-type NIGHTLY_FORM_RAW text,
//      always 0 as a number) was NOT excluded from the dynamic "any other
//      numeric stats key" scan, so it leaked into the scoreboard as a
//      literal untranslated English row reading "effort | 0".
// ===========================================================================
assert.ok(body.includes('ESFUERZO'), 'expected the new dedicated Esfuerzo scoreboard group');
assert.ok(body.includes('Nivel de Esfuerzo'), 'expected effort_score\'s real Spanish label to actually render in the scoreboard');
assert.ok(!/>effort</.test(body), 'the raw junk "effort" key must never render as its own scoreboard row');

console.log('scoreboard OK (including effort_score visibility + junk-key regression checks)');

console.log('agent1c numbers OK');
