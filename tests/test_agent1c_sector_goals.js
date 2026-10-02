// test_agent1c_sector_goals.js — each sector's own nightly goals in the Monday
// email (PLAN-2026-10-02-goals.md, G11 / decision G-D11).
//
// The graded week is held to AREA_WEEKLY_GOALS' row for ITS Monday, and the
// scoreboard prints next week's goal beside it ("próx."). GOALS_CONFIG holds
// the NEW week's goals by Monday night, so grading against it would be one
// week off — the reason the history tab exists.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const geminiEnvelope = JSON.stringify({
  candidates: [{ content: { parts: [{ text: JSON.stringify({ Arauco: 'Narrativa.' }) }] } }],
});
const env = makeGasEnv({ geminiResponse: {
  getResponseCode: () => 200, getContentText: () => geminiEnvelope } });
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
   'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs'],
  env.globals
);

// ── a1a_goalsFor_: per metric, history > GOALS_CONFIG > default ───────────────
{
  const got = scope.a1a_goalsFor_('A',
    { A: { contacts_attempted: 20 } },          // that week's history row
    { A: { roleplays: 3 } },                     // GOALS_CONFIG row
    { contacts_attempted: 150, roleplays: 7, church_invites: 50 });
  assert.deepStrictEqual(got, { contacts_attempted: 20, roleplays: 3, church_invites: 50 });
  // No history, no GOALS_CONFIG row: the mission default, every metric.
  assert.deepStrictEqual(scope.a1a_goalsFor_('B', null, {}, { roleplays: 7 }), { roleplays: 7 });
  console.log('a1a_goalsFor_ OK');
}

// ── The full letter ───────────────────────────────────────────────────────────
const ss = makeCcsmSpreadsheet(env, scope);
setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');

function toDateStr(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' +
         String(d.getDate()).padStart(2, '0');
}
const today = new Date(); today.setHours(0, 0, 0, 0);
const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
const monday = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - 6);
const nextMonday = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() + 1);
const weekDates = [];
for (let i = 0; i < 7; i++) {
  weekDates.push(toDateStr(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)));
}
addNightlyRaw(env, ss, weekDates.map((d, i) => ({
  zone: 'Arauco', area: 'Arauco 1', report_date: d, exchanges: 'Sí', effort: 'Algo',
  ...(i === 0 ? { contacts_attempted: 14, contacts_made: 7 } : {}),
})));
scope.runAgent3();

const org = ss.getSheetByName('MISSION_ORG');
const orgData = org.getDataRange().getValues();
const nameCol = orgData[0].indexOf('Area_Name');
const mailCol = orgData[0].indexOf('Companion1_Email');
const row = orgData.findIndex((r) => r[nameCol] === 'Arauco 1');
org.getRange(row + 1, mailCol + 1).setValue('zl.arauco1@example.com');

const bank = ss.getSheetByName('MESSAGE_BANK');
bank.appendRow(['S-CR-001', 'SUNDAY_COACHING_STRENGTH', 'contact_rate', '', 'Bien', 'Cuerpo.', '157', 'Contactar', 'D. y C. 4:4-5', 'Escritura', 'TRUE']);
bank.appendRow(['S-ES-001', 'SUNDAY_COACHING_STRENGTH', 'effort_score', '', 'Esfuerzo', 'Cuerpo.', '', '', '', '', 'TRUE']);
bank.appendRow(['G-CL-001', 'SUNDAY_COACHING_GROWTH', 'close_rate', '', 'Oportunidad', 'Cuerpo.', '205', 'Invitar', 'Moroni 10:4', 'Escritura', 'TRUE']);

// Last week's goal 20, this week's 23 — the shape area_goals_runner writes.
const hist = ss.insertSheet('AREA_WEEKLY_GOALS');
hist.appendRow(['Week_Start', 'Area', 'Overridden', 'contacts_attempted']);
hist.appendRow([toDateStr(monday), 'Arauco 1', '', 20]);
hist.appendRow([toDateStr(nextMonday), 'Arauco 1', '', 23]);

scope.runAgent1A();
scope.runAgent1B();
scope.runAgent1C();

const email = env.state.emails.find((e) => e.to === 'CCSM.PMG.Compass@gmail.com');
assert.ok(email, 'expected an email captured to the TEST_MODE inbox');
const body = email.htmlBody || '';

// The graded week used ITS goal (20): 14 attempts is 70%, not 14/150 = 9%.
assert.ok(/>20<div[^>]*>próx\. 23<\/div>/.test(body),
  'expected the scoreboard Meta cell to read 20 with "próx. 23" beneath it');
assert.ok(body.includes('70%'), 'expected 14 of 20 contact attempts to grade 70%');
assert.ok(body.includes('Meta · próx.'), 'expected the glossary to explain próx.');
console.log('sector goals in the email OK');

// No history tab rows for the week: the letter falls back and prints no próx.
{
  const env2 = makeGasEnv({ geminiResponse: {
    getResponseCode: () => 200, getContentText: () => geminiEnvelope } });
  const scope2 = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
     'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs'],
    env2.globals);
  makeCcsmSpreadsheet(env2, scope2);
  assert.strictEqual(scope2.a1a_loadWeeklyGoals_(toDateStr(monday)), null,
    'a missing AREA_WEEKLY_GOALS tab must read as null, not throw');
  console.log('missing history tab OK');
}

console.log('agent1c sector goals OK');
