// test_agent1a_derived.js — CCSM_Agent1A.gs multi-week data layer
// (a1a_loadMultiWeekHistory + a1a_buildDerived), the CCSM analogue of
// Provo's docs/Agent1A.gs a1a_buildDerived. Wired into runAgent1A() as
// areaData[name].derived, feeding the trend chart / scoreboard / goal grid /
// You-vs-You / funnel strip / consistency block Agent1C will render.
//
// CCSM has no WEEKLY_BREAKDOWNS equivalent (its WEEKLY_KI holds only the 7
// ki_* real/meta pairs, not nightly rollups — CCSM_Agent1A.gs's own header
// documents this), so every multi-week number here comes from DAILY_LOG
// alone. The funnel is remapped to CCSM's real nightly chain (contacts
// attempted -> made -> meaningful -> lessons -> new friends found); Provo's
// LSI fields are dropped, CCSM's form has no LSI metric.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_Agent3.gs', 'CCSM_Agent1A.gs'],
  env.globals
);
const ss = makeCcsmSpreadsheet(env, scope);

setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');

// ---------------------------------------------------------------------------
// Three weeks of Monday..Sunday for 'Arauco 1' (zone 'Arauco'): two full
// prior weeks plus the current week, current week missing Wednesday so the
// consistency block's dayFlags/streak have something real to prove.
// ---------------------------------------------------------------------------
function toDateStr(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function weekDatesEnding(sunday) {
  const out = [];
  for (let i = 6; i >= 0; i--) {
    out.push(toDateStr(new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - i)));
  }
  return out;
}
const today = new Date();
today.setHours(0, 0, 0, 0);
const thisSunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
const lastSunday = new Date(thisSunday.getFullYear(), thisSunday.getMonth(), thisSunday.getDate() - 7);
const twoAgoSunday = new Date(thisSunday.getFullYear(), thisSunday.getMonth(), thisSunday.getDate() - 14);

const weekEndStr = toDateStr(thisSunday);
const currentDates = weekDatesEnding(thisSunday);   // [Mon..Sun]
const lastWeekDates = weekDatesEnding(lastSunday);
const twoAgoDates = weekDatesEnding(twoAgoSunday);

function seedWeek(dates, attemptedOnMonday, madeOnMonday, skipIndex) {
  const rows = dates
    .map((d, i) => ({
      zone: 'Arauco',
      area: 'Arauco 1',
      report_date: d,
      exchanges: 'Sí',
      effort: 'Algo',
      ...(i === 0 ? { contacts_attempted: attemptedOnMonday, contacts_made: madeOnMonday } : {}),
    }))
    .filter((_, i) => i !== skipIndex);
  addNightlyRaw(env, ss, rows);
  scope.runAgent3();
}

seedWeek(twoAgoDates, 10, 2, -1);   // full week, no gap
seedWeek(lastWeekDates, 20, 10, -1); // full week, no gap
seedWeek(currentDates, 30, 15, 2);   // Wednesday (index 2) missing

// ---------------------------------------------------------------------------
// Run Agent1A and pull the saved A1A_DATA for Arauco 1.
// ---------------------------------------------------------------------------
scope.runAgent1A();
const a1aData = scope.loadTempData('A1A_DATA');
assert.strictEqual(a1aData.weekEnd, weekEndStr, 'A1A_DATA.weekEnd must be this Sunday');

const area = a1aData.areas['Arauco 1'];
assert.ok(area, 'expected an Arauco 1 entry in A1A_DATA');
const der = area.derived;
assert.ok(der, 'expected area.derived to be populated');

console.log('derived data OK — struct present');

// ===========================================================================
// weeks[] — 8 week-ending Sundays, ascending, last one is the current week.
// ===========================================================================
assert.strictEqual(der.weeks.length, 8, 'derived.weeks must hold exactly 8 week-ending dates');
assert.strictEqual(der.weeks[7], weekEndStr, 'the last week in derived.weeks must be the current week');
assert.strictEqual(der.weeks[6], toDateStr(lastSunday), 'the second-to-last week must be last week');

console.log('weeks[] OK');

// ===========================================================================
// lastWeek / delta — last week's Arauco 1 totals, and this week's change.
// ===========================================================================
assert.strictEqual(der.lastWeek.contacts_made, 10, 'lastWeek.contacts_made must be last week\'s total');
assert.strictEqual(der.delta.contacts_made, 5, 'delta.contacts_made must be current(15) - lastWeek(10)');

console.log('lastWeek/delta OK');

// ===========================================================================
// xferAvg / best / isBest — TRANSFER_START_DATE covers all 3 seeded weeks.
// ===========================================================================
assert.strictEqual(der.xferAvg.contacts_made, 9, 'xferAvg.contacts_made must average [15,10,2] = 9');
assert.strictEqual(der.best.contacts_made, 15, 'best.contacts_made must be the highest of the 3 weeks');
assert.strictEqual(der.isBest.contacts_made, true, 'current week IS the best week for contacts_made');

