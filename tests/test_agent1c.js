// test_agent1c.js — CCSM_Agent1C.gs (Sunday coaching email assembly/sending).
//
// Runs the full 1A -> 1B -> 1C chain on the Task 7 fixture pattern (seed a
// real week of DAILY_LOG via Agent3, seed 3 Spanish MESSAGE_BANK rows), with
// callGemini's Gemini API call stubbed via options.geminiResponse (see
// gas_stubs.js UrlFetchApp.fetch). Asserts an email is captured in TEST_MODE,
// the subject/body are the required exact Spanish strings, no English
// structural strings leak, and WEEKLY_BREAKDOWNS gains one row per area.
//
// Gemini call shape: CCSM_Helpers.gs callGemini() calls
// UrlFetchApp.fetch(...).getResponseCode()/.getContentText() on a REAL
// Gemini HTTP envelope ({candidates:[{content:{parts:[{text: "..."}]}}]}) —
// the stub's UrlFetchApp.fetch just returns options.geminiResponse verbatim,
// so geminiResponse here must be shaped like that envelope, and the "text"
// payload must itself be the batch-narrative JSON
// CCSM_Agent1C.gs's a1c_fetchBatchNarratives_ expects (a map of zone/district
// name -> narrative string). Only the zone 'Arauco' key is needed: Arauco 1
// (this suite's seeded area) is a Zone Leader's own area (Is_ZL=TRUE, see
// CcsmData.gs CCSM_MISSION_ORG_ROWS row A014), so the only Gemini-backed
// content this test's email actually renders is the pre-generated zone
// narrative for 'Arauco' (cached before peopleMap/email-building — see
// CCSM_Agent1C.gs a1c_pregenerateNarratives). No per-unit/mission on-demand
// call fires in this test (no MP/AP recipient), so a single fixed envelope
// answering both the zone-batch and district-batch calls is sufficient.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const geminiNarrativeJson = JSON.stringify({
  Arauco: 'Narrativa de prueba para la zona Arauco esta semana, con buen contacto y esfuerzo constante. PMG p.157 | D. y C. 4:4-5',
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

// ---------------------------------------------------------------------------
// This week's Monday..Sunday, matching CCSM_Agent1A.gs's own calculation
// (see test_agent1ab.js for the identical pattern this suite reuses).
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

// ---------------------------------------------------------------------------
// Seed a full week of nightly submissions for 'Arauco 1' (zone 'Arauco') —
// same ratios as test_agent1ab.js so strength1=contact_rate,
// strength2=effort_score, growth=close_rate (matches the seeded MESSAGE_BANK
// rows below).
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

// ---------------------------------------------------------------------------
// Set a real Companion1_Email on the 'Arauco 1' MISSION_ORG row (blank by
// default — see CcsmData.gs's note that companion emails are intentionally
// left blank pending real roster data), so Agent1C's people-map picks up a
// recipient. Arauco 1 / A014 has Is_ZL=TRUE, so this person gets BOTH their
// personal area coaching (Arauco 1) AND a Zone Summary section (Arauco) in
// the same email — exercising both code paths in one send.
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Seed MESSAGE_BANK — 3 minimal Spanish rows (same as test_agent1ab.js):
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
// Run the full chain.
// ---------------------------------------------------------------------------
scope.runAgent1A();
scope.runAgent1B();

const a1bData = scope.loadTempData('A1B_DATA');
const areaCount = Object.keys(a1bData.areas).length;
assert.ok(areaCount > 0, 'expected at least one area in A1B_DATA');

// WEEKLY_BREAKDOWNS must be empty before Agent1C runs.
assert.strictEqual(ss.getSheetByName('WEEKLY_BREAKDOWNS').getLastRow(), 0, 'WEEKLY_BREAKDOWNS must start empty');

scope.runAgent1C();

// ---------------------------------------------------------------------------
// Email assertions.
// ---------------------------------------------------------------------------
const emails = env.state.emails;
assert.ok(emails.length >= 1, 'expected at least one email captured');

// A leader now gets TWO messages: the personal coaching letter and a separate
// leadership report. They were one message until the combined body ran past
// Gmail's ~102KB clip threshold and started arriving truncated.
const testEmail = emails.find(
  (e) => e.to === 'CCSM.PMG.Compass@gmail.com' && /Entrenamiento Semanal/.test(e.subject)
);
assert.ok(testEmail, 'expected the personal coaching letter to the TEST_MODE inbox (CCSM.PMG.Compass@gmail.com)');
assert.ok(/PMG Compass — Entrenamiento Semanal/.test(testEmail.subject), 'subject must start with the required Spanish subject: ' + testEmail.subject);

const body = testEmail.htmlBody || '';
assert.ok(body.includes('Fortaleza'), 'body must contain "Fortaleza"');
assert.ok(body.includes('Área de Crecimiento'), 'body must contain "Área de Crecimiento"');
assert.ok(!/Growth Focus|Week ending|Mission Summary/.test(body), 'body must not leak English structural strings');

assert.ok(body.includes('Arauco 1'), 'expected the personal area section for Arauco 1');

