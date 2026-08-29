// test_message_bank_split.js — MESSAGE_BANK / LEADERSHIP_MESSAGE_BANK can be
// split into their own spreadsheet, with no Apps Script attached, so mission
// leadership can be given Editor access to just that content.
//
// WHY THIS EXISTS. Google ties "can edit this spreadsheet" to "can open its
// bound Apps Script project" — there is no native way to share edit access to
// two tabs of COMPASS_CCSM without also handing over every .gs file and
// Script Properties (including GEMINI_API_KEY). CCSM_Helpers.gs's getTab()
// is the single chokepoint every tab-access helper in the codebase routes
// through, so making IT resolve MESSAGE_BANK/LEADERSHIP_MESSAGE_BANK against
// a configurable external spreadsheet (CCSM_SPLIT_TABS /
// ccsmSpreadsheetForTab_ / MESSAGE_BANK_SPREADSHEET_ID) is what makes every
// other function — seeders, getters, the smoke test, Agent4's self-heal —
// correct with no per-call-site change. This suite proves that chokepoint
// actually redirects (not just "doesn't crash"), that the migration function
// copies LIVE content verbatim (not a re-seed, which would drop hand edits),
// and that the two split-aware call sites outside CCSM_Helpers.gs
// (CCSM_Setup.gs's smokeTestPipeline, CCSM_Agent4.gs's CHECK 12) don't
// false-fail or self-heal a stray local tab once the split is in effect.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, setConfig } = require('./fixtures');
const assert = require('assert');

const CORE_FILES = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
                     'CCSM_Agent1A.gs', 'CCSM_SeedContent.gs'];
const FULL_FILES = [
  'CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
  'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs', 'CCSM_Agent2.gs',
  'CCSM_Agent3.gs', 'CCSM_Agent4.gs', 'CCSM_Agent5A.gs', 'CCSM_Agent5B.gs',
  'CCSM_Agent6.gs', 'CCSM_AgentDuplicate.gs', 'CCSM_AgentEscalation.gs',
  'CCSM_AgentMissionReport.gs', 'CCSM_AgentQA.gs', 'CCSM_AgentReminder.gs',
  'CCSM_AgentScores.gs', 'CCSM_AgentValidation.gs', 'CCSM_SeedContent.gs',
  'CCSM_Setup.gs',
];

function firstCountMetric(scope) {
  return scope.CCSM_NIGHTLY_QUESTIONS.filter((q) => q.type === 'NUMBER')[0].key;
}

// ===========================================================================
// 1. Default (no split configured): behavior is byte-for-byte what it always
//    was — everything resolves to the bound spreadsheet. This is the state
//    every existing test in the suite already runs under; asserted directly
//    here too so a regression in ccsmSpreadsheetForTab_'s fallback branch is
//    caught by name, not just incidentally by every other suite.
// ===========================================================================
{
  const env = makeGasEnv();
  const scope = loadGs(CORE_FILES, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);

  scope.seedCcsmMessageBank();

  const bound = ss.getSheetByName('MESSAGE_BANK');
  assert.strictEqual(bound.getLastRow() - 1, 193,
    'with no MESSAGE_BANK_SPREADSHEET_ID set, seeding must still land in the bound spreadsheet');
  console.log('unsplit default behavior unchanged OK');
}

// ===========================================================================
// 2. Split active: seeders write to the EXTERNAL spreadsheet, the bound
//    tab is left untouched (still just its header row from buildCcsmSheet()),
//    and the getters read the external content back correctly. Proves real
//    redirection, not "also writes a copy locally."
// ===========================================================================
{
  const env = makeGasEnv();
  const scope = loadGs(CORE_FILES, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);

  const external = env.globals.SpreadsheetApp.create('CCSM Mission Trainings (test)');
  // getTab() never creates a tab, only finds one — simulates that the split
  // migration (splitMessageBanksToOwnSpreadsheet(), covered in block 3) has
  // already created these two tabs in the external spreadsheet; this block is
  // testing what happens on the NEXT write/read after that, not the creation
  // itself.
  external.insertSheet('MESSAGE_BANK');
  external.insertSheet('LEADERSHIP_MESSAGE_BANK');
  setConfig(env, ss, 'MESSAGE_BANK_SPREADSHEET_ID', external.getId());

  scope.seedCcsmMessageBank();
  scope.seedCcsmLeadershipMessageBank();

  assert.strictEqual(ss.getSheetByName('MESSAGE_BANK').getLastRow(), 1,
    'the bound spreadsheet\'s MESSAGE_BANK must stay at just its header row once split is configured');
  assert.strictEqual(ss.getSheetByName('LEADERSHIP_MESSAGE_BANK').getLastRow(), 1,
    'the bound spreadsheet\'s LEADERSHIP_MESSAGE_BANK must stay at just its header row once split is configured');

  const extMb = env.globals.SpreadsheetApp.openById(external.getId()).getSheetByName('MESSAGE_BANK');
  assert.strictEqual(extMb.getLastRow() - 1, 193, 'the external spreadsheet must receive the real 193 rows');
  const extLmb = env.globals.SpreadsheetApp.openById(external.getId()).getSheetByName('LEADERSHIP_MESSAGE_BANK');
  assert.strictEqual(extLmb.getLastRow() - 1, 10, 'the external spreadsheet must receive the real 10 leadership rows');

  // Functional read-through: the getters must not merely "not crash" but
  // actually return content sourced from the external spreadsheet.
  const metricKey = firstCountMetric(scope);
  const strengthMsgs = scope.getMessageBank('SUNDAY_COACHING_STRENGTH', metricKey);
  assert.ok(strengthMsgs.length > 0, 'getMessageBank must read real rows through the split');

  const leadershipMsgs = scope.getLeadershipMessageBank();
  assert.strictEqual(leadershipMsgs.length, 10, 'getLeadershipMessageBank must read all 10 rows through the split');

  console.log('split redirection + functional read-through OK')
}

