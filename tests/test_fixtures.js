// test_fixtures.js — guards tests/fixtures.js's raw-form column layout
// against drift from the real Google Forms builders. Every later agent test
// builds its NIGHTLY_FORM_RAW / WEEKLY_FORM_RAW rows through fixtures.js, so
// if fixtures.js's modeled layout ever stops matching what
// DailyReportForm_ES.gs / WeeklyReportForm_ES.gs actually produce, every
// downstream test would still pass while silently testing the wrong shape.
// This test derives its expectations directly from the ES form builders
// (never from CcsmData.gs or fixtures.js itself), so it can catch that drift
// in either direction.
const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const fixtures = require('./fixtures');
const { makeCcsmSpreadsheet, addNightlyRaw } = fixtures;

// ---------------------------------------------------------------------------
// Load the real ES form builders standalone. Their build* functions are
// never invoked (no FormApp/SpreadsheetApp calls happen at load time) — only
// the top-level QUESTIONS / ZONES / INTRO_QUESTIONS / KEY_INDICATORS data
// declarations are read, so these are the exact values a real Google Forms
// deployment would use.
// ---------------------------------------------------------------------------
const esDaily = loadGs(['DailyReportForm_ES.gs'], makeGasEnv().globals);
const esWeekly = loadGs(['WeeklyReportForm_ES.gs'], makeGasEnv().globals);

const ZONE_NAMES = Object.keys(esDaily.ZONES);
assert.deepStrictEqual(
  Object.keys(esWeekly.ZONES),
  ZONE_NAMES,
  'DailyReportForm_ES.gs and WeeklyReportForm_ES.gs must agree on zone order'
);

// Structural (non-question) titles are inline string literals passed to
// setMeta_() inside buildDailyReportFormES()/buildWeeklyReportFormES() (not
// exported data), so they are reproduced here verbatim from those files.
const ZONE_COL = '¿En qué zona sirve?';
const AREA_COL = '¿En qué área sirve?';
const TIMESTAMP_COL = 'Marca temporal'; // Google Forms' own auto-generated column

// =============================================================================
// 1. NIGHTLY layout
// =============================================================================
const dailyQuestionTitles = esDaily.QUESTIONS.map((q) => q.title);
assert.strictEqual(esDaily.QUESTIONS.filter((q) => q.type === 'number').length, 20);
assert.strictEqual(dailyQuestionTitles.length, 23); // date + yesno + 20 numbers + effort

const dateQuestion = esDaily.QUESTIONS.find((q) => q.type === 'date');
const mcpQuestion = esDaily.QUESTIONS.find((q) => q.title.includes('Mi Senda de los Convenios'));
const effortQuestion = esDaily.QUESTIONS.find((q) => q.type === 'effort');
assert.strictEqual(dateQuestion.title, '¿Qué fecha está ingresando?');
assert.strictEqual(mcpQuestion.title, 'Lecciones con conversos recientes usando Mi Senda de los Convenios');
assert.strictEqual(effortQuestion.title, '¿Dio todo, la mayor parte o algo de esfuerzo en el altar del sacrificio hoy?');

const nightlySection = [AREA_COL].concat(dailyQuestionTitles);
assert.strictEqual(nightlySection.length, 24); // area + 23 questions

const expectedNightlyHeaders = [TIMESTAMP_COL, ZONE_COL];
ZONE_NAMES.forEach(() => expectedNightlyHeaders.push(...nightlySection));

const actualNightlyHeaders = fixtures.nightlyHeaders();
assert.deepStrictEqual(actualNightlyHeaders, expectedNightlyHeaders);
assert.strictEqual(actualNightlyHeaders.length, 2 + nightlySection.length * ZONE_NAMES.length);

// Explicit accented/special-char spot checks (character-for-character,
// accents/¿ included) — not just covered transitively by deepStrictEqual.
assert.ok(actualNightlyHeaders.includes(dateQuestion.title));
assert.ok(actualNightlyHeaders.includes(mcpQuestion.title));
assert.ok(actualNightlyHeaders.includes(effortQuestion.title));

// =============================================================================
// 2. WEEKLY layout
// =============================================================================
const introTitles = esWeekly.INTRO_QUESTIONS.map((q) => q.title);
assert.strictEqual(introTitles.length, 3); // report_date, leader_call, correlation_meeting
assert.strictEqual(esWeekly.KEY_INDICATORS.length, 7);

