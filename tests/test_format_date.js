// test_format_date.js — harness fidelity for Utilities.formatDate.
//
// FINAL-REVIEW FINDING (integration H-3). The stub's pattern tokenizer did not
// implement java.text.SimpleDateFormat quoted literals, which is what Apps
// Script's Utilities.formatDate actually uses. Real CCSM code formats with
// "MMMM d, yyyy 'a las' h:mm a" (CCSM_AgentReminder.gs), and the stub
// tokenized the a/l/s inside 'a las', producing "'PM lPM9'".
//
// The .gs was correct; the STUB was wrong. Zero tests touched that string,
// which is the only reason the suite was green. That inversion is the danger:
// the next person to write a test against a reminder body would have seen
// garbage, trusted the harness, and "fixed" working production code.
//
// These tests exist so the harness's own formatting contract is pinned rather
// than assumed. A stub is only evidence if something checks the stub.
const { makeGasEnv } = require('./gas_stubs');
const assert = require('assert');

const { globals } = makeGasEnv();
const U = globals.Utilities;
const TZ = 'America/Santiago';
const D = new Date(2026, 6, 23, 14, 5); // Thu 23 Jul 2026, 14:05 local

function check(pattern, expected) {
  const got = U.formatDate(D, TZ, pattern);
  assert.strictEqual(got, expected,
    'formatDate(' + JSON.stringify(pattern) + ') -> ' + JSON.stringify(got) +
    ', expected ' + JSON.stringify(expected));
}

// ── The pattern that actually ships ─────────────────────────────────────────
// CCSM_AgentReminder.gs — the string the stub used to mangle.
check("MMMM d, yyyy 'a las' h:mm a", 'July 23, 2026 a las 2:05 PM');

// ── Quoted-literal semantics ────────────────────────────────────────────────
check("'literal'", 'literal');
check("h 'o''clock'", "2 o'clock");   // '' inside a run = one literal quote
check("''", "'");                      // '' outside a run = one literal quote
check("'unterminated", 'unterminated'); // SimpleDateFormat: rest is literal
check("'a' yyyy 'b'", 'a 2026 b');     // multiple runs, tokens in between

// Every letter that IS a token must survive verbatim inside quotes. This is
// the actual failure mode — 'a las' broke because a/l/s were tokenized.
check("'aaa EEEE MMMM yyyy hh mm ss'", 'aaa EEEE MMMM yyyy hh mm ss');

// ── Unquoted tokens still work (guard against over-correcting) ──────────────
check('yyyy-MM-dd', '2026-07-23');
check('EEEE, MMMM d', 'Thursday, July 23');
check('h:mm a', '2:05 PM');

// ── The real reminder string renders with no stray quote characters ─────────
// Broad backstop: whatever the tokenizer does, a formatted CCSM date must
// never leak a lone apostrophe from an unconsumed pattern delimiter.
const reminderStamp = U.formatDate(D, TZ, "MMMM d, yyyy 'a las' h:mm a");
assert.ok(reminderStamp.indexOf("'") === -1,
  'formatted reminder timestamp must not contain a stray quote: ' + reminderStamp);
assert.ok(/\ba las\b/.test(reminderStamp),
  'the Spanish literal "a las" must survive intact: ' + reminderStamp);

console.log('test_format_date OK');
