// test_soft_hyphenation.js — locks the fix that stopped leadership letters
// scrolling sideways on a phone.
//
// WHY THIS EXISTS. The leadership area table's min-content width is set by the
// LONGEST WORD in each column header, not by the numbers underneath. Measured
// on the live mission letter (43 areas, 9 columns), removing a column saved
// exactly the width of its longest header word -- 73px for "Significativas",
// 60px for "Encontradas", 58px for "Invitaciones". That held the table at
// 436px against a 327px budget (a 375px phone less 48px of container padding)
// and was the single cause of all 109px of horizontal overflow.
//
// The two obvious fixes were both destructive: dropping two of the five metric
// columns loses data leaders asked for, and re-abbreviating the headers would
// undo 75a3884, which deliberately restored the nightly form's own wording so
// the letter and the form name metrics identically.
//
// Instead a1c_softHyphenate_ inserts U+00AD SOFT HYPHEN at Spanish syllable
// boundaries. The character is invisible until the browser actually needs to
// break the word, so the header still READS "Conversaciones Significativas" --
// it just gains permission to wrap mid-word on a narrow screen. Measured after:
// 436px -> 305px, with every column and every word preserved.
//
// These tests fail if anyone strips the hyphenation, breaks the syllable rules
// (which would show a hyphen in the wrong place on a real phone), or lets the
// hyphenation corrupt the wording the terminology tests guarantee.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const assert = require('assert');

const env = makeGasEnv({});
const scope = loadGs(['CcsmData.gs', 'CCSM_Helpers.gs', 'CCSM_Agent1C.gs'], env.globals);

const SHY = '­';
const hy = scope.a1c_softHyphenate_;
const strip = (s) => String(s).split(SHY).join('');

assert.strictEqual(typeof hy, 'function',
  'a1c_softHyphenate_ must exist -- it is what keeps the letter inside a phone');

// ===========================================================================
// 1. The wording survives. This is the whole point: a soft hyphen must never
//    change what the header SAYS, only where it MAY break.
// ===========================================================================
scope.A1C_TABLE_METRICS.forEach((m) => {
  assert.strictEqual(strip(hy(m.label)), m.label,
    'soft-hyphenating "' + m.label + '" must not change the text it renders');
});

['Área', 'Zona', 'Esf.', '✓', 'TOTAL DE LA MISIÓN', 'TOTAL DE ZONA'].forEach((s) => {
  assert.strictEqual(strip(hy(s)), s, 'hyphenation must preserve "' + s + '"');
});

// ===========================================================================
// 2. The long words actually gain break points -- otherwise the table silently
//    goes back to 436px and the phone scrolls sideways again.
// ===========================================================================
['Conversaciones', 'Significativas', 'Encontradas', 'Invitaciones', 'Lecciones']
  .forEach((w) => {
    assert.ok(hy(w).indexOf(SHY) >= 0,
      '"' + w + '" is a header word wide enough to set the table floor and must be breakable');
  });

// ===========================================================================
// 3. The break points are correct Spanish. A soft hyphen in the wrong place is
//    visible to the reader the moment the word wraps, so these are asserted
//    exactly rather than merely "contains a hyphen".
// ===========================================================================
const syllables = {
  // consonant pairs that split: con-TAC-tos
  'Contactos':      'Con-tac-tos',
  // diphthongs stay whole: "cio" is one syllable, never ci-o
  'Conversaciones': 'Con-ver-sa-cio-nes',
  'Invitaciones':   'In-vi-ta-cio-nes',
  'Lecciones':      'Lec-cio-nes',
  // single consonant joins the following vowel
  'Significativas': 'Sig-ni-fi-ca-ti-vas',
  'Personas':       'Per-so-nas',
  // "tr" is inseparable, so it travels with the vowel after it
  'Encontradas':    'En-con-tra-das',
  // "au" is a diphthong
  'Bautismo':       'Bau-tis-mo'
};

Object.keys(syllables).forEach((word) => {
  assert.strictEqual(hy(word).split(SHY).join('-'), syllables[word],
    word + ' must break on Spanish syllable boundaries');
});

// ===========================================================================
// 4. Short words are left alone -- a hyphen offered inside "Zona" or "Esf."
//    buys no width and only risks an ugly break.
// ===========================================================================
['Zona', 'Área', 'con', 'al', 'Esf.', 'Amigos', 'Nuevas'].forEach((w) => {
  assert.strictEqual(hy(w), w, 'short word "' + w + '" must not be hyphenated');
});

// Nor may a break orphan a single letter at either end of a word.
Object.keys(syllables).concat(['Conversaciones', 'Encontradas']).forEach((w) => {
  hy(w).split(SHY).forEach((part) => {
    assert.ok(part.length >= 2,
      'hyphenating "' + w + '" left the one-letter fragment "' + part + '"');
  });
});

// ===========================================================================
// 5. It is actually WIRED IN to the table, at every leadership scope. A helper
//    that is correct but uncalled leaves the letter exactly as broken.
// ===========================================================================
const C = {
  header: '#1e3a5f', green: '#16a34a', blue: '#2563eb', yellow: '#a16207',
  red: '#dc2626', muted: '#6b7280', border: '#e5e7eb', bgLight: '#f9fafb'
};

const areaDetails = [{
  name: 'Área Uno', zone: 'Zona Uno', district: 'Distrito Uno',
  stats: {
    submissions: 3, contacts_made: 40, meaningful_conversations: 20,
    new_people_found: 5, friend_lessons: 12, baptismal_invitations: 1,
    effort_score: 2.4
  },
  growth: null, strength1: null, strength2: null
}];

['mission', 'zone', 'district'].forEach((sc) => {
  const html = scope.a1c_buildAreaDataTable_(areaDetails, sc, C);
  assert.ok(html.indexOf(SHY) >= 0,
    sc + '-scope area table must soft-hyphenate its headers');
  // and the rendered wording is still the form's, once the invisible char goes
  scope.A1C_TABLE_METRICS.forEach((m) => {
    assert.ok(strip(html).indexOf(m.label) >= 0,
      sc + '-scope table must still render the full label "' + m.label + '"');
  });
});

// The data cells must NOT be hyphenated -- they hold numbers and area names,
// where a stray hyphen would read as part of the value.
const missionHtml = scope.a1c_buildAreaDataTable_(areaDetails, 'mission', C);
const bodyOnly = missionHtml.slice(missionHtml.indexOf('</tr>'));
assert.strictEqual(bodyOnly.indexOf(SHY), -1,
  'only the header row may be soft-hyphenated; data cells must be left alone');

console.log('test_soft_hyphenation: OK');
