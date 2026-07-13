// test_agent2_4.js — CCSM_Agent2.gs (per-transfer goal recalibration) +
// CCSM_Agent4.gs (system health check).
//
// Agent2 section proves the Task-2-carried-forward casing fix: Provo's
// original a2_loadAreaGoals() reads getConfig('GOAL_' + key.toUpperCase()),
// but CCSM_AGENT_CONFIG_ROWS seeds GOAL_<metric_key> in LOWERCASE (matching
// Metric_Key casing, e.g. GOAL_new_people_found). CCSM_Agent2.gs must read
// getConfig('GOAL_' + key) (lowercase) instead. The test seeds a large
// avgT1 so that with the CORRECT (lowercase) lookup the area is "Beating
// Goal" and its Suggested_Goal is capped at Current_Goal * 1.5 (7.5); with
// the BROKEN (uppercase) lookup Current_Goal would read as 0, the trend
// would NOT be "Beating Goal" (that branch requires currentGoal > 0), and
// the ×1.10 multiplier would apply with NO cap (currentGoal <= 0 disables
// the cap entirely) — producing 22, not 7.5. Asserting Suggested_Goal ===
// 7.5 therefore fails under the old uppercase lookup and passes only once
// the lowercase fix is in place.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

// ---------------------------------------------------------------------------
// Agent2 — per-transfer goal recalibration
// ---------------------------------------------------------------------------
(function testAgent2() {
  const env = makeGasEnv();
  const scope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_Agent3.gs', 'CCSM_Agent2.gs'],
    env.globals
  );
  const ss = makeCcsmSpreadsheet(env, scope);

  // yyyy-MM-dd for a local Date, matching a2_toDateString/a2_parseDate's
  // literal-string handling (no UTC shift).
  function ymd(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${dd}`;
  }

  const today = new Date();
  today.setHours(12, 0, 0, 0);

  // TRANSFER_START_DATE = 7 days ago -> a2_loadTransferBoundaries computes
  // t1Weeks = ceil(7days / 7days) = 1, so avgT1 = sum/1 = sum exactly.
  const t1Start = new Date(today);
  t1Start.setDate(t1Start.getDate() - 7);
  const t1StartStr = ymd(t1Start);

  // Older transfer (T2) — no TRANSFER_SCHEDULE seeded, so
  // a2_loadTransferBoundaries falls back to the fixed 42-day-back guess:
  // t2Start = t1Start - 42d, t2End = t1Start - 1d. Pick a date safely inside
  // that window.
  const t2Mid = new Date(t1Start);
  t2Mid.setDate(t2Mid.getDate() - 20);
  const t2MidStr = ymd(t2Mid);

  setConfig(env, ss, 'TRANSFER_START_DATE', t1StartStr);
  // GOAL_new_people_found seeded in LOWERCASE, matching CCSM_AGENT_CONFIG_ROWS'
  // real seeded key casing (CcsmData.gs) — this is the key CCSM_Agent2.gs
  // must read via getConfig('GOAL_' + key), not the uppercase Provo original.
  setConfig(env, ss, 'GOAL_new_people_found', '5');

  // Two transfers of DAILY_LOG history for a real, non-leadership CCSM area.
  // Current transfer: a large new_people_found value (20) so avgT1 (20) is
  // far above the seeded goal (5), forcing the "Beating Goal" trend and the
  // ×1.5 cap. Older transfer: a modest value, present purely to prove 2
  // transfers of history load and average correctly (not required for the
  // Beating-Goal branch, which short-circuits on T1 alone).
  addNightlyRaw(env, ss, [
    { zone: 'Angol', area: 'Alemania 1', report_date: ymd(today), new_people_found: 20, effort: 'Todo' },
    { zone: 'Angol', area: 'Alemania 1', report_date: t2MidStr, new_people_found: 3, effort: 'Algo' },
  ]);
  scope.runAgent3(); // populates DAILY_LOG from NIGHTLY_FORM_RAW (Agent2 reads DAILY_LOG directly)

  scope.runAgent2();

  const grid = ss.getSheetByName('GOAL_RECALIBRATION').getDataRange().getValues();
  const headers = grid[0];
  const col = (name) => headers.indexOf(name);
  const t2Col = headers.findIndex((h) => String(h).indexOf('Avg_Week_T2') === 0);

  assert.ok(col('Area') >= 0 && col('Metric_Key') >= 0 && col('Suggested_Goal') >= 0,
    'GOAL_RECALIBRATION must self-initialize its header row: ' + JSON.stringify(headers));

  const row = grid.slice(1).find(
    (r) => r[col('Area')] === 'Alemania 1' && r[col('Metric_Key')] === 'new_people_found'
  );
  assert.ok(row, 'expected a GOAL_RECALIBRATION row for Alemania 1 / new_people_found');

  // Current_Goal must reflect the seeded GOAL_new_people_found=5 — proves the
  // lowercase goal-key lookup actually ran (uppercase lookup would read 0).
  assert.strictEqual(row[col('Current_Goal')], 5, 'Current_Goal must read the lowercase-seeded GOAL_new_people_found');
  assert.strictEqual(row[col('Trend')], 'Beating Goal', 'avgT1 (20) >= Current_Goal (5) must trend "Beating Goal"');

  // Suggested_Goal must be capped at Current_Goal * 1.5 = 7.5, not
  // avgT1 * 1.05 = 21 (would exceed the cap) and not the broken-lookup value
  // of 22 (avgT1 * 1.10 with no cap, since currentGoal <= 0 disables it).
  assert.strictEqual(row[col('Suggested_Goal')], 7.5, 'Suggested_Goal must respect the x1.5 cap on the current (correctly-read) goal');

  // Second transfer of history was loaded and averaged: 3 total / 6 weeks = 0.5.
  assert.ok(t2Col >= 0, 'expected an Avg_Week_T2 column');
  assert.strictEqual(row[t2Col], 0.5, 'older-transfer DAILY_LOG history must be averaged into Avg_Week_T2');

  const src = require('fs').readFileSync('CCSM_Agent2.gs', 'utf8');
  assert.ok(!/Utah Provo/i.test(src));
  assert.ok(!/America\/Denver/.test(src));
  // The lowercase-lookup call must actually be present in the executable
  // code (not just documented in a comment) — checks the literal call site.
  assert.ok(/var val = getConfig\('GOAL_' \+ key\);/.test(src), 'must use the lowercase goal-key lookup in a2_loadAreaGoals');

  console.log('agent2 OK');
})();

// ---------------------------------------------------------------------------
// Agent4 — system health check
// ---------------------------------------------------------------------------
(function testAgent4() {
  const env = makeGasEnv();
  const scope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent4.gs'],
    env.globals
  );
  const ss = makeCcsmSpreadsheet(env, scope);

  // Deliberately NOT calling addNightlyRaw/addWeeklyRaw — those tabs are only
  // created when the real Google Forms are attached, so a freshly-built
  // COMPASS_CCSM spreadsheet never has NIGHTLY_FORM_RAW / WEEKLY_FORM_RAW.
  assert.strictEqual(ss.getSheetByName('NIGHTLY_FORM_RAW'), null);
  assert.strictEqual(ss.getSheetByName('WEEKLY_FORM_RAW'), null);

  scope.runAgent4();

  // Exactly one health report email, Spanish subject.
  assert.strictEqual(env.state.emails.length, 1, 'expected exactly one health report email');
  const email = env.state.emails[0];
  assert.ok(
    /PMG Compass — Informe de Salud del Sistema/.test(email.subject),
    'health email subject must be the Spanish subject: ' + email.subject
  );

  // CHECK 12 self-healed by creating the two missing raw tabs — and ONLY
  // those two. Read SELF_HEAL_LOG rather than parsing the HTML report so the
  // assertion is exact, not a substring match against prose.
  const healLog = ss.getSheetByName('SELF_HEAL_LOG').getDataRange().getValues();
  const healHeaders = healLog[0];
  const checkCol = healHeaders.indexOf('Check');
  const actionCol = healHeaders.indexOf('Action');
  const check12Rows = healLog.slice(1).filter((r) => r[checkCol] === 'CHECK 12');

  const createdTabs = check12Rows
    .map((r) => String(r[actionCol]))
    .filter((a) => a.indexOf('Created missing tab:') === 0)
    .map((a) => a.replace('Created missing tab: ', '').trim())
    .sort();
  assert.deepStrictEqual(
    createdTabs,
    ['NIGHTLY_FORM_RAW', 'WEEKLY_FORM_RAW'],
    'CHECK 12 must self-heal exactly the two missing raw tabs, nothing else'
  );

  // Tabs now actually exist.
  assert.ok(ss.getSheetByName('NIGHTLY_FORM_RAW'), 'NIGHTLY_FORM_RAW must have been created');
  assert.ok(ss.getSheetByName('WEEKLY_FORM_RAW'), 'WEEKLY_FORM_RAW must have been created');

  // A tab that DOES exist from the start (e.g. MISSION_ORG, DAILY_LOG) must
  // never be flagged/self-healed as missing.
  const allCreatedTabNames = check12Rows.map((r) => String(r[actionCol]));
  assert.ok(
    !allCreatedTabNames.some((a) => /MISSION_ORG|DAILY_LOG|AGENT_RUN_LOG/.test(a)),
    'must not falsely flag tabs that already exist'
  );

  // HEALTH_LOG got its run summary row (proves Agent4's own operational tabs
  // — not part of the CCSM_TAB_SPECS-derived checklist — still work).
  const healthLog = ss.getSheetByName('HEALTH_LOG').getDataRange().getValues();
  assert.ok(healthLog.length >= 1, 'HEALTH_LOG should have at least one summary row');

  // AGENT_RUN_LOG got a row for this run.
  const runLog = ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
  assert.ok(runLog.some((r) => r[1] === 'Agent4'), 'expected an Agent4 row in AGENT_RUN_LOG');

  // No Sister Ellis / Agent7 / Provo residue.
  const src = require('fs').readFileSync('CCSM_Agent4.gs', 'utf8');
  assert.ok(!/sister/i.test(src), 'must not reference Sister Ellis');
  assert.ok(!/ellis/i.test(src), 'must not reference Sister Ellis');
  assert.ok(!/agent7/i.test(src), 'must not reference Agent7');
  assert.ok(!/Utah Provo/i.test(src));
  assert.ok(!/America\/Denver/.test(src));

  console.log('agent4 OK');
})();
