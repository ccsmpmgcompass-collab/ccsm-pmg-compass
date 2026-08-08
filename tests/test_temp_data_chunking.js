// test_temp_data_chunking.js — saveTempData() must self-heal orphaned chunks
// left behind by a crashed prior write, not just clean up after itself.
//
// saveTempData() deletes `key + '__chunks'` before writing new chunk
// properties. If a PREVIOUS call died mid-write (a thrown exception, or the
// script hitting Script Properties' own 500KB-wide quota while writing chunk
// N), that call's `__chunks` counter is already gone and never gets
// rewritten — so the NEXT call, which only knows to delete
// `key + '__0' .. '__(oldChunks-1)'` based on the counter it just read, has
// no way to find or remove that prior attempt's leftover chunk properties.
// They become permanent garbage eating into the shared 500KB budget forever.
// This is the mechanism suspected in Agent1A's real
// "You have exceeded the property storage quota" failure on 2026-08-03,
// which killed that week's entire coaching chain before Agent1B/1C ran.
//
// The fix scans for every `key__<digits>` property instead of trusting the
// counter, so orphans from ANY prior failed attempt are always found and
// removed on the next successful write — regardless of how they got there.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs'], env.globals);
makeCcsmSpreadsheet(env, scope);
const props = env.globals.PropertiesService.getScriptProperties();

// ===========================================================================
// (a) Orphaned chunks with NO `__chunks` counter (the crash-mid-write shape)
// ===========================================================================
{
  // Simulate a prior call that died after writing 3 chunks but before it
  // reached the line that sets `A1A_DATA__chunks` — exactly what a thrown
  // exception or a quota error mid-loop leaves behind.
  props.setProperty('A1A_DATA__0', 'stale-chunk-0');
  props.setProperty('A1A_DATA__1', 'stale-chunk-1');
  props.setProperty('A1A_DATA__2', 'stale-chunk-2');
  // No 'A1A_DATA__chunks' property — the crash happened before it was set.

  scope.saveTempData('A1A_DATA', { week: '2026-08-10', areas: 1 });

  assert.strictEqual(props.getProperty('A1A_DATA__0'), null,
    'orphaned chunk 0 from the simulated crash must be removed, not left as permanent garbage');
  assert.strictEqual(props.getProperty('A1A_DATA__1'), null,
    'orphaned chunk 1 from the simulated crash must be removed, not left as permanent garbage');
  assert.strictEqual(props.getProperty('A1A_DATA__2'), null,
    'orphaned chunk 2 from the simulated crash must be removed, not left as permanent garbage');

  const loaded = scope.loadTempData('A1A_DATA');
  assert.deepStrictEqual(loaded, { week: '2026-08-10', areas: 1 },
    'the new small value must load back correctly once orphans are cleared');

  console.log('tempDataChunking(orphan cleanup, no counter) OK');
}

// ===========================================================================
// (b) A real chunked value shrinks — old high-numbered chunks must not survive
// ===========================================================================
{
  const big = 'x'.repeat(30000); // forces multiple 8000-char chunks
  scope.saveTempData('BIG_KEY', big);
  const chunksAfterFirst = parseInt(props.getProperty('BIG_KEY__chunks'), 10);
  assert.ok(chunksAfterFirst >= 4, 'expected the 30000-char value to need at least 4 chunks');

  // Next write is much smaller — fits in a single un-chunked property.
  scope.saveTempData('BIG_KEY', 'small');

  for (let i = 0; i < chunksAfterFirst; i++) {
    assert.strictEqual(props.getProperty('BIG_KEY__' + i), null,
      'chunk ' + i + ' from the previous, larger write must not survive a shrink');
  }
  assert.strictEqual(props.getProperty('BIG_KEY__chunks'), null,
    'the __chunks counter itself must be cleared once the value no longer needs chunking');
  assert.strictEqual(scope.loadTempData('BIG_KEY'), 'small');

  console.log('tempDataChunking(shrink cleanup) OK');
}
