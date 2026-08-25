// test_agent1a_ki_rollup.js — the zone / district / mission roll-up of the 7
// weekly Key Indicators (a1a_rollUpKi_, reached through a1a_buildSummaries).
//
// The whole point of this roll-up is that the obvious version of it is wrong.
// A WEEKLY_KI row holds the results of the week it is dated for, but the metas
// on that same row are the goals set for the week AFTER it — the weekly form
// says so to the missionary in as many words. So grading a unit means pairing
// this week's `real` with LAST week's `meta`, and a straight same-row sum
// quietly measures every area against a goal it had not set yet. On the live
// data that is not a rounding difference: metas match week to week for only
// about half of the area × indicator pairs, and one zone goes from 2 of 7
// metas met to 4 of 7 depending purely on which row the goal is read from.
//
// The other rules tested here exist for the same reason — each is a case where
// summing everything in sight produces a plausible-looking number that means
// nothing:
//   - an area that filed no results contributes neither real NOR meta, so a
//     unit is not scored down for a report that never arrived;
//   - an area that filed results but has no prior-week row falls back to its
//     own same-week meta, and is named so the letter can mark the row.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const KI_KEYS = [
  'ki_new_people', 'ki_member_lessons', 'ki_friends_sacrament',
  'ki_friends_first_week', 'ki_baptismal_date', 'ki_baptized_confirmed',
  'ki_rc_at_church',
];

function loadScope() {
  const env = makeGasEnv({});
  const scope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs', 'CCSM_Agent1A.gs'],
    env.globals
  );
  return { env, scope };
}

// One area's `ki` array in the shape a1a_loadWeeklyKi produces. `vals` maps a
// ki key to [real, sameWeekMeta]; anything unnamed is 0/0.
function kiArray(scope, vals) {
  return scope.A1A_KI_DEFS.map((d) => ({
    key: d.key,
    display: d.display,
    real: (vals[d.key] || [0, 0])[0],
    meta: (vals[d.key] || [0, 0])[1],
  }));
}
function metaMap(vals) {
  const out = {};
  KI_KEYS.forEach((k) => { out[k] = vals[k] || 0; });
  return out;
}
function byKey(rollup, key) {
  const found = rollup.indicators.filter((i) => i.key === key)[0];
  assert.ok(found, 'expected indicator ' + key + ' in the roll-up');
  return found;
}

// ===========================================================================
// 1. The metas come from LAST week's row, not this week's.
//    Same-week metas would give 12; prior-week metas give 8. Both are
//    plausible totals, which is exactly why this needs an assertion.
// ===========================================================================
{
  const { scope } = loadScope();

  const members = [
    {
      name: 'Area Uno',
      ki: kiArray(scope, { ki_new_people: [5, 7] }),   // 7 = the goal for NEXT week
      kiMetaPrev: metaMap({ ki_new_people: 3 }),       // 3 = the goal for THIS week
    },
    {
      name: 'Area Dos',
      ki: kiArray(scope, { ki_new_people: [4, 5] }),
      kiMetaPrev: metaMap({ ki_new_people: 5 }),
    },
  ];

  const roll = scope.a1a_rollUpKi_(members, '2026-08-16');
  const np = byKey(roll, 'ki_new_people');

  assert.strictEqual(np.real, 9, 'results sum across both areas');
  assert.strictEqual(np.meta, 8, 'meta must be 3+5 from the prior week, not 7+5 from this one');
  assert.strictEqual(np.achieved, true, '9 against 8 is a goal met');
  assert.strictEqual(roll.metaWeekEnd, '2026-08-16', 'the roll-up carries the week its metas were filed');
  assert.strictEqual(roll.areasReported, 2);
  assert.strictEqual(roll.areasTotal, 2);
  assert.deepStrictEqual(roll.fallbackAreas, [], 'both areas had a prior-week row');
  assert.deepStrictEqual(roll.silentAreas, []);

  // Guard the verdict itself, not just the arithmetic: on the same-week metas
  // 9 against 12 is a miss, so the tile count flips with the rule.
  assert.strictEqual(roll.metasAchieved, 1, 'exactly the one indicator with data is met');
  assert.strictEqual(roll.metasSet, 1, 'indicators with no meta anywhere are not "set"');

  console.log('prior-week metas drive the roll-up OK');
}

