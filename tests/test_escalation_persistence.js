// test_escalation_persistence.js — stage state must survive a thrown send.
//
// FINAL-REVIEW FINDING (integration I-2). CCSM_AgentEscalation.gs and
// CCSM_AgentReminder.gs accumulate stage advances in an in-memory object and
// flush them to PropertiesService only AFTER their loop. The quota guard is
// well tested (see tests/test_agent_alerts.js), but the quota guard `break`s
// cleanly — it never throws. A THROWN send is a different path entirely, and
// it is reachable in production: when a relay IS configured, the fallback to
// MailApp.sendEmail() is unguarded, and MailApp raises on quota exhaustion.
//
// Without a `finally`, one thrown send discards every stage advance made in
// that run. Nothing is persisted, so the next morning's run sees every area
// still at its prior stage and RE-SENDS the reminder to everyone already
// emailed. That is duplicate mail to real missionaries, which is why this is
// worth a dedicated test rather than a line in an existing one.
//
// These tests fail (persisted stage stays at the pre-seeded value) if the
// `finally` blocks are removed from either agent.
//
// DETERMINISM: same technique as test_agent_alerts.js scenario (c) — anchor
// the missed date relative to the real current date and pre-seed the stage
// key directly, so the run reproduces "day 4 after 2 prior reminders" on any
// calendar day.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, addWeeklyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const AGENT_FILES = [
  'CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
  'CCSM_Agent3.gs', 'CCSM_AgentValidation.gs', 'CCSM_AgentDuplicate.gs',
  'CCSM_AgentReminder.gs', 'CCSM_AgentEscalation.gs',
];

function setOrgField(ss, areaName, header, value) {
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
  throw new Error('setOrgField: area not found: ' + areaName);
}

// Makes the Nth (1-based) MailApp.sendEmail call throw, imitating the quota
// exception the real MailApp raises. Earlier calls succeed normally, so the
// run has genuine stage advances to lose.
function throwOnSend(env, n) {
  const real = env.globals.MailApp.sendEmail;
  let calls = 0;
  env.globals.MailApp.sendEmail = function () {
    calls += 1;
    if (calls === n) {
      throw new Error('Service invoked too many times for one day: email.');
    }
    return real.apply(this, arguments);
  };
}

// ===========================================================================
// (a) ESCALATION System 1 — nightly
// ===========================================================================
{
  const env = makeGasEnv();
  const scope = loadGs(AGENT_FILES, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
  // Creates NIGHTLY_FORM_RAW with headers and ZERO submissions. Required:
  // ae_loadNightlySubmissions() needs the tab to exist, and without it
  // runNightlyEscalation() is a silent no-op (0 sends, no throw) — which would
  // make every assertion below vacuous. Zero submissions also means every
  // lookback date counts as missed, on any calendar day.
  addNightlyRaw(env, ss, []);

  // Three non-submitting areas, in MISSION_ORG row order. With zero nightly
  // submissions each one is missing every lookback date, so each takes the
  // stage '0' -> '1' ("Reminder 1") branch — two sends per area, for the dates
  // 2 and 3 days back.
  //
  // Deliberately NOT the stage '2' -> '3' escalation branch: that one also
  // requires ae_getEscalationEmail() to resolve a District Leader for the
  // area, and short-circuits with `continue` when it cannot. Reminder 1 needs
  // only the area's own companion email, so it fires for any area and keeps
  // this test about the flush rather than about the org chart. Both branches
  // write into the same `updates` object guarded by the same `finally`.
  const AREAS = ['Yumbel', 'Galvarino 2', 'Laja 1'];
  AREAS.forEach((a) => {
    setOrgField(ss, a, 'Companion1_Email', a.toLowerCase().replace(/\s+/g, '') + '@missionary.org');
  });

  const tz = scope.getMissionTimezone();
  const twoDaysAgo = env.globals.Utilities.formatDate(
    new Date(Date.now() - 2 * 86400000), tz, 'yyyy-MM-dd'
  );
  const props = env.globals.PropertiesService.getScriptProperties();

  // Yumbel's two sends land first (calls 1-2), so by call 3 there are genuine
  // stage advances in `updates` waiting to be flushed.
  throwOnSend(env, 3);

  let threw = null;
  try {
    scope.runNightlyEscalation();
  } catch (e) {
    threw = e;
  }

  // The throw is EXPECTED to escape — CCSM_AgentEscalation.gs deliberately does
  // not swallow (that is what surfaces the failure in Apps Script's execution
  // log). This test is about what got persisted on the way out, not about
  // suppressing the error.
  assert.ok(threw, 'the injected send failure should propagate out of runNightlyEscalation');

  const stage1 = props.getProperty('ESC_N_' + AREAS[0] + '_' + twoDaysAgo);
  assert.strictEqual(stage1, '1',
    'FIRST area was reminded successfully before the throw — its stage advance MUST be persisted, ' +
    'or the next run re-sends that reminder. Expected "1", got "' + stage1 + '". ' +
    'If this is null, the `finally` flush in runNightlyEscalation() is missing.');

  // The area whose send threw must NOT be recorded as advanced — a re-run has
  // to retry it, since its reminder never actually went out.
  const stage2 = props.getProperty('ESC_N_' + AREAS[1] + '_' + twoDaysAgo);
  assert.ok(stage2 === null || stage2 === undefined || stage2 === '0',
    'the area whose send THREW must not be recorded as advanced, so a re-run retries it; got "' + stage2 + '"');

  console.log('escalationPersistence(nightly) OK');
}

// ===========================================================================
// (b) REMINDER weekly compliance
// ===========================================================================
{
  const env = makeGasEnv();
  const scope = loadGs(AGENT_FILES, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');
  // Shipped default hands the weekly reminder to AgentEscalation; this block
  // tests ar_checkWeeklyCompliance specifically, so opt into it explicitly.
  setConfig(env, ss, 'WEEKLY_REMINDER_OWNER', 'AGENT_REMINDER');
  addWeeklyRaw(env, ss, []); // headers only — zero submissions

  const AREAS = ['Yumbel', 'Galvarino 2', 'Laja 1'];
  AREAS.forEach((a) => {
    setOrgField(ss, a, 'Companion1_Email', a.toLowerCase().replace(/\s+/g, '') + '@missionary.org');
  });

  throwOnSend(env, 2);

  try {
    scope.runReminderAgent({ skipTimeGate: true });
  } catch (e) {
    // runReminderAgent has its own top-level catch; either outcome is fine
    // here. What matters is the persisted progress below.
  }

  const tz = scope.getMissionTimezone();
  const dayName = env.globals.Utilities.formatDate(new Date(), tz, 'EEEE');
  const daysBack = { Sunday: 0, Monday: 1, Tuesday: 2, Wednesday: 3, Thursday: 4, Friday: 5, Saturday: 6 }[dayName] || 0;
  const weekKey = env.globals.Utilities.formatDate(
    new Date(Date.now() - daysBack * 86400000), tz, 'yyyy-MM-dd'
  );
  const remindedProp = env.globals.PropertiesService.getScriptProperties()
    .getProperty('AR_WEEKLY_REMINDED_' + weekKey) || '';
  const reminded = remindedProp.split(',').filter(Boolean);

  assert.ok(reminded.indexOf('yumbel') !== -1,
    'Yumbel was reminded successfully before the throw — it MUST be persisted, or the next run ' +
    're-sends it. Got: [' + reminded.join(', ') + ']. If this list is empty, the `finally` flush ' +
    'in ar_checkWeeklyCompliance() is missing.');

  console.log('escalationPersistence(weekly reminder) OK');
}

console.log('test_escalation_persistence OK');
