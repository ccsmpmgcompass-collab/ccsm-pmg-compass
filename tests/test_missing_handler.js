// test_missing_handler.js — smokeTestPipeline() must fail when a trigger names
// a handler this project does not define.
//
// This reproduces the real 2026-07-26 CCSM failure. Agent1B logged
// "Agent1C scheduled in ~1 min" and Agent1C then appeared NOWHERE in
// AGENT_RUN_LOG -- not even an ERROR row, which runAgent1C would have written
// for any exception inside itself, since its logRun() sits outside its
// try/catch. The function never started: Apps Script could not find it, because
// CCSM_Agent1C.gs had never been pasted into the online editor. Apps Script
// reports that as "Script function not found" in the Executions list only, so
// nothing reached the sheet, no email went out, and smokeTestPipeline()
// reported "All 10 scheduled triggers installed" in green.
//
// A trigger inventory structurally cannot catch this: the trigger really does
// exist. Only asking whether the HANDLER exists can.
//
// The test works by loading every .gs file EXCEPT CCSM_Agent1C.gs -- which is
// exactly what the live project looked like -- and asserting the smoke test
// now fails and names runAgent1C.

const assert = require('assert');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, setConfig } = require('./fixtures');

const ALL_GS = [
  'CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
  'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs', 'CCSM_Agent2.gs',
  'CCSM_Agent3.gs', 'CCSM_Agent4.gs', 'CCSM_Agent5A.gs', 'CCSM_Agent5B.gs',
  'CCSM_Agent6.gs', 'CCSM_AgentDuplicate.gs', 'CCSM_AgentEscalation.gs',
  'CCSM_AgentMissionReport.gs', 'CCSM_AgentQA.gs', 'CCSM_AgentReminder.gs',
  'CCSM_AgentScores.gs', 'CCSM_AgentValidation.gs', 'CCSM_SeedContent.gs',
  'CCSM_Setup.gs',
];

function runSmokeTest(gsFiles) {
  const env = makeGasEnv();
  const scope = loadGs(gsFiles, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');
  setConfig(env, ss, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
  setConfig(env, ss, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');
  scope.setupAllCcsmTriggers();
  return { report: scope.smokeTestPipeline(), env, scope };
}

// ---------------------------------------------------------------------------
// 1. Control: with every file loaded, the handler check passes and says so.
//    Without this, a check that always failed would satisfy the test below.
// ---------------------------------------------------------------------------
const whole = runSmokeTest(ALL_GS);
const handlerErrorsWhole = whole.report.errors.filter((e) => /NOT DEFINED/.test(e));
assert.deepStrictEqual(
  handlerErrorsWhole, [],
  'with every .gs loaded, no handler may be reported missing: ' + handlerErrorsWhole.join(' | ')
);
assert.ok(
  whole.report.lines.some((l) => /handlers are defined/.test(l)),
  'the healthy run must positively report that handlers were checked, not stay silent'
);

// ---------------------------------------------------------------------------
// 2. The real failure: CCSM_Agent1C.gs never pasted.
// ---------------------------------------------------------------------------
const without1C = runSmokeTest(ALL_GS.filter((f) => f !== 'CCSM_Agent1C.gs'));

assert.strictEqual(
  without1C.report.ok, false,
  'smokeTestPipeline must NOT report ok=true when a scheduled handler is undefined'
);

const named = without1C.report.errors.filter((e) => /runAgent1C/.test(e));
assert.ok(
  named.length > 0,
  'the smoke test must name the missing handler by name. Errors were: ' +
  without1C.report.errors.join(' | ')
);
assert.ok(
  /pasted into this Apps Script editor/.test(named[0]),
  'the error must explain the cause -- the file was never pasted -- because ' +
  'that is not inferable from "function not found". Got: ' + named[0]
);

// ---------------------------------------------------------------------------
// 3. The trigger inventory still passes in that same run, proving the new
//    check is what caught it and not some incidental side effect.
// ---------------------------------------------------------------------------
assert.ok(
  without1C.report.lines.some((l) => /OK\s+All \d+ scheduled triggers installed/.test(l)),
  'the trigger inventory should still be green -- the runAgent1C TRIGGER does ' +
  'exist. If this line is gone, the test is no longer proving what it claims.'
);

// ---------------------------------------------------------------------------
// 4. Chained handlers are covered too. runAgent1C is chained, not scheduled --
//    it has no standing trigger to be missing -- so a check that only walked
//    CCSM_TRIGGER_SCHEDULE would miss precisely the agent that actually broke.
// ---------------------------------------------------------------------------
assert.ok(
  whole.scope.CCSM_CHAINED_HANDLERS.indexOf('runAgent1C') >= 0,
  'runAgent1C must be in CCSM_CHAINED_HANDLERS for this test to mean anything'
);

// ---------------------------------------------------------------------------
// 5. cs_handlerIsDefined_ directly: it must not report a non-function global
//    (a var, an object) as a valid handler, and must reject junk safely.
// ---------------------------------------------------------------------------
const isDefined = whole.scope.cs_handlerIsDefined_;
assert.strictEqual(isDefined('runAgent3'), true);
assert.strictEqual(isDefined('runAgent1C'), true);
assert.strictEqual(isDefined('noSuchFunctionAnywhere'), false);
assert.strictEqual(isDefined('CCSM_CHAINED_HANDLERS'), false,
  'an array global is not a callable handler');
assert.strictEqual(isDefined('1); throw new Error("x"); //'), false,
  'a non-identifier must be rejected by the guard, not evaluated');

console.log('missing handler OK — smoke test catches an unpasted agent file');
