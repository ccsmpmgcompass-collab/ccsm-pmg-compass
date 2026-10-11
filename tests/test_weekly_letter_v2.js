// test_weekly_letter_v2.js — the weekly letter in model v2
// (PLAN-2026-10-11-weekly-letter.md). Replaces the suites for the sections
// v2 dropped (glossary, the old KI block, scoreboard, trend chart,
// You-vs-You, funnel). Builds the letter straight from a hand-made A1B
// payload, so every number below is one this file chose.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, setConfig } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
    'CCSM_Agent1A.gs', 'CCSM_Agent1C.gs'],
  env.globals);
const ss = makeCcsmSpreadsheet(env, scope);
setConfig(env, ss, 'WEEKLY_FORM_LINK', 'https://forms.example/semanal');

const WEEKS = ['2026-09-06', '2026-09-13', '2026-09-20', '2026-09-27', '2026-10-04'];
const WEEK_END = '2026-10-04';
const KI = ['ki_new_people', 'ki_member_lessons', 'ki_friends_sacrament', 'ki_friends_first_week',
  'ki_baptismal_date', 'ki_baptized_confirmed', 'ki_rc_at_church'];
const ki = (vals) => { const o = {}; KI.forEach((k, i) => { o[k] = vals[i] || 0; }); return o; };

/** WEEKLY_KI-shaped rows for a1a_kiWeeks_: { week: { real, meta } }. */
function rows(spec) {
  const out = {};
  Object.keys(spec).forEach((w) => { out[w] = { real: ki(spec[w][0]), meta: ki(spec[w][1]) }; });
  return out;
}

/** One area of the A1B payload, with four weeks of nightly numbers. */
function area(zone, district, kiRows, nights, extra) {
  const kiWeeks = scope.a1a_kiWeeks_(kiRows, WEEKS);
  const nightWeeks = WEEKS.slice(1).map((w, i) => ({
    week: w, nights: nights[i],
    m: nights[i] ? { contacts_attempted: 40 + i, contacts_made: 20, meaningful_conversations: 10 + 2 * i,
      friend_lessons: 6, baptismal_invitations: 1, church_invites: 8 } : {},
  }));
  return Object.assign({
    zone, district, stats: { submissions: nights[3], effort_all: nights[3], effort_score: 3 },
    kiWeeks, nightWeeks, focus: null, goals: { contacts_attempted: 50, contact_rate: 0.5 },
    nextGoals: { contacts_attempted: 55 },
    derived: { consistency: { dayFlags: 'LMXJVSD'.split('').map((l, i) => ({ label: l, reported: i < nights[3] })) } },
  }, extra || {});
}

// ===========================================================================
// 1. a1a_kiWeeks_: a week's result is graded against the PREVIOUS week's form.
// ===========================================================================
{
  const w = scope.a1a_kiWeeks_(rows({
    '2026-09-27': [[99], [10]],
    '2026-10-04': [[8], [40]],
  }), WEEKS);
  assert.strictEqual(w.length, 4);
  assert.strictEqual(w[3].real.ki_new_people, 8);
  assert.strictEqual(w[3].goal.ki_new_people, 10, 'the goal comes from last week\'s form');
  assert.strictEqual(w[3].next.ki_new_people, 40, 'this week\'s form sets next week\'s goal');
  assert.strictEqual(w[1].filed, false);
  assert.strictEqual(w[2].goal, null, 'no form two weeks back = no goal last week');
  console.log('kiWeeks OK');
}

// ===========================================================================
// 2. a1a_pickFocus_: the KI furthest below goal that has a nightly chain, and
//    its weakest feeder -- passing over last week's growth topic.
// ===========================================================================
{
  const kw = scope.a1a_kiWeeks_(rows({
    '2026-09-27': [[], [10, 10, 4, 1, 4, 1, 1]],
    '2026-10-04': [[9, 2, 4, 0, 1, 0, 1], []],
  }), WEEKS);
  const ranked = [
    { key: 'baptismal_invitations', pct: 0.2 }, { key: 'baptism_doctrine_lessons', pct: 0.5 },
    { key: 'member_contacts', pct: 0.9 }, { key: 'lessons_member_present', pct: 0.4 },
  ];
  const f = scope.a1a_pickFocus_(kw, ranked, '');
  assert.strictEqual(f.ki, 'ki_member_lessons', 'member lessons 2/10 is furthest below goal');
  assert.strictEqual(f.feeder, 'lessons_member_present', 'its weakest feeder with a goal');
  const g = scope.a1a_pickFocus_(kw, ranked, 'lessons_member_present');
  assert.strictEqual(g.feeder, 'member_contacts', 'last week\'s topic is passed over');
  assert.strictEqual(scope.a1a_pickFocus_(null, ranked, ''), null, 'no form, no KI focus');
  console.log('focus OK');
}

