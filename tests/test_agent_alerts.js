// test_agent_alerts.js — CCSM_AgentDuplicate.gs + CCSM_AgentReminder.gs +
// CCSM_AgentEscalation.gs.
//
// Three independent scenarios, one shared spreadsheet fixture (each scenario
// touches different areas so they don't interfere with each other):
//   (a) Duplicate — two identical NIGHTLY_FORM_RAW rows for the same
//       area+date must be flagged (AGENT_RUN_LOG entry + notification email)
//       and both rows deleted.
//   (b) Reminder  — an area with no WEEKLY_FORM_RAW submission since the
//       most recent Sunday gets a Spanish reminder to the TEST inbox; an
//       area that DID submit gets nothing.
//   (c) Escalation — an area already at "Reminder 2 sent" stage for a date
//       4 days ago gets escalated to its District Leader with a Spanish
//       subject, delivered to the TEST inbox.
//
// DETERMINISM (mirrors tests/test_agent3.js): all three agents key their
// "missing since when" logic off the real wall clock (`new Date()`), not a
// fixture date. Rather than pin a fixed date (which would drift out of sync
// with "today" and become flaky), every scenario anchors relative to the
// ACTUAL current date/time:
//   (a) duplicate detection has no time dimension at all — always deterministic.
//   (b) the "submitted" area gets a WEEKLY_FORM_RAW row with the DEFAULT
//       addWeeklyRaw timestamp (`new Date()`, i.e. right now), which is
//       always >= the computed "most recent Sunday" cutoff regardless of
//       which weekday the suite runs on. The "not submitted" area simply
//       gets ZERO WEEKLY_FORM_RAW rows — zero submissions is unambiguous on
//       any date, the same technique test_agent3.js uses for its own
//       missed-days area.
//   (c) the escalation stage key is computed from `new Date()` minus 4 days
//       (formatted the same way CCSM_AgentEscalation.gs itself would), then
//       pre-seeded directly into PropertiesService — this reproduces "day 4
//       after 2 prior reminders" deterministically in a single run without
//       needing to simulate multiple days passing.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, addWeeklyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_Agent3.gs',
   'CCSM_AgentDuplicate.gs', 'CCSM_AgentReminder.gs', 'CCSM_AgentEscalation.gs'],
  env.globals
);
const ss = makeCcsmSpreadsheet(env, scope);

const MISSION_TZ = 'America/Santiago'; // CCSM_AGENT_CONFIG_ROWS MISSION_TIMEZONE default
const TEST_INBOX = 'CCSM.PMG.Compass@gmail.com'; // CCSM_AGENT_CONFIG_ROWS TEST_INBOX_EMAIL default

