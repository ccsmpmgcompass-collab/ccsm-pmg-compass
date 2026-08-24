// test_spanish_terminology.js — locks the coaching letter's Spanish to the
// two things that define it: the nightly/weekly Google Forms the missionaries
// actually fill in, and the formal "usted" register those forms use.
//
// WHY THIS EXISTS. Every metric label used to be hand-copied into each agent
// file, and the copies drifted: 16 of the 20 nightly labels in CCSM_Agent1C.gs
// and 17 of 20 in CCSM_AgentMissionReport.gs no longer matched the form. Two
// had drifted into naming a different metric outright:
//
//   rc_lessons_mcp  rendered "Lecciones CR con Miembro"
//                   -- but the metric counts recent-convert lessons taught
//                      using MI SENDA DE LOS CONVENIOS, and the row beside it
//                      was the real "Lecciones con Miembro Presente".
//   pmf_lessons     rendered "Lecciones PMF"
//                   -- an untranslated English acronym (Part-Member Families)
//                      shown to Spanish-speaking missionaries.
//
// Both agents now resolve labels from CcsmData.gs CCSM_NIGHTLY_QUESTIONS
// instead of copying them. These tests fail if anyone reintroduces a copy.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const repo = path.join(__dirname, '..');
const env = makeGasEnv({});
const scope = loadGs(['CcsmData.gs', 'CCSM_Helpers.gs', 'CCSM_Agent1C.gs', 'CCSM_AgentMissionReport.gs'], env.globals);

// ===========================================================================
// 1. Both agents resolve every nightly metric to the form's own wording.
// ===========================================================================
const canonical = {};
scope.CCSM_NIGHTLY_QUESTIONS.forEach((q) => {
  if (q.key && q.displayEs) canonical[q.key] = q.displayEs;
});
assert.ok(Object.keys(canonical).length >= 20,
  'expected CcsmData.gs to define displayEs for the nightly questions');

Object.keys(canonical).forEach((key) => {
  assert.strictEqual(scope.a1c_scoreboardLabel_(key), canonical[key],
    'Agent1C label for ' + key + ' must be the nightly form wording');
  assert.strictEqual(scope.amr_metricLabel(key), canonical[key],
    'MissionReport label for ' + key + ' must be the nightly form wording');
});

// The two that were outright wrong, asserted by name so the regression is
// named in the failure output rather than buried in the loop above.
assert.strictEqual(scope.a1c_scoreboardLabel_('rc_lessons_mcp'),
  'Lecciones con CR (Mi Senda de los Convenios)',
  'rc_lessons_mcp is the Mi Senda de los Convenios metric, not a with-a-member metric');
assert.strictEqual(scope.a1c_scoreboardLabel_('pmf_lessons'),
  'Lecciones con Familias Parciales',
  'pmf_lessons must not render the untranslated English acronym "PMF"');

// ...and they must stay distinguishable from the real member-present metric.
assert.notStrictEqual(scope.a1c_scoreboardLabel_('rc_lessons_mcp'),
  scope.a1c_scoreboardLabel_('lessons_member_present'),
  'rc_lessons_mcp and lessons_member_present must not read as the same metric');

// An unknown key still renders something rather than a blank label.
assert.strictEqual(scope.a1c_scoreboardLabel_('some_future_metric'), 'some_future_metric');

console.log('metric labels match the nightly form OK');

// ===========================================================================
// 2. Rate-metric labels agree between Agent1A (coaching card headings) and
//    Agent1C (scoreboard rows), and every glossary term is one the letter
//    really renders.
// ===========================================================================
const a1aSrc = fs.readFileSync(path.join(repo, 'CCSM_Agent1A.gs'), 'utf8');
const rateBlock = a1aSrc.slice(a1aSrc.indexOf('var A1A_RATE_METRICS'));
['contact_rate', 'mc_rate', 'lesson_rate', 'close_rate', 'effort_score'].forEach((key) => {
  const m = new RegExp("key:\\s*'" + key + "',\\s*display:\\s*'([^']+)'").exec(rateBlock);
  assert.ok(m, 'expected A1A_RATE_METRICS to define a display for ' + key);
  assert.strictEqual(scope.a1c_scoreboardLabel_(key), m[1],
    'Agent1C and Agent1A must name ' + key + ' identically -- both appear in the same letter');
});

// Glossary: the left-hand term of a rate entry must be exactly what the
// letter renders for that metric, or it defines a word the reader never sees.
const glossTerms = scope.A1C_GLOSSARY.map((p) => p[0]);
['contact_rate', 'mc_rate', 'lesson_rate', 'close_rate', 'effort_score'].forEach((key) => {
  const label = scope.a1c_scoreboardLabel_(key);
  assert.ok(glossTerms.indexOf(label) >= 0,
    'the glossary must define "' + label + '" (' + key + ') under the name the letter uses');
});

console.log('rate labels + glossary agree OK');

// ===========================================================================
// 3. Formal register. The Spanish forms address the missionary as "usted"
//    throughout, so the letter must not switch to "tú" in its own furniture.
//    Checked against the SOURCE of the letter-building files, since these are
//    fixed strings rather than data-dependent output.
// ===========================================================================
const letterSrc = fs.readFileSync(path.join(repo, 'CCSM_Agent1C.gs'), 'utf8');
const informal = [
  'Tu Semana', 'Tu Embudo', 'Tu Mejor', 'Tú contra Ti', 'tu área', 'tus ',
];
informal.forEach((frag) => {
  assert.ok(letterSrc.indexOf("'" + frag) === -1 && letterSrc.indexOf('>' + frag) === -1,
    'informal address "' + frag + '" must not appear in the letter -- the forms use usted');
});

// Anglicisms the Spanish letter should not carry.
assert.ok(!/Coaching de Liderazgo/.test(letterSrc),
  '"Coaching" is an anglicism -- use "Capacitación de Líderes"');
assert.ok(!/Prom\. Transfer|este transfer/.test(letterSrc),
  '"transfer" is an anglicism -- a transfer is a "cambio"');

// The Gemini prompts build Spanish sentences around the scope token, so the
// raw English 'zone'/'district'/'mission' must never be interpolated into
// them (it used to read "narrativa para el líder de zone").
assert.strictEqual(scope.a1c_scopeNoun_('zone'), 'zona');
assert.strictEqual(scope.a1c_scopeNoun_('district'), 'distrito');
assert.strictEqual(scope.a1c_scopeNoun_('mission'), 'misión');
// Logger.log lines legitimately use the raw token -- those are internal
// English diagnostics, not letter copy. Only prose lines are checked.
letterSrc.split(/\r?\n/).forEach((line, i) => {
  if (/Logger\.log/.test(line)) return;
  assert.ok(!/' \+ scope \+ '|' \+ scopeType \+ '/.test(line),
    'raw scope token enters Spanish prose at CCSM_Agent1C.gs:' + (i + 1) +
    ' -- route it through a1c_scopeNoun_');
});

console.log('formal register + anglicisms OK');

console.log('spanish terminology OK');