// ===========================================================================
// 2. Filed this week, nothing last week -> falls back to its own same-week
//    meta and says so. Silently dropping the area would understate the goal;
//    silently using zero would overstate the achievement.
// ===========================================================================
{
  const { scope } = loadScope();

  const roll = scope.a1a_rollUpKi_([
    {
      name: 'Area Nueva',
      ki: kiArray(scope, { ki_member_lessons: [6, 4] }),
      kiMetaPrev: null,                                  // filed no weekly form last week
    },
    {
      name: 'Area Vieja',
      ki: kiArray(scope, { ki_member_lessons: [2, 9] }),
      kiMetaPrev: metaMap({ ki_member_lessons: 5 }),
    },
  ], '2026-08-16');

  const ml = byKey(roll, 'ki_member_lessons');
  assert.strictEqual(ml.real, 8);
  assert.strictEqual(ml.meta, 9, '4 (own same-week fallback) + 5 (prior week)');
  assert.deepStrictEqual(roll.fallbackAreas, ['Area Nueva'],
    'the fallback area must be named so the letter can mark its contribution');
  assert.strictEqual(roll.areasReported, 2, 'a fallback area still reported');

  console.log('same-week meta fallback OK');
}

// ===========================================================================
// 3. Set a meta last week and filed nothing this week -> named, and kept out
//    of BOTH totals. Counting its meta while its results are missing is the
//    bug this rule exists to prevent: the unit would look like it missed a
//    goal that nobody has actually measured.
// ===========================================================================
{
  const { scope } = loadScope();

  const roll = scope.a1a_rollUpKi_([
    {
      name: 'Area Activa',
      ki: kiArray(scope, { ki_baptismal_date: [4, 4] }),
      kiMetaPrev: metaMap({ ki_baptismal_date: 4 }),
    },
    {
      name: 'Villa Silenciosa',
      ki: [],                                            // tab readable, no row this week
      kiMetaPrev: metaMap({ ki_baptismal_date: 6 }),     // but a real goal last week
    },
  ], '2026-08-16');

  const bd = byKey(roll, 'ki_baptismal_date');
  assert.strictEqual(bd.real, 4, 'only the reporting area contributes results');
  assert.strictEqual(bd.meta, 4, 'the silent area meta of 6 must NOT be added');
  assert.strictEqual(bd.achieved, true, 'including the unmeasured meta would have made this a miss');

  assert.deepStrictEqual(roll.silentAreas, ['Villa Silenciosa']);
  assert.strictEqual(roll.areasReported, 1);
  assert.strictEqual(roll.areasTotal, 2, 'the silent area still counts toward the unit size');

  console.log('meta sin resultado excluded from the totals OK');
}

// ===========================================================================
// 4. Silence is only worth reporting when a goal was actually owed.
// ===========================================================================
{
  const { scope } = loadScope();

  const roll = scope.a1a_rollUpKi_([
    { name: 'Con Meta',   ki: [], kiMetaPrev: metaMap({ ki_rc_at_church: 2 }) },
    { name: 'Sin Fila',   ki: [], kiMetaPrev: null },        // filed nothing either week
    { name: 'Metas Cero', ki: [], kiMetaPrev: metaMap({}) }, // filed, but planned nothing
  ], '2026-08-16');

  assert.deepStrictEqual(roll.silentAreas, ['Con Meta'],
    'only an area that set a goal above zero owes a result');
  assert.strictEqual(roll.areasReported, 0);

  console.log('silent-area naming is limited to real goals OK');
}

