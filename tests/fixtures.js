// fixtures.js — shared test-fixture factory for CCSM agent tests.
//
// Every later agent test builds its in-memory COMPASS_CCSM spreadsheet and
// raw form-response rows through this module, so the raw-form column layout
// modeled here MUST match what the real Google Forms (DailyReportForm_ES.gs /
// WeeklyReportForm_ES.gs) actually produce: a single response sheet with one
// zone-selector column plus one repeated column-block PER ZONE (Google Forms'
// "section per zone with branching" produces one flat response row per
// submission, with only the submitter's zone-section columns filled in and
// every other zone's columns blank).
//
// The zone/question data itself is NOT duplicated here — it is loaded once,
// directly from CcsmData.gs (the single source of truth also used by
// BuildCcsmSheet.gs and every CCSM_*.gs agent), so this file can never drift
// out of sync with the real form headers.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');

// CcsmData.gs is pure data (no SpreadsheetApp/etc. calls at load time), so it
// is safe to load once into a throwaway scope, independent of any test's own
// env/scope, purely to read CCSM_ZONES / CCSM_NIGHTLY_QUESTIONS / etc.
const _data = loadGs(['CcsmData.gs'], makeGasEnv().globals);

const ZONE_NAMES = Object.keys(_data.CCSM_ZONES);

// ---------------------------------------------------------------------------
// makeCcsmSpreadsheet — builds the in-memory COMPASS_CCSM sheet via the real
// buildCcsmSheet() builder (loaded into `scope` by the caller) and wires it up
// as SpreadsheetApp.getActiveSpreadsheet(), which CCSM_Helpers.gs's
// getSpreadsheet() (and therefore getConfig/getTab/etc.) depends on.
//
// CRITICAL WIRING FACT (from Task 1's review): the harness's
// SpreadsheetApp.getActiveSpreadsheet() reads state.activeSpreadsheetId, but
// nothing sets that by default — buildCcsmSheet() calls SpreadsheetApp.create()
// internally and never marks its result "active". Without the assignment
// below, getSpreadsheet() returns null and every CCSM_Helpers.gs function
// that depends on it throws or silently no-ops.
// ---------------------------------------------------------------------------
function makeCcsmSpreadsheet(env, scope) {
  scope.buildCcsmSheet();

  const id = Object.keys(env.state.spreadsheets).find(
    (k) => env.state.spreadsheets[k].name === 'COMPASS_CCSM'
  );
  if (!id) {
    throw new Error('makeCcsmSpreadsheet: no COMPASS_CCSM spreadsheet found after buildCcsmSheet()');
  }
  env.state.activeSpreadsheetId = id;
  return env.globals.SpreadsheetApp.getActiveSpreadsheet();
}

// ---------------------------------------------------------------------------
// setConfig — sets (or overwrites) a single AGENT_CONFIG key/value pair.
// Used by later tests to fill blanks the builder leaves empty
// (SYSTEM_START_DATE, TRANSFER_START_DATE, form links, GOAL_* rows, ...).
// ---------------------------------------------------------------------------
function setConfig(env, ss, key, value) {
  const sheet = ss.getSheetByName('AGENT_CONFIG');
  if (!sheet) throw new Error('setConfig: AGENT_CONFIG tab not found');
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() === key) {
      sheet.getRange(i + 1, 2).setValue(value);
      return;
    }
  }
  sheet.appendRow([key, value]);
}

// ---------------------------------------------------------------------------
// NIGHTLY (daily) raw layout
//
// Real form order (DailyReportForm_ES.gs): zone selector, then per zone
// section: area dropdown, then the QUESTIONS[] array in order — date, yesno
// (exchanges), 20 numeric metrics, effort. CCSM_NIGHTLY_QUESTIONS (CcsmData.gs)
// is copied verbatim in that same order (report_date, exchanges, ...,
// effort), so one zone-section's headers are simply:
//   [areaCol].concat(CCSM_NIGHTLY_QUESTIONS.map(q => q.headerEs))
// ---------------------------------------------------------------------------
function nightlySectionHeaders() {
  return [_data.CCSM_FORM_STRUCTURAL.areaCol].concat(
    _data.CCSM_NIGHTLY_QUESTIONS.map((q) => q.headerEs)
  );
}

function nightlyHeaders() {
  const headers = ['Marca temporal', _data.CCSM_FORM_STRUCTURAL.zoneCol];
  const section = nightlySectionHeaders();
  ZONE_NAMES.forEach(() => headers.push(...section));
  return headers;
}

const NIGHTLY_SECTION_WIDTH = 1 + _data.CCSM_NIGHTLY_QUESTIONS.length; // area + 23 questions = 24

