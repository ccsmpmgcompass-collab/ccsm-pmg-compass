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
const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs'], env.globals);
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

// ---------------------------------------------------------------------------
// Missed-days alert seeding — makes the alert assertion below REAL instead of
// vacuous. Three things must all be present for a3_checkMissedDays to send
// anything (see CCSM_Agent3.gs a3_checkMissedDays / a3_getMissingDates):
//   1. An active MESSAGE_BANK row with Category='MISSED_DAYS' (else
//      a3_loadMissedDayMessages() returns [] and the whole step no-ops).
//   2. A non-blank Companion1_Email on a real (non-leadership) MISSION_ORG
//      area — required for the Tier-1 companionship reminder.
//   3. A non-blank Companion email on that area's district's Is_DL='TRUE'
//      row — required for the Tier-2 District Leader escalation
//      (a3_buildDistrictLeaderLookup keys off District, case-insensitive).
//
// "San Pedro 2" (district "Los Huertos") is deliberately left with ZERO
// nightly submissions — unlike "San Pedro" above, which already has a
// 2026-07-10 row. MISSED_DAYS_LOOKBACK defaults to 3 (CCSM_AGENT_CONFIG_ROWS)
// and a3_getMissingDates scans back from the REAL wall-clock "today" (not a
// fixture date), so with zero submissions ALL 3 days in that window are
// missing and always consecutive — a3_findConsecutiveGaps always finds a
// 3-day run (fires Tier 1) which also meets the default
// MISSED_DAYS_ESCALATE_THRESHOLD of 3 (fires Tier 2). Anchoring on a
// partially-submitted area instead would make the gap's consecutiveness
// depend on which real calendar day the suite happens to run on.
const messageBank = ss.getSheetByName('MESSAGE_BANK');
messageBank.appendRow([
  'MD-001', 'MISSED_DAYS', '', '',
  'Recordatorio de Informe Nocturno — {{AREA}}',
  'Hola compañía de {{AREA}}: no hemos recibido su informe nocturno correspondiente a {{MISSING_DATES}}. ' +
    'Por favor complete el formulario aquí: {{FORM_LINK}}',
  '', '', '', '', 'TRUE',
]);

function setMissionOrgField(areaName, header, value) {
  const sheet = ss.getSheetByName('MISSION_ORG');
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const colIdx = headers.indexOf(header);
  const areaIdx = headers.indexOf('Area_Name');
  for (let i = 1; i < data.length; i++) {
    if (data[i][areaIdx] === areaName) {
      sheet.getRange(i + 1, colIdx + 1).setValue(value);
      return;
    }
  }
  throw new Error('setMissionOrgField: area not found: ' + areaName);
}

// "San Pedro 2" (A055) — real submitting area, district "Los Huertos".
setMissionOrgField('San Pedro 2', 'Companion1_Email', 'sanpedro2.companion@missionary.org');
// "Los Huertos" (A053) — Is_DL='TRUE' row for the SAME district, so the
// escalation tier can resolve a DL email via a3_buildDistrictLeaderLookup.
setMissionOrgField('Los Huertos', 'Companion1_Email', 'dl.loshuertos@missionary.org');

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

// missed-days: with the MESSAGE_BANK row + companion/DL emails seeded above,
// "San Pedro 2" (zero submissions) MUST trip both the Tier-1 companionship
// reminder and the Tier-2 District Leader escalation. TEST_MODE (default
// AGENT_CONFIG) redirects every alert to the test inbox regardless of the
// real recipient, and both templates are Spanish-only.
const alerts = env.state.emails;
assert.ok(alerts.length > 0, 'expected at least one missed-days alert to fire');
alerts.forEach((e) => {
  assert.strictEqual(e.to, 'CCSM.PMG.Compass@gmail.com', 'TEST_MODE must redirect to the test inbox');
  const text = e.subject + ' ' + (e.htmlBody || '');
  assert.ok(
    /Informe/.test(text) || /Alerta de Informes Faltantes/.test(text),
    'alert must contain Spanish subject/body text: ' + e.subject
  );
  assert.ok(!/Missing|Alert:|missed/i.test(text), 'alert must not leak English: ' + e.subject);
});
// At least one Tier-1 companionship reminder (subject carries the injected
// MESSAGE_BANK Subject_Line) and one Tier-2 DL escalation (fixed Spanish
// subject built directly in a3_checkMissedDays) must both be present.
assert.ok(alerts.some((e) => /Recordatorio de Informe Nocturno/.test(e.subject)), 'expected a Tier-1 companionship reminder');
assert.ok(alerts.some((e) => /Alerta de Informes Faltantes/.test(e.subject)), 'expected a Tier-2 District Leader escalation');

// no Provo/blitz/English residue
const src = require('fs').readFileSync('CCSM_Agent3.gs', 'utf8');
assert.ok(!/Utah Provo/i.test(src));
assert.ok(!/America\/Denver/.test(src));
assert.ok(!/blitz/i.test(src));
assert.ok(!/What is your area/.test(src));

console.log('agent3 OK');
