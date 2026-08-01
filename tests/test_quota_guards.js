// test_quota_guards.js — the main account's 100/day Gmail limit must degrade
// visibly, not silently.
//
// This pins down a failure that was live on COMPASS_CCSM for five days.
// Agent3 sent 97 missed-day alerts on 2026-07-29 and exhausted the account.
// Every run from 2026-07-30 to 2026-08-01 then logged
//   "MISSED_DAYS ERROR: Service invoked too many times for one day: email."
// inside a row whose Status column said SUCCESS, and sent nothing at all.
// Anyone reading AGENT_RUN_LOG saw a healthy agent and "0 alerts sent", which
// is indistinguishable from "everyone reported on time".
//
// Agent1C had the same exposure and worse consequences: its send loop is one
// email per unique address in MISSION_ORG (97 on the live roster), it caught
// per-email failures into an emailErrors counter, and it reported SUCCESS.
//
// Both now check MailApp.getRemainingDailyQuota() before each send, count what
// they could not send, and force the run's status to ERROR. Both skip the
// guard entirely when the relay is configured, because relay mail leaves
// through UrlFetchApp on another account's quota.
//
// gas_stubs' makeGasEnv({ remainingQuota: N }) decrements on every send, so
// the exhaustion point is deterministic.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');

const GS = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs',
  'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs'];