// ===========================================================================
// 3. splitMessageBanksToOwnSpreadsheet(): copies LIVE content verbatim
//    (including a hand edit made directly in the sheet, which a re-seed would
//    have overwritten), leaves the source tabs untouched (deletion is a
//    manual step per its own docstring, not automatic), and skips a tab that
//    doesn't exist yet rather than failing outright.
// ===========================================================================
{
  const env = makeGasEnv();
  const scope = loadGs(CORE_FILES, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);

  scope.seedCcsmMessageBank();
  // Simulate a hand edit made directly in the live sheet, the exact scenario
  // this function exists to preserve — a re-seed would silently discard this.
  ss.getSheetByName('MESSAGE_BANK').getRange(2, 6).setValue('HAND-EDITED BODY TEXT');

  // LEADERSHIP_MESSAGE_BANK exists (buildCcsmSheet() creates it from
  // CCSM_TAB_SPECS) but is unseeded, i.e. empty except its header — this
  // models a mission that has migrated MESSAGE_BANK but not yet run
  // seedCcsmLeadershipMessageBank(). Delete it entirely to also exercise the
  // "tab genuinely absent" skip path a real pre-migration sheet would hit.
  ss.deleteSheet(ss.getSheetByName('LEADERSHIP_MESSAGE_BANK'));

  const newId = scope.splitMessageBanksToOwnSpreadsheet();
  assert.ok(newId, 'splitMessageBanksToOwnSpreadsheet must return the new spreadsheet id');

  const newSs = env.globals.SpreadsheetApp.openById(newId);
  assert.strictEqual(newSs.getName(), 'CCSM Mission Trainings');

  const copiedMb = newSs.getSheetByName('MESSAGE_BANK');
  assert.ok(copiedMb, 'MESSAGE_BANK must be copied into the new spreadsheet');
  assert.strictEqual(copiedMb.getLastRow() - 1, 193, 'row count must be preserved exactly');
  assert.strictEqual(copiedMb.getRange(2, 6).getValue(), 'HAND-EDITED BODY TEXT',
    'the migration must copy the LIVE cell value, not re-derive it from code — this is the whole point');

  assert.strictEqual(newSs.getSheetByName('LEADERSHIP_MESSAGE_BANK'), null,
    'a genuinely absent source tab must be skipped, not fabricated');
  assert.ok(env.state.logs.some((l) => /skipping LEADERSHIP_MESSAGE_BANK/.test(l)),
    'the skip must be logged so a human running this by hand can see why');

  // Source tabs are untouched — deletion is a deliberate manual step later.
  const sourceMb = ss.getSheetByName('MESSAGE_BANK');
  assert.strictEqual(sourceMb.getLastRow() - 1, 193, 'the source MESSAGE_BANK must be left exactly as it was');
  assert.strictEqual(sourceMb.getRange(2, 6).getValue(), 'HAND-EDITED BODY TEXT',
    'the source hand edit must still be there — the function must not have moved or cleared it');

  console.log('splitMessageBanksToOwnSpreadsheet copies live content + skips absent tabs OK');
}

