// test_agent5b6.js — CCSM_Agent5B.gs (Friday encouragement qualifier) +
// CCSM_Agent6.gs (Friday encouragement Spanish email sender), tested as one
// chain: runAgent5B() saves qualifying areas to Script Properties (A5B_DATA),
// runAgent6() sends the Spanish encouragement email + writes
// ENCOURAGEMENT_HISTORY.
//
// Uses fixtures.js's REAL addNightlyRaw(env, ss, rows) contract (locked in by
// test_fixtures.js): each row is a flat object keyed by
// CCSM_NIGHTLY_QUESTIONS[].key plus {zone, area, timestamp?}.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs', 'CCSM_Agent5B.gs', 'CCSM_Agent6.gs'],
  env.globals
);
const ss = makeCcsmSpreadsheet(env, scope);

// Agent3 gates on these AGENT_CONFIG dates — the builder leaves both blank.
setConfig(env, ss, 'SYSTEM_START_DATE', '2026-07-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2026-07-01');

// GOALS_CONFIG starts completely empty (no header row) — every area falls
// back to a5b_loadDefaultGoals(), which reads GOAL_<metric_key> straight out
// of AGENT_CONFIG (lowercase — see CcsmData.gs CCSM_AGENT_CONFIG_ROWS GOAL_*
// rows). Weekly goal of 3 for new_people_found -> 75% threshold = 2.25.
setConfig(env, ss, 'GOAL_new_people_found', '3');

// Real Companion1_Email required — MISSION_ORG fixture rows ship with BOTH
// companion email columns intentionally blank (see CcsmData.gs comment), and
// Agent6 skips any qualifying area with no valid recipient email.
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
setMissionOrgField('Arauco 1', 'Companion1_Email', 'arauco1.companion@missionary.org');
setMissionOrgField('Arauco 2', 'Companion1_Email', 'arauco2.companion@missionary.org');

// ---------------------------------------------------------------------------
// Seed NIGHTLY_FORM_RAW for the CURRENT Mon-Thu window (computed the same way
// runAgent5B() computes it) so the qualification window always matches
// whatever real day the suite happens to run on.
// ---------------------------------------------------------------------------
const bounds = scope.a5b_getWeekBounds();

// "Arauco 1" — submits all 4 days (Mon-Thu) and beats 75% of its
// new_people_found goal (1+1+1+1 = 4 >= 2.25).
addNightlyRaw(env, ss, [
  { zone: 'Arauco', area: 'Arauco 1', report_date: bounds.monday, new_people_found: 1, effort: 'Todo' },
  { zone: 'Arauco', area: 'Arauco 1', report_date: bounds.tuesday, new_people_found: 1, effort: 'Todo' },
  { zone: 'Arauco', area: 'Arauco 1', report_date: bounds.wednesday, new_people_found: 1, effort: 'Todo' },
  { zone: 'Arauco', area: 'Arauco 1', report_date: bounds.thursday, new_people_found: 1, effort: 'Todo' },
  // "Arauco 2" — missing Tuesday, even though it also clears the goal on the
  // days it DID submit (1+1+1 = 3 >= 2.25) — must NOT qualify.
  { zone: 'Arauco', area: 'Arauco 2', report_date: bounds.monday, new_people_found: 1, effort: 'Todo' },
  { zone: 'Arauco', area: 'Arauco 2', report_date: bounds.wednesday, new_people_found: 1, effort: 'Todo' },
  { zone: 'Arauco', area: 'Arauco 2', report_date: bounds.thursday, new_people_found: 1, effort: 'Todo' },
]);
scope.runAgent3();

