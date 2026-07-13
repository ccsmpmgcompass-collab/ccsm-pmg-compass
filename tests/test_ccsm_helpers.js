const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs'], env.globals);
makeCcsmSpreadsheet(env, scope);

assert.strictEqual(scope.getConfig('MISSION_TIMEZONE'), 'America/Santiago');
assert.strictEqual(scope.getMissionName(), 'Chile Concepción South Mission');

// TEST_MODE email redirect
scope.sendEmail('real.missionary@missionary.org', 'Asunto', '<p>hola</p>', 'TestAgent');
assert.strictEqual(env.state.emails.length, 1);
assert.strictEqual(env.state.emails[0].to, 'CCSM.PMG.Compass@gmail.com'); // TEST_MODE redirect
// sendEmail's TEST_MODE branch (resolveSubject, mirroring Provo AgentTestMode.gs)
// prepends '[TEST] ' to the subject line.
assert.strictEqual(env.state.emails[0].subject, '[TEST] Asunto');

// ccsmEffortScore() — Todo=3, La mayor parte=2, Algo=1
assert.strictEqual(scope.ccsmEffortScore('Todo'), 3);
assert.strictEqual(scope.ccsmEffortScore('La mayor parte'), 2);
assert.strictEqual(scope.ccsmEffortScore('Algo'), 1);

// no Provo residue
const src = require('fs').readFileSync('CCSM_Helpers.gs', 'utf8');
assert.ok(!/Utah Provo/i.test(src));
assert.ok(!/America\/Denver/.test(src));
console.log('helpers OK');