// ---------------------------------------------------------------------------
// Agent3 harness. Seeds the three things a3_checkMissedDays needs to send
// anything (an active MISSED_DAYS MESSAGE_BANK row, a companion email on a
// non-leadership area, a DL email for that area's district) across MANY areas,
// so the run wants far more sends than the quota allows.
// ---------------------------------------------------------------------------
function runAgent3WithQuota(remainingQuota, opts) {
  opts = opts || {};
  const env = makeGasEnv({ remainingQuota });
  const scope = loadGs(GS, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);

  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');
  setConfig(env, ss, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
  if (opts.relay) {
    setConfig(env, ss, 'RELAY_2_URL', 'https://script.google.com/macros/s/AKfy/exec');
    setConfig(env, ss, 'RELAY_SECRET', 'shhh');
  }

  // Creates NIGHTLY_FORM_RAW with the real multi-section header and no data
  // rows — Agent3 reads the tab unconditionally, and "no submissions at all"
  // is exactly the state that makes every area overdue.
  addNightlyRaw(env, ss, []);

  ss.getSheetByName('MESSAGE_BANK').appendRow([
    'MD-001', 'MISSED_DAYS', '', '',
    'Recordatorio de Informe Nocturno — {{AREA}}',
    'Hola compañía de {{AREA}}: falta su informe de {{MISSING_DATES}}. {{FORM_LINK}}',
    '', '', '', '', 'TRUE',
  ]);

  // Give EVERY area a companion email so the fan-out is as wide as the real
  // roster. No nightly submissions are seeded at all, so every area has a full
  // lookback window of missing days and every one of them wants an alert.
  const orgSheet = ss.getSheetByName('MISSION_ORG');
  const orgData = orgSheet.getDataRange().getValues();
  const headers = orgData[0];
  const c1 = headers.indexOf('Companion1_Email');
  const areaIdx = headers.indexOf('Area_Name');
  for (let i = 1; i < orgData.length; i++) {
    const slug = String(orgData[i][areaIdx]).toLowerCase().replace(/[^a-z0-9]/g, '');
    orgSheet.getRange(i + 1, c1 + 1).setValue(slug + '@missionary.org');
  }

  scope.runAgent3();

  const runLog = ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
  const last = runLog[runLog.length - 1];
  return { env, scope, ss, status: last[2], notes: String(last[7] || '') };
}

// --- 1. Control: plenty of quota => SUCCESS, no shortfall reported ----------
const plenty = runAgent3WithQuota(1000);
assert.strictEqual(plenty.status, 'SUCCESS',
  'with quota to spare Agent3 must still report SUCCESS: ' + plenty.notes);
assert.ok(!/QUOTA EXHAUSTED/.test(plenty.notes),
  'no shortfall may be reported when none occurred: ' + plenty.notes);
const plentySent = plenty.env.state.emails.length;
assert.ok(plentySent > 20,
  'the fixture must want a large burst for this test to mean anything, got ' + plentySent);

// --- 2. Tight quota: sends what fits, reports the rest, status ERROR --------
const tight = runAgent3WithQuota(10);
assert.ok(tight.env.state.emails.length <= 10,
  'Agent3 must not send past the quota, sent ' + tight.env.state.emails.length);
assert.ok(tight.env.state.emails.length > 0,
  'Agent3 must still send what the quota allows, not give up entirely');
assert.strictEqual(tight.status, 'ERROR',
  'a run that dropped alerts for quota must NOT be logged SUCCESS. Notes: ' + tight.notes);
assert.ok(/QUOTA EXHAUSTED: \d+ alert\(s\) NOT sent/.test(tight.notes),
  'the run notes must state how many alerts were dropped: ' + tight.notes);
assert.ok(/RELAY_2_URL/.test(tight.notes),
  'the notes must name the fix, since the reader is an operator not a developer');

// --- 3. The dropped count is real, not a constant ---------------------------
const tighter = runAgent3WithQuota(3);
function skippedCount(notes) {
  const m = notes.match(/QUOTA EXHAUSTED: (\d+) alert/);
  return m ? Number(m[1]) : 0;
}
assert.ok(skippedCount(tighter.notes) > skippedCount(tight.notes),
  'a smaller quota must drop more alerts: quota 3 dropped ' +
  skippedCount(tighter.notes) + ', quota 10 dropped ' + skippedCount(tight.notes));

// --- 4. No partial-send crash: the run still completes its other steps ------
assert.ok(/LIVE_SNAPSHOT: rebuilt/.test(tight.notes),
  'exhausting the quota must not abort DAILY_LOG/LIVE_SNAPSHOT: ' + tight.notes);

// --- 5. Relay configured => guard does not fire even at zero quota ----------
// Relay mail leaves via UrlFetchApp on the relay account. The stub's
// UrlFetchApp.fetch throws with no geminiResponse configured, which is exactly
// what a relay outage looks like; sendEmail() catches it and falls back to
// MailApp. So this asserts the GUARD's behavior (it did not pre-emptively skip
// on a MailApp quota that does not apply), not that relay delivery succeeded.
const relayed = runAgent3WithQuota(0, { relay: true });
assert.ok(!/QUOTA EXHAUSTED/.test(relayed.notes),
  'with the relay configured, the MailApp quota guard must not fire: ' + relayed.notes);

// --- 6. a3_relayConfigured demands BOTH url and secret ----------------------
// sendEmail() falls back to MailApp when the secret is missing, so a URL alone
// must NOT disable the guard.
{
  const env = makeGasEnv({ remainingQuota: 5 });
  const scope = loadGs(GS, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'RELAY_2_URL', 'https://script.google.com/macros/s/AKfy/exec');
  setConfig(env, ss, 'RELAY_SECRET', '');
  assert.strictEqual(scope.a3_relayConfigured(), false,
    'a relay URL with no secret still spends the MAIN account quota, so the ' +
    'guard must stay armed');
}

// ---------------------------------------------------------------------------
// Agent1C. Same property, different agent: its send loop is the largest single
// burst in the system.
// ---------------------------------------------------------------------------
const geminiEnvelope = {
  getResponseCode: () => 200,
  getContentText: () => JSON.stringify({
    candidates: [{ content: { parts: [{ text: '{}' }] } }],
  }),
};

function runChainWithQuota(remainingQuota) {
  const env = makeGasEnv({ remainingQuota, geminiResponse: geminiEnvelope });
  const scope = loadGs(
    GS.concat(['CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs']),
    env.globals
  );
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');

  // Agent1B needs message-bank rows to attach; Agent1C needs the people map,
  // which comes from MISSION_ORG's emails.
  const bank = ss.getSheetByName('MESSAGE_BANK');
  ['SUNDAY_COACHING_STRENGTH', 'SUNDAY_COACHING_GROWTH'].forEach((cat, i) => {
    ['contact_rate', 'effort_score', 'close_rate'].forEach((metric, j) => {
      bank.appendRow([
        'MSG-' + i + '-' + j, cat, metric, '',
        'Asunto de prueba', 'Cuerpo del mensaje de prueba.',
        '', '', '', '', 'TRUE',
      ]);
    });
  });

  const orgSheet = ss.getSheetByName('MISSION_ORG');
  const orgData = orgSheet.getDataRange().getValues();
  const headers = orgData[0];
  const c1 = headers.indexOf('Companion1_Email');
  const areaIdx = headers.indexOf('Area_Name');
  for (let i = 1; i < orgData.length; i++) {
    const slug = String(orgData[i][areaIdx]).toLowerCase().replace(/[^a-z0-9]/g, '');
    orgSheet.getRange(i + 1, c1 + 1).setValue(slug + '@missionary.org');
  }

  // A week of submissions for one area so Agent1A has something to analyze.
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
  const monday = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - 6);
  const rows = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i);
    rows.push({
      zone: 'Arauco', area: 'Arauco 1',
      report_date: d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
                   '-' + String(d.getDate()).padStart(2, '0'),
      contacts_attempted: 20, contacts_made: 10, meaningful_conversations: 5,
      friend_lessons: 2, new_people_found: 1, effort: 'Todo',
    });
  }
  addNightlyRaw(env, ss, rows);

  scope.runAgent1A();
  scope.runAgent1B();
  env.state.emails.length = 0;      // discard anything the earlier steps sent
  env.state.remainingQuota = remainingQuota;
  scope.runAgent1C();

  const runLog = ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
  const a1c = runLog.filter((r) => r[1] === 'Agent1C').pop();
  return { env, scope, status: a1c && a1c[2], notes: String((a1c && a1c[7]) || '') };
}

const chainPlenty = runChainWithQuota(1000);
assert.strictEqual(chainPlenty.status, 'SUCCESS',
  'Agent1C with quota to spare must report SUCCESS: ' + chainPlenty.notes);
assert.ok(chainPlenty.env.state.emails.length > 20,
  'the Agent1C fixture must produce a large burst, got ' +
  chainPlenty.env.state.emails.length);

const chainTight = runChainWithQuota(5);
assert.ok(chainTight.env.state.emails.length <= 5,
  'Agent1C must not send past the quota, sent ' + chainTight.env.state.emails.length);
assert.strictEqual(chainTight.status, 'ERROR',
  'Agent1C must NOT report SUCCESS when missionaries got no coaching letter: ' +
  chainTight.notes);
assert.ok(/QUOTA EXHAUSTED: \d+ missionary/.test(chainTight.notes),
  'Agent1C must state how many people received nothing: ' + chainTight.notes);
assert.ok(/RELAY_2_URL/.test(chainTight.notes),
  'Agent1C notes must name the fix too: ' + chainTight.notes);

console.log('quota guards OK — Agent3 and Agent1C degrade visibly, not silently');