// ===========================================================================
// 4. CCSM_Setup.gs smokeTestPipeline() must not false-fail once the split is
//    live and the local copies have been deleted (the documented end state of
//    a completed migration) — and must still correctly fail if
//    MESSAGE_BANK_SPREADSHEET_ID points at nothing.
// ===========================================================================
{
  const env = makeGasEnv();
  const scope = loadGs(FULL_FILES, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');
  setConfig(env, ss, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
  setConfig(env, ss, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');
  scope.setupAllCcsmTriggers();
  scope.setupCcsmScoreConfig();
  scope.seedCcsmKnowledgeBase();
  scope.seedCcsmMessageBank();
  scope.seedCcsmLeadershipMessageBank();

  const newId = scope.splitMessageBanksToOwnSpreadsheet();
  setConfig(env, ss, 'MESSAGE_BANK_SPREADSHEET_ID', newId);
  // The documented end state: delete the now-inert local copies.
  ss.deleteSheet(ss.getSheetByName('MESSAGE_BANK'));
  ss.deleteSheet(ss.getSheetByName('LEADERSHIP_MESSAGE_BANK'));

  // readAgentConfig()/ccsmMessageBankSpreadsheet_() cache once per execution
  // by design (Apps Script globals reset between separate real runs — see
  // both functions' own comments) — this scope already resolved and cached
  // MESSAGE_BANK_SPREADSHEET_ID as unset while seeding, above. A fresh scope
  // over the same underlying env.state models the NEXT real execution, which
  // is the one that actually reads the config value just saved.
  const scope2 = loadGs(FULL_FILES, env.globals);
  const healthy = scope2.smokeTestPipeline();
  assert.deepStrictEqual(healthy.errors, [],
    'smokeTestPipeline must not report MESSAGE_BANK/LEADERSHIP_MESSAGE_BANK missing once split and cleaned up: ' +
    healthy.errors.join(' | '));
  assert.strictEqual(healthy.ok, true);

  // Negative control: prove the check actually discriminates rather than
  // vacuously passing regardless of the config value. Same reasoning — a new
  // scope so the changed config value is actually read.
  setConfig(env, ss, 'MESSAGE_BANK_SPREADSHEET_ID', 'not-a-real-id');
  const scope3 = loadGs(FULL_FILES, env.globals);
  const broken = scope3.smokeTestPipeline();
  assert.ok(broken.errors.some((e) => /MESSAGE_BANK/.test(e)),
    'a bad MESSAGE_BANK_SPREADSHEET_ID must surface as a smoke-test ERROR naming MESSAGE_BANK, got: ' +
    broken.errors.join(' | '));

  console.log('smokeTestPipeline is split-aware, in both directions OK');
}

// ===========================================================================
// 5. CCSM_Agent4.gs CHECK 12 must not self-heal a stray local placeholder tab
//    once the split is live — that would recreate exactly the tab the split
//    was meant to retire, silently, every week the health check runs.
// ===========================================================================
{
  const env = makeGasEnv();
  const scope = loadGs(FULL_FILES, env.globals);
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');
  // a4_requiredTabs_() also expects these two (only real once a Google Form
  // is attached) — created here so this block's assertions are about
  // MESSAGE_BANK/LEADERSHIP_MESSAGE_BANK specifically, not incidental noise
  // from an otherwise-minimal fixture.
  ss.insertSheet('NIGHTLY_FORM_RAW');
  ss.insertSheet('WEEKLY_FORM_RAW');
  scope.seedCcsmMessageBank();
  scope.seedCcsmLeadershipMessageBank();

  const newId = scope.splitMessageBanksToOwnSpreadsheet();
  setConfig(env, ss, 'MESSAGE_BANK_SPREADSHEET_ID', newId);
  ss.deleteSheet(ss.getSheetByName('MESSAGE_BANK'));
  ss.deleteSheet(ss.getSheetByName('LEADERSHIP_MESSAGE_BANK'));

  // Fresh scope — see block 4's comment on why (config caches per execution).
  const scope2 = loadGs(FULL_FILES, env.globals);
  const selfHealLog = [];
  const result = scope2.a4_check12_requiredTabs(selfHealLog);

  assert.strictEqual(result.status, 'OK',
    'CHECK 12 must treat the split tabs as present, not missing: ' + result.detail);
  assert.strictEqual(selfHealLog.length, 0,
    'CHECK 12 must not attempt to self-heal (recreate) a tab that only moved to the split spreadsheet');
  assert.strictEqual(ss.getSheetByName('MESSAGE_BANK'), null,
    'no stray local MESSAGE_BANK placeholder must have been created back in COMPASS_CCSM');
  assert.strictEqual(ss.getSheetByName('LEADERSHIP_MESSAGE_BANK'), null,
    'no stray local LEADERSHIP_MESSAGE_BANK placeholder must have been created back in COMPASS_CCSM');

  console.log('Agent4 CHECK 12 does not self-heal split tabs OK');
}

console.log('\ntest_message_bank_split: all blocks passed');
