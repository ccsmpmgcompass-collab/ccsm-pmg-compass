// test_leadership_citations_withheld.js — keeps unverified Predicad Mi
// Evangelio page numbers and written-out scripture out of the leadership
// letter.
//
// WHY THIS EXISTS. Every entry in CCSM_Agent1C.gs's _LEADERSHIP_MSGS carries
// three citation fields alongside its coaching prose: `pmg` (a page number),
// `scripture` (a reference) and `scriptText` (the verse, written out).
// CONTENT_REVIEW.md's "MENSAJES DE LIDERAZGO" section already records that
// none of the three is trustworthy — the page numbers come from the ENGLISH
// edition, the verse text was drafted by a model rather than copied from the
// official Spanish edition, and at least two references do not match the text
// quoted alongside them. That review document flags the problem but does not
// stop the same text going out in the weekly email, which is what this test
// closes.
//
// The prose itself carries no direct quote and is unaffected: subject and body
// still render exactly as written. Only the citation line is withheld, and
// only until each reference has been verified — _LEADERSHIP_MSGS keeps all
// three fields populated (asserted below) so restoring them is a change to
// three lines at the one call site in a1c_buildLeadershipSection.
//
// SCOPE. This covers the STATIC message bank. The Gemini leadership narrative
// asks for a "PMG p.{página} | {escritura}" line of its own, freshly invented
// every week; that prompt is rewritten when the "Lectura de la semana"
// paragraph replaces the standalone narrative box, and gets its own assertion
// then.
//
// The picker chooses at random within a theme (a1c_pickRelevantLeadershipMsg_),
// so this walks every theme AND every message inside it — 10 renders, one per
// entry — rather than trusting one lucky draw.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent1C.gs'],
  env.globals);
// a1c_buildEmail's footer calls getMissionName(), which reads AGENT_CONFIG.
makeCcsmSpreadsheet(env, scope);

const MSGS = scope._LEADERSHIP_MSGS;
const LEADER_EMAIL = 'lider@missionary.org';
const WEEK_END = new Date(2026, 7, 23);

// ===========================================================================
// 1. The source data must stay INTACT. The fix withholds the citations at the
//    render call site on purpose, so that verifying them later is a one-place
//    change and nothing has to be re-researched from scratch.
// ===========================================================================
assert.strictEqual(MSGS.length, 10, '_LEADERSHIP_MSGS should still hold 10 messages');
MSGS.forEach((m) => {
  assert.ok(m.subject && m.body, m.theme + ': coaching prose must survive untouched');
  assert.ok(m.scripture,  m.theme + ': the scripture reference must stay in the data');
  assert.ok(m.scriptText, m.theme + ': the scripture text must stay in the data');
});
assert.ok(MSGS.some((m) => m.pmg), 'the PMG page numbers must stay in the data');