// ===========================================================================
// The mission: one zone, two districts.
//   Norte:  Alfa (goal 10, got 8), Beta (no form last week: got 5, no goal)
//   Sur:    Gamma (never filed in four weeks)
// ===========================================================================
const AREAS = {
  Alfa: area('Zeta', 'Norte', rows({
    '2026-09-06': [[], [10, 4, 2]], '2026-09-13': [[6, 4, 1], [10, 4, 2]],
    '2026-09-20': [[7, 4, 0], [10, 4, 2]], '2026-09-27': [[5, 3, 1], [10, 4, 2]],
    '2026-10-04': [[8, 4, 3], [12, 4, 2]],
  }), [7, 7, 6, 7], { code: 'A1' }),
  Beta: area('Zeta', 'Norte', rows({
    '2026-10-04': [[5, 1, 0], [6, 1, 1]],
  }), [5, 4, 5, 3], { code: 'B1' }),
  Gamma: area('Zeta', 'Sur', {}, [0, 0, 0, 2], { code: 'G1' }),
};
const SUMMARIES = { mission: {}, zones: {}, districts: {} };
const letter = (person) => scope.a1c_v2letter_(person, AREAS, SUMMARIES, WEEK_END, []);

// ===========================================================================
// 3. Totals follow the KI PDFs' rule (decision 2).
// ===========================================================================
{
  const idx = scope.a1c_v2index_(AREAS, WEEK_END);
  const norte = idx.districts.Norte;
  const c = scope.a1c_v2kiCell_(norte, 3, 'ki_new_people');
  assert.strictEqual(c.big, '8', 'Beta had no goal: its 5 stays out of the graded total');
  assert.strictEqual(c.small, 'de 10');
  assert.strictEqual(norte.weeks[3].ki.ki_new_people.r, 13, 'the raw total still counts it');
  const beta = scope.a1c_v2kiCell_(idx.sectors.Beta, 3, 'ki_new_people');
  assert.strictEqual(beta.pct, null, 'Beta\'s own cell is grey');
  assert.strictEqual(beta.small, 'sin meta');
  const gamma = scope.a1c_v2kiCell_(idx.sectors.Gamma, 3, 'ki_new_people');
  assert.strictEqual(gamma.big, '—', 'no form: no number, never a zero');
  assert.strictEqual(idx.mission.weeks[3].filedCount, 2);
  console.log('PDF totals rule OK');
}

// ===========================================================================
// 4. A companionship letter: their own week, nobody else's.
// ===========================================================================
{
  const L = letter({ name: 'Alfa', areas: ['Alfa'], roles: [] });
  assert.ok(/^Alfa · /.test(L.subject), 'the subject leads with the sector: ' + L.subject);
  assert.ok(/su mejor semana en un mes/.test(L.subject), 'and its news (8 is above 6, 7, 5): ' + L.subject);
  assert.ok(L.html.includes('✓ Recibimos sus informes'));
  assert.ok(L.html.includes('Sus 7 indicadores clave'));
  assert.ok(L.html.includes('Sus metas para esta semana'), 'next week\'s goals from their own form');
  assert.ok(L.html.includes('Su informe nocturno · todos sus números'));
  assert.ok(L.html.includes('>55<'), 'next week\'s nightly goal in "Meta próx."');
  ['Beta', 'Gamma', 'Su distrito', 'Todos los datos'].forEach((x) => {
    assert.ok(!L.html.includes(x), 'a companionship sees only itself: found ' + x);
  });
  assert.ok(!/En la misión esta semana/.test(L.html), 'no mission news in any letter');
  assert.ok(L.html.includes('display:none'), 'the inbox preview line rides in a hidden preheader');
  console.log('companionship letter OK');
}