const realTitles = esWeekly.KEY_INDICATORS.map((t) => t + ' (Real)');
const metaTitles = esWeekly.KEY_INDICATORS.map((t) => t + ' (Meta)');

const weeklySection = [AREA_COL].concat(introTitles, realTitles, metaTitles);
assert.strictEqual(weeklySection.length, 18); // area + 3 intro + 7 real + 7 meta

const expectedWeeklyHeaders = [TIMESTAMP_COL, ZONE_COL];
ZONE_NAMES.forEach(() => expectedWeeklyHeaders.push(...weeklySection));

const actualWeeklyHeaders = fixtures.weeklyHeaders();
assert.deepStrictEqual(actualWeeklyHeaders, expectedWeeklyHeaders);
assert.strictEqual(actualWeeklyHeaders.length, 2 + weeklySection.length * ZONE_NAMES.length);

// Explicit "(Real)"/"(Meta)" string checks.
assert.strictEqual(realTitles[0], 'Nuevas personas encontradas (Real)');
assert.strictEqual(metaTitles[0], 'Nuevas personas encontradas (Meta)');

// GROUPED, not interleaved: within the first zone's section, all 7 Real
// titles must come immediately after the intro block, followed by all 7
// Meta titles — i.e. section[5] (2nd Real slot) must be indicator[1]'s Real
// title, NOT indicator[0]'s Meta title, which is what an interleaved layout
// would produce there instead.
const firstZoneSection = actualWeeklyHeaders.slice(2, 2 + weeklySection.length);
const realBlock = firstZoneSection.slice(4, 11); // after area(1) + intro(3)
const metaBlock = firstZoneSection.slice(11, 18);
assert.ok(realBlock.every((h) => h.endsWith(' (Real)')), 'expected all 7 Real headers grouped together');
assert.ok(metaBlock.every((h) => h.endsWith(' (Meta)')), 'expected all 7 Meta headers grouped together');
assert.strictEqual(firstZoneSection[5], esWeekly.KEY_INDICATORS[1] + ' (Real)'); // proves grouped, not interleaved
assert.strictEqual(firstZoneSection[11], esWeekly.KEY_INDICATORS[0] + ' (Meta)');

// =============================================================================
// 3. Blank-other-zones — a submission for a zone in the MIDDLE of the zone
// list must only populate that zone's section columns (+ timestamp + zone
// selector); every other zone's section columns stay blank, matching what
// Google Forms' per-zone branching actually produces (one flat response row,
// only the submitter's section filled in).
// =============================================================================
const env = makeGasEnv();
const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs'], env.globals);
const ss = makeCcsmSpreadsheet(env, scope);

const targetZoneIdx = 5;
const targetZone = ZONE_NAMES[targetZoneIdx];
assert.strictEqual(targetZone, 'Angol'); // sanity: confirms this is indeed a middle zone (10 total)

const rowObj = { zone: targetZone, area: 'Alemania 1', timestamp: new Date('2026-07-11T00:00:00Z') };
scope.CCSM_NIGHTLY_QUESTIONS.forEach((q, i) => {
  if (q.type === 'DATE') rowObj[q.key] = '2026-07-10';
  else if (q.type === 'YESNO') rowObj[q.key] = 'No';
  else if (q.type === 'CHOICE') rowObj[q.key] = 'Todo';
  else rowObj[q.key] = i + 1; // NUMBER
});

addNightlyRaw(env, ss, [rowObj]);

const sheet = ss.getSheetByName('NIGHTLY_FORM_RAW');
const data = sheet.getDataRange().getValues();
const dataRow = data[1];

assert.notStrictEqual(dataRow[0], ''); // timestamp
assert.strictEqual(dataRow[1], targetZone); // zone selector

const nightlySectionWidth = nightlySection.length; // 24
const targetBase = 2 + targetZoneIdx * nightlySectionWidth;

for (let c = targetBase; c < targetBase + nightlySectionWidth; c++) {
  assert.notStrictEqual(dataRow[c], '', `expected target zone-section col ${c} to be filled`);
}

ZONE_NAMES.forEach((zone, idx) => {
  if (idx === targetZoneIdx) return;
  const base = 2 + idx * nightlySectionWidth;
  for (let c = base; c < base + nightlySectionWidth; c++) {
    assert.strictEqual(dataRow[c], '', `expected zone "${zone}" section col ${c} to stay blank`);
  }
});

console.log('fixtures layout OK');