setConfig(env, ss, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
setConfig(env, ss, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');

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

// ===========================================================================
// (a) DUPLICATE — CCSM_AgentDuplicate.gs
// ===========================================================================

setMissionOrgField('Arauco 1', 'Companion1_Email', 'arauco1.companion@missionary.org');

addNightlyRaw(env, ss, [
  { zone: 'Arauco', area: 'Arauco 1', report_date: '2026-07-10', exchanges: 'Sí', roleplays: 2 },
  { zone: 'Arauco', area: 'Arauco 1', report_date: '2026-07-10', exchanges: 'Sí', roleplays: 3 },
]);

const nightlyRowsBefore = ss.getSheetByName('NIGHTLY_FORM_RAW').getDataRange().getValues().length - 1;
assert.strictEqual(nightlyRowsBefore, 2, 'expected 2 seeded duplicate rows before the agent runs');

scope.onNightlyFormSubmit();

const nightlyRowsAfter = ss.getSheetByName('NIGHTLY_FORM_RAW').getDataRange().getValues().length - 1;
assert.strictEqual(nightlyRowsAfter, 0, 'both duplicate rows must be deleted from NIGHTLY_FORM_RAW');

// AgentDuplicate logs via logRun() -> AGENT_RUN_LOG (not AUDIT_LOG — verified
// by reading CCSM_AgentDuplicate.gs: it never touches AUDIT_LOG at all).
const runLog = ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
const runLogHeaders = runLog[0];
const agentCol = runLogHeaders.indexOf('Agent');
const notesCol = runLogHeaders.indexOf('Notes');
const dupRunRow = runLog.find((r) => r[agentCol] === 'AgentDuplicate');
assert.ok(dupRunRow, 'expected an AGENT_RUN_LOG row for AgentDuplicate');
assert.ok(
  /duplicate group\(s\) resolved/.test(String(dupRunRow[notesCol])),
  'AGENT_RUN_LOG entry must flag the duplicate group: ' + dupRunRow[notesCol]
);

// Duplicate notification email — Spanish, TEST_MODE-redirected.
const dupEmail = env.state.emails.find((e) => /Envío Duplicado/.test(e.subject));
assert.ok(dupEmail, 'expected a Spanish duplicate-notification email');
assert.strictEqual(dupEmail.to, TEST_INBOX, 'TEST_MODE must redirect to the test inbox');
assert.ok(dupEmail.subject.indexOf('[TEST]') === 0, 'subject must carry the [TEST] prefix');
assert.ok(/Arauco 1/.test(dupEmail.htmlBody || dupEmail.body), 'body must reference the area');

console.log('agentDuplicate OK');

// ===========================================================================
// (b) REMINDER — CCSM_AgentReminder.gs (weekly compliance half)
// ===========================================================================

setMissionOrgField('Cabrero 1', 'Companion1_Email', 'cabrero1.companion@missionary.org');
setMissionOrgField('Cabrero 2', 'Companion1_Email', 'cabrero2.companion@missionary.org');

// "Cabrero 1" submitted the weekly form just now (default addWeeklyRaw
// timestamp = new Date()) — always counts as "this week" regardless of the
// real weekday the suite runs on.
addWeeklyRaw(env, ss, [
  { zone: 'Los Angeles Norte', area: 'Cabrero 1', report_date: '2026-07-10',
    leader_call: 'Sí', correlation_meeting: 'Sí' },
]);
// "Cabrero 2" gets ZERO WEEKLY_FORM_RAW rows — unambiguously non-submitting.

scope.runReminderAgent();

const weeklySubject = '[TEST] Recordatorio: Informe Semanal — ' + scope.getMissionName();
const remindedEmails = env.state.emails.filter((e) => e.subject === weeklySubject);

const remindedCabrero2 = remindedEmails.some((e) => /Cabrero 2/.test(e.htmlBody || e.body));
const remindedCabrero1 = remindedEmails.some((e) => /Cabrero 1/.test(e.htmlBody || e.body));
assert.ok(remindedCabrero2, 'non-submitting area "Cabrero 2" must receive the weekly reminder');
assert.ok(!remindedCabrero1, 'submitting area "Cabrero 1" must NOT receive the weekly reminder');

const cabrero2Email = remindedEmails.find((e) => /Cabrero 2/.test(e.htmlBody || e.body));
assert.strictEqual(cabrero2Email.to, TEST_INBOX, 'TEST_MODE must redirect to the test inbox');
assert.ok(
  /¡Hola! Este es su recordatorio para enviar el informe semanal de esta semana\./.test(cabrero2Email.htmlBody || cabrero2Email.body),
  'body must contain the exact required Spanish reminder sentence'
);
assert.ok(
  /Enviar Informe Ahora/.test(cabrero2Email.htmlBody || cabrero2Email.body),
  'body must contain the "Enviar Informe Ahora" button'
);
assert.ok(
  (cabrero2Email.htmlBody || cabrero2Email.body).indexOf('https://forms.example/weekly') !== -1,
  'button must link WEEKLY_FORM_LINK'
);

console.log('agentReminder OK');

// ===========================================================================
// (c) ESCALATION — CCSM_AgentEscalation.gs (nightly System 1)
// ===========================================================================

setMissionOrgField('San Pedro 2', 'Companion1_Email', 'sanpedro2.companion@missionary.org');
setMissionOrgField('Los Huertos', 'Companion1_Email', 'dl.loshuertos@missionary.org');

// Pre-seed PropertiesService so the missed date 4 days ago is already at
// "Reminder 2 sent" (stage '2') — on this run, System 1 will therefore
// escalate that specific date straight to the District Leader, deterministic
// regardless of which real calendar day the suite executes on.
const fourDaysAgo = env.globals.Utilities.formatDate(
  new Date(Date.now() - 4 * 86400000), MISSION_TZ, 'yyyy-MM-dd'
);
env.globals.PropertiesService.getScriptProperties().setProperty(
  'ESC_N_San Pedro 2_' + fourDaysAgo, '2'
);

scope.runNightlyEscalation();

const escSubject = 'Escalamiento: Informes Faltantes — San Pedro 2';
const escEmail = env.state.emails.find((e) => e.subject.indexOf(escSubject) !== -1);
assert.ok(escEmail, 'expected a DL escalation email for "San Pedro 2"');
assert.strictEqual(escEmail.to, TEST_INBOX, 'TEST_MODE must redirect to the test inbox');
assert.ok(escEmail.subject.indexOf('[TEST]') === 0, 'subject must carry the [TEST] prefix');
assert.ok(
  !/Missing|Alert:|Escalation:/i.test(escEmail.subject),
  'subject must not leak English: ' + escEmail.subject
);

console.log('agentEscalation OK');

// ===========================================================================
// No Provo/blitz/English-form residue in any of the three forked files
// ===========================================================================
['CCSM_AgentDuplicate.gs', 'CCSM_AgentReminder.gs', 'CCSM_AgentEscalation.gs'].forEach((file) => {
  const src = require('fs').readFileSync(file, 'utf8');
  assert.ok(!/Utah Provo/i.test(src), file + ' must not contain "Utah Provo"');
  assert.ok(!/America\/Denver/.test(src), file + ' must not contain "America/Denver"');
  assert.ok(!/What is your area/i.test(src), file + ' must not contain the English form column text');
});

console.log('agent alerts OK');
