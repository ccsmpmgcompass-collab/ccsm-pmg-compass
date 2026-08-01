// test_live_form_headers.js — does the CODE match the REAL Google Form?
//
// Every other test in this suite builds its *_FORM_RAW header from
// fixtures.js, which generates it from CcsmData.gs — the same file the agents
// read. Those tests can therefore only ever prove the agents are
// self-consistent with CcsmData.gs. They can NOT prove the agents match the
// live Google Form, because nothing in this repo produced that form's header
// row: a human built the form and Google wrote the header.
//
// On Aug 5 2026 the first real submissions land in COMPASS_CCSM. If a single
// question's wording differs by one character between CcsmData.gs and the live
// form, a3_parseSectionStructure() logs a warning and that metric silently
// reads as zero forever — the run still reports SUCCESS. That is the failure
// this file exists to make impossible.
//
// The fixture is a snapshot of the live header rows, pulled read-only with
//   dashboard/venv/Scripts/python.exe dashboard/tools/probe_live.py json \
//     tests/live/live_form_headers.json NIGHTLY_FORM_RAW WEEKLY_FORM_RAW QUESTIONS_CONFIG
// Re-pull it after ANY edit to the live Google Forms.

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { nightlyHeaders, weeklyHeaders } = require('./fixtures');

// Strip a UTF-8 BOM before parsing: probe_live.py writes clean UTF-8, but any
// hand-edit of this fixture through PowerShell (Out-File -Encoding utf8 adds a
// BOM in 5.1) would otherwise fail with a JSON syntax error that looks nothing
// like the encoding problem it actually is.
const LIVE = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'live', 'live_form_headers.json'), 'utf8')
    .replace(/^﻿/, '')
);

const env = makeGasEnv();
const scope = loadGs(['CcsmData.gs', 'CCSM_Helpers.gs', 'CCSM_Agent3.gs'], env.globals);

const liveNightly = LIVE.NIGHTLY_FORM_RAW[0].map((h) => String(h).trim());
const liveWeekly = LIVE.WEEKLY_FORM_RAW[0].map((h) => String(h).trim());

// ---------------------------------------------------------------------------
// 1. Shape: the live sheets really are one repeated block per zone.
// ---------------------------------------------------------------------------
const ZONES = Object.keys(scope.CCSM_ZONES);
const expectedNightly = nightlyHeaders().map((h) => String(h).trim());
const expectedWeekly = weeklyHeaders().map((h) => String(h).trim());

assert.strictEqual(
  liveNightly.length, expectedNightly.length,
  `NIGHTLY_FORM_RAW is ${liveNightly.length} columns, CcsmData.gs implies ` +
  `${expectedNightly.length} (2 + ${ZONES.length} zones x section width). ` +
  'A question was added to or removed from the live form.'
);
assert.strictEqual(
  liveWeekly.length, expectedWeekly.length,
  `WEEKLY_FORM_RAW is ${liveWeekly.length} columns, CcsmData.gs implies ${expectedWeekly.length}.`
);

// ---------------------------------------------------------------------------
// 2. Wording: every column matches, character for character.
//
// Column 1 is deliberately exempt. Google names it in the FORM's locale
// ("Timestamp" on the live sheet, 'Marca temporal' in the fixture) and no
// agent ever reads it — a3_buildDailyRecords locates its data by finding the
// non-blank area column, never by position 0. Asserting on it would fail
// loudly for a difference that cannot affect behavior.
// ---------------------------------------------------------------------------
function diffHeaders(live, expected, label) {
  const bad = [];
  for (let i = 1; i < expected.length; i++) {
    if (live[i] !== expected[i]) {
      bad.push(`  col ${i + 1}: live=${JSON.stringify(live[i])} ` +
               `cfg=${JSON.stringify(expected[i])}`);
    }
  }
  assert.deepStrictEqual(
    bad, [],
    `${label}: ${bad.length} column(s) differ between the live Google Form and ` +
    `CcsmData.gs.\n${bad.slice(0, 12).join('\n')}`
  );
}

diffHeaders(liveNightly, expectedNightly, 'NIGHTLY_FORM_RAW');
diffHeaders(liveWeekly, expectedWeekly, 'WEEKLY_FORM_RAW');

