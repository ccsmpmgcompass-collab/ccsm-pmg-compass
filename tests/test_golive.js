// test_golive.js — CCSM_GoLive.gs, the two go-live config switches.
//
// These two functions are the only things in the system that decide whether
// real mail reaches real missionaries, and they run exactly twice ever, on
// dates that cannot slip. There is no second chance to notice a bug, so the
// properties below are asserted rather than trusted:
//
//   - a dry run writes NOTHING
//   - Step A activates leader rows ONLY, and it is the live count (45), not
//     "some subset"
//   - Step B activates everything
//   - both are idempotent
//   - apply REFUSES when mail cannot actually be delivered at that scale
//   - a misread leader flag (which would silence everyone, or activate
//     everyone, during a leaders-only trial) is refused rather than applied

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, setConfig } = require('./fixtures');

const GS = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs',
  'CCSM_AgentTestMode.gs', 'CCSM_GoLive.gs'];

const GOOD_RELAY = 'https://script.google.com/macros/s/AKfycbxDEADBEEF/exec';

function setup(opts) {
  opts = opts || {};
  const env = makeGasEnv();
  const scope = loadGs(GS, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  if (opts.relayUrl !== undefined) setConfig(env, ss, 'RELAY_2_URL', opts.relayUrl);
  if (opts.relaySecret !== undefined) setConfig(env, ss, 'RELAY_SECRET', opts.relaySecret);
  if (opts.relay1 !== undefined) setConfig(env, ss, 'RELAY_1_URL', opts.relay1);

  // Give every area a mailbox, like the live roster, so the capacity check has
  // something real to count.
  const org = ss.getSheetByName('MISSION_ORG');
  const data = org.getDataRange().getValues();
  const h = data[0];
  const c1 = h.indexOf('Companion1_Email');
  const areaIdx = h.indexOf('Area_Name');
  for (let i = 1; i < data.length; i++) {
    const slug = String(data[i][areaIdx]).toLowerCase().replace(/[^a-z0-9]/g, '');
    org.getRange(i + 1, c1 + 1).setValue(slug + '@missionary.org');
  }
  return { env, scope, ss };
}

// Read AGENT_CONFIG straight from the sheet, NOT through getConfig().
// CCSM_Helpers.readAgentConfig() memoizes the whole tab for the duration of one
// execution — correct in Apps Script, where globals reset between runs, but it
// means getConfig() inside this single node process still returns the values
// read before goLiveApply* wrote. The cell is the thing under test anyway.
function configCell(ss, key) {
  const data = ss.getSheetByName('AGENT_CONFIG').getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() === key) return String(data[i][1]).trim();
  }
  return null;
}

function activeCounts(ss, scope) {
  const org = ss.getSheetByName('MISSION_ORG');
  const data = org.getDataRange().getValues();
  const h = data[0];
  const activeIdx = h.indexOf('Active');
  const flagIdx = scope.GOLIVE_LEADER_FLAGS.map((f) => h.indexOf(f));
  const isTrue = (v) => v === true || String(v).trim().toUpperCase() === 'TRUE';
  let active = 0, leaders = 0, activeNonLeaders = 0;
  for (let i = 1; i < data.length; i++) {
    const a = isTrue(data[i][activeIdx]);
    const l = flagIdx.some((j) => isTrue(data[i][j]));
    if (a) active++;
    if (l) leaders++;
    if (a && !l) activeNonLeaders++;
  }
  return { total: data.length - 1, active, leaders, activeNonLeaders };
}

// ---------------------------------------------------------------------------
// 1. Dry run writes nothing at all.
// ---------------------------------------------------------------------------
{
  const { scope, ss } = setup({ relayUrl: GOOD_RELAY, relaySecret: 's3cret' });
  const before = JSON.stringify(ss.getSheetByName('MISSION_ORG').getDataRange().getValues());
  const cfgBefore = JSON.stringify(ss.getSheetByName('AGENT_CONFIG').getDataRange().getValues());

  const res = scope.goLiveDryRunStepA();

  assert.strictEqual(res.applied, false, 'a dry run must never apply');
  assert.ok(res.changes.length > 0, 'the dry run must have found pending changes to report');
  assert.strictEqual(
    JSON.stringify(ss.getSheetByName('MISSION_ORG').getDataRange().getValues()), before,
    'DRY RUN MUTATED MISSION_ORG'
  );
  assert.strictEqual(
    JSON.stringify(ss.getSheetByName('AGENT_CONFIG').getDataRange().getValues()), cfgBefore,
    'DRY RUN MUTATED AGENT_CONFIG'
  );
}

