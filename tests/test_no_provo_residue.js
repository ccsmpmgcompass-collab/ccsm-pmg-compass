// test_no_provo_residue.js — CCSM must carry no Utah Provo identifiers.
//
// The CCSM agents were forked from the live Provo PMG Compass. The hard rule
// of that fork: no Provo data or identifiers survive in CCSM code. Provo is a
// live production system serving real missionaries, and its addresses, names
// and timezone are confidential to that mission.
//
// WHY THIS IS A TEST AND NOT A GREP. The sweep used to be an ad-hoc command
// recorded in the task ledger:
//
//     grep -E "Utah Provo|America/Denver|Sister Ellis|missionary\.org.*@"
//
// It reported CLEAN at every task — and it was clean, for those four patterns.
// It never mentioned pmg.compass@gmail.com, so the Provo mission inbox sat
// hardcoded as the Reply-To on every CCSM email, and as the send target of a
// zero-argument testRelay(), through fifteen reviews. The finding was not
// "somebody ran the wrong grep"; it was that the pattern list lived in a
// commit message where nothing could execute it or notice it was incomplete.
//
// So: patterns live here, they run with the suite, and adding a newly-learned
// pattern is a one-line change that protects every future commit.
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const ROOT = path.join(__dirname, '..');

// Files that ship into the Apps Script project. Docs and tests are excluded:
// they legitimately DISCUSS Provo (this file names the addresses it forbids).
const SHIPPING = fs.readdirSync(ROOT)
  .filter((f) => f.endsWith('.gs'))
  .sort();

assert.ok(SHIPPING.length > 0, 'expected .gs files at the repo root');

const FORBIDDEN = [
  // — Mission identity —
  { re: /Utah Provo/i,            why: 'Provo mission name' },
  { re: /America\/Denver/,        why: "Provo's timezone — CCSM is America/Santiago" },
  // NOT a bare /Provo/: the .gs headers document what was changed relative to
  // the Provo originals and why, which is provenance worth keeping. Only
  // Provo *identifiers* — its name, timezone, addresses, cut subsystems — are
  // residue. Scrubbing the word would delete the explanation of the fork.

  // — Provo-only subsystems that were cut from CCSM —
  { re: /Sister Ellis/i,          why: 'Sister Ellis system was cut from CCSM' },
  { re: /SISTER_ELLIS_LOG/,       why: 'Sister Ellis tab was cut from CCSM' },
  { re: /\bAgent7\b/,             why: 'Agent7 was cut from CCSM' },

  // — Addresses. The gap that let the Reply-To bug through: the old sweep
  //   checked missionary.org but never the pmg.compass Gmail accounts. —
  // Lookbehind excludes CCSM's OWN ccsm.pmg.compass@gmail.com, which is
  // legitimate and appears as the TEST_INBOX_EMAIL default in several files.
  { re: /(?<!ccsm\.)\bpmg\.compass[\w.]*@gmail\.com/i,
    why: "Provo's Gmail accounts — CCSM uses ccsm.pmg.compass@gmail.com" },
  // Requires a local part: an actual address, not the bare domain, which the
  // .gs headers mention when explaining where missionary emails come from.
  { re: /[\w.+-]+@missionary\.org/i,
    why: 'real missionary addresses must never be committed' },
];

const failures = [];

SHIPPING.forEach((file) => {
  const lines = fs.readFileSync(path.join(ROOT, file), 'utf8').split(/\r?\n/);
  lines.forEach((line, i) => {
    FORBIDDEN.forEach(({ re, why }) => {
      if (re.test(line)) {
        failures.push(file + ':' + (i + 1) + '  [' + why + ']\n      ' + line.trim());
      }
    });
  });
});

assert.strictEqual(failures.length, 0,
  'Provo residue found in shipping .gs files (' + failures.length + '):\n\n  ' +
  failures.join('\n  ') + '\n\nRemove it, or if a match is a deliberate false ' +
  'positive, narrow the pattern in tests/test_no_provo_residue.js.\n');

console.log('test_no_provo_residue OK — ' + SHIPPING.length + ' .gs files, ' +
  FORBIDDEN.length + ' patterns');