// ===========================================================================
// 5. A missing weekly form is one kind line with the link, never an empty box.
// ===========================================================================
{
  const L = letter({ name: 'Gamma', areas: ['Gamma'], roles: [] });
  assert.ok(L.html.includes('todavía no nos llegó'), 'the kind missing-form line');
  assert.ok(L.html.includes('https://forms.example/semanal'), 'with the form\'s link');
  assert.ok(!L.html.includes('No recibimos su informe semanal de indicadores clave'), 'never the old empty box');
  assert.ok(L.html.includes('Su informe nocturno · todos sus números'), 'the rest of the letter still comes');
  console.log('missing form OK');
}

// ===========================================================================
// 6. A DL letter: own sector, the district's quick read, all its data.
// ===========================================================================
{
  const L = letter({ name: 'Alfa', areas: ['Alfa'], roles: [{ type: 'DL', zone: 'Zeta', district: 'Norte' }] });
  assert.ok(L.html.includes('1 · Su sector: Alfa'));
  assert.ok(L.html.includes('2 · Su distrito: Norte'));
  assert.ok(L.html.includes('3 · Todos los datos del distrito'));
  assert.ok(L.html.includes('Resumen por sector'), 'the per-area table opens section 3 (decision 6)');
  assert.ok(L.html.includes('Beta'), 'a leader sees the district\'s sectors');
  assert.ok(L.html.includes('Esta semana, como líder de distrito'));
  assert.ok(/Llamar[\s\S]*Beta/.test(L.html), 'Beta reported 3 of 7 nights: call');
  assert.ok(!/Intercambio sugerido[\s\S]{0,400}<b>Alfa<\/b>/.test(L.html), 'never an exchange with their own sector');
  assert.ok(/^Alfa · /.test(L.subject));
  assert.ok(/^Distrito Norte: 2 de 2 informaron/.test(L.preheader), L.preheader);
  console.log('DL letter OK');
}

// ===========================================================================
// 7. ZL, STL and AP letters: their sections and only their attachments' note.
// ===========================================================================
{
  const zl = letter({ name: 'Alfa', areas: ['Alfa'], roles: [{ type: 'ZL', zone: 'Zeta', district: 'Norte' }] });
  assert.ok(zl.html.includes('2 · Su zona: Zeta'));
  assert.ok(zl.html.includes('Indicadores clave por distrito'));
  assert.ok(/Gamma<\/b>: ningún informe semanal en 4 semanas/.test(zl.html), 'four silent weeks are named');
  const stl = letter({ name: 'Alfa', areas: ['Alfa'], roles: [{ type: 'STL', zone: 'Zeta', district: 'Norte' }] });
  assert.ok(stl.html.includes('Esta semana, como hermanas capacitadoras'));
  const ap = scope.a1c_v2letter_({ name: 'AP', areas: [], roles: [{ type: 'AP', zone: 'ALL', district: '' }] },
    AREAS, SUMMARIES, WEEK_END, [{ scope: 'MISSION', fileName: 'Indicadores_clave_mision.pdf', pages: 11 }]);
  assert.ok(ap.html.includes('Resumen de la Misión'));
  assert.ok(ap.html.includes('1 · La misión') && ap.html.includes('2 · Por zona') && ap.html.includes('3 · Todos los datos de la misión'));
  assert.ok(ap.html.includes('📄 Indicadores_clave_mision.pdf · 11 págs.'));
  assert.ok(/^Misión · /.test(ap.subject), ap.subject);
  console.log('ZL / STL / AP letters OK');
}

// ===========================================================================
// 8. Size: Gmail hides everything past ~102 KB. The biggest live zone has 12
//    sectors in 4 districts; this one has 13 in 4, and must stay under 100 KB.
// ===========================================================================
{
  const big = {};
  for (let i = 0; i < 13; i++) {
    const a = JSON.parse(JSON.stringify(AREAS.Alfa));
    a.district = 'D' + (i % 4);
    big['Sector ' + i] = a;
  }
  const L = scope.a1c_v2letter_({ name: 'x', areas: ['Sector 0'], roles: [{ type: 'ZL', zone: 'Zeta', district: 'D0' }] },
    big, SUMMARIES, WEEK_END, []);
  const kb = Buffer.byteLength(L.html, 'utf8') / 1024;
  assert.ok(kb < 100, 'a 13-sector ZL letter is ' + kb.toFixed(1) + ' KB; Gmail clips past ~102 KB');
  console.log('size budget OK (' + kb.toFixed(1) + ' KB)');
}

console.log('weekly letter v2 OK');