// ---------------------------------------------------------------------------
// Seed a FRIDAY_ENCOURAGEMENT MESSAGE_BANK row for new_people_found — a5b's
// message lookup tries the raw metric key first, so Metric='new_people_found'
// matches directly without needing the display-name fallback.
// ---------------------------------------------------------------------------
const messageBank = ss.getSheetByName('MESSAGE_BANK');
messageBank.appendRow([
  'FE-001', 'FRIDAY_ENCOURAGEMENT', 'new_people_found', '',
  '¡Su arduo trabajo está dando fruto!',
  '¡Felicidades, compañía! Su dedicación a encontrar nuevas personas esta semana ' +
    'ha sido un verdadero ejemplo de fe en acción. Sigan adelante con ese mismo espíritu.',
  'Capítulo 1 — El Ministerio de la Salvación',
  'Cómo compartir el evangelio con amor',
  'Doctrina y Convenios 4:2',
  'Por tanto, oh vosotros los que os embarcáis en el servicio de Dios, mirad que le sirváis con todo vuestro corazón.',
  'TRUE',
]);

// ---------------------------------------------------------------------------
// Run the chain
// ---------------------------------------------------------------------------
scope.runAgent5B();
scope.runAgent6();

// ---------------------------------------------------------------------------
// Assertions
// ---------------------------------------------------------------------------
const allEmails = env.state.emails;
assert.ok(allEmails.length > 0, 'expected at least one email to be sent');

const encouragementEmails = allEmails.filter((e) => /¡Buen trabajo/.test(e.subject));
assert.strictEqual(encouragementEmails.length, 1, 'expected exactly one Spanish encouragement email');

const email = encouragementEmails[0];
assert.strictEqual(email.to, 'CCSM.PMG.Compass@gmail.com', 'TEST_MODE must redirect to the test inbox');
assert.ok(email.subject.includes('¡Buen trabajo'), 'subject must contain ¡Buen trabajo: ' + email.subject);
assert.ok(email.subject.includes('Arauco 1'), 'subject must name the qualifying area: ' + email.subject);

const body = email.htmlBody || email.body || '';
assert.ok(/Felicitaciones/.test(body), 'body must contain the Spanish congratulatory line');
assert.ok(/75%|1[0-9][0-9]%|8[0-9]%|9[0-9]%/.test(body) || /%/.test(body), 'body must show a percentage of goal');
assert.ok(body.indexOf('Su arduo trabajo está dando fruto') >= 0, 'body must include the MESSAGE_BANK message text (never generated)');
assert.ok(body.indexOf('PMG Compass') >= 0 && body.indexOf('Chile Concepción South Mission') >= 0,
  'footer must be "PMG Compass — " + getMissionName()');

// Non-qualifying area ("Arauco 2", missing Tuesday) must get NOTHING.
assert.ok(!/Arauco 2/.test(body), 'non-qualifying area must not appear in the encouragement email');
assert.ok(
  !allEmails.some((e) => (e.htmlBody || e.body || '').indexOf('arauco2.companion@missionary.org') >= 0),
  'non-qualifying area\'s companion email must never appear as a recipient anywhere'
);

// ENCOURAGEMENT_HISTORY gained exactly one row for "Arauco 1".
const history = ss.getSheetByName('ENCOURAGEMENT_HISTORY').getDataRange().getValues();
assert.ok(history.length >= 2, 'ENCOURAGEMENT_HISTORY must have gained a data row');
const hh = history[0];
const areaIdx = hh.indexOf('Area');
assert.ok(areaIdx >= 0, 'ENCOURAGEMENT_HISTORY header must include Area');
assert.ok(history.some((r) => r[areaIdx] === 'Arauco 1'), 'expected an Arauco 1 row in ENCOURAGEMENT_HISTORY');
assert.ok(!history.some((r) => r[areaIdx] === 'Arauco 2'), 'Arauco 2 must not appear in ENCOURAGEMENT_HISTORY');

// ---------------------------------------------------------------------------
// No Provo/English residue + no redeclared ccsmEffortScore
// ---------------------------------------------------------------------------
const src5b = require('fs').readFileSync('CCSM_Agent5B.gs', 'utf8');
const src6 = require('fs').readFileSync('CCSM_Agent6.gs', 'utf8');
[src5b, src6].forEach((src) => {
  assert.ok(!/Utah Provo/i.test(src));
  assert.ok(!/America\/Denver/.test(src));
  assert.ok(!/function ccsmEffortScore/.test(src));
});

console.log('agent5b6 OK');