// ---------------------------------------------------------------------------
// 3. Every ACTIVE nightly metric in the LIVE QUESTIONS_CONFIG resolves to a
//    real column, through a3_parseSectionStructure itself.
//
// This is the check that actually protects Aug 5. QUESTIONS_CONFIG lives in
// the sheet and is editable from the Maintenance page, so it can drift away
// from both CcsmData.gs and the form without any code change at all.
// ---------------------------------------------------------------------------
const qcGrid = LIVE.QUESTIONS_CONFIG;
const qcHeaders = qcGrid[0].map((h) => String(h).trim());
const liveMetrics = qcGrid.slice(1).map((row) => {
  const m = {};
  qcHeaders.forEach((h, i) => { m[h] = row[i] != null ? String(row[i]).trim() : ''; });
  return m;
}).filter((m) =>
  m.Active && m.Active.toUpperCase() === 'TRUE' &&
  (!m.Form_Type || m.Form_Type.toUpperCase() === 'NIGHTLY') &&
  m.Metric_Key !== 'report_date' && m.Metric_Key && m.Form_Column_Header
);

assert.ok(liveMetrics.length >= 20,
  `expected ~22 active nightly metrics in the live QUESTIONS_CONFIG, got ${liveMetrics.length}`);

const structure = scope.a3_parseSectionStructure(liveNightly, liveMetrics);

assert.strictEqual(structure.areaCols.length, ZONES.length,
  `a3_parseSectionStructure found ${structure.areaCols.length} zone sections in the ` +
  `live header, expected ${ZONES.length}`);
assert.ok(structure.zoneIdx >= 0, 'the global zone column was not found');

// Any metric that landed in globalMetricCols instead of metricOffsets is a
// question appended after launch — legal, but it means the section template no
// longer describes the form, so surface it rather than letting it pass mute.
const appended = Object.keys(structure.globalMetricCols || {});
assert.deepStrictEqual(appended, [],
  `metric(s) resolved outside the section template (appended to the form after ` +
  `launch?): ${appended.join(', ')}`);

const unresolved = liveMetrics
  .map((m) => m.Metric_Key)
  .filter((k) => structure.metricOffsets[k] === undefined);
assert.deepStrictEqual(unresolved, [],
  `metric(s) in the live QUESTIONS_CONFIG match NO column in the live form — ` +
  `these would silently read as 0 forever: ${unresolved.join(', ')}`);

// ---------------------------------------------------------------------------
// 4. End to end: a submission from the LAST zone parses correctly.
//
// Section 0 would pass even if the offset arithmetic were wrong, because its
// start index is 0 relative to itself. The last zone is the case that fails if
// dateOffset or metricOffsets are computed against the wrong base — the exact
// bug the repeated-header layout invites.
// ---------------------------------------------------------------------------
const lastZone = ZONES[ZONES.length - 1];
const lastAreas = scope.CCSM_ZONES[lastZone];
const testArea = Array.isArray(lastAreas) ? lastAreas[0] : Object.keys(lastAreas)[0];

const sectionStart = structure.areaCols[structure.areaCols.length - 1];
const row = new Array(liveNightly.length).fill('');
row[0] = new Date();
row[structure.zoneIdx] = lastZone;
row[sectionStart] = testArea;
row[sectionStart + structure.dateOffset] = '2026-08-05';

// A distinct value per metric, so a wrong offset lands on the wrong key and
// fails instead of coincidentally matching.
const expectedValues = {};
liveMetrics.forEach((m, i) => {
  const off = structure.metricOffsets[m.Metric_Key];
  if (m.Data_Type === 'YESNO') {
    row[sectionStart + off] = 'Sí';
    expectedValues[m.Metric_Key] = 'TRUE';
  } else if (m.Data_Type === 'CHOICE') {
    row[sectionStart + off] = 'Todo';
    expectedValues[m.Metric_Key] = 'Todo';
  } else {
    row[sectionStart + off] = i + 1;
    expectedValues[m.Metric_Key] = i + 1;
  }
});

const areaLookup = {};
areaLookup[testArea.toLowerCase()] = testArea;

const records = scope.a3_buildDailyRecords([liveNightly, row], areaLookup, liveMetrics);
const key = testArea + '|2026-08-05';
assert.ok(records[key],
  `a submission from the LAST zone section (${lastZone} / ${testArea}) produced no ` +
  `DAILY_LOG record. Got keys: ${Object.keys(records).join(', ')}`);
assert.strictEqual(records[key].zone, lastZone);
assert.deepStrictEqual(records[key].totals, expectedValues,
  'last-zone submission parsed to the wrong values — section offset arithmetic is wrong');

console.log(
  `live form headers OK — ${ZONES.length} zone sections, ` +
  `${liveNightly.length} nightly / ${liveWeekly.length} weekly columns, ` +
  `${liveMetrics.length} active nightly metrics all resolved, ` +
  `last-zone (${lastZone}) submission parsed clean`
);