// ---------------------------------------------------------------------------
// 2. Step A: leaders only, TEST_MODE off, SYSTEM_START_DATE re-baselined.
// ---------------------------------------------------------------------------
{
  const { scope, ss } = setup({ relayUrl: GOOD_RELAY, relaySecret: 's3cret' });
  const res = scope.goLiveApplyStepA();
  assert.strictEqual(res.applied, true, 'Step A must apply when the relay is ready');

  const c = activeCounts(ss, scope);
  assert.strictEqual(c.activeNonLeaders, 0,
    'Step A must leave NO non-leader area active — that is the whole point of ' +
    'a leadership-only trial. ' + c.activeNonLeaders + ' remained active.');
  assert.strictEqual(c.active, c.leaders,
    'every leader row must be active: ' + c.active + ' active vs ' + c.leaders + ' leaders');
  assert.ok(c.active > 0 && c.active < c.total,
    'Step A must activate SOME but not ALL rows, got ' + c.active + '/' + c.total);

  assert.strictEqual(configCell(ss, 'TEST_MODE'), 'FALSE');
  assert.strictEqual(configCell(ss, 'SYSTEM_START_DATE'), '2026-08-05');
  // Explicitly NOT moved — it drives "since transfer" stats, not nagging.
  assert.notStrictEqual(configCell(ss, 'TRANSFER_START_DATE'), '2026-08-05',
    'TRANSFER_START_DATE must be left alone by Step A');
}

// ---------------------------------------------------------------------------
// 3. Idempotence: applying twice changes nothing the second time.
// ---------------------------------------------------------------------------
{
  const { scope, ss } = setup({ relayUrl: GOOD_RELAY, relaySecret: 's3cret' });
  scope.goLiveApplyStepA();
  const snapshot = JSON.stringify(ss.getSheetByName('MISSION_ORG').getDataRange().getValues());
  const second = scope.goLiveApplyStepA();
  assert.strictEqual(second.applied, false, 'a second apply must be a no-op');
  assert.strictEqual(second.changes.length, 0, 'a second apply must find no changes');
  assert.strictEqual(
    JSON.stringify(ss.getSheetByName('MISSION_ORG').getDataRange().getValues()), snapshot,
    'a second apply must not touch the sheet'
  );
}

// ---------------------------------------------------------------------------
// 4. Step B activates everything and re-baselines to the launch date.
// ---------------------------------------------------------------------------
{
  const { scope, ss } = setup({ relayUrl: GOOD_RELAY, relaySecret: 's3cret' });
  scope.goLiveApplyStepA();
  const res = scope.goLiveApplyStepB();
  assert.strictEqual(res.applied, true, 'Step B must apply');

  const c = activeCounts(ss, scope);
  assert.strictEqual(c.active, c.total,
    'Step B must activate every row: ' + c.active + '/' + c.total);
  assert.strictEqual(configCell(ss, 'SYSTEM_START_DATE'), '2026-08-17');
}

// ---------------------------------------------------------------------------
// 5. THE GATE: mission-wide with no relay must be REFUSED, not applied.
//
// This is the case that actually costs something. Agent1C needs ~97 sends for
// the full roster against a 100/day account limit shared with three other
// agents, so launching without a relay means missionaries silently receive
// nothing.
// ---------------------------------------------------------------------------
{
  const { scope, ss } = setup({ relayUrl: '', relaySecret: '' });
  const before = JSON.stringify(ss.getSheetByName('AGENT_CONFIG').getDataRange().getValues());

  const res = scope.goLiveApplyStepB();

  assert.strictEqual(res.ok, false, 'Step B without a relay must not report ok');
  assert.strictEqual(res.applied, false, 'Step B without a relay must NOT apply');
  assert.strictEqual(
    JSON.stringify(ss.getSheetByName('AGENT_CONFIG').getDataRange().getValues()), before,
    'a refused step must not have written anything'
  );
  assert.notStrictEqual(configCell(ss, 'TEST_MODE'), 'FALSE',
    'TEST_MODE must still be TRUE after a refusal — this is the irreversible flip'
  );
}

