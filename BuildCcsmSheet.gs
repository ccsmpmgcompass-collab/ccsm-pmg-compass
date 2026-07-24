/**
 * BuildCcsmSheet.gs — one-shot builder for the COMPASS_CCSM spreadsheet
 * ------------------------------------------------------------------
 * HOW TO USE
 *   1. Create a new standalone Google Apps Script project (script.google.com
 *      > New project), NOT bound to any existing sheet.
 *   2. Paste CcsmData.gs and this file (BuildCcsmSheet.gs) into the project
 *      (CcsmData.gs first — this file reads its globals).
 *   3. Select buildCcsmSheet from the function dropdown and click Run.
 *      Authorize when prompted (creates a new spreadsheet in your Drive).
 *   4. Check the Execution log (View > Logs) for the new sheet's URL and the
 *      VERIFY result, then follow the NEXT STEPS printed at the end.
 *
 * WHAT IT DOES
 *   Creates one new spreadsheet named COMPASS_CCSM, builds every tab listed
 *   in CCSM_TAB_SPECS (CcsmData.gs) with its header row (if any) and any
 *   pre-filled config/org/questions rows, then runs a self-verifying
 *   reopen-compare-fix pass (verifyCcsmSheet_) to guard against Google
 *   Sheets occasionally dropping a write under load — it reopens the
 *   spreadsheet by ID (fresh server state, not a cached handle), compares
 *   every expected cell, re-applies any mismatch, and repeats (capped at 20
 *   rounds) until a clean read-back.
 *
 * This is a standalone builder script — it is never bound to the sheet it
 * creates, and it is not part of the ported CCSM_* agent scripts that will
 * later run against the sheet it produces.
 */

function buildCcsmSheet() {
  var ss = SpreadsheetApp.create('COMPASS_CCSM');
  CCSM_TAB_SPECS.forEach(function(spec) {
    var sh = ss.insertSheet(spec.name);
    if (spec.headers) {
      sh.getRange(1, 1, 1, spec.headers.length).setValues([spec.headers]);
      sh.getRange(1, 1, 1, spec.headers.length).setFontWeight('bold').setBackground('#173A72').setFontColor('#FFFFFF');
      sh.setFrozenRows(1);
    }
    var rows = ccsmPrefillRows_(spec);
    if (rows && rows.length) sh.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  });
  // remove the default sheet LAST (a spreadsheet can never have zero sheets)
  var def = ss.getSheetByName('Sheet1') || ss.getSheetByName('Hoja 1');
  if (def) ss.deleteSheet(def);
  SpreadsheetApp.flush();
  var ok = verifyCcsmSheet_(ss.getId());
  Logger.log('COMPASS_CCSM created: ' + ss.getUrl());
  Logger.log(ok ? 'VERIFY: all tabs & headers correct.' : 'VERIFY WARNING: see fix log above.');
  Logger.log('NEXT STEPS: (1) attach the ES daily form -> rename its new tab to NIGHTLY_FORM_RAW; ' +
             '(2) attach the ES weekly form -> rename to WEEKLY_FORM_RAW; ' +
             '(3) fill AGENT_CONFIG blanks (SYSTEM_START_DATE, form links, GEMINI key via Script Properties); ' +
             '(4) create the bound Apps Script project and paste the CCSM_*.gs files (Helpers first).');
}

function ccsmPrefillRows_(spec) {
  if (spec.prefill === 'CCSM_MISSION_ORG_ROWS') return CCSM_MISSION_ORG_ROWS;
  if (spec.prefill === 'CCSM_AGENT_CONFIG_ROWS') return CCSM_AGENT_CONFIG_ROWS;
  if (spec.name === 'QUESTIONS_CONFIG') return ccsmQuestionsConfigRows_();
  return null;
}

function ccsmQuestionsConfigRows_() {
  var rows = [], n = 0;
  CCSM_NIGHTLY_QUESTIONS.forEach(function(q) {
    n++;
    rows.push(['Q-N-' + ('00' + n).slice(-3), 'NIGHTLY', q.headerEs, q.key, q.displayEs,
               q.type, 'TRUE', 'TRUE', 'TRUE', q.order, 'TRUE']);
  });
  var w = 0;
  CCSM_WEEKLY_QUESTIONS.forEach(function(q) {
    w++;
    rows.push(['Q-W-' + ('00' + w).slice(-3), 'WEEKLY', q.headerEs, q.key, q.displayEs,
               q.type, 'FALSE', 'FALSE', 'TRUE', q.order, 'TRUE']);
  });
  return rows;
}

// Builds the same {tabName: [[row1],[row2],...]} shape the builder wrote,
// from the same CcsmData.gs globals — so the verify pass never drifts from
// what buildCcsmSheet() actually intended to write. Each tab's array starts
// with its header row (if the spec has one) followed by any prefill rows;
// tabs with neither are recorded as an empty array (skipped by the verifier).
function ccsmExpectedState_() {
  var expected = {};
  CCSM_TAB_SPECS.forEach(function(spec) {
    var rows = [];
    if (spec.headers) rows.push(spec.headers.slice());
    var prefill = ccsmPrefillRows_(spec);
    if (prefill && prefill.length) rows = rows.concat(prefill);
    expected[spec.name] = rows;
  });
  return expected;
}

// Google Sheets auto-parses a plain string literal that LOOKS like a boolean
// or a number into that typed value when it is written via setValue /
// setValues — "TRUE"/"FALSE" become real Booleans, "0.50" becomes the Number
// 0.5. want[] is always the literal string CcsmData.gs authored; got[] is
// whatever Sheets actually stored. A naive String(got) !== String(want)
// never converges here: String(true) is "true", not "TRUE"; String(0.5) is
// "0.5", not "0.50". This normalizes both sides to what Sheets will actually
// treat as equivalent, so the verify pass can recognize a correctly-written
// cell instead of "fixing" it forever.
function ccsmCellsEqual_(got, want) {
  if (want === 'TRUE' || want === 'FALSE') {
    return String(got).trim().toUpperCase() === want;
  }
  if (typeof want === 'string' && /^-?\d+(\.\d+)?$/.test(want)) {
    return Number(got) === Number(want);
  }
  return String(got) === String(want);
}

function verifyCcsmSheet_(spreadsheetId) {
  var expected = ccsmExpectedState_();
  for (var round = 1; round <= 20; round++) {
    var ss = SpreadsheetApp.openById(spreadsheetId);   // FRESH open — true server state
    var fixes = 0;
    Object.keys(expected).forEach(function(tabName) {
      var sh = ss.getSheetByName(tabName);
      if (!sh) { ss.insertSheet(tabName); fixes++; return; }
      var want = expected[tabName];
      if (!want.length) return;
      var got = sh.getLastRow() > 0 ? sh.getRange(1, 1, want.length, want[0].length).getValues() : [];
      for (var r = 0; r < want.length; r++) {
        for (var c = 0; c < want[r].length; c++) {
          var g = got[r] ? got[r][c] : '';
          if (!ccsmCellsEqual_(g, want[r][c])) { sh.getRange(r + 1, c + 1).setValue(want[r][c]); fixes++; }
        }
      }
    });
    Logger.log('Verify round ' + round + ': applied ' + fixes + ' fix(es)');
    if (fixes === 0) return true;
    SpreadsheetApp.flush();
  }
  return false;
}
