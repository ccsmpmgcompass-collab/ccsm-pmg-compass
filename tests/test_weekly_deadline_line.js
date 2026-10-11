// test_weekly_deadline_line.js — Monday's weekly-form reminder says the
// deadline out loud (letter redesign R1, PLAN-2026-10-10-ki-autosend.md K8):
// a form sent after the letter's Monday-night cutoff waits for next week.
// Tuesday's second reminder does not repeat it — that letter has gone.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');

const env = makeGasEnv();
const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs',
  'CCSM_AgentEscalation.gs'], env.globals);
makeCcsmSpreadsheet(env, scope);

const DEADLINE = 'Envíen su informe semanal antes del lunes a las 21:00 para ver sus ' +
  'resultados en el correo de esta semana.';
const first = scope.ae_buildWeeklyReminderBody('Arauco 1', '2026-10-04', 1, 'https://forms.example/w');
const second = scope.ae_buildWeeklyReminderBody('Arauco 1', '2026-10-04', 2, 'https://forms.example/w');
assert.ok(first.includes(DEADLINE), 'Monday\'s reminder states the deadline');
assert.ok(!second.includes(DEADLINE), 'Tuesday\'s reminder does not');
assert.ok(first.includes('https://forms.example/w'), 'the form button is still there');

console.log('weekly deadline line OK');