// ---------------------------------------------------------------------------
// 6. Step A with no relay is ALLOWED: 45 leader sends fit inside 100/day.
//    A gate that blocked the trial too would be wrong, and would push someone
//    to bypass it.
// ---------------------------------------------------------------------------
{
  const { scope } = setup({ relayUrl: '', relaySecret: '' });
  const res = scope.goLiveApplyStepA();
  assert.strictEqual(res.applied, true,
    'the leadership trial must NOT be blocked for want of a relay — it fits in ' +
    'the main account quota. Refusing it would just get the gate bypassed.');
}

// ---------------------------------------------------------------------------
// 7. A relay URL with no secret must NOT count as configured. sendEmail()
//    falls back to MailApp in that state, so it looks configured while still
//    spending the main quota.
// ---------------------------------------------------------------------------
{
  const { scope } = setup({ relayUrl: GOOD_RELAY, relaySecret: '' });
  const r = scope.goLiveCheckRelay();
  assert.strictEqual(r.ok, false, 'a relay URL without a secret must not pass the gate');
  assert.ok(r.problems.join(' ').match(/RELAY_SECRET/), r.problems.join(' | '));
}

// ---------------------------------------------------------------------------
// 8. An email address in RELAY_1_URL is reported. It is inert today (no code
//    reads RELAY_1_URL) so it must NOT block, but it must not be silent either.
// ---------------------------------------------------------------------------
{
  const { scope } = setup({ relayUrl: GOOD_RELAY, relaySecret: 's3cret',
                            relay1: 'CCSM.PMG.Relay@gmail.com' });
  const r = scope.goLiveCheckRelay();
  assert.strictEqual(r.ok, true, 'an inert RELAY_1_URL must not block go-live');
  assert.ok(r.lines.join(' ').match(/RELAY_1_URL is not a Web App URL/),
    'a malformed RELAY_1_URL must still be surfaced: ' + r.lines.join(' | '));
}

// ---------------------------------------------------------------------------
// 9. Misread leader flags are refused. If the flag columns were renamed or the
//    values stopped parsing, a LEADERS-scoped step would either silence the
//    whole mission or activate it — both catastrophic, both silent.
// ---------------------------------------------------------------------------
{
  const { scope, ss } = setup({ relayUrl: GOOD_RELAY, relaySecret: 's3cret' });
  const org = ss.getSheetByName('MISSION_ORG');
  const data = org.getDataRange().getValues();
  const h = data[0];
  scope.GOLIVE_LEADER_FLAGS.forEach((f) => {
    const j = h.indexOf(f);
    for (let i = 1; i < data.length; i++) org.getRange(i + 1, j + 1).setValue('FALSE');
  });

  const res = scope.goLiveApplyStepA();
  assert.strictEqual(res.applied, false,
    'a Step A that would activate ZERO rows must be refused, not applied');
  assert.ok(res.lines.join(' ').match(/leader flags are not being read as expected/),
    'the refusal must explain itself: ' + res.lines.join(' | '));
}

// ---------------------------------------------------------------------------
// 10. A missing Active column fails loudly rather than silently doing nothing.
// ---------------------------------------------------------------------------
{
  const { scope, ss } = setup({ relayUrl: GOOD_RELAY, relaySecret: 's3cret' });
  const org = ss.getSheetByName('MISSION_ORG');
  const activeIdx = org.getDataRange().getValues()[0].indexOf('Active');
  org.getRange(1, activeIdx + 1).setValue('Activo');   // renamed
  assert.throws(() => scope.goLiveDryRunStepA(), /no "Active" column/,
    'a renamed Active column must throw, not silently no-op');
}

console.log('golive OK — dry run is inert, Step A is leaders-only, gates hold');
