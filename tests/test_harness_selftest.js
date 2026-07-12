const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const assert = require('assert');

const env = makeGasEnv();
const g = env.globals;

// spreadsheet round-trip
const ss = g.SpreadsheetApp.create('T');
const sh = ss.insertSheet('TAB1');
sh.appendRow(['A', 'B']);
sh.getRange(2, 1, 1, 2).setValues([[1, 2]]);
assert.strictEqual(sh.getLastRow(), 2);
assert.deepStrictEqual(sh.getDataRange().getValues(), [['A', 'B'], [1, 2]]);
// openById returns fresh true state
assert.deepStrictEqual(
  g.SpreadsheetApp.openById(ss.getId()).getSheetByName('TAB1').getDataRange().getValues(),
  [['A', 'B'], [1, 2]]);
// email capture
g.MailApp.sendEmail({ to: 'x@y.z', subject: 's', htmlBody: '<b>hi</b>' });
assert.strictEqual(env.state.emails.length, 1);
// formatDate honors tz + pattern
const d = new Date('2026-07-11T03:00:00Z'); // 2026-07-10 23:00 in Santiago (UTC-4)
assert.strictEqual(g.Utilities.formatDate(d, 'America/Santiago', 'yyyy-MM-dd'), '2026-07-10');
// formatDate tokenizer regression: chained-.replace() substitution used to
// corrupt single-letter tokens (h/a/d) that landed INSIDE the weekday/month
// names it had just inserted (e.g. "Thursday, July 9" -> "T2ursdPMy, July
// 9"). 2026-07-09T15:00:00Z is 2026-07-09 11:00 in Santiago — a Thursday.
const thu = new Date('2026-07-09T15:00:00Z');
assert.strictEqual(g.Utilities.formatDate(thu, 'America/Santiago', 'EEEE, MMMM d'), 'Thursday, July 9');
// loadGs evaluates a .gs snippet
const fs = require('fs'); const os = require('os'); const path = require('path');
const tmp = path.join(os.tmpdir(), 'snippet.gs');
fs.writeFileSync(tmp, 'function addOne(n) { return n + 1; }');
const scope = loadGs([tmp], g);
assert.strictEqual(scope.addOne(41), 42);
console.log('harness selftest OK');

const scope2 = loadGs(['C:/Users/2011794-MTS/Desktop/PMG-Compass/docs/Agent3.gs'], makeGasEnv().globals);
assert.strictEqual(typeof scope2.a3_normHeader, 'function');
assert.strictEqual(scope2.a3_normHeader("  What's  UP "), 'whats up');
console.log('provo smoke-load OK');
