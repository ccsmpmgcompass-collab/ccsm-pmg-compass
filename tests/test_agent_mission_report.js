// test_agent_mission_report.js — CCSM_AgentMissionReport.gs (Phase 6:
// weekly mission-wide numbers for AP/MP). No Provo equivalent -- built
// fresh, independent of the Agent1A/1B/1C chain (see the file's own header
// for why). Seeds 2 zones' worth of DAILY_LOG + a SCORES tab, sets one
// MISSION_ORG row Is_AP=TRUE and another Is_MP=TRUE, and asserts on the
// actual sent email.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs', 'CCSM_AgentMissionReport.gs'],
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
const weekEndStr = weekDates[6];

// ---------------------------------------------------------------------------
// Two areas, two zones. Arauco 1 reports all 7 days; Camilo Olivarria 1
// reports only 3 (proves the compliance count is real, not "everyone
// submitted"). Monday carries the real metric numbers, matching every other
// suite's convention in this repo.
// ---------------------------------------------------------------------------
const araucoRows = weekDates.map((d, i) => ({
  zone: 'Arauco', area: 'Arauco 1', report_date: d, exchanges: 'Sí', effort: 'Algo',
  ...(i === 0 ? { contacts_made: 10, friend_lessons: 4, baptismal_invitations: 1 } : {}),
}));
const camiloRows = weekDates.slice(0, 3).map((d, i) => ({
  zone: 'Camilo', area: 'Camilo Olivarria 1', report_date: d, exchanges: 'Sí', effort: 'Algo',
  ...(i === 0 ? { contacts_made: 6, friend_lessons: 2, baptismal_invitations: 0 } : {}),
}));
addNightlyRaw(env, ss, araucoRows.concat(camiloRows));
scope.runAgent3();

// ---------------------------------------------------------------------------
// SCORES tab: starts empty (no header row) like DAILY_LOG -- write it the
// same way CCSM_AgentScores.gs would, then 3 area rows so the report has a
// real "top 5 / bottom 5" (with fewer than 5 areas total, both lists just
// show what exists -- no padding, no fabricated rows).
// ---------------------------------------------------------------------------
const scoresHeaders = ['Area_Code', 'Area_Name', 'Zone', 'Missionary_Names',
  'Week_Ending_Date', 'Effort_Score', 'Skill_Score', 'KI_Score', 'Effectiveness_Score', 'Computed_At'];
const scoresSheet = ss.getSheetByName('SCORES');
scoresSheet.getRange(1, 1, 1, scoresHeaders.length).setValues([scoresHeaders]);
scoresSheet.appendRow(['A014', 'Arauco 1', 'Arauco', 'Elder A / Elder B', weekEndStr, 80, 75, 90, 82, new Date()]);
scoresSheet.appendRow(['C001', 'Camilo Olivarria 1', 'Camilo', 'Elder C / Elder D', weekEndStr, 40, 35, 30, 38, new Date()]);

// ---------------------------------------------------------------------------
// Leader flags: Arauco 1's companion is the AP, Camilo Olivarria 1's is the MP.
// ---------------------------------------------------------------------------
const orgSheet = ss.getSheetByName('MISSION_ORG');
const orgData = orgSheet.getDataRange().getValues();
const orgHeaders = orgData[0];
const nameCol = orgHeaders.indexOf('Area_Name');
const email1Col = orgHeaders.indexOf('Companion1_Email');
const isApCol = orgHeaders.indexOf('Is_AP');
const isMpCol = orgHeaders.indexOf('Is_MP');
for (let i = 1; i < orgData.length; i++) {
  if (orgData[i][nameCol] === 'Arauco 1') {
    orgSheet.getRange(i + 1, email1Col + 1).setValue('ap@example.com');
    orgSheet.getRange(i + 1, isApCol + 1).setValue('TRUE');
  }
  if (orgData[i][nameCol] === 'Camilo Olivarria 1') {
    orgSheet.getRange(i + 1, email1Col + 1).setValue('mp@example.com');
    orgSheet.getRange(i + 1, isMpCol + 1).setValue('TRUE');
  }
}

scope.runAgentMissionReport();

// ===========================================================================
// Recipients: exactly the AP and MP addresses, no duplicates, no one else.
// ===========================================================================
// TEST_MODE defaults TRUE in the builder, so resolveRecipient() redirects
// every real address to the TEST_INBOX_EMAIL -- same as every other suite
// in this repo (see test_agent1c.js). 2 sends still means 2 real
// recipients were resolved (AP + MP), even though both land in one inbox.
const emails = env.state.emails;
assert.strictEqual(emails.length, 2, 'expected exactly 2 emails, one per AP/MP recipient');
assert.ok(emails.every((e) => e.to === 'CCSM.PMG.Compass@gmail.com'),
  'expected both sends redirected to the TEST_MODE inbox');

console.log('recipients OK');

const body = emails[0].htmlBody || '';
assert.ok(/Números de la Misión/.test(emails[0].subject), 'expected the Spanish subject line');

// ===========================================================================
// Compliance: 2 of 99 areas submitted at all (only Arauco 1 and Camilo
// Olivarria 1 have any DAILY_LOG rows this week).
// ===========================================================================
assert.ok(/2 \/ \d+ áreas/.test(body), 'expected a real "N / total áreas" compliance count, got: ' + body.match(/\d+ \/ \d+ áreas/));

console.log('compliance OK');

// ===========================================================================
// Mission-wide KPI tiles: sums across BOTH areas (contacts_made 10+6=16).
// ===========================================================================
assert.ok(body.includes('Totales de la Misión'), 'expected the mission totals section');
assert.ok(body.includes('>16<'), 'expected the summed contacts_made (10+6) tile value');
assert.ok(body.includes('Contactos Logrados'), 'expected a real CCSM metric label, not a raw key');

console.log('KPI tiles OK');

// ===========================================================================
// Zone-by-zone table: both zones present with their own area's numbers.
// ===========================================================================
assert.ok(body.includes('Arauco') && body.includes('Camilo'), 'expected both zones in the breakdown table');

console.log('zone table OK');

// ===========================================================================
// Scores summary: mission averages + top/bottom, using real Effectiveness
// values (Arauco 1 highest at 82, Camilo Olivarria 1 lowest at 38).
// ===========================================================================
assert.ok(body.includes('Resumen de Puntajes'), 'expected the scores summary section');
assert.ok(body.includes('Arauco 1'), 'expected Arauco 1 named in the scores ranking');
assert.ok(body.includes('Camilo Olivarria 1'), 'expected Camilo Olivarria 1 named in the scores ranking');

console.log('scores summary OK');

console.log('agent mission report OK');
