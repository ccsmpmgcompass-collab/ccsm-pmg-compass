// test_relay_attachments.js — the weekly KI PDFs ride on the letter through
// the relay (PLAN-2026-10-10-ki-autosend.md K7).
//
// sendEmail(..., { attachments }) sends them to the relay as base64; the relay
// decodes them, attaches them, and replies with how many it attached. A relay
// deployed before this change ignores the field: the email still goes once,
// and the sender reports 0 attached instead of sending it again.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, setConfig } = require('./fixtures');

const GS = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs'];
const PDF = [37, 80, 68, 70, 45, 49, 46, 55, 0, 255, 128, 10];   // "%PDF-1.7" + binary

function setup(urlFetch, relay) {
  const env = makeGasEnv({ urlFetch });
  const scope = loadGs(GS, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'TEST_MODE', 'FALSE');
  if (relay) {
    setConfig(env, ss, 'RELAY_2_URL', 'https://script.google.com/macros/s/AKfy/exec');
    setConfig(env, ss, 'RELAY_SECRET', 'shhh');
  }
  return { env, scope };
}

function pdfBlob(env, name) {
  return env.globals.Utilities.newBlob(PDF, 'application/pdf', name);
}

function reply(obj) {
  return { getContentText: () => JSON.stringify(obj) };
}

// 1. No relay: the main account attaches the blobs itself.
{
  const { env, scope } = setup(null, false);
  const out = scope.sendEmail('zl@missionary.org', 'S', '<p>b</p>', 'Agent1C',
    { attachments: [pdfBlob(env, 'Indicadores_clave_Angol_28sep-4oct.pdf')] });
  assert.strictEqual(out.attached, 1);
  assert.strictEqual(env.state.emails.length, 1);
  const att = env.state.emails[0].attachments;
  assert.strictEqual(att.length, 1);
  assert.strictEqual(att[0].getName(), 'Indicadores_clave_Angol_28sep-4oct.pdf');
  assert.deepStrictEqual(att[0].getBytes(), PDF);
}

// 2. Without attachments nothing changes: no attachments key at all.
{
  const { env, scope } = setup(null, false);
  const out = scope.sendEmail('a@missionary.org', 'S', '<p>b</p>', 'Agent1C');
  assert.strictEqual(out.attached, 0);
  assert.ok(!('attachments' in env.state.emails[0]));
}

// 3. The updated relay: the sender ships base64, the relay project decodes it,
//    and the count comes back. Runs the REAL relay doPost on the payload.
{
  let relayEnv;
  const relayFetch = (url, params) => {
    relayEnv = makeGasEnv({});
    relayEnv.state.props.script = { RELAY_SECRET: 'shhh' };
    const relay = loadGs(['CCSM_RelayReceiver.gs'], Object.assign({}, relayEnv.globals, {
      ContentService: {
        createTextOutput(t) { return { t, setMimeType() { return this; } }; },
        MimeType: { JSON: 'json' },
      },
    }));
    const out = relay.doPost({ postData: { contents: params.payload } });
    return { getContentText: () => out.t };
  };
  const { env, scope } = setup(relayFetch, true);
  const out = scope.sendEmail('ap@missionary.org', 'S', '<p>b</p>', 'Agent1C', {
    attachments: [pdfBlob(env, 'Indicadores_clave_mision_28sep-4oct.pdf'),
                  pdfBlob(env, 'Indicadores_clave_Angol_28sep-4oct.pdf')],
  });
  assert.strictEqual(out.attached, 2);
  assert.strictEqual(env.state.emails.length, 0, 'the main account must not send it too');
  const sent = relayEnv.state.emails;
  assert.strictEqual(sent.length, 1);
  assert.deepStrictEqual(sent[0].attachments.map((b) => b.getName()),
    ['Indicadores_clave_mision_28sep-4oct.pdf', 'Indicadores_clave_Angol_28sep-4oct.pdf']);
  assert.deepStrictEqual(sent[0].attachments[0].getBytes(), PDF);
  assert.strictEqual(sent[0].attachments[0].getContentType(), 'application/pdf');
}

// 4. An outdated relay (replies success, no count): sent ONCE, 0 attached, and
//    the log says to redeploy.
{
  let calls = 0;
  const { env, scope } = setup(() => { calls++; return reply({ success: true }); }, true);
  const out = scope.sendEmail('ap@missionary.org', 'S', '<p>b</p>', 'Agent1C',
    { attachments: [pdfBlob(env, 'x.pdf')] });
  assert.strictEqual(out.attached, 0);
  assert.strictEqual(calls, 1);
  assert.strictEqual(env.state.emails.length, 0, 'no second copy from the main account');
  assert.ok(env.state.logs.some((l) => /redeploy CCSM_RelayReceiver/.test(l)),
    'the log must say the relay needs redeploying');
}

// 5. A relay that rejects falls back to the main account, attachments included.
{
  const { env, scope } = setup(() => reply({ success: false, error: 'Invalid secret.' }), true);
  const out = scope.sendEmail('ap@missionary.org', 'S', '<p>b</p>', 'Agent1C',
    { attachments: [pdfBlob(env, 'x.pdf')] });
  assert.strictEqual(out.attached, 1);
  assert.strictEqual(env.state.emails[0].attachments.length, 1);
}

console.log('relay attachments OK');
