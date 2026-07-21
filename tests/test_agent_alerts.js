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
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs',
   'CCSM_AgentValidation.gs', 'CCSM_AgentDuplicate.gs', 'CCSM_AgentReminder.gs', 'CCSM_AgentEscalation.gs'],
  env.globals
);
const ss = makeCcsmSpreadsheet(env, scope);

const MISSION_TZ = 'America/Santiago'; // CCSM_AGENT_CONFIG_ROWS MISSION_TIMEZONE default
const TEST_INBOX = 'CCSM.PMG.Compass@gmail.com'; // CCSM_AGENT_CONFIG_ROWS TEST_INBOX_EMAIL default

setConfig(env, ss, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
setConfig(env, ss, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');
// WEEKLY_REMINDER_OWNER (added in Task 14 — see CCSM_Setup.gs's header) makes
// the AgentReminder-vs-AgentEscalation weekly-reminder overlap a single-owner
// choice. The SHIPPED DEFAULT is AGENT_ESCALATION, which switches
// ar_checkWeeklyCompliance() off; scenario (b) below tests that function
// specifically, so it opts into the AGENT_REMINDER path explicitly. Set here,
// with the other config, because CCSM_Helpers.readAgentConfig() caches
// AGENT_CONFIG on the first getConfig() call of the execution.
setConfig(env, ss, 'WEEKLY_REMINDER_OWNER', 'AGENT_REMINDER');

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

// ---------------------------------------------------------------------------
// (a-neg) DUPLICATE — negative case: the dup key is area+date, not area
// alone. Two rows for the SAME area on DIFFERENT dates must NOT be flagged
// as duplicates — both must survive.
// ---------------------------------------------------------------------------
addNightlyRaw(env, ss, [
  { zone: 'Arauco', area: 'Arauco 2', report_date: '2026-07-08', exchanges: 'Sí', roleplays: 1 },
  { zone: 'Arauco', area: 'Arauco 2', report_date: '2026-07-09', exchanges: 'Sí', roleplays: 2 },
]);

const negRowsBefore = ss.getSheetByName('NIGHTLY_FORM_RAW').getDataRange().getValues().length - 1;
assert.strictEqual(negRowsBefore, 2, 'expected 2 seeded same-area/different-date rows before the agent runs');

scope.onNightlyFormSubmit();

const negRowsAfter = ss.getSheetByName('NIGHTLY_FORM_RAW').getDataRange().getValues().length - 1;
assert.strictEqual(negRowsAfter, 2,
  'same area on DIFFERENT dates must NOT be treated as a duplicate — both rows must survive (dup key is area+date, not area alone)');

console.log('agentDuplicate negative case (same area, different dates) OK');

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

// skipTimeGate: true — see CCSM_AgentReminder.gs's restored Mon/Tue 8 AM–9 PM
// day/hour gate on ar_checkWeeklyCompliance(). Bypassing it here keeps this
// scenario deterministic regardless of which real weekday/hour the suite runs.
scope.runReminderAgent({ skipTimeGate: true });

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
// (d) QUOTA GUARD — CCSM_AgentReminder.gs's weekly compliance half must stop
// sending once MailApp's remaining daily quota drops below 20, persist
// progress for areas already reminded (so a re-run does not re-send them),
// leave areas the guard blocked UNreminded (so a re-run picks them up
// normally), and never let an exception escape runReminderAgent().
//
// Isolated env/spreadsheet so remainingQuota starts clean and unaffected by
// the emails already sent in scenarios (a)/(b)/(c) above.
// ===========================================================================
{
  const quotaEnv = makeGasEnv({ remainingQuota: 20 });
  const quotaScope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs',
     'CCSM_AgentValidation.gs', 'CCSM_AgentDuplicate.gs', 'CCSM_AgentReminder.gs', 'CCSM_AgentEscalation.gs'],
    quotaEnv.globals
  );
  const quotaSs = makeCcsmSpreadsheet(quotaEnv, quotaScope);
  setConfig(quotaEnv, quotaSs, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');
  // See scenario (b): opt into the AgentReminder weekly path explicitly, since
  // the shipped WEEKLY_REMINDER_OWNER default hands it to AgentEscalation.
  setConfig(quotaEnv, quotaSs, 'WEEKLY_REMINDER_OWNER', 'AGENT_REMINDER');
  // Creates WEEKLY_FORM_RAW with headers only (zero submissions) — ar_checkWeeklyCompliance
  // requires the tab to exist.
  addWeeklyRaw(quotaEnv, quotaSs, []);

  function setQuotaOrgField(areaName, header, value) {
    const sheet = quotaSs.getSheetByName('MISSION_ORG');
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
    throw new Error('setQuotaOrgField: area not found: ' + areaName);
  }

  // Three non-submitting areas, all in MISSION_ORG row order ahead of any
  // other area with a companion email set in this isolated fixture (Yumbel,
  // Galvarino 2, Laja 1 — all zone "Los Angeles Norte"). None get a
  // WEEKLY_FORM_RAW row, so all three are otherwise eligible for the reminder.
  setQuotaOrgField('Yumbel', 'Companion1_Email', 'yumbel.companion@missionary.org');
  setQuotaOrgField('Galvarino 2', 'Companion1_Email', 'galvarino2.companion@missionary.org');
  setQuotaOrgField('Laja 1', 'Companion1_Email', 'laja1.companion@missionary.org');

  let quotaRunError = null;
  try {
    quotaScope.runReminderAgent({ skipTimeGate: true });
  } catch (e) {
    quotaRunError = e;
  }
  assert.strictEqual(quotaRunError, null,
    'runReminderAgent must not let an exception escape when the quota guard trips: ' +
    (quotaRunError && quotaRunError.message));

  const quotaWeeklySubject = '[TEST] Recordatorio: Informe Semanal — ' + quotaScope.getMissionName();
  const quotaReminded = quotaEnv.state.emails.filter((e) => e.subject === quotaWeeklySubject);
  assert.strictEqual(quotaReminded.length, 1,
    'remainingQuota=20 means the <20 check passes once (send, quota drops to 19) then trips on the ' +
    'next area — exactly 1 weekly reminder should send before the guard stops the run, got ' +
    quotaReminded.length);
  assert.ok(/Yumbel/.test(quotaReminded[0].htmlBody || quotaReminded[0].body),
    'the one area reminded must be the first eligible one in MISSION_ORG row order (Yumbel)');

  // Progress persistence: the reminded area must be recorded (no duplicate
  // re-send next run); the blocked areas must NOT be recorded (so a re-run
  // with quota available picks them up normally).
  const qtz = quotaScope.getMissionTimezone();
  const qDayName = quotaEnv.globals.Utilities.formatDate(new Date(), qtz, 'EEEE');
  const qDaysBack = { Sunday: 0, Monday: 1, Tuesday: 2, Wednesday: 3, Thursday: 4, Friday: 5, Saturday: 6 }[qDayName] || 0;
  const qWeekKey = quotaEnv.globals.Utilities.formatDate(
    new Date(Date.now() - qDaysBack * 86400000), qtz, 'yyyy-MM-dd'
  );
  const qRemindedProp = quotaEnv.globals.PropertiesService.getScriptProperties()
    .getProperty('AR_WEEKLY_REMINDED_' + qWeekKey) || '';
  const qRemindedList = qRemindedProp.split(',').filter(Boolean);
  assert.ok(qRemindedList.indexOf('yumbel') !== -1,
    'Yumbel must be recorded as reminded so a re-run does not re-send it');
  assert.strictEqual(qRemindedList.indexOf('galvarino 2'), -1,
    'Galvarino 2 must NOT be recorded as reminded — the guard blocked it before it sent, so a re-run must still try it');
  assert.strictEqual(qRemindedList.indexOf('laja 1'), -1,
    'Laja 1 must NOT be recorded as reminded — the guard blocked it before it sent, so a re-run must still try it');

  console.log('agentReminder quota guard OK');
}

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
