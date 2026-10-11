// test_agent1a_ki_request.js — R1 and the KI PDF request
// (PLAN-2026-10-10-ki-autosend.md K3, K4, K5).
//
// runAgent1A must (a) rebuild WEEKLY_KI from WEEKLY_FORM_RAW before reading
// it, so a form sent after Agent5A's noon run is in the letter; (b) count a
// form dated after the graded week as the graded week when the area has no
// row for it; (c) write KI_PDF_OUTBOX = header + one REQUEST row (week end,
// cutoff) as plain text, for the Monday job.
//
// Agent1A computes its week from the real clock (most recent Sunday), so the
// forms are dated relative to today, like test_agent1ab.js.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, addWeeklyRaw, setConfig } = require('./fixtures');

const env = makeGasEnv();
const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs',
  'CCSM_Agent5A.gs', 'CCSM_Agent1A.gs'], env.globals);
const ss = makeCcsmSpreadsheet(env, scope);
setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');
addNightlyRaw(env, ss, []);   // Agent1A reads the nightly tab too; no nights needed here

function ymd(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' +
    String(d.getDate()).padStart(2, '0');
}
const today = new Date();
today.setHours(0, 0, 0, 0);
const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
const weekEnd = ymd(sunday);
const nextSunday = ymd(new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() + 7));
const prevSunday = ymd(new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - 7));

function form(area, date, real, meta) {
  const row = { zone: 'Arauco', area, report_date: date, leader_call: 'Sí', correlation_meeting: 'No' };
  ['ki_new_people', 'ki_member_lessons', 'ki_friends_sacrament', 'ki_friends_first_week',
    'ki_baptismal_date', 'ki_baptized_confirmed', 'ki_rc_at_church'].forEach((k) => {
    row[k + '_real'] = real;
    row[k + '_meta'] = meta;
  });
  return row;
}

addWeeklyRaw(env, ss, [
  form('Arauco 1', prevSunday, 2, 5),   // last week: the metas this week is graded on
  form('Arauco 1', weekEnd, 4, 6),      // this week, on time
  form('Arauco 2', nextSunday, 3, 7),   // this week's form, dated next Sunday by mistake
]);
// WEEKLY_KI as Agent5A left it at noon: empty. The letter must not care.
assert.strictEqual(ss.getSheetByName('WEEKLY_KI').getLastRow() <= 1, true);

scope.runAgent1A();

// (a) WEEKLY_KI was rebuilt from the raw forms.
const kiRows = ss.getSheetByName('WEEKLY_KI').getDataRange().getValues();
assert.strictEqual(kiRows.length - 1, 3, 'WEEKLY_KI must hold the three forms');

const a1a = scope.loadTempData('A1A_DATA');
const ki = (area) => a1a.areas[area].ki;
assert.strictEqual(ki('Arauco 1').length, 7, 'Arauco 1 filed this week');
assert.strictEqual(ki('Arauco 1')[0].real, 4);
assert.strictEqual(a1a.areas['Arauco 1'].kiMetaPrev.ki_new_people, 5,
  'graded against LAST week\'s metas, as before');

// (b) The slip counts as this week.
assert.strictEqual(ki('Arauco 2').length, 7, 'a form dated next Sunday counts as this week');
assert.strictEqual(ki('Arauco 2')[0].real, 3);
assert.deepStrictEqual(ki('Cañete 1'), [], 'an area with no form still reads as no form');

// (c) The REQUEST row.
const outbox = ss.getSheetByName('KI_PDF_OUTBOX');
assert.ok(outbox, 'KI_PDF_OUTBOX is created on the first run');
const grid = outbox.getDataRange().getValues();
assert.deepStrictEqual(grid[0], ['Kind', 'Week_End', 'Scope', 'File_Name', 'Stamp', 'Pages', 'Parts']);
assert.strictEqual(grid.length, 2, 'header + one REQUEST row');
assert.strictEqual(grid[1][0], 'REQUEST');
assert.strictEqual(grid[1][1], weekEnd);
assert.ok(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(grid[1][4]), 'cutoff as yyyy-MM-dd HH:mm:ss');
const book = Object.values(env.state.spreadsheets).find((s) => s.name === 'COMPASS_CCSM');
const formats = book.sheets.KI_PDF_OUTBOX.numberFormats || {};
assert.strictEqual(formats['2,2'], '@', 'the week end is written as text');
assert.strictEqual(formats['2,5'], '@', 'the cutoff is written as text');

// A second run replaces the request instead of stacking it.
scope.runAgent1A();
assert.strictEqual(ss.getSheetByName('KI_PDF_OUTBOX').getDataRange().getValues().length, 2);

console.log('agent1a ki request OK');