// Zone Leader path: Arauco 1's companion also gets a Zone Summary (Resumen de
// Zona — Arauco), rendered from the pre-generated (cached) zone narrative — no
// on-demand Gemini call needed for this test's only recipient. It now lives in
// its OWN email rather than appended to the personal letter.
const leaderEmail = emails.find(
  (e) => e.to === 'CCSM.PMG.Compass@gmail.com' && /Resumen de Liderazgo/.test(e.subject)
);
assert.ok(leaderEmail, 'expected a SEPARATE leadership report email for the ZL');
const leaderBody = leaderEmail.htmlBody || '';
assert.ok(leaderBody.includes('Resumen de Zona — Arauco'), 'expected the ZL zone summary section in the leadership email');

// The split is the whole point — the zone summary must NOT also be duplicated
// back into the personal letter, or nothing was gained on message size.
assert.ok(!body.includes('Resumen de Zona — Arauco'), 'zone summary must NOT remain in the personal coaching letter');
assert.ok(body.includes('correo aparte'), 'personal letter must point the leader at the separate report');

// No message TEXT was generated for the personal coaching messages — the
// exact seeded subject lines must appear verbatim.
assert.ok(body.includes('¡Excelente tasa de contacto!'), 'expected the seeded strength1 subject line verbatim');
assert.ok(body.includes('Oportunidad: invitaciones al bautismo'), 'expected the seeded growth subject line verbatim');

// ---------------------------------------------------------------------------
// WEEKLY_BREAKDOWNS: gained exactly one row per area.
// ---------------------------------------------------------------------------
const wb = ss.getSheetByName('WEEKLY_BREAKDOWNS').getDataRange().getValues();
assert.strictEqual(wb.length - 1, areaCount, 'expected one new WEEKLY_BREAKDOWNS row per area (header excluded)');
const wbHeaders = wb[0];
['week_end_date', 'area', 'zone', 'district', 'contact_rate', 'mc_rate', 'lesson_rate', 'close_rate', 'effort_score', 'submissions'].forEach((col) => {
  assert.ok(wbHeaders.includes(col), 'WEEKLY_BREAKDOWNS header missing expected CCSM column: ' + col);
});
// No Provo-only/English weekly-KI columns.
['pew', 'date_metric', 'gate', 'renew', 'nm_doors', 'nm_contacted', 'nm_lessons'].forEach((col) => {
  assert.ok(!wbHeaders.includes(col), 'WEEKLY_BREAKDOWNS header must not contain dropped Provo field: ' + col);
});

const areaColIdx = wbHeaders.indexOf('area');
const arauco1Wb = wb.find((r, i) => i > 0 && r[areaColIdx] === 'Arauco 1');
assert.ok(arauco1Wb, 'expected an Arauco 1 row in WEEKLY_BREAKDOWNS');

// ---------------------------------------------------------------------------
// FEEDBACK_HISTORY: recordMessageSent() (CCSM_Helpers.gs) wrote both
// categories for Arauco 1 (Area_Code A014), including Last_Growth_Metric.
// ---------------------------------------------------------------------------
const fh = ss.getSheetByName('FEEDBACK_HISTORY').getDataRange().getValues();
const fhHeaders = fh[0];
const fhAreaIdx = fhHeaders.indexOf('Area_ID');
const fhCatIdx = fhHeaders.indexOf('Category');
const fhMsgIdx = fhHeaders.indexOf('Last_Message_ID');
const fhGrowthIdx = fhHeaders.indexOf('Last_Growth_Metric');

const strengthRow = fh.find((r, i) => i > 0 && r[fhAreaIdx] === 'A014' && r[fhCatIdx] === 'SUNDAY_COACHING_STRENGTH');
assert.ok(strengthRow, 'expected a SUNDAY_COACHING_STRENGTH FEEDBACK_HISTORY row for Arauco 1 (A014)');
assert.strictEqual(strengthRow[fhMsgIdx], 'S-CR-001');

const growthRow = fh.find((r, i) => i > 0 && r[fhAreaIdx] === 'A014' && r[fhCatIdx] === 'SUNDAY_COACHING_GROWTH');
assert.ok(growthRow, 'expected a SUNDAY_COACHING_GROWTH FEEDBACK_HISTORY row for Arauco 1 (A014)');
assert.strictEqual(growthRow[fhMsgIdx], 'G-CL-001');
assert.strictEqual(growthRow[fhGrowthIdx], 'close_rate');

// ---------------------------------------------------------------------------
// Script Properties cleaned up after Agent1C. saveTempData('A1A_DATA', '')
// stores JSON.stringify('') = '""', so loadTempData() parses back to '' (an
// empty string) rather than null — check falsiness, not strict null.
// ---------------------------------------------------------------------------
assert.ok(!scope.loadTempData('A1A_DATA'), 'A1A_DATA should be cleared after Agent1C');
assert.ok(!scope.loadTempData('A1B_DATA'), 'A1B_DATA should be cleared after Agent1C');

// ---------------------------------------------------------------------------
// No Provo/English/doors residue (acceptance grep, mirrored inline).
// ---------------------------------------------------------------------------
const srcC = require('fs').readFileSync('CCSM_Agent1C.gs', 'utf8');
assert.ok(!/Utah Provo/i.test(srcC));
assert.ok(!/America\/Denver/.test(srcC));
assert.ok(!/Growth Focus/.test(srcC));
assert.ok(!/Week ending/.test(srcC));
assert.ok(!/Mission Summary/.test(srcC));

console.log('agent1c OK');
