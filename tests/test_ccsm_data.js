const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const assert = require('assert');
const g = makeGasEnv().globals;
const d = loadGs(['CcsmData.gs'], g);

// zones match the live form builders exactly
const wf = loadGs(['WeeklyReportForm.gs'], makeGasEnv().globals);
assert.deepStrictEqual(d.CCSM_ZONES, wf.ZONES, 'CCSM_ZONES must equal the form ZONES verbatim');

// nightly questions: 23 entries, exactly one DATE / one YESNO / one CHOICE / 20 NUMBER
const byType = t => d.CCSM_NIGHTLY_QUESTIONS.filter(q => q.type === t).length;
assert.strictEqual(d.CCSM_NIGHTLY_QUESTIONS.length, 23);
assert.deepStrictEqual([byType('DATE'), byType('YESNO'), byType('CHOICE'), byType('NUMBER')], [1, 1, 1, 20]);

// nightly headers match the ES daily form titles verbatim
const df = loadGs(['DailyReportForm_ES.gs'], makeGasEnv().globals);
const formTitles = df.QUESTIONS.map(q => q.title);
d.CCSM_NIGHTLY_QUESTIONS.forEach(q =>
  assert.ok(formTitles.includes(q.headerEs), 'missing in ES form: ' + q.headerEs));

// weekly: 3 intro + 14 KI entries; every KI base has _real and _meta
assert.strictEqual(d.CCSM_WEEKLY_QUESTIONS.length, 17);
const kis = d.CCSM_WEEKLY_QUESTIONS.filter(q => q.key.startsWith('ki_'));
assert.strictEqual(kis.length, 14);
kis.forEach(q => assert.ok(/_(real|meta)$/.test(q.key), q.key));
kis.forEach(q => assert.ok(/ \((Real|Meta)\)$/.test(q.headerEs), q.headerEs));

// mission org: headers + ~101 rows, all areas in zones, emails blank
assert.deepStrictEqual(d.CCSM_MISSION_ORG_HEADERS,
  ['Area_Code','Area_Name','Zone','District','Companion1_Name','Companion1_Email',
   'Companion2_Name','Companion2_Email','Is_DL','Is_ZL','Is_STL','Is_AP','Is_MP','Active']);
const allAreas = Object.values(d.CCSM_ZONES).flat();
d.CCSM_MISSION_ORG_ROWS.forEach(r => {
  assert.ok(allAreas.includes(r[1]), 'org area not in ZONES: ' + r[1]);
  assert.strictEqual(r[5], ''); assert.strictEqual(r[7], '');   // emails blank
  assert.strictEqual(r[13], 'TRUE');
});
assert.ok(d.CCSM_MISSION_ORG_ROWS.length >= 98 && d.CCSM_MISSION_ORG_ROWS.length <= 104);
// leadership flags present: at least 2 AP=false? APs live in an office area — expect >=15 DL, >=8 ZL rows
assert.ok(d.CCSM_MISSION_ORG_ROWS.filter(r => r[8] === 'TRUE').length >= 15, 'DL flags missing');

// config rows include the required keys with required defaults
const cfg = Object.fromEntries(d.CCSM_AGENT_CONFIG_ROWS);
assert.strictEqual(cfg.TEST_MODE, 'TRUE');
assert.strictEqual(cfg.MISSION_TIMEZONE, 'America/Santiago');
assert.strictEqual(cfg.MISSION_LANGUAGE, 'ES');
assert.strictEqual(cfg.MISSION_NAME, 'Chile Concepción South Mission');
assert.ok('GOAL_new_people_found' in cfg && 'GOAL_baptismal_invitations' in cfg);
console.log('ccsm data OK');