// ===========================================================================
// 5. A meta of zero is "nothing planned", never a goal met by doing nothing.
// ===========================================================================
{
  const { scope } = loadScope();

  const roll = scope.a1a_rollUpKi_([{
    name: 'Area Cero',
    ki: kiArray(scope, { ki_baptized_confirmed: [0, 0] }),
    kiMetaPrev: metaMap({ ki_baptized_confirmed: 0 }),
  }], '2026-08-16');

  const bc = byKey(roll, 'ki_baptized_confirmed');
  assert.strictEqual(bc.meta, 0);
  assert.strictEqual(bc.achieved, false, '0 >= 0 must not count as a goal achieved');
  assert.strictEqual(roll.metasAchieved, 0);
  assert.strictEqual(roll.metasSet, 0);

  console.log('zero meta is not an achievement OK');
}

// ===========================================================================
// 6. All 7 indicators are always present, in A1A_KI_DEFS order, even when the
//    week is empty — the letter renders a fixed 7-row block and a missing key
//    would drop a row rather than show a zero.
// ===========================================================================
{
  const { scope } = loadScope();

  const roll = scope.a1a_rollUpKi_([{
    name: 'Area Vacia', ki: kiArray(scope, {}), kiMetaPrev: null,
  }], '2026-08-16');

  assert.deepStrictEqual(roll.indicators.map((i) => i.key), KI_KEYS,
    'every KI must be present, in the canonical order');
  roll.indicators.forEach((i) => {
    assert.ok(i.display && !/^ki_/.test(i.display), 'each row carries its Spanish label');
  });

  console.log('all 7 indicators always render OK');
}

// ===========================================================================
// 7. Tab unavailable -> null, matching area.ki. The letter must stay silent
//    rather than publish zeros the areas did not earn.
// ===========================================================================
{
  const { scope } = loadScope();

  assert.strictEqual(scope.a1a_rollUpKi_([{ name: 'A', ki: null, kiMetaPrev: null }], '2026-08-16'), null,
    'a null area.ki means the source is unavailable, not that the unit scored zero');
  assert.strictEqual(scope.a1a_rollUpKi_([], '2026-08-16'), null, 'a unit with no areas has no roll-up');
  assert.strictEqual(scope.a1a_rollUpKi_(null, '2026-08-16'), null);

  console.log('unavailable source returns null OK');
}

// ===========================================================================
// 8. a1a_buildSummaries attaches a roll-up at all three scopes, scoped
//    correctly, without disturbing the nightly totals it already produced.
// ===========================================================================
{
  const { scope } = loadScope();

  const missionOrg = [
    { Area_Name: 'Uno',  Zone: 'Norte', District: 'D1' },
    { Area_Name: 'Dos',  Zone: 'Norte', District: 'D2' },
    { Area_Name: 'Tres', Zone: 'Sur',   District: 'D3' },
  ];
  const areaData = {
    Uno:  { stats: { submissions: 7, contacts_made: 10 }, ki: kiArray(scope, { ki_new_people: [4, 0] }), kiMetaPrev: metaMap({ ki_new_people: 2 }) },
    Dos:  { stats: { submissions: 5, contacts_made: 20 }, ki: kiArray(scope, { ki_new_people: [1, 0] }), kiMetaPrev: metaMap({ ki_new_people: 6 }) },
    Tres: { stats: { submissions: 0, contacts_made: 0  }, ki: [],                                        kiMetaPrev: metaMap({ ki_new_people: 9 }) },
  };

  const s = scope.a1a_buildSummaries(areaData, missionOrg, '2026-08-16');

  // Nightly aggregation is untouched.
  assert.strictEqual(s.mission.total_areas, 3);
  assert.strictEqual(s.mission.submitted, 2);
  assert.strictEqual(s.mission.contacts_made, 30);

  const missionNp = byKey(s.mission.ki, 'ki_new_people');
  assert.strictEqual(missionNp.real, 5, 'mission sums the two reporting areas');
  assert.strictEqual(missionNp.meta, 8, 'Tres set 9 but filed nothing, so its meta stays out');
  assert.deepStrictEqual(s.mission.ki.silentAreas, ['Tres']);

  const zoneNp = byKey(s.zones['Norte'].ki, 'ki_new_people');
  assert.strictEqual(zoneNp.real, 5);
  assert.strictEqual(zoneNp.meta, 8);
  assert.strictEqual(s.zones['Norte'].ki.areasTotal, 2, 'the zone roll-up covers only its own areas');
  assert.deepStrictEqual(s.zones['Sur'].ki.silentAreas, ['Tres'], 'Sur is the silent area own zone');
  assert.strictEqual(byKey(s.zones['Sur'].ki, 'ki_new_people').meta, 0, 'a zone that filed nothing has no meta to grade');

  assert.strictEqual(s.districts['D1'].ki.areasTotal, 1);
  assert.strictEqual(byKey(s.districts['D1'].ki, 'ki_new_people').real, 4);
  assert.strictEqual(byKey(s.districts['D2'].ki, 'ki_new_people').real, 1);

  console.log('roll-up attached at mission / zone / district OK');
}