console.log('xferAvg/best/isBest OK');

// ===========================================================================
// RATE METRIC correctness (contact_rate) — regression coverage for a real
// shipped bug (found in code review, 2026-08-01): a1a_loadMultiWeekHistory
// only summed raw DAILY_LOG columns and never derived the 4 fraction rate
// metrics per week, so a1a_pastWeekValue_ found no such key for ANY week
// (including weeks that DID report), xferVals/allVals collapsed to just
// the current week's own value, and xferAvg/best silently rendered as a
// copy of THIS week's number mislabeled as historical. A compounding
// second bug (a1a_round1's 0.1 absolute step applied to a 0-1 fraction)
// rounded 5% to 10%, a 100% relative error. Both are fixed; this section
// proves it with real computed values, not just "a label is present."
//
// Known contact_rate per week from the contacts_attempted/contacts_made
// numbers already seeded above: twoAgo 2/10=0.2, lastWeek 10/20=0.5,
// current 15/30=0.5.
// ===========================================================================
assert.strictEqual(der.lastWeek.contact_rate, 0.5, 'lastWeek.contact_rate must be last week\'s TRUE rate (10/20), not null/undefined');
assert.strictEqual(der.delta.contact_rate, 0, 'delta.contact_rate must be current(0.5) - lastWeek(0.5) = 0, not null');
assert.strictEqual(der.xferAvg.contact_rate, 0.4, 'xferAvg.contact_rate must average the 3 REAL weekly rates [0.5,0.5,0.2] = 0.4, not collapse to the current week\'s own 0.5');
assert.strictEqual(der.best.contact_rate, 0.5, 'best.contact_rate must be the true highest of the 3 real weekly rates, not just the current week');
assert.strictEqual(der.isBest.contact_rate, true, 'current week ties the true best (0.5), so isBest must fire');

// effort_score: same regression, but via the separate a1a_loadMultiWeekEffort
// (NIGHTLY_FORM_RAW) path rather than a1a_loadMultiWeekHistory. Every
// reported night this whole fixture answered 'Algo' (score 1), constant
// across all 3 weeks, so effort_score must be exactly 1 for every week —
// a real computed value, not a null/undefined collapse.
assert.strictEqual(der.lastWeek.effort_score, 1, 'lastWeek.effort_score must be last week\'s real weighted average (all "Algo" = 1), not null');
assert.strictEqual(der.xferAvg.effort_score, 1, 'xferAvg.effort_score must average the 3 real weeks (all 1) = 1');
assert.strictEqual(der.best.effort_score, 1, 'best.effort_score must be the true best across real weeks');

console.log('rate metric (contact_rate) + effort_score history OK');

// ===========================================================================
// trend — present for whichever metric ranked as growth, 8-point series,
// last point matches this week's own stat (structural check only — which
// metric ranks as growth depends on goal config, not asserted here).
// ===========================================================================
assert.ok(der.trend, 'expected a trend series for the growth metric');
assert.strictEqual(der.trend.series.length, 8, 'trend series must have 8 points');
assert.strictEqual(der.trend.series[7].week, weekEndStr);
assert.strictEqual(
  der.trend.series[7].value, area.stats[der.trend.key],
  'the trend series\' last point must equal this week\'s own stat for that metric'
);

console.log('trend OK');

// ===========================================================================
// funnel — remapped to CCSM's real chain, no LSI fields at all.
// ===========================================================================
assert.strictEqual(der.funnel.attempted, 30);
assert.strictEqual(der.funnel.contacted, 15);
assert.strictEqual(der.funnel.contactedPct, 50, 'contactedPct must be contacts_made/contacts_attempted = 15/30 = 50%');
assert.strictEqual(der.funnel.lsiGiven, undefined, 'funnel must NOT carry Provo\'s LSI fields — CCSM has no LSI metric');
assert.strictEqual(der.funnel.lsiFollowups, undefined, 'funnel must NOT carry Provo\'s LSI fields — CCSM has no LSI metric');

console.log('funnel OK');

// ===========================================================================
// consistency — Wednesday missing this week: dayFlags shows the gap,
// daysReported is 6 (not 7), and the streak (counted backward from Sunday)
// stops at the gap.
// ===========================================================================
assert.strictEqual(der.consistency.daysReported, 6, 'daysReported must be 6 — Wednesday was never submitted');
assert.strictEqual(der.consistency.dayFlags.length, 7);
assert.strictEqual(der.consistency.dayFlags[2].label, 'X', 'index 2 (Wednesday) must carry the Spanish Miercoles initial');
assert.strictEqual(der.consistency.dayFlags[2].reported, false, 'Wednesday must be flagged unreported');
assert.strictEqual(der.consistency.dayFlags[6].reported, true, 'Sunday must be flagged reported');
assert.strictEqual(der.consistency.streak, 4, 'streak counts backward from Sunday and stops at the Wednesday gap: Sun,Sat,Fri,Thu = 4');

console.log('consistency OK');

console.log('agent1a derived OK');