// addNightlyRaw(env, ss, rows) — creates (or reuses) NIGHTLY_FORM_RAW with the
// real multi-section header layout, then appends one row per entry in `rows`.
// Each row object: { timestamp?, zone, area, <question key>: value, ... }
// using CCSM_NIGHTLY_QUESTIONS[].key as property names (report_date,
// exchanges, roleplays, ..., effort). Only the submitter's zone-section
// columns are filled; every other zone's columns are left blank ('') —
// matching what Google Forms' branching actually produces.
function addNightlyRaw(env, ss, rows) {
  const headers = nightlyHeaders();
  let sheet = ss.getSheetByName('NIGHTLY_FORM_RAW');
  if (!sheet) sheet = ss.insertSheet('NIGHTLY_FORM_RAW');
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }

  rows.forEach((row) => {
    const zoneIdx = ZONE_NAMES.indexOf(row.zone);
    if (zoneIdx === -1) {
      throw new Error('addNightlyRaw: unknown zone "' + row.zone + '"');
    }
    const rowArr = new Array(headers.length).fill('');
    rowArr[0] = row.timestamp || new Date();
    rowArr[1] = row.zone;

    const base = 2 + zoneIdx * NIGHTLY_SECTION_WIDTH; // 0-indexed start of this zone's block
    rowArr[base] = row.area;
    _data.CCSM_NIGHTLY_QUESTIONS.forEach((q, i) => {
      const val = row[q.key];
      rowArr[base + 1 + i] = val !== undefined ? val : '';
    });

    sheet.appendRow(rowArr);
  });

  return sheet;
}

// ---------------------------------------------------------------------------
// WEEKLY raw layout
//
// Real form order (WeeklyReportForm_ES.gs): zone selector, then per zone
// section: area dropdown, 3 intro questions (date, 2 yes/no), then a
// "(Real)" section with all 7 key indicators, then a "(Meta)" section with
// all 7 key indicators (addKeyIndicatorGroup_ is called once per suffix, so
// the two groups of 7 are NOT interleaved). CCSM_WEEKLY_QUESTIONS interleaves
// real/meta pairs per-indicator, so the real/meta groups are reconstructed
// here by filtering on the _real / _meta key suffix (both filters preserve
// the original per-indicator order, matching KEY_INDICATORS order).
// ---------------------------------------------------------------------------
function weeklySectionQuestions() {
  const intro = _data.CCSM_WEEKLY_QUESTIONS.slice(0, 3); // report_date, leader_call, correlation_meeting
  const reals = _data.CCSM_WEEKLY_QUESTIONS.filter((q) => q.key.endsWith('_real'));
  const metas = _data.CCSM_WEEKLY_QUESTIONS.filter((q) => q.key.endsWith('_meta'));
  return intro.concat(reals, metas);
}

function weeklySectionHeaders() {
  return [_data.CCSM_FORM_STRUCTURAL.areaCol].concat(
    weeklySectionQuestions().map((q) => q.headerEs)
  );
}

function weeklyHeaders() {
  const headers = ['Marca temporal', _data.CCSM_FORM_STRUCTURAL.zoneCol];
  const section = weeklySectionHeaders();
  ZONE_NAMES.forEach(() => headers.push(...section));
  return headers;
}

const WEEKLY_SECTION_QUESTIONS = weeklySectionQuestions();
const WEEKLY_SECTION_WIDTH = 1 + WEEKLY_SECTION_QUESTIONS.length; // area + 3 intro + 7 real + 7 meta = 18

// addWeeklyRaw(env, ss, rows) — mirrors addNightlyRaw for WEEKLY_FORM_RAW.
// Each row object: { timestamp?, zone, area, report_date, leader_call,
// correlation_meeting, ki_*_real, ki_*_meta, ... } using
// CCSM_WEEKLY_QUESTIONS[].key as property names.
function addWeeklyRaw(env, ss, rows) {
  const headers = weeklyHeaders();
  let sheet = ss.getSheetByName('WEEKLY_FORM_RAW');
  if (!sheet) sheet = ss.insertSheet('WEEKLY_FORM_RAW');
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }

  rows.forEach((row) => {
    const zoneIdx = ZONE_NAMES.indexOf(row.zone);
    if (zoneIdx === -1) {
      throw new Error('addWeeklyRaw: unknown zone "' + row.zone + '"');
    }
    const rowArr = new Array(headers.length).fill('');
    rowArr[0] = row.timestamp || new Date();
    rowArr[1] = row.zone;

    const base = 2 + zoneIdx * WEEKLY_SECTION_WIDTH;
    rowArr[base] = row.area;
    WEEKLY_SECTION_QUESTIONS.forEach((q, i) => {
      const val = row[q.key];
      rowArr[base + 1 + i] = val !== undefined ? val : '';
    });

    sheet.appendRow(rowArr);
  });

  return sheet;
}

module.exports = {
  makeCcsmSpreadsheet,
  setConfig,
  addNightlyRaw,
  addWeeklyRaw,
  nightlyHeaders,
  weeklyHeaders,
};