// ===========================================================================
// 9. End to end through runAgent1A: the second WEEKLY_KI read really happens,
//    really lands on weekEnd − 7, and really reaches the saved payload.
//    Every unit test above can pass while the wiring reads the wrong week.
// ===========================================================================
{
  const { env, scope } = loadScope();
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const thisSunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
  const toStr = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  const weekEnd = toStr(thisSunday);
  const prevEnd = toStr(new Date(thisSunday.getFullYear(), thisSunday.getMonth(), thisSunday.getDate() - 7));

  addNightlyRaw(env, ss, [{
    zone: 'Arauco', area: 'Arauco 1', report_date: weekEnd,
    exchanges: 'Sí', effort: 'Algo', contacts_made: 12,
  }]);
  scope.runAgent3();

  const headers = ['Week_End_Date', 'Area', 'Zone', 'District']
    .concat(...KI_KEYS.map((k) => [k + '_real', k + '_meta']));
  const sheet = ss.insertSheet('WEEKLY_KI');
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  const row = (weekEndDate, real, meta) => {
    const o = { Week_End_Date: weekEndDate, Area: 'Arauco 1', Zone: 'Arauco', District: 'Arauco' };
    o['ki_new_people_real'] = real;
    o['ki_new_people_meta'] = meta;
    return headers.map((h) => (o[h] !== undefined ? o[h] : 0));
  };
  // Last week the area set a meta of 3. This week it reported 5 and set 99 for
  // the week ahead. Grading against 99 is the bug; grading against 3 is right.
  sheet.appendRow(row(prevEnd, 1, 3));
  sheet.appendRow(row(weekEnd, 5, 99));

  scope.runAgent1A();

  const payload = scope.loadTempData('A1A_DATA');
  assert.ok(payload && payload.summaries, 'runAgent1A must save a payload with summaries');

  const zoneKi = payload.summaries.zones['Arauco'].ki;
  assert.ok(zoneKi, 'the zone summary must carry a KI roll-up');
  assert.strictEqual(zoneKi.metaWeekEnd, prevEnd, 'metas must be dated one week before the results');

  const np = zoneKi.indicators.filter((i) => i.key === 'ki_new_people')[0];
  assert.strictEqual(np.real, 5);
  assert.strictEqual(np.meta, 3, 'read from the prior-week row, not the 99 filed this week');
  assert.strictEqual(np.achieved, true);

  const area = payload.areas['Arauco 1'];
  assert.ok(area.kiMetaPrev, 'the per-area prior-week metas ride along for the missionary block');
  assert.strictEqual(area.kiMetaPrev['ki_new_people'], 3);
  assert.strictEqual(area.ki.filter((i) => i.key === 'ki_new_people')[0].meta, 99,
    'the same-week meta stays on area.ki — switching the missionary block over is a separate change');

  console.log('end-to-end prior-week wiring OK');
}

console.log('\nAll KI roll-up tests passed');
