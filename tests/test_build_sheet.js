const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const assert = require('assert');

const env = makeGasEnv();
const s = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs'], env.globals);
s.buildCcsmSheet();

const id = Object.keys(env.state.spreadsheets)[0];
const ss = env.globals.SpreadsheetApp.openById(id);

// every tab exists, default 'Sheet1' removed
const specs = s.CCSM_TAB_SPECS;
specs.forEach(t => assert.ok(ss.getSheetByName(t.name), 'missing tab ' + t.name));
assert.strictEqual(ss.getSheets().length, specs.length);

// header rows written where specified; empty tabs truly empty
const cfg = ss.getSheetByName('AGENT_CONFIG').getDataRange().getValues();
assert.deepStrictEqual(cfg[0], ['Key', 'Value']);
assert.ok(cfg.some(r => r[0] === 'MISSION_TIMEZONE' && r[1] === 'America/Santiago'));
assert.strictEqual(ss.getSheetByName('DAILY_LOG').getLastRow(), 0);

// MISSION_ORG fully populated
const org = ss.getSheetByName('MISSION_ORG').getDataRange().getValues();
assert.strictEqual(org.length - 1, s.CCSM_MISSION_ORG_ROWS.length);

// QUESTIONS_CONFIG: one row per nightly+weekly question, Form_Column_Header verbatim ES
const qc = ss.getSheetByName('QUESTIONS_CONFIG').getDataRange().getValues();
const qcHeaders = qc[0];
const colHdr = qcHeaders.indexOf('Form_Column_Header');
const colType = qcHeaders.indexOf('Form_Type');
assert.strictEqual(qc.length - 1, s.CCSM_NIGHTLY_QUESTIONS.length + s.CCSM_WEEKLY_QUESTIONS.length);
assert.ok(qc.some(r => r[colHdr] === 'Prácticas de enseñanza realizadas hoy' && r[colType] === 'NIGHTLY'));
assert.ok(qc.some(r => r[colHdr] === 'Nuevas personas encontradas (Meta)' && r[colType] === 'WEEKLY'));

// verify pass reports clean
assert.strictEqual(s.verifyCcsmSheet_(id), true);
console.log('build sheet OK');

// --- Step 5: dropped-writes resilience -------------------------------------
for (let i = 0; i < 10; i++) {
  const dEnv = makeGasEnv({ dropWriteRate: 0.4 });
  const ds = loadGs(['CcsmData.gs', 'BuildCcsmSheet.gs'], dEnv.globals);
  ds.buildCcsmSheet();
  const dId = Object.keys(dEnv.state.spreadsheets)[0];
  const ok = ds.verifyCcsmSheet_(dId);
  assert.strictEqual(ok, true, 'verify did not converge on iteration ' + i);

  const dss = dEnv.globals.SpreadsheetApp.openById(dId);
  const expected = ds.ccsmExpectedState_();
  Object.keys(expected).forEach((tabName) => {
    const want = expected[tabName];
    if (!want.length) return;
    const sh = dss.getSheetByName(tabName);
    const got = sh.getRange(1, 1, want.length, want[0].length).getValues();
    for (let r = 0; r < want.length; r++) {
      for (let c = 0; c < want[r].length; c++) {
        assert.ok(ds.ccsmCellsEqual_(got[r][c], want[r][c]),
          `mismatch iter ${i} tab ${tabName} row ${r} col ${c}: ${JSON.stringify(got[r][c])} !== ${JSON.stringify(want[r][c])}`);
      }
    }
  });
}
console.log('dropped-writes resilience OK (10/10 clean)');