// ===========================================================================
// 2. Nothing unverified may reach the rendered letter.
// ===========================================================================
// Derived from the bank itself, so a new message cannot slip past this test.
const FORBIDDEN = [];
function forbid(needle, why) {
  // The assertions below are all negative, so a needle that a1c_esc would
  // have escaped could pass for the wrong reason. Keep them escape-free.
  assert.ok(!/[&<>"']/.test(needle), 'needle must be escape-free to be checked: ' + needle);
  FORBIDDEN.push({ needle: needle, why: why });
}
forbid('Predicad Mi Evangelio', 'the PMG page numbers come from the English edition');
forbid('PMG p.', 'the legacy page-reference form');
forbid('✏️', 'the pencil glyph that labels the scripture reference');
MSGS.forEach((m) => {
  forbid(m.scripture, 'unverified scripture reference');
  forbid(m.scriptText.slice(0, 30), 'scripture text not copied from the official Spanish edition');
});

function areasFor(growthKey) {
  return {
    'Área Uno': {
      zone: 'Zona Uno', district: 'Distrito Uno',
      stats: { submissions: 7, contacts_made: 40, meaningful_conversations: 20,
               new_people_found: 5, friend_lessons: 12, baptismal_invitations: 1,
               effort_score: 2.4 },
      growth: growthKey ? { key: growthKey, display: 'Enfoque' } : null,
      strength1: null, strength2: null, ki: null
    }
  };
}

// submitted / total_areas stays at 1 so a1c_pickRelevantLeadershipMsg_ takes
// the growth-focus branch instead of forcing 'Cultura de Zona' on low
// reporting.
const summaries = {
  mission:   { total_areas: 1, submitted: 1, contacts_made: 40 },
  zones:     { 'Zona Uno':     { total_areas: 1, submitted: 1, contacts_made: 40 } },
  districts: { 'Distrito Uno': { total_areas: 1, submitted: 1, contacts_made: 40 } }
};

const person = scope.a1c_buildPeopleMap([{
  Area_Name: 'Área Uno', Zone: 'Zona Uno', District: 'Distrito Uno',
  Companion1_Name: 'Elder Uno', Companion1_Email: LEADER_EMAIL,
  Companion2_Name: '', Companion2_Email: '',
  Is_DL: 'FALSE', Is_ZL: 'TRUE', Is_STL: 'FALSE',
  Is_AP: 'FALSE', Is_MP: 'FALSE', Active: 'TRUE'
}])[LEADER_EMAIL];

// One growth key per theme, matching a1c_pickRelevantLeadershipMsg_'s own key
// groupings. `null` leaves every count at zero, which falls back to 'Fe'.
const GROWTH_KEY_BY_THEME = {
  'Buscar':            'contact_rate',
  'Enseñar':           'mc_rate',
  'Indicadores Clave': 'close_rate',
  'Cultura de Zona':   'effort_score',
  'Fe':                null
};

const realRandom = Math.random;
let rendered = 0;
try {
  Object.keys(GROWTH_KEY_BY_THEME).forEach((theme) => {
    const areas = areasFor(GROWTH_KEY_BY_THEME[theme]);
    const inTheme = MSGS.filter((m) => m.theme === theme);
    assert.ok(inTheme.length > 0, 'no messages for theme ' + theme);

    inTheme.forEach((msg, i) => {
      // Land squarely on index i of this theme's messages.
      Math.random = () => (i + 0.5) / inTheme.length;
      const html = scope.a1c_buildEmail(person, areas, summaries, WEEK_END);

      // Positive control: this exact message really did render, so the
      // negative assertions below are not passing vacuously.
      assert.ok(html.indexOf('Capacitación de Líderes') !== -1,
        theme + ' #' + i + ': the leadership coaching block must still render');
      assert.ok(html.indexOf(msg.subject) !== -1,
        theme + ' #' + i + ': expected the message "' + msg.subject + '" to render');
      assert.ok(html.indexOf(msg.body.slice(0, 40)) !== -1,
        theme + ' #' + i + ': the coaching prose must render in full');

      FORBIDDEN.forEach((f) => {
        assert.strictEqual(html.indexOf(f.needle), -1,
          theme + ' #' + i + ': letter must not contain "' + f.needle + '" — ' + f.why);
      });
      rendered++;
    });
  });
} finally {
  Math.random = realRandom;
}
assert.strictEqual(rendered, MSGS.length,
  'every message in the bank must have been rendered and checked');

// ===========================================================================
// 3. a1c_buildMessageBlock itself is UNCHANGED and must stay that way: it is
//    shared with the missionary Fortaleza / Crecimiento cards, which read from
//    MESSAGE_BANK. Those already ship with blank scripture text, but the
//    citation machinery must keep working for the day the leadership
//    references are verified and switched back on.
// ===========================================================================
const C = { header: '#1e3a5f', muted: '#6b7280' };
const withCitation = scope.a1c_buildMessageBlock('Etiqueta', {
  subjectLine: 'Asunto', bodyText: 'Cuerpo',
  pmgPage: '157', pmgDescription: '', scripture: 'D. y C. 4:4-5', scriptureText: 'Texto'
}, C, C.header);
assert.ok(withCitation.indexOf('Predicad Mi Evangelio, p.157') !== -1,
  'a1c_buildMessageBlock must still render a citation when it is given one');
assert.ok(withCitation.indexOf('D. y C. 4:4-5') !== -1,
  'a1c_buildMessageBlock must still render a scripture reference when given one');

const withoutCitation = scope.a1c_buildMessageBlock('Etiqueta', {
  subjectLine: 'Asunto', bodyText: 'Cuerpo',
  pmgPage: null, pmgDescription: '', scripture: '', scriptureText: ''
}, C, C.header);
assert.ok(withoutCitation.indexOf('Asunto') !== -1 && withoutCitation.indexOf('Cuerpo') !== -1,
  'withholding the citation must not touch the prose');
assert.strictEqual(withoutCitation.indexOf('✏️'), -1,
  'no citation line when there is nothing to cite');

console.log('test_leadership_citations_withheld: OK');
