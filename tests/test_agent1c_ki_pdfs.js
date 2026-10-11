// test_agent1c_ki_pdfs.js — the weekly KI PDFs ride on the weekly letter
// (PLAN-2026-10-10-ki-autosend.md K1, K2, K6).
//
// Runs the real 1A -> 1B -> 1C chain. Agent1A writes the REQUEST row; the test
// plays the Monday job by adding PDF rows to KI_PDF_OUTBOX; Agent1C must attach
// the mission document + every zone's to the APs, the zone's own to its ZL,
// nothing to anyone else — and, when the PDFs are late, wait (without spending
// Gemini calls) and finally send without them, saying so.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');

const GS = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
  'CCSM_Agent3.gs', 'CCSM_Agent5A.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs'];

const geminiEnvelope = JSON.stringify({
  candidates: [{ content: { parts: [{ text: JSON.stringify({ Arauco: 'Narrativa de prueba.' }) }] } }],
});

function chain(opts) {
  opts = opts || {};
  const calls = { gemini: 0 };
  const env = makeGasEnv({
    urlFetch: () => { calls.gemini++; return { getResponseCode: () => 200, getContentText: () => geminiEnvelope }; },
  });
  const scope = loadGs(GS, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TEST_MODE', 'FALSE');
  addNightlyRaw(env, ss, []);

  // Arauco 1 is Arauco's ZL area in the fixture roster; Arauco 2 is not a leader.
  const org = ss.getSheetByName('MISSION_ORG');
  const data = org.getDataRange().getValues();
  const h = data[0];
  for (let i = 1; i < data.length; i++) {
    const area = data[i][h.indexOf('Area_Name')];
    if (area === 'Arauco 1') org.getRange(i + 1, h.indexOf('Companion1_Email') + 1).setValue('zl.arauco1@missionary.org');
    if (area === 'Arauco 2') org.getRange(i + 1, h.indexOf('Companion1_Email') + 1).setValue('arauco2@missionary.org');
  }
  ss.insertSheet('MISSION_LEADERSHIP').getRange(1, 1, 3, 5).setValues([
    ['Name', 'Email', 'Role', 'Active', 'Notes'],
    ['Presidente', 'presidente@churchofjesuschrist.org', 'president', 'TRUE', ''],
    ['AP Uno', 'ap.uno@missionary.org', 'assistant', 'TRUE', ''],
  ]);

  if (!opts.noJob) ss.insertSheet('KI_PDF_OUTBOX');   // the Monday job creates it
  scope.runAgent1A();
  scope.runAgent1B();
  return { env, scope, ss, calls };
}

function pdfBytes(tag) {
  return Array.from(Buffer.from('%PDF-1.4 ' + tag, 'utf8'));
}

function addPdfRows(env, ss, docs) {
  const sheet = ss.getSheetByName('KI_PDF_OUTBOX');
  const req = sheet.getDataRange().getValues()[1];
  const U = env.globals.Utilities;
  docs.forEach(([scope, name, pages]) => {
    sheet.appendRow(['PDF', req[1], scope, name, req[4], String(pages), '1', U.base64Encode(pdfBytes(scope))]);
  });
  return req;
}

function lastRun(ss) {
  const log = ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
  return log[log.length - 1];
}

const byTo = (env, to) => env.state.emails.find((e) => e.to === to);
const names = (e) => (e.attachments || []).map((b) => b.getName());

// ── 1. PDFs ready: each recipient gets exactly their set. ─────────────────────
{
  const { env, scope, ss } = chain();
  addPdfRows(env, ss, [
    ['MISSION', 'Indicadores_clave_mision_28sep-4oct.pdf', 11],
    ['Arauco', 'Indicadores_clave_Arauco_28sep-4oct.pdf', 3],
    ['Angol', 'Indicadores_clave_Angol_28sep-4oct.pdf', 3],
  ]);
  scope.runAgent1C();

  const ap = byTo(env, 'ap.uno@missionary.org');
  assert.deepStrictEqual(names(ap), ['Indicadores_clave_mision_28sep-4oct.pdf'],
    'the AP gets the mission document only: it already holds every zone');
  assert.deepStrictEqual(ap.attachments[0].getBytes(), pdfBytes('MISSION'), 'the bytes survive the outbox');
  assert.ok(/Indicadores clave por sector — adjuntos/.test(ap.htmlBody), 'the AP letter says what is attached');
  assert.ok(/el documento de la misión<\/b> \(11 páginas: el total de la misión/.test(ap.htmlBody));

  const zl = byTo(env, 'zl.arauco1@missionary.org');
  assert.deepStrictEqual(names(zl), ['Indicadores_clave_Arauco_28sep-4oct.pdf'], 'the ZL gets only their zone\'s');
  assert.ok(/La clasificación de su zona/.test(zl.htmlBody));

  const mp = byTo(env, 'presidente@churchofjesuschrist.org');
  assert.ok(mp, 'the President still gets the letter');
  assert.deepStrictEqual(names(mp), [], 'the President gets no PDFs (not asked for)');
  assert.ok(!/adjuntos/.test(mp.htmlBody), 'and no note about them');

  const comp = byTo(env, 'arauco2@missionary.org');
  assert.deepStrictEqual(names(comp), [], 'a companionship gets no PDFs');
  assert.ok(!/adjuntos/.test(comp.htmlBody));

  const run = lastRun(ss);
  assert.strictEqual(run[2], 'SUCCESS', 'run status: ' + run[2] + ' ' + run[7]);
  assert.ok(/KI PDFs attached: 2/.test(run[7]), 'the run log counts the attachments: ' + run[7]);
}

// ── 2. PDFs late: wait (no Gemini), then send without them and say so. ────────
{
  const { env, scope, ss, calls } = chain();
  const before = calls.gemini;
  scope.runAgent1C();
  assert.strictEqual(env.state.emails.length, 0, 'no letter goes while waiting for the PDFs');
  assert.strictEqual(calls.gemini, before, 'waiting spends no Gemini call');
  assert.strictEqual(lastRun(ss)[2], 'WAITING');
  const key = Object.keys(env.state.props.script).find((k) => k.indexOf('A1C_KI_PDF_WAIT_') === 0);
  assert.strictEqual(env.state.props.script[key], '1');

  env.state.props.script[key] = String(scope.A1C_KI_PDF_MAX_WAITS);   // the last retry
  scope.runAgent1C();
  assert.ok(env.state.emails.length > 0, 'after the last wait the letters go anyway');
  assert.deepStrictEqual(names(byTo(env, 'ap.uno@missionary.org')), [], 'without the PDFs');
  const run = lastRun(ss);
  assert.strictEqual(run[2], 'ERROR');
  assert.ok(/went WITHOUT them/.test(run[7]), run[7]);
  assert.ok(!(key in env.state.props.script), 'the wait counter is cleared');
}

// ── 3. No job set up (no KI_PDF_OUTBOX): no request, no wait, no PDFs. ────────
{
  const { env, scope, ss } = chain({ noJob: true });
  scope.runAgent1C();
  assert.ok(env.state.emails.length > 0, 'letters go at once');
  assert.deepStrictEqual(names(byTo(env, 'ap.uno@missionary.org')), []);
  assert.notStrictEqual(lastRun(ss)[2], 'WAITING');
}

console.log('agent1c ki pdfs OK');
