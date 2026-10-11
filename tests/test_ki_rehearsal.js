// test_ki_rehearsal.js — the KI PDF dress rehearsal (CCSM_KiRehearsal.gs)
// mails ONLY the address it is given, never the mission, and reports PASS /
// FAIL the way Monday's run would turn out.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');

const GS = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
  'CCSM_Agent3.gs', 'CCSM_Agent5A.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs',
  'CCSM_KiRehearsal.gs'];
const TO = 'tester@missionary.org';

function setup(opts) {
  opts = opts || {};
  const relayCalls = [];
  const env = makeGasEnv({
    urlFetch: (url, params) => {
      const req = JSON.parse(params.payload);
      relayCalls.push(req);
      const n = opts.oldRelay ? 0 : (req.attachments || []).length;
      return { getResponseCode: () => 200, getContentText: () => JSON.stringify({ success: true, attachments: n }) };
    },
  });
  const scope = loadGs(GS, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'TEST_MODE', 'FALSE');
  setConfig(env, ss, 'RELAY_2_URL', 'https://script.google.com/macros/s/AKfy/exec');
  setConfig(env, ss, 'RELAY_SECRET', 'shhh');
  addNightlyRaw(env, ss, []);
  const org = ss.getSheetByName('MISSION_ORG');
  const data = org.getDataRange().getValues();
  const h = data[0];
  for (let i = 1; i < data.length; i++) {
    if (data[i][h.indexOf('Area_Name')] === 'Arauco 1') {
      org.getRange(i + 1, h.indexOf('Companion1_Email') + 1).setValue('zl.arauco1@missionary.org');
    }
  }
  ss.insertSheet('MISSION_LEADERSHIP').getRange(1, 1, 2, 5).setValues([
    ['Name', 'Email', 'Role', 'Active', 'Notes'],
    ['AP Uno', 'ap.uno@missionary.org', 'assistant', 'TRUE', ''],
  ]);
  return { env, scope, ss, relayCalls };
}

// Plays the GitHub job: one PDF row per document under the REQUEST's stamp.
function playJob(env, ss, docs) {
  const sheet = ss.getSheetByName('KI_PDF_OUTBOX');
  const req = sheet.getDataRange().getValues()[1];
  const U = env.globals.Utilities;
  docs.forEach(([scope, name]) => {
    const bytes = Array.from(Buffer.from('%PDF-1.4 ' + scope, 'utf8'));
    sheet.appendRow(['PDF', req[1], scope, name, req[4], '3', '1', U.base64Encode(bytes)]);
  });
}

const DOCS = [['MISSION', 'Indicadores_clave_mision.pdf'], ['Arauco', 'Indicadores_clave_Arauco.pdf']];

// 1. Happy path: step 1 requests (creating the tab), the job builds, step 2
//    sends exactly two test emails, both to TO, with the right PDFs.
{
  const { env, scope, ss, relayCalls } = setup();
  const s1 = scope.rehearseKiPdfsStep1();
  assert.ok(s1.some((l) => /^Created KI_PDF_OUTBOX/.test(l)), s1.join('\n'));
  assert.ok(s1.some((l) => /^PASS/.test(l)), s1.join('\n'));
  const req = ss.getSheetByName('KI_PDF_OUTBOX').getDataRange().getValues()[1];
  assert.deepStrictEqual(req.slice(0, 2).concat(req[4]), ['REQUEST', '2026-10-04', '2026-10-11 00:00:00']);

  playJob(env, ss, DOCS);
  const s2 = scope.rehearseKiPdfsStep2(TO);
  assert.ok(s2.some((l) => /^PASS/.test(l)), s2.join('\n'));
  assert.strictEqual(relayCalls.length, 2, 'two test emails, nothing else');
  relayCalls.forEach((c) => assert.strictEqual(c.to, TO, 'never a missionary'));
  assert.deepStrictEqual(relayCalls.map((c) => c.attachments.map((a) => a.name)),
    [['Indicadores_clave_mision.pdf'], ['Indicadores_clave_Arauco.pdf']]);
  assert.ok(s2.some((l) => /ap\.uno@missionary\.org/.test(l)), 'the routing list names the AP');
  assert.ok(s2.some((l) => /zl\.arauco1@missionary\.org/.test(l)), 'and the ZL mailbox');
  assert.strictEqual(env.state.emails.length, 0, 'nothing through MailApp');
  assert.ok(!ss.getSheetByName('AGENT_RUN_LOG') ||
            ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues().length <= 1,
            'no run-log row for the missed-run check to trip on');
}

// 2. Job not run yet: step 2 says so and sends nothing.
{
  const { scope, relayCalls } = setup();
  scope.rehearseKiPdfsStep1();
  const s2 = scope.rehearseKiPdfsStep2(TO);
  assert.ok(s2.some((l) => /^FAIL -- requested, but the job/.test(l)), s2.join('\n'));
  assert.strictEqual(relayCalls.length, 0);
}

// 3. Relay never redeployed: the emails go without PDFs, and step 2 FAILs.
{
  const { env, scope, ss } = setup({ oldRelay: true });
  scope.rehearseKiPdfsStep1();
  playJob(env, ss, DOCS);
  const s2 = scope.rehearseKiPdfsStep2(TO);
  assert.ok(s2.some((l) => /redeploy CCSM_RelayReceiver/.test(l)), s2.join('\n'));
  assert.ok(s2.some((l) => /^FAIL -- see above/.test(l)));
}

console.log('ki rehearsal OK');
